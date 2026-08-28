"""Non-publishing historical shadow evaluation for daily editorial contracts."""

# Standard Library
import os
import re
import json
import uuid
import shutil
import datetime

# local repo modules
import daily_blog.locks
import daily_blog.routes
import daily_blog.schema
import daily_blog.config
import daily_blog.activity
import daily_blog.evidence
import daily_blog.projection
import daily_blog.editorial
import daily_blog.contracts
import daily_blog.candidates
import daily_blog.io_utils
import daily_blog.mirrors
import daily_blog.repositories


SHADOW_SCHEMA_VERSION = "vosslab.daily-blog.shadow.v1"
EVALUATOR_TEMPLATE_NAME = "daily_blog_shadow_evaluator_v1.txt"
EVALUATOR_REPAIR_TEMPLATE_NAME = "daily_blog_shadow_evaluator_repair_v1.txt"
SCORE_FIELDS = (
	"factual_grounding",
	"changelog_use",
	"thematic_structure",
	"reader_interest",
	"house_style_match",
)
MAX_EVALUATOR_RESPONSE_CHARS = 5000
VISIBLE_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*")
SENTENCE_RE = re.compile(r"[^.!?]+(?:[.!?]+|$)")
FIRST_PERSON_RE = re.compile(
	r"(?<![A-Za-z0-9/])(?:I|me|my|mine|myself)(?![A-Za-z0-9/])",
	flags=re.IGNORECASE,
)
FIRST_PERSON_SUBJECT_RE = re.compile(
	r"(?<![A-Za-z0-9/])I(?![A-Za-z0-9/])",
	flags=re.IGNORECASE,
)
FENCED_CODE_RE = re.compile(r"(?ms)^[ \t]*(`{3,}|~{3,}).*?^[ \t]*\1[^\n]*(?:\n|$)")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
COMMENT_RE = re.compile(r"<!--.*?-->", flags=re.DOTALL)
COORDINATED_ACTION_RE = re.compile(
	r"(?:,\s*(?:and\s+)?(?:I\s+)?|\band\s+(?:I\s+)?)([A-Za-z]+(?:'[A-Za-z]+)?)",
	flags=re.IGNORECASE,
)
CONTRACTION_RE = re.compile(r"\bI'(m|ve|d|ll)\b", flags=re.IGNORECASE)
CONCRETE_VISIBLE_SIGNAL_RE = re.compile(
	r"\b\d+(?:\.\d+)?(?:%|[A-Za-z]+)?\b|"
	r"\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+\b|"
	r"\b[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z0-9_-]+)+\b|"
	r"(?:\b[A-Za-z0-9._-]+/)+[A-Za-z0-9._-]+\b|"
	r"\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+){2,}\b"
)
NO_INLINE_MARKDOWN_LINKS = None
STANDALONE_SHORT_PARAGRAPH_WORD_LIMIT = 12
ACTION_PREFIX_WORDS = {
	"am", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do",
	"does", "did", "will", "would", "can", "could", "should", "might", "may", "must",
	"really", "very", "quite", "just", "also", "still", "finally", "then", "now", "quickly",
	"carefully", "slowly", "again", "actually", "probably", "perhaps", "almost", "already",
	"only", "even", "to",
}
CONTRACTION_PREFIXES = {
	"m": "am",
	"ve": "have",
	"d": "would",
	"ll": "will",
}


#============================================
def _matching_link_end(text: str, opening_index: int) -> int | None:
	"""Return a balanced inline-link target end, or None for unsupported Markdown."""
	depth = 1
	index = opening_index + 1
	quote = ""
	while index < len(text):
		character = text[index]
		if character == "\\":
			index += 2
			continue
		if quote:
			if character == quote:
				quote = ""
			index += 1
			continue
		if character in {"\"", "'"}:
			quote = character
			index += 1
			continue
		if character == "(":
			depth += 1
		elif character == ")":
			depth -= 1
			if depth == 0:
				return index
		index += 1
	return None


#============================================
def _visible_markdown_text_and_link_count(text: str) -> tuple[str, int]:
	"""Return reader-visible prose and ordinary inline-link count from a bounded subset.

	This scanner supports ``[label](target)`` links with balanced target parentheses and optional
	titles. It removes comments, fenced code, inline code, image links, and link targets before
	word or punctuation analysis. Reference links, nested labels, HTML, and full Markdown grammar
	remain outside this diagnostic-only subset.
	"""
	visible = COMMENT_RE.sub(" ", text)
	visible = FENCED_CODE_RE.sub(" ", visible)
	visible = INLINE_CODE_RE.sub(" ", visible)
	output = []
	link_count = 0
	index = 0
	while index < len(visible):
		is_image = visible.startswith("![", index)
		if visible[index] == "[" or is_image:
			label_start = index + 2 if is_image else index + 1
			label_end = visible.find("]", label_start)
			if label_end != -1 and label_end + 1 < len(visible) and visible[label_end + 1] == "(":
				target_end = _matching_link_end(visible, label_end + 1)
				if target_end is not None:
					if not is_image:
						output.append(visible[label_start:label_end])
						link_count += 1
					index = target_end + 1
					continue
		output.append(visible[index])
		index += 1
	text = "".join(output)
	return text, link_count


#============================================
def _visible_markdown_text(text: str) -> str:
	"""Return reader-visible prose while discarding the separately measured link count."""
	visible, _link_count = _visible_markdown_text_and_link_count(text)
	return visible


#============================================
def _has_concrete_surface_signal(block: str) -> bool:
	"""Return whether a prose block has one intentionally narrow concrete-looking signal.

	Evidence comments, reader-visible inline links, inline code, numbers, measurements, paths,
	and identifier-like tokens count. This is an auditable syntax heuristic, not claim detection:
	it will miss concrete plain-language claims and it must never serve as a quality score or gate.
	"""
	visible, link_count = _visible_markdown_text_and_link_count(block)
	return bool(
		daily_blog.candidates.EVIDENCE_COMMENT_RE.search(block)
		or link_count
		or INLINE_CODE_RE.search(block)
		or CONCRETE_VISIBLE_SIGNAL_RE.search(visible)
	)


#============================================
def _sentence_texts(blocks: list[str]) -> list[str]:
	"""Return non-empty regex sentence spans from narrative prose blocks."""
	sentences = []
	for block in blocks:
		visible = _visible_markdown_text(block)
		for match in SENTENCE_RE.finditer(visible):
			sentence = match.group(0).strip()
			if sentence:
				sentences.append(sentence)
	return sentences


#============================================
def _first_person_action_surfaces(sentences: list[str]) -> set[str]:
	"""Return bounded first-person action surfaces, rather than claimed grammatical verbs.

	The heuristic recognizes ``I`` as a standalone pronoun, so terms such as ``I/O`` stay out.
	It skips a bounded auxiliary/adverb prefix, then records the first surface action plus actions
	after comma or ``and`` coordination. This supports common maker prose while deliberately
	avoiding a claim of full part-of-speech parsing.
	"""
	actions = set()
	for sentence in sentences:
		match = FIRST_PERSON_SUBJECT_RE.search(sentence)
		if not match:
			continue
		tail = sentence[match.end():]
		contraction = CONTRACTION_RE.match(sentence, match.start())
		if contraction:
			tail = (
				CONTRACTION_PREFIXES[contraction.group(1).casefold()]
				+ " "
				+ sentence[contraction.end():]
			)
		words = VISIBLE_WORD_RE.findall(tail)
		for word in words:
			surface = word.casefold()
			if surface in ACTION_PREFIX_WORDS:
				continue
			actions.add(surface)
			break
		for coordinated in COORDINATED_ACTION_RE.findall(tail):
			surface = coordinated.casefold()
			if surface not in ACTION_PREFIX_WORDS:
				actions.add(surface)
	return actions


#============================================
def _new_shadow_id() -> str:
	"""Create one sortable immutable shadow identity."""
	moment = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
	shadow_id = f"{moment}-{uuid.uuid4().hex[:10]}"
	return shadow_id


#============================================
def _reference_date(post: str) -> str:
	"""Return the date represented by current or historical MkDocs front matter."""
	front_matter, _body = daily_blog.candidates.parse_front_matter(post)
	value = front_matter["date"]
	if isinstance(value, dict):
		date_text = str(value["created"])
	else:
		date_text = str(value)
	return date_text


#============================================
def article_profile(post: str) -> dict:
	"""Return deterministic narrative-shape diagnostics for one MkDocs article.

	Regex parsing intentionally measures a narrow Markdown subset and bounded first-person action
	surfaces, rather than full Markdown or grammar. Uncited blocks are provenance telemetry only.
	The concrete-surface heuristic deliberately misses ordinary-language factual claims. These
	measurements describe samples; they are never validation rules, thresholds, or quality verdicts.
	"""
	_front_matter, body = daily_blog.candidates.parse_front_matter(post)
	title_match = re.search(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
	headings = re.findall(r"^##\s+(.+?)\s*$", body, flags=re.MULTILINE)
	coverage_matches = list(
		re.finditer(r"^##\s+Project coverage\s*$", body, flags=re.MULTILINE | re.IGNORECASE)
	)
	narrative = body[:coverage_matches[-1].start()] if coverage_matches else body
	raw_blocks = daily_blog.candidates.prose_blocks(narrative)
	blocks = [block for block in raw_blocks if _visible_markdown_text(block).strip()]
	visible_blocks = [_visible_markdown_text(block) for block in blocks]
	paragraph_word_counts = [len(VISIBLE_WORD_RE.findall(block)) for block in visible_blocks]
	sentences = _sentence_texts(blocks)
	sentence_word_counts = [len(VISIBLE_WORD_RE.findall(sentence)) for sentence in sentences]
	first_person_sentences = [
		sentence for sentence in sentences if FIRST_PERSON_RE.search(sentence)
	]
	first_person_actions = _first_person_action_surfaces(first_person_sentences)
	_narrative_visible, inline_link_count = _visible_markdown_text_and_link_count(narrative)
	if inline_link_count:
		words_per_link = sum(paragraph_word_counts) / inline_link_count
	else:
		words_per_link = NO_INLINE_MARKDOWN_LINKS
	if sentence_word_counts:
		mean_sentence_words = sum(sentence_word_counts) / len(sentence_word_counts)
		sentence_length_variance = sum(
			(word_count - mean_sentence_words) ** 2
			for word_count in sentence_word_counts
		) / len(sentence_word_counts)
	else:
		sentence_length_variance = 0.0
	if first_person_sentences:
		first_person_action_surface_diversity_ratio = (
			len(first_person_actions) / len(first_person_sentences)
		)
	else:
		first_person_action_surface_diversity_ratio = 0.0
	opening = body.split("<!-- more -->", 1)[0]
	opening_blocks = daily_blog.candidates.prose_blocks(opening)
	article_visible = _visible_markdown_text(body)
	profile = {
		"title": title_match.group(1).strip() if title_match else "",
		"h2_headings": headings,
		"narrative_h2_count": len(
			[heading for heading in headings if heading.casefold() != "project coverage"]
		),
		"narrative_words": sum(
			len(VISIBLE_WORD_RE.findall(block)) for block in visible_blocks
		),
		"opening_words": (
			len(VISIBLE_WORD_RE.findall(_visible_markdown_text(opening_blocks[0])))
			if len(opening_blocks) == 1
			else 0
		),
		"first_person": bool(FIRST_PERSON_RE.search(article_visible)),
		"has_project_coverage": any(
			heading.casefold() == "project coverage" for heading in headings
		),
		"narrative_prose_block_count": len(blocks),
		"mean_narrative_paragraph_words": (
			sum(paragraph_word_counts) / len(paragraph_word_counts)
			if paragraph_word_counts
			else 0.0
		),
		"standalone_short_single_sentence_paragraph_count": sum(
			1
			for block in visible_blocks
			if len(_sentence_texts([block])) == 1
			and len(VISIBLE_WORD_RE.findall(block)) <= STANDALONE_SHORT_PARAGRAPH_WORD_LIMIT
		),
		"sentence_length_variance": sentence_length_variance,
		"sentences_under_eight_visible_words": sum(
			1 for word_count in sentence_word_counts if word_count < 8
		),
		"question_count": sum(1 for sentence in sentences if "?" in sentence),
		"inline_markdown_link_count": inline_link_count,
		"words_per_inline_markdown_link": words_per_link,
		"uncited_narrative_prose_block_count": sum(
			1 for block in blocks if not daily_blog.candidates.EVIDENCE_COMMENT_RE.search(block)
		),
		"narrative_prose_blocks_without_concrete_surface_signal": sum(
			1 for block in blocks if not _has_concrete_surface_signal(block)
		),
		"first_person_sentence_count": len(first_person_sentences),
		"distinct_first_person_action_surfaces": sorted(first_person_actions),
		"distinct_first_person_action_surface_count": len(first_person_actions),
		"first_person_action_surface_diversity_ratio": first_person_action_surface_diversity_ratio,
	}
	return profile


#============================================
def _evaluation_evidence(
	projection: daily_blog.schema.EditorialProjection,
	generated_post: str,
) -> str:
	"""Render exact generated-post citations from the bounded projection."""
	used_ids = daily_blog.candidates.evidence_ids_in_post(generated_post)
	text = projection.render_context(used_ids)
	return text


#============================================
def _validate_evaluator_templates() -> tuple[str, str]:
	"""Load affirmative versioned evaluation and repair instructions."""
	template = daily_blog.editorial.load_evaluation_prompt(EVALUATOR_TEMPLATE_NAME)
	repair = daily_blog.editorial.load_evaluation_prompt(EVALUATOR_REPAIR_TEMPLATE_NAME)
	return template, repair


#============================================
def render_evaluator_prompt(
	projection: daily_blog.schema.EditorialProjection,
	generated_post: str,
	reference_post: str,
	limit: int,
) -> str:
	"""Render one bounded semantic comparison prompt."""
	template, _repair = _validate_evaluator_templates()
	prompt = template.format(
		report_date=projection.report_date,
		evidence_json=_evaluation_evidence(projection, generated_post),
		generated_post=generated_post,
		reference_post=reference_post,
	)
	if len(prompt) > limit:
		raise RuntimeError(
			f"Shadow evaluator prompt requires {len(prompt)} characters and exceeds its {limit} budget."
		)
	return prompt


#============================================
def parse_evaluator_result(response: str) -> dict:
	"""Parse and validate one exact semantic shadow scorecard."""
	if len(response) > MAX_EVALUATOR_RESPONSE_CHARS:
		raise RuntimeError("Shadow evaluator response exceeds its structured response budget.")
	value = json.loads(response.strip())
	if not isinstance(value, dict):
		raise RuntimeError("Shadow evaluator result must be one JSON object.")
	for field in SCORE_FIELDS:
		score = value.get(field)
		if type(score) is not int or not 1 <= score <= 5:
			raise RuntimeError(f"Shadow evaluator {field} must be an integer from one through five.")
	verdict = str(value.get("verdict") or "")
	if verdict not in {"close", "partial", "weak"}:
		raise RuntimeError("Shadow evaluator verdict must be close, partial, or weak.")
	reason = str(value.get("reason") or "").strip()
	if not reason or len(reason) > 1000:
		raise RuntimeError("Shadow evaluator reason must be concise and non-empty.")
	result = {field: value[field] for field in SCORE_FIELDS}
	result["verdict"] = verdict
	result["reason"] = reason
	return result


#============================================
def require_model_data_sharing(config: daily_blog.config.DailyBlogConfig) -> None:
	"""Stop every shadow model route until its evidence destination is approved."""
	if not config.allow_shadow_model_data_sharing:
		raise RuntimeError(
			"Shadow evaluation requires daily_blog.shadow_evaluation."
			"external_model_data_sharing: true because exact-Git evidence is sent to configured "
			"author routes, and the reference plus evidence are sent to the referee route."
		)


#============================================
def semantic_evaluation(
	projection: daily_blog.schema.EditorialProjection,
	generated_post: str,
	reference_post: str,
	config: daily_blog.config.DailyBlogConfig,
	runner: object,
) -> dict:
	"""Run one isolated semantic comparison with one structured repair attempt."""
	require_model_data_sharing(config)
	limit = config.prompt_limits["referee_chars"]
	prompt = render_evaluator_prompt(projection, generated_post, reference_post, limit)
	response = runner.run(config.referee_route, prompt, config.daily_blog_repository)
	try:
		result = parse_evaluator_result(response)
	except (json.JSONDecodeError, RuntimeError):
		_template, repair = _validate_evaluator_templates()
		repair_prompt = repair.format(response=response[:MAX_EVALUATOR_RESPONSE_CHARS])
		repaired = runner.run(config.referee_route, repair_prompt, config.daily_blog_repository)
		result = parse_evaluator_result(repaired)
	return result


#============================================
def collect_evidence(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
	refresh_mirrors: bool,
) -> tuple[
	list[dict],
	list[daily_blog.schema.RepositoryActivity],
	daily_blog.schema.EvidencePacket,
	dict[str, bytes],
]:
	"""Collect the same exact-Git evidence used by production without publishing it."""
	roster = daily_blog.repositories.discover_owner_repositories(
		config.output_owner,
		config.output_root,
	)
	manager = daily_blog.mirrors.MirrorManager(config.mirror_cache_root, roster)
	mirrors = manager.refresh_all(refresh=refresh_mirrors)
	failed = [item["repository"] for item in mirrors if item["refresh_result"] == "failed"]
	if failed:
		raise RuntimeError("Shadow mirror refresh failed for: " + ", ".join(failed))
	activity = daily_blog.activity.locate_activity(
		report_date,
		config.report_timezone,
		mirrors,
		config.identity_names,
		config.identity_emails,
	)
	assembler = daily_blog.evidence.EvidenceAssembler(
		report_date,
		config.report_timezone,
		config.collection_limits,
	)
	packet, assets = assembler.assemble(mirrors, activity)
	if not packet.complete:
		raise RuntimeError("Shadow evidence assembly is incomplete.")
	return mirrors, activity, packet, assets


#============================================
def _write_shadow_artifacts(
	config: daily_blog.config.DailyBlogConfig,
	shadow_id: str,
	packet: daily_blog.schema.EvidencePacket,
	projection: daily_blog.schema.EditorialProjection,
	assets: dict[str, bytes],
	raw_candidates: list[dict],
	candidates: list[daily_blog.editorial.CandidateResult],
	decision: daily_blog.editorial.EditorialDecision,
	reference_post: str,
	semantic: dict,
	prompt_contract: dict[str, object],
) -> tuple[str, dict]:
	"""Atomically install one immutable complete shadow evaluation."""
	date_root = os.path.join(
		config.output_root,
		config.output_owner,
		"daily_blog_shadow",
		packet.report_date,
	)
	shadow_path = os.path.join(date_root, shadow_id)
	if os.path.exists(shadow_path):
		raise RuntimeError(f"Immutable shadow evaluation already exists: {shadow_path}")
	generated_post = decision.post
	used_ids = daily_blog.candidates.evidence_ids_in_post(generated_post)
	primary_ids = {
		item.evidence_id for item in packet.items if item.kind == "dated_changelog"
	}
	validation = [
		candidate.public_summary(f"candidate_{index + 1}")
		for index, candidate in enumerate(candidates)
	]
	scorecard = {
		"schema_version": SHADOW_SCHEMA_VERSION,
		"shadow_id": shadow_id,
		"report_date": packet.report_date,
		"timezone": packet.timezone,
		"prompt_version": prompt_contract["prompt_version"],
		"rubric_version": prompt_contract["rubric_version"],
		"editorial_prompt_contract": prompt_contract,
		"evidence_packet": packet.packet_id,
		"editorial_projection": projection.projection_id,
		"reference": {
			"sha256": daily_blog.io_utils.sha256_text(reference_post),
			"profile": article_profile(reference_post),
		},
		"generated": {
			"sha256": daily_blog.io_utils.sha256_text(generated_post),
			"referee_winner": decision.winner,
			"valid_candidate_count": sum(candidate.valid for candidate in candidates),
			"profile": article_profile(generated_post),
			"known_evidence_references": used_ids.issubset(
				{item.evidence_id for item in packet.items}
			),
			"dated_changelog_used": bool(primary_ids.intersection(used_ids)),
		},
		"semantic_assessment": semantic,
		"candidate_validation": validation,
	}
	os.makedirs(date_root, exist_ok=True)
	stage = os.path.join(date_root, f".{shadow_id}.staging-{uuid.uuid4().hex}")
	os.makedirs(os.path.join(stage, "assets"))
	try:
		daily_blog.io_utils.atomic_write_json(os.path.join(stage, "scorecard.json"), scorecard)
		daily_blog.io_utils.atomic_write_json(os.path.join(stage, "evidence.json"), packet.to_dict())
		daily_blog.io_utils.atomic_write_json(
			os.path.join(stage, "editorial_projection.json"),
			projection.to_dict(),
		)
		daily_blog.io_utils.atomic_write_json(os.path.join(stage, "candidates.json"), raw_candidates)
		daily_blog.io_utils.atomic_write_json(
			os.path.join(stage, "candidate_validation.json"),
			validation,
		)
		daily_blog.io_utils.atomic_write_text(os.path.join(stage, "generated_post.md"), generated_post)
		daily_blog.io_utils.atomic_write_text(os.path.join(stage, "reference_post.md"), reference_post)
		for asset_path, contents in assets.items():
			if not asset_path.startswith("assets/") or ".." in asset_path.split("/"):
				raise RuntimeError(f"Shadow asset path is outside its owned directory: {asset_path}")
			daily_blog.io_utils.atomic_write_bytes(os.path.join(stage, asset_path), contents)
		os.replace(stage, shadow_path)
	except Exception:
		if os.path.exists(stage):
			shutil.rmtree(stage)
		raise
	latest = {
		"schema_version": SHADOW_SCHEMA_VERSION,
		"report_date": packet.report_date,
		"shadow_id": shadow_id,
		"path": shadow_id,
		"scorecard_sha256": daily_blog.io_utils.hash_value(scorecard),
		"updated_at": daily_blog.schema.utc_now(),
	}
	daily_blog.io_utils.atomic_write_json(os.path.join(date_root, "latest.json"), latest)
	return shadow_path, scorecard


#============================================
def evaluate_packet(
	config: daily_blog.config.DailyBlogConfig,
	packet: daily_blog.schema.EvidencePacket,
	assets: dict[str, bytes],
	reference_post: str,
	runner: object | None = None,
	contract: daily_blog.contracts.EditorialContract | None = None,
	snapshot: daily_blog.editorial.PromptContractSnapshot | None = None,
) -> tuple[str, dict]:
	"""Generate, judge, compare, and retain one non-publishing shadow evaluation."""
	require_model_data_sharing(config)
	# ASVS 2.2.1: one authoritative resolver owns the trusted prompt-file read.
	resolved_snapshot = daily_blog.editorial.resolve_run_snapshot(contract, snapshot)
	resolved_contract = resolved_snapshot.contract
	prompt_contract = daily_blog.editorial.prompt_contract_identity(
		snapshot=resolved_snapshot
	)
	if _reference_date(reference_post) != packet.report_date:
		raise RuntimeError("Shadow reference date does not match the evidence packet.")
	shadow_id = _new_shadow_id()
	route_runner = runner if runner is not None else daily_blog.routes.CommandRouteRunner()
	projection = daily_blog.projection.build_projection(packet, config.projection_limits)
	raw_candidates = daily_blog.editorial.generate_candidates(
		packet,
		projection,
		shadow_id,
		config,
		runner=route_runner,
		contract=resolved_contract,
		snapshot=resolved_snapshot,
	)
	candidates = daily_blog.editorial.validate_candidates(
		raw_candidates,
		packet,
		projection,
		shadow_id,
		snapshot=resolved_snapshot,
	)
	decision = daily_blog.editorial.select_candidate(
		packet,
		projection,
		shadow_id,
		candidates,
		config,
		runner=route_runner,
		contract=resolved_contract,
		snapshot=resolved_snapshot,
	)
	semantic = semantic_evaluation(
		projection,
		decision.post,
		reference_post,
		config,
		route_runner,
	)
	result = _write_shadow_artifacts(
		config,
		shadow_id,
		packet,
		projection,
		assets,
		raw_candidates,
		candidates,
		decision,
		reference_post,
		semantic,
		prompt_contract,
	)
	return result


#============================================
def run_shadow_evaluation(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
	reference_path: str,
	refresh_mirrors: bool = True,
	contract: daily_blog.contracts.EditorialContract | None = None,
	snapshot: daily_blog.editorial.PromptContractSnapshot | None = None,
) -> tuple[str, dict]:
	"""Acquire the shadow lock and evaluate one historical date without site import."""
	require_model_data_sharing(config)
	# ASVS 2.2.1: one authoritative resolver owns the trusted prompt-file read.
	resolved_snapshot = daily_blog.editorial.resolve_run_snapshot(contract, snapshot)
	resolved_contract = resolved_snapshot.contract
	daily_blog.activity.build_date_window(report_date, config.report_timezone)
	with open(reference_path, "r", encoding="utf-8") as handle:
		reference_post = handle.read()
	lock_path = os.path.join(
		config.output_root,
		config.output_owner,
		"daily_blog_shadow_locks",
		f"{report_date}.lock",
	)
	with daily_blog.locks.FileLock(lock_path):
		_mirrors, _activity, packet, assets = collect_evidence(
			config,
			report_date,
			refresh_mirrors,
		)
		result = evaluate_packet(
			config,
			packet,
			assets,
			reference_post,
			contract=resolved_contract,
			snapshot=resolved_snapshot,
		)
	return result

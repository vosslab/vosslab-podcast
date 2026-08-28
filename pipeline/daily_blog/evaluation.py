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
import daily_blog.candidates
import daily_blog.io_utils
import daily_blog.mirrors


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
	"""Return deterministic narrative-shape measurements for one MkDocs article."""
	_front_matter, body = daily_blog.candidates.parse_front_matter(post)
	title_match = re.search(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
	headings = re.findall(r"^##\s+(.+?)\s*$", body, flags=re.MULTILINE)
	coverage_match = re.search(r"^##\s+Project coverage\s*$", body, flags=re.MULTILINE | re.IGNORECASE)
	narrative = body[:coverage_match.start()] if coverage_match else body
	blocks = daily_blog.candidates.prose_blocks(narrative)
	opening = body.split("<!-- more -->", 1)[0]
	opening_blocks = daily_blog.candidates.prose_blocks(opening)
	profile = {
		"title": title_match.group(1).strip() if title_match else "",
		"h2_headings": headings,
		"narrative_h2_count": len(
			[heading for heading in headings if heading.casefold() != "project coverage"]
		),
		"narrative_words": sum(
			daily_blog.candidates.visible_word_count(block) for block in blocks
		),
		"opening_words": (
			daily_blog.candidates.visible_word_count(opening_blocks[0])
			if len(opening_blocks) == 1
			else 0
		),
		"first_person": bool(re.search(r"\b(?:I|my)\b", body, flags=re.IGNORECASE)),
		"has_project_coverage": any(
			heading.casefold() == "project coverage" for heading in headings
		),
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
	template = daily_blog.editorial.load_prompt(EVALUATOR_TEMPLATE_NAME)
	repair = daily_blog.editorial.load_prompt(EVALUATOR_REPAIR_TEMPLATE_NAME)
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
	manager = daily_blog.mirrors.MirrorManager(config.mirror_cache_root, config.repository_urls)
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
		"prompt_version": daily_blog.schema.PROMPT_VERSION,
		"rubric_version": daily_blog.schema.RUBRIC_VERSION,
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
) -> tuple[str, dict]:
	"""Generate, judge, compare, and retain one non-publishing shadow evaluation."""
	require_model_data_sharing(config)
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
	)
	candidates = daily_blog.editorial.validate_candidates(
		raw_candidates,
		packet,
		projection,
		shadow_id,
	)
	decision = daily_blog.editorial.select_candidate(
		packet,
		projection,
		shadow_id,
		candidates,
		config,
		runner=route_runner,
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
	)
	return result


#============================================
def run_shadow_evaluation(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
	reference_path: str,
	refresh_mirrors: bool = True,
) -> tuple[str, dict]:
	"""Acquire the shadow lock and evaluate one historical date without site import."""
	require_model_data_sharing(config)
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
		result = evaluate_packet(config, packet, assets, reference_post)
	return result

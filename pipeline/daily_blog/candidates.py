"""Deterministic candidate and provenance validation for LLM-authored posts."""

# Standard Library
import re
import unicodedata

# PIP3 modules
import yaml  # type: ignore[import-untyped]

# local repo modules
import daily_blog.schema
import daily_blog.publication_source_safety
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.editorial_contracts


FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
EVIDENCE_COMMENT_RE = re.compile(r"<!--\s*evidence:\s*([^>]+?)\s*-->")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SLUG_PLACEHOLDER = "thematic-lowercase-slug"
FENCE_RE = re.compile(r"(^|\n)\s*(?:`{3,}|~{3,})")
INLINE_MARKDOWN_LINK_RE = re.compile(
	r"(?P<image>!)?\[(?P<label>[^\]\n]*)\]\(\s*"
	r"(?P<target><[^>\n]+>|[^()\s]+)"
	r"(?:\s+(?P<title>\"[^\"\n]*\"|'[^'\n]*'|\([^)\n]*\)))?\s*\)"
)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
FENCED_CODE_BLOCK_RE = re.compile(
	r"(?ms)^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$"
)
INLINE_CODE_RE = re.compile(r"(?<!`)`+[^`\n]*`+")
REFERENCE_DEFINITION_RE = re.compile(r"(?m)^\s*\[[^\]\n]+\]:[^\n]*$")


#============================================
def parse_front_matter(post: str) -> tuple[dict, str]:
	"""Parse one Markdown post's opening YAML mapping and body."""
	match = FRONT_MATTER_RE.search(post)
	if not match:
		raise RuntimeError("Post must begin with YAML front matter.")
	value = yaml.safe_load(match.group(1))
	if not isinstance(value, dict):
		raise RuntimeError("Post front matter must be a mapping.")
	body = post[match.end():]
	return value, body


#============================================
def slug_from_title(title: str) -> str:
	"""Return one deterministic lowercase ASCII slug for a thematic H1."""
	decomposed = unicodedata.normalize("NFKD", title)
	ascii_title = decomposed.encode("ascii", "ignore").decode("ascii").casefold()
	slug = re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-")
	return slug


#============================================
def resolve_slug_placeholder(post: str) -> str:
	"""Resolve the prompt's literal slug sentinel from an otherwise parseable H1."""
	match = FRONT_MATTER_RE.search(post)
	if not match:
		return post
	placeholder_re = re.compile(
		rf"^slug:\s*{re.escape(SLUG_PLACEHOLDER)}\s*$",
		flags=re.MULTILINE,
	)
	front_matter = match.group(1)
	if not placeholder_re.search(front_matter):
		return post
	body = post[match.end():]
	h1_values = re.findall(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
	if len(h1_values) != 1:
		return post
	slug = slug_from_title(h1_values[0])
	if not slug:
		return post
	resolved_front_matter = placeholder_re.sub(f"slug: {slug}", front_matter, count=1)
	resolved = post[:match.start(1)] + resolved_front_matter + post[match.end(1):]
	return resolved


#============================================
def evidence_ids_in_post(post: str) -> set[str]:
	"""Return all evidence IDs named by paragraph provenance comments."""
	identifiers = set()
	for match in EVIDENCE_COMMENT_RE.finditer(post):
		for value in match.group(1).split(","):
			identifier = value.strip()
			if identifier:
				identifiers.add(identifier)
	return identifiers


#============================================
def prose_blocks(body: str) -> list[str]:
	"""Return visible prose blocks after removing a leading Markdown heading."""
	blocks = []
	for block in re.split(r"\n\s*\n", body.strip()):
		text = block.strip()
		# A heading may share its block with prose when the author omits a blank line.
		# Treat that prose as visible for every policy; otherwise a heading is an
		# untrusted-model bypass around v3's paragraph-provenance requirement.
		text = re.sub(r"\A#{1,6}\s+[^\n]*(?:\n|\Z)", "", text).strip()
		if not text or text == "<!-- more -->":
			continue
		if text.startswith("!["):
			continue
		if text.startswith("<!--") and text.endswith("-->"):
			continue
		blocks.append(text)
	return blocks


#============================================
def visible_word_count(text: str) -> int:
	"""Count reader-visible ASCII words rather than Markdown source syntax."""
	visible = _reader_visible_markdown(text)
	words = re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", visible)
	return len(words)


#============================================
def _legacy_source_word_count(text: str) -> int:
	"""Return the historical v3 source-token count without rendering Markdown."""
	visible = EVIDENCE_COMMENT_RE.sub(" ", text)
	visible = HTML_COMMENT_RE.sub(" ", visible)
	words = re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", visible)
	return len(words)


#============================================
def _policy_word_count(
	text: str,
	policy: daily_blog.prompt_registry.definitions.CandidateValidationPolicy,
) -> int:
	"""Count one declared validation-policy budget without identity-based behavior."""
	if policy.word_count_mode == "legacy_source":
		count = _legacy_source_word_count(text)
	elif policy.word_count_mode == "reader_visible_markdown":
		count = visible_word_count(text)
	else:
		raise RuntimeError("Candidate validation policy word count mode is unsupported.")
	return count


#============================================
def narrative_prose_sections(
	body: str,
) -> list[str]:
	"""Return prose-bearing narrative sections before the final coverage footer."""
	coverage_matches = list(
		re.finditer(r"^##\s+Project coverage\s*$", body, flags=re.MULTILINE | re.IGNORECASE)
	)
	narrative = body[:coverage_matches[-1].start()] if coverage_matches else body
	sections = []
	for section in re.split(r"(?=^##\s+)", narrative, flags=re.MULTILINE):
		if prose_blocks(section):
			sections.append(section)
	return sections


#============================================
def narrative_visible_markdown(body: str) -> str:
	"""Return all visible narrative Markdown, including headings, before final coverage."""
	coverage_matches = list(
		re.finditer(r"^##\s+Project coverage\s*$", body, flags=re.MULTILINE | re.IGNORECASE)
	)
	if coverage_matches:
		return body[:coverage_matches[-1].start()]
	return body


#============================================
def _masked_text(text: str) -> str:
	"""Return whitespace with the same length as one nonvisible source span."""
	masked = " " * len(text)
	return masked


#============================================
def _mask_image_markdown(text: str) -> str:
	"""Mask complete image syntax while respecting quotes and nested destination parentheses."""
	parts = []
	index = 0
	while index < len(text):
		start = text.find("![", index)
		if start < 0:
			parts.append(text[index:])
			break
		parts.append(text[index:start])
		alt_end = text.find("]", start + 2)
		if alt_end < 0:
			# An incomplete image may render as prose, so preserve it for safe rejection.
			parts.append(text[start:])
			break
		end = alt_end + 1
		if end < len(text) and text[end] == "(":
			depth = 0
			quote = ""
			cursor = end
			while cursor < len(text):
				character = text[cursor]
				if quote:
					if character == quote and (cursor == 0 or text[cursor - 1] != "\\"):
						quote = ""
				elif character in {"\"", "'"}:
					quote = character
				elif character == "(":
					depth += 1
				elif character == ")":
					depth -= 1
					if depth == 0:
						end = cursor + 1
						break
				cursor += 1
			if depth != 0 or quote:
				# Ambiguous source remains visible instead of creating a link-check bypass.
				parts.append(text[start:])
				break
		elif end < len(text) and text[end] == "[":
			reference_end = text.find("]", end + 1)
			if reference_end < 0:
				parts.append(text[start:])
				break
			end = reference_end + 1
		parts.append(_masked_text(text[start:end]))
		index = end
	masked = "".join(parts)
	return masked


#============================================
def _mask_html_tags(text: str) -> str:
	"""Mask ordinary well-formed raw HTML tags, not a full HTML rendering implementation."""
	parts = []
	index = 0
	while index < len(text):
		start = text.find("<", index)
		if start < 0:
			parts.append(text[index:])
			break
		parts.append(text[index:start])
		if start + 1 >= len(text) or text[start + 1] not in "/!" and not text[start + 1].isalpha():
			parts.append("<")
			index = start + 1
			continue
		quote = ""
		cursor = start + 1
		while cursor < len(text):
			character = text[cursor]
			if quote:
				if character == quote and text[cursor - 1] != "\\":
					quote = ""
			elif character in {"\"", "'"}:
				quote = character
			elif character == ">":
				break
			cursor += 1
		if cursor >= len(text) or quote:
			# Ambiguous raw HTML stays visible to force a conservative first-use failure.
			parts.append(text[start:])
			break
		parts.append(_masked_text(text[start:cursor + 1]))
		index = cursor + 1
	masked = "".join(parts)
	return masked


#============================================
def _reader_visible_markdown(text: str) -> str:
	"""Return bounded reader-visible Markdown text for deterministic word budgets."""
	visible = HTML_COMMENT_RE.sub(" ", text)
	visible = FENCED_CODE_BLOCK_RE.sub(" ", visible)
	visible = INLINE_CODE_RE.sub(" ", visible)
	visible = _mask_image_markdown(visible)
	visible = _mask_html_tags(visible)
	visible = REFERENCE_DEFINITION_RE.sub(" ", visible)

	def replace_link(match: re.Match[str]) -> str:
		"""Keep a visible link label while omitting destination and title metadata."""
		if match.group("image"):
			return _masked_text(match.group(0))
		return match.group("label")

	return INLINE_MARKDOWN_LINK_RE.sub(replace_link, visible)


#============================================
def _first_repository_appearance_is_direct_link(
	narrative: str,
	repository: str,
	repository_url: str,
) -> bool | None:
	"""Return whether a repository's first visible mention is its exact inline link."""
	# Keep nonvisible source out of the first-visible-mention decision.
	narrative = HTML_COMMENT_RE.sub(" ", narrative)
	narrative = FENCED_CODE_BLOCK_RE.sub(" ", narrative)
	narrative = INLINE_CODE_RE.sub(" ", narrative)
	narrative = _mask_image_markdown(narrative)
	narrative = _mask_html_tags(narrative)
	narrative = REFERENCE_DEFINITION_RE.sub(" ", narrative)
	previous_end = 0
	for match in INLINE_MARKDOWN_LINK_RE.finditer(narrative):
		plain_match = re.search(re.escape(repository), narrative[previous_end:match.start()])
		if plain_match:
			return False
		previous_end = match.end()
		if match.group("image"):
			continue
		label = match.group("label")
		if repository in label:
			target = match.group("target").removeprefix("<").removesuffix(">")
			return label == repository and target == repository_url
	plain_match = re.search(re.escape(repository), narrative[previous_end:])
	if plain_match:
		return False
	return None


#============================================
def _validate_narrative_repository_links(
	body: str,
	projection: daily_blog.schema.EditorialProjection,
	policy: daily_blog.prompt_registry.definitions.CandidateValidationPolicy,
) -> list[str]:
	"""Require exact first-use links for repositories selected in narrative prose."""
	issues = []
	# Headings are reader-visible narrative and can be the first repository mention.
	# Keep them here rather than rebuilding blocks, which intentionally strips headings
	# for provenance and word-count checks.
	narrative = narrative_visible_markdown(body)
	for card in projection.repositories:
		linked = _first_repository_appearance_is_direct_link(
			narrative,
			card.repository,
			card.repository_url,
		)
		if linked is False:
			issues.append(
				"First narrative mention of "
				+ card.repository
				+ " must be an inline Markdown link to "
				+ card.repository_url
				+ "."
			)
	return issues


#============================================
def _section_has_projected_evidence(section: str, projected_ids: set[str]) -> bool:
	"""Return whether one narrative section cites projected evidence."""
	section_ids = evidence_ids_in_post(section)
	return bool(section_ids.intersection(projected_ids))


#============================================
def _validate_final_house_style(
	body: str,
	packet: daily_blog.schema.EvidencePacket,
	projection: daily_blog.schema.EditorialProjection,
	policy: daily_blog.prompt_registry.definitions.CandidateValidationPolicy,
) -> list[str]:
	"""Validate the objective publication shape shared by final editorial candidates."""
	issues = []
	marker = "<!-- more -->"
	before_excerpt = body.split(marker, 1)[0]
	opening_blocks = prose_blocks(before_excerpt)
	if len(opening_blocks) != policy.required_opening_prose_blocks or len(
		re.findall(r"^##\s+", before_excerpt, flags=re.MULTILINE)
	) > policy.maximum_opening_h2_sections:
		issues.append("Final post must place one opening prose paragraph before the excerpt marker.")
	elif (
		sum(_policy_word_count(block, policy) for block in opening_blocks)
		> policy.maximum_opening_words
	):
		issues.append("Final post opening paragraph exceeds its compact word budget.")
	headings = re.findall(r"^##\s+(.+?)\s*$", body, flags=re.MULTILINE)
	coverage = [heading for heading in headings if heading.casefold() == "project coverage"]
	if (
		policy.require_final_project_coverage
		and (len(coverage) != 1 or not headings or headings[-1].casefold() != "project coverage")
	):
		issues.append("Final post must finish with one Project coverage H2 section.")
	narrative_headings = [
		heading for heading in headings if heading.casefold() != "project coverage"
	]
	if not (
		policy.minimum_narrative_h2_sections
		<= len(narrative_headings)
		<= policy.maximum_narrative_h2_sections
	):
		issues.append(
			"Final post must contain "
			+ str(policy.minimum_narrative_h2_sections)
			+ " through "
			+ str(policy.maximum_narrative_h2_sections)
			+ " narrative H2 sections."
		)
	coverage_match = (
		re.search(r"^##\s+Project coverage\s*$", body, flags=re.MULTILINE | re.IGNORECASE)
		if policy.require_final_project_coverage
		else None
	)
	narrative = body[:coverage_match.start()] if coverage_match else body
	word_count = sum(_policy_word_count(block, policy) for block in prose_blocks(narrative))
	if not policy.minimum_narrative_words <= word_count <= policy.maximum_narrative_words:
		issues.append(
			"Final post narrative must contain "
			+ str(policy.minimum_narrative_words)
			+ " through "
			+ str(policy.maximum_narrative_words)
			+ " visible prose words."
		)
	coverage_text = body[coverage_match.end():] if coverage_match else ""
	coverage_blocks = prose_blocks(coverage_text)
	if (
		policy.require_final_project_coverage
		and policy.coverage_reject_afterword
		and re.search(
			r"(?:^#{1,6}\s+|<h[1-6](?:\s|>|/))",
			coverage_text,
			flags=re.IGNORECASE | re.MULTILINE,
		)
	):
		issues.append("Project coverage must not contain a later heading or afterword.")
	if (
		policy.require_final_project_coverage
		and policy.coverage_maximum_blocks
		and len(coverage_blocks) != policy.coverage_maximum_blocks
	):
		issues.append("Project coverage must use one compact paragraph or list.")
	elif (
		policy.require_final_project_coverage
		and policy.coverage_maximum_words
		and coverage_blocks
		and _policy_word_count(coverage_blocks[0], policy) > policy.coverage_maximum_words
	):
		issues.append("Project coverage exceeds its compact visible word budget.")
	if policy.coverage_repository_scope == "all_packet_activity":
		repositories = [activity.repository for activity in packet.activity]
	elif policy.coverage_repository_scope == "projected_repositories":
		repositories = [card.repository for card in projection.repositories]
	else:
		raise RuntimeError("Candidate validation policy coverage repository scope is unsupported.")
	missing_repositories = (
		[repository for repository in repositories if repository not in coverage_text]
		if policy.require_final_project_coverage
		else []
	)
	if missing_repositories:
		issues.append(
			"Project coverage is missing active repositories: " + ", ".join(missing_repositories)
		)
	if policy.require_first_repository_link:
		issues.extend(_validate_narrative_repository_links(body, projection, policy))
	return issues


#============================================
def _generic_work_log_title(title: str, report_date: str) -> bool:
	"""Return whether an H1 is only a generic date-derived work-log label."""
	normalized = re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()
	date_words = report_date.replace("-", " ")
	generic = {
		"work log",
		"daily work log",
		f"work log {date_words}",
		f"work log for {date_words}",
		f"daily work log {date_words}",
		f"daily work log for {date_words}",
		f"{date_words} work log",
		f"{date_words} daily work log",
	}
	return normalized in generic


#============================================
def validate_complete_post_body(
	post: str,
	packet: daily_blog.schema.EvidencePacket,
	projection: daily_blog.schema.EditorialProjection,
	policy: daily_blog.prompt_registry.definitions.CandidateValidationPolicy | None = None,
) -> list[str]:
	"""Validate authored final-post prose without trusting machine metadata.

	Stage 6 and 7 use this before promotion; Stage 8 repeats the invariant after
	it constructs canonical metadata.  A synthetic closed metadata envelope keeps
	the body policy in one deterministic implementation.
	"""
	try:
		_front_matter, body = parse_front_matter(post)
	except RuntimeError:
		body = post
	titles = re.findall(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
	if len(titles) != 1:
		return ["Post body must contain exactly one H1."]
	metadata = (
		"---\n"
		+ "date: " + packet.report_date + "\n"
		+ "slug: " + slug_from_title(titles[0]) + "\n"
		+ "generator_run: stage-admission\n"
		+ "evidence_manifest: evidence.json\n"
		+ "editorial_projection: editorial_projection.json\n---\n"
	)
	return validate_candidate(metadata + body, packet, projection, "stage-admission", policy)


#============================================
def validate_candidate(
	post: str,
	packet: daily_blog.schema.EvidencePacket,
	projection: daily_blog.schema.EditorialProjection,
	run_id: str,
	policy: daily_blog.prompt_registry.definitions.CandidateValidationPolicy | None = None,
) -> list[str]:
	"""Return deterministic structural and evidence-provenance issues."""
	policy = daily_blog.prompt_registry.editorial_contracts.resolve_validation_policy(policy)
	issues = []
	if projection.packet_id != packet.packet_id:
		return ["Editorial projection does not match the authoritative evidence packet."]
	if len(post) > policy.maximum_candidate_characters:
		issues.append("Post exceeds the candidate character budget.")
	try:
		front_matter, body = parse_front_matter(post)
	except RuntimeError as error:
		return [str(error)]
	required = (
		"date",
		"slug",
		"generator_run",
		"evidence_manifest",
		"editorial_projection",
	)
	if set(front_matter) != set(required):
		issues.append("Front matter must contain only the publication metadata fields.")
	for key in required:
		if key not in front_matter:
			issues.append(f"Front matter is missing {key}.")
	if str(front_matter.get("date") or "") != packet.report_date:
		issues.append("Front matter date does not match the evidence packet.")
	slug = str(front_matter.get("slug") or "")
	if slug == SLUG_PLACEHOLDER:
		issues.append("Front matter contains an unresolved slug placeholder.")
	elif not SLUG_RE.fullmatch(slug):
		issues.append("Front matter slug must use lowercase ASCII words and hyphens.")
	if front_matter.get("generator_run") != run_id:
		issues.append("Front matter generator_run does not match the active run.")
	if front_matter.get("evidence_manifest") != "evidence.json":
		issues.append("Front matter evidence_manifest must name evidence.json.")
	if front_matter.get("editorial_projection") != "editorial_projection.json":
		issues.append("Front matter editorial_projection must name editorial_projection.json.")
	h1_values = re.findall(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
	if len(h1_values) != 1:
		issues.append("Post body must contain exactly one H1.")
	elif _generic_work_log_title(h1_values[0], packet.report_date):
		issues.append("Post H1 must use a specific thematic title instead of a dated Work log label.")
	if not re.search(r"^##\s+\S", body, flags=re.MULTILINE):
		issues.append("Post body must contain at least one meaningful H2.")
	marker_count = body.count("<!-- more -->")
	if marker_count != policy.required_excerpt_marker_count:
		issues.append("Post body must contain exactly one excerpt marker.")
	if marker_count == policy.required_excerpt_marker_count:
		# ASVS 2.2.1: validate model-authored structure against predefined publication limits.
		issues.extend(_validate_final_house_style(body, packet, projection, policy))
	if FENCE_RE.search(body):
		issues.append("Post body contains a fenced payload.")
	if not re.search(r"\b(?:I|my)\b", body, flags=re.IGNORECASE):
		issues.append("Post body must use first-person work-log voice.")
	packet_ids = {item.evidence_id for item in packet.items}
	known_ids = {excerpt.evidence_id for excerpt in projection.excerpts}
	used_ids = evidence_ids_in_post(body)
	if not known_ids.issubset(packet_ids):
		issues.append("Editorial projection contains evidence outside the authoritative packet.")
	unknown_ids = sorted(used_ids - known_ids)
	if unknown_ids:
		issues.append("Post cites unknown evidence IDs: " + ", ".join(unknown_ids))
	if policy.every_prose_block_cited:
		for block in prose_blocks(body):
			if not EVIDENCE_COMMENT_RE.search(block):
				issues.append("Every factual prose paragraph must cite projected evidence.")
				break
	primary_ids = {
		excerpt.evidence_id
		for excerpt in projection.excerpts
		if excerpt.kind == "dated_changelog"
	}
	if primary_ids and not used_ids.intersection(primary_ids):
		issues.append("Post must cite dated changelog evidence when it is available.")
	if not primary_ids and not used_ids:
		issues.append("Post must cite at least one projected evidence item.")
	projected_ids = {excerpt.evidence_id for excerpt in projection.excerpts}
	# ASVS 2.2.1: validate model-authored prose at its trusted producer boundary.
	narrative_sections = narrative_prose_sections(body)
	if policy.require_section_evidence and any(
		not _section_has_projected_evidence(section, projected_ids)
		for section in narrative_sections
	):
		issues.append("Each narrative section must cite projected evidence.")
	narrative_blocks = [
		block
		for section in narrative_sections
		for block in prose_blocks(section)
	]
	uncited_blocks = [
		block for block in narrative_blocks if not EVIDENCE_COMMENT_RE.search(block)
	]
	if (
		policy.maximum_uncited_narrative_blocks
		and len(uncited_blocks) > policy.maximum_uncited_narrative_blocks
	):
		issues.append("Post exceeds the uncited narrative prose block limit.")
	image_items = [
		item
		for item in packet.items
		if item.kind == "screenshot" and item.evidence_id in projected_ids
	]
	approved_screenshot_paths = tuple(
		item.publish_path for item in image_items if type(item.publish_path) is str
	)
	if daily_blog.publication_source_safety.validate_post_source(post, approved_screenshot_paths):
		issues.append("Post source contains an unsafe publication construct.")
	for path in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", body):
		if path not in {item.publish_path for item in image_items}:
			issues.append(f"Post embeds an image path outside projected evidence: {path}")
	return issues

"""Deterministic candidate and provenance validation for LLM-authored posts."""

# Standard Library
import re
import unicodedata

# PIP3 modules
import yaml

# local repo modules
import daily_blog.schema


FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
EVIDENCE_COMMENT_RE = re.compile(r"<!--\s*evidence:\s*([^>]+?)\s*-->")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SLUG_PLACEHOLDER = "thematic-lowercase-slug"
FENCE_RE = re.compile(r"(^|\n)\s*(?:`{3,}|~{3,})")
MAX_CANDIDATE_CHARS = 24000
MIN_NARRATIVE_WORDS = 350
MAX_NARRATIVE_WORDS = 650
MAX_OPENING_WORDS = 100
MIN_NARRATIVE_H2_SECTIONS = 2
MAX_NARRATIVE_H2_SECTIONS = 4


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
	"""Return factual prose blocks that require explicit provenance."""
	blocks = []
	for block in re.split(r"\n\s*\n", body.strip()):
		text = block.strip()
		if not text or text == "<!-- more -->":
			continue
		if text.startswith("#") or text.startswith("!["):
			continue
		if text.startswith("<!--") and text.endswith("-->"):
			continue
		blocks.append(text)
	return blocks


#============================================
def visible_word_count(text: str) -> int:
	"""Count visible ASCII words while omitting provenance comments and Markdown punctuation."""
	visible = EVIDENCE_COMMENT_RE.sub(" ", text)
	visible = re.sub(r"<!--.*?-->", " ", visible, flags=re.DOTALL)
	words = re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", visible)
	return len(words)


#============================================
def _validate_final_house_style(body: str, packet: daily_blog.schema.EvidencePacket) -> list[str]:
	"""Validate the objective publication shape shared by final editorial candidates."""
	issues = []
	marker = "<!-- more -->"
	before_excerpt = body.split(marker, 1)[0]
	opening_blocks = prose_blocks(before_excerpt)
	if len(opening_blocks) != 1 or re.search(r"^##\s+", before_excerpt, flags=re.MULTILINE):
		issues.append("Final post must place one opening prose paragraph before the excerpt marker.")
	elif visible_word_count(opening_blocks[0]) > MAX_OPENING_WORDS:
		issues.append("Final post opening paragraph exceeds its compact word budget.")
	headings = re.findall(r"^##\s+(.+?)\s*$", body, flags=re.MULTILINE)
	coverage = [heading for heading in headings if heading.casefold() == "project coverage"]
	if len(coverage) != 1 or not headings or headings[-1].casefold() != "project coverage":
		issues.append("Final post must finish with one Project coverage H2 section.")
	narrative_headings = [heading for heading in headings if heading.casefold() != "project coverage"]
	if not MIN_NARRATIVE_H2_SECTIONS <= len(narrative_headings) <= MAX_NARRATIVE_H2_SECTIONS:
		issues.append("Final post must contain two through four narrative H2 sections.")
	coverage_match = re.search(r"^##\s+Project coverage\s*$", body, flags=re.MULTILINE | re.IGNORECASE)
	narrative = body[:coverage_match.start()] if coverage_match else body
	word_count = sum(visible_word_count(block) for block in prose_blocks(narrative))
	if not MIN_NARRATIVE_WORDS <= word_count <= MAX_NARRATIVE_WORDS:
		issues.append("Final post narrative must contain 350 through 650 visible prose words.")
	coverage_text = body[coverage_match.end():] if coverage_match else ""
	missing_repositories = [
		activity.repository
		for activity in packet.activity
		if activity.repository not in coverage_text
	]
	if missing_repositories:
		issues.append(
			"Project coverage is missing active repositories: " + ", ".join(missing_repositories)
		)
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
def validate_candidate(
	post: str,
	packet: daily_blog.schema.EvidencePacket,
	projection: daily_blog.schema.EditorialProjection,
	run_id: str,
) -> list[str]:
	"""Return deterministic structural and evidence-provenance issues."""
	issues = []
	if projection.packet_id != packet.packet_id:
		return ["Editorial projection does not match the authoritative evidence packet."]
	if len(post) > MAX_CANDIDATE_CHARS:
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
	if body.count("<!-- more -->") != 1:
		issues.append("Post body must contain exactly one excerpt marker.")
	if body.count("<!-- more -->") == 1:
		issues.extend(_validate_final_house_style(body, packet))
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
	image_items = [
		item
		for item in packet.items
		if item.kind == "screenshot" and item.evidence_id in projected_ids
	]
	for path in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", body):
		if path not in {item.publish_path for item in image_items}:
			issues.append(f"Post embeds an image path outside projected evidence: {path}")
	return issues

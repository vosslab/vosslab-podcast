"""Deterministic candidate and provenance validation for LLM-authored posts."""

# Standard Library
import re

# PIP3 modules
import yaml

# local repo modules
import daily_blog.schema


FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
EVIDENCE_COMMENT_RE = re.compile(r"<!--\s*evidence:\s*([^>]+?)\s*-->")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
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
def validate_candidate(
	post: str,
	packet: daily_blog.schema.EvidencePacket,
	run_id: str,
	expected_quality: str = "final",
) -> list[str]:
	"""Return deterministic structural and evidence-provenance issues."""
	issues = []
	if len(post) > MAX_CANDIDATE_CHARS:
		issues.append("Post exceeds the candidate character budget.")
	try:
		front_matter, body = parse_front_matter(post)
	except RuntimeError as error:
		return [str(error)]
	required = ("date", "slug", "publication_quality", "generator_run", "evidence_manifest")
	for key in required:
		if key not in front_matter:
			issues.append(f"Front matter is missing {key}.")
	if str(front_matter.get("date") or "") != packet.report_date:
		issues.append("Front matter date does not match the evidence packet.")
	slug = str(front_matter.get("slug") or "")
	if not SLUG_RE.fullmatch(slug):
		issues.append("Front matter slug must use lowercase ASCII words and hyphens.")
	if front_matter.get("publication_quality") != expected_quality:
		issues.append("Front matter publication_quality does not match the candidate role.")
	if front_matter.get("generator_run") != run_id:
		issues.append("Front matter generator_run does not match the active run.")
	if front_matter.get("evidence_manifest") != "evidence.json":
		issues.append("Front matter evidence_manifest must name evidence.json.")
	if len(re.findall(r"^#\s+\S", body, flags=re.MULTILINE)) != 1:
		issues.append("Post body must contain exactly one H1.")
	if not re.search(r"^##\s+\S", body, flags=re.MULTILINE):
		issues.append("Post body must contain at least one meaningful H2.")
	if body.count("<!-- more -->") != 1:
		issues.append("Post body must contain exactly one excerpt marker.")
	if expected_quality == "final" and body.count("<!-- more -->") == 1:
		issues.extend(_validate_final_house_style(body, packet))
	if FENCE_RE.search(body):
		issues.append("Post body contains a fenced payload.")
	if not re.search(r"\b(?:I|my)\b", body, flags=re.IGNORECASE):
		issues.append("Post body must use first-person work-log voice.")
	known_ids = {item.evidence_id for item in packet.items}
	used_ids = evidence_ids_in_post(body)
	unknown_ids = sorted(used_ids - known_ids)
	if unknown_ids:
		issues.append("Post cites unknown evidence IDs: " + ", ".join(unknown_ids))
	for block in prose_blocks(body):
		if not EVIDENCE_COMMENT_RE.search(block):
			issues.append("Every factual prose paragraph must cite packet evidence.")
			break
	primary_ids = {
		item.evidence_id for item in packet.items if item.kind == "dated_changelog"
	}
	if primary_ids and not used_ids.intersection(primary_ids):
		issues.append("Post must cite dated changelog evidence when it is available.")
	if not primary_ids and not used_ids:
		issues.append("Post must cite at least one packet evidence item.")
	image_items = [item for item in packet.items if item.kind == "screenshot"]
	used_images = [item for item in image_items if item.publish_path in body]
	for path in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", body):
		if path not in {item.publish_path for item in image_items}:
			issues.append(f"Post embeds an image path outside packet evidence: {path}")
	if used_images:
		used_image_ids = {item.evidence_id for item in used_images}
		if not used_ids.intersection(used_image_ids):
			issues.append("Embedded screenshots must cite their evidence IDs.")
	return issues


#============================================
def _compact_evidence_text(item: daily_blog.schema.EvidenceItem) -> str:
	"""Condense one evidence item for a deterministic provisional paragraph."""
	text = re.sub(r"^##\s+\d{4}-\d{2}-\d{2}[^\n]*\n?", "", item.content)
	text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
	text = re.sub(r"\s+", " ", text).strip()
	if len(text) > 900:
		text = text[:897].rstrip() + "..."
	return text


#============================================
def provisional_post(
	packet: daily_blog.schema.EvidencePacket,
	run_id: str,
) -> str:
	"""Build a deterministic evidence-first post for pending editorial approval."""
	front_matter = (
		"---\n"
		+ f"date: {packet.report_date}\n"
		+ f"slug: work-log-{packet.report_date}\n"
		+ "publication_quality: provisional\n"
		+ f"generator_run: {run_id}\n"
		+ "evidence_manifest: evidence.json\n"
		+ "---\n\n"
	)
	first_item = packet.items[0]
	paragraphs = [
		f"# Work log for {packet.report_date}",
		(
			"I assembled the day from exact Git objects and kept this provisional account close "
			+ f"to the available evidence. <!-- evidence: {first_item.evidence_id} -->"
		),
		"<!-- more -->",
	]
	if not packet.activity:
		paragraphs.extend(
			[
				"## Recorded activity",
				(
					"I found no attributed commits for this Central-calendar day in the refreshed "
					+ f"repository caches. <!-- evidence: {first_item.evidence_id} -->"
				),
			]
		)
	else:
		for activity in packet.activity[:3]:
			repository_items = [
				item for item in packet.items if item.repository == activity.repository
			]
			primary = next(
				(item for item in repository_items if item.kind == "dated_changelog"),
				repository_items[0],
			)
			detail = _compact_evidence_text(primary)
			paragraphs.extend(
				[
					"## " + activity.repository.split("/", 1)[-1],
					(
						f"I recorded work in [{activity.repository}]({activity.repository_url}). "
						+ f"{detail} <!-- evidence: {primary.evidence_id} -->"
					),
				]
			)
			screenshot = next(
				(item for item in repository_items if item.kind == "screenshot"),
				None,
			)
			if screenshot is not None:
				paragraphs.append(
					f"![Evidence from {activity.repository}]({screenshot.publish_path})\n"
					+ f"<!-- evidence: {screenshot.evidence_id} -->"
				)
		if len(packet.activity) > 3:
			extra_ids = []
			extra_names = []
			for activity in packet.activity[3:]:
				item = next(item for item in packet.items if item.repository == activity.repository)
				extra_ids.append(item.evidence_id)
				extra_names.append(activity.repository)
			paragraphs.extend(
				[
					"## Additional repositories",
					(
						"I also recorded attributed work across "
						+ ", ".join(extra_names)
						+ ". <!-- evidence: "
						+ ", ".join(extra_ids)
						+ " -->"
					),
				]
			)
	body = "\n\n".join(paragraphs).rstrip() + "\n"
	post = front_matter + body
	issues = validate_candidate(post, packet, run_id, expected_quality="provisional")
	if issues:
		raise RuntimeError("Deterministic provisional post failed validation: " + "; ".join(issues))
	return post

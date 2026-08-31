"""Portable, deterministic source-safety policy for published Markdown."""

# Standard Library
import html
import re
import urllib.parse

# local repo modules
import daily_blog.io_utils


POLICY_VERSION = "publication_source_safety.v1"
_FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_EVIDENCE_COMMENT_RE = re.compile(r"<!-- evidence: ev-[0-9a-f]{16}(?:, ev-[0-9a-f]{16})* -->")
_FENCE_START_RE = re.compile(r"(?m)^[ \t]{0,3}(`{3,}|~{3,})[^\n]*\n")
_ATTRIBUTE_LIST_RE = re.compile(r"(?<!\\)\{[ \t]*:?[ \t]*(?:[.#][^ \t{}\n]+|[^ \t={}][^ \t={}]*[ \t]*=)[^{}\n]*\}")
_ESCAPE_RE = re.compile(r"\\([!\"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~])")
_REFERENCE_DEFINITION_START_RE = re.compile(r"^[ \t]{0,3}\[([^\]\n]+)\]:[ \t]*(.*)$")
_REFERENCE_USE_RE = re.compile(r"!?\[([^\]\n]+)\](?:\[([^\]\n]*)\])?")
_ANGLE_RE = re.compile(r"<([^<>\n]+)>")
# Markdown passes raw HTML through. Mask allowed URL autolinks first, then reject the complete
# raw-tag grammar rather than maintaining an unsafe, incomplete tag-name allowlist.
_RAW_HTML_RE = re.compile(r"</?[a-z][^<>]*>|<!\[cdata\[[\s\S]*?\]\]>|<![^<>]*>|<\?[\s\S]*?\?>", re.IGNORECASE)


def _post(body: str) -> str:
	"""Return a compact complete post for executable policy cases."""
	return "---\ndate: 2026-08-30\n---\n# Note\n\n" + body + "\n"


# This is a behavioral specification, not a set of implementation examples. The sibling
# carries identical bytes but independently parses the Markdown at its trust boundary.
CANONICAL_VECTOR = {
	"approved_paths": ["assets/proof.png"],
	"cases": [
		{"name": "approved_url_and_asset", "post": _post("[GitHub](https://github.com/vosslab/project) ![proof](assets/proof.png) <!-- evidence: ev-0123456789abcdef -->"), "valid": True},
		{"name": "missing_front_matter", "post": "# Note\n", "valid": False},
		{"name": "whitespace_front_matter_delimiter", "post": "--- \ndate: x\n---\n# Note\n", "valid": False},
		{"name": "raw_html", "post": _post("<script>alert(1)</script>"), "valid": False},
		{"name": "raw_declaration", "post": _post("<!DOCTYPE html>"), "valid": False},
		{"name": "raw_comment", "post": _post("<!-- not evidence -->"), "valid": False},
		{"name": "code_is_inert", "post": _post("`<script> [bad](javascript:alert(1)) { .bad }`\n\n```html\n<!-- bad -->\n```"), "valid": True},
		{"name": "ordinary_brace_and_angle_prose", "post": _post("A {small set} has 3 < 5 elements."), "valid": True},
		{"name": "raw_custom_element", "post": _post("<foo onclick=alert(1)>x</foo>"), "valid": False},
		{"name": "raw_custom_self_closing", "post": _post("<maker-widget/>"), "valid": False},
		{"name": "raw_svg_event", "post": _post("<svg/onload=alert(1)>"), "valid": False},
		{"name": "raw_mathml_link", "post": _post("<math><mi xlink:href=javascript:alert(1)>x</mi></math>"), "valid": False},
		{"name": "raw_processing_instruction", "post": _post("<?xml version='1.0'?>"), "valid": False},
		{"name": "raw_cdata", "post": _post("<![CDATA[not Markdown]]>"), "valid": False},
		{"name": "attribute_list", "post": _post("# Note { .unsafe }"), "valid": False},
		{"name": "inline_title", "post": _post("[GitHub](https://github.com/vosslab/project \"source title\")"), "valid": True},
		{"name": "nested_parentheses", "post": _post("[issue](https://github.com/vosslab/project/issues/(123))"), "valid": True},
		{"name": "approved_reference", "post": _post("[source][repo]\n\n[repo]: https://github.com/vosslab/project 'title'"), "valid": True},
		{"name": "unknown_reference", "post": _post("[source][missing]"), "valid": False},
		{"name": "unused_reference", "post": _post("[repo]: https://github.com/vosslab/project"), "valid": False},
		{"name": "malformed_reference", "post": _post("[repo]: <https://github.com/vosslab/project"), "valid": False},
		{"name": "javascript", "post": _post("[bad](javascript:alert(1))"), "valid": False},
		{"name": "data_url", "post": _post("[bad](data:text/html,boom)"), "valid": False},
		{"name": "protocol_relative", "post": _post("[bad](//github.com/vosslab/project)"), "valid": False},
		{"name": "mixed_case_scheme", "post": _post("[bad](HTTPS://github.com/vosslab/project)"), "valid": False},
		{"name": "userinfo", "post": _post("[bad](https://user@github.com/vosslab/project)"), "valid": False},
		{"name": "nondefault_port", "post": _post("[bad](https://github.com:444/vosslab/project)"), "valid": False},
		{"name": "control_character", "post": _post("[bad](https://github.com/vosslab/\u0001project)"), "valid": False},
		{"name": "whitespace_destination", "post": _post("[bad](https://github.com/vosslab/project not-a-title)"), "valid": False},
		{"name": "entity_evil_url", "post": _post("[bad](https&#58;//evil.example/project)"), "valid": False},
		{"name": "percent_evil_url", "post": _post("[bad](https%3A//evil.example/project)"), "valid": False},
		{"name": "encoded_asset", "post": _post("![bad](assets%2Fproof.png)"), "valid": False},
		{"name": "entity_asset", "post": _post("![bad](assets&#47;proof.png)"), "valid": False},
		{"name": "email_autolink", "post": _post("<author@example.com>"), "valid": False},
		{"name": "github_autolink", "post": _post("<https://api.github.com/repos/vosslab/project>"), "valid": True},
	],
	"schema_version": POLICY_VERSION,
}
CANONICAL_VECTOR_BYTES = daily_blog.io_utils.canonical_json_bytes(CANONICAL_VECTOR)
CANONICAL_VECTOR_SHA256 = daily_blog.io_utils.sha256_bytes(CANONICAL_VECTOR_BYTES)


#============================================
def policy_identity() -> dict[str, str]:
	"""Return the portable policy identity carried by every new bundle."""
	return {"version": POLICY_VERSION, "sha256": CANONICAL_VECTOR_SHA256}


#============================================
def policy_vector_bytes() -> bytes:
	"""Return the byte-exact cross-repository executable policy corpus."""
	return CANONICAL_VECTOR_BYTES


#============================================
def _body(post: str) -> str | None:
	"""Return a body only when the post has exact opening front matter."""
	match = _FRONT_MATTER_RE.match(post)
	return post[match.end():] if match else None


#============================================
def inert_source(source: str) -> str:
	"""Mask fenced and inline code without inspecting syntactically inert text."""
	masked = list(source)
	position = 0
	while True:
		match = _FENCE_START_RE.search(source, position)
		if match is None:
			break
		marker = match.group(1)
		end_re = re.compile(r"(?m)^[ \t]{0,3}" + re.escape(marker[0]) + "{" + str(len(marker)) + r",\}[ \t]*$")
		end = end_re.search(source, match.end())
		stop = end.end() if end is not None else len(source)
		for index in range(match.start(), stop):
			if masked[index] != "\n":
				masked[index] = " "
		position = stop
	index = 0
	while index < len(source):
		if source[index] != "`" or masked[index] == " ":
			index += 1
			continue
		end = index
		while end < len(source) and source[end] == "`":
			end += 1
		marker = source[index:end]
		closing = source.find(marker, end)
		if closing < 0 or "\n" in source[end:closing]:
			index = end
			continue
		for cursor in range(index, closing + len(marker)):
			if masked[cursor] != "\n":
				masked[cursor] = " "
		index = closing + len(marker)
	return "".join(masked)


#============================================
def _url_target(value: str) -> str | None:
	"""Normalize only external URLs before enforcing canonical HTTPS."""
	if not value or any(character.isspace() or ord(character) < 32 for character in value):
		return None
	value = urllib.parse.unquote(_ESCAPE_RE.sub(r"\1", html.unescape(value)))
	if not value or any(character.isspace() or ord(character) < 32 for character in value):
		return None
	return value


#============================================
def _target_is_allowed(value: str, approved_paths: frozenset[str]) -> bool:
	"""Allow exact declared assets or canonical GitHub HTTPS destinations only."""
	if value in approved_paths:
		return True
	url = _url_target(value)
	if url is None or not url.startswith("https://") or url.startswith("https:///"):
		return False
	try:
		parsed = urllib.parse.urlsplit(url)
		port = parsed.port
	except ValueError:
		return False
	if parsed.scheme != "https" or parsed.hostname not in {"github.com", "api.github.com"}:
		return False
	if parsed.username is not None or parsed.password is not None or port not in {None, 443}:
		return False
	return parsed.netloc in {"github.com", "api.github.com", "github.com:443", "api.github.com:443"}


#============================================
def _destination_and_title(value: str) -> str | None:
	"""Parse one Markdown destination and optional standard title."""
	if not value:
		return None
	if value.startswith("<"):
		end = value.find(">")
		if end < 1:
			return None
		destination, tail = value[1:end], value[end + 1:].strip()
	else:
		depth = 0
		end = 0
		while end < len(value):
			character = value[end]
			if character == "\\" and end + 1 < len(value):
				end += 2
				continue
			if character == "(":
				depth += 1
			elif character == ")":
				if depth == 0:
					break
				depth -= 1
			elif character.isspace() and depth == 0:
				break
			end += 1
		if end == 0 or depth:
			return None
		destination, tail = value[:end], value[end:].strip()
	if not tail:
		return destination
	if len(tail) < 2 or tail[0] not in {"\"", "'", "("}:
		return None
	closer = ")" if tail[0] == "(" else tail[0]
	if tail[-1] != closer or "\n" in tail:
		return None
	return destination


#============================================
def _inline_links(source: str) -> tuple[list[str], bool]:
	"""Return inline destinations and whether malformed inline syntax appeared."""
	targets = []
	malformed = False
	index = 0
	while index < len(source):
		start = source.find("[", index)
		if start < 0:
			break
		label_end = source.find("]", start + 1)
		if label_end < 0 or label_end + 1 >= len(source) or source[label_end + 1] != "(":
			index = start + 1
			continue
		depth = 1
		cursor = label_end + 2
		while cursor < len(source) and depth:
			if source[cursor] == "\\" and cursor + 1 < len(source):
				cursor += 2
				continue
			if source[cursor] == "(":
				depth += 1
			elif source[cursor] == ")":
				depth -= 1
			cursor += 1
		if depth:
			malformed = True
			index = label_end + 2
			continue
		target = _destination_and_title(source[label_end + 2:cursor - 1].strip())
		if target is None:
			malformed = True
		else:
			targets.append(target)
		index = cursor
	return targets, malformed


#============================================
def validate_post_source(post: object, approved_screenshot_paths: object) -> tuple[str, ...]:
	"""Return bounded categories for source unsafe to cross the publication boundary."""
	if type(post) is not str or type(approved_screenshot_paths) not in {list, set, frozenset, tuple}:
		return ("invalid_source",)
	if any(type(path) is not str for path in approved_screenshot_paths):
		return ("invalid_source",)
	body = _body(post)
	if body is None:
		return ("invalid_source",)
	source = inert_source(body)
	reasons = set()
	comment_spans = []
	for match in re.finditer(r"<!--.*?-->", source, re.DOTALL):
		comment_spans.append(match.span())
		if match.group(0) != "<!-- more -->" and _EVIDENCE_COMMENT_RE.fullmatch(match.group(0)) is None:
			reasons.add("unsafe_comment")
	masked = list(source)
	for start, end in comment_spans:
		for index in range(start, end):
			masked[index] = " "
	source = "".join(masked)
	if "<!--" in source or "-->" in source:
		reasons.add("unsafe_comment")
	if _ATTRIBUTE_LIST_RE.search(source):
		reasons.add("markdown_attribute_list")
	approved_paths = frozenset(approved_screenshot_paths)
	definitions = {}
	definition_lines = set()
	for line_number, line in enumerate(source.splitlines()):
		match = _REFERENCE_DEFINITION_START_RE.fullmatch(line)
		if match is None:
			if re.match(r"^[ \t]{0,3}\[[^\]\n]+\]:", line):
				reasons.add("unsafe_link")
			continue
		definition_lines.add(line_number)
		label = match.group(1).strip().casefold()
		target = _destination_and_title(match.group(2).strip())
		if not label or target is None or not _target_is_allowed(target, approved_paths):
			reasons.add("unsafe_link")
			continue
		definitions[label] = target
	inline_targets, malformed = _inline_links(source)
	if malformed:
		reasons.add("unsafe_link")
	for target in inline_targets:
		if not _target_is_allowed(target, approved_paths):
			reasons.add("unsafe_link")
	used_definitions = set()
	for line_number, line in enumerate(source.splitlines()):
		if line_number in definition_lines:
			continue
		for match in _REFERENCE_USE_RE.finditer(line):
			if match.end() < len(line) and line[match.end()] == "(":
				continue
			label = (match.group(2) if match.group(2) else match.group(1)).strip().casefold()
			if label not in definitions:
				reasons.add("unsafe_link")
			else:
				used_definitions.add(label)
	if set(definitions) != used_definitions:
		reasons.add("unsafe_link")
	angle_spans = []
	for match in _ANGLE_RE.finditer(source):
		target = match.group(1)
		if target.startswith(("http:", "https:", "//")) or "@" in target:
			angle_spans.append(match.span())
			if not _target_is_allowed(target, approved_paths):
				reasons.add("unsafe_link")
	angle_mask = list(source)
	for start, end in angle_spans:
		for index in range(start, end):
			angle_mask[index] = " "
	if _RAW_HTML_RE.search("".join(angle_mask)):
		reasons.add("raw_html")
	return tuple(sorted(reasons))

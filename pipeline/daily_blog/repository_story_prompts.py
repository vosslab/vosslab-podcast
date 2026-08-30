"""Versioned prompt resources and strict verdicts for repository stories."""

# Standard Library
import dataclasses
import json
import re

# local repo modules
import daily_blog.io_utils
import daily_blog.prompt_resources


REPOSITORY_STORY_PROMPT_VERSION = "repository-story-v1"
MAX_OUTLINE_CONTEXT_CHARS = 30000
MAX_EVIDENCE_CONTEXT_CHARS = 60000
MAX_CANDIDATE_STORIES_CHARS = 80000
MAX_RUBRIC_CHARS = 16000
MAX_RUBRIC_IDENTITY_CHARS = 256
MAX_COMPARISON_PROMPT_CHARS = 120000
MAX_REPAIR_RESPONSE_CHARS = 4000
MAX_VERDICT_REASON_CHARS = 500
_RESOURCE_NAME_RE = re.compile(r"[a-z0-9_]+_v[0-9]+\.txt\Z")
_REPLICA_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

WRITER_TEMPLATE = "daily_blog_repository_story_writer_v1.txt"
EDITOR_TEMPLATE = "daily_blog_repository_story_editor_v1.txt"
COMPARISON_TEMPLATE = "daily_blog_repository_story_comparison_v1.txt"
REPAIR_TEMPLATE = "daily_blog_repository_story_verdict_repair_v1.txt"
REPOSITORY_STORY_RESOURCE_NAMES = frozenset({
	WRITER_TEMPLATE,
	EDITOR_TEMPLATE,
	COMPARISON_TEMPLATE,
	REPAIR_TEMPLATE,
})
PINNED_RESOURCE_SHA256 = {
	"daily_blog_repository_story_comparison_v1.txt": "1a164dd5dd29c3b34d803c5f77d962a6bfb62131b933ed4ee8c1ee10d722383c",
	"daily_blog_repository_story_editor_v1.txt": "8d87027b34671ff135bce9e668287637f17f4876f9fa46cad108ada728534edc",
	"daily_blog_repository_story_verdict_repair_v1.txt": "ccbc7c3f8c2c55f7a30d9bbbac1e297f99af2d1191373eb2145741071d3f24c7",
	"daily_blog_repository_story_writer_v1.txt": "cb851bca50652cf98e7505e259a7574318881a0ee828114214e1499645e5ba42",
}


class RepositoryStoryVerdictParseError(RuntimeError):
	"""A repository-story verdict misses the exact structured contract."""


@dataclasses.dataclass(frozen=True)
class RepositoryStoryPromptContract:
	"""One immutable, content-addressed prompt set for Stage 4."""

	version: str
	templates: tuple[tuple[str, str], ...]
	resource_sha256: tuple[tuple[str, str], ...]
	resource_bytes: tuple[tuple[str, bytes], ...] = dataclasses.field(repr=False)
	integrity_sha256: str

	#============================================
	def text(self, name: str) -> str:
		"""Return one validated template by its stable resource name."""
		if name not in REPOSITORY_STORY_RESOURCE_NAMES:
			raise RuntimeError("Repository-story prompt resource is unavailable.")
		return dict(self.templates)[name]

	#============================================
	def identity_dict(self) -> dict[str, object]:
		"""Return durable prompt provenance without copying prompt bodies."""
		return {
			"version": self.version,
			"resources": dict(self.resource_sha256),
			"integrity_sha256": self.integrity_sha256,
		}


#============================================
def _validate_resource_name(name: object) -> str:
	"""Require one owned bare prompt filename."""
	if type(name) is not str or name not in REPOSITORY_STORY_RESOURCE_NAMES:
		raise RuntimeError("Repository-story prompt resource is unavailable.")
	if _RESOURCE_NAME_RE.fullmatch(name) is None:
		raise RuntimeError("Repository-story prompt resource name is invalid.")
	return name


#============================================
def _validate_template_placeholders(name: str, text: str) -> None:
	"""Require the exact bounded values owned by each prompt renderer."""
	required = {
		WRITER_TEMPLATE: {"repo_outline_json", "evidence_json", "replica_id"},
		EDITOR_TEMPLATE: {"repo_outline_json", "evidence_json", "candidate_stories_json", "replica_id"},
		COMPARISON_TEMPLATE: {
			"rubric_identity", "rubric", "repo_outline_json", "evidence_json", "candidate_a", "candidate_b",
		},
		REPAIR_TEMPLATE: {"response"},
	}[name]
	found = set(_PLACEHOLDER_RE.findall(text))
	if found != required:
		raise RuntimeError(f"Repository-story prompt placeholders are invalid: {name}")
	if "{" in _PLACEHOLDER_RE.sub("", text) or "}" in _PLACEHOLDER_RE.sub("", text):
		raise RuntimeError(f"Repository-story prompt braces are invalid: {name}")


#============================================
def load_repository_story_prompt_contract() -> RepositoryStoryPromptContract:
	"""Load the owned Stage 4 assets once with exact byte identities."""
	templates: list[tuple[str, str]] = []
	digests: list[tuple[str, str]] = []
	contents_by_name: list[tuple[str, bytes]] = []
	for name in sorted(REPOSITORY_STORY_RESOURCE_NAMES):
		_validate_resource_name(name)
		text, contents = daily_blog.prompt_resources.load_allowlisted_instruction_prompt_with_bytes(
			name, REPOSITORY_STORY_RESOURCE_NAMES, "repository-story prompt contract",
		)
		_validate_template_placeholders(name, text)
		digest = daily_blog.io_utils.sha256_text(contents.decode("utf-8"))
		if digest != PINNED_RESOURCE_SHA256[name]:
			raise RuntimeError(f"Repository-story prompt bytes do not match the pinned asset: {name}")
		templates.append((name, text))
		digests.append((name, digest))
		contents_by_name.append((name, contents))
	identity = {
		"version": REPOSITORY_STORY_PROMPT_VERSION,
		"pinned_resources": PINNED_RESOURCE_SHA256,
		"resources": dict(digests),
	}
	return RepositoryStoryPromptContract(
		REPOSITORY_STORY_PROMPT_VERSION, tuple(templates), tuple(digests), tuple(contents_by_name),
		daily_blog.io_utils.hash_value(identity),
	)


#============================================
def repository_story_prompt_identity(
	contract: RepositoryStoryPromptContract | None = None,
) -> dict[str, object]:
	"""Return exact content-addressed Stage 4 prompt provenance."""
	value = contract if contract is not None else load_repository_story_prompt_contract()
	if type(value) is not RepositoryStoryPromptContract:
		raise RuntimeError("Repository-story prompt contract type is invalid.")
	if value.version != REPOSITORY_STORY_PROMPT_VERSION:
		raise RuntimeError("Repository-story prompt contract version is invalid.")
	if tuple(name for name, _text in value.templates) != tuple(sorted(REPOSITORY_STORY_RESOURCE_NAMES)):
		raise RuntimeError("Repository-story prompt templates are incomplete.")
	if tuple(name for name, _digest in value.resource_sha256) != tuple(sorted(REPOSITORY_STORY_RESOURCE_NAMES)):
		raise RuntimeError("Repository-story prompt identities are incomplete.")
	if tuple(name for name, _contents in value.resource_bytes) != tuple(sorted(REPOSITORY_STORY_RESOURCE_NAMES)):
		raise RuntimeError("Repository-story prompt bytes are incomplete.")
	if dict(value.resource_sha256) != PINNED_RESOURCE_SHA256:
		raise RuntimeError("Repository-story prompt identities do not match pinned assets.")
	if any(_SHA256_RE.fullmatch(digest) is None for _name, digest in value.resource_sha256):
		raise RuntimeError("Repository-story prompt resource identity is invalid.")
	for name, contents in value.resource_bytes:
		if type(contents) is not bytes:
			raise RuntimeError("Repository-story prompt bytes are invalid.")
		try:
			text = contents.decode("utf-8").strip()
		except UnicodeDecodeError as error:
			raise RuntimeError("Repository-story prompt bytes are invalid.") from error
		if text != value.text(name):
			raise RuntimeError("Repository-story prompt text and bytes conflict.")
		if daily_blog.io_utils.sha256_text(contents.decode("utf-8")) != PINNED_RESOURCE_SHA256[name]:
			raise RuntimeError("Repository-story prompt bytes do not match pinned assets.")
	expected = daily_blog.io_utils.hash_value({
		"version": value.version, "pinned_resources": PINNED_RESOURCE_SHA256,
		"resources": dict(value.resource_sha256),
	})
	if value.integrity_sha256 != expected:
		raise RuntimeError("Repository-story prompt contract integrity is invalid.")
	return value.identity_dict()


#============================================
def _bounded_text(value: object, label: str, maximum: int) -> str:
	"""Require one exact context component within its stage budget."""
	if type(value) is not str or not value or len(value) > maximum:
		raise RuntimeError(f"Repository-story {label} is invalid or exceeds its limit.")
	return value


#============================================
def _replica_id(value: object) -> str:
	"""Require an assignment identity without editorial ordering meaning."""
	if type(value) is not str or _REPLICA_ID_RE.fullmatch(value) is None:
		raise RuntimeError("Repository-story replica identity is invalid.")
	return value


#============================================
def _rubric_identity(value: object) -> str:
	"""Require an externally selected, durable rubric identity."""
	if type(value) is not str or not value or len(value) > MAX_RUBRIC_IDENTITY_CHARS:
		raise RuntimeError("Repository-story rubric identity is invalid.")
	return value


#============================================
def _render(contract: RepositoryStoryPromptContract, name: str, values: dict[str, str], maximum: int) -> str:
	"""Render a complete owned template after exact contract validation."""
	repository_story_prompt_identity(contract)
	template = contract.text(name)
	if set(values) != set(_PLACEHOLDER_RE.findall(template)):
		raise RuntimeError("Repository-story prompt values do not match the template.")
	rendered = template.format(**values)
	if len(rendered) > maximum:
		raise RuntimeError("Repository-story rendered prompt exceeds its configured limit.")
	return rendered


#============================================
def render_repository_story_writer(
	repo_outline_json: str,
	evidence_json: str,
	replica_id: str,
	contract: RepositoryStoryPromptContract | None = None,
) -> str:
	"""Render one bounded whole-story writer task."""
	value = contract if contract is not None else load_repository_story_prompt_contract()
	return _render(value, WRITER_TEMPLATE, {
		"repo_outline_json": _bounded_text(repo_outline_json, "outline context", MAX_OUTLINE_CONTEXT_CHARS),
		"evidence_json": _bounded_text(evidence_json, "evidence context", MAX_EVIDENCE_CONTEXT_CHARS),
		"replica_id": _replica_id(replica_id),
	}, MAX_OUTLINE_CONTEXT_CHARS + MAX_EVIDENCE_CONTEXT_CHARS + 5000)


#============================================
def render_repository_story_editor(
	repo_outline_json: str,
	evidence_json: str,
	candidate_stories_json: str,
	replica_id: str,
	contract: RepositoryStoryPromptContract | None = None,
) -> str:
	"""Render one bounded anonymous whole-story editor task."""
	value = contract if contract is not None else load_repository_story_prompt_contract()
	return _render(value, EDITOR_TEMPLATE, {
		"repo_outline_json": _bounded_text(repo_outline_json, "outline context", MAX_OUTLINE_CONTEXT_CHARS),
		"evidence_json": _bounded_text(evidence_json, "evidence context", MAX_EVIDENCE_CONTEXT_CHARS),
		"candidate_stories_json": _bounded_text(
			candidate_stories_json, "candidate stories", MAX_CANDIDATE_STORIES_CHARS,
		),
		"replica_id": _replica_id(replica_id),
	}, MAX_OUTLINE_CONTEXT_CHARS + MAX_EVIDENCE_CONTEXT_CHARS + MAX_CANDIDATE_STORIES_CHARS + 5000)


#============================================
def render_repository_story_comparison(
	repo_outline_json: str,
	evidence_json: str,
	candidate_a: str,
	candidate_b: str,
	rubric: str,
	rubric_identity: str,
	contract: RepositoryStoryPromptContract | None = None,
) -> str:
	"""Render a rubric-first anonymous comparison in its supplied order."""
	value = contract if contract is not None else load_repository_story_prompt_contract()
	return _render(value, COMPARISON_TEMPLATE, {
		"repo_outline_json": _bounded_text(repo_outline_json, "outline context", MAX_OUTLINE_CONTEXT_CHARS),
		"evidence_json": _bounded_text(evidence_json, "evidence context", MAX_EVIDENCE_CONTEXT_CHARS),
		"candidate_a": _bounded_text(candidate_a, "candidate A", MAX_CANDIDATE_STORIES_CHARS),
		"candidate_b": _bounded_text(candidate_b, "candidate B", MAX_CANDIDATE_STORIES_CHARS),
		"rubric": _bounded_text(rubric, "rubric", MAX_RUBRIC_CHARS),
		"rubric_identity": _rubric_identity(rubric_identity),
	}, MAX_COMPARISON_PROMPT_CHARS)


#============================================
def render_repository_story_verdict_repair(
	response: str,
	contract: RepositoryStoryPromptContract | None = None,
) -> str:
	"""Render the single bounded format-repair task for one verdict response."""
	value = contract if contract is not None else load_repository_story_prompt_contract()
	return _render(value, REPAIR_TEMPLATE, {
		"response": _bounded_text(response, "repair response", MAX_REPAIR_RESPONSE_CHARS),
	}, MAX_REPAIR_RESPONSE_CHARS + 3000)


#============================================
def parse_repository_story_verdict(
	response: str,
	allowed_labels: frozenset[str] = frozenset({"A", "B"}),
) -> dict[str, object]:
	"""Parse one exact anonymous comparison verdict without a candidate identity."""
	if type(response) is not str or len(response) > MAX_REPAIR_RESPONSE_CHARS:
		raise RepositoryStoryVerdictParseError("Repository-story verdict exceeds its response budget.")
	if type(allowed_labels) is not frozenset or allowed_labels != frozenset({"A", "B"}):
		raise RuntimeError("Repository-story verdict labels are invalid.")
	try:
		value = json.loads(response.strip())
	except json.JSONDecodeError as error:
		raise RepositoryStoryVerdictParseError("Repository-story verdict is not valid JSON.") from error
	if type(value) is not dict or set(value) != {"winner", "reason", "evidence_quality", "confidence"}:
		raise RepositoryStoryVerdictParseError("Repository-story verdict fields are invalid.")
	if type(value["winner"]) is not str or value["winner"] not in allowed_labels | {"NONE"}:
		raise RepositoryStoryVerdictParseError("Repository-story verdict winner is invalid.")
	if type(value["reason"]) is not str or not value["reason"].strip() or len(value["reason"].strip()) > MAX_VERDICT_REASON_CHARS:
		raise RepositoryStoryVerdictParseError("Repository-story verdict reason is invalid.")
	if type(value["evidence_quality"]) is not str or value["evidence_quality"] not in {"high", "medium", "low"}:
		raise RepositoryStoryVerdictParseError("Repository-story verdict evidence quality is invalid.")
	if type(value["confidence"]) not in {int, float} or not 0 <= value["confidence"] <= 1:
		raise RepositoryStoryVerdictParseError("Repository-story verdict confidence is invalid.")
	return {
		"winner": value["winner"], "reason": value["reason"].strip(),
		"evidence_quality": value["evidence_quality"], "confidence": float(value["confidence"]),
	}

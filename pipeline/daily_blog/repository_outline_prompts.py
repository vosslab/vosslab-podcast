"""Versioned prompt resources and strict verdicts for repository outlines."""

# Standard Library
import dataclasses
import json
import re

# local repo modules
import daily_blog.io_utils
import daily_blog.prompt_resources


REPOSITORY_OUTLINE_PROMPT_VERSION = "repository-outline-v1"
MAX_EVIDENCE_CONTEXT_CHARS = 60000
MAX_CANDIDATE_OUTLINES_CHARS = 60000
MAX_COMPARISON_PROMPT_CHARS = 90000
MAX_REPAIR_RESPONSE_CHARS = 4000
MAX_VERDICT_REASON_CHARS = 500
_RESOURCE_NAME_RE = re.compile(r"[a-z0-9_]+_v[0-9]+\.(?:txt|md)\Z")
_REPLICA_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

GENERATOR_TEMPLATE = "repository_outline_generator_v1.txt"
MERGER_TEMPLATE = "repository_outline_merger_v1.txt"
RUBRIC_RESOURCE = "repository_outline_rubric_v1.md"
COMPARISON_TEMPLATE = "repository_outline_comparison_v1.txt"
REPAIR_TEMPLATE = "repository_outline_verdict_repair_v1.txt"
REPOSITORY_OUTLINE_RESOURCE_NAMES = frozenset({
	GENERATOR_TEMPLATE,
	MERGER_TEMPLATE,
	RUBRIC_RESOURCE,
	COMPARISON_TEMPLATE,
	REPAIR_TEMPLATE,
})
PINNED_RESOURCE_SHA256 = {
	"repository_outline_comparison_v1.txt": "084140fa6d3d103878db8e181d9623b345536c908bdce720d851f228cb5c16ad",
	"repository_outline_generator_v1.txt": "357014c83af0b08f9151c3d3d7326d6bfaac8cc51eb11b0ed64005af2a13bed1",
	"repository_outline_merger_v1.txt": "ae206dcca3bec5428d74819405b2cfd57672b5e6b8db082293a7562db562f52c",
	"repository_outline_rubric_v1.md": "3efa235111913cb67ab961d5bd75f1754d52887a914b7a19876b9974d3468633",
	"repository_outline_verdict_repair_v1.txt": "75fab060d5bb1a8bc25a219a896762a06d7284d30e893bfe9426f810c1b2e718",
}


class RepositoryOutlineVerdictParseError(RuntimeError):
	"""A repository-outline verdict misses the exact structured contract."""


@dataclasses.dataclass(frozen=True)
class RepositoryOutlinePromptContract:
	"""One immutable, content-addressed prompt set for Stage 3."""

	version: str
	templates: tuple[tuple[str, str], ...]
	resource_sha256: tuple[tuple[str, str], ...]
	resource_bytes: tuple[tuple[str, bytes], ...] = dataclasses.field(repr=False)
	integrity_sha256: str

	#============================================
	def text(self, name: str) -> str:
		"""Return one validated template by its stable resource name."""
		if name not in REPOSITORY_OUTLINE_RESOURCE_NAMES:
			raise RuntimeError("Repository-outline prompt resource is unavailable.")
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
	if type(name) is not str or name not in REPOSITORY_OUTLINE_RESOURCE_NAMES:
		raise RuntimeError("Repository-outline prompt resource is unavailable.")
	if _RESOURCE_NAME_RE.fullmatch(name) is None:
		raise RuntimeError("Repository-outline prompt resource name is invalid.")
	return name


#============================================
def _validate_template_placeholders(name: str, text: str) -> None:
	"""Require the exact bounded values owned by each prompt renderer."""
	required = {
		GENERATOR_TEMPLATE: {"evidence_json", "replica_id"},
		MERGER_TEMPLATE: {"evidence_json", "candidate_outlines_json", "replica_id"},
		RUBRIC_RESOURCE: set(),
		COMPARISON_TEMPLATE: {"rubric", "evidence_json", "candidate_a", "candidate_b"},
		REPAIR_TEMPLATE: {"response"},
	}[name]
	found = set(_PLACEHOLDER_RE.findall(text))
	if found != required:
		raise RuntimeError(f"Repository-outline prompt placeholders are invalid: {name}")
	if "{" in _PLACEHOLDER_RE.sub("", text) or "}" in _PLACEHOLDER_RE.sub("", text):
		raise RuntimeError(f"Repository-outline prompt braces are invalid: {name}")


#============================================
def load_repository_outline_prompt_contract() -> RepositoryOutlinePromptContract:
	"""Load the owned Stage 3 assets once with exact byte identities."""
	templates: list[tuple[str, str]] = []
	digests: list[tuple[str, str]] = []
	contents_by_name: list[tuple[str, bytes]] = []
	for name in sorted(REPOSITORY_OUTLINE_RESOURCE_NAMES):
		_validate_resource_name(name)
		text, contents = daily_blog.prompt_resources.load_allowlisted_instruction_prompt_with_bytes(
			name, REPOSITORY_OUTLINE_RESOURCE_NAMES, "repository-outline prompt contract",
		)
		_validate_template_placeholders(name, text)
		digest = daily_blog.io_utils.sha256_text(contents.decode("utf-8"))
		if digest != PINNED_RESOURCE_SHA256[name]:
			raise RuntimeError(f"Repository-outline prompt bytes do not match the pinned asset: {name}")
		templates.append((name, text))
		digests.append((name, digest))
		contents_by_name.append((name, contents))
	identity = {
		"version": REPOSITORY_OUTLINE_PROMPT_VERSION,
		"pinned_resources": PINNED_RESOURCE_SHA256,
		"resources": dict(digests),
	}
	return RepositoryOutlinePromptContract(
		REPOSITORY_OUTLINE_PROMPT_VERSION, tuple(templates), tuple(digests), tuple(contents_by_name),
		daily_blog.io_utils.hash_value(identity),
	)


#============================================
def repository_outline_prompt_identity(
	contract: RepositoryOutlinePromptContract | None = None,
) -> dict[str, object]:
	"""Return exact content-addressed Stage 3 prompt provenance."""
	value = contract if contract is not None else load_repository_outline_prompt_contract()
	if type(value) is not RepositoryOutlinePromptContract:
		raise RuntimeError("Repository-outline prompt contract type is invalid.")
	if value.version != REPOSITORY_OUTLINE_PROMPT_VERSION:
		raise RuntimeError("Repository-outline prompt contract version is invalid.")
	if tuple(name for name, _text in value.templates) != tuple(sorted(REPOSITORY_OUTLINE_RESOURCE_NAMES)):
		raise RuntimeError("Repository-outline prompt templates are incomplete.")
	if tuple(name for name, _digest in value.resource_sha256) != tuple(sorted(REPOSITORY_OUTLINE_RESOURCE_NAMES)):
		raise RuntimeError("Repository-outline prompt identities are incomplete.")
	if tuple(name for name, _contents in value.resource_bytes) != tuple(sorted(REPOSITORY_OUTLINE_RESOURCE_NAMES)):
		raise RuntimeError("Repository-outline prompt bytes are incomplete.")
	if dict(value.resource_sha256) != PINNED_RESOURCE_SHA256:
		raise RuntimeError("Repository-outline prompt identities do not match pinned assets.")
	if any(_SHA256_RE.fullmatch(digest) is None for _name, digest in value.resource_sha256):
		raise RuntimeError("Repository-outline prompt resource identity is invalid.")
	for name, contents in value.resource_bytes:
		if type(contents) is not bytes:
			raise RuntimeError("Repository-outline prompt bytes are invalid.")
		try:
			text = contents.decode("utf-8").strip()
		except UnicodeDecodeError as error:
			raise RuntimeError("Repository-outline prompt bytes are invalid.") from error
		if text != value.text(name):
			raise RuntimeError("Repository-outline prompt text and bytes conflict.")
		if daily_blog.io_utils.sha256_text(contents.decode("utf-8")) != PINNED_RESOURCE_SHA256[name]:
			raise RuntimeError("Repository-outline prompt bytes do not match pinned assets.")
	expected = daily_blog.io_utils.hash_value({
		"version": value.version, "pinned_resources": PINNED_RESOURCE_SHA256,
		"resources": dict(value.resource_sha256),
	})
	if value.integrity_sha256 != expected:
		raise RuntimeError("Repository-outline prompt contract integrity is invalid.")
	return value.identity_dict()


#============================================
def _bounded_text(value: object, label: str, maximum: int) -> str:
	"""Require one exact context component within its stage budget."""
	if type(value) is not str or not value or len(value) > maximum:
		raise RuntimeError(f"Repository-outline {label} is invalid or exceeds its limit.")
	return value


#============================================
def _replica_id(value: object) -> str:
	"""Require one bounded assignment identity without editorial ordering meaning."""
	if type(value) is not str or _REPLICA_ID_RE.fullmatch(value) is None:
		raise RuntimeError("Repository-outline replica identity is invalid.")
	return value


#============================================
def _render(contract: RepositoryOutlinePromptContract, name: str, values: dict[str, str], maximum: int) -> str:
	"""Render a complete owned template after exact contract validation."""
	repository_outline_prompt_identity(contract)
	template = contract.text(name)
	if set(values) != set(_PLACEHOLDER_RE.findall(template)):
		raise RuntimeError("Repository-outline prompt values do not match the template.")
	rendered = template.format(**values)
	if len(rendered) > maximum:
		raise RuntimeError("Repository-outline rendered prompt exceeds its configured limit.")
	return rendered


#============================================
def render_repository_outline_generator(
	evidence_json: str,
	replica_id: str,
	contract: RepositoryOutlinePromptContract | None = None,
) -> str:
	"""Render one bounded evidence-grounded generator task."""
	value = contract if contract is not None else load_repository_outline_prompt_contract()
	return _render(value, GENERATOR_TEMPLATE, {
		"evidence_json": _bounded_text(evidence_json, "evidence context", MAX_EVIDENCE_CONTEXT_CHARS),
		"replica_id": _replica_id(replica_id),
	}, MAX_EVIDENCE_CONTEXT_CHARS + 4000)


#============================================
def render_repository_outline_merger(
	evidence_json: str,
	candidate_outlines_json: str,
	replica_id: str,
	contract: RepositoryOutlinePromptContract | None = None,
) -> str:
	"""Render one bounded anonymous whole-outline merger task."""
	value = contract if contract is not None else load_repository_outline_prompt_contract()
	return _render(value, MERGER_TEMPLATE, {
		"evidence_json": _bounded_text(evidence_json, "evidence context", MAX_EVIDENCE_CONTEXT_CHARS),
		"candidate_outlines_json": _bounded_text(
			candidate_outlines_json, "candidate outlines", MAX_CANDIDATE_OUTLINES_CHARS,
		),
		"replica_id": _replica_id(replica_id),
	}, MAX_EVIDENCE_CONTEXT_CHARS + MAX_CANDIDATE_OUTLINES_CHARS + 5000)


#============================================
def render_repository_outline_comparison(
	evidence_json: str,
	candidate_a: str,
	candidate_b: str,
	contract: RepositoryOutlinePromptContract | None = None,
) -> str:
	"""Render one rubric-first anonymous comparison in its supplied order."""
	value = contract if contract is not None else load_repository_outline_prompt_contract()
	return _render(value, COMPARISON_TEMPLATE, {
		"rubric": value.text(RUBRIC_RESOURCE),
		"evidence_json": _bounded_text(evidence_json, "evidence context", MAX_EVIDENCE_CONTEXT_CHARS),
		"candidate_a": _bounded_text(candidate_a, "candidate A", MAX_CANDIDATE_OUTLINES_CHARS),
		"candidate_b": _bounded_text(candidate_b, "candidate B", MAX_CANDIDATE_OUTLINES_CHARS),
	}, MAX_COMPARISON_PROMPT_CHARS)


#============================================
def render_repository_outline_verdict_repair(
	response: str,
	contract: RepositoryOutlinePromptContract | None = None,
) -> str:
	"""Render the single bounded format-repair task for one verdict response."""
	value = contract if contract is not None else load_repository_outline_prompt_contract()
	return _render(value, REPAIR_TEMPLATE, {
		"response": _bounded_text(response, "repair response", MAX_REPAIR_RESPONSE_CHARS),
	}, MAX_REPAIR_RESPONSE_CHARS + 3000)


#============================================
def parse_repository_outline_verdict(
	response: str,
	allowed_labels: frozenset[str] = frozenset({"A", "B"}),
) -> dict[str, object]:
	"""Parse one exact generic anonymous comparison verdict."""
	if type(response) is not str or len(response) > MAX_REPAIR_RESPONSE_CHARS:
		raise RepositoryOutlineVerdictParseError("Repository-outline verdict exceeds its response budget.")
	if type(allowed_labels) is not frozenset or allowed_labels != frozenset({"A", "B"}):
		raise RuntimeError("Repository-outline verdict labels are invalid.")
	try:
		value = json.loads(response.strip())
	except json.JSONDecodeError as error:
		raise RepositoryOutlineVerdictParseError("Repository-outline verdict is not valid JSON.") from error
	if type(value) is not dict or set(value) != {"winner", "reason", "evidence_quality", "confidence"}:
		raise RepositoryOutlineVerdictParseError("Repository-outline verdict fields are invalid.")
	if type(value["winner"]) is not str or value["winner"] not in allowed_labels | {"NONE"}:
		raise RepositoryOutlineVerdictParseError("Repository-outline verdict winner is invalid.")
	if type(value["reason"]) is not str or not value["reason"].strip() or len(value["reason"].strip()) > MAX_VERDICT_REASON_CHARS:
		raise RepositoryOutlineVerdictParseError("Repository-outline verdict reason is invalid.")
	if type(value["evidence_quality"]) is not str or value["evidence_quality"] not in {"high", "medium", "low"}:
		raise RepositoryOutlineVerdictParseError("Repository-outline verdict evidence quality is invalid.")
	if type(value["confidence"]) not in {int, float} or not 0 <= value["confidence"] <= 1:
		raise RepositoryOutlineVerdictParseError("Repository-outline verdict confidence is invalid.")
	return {
		"winner": value["winner"], "reason": value["reason"].strip(),
		"evidence_quality": value["evidence_quality"], "confidence": float(value["confidence"]),
	}

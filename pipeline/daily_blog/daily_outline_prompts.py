"""Versioned prompt resources and strict structured results for daily outlines."""

# Standard Library
import dataclasses
import json
import re

# local repo modules
import daily_blog.io_utils
import daily_blog.prompt_resources


DAILY_OUTLINE_PROMPT_VERSION = "daily-outline-v1"
MAX_STORIES_CONTEXT_CHARS = 100000
MAX_REPOSITORY_OUTLINES_CONTEXT_CHARS = 100000
MAX_EVIDENCE_CONTEXT_CHARS = 60000
MAX_RANKING_CONTEXT_CHARS = 16000
MAX_RUBRIC_CHARS = 16000
MAX_CANDIDATE_OUTLINE_CHARS = 80000
MAX_COMPARISON_PROMPT_CHARS = 300000
MAX_RESPONSE_CHARS = 8000
MAX_RATIONALE_CHARS = 800
MAX_VERDICT_REASON_CHARS = 500
_UNTRUSTED_BLOCK_LABELS = frozenset({
	"STORY_RANKING", "REPOSITORY_STORIES", "REPOSITORY_OUTLINES", "EVIDENCE_PACKETS",
	"STORY_RANKING_REVIEW", "CANDIDATE_A", "CANDIDATE_B", "PRIOR_RESPONSE",
})
_RESOURCE_NAME_RE = re.compile(r"[a-z0-9_]+_v[0-9]+\.(?:txt|md)\Z")
_REPLICA_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_SEMANTIC_ARTIFACT_ID_RE = re.compile(r"[0-9a-f]{64}\Z")
_PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

RANKING_TEMPLATE = "daily_blog_story_ranking_v1.txt"
RANKING_RUBRIC_RESOURCE = "daily_blog_story_ranking_rubric_v1.md"
RANKING_REVIEW_TEMPLATE = "daily_blog_story_ranking_review_v1.txt"
RANKING_REVIEW_REPAIR_TEMPLATE = "daily_blog_story_ranking_review_repair_v1.txt"
WRITER_TEMPLATE = "daily_blog_daily_outline_writer_v1.txt"
OUTLINE_RUBRIC_RESOURCE = "daily_blog_daily_outline_rubric_v1.md"
COMPARISON_TEMPLATE = "daily_blog_daily_outline_comparison_v1.txt"
REPAIR_TEMPLATE = "daily_blog_daily_outline_verdict_repair_v1.txt"
DAILY_OUTLINE_RESOURCE_NAMES = frozenset({
	RANKING_TEMPLATE, RANKING_RUBRIC_RESOURCE, RANKING_REVIEW_TEMPLATE,
	RANKING_REVIEW_REPAIR_TEMPLATE, WRITER_TEMPLATE, OUTLINE_RUBRIC_RESOURCE,
	COMPARISON_TEMPLATE, REPAIR_TEMPLATE,
})
PINNED_RESOURCE_SHA256 = {
	"daily_blog_daily_outline_comparison_v1.txt": "47eb85d8d3855501d1a4e9e3b14f624b841333893d332a4ac15435efb0a486ef",
	"daily_blog_daily_outline_rubric_v1.md": "dfca56e4309b3761ad6c9d55b9beecccdb66cedf954e2e14129687af52070c24",
	"daily_blog_daily_outline_verdict_repair_v1.txt": "c23be6c118e1144980f4d7139311c943cf608233e7677fa602a3b5605b83b329",
	"daily_blog_daily_outline_writer_v1.txt": "f4a443825640875d74a55772fe5890b15c4a794eab6a1a0ecea8dde336730e4a",
	"daily_blog_story_ranking_rubric_v1.md": "d96186dcd4bf0d3382e92be577a7106eabbb9fc9038522502fbbf7ad25e0ab2b",
	"daily_blog_story_ranking_review_v1.txt": "cf7f28f2d6af7089ee4f22c118805ebc688365e3e1d9ca47def84f57b5275d99",
	"daily_blog_story_ranking_review_repair_v1.txt": "e82b58cdfb8ce558771cc8be994d26d741b04342877b2dc14b1a4ed0cfbdfc46",
	"daily_blog_story_ranking_v1.txt": "e20f4809d5f281b98aa6cc9d750603325edab86594a88e132f08c4e9e64f5e2a",
}


class DailyOutlineRankingParseError(RuntimeError):
	"""A daily-story ranking misses its exact structured contract."""


class DailyOutlineVerdictParseError(RuntimeError):
	"""A daily-outline verdict misses its exact structured contract."""


@dataclasses.dataclass(frozen=True)
class DailyOutlinePromptContract:
	"""One immutable, content-addressed Stage 5 prompt set."""

	version: str
	templates: tuple[tuple[str, str], ...]
	resource_sha256: tuple[tuple[str, str], ...]
	resource_bytes: tuple[tuple[str, bytes], ...] = dataclasses.field(repr=False)
	integrity_sha256: str

	#============================================
	def text(self, name: str) -> str:
		"""Return one validated template by stable resource name."""
		if name not in DAILY_OUTLINE_RESOURCE_NAMES:
			raise RuntimeError("Daily-outline prompt resource is unavailable.")
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
	if type(name) is not str or name not in DAILY_OUTLINE_RESOURCE_NAMES:
		raise RuntimeError("Daily-outline prompt resource is unavailable.")
	if _RESOURCE_NAME_RE.fullmatch(name) is None:
		raise RuntimeError("Daily-outline prompt resource name is invalid.")
	return name


#============================================
def _validate_template_placeholders(name: str, text: str) -> None:
	"""Require exact renderer-owned interpolation fields for each asset."""
	required = {
		RANKING_TEMPLATE: {"rubric", "stories_json", "repository_outlines_json", "evidence_json", "replica_id"},
		RANKING_RUBRIC_RESOURCE: set(),
		RANKING_REVIEW_TEMPLATE: {
			"rubric", "candidate_ranking_json", "stories_json", "repository_outlines_json",
			"evidence_json", "replica_id",
		},
		RANKING_REVIEW_REPAIR_TEMPLATE: {"response"},
		WRITER_TEMPLATE: {"ranking_json", "stories_json", "repository_outlines_json", "evidence_json", "replica_id"},
		OUTLINE_RUBRIC_RESOURCE: set(),
		COMPARISON_TEMPLATE: {
			"rubric", "stories_json", "repository_outlines_json", "evidence_json", "candidate_a", "candidate_b",
		},
		REPAIR_TEMPLATE: {"response"},
	}[name]
	found = set(_PLACEHOLDER_RE.findall(text))
	if found != required:
		raise RuntimeError(f"Daily-outline prompt placeholders are invalid: {name}")
	if "{" in _PLACEHOLDER_RE.sub("", text) or "}" in _PLACEHOLDER_RE.sub("", text):
		raise RuntimeError(f"Daily-outline prompt braces are invalid: {name}")


#============================================
def load_daily_outline_prompt_contract() -> DailyOutlinePromptContract:
	"""Load the owned Stage 5 assets once with exact byte identities."""
	templates: list[tuple[str, str]] = []
	digests: list[tuple[str, str]] = []
	contents_by_name: list[tuple[str, bytes]] = []
	for name in sorted(DAILY_OUTLINE_RESOURCE_NAMES):
		_validate_resource_name(name)
		text, contents = daily_blog.prompt_resources.load_allowlisted_instruction_prompt_with_bytes(
			name, DAILY_OUTLINE_RESOURCE_NAMES, "daily-outline prompt contract",
		)
		_validate_template_placeholders(name, text)
		digest = daily_blog.io_utils.sha256_text(contents.decode("utf-8"))
		if digest != PINNED_RESOURCE_SHA256[name]:
			raise RuntimeError(f"Daily-outline prompt bytes do not match the pinned asset: {name}")
		templates.append((name, text))
		digests.append((name, digest))
		contents_by_name.append((name, contents))
	identity = {
		"version": DAILY_OUTLINE_PROMPT_VERSION,
		"pinned_resources": PINNED_RESOURCE_SHA256,
		"resources": dict(digests),
	}
	return DailyOutlinePromptContract(
		DAILY_OUTLINE_PROMPT_VERSION, tuple(templates), tuple(digests), tuple(contents_by_name),
		daily_blog.io_utils.hash_value(identity),
	)


#============================================
def daily_outline_prompt_identity(
	contract: DailyOutlinePromptContract | None = None,
) -> dict[str, object]:
	"""Return exact content-addressed Stage 5 prompt provenance."""
	value = contract if contract is not None else load_daily_outline_prompt_contract()
	if type(value) is not DailyOutlinePromptContract:
		raise RuntimeError("Daily-outline prompt contract type is invalid.")
	if value.version != DAILY_OUTLINE_PROMPT_VERSION:
		raise RuntimeError("Daily-outline prompt contract version is invalid.")
	if tuple(name for name, _text in value.templates) != tuple(sorted(DAILY_OUTLINE_RESOURCE_NAMES)):
		raise RuntimeError("Daily-outline prompt templates are incomplete.")
	if tuple(name for name, _digest in value.resource_sha256) != tuple(sorted(DAILY_OUTLINE_RESOURCE_NAMES)):
		raise RuntimeError("Daily-outline prompt identities are incomplete.")
	if tuple(name for name, _contents in value.resource_bytes) != tuple(sorted(DAILY_OUTLINE_RESOURCE_NAMES)):
		raise RuntimeError("Daily-outline prompt bytes are incomplete.")
	if dict(value.resource_sha256) != PINNED_RESOURCE_SHA256:
		raise RuntimeError("Daily-outline prompt identities do not match pinned assets.")
	if any(_SHA256_RE.fullmatch(digest) is None for _name, digest in value.resource_sha256):
		raise RuntimeError("Daily-outline prompt resource identity is invalid.")
	for name, contents in value.resource_bytes:
		if type(contents) is not bytes:
			raise RuntimeError("Daily-outline prompt bytes are invalid.")
		try:
			text = contents.decode("utf-8").strip()
		except UnicodeDecodeError as error:
			raise RuntimeError("Daily-outline prompt bytes are invalid.") from error
		if text != value.text(name):
			raise RuntimeError("Daily-outline prompt text and bytes conflict.")
		if daily_blog.io_utils.sha256_text(contents.decode("utf-8")) != PINNED_RESOURCE_SHA256[name]:
			raise RuntimeError("Daily-outline prompt bytes do not match pinned assets.")
	expected = daily_blog.io_utils.hash_value({
		"version": value.version, "pinned_resources": PINNED_RESOURCE_SHA256,
		"resources": dict(value.resource_sha256),
	})
	if value.integrity_sha256 != expected:
		raise RuntimeError("Daily-outline prompt contract integrity is invalid.")
	return value.identity_dict()


#============================================
def _bounded_text(value: object, label: str, maximum: int) -> str:
	"""Require one exact context component within the Stage 5 budget."""
	if type(value) is not str or not value or len(value) > maximum:
		raise RuntimeError(f"Daily-outline {label} is invalid or exceeds its limit.")
	return value


#============================================
def _replica_id(value: object) -> str:
	"""Require an assignment identity without editorial-order meaning."""
	if type(value) is not str or _REPLICA_ID_RE.fullmatch(value) is None:
		raise RuntimeError("Daily-outline replica identity is invalid.")
	return value


#============================================
def _untrusted_data_block(label: str, value: object, context_label: str, maximum: int) -> str:
	"""Serialize one untrusted payload so data cannot close or add prompt instructions."""
	if label not in _UNTRUSTED_BLOCK_LABELS:
		raise RuntimeError("Daily-outline untrusted data label is invalid.")
	literal = _bounded_text(value, context_label, maximum)
	payload = json.dumps(
		{"encoding": "utf-8-json-string", "literal_content": literal},
		ensure_ascii=True, separators=(",", ":"),
	).replace("<", "\\u003c").replace(">", "\\u003e")
	return f"<<BEGIN_UNTRUSTED_{label}_DATA>>\n{payload}\n<<END_UNTRUSTED_{label}_DATA>>"


#============================================
def _render(contract: DailyOutlinePromptContract, name: str, values: dict[str, str], maximum: int) -> str:
	"""Render one complete owned template after its identity is checked."""
	daily_outline_prompt_identity(contract)
	template = contract.text(name)
	if set(values) != set(_PLACEHOLDER_RE.findall(template)):
		raise RuntimeError("Daily-outline prompt values do not match the template.")
	rendered = template.format(**values)
	if len(rendered) > maximum:
		raise RuntimeError("Daily-outline rendered prompt exceeds its configured limit.")
	return rendered


#============================================
def render_story_ranking(
	stories_json: str, repository_outlines_json: str, evidence_json: str, replica_id: str,
	contract: DailyOutlinePromptContract | None = None,
) -> str:
	"""Render one all-story, evidence-grounded ranking task."""
	value = contract if contract is not None else load_daily_outline_prompt_contract()
	return _render(value, RANKING_TEMPLATE, {
		"rubric": _bounded_text(
			value.text(RANKING_RUBRIC_RESOURCE), "ranking rubric", MAX_RUBRIC_CHARS,
		),
		"stories_json": _untrusted_data_block(
			"REPOSITORY_STORIES", stories_json, "stories context", MAX_STORIES_CONTEXT_CHARS,
		),
		"repository_outlines_json": _untrusted_data_block(
			"REPOSITORY_OUTLINES", repository_outlines_json, "repository outlines context",
			MAX_REPOSITORY_OUTLINES_CONTEXT_CHARS,
		),
		"evidence_json": _untrusted_data_block(
			"EVIDENCE_PACKETS", evidence_json, "evidence context", MAX_EVIDENCE_CONTEXT_CHARS,
		),
		"replica_id": _replica_id(replica_id),
	}, MAX_STORIES_CONTEXT_CHARS + MAX_REPOSITORY_OUTLINES_CONTEXT_CHARS + MAX_EVIDENCE_CONTEXT_CHARS + MAX_RUBRIC_CHARS + 6000)


#============================================
def render_daily_outline_writer(
	ranking_json: str, stories_json: str, repository_outlines_json: str, evidence_json: str, replica_id: str,
	contract: DailyOutlinePromptContract | None = None,
) -> str:
	"""Render one whole authored-outline task with all eligible material present."""
	value = contract if contract is not None else load_daily_outline_prompt_contract()
	return _render(value, WRITER_TEMPLATE, {
		"ranking_json": _untrusted_data_block(
			"STORY_RANKING", ranking_json, "ranking context", MAX_RANKING_CONTEXT_CHARS,
		),
		"stories_json": _untrusted_data_block(
			"REPOSITORY_STORIES", stories_json, "stories context", MAX_STORIES_CONTEXT_CHARS,
		),
		"repository_outlines_json": _untrusted_data_block(
			"REPOSITORY_OUTLINES", repository_outlines_json, "repository outlines context",
			MAX_REPOSITORY_OUTLINES_CONTEXT_CHARS,
		),
		"evidence_json": _untrusted_data_block(
			"EVIDENCE_PACKETS", evidence_json, "evidence context", MAX_EVIDENCE_CONTEXT_CHARS,
		),
		"replica_id": _replica_id(replica_id),
	}, MAX_STORIES_CONTEXT_CHARS + MAX_REPOSITORY_OUTLINES_CONTEXT_CHARS + MAX_EVIDENCE_CONTEXT_CHARS + MAX_RANKING_CONTEXT_CHARS + 7000)


#============================================
def render_story_ranking_review(
	candidate_ranking_json: str, stories_json: str, repository_outlines_json: str, evidence_json: str,
	replica_id: str, contract: DailyOutlinePromptContract | None = None,
) -> str:
	"""Render one independent review of a complete anonymous ranking candidate."""
	value = contract if contract is not None else load_daily_outline_prompt_contract()
	return _render(value, RANKING_REVIEW_TEMPLATE, {
		"rubric": _bounded_text(
			value.text(RANKING_RUBRIC_RESOURCE), "ranking rubric", MAX_RUBRIC_CHARS,
		),
		"candidate_ranking_json": _untrusted_data_block(
			"STORY_RANKING_REVIEW", candidate_ranking_json, "ranking review candidate",
			MAX_RANKING_CONTEXT_CHARS,
		),
		"stories_json": _untrusted_data_block(
			"REPOSITORY_STORIES", stories_json, "stories context", MAX_STORIES_CONTEXT_CHARS,
		),
		"repository_outlines_json": _untrusted_data_block(
			"REPOSITORY_OUTLINES", repository_outlines_json, "repository outlines context",
			MAX_REPOSITORY_OUTLINES_CONTEXT_CHARS,
		),
		"evidence_json": _untrusted_data_block(
			"EVIDENCE_PACKETS", evidence_json, "evidence context", MAX_EVIDENCE_CONTEXT_CHARS,
		),
		"replica_id": _replica_id(replica_id),
	}, MAX_STORIES_CONTEXT_CHARS + MAX_REPOSITORY_OUTLINES_CONTEXT_CHARS + MAX_EVIDENCE_CONTEXT_CHARS + MAX_RANKING_CONTEXT_CHARS + MAX_RUBRIC_CHARS + 6000)


#============================================
def render_story_ranking_review_repair(
	response: str, contract: DailyOutlinePromptContract | None = None,
) -> str:
	"""Render the one bounded format-repair task for a ranking-review verdict."""
	value = contract if contract is not None else load_daily_outline_prompt_contract()
	return _render(value, RANKING_REVIEW_REPAIR_TEMPLATE, {
		"response": _untrusted_data_block(
			"PRIOR_RESPONSE", response, "ranking review repair response", MAX_RESPONSE_CHARS,
		),
	}, MAX_RESPONSE_CHARS + 3000)


#============================================
def render_daily_outline_comparison(
	stories_json: str, repository_outlines_json: str, evidence_json: str, candidate_a: str, candidate_b: str,
	contract: DailyOutlinePromptContract | None = None,
) -> str:
	"""Render a rubric-first anonymous outline comparison in supplied order."""
	value = contract if contract is not None else load_daily_outline_prompt_contract()
	return _render(value, COMPARISON_TEMPLATE, {
		"rubric": value.text(OUTLINE_RUBRIC_RESOURCE),
		"stories_json": _untrusted_data_block(
			"REPOSITORY_STORIES", stories_json, "stories context", MAX_STORIES_CONTEXT_CHARS,
		),
		"repository_outlines_json": _untrusted_data_block(
			"REPOSITORY_OUTLINES", repository_outlines_json, "repository outlines context",
			MAX_REPOSITORY_OUTLINES_CONTEXT_CHARS,
		),
		"evidence_json": _untrusted_data_block(
			"EVIDENCE_PACKETS", evidence_json, "evidence context", MAX_EVIDENCE_CONTEXT_CHARS,
		),
		"candidate_a": _untrusted_data_block(
			"CANDIDATE_A", candidate_a, "candidate A", MAX_CANDIDATE_OUTLINE_CHARS,
		),
		"candidate_b": _untrusted_data_block(
			"CANDIDATE_B", candidate_b, "candidate B", MAX_CANDIDATE_OUTLINE_CHARS,
		),
	}, MAX_COMPARISON_PROMPT_CHARS)


#============================================
def render_daily_outline_verdict_repair(
	response: str, contract: DailyOutlinePromptContract | None = None,
) -> str:
	"""Render the one bounded format-repair task for an outline verdict."""
	value = contract if contract is not None else load_daily_outline_prompt_contract()
	return _render(value, REPAIR_TEMPLATE, {
		"response": _untrusted_data_block(
			"PRIOR_RESPONSE", response, "repair response", MAX_RESPONSE_CHARS,
		),
	}, MAX_RESPONSE_CHARS + 3000)


#============================================
def _expected_artifact_ids(value: object) -> tuple[str, ...]:
	"""Require a canonical complete Stage 5 candidate identity set."""
	if type(value) is not tuple or not value or any(type(item) is not str for item in value):
		raise RuntimeError("Daily-outline ranking expected artifact IDs are invalid.")
	if any(_SEMANTIC_ARTIFACT_ID_RE.fullmatch(item) is None for item in value):
		raise RuntimeError("Daily-outline ranking expected artifact IDs are invalid.")
	if len(set(value)) != len(value):
		raise RuntimeError("Daily-outline ranking expected artifact IDs are invalid.")
	return value


#============================================
def parse_story_ranking(response: str, expected_artifact_ids: tuple[str, ...]) -> dict[str, object]:
	"""Parse a complete identity-keyed ranking without retaining call position."""
	identifiers = _expected_artifact_ids(expected_artifact_ids)
	if type(response) is not str or len(response) > MAX_RESPONSE_CHARS:
		raise DailyOutlineRankingParseError("Daily-story ranking exceeds its response budget.")
	try:
		value = json.loads(response.strip())
	except json.JSONDecodeError as error:
		raise DailyOutlineRankingParseError("Daily-story ranking is not valid JSON.") from error
	if type(value) is not dict or set(value) != {"artifact_ids", "scores", "rationale"}:
		raise DailyOutlineRankingParseError("Daily-story ranking fields are invalid.")
	if type(value["artifact_ids"]) is not list or any(type(item) is not str for item in value["artifact_ids"]):
		raise DailyOutlineRankingParseError("Daily-story ranking order is invalid.")
	if len(value["artifact_ids"]) != len(identifiers) or set(value["artifact_ids"]) != set(identifiers):
		raise DailyOutlineRankingParseError("Daily-story ranking must order every supplied artifact exactly once.")
	if type(value["scores"]) is not dict or set(value["scores"]) != set(identifiers):
		raise DailyOutlineRankingParseError("Daily-story ranking scores are incomplete.")
	if any(type(score) is not int or isinstance(score, bool) or not 0 <= score <= 100 for score in value["scores"].values()):
		raise DailyOutlineRankingParseError("Daily-story ranking scores are invalid.")
	if type(value["rationale"]) is not str or not value["rationale"].strip() or len(value["rationale"].strip()) > MAX_RATIONALE_CHARS:
		raise DailyOutlineRankingParseError("Daily-story ranking rationale is invalid.")
	return {
		"artifact_ids": tuple(value["artifact_ids"]), "scores": dict(value["scores"]),
		"rationale": value["rationale"].strip(),
	}


#============================================
def _reject_duplicate_json_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
	"""Build one JSON object only when every member name is unique."""
	value: dict[str, object] = {}
	for key, item in pairs:
		if key in value:
			raise ValueError("JSON object contains duplicate members.")
		value[key] = item
	return value


#============================================
def parse_story_ranking_review_verdict(response: str) -> dict[str, object]:
	"""Parse one exact candidate-ranking eligibility verdict."""
	if type(response) is not str or len(response) > MAX_RESPONSE_CHARS:
		raise DailyOutlineVerdictParseError("Daily-story ranking review exceeds its response budget.")
	try:
		value = json.loads(response.strip(), object_pairs_hook=_reject_duplicate_json_members)
	except (json.JSONDecodeError, ValueError) as error:
		raise DailyOutlineVerdictParseError("Daily-story ranking review is not valid JSON.") from error
	if type(value) is not dict or set(value) != {"decision", "score", "reason"}:
		raise DailyOutlineVerdictParseError("Daily-story ranking review fields are invalid.")
	if type(value["decision"]) is not str or value["decision"] not in {"ACCEPT", "REJECT"}:
		raise DailyOutlineVerdictParseError("Daily-story ranking review decision is invalid.")
	if type(value["score"]) is not int or isinstance(value["score"], bool) or not 0 <= value["score"] <= 100:
		raise DailyOutlineVerdictParseError("Daily-story ranking review score is invalid.")
	if type(value["reason"]) is not str or not value["reason"].strip() or len(value["reason"].strip()) > MAX_VERDICT_REASON_CHARS:
		raise DailyOutlineVerdictParseError("Daily-story ranking review reason is invalid.")
	return {"decision": value["decision"], "score": value["score"], "reason": value["reason"].strip()}


#============================================
def parse_daily_outline_verdict(
	response: str, allowed_labels: frozenset[str] = frozenset({"A", "B"}),
) -> dict[str, object]:
	"""Parse one exact anonymous outline verdict before identity mapping."""
	if type(response) is not str or len(response) > MAX_RESPONSE_CHARS:
		raise DailyOutlineVerdictParseError("Daily-outline verdict exceeds its response budget.")
	if type(allowed_labels) is not frozenset or allowed_labels != frozenset({"A", "B"}):
		raise RuntimeError("Daily-outline verdict labels are invalid.")
	try:
		value = json.loads(response.strip())
	except json.JSONDecodeError as error:
		raise DailyOutlineVerdictParseError("Daily-outline verdict is not valid JSON.") from error
	if type(value) is not dict or set(value) != {"winner", "reason", "evidence_quality", "confidence"}:
		raise DailyOutlineVerdictParseError("Daily-outline verdict fields are invalid.")
	if type(value["winner"]) is not str or value["winner"] not in allowed_labels | {"NONE"}:
		raise DailyOutlineVerdictParseError("Daily-outline verdict winner is invalid.")
	if type(value["reason"]) is not str or not value["reason"].strip() or len(value["reason"].strip()) > MAX_VERDICT_REASON_CHARS:
		raise DailyOutlineVerdictParseError("Daily-outline verdict reason is invalid.")
	if type(value["evidence_quality"]) is not str or value["evidence_quality"] not in {"high", "medium", "low"}:
		raise DailyOutlineVerdictParseError("Daily-outline verdict evidence quality is invalid.")
	if type(value["confidence"]) not in {int, float} or isinstance(value["confidence"], bool) or not 0 <= value["confidence"] <= 1:
		raise DailyOutlineVerdictParseError("Daily-outline verdict confidence is invalid.")
	return {
		"winner": value["winner"], "reason": value["reason"].strip(),
		"evidence_quality": value["evidence_quality"], "confidence": float(value["confidence"]),
	}

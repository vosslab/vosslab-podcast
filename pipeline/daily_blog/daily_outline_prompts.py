"""Versioned prompt resources and strict structured results for daily outlines."""

# Standard Library
import json
import re

# local repo modules
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.loader


MAX_STORIES_CONTEXT_CHARS = 100000
MAX_REPOSITORY_OUTLINES_CONTEXT_CHARS = 100000
MAX_EVIDENCE_CONTEXT_CHARS = 60000
MAX_RANKING_CONTEXT_CHARS = 16000
MAX_RUBRIC_CHARS = 16000
MAX_CANDIDATE_OUTLINE_CHARS = 80000
MAX_COMPARISON_PROMPT_CHARS = 300000
MAX_RESPONSE_CHARS = 8000
# The rationale is data inside the one bounded response envelope.  A second,
# shorter hidden limit made otherwise contract-valid model responses fail.
MAX_RATIONALE_CHARS = MAX_RESPONSE_CHARS
MAX_VERDICT_REASON_CHARS = 500
_UNTRUSTED_BLOCK_LABELS = frozenset({
	"STORY_RANKING", "REPOSITORY_STORIES", "REPOSITORY_OUTLINES", "EVIDENCE_PACKETS",
	"STORY_RANKING_REVIEW", "CANDIDATE_A", "CANDIDATE_B", "PRIOR_RESPONSE",
})
_REPLICA_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_SEMANTIC_ARTIFACT_ID_RE = re.compile(r"[0-9a-f]{64}\Z")
_RANKING_PARSE_CATEGORIES = frozenset({
	"response_limit", "invalid_json", "invalid_fields", "invalid_order",
	"invalid_aliases", "invalid_scores", "invalid_rationale",
})


class DailyOutlineRankingParseError(RuntimeError):
	"""A daily-story ranking misses its exact structured contract."""

	def __init__(self, category: str) -> None:
		if category not in _RANKING_PARSE_CATEGORIES:
			raise RuntimeError("Daily-story ranking parse category is invalid.")
		self.category = category
		super().__init__("Daily-story ranking parse failed: " + category + ".")


class DailyOutlineVerdictParseError(RuntimeError):
	"""A daily-outline verdict misses its exact structured contract."""


def _loaded_prompts(
	value: daily_blog.prompt_registry.loader.LoadedPromptSet | None,
) -> daily_blog.prompt_registry.loader.LoadedPromptSet:
	"""Resolve the one central issued Stage 5 prompt set."""
	return daily_blog.prompt_registry.loader.resolve_loaded_prompt_set(
		value, daily_blog.prompt_registry.definitions.DAILY_OUTLINE_PROMPT_SET,
	)


#============================================
def daily_outline_prompt_identity(
	prompts: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None,
) -> dict[str, object]:
	"""Return the legacy Stage 5 cache identity from the central registry."""
	return _loaded_prompts(prompts).legacy_identity_dict()


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
def _render(
	prompts: daily_blog.prompt_registry.loader.LoadedPromptSet,
	resource: daily_blog.prompt_registry.definitions.RegisteredPromptResource,
	values: dict[str, str], maximum: int,
) -> str:
	"""Render one complete owned template after its identity is checked."""
	rendered = prompts.render(resource, values)
	if len(rendered) > maximum:
		raise RuntimeError("Daily-outline rendered prompt exceeds its configured limit.")
	return rendered


#============================================
def render_story_ranking(
	stories_json: str, repository_outlines_json: str, evidence_json: str, replica_id: str,
	prompts: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None,
) -> str:
	"""Render one all-story, evidence-grounded ranking task."""
	value = _loaded_prompts(prompts)
	return _render(value, daily_blog.prompt_registry.definitions.STORY_RANKING_RESOURCE, {
		"rubric": _bounded_text(
			value.text(daily_blog.prompt_registry.definitions.STORY_RANKING_RUBRIC_RESOURCE),
			"ranking rubric", MAX_RUBRIC_CHARS,
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
	prompts: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None,
) -> str:
	"""Render one whole authored-outline task with all eligible material present."""
	value = _loaded_prompts(prompts)
	return _render(value, daily_blog.prompt_registry.definitions.DAILY_OUTLINE_WRITER_RESOURCE, {
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
	replica_id: str, prompts: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None,
) -> str:
	"""Render one independent review of a complete anonymous ranking candidate."""
	value = _loaded_prompts(prompts)
	return _render(value, daily_blog.prompt_registry.definitions.STORY_RANKING_REVIEW_RESOURCE, {
		"rubric": _bounded_text(
			value.text(daily_blog.prompt_registry.definitions.STORY_RANKING_RUBRIC_RESOURCE),
			"ranking rubric", MAX_RUBRIC_CHARS,
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
	response: str, prompts: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None,
) -> str:
	"""Render the one bounded format-repair task for a ranking-review verdict."""
	value = _loaded_prompts(prompts)
	return _render(value, daily_blog.prompt_registry.definitions.STORY_RANKING_REVIEW_REPAIR_RESOURCE, {
		"response": _untrusted_data_block(
			"PRIOR_RESPONSE", response, "ranking review repair response", MAX_RESPONSE_CHARS,
		),
	}, MAX_RESPONSE_CHARS + 3000)


#============================================
def render_daily_outline_comparison(
	stories_json: str, repository_outlines_json: str, evidence_json: str, candidate_a: str, candidate_b: str,
	prompts: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None,
) -> str:
	"""Render a rubric-first anonymous outline comparison in supplied order."""
	value = _loaded_prompts(prompts)
	return _render(value, daily_blog.prompt_registry.definitions.DAILY_OUTLINE_COMPARISON_RESOURCE, {
		"rubric": value.text(daily_blog.prompt_registry.definitions.DAILY_OUTLINE_RUBRIC_RESOURCE),
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
	response: str, prompts: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None,
) -> str:
	"""Render the one bounded format-repair task for an outline verdict."""
	value = _loaded_prompts(prompts)
	return _render(value, daily_blog.prompt_registry.definitions.DAILY_OUTLINE_VERDICT_REPAIR_RESOURCE, {
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
		raise DailyOutlineRankingParseError("response_limit")
	try:
		value = json.loads(response.strip())
	except json.JSONDecodeError as error:
		raise DailyOutlineRankingParseError("invalid_json") from error
	if type(value) is not dict or set(value) != {"artifact_ids", "scores", "rationale"}:
		raise DailyOutlineRankingParseError("invalid_fields")
	if type(value["artifact_ids"]) is not list or any(type(item) is not str for item in value["artifact_ids"]):
		raise DailyOutlineRankingParseError("invalid_order")
	if len(value["artifact_ids"]) != len(identifiers) or set(value["artifact_ids"]) != set(identifiers):
		raise DailyOutlineRankingParseError("invalid_order")
	if type(value["scores"]) is not dict or set(value["scores"]) != set(identifiers):
		raise DailyOutlineRankingParseError("invalid_scores")
	if any(type(score) is not int or isinstance(score, bool) or not 0 <= score <= 100 for score in value["scores"].values()):
		raise DailyOutlineRankingParseError("invalid_scores")
	if type(value["rationale"]) is not str or not value["rationale"].strip() or len(value["rationale"].strip()) > MAX_RATIONALE_CHARS:
		raise DailyOutlineRankingParseError("invalid_rationale")
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

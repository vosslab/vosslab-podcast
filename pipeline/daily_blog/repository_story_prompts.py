"""Stage 4 renderers and strict verdict parsing."""

import json
import re

import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.loader


REPOSITORY_STORY_PROMPT_VERSION = "repository-story-v1"
MAX_OUTLINE_CONTEXT_CHARS = 30000
MAX_EVIDENCE_CONTEXT_CHARS = 60000
MAX_CANDIDATE_STORIES_CHARS = 80000
MAX_RUBRIC_CHARS = 16000
MAX_RUBRIC_IDENTITY_CHARS = 256
MAX_COMPARISON_PROMPT_CHARS = 120000
MAX_REPAIR_RESPONSE_CHARS = 4000
MAX_VERDICT_REASON_CHARS = 500
_REPLICA_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")


class RepositoryStoryVerdictParseError(RuntimeError):
	"""A repository-story verdict misses the exact structured contract."""


def _loaded(value: daily_blog.prompt_registry.loader.LoadedPromptSet | None) -> daily_blog.prompt_registry.loader.LoadedPromptSet:
	return daily_blog.prompt_registry.loader.resolve_loaded_prompt_set(
		value, daily_blog.prompt_registry.definitions.REPOSITORY_STORY_PROMPT_SET,
	)


def repository_story_prompt_identity(loaded: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None) -> dict[str, object]:
	"""Return durable Stage 4 prompt provenance in its legacy payload form."""
	return _loaded(loaded).legacy_identity_dict()


def _bounded_text(value: object, label: str, maximum: int) -> str:
	if type(value) is not str or not value or len(value) > maximum:
		raise RuntimeError(f"Repository-story {label} is invalid or exceeds its limit.")
	return value


def _replica_id(value: object) -> str:
	if type(value) is not str or _REPLICA_ID_RE.fullmatch(value) is None:
		raise RuntimeError("Repository-story replica identity is invalid.")
	return value


def _rubric_identity(value: object) -> str:
	if type(value) is not str or not value or len(value) > MAX_RUBRIC_IDENTITY_CHARS:
		raise RuntimeError("Repository-story rubric identity is invalid.")
	return value


def _render(loaded: daily_blog.prompt_registry.loader.LoadedPromptSet | None,
	resource: daily_blog.prompt_registry.definitions.RegisteredPromptResource, values: dict[str, str], maximum: int) -> str:
	rendered = _loaded(loaded).render(resource, values)
	if len(rendered) > maximum:
		raise RuntimeError("Repository-story rendered prompt exceeds its configured limit.")
	return rendered


def render_repository_story_writer(repo_outline_json: str, evidence_json: str, replica_id: str,
	loaded: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None) -> str:
	return _render(loaded, daily_blog.prompt_registry.definitions.REPOSITORY_STORY_WRITER_RESOURCE, {
		"repo_outline_json": _bounded_text(repo_outline_json, "outline context", MAX_OUTLINE_CONTEXT_CHARS),
		"evidence_json": _bounded_text(evidence_json, "evidence context", MAX_EVIDENCE_CONTEXT_CHARS),
		"replica_id": _replica_id(replica_id),
	}, MAX_OUTLINE_CONTEXT_CHARS + MAX_EVIDENCE_CONTEXT_CHARS + 5000)


def render_repository_story_editor(repo_outline_json: str, evidence_json: str, candidate_stories_json: str,
	replica_id: str, loaded: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None) -> str:
	return _render(loaded, daily_blog.prompt_registry.definitions.REPOSITORY_STORY_EDITOR_RESOURCE, {
		"repo_outline_json": _bounded_text(repo_outline_json, "outline context", MAX_OUTLINE_CONTEXT_CHARS),
		"evidence_json": _bounded_text(evidence_json, "evidence context", MAX_EVIDENCE_CONTEXT_CHARS),
		"candidate_stories_json": _bounded_text(candidate_stories_json, "candidate stories", MAX_CANDIDATE_STORIES_CHARS),
		"replica_id": _replica_id(replica_id),
	}, MAX_OUTLINE_CONTEXT_CHARS + MAX_EVIDENCE_CONTEXT_CHARS + MAX_CANDIDATE_STORIES_CHARS + 5000)


def render_repository_story_comparison(repo_outline_json: str, evidence_json: str, candidate_a: str,
	candidate_b: str, rubric: str, rubric_identity: str,
	loaded: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None) -> str:
	return _render(loaded, daily_blog.prompt_registry.definitions.REPOSITORY_STORY_COMPARISON_RESOURCE, {
		"repo_outline_json": _bounded_text(repo_outline_json, "outline context", MAX_OUTLINE_CONTEXT_CHARS),
		"evidence_json": _bounded_text(evidence_json, "evidence context", MAX_EVIDENCE_CONTEXT_CHARS),
		"candidate_a": _bounded_text(candidate_a, "candidate A", MAX_CANDIDATE_STORIES_CHARS),
		"candidate_b": _bounded_text(candidate_b, "candidate B", MAX_CANDIDATE_STORIES_CHARS),
		"rubric": _bounded_text(rubric, "rubric", MAX_RUBRIC_CHARS),
		"rubric_identity": _rubric_identity(rubric_identity),
	}, MAX_COMPARISON_PROMPT_CHARS)


def render_repository_story_verdict_repair(response: str,
	loaded: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None) -> str:
	return _render(loaded, daily_blog.prompt_registry.definitions.REPOSITORY_STORY_VERDICT_REPAIR_RESOURCE, {
		"response": _bounded_text(response, "repair response", MAX_REPAIR_RESPONSE_CHARS),
	}, MAX_REPAIR_RESPONSE_CHARS + 3000)


def parse_repository_story_verdict(response: str,
	allowed_labels: frozenset[str] = frozenset({"A", "B"})) -> dict[str, object]:
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
	return {"winner": value["winner"], "reason": value["reason"].strip(),
		"evidence_quality": value["evidence_quality"], "confidence": float(value["confidence"])}

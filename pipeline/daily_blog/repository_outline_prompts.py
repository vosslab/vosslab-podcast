"""Stage 3 renderers and strict verdict parsing."""

import json
import re

import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.loader


REPOSITORY_OUTLINE_PROMPT_VERSION = "repository-outline-v1"
MAX_EVIDENCE_CONTEXT_CHARS = 60000
MAX_CANDIDATE_OUTLINES_CHARS = 60000
MAX_COMPARISON_PROMPT_CHARS = 90000
MAX_REPAIR_RESPONSE_CHARS = 4000
MAX_VERDICT_REASON_CHARS = 500
_REPLICA_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")


class RepositoryOutlineVerdictParseError(RuntimeError):
	"""A repository-outline verdict misses the exact structured contract."""


def _loaded(value: daily_blog.prompt_registry.loader.LoadedPromptSet | None) -> daily_blog.prompt_registry.loader.LoadedPromptSet:
	"""Resolve only the issued canonical Stage 3 prompt view."""
	return daily_blog.prompt_registry.loader.resolve_loaded_prompt_set(
		value, daily_blog.prompt_registry.definitions.REPOSITORY_OUTLINE_PROMPT_SET,
	)


def repository_outline_prompt_identity(
	loaded: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None,
) -> dict[str, object]:
	"""Return durable Stage 3 prompt provenance in its legacy payload form."""
	return _loaded(loaded).identity_dict()


def _bounded_text(value: object, label: str, maximum: int) -> str:
	if type(value) is not str or not value or len(value) > maximum:
		raise RuntimeError(f"Repository-outline {label} is invalid or exceeds its limit.")
	return value


def _replica_id(value: object) -> str:
	if type(value) is not str or _REPLICA_ID_RE.fullmatch(value) is None:
		raise RuntimeError("Repository-outline replica identity is invalid.")
	return value


def _render(loaded: daily_blog.prompt_registry.loader.LoadedPromptSet | None,
	resource: daily_blog.prompt_registry.definitions.RegisteredPromptResource, values: dict[str, str], maximum: int) -> str:
	rendered = _loaded(loaded).render(resource, values)
	if len(rendered) > maximum:
		raise RuntimeError("Repository-outline rendered prompt exceeds its configured limit.")
	return rendered


def render_repository_outline_generator(evidence_json: str, replica_id: str,
	loaded: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None) -> str:
	return _render(loaded, daily_blog.prompt_registry.definitions.REPOSITORY_OUTLINE_GENERATOR_RESOURCE, {
		"evidence_json": _bounded_text(evidence_json, "evidence context", MAX_EVIDENCE_CONTEXT_CHARS),
		"replica_id": _replica_id(replica_id),
	}, MAX_EVIDENCE_CONTEXT_CHARS + 4000)


def render_repository_outline_merger(evidence_json: str, candidate_outlines_json: str, replica_id: str,
	loaded: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None) -> str:
	return _render(loaded, daily_blog.prompt_registry.definitions.REPOSITORY_OUTLINE_MERGER_RESOURCE, {
		"evidence_json": _bounded_text(evidence_json, "evidence context", MAX_EVIDENCE_CONTEXT_CHARS),
		"candidate_outlines_json": _bounded_text(candidate_outlines_json, "candidate outlines", MAX_CANDIDATE_OUTLINES_CHARS),
		"replica_id": _replica_id(replica_id),
	}, MAX_EVIDENCE_CONTEXT_CHARS + MAX_CANDIDATE_OUTLINES_CHARS + 5000)


def render_repository_outline_comparison(evidence_json: str, candidate_a: str, candidate_b: str,
	loaded: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None) -> str:
	value = _loaded(loaded)
	return _render(value, daily_blog.prompt_registry.definitions.REPOSITORY_OUTLINE_COMPARISON_RESOURCE, {
		"rubric": value.text(daily_blog.prompt_registry.definitions.REPOSITORY_OUTLINE_RUBRIC_RESOURCE),
		"evidence_json": _bounded_text(evidence_json, "evidence context", MAX_EVIDENCE_CONTEXT_CHARS),
		"candidate_a": _bounded_text(candidate_a, "candidate A", MAX_CANDIDATE_OUTLINES_CHARS),
		"candidate_b": _bounded_text(candidate_b, "candidate B", MAX_CANDIDATE_OUTLINES_CHARS),
	}, MAX_COMPARISON_PROMPT_CHARS)


def render_repository_outline_verdict_repair(response: str,
	loaded: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None) -> str:
	return _render(loaded, daily_blog.prompt_registry.definitions.REPOSITORY_OUTLINE_VERDICT_REPAIR_RESOURCE, {
		"response": _bounded_text(response, "repair response", MAX_REPAIR_RESPONSE_CHARS),
	}, MAX_REPAIR_RESPONSE_CHARS + 3000)


def parse_repository_outline_verdict(response: str,
	allowed_labels: frozenset[str] = frozenset({"A", "B"})) -> dict[str, object]:
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
	return {"winner": value["winner"], "reason": value["reason"].strip(),
		"evidence_quality": value["evidence_quality"], "confidence": float(value["confidence"])}

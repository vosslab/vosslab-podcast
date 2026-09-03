"""Shared bounded prompt contract for one-pass complete-candidate-set review."""

# Standard Library
import json
import re

# local repo modules
import daily_blog.artifacts
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.loader


MAX_RUBRIC_CHARS = 24000
MAX_CONTEXT_CHARS = 180000
MAX_CANDIDATES_CHARS = 180000
MAX_RENDERED_PROMPT_CHARS = 390000
MAX_RESPONSE_CHARS = 4000
MAX_REASON_CHARS = 500
_LABEL_RE = re.compile(r"C[0-9]{2}\Z")


class CandidateSetVerdictParseError(RuntimeError):
	"""A complete-set reviewer response misses the bounded JSON contract."""


#============================================
def load_prompt_set() -> daily_blog.prompt_registry.loader.LoadedPromptSet:
	"""Load the registered candidate-set prompt and verify its exact bytes."""
	return daily_blog.prompt_registry.loader.load_prompt_set(
		daily_blog.prompt_registry.definitions.CANDIDATE_SET_REVIEW_PROMPT_SET,
	)


#============================================
def _bounded(value: object, label: str, maximum: int) -> str:
	"""Require one bounded text component before rendering."""
	if type(value) is not str or not value or len(value) > maximum:
		raise RuntimeError(f"Candidate-set review {label} is invalid or exceeds its limit.")
	return value


#============================================
def candidate_labels(count: int) -> tuple[str, ...]:
	"""Return position-neutral labels for one bounded displayed ordering."""
	if type(count) is not int or not 2 <= count <= 99:
		raise RuntimeError("Candidate-set review requires two through 99 candidates.")
	return tuple(f"C{index:02d}" for index in range(1, count + 1))


#============================================
def render_candidate_set_review(
	rubric: str,
	context: str,
	candidates: tuple[daily_blog.artifacts.EditorialArtifact, ...],
	prompt_set: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None,
) -> tuple[str, dict[str, str]]:
	"""Render one anonymous complete-set request and return its label map."""
	if type(candidates) is not tuple or any(
		type(item) not in daily_blog.artifacts.ARTIFACT_TYPES for item in candidates
	):
		raise RuntimeError("Candidate-set review candidates are invalid.")
	labels = candidate_labels(len(candidates))
	label_map = dict(zip(labels, (item.artifact_id for item in candidates), strict=True))
	payload = json.dumps([
		{"label": label, "content": item.content}
		for label, item in zip(labels, candidates, strict=True)
	], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
	loaded = daily_blog.prompt_registry.loader.resolve_loaded_prompt_set(
		prompt_set or load_prompt_set(),
		daily_blog.prompt_registry.definitions.CANDIDATE_SET_REVIEW_PROMPT_SET,
	)
	prompt = loaded.render(
		daily_blog.prompt_registry.definitions.CANDIDATE_SET_REVIEW_RESOURCE,
		{
			"rubric": _bounded(rubric, "rubric", MAX_RUBRIC_CHARS),
			"context": _bounded(context, "context", MAX_CONTEXT_CHARS),
			"candidates": _bounded(payload, "candidates", MAX_CANDIDATES_CHARS),
		},
	)
	if len(prompt) > MAX_RENDERED_PROMPT_CHARS:
		raise RuntimeError("Candidate-set review prompt exceeds its rendered limit.")
	return prompt, label_map


#============================================
def parse_candidate_set_verdict(
	response: str,
	label_map: dict[str, str],
) -> str:
	"""Return the selected artifact identity from one strict allowlisted verdict."""
	if (
		type(response) is not str or len(response) > MAX_RESPONSE_CHARS
		or type(label_map) is not dict or len(label_map) < 2
		or any(
			type(label) is not str or _LABEL_RE.fullmatch(label) is None
			or type(artifact_id) is not str or not artifact_id
			for label, artifact_id in label_map.items()
		)
		or len(set(label_map.values())) != len(label_map)
	):
		raise CandidateSetVerdictParseError("Candidate-set verdict boundary is invalid.")
	try:
		value = json.loads(response.strip())
	except json.JSONDecodeError as error:
		raise CandidateSetVerdictParseError("Candidate-set verdict is not valid JSON.") from error
	if type(value) is not dict or set(value) != {
		"winner", "reason", "evidence_quality", "confidence",
	}:
		raise CandidateSetVerdictParseError("Candidate-set verdict fields are invalid.")
	if type(value["winner"]) is not str or (
		value["winner"] != "NONE" and value["winner"] not in label_map
	):
		raise CandidateSetVerdictParseError("Candidate-set verdict winner is invalid.")
	if (
		type(value["reason"]) is not str or not value["reason"].strip()
		or len(value["reason"].strip()) > MAX_REASON_CHARS
		or type(value["evidence_quality"]) is not str
		or value["evidence_quality"] not in {"high", "medium", "low"}
		or type(value["confidence"]) not in {int, float}
		or not 0 <= value["confidence"] <= 1
	):
		raise CandidateSetVerdictParseError("Candidate-set verdict values are invalid.")
	return label_map.get(value["winner"], "")

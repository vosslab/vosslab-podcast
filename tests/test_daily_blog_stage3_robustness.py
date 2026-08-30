"""Failure-injection coverage for whole-artifact Stage 3 recovery."""

# Standard Library
import os
import pathlib
import threading

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.editorial_stage_config
import daily_blog.repository_outline_workflow
import daily_blog.routes
import daily_blog.schema


#============================================
def _input(tmp_path: pathlib.Path) -> daily_blog.repository_outline_workflow.RepositoryOutlineInput:
	"""Return one repository-isolated input rooted in pytest-owned storage."""
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/stage3", "a" * 40, "CHANGELOG.md", "b" * 40,
		"Stage 3 recovery evidence.", "git show",
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-29", "America/Chicago", True, {}, [], [], [item],
	)
	return daily_blog.repository_outline_workflow.RepositoryOutlineInput(
		packet, "vosslab/stage3", os.fspath(tmp_path),
	)


#============================================
def _config() -> daily_blog.editorial_stage_config.RepositoryOutlineConfig:
	"""Use two independent peers, one balanced reviewer, and no hidden retry."""
	return daily_blog.editorial_stage_config.RepositoryOutlineConfig(
		maximum_parallel_calls=2, route_retry_attempts=0,
	)


#============================================
def _outline(value: daily_blog.repository_outline_workflow.RepositoryOutlineInput, name: str) -> str:
	"""Return a complete mechanically grounded outline from one model call."""
	return "# " + name + "\n\nGrounded work. <!-- evidence: " + value.packet.items[0].evidence_id + " -->\n"


#============================================
def _verdict(winner: str) -> str:
	"""Return the strict position-neutral reviewer envelope."""
	return '{"winner":"' + winner + '","reason":"grounded","evidence_quality":"high","confidence":1}'


class _Runner:
	"""Thread-safe response queue for bounded offline fault injection."""

	#============================================
	def __init__(self, responses: dict[str, list[object]]) -> None:
		self.responses = responses
		self.lock = threading.Lock()

	#============================================
	def run(self, route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, working_directory: str) -> str:
		"""Return the next isolated response or surface its typed route failure."""
		with self.lock:
			response = self.responses[route.name].pop(0)
		if isinstance(response, BaseException):
			raise response
		return response


#============================================
def _run(
	value: daily_blog.repository_outline_workflow.RepositoryOutlineInput,
	runner: _Runner,
	maximum_calls: int,
) -> daily_blog.repository_outline_workflow.RepositoryOutlineResult:
	"""Invoke the public Stage 3 boundary with a run-owned bounded budget."""
	return daily_blog.repository_outline_workflow.run_repository_outline(
		value, _config(), daily_blog.agents.RouteBudget(maximum_calls, 2), runner,
	)


#============================================
def _assert_whole_artifact(
	result: daily_blog.repository_outline_workflow.RepositoryOutlineResult,
) -> None:
	"""Require promotion of one original typed artifact, never assembled prose."""
	assert type(result.artifact) is daily_blog.artifacts.RepoOutline
	assert "<!-- evidence: " in result.artifact.content


#============================================
def test_generator_route_failure_keeps_independent_merger_recovery(tmp_path: pathlib.Path) -> None:
	"""One unavailable generator route degrades 3.1 while mergers promote whole work."""
	value = _input(tmp_path)
	runner = _Runner({
		"repository_outline_generator": [daily_blog.routes.EditorialRouteProcessError("x"), _outline(value, "generator")],
		"repository_outline_merger": [_outline(value, "merger one"), _outline(value, "merger two")],
		"repository_outline_reviewer": [_verdict("A"), _verdict("B")],
	})
	result = _run(value, runner, 6)

	_assert_whole_artifact(result)
	assert result.artifact.content in {_outline(value, "merger one"), _outline(value, "merger two")}


#============================================
def test_merger_route_failure_promotes_a_whole_surviving_merger(tmp_path: pathlib.Path) -> None:
	"""One unavailable merger route records only its local degraded mechanism."""
	value = _input(tmp_path)
	runner = _Runner({
		"repository_outline_generator": [_outline(value, "generator one"), _outline(value, "generator two")],
		"repository_outline_merger": [daily_blog.routes.EditorialRouteProcessError("x"), _outline(value, "surviving merger")],
		"repository_outline_reviewer": [],
	})
	result = _run(value, runner, 4)

	_assert_whole_artifact(result)
	assert result.artifact.content == _outline(value, "surviving merger")


#============================================
def test_reviewer_route_failure_uses_typed_whole_peer_promotion(tmp_path: pathlib.Path) -> None:
	"""Unavailable referees do not discard eligible whole merger candidates."""
	value = _input(tmp_path)
	runner = _Runner({
		"repository_outline_generator": [_outline(value, "generator one"), _outline(value, "generator two")],
		"repository_outline_merger": [_outline(value, "merger one"), _outline(value, "merger two")],
		"repository_outline_reviewer": [daily_blog.routes.EditorialRouteProcessError("x")] * 2,
	})
	result = _run(value, runner, 6)

	_assert_whole_artifact(result)
	assert isinstance(result.promotion, daily_blog.artifacts.DegradedPromotion)
	assert {candidate.content for candidate in result.merger.eligible} >= {result.artifact.content}


#============================================
def test_all_generator_routes_unavailable_retain_typed_recovery_evidence(
	tmp_path: pathlib.Path,
) -> None:
	"""Route absence remains a typed NoArtifact without entering another ladder rung."""
	value = _input(tmp_path)
	runner = _Runner({
		"repository_outline_generator": [daily_blog.routes.EditorialRouteProcessError("x")] * 2,
		"repository_outline_merger": [], "repository_outline_reviewer": [],
	})
	result = _run(value, runner, 2)

	assert isinstance(result.promotion, daily_blog.artifacts.NoArtifact)
	assert result.artifact is None


#============================================

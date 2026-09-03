"""Offline behavioral coverage for the pure Stage 3 repository-outline workflow."""

# Standard Library
import os
import pathlib
import threading

# PIP3 modules
import pytest

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.editorial_stage_config
import daily_blog.repository_outline_workflow
import daily_blog.routes
import daily_blog.schema


#============================================
def packet() -> daily_blog.schema.EvidencePacket:
	"""Return one packet whose evidence is isolated to the requested repository."""
	items = [daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/project", "a" * 40, "CHANGELOG.md", "b" * 40,
		"Project change.", "git show",
	)]
	return daily_blog.schema.EvidencePacket.create(
		"2026-08-29", "America/Chicago", True, {}, [], [], items,
	)


#============================================
def input_value(tmp_path: pathlib.Path) -> daily_blog.repository_outline_workflow.RepositoryOutlineInput:
	"""Return the exact Stage 3 repository boundary used by all fixture calls."""
	return daily_blog.repository_outline_workflow.RepositoryOutlineInput(
		packet(), "vosslab/project", os.fspath(tmp_path),
	)


#============================================
def config() -> daily_blog.editorial_stage_config.RepositoryOutlineConfig:
	"""Use bounded independent roles with no retries for deterministic fixtures."""
	return daily_blog.editorial_stage_config.RepositoryOutlineConfig(
		reviewer_count=1, maximum_parallel_calls=2, route_retry_attempts=0,
	)


#============================================
def outline(value: daily_blog.repository_outline_workflow.RepositoryOutlineInput, name: str) -> str:
	"""Return one whole, mechanically grounded repository outline response."""
	return "# " + name + "\n\nGrounded work. <!-- evidence: " + value.packet.items[0].evidence_id + " -->\n"


#============================================
def verdict(winner: str) -> str:
	"""Return one strict anonymous comparison verdict."""
	return '{"winner":"' + winner + '","reason":"grounded","evidence_quality":"high","confidence":1}'


class Runner:
	"""Thread-safe role queue fake retaining every exact Stage 3 request observation."""

	#============================================
	def __init__(self, responses: dict[str, list[object]]) -> None:
		self.responses = responses
		self.lock = threading.Lock()

	#============================================
	def run(self, route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, working_directory: str) -> str:
		with self.lock:
			response = self.responses[route.name].pop(0)
		if isinstance(response, BaseException):
			raise response
		return response


#============================================
def test_workflow_promotes_whole_eligible_merger(tmp_path: pathlib.Path) -> None:
	"""Eligible merger work is promoted as one complete repository outline."""
	value = input_value(tmp_path)
	runner = Runner({
		"repository_outline_generator": [outline(value, "generator one"), outline(value, "generator two")],
		"repository_outline_merger": [outline(value, "merger one"), outline(value, "merger two")],
		"repository_outline_reviewer": [verdict("A"), verdict("B")],
	})
	result = daily_blog.repository_outline_workflow.run_repository_outline(
		value, config(), daily_blog.agents.RouteBudget(6, 8), runner,
	)

	assert type(result.artifact) is daily_blog.artifacts.RepoOutline
	assert result.artifact in result.merger.eligible


#============================================
def test_wrong_repository_generator_is_filtered_while_peer_survives(tmp_path: pathlib.Path) -> None:
	"""A peer citing evidence outside the requested repository cannot reach merger work."""
	value = input_value(tmp_path)
	wrong = "# wrong\n\nOther. <!-- evidence: ev-other-repository -->\n"
	runner = Runner({
		"repository_outline_generator": [wrong, outline(value, "generator")],
		"repository_outline_merger": [outline(value, "merger one"), outline(value, "merger two")],
		"repository_outline_reviewer": [verdict("A"), verdict("B")],
	})
	result = daily_blog.repository_outline_workflow.run_repository_outline(
		value, config(), daily_blog.agents.RouteBudget(6, 8), runner,
	)

	assert type(result.artifact) is daily_blog.artifacts.RepoOutline
	assert result.artifact.repositories == (value.repository,)


#============================================
def test_input_rejects_multi_repository_packet_before_runner_calls(tmp_path: pathlib.Path) -> None:
	"""A Stage 3 model never receives a packet that mixes repository evidence."""
	first = packet().items[0]
	other = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/other", "c" * 40, "CHANGELOG.md", "d" * 40,
		"Other change.", "git show",
	)
	mixed = daily_blog.schema.EvidencePacket.create(
		"2026-08-29", "America/Chicago", True, {}, [], [], [first, other],
	)
	with pytest.raises(RuntimeError, match="isolate one repository"):
		daily_blog.repository_outline_workflow.RepositoryOutlineInput(
			mixed, "vosslab/project", os.fspath(tmp_path),
		)


#============================================
def test_input_requires_a_real_absolute_route_working_directory(tmp_path: pathlib.Path) -> None:
	"""Live route execution never inherits the process current working directory."""
	source = packet()
	with pytest.raises(RuntimeError, match="absolute working directory"):
		daily_blog.repository_outline_workflow.RepositoryOutlineInput(
			source, "vosslab/project", "relative",
		)
	with pytest.raises(RuntimeError, match="working directory must exist"):
		daily_blog.repository_outline_workflow.RepositoryOutlineInput(
			source, "vosslab/project", str(tmp_path / "missing"),
		)


#============================================
def test_merger_loss_promotes_whole_generator_as_typed_degradation(tmp_path: pathlib.Path) -> None:
	"""No merger prose is assembled when eligible generator outlines already exist."""
	value = input_value(tmp_path)
	runner = Runner({
		"repository_outline_generator": [outline(value, "g1"), outline(value, "g2")],
		"repository_outline_merger": [daily_blog.routes.EditorialRouteProcessError("x")] * 2,
		"repository_outline_reviewer": [verdict("A"), verdict("B")],
	})
	result = daily_blog.repository_outline_workflow.run_repository_outline(
		value, config(), daily_blog.agents.RouteBudget(6, 8), runner,
	)

	assert result.artifact is not None
	assert result.artifact.content in {outline(value, "g1"), outline(value, "g2")}
	assert isinstance(result.promotion, daily_blog.artifacts.DegradedPromotion)


#============================================
def test_eligible_incumbent_survives_unavailable_review(tmp_path: pathlib.Path) -> None:
	"""An incumbent remains unless a challenger has complete direct evidence."""
	value = input_value(tmp_path)
	incumbent = daily_blog.artifacts.RepoOutline.create(
		value.report_date, (value.packet,), value.repository, outline(value, "incumbent"),
		(value.packet.items[0].evidence_id,),
	)
	runner = Runner({
		"repository_outline_generator": [outline(value, "g1"), outline(value, "g2")],
		"repository_outline_merger": [outline(value, "m1"), outline(value, "m2")],
		"repository_outline_reviewer": [daily_blog.routes.EditorialRouteProcessError("x")] * 6,
	})
	result = daily_blog.repository_outline_workflow.run_repository_outline(
		value, config(), daily_blog.agents.RouteBudget(12, 8), runner, incumbent=incumbent,
	)

	assert isinstance(result.promotion, daily_blog.artifacts.PreservedArtifact)
	assert result.artifact == incumbent


#============================================
def test_unsupported_runner_response_escapes_as_pipeline_defect(tmp_path: pathlib.Path) -> None:
	"""Unsupported runner responses are faults, not editorial degradation."""
	value = input_value(tmp_path)
	defective = Runner({
		"repository_outline_generator": [object(), outline(value, "x")],
		"repository_outline_merger": [], "repository_outline_reviewer": [],
	})
	with pytest.raises(RuntimeError, match="unsupported response type"):
		daily_blog.repository_outline_workflow.run_repository_outline(
			value, config(), daily_blog.agents.RouteBudget(2, 8), defective,
		)

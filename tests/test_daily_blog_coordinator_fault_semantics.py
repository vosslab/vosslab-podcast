"""Focused terminal-fault semantics for the durable recovery coordinator."""

# Standard Library
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.editorial_stage_config
import daily_blog.io_utils
import daily_blog.recovery
import daily_blog.replication
import daily_blog.run_contracts
import daily_blog.run_state
import daily_blog.schema
import daily_blog.stage_recovery_coordinator


def _candidate(ok: bool, root: pathlib.Path) -> daily_blog.replication.ReplicatedCandidate:
	"""Build one source route fact without external model work."""
	route = daily_blog.editorial_stage_config.RoleRoute("fixture", ("fixture-hermes",))
	request = daily_blog.agents.RouteRequest(
		"source", "source", route, "fixture prompt", str(root), input_hash="a" * 64,
	)
	text = "ineligible" if ok else ""
	result = daily_blog.agents.AgentResult(
		"editorial", text, ok, "" if ok else "timeout", 1, 0.0, False, False,
		route.name, request.request_id, request.identity_sha256,
		daily_blog.io_utils.sha256_text(text),
	)
	return daily_blog.replication.ReplicatedCandidate(
		request, result, None, None, "" if ok else "timeout",
	)


def _packet() -> daily_blog.schema.EvidencePacket:
	"""Build one sealed evidence packet for a report date."""
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/recovery", "a" * 40, "CHANGELOG.md", "b" * 40,
		"A grounded recovery change.", "git show",
	)
	return daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item],
	)


def _summary() -> daily_blog.replication.StepReliability:
	"""Build a bounded source reliability summary."""
	return daily_blog.replication.StepReliability(
		"writer", "degraded", 1, 0, 1, 0, 0, 0, "", ("route_unavailable",),
	)


def _coordinator(root: pathlib.Path) -> daily_blog.stage_recovery_coordinator.StageRecoveryCoordinator:
	"""Build a run-owned coordinator with no external cache or route."""
	store = daily_blog.run_state.RunStore(str(root), "vosslab", "2026-08-23", "recovery")
	record = daily_blog.run_contracts.RunRecord.create("recovery", "2026-08-23")
	return daily_blog.stage_recovery_coordinator.StageRecoveryCoordinator(
		store, record, daily_blog.agents.RouteBudget(2),
	)


def _input(
	root: pathlib.Path, reason: daily_blog.recovery.TerminalFaultCategory, ok: bool,
) -> daily_blog.stage_recovery_coordinator.StageRecoveryInput:
	"""Build one no-artifact stage result with real source route counts."""
	packet = _packet()
	return daily_blog.stage_recovery_coordinator.StageRecoveryInput(
		packet.report_date, "stage4/no_artifact/recovery", daily_blog.artifacts.CompletePost,
		daily_blog.artifacts.NoArtifact(daily_blog.artifacts.CompletePost, reason.value),
		daily_blog.replication.ReplicationResult(
			daily_blog.artifacts.CompletePost, (_candidate(ok, root),),
		),
		(_summary(),), (packet,), str(root), ("a" * 64,), ("b" * 64,), None, (),
	)


@pytest.mark.parametrize("category", (
	daily_blog.recovery.TerminalFaultCategory.EVIDENCE_UNAVAILABLE,
	daily_blog.recovery.TerminalFaultCategory.CONFIGURATION,
	daily_blog.recovery.TerminalFaultCategory.IMPLEMENTATION_DEFECT,
))
def test_explicit_source_faults_bind_the_matching_typed_observation(
	tmp_path: pathlib.Path, category: daily_blog.recovery.TerminalFaultCategory,
) -> None:
	"""Each nonordinary source diagnosis reaches the fault invariant honestly."""
	result = _coordinator(tmp_path).run(_input(tmp_path, category, True))
	assert result.fault is not None
	assert result.fault.category is category
	assert result.fault.observations[0].explicit_fault is category


@pytest.mark.parametrize(("reported", "ok", "expected"), (
	(
		daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE,
		False,
		daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE,
	),
	(
		daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION,
		True,
		daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION,
	),
))
def test_ordinary_source_faults_remain_derived_from_raw_counts(
	tmp_path: pathlib.Path, reported: daily_blog.recovery.TerminalFaultCategory,
	ok: bool, expected: daily_blog.recovery.TerminalFaultCategory,
) -> None:
	"""Route failure and ineligibility preserve their observed route semantics."""
	result = _coordinator(tmp_path).run(_input(tmp_path, reported, ok))
	assert result.fault is not None
	assert result.fault.category is expected
	assert result.fault.observations[0].explicit_fault is None

"""Focused tests for the recovery coordinator's durable publication boundary."""

# Standard Library
import dataclasses
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
	"""Return a real transport-bound candidate without invoking an external route."""
	route = daily_blog.editorial_stage_config.RoleRoute("fixture", ("fixture-hermes",))
	request = daily_blog.agents.RouteRequest(
		"source", "source", route, "fixture prompt", str(root), input_hash="a" * 64,
	)
	text = "unusable" if ok else ""
	result = daily_blog.agents.AgentResult(
		"editorial", text, ok, "" if ok else "timeout", 1, 0.0, False, False,
		route.name, request.request_id, request.identity_sha256, daily_blog.io_utils.sha256_text(text),
	)
	return daily_blog.replication.ReplicatedCandidate(request, result, None, None, "" if ok else "timeout")


def _packet() -> daily_blog.schema.EvidencePacket:
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/recovery", "a" * 40, "CHANGELOG.md", "b" * 40,
		"A grounded recovery change.", "git show",
	)
	return daily_blog.schema.EvidencePacket.create("2026-08-23", "America/Chicago", True, {}, [], [], [item])


def _post(packet: daily_blog.schema.EvidencePacket, root: pathlib.Path, body: str) -> daily_blog.artifacts.CompletePost:
	return daily_blog.artifacts.CompletePost.create(
		packet.report_date, (packet,), ("vosslab/recovery",),
		f"{body} <!-- evidence: {packet.items[0].evidence_id} -->", (packet.items[0].evidence_id,),
		packet.report_date, str(root / "post.md"),
	)


def _summary() -> daily_blog.replication.StepReliability:
	return daily_blog.replication.StepReliability("6.writer", "degraded", 1, 0, 1, 0, 0, 0, "", ("route_unavailable",))


def _recovery_generation(
	root: pathlib.Path, candidate: daily_blog.artifacts.CompletePost,
) -> daily_blog.replication.ReplicationResult:
	"""Return one exact eligible recovery observation without a route invocation."""
	item = dataclasses.replace(
		_candidate(True, root), artifact=candidate,
		eligibility=daily_blog.artifacts.EligibilityResult(True, ()),
	)
	return daily_blog.replication.ReplicationResult(daily_blog.artifacts.CompletePost, (item,))


def _input(packet: daily_blog.schema.EvidencePacket, root: pathlib.Path, paths: tuple[object, ...], ok: bool = True) -> daily_blog.stage_recovery_coordinator.StageRecoveryInput:
	result = daily_blog.replication.ReplicationResult(
		daily_blog.artifacts.CompletePost, (_candidate(ok, root),),
	)
	return daily_blog.stage_recovery_coordinator.StageRecoveryInput(
		packet.report_date, "stage6/no_artifact/recovery", daily_blog.artifacts.CompletePost,
		daily_blog.artifacts.NoArtifact(daily_blog.artifacts.CompletePost, "no_eligible_generation"),
		result, (_summary(),), (packet,), str(root), ("a" * 64,), ("b" * 64,), None, paths,
	)


def _coordinator(tmp_path: pathlib.Path) -> daily_blog.stage_recovery_coordinator.StageRecoveryCoordinator:
	store = daily_blog.run_state.RunStore(str(tmp_path), "vosslab", "2026-08-23", "recovery")
	record = daily_blog.run_contracts.RunRecord.create("recovery", "2026-08-23")
	return daily_blog.stage_recovery_coordinator.StageRecoveryCoordinator(store, record, daily_blog.agents.RouteBudget(2))


def test_no_eligible_source_recovers_a_whole_post(tmp_path: pathlib.Path) -> None:
	"""A no-eligible source can recover an independently eligible whole post."""
	packet = _packet()
	candidate = _post(packet, tmp_path, "Recovered")

	def invoke(_budget: object, _load: object, _store: object) -> daily_blog.recovery.RecoveryAttempt:
		return daily_blog.recovery.RecoveryAttempt(
			daily_blog.artifacts.SelectedPeer(candidate, daily_blog.artifacts.CompletePost),
			daily_blog.recovery.GenerationObservation("recovery_writer", 1, 1, (candidate.artifact_id,)),
		)

	coordinator = _coordinator(tmp_path)
	result = coordinator.run(_input(packet, tmp_path, (
		daily_blog.stage_recovery_coordinator.RecoveryPathAdapter(
			daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST, invoke,
		),
	)))
	assert result.artifact is not None
	assert result.artifact.content == candidate.content


def test_selected_recovery_retains_generation_lineage(tmp_path: pathlib.Path) -> None:
	"""The durable coordinator retains recovery lineage without altering source streams."""
	packet = _packet()
	candidate = _post(packet, tmp_path, "Recovered")
	generation = _recovery_generation(tmp_path, candidate)

	def invoke(*_args: object) -> daily_blog.recovery.RecoveryAttempt:
		return daily_blog.recovery.RecoveryAttempt(
			daily_blog.artifacts.SelectedPeer(candidate, daily_blog.artifacts.CompletePost),
			daily_blog.recovery.GenerationObservation(
				"recovery_writer", 1, 1, (candidate.artifact_id,),
			), generation,
		)

	result = _coordinator(tmp_path).run(_input(packet, tmp_path, (
		daily_blog.stage_recovery_coordinator.RecoveryPathAdapter(
			daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST, invoke,
		),
	)))
	assert result.artifact is not None
	assert result.recovery_generation is not None
	assert result.artifact.artifact_id in {
		item.artifact.artifact_id
		for item in result.recovery_generation.candidates
		if item.artifact is not None
	}


def test_failed_recovery_generation_does_not_cross_the_fault_result_boundary(tmp_path: pathlib.Path) -> None:
	"""A failed attempt may retain facts locally but cannot turn into recovery success."""
	packet = _packet()
	failed = daily_blog.replication.ReplicationResult(
		daily_blog.artifacts.CompletePost, (_candidate(False, tmp_path),),
	)

	def invoke(*_args: object) -> daily_blog.recovery.RecoveryAttempt:
		return daily_blog.recovery.RecoveryAttempt(
			daily_blog.artifacts.NoArtifact(
				daily_blog.artifacts.CompletePost, "route_unavailable",
			), daily_blog.recovery.GenerationObservation("recovery_writer", 1, 0), failed,
		)

	result = _coordinator(tmp_path).run(_input(packet, tmp_path, (
		daily_blog.stage_recovery_coordinator.RecoveryPathAdapter(
			daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST, invoke,
		),
	), False))
	assert result.artifact is None
	assert result.recovery_generation is None


@pytest.mark.parametrize(("ok", "expected"), [
	(False, daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE),
	(True, daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION),
])
def test_exhaustion_preserves_the_raw_generation_category(
	tmp_path: pathlib.Path, ok: bool, expected: daily_blog.recovery.TerminalFaultCategory,
) -> None:
	"""All route failures and successful ineligibility never collapse into one diagnosis."""
	coordinator = _coordinator(tmp_path)
	result = coordinator.run(_input(_packet(), tmp_path, (), ok))
	assert result.fault is not None and result.fault.category is expected
	assert pathlib.Path(result.digest_path).is_file()


def test_reviewer_loss_with_a_promoted_artifact_never_descends(tmp_path: pathlib.Path) -> None:
	"""A retained grounded artifact ends the stage without fabricating more prose."""
	packet = _packet()
	candidate = _post(packet, tmp_path, "Retained")
	result = daily_blog.replication.ReplicationResult(daily_blog.artifacts.CompletePost, ())
	called = False

	def invoke(*_args: object) -> daily_blog.recovery.RecoveryAttempt:
		nonlocal called
		called = True
		raise RuntimeError("must not run")

	value = daily_blog.stage_recovery_coordinator.StageRecoveryInput(
		packet.report_date, "stage6/no_artifact/recovery", daily_blog.artifacts.CompletePost,
		daily_blog.artifacts.DegradedPromotion(candidate, daily_blog.artifacts.CompletePost, ("reviewer_unavailable",)),
		result, (_summary(),), (packet,), str(tmp_path), ("a" * 64,), ("b" * 64,), None,
		(daily_blog.stage_recovery_coordinator.RecoveryPathAdapter(daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST, invoke),),
	)
	assert _coordinator(tmp_path).run(value).artifact is candidate
	assert not called


def test_replay_reuses_equal_summary_and_rejects_changed_summary(tmp_path: pathlib.Path) -> None:
	"""Resume is idempotent for exact work but does not hide divergent facts."""
	packet = _packet()
	coordinator = _coordinator(tmp_path)
	value = _input(packet, tmp_path, (), False)
	first = coordinator.run(value)
	second = coordinator.run(value)
	assert first.digest_sha256 == second.digest_sha256
	changed = dataclasses.replace(value, source_summaries=(dataclasses.replace(_summary(), attempted=2, failed=2),))
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError, match="diverged"):
		coordinator.run(changed)


def test_evidence_unavailable_accepts_zero_packets_but_other_faults_do_not(tmp_path: pathlib.Path) -> None:
	"""Only the typed evidence fault may cross the digest boundary without packets."""
	result = daily_blog.replication.ReplicationResult(daily_blog.artifacts.CompletePost, ())
	summary = daily_blog.replication.StepReliability("6.writer", "degraded", 0, 0, 0, 0, 0, 0, "", ("evidence_unavailable",))
	value = daily_blog.stage_recovery_coordinator.StageRecoveryInput(
		"2026-08-23", "stage6/no_artifact/recovery", daily_blog.artifacts.CompletePost,
		daily_blog.artifacts.NoArtifact(daily_blog.artifacts.CompletePost, "evidence_unavailable"),
		result, (summary,), (), str(tmp_path), ("a" * 64,), ("b" * 64,), None, (),
	)
	assert _coordinator(tmp_path).run(value).fault is not None
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError, match="unavailable evidence"):
		dataclasses.replace(value, source_promotion=daily_blog.artifacts.NoArtifact(
			daily_blog.artifacts.CompletePost, "no_eligible_generation",
		))


def test_source_post_outside_trusted_root_is_rejected(tmp_path: pathlib.Path) -> None:
	"""Recovery does not let candidate metadata choose its own output root."""
	packet = _packet()
	outside_root = tmp_path.parent / "outside_trusted_root"
	candidate = _post(packet, outside_root, "Escaped")
	value = dataclasses.replace(
		_input(packet, tmp_path, (), True),
		source_promotion=daily_blog.artifacts.SelectedPeer(candidate, daily_blog.artifacts.CompletePost),
	)
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError):
		_coordinator(tmp_path).run(value)


def test_unbounded_source_reason_is_rejected_before_any_durable_write(tmp_path: pathlib.Path) -> None:
	"""Model/provider-like text cannot enter run state through a source summary."""
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError, match="reason is unsafe"):
		dataclasses.replace(_input(_packet(), tmp_path, (), False), source_summaries=(
			daily_blog.replication.StepReliability(
				"6.writer", "degraded", 1, 0, 1, 0, 0, 0, "", ("prompt /tmp/token",),
			),
		))

"""Focused tests for the recovery coordinator's durable publication boundary."""

# Standard Library
import dataclasses
import json
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.editorial_stage_config
import daily_blog.io_utils
import daily_blog.publication_admission
import daily_blog.recovery
import daily_blog.replication
import daily_blog.run_contracts
import daily_blog.run_state
import daily_blog.schema
import daily_blog.stage_recovery_coordinator


_LIMITS = {"commit_subject_chars": 120, "context_chars": 12000, "excerpt_chars": 1000}


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


def _packet(
	repository: str = "vosslab/recovery", report_date: str = "2026-08-23",
) -> daily_blog.schema.EvidencePacket:
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", repository, "a" * 40, "CHANGELOG.md", "b" * 40,
		"A grounded recovery change.", "git show",
	)
	return daily_blog.schema.EvidencePacket.create(report_date, "America/Chicago", True, {}, [], [], [item])


def _post(packet: daily_blog.schema.EvidencePacket, root: pathlib.Path, body: str) -> daily_blog.artifacts.CompletePost:
	paragraph = (
		"I followed the grounded change through its practical boundary, checked the behavior it "
		"preserved, and recorded the next useful question before moving to the related work. "
	) * 14
	content = (
		f"# {body}\n\nI returned to the evidence with the implementation in view. "
		f"<!-- evidence: {packet.items[0].evidence_id} -->\n\n<!-- more -->\n\n"
		"## Grounded work\n\n" + paragraph
		+ f"<!-- evidence: {packet.items[0].evidence_id} -->\n\n"
		"## Project coverage\n\n" + packet.items[0].repository + ".\n"
	)
	return daily_blog.artifacts.CompletePost.create(
		packet.report_date, (packet,), (packet.items[0].repository,),
		content, (packet.items[0].evidence_id,),
		packet.report_date, str(root / "post.md"),
	)


def _ineligible_post(
	packet: daily_blog.schema.EvidencePacket, root: pathlib.Path,
) -> daily_blog.artifacts.CompletePost:
	"""Return a grounded post whose image cannot enter the approved publication set."""
	valid = _post(packet, root, "Ineligible")
	content = valid.content.replace(
		"I returned to the evidence", "![unapproved](unapproved.png)\n\nI returned to the evidence",
		1,
	)
	return daily_blog.artifacts.CompletePost.create(
		packet.report_date, (packet,), (packet.items[0].repository,),
		content,
		(packet.items[0].evidence_id,), packet.report_date, str(root / "post.md"),
		("unapproved.png",),
	)


def _surface(
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
) -> daily_blog.publication_admission.PublicationSurface:
	"""Build the exact final-post authority for one recovery fixture."""
	canonical = tuple(sorted(packets, key=lambda item: item.packet_id))
	repositories = tuple(sorted({item.repository for packet in canonical for item in packet.items}))
	return daily_blog.publication_admission.build_surface(canonical, repositories, _LIMITS)


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
		result, (_summary(),), (packet,), (packet.items[0].repository,), str(root),
		_surface((packet,)), ("a" * 64,), ("b" * 64,), None, paths,
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


def test_parsed_ineligible_source_descends_to_an_eligible_recovery_post(
	tmp_path: pathlib.Path,
) -> None:
	"""An unapproved primary image is editorial degradation, not a lineage fault."""
	packet = _packet()
	primary = _ineligible_post(packet, tmp_path)
	primary_candidate = dataclasses.replace(
		_candidate(True, tmp_path), artifact=primary,
		eligibility=daily_blog.publication_admission.complete_post_eligibility(
			primary, _surface((packet,)), str(tmp_path),
		),
	)
	result = daily_blog.replication.ReplicationResult(
		daily_blog.artifacts.CompletePost, (primary_candidate,),
	)
	recovered = _post(packet, tmp_path, "Recovered")

	def invoke(*_args: object) -> daily_blog.recovery.RecoveryAttempt:
		return daily_blog.recovery.RecoveryAttempt(
			daily_blog.artifacts.SelectedPeer(recovered, daily_blog.artifacts.CompletePost),
			daily_blog.recovery.GenerationObservation("recovery_writer", 1, 1, (recovered.artifact_id,)),
			_recovery_generation(tmp_path, recovered),
		)

	value = dataclasses.replace(
		_input(packet, tmp_path, ()), source_result=result,
	)
	coordinator = _coordinator(tmp_path)
	result = coordinator.run(dataclasses.replace(value, paths=(
		daily_blog.stage_recovery_coordinator.RecoveryPathAdapter(
			daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST, invoke,
		),
	)))
	assert not primary_candidate.eligibility.eligible
	assert result.artifact is recovered


def test_parsed_source_with_forged_machine_metadata_is_a_configuration_fault(
	tmp_path: pathlib.Path,
) -> None:
	"""Recovery retains ordinary ineligibility but never accepts a forged primary peer."""
	packet = _packet()
	forged = dataclasses.replace(_post(packet, tmp_path, "Forged"), content_hash="a" * 64)
	candidate = dataclasses.replace(
		_candidate(True, tmp_path), artifact=forged,
		eligibility=daily_blog.artifacts.EligibilityResult(False, ("invalid_machine_metadata",)),
	)
	value = dataclasses.replace(
		_input(packet, tmp_path, ()),
		source_result=daily_blog.replication.ReplicationResult(
			daily_blog.artifacts.CompletePost, (candidate,),
		),
	)
	coordinator = _coordinator(tmp_path)
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError, match="machine metadata"):
		coordinator.run(value)
	assert not coordinator.record.editorial_steps


def test_parsed_source_with_cited_evidence_outside_its_scope_is_a_configuration_fault(
	tmp_path: pathlib.Path,
) -> None:
	"""A source peer cannot use another repository's evidence under a local label."""
	packet = _packet()
	other_packet = _packet("vosslab/other")
	forged = daily_blog.artifacts.CompletePost.create(
		packet.report_date, (packet, other_packet), (packet.items[0].repository,),
		"Mismatched <!-- evidence: " + other_packet.items[0].evidence_id + " -->",
		(other_packet.items[0].evidence_id,), packet.report_date, str(tmp_path / "post.md"),
	)
	candidate = dataclasses.replace(
		_candidate(True, tmp_path), artifact=forged,
		eligibility=daily_blog.artifacts.EligibilityResult(
			False, ("evidence_outside_repository_scope",),
		),
	)
	value = dataclasses.replace(
		_input(packet, tmp_path, ()), packets=tuple(sorted((packet, other_packet), key=lambda item: item.packet_id)),
		source_result=daily_blog.replication.ReplicationResult(
			daily_blog.artifacts.CompletePost, (candidate,),
		),
	)
	coordinator = _coordinator(tmp_path)
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError, match="cited evidence scope"):
		coordinator.run(value)
	assert not coordinator.record.editorial_steps


def test_parsed_source_with_a_forged_ineligible_decision_is_a_configuration_fault(
	tmp_path: pathlib.Path,
) -> None:
	"""A publishable peer cannot manufacture the no-eligible recovery branch."""
	packet = _packet()
	publishable = _post(packet, tmp_path, "Publishable")
	candidate = dataclasses.replace(
		_candidate(True, tmp_path), artifact=publishable,
		eligibility=daily_blog.artifacts.EligibilityResult(False, ("unapproved_image_path",)),
	)
	value = dataclasses.replace(
		_input(packet, tmp_path, ()),
		source_result=daily_blog.replication.ReplicationResult(
			daily_blog.artifacts.CompletePost, (candidate,),
		),
	)
	coordinator = _coordinator(tmp_path)
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError, match="eligibility decision"):
		coordinator.run(value)
	assert not coordinator.record.editorial_steps


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
		result, (_summary(),), (packet,), (packet.items[0].repository,), str(tmp_path),
		_surface((packet,)), ("a" * 64,), ("b" * 64,), None,
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
		result, (summary,), (), ("vosslab/recovery",), str(tmp_path),
		None, ("a" * 64,), ("b" * 64,), None, (),
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


def test_publishable_recovery_post_requires_the_exact_stage6_packet_union(
	tmp_path: pathlib.Path,
) -> None:
	"""A recovery post cannot publish from a narrower packet subset than Stage 6 owns."""
	packet = _packet()
	other_packet = _packet("vosslab/other")
	candidate = _post(packet, tmp_path, "Narrow")
	value = dataclasses.replace(
		_input(packet, tmp_path, (), False), packets=tuple(sorted((packet, other_packet), key=lambda item: item.packet_id)),
		source_promotion=daily_blog.artifacts.SelectedPeer(
			candidate, daily_blog.artifacts.CompletePost,
		),
	)
	coordinator = _coordinator(tmp_path)
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError, match="provenance"):
		coordinator.run(value)
	assert not coordinator.record.editorial_steps


def test_adapter_selected_post_with_a_packet_subset_never_reaches_recovery_persistence(
	tmp_path: pathlib.Path,
) -> None:
	"""An adapter cannot promote an eligible-looking post outside Stage 6's packet union."""
	packet = _packet()
	other_packet = _packet("vosslab/other")
	candidate = _post(packet, tmp_path, "Subset")

	def invoke(*_args: object) -> daily_blog.recovery.RecoveryAttempt:
		return daily_blog.recovery.RecoveryAttempt(
			daily_blog.artifacts.SelectedPeer(candidate, daily_blog.artifacts.CompletePost),
			daily_blog.recovery.GenerationObservation("recovery_writer", 1, 1, (candidate.artifact_id,)),
		)

	value = dataclasses.replace(
		_input(packet, tmp_path, (), False),
		packets=tuple(sorted((packet, other_packet), key=lambda item: item.packet_id)),
		allowed_repositories=tuple(sorted((packet.items[0].repository, other_packet.items[0].repository))),
		paths=(daily_blog.stage_recovery_coordinator.RecoveryPathAdapter(
			daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST, invoke,
		),),
	)
	coordinator = _coordinator(tmp_path)
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError, match="provenance"):
		coordinator.run(value)
	assert coordinator.record.best_artifact_id == ""
	assert all(not step["step"].startswith("recovery/") for step in coordinator.record.editorial_steps)


def test_terminal_recovery_incumbent_rejects_repo_outline(tmp_path: pathlib.Path) -> None:
	"""Only a singleton RepoStory may remain as terminal strongest-story provenance."""
	packet = _packet()
	outline = daily_blog.artifacts.RepoOutline.create(
		packet.report_date, (packet,), "vosslab/recovery",
		"Outline <!-- evidence: " + packet.items[0].evidence_id + " -->",
		(packet.items[0].evidence_id,),
	)
	value = dataclasses.replace(
		_input(packet, tmp_path, (), False),
		incumbent=daily_blog.recovery.RecoveryIncumbent(
			outline, daily_blog.recovery.RecoveryRung.STRONGEST_REPOSITORY_MATERIAL,
		),
	)
	coordinator = _coordinator(tmp_path)
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError, match="terminal incumbent type"):
		coordinator.run(value)
	assert not coordinator.record.editorial_steps


def test_repository_incumbent_with_a_grounded_packet_subset_remains_terminal_provenance(
	tmp_path: pathlib.Path,
) -> None:
	"""A strongest repository story is retained in the terminal fault, never published."""
	packet = _packet()
	other_packet = _packet("vosslab/other")
	story = daily_blog.artifacts.RepoStory.create(
		packet.report_date, (packet,), "vosslab/recovery",
		f"Recovered repository story <!-- evidence: {packet.items[0].evidence_id} -->",
		(packet.items[0].evidence_id,),
	)
	value = dataclasses.replace(
		_input(packet, tmp_path, (), False), packets=(packet, other_packet),
		publication_surface=_surface((packet, other_packet)),
		allowed_repositories=tuple(sorted((
			packet.items[0].repository, other_packet.items[0].repository,
		))),
		incumbent=daily_blog.recovery.RecoveryIncumbent(
			story, daily_blog.recovery.RecoveryRung.STRONGEST_REPOSITORY_MATERIAL,
		),
	)
	result = _coordinator(tmp_path).run(value)
	assert result.artifact is None
	assert result.fault is not None
	assert result.fault.strongest_artifact_id == story.artifact_id
	assert result.fault.strongest_artifact_type == "RepoStory"


@pytest.mark.parametrize("artifact_type", (daily_blog.artifacts.CompletePost, daily_blog.artifacts.RepoStory))
def test_recovery_rejects_artifacts_outside_its_stage6_repository_ceiling(
	tmp_path: pathlib.Path,
	artifact_type: type[daily_blog.artifacts.CompletePost] | type[daily_blog.artifacts.RepoStory],
) -> None:
	"""Stage 6 cannot promote a recovery artifact outside its promoted outline scope."""
	allowed_packet = _packet("vosslab/recovery")
	outside_packet = _packet("vosslab/outside")
	if artifact_type is daily_blog.artifacts.CompletePost:
		artifact = _post(outside_packet, tmp_path, "Outside")
		value = dataclasses.replace(
			_input(allowed_packet, tmp_path, (), False), packets=(allowed_packet, outside_packet),
			source_promotion=daily_blog.artifacts.SelectedPeer(
				artifact, daily_blog.artifacts.CompletePost,
			),
		)
	else:
		artifact = daily_blog.artifacts.RepoStory.create(
			outside_packet.report_date, (outside_packet,), "vosslab/outside",
			"Outside <!-- evidence: " + outside_packet.items[0].evidence_id + " -->",
			(outside_packet.items[0].evidence_id,),
		)
		value = dataclasses.replace(
			_input(allowed_packet, tmp_path, (), False), packets=(allowed_packet, outside_packet),
			incumbent=daily_blog.recovery.RecoveryIncumbent(
				artifact, daily_blog.recovery.RecoveryRung.STRONGEST_REPOSITORY_MATERIAL,
			),
		)
	coordinator = _coordinator(tmp_path)
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError, match="provenance|repository scope"):
		coordinator.run(value)
	assert not coordinator.record.editorial_steps


@pytest.mark.parametrize("mismatch", ("date", "packet", "repository"))
def test_repository_incumbent_rejects_mismatched_subset_provenance(
	tmp_path: pathlib.Path,
	mismatch: str,
) -> None:
	"""Subset provenance must still bind date, packets, repositories, and evidence together."""
	packet = _packet()
	other_packet = _packet("vosslab/other")
	if mismatch == "date":
		artifact_packet = _packet(report_date="2026-08-24")
		repository = "vosslab/recovery"
	elif mismatch == "packet":
		artifact_packet = _packet("vosslab/unlisted")
		repository = "vosslab/unlisted"
	else:
		artifact_packet = packet
		repository = "vosslab/other"
	invalid = daily_blog.artifacts.RepoStory.create(
		artifact_packet.report_date, (artifact_packet,), repository,
		f"Recovered repository story <!-- evidence: {artifact_packet.items[0].evidence_id} -->",
		(artifact_packet.items[0].evidence_id,),
	)
	value = dataclasses.replace(
		_input(packet, tmp_path, (), False), packets=(packet, other_packet),
		incumbent=daily_blog.recovery.RecoveryIncumbent(
			invalid, daily_blog.recovery.RecoveryRung.STRONGEST_REPOSITORY_MATERIAL,
		),
	)
	coordinator = _coordinator(tmp_path)
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError):
		coordinator.run(value)
	assert not coordinator.record.editorial_steps


def test_unbounded_source_reason_is_rejected_before_any_durable_write(tmp_path: pathlib.Path) -> None:
	"""Model/provider-like text cannot enter run state through a source summary."""
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError, match="reason is unsafe"):
		dataclasses.replace(_input(_packet(), tmp_path, (), False), source_summaries=(
			daily_blog.replication.StepReliability(
				"6.writer", "degraded", 1, 0, 1, 0, 0, 0, "", ("prompt /tmp/token",),
		),
	))


#============================================
def _recovery_summaries(
	artifact_id: str = "", writer_failed: int = 0,
) -> tuple[daily_blog.replication.StepReliability, ...]:
	"""Return bounded writer, editor, review, and promotion facts for one rung."""
	writer_attempted = 1 + writer_failed
	return (
		daily_blog.replication.StepReliability(
			"6.1", "degraded" if writer_failed else "succeeded", writer_attempted, 1,
			writer_failed, 0, 0, 0, "", ("route_unavailable",) if writer_failed else (),
		),
		daily_blog.replication.StepReliability(
			"6.2", "degraded", 0, 0, 0, 0, 0, 0, "", ("editor_unavailable",),
		),
		daily_blog.replication.StepReliability(
			"6.3", "degraded", 0, 0, 0, 0, 0, 0, "", ("review_unavailable",),
		),
		daily_blog.replication.StepReliability(
			"6.4", "degraded" if not artifact_id else "succeeded", 1, 1, 0, 0, 0, 0,
			artifact_id, ("no_eligible_generation",) if not artifact_id else (),
		),
	)


#============================================
def test_coordinator_persists_detailed_recovery_rungs_and_only_promotes_selected_path(
		tmp_path: pathlib.Path,
) -> None:
	"""Failed and selected recovery rungs keep independent namespaced facts and transitions."""
	packet = _packet()
	candidate = _post(packet, tmp_path, "Lower rung recovery")

	def failed(*_args: object) -> daily_blog.recovery.RecoveryAttempt:
		return daily_blog.recovery.RecoveryAttempt(
			daily_blog.artifacts.NoArtifact(daily_blog.artifacts.CompletePost, "no_eligible_generation"),
			daily_blog.recovery.GenerationObservation("recovery_writer", 2, 1),
			step_reliability=_recovery_summaries(writer_failed=1),
		)

	def selected(*_args: object) -> daily_blog.recovery.RecoveryAttempt:
		return daily_blog.recovery.RecoveryAttempt(
			daily_blog.artifacts.SelectedPeer(candidate, daily_blog.artifacts.CompletePost),
			daily_blog.recovery.GenerationObservation("recovery_writer", 1, 1, (candidate.artifact_id,)),
			_recovery_generation(tmp_path, candidate), _recovery_summaries(candidate.artifact_id),
		)

	coordinator = _coordinator(tmp_path)
	value = _input(packet, tmp_path, (
		daily_blog.stage_recovery_coordinator.RecoveryPathAdapter(
			daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST, failed,
		),
		daily_blog.stage_recovery_coordinator.RecoveryPathAdapter(
			daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION, selected,
		),
	))
	result = coordinator.run(value)
	steps = {item["step"] for item in coordinator.record.editorial_steps}
	transitions = {
		step: transition
		for step, transition in map(daily_blog.run_contracts.parse_incumbent_transition,
			coordinator.record.editorial_transitions)
	}

	assert result.artifact is candidate
	assert {
		"recovery/complete_post/writer_complete_post/" + step
		for step in ("6.1", "6.2", "6.3", "6.4")
	}.issubset(steps)
	assert {
		"recovery/complete_post/daily_outline_expansion/" + step
		for step in ("6.1", "6.2", "6.3", "6.4")
	}.issubset(steps)
	assert isinstance(
		transitions["recovery/complete_post/daily_outline_expansion/6.4"],
		daily_blog.run_contracts.EstablishIncumbent,
	)
	assert all(
		isinstance(transition, daily_blog.run_contracts.ObserveIncumbent)
		for step, transition in transitions.items()
		if step != "recovery/complete_post/daily_outline_expansion/6.4"
	)


#============================================
def test_terminal_recovery_digest_retains_detailed_failed_rung_facts(
		tmp_path: pathlib.Path,
) -> None:
	"""Terminal diagnostics retain categorical facts from every detailed failed path."""
	packet = _packet()

	def failed(*_args: object) -> daily_blog.recovery.RecoveryAttempt:
		return daily_blog.recovery.RecoveryAttempt(
			daily_blog.artifacts.NoArtifact(daily_blog.artifacts.CompletePost, "no_eligible_generation"),
			daily_blog.recovery.GenerationObservation("recovery_writer", 2, 1),
			step_reliability=_recovery_summaries(writer_failed=1),
		)

	coordinator = _coordinator(tmp_path)
	result = coordinator.run(_input(packet, tmp_path, (
		daily_blog.stage_recovery_coordinator.RecoveryPathAdapter(
			daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST, failed,
		),
		daily_blog.stage_recovery_coordinator.RecoveryPathAdapter(
			daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION, failed,
		),
	)))
	with open(result.digest_path, encoding="utf-8") as handle:
		payload = json.load(handle)
	steps = {item["step_key"]: item for item in payload["steps"]}

	assert result.fault is not None
	assert steps["recovery/complete_post/writer_complete_post/6.1"]["failed"] == 1
	assert steps["recovery/complete_post/daily_outline_expansion/6.2"]["reasons"] == ["editor_unavailable"]
	assert all(not item["best_artifact_id"] for item in steps.values())

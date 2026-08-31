"""Focused tests for typed editorial recovery and safe evidence digests."""

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
import daily_blog.schema


#============================================
def packet() -> daily_blog.schema.EvidencePacket:
	"""Return one minimal authoritative packet."""
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/project", "a" * 40, "CHANGELOG.md", "b" * 40,
		"A grounded implementation change.", "git show",
	)
	return daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item],
	)


#============================================
def post(source: daily_blog.schema.EvidencePacket, body: str = "Text") -> daily_blog.artifacts.CompletePost:
	"""Return one exact eligible complete-post artifact."""
	content = f"{body} <!-- evidence: {source.items[0].evidence_id} -->"
	return daily_blog.artifacts.CompletePost.create(
		source.report_date, (source,), ("vosslab/project",), content,
		(source.items[0].evidence_id,), source.report_date, "post.md",
	)


#============================================
def outline(source: daily_blog.schema.EvidencePacket) -> daily_blog.artifacts.RepoOutline:
	"""Return one exact eligible repository-material artifact."""
	content = f"Text <!-- evidence: {source.items[0].evidence_id} -->"
	return daily_blog.artifacts.RepoOutline.create(
		source.report_date, (source,), "vosslab/project", content, (source.items[0].evidence_id,),
	)


#============================================
def observation(
	step: str = "stage9", attempted: int = 1, successful: int = 0,
	eligible: tuple[str, ...] = (), fault: daily_blog.recovery.TerminalFaultCategory | None = None,
) -> daily_blog.recovery.GenerationObservation:
	"""Build one bounded route fact."""
	return daily_blog.recovery.GenerationObservation(step, attempted, successful, eligible, fault)


#============================================
def recovery_generation(
	item: daily_blog.artifacts.CompletePost | None, *, ok: bool = True,
	expected_type: type = daily_blog.artifacts.CompletePost,
) -> daily_blog.replication.ReplicationResult:
	"""Return one exact recovery observation without invoking a route."""
	route = daily_blog.editorial_stage_config.RoleRoute("fixture", ("fixture-hermes",))
	request = daily_blog.agents.RouteRequest(
		"recovery-source", "recovery-source", route, "fixture prompt", "recovery",
		input_hash="a" * 64,
	)
	text = "fixture" if ok else ""
	result = daily_blog.agents.AgentResult(
		"recovery", text, ok, "" if ok else "timeout", 1, 0.0, False, False,
		route.name, request.request_id, request.identity_sha256,
		daily_blog.io_utils.sha256_text(text),
	)
	candidate = daily_blog.replication.ReplicatedCandidate(
		request, result, item,
		daily_blog.artifacts.EligibilityResult(True, ()) if item is not None else None,
		"" if ok else "timeout",
	)
	return daily_blog.replication.ReplicationResult(expected_type, (candidate,))


#============================================
def no_artifact(
	reason: str, item: daily_blog.recovery.GenerationObservation,
) -> daily_blog.recovery.RecoveryAttempt:
	"""Bind a complete-post no-artifact outcome to one generator observation."""
	return daily_blog.recovery.RecoveryAttempt(
		daily_blog.artifacts.NoArtifact(daily_blog.artifacts.CompletePost, reason), item,
	)


#============================================
def digest_step() -> daily_blog.recovery.EvidenceDigestStep:
	"""Return one canonical, bounded mechanism summary."""
	return daily_blog.recovery.EvidenceDigestStep(
		"stage4/artifact-aaaaaaaaaaaaaaaaaaaaaaaa/writer", "degraded",
		2, 1, 1, 0, 0, 0, "", ("route_unavailable",),
	)


#============================================
@pytest.mark.parametrize(("item", "expected"), [
	((observation(),), daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE),
	((observation(successful=1),), daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION),
	((observation(fault=daily_blog.recovery.TerminalFaultCategory.EVIDENCE_UNAVAILABLE),), daily_blog.recovery.TerminalFaultCategory.EVIDENCE_UNAVAILABLE),
	((observation(fault=daily_blog.recovery.TerminalFaultCategory.CONFIGURATION),), daily_blog.recovery.TerminalFaultCategory.CONFIGURATION),
	((observation(fault=daily_blog.recovery.TerminalFaultCategory.IMPLEMENTATION_DEFECT),), daily_blog.recovery.TerminalFaultCategory.IMPLEMENTATION_DEFECT),
	((observation(fault=daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE),), daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE),
	((observation(fault=daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION),), daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION),
])
def test_fault_categories_are_discriminated_from_typed_observations(
	item: tuple[daily_blog.recovery.GenerationObservation, ...], expected: daily_blog.recovery.TerminalFaultCategory,
) -> None:
	"""All terminal categories derive from typed observations."""
	assert daily_blog.recovery.classify_pipeline_fault(item) is expected


#============================================
@pytest.mark.parametrize(("reason", "item"), [
	("route_unavailable", observation(successful=1)),
	("no_eligible_generation", observation()),
	("route_unavailable", observation(fault=daily_blog.recovery.TerminalFaultCategory.CONFIGURATION)),
	("configuration", observation(fault=daily_blog.recovery.TerminalFaultCategory.EVIDENCE_UNAVAILABLE)),
])
def test_no_artifact_reason_must_exactly_match_its_typed_facts(
	reason: str, item: daily_blog.recovery.GenerationObservation,
) -> None:
	"""No outcome can fabricate a route diagnosis from conflicting facts."""
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError):
		no_artifact(reason, item)


#============================================
def test_mixed_route_observations_classify_from_validated_aggregate_facts() -> None:
	"""One response among route failures yields no-eligible, not route-unavailable."""
	items = (observation("first"), observation("second", 1, 1))
	assert daily_blog.recovery.classify_pipeline_fault(items) is (
		daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION
	)


#============================================
def test_ladder_descends_only_after_no_artifact_and_promotes_whole_post() -> None:
	"""A valid no-eligible generation admits the next plan-ordered editorial path."""
	source = packet()
	candidate = post(source, "Candidate")
	first = daily_blog.recovery.RecoveryPath(
		daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST,
		lambda: no_artifact("no_eligible_generation", observation("writer", 2, 2)),
	)
	second = daily_blog.recovery.RecoveryPath(
		daily_blog.recovery.RecoveryRung.REPOSITORY_STORY_MERGE,
		lambda: daily_blog.recovery.RecoveryAttempt(
			daily_blog.artifacts.SelectedPeer(candidate, daily_blog.artifacts.CompletePost),
			observation("merge", 1, 1, (candidate.artifact_id,)),
		),
	)
	result = daily_blog.recovery.recover_ladder((first, second), None, lambda item: item is candidate, lambda _, item: item)
	assert isinstance(result, daily_blog.recovery.RecoveryResult)
	assert result.artifact is candidate


#============================================
def test_selected_recovery_generation_attests_to_the_selected_artifact() -> None:
	"""A winning recovery attempt retains lineage for the selected whole post."""
	source = packet()
	candidate = post(source, "Recovered")
	generation = recovery_generation(candidate)
	attempt = daily_blog.recovery.RecoveryAttempt(
		daily_blog.artifacts.SelectedPeer(candidate, daily_blog.artifacts.CompletePost),
		observation("recovery_writer", 1, 1, (candidate.artifact_id,)), generation,
	)
	result = daily_blog.recovery.recover_ladder((
		daily_blog.recovery.RecoveryPath(
			daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST, lambda: attempt,
		),
	), None, lambda item: item is candidate, lambda _prior, item: item)
	assert isinstance(result, daily_blog.recovery.RecoveryResult)
	assert result.artifact.artifact_id == candidate.artifact_id
	assert result.recovery_generation is not None
	assert any(
		item.artifact is not None and item.artifact.artifact_id == result.artifact.artifact_id
		for item in result.recovery_generation.candidates
	)


#============================================
def test_incumbent_fast_path_drops_an_uninvoked_recovery_generation() -> None:
	"""An older incumbent does not acquire provenance from an uncalled lower rung."""
	source = packet()
	incumbent = post(source, "Incumbent")
	candidate = post(source, "Would not run")
	generation = recovery_generation(candidate)
	called = False

	def invoke() -> daily_blog.recovery.RecoveryAttempt:
		nonlocal called
		called = True
		return daily_blog.recovery.RecoveryAttempt(
			daily_blog.artifacts.SelectedPeer(candidate, daily_blog.artifacts.CompletePost),
			observation("recovery_writer", 1, 1, (candidate.artifact_id,)), generation,
		)

	result = daily_blog.recovery.recover_ladder((
		daily_blog.recovery.RecoveryPath(
			daily_blog.recovery.RecoveryRung.REPOSITORY_STORY_MERGE, invoke,
		),
	), daily_blog.recovery.RecoveryIncumbent(
		incumbent, daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST,
	), lambda _item: True, lambda _prior, item: item)
	assert isinstance(result, daily_blog.recovery.RecoveryResult)
	assert result.artifact is incumbent
	assert result.recovery_generation is None
	assert not called


#============================================
def test_recovery_generation_rejects_a_selected_artifact_without_matching_lineage() -> None:
	"""A retained observation cannot attest to a different successful post."""
	source = packet()
	candidate = post(source, "Selected")
	other = post(source, "Other")
	valid_observation = observation("recovery_writer", 1, 1, (candidate.artifact_id,))
	valid_outcome = daily_blog.artifacts.SelectedPeer(candidate, daily_blog.artifacts.CompletePost)
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError):
		daily_blog.recovery.RecoveryAttempt(valid_outcome, valid_observation, recovery_generation(other))


#============================================
def test_failed_recovery_attempt_may_retain_generation_but_never_a_success_result() -> None:
	"""Failed generation provenance is local to its attempt and cannot promote a post."""
	generation = recovery_generation(None, ok=False)
	attempt = daily_blog.recovery.RecoveryAttempt(
		daily_blog.artifacts.NoArtifact(daily_blog.artifacts.CompletePost, "route_unavailable"),
		observation("recovery_writer", 1, 0), generation,
	)
	result = daily_blog.recovery.recover_ladder((
		daily_blog.recovery.RecoveryPath(
			daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST, lambda: attempt,
		),
	), None, lambda _item: True, lambda _prior, item: item)
	assert attempt.recovery_generation is generation
	assert isinstance(result, daily_blog.recovery.PipelineFault)


#============================================
def test_explicit_terminal_fault_stops_before_lower_rung() -> None:
	"""Evidence/configuration/defect observations never descend editorially."""
	for category in (
		daily_blog.recovery.TerminalFaultCategory.EVIDENCE_UNAVAILABLE,
		daily_blog.recovery.TerminalFaultCategory.CONFIGURATION,
		daily_blog.recovery.TerminalFaultCategory.IMPLEMENTATION_DEFECT,
	):
		called: list[str] = []
		first = daily_blog.recovery.RecoveryPath(
			daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST,
			lambda category=category: no_artifact(category.value, observation("terminal", 0, 0, (), category)),
		)
		second = daily_blog.recovery.RecoveryPath(
			daily_blog.recovery.RecoveryRung.REPOSITORY_STORY_MERGE,
			lambda: (called.append("lower") or no_artifact("route_unavailable", observation("lower"))),
		)
		result = daily_blog.recovery.recover_ladder((first, second), None, lambda _: True, lambda _, item: item)
		assert isinstance(result, daily_blog.recovery.PipelineFault)
		assert result.category is category
		assert not called


#============================================
def test_closed_rungs_reject_an_out_of_order_plan() -> None:
	"""Recovery accepts only a descending editorial plan."""
	path = lambda rung: daily_blog.recovery.RecoveryPath(rung, lambda: no_artifact("route_unavailable", observation()))
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError):
		daily_blog.recovery.recover_ladder((path(daily_blog.recovery.RecoveryRung.REPOSITORY_STORY_MERGE), path(daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST)), None, lambda _: True, lambda _, item: item)


#============================================
def test_repository_material_is_terminal_provenance_not_a_publishable_replacement() -> None:
	"""An eligible repository artifact remains fault provenance rather than a post."""
	source = packet()
	current = daily_blog.recovery.RecoveryIncumbent(
		outline(source), daily_blog.recovery.RecoveryRung.STRONGEST_REPOSITORY_MATERIAL,
	)
	path = daily_blog.recovery.RecoveryPath(
		daily_blog.recovery.RecoveryRung.REPOSITORY_STORY_MERGE,
		lambda: no_artifact("route_unavailable", observation("merge")),
	)
	result = daily_blog.recovery.recover_ladder((path,), current, lambda _: True, lambda _, item: item)
	assert isinstance(result, daily_blog.recovery.PipelineFault)
	assert result.strongest_artifact_id == current.artifact.artifact_id


#============================================
def test_higher_whole_post_can_replace_lower_repository_provenance() -> None:
	"""Repository material is not compared as a publishable cross-type candidate."""
	source = packet()
	candidate = post(source, "Recovered")
	current = daily_blog.recovery.RecoveryIncumbent(
		outline(source), daily_blog.recovery.RecoveryRung.STRONGEST_REPOSITORY_MATERIAL,
	)
	path = daily_blog.recovery.RecoveryPath(
		daily_blog.recovery.RecoveryRung.REPOSITORY_STORY_MERGE,
		lambda: daily_blog.recovery.RecoveryAttempt(
			daily_blog.artifacts.SelectedPeer(candidate, daily_blog.artifacts.CompletePost),
			observation("merge", 1, 1, (candidate.artifact_id,)),
		),
	)
	result = daily_blog.recovery.recover_ladder((path,), current, lambda _: True, lambda _, item: item)
	assert isinstance(result, daily_blog.recovery.RecoveryResult)
	assert result.artifact is candidate


#============================================
def test_outer_boundary_preserves_typed_configuration_and_redacts_only_unexpected() -> None:
	"""The sole broad catch cannot swallow a known configuration/provenance fault."""
	configured = daily_blog.recovery.RecoveryPath(
		daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST,
		lambda: (_ for _ in ()).throw(daily_blog.recovery.RecoveryConfigurationError("configuration")),
	)
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError):
		daily_blog.recovery.recover_at_outer_boundary((configured,), None, lambda _: True, lambda _, item: item)
	unexpected = daily_blog.recovery.RecoveryPath(
		daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST,
		lambda: (_ for _ in ()).throw(ValueError("secret prompt content")),
	)
	result = daily_blog.recovery.recover_at_outer_boundary((unexpected,), None, lambda _: True, lambda _, item: item)
	assert isinstance(result, daily_blog.recovery.PipelineFault)
	assert result.category is daily_blog.recovery.TerminalFaultCategory.IMPLEMENTATION_DEFECT
	assert "secret" not in repr(result)


#============================================
def test_outer_boundary_retains_incumbent_artifact_for_unexpected_defect() -> None:
	"""An outer defect keeps the strongest produced artifact visible to operators."""
	source = packet()
	current = daily_blog.recovery.RecoveryIncumbent(
		post(source), daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST,
	)
	path = daily_blog.recovery.RecoveryPath(
		daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST,
		lambda: (_ for _ in ()).throw(ValueError("untrusted route detail")),
	)
	result = daily_blog.recovery.recover_at_outer_boundary((path,), current, lambda _: True, lambda _, item: item)
	assert isinstance(result, daily_blog.recovery.PipelineFault)
	assert result.strongest_artifact_id == current.artifact.artifact_id


#============================================
def test_empty_packet_digest_is_limited_to_evidence_unavailable() -> None:
	"""No synthetic packet is needed when evidence collection itself had none."""
	evidence_fault = daily_blog.recovery.PipelineFault(
		daily_blog.recovery.TerminalFaultCategory.EVIDENCE_UNAVAILABLE, 0, "", "",
		(observation(fault=daily_blog.recovery.TerminalFaultCategory.EVIDENCE_UNAVAILABLE),),
	)
	accepted = daily_blog.recovery.EvidenceDigestInput(
		"2026-08-23", "stage4/artifact-aaaaaaaaaaaaaaaaaaaaaaaa/collect", (), (), (), (), evidence_fault,
	)
	assert daily_blog.recovery.canonical_evidence_digest(accepted)[0]["packets"] == []
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError):
		dataclasses.replace(
			evidence_fault,
			category=daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE,
		)


#============================================
def test_digest_is_deterministic_and_binds_meaningful_provenance() -> None:
	"""Digest hashes bind safe, meaningful provenance changes."""
	fault = daily_blog.recovery.PipelineFault(
		daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE, 1, "", "", (observation(),),
	)
	base = daily_blog.recovery.EvidenceDigestInput(
		"2026-08-23", "stage4/artifact-aaaaaaaaaaaaaaaaaaaaaaaa/writer", (digest_step(),),
		(daily_blog.recovery.EvidenceDigestPacket("a" * 64, "b" * 64, ("ev-1",)),),
		("c" * 64,), ("d" * 64,), fault,
	)
	payload, digest = daily_blog.recovery.canonical_evidence_digest(base)
	assert daily_blog.recovery.canonical_evidence_digest(base) == (payload, digest)
	assert daily_blog.recovery.canonical_evidence_digest(dataclasses.replace(base, prompt_identities=("e" * 64,)))[1] != digest
	assert daily_blog.recovery.canonical_evidence_digest(dataclasses.replace(
		base, ranking_promotion_ids=("ranking-promotion-aaaaaaaaaaaaaaaaaaaaaaaa",),
	))[1] != digest
	assert daily_blog.recovery.canonical_evidence_digest(dataclasses.replace(
		base, allowed_repositories=("vosslab/recovery",),
	))[1] != digest
	assert payload["stage_key"] == base.stage_key


#============================================
def test_digest_step_rejects_an_unsafe_operational_path() -> None:
	"""Mechanism summaries do not serialize private operational paths."""
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError):
		daily_blog.recovery.EvidenceDigestStep(
			str(pathlib.PurePosixPath("/", "private")), "degraded", 1, 1, 0, 0, 0, 0, "", (),
		)


#============================================
def test_terminal_digest_binds_ranking_promotion_identity() -> None:
	"""Terminal recovery keeps ranking provenance type-safe."""
	fault = daily_blog.recovery.PipelineFault(
		daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION, 1, "", "",
		(observation(successful=1),),
	)
	digest = daily_blog.recovery.EvidenceDigestInput(
		"2026-08-23", "stage4/daily_outline/terminal", (),
		(daily_blog.recovery.EvidenceDigestPacket("a" * 64, "b" * 64, ("ev-1",)),),
		("c" * 64,), ("d" * 64,), fault, (),
		("ranking-promotion-aaaaaaaaaaaaaaaaaaaaaaaa",),
	)
	_, original_digest = daily_blog.recovery.canonical_evidence_digest(digest)
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError):
		dataclasses.replace(digest, ranking_promotion_ids=("artifact-aaaaaaaaaaaaaaaaaaaaaaaa",))
	with pytest.raises(daily_blog.recovery.RecoveryConfigurationError):
		dataclasses.replace(
			digest_step(),
			best_artifact_id="ranking-promotion-aaaaaaaaaaaaaaaaaaaaaaaa",
		)
	assert original_digest == daily_blog.recovery.canonical_evidence_digest(digest)[1]

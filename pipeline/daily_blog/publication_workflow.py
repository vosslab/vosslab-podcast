"""Producer-owned Stage 8/9 coordinator helpers for one selected complete post."""

# Standard Library
import os
import dataclasses
import collections.abc
import json

# local repo modules
import daily_blog.artifacts
import daily_blog.io_utils
import daily_blog.publication_validation
import daily_blog.replication
import daily_blog.schema
import daily_blog.activity
import daily_blog.evidence
import daily_blog.mirrors
import daily_blog.recovery
import daily_blog.stage6
import daily_blog.stage7
import daily_blog.stage_recovery_coordinator
import daily_blog.editorial
import daily_blog.complete_post_editor_prompts
import daily_blog.daily_outline_prompts
import daily_blog.daily_outline_workflow
import daily_blog.route_cache
import daily_blog.run_contracts


def _cache_buffer(coordinator: object) -> daily_blog.route_cache.BufferedRouteEffects:
	"""Return one serial-stage collector; only this workflow commits its effects."""
	return daily_blog.route_cache.BufferedRouteEffects(coordinator.route_cache)


@dataclasses.dataclass(frozen=True)
class PublicationRuntime:
	"""Optional external-provider overrides for controlled real-pipeline execution."""

	repository_loader: collections.abc.Callable | None = None
	mirror_refresh: collections.abc.Callable | None = None
	activity_locator: collections.abc.Callable | None = None
	evidence_assembler: collections.abc.Callable | None = None
	route_runner: object | None = None
	publisher_function: collections.abc.Callable | None = None
	page_verifier: collections.abc.Callable | None = None


#============================================
def require_runtime(value: object | None) -> PublicationRuntime:
	"""Return one frozen runtime boundary without serializing provider objects."""
	if value is None:
		return PublicationRuntime()
	if type(value) is not PublicationRuntime:
		raise RuntimeError("Publication runtime must be an exact PublicationRuntime.")
	return value


#============================================
def refresh_mirrors(runtime: PublicationRuntime, config: object, roster: object, refresh: bool) -> list[dict]:
	"""Use the optional mirror provider or the real manager implementation."""
	if runtime.mirror_refresh is not None:
		return runtime.mirror_refresh(config, roster, refresh)
	manager = daily_blog.mirrors.MirrorManager(config.mirror_cache_root, roster)
	return manager.refresh_all(refresh=refresh)


#============================================
def locate_activity(
	runtime: PublicationRuntime, report_date: str, timezone: str, mirrors: list[dict],
	names: tuple[str, ...], emails: tuple[str, ...],
) -> list[object]:
	"""Use the optional activity provider or the real deterministic locator."""
	if runtime.activity_locator is not None:
		return runtime.activity_locator(report_date, timezone, mirrors, names, emails)
	return daily_blog.activity.locate_activity(report_date, timezone, mirrors, names, emails)


#============================================
def assemble_evidence(
	runtime: PublicationRuntime, report_date: str, timezone: str, limits: dict,
	mirrors: list[dict], activities: list[object],
) -> tuple[object, dict[str, bytes]]:
	"""Use the optional evidence provider or the real evidence assembler."""
	if runtime.evidence_assembler is not None:
		return runtime.evidence_assembler(report_date, timezone, limits, mirrors, activities)
	assembler = daily_blog.evidence.EvidenceAssembler(report_date, timezone, limits)
	return assembler.assemble(mirrors, activities)


#============================================
def _stage5_output_path(coordinator: object) -> str:
	"""Return the trusted date-owned Stage 6 destination for one Stage 5 handoff."""
	return os.path.join(
		os.path.abspath(coordinator.config.output_root), coordinator.config.output_owner,
		"daily_blog", coordinator.report_date, "post.md",
	)


#============================================
def _record_stage5_summaries(coordinator: object, result: daily_blog.daily_outline_workflow.DailyOutlineResult) -> None:
	"""Persist every Stage 5 mechanism without moving the publishable incumbent."""
	if type(result) is not daily_blog.daily_outline_workflow.DailyOutlineResult:
		raise RuntimeError("Stage 5 result must be an exact DailyOutlineResult.")
	steps = result.reliability
	if tuple(item.step for item in steps) != ("5.1", "5.2", "5.3", "5.4", "5.5"):
		raise RuntimeError("Stage 5 must expose its five mechanism reliability steps.")
	for summary in steps:
		coordinator.store.record_editorial_step(
			coordinator.record, summary, daily_blog.run_contracts.ObserveIncumbent(),
		)


#============================================
def _stage5_artifact_payload(result: daily_blog.daily_outline_workflow.DailyOutlineResult) -> dict[str, object]:
	"""Project one promoted outline without route prompts, results, or diagnostics."""
	artifact = result.artifact
	if type(artifact) is not daily_blog.artifacts.DailyOutline:
		raise RuntimeError("Stage 5 artifact projection requires an exact DailyOutline.")
	promoted = result.promoted_ranking
	return {
		"schema_version": "vosslab.daily-blog.stage5-daily-outline.v1",
		"artifact_id": artifact.artifact_id,
		"content_hash": artifact.content_hash,
		"artifact": artifact.to_dict(),
		"source_story_ids": [item.artifact_id for item in result.source_stories],
		"selected_story_ids": [item.artifact_id for item in result.selected_stories],
		"promoted_ranking_id": "" if promoted is None else promoted.promotion_id,
		"promoted_ranking_hash": "" if promoted is None else promoted.ranking_content_sha256,
		"eligible_candidate_ids": sorted(item.artifact_id for item in result.generation.eligible),
	}


#============================================
def _stage5_observations(result: daily_blog.daily_outline_workflow.DailyOutlineResult) -> tuple[daily_blog.recovery.GenerationObservation, ...]:
	"""Project raw route facts for the terminal classification boundary."""
	observations: list[daily_blog.recovery.GenerationObservation] = []
	for step, values in (
		("stage5_ranking", result.rankings),
		("stage5_ranking_review", result.ranking_reviews),
	):
		observations.append(daily_blog.recovery.GenerationObservation(
			step, len(values), sum(item.result.ok for item in values), (),
		))
	if result.generation.candidates:
		eligible = tuple(sorted({item.artifact.artifact_id for item in result.generation.candidates
			if type(item.artifact) is daily_blog.artifacts.DailyOutline
			and item.eligibility is not None and item.eligibility.eligible}))
		observations.append(daily_blog.recovery.GenerationObservation(
			"stage5_outline_writer", len(result.generation.candidates),
			sum(item.result.ok for item in result.generation.candidates), eligible,
		))
	return tuple(observations)


#============================================
def _stage5_terminal_fault(coordinator: object, value: daily_blog.daily_outline_workflow.DailyOutlineInput,
	result: daily_blog.daily_outline_workflow.DailyOutlineResult) -> None:
	"""Write and verify the closed Stage 5 terminal digest, then raise it."""
	observations = _stage5_observations(result)
	fault = daily_blog.recovery.PipelineFault(
		daily_blog.recovery.classify_pipeline_fault(observations), 0, "", "", observations,
	)
	contract = daily_blog.daily_outline_prompts.load_daily_outline_prompt_contract()
	resources = dict(contract.resource_sha256)
	prompts = tuple(sorted(value for name, value in resources.items() if name.endswith(".txt")))
	rubrics = tuple(sorted(value for name, value in resources.items() if name.endswith(".md")))
	steps = []
	for summary in result.reliability:
		steps.append(daily_blog.recovery.EvidenceDigestStep(
			"stage5/daily_outline/" + summary.step, summary.outcome, summary.attempted,
			summary.succeeded, summary.failed, summary.reused, summary.repaired,
			summary.disagreements, "", summary.reasons,
		))
	packets = tuple(daily_blog.recovery.EvidenceDigestPacket(
		item.packet_id, daily_blog.io_utils.hash_value(item.content_dict()),
		tuple(sorted(evidence.evidence_id for evidence in item.items)),
	) for item in value.packets)
	promotion_ids = () if result.promoted_ranking is None else (result.promoted_ranking.promotion_id,)
	payload, digest = daily_blog.recovery.canonical_evidence_digest(
		daily_blog.recovery.EvidenceDigestInput(
			value.report_date, "stage5/daily_outline/terminal", tuple(steps), packets,
			prompts, rubrics, fault, (), promotion_ids,
		)
	)
	path = os.path.join(coordinator.store.run_dir, "recovery_fault.json")
	if os.path.exists(path):
		with open(path, encoding="utf-8") as handle:
			existing = json.load(handle)
		if daily_blog.io_utils.hash_value(existing) != digest:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage 5 recovery digest replay diverged.")
	else:
		path = coordinator.store.write_artifact("recovery_fault.json", payload)
	with open(path, encoding="utf-8") as handle:
		if daily_blog.io_utils.hash_value(json.load(handle)) != digest:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage 5 recovery digest write did not verify.")
	raise daily_blog.recovery.PipelineFaultError(fault, digest)


#============================================
def _validate_stage5_input(value: object, coordinator: object) -> daily_blog.daily_outline_workflow.DailyOutlineInput:
	"""Require the generated joined input to bind this run and its local union."""
	if type(value) is not daily_blog.daily_outline_workflow.DailyOutlineInput:
		raise RuntimeError("Stage 5 requires an exact generated DailyOutlineInput.")
	if value.report_date != coordinator.report_date or not value.packets:
		raise RuntimeError("Stage 5 generated input report date is invalid.")
	return value


#============================================
def run_typed_stage5(coordinator: object, value: object) -> daily_blog.stage6.Stage6Input:
	"""Run Stage 5 once, preserve its durable evidence, and build the typed Stage 6 handoff."""
	root = os.path.abspath(coordinator.config.output_root)
	value = _validate_stage5_input(value, coordinator)
	coordinator._start("stage5_daily_outline", {
		"packet_ids": [item.packet_id for item in value.packets], "output_root": root,
	})
	cache_effects = _cache_buffer(coordinator)
	result = daily_blog.daily_outline_workflow.run_daily_outline(
		value, coordinator.config.daily_outline, coordinator.route_budget,
		runner=coordinator.route_runner, cache_load=cache_effects.load,
		cache_accept=cache_effects.accept,
	)
	coordinator.store.write_artifact("stage5_reliability.json", {
		"schema_version": "vosslab.daily-blog.stage5-reliability.v1",
		"steps": [item.to_dict() for item in result.reliability],
	})
	_record_stage5_summaries(coordinator, result)
	if result.artifact is None:
		_stage5_terminal_fault(coordinator, value, result)
	coordinator.route_cache.commit(cache_effects.drain())
	coordinator.store.write_artifact("stage5_daily_outline.json", _stage5_artifact_payload(result))
	stage6_value = daily_blog.stage6.Stage6Input(
		result.artifact, result.selected_stories, value.packets, root, _stage5_output_path(coordinator),
	)
	coordinator._complete("stage5_daily_outline", {
		"artifact_id": result.artifact.artifact_id,
		"content_hash": result.artifact.content_hash,
		"selected_story_ids": [item.artifact_id for item in result.selected_stories],
	})
	return stage6_value


#============================================
def _stage6_incumbent_transition(
	coordinator: object,
	value: daily_blog.stage6.Stage6Input,
	result: daily_blog.stage6.Stage6Result,
) -> daily_blog.run_contracts.IncumbentTransition:
	"""Establish only the exact first eligible complete post selected by Stage 6.

	ASVS 2.2.1, 2.3.1, and 15.3.5: promotion authority comes from the exact
	typed selected artifact and its eligibility, never from a stage label.
	"""
	artifact = result.artifact
	if type(artifact) is not daily_blog.artifacts.CompletePost:
		return daily_blog.run_contracts.ObserveIncumbent()
	eligibility = daily_blog.artifacts.evaluate_eligibility(
		artifact, value.packets, (value.output_root,),
	)
	if not eligibility.eligible:
		raise RuntimeError("Stage 6 selected post is not eligible for establishment.")
	if coordinator.record.best_artifact_id:
		return daily_blog.run_contracts.ObserveIncumbent()
	return daily_blog.run_contracts.EstablishIncumbent(artifact.artifact_id)


#============================================
def run_typed_stage6(
	coordinator: object, value: daily_blog.stage6.Stage6Input,
) -> daily_blog.stage6.Stage6Result:
	"""Run the permanent Stage-6 contract from a supplied typed upstream boundary."""
	output_root = os.path.abspath(coordinator.config.output_root)
	output_path = _stage5_output_path(coordinator)
	if type(value) is not daily_blog.stage6.Stage6Input or value.report_date != coordinator.report_date:
		raise RuntimeError("Stage 6 requires an exact generated Stage6Input.")
	if value.output_root != output_root or value.output_path != output_path:
		raise RuntimeError("Stage 6 input must use the coordinator-owned output root and path.")
	coordinator._start("stage6_complete_post", {
		"packet_ids": [item.packet_id for item in value.packets], "output_path": output_path,
	})
	cache_effects = _cache_buffer(coordinator)
	result = daily_blog.stage6.run_stage6(
		value, coordinator.run_id, coordinator.config, coordinator.route_budget,
		runner=coordinator.route_runner, contract=coordinator.editorial_contract,
		snapshot=coordinator.prompt_snapshot, cache_load=cache_effects.load,
		cache_accept=cache_effects.accept,
	)
	# Preserve the Stage-6 aggregate record while making its mechanisms
	# independently queryable through bounded summaries.
	# The step names are an identity boundary in RunRecord, so reject malformed
	# Stage6Result values before any durable state is changed.
	steps = result.step_reliability
	if len({summary.step for summary in steps}) != len(steps):
		raise RuntimeError("Stage 6 mechanism reliability steps must be unique.")
	if tuple(summary.step for summary in steps) != ("6.1", "6.2", "6.3", "6.4"):
		raise RuntimeError("Stage 6 must expose its four mechanism reliability steps.")
	coordinator.store.write_artifact("stage6_reliability.json", result.reliability.to_dict())
	coordinator.store.write_artifact("stage6_step_reliability.json", {
		"schema_version": "vosslab.daily-blog.stage6-step-reliability.v1",
		"steps": [summary.to_dict() for summary in steps],
	})
	for summary in steps:
		coordinator.store.record_editorial_step(
			coordinator.record, summary, daily_blog.run_contracts.ObserveIncumbent(),
		)
	coordinator.store.record_editorial_step(
		coordinator.record, result.reliability,
		_stage6_incumbent_transition(coordinator, value, result),
	)
	if result.artifact is None:
		result = _recover_stage6(coordinator, value, result, cache_effects)
	coordinator.route_cache.commit(cache_effects.drain())
	coordinator._complete("stage6_complete_post", {
		"artifact_id": result.artifact.artifact_id,
		"outcome": result.reliability.outcome,
	})
	return result


#============================================
def _write_replay_checked_artifact(coordinator: object, name: str, value: dict[str, object]) -> str:
	"""Persist one bounded Stage 7 projection without overwriting divergent replay facts."""
	path = os.path.join(coordinator.store.run_dir, name)
	if os.path.exists(path):
		with open(path, encoding="utf-8") as handle:
			existing = json.load(handle)
		if daily_blog.io_utils.hash_value(existing) != daily_blog.io_utils.hash_value(value):
			raise RuntimeError("Stage 7 artifact replay diverged.")
		return path
	return coordinator.store.write_artifact(name, value)


#============================================
def _validate_stage7_boundary(
	coordinator: object, stage6_input: object, stage6_result: object,
) -> daily_blog.stage7.Stage7Input:
	"""Build the sole Stage 7 boundary before its phase or routes can start."""
	if type(stage6_input) is not daily_blog.stage6.Stage6Input:
		raise RuntimeError("Stage 7 requires an exact Stage6Input.")
	if type(stage6_result) is not daily_blog.stage6.Stage6Result:
		raise RuntimeError("Stage 7 requires an exact Stage6Result.")
	output_root = os.path.abspath(coordinator.config.output_root)
	output_path = _stage5_output_path(coordinator)
	if (
		stage6_input.report_date != coordinator.report_date
		or not stage6_input.packets
		or stage6_input.output_root != output_root
		or stage6_input.output_path != output_path
	):
		raise RuntimeError("Stage 7 input must bind the coordinator union, date, root, and path.")
	return daily_blog.stage7.Stage7Input(stage6_input, stage6_result)


#============================================
def _validate_stage7_result(
	coordinator: object, value: daily_blog.stage7.Stage7Input, result: object,
) -> daily_blog.stage7.Stage7Result:
	"""Reject forged final-synthesis facts before a run artifact or event is written."""
	if type(result) is not daily_blog.stage7.Stage7Result:
		raise RuntimeError("Stage 7 worker must return an exact Stage7Result.")
	if result.incumbent is not value.incumbent or result.reviewer_count != coordinator.config.final_synthesis.reviewer_count:
		raise RuntimeError("Stage 7 result incumbent or reviewer count is invalid.")
	if tuple(item.step for item in result.step_reliability) != ("7.1", "7.2", "7.3"):
		raise RuntimeError("Stage 7 must expose its three mechanism reliability steps.")
	replaced = result.synthesis_won
	if result.direct_incumbent_comparison is not replaced:
		raise RuntimeError("Stage 7 direct-comparison attestation is inconsistent.")
	if replaced:
		if result.artifact is value.incumbent:
			raise RuntimeError("Stage 7 replacement must differ from the Stage 6 incumbent.")
	else:
		if result.artifact is not value.incumbent:
			raise RuntimeError("Stage 7 preservation must retain the exact Stage 6 incumbent.")
	return result


#============================================
def _stage7_incumbent_transition(
	result: daily_blog.stage7.Stage7Result,
) -> daily_blog.run_contracts.IncumbentTransition:
	"""Derive the sole editorial replacement operation from exact Stage 7 facts.

	ASVS 2.2.1, 2.3.1, and 15.3.5: only Stage7Result's validated direct
	incumbent comparison can authorize an editorial successor.
	"""
	if type(result) is not daily_blog.stage7.Stage7Result:
		raise RuntimeError("Stage 7 transition requires an exact Stage7Result.")
	if result.direct_incumbent_comparison:
		if not result.synthesis_won or result.artifact is result.incumbent:
			raise RuntimeError("Stage 7 direct comparison does not attest a distinct winner.")
		return daily_blog.run_contracts.ReplaceIncumbent(
			result.incumbent.artifact_id, result.artifact.artifact_id,
		)
	if result.artifact is not result.incumbent:
		raise RuntimeError("Stage 7 preservation does not retain its exact incumbent.")
	return daily_blog.run_contracts.ObserveIncumbent()


#============================================
def run_typed_stage7(
	coordinator: object,
	stage6_input: daily_blog.stage6.Stage6Input,
	stage6_result: daily_blog.stage6.Stage6Result,
) -> daily_blog.stage7.Stage7Result:
	"""Run one incumbent-preserving Stage 7 using the coordinator's sole route resources."""
	value = _validate_stage7_boundary(coordinator, stage6_input, stage6_result)
	coordinator._start("stage7_final_synthesis", {
		"packet_ids": [item.packet_id for item in stage6_input.packets],
		"incumbent_artifact_id": value.incumbent.artifact_id,
		"incumbent_content_hash": value.incumbent.content_hash,
		"stage6_input_identity": value.identity_sha256,
	})
	cache_effects = _cache_buffer(coordinator)
	result = daily_blog.stage7.run_stage7(
		value, coordinator.run_id, coordinator.config, coordinator.route_budget,
		runner=coordinator.route_runner, cache_load=cache_effects.load,
		cache_accept=cache_effects.accept,
	)
	result = _validate_stage7_result(coordinator, value, result)
	coordinator.route_cache.commit(cache_effects.drain())
	_write_replay_checked_artifact(coordinator, "stage7_reliability.json", {
		"schema_version": "vosslab.daily-blog.stage7-reliability.v1",
		"steps": [item.to_dict() for item in result.step_reliability],
	})
	transition = _stage7_incumbent_transition(result)
	for summary in result.step_reliability[:-1]:
		coordinator.store.record_editorial_step(
			coordinator.record, summary, daily_blog.run_contracts.ObserveIncumbent(),
		)
	coordinator.store.record_editorial_step(
		coordinator.record, result.step_reliability[-1], transition,
	)
	coordinator._complete("stage7_final_synthesis", {
		"selected_artifact_id": result.artifact.artifact_id,
		"selected_content_hash": result.artifact.content_hash,
		"replaced_incumbent": type(transition) is daily_blog.run_contracts.ReplaceIncumbent,
	})
	return result


#============================================
def _stage6_recovery_identities(coordinator: object) -> tuple[tuple[str, ...], tuple[str, ...]]:
	"""Return the frozen Stage 6 prompt and rubric byte identities for the digest."""
	templates = coordinator.prompt_snapshot.template_dict()
	editor = daily_blog.complete_post_editor_prompts.load_complete_post_editor_prompt_contract()
	prompts = tuple(sorted({
		daily_blog.io_utils.sha256_text(templates[name])
		for name in ("author", "referee", "repair", "examples")
	} | {editor.resource_sha256}))
	return prompts, (daily_blog.io_utils.sha256_text(templates["rubric"]),)


#============================================
def _recover_stage6(
	coordinator: object, value: daily_blog.stage6.Stage6Input, result: daily_blog.stage6.Stage6Result,
	cache_effects: daily_blog.route_cache.BufferedRouteEffects,
) -> daily_blog.stage6.Stage6Result:
	"""Recover only an exhausted complete-post stage through its durable run owner."""
	prompt_identities, rubric_identities = _stage6_recovery_identities(coordinator)

	def invoke(
		budget: object, cache_load: object, cache_accept: object,
	) -> daily_blog.recovery.RecoveryAttempt:
		"""Delegate one writer recovery to the configured Stage 6 editorial path."""
		return daily_blog.stage6.recover_writer_complete_post(
			value, coordinator.run_id + "-recovery", coordinator.config, budget,
			runner=coordinator.route_runner, contract=coordinator.editorial_contract,
			snapshot=coordinator.prompt_snapshot, cache_load=cache_load, cache_accept=cache_accept,
		)

	recovery = daily_blog.stage_recovery_coordinator.StageRecoveryCoordinator(
		coordinator.store, coordinator.record, coordinator.route_budget,
		cache_load=cache_effects.load, cache_accept=cache_effects.accept,
	)
	recovered = recovery.run(daily_blog.stage_recovery_coordinator.StageRecoveryInput(
		value.report_date, "stage6/complete_post/recovery", daily_blog.artifacts.CompletePost,
		result.promotion, result.generation, result.step_reliability, value.packets,
		os.path.realpath(value.output_root), prompt_identities, rubric_identities, None,
		(daily_blog.stage_recovery_coordinator.RecoveryPathAdapter(
			daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST, invoke,
		),),
	))
	if recovered.fault is not None:
		raise daily_blog.recovery.PipelineFaultError(
			recovered.fault, recovered.digest_sha256,
		)
	if recovered.artifact is None:
		raise RuntimeError("Stage 6 recovery returned neither a post nor a pipeline fault.")
	if recovered.selected_path is not daily_blog.recovery.RecoveryRung.WRITER_COMPLETE_POST:
		raise RuntimeError("Stage 6 recovery must select the configured writer rung.")
	recovery_generation = recovered.recovery_generation
	if (
		type(recovery_generation) is not daily_blog.replication.ReplicationResult
		or recovery_generation.expected_type is not daily_blog.artifacts.CompletePost
		or len(recovery_generation.eligible) != 1
		or recovery_generation.eligible[0] is not recovered.artifact
	):
		raise RuntimeError("Stage 6 selected writer recovery lacks exact generation provenance.")
	return dataclasses.replace(
		result,
		promotion=daily_blog.artifacts.DegradedPromotion(
			recovered.artifact, daily_blog.artifacts.CompletePost, ("no_eligible_generation",),
		),
		recovery_generation=recovery_generation,
	)


def _publication_validation_transition(
	result: daily_blog.publication_validation.PublicationValidationResult,
) -> daily_blog.run_contracts.IncumbentTransition:
	"""Derive Stage 8's distinct repair audit operation from exact identities.

	ASVS 2.2.1, 2.3.1, and 15.3.5: a derivative must retain the exact validated
	parent identity; no-op validation is observational and cannot advance state.
	"""
	if type(result) is not daily_blog.publication_validation.PublicationValidationResult:
		raise RuntimeError("Publication transition requires an exact validation result.")
	if result.before_artifact_id == result.after_artifact_id:
		if result.post is not result.source_post or result.repaired:
			raise RuntimeError("Publication no-op validation has inconsistent source facts.")
		return daily_blog.run_contracts.ObserveIncumbent()
	if not result.repaired or result.post is result.source_post:
		raise RuntimeError("Publication repair lacks an exact validated derivative.")
	return daily_blog.run_contracts.RepairPublicationIncumbent(
		result.before_artifact_id, result.after_artifact_id,
	)


#============================================
def validate_selected_post(
	coordinator: object,
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
	post: daily_blog.artifacts.CompletePost,
) -> daily_blog.publication_validation.PublicationValidationResult:
	"""Apply Stage 8 and advance the coordinator's sole best-artifact pointer."""
	if type(post) is not daily_blog.artifacts.CompletePost:
		raise RuntimeError("Publication validation requires an exact Stage 7 selected CompletePost.")
	if type(packets) is not tuple or not packets or any(type(item) is not daily_blog.schema.EvidencePacket for item in packets):
		raise RuntimeError("Publication validation requires the exact editorial packet union.")
	phase_input = {
		"before_artifact_id": post.artifact_id,
		"content_hash": post.content_hash,
		"packet_ids": [item.packet_id for item in packets],
		"report_date": coordinator.report_date,
	}
	coordinator._start("publication_validation", phase_input)
	result = daily_blog.publication_validation.validate_and_repair_complete_post(
		post,
		report_date=coordinator.report_date,
		packets=packets,
		approved_output_root=os.path.abspath(coordinator.config.output_root),
		generator_run=coordinator.run_id,
	)
	daily_blog.publication_validation.validate_result_for_inputs(
		result, source_post=post, report_date=coordinator.report_date, packets=packets,
		approved_output_root=os.path.abspath(coordinator.config.output_root),
		generator_run=coordinator.run_id,
	)
	value = {
		"before_artifact_id": result.before_artifact_id,
		"after_artifact_id": result.after_artifact_id,
		"content_hash": result.post.content_hash,
		"reasons": list(result.reasons),
	}
	coordinator.store.write_artifact("publication_validation.json", value)
	reliability = daily_blog.replication.StepReliability(
		"publication_validation", "degraded" if result.repaired else "succeeded", 1, 1,
		0, 0, int(result.repaired), 0, result.after_artifact_id, result.reasons,
	)
	coordinator.store.record_editorial_step(
		coordinator.record, reliability, _publication_validation_transition(result),
	)
	coordinator._complete("publication_validation", value)
	return result


#============================================
def write_selected_post(
	coordinator: object,
	post: daily_blog.artifacts.CompletePost,
) -> None:
	"""Atomically materialize the selected Stage-8 bytes before any import."""
	phase_input = {
		"artifact_id": post.artifact_id,
		"content_hash": post.content_hash,
		"output_path": post.output_path,
	}
	coordinator._start("post_write", phase_input)
	daily_blog.io_utils.atomic_write_text(post.output_path, post.content)
	with open(post.output_path, "r", encoding="utf-8") as handle:
		written = handle.read()
	if written != post.content:
		raise RuntimeError("Post-write bytes do not match the selected complete post.")
	coordinator.store.write_artifact("post_write.json", {
		"artifact_id": post.artifact_id,
		"path": coordinator.store.derive_output_logical_path(post.output_path),
		"sha256": daily_blog.io_utils.sha256_text(written),
	})
	coordinator._complete("post_write", {
		"artifact_id": post.artifact_id,
		"sha256": post.content_hash,
	})

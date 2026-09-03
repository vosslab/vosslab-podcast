"""Serial repository-editorial acceptance between fan-out and Stage 5."""

# Standard Library
import collections.abc
import dataclasses
import os

# local repo modules
import daily_blog.agents
import daily_blog.config
import daily_blog.daily_outline_prompts
import daily_blog.daily_outline_workflow
import daily_blog.editorial
import daily_blog.io_utils
import daily_blog.multi_repository_coordinator
import daily_blog.projection
import daily_blog.recovery
import daily_blog.replication
import daily_blog.route_cache
import daily_blog.run_contracts
import daily_blog.schema


#============================================
def _aggregate_repository_reliability(
	results: tuple[daily_blog.multi_repository_coordinator.RepositoryJobResult, ...],
) -> tuple[daily_blog.replication.StepReliability, ...]:
	"""Combine repository observations once per mechanism for durable state."""
	by_step: dict[str, list[daily_blog.replication.StepReliability]] = {}
	for result in results:
		for summary in result.reliability:
			by_step.setdefault(summary.step, []).append(summary)
	values = []
	for step in sorted(by_step):
		items = by_step[step]
		reasons = tuple(sorted({reason for item in items for reason in item.reasons}))
		values.append(daily_blog.replication.StepReliability(
			step, "degraded" if reasons else "succeeded",
			sum(item.attempted for item in items), sum(item.succeeded for item in items),
			sum(item.failed for item in items), sum(item.reused for item in items),
			sum(item.repaired for item in items), sum(item.disagreements for item in items),
			"", reasons,
		))
	return tuple(values)


def _projection_phase_input(
	packet: daily_blog.schema.EvidencePacket,
	config: daily_blog.config.DailyBlogConfig,
) -> dict[str, object]:
	"""Bind the pre-dispatch phase to hashes and counts, never packet contents."""
	return {
		"config_sha256": daily_blog.io_utils.hash_value(dataclasses.asdict(config)),
		"global_packet_id": packet.packet_id,
		"global_packet_sha256": daily_blog.io_utils.hash_value(packet.content_dict()),
		"activity_count": len(packet.activity),
		"evidence_count": len(packet.items),
		"mirror_count": len(packet.mirrors),
	}


def _packet_digest_packet(
	packet: daily_blog.schema.EvidencePacket,
) -> daily_blog.recovery.EvidenceDigestPacket:
	"""Retain original sealed packet identity and evidence refs for a safe fault."""
	return daily_blog.recovery.EvidenceDigestPacket(
		packet.packet_id, daily_blog.io_utils.hash_value(packet.content_dict()),
		tuple(sorted(item.evidence_id for item in packet.items)),
	)


@dataclasses.dataclass(frozen=True)
class RepositoryEditorialDependencies:
	"""Exact capabilities for the serial acceptance of repository editorial work."""

	config: daily_blog.config.DailyBlogConfig
	report_date: str
	prompt_snapshot: daily_blog.editorial.PromptContractSnapshot
	route_runner: object | None
	route_cache: daily_blog.route_cache.RouteResultCache
	working_directory: str
	start: collections.abc.Callable[[str, object], str]
	complete: collections.abc.Callable[[str, object, bool], str]
	record_summary: collections.abc.Callable[
		[daily_blog.replication.StepReliability, daily_blog.run_contracts.IncumbentTransition], None
	]
	write_artifact: collections.abc.Callable[[str, dict[str, object]], str]

	#============================================
	def __post_init__(self) -> None:
		"""Reject ambiguous collaborators before dispatching external editorial work."""
		# ASVS 2.2.1, 2.2.3, 15.3.5: exact trusted boundary values bind one run.
		if (
			type(self.config) is not daily_blog.config.DailyBlogConfig
			or type(self.report_date) is not str
			or type(self.prompt_snapshot) is not daily_blog.editorial.PromptContractSnapshot
			or type(self.route_cache) is not daily_blog.route_cache.RouteResultCache
			or type(self.working_directory) is not str
			or not os.path.isabs(self.working_directory)
			or os.path.realpath(self.working_directory) != self.working_directory
			or not os.path.isdir(self.working_directory)
			or not all(callable(value) for value in (
				self.start, self.complete, self.record_summary, self.write_artifact,
			))
		):
			raise RuntimeError("Repository editorial dependencies are invalid.")
		daily_blog.editorial.validate_snapshot(self.prompt_snapshot)


@dataclasses.dataclass(frozen=True)
class RepositoryEditorialResult:
	"""Accepted Stage-5 input and the exact shared route admission it requires."""

	stage5_input: daily_blog.daily_outline_workflow.DailyOutlineInput
	route_capacity: daily_blog.route_cache.RunCapacityPlan
	route_budget: daily_blog.agents.RouteBudget

	#============================================
	def __post_init__(self) -> None:
		"""Keep one budget and capacity identity available to later editorial stages."""
		if (
			type(self.stage5_input) is not daily_blog.daily_outline_workflow.DailyOutlineInput
			or type(self.route_capacity) is not daily_blog.route_cache.RunCapacityPlan
			or type(self.route_budget) is not daily_blog.agents.RouteBudget
			or self.route_budget.maximum_parallel_calls != self.route_capacity.maximum_parallel_calls
		):
			raise RuntimeError("Repository editorial result is invalid.")


class RepositoryEditorialCoordinator:
	"""Accept a canonical repository join without owning route workers or Stage 5."""

	#============================================
	def __init__(self, dependencies: RepositoryEditorialDependencies) -> None:
		if type(dependencies) is not RepositoryEditorialDependencies:
			raise RuntimeError("Repository editorial coordinator requires exact dependencies.")
		self._dependencies = dependencies

	#============================================
	def run(
		self, packet: daily_blog.schema.EvidencePacket,
	) -> RepositoryEditorialResult:
		"""Run the pure fan-out, then serialize only its accepted bounded effects."""
		# ASVS 1.5.2, 2.2.1, and 2.3.1: revalidate frozen evidence and bind it
		# to this run before capacity admission or any durable state transition.
		if type(packet) is not daily_blog.schema.EvidencePacket:
			raise RuntimeError("Repository editorial requires an exact EvidencePacket.")
		dependencies = self._dependencies
		if packet.report_date != dependencies.report_date:
			raise RuntimeError("Repository editorial packet date does not match the run.")
		dependencies.start("repository_editorial", _projection_phase_input(packet, dependencies.config))
		try:
			projected = daily_blog.multi_repository_coordinator.project_repository_packets(packet)
		except daily_blog.multi_repository_coordinator.RepositoryProjectionFault as error:
			self._raise_projection_fault(packet, error.terminal_fault)
		capacity = daily_blog.route_cache.RunCapacityPlan.for_run(
			dependencies.config, len(projected),
		)
		budget = capacity.new_budget()
		templates = dependencies.prompt_snapshot.template_dict()
		rubric = templates.get("rubric")
		if type(rubric) is not str or not rubric:
			raise RuntimeError("Repository editorial prompt snapshot has no rubric.")
		rubric_sha256 = daily_blog.io_utils.sha256_text(rubric)
		joined = daily_blog.multi_repository_coordinator.run_repository_editorial(
			packet, projected, dependencies.config, budget, dependencies.route_runner,
			rubric, rubric_sha256, dependencies.route_cache, dependencies.working_directory,
		)
		if type(joined) is not daily_blog.multi_repository_coordinator.RepositoryEditorialJoin:
			raise RuntimeError("Repository editorial join is invalid.")
		# ASVS 15.4.1-15.4.3: the fan-out returns buffered effects; only this
		# serial owner admits the validated complete join to the shared cache.
		dependencies.route_cache.commit(joined.cache_effects)
		aggregates = _aggregate_repository_reliability(joined.results)
		for summary in aggregates:
			dependencies.record_summary(summary, daily_blog.run_contracts.ObserveIncumbent())
		artifact = {
			"schema_version": "vosslab.daily-blog.repository-editorial.v1",
			"repositories": [{
				"repository": item.repository,
				"packet_id": item.packet.packet_id,
				"outline_artifact_id": "" if item.outline is None else item.outline.artifact_id,
				"story_artifact_id": "" if item.story is None else item.story.artifact_id,
				"outcome": "failed" if item.terminal_fault is not None else "succeeded",
				"terminal_fault": "" if item.terminal_fault is None else str(item.terminal_fault),
				"degraded": item.degraded,
			} for item in joined.results],
			"survivor_packet_ids": [item.packet_id for item in joined.packets],
			"reliability": [item.to_dict() for item in aggregates],
		}
		if not joined.repo_stories:
			dependencies.write_artifact("repository_editorial.json", artifact)
			self._raise_terminal_fault(joined, projected, aggregates, rubric_sha256)
		context_chars = min(
			dependencies.config.projection_limits["context_chars"],
			daily_blog.daily_outline_prompts.MAX_EVIDENCE_CONTEXT_CHARS,
		)
		evidence_context = daily_blog.projection.build_bounded_evidence_context(
			joined.packets,
			dependencies.config.projection_limits,
			context_chars,
		)
		daily_blog.projection.validate_bounded_evidence_context(
			joined.packets,
			evidence_context,
		)
		artifact["stage5_evidence_context"] = {
			"context_id": evidence_context.context_id,
			"model_context_id": evidence_context.model_context_id,
			"packet_ids": list(evidence_context.packet_ids),
		}
		dependencies.write_artifact("stage5_evidence_context.json", evidence_context.to_dict())
		value = daily_blog.daily_outline_workflow.DailyOutlineInput(
			joined.repo_stories, joined.repo_outlines, joined.packets, evidence_context,
			os.path.abspath(dependencies.config.output_root),
		)
		artifact["stage5_repository_context"] = {
			"context_id": value.repository_context.context_id,
			"model_context_id": value.repository_context.model_context_id,
			"projection_version": value.repository_context.story_context.projection_version,
		}
		dependencies.write_artifact(
			"stage5_repository_context.json", value.repository_context.to_dict(),
		)
		dependencies.write_artifact("repository_editorial.json", artifact)
		dependencies.complete("repository_editorial", {
			"repositories": list(value.repositories),
			"packet_ids": [item.packet_id for item in value.packets],
			"stage5_evidence_context_id": evidence_context.context_id,
			"stage5_evidence_context_model_id": evidence_context.model_context_id,
			"stage5_repository_context_id": value.repository_context.context_id,
			"stage5_repository_context_model_id": value.repository_context.model_context_id,
		}, False)
		return RepositoryEditorialResult(value, capacity, budget)

	#============================================
	def _raise_projection_fault(
		self, packet: daily_blog.schema.EvidencePacket,
		terminal_fault: daily_blog.recovery.TerminalFaultDigest,
	) -> None:
		"""Persist one projection diagnosis before the public workflow boundary."""
		if (
			type(terminal_fault) is not daily_blog.recovery.TerminalFaultDigest
			or terminal_fault.category is not daily_blog.recovery.TerminalFaultCategory.IMPLEMENTATION_DEFECT
		):
			raise RuntimeError("Repository projection terminal fault is invalid.")
		observation = daily_blog.recovery.GenerationObservation(
			"repository_terminal", 0, 0, (), terminal_fault.category,
		)
		fault = daily_blog.recovery.PipelineFault(
			terminal_fault.category, 0, "", "", (observation,),
			terminal_fault=terminal_fault,
		)
		payload, digest = daily_blog.recovery.canonical_evidence_digest(
			daily_blog.recovery.EvidenceDigestInput(
				self._dependencies.report_date, "stage3/repository_editorial/terminal",
				(), (_packet_digest_packet(packet),), (), (), fault,
				allowed_repositories=(),
			)
		)
		# ASVS 13.4.2, 15.4.2, and 16.2.5: serialize one atomic canonical
		# digest only; it contains neither prompts, route output, nor error text.
		self._dependencies.write_artifact("recovery_fault.json", payload)
		raise daily_blog.recovery.PipelineFaultError(fault, digest)

	#============================================
	def _raise_terminal_fault(
		self,
		joined: daily_blog.multi_repository_coordinator.RepositoryEditorialJoin,
		projected: tuple[daily_blog.schema.EvidencePacket, ...],
		aggregates: tuple[daily_blog.replication.StepReliability, ...],
		rubric_sha256: str,
	) -> None:
		"""Persist a bounded terminal digest before exposing the typed fault."""
		candidates = []
		for result in joined.results:
			if result.outline_result is None:
				continue
			candidates.extend(result.outline_result.generation.candidates)
			candidates.extend(result.outline_result.merger.candidates)
			if result.story_result is not None:
				candidates.extend(result.story_result.writing.candidates)
				candidates.extend(result.story_result.editing.candidates)
		observations = [daily_blog.recovery.GenerationObservation(
			"repository_editorial", len(candidates), sum(item.result.ok for item in candidates), (),
		)] if candidates else [daily_blog.recovery.GenerationObservation(
			"repository_editorial", 0, 0, (),
		)]
		if not projected:
			observations[0] = daily_blog.recovery.GenerationObservation(
				"repository_evidence", 0, 0, (),
				daily_blog.recovery.TerminalFaultCategory.EVIDENCE_UNAVAILABLE,
			)
		if joined.terminal_fault is not None:
			observations.append(daily_blog.recovery.GenerationObservation(
				"repository_terminal", 0, 0, (), joined.terminal_fault,
			))
		outlines = tuple(sorted(
			(item.outline for item in joined.results if item.outline is not None),
			key=lambda item: (item.content_hash, item.artifact_id),
		))
		strongest = outlines[0] if outlines else None
		fault = daily_blog.recovery.PipelineFault(
			daily_blog.recovery.classify_pipeline_fault(tuple(observations)), 0,
			"" if strongest is None else strongest.artifact_id,
			"" if strongest is None else type(strongest).__name__, tuple(observations),
			terminal_fault=joined.terminal_fault_digest,
		)
		steps = tuple(sorted((daily_blog.recovery.EvidenceDigestStep(
			("stage3" if item.step.startswith("3.") else "stage4")
			+ "/repository_editorial/" + item.step, item.outcome, item.attempted,
			item.succeeded, item.failed, item.reused, item.repaired,
			item.disagreements, item.best_artifact_id, item.reasons,
		) for item in aggregates), key=lambda item: item.step_key))
		packets = tuple(sorted((daily_blog.recovery.EvidenceDigestPacket(
			item.packet_id, daily_blog.io_utils.hash_value(item.content_dict()),
			tuple(sorted(value.evidence_id for value in item.items)),
		) for item in projected), key=lambda item: item.packet_id))
		allowed_repositories = tuple(sorted(
			{item.activity[0].repository for item in projected},
		))
		payload, digest = daily_blog.recovery.canonical_evidence_digest(
			daily_blog.recovery.EvidenceDigestInput(
				self._dependencies.report_date, "stage3/repository_editorial/terminal",
				steps, packets, (), (rubric_sha256,), fault,
				() if strongest is None else (strongest.artifact_id,),
				allowed_repositories=allowed_repositories,
			)
		)
		# ASVS 13.4.2, 14.2.4, and 16.2.5: write only canonical bounded facts,
		# never route prompts, responses, working paths, or exception diagnostics.
		self._dependencies.write_artifact("recovery_fault.json", payload)
		raise daily_blog.recovery.PipelineFaultError(fault, digest)

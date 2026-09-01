"""Persist editorial recovery outcomes at the recovery/publication boundary.

This module deliberately owns the only durable ``RunStore`` writes for
editorial recovery. Stage workers return typed facts; recovery selection remains
in :mod:`daily_blog.recovery` before a recovery outcome is published to run state.
"""

# Standard Library
import collections.abc
import dataclasses
import datetime
import json
import os

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.io_utils
import daily_blog.publication_admission
import daily_blog.recovery
import daily_blog.replication
import daily_blog.run_contracts
import daily_blog.run_state
import daily_blog.schema


_STAGE_KEY_RE = daily_blog.recovery.STAGE_KEY_RE
_REUSED_KEY_RE = daily_blog.recovery.STAGE_KEY_RE
_MAX_REUSED_STEP_KEYS = 512
_SAFE_RELIABILITY_REASONS = frozenset({
	"configuration", "editor_unavailable", "empty_response", "evidence_unavailable",
	"editor_prompt_limit",
	"implementation_defect", "ineligible_generation", "merger_unavailable",
	"invalid_aliases", "invalid_fields", "invalid_json", "invalid_order",
	"invalid_rationale", "invalid_scores",
	"no_eligible_generation", "partial_route_failure", "process_failure",
	"ranking_fallback_used",
	"route_empty_response", "route_process_failure", "route_start_failure", "route_timeout",
	"route_unavailable",
	"review_disagreement", "review_empty_response", "review_invalid_verdict",
	"review_process_failure", "review_start_failure", "review_timeout", "review_unavailable",
	"reviewer_unavailable",
	"response_limit", "start_failure", "timeout", "upstream_unavailable",
}) | daily_blog.artifacts.ELIGIBILITY_REASONS


@dataclasses.dataclass(frozen=True)
class RecoveryPathAdapter:
	"""A recovery route which cannot substitute the run-owned budget or cache."""

	rung: daily_blog.recovery.RecoveryRung
	invoke: collections.abc.Callable[
		[
			daily_blog.agents.RouteBudget,
			collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None,
			collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None,
		], daily_blog.recovery.RecoveryAttempt,
	]

	def __post_init__(self) -> None:
		if type(self.rung) is not daily_blog.recovery.RecoveryRung or not callable(self.invoke):
			raise daily_blog.recovery.RecoveryConfigurationError("Recovery path adapter is invalid.")


@dataclasses.dataclass(frozen=True)
class StageRecoveryInput:
	"""Exact provenance and adapters needed to recover one complete-post stage."""

	report_date: str
	stage_key: str
	source_artifact_type: type
	source_promotion: (daily_blog.artifacts.SelectedPeer | daily_blog.artifacts.PreservedArtifact
		| daily_blog.artifacts.DegradedPromotion | daily_blog.artifacts.NoArtifact)
	source_result: daily_blog.replication.ReplicationResult
	source_summaries: tuple[daily_blog.replication.StepReliability, ...]
	packets: tuple[daily_blog.schema.EvidencePacket, ...]
	allowed_repositories: tuple[str, ...]
	trusted_output_root: str
	publication_surface: daily_blog.publication_admission.PublicationSurface | None
	prompt_identities: tuple[str, ...]
	rubric_identities: tuple[str, ...]
	incumbent: daily_blog.recovery.RecoveryIncumbent | None
	paths: tuple[RecoveryPathAdapter, ...]

	def __post_init__(self) -> None:
		if type(self.report_date) is not str or type(self.stage_key) is not str or _STAGE_KEY_RE.fullmatch(self.stage_key) is None:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery identity is invalid.")
		try:
			datetime.date.fromisoformat(self.report_date)
		except ValueError as error:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery report date is invalid.") from error
		if self.source_artifact_type is not daily_blog.artifacts.CompletePost:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery must produce exact CompletePost artifacts.")
		if type(self.source_result) is not daily_blog.replication.ReplicationResult:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery source result is invalid.")
		if self.source_result.expected_type is not self.source_artifact_type:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery source type is inconsistent.")
		if type(self.source_promotion) not in (
			daily_blog.artifacts.SelectedPeer, daily_blog.artifacts.PreservedArtifact,
			daily_blog.artifacts.DegradedPromotion, daily_blog.artifacts.NoArtifact,
		) or self.source_promotion.expected_type is not self.source_artifact_type:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery promotion is invalid.")
		if type(self.source_summaries) is not tuple or not self.source_summaries:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery summaries are invalid.")
		if any(type(item) is not daily_blog.replication.StepReliability for item in self.source_summaries):
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery summary type is invalid.")
		for summary in self.source_summaries:
			summary.validate()
			if any(reason not in _SAFE_RELIABILITY_REASONS for reason in summary.reasons):
				raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery summary reason is unsafe.")
		if type(self.packets) is not tuple or any(
			type(packet) is not daily_blog.schema.EvidencePacket for packet in self.packets
		):
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery packets are invalid.")
		if not self.packets and (
			type(self.source_promotion) is not daily_blog.artifacts.NoArtifact
			or self.source_promotion.reason != "evidence_unavailable"
		):
			raise daily_blog.recovery.RecoveryConfigurationError("Only unavailable evidence may omit packets.")
		if self.packets and (
			tuple(packet.packet_id for packet in self.packets) != tuple(sorted(packet.packet_id for packet in self.packets))
			or len({packet.packet_id for packet in self.packets}) != len(self.packets)
		):
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery packet identities are not canonical.")
		if (
			type(self.allowed_repositories) is not tuple
			or not self.allowed_repositories
			or tuple(sorted(set(self.allowed_repositories))) != self.allowed_repositories
			or any(type(repository) is not str or not repository for repository in self.allowed_repositories)
		):
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery allowed repository scope is invalid.")
		packet_repositories = {
			item.repository for packet in self.packets for item in packet.items
		}
		if packet_repositories and not set(self.allowed_repositories).issubset(packet_repositories):
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery allowed repository scope exceeds packets.")
		if type(self.trusted_output_root) is not str or not os.path.isabs(self.trusted_output_root) or not os.path.isdir(self.trusted_output_root) or os.path.realpath(self.trusted_output_root) != self.trusted_output_root:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery output root is not trusted.")
		if self.packets:
			if type(self.publication_surface) is not daily_blog.publication_admission.PublicationSurface:
				raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery publication surface is invalid.")
		elif self.publication_surface is not None:
			raise daily_blog.recovery.RecoveryConfigurationError(
				"Unavailable evidence cannot carry a publication surface."
			)
		if type(self.paths) is not tuple or any(type(path) is not RecoveryPathAdapter for path in self.paths):
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery paths are invalid.")
		for identities, label in ((self.prompt_identities, "prompt"), (self.rubric_identities, "rubric")):
			if type(identities) is not tuple or not identities or len(identities) > daily_blog.recovery.MAX_DIGEST_EVIDENCE_REFS or tuple(sorted(set(identities))) != identities or any(
				type(identity) is not str or daily_blog.recovery.SHA256_RE.fullmatch(identity) is None for identity in identities
			):
				raise daily_blog.recovery.RecoveryConfigurationError(f"Stage recovery {label} identities are invalid.")
		if self.incumbent is not None and type(self.incumbent) is not daily_blog.recovery.RecoveryIncumbent:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery incumbent is invalid.")


@dataclasses.dataclass(frozen=True)
class StageRecoveryResult:
	"""One successful whole post or a structured terminal fault and digest identity."""

	artifact: daily_blog.artifacts.CompletePost | None
	selected_path: daily_blog.recovery.RecoveryRung | None
	fault: daily_blog.recovery.PipelineFault | None
	digest_path: str
	digest_sha256: str
	reused_step_keys: tuple[str, ...]
	recovery_generation: daily_blog.replication.ReplicationResult | None = None

	def __post_init__(self) -> None:
		if type(self.reused_step_keys) is not tuple or len(self.reused_step_keys) > _MAX_REUSED_STEP_KEYS or tuple(sorted(set(self.reused_step_keys))) != self.reused_step_keys or any(
			type(key) is not str or _REUSED_KEY_RE.fullmatch(key) is None for key in self.reused_step_keys
		):
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery reused keys are invalid.")
		if self.artifact is not None:
			if type(self.artifact) is not daily_blog.artifacts.CompletePost or self.selected_path is not None and type(self.selected_path) is not daily_blog.recovery.RecoveryRung or self.fault is not None or self.digest_path or self.digest_sha256:
				raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery success result is invalid.")
			if self.recovery_generation is not None:
				daily_blog.recovery._validate_recovery_generation(
					self.recovery_generation, daily_blog.artifacts.CompletePost,
					selected_artifact=self.artifact,
				)
			return
		if self.recovery_generation is not None or self.selected_path is not None or type(self.fault) is not daily_blog.recovery.PipelineFault or not os.path.isabs(self.digest_path) or os.path.basename(self.digest_path) != "recovery_fault.json" or daily_blog.recovery.SHA256_RE.fullmatch(self.digest_sha256) is None:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery fault result is invalid.")


class StageRecoveryCoordinator:
	"""The sole durable-write boundary for recovery summaries and faults."""

	def __init__(
		self, store: daily_blog.run_state.RunStore, record: daily_blog.run_contracts.RunRecord,
		budget: daily_blog.agents.RouteBudget,
		cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None = None,
		cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None = None,
	) -> None:
		if type(store) is not daily_blog.run_state.RunStore or type(record) is not daily_blog.run_contracts.RunRecord:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery durable state is invalid.")
		if type(budget) is not daily_blog.agents.RouteBudget or (cache_load is not None and not callable(cache_load)) or (cache_accept is not None and not callable(cache_accept)):
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery route boundary is invalid.")
		self.store = store
		self.record = record
		self.budget = budget
		self.cache_load = cache_load
		self.cache_accept = cache_accept

	def _validate_lineage(self, value: StageRecoveryInput) -> None:
		# ASVS 1.5.2, 2.2.1, 2.3.1: bind every recovery action to immutable run identity.
		if value.report_date != self.record.report_date or value.report_date != self.store.report_date:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery report date does not match run state.")
		try:
			if os.path.commonpath((value.trusted_output_root, self.store.run_dir)) != value.trusted_output_root:
				raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery output root is outside this run owner.")
		except ValueError as error:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery output root is invalid.") from error
		if any(packet.report_date != value.report_date or daily_blog.io_utils.hash_value(packet.content_dict()) != packet.packet_id for packet in value.packets):
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery packet lineage is invalid.")
		for candidate in value.source_result.candidates:
			self._validate_source_candidate(candidate, value)
		if not isinstance(value.source_promotion, daily_blog.artifacts.NoArtifact):
			self._validate_artifact(
				value.source_promotion.artifact, value, daily_blog.artifacts.CompletePost,
				require_full_packet_union=True, require_publication_eligibility=True,
			)
		if value.incumbent is not None:
			if value.incumbent.rung is not daily_blog.recovery.RecoveryRung.STRONGEST_REPOSITORY_MATERIAL:
				raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery incumbent rung is invalid.")
			if type(value.incumbent.artifact) is not daily_blog.artifacts.RepoStory:
				raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery terminal incumbent type is invalid.")
			self._validate_artifact(
				value.incumbent.artifact, value, daily_blog.artifacts.RepoStory,
				require_full_packet_union=False, require_publication_eligibility=False,
			)
		if value.publication_surface is not None and (
			value.publication_surface.source_packets != value.packets
			or value.publication_surface.coverage_repositories != value.allowed_repositories
			or value.publication_surface.packet.report_date != value.report_date
		):
			raise daily_blog.recovery.RecoveryConfigurationError(
				"Stage recovery publication surface provenance is invalid."
			)

	def _validate_artifact(
		self,
		artifact: daily_blog.artifacts.EditorialArtifact,
		value: StageRecoveryInput,
		expected_type: type[daily_blog.artifacts.EditorialArtifact],
		*,
		require_full_packet_union: bool,
		require_publication_eligibility: bool,
	) -> None:
		"""Validate one retained artifact at its exact recovery boundary.

		A parsed primary CompletePost may be mechanically ineligible and still
		record the ordinary editorial outcome that activates recovery.  Promotion
		and recovery output require full publication eligibility.  The terminal
		RepoStory incumbent may honestly cover only its packet subset.
		"""
		if type(artifact) is not expected_type:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery artifact type is invalid.")
		try:
			artifact._validate_machine_state()
		except (AttributeError, RuntimeError, TypeError) as error:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery artifact machine metadata is invalid.") from error
		packet_ids = artifact.packet_ids if type(artifact.packet_ids) is tuple else ()
		authoritative_packet_ids = tuple(packet.packet_id for packet in value.packets)
		if (
			artifact.report_date != value.report_date
			or not packet_ids
			or tuple(sorted(set(packet_ids))) != packet_ids
			or (
				packet_ids != authoritative_packet_ids if require_full_packet_union
				else not set(packet_ids).issubset(authoritative_packet_ids)
			)
		):
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery artifact provenance is invalid.")
		repositories = artifact.repositories if type(artifact.repositories) is tuple else ()
		if (
			not repositories
			or tuple(sorted(set(repositories))) != repositories
			or not set(repositories).issubset(value.allowed_repositories)
			or not require_full_packet_union and len(repositories) != 1
		):
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery repository scope is invalid.")
		try:
			cited_repositories = daily_blog.artifacts.resolve_evidence_scope(
				artifact.evidence_ids, value.packets, value.allowed_repositories, packet_ids,
			)
		except RuntimeError as error:
			raise daily_blog.recovery.RecoveryConfigurationError(
				"Stage recovery artifact cited evidence scope is invalid."
			) from error
		if repositories != cited_repositories:
			raise daily_blog.recovery.RecoveryConfigurationError(
				"Stage recovery artifact repository declaration is invalid."
			)
		if not require_publication_eligibility:
			return
		if not self._complete_post_eligible(value, artifact):
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery artifact is not mechanically eligible.")

	def _complete_post_eligible(
		self,
		value: StageRecoveryInput,
		artifact: daily_blog.artifacts.CompletePost,
	) -> bool:
		"""Apply the exact admission scope owned by this recovery stage."""
		if value.publication_surface is None:
			return False
		return daily_blog.publication_admission.complete_post_eligibility(
			artifact, value.publication_surface, value.trusted_output_root,
			recovery=value.stage_key == "stage6/complete_post/recovery",
		).eligible

	def _validate_source_candidate(
		self,
		candidate: daily_blog.replication.ReplicatedCandidate,
		value: StageRecoveryInput,
	) -> None:
		"""Validate retained primary facts before they can activate recovery.

		The stored decision is evidence, not authority: recovery recomputes the
		mechanical decision from this run's packet union and trusted root.  An
		ineligible result remains ordinary editorial degradation only when those
		facts agree exactly.
		"""
		if type(candidate) is not daily_blog.replication.ReplicatedCandidate:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery source candidate is invalid.")
		if (candidate.artifact is None) != (candidate.eligibility is None):
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery candidate eligibility is invalid.")
		if candidate.artifact is None:
			return
		if type(candidate.eligibility) is not daily_blog.artifacts.EligibilityResult:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery candidate eligibility is invalid.")
		# Parsed primary peers are retained as editorial evidence even when
		# publication eligibility rejects them.  Their immutable provenance
		# still has to bind exactly to this Stage-6 run before recovery can treat
		# that rejection as ordinary degradation.
		self._validate_artifact(
			candidate.artifact, value, daily_blog.artifacts.CompletePost,
			require_full_packet_union=True, require_publication_eligibility=False,
		)
		if value.publication_surface is None:
			raise daily_blog.recovery.RecoveryConfigurationError(
				"Stage recovery publication surface is unavailable."
			)
		recomputed = daily_blog.publication_admission.complete_post_eligibility(
			candidate.artifact, value.publication_surface, value.trusted_output_root,
			recovery=value.stage_key == "stage6/complete_post/recovery",
		)
		if candidate.eligibility != recomputed:
			raise daily_blog.recovery.RecoveryConfigurationError(
				"Stage recovery candidate eligibility decision is invalid."
			)

	def _source_observation(self, value: StageRecoveryInput) -> daily_blog.recovery.GenerationObservation:
		candidates = value.source_result.candidates
		for candidate in candidates:
			if type(candidate) is not daily_blog.replication.ReplicatedCandidate or type(candidate.result) is not daily_blog.agents.AgentResult:
				raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery source candidates are invalid.")
			if (candidate.artifact is None) != (candidate.eligibility is None) or (
				candidate.artifact is not None and type(candidate.artifact) is not value.source_artifact_type
			) or (candidate.eligibility is not None and type(candidate.eligibility) is not daily_blog.artifacts.EligibilityResult):
				raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery candidate eligibility is invalid.")
		attempted = len(candidates)
		successful = sum(1 for candidate in candidates if candidate.result.ok)
		eligible = tuple(sorted(item.artifact.artifact_id for item in candidates if item.artifact is not None and item.eligibility is not None and item.eligibility.eligible))
		return daily_blog.recovery.GenerationObservation(
			"source_generation", attempted, successful, eligible,
		)

	def _namespace(self, value: StageRecoveryInput, summary: daily_blog.replication.StepReliability) -> daily_blog.replication.StepReliability:
		stage, identity, _marker = value.stage_key.split("/")
		return dataclasses.replace(summary, step=f"{stage}/{identity}/{summary.step}")

	def _persist(
		self,
		summary: daily_blog.replication.StepReliability,
		transition: daily_blog.run_contracts.IncumbentTransition,
	) -> bool:
		"""Persist once; same key with changed facts is an implementation defect."""
		payload = summary.to_dict()
		for index, existing in enumerate(self.record.editorial_steps):
			if existing.get("step") != summary.step:
				continue
			if daily_blog.io_utils.hash_value(existing) != daily_blog.io_utils.hash_value(payload):
				raise daily_blog.recovery.RecoveryConfigurationError("Recovery replay diverged from durable summary.")
			stored_step, stored_transition = daily_blog.run_contracts.parse_incumbent_transition(
				self.record.editorial_transitions[index],
			)
			if stored_step != summary.step or stored_transition != transition:
				raise daily_blog.recovery.RecoveryConfigurationError("Recovery replay diverged from durable transition.")
			return True
		self.store.record_editorial_step(self.record, summary, transition)
		return False

	def _eligible(self, value: StageRecoveryInput, artifact: daily_blog.artifacts.EditorialArtifact) -> bool:
		"""Apply final-post policy while retaining a grounded story incumbent."""
		if type(artifact) is daily_blog.artifacts.CompletePost:
			return self._complete_post_eligible(value, artifact)
		return daily_blog.artifacts.evaluate_eligibility(
			artifact, value.packets, (), value.allowed_repositories,
		).eligible

	def _promote(self, prior: daily_blog.artifacts.CompletePost | None, candidate: daily_blog.artifacts.CompletePost) -> daily_blog.artifacts.CompletePost:
		return prior if prior is not None else candidate

	def _recovery_transition(
		self,
		value: StageRecoveryInput,
		artifact: daily_blog.artifacts.CompletePost,
	) -> daily_blog.run_contracts.IncumbentTransition:
		"""Establish only a first exact eligible recovery artifact.

		ASVS 2.2.1, 2.3.1, and 15.3.5: recovery selection cannot replace an
		existing editorial incumbent or promote an unchecked artifact.
		"""
		if type(artifact) is not daily_blog.artifacts.CompletePost or not self._eligible(value, artifact):
			raise daily_blog.recovery.RecoveryConfigurationError(
				"Stage recovery selected artifact is not an eligible complete post."
			)
		if self.record.best_artifact_id:
			return daily_blog.run_contracts.ObserveIncumbent()
		return daily_blog.run_contracts.EstablishIncumbent(artifact.artifact_id)

	def _recovery_summary(
		self, value: StageRecoveryInput, rung: daily_blog.recovery.RecoveryRung,
		artifact: daily_blog.artifacts.CompletePost, observation: daily_blog.recovery.GenerationObservation,
	) -> daily_blog.replication.StepReliability:
		"""Project one selected whole artifact into a bounded durable promotion event."""
		outcome = "degraded" if observation.successful_responses < observation.attempted_routes else "succeeded"
		reasons = ("partial_route_failure",) if outcome == "degraded" else ()
		return daily_blog.replication.StepReliability(
			step=f"recovery/{value.stage_key.split('/')[1]}/{rung.value}", outcome=outcome,
			attempted=observation.attempted_routes, succeeded=observation.successful_responses,
			failed=observation.attempted_routes - observation.successful_responses, reused=0,
			repaired=0, disagreements=0, best_artifact_id=artifact.artifact_id, reasons=reasons,
		)

	def _unselected_recovery_summary(
		self, value: StageRecoveryInput, rung: daily_blog.recovery.RecoveryRung,
		observation: daily_blog.recovery.GenerationObservation,
	) -> daily_blog.replication.StepReliability:
		"""Record a bounded failed recovery attempt without retaining route diagnostics."""
		reason = "partial_route_failure" if observation.successful_responses < observation.attempted_routes else "no_eligible_generation"
		return daily_blog.replication.StepReliability(
			f"recovery/{value.stage_key.split('/')[1]}/{rung.value}", "degraded",
			observation.attempted_routes, observation.successful_responses,
			observation.attempted_routes - observation.successful_responses, 0, 0, 0, "", (reason,),
		)

	def _persist_rung_reliability(
		self, value: StageRecoveryInput, facts: daily_blog.recovery.RecoveryRungReliability,
		selected_artifact: daily_blog.artifacts.CompletePost | None,
	) -> tuple[str, ...]:
		"""Persist detailed route facts before a recovery result or fault is finalized."""
		identity = value.stage_key.split("/")[1]
		values = []
		selected_promotion = False
		for summary in facts.summaries:
			namespaced = dataclasses.replace(
				summary, step=f"recovery/{identity}/{facts.rung.value}/{summary.step}",
			)
			transition: daily_blog.run_contracts.IncumbentTransition = daily_blog.run_contracts.ObserveIncumbent()
			if selected_artifact is not None and summary.step == "6.4":
				if summary.best_artifact_id != selected_artifact.artifact_id:
					raise daily_blog.recovery.RecoveryConfigurationError("Recovery promotion fact conflicts with selection.")
				transition = self._recovery_transition(value, selected_artifact)
				selected_promotion = True
			if self._persist(namespaced, transition):
				values.append(namespaced.step)
		if selected_artifact is not None and not selected_promotion:
			raise daily_blog.recovery.RecoveryConfigurationError("Recovery selection lacks a promotion fact.")
		return tuple(sorted(values))

	def _digest_steps(self, value: StageRecoveryInput) -> tuple[daily_blog.recovery.EvidenceDigestStep, ...]:
		"""Project current run summaries to the safe, core-owned digest schema."""
		stage, identity, _marker = value.stage_key.split("/")
		prefixes = (f"{stage}/{identity}/", f"recovery/{identity}/")
		steps = []
		for item in self.record.editorial_steps:
			if type(item) is not dict or not isinstance(item.get("step"), str) or not item["step"].startswith(prefixes):
				continue
			summary = daily_blog.replication.StepReliability.from_dict(item)
			reasons = tuple(reason for reason in summary.reasons if daily_blog.recovery.IDENTIFIER_RE.fullmatch(reason))
			steps.append(daily_blog.recovery.EvidenceDigestStep(
				summary.step, summary.outcome, summary.attempted, summary.succeeded, summary.failed,
				summary.reused, summary.repaired, summary.disagreements, summary.best_artifact_id, reasons,
			))
		return tuple(sorted(steps, key=lambda item: item.step_key))

	def _digest(self, value: StageRecoveryInput, fault: daily_blog.recovery.PipelineFault) -> tuple[str, str]:
		# ASVS 1.5.2 and 2.2.1: only canonical bounded data crosses the file boundary.
		packets = tuple(daily_blog.recovery.EvidenceDigestPacket(
			packet.packet_id, daily_blog.io_utils.hash_value(packet.content_dict()),
			tuple(sorted(item.evidence_id for item in packet.items)),
		) for packet in sorted(value.packets, key=lambda item: item.packet_id))
		payload, digest = daily_blog.recovery.canonical_evidence_digest(daily_blog.recovery.EvidenceDigestInput(
			value.report_date, value.stage_key, self._digest_steps(value), packets,
			value.prompt_identities, value.rubric_identities, fault,
			tuple(sorted({item.best_artifact_id for item in value.source_summaries if item.best_artifact_id})),
			(), value.allowed_repositories,
		))
		path = os.path.join(self.store.run_dir, "recovery_fault.json")
		if os.path.exists(path):
			with open(path, encoding="utf-8") as handle:
				existing = json.load(handle)
			if daily_blog.io_utils.hash_value(existing) != digest:
				raise daily_blog.recovery.RecoveryConfigurationError("Recovery digest replay diverged.")
		else:
			path = self.store.write_artifact("recovery_fault.json", payload)
		with open(path, encoding="utf-8") as handle:
			if daily_blog.io_utils.hash_value(json.load(handle)) != digest:
				raise daily_blog.recovery.RecoveryConfigurationError("Recovery digest write did not verify.")
		return path, digest

	def run(self, value: StageRecoveryInput) -> StageRecoveryResult:
		"""Persist source facts, recover only ordinary no-artifact outcomes, or fault."""
		if type(value) is not StageRecoveryInput:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery input must be exact.")
		self._validate_lineage(value)
		reused_values: list[str] = []
		for summary in value.source_summaries:
			namespaced = self._namespace(value, summary)
			if self._persist(namespaced, daily_blog.run_contracts.ObserveIncumbent()):
				reused_values.append(namespaced.step)
		reused = tuple(sorted(reused_values))
		if not isinstance(value.source_promotion, daily_blog.artifacts.NoArtifact):
			artifact = value.source_promotion.artifact
			if type(artifact) is not daily_blog.artifacts.CompletePost or not self._eligible(value, artifact):
				raise daily_blog.recovery.RecoveryConfigurationError("Stage recovery source did not produce a complete post.")
			return StageRecoveryResult(artifact, None, None, "", "", reused)
		source_observation = self._source_observation(value)
		# Source ``NoArtifact.reason`` can be a stage-level collapsed label.  The
		# coordinator deliberately derives ordinary degradation from raw result
		# facts, so a route outage cannot masquerade as successful ineligibility.
		try:
			reported_category = daily_blog.recovery.TerminalFaultCategory(value.source_promotion.reason)
		except ValueError as error:
			raise daily_blog.recovery.RecoveryConfigurationError("Stage no-artifact category is invalid.") from error
		category = (reported_category if reported_category not in daily_blog.recovery.ORDINARY_NO_ARTIFACT
			else daily_blog.recovery.classify_pipeline_fault((source_observation,)))
		if category not in daily_blog.recovery.ORDINARY_NO_ARTIFACT:
			# Preserve the raw route counts while binding a stage-level terminal
			# diagnosis to the typed fact required by ``PipelineFault``.  Ordinary
			# route outcomes remain classified solely from those raw facts.
			source_observation = dataclasses.replace(source_observation, explicit_fault=category)
			fault = daily_blog.recovery.PipelineFault(category, 0, "", "", (source_observation,))
			path, digest = self._digest(value, fault)
			return StageRecoveryResult(None, None, fault, path, digest, reused)
		if not value.paths:
			fault = daily_blog.recovery.PipelineFault(
				category, 0,
				"" if value.incumbent is None else value.incumbent.artifact.artifact_id,
				"" if value.incumbent is None else type(value.incumbent.artifact).__name__,
				(source_observation,),
			)
			path, digest = self._digest(value, fault)
			return StageRecoveryResult(None, None, fault, path, digest, reused)
		paths = tuple(daily_blog.recovery.RecoveryPath(
			adapter.rung,
			lambda adapter=adapter: adapter.invoke(self.budget, self.cache_load, self.cache_accept),
		) for adapter in value.paths)
		result = daily_blog.recovery.recover_at_outer_boundary(paths, value.incumbent,
			lambda artifact: self._eligible(value, artifact), self._promote)
		if type(result) is daily_blog.recovery.RecoveryResult:
			if not result.observations:
				return StageRecoveryResult(result.artifact, None, None, "", "", reused)
			# Recovery adapters are extensible execution boundaries.  Revalidate the
			# selected result against this run's complete Stage-6 authority before it
			# can establish an incumbent or create a durable recovery summary.
			self._validate_artifact(
				result.artifact, value, daily_blog.artifacts.CompletePost,
				require_full_packet_union=True, require_publication_eligibility=True,
			)
			rung = paths[result.depth - 1].rung
			detailed = {item.rung: item for item in result.rung_reliability}
			for facts in result.rung_reliability:
				selected = result.artifact if facts.rung is rung else None
				reused = tuple(sorted(reused + self._persist_rung_reliability(value, facts, selected)))
			if rung not in detailed:
				recovery_summary = self._recovery_summary(value, rung, result.artifact, result.observations[-1])
				transition = self._recovery_transition(value, result.artifact)
				if self._persist(recovery_summary, transition):
					reused = tuple(sorted(reused + (recovery_summary.step,)))
			return StageRecoveryResult(
				result.artifact, rung, None, "", "", reused, result.recovery_generation,
			)
		detailed = {item.rung: item for item in result.rung_reliability}
		for facts in result.rung_reliability:
			reused = tuple(sorted(reused + self._persist_rung_reliability(value, facts, None)))
		for ordinal, observation in enumerate(result.observations):
			if paths[ordinal].rung in detailed:
				continue
			recovery_summary = self._unselected_recovery_summary(value, paths[ordinal].rung, observation)
			if self._persist(recovery_summary, daily_blog.run_contracts.ObserveIncumbent()):
				reused = tuple(sorted(reused + (recovery_summary.step,)))
		observations = (source_observation,) + result.observations
		fault = dataclasses.replace(result, category=daily_blog.recovery.classify_pipeline_fault(observations), observations=observations)
		path, digest = self._digest(value, fault)
		return StageRecoveryResult(None, None, fault, path, digest, reused)

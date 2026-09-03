"""Typed Stage 6 whole-post writing, editing, review, and promotion."""

# Standard Library
import collections.abc
import dataclasses
import json
import os

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.complete_post_editor_prompts
import daily_blog.config
import daily_blog.editorial_stage_config
import daily_blog.daily_outline_workflow
import daily_blog.editorial
import daily_blog.io_utils
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.loader
import daily_blog.replication
import daily_blog.recovery
import daily_blog.routes
import daily_blog.schema
import daily_blog.stage6_context
import daily_blog.stage6_attempt_plan
import daily_blog.publication_admission
import daily_blog.stage6_recovery


RELIABILITY_SCOPE_PLANNED_ROUTES_COMPLETE = "planned_routes_complete"
RELIABILITY_SCOPE_EXTERNAL_INCUMBENT_OBSERVED = "external_incumbent_observed"
RELIABILITY_SCOPES = frozenset({
	RELIABILITY_SCOPE_PLANNED_ROUTES_COMPLETE,
	RELIABILITY_SCOPE_EXTERNAL_INCUMBENT_OBSERVED,
})


#============================================
@dataclasses.dataclass(frozen=True)
class Stage6RecoverySources:
	"""Exact Stage-5 material available to lower editorial recovery rungs."""

	repo_stories: tuple[daily_blog.artifacts.RepoStory, ...]
	repo_outlines: tuple[daily_blog.artifacts.RepoOutline, ...]
	packets: tuple[daily_blog.schema.EvidencePacket, ...]
	promoted_ranking: daily_blog.daily_outline_workflow.PromotedRanking
	strongest_story_id: str

	def __post_init__(self) -> None:
		"""Bind recovery material to one complete eligible Stage-5 evidence union."""
		if (
			type(self.repo_stories) is not tuple or type(self.repo_outlines) is not tuple
			or type(self.packets) is not tuple
			or type(self.promoted_ranking) is not daily_blog.daily_outline_workflow.PromotedRanking
			or type(self.strongest_story_id) is not str
		):
			raise RuntimeError("Stage 6 recovery sources require exact typed values.")
		if not self.repo_stories or len(self.repo_stories) != len(self.repo_outlines) or not self.packets:
			raise RuntimeError("Stage 6 recovery sources require complete repository material.")
		if any(type(item) is not daily_blog.artifacts.RepoStory for item in self.repo_stories):
			raise RuntimeError("Stage 6 recovery sources require exact RepoStory values.")
		if any(type(item) is not daily_blog.artifacts.RepoOutline for item in self.repo_outlines):
			raise RuntimeError("Stage 6 recovery sources require exact RepoOutline values.")
		if any(type(item) is not daily_blog.schema.EvidencePacket for item in self.packets):
			raise RuntimeError("Stage 6 recovery sources require exact EvidencePacket values.")
		if len({item.artifact_id for item in self.repo_stories}) != len(self.repo_stories):
			raise RuntimeError("Stage 6 recovery source story identities must be unique.")
		if len({item.artifact_id for item in self.repo_outlines}) != len(self.repo_outlines):
			raise RuntimeError("Stage 6 recovery source outline identities must be unique.")
		if len({item.packet_id for item in self.packets}) != len(self.packets):
			raise RuntimeError("Stage 6 recovery source packet identities must be unique.")
		story_by_repository = {item.repositories[0]: item for item in self.repo_stories}
		outline_by_repository = {item.repositories[0]: item for item in self.repo_outlines}
		if (
			len(story_by_repository) != len(self.repo_stories)
			or len(outline_by_repository) != len(self.repo_outlines)
			or set(story_by_repository) != set(outline_by_repository)
		):
			raise RuntimeError("Stage 6 recovery sources require one paired artifact per repository.")
		repositories = tuple(sorted(story_by_repository))
		stories = tuple(story_by_repository[item] for item in repositories)
		outlines = tuple(outline_by_repository[item] for item in repositories)
		packet_by_id = {item.packet_id: item for item in self.packets}
		expected_packet_ids: set[str] = set()
		for repository, story, outline in zip(repositories, stories, outlines, strict=True):
			if story.packet_ids != outline.packet_ids or not story.packet_ids:
				raise RuntimeError("Stage 6 recovery source pairs must share local packet provenance.")
			for packet_id in story.packet_ids:
				packet = packet_by_id.get(packet_id)
				if packet is None or {item.repository for item in packet.items} != {repository}:
					raise RuntimeError("Stage 6 recovery source packet ownership conflicts.")
				expected_packet_ids.add(packet_id)
		if expected_packet_ids != set(packet_by_id):
			raise RuntimeError("Stage 6 recovery sources contain an orphan packet.")
		packets = tuple(
			packet_by_id[packet_id]
			for repository in repositories
			for packet_id in story_by_repository[repository].packet_ids
		)
		if (
			any(item.report_date != stories[0].report_date for item in stories + outlines)
			or any(item.report_date != stories[0].report_date for item in packets)
		):
			raise RuntimeError("Stage 6 recovery source date or repository scope conflicts.")
		if any(
			not daily_blog.artifacts.evaluate_eligibility(
				item, packets, allowed_repositories=repositories,
			).eligible
			for item in stories + outlines
		):
			raise RuntimeError("Stage 6 recovery sources must be mechanically eligible.")
		if set(dict(self.promoted_ranking.scores)) != {item.content_hash for item in stories}:
			raise RuntimeError("Stage 6 promoted ranking must cover the exact recovery stories.")
		score_by_hash = dict(self.promoted_ranking.scores)
		best_score = max(score_by_hash[item.content_hash] for item in stories)
		strongest = min(
			(item for item in stories if score_by_hash[item.content_hash] == best_score),
			key=lambda item: item.artifact_id,
		)
		if self.strongest_story_id != strongest.artifact_id:
			raise RuntimeError("Stage 6 strongest recovery story conflicts with promoted ranking.")
		object.__setattr__(self, "repo_stories", stories)
		object.__setattr__(self, "repo_outlines", outlines)
		object.__setattr__(self, "packets", packets)

	@property
	def report_date(self) -> str:
		"""Expose the common report date of the authoritative source union."""
		return self.repo_stories[0].report_date

	@property
	def strongest_story(self) -> daily_blog.artifacts.RepoStory:
		"""Return the exact stable strongest repository story identity."""
		return next(item for item in self.repo_stories if item.artifact_id == self.strongest_story_id)

	#============================================
	@classmethod
	def from_stage5(
		cls,
		value: daily_blog.daily_outline_workflow.DailyOutlineInput,
		result: daily_blog.daily_outline_workflow.DailyOutlineResult,
	) -> "Stage6RecoverySources":
		"""Derive recovery provenance from the exact Stage-5 source and reviewed ranking."""
		if (
			type(value) is not daily_blog.daily_outline_workflow.DailyOutlineInput
			or type(result) is not daily_blog.daily_outline_workflow.DailyOutlineResult
			or type(result.promoted_ranking) is not daily_blog.daily_outline_workflow.PromotedRanking
		):
			raise RuntimeError("Stage 6 recovery sources require an exact promoted Stage-5 ranking.")
		score_by_hash = dict(result.promoted_ranking.scores)
		best_score = max(score_by_hash[item.content_hash] for item in value.repo_stories)
		strongest = min(
			(item for item in value.repo_stories if score_by_hash[item.content_hash] == best_score),
			key=lambda item: item.artifact_id,
		)
		return cls(
			value.repo_stories, value.repo_outlines, value.packets,
			result.promoted_ranking, strongest.artifact_id,
		)
#============================================
@dataclasses.dataclass(frozen=True)
class Stage6Input:
	"""The provenance-checked input boundary for complete-post work."""

	output_root: str
	output_path: str
	recovery_sources: Stage6RecoverySources
	publication_surface: daily_blog.publication_admission.PublicationSurface

	def __post_init__(self) -> None:
		"""Fail closed before a prompt can observe ungrounded editorial state."""
		if type(self.output_root) is not str or not os.path.isabs(self.output_root):
			raise RuntimeError("Stage 6 requires one trusted absolute output root.")
		if type(self.output_path) is not str or not os.path.isabs(self.output_path):
			raise RuntimeError("Stage 6 requires one trusted absolute output path.")
		if type(self.recovery_sources) is not Stage6RecoverySources:
			raise RuntimeError("Stage 6 requires exact recovery sources.")
		if type(self.publication_surface) is not daily_blog.publication_admission.PublicationSurface:
			raise RuntimeError("Stage 6 requires one exact publication surface.")
		if not os.path.isdir(os.path.realpath(self.output_root)):
			raise RuntimeError("Stage 6 trusted output root must exist.")
		self._validate_grounding()
		if os.path.basename(self.output_path) != "post.md":
			raise RuntimeError("Stage 6 output path must be the date-owned post.md destination.")
		if os.path.basename(os.path.dirname(self.output_path)) != self.report_date:
			raise RuntimeError("Stage 6 output path report date does not match DailyOutline.")
		self.render_context()

	@property
	def report_date(self) -> str:
		"""Expose the sole publication identity required by the frozen V4 prompt."""
		return self.daily_outline.report_date

	@property
	def daily_outline(self) -> daily_blog.artifacts.DailyOutline:
		"""Return the only promoted outline, owned by the publication surface."""
		return self.publication_surface.daily_outline

	@property
	def repo_stories(self) -> tuple[daily_blog.artifacts.RepoStory, ...]:
		"""Return the normal-generation narrative stories owned by the surface."""
		return self.publication_surface.narrative_repo_stories

	@property
	def packets(self) -> tuple[daily_blog.schema.EvidencePacket, ...]:
		"""Return the sole survivor packet union used by Stage 6 and admission."""
		return self.publication_surface.source_packets

	@property
	def evidence_context(self) -> daily_blog.schema.BoundedEvidenceContext:
		"""Return the model-visible evidence projection owned by the publication surface."""
		return self.publication_surface.evidence_context

	@property
	def prompt_context(self) -> daily_blog.stage6_context.Stage6PromptContext:
		"""Return the one bounded artifact-and-evidence view owned by the surface."""
		return self.publication_surface.stage6_prompt_context

	@property
	def context_packets(self) -> tuple[daily_blog.schema.EvidencePacket, ...]:
		"""Return the same survivor packets used by prompt context and admission."""
		return self.packets

	def _validate_grounding(self) -> None:
		"""Require artifact, packet, repository, and date consistency at the seam."""
		# ASVS 2.2.3 and 2.3.1: the surface has already bound the editorial
		# artifacts, evidence union, and repository scope.  Only the recovery
		# catalog may add facts here, and it must contain the selected sources.
		if any(item.report_date != self.report_date for item in self.packets):
			raise RuntimeError("Stage 6 packets must share the DailyOutline report date.")
		repositories: set[str] = set()
		for story in self.repo_stories:
			if story.report_date != self.report_date:
				raise RuntimeError("Stage 6 RepoStory report date does not match DailyOutline.")
			repositories.update(story.repositories)
		if repositories != set(self.publication_surface.narrative_repositories):
			raise RuntimeError("Stage 6 RepoStory repositories must exactly cover DailyOutline scope.")
		if (
			self.recovery_sources.report_date != self.report_date
			or not {item.packet_id for item in self.packets}.issubset(
				{item.packet_id for item in self.recovery_sources.packets}
			)
			or tuple(sorted(self.recovery_sources.repo_stories, key=lambda item: item.artifact_id))
			!= tuple(sorted(self.publication_surface.repo_stories, key=lambda item: item.artifact_id))
		):
			raise RuntimeError("Stage 6 recovery sources must contain the exact Stage 6 provenance.")
		probe_evidence_ids = (self.daily_outline.evidence_ids[0],)
		probe = daily_blog.artifacts.CompletePost.create(
			self.report_date, self.packets, daily_blog.artifacts.resolve_evidence_scope(
				probe_evidence_ids, self.packets, self.daily_outline.repositories,
			), "probe <!-- evidence: " + probe_evidence_ids[0] + " -->",
			probe_evidence_ids, self.report_date, self.output_path,
		)
		if "output_path_outside_root" in daily_blog.artifacts.evaluate_eligibility(
			probe, self.packets, (self.output_root,),
			self.daily_outline.repositories,
		).reasons:
			raise RuntimeError("Stage 6 output path is outside its trusted root.")

	def render_context(self) -> str:
		"""Render the one surface-owned bounded artifact-and-evidence view."""
		return self.prompt_context.render_context()


#============================================
def build_stage6_publication_surface(
	daily_outline: daily_blog.artifacts.DailyOutline,
	repo_stories: tuple[daily_blog.artifacts.RepoStory, ...],
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
	projection_limits: dict[str, int],
	*,
	survivor_stories: tuple[daily_blog.artifacts.RepoStory, ...] | None = None,
) -> daily_blog.publication_admission.PublicationSurface:
	"""Build the only survivor-scoped evidence authority Stage 6 may consume."""
	coverage_repositories = tuple(sorted({
		item.repository for packet in packets for item in packet.items
	}))
	# ASVS 2.2.1 and 2.3.1: one surface retains full coverage authority while
	# its narrative artifacts and prompt frame remain promoted-outline scoped.
	all_stories = repo_stories if survivor_stories is None else survivor_stories
	return daily_blog.publication_admission.build_surface(
		packets, coverage_repositories, projection_limits,
		(daily_outline,) + all_stories,
	)


#============================================
@dataclasses.dataclass(frozen=True)
class CompletePostRecoveryInput:
	"""One exact lower-rung source projection for independently authored Markdown."""

	stage6_input: Stage6Input
	rung: daily_blog.recovery.RecoveryRung
	evidence_context: daily_blog.schema.BoundedEvidenceContext = dataclasses.field(init=False)

	def __post_init__(self) -> None:
		"""Allow only the two Stage-6-owned whole-post recovery source forms."""
		if type(self.stage6_input) is not Stage6Input:
			raise RuntimeError("Complete-post recovery requires an exact Stage6Input.")
		if self.rung not in {
			daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION,
			daily_blog.recovery.RecoveryRung.REPOSITORY_STORY_MERGE,
		}:
			raise RuntimeError("Complete-post recovery rung is unsupported.")
		# Every recovery rung reuses the exact Stage 6 authority.  A lower path may
		# change editorial source artifacts, but it cannot select new evidence.
		object.__setattr__(
			self, "evidence_context", self.stage6_input.prompt_context.recovery_evidence_context,
		)
		self.render_context()

	@property
	def report_date(self) -> str:
		"""Expose the single date identity inherited from Stage 6."""
		return self.stage6_input.report_date

	@property
	def packets(self) -> tuple[daily_blog.schema.EvidencePacket, ...]:
		"""Return the exact authoritative packet union carried by Stage 6."""
		return self.stage6_input.packets

	@property
	def repositories(self) -> tuple[str, ...]:
		"""Return the exact target scope for the requested recovery editorial path."""
		return self.stage6_input.publication_surface.coverage_repositories

	@property
	def source_artifacts(self) -> tuple[daily_blog.artifacts.DailyOutline | daily_blog.artifacts.RepoStory, ...]:
		"""Return the immutable source artifacts without composing their prose."""
		if self.rung is daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION:
			return (self.stage6_input.publication_surface.daily_outline,)
		return self.stage6_input.publication_surface.repo_stories

	@property
	def strongest_story_within_scope(self) -> daily_blog.artifacts.RepoStory:
		"""Return the ranked fallback story without crossing the promoted outline scope.

		Recovery paths use the surface-owned full survivor catalog. The ranking
		remains recovery metadata, not a second story authority.
		"""
		stories = tuple(
			item for item in self.source_artifacts
			if type(item) is daily_blog.artifacts.RepoStory
		)
		if not stories:
			stories = tuple(
			item for item in self.stage6_input.publication_surface.repo_stories
			)
		scores = dict(self.stage6_input.recovery_sources.promoted_ranking.scores)
		best_score = max(scores[item.content_hash] for item in stories)
		return min(
			(item for item in stories if scores[item.content_hash] == best_score),
			key=lambda item: item.artifact_id,
		)

	def render_context(self) -> str:
		"""Render one lower path from the surface-owned bounded source authority."""
		return self.stage6_input.prompt_context.render_recovery_context(self.rung)
#============================================
@dataclasses.dataclass(frozen=True)
class Stage6BatchObservation:
	"""One batch's final admitted work and exact route observations."""

	materialization: daily_blog.stage6_attempt_plan.MaterializedStage6AttemptPlan
	results: tuple[daily_blog.agents.AgentResult, ...]

	def __post_init__(self) -> None:
		"""Require canonical request-result coverage without synthetic attempts."""
		if type(self.materialization) is not daily_blog.stage6_attempt_plan.MaterializedStage6AttemptPlan:
			raise RuntimeError("Stage 6 batch observation requires an exact materialization.")
		if type(self.results) is not tuple or any(type(item) is not daily_blog.agents.AgentResult for item in self.results):
			raise RuntimeError("Stage 6 batch observation requires exact agent results.")
		if tuple(item.request_id for item in self.results) != self.materialization.semantic_identities:
			raise RuntimeError("Stage 6 batch observations must match materialized slots in canonical order.")


#============================================
@dataclasses.dataclass(frozen=True, kw_only=True)
class Stage6Result:
	"""The promotion plus independently inspectable Stage 6 observations."""

	promotion: (daily_blog.artifacts.SelectedPeer | daily_blog.artifacts.PreservedArtifact
		| daily_blog.artifacts.DegradedPromotion | daily_blog.artifacts.NoArtifact)
	generation: daily_blog.replication.ReplicationResult
	review: daily_blog.replication.CandidateSetReviewResult
	reliability: daily_blog.replication.StepReliability
	editing: daily_blog.replication.ReplicationResult
	step_reliability: tuple[daily_blog.replication.StepReliability, ...]
	recovery_generation: daily_blog.replication.ReplicationResult | None = None
	primary_observations: tuple["Stage6BatchObservation", ...] = ()
	recovery_observations: tuple["Stage6BatchObservation", ...] = ()
	reliability_scope: str = RELIABILITY_SCOPE_EXTERNAL_INCUMBENT_OBSERVED

	def __post_init__(self) -> None:
		"""Validate every independently recorded Stage 6 observation."""
		if type(self.editing) is not daily_blog.replication.ReplicationResult:
			raise RuntimeError("Stage 6 editing observation is invalid.")
		if any(type(item) is not daily_blog.replication.StepReliability for item in self.step_reliability):
			raise RuntimeError("Stage 6 step reliability is invalid.")
		if (type(self.primary_observations) is not tuple
			or any(type(item) is not Stage6BatchObservation for item in self.primary_observations)):
			raise RuntimeError("Stage 6 primary execution observation is invalid.")
		if (type(self.recovery_observations) is not tuple
			or any(type(item) is not Stage6BatchObservation for item in self.recovery_observations)):
			raise RuntimeError("Stage 6 recovery execution observation is invalid.")
		if self.reliability_scope not in RELIABILITY_SCOPES:
			raise RuntimeError("Stage 6 reliability scope is invalid.")
		if self.artifact is None:
			self._validate_primary_no_artifact()
		if self.recovery_generation is not None:
			if (
				type(self.recovery_generation) is not daily_blog.replication.ReplicationResult
				or self.recovery_generation.expected_type is not daily_blog.artifacts.CompletePost
				or not self.recovery_observations
			):
				raise RuntimeError("Stage 6 recovery generation observation is invalid.")
			if (
				self.artifact is None
				or self.artifact not in self.recovery_generation.eligible
			):
				raise RuntimeError(
					"Stage 6 recovery generation must contain the exact promoted artifact."
				)

	#============================================
	def _validate_primary_no_artifact(self) -> None:
		"""Bind an exhausted primary stage to its real writer-route observations."""
		if (
			type(self.promotion) is not daily_blog.artifacts.NoArtifact
			or type(self.generation) is not daily_blog.replication.ReplicationResult
			or self.generation.expected_type is not daily_blog.artifacts.CompletePost
			or not self.generation.candidates
		):
			raise RuntimeError("Stage 6 no-artifact result requires primary writer observations.")
		writer_summaries = tuple(item for item in self.step_reliability if item.step == "6.1")
		if len(writer_summaries) != 1:
			raise RuntimeError("Stage 6 no-artifact result requires one writer summary.")
		writer_summary = writer_summaries[0]
		writer_summary.validate()
		eligible_ids: set[str] = set()
		for candidate in self.generation.candidates:
			if (
				type(candidate) is not daily_blog.replication.ReplicatedCandidate
				or type(candidate.request) is not daily_blog.agents.RouteRequest
				or type(candidate.result) is not daily_blog.agents.AgentResult
				or (candidate.artifact is None) != (candidate.eligibility is None)
				or (
					candidate.artifact is not None
					and type(candidate.artifact) is not daily_blog.artifacts.CompletePost
				)
				or (
					candidate.eligibility is not None
					and type(candidate.eligibility) is not daily_blog.artifacts.EligibilityResult
				)
			):
				raise RuntimeError("Stage 6 no-artifact writer candidate is invalid.")
			if candidate.eligibility is not None and candidate.eligibility.eligible:
				eligible_ids.add(candidate.artifact.artifact_id)
		attempted = len(self.generation.candidates)
		succeeded = len(eligible_ids)
		if (
			writer_summary.attempted != attempted
			or writer_summary.succeeded != succeeded
			or writer_summary.failed != attempted - succeeded
			or writer_summary.best_artifact_id
			or eligible_ids
		):
			raise RuntimeError("Stage 6 no-artifact writer summary conflicts with generation facts.")
		# ASVS 2.2.1 and 2.3.1: make the terminal category derive from the
		# exact route observations before a lower editorial path can begin.
		observation = daily_blog.recovery.GenerationObservation(
			"stage6_writer", attempted,
			sum(candidate.result.ok for candidate in self.generation.candidates), (),
		)
		daily_blog.recovery.no_artifact_category(self.promotion, observation)

	@property
	def artifact(self) -> daily_blog.artifacts.CompletePost | None:
		"""Return the exact-rung promoted artifact, if editorial work produced one."""
		return None if isinstance(self.promotion, daily_blog.artifacts.NoArtifact) else self.promotion.artifact
def _eligible(value: Stage6Input, item: daily_blog.artifacts.EditorialArtifact) -> daily_blog.artifacts.EligibilityResult:
	"""Apply shared mechanical eligibility to a Stage 6 complete post."""
	if type(item) is not daily_blog.artifacts.CompletePost:
		return daily_blog.artifacts.EligibilityResult(False, ("invalid_machine_metadata",))
	return daily_blog.publication_admission.complete_post_eligibility(
		item, value.publication_surface, value.output_root,
	)


#============================================
def _post(value: Stage6Input, result: daily_blog.agents.AgentResult) -> daily_blog.artifacts.CompletePost:
	"""Parse one post and close machine-owned metadata and missing provenance syntax."""
	content = result.text.rstrip() + "\n"
	if not content.startswith("---"):
		content = f"---\ndate: {value.report_date}\n---\n" + content
	content, evidence_ids = daily_blog.artifacts.ensure_evidence_references(
		content, value.publication_surface.allowed_evidence_ids,
	)
	try:
		repositories = daily_blog.artifacts.resolve_evidence_scope(
			evidence_ids, value.packets, value.daily_outline.repositories,
		)
	except daily_blog.artifacts.EvidenceScopeError as error:
		raise daily_blog.agents.RepairableStructuredOutput(
			"Complete post evidence scope is invalid."
		) from error
	return daily_blog.artifacts.CompletePost.create(value.report_date, value.packets,
		repositories, content, evidence_ids, value.report_date, value.output_path,
		daily_blog.artifacts.referenced_image_paths(content))


#============================================
def _unique(items: collections.abc.Iterable[daily_blog.artifacts.CompletePost]) -> tuple[daily_blog.artifacts.CompletePost, ...]:
	"""Return identity-sorted distinct same-rung candidates."""
	return tuple(sorted({item.artifact_id: item for item in items}.values(),
		key=lambda item: (item.content_hash, item.artifact_id)))


#============================================
def _anonymous_posts(
	value: Stage6Input,
	items: collections.abc.Iterable[daily_blog.artifacts.CompletePost],
) -> str:
	"""Render anonymous mechanically grounded drafts for an editor."""
	candidates = [
		{
			"alias": "candidate-" + str(index + 1),
			"content": item.content,
		}
		for index, item in enumerate(_unique(items))
	]
	rendered = json.dumps({"candidates": candidates}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
	if len(rendered) > daily_blog.complete_post_editor_prompts.MAX_CANDIDATE_POSTS_CHARS:
		raise RuntimeError("Stage 6 editor candidate context exceeds its bounded limit.")
	return rendered
#============================================
def _aggregate(steps: tuple[daily_blog.replication.StepReliability, ...]) -> daily_blog.replication.StepReliability:
	"""Summarize the current Stage 6 observations for publication consumers."""
	reasons = tuple(sorted({reason for item in steps for reason in item.reasons}))
	rejection_counts: dict[str, int] = {}
	for item in steps:
		for code, count in item.rejection_counts:
			rejection_counts[code] = rejection_counts.get(code, 0) + count
	return daily_blog.replication.StepReliability("stage6_complete_post", "degraded" if reasons else "succeeded",
		sum(item.attempted for item in steps[:3]), sum(item.succeeded for item in steps[:3]),
		sum(item.failed for item in steps[:3]), sum(item.reused for item in steps[:3]),
		sum(item.repaired for item in steps[:3]), steps[2].disagreements, steps[3].best_artifact_id,
		reasons, tuple(sorted(rejection_counts.items())))


#============================================
def _recovery_post(
	value: CompletePostRecoveryInput,
	result: daily_blog.agents.AgentResult,
) -> daily_blog.artifacts.CompletePost:
	"""Parse one recovery post and close machine-owned packaging."""
	content = result.text.rstrip() + "\n"
	if not content.startswith("---"):
		content = f"---\ndate: {value.report_date}\n---\n" + content
	content, evidence_ids = daily_blog.artifacts.ensure_evidence_references(
		content,
		tuple(sorted(
			item.evidence_id
			for item in value.stage6_input.publication_surface.packet.items
		)),
	)
	try:
		repositories = daily_blog.artifacts.resolve_evidence_scope(
			evidence_ids, value.packets, value.repositories,
		)
	except daily_blog.artifacts.EvidenceScopeError as error:
		raise daily_blog.agents.RepairableStructuredOutput(
			"Recovery complete post evidence scope is invalid."
		) from error
	return daily_blog.artifacts.CompletePost.create(
		value.report_date, value.packets, repositories, content, evidence_ids,
		value.report_date, value.stage6_input.output_path,
		daily_blog.artifacts.referenced_image_paths(content),
	)


#============================================
def _recover_complete_post(
	value: CompletePostRecoveryInput,
	run_id: str,
	config: daily_blog.config.DailyBlogConfig,
	budget: daily_blog.agents.RouteBudget,
	runner: object | None,
	contract: daily_blog.prompt_registry.definitions.EditorialContract | None,
	selection: daily_blog.prompt_registry.definitions.ExampleSelection | None,
	snapshot: daily_blog.editorial.PromptContractSnapshot | None,
	cache_load: collections.abc.Callable[
		[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None,
	] | None,
	cache_accept: collections.abc.Callable[
		[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None,
	] | None,
	plan: daily_blog.stage6_attempt_plan.Stage6AttemptPlan | None = None,
) -> daily_blog.recovery.RecoveryAttempt:
	"""Delegate the bounded recovery topology while retaining the public API."""
	if type(value) is not CompletePostRecoveryInput or type(run_id) is not str or not run_id:
		raise RuntimeError("Stage 6 recovery requires exact input and a nonempty run identity.")
	if type(config.complete_post) is not daily_blog.editorial_stage_config.CompletePostConfig:
		raise RuntimeError("Stage 6 recovery requires exact complete-post configuration.")
	if type(budget) is not daily_blog.agents.RouteBudget:
		raise RuntimeError("Stage 6 recovery requires the coordinator-owned RouteBudget.")
	recovery_plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(
		config.complete_post.stage6_attempt_policy,
	) if plan is None else plan
	return daily_blog.stage6_recovery.recover_complete_post(
		value, run_id, config, budget, runner, contract, selection, snapshot,
		cache_load, cache_accept, _recovery_post, _anonymous_posts, recovery_plan,
	)


#============================================
def recover_daily_outline_expansion(
	value: CompletePostRecoveryInput,
	run_id: str,
	config: daily_blog.config.DailyBlogConfig,
	budget: daily_blog.agents.RouteBudget,
	runner: object | None = None,
	contract: daily_blog.prompt_registry.definitions.EditorialContract | None = None,
	selection: daily_blog.prompt_registry.definitions.ExampleSelection | None = None,
	snapshot: daily_blog.editorial.PromptContractSnapshot | None = None,
	cache_load: collections.abc.Callable[
		[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None,
	] | None = None,
	cache_accept: collections.abc.Callable[
		[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None,
	] | None = None,
	plan: daily_blog.stage6_attempt_plan.Stage6AttemptPlan | None = None,
) -> daily_blog.recovery.RecoveryAttempt:
	"""Expand the promoted daily outline through one independently authored whole post."""
	if (
		type(value) is not CompletePostRecoveryInput
		or value.rung is not daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION
	):
		raise RuntimeError("Daily-outline recovery requires its exact recovery input.")
	return _recover_complete_post(
		value, run_id, config, budget, runner, contract, selection, snapshot,
		cache_load, cache_accept, plan,
	)


#============================================
def recover_repository_story_merge(
	value: CompletePostRecoveryInput,
	run_id: str,
	config: daily_blog.config.DailyBlogConfig,
	budget: daily_blog.agents.RouteBudget,
	runner: object | None = None,
	contract: daily_blog.prompt_registry.definitions.EditorialContract | None = None,
	selection: daily_blog.prompt_registry.definitions.ExampleSelection | None = None,
	snapshot: daily_blog.editorial.PromptContractSnapshot | None = None,
	cache_load: collections.abc.Callable[
		[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None,
	] | None = None,
	cache_accept: collections.abc.Callable[
		[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None,
	] | None = None,
	plan: daily_blog.stage6_attempt_plan.Stage6AttemptPlan | None = None,
) -> daily_blog.recovery.RecoveryAttempt:
	"""Merge eligible repository stories through one independently authored whole post."""
	if (
		type(value) is not CompletePostRecoveryInput
		or value.rung is not daily_blog.recovery.RecoveryRung.REPOSITORY_STORY_MERGE
	):
		raise RuntimeError("Repository-story recovery requires its exact recovery input.")
	return _recover_complete_post(
		value, run_id, config, budget, runner, contract, selection, snapshot,
		cache_load, cache_accept, plan,
	)


#============================================
def run_stage6(value: Stage6Input, run_id: str, config: daily_blog.config.DailyBlogConfig,
	budget: daily_blog.agents.RouteBudget, runner: object | None = None,
	contract: daily_blog.prompt_registry.definitions.EditorialContract | None = None,
	selection: daily_blog.prompt_registry.definitions.ExampleSelection | None = None,
	snapshot: daily_blog.editorial.PromptContractSnapshot | None = None,
	cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None = None,
	cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None = None,
	incumbent: daily_blog.artifacts.CompletePost | None = None) -> Stage6Result:
	"""Run 6.1 writers, 6.2 editors, 6.3 review, and 6.4 promotion."""
	if type(value) is not Stage6Input or type(run_id) is not str or not run_id:
		raise RuntimeError("Stage 6 requires exact input and a nonempty run identity.")
	if type(config.complete_post) is not daily_blog.editorial_stage_config.CompletePostConfig:
		raise RuntimeError("Stage 6 requires exact complete-post configuration.")
	if type(budget) is not daily_blog.agents.RouteBudget:
		raise RuntimeError("Stage 6 requires the coordinator-owned RouteBudget.")
	if incumbent is not None and type(incumbent) is not daily_blog.artifacts.CompletePost:
		raise RuntimeError("Stage 6 incumbent must be an exact CompletePost.")
	if incumbent is not None and not _eligible(value, incumbent).eligible:
		raise RuntimeError("Stage 6 incumbent is not mechanically eligible.")
	resolved = daily_blog.editorial.resolve_snapshot(contract, selection, snapshot)
	templates = daily_blog.editorial.validate_prompt_templates(snapshot=resolved)
	editor_prompt_set = daily_blog.prompt_registry.loader.load_prompt_set(
		daily_blog.prompt_registry.definitions.COMPLETE_POST_EDITOR_PROMPT_SET,
	)
	route_runner = runner if runner is not None else daily_blog.routes.CommandRouteRunner()
	# The primary runner imports this facade after all Stage 6 types exist.
	from daily_blog import stage6_primary
	return stage6_primary.run_primary_batches(
		value, run_id, config, budget, route_runner, resolved, templates,
		editor_prompt_set, cache_load, cache_accept, incumbent,
	)

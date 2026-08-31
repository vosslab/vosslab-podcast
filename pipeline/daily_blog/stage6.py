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
import daily_blog.projection
import daily_blog.replication
import daily_blog.recovery
import daily_blog.routes
import daily_blog.schema
import daily_blog.stage6_context
import daily_blog.publication_admission
import daily_blog.stage6_recovery


MAX_STAGE6_CONTEXT_CHARS = 60000
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

	daily_outline: daily_blog.artifacts.DailyOutline
	repo_stories: tuple[daily_blog.artifacts.RepoStory, ...]
	packets: tuple[daily_blog.schema.EvidencePacket, ...]
	output_root: str
	output_path: str
	recovery_sources: Stage6RecoverySources
	evidence_context: daily_blog.schema.BoundedEvidenceContext
	publication_surface: daily_blog.publication_admission.PublicationSurface = dataclasses.field(init=False)

	def __post_init__(self) -> None:
		"""Fail closed before a prompt can observe ungrounded editorial state."""
		if type(self.daily_outline) is not daily_blog.artifacts.DailyOutline:
			raise RuntimeError("Stage 6 requires an exact DailyOutline.")
		if type(self.repo_stories) is not tuple or not self.repo_stories:
			raise RuntimeError("Stage 6 requires a nonempty promoted RepoStory tuple.")
		if any(type(item) is not daily_blog.artifacts.RepoStory for item in self.repo_stories):
			raise RuntimeError("Stage 6 requires exact RepoStory values.")
		story_ids = tuple(item.artifact_id for item in self.repo_stories)
		if story_ids != tuple(sorted(story_ids)) or len(set(story_ids)) != len(story_ids):
			raise RuntimeError("Stage 6 RepoStory values must be identity-sorted and unique.")
		if type(self.packets) is not tuple or not self.packets or any(
			type(item) is not daily_blog.schema.EvidencePacket for item in self.packets
		):
			raise RuntimeError("Stage 6 requires authoritative EvidencePacket values.")
		packet_ids = tuple(item.packet_id for item in self.packets)
		if packet_ids != tuple(sorted(packet_ids)) or len(set(packet_ids)) != len(packet_ids):
			raise RuntimeError("Stage 6 EvidencePacket values must be identity-sorted and unique.")
		if type(self.output_root) is not str or not os.path.isabs(self.output_root):
			raise RuntimeError("Stage 6 requires one trusted absolute output root.")
		if type(self.output_path) is not str or not os.path.isabs(self.output_path):
			raise RuntimeError("Stage 6 requires one trusted absolute output path.")
		if type(self.recovery_sources) is not Stage6RecoverySources:
			raise RuntimeError("Stage 6 requires exact recovery sources.")
		if type(self.evidence_context) is not daily_blog.schema.BoundedEvidenceContext:
			raise RuntimeError("Stage 6 requires one exact bounded evidence context.")
		if not os.path.isdir(os.path.realpath(self.output_root)):
			raise RuntimeError("Stage 6 trusted output root must exist.")
		self._validate_grounding()
		daily_blog.projection.validate_bounded_evidence_context(
			self.context_packets, self.evidence_context,
		)
		object.__setattr__(self, "publication_surface", daily_blog.publication_admission.build_surface(
			self.context_packets, self.daily_outline.repositories,
			dict(self.evidence_context.projection_limits),
		))
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
	def context_packets(self) -> tuple[daily_blog.schema.EvidencePacket, ...]:
		"""Return selected-scope packets exposed to the Stage 6 model frame only."""
		scope = frozenset(self.daily_outline.repositories)
		packets = tuple(
			packet for packet in self.packets
			if {item.repository for item in packet.items}.issubset(scope)
		)
		if not packets:
			raise RuntimeError("Stage 6 selected scope has no authoritative evidence packets.")
		return packets

	def _validate_grounding(self) -> None:
		"""Require artifact, packet, repository, and date consistency at the seam."""
		if not daily_blog.artifacts.evaluate_eligibility(
			self.daily_outline, self.packets,
			allowed_repositories=self.daily_outline.repositories,
		).eligible:
			raise RuntimeError("Stage 6 DailyOutline is not mechanically eligible.")
		if any(item.report_date != self.report_date for item in self.packets):
			raise RuntimeError("Stage 6 packets must share the DailyOutline report date.")
		repositories: set[str] = set()
		for story in self.repo_stories:
			if not daily_blog.artifacts.evaluate_eligibility(
				story, self.packets,
				allowed_repositories=self.daily_outline.repositories,
			).eligible:
				raise RuntimeError("Stage 6 RepoStory is not mechanically eligible.")
			if story.report_date != self.report_date:
				raise RuntimeError("Stage 6 RepoStory report date does not match DailyOutline.")
			repositories.update(story.repositories)
		if repositories != set(self.daily_outline.repositories):
			raise RuntimeError("Stage 6 RepoStory repositories must exactly cover DailyOutline scope.")
		if (
			self.recovery_sources.report_date != self.report_date
			or {item.packet_id for item in self.recovery_sources.packets}
			!= {item.packet_id for item in self.packets}
			or any(
				story.artifact_id not in {item.artifact_id for item in self.recovery_sources.repo_stories}
				for story in self.repo_stories
			)
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
		"""Render full editorial state plus an exact bounded evidence projection."""
		value = daily_blog.stage6_context.stage6_frame(self.daily_outline, self.repo_stories, {})
		available = MAX_STAGE6_CONTEXT_CHARS - len(daily_blog.stage6_context.canonical_context(value)) + 2
		if self.evidence_context.context_chars > available:
			raise RuntimeError("Stage 6 bounded evidence cap exceeds its complete frame.")
		value["evidence"] = json.loads(
			self.evidence_context.render_context(self.evidence_context.context_chars),
		)
		context = daily_blog.stage6_context.canonical_context(value)
		if len(context) > MAX_STAGE6_CONTEXT_CHARS:
			raise RuntimeError("Stage 6 typed evidence context exceeds its bounded limit.")
		return context
def build_stage6_evidence_context(
	daily_outline: daily_blog.artifacts.DailyOutline,
	repo_stories: tuple[daily_blog.artifacts.RepoStory, ...],
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
	projection_limits: dict[str, int],
) -> daily_blog.schema.BoundedEvidenceContext:
	"""Build a Stage-6-specific exact context within its complete prompt frame."""
	return daily_blog.stage6_context.build_stage6_evidence_context(
		daily_outline, repo_stories, packets, projection_limits,
	)
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
		context = daily_blog.stage6_context.build_recovery_evidence_context(
			self.rung, self._context_packets, self.source_artifacts,
			dict(self.stage6_input.evidence_context.projection_limits),
		)
		daily_blog.projection.validate_bounded_evidence_context(self._context_packets, context)
		object.__setattr__(self, "evidence_context", context)
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
		if self.rung is daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION:
			return self.stage6_input.daily_outline.repositories
		return tuple(
			item.repositories[0]
			for item in self.stage6_input.recovery_sources.repo_stories
			if item.repositories[0] in self.stage6_input.daily_outline.repositories
		)

	@property
	def source_artifacts(self) -> tuple[daily_blog.artifacts.DailyOutline | daily_blog.artifacts.RepoStory, ...]:
		"""Return the immutable source artifacts without composing their prose."""
		if self.rung is daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION:
			return (self.stage6_input.daily_outline,)
		return tuple(
			item for item in self.stage6_input.recovery_sources.repo_stories
			if item.repositories[0] in self.stage6_input.daily_outline.repositories
		)

	@property
	def strongest_story_within_scope(self) -> daily_blog.artifacts.RepoStory:
		"""Return the ranked fallback story without crossing the promoted outline scope.

		The full Stage-5 strongest story remains retained on recovery_sources for
		terminal provenance; a recovery path may only expose selected repositories.
		"""
		stories = tuple(
			item for item in self.source_artifacts
			if type(item) is daily_blog.artifacts.RepoStory
		)
		if not stories:
			stories = tuple(
				item for item in self.stage6_input.recovery_sources.repo_stories
				if item.repositories[0] in self.repositories
			)
		scores = dict(self.stage6_input.recovery_sources.promoted_ranking.scores)
		best_score = max(scores[item.content_hash] for item in stories)
		return min(
			(item for item in stories if scores[item.content_hash] == best_score),
			key=lambda item: item.artifact_id,
		)

	@property
	def _context_packets(self) -> tuple[daily_blog.schema.EvidencePacket, ...]:
		"""Keep lower-rung prompt/cache evidence within its trusted repository ceiling."""
		scope = frozenset(self.repositories)
		return tuple(
			packet for packet in self.packets
			if {item.repository for item in packet.items}.issubset(scope)
		)

	def render_context(self) -> str:
		"""Render one scoped source frame plus exact bounded source slices."""
		value = daily_blog.stage6_context.recovery_frame(self.rung, self.source_artifacts, {})
		value["evidence"] = json.loads(
			self.evidence_context.render_context(self.evidence_context.context_chars),
		)
		context = daily_blog.stage6_context.canonical_context(value)
		if len(context) > MAX_STAGE6_CONTEXT_CHARS:
			raise RuntimeError("Stage 6 recovery evidence context exceeds its bounded limit.")
		return context
#============================================
@dataclasses.dataclass(frozen=True, kw_only=True)
class Stage6Result:
	"""The promotion plus independently inspectable Stage 6 observations."""

	promotion: (daily_blog.artifacts.SelectedPeer | daily_blog.artifacts.PreservedArtifact
		| daily_blog.artifacts.DegradedPromotion | daily_blog.artifacts.NoArtifact)
	generation: daily_blog.replication.ReplicationResult
	review: daily_blog.replication.ReviewResult
	reliability: daily_blog.replication.StepReliability
	editing: daily_blog.replication.ReplicationResult
	step_reliability: tuple[daily_blog.replication.StepReliability, ...]
	recovery_generation: daily_blog.replication.ReplicationResult | None = None

	def __post_init__(self) -> None:
		"""Validate every independently recorded Stage 6 observation."""
		if type(self.editing) is not daily_blog.replication.ReplicationResult:
			raise RuntimeError("Stage 6 editing observation is invalid.")
		if any(type(item) is not daily_blog.replication.StepReliability for item in self.step_reliability):
			raise RuntimeError("Stage 6 step reliability is invalid.")
		if self.artifact is None:
			self._validate_primary_no_artifact()
		if self.recovery_generation is not None:
			if (
				type(self.recovery_generation) is not daily_blog.replication.ReplicationResult
				or self.recovery_generation.expected_type is not daily_blog.artifacts.CompletePost
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
	"""Parse one whole post response and close its machine-owned front matter."""
	content = result.text.rstrip() + "\n"
	if not content.startswith("---"):
		content = f"---\ndate: {value.report_date}\n---\n" + content
	evidence_ids = daily_blog.artifacts.evidence_references(content)
	if not evidence_ids:
		raise daily_blog.agents.RepairableStructuredOutput("Complete post has no evidence reference.")
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
	"""Render anonymous grounded drafts with bounded deterministic repair facts."""
	candidates = [{
		"alias": "candidate-" + str(index + 1),
		"content": item.content,
		"validation_issues": daily_blog.candidates.validate_complete_post_body(
			item.content, value.publication_surface.packet,
			value.publication_surface.projection,
		),
	} for index, item in enumerate(_unique(items))]
	rendered = json.dumps({"candidates": candidates}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
	if len(rendered) > daily_blog.complete_post_editor_prompts.MAX_CANDIDATE_POSTS_CHARS:
		raise RuntimeError("Stage 6 editor candidate context exceeds its bounded limit.")
	return rendered


#============================================
def _request(value: Stage6Input, run_id: str, step: str, role: str, ordinal: str,
	route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, config: daily_blog.editorial_stage_config.CompletePostConfig,
	working_directory: str, contract_version: str, editor_identity: dict[str, object], input_ids: tuple[str, ...] = (),
	assignment: daily_blog.replication.ReviewAssignment | None = None, repair_of: str = "") -> daily_blog.agents.RouteRequest:
	"""Build one cache-safe request binding role, inputs, V4, and editor identities."""
	assignment_data = {} if assignment is None else {"pair_index": assignment.pair_index,
		"reviewer_index": assignment.reviewer_index, "display_order": assignment.display_order}
	logical_input = {"report_date": value.report_date,
		"context": value.render_context(), "output_path": value.output_path, "step": step, "role": role,
		"ordinal": ordinal, "input_ids": list(input_ids), "editor_prompt": editor_identity,
		"model_context_id": value.evidence_context.model_context_id,
		"v4_contract": contract_version, "assignment": assignment_data}
	logical_input.pop("output_path")
	cache_input_hash = daily_blog.io_utils.hash_value(logical_input)
	input_hash = daily_blog.io_utils.hash_value({"run_id": run_id, "logical": logical_input,
		"output_path": value.output_path})
	return daily_blog.agents.RouteRequest(
		request_id=f"stage6_{step}_{role}_{ordinal}_{cache_input_hash[:12]}", step="stage6_" + step,
		route=route, prompt=prompt, working_directory=working_directory, role=role,
		retry_attempts=config.route_retry_attempts, maximum_parallel_calls=config.maximum_parallel_calls,
		repair_of=repair_of, input_hash=input_hash, contract_version=contract_version,
		cache_input_hash=cache_input_hash,
	)


#============================================
def _generation_reliability(step: str, result: daily_blog.replication.ReplicationResult,
	reasons: collections.abc.Iterable[str] = ()) -> daily_blog.replication.StepReliability:
	"""Summarize exactly one generation mechanism."""
	values = result.candidates
	all_reasons = set(reasons) | {item.failure for item in values if item.failure}
	if any(item.result.ok and (item.eligibility is None or not item.eligibility.eligible) for item in values):
		all_reasons.add("ineligible_generation")
	succeeded = sum(item.result.ok and item.eligibility is not None and item.eligibility.eligible for item in values)
	return daily_blog.replication.StepReliability(step, "degraded" if all_reasons else "succeeded",
		len(values), succeeded, len(values) - succeeded, sum(item.result.resumed and item.result.ok for item in values),
		0, 0, "", tuple(sorted(all_reasons)))


#============================================
def _disagreements(votes: collections.abc.Iterable[daily_blog.replication.ReviewVote]) -> int:
	"""Count candidate-pair conflicts without retaining any reviewer prose."""
	pairs: dict[tuple[str, str], set[str]] = {}
	for vote in votes:
		if vote.status == "succeeded":
			pairs.setdefault(tuple(sorted((vote.first_artifact_id, vote.second_artifact_id))), set()).add(vote.winner_artifact_id)
	return sum(len(winners) > 1 for winners in pairs.values())


#============================================
def _review_reliability(review: daily_blog.replication.ReviewResult, promotion: object,
	reasons: collections.abc.Iterable[str] = ()) -> daily_blog.replication.StepReliability:
	"""Summarize actual review routes, including repair success and disagreements."""
	votes, disagreements = review.votes, _disagreements(review.votes)
	all_reasons = set(reasons) | set(daily_blog.replication.review_reasons(votes, disagreements))
	best = "" if isinstance(promotion, daily_blog.artifacts.NoArtifact) else promotion.artifact.artifact_id
	return daily_blog.replication.StepReliability("6.3", "degraded" if all_reasons else "succeeded",
		len(votes), sum(item.status == "succeeded" for item in votes), sum(item.status == "failed" for item in votes),
		0, sum(item.repaired and item.status == "succeeded" for item in votes), disagreements, best,
		tuple(sorted(all_reasons)))


#============================================
def _promotion_reliability(promotion: object, votes: collections.abc.Iterable[daily_blog.replication.ReviewVote]) -> daily_blog.replication.StepReliability:
	"""Record deterministic selection separately from route observations."""
	if isinstance(promotion, daily_blog.artifacts.NoArtifact):
		reasons, best = (promotion.reason,), ""
	elif isinstance(promotion, daily_blog.artifacts.DegradedPromotion):
		reasons, best = promotion.reasons, promotion.artifact.artifact_id
	else:
		reasons, best = (), promotion.artifact.artifact_id
	return daily_blog.replication.StepReliability("6.4", "degraded" if reasons else "succeeded", 1, 1, 0,
		0, 0, _disagreements(votes), best, reasons)


#============================================
def _aggregate(steps: tuple[daily_blog.replication.StepReliability, ...]) -> daily_blog.replication.StepReliability:
	"""Summarize the current Stage 6 observations for publication consumers."""
	reasons = tuple(sorted({reason for item in steps for reason in item.reasons}))
	return daily_blog.replication.StepReliability("stage6_complete_post", "degraded" if reasons else "succeeded",
		sum(item.attempted for item in steps[:3]), sum(item.succeeded for item in steps[:3]),
		sum(item.failed for item in steps[:3]), sum(item.reused for item in steps[:3]),
		sum(item.repaired for item in steps[:3]), steps[2].disagreements, steps[3].best_artifact_id, reasons)


#============================================
def _recovery_post(
	value: CompletePostRecoveryInput,
	result: daily_blog.agents.AgentResult,
) -> daily_blog.artifacts.CompletePost:
	"""Parse one independently authored recovery post and close its front matter."""
	content = result.text.rstrip() + "\n"
	if not content.startswith("---"):
		content = f"---\ndate: {value.report_date}\n---\n" + content
	evidence_ids = daily_blog.artifacts.evidence_references(content)
	if not evidence_ids:
		raise daily_blog.agents.RepairableStructuredOutput("Recovery complete post has no evidence reference.")
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
def _recovery_request(
	value: CompletePostRecoveryInput,
	run_id: str,
	config: daily_blog.config.DailyBlogConfig,
	contract_version: str,
	prompt_identity: dict[str, object],
	prompt: str,
	role: str = "recovery_author",
	ordinal: str = "1",
	input_ids: tuple[str, ...] = (),
	assignment: daily_blog.replication.ReviewAssignment | None = None,
	repair_of: str = "",
) -> daily_blog.agents.RouteRequest:
	"""Bind one lower editorial rung to its exact sources, contract, and cache identity."""
	stage = config.complete_post
	source_ids = tuple(item.content_hash for item in value.source_artifacts)
	logical_input = {
		"report_date": value.report_date,
		"rung": value.rung.value,
		"context": value.render_context(),
		"model_context_id": value.evidence_context.model_context_id,
		"source_ids": list(source_ids),
		"repositories": list(value.repositories),
		"prompt_contract": prompt_identity,
		"v4_contract": contract_version,
		"role": role,
		"ordinal": ordinal,
		"input_ids": list(input_ids),
		"assignment": {} if assignment is None else {
			"pair_index": assignment.pair_index,
			"reviewer_index": assignment.reviewer_index,
			"display_order": assignment.display_order,
		},
	}
	cache_input_hash = daily_blog.io_utils.hash_value(logical_input)
	input_hash = daily_blog.io_utils.hash_value({
		"run_id": run_id,
		"logical": logical_input,
		"output_path": value.stage6_input.output_path,
	})
	return daily_blog.agents.RouteRequest(
		request_id="stage6_recovery_" + value.rung.value + "_" + role + "_" + ordinal + "_" + cache_input_hash[:12],
		step="stage6_recovery_" + value.rung.value,
		route={"recovery_author": stage.writer_route, "recovery_editor": stage.editor_route,
			"recovery_reviewer": stage.reviewer_route}[role],
		prompt=prompt,
		working_directory=config.daily_blog_repository,
		role=role,
		retry_attempts=stage.route_retry_attempts,
		maximum_parallel_calls=stage.maximum_parallel_calls,
		input_hash=input_hash,
		contract_version=contract_version,
		cache_input_hash=cache_input_hash,
		repair_of=repair_of,
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
) -> daily_blog.recovery.RecoveryAttempt:
	"""Delegate the bounded recovery topology while retaining the public API."""
	if type(value) is not CompletePostRecoveryInput or type(run_id) is not str or not run_id:
		raise RuntimeError("Stage 6 recovery requires exact input and a nonempty run identity.")
	if type(config.complete_post) is not daily_blog.editorial_stage_config.CompletePostConfig:
		raise RuntimeError("Stage 6 recovery requires exact complete-post configuration.")
	if type(budget) is not daily_blog.agents.RouteBudget:
		raise RuntimeError("Stage 6 recovery requires the coordinator-owned RouteBudget.")
	return daily_blog.stage6_recovery.recover_complete_post(
		value, run_id, config, budget, runner, contract, selection, snapshot,
		cache_load, cache_accept, _recovery_post, _recovery_request, _anonymous_posts,
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
) -> daily_blog.recovery.RecoveryAttempt:
	"""Expand the promoted daily outline through one independently authored whole post."""
	if (
		type(value) is not CompletePostRecoveryInput
		or value.rung is not daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION
	):
		raise RuntimeError("Daily-outline recovery requires its exact recovery input.")
	return _recover_complete_post(
		value, run_id, config, budget, runner, contract, selection, snapshot,
		cache_load, cache_accept,
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
) -> daily_blog.recovery.RecoveryAttempt:
	"""Merge eligible repository stories through one independently authored whole post."""
	if (
		type(value) is not CompletePostRecoveryInput
		or value.rung is not daily_blog.recovery.RecoveryRung.REPOSITORY_STORY_MERGE
	):
		raise RuntimeError("Repository-story recovery requires its exact recovery input.")
	return _recover_complete_post(
		value, run_id, config, budget, runner, contract, selection, snapshot,
		cache_load, cache_accept,
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
	editor_identity = daily_blog.complete_post_editor_prompts.complete_post_editor_prompt_identity(
		editor_prompt_set,
	)
	stage = config.complete_post
	route_runner = runner if runner is not None else daily_blog.routes.CommandRouteRunner()
	logical_writer_run = "stage6-" + daily_blog.io_utils.sha256_text(value.render_context())[:24]
	writer_requests = tuple(_request(value, run_id, "6_1", "writer", str(index + 1), stage.writer_route,
		daily_blog.editorial.render_author_prompt(value, f"{logical_writer_run}-writer-{index + 1}",
			stage.prompt_limits["writer_chars"], snapshot=resolved), stage, config.daily_blog_repository, resolved.contract.prompt_version,
		editor_identity) for index in range(stage.writer_count))
	if any(len(item.prompt) > stage.prompt_limits["writer_chars"] for item in writer_requests):
		raise RuntimeError("Stage 6 writer prompt exceeds its configured limit.")
	writing = daily_blog.replication.replicate(writer_requests, route_runner, budget,
		daily_blog.artifacts.CompletePost, lambda item: _post(value, item), lambda item: _eligible(value, item),
		cache_load, cache_accept,
		lambda item: daily_blog.publication_admission.complete_post_mechanical_eligibility(
			item, value.publication_surface, value.output_root,
		))
	writer_peers = _unique(writing.eligible)
	writer_material = _unique(
		item.artifact for item in writing.candidates if item.artifact is not None
		and daily_blog.publication_admission.complete_post_mechanical_eligibility(
			item.artifact, value.publication_surface, value.output_root,
		).eligible)
	editing = daily_blog.replication.ReplicationResult(daily_blog.artifacts.CompletePost, ())
	editor_prompt_limited = False
	# Editors may refine provenance-valid drafts which missed body policy; only
	# fully eligible editor output can enter the review and promotion peer set.
	editor_source = writer_material if incumbent is None else _unique(writer_material + (incumbent,))
	if editor_source:
		candidate_json = _anonymous_posts(value, editor_source)
		editor_requests = tuple(_request(value, run_id, "6_2", "editor", str(index + 1), stage.editor_route,
			daily_blog.complete_post_editor_prompts.render_complete_post_editor_prompt(value.render_context(),
				candidate_json, "editor-" + str(index + 1), editor_prompt_set), stage, config.daily_blog_repository,
			resolved.contract.prompt_version, editor_identity, tuple(item.content_hash for item in editor_source))
			for index in range(stage.editor_count))
		if any(len(item.prompt) > stage.prompt_limits["editor_chars"] for item in editor_requests):
			editor_prompt_limited = True
		else:
			editing = daily_blog.replication.replicate(editor_requests, route_runner, budget,
				daily_blog.artifacts.CompletePost, lambda item: _post(value, item), lambda item: _eligible(value, item),
				cache_load, cache_accept, lambda item: daily_blog.publication_admission.complete_post_mechanical_eligibility(
					item, value.publication_surface, value.output_root,
				))
	editor_peers = _unique(editing.eligible)
	# Every eligible whole post is an independent peer.  Editors are an
	# additional editorial path, never a mechanical replacement for writers.
	peers = _unique(writer_peers + editor_peers)
	if incumbent is not None:
		peers = _unique(peers + (incumbent,))
	if not peers:
		category = (
			"no_eligible_generation"
			if any(item.result.ok for item in writing.candidates)
			else "route_unavailable"
		)
		promotion = daily_blog.artifacts.NoArtifact(daily_blog.artifacts.CompletePost, category)
		empty = daily_blog.replication.ReviewResult((), ())
		steps = (_generation_reliability("6.1", writing), _generation_reliability("6.2", editing, ("upstream_unavailable",)),
			_review_reliability(empty, promotion, ("upstream_unavailable",)), _promotion_reliability(promotion, ()))
		return Stage6Result(
			promotion=promotion, generation=writing, review=empty,
			reliability=_aggregate(steps), editing=editing, step_reliability=steps,
		)

	def build_work(left: daily_blog.artifacts.EditorialArtifact, right: daily_blog.artifacts.EditorialArtifact,
		assignment: daily_blog.replication.ReviewAssignment) -> daily_blog.replication.ReviewWork:
		prompt = templates["referee"].format(rubric=templates["rubric"], evidence_json=value.render_context(),
			candidate_a=left.content, candidate_b=right.content)
		if len(prompt) > stage.prompt_limits["reviewer_chars"]:
			raise RuntimeError("Stage 6 reviewer prompt exceeds its configured limit.")
		request = _request(value, run_id, "6_3", "reviewer",
			f"{assignment.pair_index}_{assignment.reviewer_index}_{assignment.display_order}", stage.reviewer_route,
			prompt, stage, config.daily_blog_repository, resolved.contract.prompt_version, editor_identity, (left.content_hash, right.content_hash), assignment)
		return daily_blog.replication.ReviewWork(request, left.artifact_id, right.artifact_id, assignment)

	def parse_winner(text: str, work: daily_blog.replication.ReviewWork) -> str:
		try:
			verdict = daily_blog.editorial.parse_referee_verdict(text, {"A", "B"})
		except daily_blog.editorial.RefereeVerdictParseError as error:
			raise daily_blog.agents.RepairableStructuredOutput(str(error)) from error
		return {"A": work.first_artifact_id, "B": work.second_artifact_id}.get(verdict["winner"], "")

	def repair(work: daily_blog.replication.ReviewWork, response: str) -> daily_blog.replication.ReviewWork:
		prompt = templates["repair"].format(response=response[:daily_blog.editorial.MAX_REFEREE_RESPONSE_CHARS])
		if len(prompt) > stage.prompt_limits["repair_chars"]:
			raise RuntimeError("Stage 6 reviewer repair prompt exceeds its configured limit.")
		request = _request(value, run_id, "6_3_repair", "reviewer_repair", work.request.request_id,
			stage.reviewer_route, prompt, stage, config.daily_blog_repository, resolved.contract.prompt_version, editor_identity,
			(daily_blog.io_utils.sha256_text(response),), work.assignment, work.request.cache_input_hash)
		return daily_blog.replication.ReviewWork(request, work.first_artifact_id, work.second_artifact_id, work.assignment)

	def salvage(text: str, work: daily_blog.replication.ReviewWork) -> str | None:
		label = daily_blog.replication.salvage_allowed_identifier(text, ("A", "B"))
		return {"A": work.first_artifact_id, "B": work.second_artifact_id}.get(label)

	review = daily_blog.replication.review(peers, daily_blog.artifacts.CompletePost, stage.reviewer_count,
		build_work, parse_winner, route_runner, budget, repair, salvage, cache_load, cache_accept)
	promotion = daily_blog.replication.promote(peers, daily_blog.artifacts.CompletePost,
		lambda item: _eligible(value, item), review.votes, incumbent)
	if not editor_peers and writer_peers and isinstance(promotion, (daily_blog.artifacts.SelectedPeer,
		daily_blog.artifacts.DegradedPromotion)):
		reasons = ("editor_unavailable",) if isinstance(promotion, daily_blog.artifacts.SelectedPeer) else tuple(sorted(set(promotion.reasons) | {"editor_unavailable"}))
		promotion = daily_blog.artifacts.DegradedPromotion(promotion.artifact, daily_blog.artifacts.CompletePost, reasons)
	editor_reasons = () if editor_peers else (("editor_prompt_limit", "editor_unavailable")
		if editor_prompt_limited else (("editor_unavailable",) if editor_source else ("upstream_unavailable",)))
	review_reasons = () if review.work else ("review_unavailable",)
	steps = (_generation_reliability("6.1", writing), _generation_reliability("6.2", editing, editor_reasons),
		_review_reliability(review, promotion, review_reasons), _promotion_reliability(promotion, review.votes))
	return Stage6Result(
		promotion=promotion, generation=writing, review=review,
		reliability=_aggregate(steps), editing=editing, step_reliability=steps,
	)

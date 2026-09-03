"""Independent editorial topology for the Stage 6 lower recovery rungs."""

# Standard Library
import collections.abc
import dataclasses

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.candidate_set_prompts
import daily_blog.complete_post_editor_prompts
import daily_blog.config
import daily_blog.editorial
import daily_blog.io_utils
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.loader
import daily_blog.publication_admission
import daily_blog.replication
import daily_blog.recovery
import daily_blog.routes
import daily_blog.stage6
import daily_blog.stage6_attempt_plan
import daily_blog.stage6_attempt_reliability
import daily_blog.stage6_execution


#============================================
RecoveryPromotion = (
	daily_blog.artifacts.SelectedPeer
	| daily_blog.artifacts.DegradedPromotion
	| daily_blog.artifacts.NoArtifact
)


#============================================
@dataclasses.dataclass(frozen=True)
class _RecoveryContext:
	"""Stable dependencies shared by one recovery-rung execution."""

	value: object
	run_id: str
	config: daily_blog.config.DailyBlogConfig
	budget: daily_blog.agents.RouteBudget
	route_runner: object
	resolved: daily_blog.editorial.PromptContractSnapshot
	templates: dict[str, str]
	editor_prompt_set: daily_blog.prompt_registry.loader.LoadedPromptSet
	cache_load: collections.abc.Callable[
		[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None,
	] | None
	cache_accept: collections.abc.Callable[
		[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None,
	] | None
	post: collections.abc.Callable[
		[object, daily_blog.agents.AgentResult], daily_blog.artifacts.CompletePost,
	]
	anonymous_posts: collections.abc.Callable[
		[object, collections.abc.Iterable[daily_blog.artifacts.CompletePost]], str,
	]
	plan: daily_blog.stage6_attempt_plan.Stage6AttemptPlan
	rendered_context: str
	rung: str

	#============================================
	def parse_post(
		self, result: daily_blog.agents.AgentResult,
	) -> daily_blog.artifacts.CompletePost:
		"""Parse one writer response through the public recovery source."""
		return self.post(self.value, result)

	#============================================
	def mechanical(
		self, item: daily_blog.artifacts.CompletePost,
	) -> daily_blog.artifacts.EligibilityResult:
		"""Apply the recovery mechanical boundary to a parsed post."""
		return daily_blog.publication_admission.complete_post_mechanical_eligibility(
			item, self.value.stage6_input.publication_surface,
			self.value.stage6_input.output_root, recovery=True,
		)

	#============================================
	def eligible(
		self, item: daily_blog.artifacts.CompletePost,
	) -> daily_blog.artifacts.EligibilityResult:
		"""Apply final recovery admission to a parsed post."""
		return daily_blog.publication_admission.complete_post_eligibility(
			item, self.value.stage6_input.publication_surface,
			self.value.stage6_input.output_root, recovery=True,
		)


#============================================
def recover_complete_post(
	value: object,
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
	post: collections.abc.Callable[
		[object, daily_blog.agents.AgentResult], daily_blog.artifacts.CompletePost,
	],
	anonymous_posts: collections.abc.Callable[
		[object, collections.abc.Iterable[daily_blog.artifacts.CompletePost]], str,
	],
	plan: daily_blog.stage6_attempt_plan.Stage6AttemptPlan,
) -> object:
	"""Execute every needed fresh batch for one exact recovery rung."""
	if type(run_id) is not str or not run_id:
		raise RuntimeError("Stage 6 recovery requires a nonempty run identity.")
	resolved = daily_blog.editorial.resolve_snapshot(contract, selection, snapshot)
	templates = daily_blog.editorial.validate_prompt_templates(snapshot=resolved)
	editor_prompt_set = daily_blog.prompt_registry.loader.load_prompt_set(
		daily_blog.prompt_registry.definitions.COMPLETE_POST_EDITOR_PROMPT_SET,
	)
	stage = config.complete_post
	canonical_plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(
		stage.stage6_attempt_policy,
	)
	if type(plan) is not daily_blog.stage6_attempt_plan.Stage6AttemptPlan or plan != canonical_plan:
		raise RuntimeError("Stage 6 recovery requires the exact current canonical attempt plan.")
	context = _RecoveryContext(
		value, run_id, config, budget,
		runner if runner is not None else daily_blog.routes.CommandRouteRunner(),
		resolved, templates, editor_prompt_set, cache_load, cache_accept, post,
		anonymous_posts, plan, value.render_context(), value.rung.value,
	)
	writer_parts: list[daily_blog.replication.ReplicationResult] = []
	editor_parts: list[daily_blog.replication.ReplicationResult] = []
	reviews: list[daily_blog.replication.CandidateSetReviewResult] = []
	observations: list["daily_blog.stage6.Stage6BatchObservation"] = []
	promotion: RecoveryPromotion | None = None
	editor_prompt_limited = False
	for batch_index in range(plan.policy.fresh_batch_count):
		writer_slots, writing, material = _run_recovery_writers(context, batch_index)
		writer_parts.append(writing)
		editor_source = material
		editing, prompt_limited = _run_recovery_editors(
			context, batch_index, writer_slots, editor_source,
		)
		editor_parts.append(editing)
		editor_prompt_limited = editor_prompt_limited or prompt_limited
		peers = _unique(tuple(writing.eligible) + tuple(editing.eligible))
		if not peers:
			observations.append(_recovery_generation_observation(
				context, batch_index, writer_slots, writing, editing,
			))
			continue
		if len(peers) == 1:
			observations.append(_recovery_generation_observation(
				context, batch_index, writer_slots, writing, editing,
			))
			promotion = daily_blog.artifacts.SelectedPeer(
				peers[0], daily_blog.artifacts.CompletePost,
			)
			break
		review, observation, promotion = _review_recovery_batch(
			context, batch_index, writer_slots, writing, editing, peers,
		)
		reviews.append(review)
		observations.append(observation)
		if not isinstance(promotion, daily_blog.artifacts.NoArtifact):
			break
	result = _finish_recovery(
		context, writer_parts, editor_parts, reviews, observations, promotion,
		editor_prompt_limited,
	)
	return result


#============================================
def _run_recovery_writers(
	context: _RecoveryContext, batch_index: int,
) -> tuple[
	tuple[daily_blog.stage6_attempt_plan.PlannedStage6Attempt, ...],
	daily_blog.replication.ReplicationResult,
	tuple[daily_blog.artifacts.CompletePost, ...],
]:
	"""Execute and mechanically admit one recovery writer batch."""
	stage = context.config.complete_post
	writer_slots = tuple(daily_blog.stage6_execution.planned_attempt(
		context.plan, context.rung, batch_index, "writer", index,
	) for index in range(1, stage.writer_count + 1))
	writer_view = context.plan.materialize(
		context.rung, batch_index,
		tuple(item.semantic_identity for item in writer_slots),
	)
	logical_run = "stage6-" + daily_blog.io_utils.sha256_text(
		context.rendered_context,
	)[:24]
	writer_requests = tuple(daily_blog.stage6_execution.build_request(
		context.value.stage6_input, context.run_id, item, writer_view,
		stage.writer_route,
		daily_blog.editorial.render_author_prompt(
			context.value,
			f"{logical_run}-{context.rung}-batch-{batch_index + 1}-writer-{item.replica_index}",
			stage.prompt_limits["writer_chars"], snapshot=context.resolved,
		), stage, context.resolved.contract.prompt_version,
		working_directory=context.config.daily_blog_repository,
	) for item in writer_slots)
	if any(len(item.prompt) > stage.prompt_limits["writer_chars"] for item in writer_requests):
		raise RuntimeError("Stage 6 recovery writer prompt exceeds its configured limit.")
	writing = daily_blog.replication.replicate(
		writer_requests, context.route_runner, context.budget,
		daily_blog.artifacts.CompletePost, context.parse_post, context.eligible,
		context.cache_load, context.cache_accept, context.mechanical,
	)
	material = _unique(
		item.artifact for item in writing.candidates
		if item.artifact is not None and context.mechanical(item.artifact).eligible
	)
	result = (writer_slots, writing, material)
	return result


#============================================
def _run_recovery_editors(
	context: _RecoveryContext,
	batch_index: int,
	writer_slots: tuple[daily_blog.stage6_attempt_plan.PlannedStage6Attempt, ...],
	editor_source: tuple[daily_blog.artifacts.CompletePost, ...],
) -> tuple[daily_blog.replication.ReplicationResult, bool]:
	"""Execute one recovery editor batch and report prompt-bound rejection."""
	editing = daily_blog.replication.ReplicationResult(
		daily_blog.artifacts.CompletePost, (),
	)
	if not editor_source:
		return editing, False
	stage = context.config.complete_post
	editor_slots = tuple(daily_blog.stage6_execution.planned_attempt(
		context.plan, context.rung, batch_index, "editor", index,
	) for index in range(1, stage.editor_count + 1))
	generation_ids = tuple(
		item.semantic_identity for item in writer_slots + editor_slots
	)
	editor_view = context.plan.materialize(
		context.rung, batch_index, generation_ids,
	)
	candidate_json = context.anonymous_posts(
		context.value.stage6_input, editor_source,
	)
	editor_requests = tuple(daily_blog.stage6_execution.build_request(
		context.value.stage6_input, context.run_id, item, editor_view,
		stage.editor_route,
		daily_blog.complete_post_editor_prompts.render_complete_post_editor_prompt(
			context.rendered_context, candidate_json,
			"editor-" + str(item.replica_index), context.editor_prompt_set,
		), stage, context.resolved.contract.prompt_version,
		tuple(candidate.content_hash for candidate in editor_source),
		working_directory=context.config.daily_blog_repository,
	) for item in editor_slots)
	if any(len(item.prompt) > stage.prompt_limits["editor_chars"] for item in editor_requests):
		return editing, True
	editing = daily_blog.replication.replicate(
		editor_requests, context.route_runner, context.budget,
		daily_blog.artifacts.CompletePost, context.parse_post, context.eligible,
		context.cache_load, context.cache_accept, context.mechanical,
	)
	return editing, False
#============================================
def _recovery_generation_observation(
	context: _RecoveryContext,
	batch_index: int,
	writer_slots: tuple[daily_blog.stage6_attempt_plan.PlannedStage6Attempt, ...],
	writing: daily_blog.replication.ReplicationResult,
	editing: daily_blog.replication.ReplicationResult,
) -> "daily_blog.stage6.Stage6BatchObservation":
	"""Close one recovery generation-only materialization in canonical order."""
	generation_ids = tuple(item.semantic_identity for item in writer_slots) + tuple(
		item.request.request_id for item in editing.candidates
	)
	view = context.plan.materialize(context.rung, batch_index, generation_ids)
	results = {
		item.request.request_id: item.result
		for item in writing.candidates + editing.candidates
	}
	observation = daily_blog.stage6.Stage6BatchObservation(
		view, tuple(results[item] for item in view.semantic_identities),
	)
	return observation


#============================================
def _review_recovery_batch(
	context: _RecoveryContext,
	batch_index: int,
	writer_slots: tuple[daily_blog.stage6_attempt_plan.PlannedStage6Attempt, ...],
	writing: daily_blog.replication.ReplicationResult,
	editing: daily_blog.replication.ReplicationResult,
	peers: tuple[daily_blog.artifacts.CompletePost, ...],
) -> tuple[
	daily_blog.replication.CandidateSetReviewResult,
	"daily_blog.stage6.Stage6BatchObservation",
	RecoveryPromotion,
]:
	"""Review one recovery peer set and close its observed materialization."""
	stage = context.config.complete_post
	bindings = daily_blog.stage6_execution.candidate_set_bindings(
		peers, context.rung, batch_index,
	)
	generation_ids = tuple(item.semantic_identity for item in writer_slots) + tuple(
		item.request.request_id for item in editing.candidates
	)
	review_view = context.plan.materialize(
		context.rung, batch_index, generation_ids, bindings,
	)

	review_prompts = daily_blog.candidate_set_prompts.load_prompt_set()

	def build_work(
		ordered: tuple[daily_blog.artifacts.EditorialArtifact, ...],
		assignment: daily_blog.replication.CandidateSetReviewAssignment,
	) -> daily_blog.replication.CandidateSetReviewWork:
		"""Bind one complete anonymous candidate set to one recovery reviewer."""
		attempt = daily_blog.stage6_execution.planned_attempt(
			context.plan, context.rung, batch_index, "reviewer",
			assignment.reviewer_index + 1,
		)
		prompt, _labels = daily_blog.candidate_set_prompts.render_candidate_set_review(
			context.templates["rubric"], context.rendered_context, ordered, review_prompts,
		)
		if len(prompt) > stage.prompt_limits["reviewer_chars"]:
			raise daily_blog.replication.ReviewUnavailable(
				"Stage 6 recovery reviewer prompt exceeds its configured limit."
			)
		request = daily_blog.stage6_execution.build_request(
			context.value.stage6_input, context.run_id, attempt, review_view,
			stage.reviewer_route, prompt, stage,
			context.resolved.contract.prompt_version,
			candidate_identities=tuple(item.content_hash for item in ordered),
			working_directory=context.config.daily_blog_repository,
		)
		return daily_blog.replication.CandidateSetReviewWork(request, assignment)

	def parse_winner(text: str, work: daily_blog.replication.CandidateSetReviewWork) -> str:
		"""Resolve one bounded complete-set label to its recovery artifact."""
		labels = dict(zip(
			daily_blog.candidate_set_prompts.candidate_labels(len(work.assignment.candidate_artifact_ids)),
			work.assignment.candidate_artifact_ids, strict=True,
		))
		try:
			return daily_blog.candidate_set_prompts.parse_candidate_set_verdict(text, labels)
		except daily_blog.candidate_set_prompts.CandidateSetVerdictParseError as error:
			raise daily_blog.agents.RepairableStructuredOutput(str(error)) from error

	review_results: dict[str, daily_blog.agents.AgentResult] = {}

	def observe(
		request: daily_blog.agents.RouteRequest,
		result: daily_blog.agents.AgentResult,
	) -> None:
		"""Retain reviewer results for the recovery batch observation."""
		review_results[request.request_id] = result

	review = daily_blog.replication.review_candidate_set(
		peers, daily_blog.artifacts.CompletePost, stage.reviewer_count,
		build_work, parse_winner, context.route_runner, context.budget,
		context.cache_load, context.cache_accept, observe,
	)
	results = {
		item.request.request_id: item.result
		for item in writing.candidates + editing.candidates
	}
	results.update(review_results)
	# Route observers prove review dispatch; narrow offline seams may return only votes.
	observed_bindings = bindings if all(
		item.semantic_identity in results
		for item in review_view.attempts if item.work_kind == "review"
	) else ()
	view = context.plan.materialize(
		context.rung, batch_index, generation_ids, observed_bindings,
	)
	observation = daily_blog.stage6.Stage6BatchObservation(
		view, tuple(results[item] for item in view.semantic_identities),
	)
	promotion = daily_blog.replication.promote(
		peers, daily_blog.artifacts.CompletePost, context.eligible, review.votes,
	)
	result = (review, observation, promotion)
	return result


#============================================
def _finish_recovery(
	context: _RecoveryContext,
	writer_parts: list[daily_blog.replication.ReplicationResult],
	editor_parts: list[daily_blog.replication.ReplicationResult],
	reviews: list[daily_blog.replication.CandidateSetReviewResult],
	observations: list["daily_blog.stage6.Stage6BatchObservation"],
	promotion: RecoveryPromotion | None,
	editor_prompt_limited: bool,
) -> daily_blog.recovery.RecoveryAttempt:
	"""Aggregate and close one recovery execution after its batch loop."""
	all_writing = daily_blog.stage6_execution.merge_generation(tuple(writer_parts))
	all_editing = daily_blog.stage6_execution.merge_generation(tuple(editor_parts))
	all_review = daily_blog.replication.CandidateSetReviewResult(
		tuple(work for review in reviews for work in review.work),
		tuple(vote for review in reviews for vote in review.votes),
	)
	if promotion is None:
		category = (
			"no_eligible_generation"
			if any(item.result.ok for item in all_writing.candidates)
			else "route_unavailable"
		)
		promotion = daily_blog.artifacts.NoArtifact(
			daily_blog.artifacts.CompletePost, category,
		)
	generation = daily_blog.replication.ReplicationResult(
		daily_blog.artifacts.CompletePost,
		all_writing.candidates + all_editing.candidates,
	)
	eligible_ids = tuple(sorted({item.artifact_id for item in generation.eligible}))
	generation_observation = daily_blog.recovery.GenerationObservation(
		"stage6_" + context.rung, len(generation.candidates),
		sum(item.result.ok for item in generation.candidates), eligible_ids,
	)
	if isinstance(promotion, daily_blog.artifacts.NoArtifact):
		category = (
			"no_eligible_generation"
			if generation_observation.successful_responses
			else "route_unavailable"
		)
		promotion = daily_blog.artifacts.NoArtifact(
			daily_blog.artifacts.CompletePost, category,
		)
	editor_reasons = () if all_editing.candidates else (
		("editor_prompt_limit", "editor_unavailable")
		if editor_prompt_limited else ("editor_unavailable",)
	)
	review_reasons = () if all_review.work else ("review_unavailable",)
	steps = (
		daily_blog.replication.generation_reliability("6.1", all_writing),
		daily_blog.replication.generation_reliability(
			"6.2", all_editing, editor_reasons,
		),
		daily_blog.stage6_attempt_reliability.review_reliability(
			all_review, promotion, review_reasons,
		),
		daily_blog.stage6_attempt_reliability.promotion_reliability(
			promotion, all_review.votes,
		),
	)
	result = daily_blog.recovery.RecoveryAttempt(
		promotion, generation_observation, recovery_generation=generation,
		step_reliability=steps, stage6_observations=tuple(observations),
	)
	return result


#============================================
def _unique(
	items: collections.abc.Iterable[daily_blog.artifacts.EditorialArtifact],
) -> tuple:
	"""Return stable exact candidate identities without carrying author order."""
	unique = tuple(sorted(
		{item.artifact_id: item for item in items}.values(),
		key=lambda item: (item.content_hash, item.artifact_id),
	))
	return unique

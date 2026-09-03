"""Primary fresh-batch execution for the bounded Stage 6 attempt plan."""

# Standard Library
import collections.abc
import dataclasses

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.complete_post_editor_prompts
import daily_blog.config
import daily_blog.editorial
import daily_blog.io_utils
import daily_blog.prompt_registry.loader
import daily_blog.publication_admission
import daily_blog.replication
import daily_blog.stage6
import daily_blog.stage6_attempt_plan
import daily_blog.stage6_attempt_reliability
import daily_blog.stage6_execution


#============================================
def _candidate_identity(item: daily_blog.artifacts.CompletePost) -> str:
	"""Return the opaque witness for the exact artifact shown to another role."""
	return item.content_hash


#============================================
PrimaryPromotion = (
	daily_blog.artifacts.SelectedPeer
	| daily_blog.artifacts.PreservedArtifact
	| daily_blog.artifacts.DegradedPromotion
	| daily_blog.artifacts.NoArtifact
)


#============================================
@dataclasses.dataclass(frozen=True)
class _PrimaryContext:
	"""Stable dependencies shared by one primary Stage 6 execution."""

	value: daily_blog.stage6.Stage6Input
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
	incumbent: daily_blog.artifacts.CompletePost | None
	plan: daily_blog.stage6_attempt_plan.Stage6AttemptPlan

	#============================================
	def parse_post(
		self, result: daily_blog.agents.AgentResult,
	) -> daily_blog.artifacts.CompletePost:
		"""Parse one primary response through the canonical post boundary."""
		return daily_blog.stage6._post(self.value, result)

	#============================================
	def eligible(
		self, item: daily_blog.artifacts.CompletePost,
	) -> daily_blog.artifacts.EligibilityResult:
		"""Apply final primary publication admission."""
		return daily_blog.stage6._eligible(self.value, item)

	#============================================
	def mechanical(
		self, item: daily_blog.artifacts.CompletePost,
	) -> daily_blog.artifacts.EligibilityResult:
		"""Apply primary mechanical admission before editorial use."""
		return daily_blog.publication_admission.complete_post_mechanical_eligibility(
			item, self.value.publication_surface, self.value.output_root,
		)


#============================================
def run_primary_batches(
	value: daily_blog.stage6.Stage6Input, run_id: str,
	config: daily_blog.config.DailyBlogConfig, budget: daily_blog.agents.RouteBudget,
	route_runner: object, resolved: daily_blog.editorial.PromptContractSnapshot,
	templates: dict[str, str], editor_prompt_set: daily_blog.prompt_registry.loader.LoadedPromptSet,
	cache_load: collections.abc.Callable[
		[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None,
	] | None,
	cache_accept: collections.abc.Callable[
		[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None,
	] | None,
	incumbent: daily_blog.artifacts.CompletePost | None,
) -> daily_blog.stage6.Stage6Result:
	"""Execute primary batches until deterministic promotion finds one artifact."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(
		config.complete_post.stage6_attempt_policy
	)
	context = _PrimaryContext(
		value, run_id, config, budget, route_runner, resolved, templates,
		editor_prompt_set, cache_load, cache_accept, incumbent, plan,
	)
	writer_parts: list[daily_blog.replication.ReplicationResult] = []
	editor_parts: list[daily_blog.replication.ReplicationResult] = []
	reviews: list[daily_blog.replication.ReviewResult] = []
	observations: list[daily_blog.stage6.Stage6BatchObservation] = []
	feedback_candidates: tuple[daily_blog.artifacts.CompletePost, ...] = ()
	last_promotion: PrimaryPromotion | None = None
	for batch_index in range(plan.policy.fresh_batch_count):
		writer_slots, writing, writer_material = _run_primary_writers(
			context, batch_index,
		)
		writer_parts.append(writing)
		editor_source = daily_blog.stage6._unique(
			writer_material + feedback_candidates + (() if incumbent is None else (incumbent,))
		)
		editing = _run_primary_editors(context, batch_index, writer_slots, editor_source)
		editor_parts.append(editing)
		feedback_candidates = daily_blog.stage6._unique(feedback_candidates + tuple(
			item.artifact for item in writing.candidates + editing.candidates
			if item.artifact is not None and daily_blog.publication_admission.complete_post_repair_feedback(
				item.artifact, value.publication_surface, value.output_root,
			) is not None
		))
		writer_peers = daily_blog.stage6._unique(writing.eligible)
		editor_peers = daily_blog.stage6._unique(editing.eligible)
		peers = daily_blog.stage6._unique(
			writer_peers + editor_peers + (() if incumbent is None else (incumbent,))
		)
		peers = tuple({item.content_hash: item for item in peers}[key] for key in sorted({item.content_hash for item in peers}))
		if not peers:
			observations.append(_primary_generation_observation(
				context, batch_index, writer_slots, writing, editing,
			))
			continue
		review, observation, promotion = _review_primary_batch(
			context, batch_index, writer_slots, writing, editing, peers,
		)
		reviews.append(review)
		observations.append(observation)
		last_promotion = promotion
		if not isinstance(promotion, daily_blog.artifacts.NoArtifact):
			break
	return _finish_primary(context, writer_parts, editor_parts, reviews, observations, last_promotion)


#============================================
def _run_primary_writers(
	context: _PrimaryContext, batch_index: int,
) -> tuple[
	tuple[daily_blog.stage6_attempt_plan.PlannedStage6Attempt, ...],
	daily_blog.replication.ReplicationResult,
	tuple[daily_blog.artifacts.CompletePost, ...],
]:
	"""Execute and mechanically admit one primary writer batch."""
	stage = context.config.complete_post
	writer_slots = tuple(daily_blog.stage6_execution.planned_attempt(
		context.plan, "primary", batch_index, "writer", index,
	) for index in range(1, stage.writer_count + 1))
	writer_view = context.plan.materialize(
		"primary", batch_index, tuple(item.semantic_identity for item in writer_slots),
	)
	logical_run = "stage6-" + daily_blog.io_utils.sha256_text(
		context.value.render_context(),
	)[:24]
	writer_requests = tuple(daily_blog.stage6_execution.build_request(
		context.value, context.run_id, item, writer_view, stage.writer_route,
		daily_blog.editorial.render_author_prompt(
			context.value,
			f"{logical_run}-batch-{batch_index + 1}-writer-{item.replica_index}",
			stage.prompt_limits["writer_chars"], snapshot=context.resolved,
		), stage, context.resolved.contract.prompt_version,
		working_directory=context.config.daily_blog_repository,
	) for item in writer_slots)
	if any(len(item.prompt) > stage.prompt_limits["writer_chars"] for item in writer_requests):
		raise RuntimeError("Stage 6 writer prompt exceeds its configured limit.")
	writing = daily_blog.replication.replicate(
		writer_requests, context.route_runner, context.budget,
		daily_blog.artifacts.CompletePost, context.parse_post, context.eligible,
		context.cache_load, context.cache_accept, context.mechanical,
	)
	writer_material = daily_blog.stage6._unique(
		item.artifact for item in writing.candidates
		if item.artifact is not None and context.mechanical(item.artifact).eligible
	)
	result = (writer_slots, writing, writer_material)
	return result


#============================================
def _run_primary_editors(
	context: _PrimaryContext,
	batch_index: int,
	writer_slots: tuple[daily_blog.stage6_attempt_plan.PlannedStage6Attempt, ...],
	editor_source: tuple[daily_blog.artifacts.CompletePost, ...],
) -> daily_blog.replication.ReplicationResult:
	"""Execute one editor batch over exact mechanically admitted sources."""
	editing = daily_blog.replication.ReplicationResult(
		daily_blog.artifacts.CompletePost, (),
	)
	if not editor_source:
		return editing
	stage = context.config.complete_post
	editor_slots = tuple(daily_blog.stage6_execution.planned_attempt(
		context.plan, "primary", batch_index, "editor", index,
	) for index in range(1, stage.editor_count + 1))
	generation_ids = tuple(
		item.semantic_identity for item in writer_slots + editor_slots
	)
	editor_view = context.plan.materialize("primary", batch_index, generation_ids)
	candidate_json = daily_blog.stage6._anonymous_posts(context.value, editor_source)
	feedback_digest = daily_blog.stage6._repair_feedback_digest(
		context.value, editor_source,
	)
	editor_requests = tuple(daily_blog.stage6_execution.build_request(
		context.value, context.run_id, item, editor_view, stage.editor_route,
		daily_blog.complete_post_editor_prompts.render_complete_post_editor_prompt(
			context.value.render_context(), candidate_json,
			"editor-" + str(item.replica_index), context.editor_prompt_set,
		), stage, context.resolved.contract.prompt_version,
		tuple(_candidate_identity(candidate) for candidate in editor_source),
		feedback_digest, working_directory=context.config.daily_blog_repository,
	) for item in editor_slots)
	if any(len(item.prompt) > stage.prompt_limits["editor_chars"] for item in editor_requests):
		return editing
	editing = daily_blog.replication.replicate(
		editor_requests, context.route_runner, context.budget,
		daily_blog.artifacts.CompletePost, context.parse_post, context.eligible,
		context.cache_load, context.cache_accept, context.mechanical,
	)
	return editing


#============================================
def _primary_generation_observation(
	context: _PrimaryContext,
	batch_index: int,
	writer_slots: tuple[daily_blog.stage6_attempt_plan.PlannedStage6Attempt, ...],
	writing: daily_blog.replication.ReplicationResult,
	editing: daily_blog.replication.ReplicationResult,
) -> daily_blog.stage6.Stage6BatchObservation:
	"""Close one primary generation-only materialization in canonical order."""
	generation_ids = tuple(item.semantic_identity for item in writer_slots) + tuple(
		item.request.request_id for item in editing.candidates
	)
	view = context.plan.materialize("primary", batch_index, generation_ids)
	results = {item.request.request_id: item.result for item in writing.candidates}
	results.update({item.request.request_id: item.result for item in editing.candidates})
	observation = daily_blog.stage6.Stage6BatchObservation(
		view, tuple(results[item] for item in view.semantic_identities),
	)
	return observation


#============================================
def _review_primary_batch(
	context: _PrimaryContext,
	batch_index: int,
	writer_slots: tuple[daily_blog.stage6_attempt_plan.PlannedStage6Attempt, ...],
	writing: daily_blog.replication.ReplicationResult,
	editing: daily_blog.replication.ReplicationResult,
	peers: tuple[daily_blog.artifacts.CompletePost, ...],
) -> tuple[
	daily_blog.replication.ReviewResult,
	daily_blog.stage6.Stage6BatchObservation,
	PrimaryPromotion,
]:
	"""Review one exact peer set and close its observed materialization."""
	stage = context.config.complete_post
	bindings = daily_blog.stage6_execution.candidate_pair_bindings(
		peers, "primary", batch_index,
	)
	generation_ids = tuple(item.semantic_identity for item in writer_slots) + tuple(
		item.request.request_id for item in editing.candidates
	)
	review_view = context.plan.materialize(
		"primary", batch_index, generation_ids, bindings,
	)

	def build_work(
		left: daily_blog.artifacts.CompletePost,
		right: daily_blog.artifacts.CompletePost,
		assignment: daily_blog.replication.ReviewAssignment,
	) -> daily_blog.replication.ReviewWork:
		"""Bind one anonymous candidate pair to its exact reviewer slot."""
		attempt = daily_blog.stage6_execution.planned_attempt(
			context.plan, "primary", batch_index, "reviewer",
			assignment.reviewer_index + 1, assignment.pair_index + 1,
			assignment.display_order + 1,
		)
		prompt = context.templates["referee"].format(
			rubric=context.templates["rubric"],
			evidence_json=context.value.render_context(),
			candidate_a=left.content, candidate_b=right.content,
		)
		if len(prompt) > stage.prompt_limits["reviewer_chars"]:
			raise RuntimeError("Stage 6 reviewer prompt exceeds its configured limit.")
		request = daily_blog.stage6_execution.build_request(
			context.value, context.run_id, attempt, review_view,
			stage.reviewer_route, prompt, stage,
			context.resolved.contract.prompt_version,
			working_directory=context.config.daily_blog_repository,
		)
		work = daily_blog.replication.ReviewWork(
			request, left.artifact_id, right.artifact_id, assignment,
		)
		return work

	def parse_winner(text: str, work: daily_blog.replication.ReviewWork) -> str:
		"""Resolve one bounded referee label to its anonymous artifact."""
		try:
			verdict = daily_blog.editorial.parse_referee_verdict(text, {"A", "B"})
		except daily_blog.editorial.RefereeVerdictParseError as error:
			raise daily_blog.agents.RepairableStructuredOutput(str(error)) from error
		winner = {"A": work.first_artifact_id, "B": work.second_artifact_id}.get(
			verdict["winner"], "",
		)
		return winner

	repair_results: dict[str, daily_blog.agents.AgentResult] = {}
	repair_sources: list[str] = []

	def repair(
		work: daily_blog.replication.ReviewWork, response: str,
	) -> daily_blog.replication.ReviewWork:
		"""Bind a repair request to the materialized review response it repairs."""
		review_slot = work.request.request_id
		repair_view = context.plan.materialize(
			"primary", batch_index, generation_ids, bindings, (review_slot,),
		)
		attempt = next(
			item for item in repair_view.attempts
			if item.work_kind == "review_repair"
			and item.repair_of_identity == review_slot
		)
		prompt = context.templates["repair"].format(
			response=response[:daily_blog.editorial.MAX_REFEREE_RESPONSE_CHARS],
		)
		if len(prompt) > stage.prompt_limits["repair_chars"]:
			raise RuntimeError("Stage 6 reviewer repair prompt exceeds its configured limit.")
		request = daily_blog.stage6_execution.build_request(
			context.value, context.run_id, attempt, repair_view,
			stage.reviewer_route, prompt, stage,
			context.resolved.contract.prompt_version, repair_response=response,
			working_directory=context.config.daily_blog_repository,
		)
		repaired = daily_blog.replication.ReviewWork(
			request, work.first_artifact_id, work.second_artifact_id,
			work.assignment,
		)
		return repaired

	def salvage(text: str, work: daily_blog.replication.ReviewWork) -> str | None:
		"""Map an allowed standalone label to its anonymous artifact."""
		label = daily_blog.replication.salvage_allowed_identifier(text, ("A", "B"))
		winner = {"A": work.first_artifact_id, "B": work.second_artifact_id}.get(label)
		return winner

	def observe_review(
		request: daily_blog.agents.RouteRequest,
		result: daily_blog.agents.AgentResult,
	) -> None:
		"""Retain response-free route facts for exact ledger closure."""
		repair_results[request.request_id] = result
		if request.repair_of:
			repair_sources.append(request.repair_of)

	review = daily_blog.replication.review(
		peers, daily_blog.artifacts.CompletePost, stage.reviewer_count,
		build_work, parse_winner, context.route_runner, context.budget, repair,
		salvage, context.cache_load, context.cache_accept, observe_review,
	)
	all_results = {item.request.request_id: item.result for item in writing.candidates}
	all_results.update({item.request.request_id: item.result for item in editing.candidates})
	all_results.update(repair_results)
	# Materialize only the review repairs that the route observer actually saw.
	repair_source_set = frozenset(repair_sources)
	repair_source_slot_ids = tuple(
		item.semantic_identity
		for item in context.plan.attempts_for("primary", batch_index)
		if item.work_kind == "review" and item.semantic_identity in repair_source_set
	)
	final_view = context.plan.materialize(
		"primary", batch_index, generation_ids, bindings, repair_source_slot_ids,
	)
	observation = daily_blog.stage6.Stage6BatchObservation(
		final_view, tuple(all_results[item] for item in final_view.semantic_identities),
	)
	promotion = daily_blog.replication.promote(
		peers, daily_blog.artifacts.CompletePost, context.eligible, review.votes,
		context.incumbent,
	)
	result = (review, observation, promotion)
	return result


#============================================
def _finish_primary(
	context: _PrimaryContext,
	writer_parts: list[daily_blog.replication.ReplicationResult],
	editor_parts: list[daily_blog.replication.ReplicationResult],
	reviews: list[daily_blog.replication.ReviewResult],
	observations: list[daily_blog.stage6.Stage6BatchObservation],
	last_promotion: PrimaryPromotion | None,
) -> daily_blog.stage6.Stage6Result:
	"""Aggregate and close one primary execution after its batch loop."""
	all_writing = daily_blog.stage6_execution.merge_generation(tuple(writer_parts))
	all_editing = daily_blog.stage6_execution.merge_generation(tuple(editor_parts))
	all_review = daily_blog.replication.ReviewResult(
		tuple(work for review in reviews for work in review.work),
		tuple(vote for review in reviews for vote in review.votes),
	)
	if last_promotion is None:
		category = "no_eligible_generation" if any(item.result.ok for item in all_writing.candidates) else "route_unavailable"
		last_promotion = daily_blog.artifacts.NoArtifact(daily_blog.artifacts.CompletePost, category)
	editor_reasons = () if all_editing.candidates else ("editor_unavailable",)
	review_reasons = () if all_review.work else ("review_unavailable",)
	steps = (
		daily_blog.replication.generation_reliability("6.1", all_writing),
		daily_blog.replication.generation_reliability("6.2", all_editing, editor_reasons),
		daily_blog.stage6_attempt_reliability.review_reliability(
			all_review, last_promotion, review_reasons,
		),
		daily_blog.stage6_attempt_reliability.promotion_reliability(
			last_promotion, all_review.votes,
		),
	)
	if context.incumbent is None:
		ledger = daily_blog.stage6_attempt_reliability.stage6_attempt_ledger(
			context.plan, tuple(observations), all_writing, all_editing, all_review,
			"" if isinstance(last_promotion, daily_blog.artifacts.NoArtifact) else last_promotion.artifact.artifact_id,
		)
		facts = {item.slot_id: item for item in ledger.facts}
		observations = [dataclasses.replace(item, closed_facts=tuple(
			facts[slot] for slot in item.materialization.semantic_identities
		)) for item in observations]
	result = daily_blog.stage6.Stage6Result(
		promotion=last_promotion, generation=all_writing, review=all_review,
		reliability=daily_blog.stage6._aggregate(steps), editing=all_editing,
		step_reliability=steps,
		primary_observations=tuple(observations),
		reliability_scope=(
			daily_blog.stage6.RELIABILITY_SCOPE_PLANNED_ROUTES_COMPLETE
			if context.incumbent is None
			else daily_blog.stage6.RELIABILITY_SCOPE_EXTERNAL_INCUMBENT_OBSERVED
		),
	)
	return result

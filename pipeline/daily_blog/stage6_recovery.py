"""Independent editorial topology for the Stage 6 lower recovery rungs."""

# Standard Library
import collections.abc

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
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
	cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None,
	cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None,
	post: collections.abc.Callable[[object, daily_blog.agents.AgentResult], daily_blog.artifacts.CompletePost],
	request: collections.abc.Callable[..., daily_blog.agents.RouteRequest],
	anonymous_posts: collections.abc.Callable[[object, collections.abc.Iterable[daily_blog.artifacts.CompletePost]], str],
) -> object:
	"""Create, repair, compare, and promote one exact recovery-rung post set."""
	if type(run_id) is not str or not run_id:
		raise RuntimeError("Stage 6 recovery requires a nonempty run identity.")
	resolved = daily_blog.editorial.resolve_snapshot(contract, selection, snapshot)
	templates = daily_blog.editorial.validate_prompt_templates(snapshot=resolved)
	prompt_identity = daily_blog.editorial.prompt_contract_identity(snapshot=resolved)
	editor_prompt_set = daily_blog.prompt_registry.loader.load_prompt_set(
		daily_blog.prompt_registry.definitions.COMPLETE_POST_EDITOR_PROMPT_SET,
	)
	editor_identity = daily_blog.complete_post_editor_prompts.complete_post_editor_prompt_identity(editor_prompt_set)
	stage = config.complete_post
	context = value.render_context()
	logical_run = "stage6-" + daily_blog.io_utils.sha256_text(context)[:24]
	writer_requests = tuple(request(
		value, run_id, config, resolved.contract.prompt_version, prompt_identity,
		daily_blog.editorial.render_author_prompt(value, logical_run + "-" + value.rung.value + "-writer-" + str(index + 1),
			stage.prompt_limits["writer_chars"], snapshot=resolved), "recovery_author", str(index + 1),
	) for index in range(stage.writer_count))
	if any(len(item.prompt) > stage.prompt_limits["writer_chars"] for item in writer_requests):
		raise RuntimeError("Stage 6 recovery writer prompt exceeds its configured limit.")
	route_runner = runner if runner is not None else daily_blog.routes.CommandRouteRunner()
	mechanical = lambda item: daily_blog.publication_admission.complete_post_mechanical_eligibility(
		item, value.stage6_input.publication_surface, value.stage6_input.output_root,
	)
	eligible = lambda item: daily_blog.publication_admission.complete_post_eligibility(
		item, value.stage6_input.publication_surface, value.stage6_input.output_root,
	)
	writing = daily_blog.replication.replicate(
		writer_requests, route_runner, budget, daily_blog.artifacts.CompletePost,
		lambda item: post(value, item), eligible, cache_load, cache_accept, mechanical,
	)
	material = _unique(item.artifact for item in writing.candidates if item.artifact is not None
		and mechanical(item.artifact).eligible)
	editing = daily_blog.replication.ReplicationResult(daily_blog.artifacts.CompletePost, ())
	editor_prompt_limited = False
	if material:
		candidate_json = anonymous_posts(value.stage6_input, material)
		editor_requests = tuple(request(
			value, run_id, config, resolved.contract.prompt_version, editor_identity,
			daily_blog.complete_post_editor_prompts.render_complete_post_editor_prompt(
				context, candidate_json, "editor-" + str(index + 1), editor_prompt_set),
			"recovery_editor", str(index + 1), tuple(item.content_hash for item in material),
		) for index in range(stage.editor_count))
		if all(len(item.prompt) <= stage.prompt_limits["editor_chars"] for item in editor_requests):
			editing = daily_blog.replication.replicate(
				editor_requests, route_runner, budget, daily_blog.artifacts.CompletePost,
				lambda item: post(value, item), eligible, cache_load, cache_accept, mechanical,
			)
		else:
			editor_prompt_limited = True
	peers = _unique(tuple(writing.eligible) + tuple(editing.eligible))
	def build_work(left: daily_blog.artifacts.EditorialArtifact, right: daily_blog.artifacts.EditorialArtifact,
		assignment: daily_blog.replication.ReviewAssignment) -> daily_blog.replication.ReviewWork:
		prompt = templates["referee"].format(rubric=templates["rubric"], evidence_json=context,
			candidate_a=left.content, candidate_b=right.content)
		if len(prompt) > stage.prompt_limits["reviewer_chars"]:
			raise RuntimeError("Stage 6 recovery reviewer prompt exceeds its configured limit.")
		work_request = request(value, run_id, config, resolved.contract.prompt_version, editor_identity, prompt,
			"recovery_reviewer", f"{assignment.pair_index}_{assignment.reviewer_index}_{assignment.display_order}",
			(left.content_hash, right.content_hash), assignment)
		return daily_blog.replication.ReviewWork(work_request, left.artifact_id, right.artifact_id, assignment)
	def parse_winner(text: str, work: daily_blog.replication.ReviewWork) -> str:
		try:
			verdict = daily_blog.editorial.parse_referee_verdict(text, {"A", "B"})
		except daily_blog.editorial.RefereeVerdictParseError as error:
			raise daily_blog.agents.RepairableStructuredOutput(str(error)) from error
		return {"A": work.first_artifact_id, "B": work.second_artifact_id}.get(verdict["winner"], "")
	def repair(work: daily_blog.replication.ReviewWork, response: str) -> daily_blog.replication.ReviewWork:
		prompt = templates["repair"].format(response=response[:daily_blog.editorial.MAX_REFEREE_RESPONSE_CHARS])
		if len(prompt) > stage.prompt_limits["repair_chars"]:
			raise RuntimeError("Stage 6 recovery reviewer repair prompt exceeds its configured limit.")
		work_request = request(value, run_id, config, resolved.contract.prompt_version, editor_identity, prompt,
			"recovery_reviewer", "repair_" + work.request.request_id,
			(daily_blog.io_utils.sha256_text(response),), work.assignment, work.request.cache_input_hash)
		return daily_blog.replication.ReviewWork(work_request, work.first_artifact_id, work.second_artifact_id, work.assignment)
	def salvage(text: str, work: daily_blog.replication.ReviewWork) -> str | None:
		label = daily_blog.replication.salvage_allowed_identifier(text, ("A", "B"))
		return {"A": work.first_artifact_id, "B": work.second_artifact_id}.get(label)
	if len(peers) == 1:
		review = daily_blog.replication.ReviewResult((), ())
		promotion = daily_blog.artifacts.SelectedPeer(peers[0], daily_blog.artifacts.CompletePost)
	else:
		review = daily_blog.replication.review(peers, daily_blog.artifacts.CompletePost, stage.reviewer_count,
			build_work, parse_winner, route_runner, budget, repair, salvage, cache_load, cache_accept)
		promotion = daily_blog.replication.promote(peers, daily_blog.artifacts.CompletePost, eligible, review.votes)
	result = daily_blog.replication.ReplicationResult(
		daily_blog.artifacts.CompletePost, writing.candidates + editing.candidates,
	)
	eligible_ids = tuple(sorted({item.artifact_id for item in result.eligible}))
	observation = daily_blog.recovery.GenerationObservation(
		"stage6_" + value.rung.value, len(result.candidates),
		sum(item.result.ok for item in result.candidates), eligible_ids,
	)
	if isinstance(promotion, daily_blog.artifacts.NoArtifact):
		category = "no_eligible_generation" if observation.successful_responses else "route_unavailable"
		promotion = daily_blog.artifacts.NoArtifact(daily_blog.artifacts.CompletePost, category)
	editor_reasons = () if editing.eligible else (
		("editor_prompt_limit", "editor_unavailable") if editor_prompt_limited else
		(("editor_unavailable",) if material else ("upstream_unavailable",))
	)
	review_reasons = () if review.work else ("review_unavailable",)
	steps = (
		_generation_reliability("6.1", writing),
		_generation_reliability("6.2", editing, editor_reasons),
		_review_reliability(review, promotion, review_reasons),
		_promotion_reliability(promotion, review.votes),
	)
	return daily_blog.recovery.RecoveryAttempt(
		promotion, observation, recovery_generation=result, step_reliability=steps,
	)


#============================================
def _unique(items: collections.abc.Iterable[daily_blog.artifacts.EditorialArtifact]) -> tuple:
	"""Return stable exact candidate identities without carrying author order."""
	return tuple(sorted({item.artifact_id: item for item in items}.values(),
		key=lambda item: (item.content_hash, item.artifact_id)))


def _generation_reliability(step: str, result: daily_blog.replication.ReplicationResult,
	reasons: tuple[str, ...] = ()) -> daily_blog.replication.StepReliability:
	"""Summarize one bounded recovery generation mechanism."""
	values = result.candidates
	all_reasons = set(reasons) | {item.failure for item in values if item.failure}
	if any(item.result.ok and (item.eligibility is None or not item.eligibility.eligible) for item in values):
		all_reasons.add("ineligible_generation")
	succeeded = sum(item.result.ok and item.eligibility is not None and item.eligibility.eligible for item in values)
	return daily_blog.replication.StepReliability(step, "degraded" if all_reasons else "succeeded",
		len(values), succeeded, len(values) - succeeded, sum(item.result.ok and item.result.resumed for item in values),
		0, 0, "", tuple(sorted(all_reasons)))


def _review_reliability(review: daily_blog.replication.ReviewResult, promotion: object,
	reasons: tuple[str, ...]) -> daily_blog.replication.StepReliability:
	"""Summarize recovery referee and repair observations without prose."""
	votes = review.votes
	pairs: dict[tuple[str, str], set[str]] = {}
	for item in votes:
		if item.status == "succeeded":
			pairs.setdefault(tuple(sorted((item.first_artifact_id, item.second_artifact_id))), set()).add(item.winner_artifact_id)
	disagreements = sum(len(item) > 1 for item in pairs.values())
	all_reasons = set(reasons) | set(daily_blog.replication.review_reasons(votes, disagreements))
	best = "" if isinstance(promotion, daily_blog.artifacts.NoArtifact) else promotion.artifact.artifact_id
	return daily_blog.replication.StepReliability("6.3", "degraded" if all_reasons else "succeeded",
		len(votes), sum(item.status == "succeeded" for item in votes), sum(item.status == "failed" for item in votes),
		0, sum(item.repaired and item.status == "succeeded" for item in votes), disagreements, best,
		tuple(sorted(all_reasons)))


def _promotion_reliability(promotion: object, votes: tuple[daily_blog.replication.ReviewVote, ...]) -> daily_blog.replication.StepReliability:
	"""Record the deterministic recovery promotion separately from route facts."""
	if isinstance(promotion, daily_blog.artifacts.NoArtifact):
		reasons, best = (promotion.reason,), ""
	elif isinstance(promotion, daily_blog.artifacts.DegradedPromotion):
		reasons, best = promotion.reasons, promotion.artifact.artifact_id
	else:
		reasons, best = (), promotion.artifact.artifact_id
	return daily_blog.replication.StepReliability("6.4", "degraded" if reasons else "succeeded", 1, 1, 0,
		0, 0, 0, best, tuple(sorted(reasons)))

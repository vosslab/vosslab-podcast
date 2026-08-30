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
import daily_blog.contracts
import daily_blog.editorial
import daily_blog.io_utils
import daily_blog.replication
import daily_blog.recovery
import daily_blog.routes
import daily_blog.schema


MAX_STAGE6_CONTEXT_CHARS = 60000


#============================================
@dataclasses.dataclass(frozen=True)
class Stage6Input:
	"""The provenance-checked input boundary for complete-post work."""

	daily_outline: daily_blog.artifacts.DailyOutline
	repo_stories: tuple[daily_blog.artifacts.RepoStory, ...]
	packets: tuple[daily_blog.schema.EvidencePacket, ...]
	output_root: str
	output_path: str

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
		if not os.path.isdir(os.path.realpath(self.output_root)):
			raise RuntimeError("Stage 6 trusted output root must exist.")
		self._validate_grounding()
		if os.path.basename(self.output_path) != "post.md":
			raise RuntimeError("Stage 6 output path must be the date-owned post.md destination.")
		if os.path.basename(os.path.dirname(self.output_path)) != self.report_date:
			raise RuntimeError("Stage 6 output path report date does not match DailyOutline.")

	@property
	def report_date(self) -> str:
		"""Expose the sole publication identity required by the frozen V4 prompt."""
		return self.daily_outline.report_date

	def _validate_grounding(self) -> None:
		"""Require artifact, packet, repository, and date consistency at the seam."""
		if not daily_blog.artifacts.evaluate_eligibility(self.daily_outline, self.packets).eligible:
			raise RuntimeError("Stage 6 DailyOutline is not mechanically eligible.")
		if any(item.report_date != self.report_date for item in self.packets):
			raise RuntimeError("Stage 6 packets must share the DailyOutline report date.")
		repositories: set[str] = set()
		for story in self.repo_stories:
			if not daily_blog.artifacts.evaluate_eligibility(story, self.packets).eligible:
				raise RuntimeError("Stage 6 RepoStory is not mechanically eligible.")
			if story.report_date != self.report_date:
				raise RuntimeError("Stage 6 RepoStory report date does not match DailyOutline.")
			repositories.update(story.repositories)
		if repositories != set(self.daily_outline.repositories):
			raise RuntimeError("Stage 6 RepoStory repositories must exactly cover DailyOutline scope.")
		probe = daily_blog.artifacts.CompletePost.create(
			self.report_date, self.packets, self.daily_outline.repositories,
			"probe <!-- evidence: " + self.daily_outline.evidence_ids[0] + " -->",
			(self.daily_outline.evidence_ids[0],), self.report_date, self.output_path,
		)
		if "output_path_outside_root" in daily_blog.artifacts.evaluate_eligibility(
			probe, self.packets, (self.output_root,),
		).reasons:
			raise RuntimeError("Stage 6 output path is outside its trusted root.")

	def render_context(self) -> str:
		"""Render bounded canonical typed evidence without an EditorialProjection."""
		value = {"daily_outline": daily_blog.schema.model_cache_artifact(self.daily_outline.to_dict()),
			"repo_stories": [daily_blog.schema.model_cache_artifact(item.to_dict()) for item in sorted(self.repo_stories, key=lambda item: (item.repositories, item.content_hash))],
			"packets": [daily_blog.schema.model_cache_packet_content(item) for item in sorted(self.packets, key=daily_blog.schema.model_cache_packet_identity)]}
		context = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
		if len(context) > MAX_STAGE6_CONTEXT_CHARS:
			raise RuntimeError("Stage 6 typed evidence context exceeds its bounded limit.")
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
		if self.recovery_generation is not None:
			if (
				type(self.recovery_generation) is not daily_blog.replication.ReplicationResult
				or self.recovery_generation.expected_type is not daily_blog.artifacts.CompletePost
			):
				raise RuntimeError("Stage 6 recovery generation observation is invalid.")
			if (
				self.artifact is None
				or len(self.recovery_generation.eligible) != 1
				or self.recovery_generation.eligible[0] is not self.artifact
			):
				raise RuntimeError(
					"Stage 6 recovery generation must contain the exact promoted artifact."
				)

	@property
	def artifact(self) -> daily_blog.artifacts.CompletePost | None:
		"""Return the exact-rung promoted artifact, if editorial work produced one."""
		return None if isinstance(self.promotion, daily_blog.artifacts.NoArtifact) else self.promotion.artifact


#============================================
def _eligible(value: Stage6Input, item: daily_blog.artifacts.EditorialArtifact) -> daily_blog.artifacts.EligibilityResult:
	"""Apply shared mechanical eligibility to a Stage 6 complete post."""
	return daily_blog.artifacts.evaluate_eligibility(item, value.packets, (value.output_root,))


#============================================
def _post(value: Stage6Input, result: daily_blog.agents.AgentResult) -> daily_blog.artifacts.CompletePost:
	"""Parse one whole post response; no code path assembles prose."""
	content = result.text.rstrip() + "\n"
	evidence_ids = daily_blog.artifacts.evidence_references(content)
	if not evidence_ids:
		raise daily_blog.agents.RepairableStructuredOutput("Complete post has no evidence reference.")
	return daily_blog.artifacts.CompletePost.create(value.report_date, value.packets,
		value.daily_outline.repositories, content, evidence_ids, value.report_date, value.output_path,
		daily_blog.artifacts.referenced_image_paths(content))


#============================================
def _unique(items: collections.abc.Iterable[daily_blog.artifacts.CompletePost]) -> tuple[daily_blog.artifacts.CompletePost, ...]:
	"""Return identity-sorted distinct same-rung candidates."""
	return tuple(sorted({item.artifact_id: item for item in items}.values(),
		key=lambda item: (item.content_hash, item.artifact_id)))


#============================================
def _anonymous_posts(items: collections.abc.Iterable[daily_blog.artifacts.CompletePost]) -> str:
	"""Render identity-sorted whole writer candidates without author identity."""
	value = {"candidates": [{"alias": "candidate-" + str(index + 1), "content": item.content}
		for index, item in enumerate(_unique(items))]}
	rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
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
def recover_writer_complete_post(value: Stage6Input, run_id: str,
	config: daily_blog.config.DailyBlogConfig, budget: daily_blog.agents.RouteBudget,
	runner: object | None = None, contract: daily_blog.contracts.EditorialContract | None = None,
	selection: daily_blog.contracts.ExampleSelection | None = None,
	snapshot: daily_blog.editorial.PromptContractSnapshot | None = None,
	cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None = None,
	cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None = None,
) -> daily_blog.recovery.RecoveryAttempt:
	"""Run one configured whole-post writer recovery attempt without durable writes."""
	if type(value) is not Stage6Input or type(run_id) is not str or not run_id:
		raise RuntimeError("Stage 6 recovery requires exact input and a nonempty run identity.")
	if type(config.complete_post) is not daily_blog.editorial_stage_config.CompletePostConfig:
		raise RuntimeError("Stage 6 recovery requires exact complete-post configuration.")
	if type(budget) is not daily_blog.agents.RouteBudget:
		raise RuntimeError("Stage 6 recovery requires the coordinator-owned RouteBudget.")
	resolved = daily_blog.editorial.resolve_snapshot(contract, selection, snapshot)
	daily_blog.editorial.validate_prompt_templates(snapshot=resolved)
	editor_contract = daily_blog.complete_post_editor_prompts.load_complete_post_editor_prompt_contract()
	editor_identity = daily_blog.complete_post_editor_prompts.complete_post_editor_prompt_identity(editor_contract)
	stage = config.complete_post
	logical_writer_run = "stage6-" + daily_blog.io_utils.sha256_text(value.render_context())[:24]
	request = _request(value, run_id, "recovery", "writer_recovery", "1", stage.writer_route,
		daily_blog.editorial.render_author_prompt(value, logical_writer_run + "-writer-recovery",
			stage.prompt_limits["writer_chars"], snapshot=resolved), stage,
		config.daily_blog_repository, resolved.contract.prompt_version, editor_identity)
	if len(request.prompt) > stage.prompt_limits["writer_chars"]:
		raise RuntimeError("Stage 6 recovery writer prompt exceeds its configured limit.")
	result = daily_blog.replication.replicate(
		(request,), runner if runner is not None else daily_blog.routes.CommandRouteRunner(), budget,
		daily_blog.artifacts.CompletePost, lambda item: _post(value, item),
		lambda item: _eligible(value, item), cache_load, cache_accept,
	)
	candidate = result.candidates[0]
	eligible = tuple(sorted(item.artifact_id for item in result.eligible))
	observation = daily_blog.recovery.GenerationObservation(
		"stage6_writer_recovery", 1, int(candidate.result.ok), eligible,
	)
	if eligible:
		return daily_blog.recovery.RecoveryAttempt(
			daily_blog.artifacts.SelectedPeer(candidate.artifact, daily_blog.artifacts.CompletePost),
			observation, recovery_generation=result,
		)
	category = (daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION
		if candidate.result.ok else daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE)
	return daily_blog.recovery.RecoveryAttempt(
		daily_blog.artifacts.NoArtifact(daily_blog.artifacts.CompletePost, category.value), observation,
		recovery_generation=result,
	)


#============================================
def run_stage6(value: Stage6Input, run_id: str, config: daily_blog.config.DailyBlogConfig,
	budget: daily_blog.agents.RouteBudget, runner: object | None = None,
	contract: daily_blog.contracts.EditorialContract | None = None,
	selection: daily_blog.contracts.ExampleSelection | None = None,
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
	editor_contract = daily_blog.complete_post_editor_prompts.load_complete_post_editor_prompt_contract()
	editor_identity = daily_blog.complete_post_editor_prompts.complete_post_editor_prompt_identity(editor_contract)
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
		cache_load, cache_accept)
	writer_peers = _unique(writing.eligible)
	editing = daily_blog.replication.ReplicationResult(daily_blog.artifacts.CompletePost, ())
	editor_prompt_limited = False
	editor_source = writer_peers if incumbent is None else _unique(writer_peers + (incumbent,))
	if editor_source:
		candidate_json = _anonymous_posts(editor_source)
		editor_requests = tuple(_request(value, run_id, "6_2", "editor", str(index + 1), stage.editor_route,
			daily_blog.complete_post_editor_prompts.render_complete_post_editor_prompt(value.render_context(),
				candidate_json, "editor-" + str(index + 1), editor_contract), stage, config.daily_blog_repository,
			resolved.contract.prompt_version, editor_identity, tuple(item.content_hash for item in editor_source))
			for index in range(stage.editor_count))
		if any(len(item.prompt) > stage.prompt_limits["editor_chars"] for item in editor_requests):
			editor_prompt_limited = True
		else:
			editing = daily_blog.replication.replicate(editor_requests, route_runner, budget,
				daily_blog.artifacts.CompletePost, lambda item: _post(value, item), lambda item: _eligible(value, item),
				cache_load, cache_accept)
	editor_peers = _unique(editing.eligible)
	# Every eligible whole post is an independent peer.  Editors are an
	# additional editorial path, never a mechanical replacement for writers.
	peers = _unique(writer_peers + editor_peers)
	if incumbent is not None:
		peers = _unique(peers + (incumbent,))
	if not peers:
		promotion = daily_blog.artifacts.NoArtifact(daily_blog.artifacts.CompletePost, "no_eligible_generation")
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

"""Pure Stage 7 final synthesis with incumbent-preserving promotion."""

# Standard Library
import collections.abc
import dataclasses
import json

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.config
import daily_blog.editorial_stage_config
import daily_blog.final_synthesis_config
import daily_blog.editorial
import daily_blog.final_synthesis_prompts
import daily_blog.io_utils
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.loader
import daily_blog.replication
import daily_blog.routes
import daily_blog.schema
import daily_blog.stage6
import daily_blog.publication_admission


MAX_STAGE7_REVIEW_FACTS_CHARS = 30000


#============================================
@dataclasses.dataclass(frozen=True)
class Stage7Input:
	"""Exact, validated Stage 6 facts that final synthesis may observe."""
	stage6_input: daily_blog.stage6.Stage6Input
	stage6_result: daily_blog.stage6.Stage6Result

	def __post_init__(self) -> None:
		"""Reject a mismatched or ungrounded incumbent before route work."""
		if type(self.stage6_input) is not daily_blog.stage6.Stage6Input:
			raise RuntimeError("Stage 7 requires an exact Stage6Input.")
		if type(self.stage6_result) is not daily_blog.stage6.Stage6Result:
			raise RuntimeError("Stage 7 requires an exact Stage6Result.")
		if type(self.stage6_result.artifact) is not daily_blog.artifacts.CompletePost:
			raise RuntimeError("Stage 7 requires an exact promoted Stage 6 CompletePost incumbent.")
		if not _matches_stage6_target(self, self.stage6_result.artifact):
			raise RuntimeError("Stage 7 Stage 6 incumbent is not mechanically eligible.")
		if not _is_stage6_lineage_incumbent(self, self.stage6_result.artifact):
			raise RuntimeError("Stage 7 incumbent is absent from eligible Stage 6 lineage.")

	@property
	def report_date(self) -> str:
		"""Expose the sole publication identity from the exact Stage 6 input."""
		return self.stage6_input.report_date

	@property
	def incumbent(self) -> daily_blog.artifacts.CompletePost:
		"""Return the validated Stage 6 object, never a reconstructed copy."""
		artifact = self.stage6_result.artifact
		if type(artifact) is not daily_blog.artifacts.CompletePost:
			raise RuntimeError("Stage 7 incumbent disappeared after input validation.")
		return artifact

	def identity_dict(self) -> dict[str, object]:
		"""Return cache-safe exact Stage 6 input/result provenance."""
		return {
			"report_date": self.report_date,
			"daily_outline_id": self.stage6_input.daily_outline.content_hash,
			"repo_story_ids": sorted(item.content_hash for item in self.stage6_input.repo_stories),
			"packet_ids": sorted(
				daily_blog.schema.model_cache_packet_identity(item)
				for item in self.stage6_input.packets
			),
			"model_context_id": self.stage6_input.evidence_context.model_context_id,
			"publication_surface_packet_id": self.stage6_input.publication_surface.packet.packet_id,
			"publication_surface_projection_id": self.stage6_input.publication_surface.projection.projection_id,
			"output_root": self.stage6_input.output_root,
			"output_path": self.stage6_input.output_path,
			"incumbent_id": self.incumbent.content_hash,
			"incumbent_hash": self.incumbent.content_hash,
		}

	def model_identity_dict(self) -> dict[str, object]:
		"""Return model-safe provenance without filesystem locations."""
		value = self.identity_dict()
		value.pop("output_root")
		value.pop("output_path")
		value.pop("publication_surface_packet_id")
		value.pop("publication_surface_projection_id")
		return value

	@property
	def identity_sha256(self) -> str:
		"""Bind every Stage 7 request to one immutable Stage 6 boundary."""
		return daily_blog.io_utils.hash_value(self.identity_dict())


#============================================
@dataclasses.dataclass(frozen=True)
class Stage7Result:
	"""Inspectable synthesis, balanced review, and truthful selected post."""
	promotion: (daily_blog.artifacts.SelectedPeer | daily_blog.artifacts.PreservedArtifact
		| daily_blog.artifacts.DegradedPromotion | daily_blog.artifacts.NoArtifact)
	synthesis: daily_blog.replication.ReplicationResult
	review: daily_blog.replication.ReviewResult
	step_reliability: tuple[daily_blog.replication.StepReliability, ...]
	incumbent: daily_blog.artifacts.CompletePost
	reviewer_count: int

	def __post_init__(self) -> None:
		if isinstance(self.promotion, daily_blog.artifacts.NoArtifact):
			raise RuntimeError("Stage 7 must preserve its Stage 6 incumbent, never return NoArtifact.")
		if type(self.synthesis) is not daily_blog.replication.ReplicationResult:
			raise RuntimeError("Stage 7 synthesis observation is invalid.")
		if type(self.review) is not daily_blog.replication.ReviewResult:
			raise RuntimeError("Stage 7 review observation is invalid.")
		if type(self.incumbent) is not daily_blog.artifacts.CompletePost:
			raise RuntimeError("Stage 7 requires the exact Stage 6 CompletePost incumbent.")
		if type(self.reviewer_count) is not int or self.reviewer_count <= 0:
			raise RuntimeError("Stage 7 requires the configured positive reviewer count.")
		if len(self.step_reliability) != 3 or any(
			type(item) is not daily_blog.replication.StepReliability for item in self.step_reliability
		) or tuple(item.step for item in self.step_reliability) != ("7.1", "7.2", "7.3"):
			raise RuntimeError("Stage 7 requires exact 7.1 through 7.3 reliability facts.")
		if self.synthesis_won:
			self._validate_selected_synthesis()
		elif self.promotion.artifact is not self.incumbent:
			raise RuntimeError("Stage 7 may preserve only its exact Stage 6 incumbent object.")

	@property
	def artifact(self) -> daily_blog.artifacts.CompletePost:
		"""Return the selected exact post; Stage 7 never has a no-artifact normal result."""
		if type(self.promotion.artifact) is not daily_blog.artifacts.CompletePost:
			raise RuntimeError("Stage 7 promotion lost the CompletePost incumbent.")
		return self.promotion.artifact

	@property
	def synthesis_won(self) -> bool:
		"""Tell recovery owners whether FINAL_SYNTHESIS was genuinely earned."""
		return isinstance(self.promotion, daily_blog.artifacts.SelectedPeer)

	@property
	def direct_incumbent_comparison(self) -> bool:
		"""Return derived direct-comparison truth, never caller-supplied authority."""
		return self.synthesis_won

	def _validate_selected_synthesis(self) -> None:
		"""Bind a replacement to its eligible synthesis and complete direct vote work."""
		challenger = self.promotion.artifact
		if challenger is self.incumbent:
			raise RuntimeError("Stage 7 selected synthesis must differ from its incumbent.")
		if not any(candidate.artifact is challenger and _eligible_candidate(candidate) for candidate in self.synthesis.candidates):
			raise RuntimeError("Stage 7 selected synthesis is absent from eligible generation.")
		peers = _stage7_peers(self.incumbent, self.synthesis)
		expected = _expected_review_schedule(peers, self.reviewer_count)
		work_by_assignment = {item.assignment: item for item in self.review.work}
		if len(work_by_assignment) != len(self.review.work) or set(work_by_assignment) != set(expected):
			raise RuntimeError("Stage 7 review work does not attest the complete balanced schedule.")
		for assignment, item in work_by_assignment.items():
			first, second = expected[assignment]
			if (item.first_artifact_id, item.second_artifact_id) != (first, second):
				raise RuntimeError("Stage 7 review work orientation conflicts with its assignment.")
		work_by_id = {item.request.request_id: item for item in self.review.work}
		if len(work_by_id) != len(self.review.work):
			raise RuntimeError("Stage 7 review work identities are not unique.")
		votes_by_id = {item.review_id: item for item in self.review.votes}
		if len(votes_by_id) != len(self.review.votes) or set(votes_by_id) != set(work_by_id):
			raise RuntimeError("Stage 7 review votes do not exactly attest review work.")
		direct_work = [item for item in self.review.work if {
			item.first_artifact_id, item.second_artifact_id,
		} == {challenger.artifact_id, self.incumbent.artifact_id}]
		if not direct_work:
			raise RuntimeError("Stage 7 selected synthesis lacks direct incumbent work.")
		direct_votes = [votes_by_id[item.request.request_id] for item in direct_work]
		if any(
			vote.status != "succeeded"
			or (vote.first_artifact_id, vote.second_artifact_id) != (
				work_by_id[vote.review_id].first_artifact_id,
				work_by_id[vote.review_id].second_artifact_id,
			)
			for vote in direct_votes
		):
			raise RuntimeError("Stage 7 direct incumbent votes are incomplete or invalid.")
		if sum(vote.winner_artifact_id == challenger.artifact_id for vote in direct_votes) <= sum(
			vote.winner_artifact_id == self.incumbent.artifact_id for vote in direct_votes
		):
			raise RuntimeError("Stage 7 selected synthesis lacks a direct incumbent majority.")


#============================================
def _eligible(value: Stage7Input, item: daily_blog.artifacts.EditorialArtifact) -> daily_blog.artifacts.EligibilityResult:
	"""Use the trusted Stage 6 publication target for every peer."""
	if type(item) is not daily_blog.artifacts.CompletePost:
		return daily_blog.artifacts.EligibilityResult(False, ("invalid_machine_metadata",))
	return daily_blog.publication_admission.complete_post_eligibility(
		item, value.stage6_input.publication_surface, value.stage6_input.output_root,
	)


#============================================
def _eligible_candidate(candidate: daily_blog.replication.ReplicatedCandidate) -> bool:
	"""Recognize the exact shared mechanical eligibility observation."""
	return candidate.eligibility is not None and candidate.eligibility.eligible


#============================================
def _stage6_generation_streams(
	result: daily_blog.stage6.Stage6Result,
) -> tuple[daily_blog.replication.ReplicationResult, ...]:
	"""Return the named Stage-6 artifact streams without manufacturing recovery."""
	streams = (result.generation, result.editing)
	if result.recovery_generation is not None:
		streams += (result.recovery_generation,)
	if any(
		type(stream) is not daily_blog.replication.ReplicationResult
		or stream.expected_type is not daily_blog.artifacts.CompletePost
		for stream in streams
	):
		raise RuntimeError("Stage 7 Stage 6 generation provenance is invalid.")
	return streams


#============================================
def _is_stage6_lineage_incumbent(value: Stage7Input, incumbent: daily_blog.artifacts.CompletePost) -> bool:
	"""Require the promoted object to be an observed eligible Stage 6 peer."""
	promotion = value.stage6_result.promotion
	if not isinstance(promotion, (daily_blog.artifacts.SelectedPeer, daily_blog.artifacts.PreservedArtifact,
		daily_blog.artifacts.DegradedPromotion)) or promotion.artifact is not incumbent:
		return False
	for result in _stage6_generation_streams(value.stage6_result):
		for candidate in result.candidates:
			if candidate.artifact is incumbent and _eligible_candidate(candidate) and _matches_stage6_target(value, incumbent):
				return True
	return False


#============================================
def _matches_stage6_target(value: Stage7Input, item: object) -> bool:
	"""Require the same date, packet scope, repository scope, and destination."""
	if type(item) is not daily_blog.artifacts.CompletePost:
		return False
	stage6 = value.stage6_input
	return (
		item.report_date == stage6.report_date
		and item.packet_ids == tuple(packet.packet_id for packet in stage6.packets)
		and bool(item.repositories)
		and set(item.repositories).issubset(stage6.daily_outline.repositories)
		and item.publication_id == stage6.report_date
		and item.output_path == stage6.output_path
		and _eligible(value, item).eligible
	)


#============================================
def _unique(items: collections.abc.Iterable[daily_blog.artifacts.CompletePost]) -> tuple[daily_blog.artifacts.CompletePost, ...]:
	"""Identity-deduplicate reference alternatives in stable order."""
	return tuple(sorted({item.artifact_id: item for item in items}.values(),
		key=lambda item: (item.content_hash, item.artifact_id)))


#============================================
def _alternatives(value: Stage7Input) -> tuple[daily_blog.artifacts.CompletePost, ...]:
	"""Derive independently eligible writer, editor, and named recovery alternatives."""
	values = []
	for result in _stage6_generation_streams(value.stage6_result):
		for item in result.eligible:
			if type(item) is daily_blog.artifacts.CompletePost and _matches_stage6_target(value, item):
				values.append(item)
	return tuple(item for item in _unique(values) if item.artifact_id != value.incumbent.artifact_id)


#============================================
def _stage7_peers(incumbent: daily_blog.artifacts.CompletePost,
	synthesis: daily_blog.replication.ReplicationResult) -> tuple[daily_blog.artifacts.CompletePost, ...]:
	"""Return the canonical attested peer set from eligible synthesis observations."""
	return _unique((incumbent,) + tuple(
		item.artifact for item in synthesis.candidates
		if type(item.artifact) is daily_blog.artifacts.CompletePost and _eligible_candidate(item)
	))


#============================================
def _expected_review_schedule(peers: tuple[daily_blog.artifacts.CompletePost, ...],
	reviewer_count: int,
) -> dict[daily_blog.replication.ReviewAssignment, tuple[str, str]]:
	"""Build the generic complete balanced work matrix without trusting observed work."""
	expected = {}
	pair_index = 0
	for first_index, first in enumerate(peers):
		for second in peers[first_index + 1:]:
			for reviewer_index in range(reviewer_count):
				for display_order in range(2):
					assignment = daily_blog.replication.ReviewAssignment(pair_index, reviewer_index, display_order)
					expected[assignment] = ((first.artifact_id, second.artifact_id)
						if display_order == 0 else (second.artifact_id, first.artifact_id))
			pair_index += 1
	return expected


#============================================
def _canonical(value: object, maximum: int, label: str) -> str:
	"""Encode bounded data for the prompt contract without raw route diagnostics."""
	rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
	if len(rendered) > maximum:
		raise RuntimeError(f"Stage 7 {label} exceeds its bounded prompt limit.")
	return rendered


#============================================
def _review_facts(value: Stage7Input, maximum: int) -> str:
	"""Project only bounded Stage 6 vote identities and statuses."""
	artifacts = (value.incumbent,) + tuple(
		item.artifact for item in value.stage6_result.generation.candidates
		if item.artifact is not None
	)
	artifacts += tuple(
		item.artifact for item in value.stage6_result.editing.candidates
		if item.artifact is not None
	)
	aliases = {item.artifact_id: item.content_hash for item in artifacts}
	votes = [{"review_id": vote.review_id, "first_artifact_id": aliases.get(vote.first_artifact_id, ""),
		"second_artifact_id": aliases.get(vote.second_artifact_id, ""), "status": vote.status,
		"winner_artifact_id": aliases.get(vote.winner_artifact_id, ""), "failure": vote.failure,
		"repaired": vote.repaired, "resumed": vote.resumed} for vote in value.stage6_result.review.votes]
	reliability = []
	for item in value.stage6_result.step_reliability:
		projected = item.to_dict()
		projected["best_artifact_id"] = aliases.get(projected["best_artifact_id"], "")
		reliability.append(projected)
	votes.sort(key=lambda item: (item["first_artifact_id"], item["second_artifact_id"], item["review_id"]))
	return _canonical({"votes": votes, "reliability": reliability}, maximum, "review facts")


#============================================
def _model_post(item: daily_blog.artifacts.CompletePost) -> dict[str, object]:
	"""Project a CompletePost for model input without coordinator filesystem paths."""
	return {
		"report_date": item.report_date,
		"repositories": list(item.repositories),
		"content": item.content,
		"content_hash": item.content_hash,
		"evidence_ids": list(item.evidence_ids),
		"publication_id": item.publication_id,
	}


#============================================
def _prompt_data(value: Stage7Input, alternatives: tuple[daily_blog.artifacts.CompletePost, ...],
	templates: dict[str, str], identity: dict[str, object], limits: dict[str, int],
	prompt_set: daily_blog.prompt_registry.loader.LoadedPromptSet,
) -> tuple[str, dict[str, object]]:
	"""Construct the frozen bounded synthesis prompt and its provenance identity."""
	incumbent = _canonical(_model_post(value.incumbent), limits["incumbent_chars"], "incumbent")
	alternative_json = _canonical([_model_post(item) for item in alternatives],
		limits["alternatives_chars"], "alternatives")
	if limits["evidence_chars"] < value.stage6_input.evidence_context.context_chars:
		raise RuntimeError("Stage 7 evidence budget cannot retain the Stage 6 bounded context.")
	evidence = value.stage6_input.evidence_context.render_context(
		value.stage6_input.evidence_context.context_chars,
	)
	rubric = _canonical({"version": identity["rubric_version"], "text": templates["rubric"]},
		limits["rubric_chars"], "rubric")
	provenance = _canonical({"stage6_input": value.model_identity_dict(), "stage6_input_identity": daily_blog.io_utils.hash_value(value.model_identity_dict()),
		"prompt": identity, "model_context_id": value.stage6_input.evidence_context.model_context_id,
		"alternative_ids": [item.content_hash for item in alternatives]},
		limits["provenance_chars"], "provenance")
	review_facts = _review_facts(value, limits["review_facts_chars"])
	return daily_blog.final_synthesis_prompts.render_final_synthesis_prompt(
		value.report_date, incumbent, alternative_json, review_facts, rubric, evidence, provenance,
		prompt_set,
	), {"alternatives": [item.content_hash for item in alternatives], "review_facts": review_facts,
		"prompt": identity, "rubric_version": identity["rubric_version"],
		"model_context_id": value.stage6_input.evidence_context.model_context_id}


#============================================
def _request(value: Stage7Input, run_id: str, step: str, role: str, ordinal: str,
	route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, config: daily_blog.final_synthesis_config.FinalSynthesisConfig,
	working_directory: str, contract_version: str, synthesis_identity: dict[str, object],
	input_ids: tuple[str, ...] = (), assignment: daily_blog.replication.ReviewAssignment | None = None,
	repair_of: str = "") -> daily_blog.agents.RouteRequest:
	"""Bind each independent route/cache identity to exact Stage 6 and V4 facts."""
	assignment_data = {} if assignment is None else dataclasses.asdict(assignment)
	logical_input = {"report_date": value.report_date,
		"stage6_input": daily_blog.io_utils.hash_value(value.model_identity_dict()),
		"model_context_id": value.stage6_input.evidence_context.model_context_id,
		"incumbent_id": value.incumbent.content_hash,
		"input_ids": list(input_ids), "synthesis": synthesis_identity, "step": step,
		"role": role, "ordinal": ordinal,
		"v4_contract": contract_version, "assignment": assignment_data}
	cache_input_hash = daily_blog.io_utils.hash_value(logical_input)
	input_hash = daily_blog.io_utils.hash_value({"run_id": run_id, "logical": logical_input,
		"output_path": value.stage6_input.output_path})
	return daily_blog.agents.RouteRequest(
		request_id=f"stage7_{step}_{role}_{ordinal}_{cache_input_hash[:12]}", step="stage7_" + step,
		route=route, prompt=prompt, working_directory=working_directory, role=role,
		retry_attempts=config.route_retry_attempts, maximum_parallel_calls=config.maximum_parallel_calls,
		repair_of=repair_of, input_hash=input_hash, contract_version=contract_version,
		cache_input_hash=cache_input_hash,
	)


#============================================
def _parse_synthesis_candidate(
	result: daily_blog.agents.AgentResult, value: Stage7Input,
) -> daily_blog.artifacts.CompletePost:
	"""Classify model-shaped synthesis loss as degradation, not a pipeline fault."""
	try:
		candidate = daily_blog.final_synthesis_prompts.parse_final_synthesis_complete_post(
			result.text, value.report_date, value.stage6_input.packets,
			value.stage6_input.daily_outline.repositories, value.stage6_input.output_path,
			value.stage6_input.output_root,
		)
		if not _matches_stage6_target(value, candidate):
			raise RuntimeError("Final synthesis candidate conflicts with its trusted Stage 6 target.")
		return candidate
	except RuntimeError as error:
		raise daily_blog.agents.RepairableStructuredOutput(str(error)) from error


#============================================
def _generation_reliability(result: daily_blog.replication.ReplicationResult) -> daily_blog.replication.StepReliability:
	"""Report synthesis loss as editorial degradation, never a missing incumbent."""
	failures = {item.failure for item in result.candidates if item.failure}
	if any(item.result.ok and (item.eligibility is None or not item.eligibility.eligible) for item in result.candidates):
		failures.add("ineligible_generation")
	succeeded = sum(item.eligibility is not None and item.eligibility.eligible for item in result.candidates)
	return daily_blog.replication.StepReliability("7.1", "degraded" if failures else "succeeded",
		len(result.candidates), succeeded, len(result.candidates) - succeeded,
		sum(item.result.ok and item.result.resumed for item in result.candidates), 0, 0, "", tuple(sorted(failures)))


#============================================
def _disagreements(votes: collections.abc.Iterable[daily_blog.replication.ReviewVote]) -> int:
	"""Count only contradictory successful peer verdicts."""
	pairs: dict[tuple[str, str], set[str]] = {}
	for vote in votes:
		if vote.status == "succeeded":
			pairs.setdefault(tuple(sorted((vote.first_artifact_id, vote.second_artifact_id))), set()).add(vote.winner_artifact_id)
	return sum(len(winners) > 1 for winners in pairs.values())


#============================================
def _result(value: Stage7Input, synthesis: daily_blog.replication.ReplicationResult,
	review: daily_blog.replication.ReviewResult, promotion: object, reviewer_count: int) -> Stage7Result:
	"""Build exact 7.x facts while preserving the original incumbent object."""
	seven_one = _generation_reliability(synthesis)
	disagreements = _disagreements(review.votes)
	reasons = set(daily_blog.replication.review_reasons(review.votes, disagreements))
	if not review.work and synthesis.eligible:
		reasons.add("review_unavailable")
	seven_two = daily_blog.replication.StepReliability("7.2", "degraded" if reasons else "succeeded",
		len(review.votes), sum(vote.status == "succeeded" for vote in review.votes),
		sum(vote.status == "failed" for vote in review.votes), 0,
		sum(vote.status == "succeeded" and vote.repaired for vote in review.votes), disagreements, "", tuple(sorted(reasons)))
	if isinstance(promotion, daily_blog.artifacts.SelectedPeer):
		promotion_reasons, best = (), promotion.artifact.artifact_id
	else:
		promotion_reasons, best = ("incumbent_preserved",), value.incumbent.artifact_id
	seven_three = daily_blog.replication.StepReliability("7.3", "degraded" if promotion_reasons else "succeeded",
		1, 1, 0, 0, 0, disagreements, best, promotion_reasons)
	return Stage7Result(promotion, synthesis, review, (seven_one, seven_two, seven_three), value.incumbent, reviewer_count)


#============================================
def run_stage7(value: Stage7Input, run_id: str, config: daily_blog.config.DailyBlogConfig,
	budget: daily_blog.agents.RouteBudget, runner: object | None = None,
	contract: daily_blog.prompt_registry.definitions.EditorialContract | None = None,
	selection: daily_blog.prompt_registry.definitions.ExampleSelection | None = None,
	snapshot: daily_blog.editorial.PromptContractSnapshot | None = None,
	cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None = None,
	cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None = None,
) -> Stage7Result:
	"""Run independent synthesis then promote only direct-review-proven improvement."""
	if type(value) is not Stage7Input or type(run_id) is not str or not run_id:
		raise RuntimeError("Stage 7 requires exact input and a nonempty run identity.")
	if type(config.final_synthesis) is not daily_blog.final_synthesis_config.FinalSynthesisConfig:
		raise RuntimeError("Stage 7 requires exact final-synthesis configuration.")
	if type(budget) is not daily_blog.agents.RouteBudget:
		raise RuntimeError("Stage 7 requires the coordinator-owned RouteBudget.")
	resolved = daily_blog.editorial.resolve_snapshot(contract, selection, snapshot)
	templates = daily_blog.editorial.validate_prompt_templates(snapshot=resolved)
	prompt_set = daily_blog.prompt_registry.loader.resolve_loaded_prompt_set(
		daily_blog.prompt_registry.loader.load_prompt_set(daily_blog.prompt_registry.definitions.FINAL_SYNTHESIS_PROMPT_SET),
		daily_blog.prompt_registry.definitions.FINAL_SYNTHESIS_PROMPT_SET,
	)
	prompt_identity = daily_blog.final_synthesis_prompts.final_synthesis_prompt_identity(prompt_set)
	identity = {**prompt_identity, "rubric_version": resolved.contract.prompt_version,
		"rubric_sha256": daily_blog.io_utils.sha256_text(templates["rubric"]),
		"v4_contract": resolved.contract.prompt_version}
	stage = config.final_synthesis
	limits = {
		"incumbent_chars": min(stage.prompt_limits["incumbent_chars"], daily_blog.final_synthesis_prompts.MAX_INCUMBENT_POST_CHARS),
		"alternatives_chars": min(stage.prompt_limits["alternatives_chars"], daily_blog.final_synthesis_prompts.MAX_ALTERNATIVE_POSTS_CHARS),
		"review_facts_chars": min(stage.prompt_limits["review_facts_chars"], daily_blog.final_synthesis_prompts.MAX_STAGE6_REVIEW_CHARS),
		"rubric_chars": min(stage.prompt_limits["rubric_chars"], daily_blog.final_synthesis_prompts.MAX_RUBRIC_CHARS),
		"evidence_chars": min(stage.prompt_limits["evidence_chars"], daily_blog.final_synthesis_prompts.MAX_EVIDENCE_CHARS),
		"provenance_chars": min(stage.prompt_limits["provenance_chars"], daily_blog.final_synthesis_prompts.MAX_PROVENANCE_CHARS),
	}
	alternatives = _alternatives(value)
	prompt, synthesis_identity = _prompt_data(value, alternatives, templates, identity, limits, prompt_set)
	if len(prompt) > min(stage.prompt_limits["rendered_prompt_chars"], daily_blog.final_synthesis_prompts.MAX_RENDERED_PROMPT_CHARS):
		raise RuntimeError("Stage 7 synthesis prompt exceeds its configured limit.")
	route_runner = runner if runner is not None else daily_blog.routes.CommandRouteRunner()
	requests = tuple(_request(value, run_id, "7_1", "synthesizer", str(index + 1), stage.synthesis_route,
		prompt, stage, config.daily_blog_repository, resolved.contract.prompt_version, synthesis_identity,
		(value.incumbent.content_hash,) + tuple(item.content_hash for item in alternatives))
		for index in range(stage.synthesizer_count))
	synthesis = daily_blog.replication.replicate(requests, route_runner, budget, daily_blog.artifacts.CompletePost,
		lambda result: _parse_synthesis_candidate(result, value), lambda item: _eligible(value, item), cache_load, cache_accept)
	challengers = _unique(item for item in synthesis.eligible if item.artifact_id != value.incumbent.artifact_id)
	if not challengers:
		return _result(value, synthesis, daily_blog.replication.ReviewResult((), ()),
			daily_blog.artifacts.PreservedArtifact(value.incumbent, daily_blog.artifacts.CompletePost), stage.reviewer_count)
	peers = _unique((value.incumbent,) + challengers)

	def build(left: daily_blog.artifacts.EditorialArtifact, right: daily_blog.artifacts.EditorialArtifact,
		assignment: daily_blog.replication.ReviewAssignment) -> daily_blog.replication.ReviewWork:
		prompt = templates["referee"].format(rubric=templates["rubric"], evidence_json=value.stage6_input.render_context(),
			candidate_a=left.content, candidate_b=right.content)
		request = _request(value, run_id, "7_2", "reviewer",
			f"{assignment.pair_index}_{assignment.reviewer_index}_{assignment.display_order}", stage.reviewer_route,
			prompt, stage, config.daily_blog_repository, resolved.contract.prompt_version, synthesis_identity,
			(left.content_hash, right.content_hash), assignment)
		return daily_blog.replication.ReviewWork(request, left.artifact_id, right.artifact_id, assignment)

	def parse(text: str, work: daily_blog.replication.ReviewWork) -> str:
		try:
			verdict = daily_blog.editorial.parse_referee_verdict(text, {"A", "B"})
		except daily_blog.editorial.RefereeVerdictParseError as error:
			raise daily_blog.agents.RepairableStructuredOutput(str(error)) from error
		return {"A": work.first_artifact_id, "B": work.second_artifact_id}.get(verdict["winner"], "")

	def repair(work: daily_blog.replication.ReviewWork, response: str) -> daily_blog.replication.ReviewWork:
		prompt = templates["repair"].format(response=response[:daily_blog.editorial.MAX_REFEREE_RESPONSE_CHARS])
		request = _request(value, run_id, "7_2_repair", "reviewer_repair", work.request.request_id,
			stage.reviewer_route, prompt, stage, config.daily_blog_repository, resolved.contract.prompt_version,
			synthesis_identity, (daily_blog.io_utils.sha256_text(response),), work.assignment, work.request.cache_input_hash)
		return daily_blog.replication.ReviewWork(request, work.first_artifact_id, work.second_artifact_id, work.assignment)

	def salvage(text: str, work: daily_blog.replication.ReviewWork) -> str | None:
		label = daily_blog.replication.salvage_allowed_identifier(text, ("A", "B"))
		return {"A": work.first_artifact_id, "B": work.second_artifact_id}.get(label)

	review = daily_blog.replication.review(peers, daily_blog.artifacts.CompletePost, stage.reviewer_count,
		build, parse, route_runner, budget, repair, salvage, cache_load, cache_accept)
	promotion = daily_blog.replication.promote(peers, daily_blog.artifacts.CompletePost,
		lambda item: _eligible(value, item), review.votes, value.incumbent)
	if not isinstance(promotion, daily_blog.artifacts.SelectedPeer):
		promotion = daily_blog.artifacts.PreservedArtifact(value.incumbent, daily_blog.artifacts.CompletePost)
	return _result(value, synthesis, review, promotion, stage.reviewer_count)

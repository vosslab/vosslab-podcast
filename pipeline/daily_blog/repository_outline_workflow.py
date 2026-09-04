"""Pure replicated Stage 3 repository-outline editorial workflow."""

# Standard Library
import collections.abc
import dataclasses
import datetime
import json
import os

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.candidate_set_prompts
import daily_blog.config
import daily_blog.editorial_stage_config
import daily_blog.io_utils
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.loader
import daily_blog.replication
import daily_blog.repository_outline_prompts
import daily_blog.routes
import daily_blog.schema


@dataclasses.dataclass(frozen=True)
class RepositoryOutlineInput:
	"""One repository-scoped, immutable evidence boundary for Stage 3."""

	packet: daily_blog.schema.EvidencePacket
	repository: str
	working_directory: str
	model_evidence_context: str | None = None

	#============================================
	def __post_init__(self) -> None:
		"""Reject an ambiguous repository before any model route is admitted."""
		if type(self.packet) is not daily_blog.schema.EvidencePacket:
			raise RuntimeError("Repository-outline input requires one exact EvidencePacket.")
		if type(self.repository) is not str or not self.repository:
			raise RuntimeError("Repository-outline input requires one repository identity.")
		if type(self.working_directory) is not str or not os.path.isabs(self.working_directory):
			raise RuntimeError("Repository-outline input requires an absolute working directory.")
		if not os.path.isdir(os.path.realpath(self.working_directory)):
			raise RuntimeError("Repository-outline input working directory must exist.")
		try:
			datetime.date.fromisoformat(self.packet.report_date)
		except (TypeError, ValueError) as error:
			raise RuntimeError("Repository-outline input packet report date is invalid.") from error
		# Reparse before rendering so hand-built packet instances cannot bypass the
		# same exact evidence schema used at collection and cache boundaries.
		daily_blog.schema.EvidencePacket.from_dict(self.packet.to_dict())
		if {item.repository for item in self.packet.items} != {self.repository}:
			raise RuntimeError("Repository-outline input packet must isolate one repository.")
		if self.packet.packet_id != daily_blog.io_utils.hash_value(self.packet.content_dict()):
			raise RuntimeError("Repository-outline input packet identity is invalid.")
		if self.model_evidence_context is not None and (
			type(self.model_evidence_context) is not str or not self.model_evidence_context
			or len(self.model_evidence_context) > daily_blog.repository_outline_prompts.MAX_EVIDENCE_CONTEXT_CHARS
		):
			raise RuntimeError("Repository-outline model evidence context is invalid.")

	#============================================
	@property
	def report_date(self) -> str:
		"""Expose the sole report identity carried by the authoritative packet."""
		return self.packet.report_date

	#============================================
	@property
	def allowed_repositories(self) -> tuple[str, ...]:
		"""Expose the coordinator-owned singleton evidence ceiling for Stage 3."""
		return (self.repository,)

	#============================================
	def render_evidence(self) -> str:
		"""Return canonical bounded evidence without prior model conversation."""
		value = self.model_evidence_context or json.dumps(
			daily_blog.schema.model_cache_packet_content(self.packet), sort_keys=True,
			separators=(",", ":"), ensure_ascii=True,
		)
		if len(value) > daily_blog.repository_outline_prompts.MAX_EVIDENCE_CONTEXT_CHARS:
			raise RuntimeError("Repository-outline evidence context exceeds its bounded limit.")
		return value


@dataclasses.dataclass(frozen=True)
class RepositoryOutlineResult:
	"""Non-durable Stage 3 observations and its exact-rung promotion."""

	promotion: (
		daily_blog.artifacts.SelectedPeer | daily_blog.artifacts.PreservedArtifact
		| daily_blog.artifacts.DegradedPromotion | daily_blog.artifacts.NoArtifact
	)
	generation: daily_blog.replication.ReplicationResult
	merger: daily_blog.replication.ReplicationResult
	review: daily_blog.replication.CandidateSetReviewResult
	reliability: tuple[daily_blog.replication.StepReliability, ...]

	#============================================
	def __post_init__(self) -> None:
		"""Keep the public result exact, bounded, and coordinator-serializable."""
		if type(self.generation) is not daily_blog.replication.ReplicationResult:
			raise RuntimeError("Repository-outline generation observation is invalid.")
		if type(self.merger) is not daily_blog.replication.ReplicationResult:
			raise RuntimeError("Repository-outline merger observation is invalid.")
		if type(self.review) is not daily_blog.replication.CandidateSetReviewResult:
			raise RuntimeError("Repository-outline review observation is invalid.")
		if type(self.reliability) is not tuple or tuple(item.step for item in self.reliability) != (
			"3.1", "3.2", "3.3", "3.4",
		):
			raise RuntimeError("Repository-outline reliability must contain Steps 3.1 through 3.4.")
		for item in self.reliability:
			if type(item) is not daily_blog.replication.StepReliability:
				raise RuntimeError("Repository-outline reliability observation is invalid.")
			item.validate()

	#============================================
	@property
	def artifact(self) -> daily_blog.artifacts.RepoOutline | None:
		"""Return the promoted artifact without hiding a typed no-artifact outcome."""
		if isinstance(self.promotion, daily_blog.artifacts.NoArtifact):
			return None
		return self.promotion.artifact


#============================================
def _request(
	value: RepositoryOutlineInput,
	stage: str,
	role: str,
	ordinal: str,
	route: daily_blog.editorial_stage_config.RoleRoute,
	prompt: str,
	config: daily_blog.editorial_stage_config.RepositoryOutlineConfig,
	contract_identity: dict[str, object],
	input_artifact_ids: tuple[str, ...] = (),
	assignment: daily_blog.replication.CandidateSetReviewAssignment | None = None,
) -> daily_blog.agents.RouteRequest:
	"""Build one cache-safe request that attests to all Stage 3 inputs."""
	assignment_value = {} if assignment is None else dataclasses.asdict(assignment)
	logical_identity = {
		"report_date": value.report_date,
		"repository": value.repository,
		"packet_id": daily_blog.schema.model_cache_packet_identity(value.packet),
		"step": stage,
		"role": role,
		"replica": ordinal,
		"input_artifact_ids": list(input_artifact_ids),
		"prompt_identity": contract_identity,
		"assignment": assignment_value,
	}
	cache_input_hash = daily_blog.io_utils.hash_value(logical_identity)
	input_hash = daily_blog.io_utils.hash_value({
		"logical": logical_identity, "working_directory": os.path.realpath(value.working_directory),
	})
	return daily_blog.agents.RouteRequest(
		request_id=f"stage3_{stage}_{role}_{ordinal}_{cache_input_hash[:12]}", step=f"repository_outline_{stage}",
		route=route, prompt=prompt, working_directory=os.path.realpath(value.working_directory), role=role,
		retry_attempts=config.route_retry_attempts,
		maximum_parallel_calls=config.maximum_parallel_calls,
		input_hash=input_hash,
		contract_version=(daily_blog.repository_outline_prompts.REPOSITORY_OUTLINE_PROMPT_CONTRACT
			+ ":" + str(contract_identity["integrity_sha256"])),
		cache_input_hash=cache_input_hash,
	)


#============================================
def _outline(value: RepositoryOutlineInput, result: daily_blog.agents.AgentResult) -> daily_blog.artifacts.RepoOutline:
	"""Parse one whole outline and attach packet provenance when the model omits it."""
	content = result.text.rstrip() + "\n"
	content, evidence_ids = daily_blog.artifacts.ensure_evidence_references(
		content, tuple(sorted(item.evidence_id for item in value.packet.items)),
	)
	return daily_blog.artifacts.RepoOutline.create(
		value.report_date, (value.packet,), value.repository, content, evidence_ids,
		daily_blog.artifacts.referenced_image_paths(content),
	)


#============================================
def _eligible(
	value: RepositoryOutlineInput,
	item: daily_blog.artifacts.EditorialArtifact,
) -> daily_blog.artifacts.EligibilityResult:
	"""Apply the shared mechanical gate to the one repository scope."""
	return daily_blog.artifacts.evaluate_eligibility(
		item, (value.packet,), allowed_repositories=value.allowed_repositories,
	)


#============================================
def _anonymous_outlines(items: collections.abc.Iterable[daily_blog.artifacts.RepoOutline]) -> str:
	"""Render canonical whole alternatives without source identities or positions."""
	ordered = tuple(sorted(items, key=lambda item: (item.content_hash, item.artifact_id)))
	value = json.dumps({"outlines": [{"content": item.content} for item in ordered]},
		sort_keys=True, separators=(",", ":"), ensure_ascii=True)
	if len(value) > daily_blog.repository_outline_prompts.MAX_CANDIDATE_OUTLINES_CHARS:
		raise RuntimeError("Repository-outline candidate context exceeds its bounded limit.")
	return value


#============================================
def _unique(items: collections.abc.Iterable[daily_blog.artifacts.RepoOutline]) -> tuple[daily_blog.artifacts.RepoOutline, ...]:
	"""Keep one canonical copy of equivalent same-rung editorial work."""
	return tuple(sorted({item.artifact_id: item for item in items}.values(),
		key=lambda item: (item.content_hash, item.artifact_id)))


#============================================
def _generation_reliability(
	step: str,
	generation: daily_blog.replication.ReplicationResult,
	additional_reasons: collections.abc.Iterable[str] = (),
) -> daily_blog.replication.StepReliability:
	"""Summarize only one replicated generation mechanism without a future winner."""
	candidates = generation.candidates
	reasons = set(additional_reasons)
	reasons.update(item.failure for item in candidates if item.failure)
	if any(item.result.ok and (item.eligibility is None or not item.eligibility.eligible)
		for item in candidates):
		reasons.add("ineligible_generation")
	attempted = len(candidates)
	succeeded = sum(
		item.result.ok and item.eligibility is not None and item.eligibility.eligible
		for item in candidates
	)
	return daily_blog.replication.StepReliability(
		step, "degraded" if reasons else "succeeded", attempted, succeeded, attempted - succeeded,
		sum(item.result.resumed and item.result.ok for item in candidates),
		0, 0, "", tuple(sorted(reasons)),
	)


#============================================
def _review_reliability(
	review: daily_blog.replication.CandidateSetReviewResult,
	promotion: object,
	additional_reasons: collections.abc.Iterable[str] = (),
) -> daily_blog.replication.StepReliability:
	"""Summarize reviewer calls only, retaining the reviewed final identity when present."""
	votes = review.votes
	reasons = set(additional_reasons)
	disagreements = daily_blog.replication.review_disagreements(votes)
	reasons.update(daily_blog.replication.review_reasons(votes, disagreements))
	best_artifact_id = ""
	if review.work and not isinstance(promotion, daily_blog.artifacts.NoArtifact):
		best_artifact_id = promotion.artifact.artifact_id
	return daily_blog.replication.StepReliability(
		"3.3", "degraded" if reasons else "succeeded", len(votes),
		sum(vote.status == "succeeded" for vote in votes),
		sum(vote.status == "failed" for vote in votes), 0,
		0, disagreements,
		best_artifact_id, tuple(sorted(reasons)),
	)


#============================================
def _promotion_reliability(
	promotion: (
		daily_blog.artifacts.SelectedPeer | daily_blog.artifacts.PreservedArtifact
		| daily_blog.artifacts.DegradedPromotion | daily_blog.artifacts.NoArtifact
	),
	votes: collections.abc.Iterable[daily_blog.replication.CandidateSetReviewVote],
) -> daily_blog.replication.StepReliability:
	"""Record promotion as one deterministic editorial decision, not duplicated review work."""
	vote_values = tuple(votes)
	disagreements = daily_blog.replication.review_disagreements(vote_values)
	reasons: tuple[str, ...] = ()
	best_artifact_id = ""
	if isinstance(promotion, daily_blog.artifacts.DegradedPromotion):
		reasons = promotion.reasons
		best_artifact_id = promotion.artifact.artifact_id
	elif isinstance(promotion, daily_blog.artifacts.NoArtifact):
		reasons = (promotion.reason,)
	else:
		best_artifact_id = promotion.artifact.artifact_id
	return daily_blog.replication.StepReliability(
		"3.4", "degraded" if reasons else "succeeded", 1, 1, 0, 0, 0, disagreements,
		best_artifact_id, reasons,
	)


#============================================
def run_repository_outline(
	value: RepositoryOutlineInput,
	config: daily_blog.editorial_stage_config.RepositoryOutlineConfig,
	budget: daily_blog.agents.RouteBudget,
	runner: object | None = None,
	loaded_prompts: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None,
	cache_load: collections.abc.Callable[
		[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None,
	] | None = None,
	cache_accept: collections.abc.Callable[
		[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None,
	] | None = None,
	incumbent: daily_blog.artifacts.RepoOutline | None = None,
) -> RepositoryOutlineResult:
	"""Run Stage 3.1--3.4 without persisting artifacts, events, or cache state."""
	if type(value) is not RepositoryOutlineInput:
		raise RuntimeError("Repository-outline workflow requires exact input.")
	if type(config) is not daily_blog.editorial_stage_config.RepositoryOutlineConfig:
		raise RuntimeError("Repository-outline workflow requires exact stage configuration.")
	if type(budget) is not daily_blog.agents.RouteBudget:
		raise RuntimeError("Repository-outline workflow requires the run-owned RouteBudget.")
	if incumbent is not None and type(incumbent) is not daily_blog.artifacts.RepoOutline:
		raise RuntimeError("Repository-outline incumbent must be an exact RepoOutline.")
	loaded_value = daily_blog.prompt_registry.loader.resolve_loaded_prompt_set(
		loaded_prompts, daily_blog.prompt_registry.definitions.REPOSITORY_OUTLINE_PROMPT_SET,
	)
	contract_identity = daily_blog.repository_outline_prompts.repository_outline_prompt_identity(loaded_value)
	evidence_json = value.render_evidence()
	route_runner = runner if runner is not None else daily_blog.routes.CommandRouteRunner()

	generator_requests = tuple(
		_request(value, "3_1", "generator", str(index + 1), config.generator_route,
			daily_blog.repository_outline_prompts.render_repository_outline_generator(
				evidence_json, "generator-" + str(index + 1), loaded_value,
			), config, contract_identity)
		for index in range(config.generator_count)
	)
	if any(len(request.prompt) > config.prompt_limits["generator_chars"] for request in generator_requests):
		raise RuntimeError("Repository-outline generator prompt exceeds its configured limit.")
	generation = daily_blog.replication.replicate(
		generator_requests, route_runner, budget, daily_blog.artifacts.RepoOutline,
		lambda result: _outline(value, result), lambda item: _eligible(value, item), cache_load, cache_accept,
	)
	generator_peers = _unique(generation.eligible)
	merger = daily_blog.replication.ReplicationResult(daily_blog.artifacts.RepoOutline, ())
	if generator_peers:
		candidate_json = _anonymous_outlines(generator_peers)
		merger_requests = tuple(
			_request(value, "3_2", "merger", str(index + 1), config.merger_route,
				daily_blog.repository_outline_prompts.render_repository_outline_merger(
					evidence_json, candidate_json, "merger-" + str(index + 1), loaded_value,
				), config, contract_identity,
				tuple(item.content_hash for item in generator_peers))
			for index in range(config.merger_count)
		)
		if any(len(request.prompt) > config.prompt_limits["merger_chars"] for request in merger_requests):
			merger_requests = ()
		if merger_requests:
			merger = daily_blog.replication.replicate(
				merger_requests, route_runner, budget, daily_blog.artifacts.RepoOutline,
				lambda result: _outline(value, result), lambda item: _eligible(value, item), cache_load, cache_accept,
			)
	merger_peers = _unique(merger.eligible)
	# Losing every merger admits a whole generator outline as a typed editorial degradation.
	peers = merger_peers or generator_peers
	if incumbent is not None and not _eligible(value, incumbent).eligible:
		raise RuntimeError("Repository-outline incumbent is not mechanically eligible.")
	if incumbent is not None:
		peers = _unique(peers + (incumbent,))
	if not peers:
		promotion = daily_blog.artifacts.NoArtifact(
			daily_blog.artifacts.RepoOutline, "no_eligible_generation",
		)
		empty_review = daily_blog.replication.CandidateSetReviewResult((), ())
		return RepositoryOutlineResult(
			promotion, generation, merger, empty_review, (
				_generation_reliability("3.1", generation),
				_generation_reliability("3.2", merger, ("upstream_unavailable",)),
				_review_reliability(empty_review, promotion, ("upstream_unavailable",)),
				_promotion_reliability(promotion, ()),
			),
		)

	review_prompts = daily_blog.candidate_set_prompts.load_prompt_set()
	review_identity = {
		**contract_identity,
		"candidate_set_review": review_prompts.identity_dict(),
	}
	review_identity["integrity_sha256"] = daily_blog.io_utils.hash_value(review_identity)

	def build_work(
		ordered: tuple[daily_blog.artifacts.EditorialArtifact, ...],
		assignment: daily_blog.replication.CandidateSetReviewAssignment,
	) -> daily_blog.replication.CandidateSetReviewWork:
		prompt, _labels = daily_blog.candidate_set_prompts.render_candidate_set_review(
			loaded_value.text(daily_blog.prompt_registry.definitions.REPOSITORY_OUTLINE_RUBRIC_RESOURCE),
			evidence_json, ordered, review_prompts,
		)
		if len(prompt) > config.prompt_limits["reviewer_chars"]:
			raise daily_blog.replication.ReviewUnavailable(
				"Repository-outline candidate-set prompt exceeds its configured limit."
			)
		request = _request(value, "3_3", "reviewer",
			str(assignment.reviewer_index), config.reviewer_route, prompt, config, review_identity,
			tuple(item.content_hash for item in ordered), assignment)
		return daily_blog.replication.CandidateSetReviewWork(request, assignment)

	def parse_winner(text: str, work: daily_blog.replication.CandidateSetReviewWork) -> str:
		labels = dict(zip(
			daily_blog.candidate_set_prompts.candidate_labels(len(work.assignment.candidate_artifact_ids)),
			work.assignment.candidate_artifact_ids, strict=True,
		))
		try:
			return daily_blog.candidate_set_prompts.parse_candidate_set_verdict(text, labels)
		except daily_blog.candidate_set_prompts.CandidateSetVerdictParseError as error:
			raise daily_blog.agents.RepairableStructuredOutput(str(error)) from error

	review = daily_blog.replication.review_candidate_set(
		peers, daily_blog.artifacts.RepoOutline, config.reviewer_count, build_work, parse_winner,
		route_runner, budget, cache_load, cache_accept,
	)
	promotion = daily_blog.replication.promote(
		peers, daily_blog.artifacts.RepoOutline, lambda item: _eligible(value, item), review.votes, incumbent,
	)
	if not merger_peers and generator_peers:
		# This is an editorial recovery onto the same typed rung, never a hidden
		# success or a local reconstruction of fragments from multiple outlines.
		if isinstance(promotion, daily_blog.artifacts.SelectedPeer):
			promotion = daily_blog.artifacts.DegradedPromotion(
				promotion.artifact, daily_blog.artifacts.RepoOutline, ("merger_unavailable",),
			)
		elif isinstance(promotion, daily_blog.artifacts.DegradedPromotion):
			promotion = daily_blog.artifacts.DegradedPromotion(
				promotion.artifact, daily_blog.artifacts.RepoOutline,
				tuple(sorted(set(promotion.reasons) | {"merger_unavailable"})),
			)
	merger_degradation = () if merger_peers else ("merger_unavailable",)
	review_degradation = () if review.work else ("review_unavailable",)
	return RepositoryOutlineResult(
		promotion, generation, merger, review, (
			_generation_reliability("3.1", generation),
			_generation_reliability("3.2", merger, merger_degradation),
			_review_reliability(review, promotion, review_degradation),
			_promotion_reliability(promotion, review.votes),
		),
	)

"""Pure replicated Stage 4 repository-story editorial workflow."""

# Standard Library
import collections.abc
import dataclasses
import datetime
import json
import os
import re

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.config
import daily_blog.editorial_stage_config
import daily_blog.io_utils
import daily_blog.replication
import daily_blog.repository_story_prompts
import daily_blog.routes
import daily_blog.schema


_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


@dataclasses.dataclass(frozen=True)
class RepositoryStoryInput:
	"""One exact promoted-outline and evidence boundary for Stage 4."""

	outline: daily_blog.artifacts.RepoOutline
	packets: tuple[daily_blog.schema.EvidencePacket, ...]
	working_directory: str

	#============================================
	def __post_init__(self) -> None:
		"""Validate immutable repository scope before any route is admitted.

		ASVS 2.2.1 and 2.3.1: verify exact type, provenance, scope, and physical
		working directory at this workflow boundary rather than trusting callers.
		"""
		if type(self.outline) is not daily_blog.artifacts.RepoOutline:
			raise RuntimeError("Repository-story input requires one exact RepoOutline.")
		if type(self.packets) is not tuple or not self.packets or any(
			type(packet) is not daily_blog.schema.EvidencePacket for packet in self.packets
		):
			raise RuntimeError("Repository-story input requires authoritative packet tuple.")
		if type(self.working_directory) is not str or not os.path.isabs(self.working_directory):
			raise RuntimeError("Repository-story input requires an absolute working directory.")
		physical = os.path.realpath(self.working_directory)
		if physical != self.working_directory or not os.path.isdir(physical):
			raise RuntimeError("Repository-story input working directory must be physical and exist.")
		try:
			datetime.date.fromisoformat(self.outline.report_date)
		except (TypeError, ValueError) as error:
			raise RuntimeError("Repository-story input outline report date is invalid.") from error
		if len(self.outline.repositories) != 1:
			raise RuntimeError("Repository-story input outline must isolate one repository.")
		if tuple(sorted(packet.packet_id for packet in self.packets)) != self.outline.packet_ids:
			raise RuntimeError("Repository-story packets must exactly match outline provenance.")
		if len({packet.packet_id for packet in self.packets}) != len(self.packets):
			raise RuntimeError("Repository-story packets cannot repeat identities.")
		for packet in self.packets:
			daily_blog.schema.EvidencePacket.from_dict(packet.to_dict())
			if packet.packet_id != daily_blog.io_utils.hash_value(packet.content_dict()):
				raise RuntimeError("Repository-story packet identity is invalid.")
			if packet.report_date != self.outline.report_date:
				raise RuntimeError("Repository-story packet report date conflicts with outline.")
			if {item.repository for item in packet.items} != {self.outline.repositories[0]}:
				raise RuntimeError("Repository-story packets must isolate the outline repository.")
		if not daily_blog.artifacts.evaluate_eligibility(self.outline, self.packets).eligible:
			raise RuntimeError("Repository-story input outline is not mechanically eligible.")

	#============================================
	@property
	def report_date(self) -> str:
		"""Expose the sole publication identity of the promoted outline."""
		return self.outline.report_date

	#============================================
	@property
	def repository(self) -> str:
		"""Expose the one repository proven by the promoted outline."""
		return self.outline.repositories[0]

	#============================================
	def render_outline(self) -> str:
		"""Return the canonical, bounded promoted-outline identity and content."""
		value = json.dumps(daily_blog.schema.model_cache_artifact(self.outline.to_dict()), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
		if len(value) > daily_blog.repository_story_prompts.MAX_OUTLINE_CONTEXT_CHARS:
			raise RuntimeError("Repository-story outline context exceeds its bounded limit.")
		return value

	#============================================
	def render_evidence(self) -> str:
		"""Return canonical bounded packet source without model conversation state."""
		value = json.dumps([daily_blog.schema.model_cache_packet_content(packet) for packet in self.packets], sort_keys=True,
			separators=(",", ":"), ensure_ascii=True)
		if len(value) > daily_blog.repository_story_prompts.MAX_EVIDENCE_CONTEXT_CHARS:
			raise RuntimeError("Repository-story evidence context exceeds its bounded limit.")
		return value


@dataclasses.dataclass(frozen=True)
class RepositoryStoryResult:
	"""Non-durable Stage 4 observations and its exact-rung promotion."""

	promotion: (daily_blog.artifacts.SelectedPeer | daily_blog.artifacts.PreservedArtifact
		| daily_blog.artifacts.DegradedPromotion | daily_blog.artifacts.NoArtifact)
	writing: daily_blog.replication.ReplicationResult
	editing: daily_blog.replication.ReplicationResult
	review: daily_blog.replication.ReviewResult
	reliability: tuple[daily_blog.replication.StepReliability, ...]

	#============================================
	def __post_init__(self) -> None:
		"""Keep observations exact, bounded, and coordinator-serializable."""
		if type(self.writing) is not daily_blog.replication.ReplicationResult:
			raise RuntimeError("Repository-story writing observation is invalid.")
		if type(self.editing) is not daily_blog.replication.ReplicationResult:
			raise RuntimeError("Repository-story editing observation is invalid.")
		if type(self.review) is not daily_blog.replication.ReviewResult:
			raise RuntimeError("Repository-story review observation is invalid.")
		if type(self.reliability) is not tuple or tuple(item.step for item in self.reliability) != (
			"4.1", "4.2", "4.3", "4.4",
		):
			raise RuntimeError("Repository-story reliability must contain Steps 4.1 through 4.4.")
		for item in self.reliability:
			if type(item) is not daily_blog.replication.StepReliability:
				raise RuntimeError("Repository-story reliability observation is invalid.")
			item.validate()

	#============================================
	@property
	def artifact(self) -> daily_blog.artifacts.RepoStory | None:
		"""Return the promoted artifact without hiding a typed no-artifact outcome."""
		return None if isinstance(self.promotion, daily_blog.artifacts.NoArtifact) else self.promotion.artifact


#============================================
def _request(
	value: RepositoryStoryInput, step: str, role: str, ordinal: str,
	route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, config: daily_blog.editorial_stage_config.RepositoryStoryConfig,
	contract_identity: dict[str, object], rubric_identity: str, input_artifact_ids: tuple[str, ...] = (),
	assignment: daily_blog.replication.ReviewAssignment | None = None, repair_of: str = "",
) -> daily_blog.agents.RouteRequest:
	"""Build one cache-safe request attesting to all Stage 4 inputs."""
	assignment_value: dict[str, int] = {}
	if assignment is not None:
		assignment_value = {"pair_index": assignment.pair_index, "reviewer_index": assignment.reviewer_index,
			"display_order": assignment.display_order}
	logical_identity = {
		"report_date": value.report_date, "repository": value.repository,
		"outline_id": value.outline.content_hash,
		"packet_ids": [daily_blog.schema.model_cache_packet_identity(packet) for packet in value.packets],
		"step": step, "role": role, "replica": ordinal,
		"input_artifact_ids": list(input_artifact_ids), "prompt_identity": contract_identity,
		"rubric_identity": rubric_identity, "assignment": assignment_value,
	}
	cache_input_hash = daily_blog.io_utils.hash_value(logical_identity)
	input_hash = daily_blog.io_utils.hash_value({
		"logical": logical_identity, "working_directory": value.working_directory,
	})
	return daily_blog.agents.RouteRequest(
		request_id=f"stage4_{step}_{role}_{ordinal}_{cache_input_hash[:12]}", step=f"repository_story_{step}",
		route=route, prompt=prompt, working_directory=value.working_directory, role=role,
		retry_attempts=config.route_retry_attempts, maximum_parallel_calls=config.maximum_parallel_calls,
		repair_of=repair_of, input_hash=input_hash,
		contract_version=(daily_blog.repository_story_prompts.REPOSITORY_STORY_PROMPT_VERSION
			+ ":" + str(contract_identity["integrity_sha256"])),
		cache_input_hash=cache_input_hash,
	)


#============================================
def _story(value: RepositoryStoryInput, result: daily_blog.agents.AgentResult) -> daily_blog.artifacts.RepoStory:
	"""Parse one whole story response; no mechanical prose assembly occurs here."""
	content = result.text.rstrip() + "\n"
	evidence_ids = daily_blog.artifacts.evidence_references(content)
	if not evidence_ids:
		raise daily_blog.agents.RepairableStructuredOutput("Repository story has no evidence reference.")
	return daily_blog.artifacts.RepoStory.create(value.report_date, value.packets, value.repository, content,
		evidence_ids, daily_blog.artifacts.referenced_image_paths(content))


#============================================
def _eligible(
	value: RepositoryStoryInput, item: daily_blog.artifacts.EditorialArtifact,
) -> daily_blog.artifacts.EligibilityResult:
	"""Apply the shared mechanical gate against this exact repository evidence."""
	return daily_blog.artifacts.evaluate_eligibility(item, value.packets)


#============================================
def _unique(
	items: collections.abc.Iterable[daily_blog.artifacts.RepoStory],
) -> tuple[daily_blog.artifacts.RepoStory, ...]:
	"""Keep a canonical exact-rung peer set independent of arrival ordering."""
	return tuple(sorted({item.artifact_id: item for item in items}.values(),
		key=lambda item: (item.content_hash, item.artifact_id)))


#============================================
def _anonymous_stories(items: collections.abc.Iterable[daily_blog.artifacts.RepoStory]) -> str:
	"""Render canonical anonymous whole candidates for independent editors."""
	ordered = _unique(items)
	value = json.dumps({"stories": [{"content": item.content} for item in ordered]}, sort_keys=True,
		separators=(",", ":"), ensure_ascii=True)
	if len(value) > daily_blog.repository_story_prompts.MAX_CANDIDATE_STORIES_CHARS:
		raise RuntimeError("Repository-story candidate context exceeds its bounded limit.")
	return value


#============================================
def _generation_reliability(step: str, generation: daily_blog.replication.ReplicationResult,
	additional_reasons: collections.abc.Iterable[str] = ()) -> daily_blog.replication.StepReliability:
	"""Summarize a generation mechanism without claiming a future winner."""
	candidates = generation.candidates
	reasons = set(additional_reasons)
	reasons.update(item.failure for item in candidates if item.failure)
	if any(item.result.ok and (item.eligibility is None or not item.eligibility.eligible) for item in candidates):
		reasons.add("ineligible_generation")
	succeeded = sum(item.result.ok and item.eligibility is not None and item.eligibility.eligible for item in candidates)
	return daily_blog.replication.StepReliability(step, "degraded" if reasons else "succeeded", len(candidates),
		succeeded, len(candidates) - succeeded, sum(item.result.resumed and item.result.ok for item in candidates),
		0, 0, "", tuple(sorted(reasons)))


#============================================
def _disagreements(votes: collections.abc.Iterable[daily_blog.replication.ReviewVote]) -> int:
	"""Count pair-level winner conflicts without retaining reviewer prose."""
	by_pair: dict[tuple[str, str], set[str]] = {}
	for vote in votes:
		if vote.status == "succeeded":
			pair = tuple(sorted((vote.first_artifact_id, vote.second_artifact_id)))
			by_pair.setdefault(pair, set()).add(vote.winner_artifact_id)
	return sum(len(winners) > 1 for winners in by_pair.values())


#============================================
def _review_reliability(review: daily_blog.replication.ReviewResult, promotion: object,
	additional_reasons: collections.abc.Iterable[str] = ()) -> daily_blog.replication.StepReliability:
	"""Summarize actual review routes and final reviewed identity only."""
	votes = review.votes
	disagreements = _disagreements(votes)
	reasons = set(additional_reasons) | set(daily_blog.replication.review_reasons(votes, disagreements))
	best = "" if not review.work or isinstance(promotion, daily_blog.artifacts.NoArtifact) else (
		promotion.artifact.artifact_id
	)
	return daily_blog.replication.StepReliability("4.3", "degraded" if reasons else "succeeded", len(votes),
		sum(vote.status == "succeeded" for vote in votes), sum(vote.status == "failed" for vote in votes), 0,
		sum(vote.repaired and vote.status == "succeeded" for vote in votes), disagreements, best, tuple(sorted(reasons)))


#============================================
def _promotion_reliability(
	promotion: object, votes: collections.abc.Iterable[daily_blog.replication.ReviewVote],
) -> daily_blog.replication.StepReliability:
	"""Record one deterministic promotion, independent from reviewer-call counts."""
	reasons: tuple[str, ...] = ()
	best = ""
	if isinstance(promotion, daily_blog.artifacts.DegradedPromotion):
		reasons, best = promotion.reasons, promotion.artifact.artifact_id
	elif isinstance(promotion, daily_blog.artifacts.NoArtifact):
		reasons = (promotion.reason,)
	else:
		best = promotion.artifact.artifact_id
	return daily_blog.replication.StepReliability("4.4", "degraded" if reasons else "succeeded", 1, 1, 0, 0, 0,
		_disagreements(votes), best, reasons)


#============================================
def _validate_rubric(rubric: object, rubric_sha256: object) -> tuple[str, str]:
	"""Require caller-selected rubric bytes and their exact SHA-256 identity."""
	if type(rubric) is not str or not rubric or len(rubric) > daily_blog.repository_story_prompts.MAX_RUBRIC_CHARS:
		raise RuntimeError("Repository-story rubric is invalid or exceeds its bounded limit.")
	if type(rubric_sha256) is not str or _SHA256_RE.fullmatch(rubric_sha256) is None:
		raise RuntimeError("Repository-story rubric SHA-256 is invalid.")
	if daily_blog.io_utils.sha256_text(rubric) != rubric_sha256:
		raise RuntimeError("Repository-story rubric SHA-256 does not match its text.")
	return rubric, "sha256:" + rubric_sha256


#============================================
def run_repository_story(
	value: RepositoryStoryInput, config: daily_blog.editorial_stage_config.RepositoryStoryConfig,
	budget: daily_blog.agents.RouteBudget, runner: object | None = None, *, rubric: str,
	rubric_sha256: str, contract: daily_blog.repository_story_prompts.RepositoryStoryPromptContract | None = None,
	cache_load: collections.abc.Callable[
		[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None,
	] | None = None,
	cache_accept: collections.abc.Callable[
		[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None,
	] | None = None,
	incumbent: daily_blog.artifacts.RepoStory | None = None,
) -> RepositoryStoryResult:
	"""Run Stage 4.1--4.4 without persisting artifacts, events, or cache state."""
	if type(value) is not RepositoryStoryInput:
		raise RuntimeError("Repository-story workflow requires exact input.")
	if type(config) is not daily_blog.editorial_stage_config.RepositoryStoryConfig:
		raise RuntimeError("Repository-story workflow requires exact stage configuration.")
	if type(budget) is not daily_blog.agents.RouteBudget:
		raise RuntimeError("Repository-story workflow requires the run-owned RouteBudget.")
	if incumbent is not None and type(incumbent) is not daily_blog.artifacts.RepoStory:
		raise RuntimeError("Repository-story incumbent must be an exact RepoStory.")
	rubric_text, rubric_identity = _validate_rubric(rubric, rubric_sha256)
	if incumbent is not None and not _eligible(value, incumbent).eligible:
		raise RuntimeError("Repository-story incumbent is not mechanically eligible.")
	contract_value = contract or daily_blog.repository_story_prompts.load_repository_story_prompt_contract()
	if type(contract_value) is not daily_blog.repository_story_prompts.RepositoryStoryPromptContract:
		raise RuntimeError("Repository-story workflow prompt contract is invalid.")
	contract_identity = daily_blog.repository_story_prompts.repository_story_prompt_identity(contract_value)
	outline_json, evidence_json = value.render_outline(), value.render_evidence()
	route_runner = runner if runner is not None else daily_blog.routes.CommandRouteRunner()

	writer_requests = tuple(_request(value, "4_1", "writer", str(index + 1), config.writer_route,
		daily_blog.repository_story_prompts.render_repository_story_writer(outline_json, evidence_json,
			"writer-" + str(index + 1), contract_value), config, contract_identity, rubric_identity,
		(value.outline.content_hash,)) for index in range(config.writer_count))
	if any(len(request.prompt) > config.prompt_limits["writer_chars"] for request in writer_requests):
		raise RuntimeError("Repository-story writer prompt exceeds its configured limit.")
	writing = daily_blog.replication.replicate(writer_requests, route_runner, budget, daily_blog.artifacts.RepoStory,
		lambda result: _story(value, result), lambda item: _eligible(value, item), cache_load, cache_accept)
	writer_peers = _unique(writing.eligible)
	editing = daily_blog.replication.ReplicationResult(daily_blog.artifacts.RepoStory, ())
	if writer_peers:
		candidate_json = _anonymous_stories(writer_peers)
		editor_requests = tuple(_request(value, "4_2", "editor", str(index + 1), config.editor_route,
			daily_blog.repository_story_prompts.render_repository_story_editor(outline_json, evidence_json,
				candidate_json, "editor-" + str(index + 1), contract_value), config, contract_identity,
			rubric_identity, tuple(item.content_hash for item in writer_peers)) for index in range(config.editor_count))
		if any(len(request.prompt) > config.prompt_limits["editor_chars"] for request in editor_requests):
			raise RuntimeError("Repository-story editor prompt exceeds its configured limit.")
		editing = daily_blog.replication.replicate(editor_requests, route_runner, budget, daily_blog.artifacts.RepoStory,
			lambda result: _story(value, result), lambda item: _eligible(value, item), cache_load, cache_accept)
	editor_peers = _unique(editing.eligible)
	peers = editor_peers or writer_peers
	if incumbent is not None:
		peers = _unique(peers + (incumbent,))
	if not peers:
		promotion = daily_blog.artifacts.NoArtifact(daily_blog.artifacts.RepoStory, "no_eligible_generation")
		empty = daily_blog.replication.ReviewResult((), ())
		return RepositoryStoryResult(promotion, writing, editing, empty, (
			_generation_reliability("4.1", writing), _generation_reliability("4.2", editing, ("upstream_unavailable",)),
			_review_reliability(empty, promotion, ("upstream_unavailable",)), _promotion_reliability(promotion, ()),
		))

	def build_work(left: daily_blog.artifacts.EditorialArtifact, right: daily_blog.artifacts.EditorialArtifact,
		assignment: daily_blog.replication.ReviewAssignment) -> daily_blog.replication.ReviewWork:
		prompt = daily_blog.repository_story_prompts.render_repository_story_comparison(outline_json, evidence_json,
			left.content, right.content, rubric_text, rubric_identity, contract_value)
		if len(prompt) > config.prompt_limits["reviewer_chars"]:
			raise RuntimeError("Repository-story comparison prompt exceeds its configured limit.")
		request = _request(value, "4_3", "reviewer",
			f"{assignment.pair_index}_{assignment.reviewer_index}_{assignment.display_order}",
			config.reviewer_route, prompt, config, contract_identity, rubric_identity,
			(left.content_hash, right.content_hash), assignment)
		return daily_blog.replication.ReviewWork(request, left.artifact_id, right.artifact_id, assignment)

	def parse_winner(text: str, work: daily_blog.replication.ReviewWork) -> str:
		try:
			verdict = daily_blog.repository_story_prompts.parse_repository_story_verdict(text)
		except daily_blog.repository_story_prompts.RepositoryStoryVerdictParseError as error:
			raise daily_blog.agents.RepairableStructuredOutput(str(error)) from error
		return {"A": work.first_artifact_id, "B": work.second_artifact_id}.get(verdict["winner"], "")

	def repair(work: daily_blog.replication.ReviewWork, response: str) -> daily_blog.replication.ReviewWork:
		prompt = daily_blog.repository_story_prompts.render_repository_story_verdict_repair(response, contract_value)
		if len(prompt) > config.prompt_limits["repair_chars"]:
			raise RuntimeError("Repository-story repair prompt exceeds its configured limit.")
		request = _request(value, "4_3_repair", "reviewer_repair", work.request.request_id, config.reviewer_route,
			prompt, config, contract_identity, rubric_identity, (daily_blog.io_utils.sha256_text(response),),
			work.assignment, work.request.cache_input_hash)
		return daily_blog.replication.ReviewWork(request, work.first_artifact_id, work.second_artifact_id, work.assignment)

	def salvage(text: str, work: daily_blog.replication.ReviewWork) -> str | None:
		label = daily_blog.replication.salvage_allowed_identifier(text, ("A", "B"))
		return {"A": work.first_artifact_id, "B": work.second_artifact_id}.get(label)

	review = daily_blog.replication.review(peers, daily_blog.artifacts.RepoStory, config.reviewer_count, build_work,
		parse_winner, route_runner, budget, repair, salvage, cache_load, cache_accept)
	promotion = daily_blog.replication.promote(peers, daily_blog.artifacts.RepoStory,
		lambda item: _eligible(value, item), review.votes, incumbent)
	if not editor_peers and writer_peers and isinstance(
		promotion, (daily_blog.artifacts.SelectedPeer, daily_blog.artifacts.DegradedPromotion),
	):
		reasons = ("editor_unavailable",) if isinstance(promotion, daily_blog.artifacts.SelectedPeer) else (
			tuple(sorted(set(promotion.reasons) | {"editor_unavailable"}))
		)
		promotion = daily_blog.artifacts.DegradedPromotion(promotion.artifact, daily_blog.artifacts.RepoStory, reasons)
	editor_degradation = () if editor_peers else (("editor_unavailable",) if writer_peers else ("upstream_unavailable",))
	review_degradation = () if review.work else ("review_unavailable",)
	return RepositoryStoryResult(promotion, writing, editing, review, (
		_generation_reliability("4.1", writing), _generation_reliability("4.2", editing, editor_degradation),
		_review_reliability(review, promotion, review_degradation), _promotion_reliability(promotion, review.votes),
	))

"""Pure replicated Stage 5 ranking and whole daily-outline workflow."""

import collections.abc
import dataclasses
import datetime
import json
import os
import re

import daily_blog.agents
import daily_blog.artifacts
import daily_blog.editorial_stage_config
import daily_blog.daily_outline_prompts
import daily_blog.io_utils
import daily_blog.replication
import daily_blog.routes
import daily_blog.schema


_SCOPE = re.compile(r"^<!-- daily-outline-scope: (\[[^\r\n]*\]) -->$")


@dataclasses.dataclass(frozen=True)
class DailyOutlineInput:
	repo_stories: tuple[daily_blog.artifacts.RepoStory, ...]
	repo_outlines: tuple[daily_blog.artifacts.RepoOutline, ...]
	packets: tuple[daily_blog.schema.EvidencePacket, ...]
	working_directory: str

	def __post_init__(self) -> None:
		if type(self.repo_stories) is not tuple or type(self.repo_outlines) is not tuple or type(self.packets) is not tuple:
			raise RuntimeError("Daily-outline input requires tuples.")
		if not self.repo_stories or len(self.repo_stories) != len(self.repo_outlines) or not self.packets:
			raise RuntimeError("Daily-outline input requires complete repository artifacts and packets.")
		if any(type(item) is not daily_blog.artifacts.RepoStory for item in self.repo_stories) or any(type(item) is not daily_blog.artifacts.RepoOutline for item in self.repo_outlines) or any(type(item) is not daily_blog.schema.EvidencePacket for item in self.packets):
			raise RuntimeError("Daily-outline input requires exact artifact types.")
		if type(self.working_directory) is not str or not os.path.isabs(self.working_directory) or os.path.realpath(self.working_directory) != self.working_directory or not os.path.isdir(self.working_directory):
			raise RuntimeError("Daily-outline input requires an existing physical working directory.")
		packets = tuple(sorted(self.packets, key=lambda item: item.packet_id))
		stories = tuple(sorted(self.repo_stories, key=lambda item: item.artifact_id))
		outlines = tuple(sorted(self.repo_outlines, key=lambda item: item.artifact_id))
		if len({item.packet_id for item in packets}) != len(packets) or len({item.artifact_id for item in stories}) != len(stories) or len({item.artifact_id for item in outlines}) != len(outlines):
			raise RuntimeError("Daily-outline input identities cannot repeat.")
		object.__setattr__(self, "packets", packets)
		object.__setattr__(self, "repo_stories", stories)
		object.__setattr__(self, "repo_outlines", outlines)
		date = stories[0].report_date
		try:
			datetime.date.fromisoformat(date)
		except (TypeError, ValueError) as error:
			raise RuntimeError("Daily-outline input report date is invalid.") from error
		packet_ids = frozenset(item.packet_id for item in packets)
		for packet in packets:
			daily_blog.schema.EvidencePacket.from_dict(packet.to_dict())
			if packet.report_date != date or packet.packet_id != daily_blog.io_utils.hash_value(packet.content_dict()):
				raise RuntimeError("Daily-outline packet identity or report date is invalid.")
		for artifact in stories + outlines:
			if artifact.report_date != date or len(artifact.repositories) != 1 or not daily_blog.artifacts.evaluate_eligibility(artifact, packets).eligible:
				raise RuntimeError("Daily-outline artifact provenance or eligibility conflicts.")
		if tuple(sorted(item.repositories[0] for item in stories)) != tuple(sorted(item.repositories[0] for item in outlines)) or len({item.repositories[0] for item in stories}) != len(stories):
			raise RuntimeError("Daily-outline input repositories must align exactly.")
		local_packet_ids: set[str] = set()
		for story in stories:
			outline = next(item for item in outlines if item.repositories == story.repositories)
			if story.packet_ids != outline.packet_ids or not story.packet_ids:
				raise RuntimeError("Daily-outline paired artifacts must share local packet provenance.")
			for packet_id in story.packet_ids:
				matching = next((item for item in packets if item.packet_id == packet_id), None)
				if matching is None or {item.repository for item in matching.items} != set(story.repositories):
					raise RuntimeError("Daily-outline local packet scope conflicts with its repository.")
				local_packet_ids.add(packet_id)
		if local_packet_ids != packet_ids:
			raise RuntimeError("Daily-outline packet union contains an orphan local packet.")

	@property
	def report_date(self) -> str:
		return self.repo_stories[0].report_date

	@property
	def repositories(self) -> tuple[str, ...]:
		return tuple(sorted(item.repositories[0] for item in self.repo_stories))

	def _render(self, value: object, maximum: int, label: str) -> str:
		rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
		if len(rendered) > maximum:
			raise RuntimeError(f"Daily-outline {label} context exceeds its bounded limit.")
		return rendered

	def render_stories(self) -> str:
		stories = []
		for item in sorted(self.repo_stories, key=lambda item: (item.repositories, item.content_hash)):
			projected = daily_blog.schema.model_cache_artifact(item.to_dict())
			projected["artifact_id"] = item.content_hash
			stories.append(projected)
		return self._render({"stories": stories}, daily_blog.daily_outline_prompts.MAX_STORIES_CONTEXT_CHARS, "stories")

	def render_outlines(self) -> str:
		outlines = []
		for item in sorted(self.repo_outlines, key=lambda item: (item.repositories, item.content_hash)):
			projected = daily_blog.schema.model_cache_artifact(item.to_dict())
			projected["artifact_id"] = item.content_hash
			outlines.append(projected)
		return self._render({"outlines": outlines}, daily_blog.daily_outline_prompts.MAX_REPOSITORY_OUTLINES_CONTEXT_CHARS, "repository outlines")

	def render_evidence(self) -> str:
		packets = sorted(self.packets, key=daily_blog.schema.model_cache_packet_identity)
		return self._render([daily_blog.schema.model_cache_packet_content(item) for item in packets], daily_blog.daily_outline_prompts.MAX_EVIDENCE_CONTEXT_CHARS, "evidence")


@dataclasses.dataclass(frozen=True)
class RankingCandidate:
	candidate_id: str
	content_sha256: str
	request: daily_blog.agents.RouteRequest
	result: daily_blog.agents.AgentResult
	artifact_ids: tuple[str, ...]
	scores: tuple[tuple[str, int], ...]
	rationale: str

	def __post_init__(self) -> None:
		if (
			type(self.request) is not daily_blog.agents.RouteRequest
			or type(self.result) is not daily_blog.agents.AgentResult or not self.result.ok
			or type(self.artifact_ids) is not tuple or not self.artifact_ids
			or any(type(item) is not str or not item for item in self.artifact_ids)
			or len(set(self.artifact_ids)) != len(self.artifact_ids)
			or type(self.scores) is not tuple
			or any(type(pair) is not tuple or len(pair) != 2 for pair in self.scores)
			or tuple(key for key, _value in self.scores) != tuple(sorted(self.artifact_ids))
			or any(type(key) is not str or type(score) is not int or isinstance(score, bool) or not 0 <= score <= 100 for key, score in self.scores)
			or type(self.rationale) is not str or not self.rationale
			or len(self.rationale) > daily_blog.daily_outline_prompts.MAX_RATIONALE_CHARS
		):
			raise RuntimeError("Ranking candidate fields are invalid.")
		canonical = json.dumps({"request_identity_sha256": self.request.cache_input_hash, "artifact_ids": list(self.artifact_ids), "scores": dict(self.scores), "rationale": self.rationale}, sort_keys=True, separators=(",", ":"))
		content_hash = daily_blog.io_utils.sha256_text(canonical)
		if self.content_sha256 != content_hash or self.candidate_id != "ranking-" + content_hash[:24]:
			raise RuntimeError("Ranking candidate identity conflicts with canonical data.")

	def to_dict(self) -> dict[str, object]:
		return {"artifact_ids": list(self.artifact_ids), "scores": dict(self.scores), "rationale": self.rationale}


@dataclasses.dataclass(frozen=True)
class RankingObservation:
	request: daily_blog.agents.RouteRequest
	result: daily_blog.agents.AgentResult
	candidate: RankingCandidate | None
	failure: str = ""


@dataclasses.dataclass(frozen=True)
class RankingReviewObservation:
	candidate_id: str
	request: daily_blog.agents.RouteRequest
	result: daily_blog.agents.AgentResult
	verdict: tuple[tuple[str, object], ...] | None
	failure: str = ""
	repaired: bool = False

	def __post_init__(self) -> None:
		if type(self.candidate_id) is not str or not self.candidate_id or type(self.request) is not daily_blog.agents.RouteRequest or type(self.result) is not daily_blog.agents.AgentResult or type(self.repaired) is not bool:
			raise RuntimeError("Ranking-review observation provenance is invalid.")
		if self.verdict is None:
			if self.failure not in daily_blog.replication.REVIEW_FAILURES:
				raise RuntimeError("Failed ranking review requires a bounded reason.")
			return
		if (
			type(self.verdict) is not tuple or len(self.verdict) != 3
			or any(type(pair) is not tuple or len(pair) != 2 for pair in self.verdict)
			or tuple(key for key, _item in self.verdict) != ("decision", "reason", "score")
		):
			raise RuntimeError("Ranking-review verdict is invalid.")
		value = dict(self.verdict)
		if self.failure or type(value["decision"]) is not str or value["decision"] not in {"ACCEPT", "REJECT"} or type(value["score"]) is not int or isinstance(value["score"], bool) or not 0 <= value["score"] <= 100 or type(value["reason"]) is not str or not value["reason"] or len(value["reason"]) > 500:
			raise RuntimeError("Ranking-review verdict is invalid.")


@dataclasses.dataclass(frozen=True)
class PromotedRanking:
	promotion_id: str
	candidate_id: str
	ranking_content_sha256: str
	artifact_ids: tuple[str, ...]
	scores: tuple[tuple[str, int], ...]
	rationale: str
	review_ids: tuple[str, ...]
	method: str = "reviewed_ranking_promotion_v1"

	def __post_init__(self) -> None:
		if (
			type(self.promotion_id) is not str or not self.promotion_id
			or type(self.candidate_id) is not str or not self.candidate_id
			or type(self.ranking_content_sha256) is not str
			or re.fullmatch(r"[0-9a-f]{64}", self.ranking_content_sha256) is None
			or type(self.artifact_ids) is not tuple or not self.artifact_ids
			or any(type(item) is not str or not item for item in self.artifact_ids)
			or type(self.scores) is not tuple
			or any(type(pair) is not tuple or len(pair) != 2 for pair in self.scores)
			or type(self.rationale) is not str or not self.rationale
			or len(self.rationale) > daily_blog.daily_outline_prompts.MAX_RATIONALE_CHARS
			or type(self.review_ids) is not tuple or not self.review_ids
			or tuple(sorted(set(self.review_ids))) != self.review_ids
			or any(type(item) is not str or not item for item in self.review_ids)
			or tuple(key for key, _value in self.scores) != tuple(sorted(self.artifact_ids))
			or any(type(key) is not str or type(score) is not int or isinstance(score, bool) or not 0 <= score <= 100 for key, score in self.scores)
			or len(set(self.artifact_ids)) != len(self.artifact_ids)
			or type(self.method) is not str or self.method != "reviewed_ranking_promotion_v1"
		):
			raise RuntimeError("Promoted ranking fields are invalid.")
		canonical = json.dumps({"candidate_id": self.candidate_id, "accepted_review_ids": list(self.review_ids), "ranking_content_sha256": self.ranking_content_sha256}, sort_keys=True, separators=(",", ":"))
		if self.promotion_id != "ranking-promotion-" + daily_blog.io_utils.sha256_text(canonical)[:24]:
			raise RuntimeError("Promoted ranking identity conflicts with reviewed content.")

	def to_dict(self) -> dict[str, object]:
		return {"promotion_id": self.promotion_id, "candidate_id": self.candidate_id, "artifact_ids": list(self.artifact_ids), "scores": dict(self.scores), "rationale": self.rationale, "method": self.method}


@dataclasses.dataclass(frozen=True)
class DailyOutlineResult:
	promotion: daily_blog.artifacts.SelectedPeer | daily_blog.artifacts.DegradedPromotion | daily_blog.artifacts.NoArtifact
	rankings: tuple[RankingObservation, ...]
	ranking_reviews: tuple[RankingReviewObservation, ...]
	promoted_ranking: PromotedRanking | None
	generation: daily_blog.replication.ReplicationResult
	review: daily_blog.replication.ReviewResult
	reliability: tuple[daily_blog.replication.StepReliability, ...]
	source_stories: tuple[daily_blog.artifacts.RepoStory, ...]

	@property
	def artifact(self) -> daily_blog.artifacts.DailyOutline | None:
		return None if isinstance(self.promotion, daily_blog.artifacts.NoArtifact) else self.promotion.artifact

	@property
	def selected_stories(self) -> tuple[daily_blog.artifacts.RepoStory, ...]:
		return () if self.artifact is None else tuple(item for item in self.source_stories if item.repositories[0] in self.artifact.repositories)


def _request(value: DailyOutlineInput, step: str, role: str, ordinal: str, route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, config: daily_blog.editorial_stage_config.DailyOutlineConfig, contract_identity: dict[str, object], input_ids: tuple[str, ...] = (), assignment: daily_blog.replication.ReviewAssignment | None = None, repair_of: str = "") -> daily_blog.agents.RouteRequest:
	assignment_value = {} if assignment is None else {"pair_index": assignment.pair_index, "reviewer_index": assignment.reviewer_index, "display_order": assignment.display_order}
	identity = {"report_date": value.report_date, "repositories": list(value.repositories), "packet_ids": sorted(daily_blog.schema.model_cache_packet_identity(item) for item in value.packets), "story_ids": sorted(item.content_hash for item in value.repo_stories), "outline_ids": sorted(item.content_hash for item in value.repo_outlines), "step": step, "role": role, "ordinal": ordinal, "input_ids": sorted(input_ids), "prompt_identity": contract_identity, "assignment": assignment_value}
	input_hash = daily_blog.io_utils.hash_value(identity)
	return daily_blog.agents.RouteRequest(f"stage5_{step}_{role}_{ordinal}_{input_hash[:12]}", f"daily_outline_{step}", route, prompt, value.working_directory, role, config.route_retry_attempts, config.maximum_parallel_calls, repair_of, input_hash=input_hash, contract_version=daily_blog.daily_outline_prompts.DAILY_OUTLINE_PROMPT_VERSION + ":" + str(contract_identity["integrity_sha256"]), cache_input_hash=input_hash)


def _candidate(request: daily_blog.agents.RouteRequest, result: daily_blog.agents.AgentResult, ranking: dict[str, object]) -> RankingCandidate:
	ids, scores, rationale = tuple(ranking["artifact_ids"]), tuple(sorted(ranking["scores"].items())), ranking["rationale"]
	canonical = json.dumps({"request_identity_sha256": request.cache_input_hash, "artifact_ids": list(ids), "scores": dict(scores), "rationale": rationale}, sort_keys=True, separators=(",", ":"))
	hash_value = daily_blog.io_utils.sha256_text(canonical)
	return RankingCandidate("ranking-" + hash_value[:24], hash_value, request, result, ids, scores, rationale)


def _outline(value: DailyOutlineInput, result: daily_blog.agents.AgentResult) -> daily_blog.artifacts.DailyOutline:
	content = result.text.rstrip() + "\n"
	match = _SCOPE.fullmatch(content.splitlines()[0] if content.splitlines() else "")
	if match is None:
		raise daily_blog.agents.RepairableStructuredOutput("Daily outline lacks its exact scope marker.")
	try:
		repositories = json.loads(match.group(1))
	except json.JSONDecodeError as error:
		raise daily_blog.agents.RepairableStructuredOutput("Daily outline scope is not JSON.") from error
	if type(repositories) is not list or not repositories or any(type(item) is not str or not item for item in repositories) or tuple(repositories) != tuple(sorted(set(repositories))) or not set(repositories).issubset(value.repositories):
		raise daily_blog.agents.RepairableStructuredOutput("Daily outline scope is invalid.")
	evidence_ids = daily_blog.artifacts.evidence_references(content)
	if not evidence_ids:
		raise daily_blog.agents.RepairableStructuredOutput("Daily outline has no evidence reference.")
	return daily_blog.artifacts.DailyOutline.create(value.report_date, value.packets, tuple(repositories), content, evidence_ids, daily_blog.artifacts.referenced_image_paths(content))


def _generation_reliability(step: str, generation: daily_blog.replication.ReplicationResult, reasons: tuple[str, ...] = ()) -> daily_blog.replication.StepReliability:
	reason_set = set(reasons) | {item.failure for item in generation.candidates if item.failure}
	if any(item.result.ok and (item.eligibility is None or not item.eligibility.eligible) for item in generation.candidates): reason_set.add("ineligible_generation")
	succeeded = sum(item.result.ok and item.eligibility is not None and item.eligibility.eligible for item in generation.candidates)
	return daily_blog.replication.StepReliability(step, "degraded" if reason_set else "succeeded", len(generation.candidates), succeeded, len(generation.candidates) - succeeded, sum(item.result.ok and item.result.resumed for item in generation.candidates), 0, 0, "", tuple(sorted(reason_set)))


def _ranking_reliability(rankings: tuple[RankingObservation, ...]) -> daily_blog.replication.StepReliability:
	reasons = tuple(sorted({item.failure for item in rankings if item.failure}))
	return daily_blog.replication.StepReliability("5.1", "degraded" if reasons else "succeeded", len(rankings), sum(item.candidate is not None for item in rankings), sum(item.candidate is None for item in rankings), sum(item.result.ok and item.result.resumed for item in rankings), 0, 0, "", reasons)


def _promotion_reliability(promotion: object) -> daily_blog.replication.StepReliability:
	reasons = (promotion.reason,) if isinstance(promotion, daily_blog.artifacts.NoArtifact) else (promotion.reasons if isinstance(promotion, daily_blog.artifacts.DegradedPromotion) else ())
	return daily_blog.replication.StepReliability("5.5", "degraded" if reasons else "succeeded", 1, 1, 0, 0, 0, 0, "" if isinstance(promotion, daily_blog.artifacts.NoArtifact) else promotion.artifact.artifact_id, tuple(sorted(reasons)))


def _ranking_promotion_reliability(reviews: tuple[RankingReviewObservation, ...], promoted: PromotedRanking | None, had_candidates: bool) -> daily_blog.replication.StepReliability:
	reasons = {item.failure for item in reviews if item.failure}
	if reviews and not any(item.verdict is not None for item in reviews): reasons.add("review_unavailable")
	if had_candidates and promoted is None: reasons.add("no_eligible_ranking_review")
	if not had_candidates: reasons.add("ineligible_generation")
	succeeded = sum(item.verdict is not None for item in reviews)
	return daily_blog.replication.StepReliability("5.2", "degraded" if reasons else "succeeded", len(reviews), succeeded, len(reviews) - succeeded, sum(item.result.ok and item.result.resumed for item in reviews), sum(item.repaired and item.verdict is not None for item in reviews), 0, "" if promoted is None else promoted.promotion_id, tuple(sorted(reasons)))


def _review_reliability(review: daily_blog.replication.ReviewResult) -> daily_blog.replication.StepReliability:
	by_pair: dict[tuple[str, str], set[str]] = {}
	for vote in review.votes:
		if vote.status == "succeeded": by_pair.setdefault(tuple(sorted((vote.first_artifact_id, vote.second_artifact_id))), set()).add(vote.winner_artifact_id)
	disagreements = sum(len(items) > 1 for items in by_pair.values())
	reasons = daily_blog.replication.review_reasons(review.votes, disagreements)
	return daily_blog.replication.StepReliability("5.4", "degraded" if reasons else "succeeded", len(review.votes), sum(item.status == "succeeded" for item in review.votes), sum(item.status == "failed" for item in review.votes), 0, sum(item.repaired and item.status == "succeeded" for item in review.votes), disagreements, "", reasons)


def _promote_ranking(candidates: tuple[RankingCandidate, ...], reviews: tuple[RankingReviewObservation, ...]) -> PromotedRanking | None:
	eligible = []
	for candidate in candidates:
		observations = tuple(item for item in reviews if item.candidate_id == candidate.candidate_id and item.verdict is not None)
		verdicts = tuple(dict(item.verdict) for item in observations)
		if any(item["decision"] == "REJECT" for item in verdicts) or not any(item["decision"] == "ACCEPT" for item in verdicts): continue
		eligible.append((candidate, verdicts, tuple(sorted(item.request.repair_of or item.request.request_id for item in observations if dict(item.verdict)["decision"] == "ACCEPT"))))
	if not eligible: return None
	best = eligible[0]
	for contender in eligible[1:]:
		left_total, right_total = sum(int(item["score"]) for item in contender[1]), sum(int(item["score"]) for item in best[1])
		if left_total * len(best[1]) > right_total * len(contender[1]) or (left_total * len(best[1]) == right_total * len(contender[1]) and (contender[0].content_sha256, contender[0].candidate_id) < (best[0].content_sha256, best[0].candidate_id)): best = contender
	candidate, _verdicts, review_ids = best
	canonical = json.dumps({"candidate_id": candidate.candidate_id, "accepted_review_ids": list(review_ids), "ranking_content_sha256": candidate.content_sha256}, sort_keys=True, separators=(",", ":"))
	return PromotedRanking("ranking-promotion-" + daily_blog.io_utils.sha256_text(canonical)[:24], candidate.candidate_id, candidate.content_sha256, candidate.artifact_ids, candidate.scores, candidate.rationale, review_ids)


@dataclasses.dataclass(frozen=True)
class _DailyOutlinePreparation:
	"""Validated shared inputs for all Stage 5 route roles."""

	contract: daily_blog.daily_outline_prompts.DailyOutlinePromptContract
	identity: dict[str, object]
	stories_json: str
	outlines_json: str
	evidence_json: str
	story_ids: tuple[str, ...]
	route_runner: object


#============================================


def _prepare_daily_outline(
	value: DailyOutlineInput,
	config: daily_blog.editorial_stage_config.DailyOutlineConfig,
	budget: daily_blog.agents.RouteBudget,
	runner: object | None,
	contract: daily_blog.daily_outline_prompts.DailyOutlinePromptContract | None,
) -> _DailyOutlinePreparation:
	"""Validate the coordinator boundary and build its immutable route context."""
	# ASVS 2.2.1/2.3.1: exact trusted inputs are validated before route work,
	# then the coordinator passes only the resulting ordered context downstream.
	if type(value) is not DailyOutlineInput or type(config) is not daily_blog.editorial_stage_config.DailyOutlineConfig or type(budget) is not daily_blog.agents.RouteBudget:
		raise RuntimeError("Daily-outline workflow requires exact input, configuration, and RouteBudget.")
	contract_value = contract or daily_blog.daily_outline_prompts.load_daily_outline_prompt_contract()
	identity = daily_blog.daily_outline_prompts.daily_outline_prompt_identity(contract_value)
	return _DailyOutlinePreparation(
		contract_value,
		identity,
		value.render_stories(),
		value.render_outlines(),
		value.render_evidence(),
		tuple(item.content_hash for item in value.repo_stories),
		runner if runner is not None else daily_blog.routes.CommandRouteRunner(),
	)


def _observe_rankings(
	value: DailyOutlineInput,
	config: daily_blog.editorial_stage_config.DailyOutlineConfig,
	budget: daily_blog.agents.RouteBudget,
	prepared: _DailyOutlinePreparation,
	cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None,
	cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None,
) -> tuple[tuple[RankingObservation, ...], tuple[RankingCandidate, ...]]:
	"""Run independent rankers and retain each source observation."""
	requests = tuple(
		_request(
			value, "5_1", "ranker", str(index), config.ranking_route,
			daily_blog.daily_outline_prompts.render_story_ranking(
				prepared.stories_json, prepared.outlines_json, prepared.evidence_json,
				"ranker-" + str(index), prepared.contract,
			),
			config, prepared.identity, prepared.story_ids,
		)
		for index in range(config.ranker_count)
	)
	results = daily_blog.agents.execute_requests(
		list(requests), prepared.route_runner, config.maximum_parallel_calls, budget, cache_load,
	)
	observations: list[RankingObservation] = []
	for request, result in zip(requests, results, strict=True):
		try:
			candidate = None
			if result.ok:
				parsed = daily_blog.daily_outline_prompts.parse_story_ranking(result.text, prepared.story_ids)
				candidate = _candidate(request, result, parsed)
			if candidate is not None and not result.resumed and cache_accept is not None:
				cache_accept(request, result)
			observations.append(RankingObservation(
				request, result, candidate,
				"" if candidate else (result.failure or "ineligible_generation"),
			))
		except daily_blog.daily_outline_prompts.DailyOutlineRankingParseError:
			observations.append(RankingObservation(request, result, None, "ineligible_generation"))
	rankings = tuple(observations)
	return rankings, tuple(item.candidate for item in rankings if item.candidate is not None)


def _observe_ranking_reviews(
	value: DailyOutlineInput,
	config: daily_blog.editorial_stage_config.DailyOutlineConfig,
	budget: daily_blog.agents.RouteBudget,
	prepared: _DailyOutlinePreparation,
	candidates: tuple[RankingCandidate, ...],
	cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None,
	cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None,
) -> tuple[RankingReviewObservation, ...]:
	"""Review every ranking candidate, then run one ordered repair pass."""
	pairs = [(candidate, index) for candidate in candidates for index in range(config.reviewer_count)]
	requests = tuple(
		_request(
			value, "5_2", "ranking_reviewer", candidate.candidate_id + "_" + str(index),
			config.outline_reviewer_route,
			daily_blog.daily_outline_prompts.render_story_ranking_review(
				json.dumps(candidate.to_dict(), sort_keys=True, separators=(",", ":")),
				prepared.stories_json, prepared.outlines_json, prepared.evidence_json,
				"ranking-reviewer-" + str(index), prepared.contract,
			),
			config, prepared.identity, (candidate.candidate_id,),
		)
		for candidate, index in pairs
	)
	results = []
	if requests:
		results = daily_blog.agents.execute_requests(
			list(requests), prepared.route_runner, config.maximum_parallel_calls, budget, cache_load,
		)
	observations: list[RankingReviewObservation] = []
	repairs: list[tuple[RankingCandidate, daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult]] = []
	for (candidate, _index), request, result in zip(pairs, requests, results, strict=True):
		try:
			verdict = None
			if result.ok:
				verdict = daily_blog.daily_outline_prompts.parse_story_ranking_review_verdict(result.text)
			if verdict is not None and not result.resumed and cache_accept is not None:
				cache_accept(request, result)
			observations.append(RankingReviewObservation(
				candidate.candidate_id, request, result,
				None if verdict is None else tuple(sorted(verdict.items())), result.failure,
			))
		except daily_blog.daily_outline_prompts.DailyOutlineVerdictParseError:
			observations.append(RankingReviewObservation(
				candidate.candidate_id, request, result, None, "invalid_verdict",
			))
			repairs.append((candidate, request, result))
	_observe_ranking_review_repairs(
		value, config, budget, prepared, repairs, observations, cache_load, cache_accept,
	)
	return tuple(sorted(observations, key=lambda item: (
		item.candidate_id, item.request.repair_of or item.request.request_id,
		bool(item.request.repair_of), item.request.request_id,
	)))


def _observe_ranking_review_repairs(
	value: DailyOutlineInput,
	config: daily_blog.editorial_stage_config.DailyOutlineConfig,
	budget: daily_blog.agents.RouteBudget,
	prepared: _DailyOutlinePreparation,
	repairs: list[tuple[RankingCandidate, daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult]],
	observations: list[RankingReviewObservation],
	cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None,
	cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None,
) -> None:
	"""Append repair observations without replacing malformed source attempts."""
	if not repairs:
		return
	requests = tuple(
		_request(
			value, "5_2_repair", "ranking_reviewer_repair", source.request_id,
			config.outline_reviewer_route,
			daily_blog.daily_outline_prompts.render_story_ranking_review_repair(
				result.text, prepared.contract,
			),
			config, prepared.identity, (candidate.candidate_id,), None, source.request_id,
		)
		for candidate, source, result in repairs
	)
	results = daily_blog.agents.execute_requests(
		list(requests), prepared.route_runner, config.maximum_parallel_calls, budget, cache_load,
	)
	for (candidate, _source, _original), request, result in zip(repairs, requests, results, strict=True):
		try:
			verdict = None
			if result.ok:
				verdict = daily_blog.daily_outline_prompts.parse_story_ranking_review_verdict(result.text)
			if verdict is not None and not result.resumed and cache_accept is not None:
				cache_accept(request, result)
			observations.append(RankingReviewObservation(
				candidate.candidate_id, request, result,
				None if verdict is None else tuple(sorted(verdict.items())),
				result.failure if verdict is None else "", True,
			))
		except daily_blog.daily_outline_prompts.DailyOutlineVerdictParseError:
			observations.append(RankingReviewObservation(
				candidate.candidate_id, request, result, None, "invalid_verdict", True,
			))


def _replicate_outlines(
	value: DailyOutlineInput,
	config: daily_blog.editorial_stage_config.DailyOutlineConfig,
	budget: daily_blog.agents.RouteBudget,
	prepared: _DailyOutlinePreparation,
	promoted: PromotedRanking,
	cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None,
	cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None,
) -> daily_blog.replication.ReplicationResult:
	"""Generate independent whole-outline candidates from the promoted ranking."""
	ranking_json = json.dumps(promoted.to_dict(), sort_keys=True, separators=(",", ":"))
	requests = tuple(
		_request(
			value, "5_3", "outline_writer", str(index), config.outline_writer_route,
			daily_blog.daily_outline_prompts.render_daily_outline_writer(
				ranking_json, prepared.stories_json, prepared.outlines_json,
				prepared.evidence_json, "outline-writer-" + str(index), prepared.contract,
			),
			config, prepared.identity, prepared.story_ids,
		)
		for index in range(config.outline_writer_count)
	)
	return daily_blog.replication.replicate(
		requests, prepared.route_runner, budget, daily_blog.artifacts.DailyOutline,
		lambda item: _outline(value, item),
		lambda item: daily_blog.artifacts.evaluate_eligibility(item, value.packets),
		cache_load, cache_accept,
	)


def _review_outlines(
	value: DailyOutlineInput,
	config: daily_blog.editorial_stage_config.DailyOutlineConfig,
	budget: daily_blog.agents.RouteBudget,
	prepared: _DailyOutlinePreparation,
	peers: tuple[daily_blog.artifacts.DailyOutline, ...],
	cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None,
	cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None,
) -> daily_blog.replication.ReviewResult:
	"""Compare the eligible peer artifacts with balanced reviewer geometry."""
	def work(
		left: daily_blog.artifacts.EditorialArtifact,
		right: daily_blog.artifacts.EditorialArtifact,
		assignment: daily_blog.replication.ReviewAssignment,
	) -> daily_blog.replication.ReviewWork:
		request = _request(
			value, "5_4", "outline_reviewer",
			f"{assignment.pair_index}_{assignment.reviewer_index}_{assignment.display_order}",
			config.outline_reviewer_route,
			daily_blog.daily_outline_prompts.render_daily_outline_comparison(
				prepared.stories_json, prepared.outlines_json, prepared.evidence_json,
				left.content, right.content, prepared.contract,
			),
			config, prepared.identity, (left.content_hash, right.content_hash), assignment,
		)
		return daily_blog.replication.ReviewWork(
			request, left.artifact_id, right.artifact_id, assignment,
		)

	def winner(text: str, item: daily_blog.replication.ReviewWork) -> str:
		try:
			verdict = daily_blog.daily_outline_prompts.parse_daily_outline_verdict(text)
		except daily_blog.daily_outline_prompts.DailyOutlineVerdictParseError as error:
			raise daily_blog.agents.RepairableStructuredOutput(str(error)) from error
		return {"A": item.first_artifact_id, "B": item.second_artifact_id}.get(verdict["winner"], "")

	def repair(item: daily_blog.replication.ReviewWork, response: str) -> daily_blog.replication.ReviewWork:
		request = _request(
			value, "5_4_repair", "outline_reviewer_repair", item.request.cache_input_hash,
			config.outline_reviewer_route,
			daily_blog.daily_outline_prompts.render_daily_outline_verdict_repair(
				response, prepared.contract,
			),
			config, prepared.identity, (daily_blog.io_utils.sha256_text(response),),
			item.assignment, item.request.cache_input_hash,
		)
		return daily_blog.replication.ReviewWork(
			request, item.first_artifact_id, item.second_artifact_id, item.assignment,
		)

	return daily_blog.replication.review(
		peers, daily_blog.artifacts.DailyOutline, config.reviewer_count, work, winner,
		prepared.route_runner, budget, repair, None, cache_load, cache_accept,
	)


def _daily_outline_result(
	promotion: daily_blog.artifacts.SelectedPeer | daily_blog.artifacts.DegradedPromotion | daily_blog.artifacts.NoArtifact,
	rankings: tuple[RankingObservation, ...],
	ranking_reviews: tuple[RankingReviewObservation, ...],
	promoted: PromotedRanking | None,
	generation: daily_blog.replication.ReplicationResult,
	review: daily_blog.replication.ReviewResult,
	had_candidates: bool,
	value: DailyOutlineInput,
) -> DailyOutlineResult:
	"""Build the typed terminal outcome and its stage-level reliability record."""
	return DailyOutlineResult(
		promotion, rankings, ranking_reviews, promoted, generation, review,
		(
			_ranking_reliability(rankings),
			_ranking_promotion_reliability(ranking_reviews, promoted, had_candidates),
			_generation_reliability(
				"5.3", generation,
				("upstream_unavailable",) if promoted is None else (),
			),
			_review_reliability(review),
			_promotion_reliability(promotion),
		),
		value.repo_stories,
	)


#============================================


def run_daily_outline(value: DailyOutlineInput, config: daily_blog.editorial_stage_config.DailyOutlineConfig, budget: daily_blog.agents.RouteBudget, runner: object | None = None, contract: daily_blog.daily_outline_prompts.DailyOutlinePromptContract | None = None, cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None = None, cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None = None) -> DailyOutlineResult:
	"""Coordinate ranking, replication, review, and promotion for Stage 5."""
	prepared = _prepare_daily_outline(value, config, budget, runner, contract)
	rankings, candidates = _observe_rankings(
		value, config, budget, prepared, cache_load, cache_accept,
	)
	ranking_reviews = _observe_ranking_reviews(
		value, config, budget, prepared, candidates, cache_load, cache_accept,
	)
	promoted = _promote_ranking(candidates, ranking_reviews)
	if promoted is None:
		promotion = daily_blog.artifacts.NoArtifact(
			daily_blog.artifacts.DailyOutline,
			"no_eligible_ranking_review" if candidates else "no_eligible_generation",
		)
		empty_generation = daily_blog.replication.ReplicationResult(
			daily_blog.artifacts.DailyOutline, (),
		)
		return _daily_outline_result(
			promotion, rankings, ranking_reviews, None, empty_generation,
			daily_blog.replication.ReviewResult((), ()), bool(candidates), value,
		)
	generation = _replicate_outlines(
		value, config, budget, prepared, promoted, cache_load, cache_accept,
	)
	peers = tuple(sorted(
		{item.artifact_id: item for item in generation.eligible}.values(),
		key=lambda item: (item.content_hash, item.artifact_id),
	))
	if not peers:
		promotion = daily_blog.artifacts.NoArtifact(
			daily_blog.artifacts.DailyOutline, "no_eligible_generation",
		)
		return _daily_outline_result(
			promotion, rankings, ranking_reviews, promoted, generation,
			daily_blog.replication.ReviewResult((), ()), True, value,
		)
	review = _review_outlines(
		value, config, budget, prepared, peers, cache_load, cache_accept,
	)
	promotion = daily_blog.replication.promote(
		peers, daily_blog.artifacts.DailyOutline,
		lambda item: daily_blog.artifacts.evaluate_eligibility(item, value.packets),
		review.votes,
	)
	if len(peers) == 1 and isinstance(promotion, daily_blog.artifacts.SelectedPeer):
		promotion = daily_blog.artifacts.DegradedPromotion(
			promotion.artifact, daily_blog.artifacts.DailyOutline, ("review_unavailable",),
		)
	return _daily_outline_result(
		promotion, rankings, ranking_reviews, promoted, generation, review, True, value,
	)

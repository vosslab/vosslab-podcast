"""Stage-neutral replicated generation, review, and promotion contracts."""

# Standard Library
import collections
import collections.abc
import dataclasses
import re

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.io_utils


EDITORIAL_RELIABILITY_SCHEMA = "vosslab.daily-blog.editorial-reliability"
MAX_REJECTION_CODES = 64
REJECTION_CODE_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
STEP_OUTCOMES = frozenset({"succeeded", "degraded"})
REVIEW_FAILURES = frozenset({
	"timeout", "start_failure", "process_failure", "empty_response", "invalid_verdict",
})


class ReviewUnavailable(RuntimeError):
	"""Signal that an optional comparison wave cannot be constructed safely."""


@dataclasses.dataclass(frozen=True)
class StepReliability:
	"""One factual bounded summary for a subjective editorial step."""

	step: str
	outcome: str
	attempted: int
	succeeded: int
	failed: int
	reused: int
	repaired: int
	disagreements: int
	best_artifact_id: str
	reasons: tuple[str, ...]
	rejection_counts: tuple[tuple[str, int], ...] = ()
	schema_version: str = EDITORIAL_RELIABILITY_SCHEMA
	response_chars: int = 0

	#============================================
	def validate(self) -> None:
		"""Reject inconsistent or unbounded reliability metadata."""
		counts = (self.attempted, self.succeeded, self.failed, self.reused,
			self.repaired, self.disagreements, self.response_chars)
		if self.schema_version != EDITORIAL_RELIABILITY_SCHEMA:
			raise RuntimeError("Editorial reliability schema is unsupported.")
		if type(self.step) is not str or not self.step or self.outcome not in STEP_OUTCOMES:
			raise RuntimeError("Editorial reliability step or outcome is invalid.")
		if any(type(value) is not int or value < 0 for value in counts):
			raise RuntimeError("Editorial reliability counts must be nonnegative integers.")
		if self.succeeded + self.failed != self.attempted:
			raise RuntimeError("Editorial reliability attempts do not match outcomes.")
		if self.reused > self.succeeded or self.repaired > self.succeeded:
			raise RuntimeError("Editorial reliability reuse or repair count is invalid.")
		if type(self.reasons) is not tuple or any(type(reason) is not str for reason in self.reasons):
			raise RuntimeError("Editorial reliability reasons must be text.")
		if tuple(sorted(set(self.reasons))) != self.reasons:
			raise RuntimeError("Editorial reliability reasons must be sorted and unique.")
		if (
			type(self.rejection_counts) is not tuple
			or len(self.rejection_counts) > MAX_REJECTION_CODES
			or tuple(sorted(self.rejection_counts)) != self.rejection_counts
			or len({code for code, _count in self.rejection_counts}) != len(self.rejection_counts)
			or any(
				type(code) is not str
				or REJECTION_CODE_RE.fullmatch(code) is None
				or type(count) is not int
				or not 0 < count <= self.attempted
				for code, count in self.rejection_counts
			)
		):
			raise RuntimeError("Editorial reliability rejection counts are invalid.")
		if self.outcome == "succeeded" and (self.reasons or self.rejection_counts):
			raise RuntimeError("Successful editorial work cannot retain degradation reasons.")

	#============================================
	def to_dict(self) -> dict:
		"""Serialize validated bounded stage facts."""
		self.validate()
		value = dataclasses.asdict(self)
		value["reasons"] = list(self.reasons)
		value["rejection_counts"] = [
			{"code": code, "count": count} for code, count in self.rejection_counts
		]
		return value

	#============================================
	@classmethod
	def from_dict(cls, value: dict) -> "StepReliability":
		"""Restore only the current reliability summary shape."""
		fields = {field.name for field in dataclasses.fields(cls)}
		legacy_fields = fields - {"response_chars"}
		if (
			type(value) is not dict
			or set(value) not in (fields, legacy_fields)
			or type(value["reasons"]) is not list
			or type(value["rejection_counts"]) is not list
			or any(
				type(item) is not dict or set(item) != {"code", "count"}
				for item in value["rejection_counts"]
			)
		):
			raise RuntimeError("Editorial reliability summary uses unsupported fields.")
		summary = cls(
			value["step"], value["outcome"], value["attempted"], value["succeeded"],
			value["failed"], value["reused"], value["repaired"], value["disagreements"],
			value["best_artifact_id"], tuple(value["reasons"]),
			tuple((item["code"], item["count"]) for item in value["rejection_counts"]),
			value["schema_version"], value.get("response_chars", 0),
		)
		summary.validate()
		return summary


@dataclasses.dataclass(frozen=True)
class ReplicatedCandidate:
	"""One generation attempt and its independently re-evaluated artifact."""

	request: daily_blog.agents.RouteRequest
	result: daily_blog.agents.AgentResult
	artifact: daily_blog.artifacts.EditorialArtifact | None
	eligibility: daily_blog.artifacts.EligibilityResult | None
	failure: str = ""
	mechanical_eligibility: daily_blog.artifacts.EligibilityResult | None = None


@dataclasses.dataclass(frozen=True)
class ReplicationResult:
	"""Inspectable non-durable generation observations for one artifact rung."""

	expected_type: type
	candidates: tuple[ReplicatedCandidate, ...]

	#============================================
	@property
	def eligible(self) -> tuple[daily_blog.artifacts.EditorialArtifact, ...]:
		"""Return only exact-rung artifacts that passed the supplied mechanical test."""
		return tuple(
			item.artifact for item in self.candidates
			if type(item.artifact) is self.expected_type
			and item.eligibility is not None and item.eligibility.eligible
		)


#============================================
def response_characters(result: ReplicationResult) -> int:
	"""Return the aggregate text received from successful isolated routes."""
	if type(result) is not ReplicationResult:
		raise RuntimeError("Response character count requires an exact replication result.")
	characters = sum(len(item.result.text) for item in result.candidates if item.result.ok)
	return characters


#============================================
def generation_reliability(
	step: str,
	result: ReplicationResult,
	reasons: collections.abc.Iterable[str] = (),
) -> StepReliability:
	"""Summarize one replicated generation mechanism with bounded rejection counts."""
	values = result.candidates
	all_reasons = set(reasons) | {item.failure for item in values if item.failure}
	rejection_counts: dict[str, int] = {}
	for item in values:
		if not item.result.ok or item.eligibility is None or item.eligibility.eligible:
			continue
		if not item.eligibility.reasons:
			all_reasons.add("ineligible_generation")
		for reason in item.eligibility.reasons:
			all_reasons.add(reason)
			rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
	attempted = len(values)
	succeeded = sum(
		item.result.ok and item.eligibility is not None and item.eligibility.eligible
		for item in values
	)
	reused = sum(item.result.ok and item.result.resumed for item in values)
	outcome = "degraded" if all_reasons else "succeeded"
	summary = StepReliability(
		step, outcome, attempted, succeeded, attempted - succeeded, reused,
		0, 0, "", tuple(sorted(all_reasons)), tuple(sorted(rejection_counts.items())),
		response_chars=response_characters(result),
	)
	return summary


@dataclasses.dataclass(frozen=True)
class CandidateSetReviewAssignment:
	"""One independent reviewer and its sole candidate ordering."""

	reviewer_index: int
	candidate_artifact_ids: tuple[str, ...]

	#============================================
	def __post_init__(self) -> None:
		"""Require one bounded, unique complete-set ordering."""
		if (
			type(self.reviewer_index) is not int or self.reviewer_index < 0
			or type(self.candidate_artifact_ids) is not tuple
			or len(self.candidate_artifact_ids) < 2
			or any(type(value) is not str or not value for value in self.candidate_artifact_ids)
			or len(set(self.candidate_artifact_ids)) != len(self.candidate_artifact_ids)
		):
			raise RuntimeError("Candidate-set review assignment is invalid.")


@dataclasses.dataclass(frozen=True)
class CandidateSetReviewWork:
	"""One request that presents the complete candidate set exactly once."""

	request: daily_blog.agents.RouteRequest
	assignment: CandidateSetReviewAssignment


@dataclasses.dataclass(frozen=True)
class CandidateSetReviewVote:
	"""One independent selection from the complete candidate set."""

	review_id: str
	candidate_artifact_ids: tuple[str, ...]
	status: str
	winner_artifact_id: str
	failure: str = ""
	resumed: bool = False

	#============================================
	def __post_init__(self) -> None:
		"""Require one winner from the reviewed set or one bounded failure."""
		CandidateSetReviewAssignment(0, self.candidate_artifact_ids)
		if self.status not in {"succeeded", "failed"} or type(self.resumed) is not bool:
			raise RuntimeError("Candidate-set review status is unsupported.")
		if self.status == "succeeded":
			if self.winner_artifact_id not in self.candidate_artifact_ids or self.failure:
				raise RuntimeError("Candidate-set review winner is outside its candidates.")
		elif self.winner_artifact_id or self.failure not in REVIEW_FAILURES:
			raise RuntimeError("Failed candidate-set review requires one bounded failure.")


@dataclasses.dataclass(frozen=True)
class CandidateSetReviewResult:
	"""Bounded complete-set reviewer work and its observations."""

	work: tuple[CandidateSetReviewWork, ...]
	votes: tuple[CandidateSetReviewVote, ...]


@dataclasses.dataclass(frozen=True)
class _PromotionCandidate:
	"""One mechanically evaluated artifact considered for promotion."""

	artifact_id: str
	content_hash: str
	eligibility: daily_blog.artifacts.EligibilityResult


@dataclasses.dataclass(frozen=True)
class _PromotionDecision:
	"""Resolved promotion outcome before constructing a public artifact result."""

	artifact_id: str
	method: str
	reasons: tuple[str, ...]
	disagreements: int
	preserved: bool = False


#============================================
def replicate(
	requests: collections.abc.Sequence[daily_blog.agents.RouteRequest],
	runner: object,
	budget: daily_blog.agents.RouteBudget,
	expected_type: type,
	parse: collections.abc.Callable[
		[daily_blog.agents.AgentResult], daily_blog.artifacts.EditorialArtifact,
	],
	eligibility: collections.abc.Callable[
		[daily_blog.artifacts.EditorialArtifact], daily_blog.artifacts.EligibilityResult,
	],
	cache_load: collections.abc.Callable[
		[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None,
	] | None = None,
	cache_accept: collections.abc.Callable[
		[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None,
	] | None = None,
	cache_eligibility: collections.abc.Callable[
		[daily_blog.artifacts.EditorialArtifact], daily_blog.artifacts.EligibilityResult,
	] | None = None,
) -> ReplicationResult:
	"""Run independent generation and cache only explicitly grounded responses."""
	if expected_type not in daily_blog.artifacts.ARTIFACT_TYPES or not requests:
		raise RuntimeError("Replication requires requests and a supported exact artifact type.")
	results = daily_blog.agents.execute_requests(
		list(requests), runner, requests[0].maximum_parallel_calls, budget, cache_load,
	)
	observations = []
	for request, result in zip(requests, results):
		if not result.ok:
			observations.append(ReplicatedCandidate(request, result, None, None, result.failure))
			continue
		try:
			artifact = parse(result)
			if type(artifact) is not expected_type:
				raise RuntimeError("Generator returned an artifact from the wrong ladder rung.")
			decision = eligibility(artifact)
			if type(decision) is not daily_blog.artifacts.EligibilityResult:
				raise RuntimeError("Replication eligibility must return EligibilityResult.")
			cache_decision = decision if cache_eligibility is None else cache_eligibility(artifact)
			if type(cache_decision) is not daily_blog.artifacts.EligibilityResult:
				raise RuntimeError("Replication cache eligibility must return EligibilityResult.")
			if cache_decision.eligible and not result.resumed and cache_accept is not None:
				cache_accept(request, result)
			observations.append(ReplicatedCandidate(
				request, result, artifact, decision, "", cache_decision,
			))
		except daily_blog.agents.RepairableStructuredOutput:
			observations.append(ReplicatedCandidate(request, result, None, None, "ineligible_generation"))
	return ReplicationResult(expected_type, tuple(observations))


#============================================
def _canonical_artifacts(
	candidates: collections.abc.Iterable[daily_blog.artifacts.EditorialArtifact],
	expected_type: type,
) -> tuple[daily_blog.artifacts.EditorialArtifact, ...]:
	"""Return a stable exact-rung peer set independent of caller ordering."""
	values = tuple(candidates)
	if any(type(item) is not expected_type for item in values):
		raise RuntimeError("Editorial candidates must use the expected exact artifact type.")
	if len({item.artifact_id for item in values}) != len(values):
		raise RuntimeError("Editorial candidates require unique artifact identities.")
	return tuple(sorted(values, key=lambda item: (item.content_hash, item.artifact_id)))


#============================================
def review_candidate_set(
	candidates: collections.abc.Iterable[daily_blog.artifacts.EditorialArtifact],
	expected_type: type,
	reviewer_count: int,
	build_work: collections.abc.Callable[
		[tuple[daily_blog.artifacts.EditorialArtifact, ...], CandidateSetReviewAssignment],
		CandidateSetReviewWork,
	],
	parse_winner: collections.abc.Callable[[str, CandidateSetReviewWork], str],
	runner: object,
	budget: daily_blog.agents.RouteBudget,
	cache_load: collections.abc.Callable[
		[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None,
	] | None = None,
	cache_accept: collections.abc.Callable[
		[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None,
	] | None = None,
	observe_result: collections.abc.Callable[
		[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None,
	] | None = None,
) -> CandidateSetReviewResult:
	"""Evaluate the complete peer set once per independent reviewer."""
	if type(reviewer_count) is not int or reviewer_count <= 0:
		raise RuntimeError("Candidate-set review requires a positive reviewer count.")
	canonical = _canonical_artifacts(candidates, expected_type)
	if len(canonical) < 2:
		return CandidateSetReviewResult((), ())
	work = []
	canonical_ids = {item.artifact_id for item in canonical}
	for reviewer_index in range(reviewer_count):
		offset = reviewer_index % len(canonical)
		ordered = canonical[offset:] + canonical[:offset]
		if reviewer_index % 2:
			ordered = tuple(reversed(ordered))
		assignment = CandidateSetReviewAssignment(
			reviewer_index, tuple(item.artifact_id for item in ordered),
		)
		try:
			item = build_work(ordered, assignment)
		except ReviewUnavailable:
			return CandidateSetReviewResult((), ())
		if (
			type(item) is not CandidateSetReviewWork
			or item.assignment != assignment
			or set(item.assignment.candidate_artifact_ids) != canonical_ids
		):
			raise RuntimeError("Candidate-set review work conflicts with its assignment.")
		work.append(item)
	if len({item.request.request_id for item in work}) != len(work):
		raise RuntimeError("Candidate-set review requires unique request identities.")
	if len({item.request.identity_sha256 for item in work}) != len(work):
		raise RuntimeError("Candidate-set review requires unique work identities.")
	results = daily_blog.agents.execute_requests(
		[item.request for item in work], runner, work[0].request.maximum_parallel_calls,
		budget, cache_load,
	)
	votes = []
	for item, result in zip(work, results):
		if observe_result is not None:
			observe_result(item.request, result)
		if not result.ok:
			vote = CandidateSetReviewVote(
				item.request.request_id, item.assignment.candidate_artifact_ids,
				"failed", "", result.failure, result.resumed,
			)
		else:
			try:
				winner = parse_winner(result.text, item)
			except daily_blog.agents.RepairableStructuredOutput:
				winner = ""
			if winner in item.assignment.candidate_artifact_ids:
				vote = CandidateSetReviewVote(
					item.request.request_id, item.assignment.candidate_artifact_ids,
					"succeeded", winner, "", result.resumed,
				)
				if not result.resumed and cache_accept is not None:
					cache_accept(item.request, result)
			else:
				vote = CandidateSetReviewVote(
					item.request.request_id, item.assignment.candidate_artifact_ids,
					"failed", "", "invalid_verdict", result.resumed,
				)
		votes.append(vote)
	return CandidateSetReviewResult(tuple(work), tuple(votes))


#============================================
def review_reasons(
	votes: collections.abc.Iterable[CandidateSetReviewVote],
	disagreements: int,
) -> tuple[str, ...]:
	"""Return bounded categorical observations without reviewer response content."""
	reasons = {"review_" + vote.failure for vote in votes if vote.status == "failed"}
	if disagreements:
		reasons.add("review_disagreement")
	return tuple(sorted(reasons))


#============================================
def review_disagreements(
	votes: collections.abc.Iterable[CandidateSetReviewVote],
) -> int:
	"""Count reviewed sets whose successful reviewers select different candidates."""
	by_set: dict[tuple[str, ...], set[str]] = collections.defaultdict(set)
	for vote in votes:
		if type(vote) is CandidateSetReviewVote:
			candidate_set = tuple(sorted(vote.candidate_artifact_ids))
		else:
			raise RuntimeError("Editorial review vote type is unsupported.")
		if vote.status == "succeeded":
			by_set[candidate_set].add(vote.winner_artifact_id)
	return sum(len(winners) > 1 for winners in by_set.values())


#============================================
def promote(
	candidates: collections.abc.Iterable[daily_blog.artifacts.EditorialArtifact],
	expected_type: type,
	eligibility: collections.abc.Callable[
		[daily_blog.artifacts.EditorialArtifact], daily_blog.artifacts.EligibilityResult,
	],
	votes: collections.abc.Iterable[CandidateSetReviewVote],
	incumbent: daily_blog.artifacts.EditorialArtifact | None = None,
	fallback: collections.abc.Callable[
		[], daily_blog.artifacts.EditorialArtifact | None,
	] | None = None,
) -> (
	daily_blog.artifacts.SelectedPeer
	| daily_blog.artifacts.PreservedArtifact
	| daily_blog.artifacts.DegradedPromotion
	| daily_blog.artifacts.NoArtifact
):
	"""Promote an exact-rung eligible artifact without positional preference."""
	if expected_type not in daily_blog.artifacts.ARTIFACT_TYPES:
		raise RuntimeError("Promotion requires a supported exact artifact type.")
	ordered = _canonical_artifacts(candidates, expected_type)
	incumbent_artifact: daily_blog.artifacts.EditorialArtifact | None = incumbent
	incumbent_matches_rung = (
		incumbent_artifact is None or type(incumbent_artifact) is expected_type
	)
	if not incumbent_matches_rung:
		raise RuntimeError("Editorial incumbent must use the expected exact artifact type.")
	evaluated = tuple((item, eligibility(item)) for item in ordered)
	if any(
		type(decision) is not daily_blog.artifacts.EligibilityResult
		for _item, decision in evaluated
	):
		raise RuntimeError("Promotion eligibility must return EligibilityResult.")
	eligible: tuple[daily_blog.artifacts.EditorialArtifact, ...] = tuple(
		item for item, decision in evaluated if decision.eligible
	)
	if incumbent_artifact is not None and not eligibility(incumbent_artifact).eligible:
		raise RuntimeError("Editorial incumbent must remain mechanically eligible.")
	if incumbent_artifact is not None and incumbent_artifact.artifact_id not in {item.artifact_id for item in eligible}:
		eligible = tuple(sorted(
			eligible + (incumbent_artifact,),
			key=lambda item: (item.content_hash, item.artifact_id),
		))
	identity_candidates = tuple(
		_PromotionCandidate(item.artifact_id, item.content_hash, eligibility(item)) for item in eligible
	)
	vote_values = tuple(votes)
	if not eligible:
		if fallback is not None:
			value = fallback()
			if value is not None:
				if type(value) is not expected_type:
					raise RuntimeError("Editorial fallback returned the wrong ladder rung.")
				if eligibility(value).eligible:
					return daily_blog.artifacts.DegradedPromotion(
						value,
						expected_type,
						("no_eligible_generation",),
					)
		return daily_blog.artifacts.NoArtifact(expected_type, "no_eligible_generation")
	incumbent_id = incumbent_artifact.artifact_id if incumbent_artifact else ""
	decision = _decide_artifact_promotion(identity_candidates, vote_values, incumbent_id)
	if decision is None:
		raise RuntimeError("Eligible promotion candidates unexpectedly disappeared.")
	if decision.preserved:
		return daily_blog.artifacts.PreservedArtifact(incumbent, expected_type)
	winner = next(item for item in eligible if item.artifact_id == decision.artifact_id)
	if decision.reasons:
		return daily_blog.artifacts.DegradedPromotion(winner, expected_type, decision.reasons)
	return daily_blog.artifacts.SelectedPeer(winner, expected_type)


#============================================
def _decide_artifact_promotion(
	values: tuple[_PromotionCandidate, ...],
	vote_values: tuple[CandidateSetReviewVote, ...],
	incumbent_id: str,
) -> _PromotionDecision | None:
	"""Resolve review votes and incumbency for mechanically eligible artifacts."""
	if len({item.artifact_id for item in values}) != len(values):
		raise RuntimeError("Promotion candidates require unique artifact identities.")
	if any(type(item.eligibility) is not daily_blog.artifacts.EligibilityResult for item in values):
		raise RuntimeError("Identity promotion requires exact EligibilityResult values.")
	eligible = tuple(item for item in values if item.eligibility.eligible)
	by_id = {item.artifact_id: item for item in eligible}
	if incumbent_id and incumbent_id not in by_id:
		raise RuntimeError("Editorial incumbent must remain mechanically eligible.")
	for vote in vote_values:
		if type(vote) is CandidateSetReviewVote:
			reviewed_ids = set(vote.candidate_artifact_ids)
		else:
			raise RuntimeError("Editorial review vote type is unsupported.")
		if reviewed_ids - set(by_id):
			raise RuntimeError("Editorial review set is outside eligible promotion candidates.")
	disagreements = review_disagreements(vote_values)
	reasons = review_reasons(vote_values, disagreements)
	if len(eligible) > 1 and not any(vote.status == "succeeded" for vote in vote_values):
		reasons = tuple(sorted(set(reasons) | {"review_unavailable"}))
	if not eligible:
		return None
	def stable(items: collections.abc.Iterable[_PromotionCandidate]) -> _PromotionCandidate:
		return sorted(items, key=lambda item: (item.content_hash, item.artifact_id))[0]
	if incumbent_id:
		set_votes = tuple(
			vote for vote in vote_values if type(vote) is CandidateSetReviewVote
		)
		if set_votes:
			# Every complete-set reviewer saw the incumbent. Optional review failure or
			# a tie therefore preserves it; only one strict plurality challenger wins.
			if any(vote.status != "succeeded" for vote in set_votes):
				return _PromotionDecision(
					incumbent_id, "incumbent_preserved", reasons, disagreements, True,
				)
			scores = collections.Counter(vote.winner_artifact_id for vote in set_votes)
			best = max(scores.values())
			incumbent_score = scores[incumbent_id]
			challengers = [
				item for item in eligible
				if item.artifact_id != incumbent_id
				and scores[item.artifact_id] == best
				and scores[item.artifact_id] > incumbent_score
			]
			if len(challengers) != 1:
				return _PromotionDecision(
					incumbent_id, "incumbent_preserved",
					reasons or ("review_disagreement",), disagreements, True,
				)
			return _PromotionDecision(
				challengers[0].artifact_id, "review_votes", reasons, disagreements,
			)
		return _PromotionDecision(
			incumbent_id, "incumbent_preserved",
			reasons or ("review_unavailable",), disagreements, True,
		)
	scores = collections.Counter(
		vote.winner_artifact_id
		for vote in vote_values
		if vote.status == "succeeded"
	)
	if scores:
		best = max(scores[item.artifact_id] for item in eligible)
		leaders = [item for item in eligible if scores[item.artifact_id] == best]
		return _PromotionDecision(stable(leaders).artifact_id, "review_votes", reasons, disagreements)
	return _PromotionDecision(
		stable(eligible).artifact_id,
		"stable_peer_choice",
		reasons or ("review_unavailable",),
		disagreements,
	)

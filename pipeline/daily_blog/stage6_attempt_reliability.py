"""Stage 6 execution-time attempt-ledger projection."""

# Standard Library
import collections.abc

# local repo modules
import daily_blog.agents
import daily_blog.attempt_ledger
import daily_blog.artifacts
import daily_blog.replication
import daily_blog.stage6_attempt_plan


#============================================
def _review_disagreements(
	votes: collections.abc.Iterable[daily_blog.replication.ReviewVote],
) -> int:
	"""Count candidate-pair conflicts without retaining reviewer prose."""
	pairs: dict[tuple[str, str], set[str]] = {}
	for vote in votes:
		if vote.status == "succeeded":
			pair = tuple(sorted((vote.first_artifact_id, vote.second_artifact_id)))
			pairs.setdefault(pair, set()).add(vote.winner_artifact_id)
	return sum(len(winners) > 1 for winners in pairs.values())


#============================================
def review_reliability(
	review: daily_blog.replication.ReviewResult,
	promotion: object,
	reasons: collections.abc.Iterable[str] = (),
) -> daily_blog.replication.StepReliability:
	"""Summarize actual review routes, repairs, and pair disagreements."""
	votes = review.votes
	disagreements = _review_disagreements(votes)
	all_reasons = set(reasons) | set(
		daily_blog.replication.review_reasons(votes, disagreements)
	)
	best = (
		"" if isinstance(promotion, daily_blog.artifacts.NoArtifact)
		else promotion.artifact.artifact_id
	)
	return daily_blog.replication.StepReliability(
		"6.3", "degraded" if all_reasons else "succeeded", len(votes),
		sum(item.status == "succeeded" for item in votes),
		sum(item.status == "failed" for item in votes), 0,
		sum(item.repaired and item.status == "succeeded" for item in votes),
		disagreements, best, tuple(sorted(all_reasons)),
	)


#============================================
def promotion_reliability(
	promotion: object,
	votes: collections.abc.Iterable[daily_blog.replication.ReviewVote],
) -> daily_blog.replication.StepReliability:
	"""Record deterministic selection separately from route observations."""
	if isinstance(promotion, daily_blog.artifacts.NoArtifact):
		reasons, best = (promotion.reason,), ""
	elif isinstance(promotion, daily_blog.artifacts.DegradedPromotion):
		reasons, best = promotion.reasons, promotion.artifact.artifact_id
	else:
		reasons, best = (), promotion.artifact.artifact_id
	return daily_blog.replication.StepReliability(
		"6.4", "degraded" if reasons else "succeeded", 1, 1, 0, 0, 0,
		_review_disagreements(votes), best, tuple(sorted(reasons)),
	)


#============================================
def stage6_attempt_ledger(
	plan: daily_blog.stage6_attempt_plan.Stage6AttemptPlan,
	observations: tuple[object, ...],
	generation: "daily_blog.replication.ReplicationResult",
	editing: "daily_blog.replication.ReplicationResult",
	review: "daily_blog.replication.ReviewResult",
	selected_artifact_id: str = "",
) -> daily_blog.attempt_ledger.AttemptLedger:
	"""Close Stage 6's observable slots into one canonical terminal ledger.

	The maximum plan remains the capacity authority. A dependency-closed
	materialization defines the applicable terminal slots; unavailable conditional
	review and repair templates remain absent rather than acquiring inferred facts.
	"""
	if (
		type(plan) is not daily_blog.stage6_attempt_plan.Stage6AttemptPlan
		or type(observations) is not tuple
		or type(generation) is not daily_blog.replication.ReplicationResult
		or type(editing) is not daily_blog.replication.ReplicationResult
		or type(review) is not daily_blog.replication.ReviewResult
		or type(selected_artifact_id) is not str
	):
		raise RuntimeError("Stage 6 reliability requires exact execution observations.")
	results: dict[str, daily_blog.agents.AgentResult] = {}
	materialized: set[str] = set()
	for observation in observations:
		materialization = getattr(observation, "materialization", None)
		observed = getattr(observation, "results", None)
		if (
			type(materialization) is not daily_blog.stage6_attempt_plan.MaterializedStage6AttemptPlan
			or materialization.plan != plan
			or type(observed) is not tuple
		):
			raise RuntimeError("Stage 6 reliability observation is invalid.")
		for attempt, result in zip(materialization.attempts, observed, strict=True):
			if attempt.semantic_identity in results or type(result) is not daily_blog.agents.AgentResult:
				raise RuntimeError("Stage 6 reliability observations overlap or are invalid.")
			if result.request_id != attempt.semantic_identity:
				raise RuntimeError("Stage 6 reliability result identity conflicts with its slot.")
			results[attempt.semantic_identity] = result
			materialized.add(attempt.semantic_identity)
	candidates = _stage6_candidates(generation, editing)
	selected_slot_id = _selected_slot_id(plan, candidates, selected_artifact_id)
	artifacts = {
		item.artifact.artifact_id: item.artifact.content_hash
		for item in candidates.values() if item.artifact is not None
	}
	votes = {item.review_id: item for item in review.votes}
	work = {item.request.request_id: item for item in review.work}
	facts: list[daily_blog.attempt_ledger.AttemptFact] = []
	for attempt in plan.attempts:
		slot_id = attempt.semantic_identity
		if slot_id not in materialized:
			continue
		result = results[slot_id]
		if attempt.work_kind == "generation":
			candidate = candidates.get(slot_id)
			if candidate is None or candidate.result != result:
				raise RuntimeError("Stage 6 generation outcome lacks its exact candidate observation.")
			fact = _generation_attempt_fact(candidate, selected_slot_id)
		else:
			fact = _review_attempt_fact(attempt, result, work, votes, artifacts)
		facts.append(fact)
	if selected_slot_id and not any(
		item.terminal_disposition == "selected" for item in facts
	):
		raise RuntimeError("Stage 6 selection lacks a selected generation fact.")
	return daily_blog.attempt_ledger.AttemptLedger(tuple(item.slot_id for item in facts), tuple(facts))


#============================================
def observed_stage6_attempt_prefix_ledger(
	plan: daily_blog.stage6_attempt_plan.Stage6AttemptPlan,
	observations: tuple[object, ...],
) -> daily_blog.attempt_ledger.AttemptLedger:
	"""Validate an exact dependency-closed observed Stage 6 prefix.

	Each batch carries its execution-time closed facts.  This boundary combines
	the typed materialization witnesses rather than re-parsing route output or
	inferring outcomes from logs.  The returned ledger records only the exact
	dependency-closed union through the last observed rung and fresh batch.
	Callers use it before recovery to establish that the primary facts are sound;
	the terminal reconciliation API determines whether the prefix is final.
	"""
	if type(plan) is not daily_blog.stage6_attempt_plan.Stage6AttemptPlan or type(observations) is not tuple or not observations:
		raise RuntimeError("Stage 6 observed-prefix reliability requires a plan and observations.")
	views = []
	for observation in observations:
		view = getattr(observation, "materialization", None)
		facts = getattr(observation, "closed_facts", None)
		if (
			type(view) is not daily_blog.stage6_attempt_plan.MaterializedStage6AttemptPlan
			or view.plan != plan
			or type(facts) is not tuple
			or tuple(item.slot_id for item in facts) != view.semantic_identities
		):
			raise RuntimeError("Stage 6 observed-prefix reliability requires closed batch facts.")
		views.append(view)
	coordinates = tuple((
		daily_blog.stage6_attempt_plan.RUNG_ORDER.index(view.final_rung), view.final_batch_index,
	) for view in views)
	if coordinates != tuple(sorted(coordinates)) or len(set(coordinates)) != len(coordinates):
		raise RuntimeError("Stage 6 observed-prefix observations must be ordered by rung and batch.")
	available = tuple(item for view in views for item in view.available_generation_slot_ids)
	bindings = tuple(item for view in views for item in view.candidate_pair_bindings)
	repairs = tuple(item for view in views for item in view.repair_source_slot_ids)
	if len(available) != len(set(available)) or len(repairs) != len(set(repairs)):
		raise RuntimeError("Stage 6 observed-prefix observations overlap generation or repair slots.")
	if len({(item.rung, item.batch_index, item.pair_index) for item in bindings}) != len(bindings):
		raise RuntimeError("Stage 6 observed-prefix observations overlap candidate pair witnesses.")
	last = views[-1]
	materialization = plan.materialize(
		last.final_rung, last.final_batch_index, available, bindings, repairs,
	)
	facts_by_slot = {
		fact.slot_id: fact for observation in observations for fact in observation.closed_facts
	}
	if len(facts_by_slot) != sum(len(observation.closed_facts) for observation in observations):
		raise RuntimeError("Stage 6 observed-prefix observations overlap closed facts.")
	if set(facts_by_slot) != set(materialization.semantic_identities):
		raise RuntimeError("Stage 6 observed-prefix facts do not close the materialized plan.")
	return daily_blog.attempt_ledger.AttemptLedger(
		materialization.semantic_identities,
		tuple(facts_by_slot[slot] for slot in materialization.semantic_identities),
	)


#============================================
def aggregate_stage6_attempt_ledger(
	plan: daily_blog.stage6_attempt_plan.Stage6AttemptPlan,
	observations: tuple[object, ...],
) -> daily_blog.attempt_ledger.AttemptLedger:
	"""Reconcile an observed Stage 6 prefix as its final durable ledger.

	This terminal boundary builds on exact observed-prefix validation.  It accepts
	early selection and final-ladder exhaustion while keeping an exhausted primary
	prefix available for recovery without presenting it as a durable outcome.
	"""
	ledger = observed_stage6_attempt_prefix_ledger(plan, observations)
	views = tuple(getattr(observation, "materialization", None) for observation in observations)
	last = views[-1]
	if type(last) is not daily_blog.stage6_attempt_plan.MaterializedStage6AttemptPlan:
		raise RuntimeError("Stage 6 terminal reliability requires an exact final materialization.")
	# The terminal view combines the already validated prefix witnesses, so it
	# matches the complete ledger rather than only its final batch observation.
	materialization = plan.materialize(
		last.final_rung, last.final_batch_index,
		tuple(slot for view in views for slot in view.available_generation_slot_ids),
		tuple(binding for view in views for binding in view.candidate_pair_bindings),
		tuple(slot for view in views for slot in view.repair_source_slot_ids),
	)
	daily_blog.stage6_attempt_plan.reconcile_stage6_attempt_summary(materialization, ledger)
	return ledger


#============================================
def _selected_slot_id(
	plan: daily_blog.stage6_attempt_plan.Stage6AttemptPlan,
	candidates: dict[str, "daily_blog.replication.ReplicatedCandidate"],
	selected_artifact_id: str,
) -> str:
	"""Choose the first canonical generated representative for a selected artifact."""
	if not selected_artifact_id:
		return ""
	for attempt in plan.attempts:
		candidate = candidates.get(attempt.semantic_identity)
		if (
			attempt.work_kind == "generation" and candidate is not None
			and candidate.artifact is not None
			and candidate.artifact.artifact_id == selected_artifact_id
		):
			return attempt.semantic_identity
	return ""


#============================================
def _stage6_candidates(
	generation: "daily_blog.replication.ReplicationResult", editing: "daily_blog.replication.ReplicationResult",
) -> dict[str, "daily_blog.replication.ReplicatedCandidate"]:
	"""Index exact generation observations without choosing a winner."""
	values = generation.candidates + editing.candidates
	if any(type(item) is not daily_blog.replication.ReplicatedCandidate for item in values):
		raise RuntimeError("Stage 6 generation observations are invalid.")
	indexed = {item.request.request_id: item for item in values}
	if len(indexed) != len(values):
		raise RuntimeError("Stage 6 generation observations repeat a request identity.")
	return indexed


#============================================
def _attempt_source(result: daily_blog.agents.AgentResult) -> str:
	"""Classify immutable route provenance without treating retries as slots."""
	return "cache_reuse" if result.resumed else "fresh_route"


#============================================
def _route_failure_fact(
	slot_id: str, result: daily_blog.agents.AgentResult, feedback: str = "",
) -> daily_blog.attempt_ledger.AttemptFact:
	"""Close a failed route with its exact bounded transport category."""
	transport = result.failure if result.failure in daily_blog.attempt_ledger.ROUTE_REASON_BY_TRANSPORT else "process_failure"
	return daily_blog.attempt_ledger.AttemptFact(
		slot_id, _attempt_source(result), result.attempts,
		result.attempts if result.resumed else 0, transport, "transport", "route_failed",
		daily_blog.attempt_ledger.ROUTE_REASON_BY_TRANSPORT[transport],
		"", feedback,
	)


#============================================
def _generation_attempt_fact(
	candidate: "daily_blog.replication.ReplicatedCandidate", selected_slot_id: str,
) -> daily_blog.attempt_ledger.AttemptFact:
	"""Project one parser/admission outcome already decided by Stage 6."""
	result = candidate.result
	feedback = ""
	identity = candidate.request.stage6_cache_identity
	if identity is not None and candidate.request.role == "editor":
		feedback = identity.feedback_envelope_sha256
	if not result.ok:
		return _route_failure_fact(candidate.request.request_id, result, feedback)
	source = _attempt_source(result)
	restored = result.attempts if result.resumed else 0
	if candidate.artifact is None:
		return daily_blog.attempt_ledger.AttemptFact(candidate.request.request_id, source, result.attempts, restored,
			"success", "transport", "parse_rejected", "response_parse_failure", "", feedback)
	mechanical = candidate.mechanical_eligibility
	if type(mechanical) is not daily_blog.artifacts.EligibilityResult:
		raise RuntimeError("Stage 6 generation lacks its mechanical admission outcome.")
	if not mechanical.eligible:
		return daily_blog.attempt_ledger.AttemptFact(candidate.request.request_id, source, result.attempts, restored,
			"success", "parsed", "mechanical_rejected", "mechanical_ineligible",
			candidate.artifact.content_hash, feedback)
	if candidate.eligibility is None:
		raise RuntimeError("Stage 6 generation lacks its publication admission outcome.")
	if not candidate.eligibility.eligible:
		return daily_blog.attempt_ledger.AttemptFact(candidate.request.request_id, source, result.attempts, restored,
			"success", "publication_policy", "policy_rejected",
			_policy_reason_code(candidate.eligibility.reasons), candidate.artifact.content_hash, feedback)
	if candidate.request.request_id == selected_slot_id:
		return daily_blog.attempt_ledger.AttemptFact(candidate.request.request_id, source, result.attempts, restored,
			"success", "selected", "selected", "", candidate.artifact.content_hash, feedback)
	return daily_blog.attempt_ledger.AttemptFact(candidate.request.request_id, source, result.attempts, restored,
		"success", "publication_policy", "eligible_not_selected", "", candidate.artifact.content_hash, feedback)


#============================================
def _policy_reason_code(reasons: tuple[str, ...]) -> str:
	"""Map admission's detailed findings to the frozen safe reason vocabulary."""
	if type(reasons) is not tuple or not reasons or any(type(item) is not str for item in reasons):
		raise RuntimeError("Stage 6 policy rejection lacks an exact finding.")
	joined = " ".join(reasons).casefold()
	if "image" in joined:
		return "image_authority_mismatch"
	if "citation" in joined:
		return "citation_density_mismatch"
	if "evidence" in joined:
		return "evidence_grounding_mismatch"
	return "presentation_policy_mismatch"


#============================================
def _review_attempt_fact(
	attempt: daily_blog.stage6_attempt_plan.PlannedStage6Attempt,
	result: daily_blog.agents.AgentResult,
	work: dict[str, "daily_blog.replication.ReviewWork"], votes: dict[str, "daily_blog.replication.ReviewVote"],
	artifacts: dict[str, str],
) -> daily_blog.attempt_ledger.AttemptFact:
	"""Project a review or named review-repair without retaining response text."""
	slot_id = attempt.semantic_identity
	if not result.ok:
		return _route_failure_fact(slot_id, result)
	source_slot = attempt.repair_of_identity or slot_id
	item = work.get(source_slot)
	vote = votes.get(source_slot)
	if item is None or vote is None:
		raise RuntimeError("Stage 6 review result lacks its exact resolution.")
	if item.first_artifact_id not in artifacts or item.second_artifact_id not in artifacts:
		raise RuntimeError("Stage 6 review candidate identities are unavailable.")
	source = _attempt_source(result)
	restored = result.attempts if result.resumed else 0
	candidate_hash = artifacts[item.first_artifact_id]
	resolved_here = vote.repaired == (attempt.work_kind == "review_repair")
	if vote.status == "failed" or not resolved_here:
		return daily_blog.attempt_ledger.AttemptFact(slot_id, source, result.attempts, restored, "success", "review",
			"review_rejected", "review_rejected", candidate_hash)
	return daily_blog.attempt_ledger.AttemptFact(slot_id, source, result.attempts, restored, "success", "review",
		"review_completed", "", candidate_hash)

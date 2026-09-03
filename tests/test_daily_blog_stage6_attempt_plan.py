"""Offline contract tests for the immutable Stage 6 attempt topology."""

# Standard Library
import dataclasses
import hashlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.replication
import daily_blog.attempt_ledger
import daily_blog.stage6_attempt_plan


#============================================
def make_policy(fresh_batch_count: int = 1) -> daily_blog.stage6_attempt_plan.Stage6AttemptPolicy:
	"""Build a small valid policy without coupling tests to live tuning."""
	return daily_blog.stage6_attempt_plan.Stage6AttemptPolicy(2, 2, 1, 1, fresh_batch_count)


#============================================
def route_failure(slot_id: str) -> daily_blog.attempt_ledger.AttemptFact:
	"""Close one test slot with a valid non-secret terminal transport fact."""
	return daily_blog.attempt_ledger.AttemptFact(
		slot_id, "fresh_route", 1, 0, "timeout", "transport", "route_failed", "route_timeout",
	)


#============================================
def generation_ids(
	plan: daily_blog.stage6_attempt_plan.Stage6AttemptPlan,
	rung: str,
	batch_index: int,
) -> tuple[str, ...]:
	"""Return only dispatchable generation identities through one boundary."""
	return tuple(
		item.semantic_identity for item in plan.terminal_prefix(rung, batch_index)
		if item.work_kind == "generation"
	)


#============================================
def candidate_pair(
	rung: str, batch_index: int, pair_index: int,
) -> daily_blog.stage6_attempt_plan.Stage6CandidatePairBinding:
	"""Build one safe, ordered dynamic peer witness without raw artifacts."""
	def identity(label: str) -> str:
		return hashlib.sha256(label.encode("ascii")).hexdigest()
	first = identity(f"{rung}:{batch_index}:{pair_index}:first")
	second = identity(f"{rung}:{batch_index}:{pair_index}:second")
	if first > second:
		first, second = second, first
	return daily_blog.stage6_attempt_plan.Stage6CandidatePairBinding(
		rung, batch_index, pair_index, first, second,
	)


#============================================
def test_batch_identity_is_fresh_while_transport_identity_is_stable() -> None:
	"""Fresh samples differ by batch; same slot has no retry-ordinal identity."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy(2))
	first = next(item for item in plan.attempts if item.rung == "primary" and item.batch_index == 0)
	second = next(item for item in plan.attempts if item.rung == "primary" and item.batch_index == 1 and item.role == first.role)
	assert first.semantic_identity != second.semantic_identity
	assert first.semantic_input_identity != second.semantic_input_identity


#============================================
def test_repair_binds_the_exact_preceding_review_identity() -> None:
	"""Repairs cannot be relinked to a different review slot."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy())
	repair = next(item for item in plan.attempts if item.work_kind == "review_repair")
	review = next(item for item in plan.attempts if (
		item.work_kind == "review"
		and item.rung == repair.rung
		and item.batch_index == repair.batch_index
		and item.replica_index == repair.replica_index
		and item.pair_index == repair.pair_index
		and item.display_order == repair.display_order
	))
	assert repair.repair_of_identity == review.semantic_identity
	with pytest.raises(RuntimeError, match="repair source"):
		dataclasses.replace(repair, repair_of_identity="0" * 64)


#============================================
def test_primary_failure_requires_later_recovery_materialization() -> None:
	"""A no-selection primary prefix cannot be summarized as global exhaustion."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy(2))
	materialization = plan.materialize(
		"primary", 0, generation_ids(plan, "primary", 0),
	)
	ledger = daily_blog.attempt_ledger.AttemptLedger(
		materialization.semantic_identities,
		tuple(route_failure(item.semantic_identity) for item in materialization.attempts),
	)
	with pytest.raises(RuntimeError, match="final applicable"):
		daily_blog.stage6_attempt_plan.reconcile_stage6_attempt_summary(materialization, ledger)


#============================================
def test_materialization_omits_unavailable_review_pairs_without_false_skips() -> None:
	"""Candidate absence removes review work instead of inventing skip facts."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy())
	available = tuple(
		item.semantic_identity for item in plan.attempts if item.work_kind == "generation"
	)
	materialization = plan.materialize("repository_story_merge", 0, available)
	assert materialization.semantic_identities == available
	ledger = daily_blog.attempt_ledger.AttemptLedger(
		materialization.semantic_identities,
		tuple(route_failure(slot_id) for slot_id in materialization.semantic_identities),
	)
	summary = daily_blog.stage6_attempt_plan.reconcile_stage6_attempt_summary(materialization, ledger)
	assert summary.skipped == 0


#============================================
def test_final_ladder_reports_exhaustion_after_no_selection() -> None:
	"""Only a final no-selection materialization reports exhaustion."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy())
	final = plan.materialize(
		"repository_story_merge", 0,
		generation_ids(plan, "repository_story_merge", 0),
	)
	failed = daily_blog.attempt_ledger.AttemptLedger(
		final.semantic_identities,
		tuple(route_failure(slot_id) for slot_id in final.semantic_identities),
	)
	assert daily_blog.stage6_attempt_plan.reconcile_stage6_attempt_summary(final, failed).exhausted == 1


#============================================
def test_materialization_rejects_generation_outside_its_terminal_boundary() -> None:
	"""Generation materialization stays within its named terminal boundary."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy())
	later = next(item for item in plan.attempts if item.rung == "daily_outline_expansion")
	with pytest.raises(RuntimeError, match="noncanonical or post-terminal"):
		plan.materialize("primary", 0, (later.semantic_identity,))


#============================================
def test_materialization_rejects_orphan_repair_slot() -> None:
	"""A repair is derived only with its materialized review dependency."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy())
	repair = next(item for item in plan.attempts if item.work_kind == "review_repair")
	with pytest.raises(RuntimeError, match="dependency-closed"):
		daily_blog.stage6_attempt_plan.MaterializedStage6AttemptPlan(
			plan, "repository_story_merge", 0, (), (), (repair,),
		)


#============================================
def test_materialization_rejects_lone_review_slot() -> None:
	"""Review work is derived from a pair witness rather than a bare slot."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy())
	review = next(item for item in plan.attempts if item.work_kind == "review")
	with pytest.raises(RuntimeError, match="dependency-closed"):
		daily_blog.stage6_attempt_plan.MaterializedStage6AttemptPlan(
			plan, "primary", 0, (), (), (review,),
		)


#============================================
def test_candidate_pair_binding_requires_distinct_safe_digests() -> None:
	"""Each dynamic witness contains two distinct fixed-size candidate digests."""
	first = "1" * 64
	with pytest.raises(RuntimeError, match="distinct canonical"):
		daily_blog.stage6_attempt_plan.Stage6CandidatePairBinding("primary", 0, 1, first, first)
	with pytest.raises(RuntimeError, match="SHA-256"):
		daily_blog.stage6_attempt_plan.Stage6CandidatePairBinding("primary", 0, 1, "unsafe", "2" * 64)


#============================================
def test_candidate_pair_binding_requires_canonical_peer_order() -> None:
	"""A pair witness has one deterministic peer order before slot derivation."""
	with pytest.raises(RuntimeError, match="distinct canonical"):
		daily_blog.stage6_attempt_plan.Stage6CandidatePairBinding(
			"primary", 0, 1, "f" * 64, "1" * 64,
		)


#============================================
def test_candidate_pair_binding_requires_canonical_prefix_coordinates() -> None:
	"""Dynamic pair witnesses stay within one contiguous terminal prefix."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy())
	valid = candidate_pair("primary", 0, 1)
	with pytest.raises(RuntimeError, match="contiguous dynamic"):
		plan.materialize("primary", 0, (), (dataclasses.replace(valid, pair_index=2),))
	with pytest.raises(RuntimeError, match="noncanonical or post-terminal"):
		plan.materialize("primary", 0, (), (candidate_pair("daily_outline_expansion", 0, 1),))


#============================================
def test_materialization_derives_review_and_repair_from_valid_dynamic_pair_subset() -> None:
	"""A canonical dynamic subset derives all reviewers and repairs, never bare slots."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy())
	binding = candidate_pair("primary", 0, 1)
	review_slots = tuple(
		item.semantic_identity for item in plan.attempts_for("primary", 0)
		if item.work_kind == "review" and item.pair_index == 1
	)
	materialization = plan.materialize(
		"primary", 0, generation_ids(plan, "primary", 0), (binding,), review_slots,
	)
	reviews = tuple(item for item in materialization.attempts if item.work_kind == "review")
	repairs = tuple(item for item in materialization.attempts if item.work_kind == "review_repair")
	assert {item.pair_index for item in reviews} == {1}
	assert {item.repair_of_identity for item in repairs} == {item.semantic_identity for item in reviews}


#============================================
def test_materialization_requires_canonical_repair_source_order() -> None:
	"""A repair witness sequence follows its immutable planned-review order."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy())
	binding = candidate_pair("primary", 0, 1)
	review_slots = tuple(
		item.semantic_identity for item in plan.attempts_for("primary", 0)
		if item.work_kind == "review" and item.pair_index == 1
	)
	with pytest.raises(RuntimeError, match="canonical planned-review order"):
		plan.materialize(
			"primary", 0, generation_ids(plan, "primary", 0), (binding,),
			tuple(reversed(review_slots)),
		)

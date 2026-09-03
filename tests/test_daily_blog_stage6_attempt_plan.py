"""Offline contract tests for the bounded Stage 6 attempt topology."""

# Standard Library
import hashlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.stage6_attempt_plan


#============================================
def make_policy(fresh_batch_count: int = 1) -> daily_blog.stage6_attempt_plan.Stage6AttemptPolicy:
	"""Build a small valid policy without coupling tests to live tuning."""
	return daily_blog.stage6_attempt_plan.Stage6AttemptPolicy(2, 2, 3, 1, fresh_batch_count)


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
def candidate_set(
	rung: str, batch_index: int,
) -> daily_blog.stage6_attempt_plan.Stage6CandidateSetBinding:
	"""Build one safe canonical complete-set witness without raw artifacts."""
	identities = tuple(sorted(
		hashlib.sha256(f"{rung}:{batch_index}:{index}".encode("ascii")).hexdigest()
		for index in range(5)
	))
	return daily_blog.stage6_attempt_plan.Stage6CandidateSetBinding(
		rung, batch_index, identities,
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
def test_plan_review_slots_scale_with_reviewers_not_candidate_count() -> None:
	"""Every rung reserves exactly one review slot per independent reviewer."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy())
	for rung in daily_blog.stage6_attempt_plan.RUNG_ORDER:
		reviews = tuple(item for item in plan.attempts_for(rung, 0) if item.work_kind == "review")
		assert len(reviews) == 3
		assert {item.replica_index for item in reviews} == {1, 2, 3}


#============================================
def test_materialization_rejects_generation_outside_its_terminal_boundary() -> None:
	"""Generation materialization stays within its named terminal boundary."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy())
	later = next(item for item in plan.attempts if item.rung == "daily_outline_expansion")
	with pytest.raises(RuntimeError, match="noncanonical or post-terminal"):
		plan.materialize("primary", 0, (later.semantic_identity,))


#============================================
def test_candidate_set_binding_requires_canonical_distinct_digests() -> None:
	"""A review witness contains one complete canonical identity set."""
	with pytest.raises(RuntimeError, match="distinct canonical SHA-256"):
		daily_blog.stage6_attempt_plan.Stage6CandidateSetBinding(
			"primary", 0, ("1" * 64, "1" * 64),
		)
	with pytest.raises(RuntimeError, match="distinct canonical SHA-256"):
		daily_blog.stage6_attempt_plan.Stage6CandidateSetBinding(
			"primary", 0, ("unsafe", "2" * 64),
		)


#============================================
def test_materialization_derives_one_slot_per_reviewer_from_complete_set() -> None:
	"""One set witness derives the bounded reviewer wave, never candidate pairs."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy())
	materialization = plan.materialize(
		"primary", 0, generation_ids(plan, "primary", 0), (candidate_set("primary", 0),),
	)
	reviews = tuple(item for item in materialization.attempts if item.work_kind == "review")
	assert len(reviews) == 3


#============================================
def test_materialization_rejects_duplicate_or_post_terminal_set_bindings() -> None:
	"""Only one complete-set witness belongs to each admitted review wave."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy())
	binding = candidate_set("primary", 0)
	with pytest.raises(RuntimeError, match="unique per review wave"):
		plan.materialize("primary", 0, (), (binding, binding))
	with pytest.raises(RuntimeError, match="noncanonical or post-terminal"):
		plan.materialize("primary", 0, (), (candidate_set("daily_outline_expansion", 0),))

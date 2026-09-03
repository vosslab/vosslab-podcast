"""Offline contract tests for the immutable Stage 6 attempt topology."""

# Standard Library
import dataclasses
import hashlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.stage6_attempt_plan


#============================================
def make_policy(fresh_batch_count: int = 1) -> daily_blog.stage6_attempt_plan.Stage6AttemptPolicy:
	"""Build a small valid policy without coupling tests to live tuning."""
	return daily_blog.stage6_attempt_plan.Stage6AttemptPolicy(2, 2, 1, 1, fresh_batch_count)


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
def test_materialization_rejects_generation_outside_its_terminal_boundary() -> None:
	"""Generation materialization stays within its named terminal boundary."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy())
	later = next(item for item in plan.attempts if item.rung == "daily_outline_expansion")
	with pytest.raises(RuntimeError, match="noncanonical or post-terminal"):
		plan.materialize("primary", 0, (later.semantic_identity,))


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
def test_materialization_derives_reviews_from_valid_dynamic_pair_subset() -> None:
	"""A canonical dynamic subset derives all reviewer slots, never bare slots."""
	plan = daily_blog.stage6_attempt_plan.build_stage6_attempt_plan(make_policy())
	binding = candidate_pair("primary", 0, 1)
	materialization = plan.materialize(
		"primary", 0, generation_ids(plan, "primary", 0), (binding,),
	)
	reviews = tuple(item for item in materialization.attempts if item.work_kind == "review")
	assert {item.pair_index for item in reviews} == {1}

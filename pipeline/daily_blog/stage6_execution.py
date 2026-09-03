"""Shared plan-bound request mechanics for Stage 6 execution paths."""

# Standard Library
import dataclasses

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.editorial_stage_config
import daily_blog.io_utils
import daily_blog.replication
import daily_blog.route_cache
import daily_blog.stage6_attempt_plan


#============================================
def planned_attempt(
	plan: daily_blog.stage6_attempt_plan.Stage6AttemptPlan,
	rung: str, batch_index: int, role: str, replica_index: int,
	pair_index: int = 0, display_order: int = 0,
) -> daily_blog.stage6_attempt_plan.PlannedStage6Attempt:
	"""Return the exact canonical slot for public execution coordinates."""
	matches = tuple(item for item in plan.attempts_for(rung, batch_index) if (
		item.role == role and item.replica_index == replica_index
		and item.pair_index == pair_index and item.display_order == display_order
	))
	if len(matches) != 1:
		raise RuntimeError("Stage 6 execution requires one canonical planned slot.")
	return matches[0]


#============================================
def build_request(
	value: object, run_id: str,
	attempt: daily_blog.stage6_attempt_plan.PlannedStage6Attempt,
	materialization: daily_blog.stage6_attempt_plan.MaterializedStage6AttemptPlan,
	route: daily_blog.editorial_stage_config.RoleRoute, prompt: str,
	config: daily_blog.editorial_stage_config.CompletePostConfig, contract_version: str,
	candidate_identities: tuple[str, ...] = (),
	repair_response: str = "", working_directory: str = "",
) -> daily_blog.agents.RouteRequest:
	"""Build one route request with its validated Stage 6 semantic witness."""
	prototype = daily_blog.agents.RouteRequest(
		request_id=attempt.semantic_identity, step=attempt.stage, route=route,
		prompt=prompt, working_directory=working_directory, role=attempt.role,
		retry_attempts=config.route_retry_attempts,
		maximum_parallel_calls=config.maximum_parallel_calls,
		repair_of=attempt.repair_of_identity,
		input_hash=daily_blog.io_utils.hash_value({"run_id": run_id, "slot": attempt.semantic_identity}),
		contract_version=contract_version, cache_input_hash=attempt.semantic_identity,
	)
	identity = daily_blog.route_cache.build_stage6_cache_identity(
		materialization, attempt, prompt=prompt, candidate_identities=candidate_identities,
		repair_response=repair_response,
		route_name=route.name, route_contract_sha256=prototype.route_contract_sha256,
	)
	return dataclasses.replace(prototype, stage6_cache_identity=identity)


#============================================
def candidate_pair_bindings(
	peers: tuple[daily_blog.artifacts.CompletePost, ...], rung: str, batch_index: int,
) -> tuple[daily_blog.stage6_attempt_plan.Stage6CandidatePairBinding, ...]:
	"""Bind distinct dynamic candidate pairs to canonical plan coordinates."""
	by_content = {item.content_hash: item for item in peers}
	ordered = tuple(by_content[key] for key in sorted(by_content))
	bindings = []
	for first_index, first in enumerate(ordered):
		for second in ordered[first_index + 1:]:
			left, right = sorted((first.content_hash, second.content_hash))
			bindings.append(daily_blog.stage6_attempt_plan.Stage6CandidatePairBinding(
				rung, batch_index, len(bindings) + 1, left, right,
			))
	return tuple(bindings)


#============================================
def merge_generation(
	parts: tuple[daily_blog.replication.ReplicationResult, ...],
) -> daily_blog.replication.ReplicationResult:
	"""Keep actual generation observations across executed fresh batches."""
	return daily_blog.replication.ReplicationResult(
		daily_blog.artifacts.CompletePost,
		tuple(candidate for part in parts for candidate in part.candidates),
	)

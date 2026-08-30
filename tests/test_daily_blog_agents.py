"""M1 transport taxonomy, retry, budget, and cache tests."""

# PIP3 modules
import pytest

# local repo modules
import daily_blog.agents
import daily_blog.editorial_stage_config
import daily_blog.io_utils
import daily_blog.locks
import daily_blog.routes


def request(
	name: str = "one",
	*,
	retry_attempts: int = 0,
	maximum_parallel_calls: int = 2,
) -> daily_blog.agents.RouteRequest:
	"""Build one complete, non-secret M1 request identity."""
	return daily_blog.agents.RouteRequest(
		request_id=name,
		step="test_step",
		route=daily_blog.editorial_stage_config.RoleRoute("test_route", ("fake",)),
		prompt="trusted prompt " + name,
		working_directory="/work",
		role="test_role",
		retry_attempts=retry_attempts,
		maximum_parallel_calls=maximum_parallel_calls,
	)


class SequenceRunner:
	"""Return or raise the next deterministic outcome for every route call."""

	def __init__(self, outcomes: list[object]) -> None:
		"""Retain one finite route outcome sequence."""
		self.outcomes = list(outcomes)
		self.calls = 0

	def run(
		self,
		_route: daily_blog.editorial_stage_config.RoleRoute,
		_prompt: str,
		_working_directory: str,
	) -> str:
		"""Produce exactly the next controlled external transport outcome."""
		self.calls += 1
		outcome = self.outcomes.pop(0)
		if isinstance(outcome, BaseException):
			raise outcome
		return outcome


@pytest.mark.parametrize(("error", "failure"), [
	(daily_blog.routes.EditorialRouteTimeout("private"), "timeout"),
	(daily_blog.routes.EditorialRouteStartError("private"), "start_failure"),
	(daily_blog.routes.EditorialRouteProcessError("private"), "process_failure"),
	(daily_blog.routes.EditorialRouteEmptyResponse("private"), "empty_response"),
	("", "empty_response"),
	(" \t\n", "empty_response"),
])
def test_every_recoverable_transport_category_returns_a_typed_result(
	error: object,
	failure: str,
) -> None:
	"""Expected route failures remain editorial data, without raw diagnostics."""
	result = daily_blog.agents.execute_requests(
		[request()],
		SequenceRunner([error]),
		2,
		daily_blog.agents.RouteBudget(1, 2),
	)[0]

	assert (result.ok, result.failure, result.text) == (False, failure, "")
	assert result.attempts >= 1
	assert result.role == "test_role"
	assert result.route_name == "test_route"


def test_recoverable_failure_retries_until_a_later_success() -> None:
	"""A transient typed failure consumes an actual retry slot and then recovers."""
	runner = SequenceRunner([
		daily_blog.routes.EditorialRouteTimeout("private"), "recovered",
	])
	budget = daily_blog.agents.RouteBudget(2, 1)

	result = daily_blog.agents.execute_requests(
		[request(retry_attempts=1, maximum_parallel_calls=1)], runner, 1, budget
	)[0]

	assert (result.ok, result.failure, result.text) == (True, "", "recovered")
	assert result.attempts > 1


def test_whitespace_response_retries_then_records_only_nonempty_text() -> None:
	"""Whitespace-only output is a typed retryable failure, never publishable text."""
	runner = SequenceRunner([" \n", "recovered"])
	budget = daily_blog.agents.RouteBudget(2, 1)

	result = daily_blog.agents.execute_requests(
		[request(retry_attempts=1, maximum_parallel_calls=1)], runner, 1, budget
	)[0]

	assert (result.ok, result.failure, result.text) == (True, "", "recovered")
	assert result.attempts > 1


def test_recoverable_failure_stops_at_the_configured_retry_boundary() -> None:
	"""Bounded retry does not turn a permanently failing route into unbounded work."""
	runner = SequenceRunner([
		daily_blog.routes.EditorialRouteProcessError("private"),
		daily_blog.routes.EditorialRouteProcessError("private"),
		daily_blog.routes.EditorialRouteProcessError("private"),
	])
	budget = daily_blog.agents.RouteBudget(3, 1)

	result = daily_blog.agents.execute_requests(
		[request(retry_attempts=2, maximum_parallel_calls=1)], runner, 1, budget
	)[0]

	assert (result.ok, result.failure) == (False, "process_failure")
	assert result.attempts > 1


def test_unexpected_runner_defect_propagates_without_typed_failure_conversion() -> None:
	"""Implementation defects remain faults instead of being misclassified as editorial loss."""
	with pytest.raises(ValueError, match="implementation defect"):
		daily_blog.agents.execute_requests(
			[request()], SequenceRunner([ValueError("implementation defect")]), 2,
			daily_blog.agents.RouteBudget(1, 2),
		)


@pytest.mark.parametrize("error_type", [
	daily_blog.agents.RepairableStructuredOutput,
	daily_blog.agents.RepositoryEvidenceUnavailable,
	daily_blog.agents.EditorialTerminalError,
])
def test_non_route_taxonomy_classes_remain_precise_exceptions(
	error_type: type[RuntimeError],
) -> None:
	"""Non-route outcomes retain their class for their owning editorial boundary."""
	with pytest.raises(error_type, match="classified"):
		daily_blog.agents.execute_requests(
			[request(maximum_parallel_calls=1)], SequenceRunner([error_type("classified")]), 1,
			daily_blog.agents.RouteBudget(1, 1),
		)


def test_shared_budget_counts_actual_calls_across_multiple_stage_batches() -> None:
	"""Two stages sharing one budget cannot silently exceed the run's external limit."""
	budget = daily_blog.agents.RouteBudget(2, 1)
	daily_blog.agents.execute_requests(
		[request("first", maximum_parallel_calls=1)], SequenceRunner(["one"]), 1, budget
	)
	daily_blog.agents.execute_requests(
		[request("second", maximum_parallel_calls=1)], SequenceRunner(["two"]), 1, budget
	)
	with pytest.raises(daily_blog.agents.RouteBudgetExhausted, match="exhausted"):
		daily_blog.agents.execute_requests(
			[request("third", maximum_parallel_calls=1)], SequenceRunner(["three"]), 1, budget
		)


def test_resume_requires_full_checksum_validation_and_avoids_new_route_call() -> None:
	"""A valid resumable entry is reused; altered bytes are rejected before route work."""
	recorded: dict[str, object] = {}
	first = request(maximum_parallel_calls=1)
	first_runner = SequenceRunner(["sealed response"])
	first_result = daily_blog.agents.execute_requests(
		[first], first_runner, 1, daily_blog.agents.RouteBudget(1, 1),
	)[0]
	recorded.update(first_result.to_cache_dict())
	assert first_result.ok

	resumed = daily_blog.agents.execute_requests(
		[first], SequenceRunner([AssertionError("route should not run")]), 1,
		daily_blog.agents.RouteBudget(1, 1),
		cache_load=lambda _request: daily_blog.agents.AgentResult.from_cache_dict(recorded),
	)[0]
	assert resumed.resumed is True

	corrupt = dict(recorded)
	corrupt["text"] = "altered"
	with pytest.raises(RuntimeError, match="hash does not match"):
		daily_blog.agents.AgentResult.from_cache_dict(corrupt)


def test_cache_request_identity_mismatch_stops_before_route_work() -> None:
	"""A valid record for another request cannot trigger a fallback route call."""
	first = request("first", maximum_parallel_calls=1)
	second = request("second", maximum_parallel_calls=1)
	result = daily_blog.agents.execute_requests(
		[first], SequenceRunner(["sealed response"]), 1,
		daily_blog.agents.RouteBudget(1, 1),
	)[0]
	with pytest.raises(daily_blog.agents.EditorialIdentityError, match="does not match"):
		daily_blog.agents.execute_requests(
			[second], SequenceRunner([AssertionError("route work must not occur")]), 1,
			daily_blog.agents.RouteBudget(1, 1),
			cache_load=lambda _request: daily_blog.agents.AgentResult.from_cache_dict(
				result.to_cache_dict()
			),
		)


def test_cached_repair_provenance_mismatch_stops_before_route_work() -> None:
	"""A cache entry cannot alter repair provenance while retaining its valid checksums."""
	normal = request("normal", maximum_parallel_calls=1)
	result = daily_blog.agents.execute_requests(
		[normal], SequenceRunner(["sealed response"]), 1,
		daily_blog.agents.RouteBudget(1, 1),
	)[0]
	altered = result.to_cache_dict()
	altered["repaired"] = True
	cached = daily_blog.agents.AgentResult.from_cache_dict(altered)
	with pytest.raises(daily_blog.agents.EditorialIdentityError, match="does not match"):
		daily_blog.agents.execute_requests(
			[normal], SequenceRunner([AssertionError("provenance mismatch must stop route work")]), 1,
			daily_blog.agents.RouteBudget(1, 1),
			cache_load=lambda _request: cached,
		)

	assert result.matches(normal)
	assert not cached.matches(normal)


@pytest.mark.parametrize(("first", "second"), [
	(
		{"retry_attempts": 0, "maximum_parallel_calls": 1},
		{"retry_attempts": 1, "maximum_parallel_calls": 1},
	),
	(
		{"retry_attempts": 0, "maximum_parallel_calls": 1},
		{"retry_attempts": 0, "maximum_parallel_calls": 2},
	),
])
def test_request_identity_changes_when_execution_policy_changes(
	first: dict[str, int],
	second: dict[str, int],
) -> None:
	"""Distinct execution policies cannot reuse one hash-bound route result."""
	assert request(**first).identity_sha256 != request(**second).identity_sha256


def test_repair_request_marks_the_result_and_admits_one_source_repair() -> None:
	"""The M1 transport boundary retains repair provenance for one stage-owned repair call."""
	repair = daily_blog.agents.RouteRequest(
		request_id="repair", step="review_repair",
		route=daily_blog.editorial_stage_config.RoleRoute("reviewer", ("fake",)),
		prompt="repair this structured response", working_directory="/work",
		role="referee_repair", maximum_parallel_calls=1, repair_of="review_one",
		input_hash="projection", contract_version="v4",
	)
	result = daily_blog.agents.execute_requests(
		[repair], SequenceRunner(["{\"winner\":\"A\"}"]), 1,
		daily_blog.agents.RouteBudget(1, 1),
	)[0]

	assert (result.ok, result.repaired, result.role) == (True, True, "referee_repair")
	assert result.matches(repair)


def test_duplicate_repair_source_fails_without_consuming_a_route_slot() -> None:
	"""The budget admits exactly one repair for a logical response identity."""
	budget = daily_blog.agents.RouteBudget(2, 1)
	first = daily_blog.agents.RouteRequest(
		"repair_one", "review_repair", daily_blog.editorial_stage_config.RoleRoute("reviewer", ("fake",)),
		"repair", "/work", repair_of="review_one",
	)
	second = daily_blog.agents.RouteRequest(
		"repair_two", "review_repair", daily_blog.editorial_stage_config.RoleRoute("reviewer", ("fake",)),
		"repair", "/work", repair_of="review_one",
	)
	daily_blog.agents.execute_requests([first], SequenceRunner(["fixed"]), 1, budget)
	with pytest.raises(daily_blog.agents.DuplicateRepairAdmission, match="already used"):
		daily_blog.agents.execute_requests(
			[second], SequenceRunner([AssertionError("route must not run")]), 1, budget
		)


def test_duplicate_repair_batch_does_not_poison_a_later_valid_admission() -> None:
	"""A rejected duplicate batch changes neither call count nor repair admission state."""
	budget = daily_blog.agents.RouteBudget(1, 1)
	first = daily_blog.agents.RouteRequest(
		"repair_one", "review_repair", daily_blog.editorial_stage_config.RoleRoute("reviewer", ("fake",)),
		"repair", "/work", repair_of="review_one",
	)
	duplicate = daily_blog.agents.RouteRequest(
		"repair_two", "review_repair", daily_blog.editorial_stage_config.RoleRoute("reviewer", ("fake",)),
		"repair", "/work", repair_of="review_one",
	)
	with pytest.raises(daily_blog.agents.DuplicateRepairAdmission, match="duplicate"):
		daily_blog.agents.execute_requests(
			[first, duplicate], SequenceRunner([AssertionError("route must not run")]), 1, budget
		)
	result = daily_blog.agents.execute_requests([first], SequenceRunner(["fixed"]), 1, budget)[0]
	assert result.ok


def test_cached_repair_does_not_consume_admission_for_a_later_external_repair() -> None:
	"""A resumed repair is evidence, not a newly admitted external repair route."""
	repair = daily_blog.agents.RouteRequest(
		"cached_repair", "review_repair",
		daily_blog.editorial_stage_config.RoleRoute("reviewer", ("fake",)), "repair", "/work",
		maximum_parallel_calls=1, repair_of="source_one",
	)
	cached = daily_blog.agents.execute_requests(
		[repair], SequenceRunner(["cached"]), 1,
		daily_blog.agents.RouteBudget(1, 1),
	)[0]
	budget = daily_blog.agents.RouteBudget(1, 1)
	resumed = daily_blog.agents.execute_requests(
		[repair], SequenceRunner([AssertionError("cache must prevent route work")]), 1, budget,
		cache_load=lambda _request: daily_blog.agents.AgentResult.from_cache_dict(
			cached.to_cache_dict()
		),
	)[0]
	later = daily_blog.agents.RouteRequest(
		"later_repair", "review_repair",
		daily_blog.editorial_stage_config.RoleRoute("reviewer", ("fake",)), "repair", "/work",
		maximum_parallel_calls=1, repair_of="source_one",
	)
	assert resumed.resumed is True
	assert daily_blog.agents.execute_requests(
		[later], SequenceRunner(["fresh"]), 1, budget
	)[0].text == "fresh"


def test_invalid_cache_result_does_not_consume_repair_admission() -> None:
	"""Cache validation errors leave a repair source eligible for its real route call."""
	repair = daily_blog.agents.RouteRequest(
		"repair", "review_repair", daily_blog.editorial_stage_config.RoleRoute("reviewer", ("fake",)),
		"repair", "/work", maximum_parallel_calls=1, repair_of="source_one",
	)
	wrong_request = request("wrong", maximum_parallel_calls=1)
	wrong_result = daily_blog.agents.execute_requests(
		[wrong_request], SequenceRunner(["other"]), 1,
		daily_blog.agents.RouteBudget(1, 1),
	)[0]
	budget = daily_blog.agents.RouteBudget(1, 1)
	with pytest.raises(daily_blog.agents.EditorialIdentityError, match="does not match"):
		daily_blog.agents.execute_requests(
			[repair], SequenceRunner([AssertionError("invalid cache must stop first")]), 1, budget,
			cache_load=lambda _request: wrong_result,
		)
	assert daily_blog.agents.execute_requests(
		[repair], SequenceRunner(["fresh"]), 1, budget
	)[0].text == "fresh"


def test_mixed_repair_admission_rejection_does_not_reserve_new_sources() -> None:
	"""All-or-nothing batch admission preserves new sources after one duplicate fails."""
	budget = daily_blog.agents.RouteBudget(3, 1)
	used = daily_blog.agents.RouteRequest(
		"used", "review_repair", daily_blog.editorial_stage_config.RoleRoute("reviewer", ("fake",)),
		"repair", "/work", maximum_parallel_calls=1, repair_of="used_source",
	)
	daily_blog.agents.execute_requests([used], SequenceRunner(["used"]), 1, budget)
	new = daily_blog.agents.RouteRequest(
		"new", "review_repair", daily_blog.editorial_stage_config.RoleRoute("reviewer", ("fake",)),
		"repair", "/work", maximum_parallel_calls=1, repair_of="new_source",
	)
	with pytest.raises(daily_blog.agents.DuplicateRepairAdmission, match="already used"):
		daily_blog.agents.execute_requests(
			[new, used], SequenceRunner([AssertionError("batch must not run")]), 1, budget
		)
	result = daily_blog.agents.execute_requests(
		[new], SequenceRunner(["new"]), 1, budget
	)[0]
	assert result.text == "new"


def agent_result_values() -> dict[str, object]:
	"""Build one valid in-memory agent result payload for invariant tests."""
	return {
		"role": "author", "text": "answer", "ok": True, "failure": "", "attempts": 1,
		"duration_s": 0.1, "repaired": False, "resumed": False, "route_name": "author",
		"request_id": "one",
		"request_identity_sha256": daily_blog.io_utils.sha256_text("request"),
		"text_sha256": daily_blog.io_utils.sha256_text("answer"),
	}


@pytest.mark.parametrize("changes", [
	{"ok": "true"},
	{"attempts": True},
	{"duration_s": "0.1"},
	{"duration_s": float("nan")},
	{"text_sha256": "not-a-hash"},
	{"request_identity_sha256": "A" * 64},
	{"role": ""},
	{"route_name": ""},
	{"request_id": ""},
	{"text": " \t", "text_sha256": daily_blog.io_utils.sha256_text(" \t")},
])
def test_agent_result_constructor_rejects_exact_type_and_integrity_violations(
	changes: dict[str, object],
) -> None:
	"""Constructor validation rejects malformed in-memory result state before caching."""
	values = agent_result_values()
	values.update(changes)
	with pytest.raises(daily_blog.agents.EditorialIdentityError):
		daily_blog.agents.AgentResult(**values)

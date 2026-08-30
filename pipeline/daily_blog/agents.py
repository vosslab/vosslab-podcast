"""Typed, retried, globally bounded editorial command execution."""

# Standard Library
import collections.abc
import concurrent.futures
import contextlib
import dataclasses
import enum
import math
import re
import threading
import time

# local repo modules
import daily_blog.config
import daily_blog.editorial_stage_config
import daily_blog.io_utils
import daily_blog.routes


AGENT_RESULT_SCHEMA_VERSION = "vosslab.daily-blog.agent-result.v2"
RECOVERABLE_FAILURES = frozenset({
	"timeout", "start_failure", "process_failure", "empty_response",
})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class FailureClass(enum.StrEnum):
	"""The five bounded outcomes crossing the editorial route boundary."""

	RECOVERABLE_ROUTE = "recoverable_route"
	REPAIRABLE_STRUCTURED_OUTPUT = "repairable_structured_output"
	REPOSITORY_EVIDENCE_UNAVAILABLE = "repository_evidence_unavailable"
	TERMINAL = "terminal"
	IMPLEMENTATION_DEFECT = "implementation_defect"


class RepairableStructuredOutput(RuntimeError):
	"""A returned response needs its one allowed structured-output repair."""


class RepositoryEvidenceUnavailable(RuntimeError):
	"""A repository lacks evidence; its owning stage may degrade that repository."""


class EditorialTerminalError(RuntimeError):
	"""A configuration, path, identity, or cache fault that must remain a fault."""


class EditorialIdentityError(EditorialTerminalError):
	"""A request or cache result does not attest to the same immutable identity."""


class DuplicateRepairAdmission(EditorialTerminalError):
	"""A logical source response already consumed its sole repair admission."""


class RouteBudgetExhausted(RuntimeError):
	"""The run-owned external-call budget has no remaining actual-call slots."""


@dataclasses.dataclass(frozen=True)
class RouteRequest:
	"""One isolated editorial request with a cache-safe execution identity."""

	request_id: str
	step: str
	route: daily_blog.editorial_stage_config.RoleRoute
	prompt: str
	working_directory: str
	role: str = "editorial"
	retry_attempts: int = 0
	maximum_parallel_calls: int = 1
	repair_of: str = ""
	model: str = "openai-codex"
	model_options: tuple[str, ...] = ()
	input_hash: str = "unbound"
	contract_version: str = "unbound"
	cache_input_hash: str = "unbound"

	#============================================
	def __post_init__(self) -> None:
		"""Require one bounded, non-secret identity before any worker starts."""
		strings = (
			self.request_id, self.step, self.prompt, self.working_directory, self.role,
			self.model, self.input_hash, self.contract_version, self.cache_input_hash,
		)
		if any(type(value) is not str or not value for value in strings):
			raise EditorialTerminalError("Editorial route request strings must be non-empty.")
		if type(self.retry_attempts) is not int or self.retry_attempts < 0:
			raise EditorialTerminalError("Editorial retry attempts must be a nonnegative integer.")
		if type(self.maximum_parallel_calls) is not int or self.maximum_parallel_calls <= 0:
			raise EditorialTerminalError("Editorial parallel-call limit must be a positive integer.")
		if type(self.repair_of) is not str:
			raise EditorialIdentityError("Editorial repair source identity must be a string.")
		if self.repair_of and self.repair_of == self.request_id:
			raise EditorialIdentityError("Editorial repair source must differ from repair request.")
		if type(self.model_options) is not tuple or any(
			type(option) is not str or not option for option in self.model_options
		):
			raise EditorialTerminalError("Editorial model options must be a tuple of non-empty strings.")

	#============================================
	def identity_dict(self) -> dict[str, object]:
		"""Return exact cache identity without retaining prompt text or diagnostics."""
		return {
			"request_id": self.request_id,
			"step": self.step,
			"role": self.role,
			"route": dataclasses.asdict(self.route),
			"model": self.model,
			"model_options": list(self.model_options),
			"prompt_sha256": daily_blog.io_utils.sha256_text(self.prompt),
			"input_hash": self.input_hash,
			"contract_version": self.contract_version,
			"cache_input_hash": self.cache_input_hash,
			"working_directory": self.working_directory,
			"retry_attempts": self.retry_attempts,
			"maximum_parallel_calls": self.maximum_parallel_calls,
			"repair_of": self.repair_of,
		}

	#============================================
	@property
	def identity_sha256(self) -> str:
		"""Return the SHA-256 identity bound into every resumable result."""
		return daily_blog.io_utils.hash_value(self.identity_dict())

	#============================================
	@property
	def is_repair(self) -> bool:
		"""Expose repair provenance without accepting a caller-controlled Boolean."""
		return bool(self.repair_of)


@dataclasses.dataclass(frozen=True)
class AgentResult:
	"""One complete transport result, suitable for strict cache restoration."""

	role: str
	text: str
	ok: bool
	failure: str
	attempts: int
	duration_s: float
	repaired: bool
	resumed: bool
	route_name: str
	request_id: str
	request_identity_sha256: str
	text_sha256: str
	schema_version: str = AGENT_RESULT_SCHEMA_VERSION

	#============================================
	def __post_init__(self) -> None:
		"""Fail closed on malformed in-memory or deserialized transport state."""
		strings = (
			self.role, self.text, self.failure, self.route_name, self.request_id,
			self.request_identity_sha256, self.text_sha256, self.schema_version,
		)
		if any(type(value) is not str for value in strings):
			raise EditorialIdentityError("Editorial agent result has invalid string fields.")
		if not self.role or not self.route_name or not self.request_id:
			raise EditorialIdentityError("Editorial agent result identity fields must be non-empty.")
		if (
			SHA256_RE.fullmatch(self.request_identity_sha256) is None
			or SHA256_RE.fullmatch(self.text_sha256) is None
		):
			raise EditorialIdentityError("Editorial agent result hashes must be lowercase SHA-256.")
		if (
			type(self.ok) is not bool
			or type(self.repaired) is not bool
			or type(self.resumed) is not bool
		):
			raise EditorialIdentityError("Editorial agent result Boolean fields are invalid.")
		if type(self.attempts) is not int or self.attempts < 1:
			raise EditorialIdentityError("Editorial agent attempts must be a positive integer.")
		if (
			type(self.duration_s) not in (int, float)
			or not math.isfinite(self.duration_s)
			or self.duration_s < 0
		):
			raise EditorialIdentityError("Editorial agent duration must be nonnegative.")
		if self.schema_version != AGENT_RESULT_SCHEMA_VERSION:
			raise EditorialIdentityError("Editorial agent result schema is unsupported.")
		if self.ok != (self.failure == "") or self.ok != bool(self.text.strip()):
			raise EditorialIdentityError("Editorial agent success fields conflict.")
		if not self.ok and self.failure not in RECOVERABLE_FAILURES:
			raise EditorialIdentityError("Editorial agent failure category is unsupported.")
		if self.text_sha256 != daily_blog.io_utils.sha256_text(self.text):
			raise EditorialIdentityError("Editorial agent text hash does not match its content.")

	#============================================
	def matches(self, request: RouteRequest) -> bool:
		"""Return whether this result is safely bound to one exact request.

		The repaired flag is provenance, not presentation metadata: a cached repair
		can satisfy only the repair request which produced it.  Keep that binding
		here so every cache consumer uses the same fail-closed identity check.
		"""
		return (
			self.request_id == request.request_id
			and self.request_identity_sha256 == request.identity_sha256
			and self.role == request.role
			and self.route_name == request.route.name
			and self.repaired == request.is_repair
		)

	#============================================
	def to_cache_dict(self) -> dict[str, object]:
		"""Serialize only a successful completed call for coordinator-owned storage."""
		if not self.ok:
			raise EditorialIdentityError("Failed editorial agent results are not resumable cache entries.")
		return {
			"schema_version": self.schema_version,
			"role": self.role,
			"text": self.text,
			"ok": self.ok,
			"failure": self.failure,
			"attempts": self.attempts,
			"duration_s": self.duration_s,
			"repaired": self.repaired,
			"route_name": self.route_name,
			"request_id": self.request_id,
			"request_identity_sha256": self.request_identity_sha256,
			"text_sha256": self.text_sha256,
		}

	#============================================
	@classmethod
	def from_cache_dict(cls, value: object) -> "AgentResult":
		"""Restore one exact successful result from untrusted durable JSON."""
		# ASVS 1.5.2 and 2.2.1: exact fields/types reject cache confusion.
		fields = {
			"schema_version", "role", "text", "ok", "failure", "attempts",
			"duration_s", "repaired", "route_name", "request_id",
			"request_identity_sha256", "text_sha256",
		}
		if type(value) is not dict or set(value) != fields:
			raise EditorialIdentityError("Cached editorial agent result uses unsupported fields.")
		return cls(
			role=value["role"], text=value["text"], ok=value["ok"],
			failure=value["failure"], attempts=value["attempts"],
			duration_s=value["duration_s"], repaired=value["repaired"],
			resumed=True, route_name=value["route_name"],
			request_id=value["request_id"],
			request_identity_sha256=value["request_identity_sha256"],
			text_sha256=value["text_sha256"], schema_version=value["schema_version"],
		)


class RouteBudget:
	"""One run-owned, thread-safe global call and concurrency boundary."""

	#============================================
	def __init__(self, maximum_calls: int, maximum_parallel_calls: int | None = None) -> None:
		"""Create the one budget shared by every editorial stage in a run."""
		if type(maximum_calls) is not int or maximum_calls <= 0:
			raise RuntimeError("Editorial route-call budget must be a positive integer.")
		parallel = maximum_calls if maximum_parallel_calls is None else maximum_parallel_calls
		if type(parallel) is not int or parallel <= 0:
			raise RuntimeError("Editorial route concurrency must be a positive integer.")
		self.maximum_calls = maximum_calls
		self.maximum_parallel_calls = parallel
		self.used_calls = 0
		self._lock = threading.Lock()
		self._semaphore = threading.BoundedSemaphore(parallel)
		self._repaired_sources: set[str] = set()

	#============================================
	def admit_repair(self, repair_of: str) -> None:
		"""Atomically reserve the sole structured-output repair for one source response."""
		self.admit_repairs((repair_of,))

	#============================================
	def admit_repairs(self, repair_sources: collections.abc.Collection[str]) -> None:
		"""Atomically reserve an all-or-nothing set of repair source identities."""
		if any(type(source) is not str or not source for source in repair_sources):
			raise EditorialIdentityError("Editorial repair admission requires a source identity.")
		sources = set(repair_sources)
		if len(sources) != len(repair_sources):
			raise DuplicateRepairAdmission(
				"Editorial batch contains duplicate structured-output repair sources."
			)
		with self._lock:
			if sources & self._repaired_sources:
				raise DuplicateRepairAdmission(
					"Editorial source response already used its structured-output repair."
				)
			self._repaired_sources.update(sources)

	#============================================
	@contextlib.contextmanager
	def call_slot(self) -> collections.abc.Iterator[None]:
		"""Account one actual external call and hold the run-wide semaphore."""
		with self._lock:
			if self.used_calls >= self.maximum_calls:
				raise RouteBudgetExhausted("Editorial route-call budget is exhausted.")
			self.used_calls += 1
		self._semaphore.acquire()
		try:
			yield
		finally:
			self._semaphore.release()


#============================================
def _route_failure_status(error: BaseException) -> str:
	"""Map only expected external failures into safe retry categories."""
	if isinstance(error, daily_blog.routes.EditorialRouteTimeout):
		return "timeout"
	if isinstance(error, daily_blog.routes.EditorialRouteStartError):
		return "start_failure"
	if isinstance(error, daily_blog.routes.EditorialRouteProcessError):
		return "process_failure"
	if isinstance(error, daily_blog.routes.EditorialRouteEmptyResponse):
		return "empty_response"
	raise RuntimeError("Unsupported editorial route failure type.")


#============================================
def _result(
	request: RouteRequest,
	text: str,
	ok: bool,
	failure: str,
	attempts: int,
	duration_s: float,
) -> AgentResult:
	"""Construct one validated result without external diagnostics."""
	return AgentResult(
		role=request.role, text=text, ok=ok, failure=failure, attempts=attempts,
		duration_s=duration_s, repaired=request.is_repair, resumed=False,
		route_name=request.route.name, request_id=request.request_id,
		request_identity_sha256=request.identity_sha256,
		text_sha256=daily_blog.io_utils.sha256_text(text),
	)


#============================================
def _execute_request(request: RouteRequest, runner: object, budget: RouteBudget) -> AgentResult:
	"""Execute one request, retrying only the four typed route failure classes."""
	started = time.monotonic()
	run = getattr(runner, "run")
	for attempt in range(1, request.retry_attempts + 2):
		try:
			with budget.call_slot():
				response = run(request.route, request.prompt, request.working_directory)
		except (
			daily_blog.routes.EditorialRouteTimeout,
			daily_blog.routes.EditorialRouteStartError,
			daily_blog.routes.EditorialRouteProcessError,
			daily_blog.routes.EditorialRouteEmptyResponse,
		) as error:
			failure = _route_failure_status(error)
			if attempt <= request.retry_attempts:
				continue
			return _result(request, "", False, failure, attempt, time.monotonic() - started)
		if type(response) is not str:
			raise RuntimeError("Editorial route runner returned an unsupported response type.")
		if not response.strip():
			if attempt <= request.retry_attempts:
				continue
			return _result(request, "", False, "empty_response", attempt, time.monotonic() - started)
		return _result(request, response, True, "", attempt, time.monotonic() - started)
	raise RuntimeError("Editorial route retry loop ended unexpectedly.")


#============================================
def execute_requests(
	requests: list[RouteRequest],
	runner: object,
	maximum_parallel_calls: int,
	budget: RouteBudget,
	cache_load: collections.abc.Callable[[RouteRequest], AgentResult | None] | None = None,
) -> list[AgentResult]:
	"""Run cache misses concurrently without accepting or persisting raw output."""
	if type(maximum_parallel_calls) is not int or maximum_parallel_calls <= 0:
		raise EditorialTerminalError("Editorial parallel-call limit must be positive.")
	if any(request.maximum_parallel_calls != maximum_parallel_calls for request in requests):
		raise EditorialIdentityError("Editorial request identity conflicts with stage concurrency.")
	identifiers = [request.request_id for request in requests]
	if len(set(identifiers)) != len(identifiers):
		raise EditorialIdentityError("Editorial route request identities must be unique.")
	repair_sources = [request.repair_of for request in requests if request.repair_of]
	if len(set(repair_sources)) != len(repair_sources):
		raise DuplicateRepairAdmission(
			"Editorial batch contains duplicate structured-output repair sources."
		)
	results: dict[str, AgentResult] = {}
	missing: list[RouteRequest] = []
	for request in requests:
		cached = cache_load(request) if cache_load is not None else None
		if cached is None:
			missing.append(request)
			continue
		if not cached.ok or not cached.resumed or not cached.matches(request):
			raise EditorialIdentityError("Cached editorial result does not match its request.")
		results[request.request_id] = cached
	# Validate every cache entry before mutating repair state. A cached repair
	# does not consume a new external repair path.
	budget.admit_repairs(tuple(request.repair_of for request in missing if request.repair_of))
	if missing:
		workers = min(maximum_parallel_calls, budget.maximum_parallel_calls, len(missing))
		with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
			futures = {
				executor.submit(_execute_request, request, runner, budget): request
				for request in missing
			}
			for future in concurrent.futures.as_completed(futures):
				request = futures[future]
				# Unexpected implementation defects cross this boundary unchanged.
				result = future.result()
				results[request.request_id] = result
	return [results[request.request_id] for request in requests]

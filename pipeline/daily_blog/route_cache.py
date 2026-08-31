"""Coordinator-owned cache and capacity boundaries for editorial route work."""

# Standard Library
import collections.abc
import dataclasses
import threading

# local repo modules
import daily_blog.agents
import daily_blog.config
import daily_blog.io_utils
import daily_blog.locks


ROUTE_CACHE_SCHEMA_VERSION = "vosslab.daily-blog.route-cache.v1"
# Stage 6 owns two sequential, model-authored whole-post recovery rungs: daily
# outline expansion and repository-story merge.  Keeping the topology count at
# the admission boundary avoids a stage6 import cycle while reserving both
# configured retry envelopes before normal editorial work starts.
_STAGE6_SEQUENTIAL_WHOLE_POST_RECOVERY_CALLS = 2


class RouteCacheIntegrityError(daily_blog.agents.EditorialTerminalError):
	"""A durable route cache value conflicts with its immutable identity."""


@dataclasses.dataclass(frozen=True)
class RouteCacheEffect:
	"""One already-validated result awaiting a serial coordinator commit."""

	request: daily_blog.agents.RouteRequest
	result: daily_blog.agents.AgentResult

	def __post_init__(self) -> None:
		if (
			type(self.request) is not daily_blog.agents.RouteRequest
			or type(self.result) is not daily_blog.agents.AgentResult
		):
			raise RouteCacheIntegrityError("Route cache effects require exact route types.")
		if not self.result.ok or self.result.resumed or not self.result.matches(self.request):
			raise RouteCacheIntegrityError("Route cache effects require fresh matching successes.")


def _request_identity(request: daily_blog.agents.RouteRequest) -> dict[str, object]:
	"""Return immutable logical inputs without host execution paths or raw prompts."""
	return {
		"step": request.step,
		"role": request.role,
		"route": {"name": request.route.name, "command": list(request.route.command)},
		"model": request.model,
		"model_options": list(request.model_options),
		"prompt_sha256": daily_blog.io_utils.sha256_text(request.prompt),
		"cache_input_hash": request.cache_input_hash,
		"contract_version": request.contract_version,
	}


class RouteResultCache:
	"""Strict PhaseCache adapter for eligible editorial route responses only."""

	def __init__(self, cache: daily_blog.locks.PhaseCache) -> None:
		if type(cache) is not daily_blog.locks.PhaseCache:
			raise RouteCacheIntegrityError("Route cache requires the coordinator PhaseCache.")
		self._cache = cache

	def _identity(self, request: daily_blog.agents.RouteRequest) -> tuple[dict[str, object], str]:
		if request.cache_input_hash == "unbound":
			raise RouteCacheIntegrityError("Route cache requires a logical input fingerprint.")
		identity = _request_identity(request)
		return identity, daily_blog.io_utils.hash_value(identity)

	def _stored_result(
		self, request: daily_blog.agents.RouteRequest, result: daily_blog.agents.AgentResult,
	) -> dict[str, object]:
		if not result.ok or result.resumed or not result.matches(request):
			raise RouteCacheIntegrityError("Only fresh matching route successes may enter cache.")
		_identity, identity_hash = self._identity(request)
		value = result.to_cache_dict()
		# The normal AgentResult identity binds transient working_directory.  The
		# cache instead binds this result to the logical path-free request identity.
		value["request_identity_sha256"] = identity_hash
		return value

	def _envelope_value(self, effect: RouteCacheEffect) -> dict[str, object]:
		identity, identity_hash = self._identity(effect.request)
		return {
			"schema_version": ROUTE_CACHE_SCHEMA_VERSION,
			"request_identity": identity,
			"request_identity_sha256": identity_hash,
			"result": self._stored_result(effect.request, effect.result),
		}

	def _restore(
		self, request: daily_blog.agents.RouteRequest, value: object,
	) -> daily_blog.agents.AgentResult:
		# ASVS 1.5.2, 2.2.1-2.2.3, 5.3.2: exact JSON structure and every
		# identity binding are revalidated before the result becomes reusable.
		if type(value) is not dict or set(value) != {
			"schema_version", "request_identity", "request_identity_sha256", "result",
		}:
			raise RouteCacheIntegrityError("Cached route result uses unsupported fields.")
		identity, identity_hash = self._identity(request)
		if (
			value["schema_version"] != ROUTE_CACHE_SCHEMA_VERSION
			or value["request_identity"] != identity
			or value["request_identity_sha256"] != identity_hash
		):
			raise RouteCacheIntegrityError("Cached route result identity does not match request.")
		stored = daily_blog.agents.AgentResult.from_cache_dict(value["result"])
		if (
			stored.request_identity_sha256 != identity_hash
			or stored.role != request.role
			or stored.route_name != request.route.name
			or stored.repaired != request.is_repair
		):
			raise RouteCacheIntegrityError("Cached route result does not match route request.")
		return dataclasses.replace(
			stored, request_identity_sha256=request.identity_sha256, resumed=True,
		)

	def load(self, request: daily_blog.agents.RouteRequest) -> daily_blog.agents.AgentResult | None:
		"""Load one valid logical request result or fail closed on corruption."""
		_identity, identity_hash = self._identity(request)
		value = self._cache.load_json("route_result", identity_hash, "result.json")
		return None if value is None else self._restore(request, value)

	def commit(self, effects: collections.abc.Iterable[RouteCacheEffect]) -> None:
		"""Validate then atomically persist compatible effects in canonical order."""
		pending: dict[str, tuple[RouteCacheEffect, dict[str, object]]] = {}
		for effect in effects:
			if type(effect) is not RouteCacheEffect:
				raise RouteCacheIntegrityError("Route cache commit requires RouteCacheEffect values.")
			_identity, key = self._identity(effect.request)
			value = self._envelope_value(effect)
			previous = pending.get(key)
			if previous is not None and previous[1] != value:
				raise RouteCacheIntegrityError("Conflicting buffered route cache effects.")
			pending[key] = (effect, value)
		for key in sorted(pending):
			effect, value = pending[key]
			try:
				self._cache.compare_create_json("route_result", key, "result.json", value)
			except RuntimeError as error:
				raise RouteCacheIntegrityError("Conflicting durable route cache value.") from error


class BufferedRouteEffects:
	"""Thread-safe job-local validated effects with no durable writer capability."""

	def __init__(self, cache: RouteResultCache) -> None:
		if type(cache) is not RouteResultCache:
			raise RouteCacheIntegrityError("Buffered route effects require a route result cache.")
		self._cache = cache
		self._effects: dict[str, RouteCacheEffect] = {}
		self._lock = threading.Lock()

	def load(self, request: daily_blog.agents.RouteRequest) -> daily_blog.agents.AgentResult | None:
		"""Read a local validated value first, then the coordinator-owned cache."""
		_identity, key = self._cache._identity(request)
		with self._lock:
			effect = self._effects.get(key)
		if effect is not None:
			return dataclasses.replace(effect.result, resumed=True)
		return self._cache.load(request)

	def accept(
		self, request: daily_blog.agents.RouteRequest,
		result: daily_blog.agents.AgentResult,
	) -> None:
		"""Record only a caller-validated fresh result without persisting it."""
		effect = RouteCacheEffect(request, result)
		_identity, key = self._cache._identity(request)
		with self._lock:
			previous = self._effects.get(key)
			if previous is not None and previous != effect:
				raise RouteCacheIntegrityError("Conflicting buffered route cache effect.")
			self._effects[key] = effect

	def drain(self) -> tuple[RouteCacheEffect, ...]:
		"""Return a deterministic immutable snapshot for serial coordinator commit."""
		with self._lock:
			return tuple(self._effects[key] for key in sorted(self._effects))


@dataclasses.dataclass(frozen=True)
class RunCapacityPlan:
	"""Frozen run admission derived from configured work and repository scope."""

	maximum_calls: int
	maximum_parallel_calls: int

	def __post_init__(self) -> None:
		if (
			type(self.maximum_calls) is not int or self.maximum_calls <= 0
			or type(self.maximum_parallel_calls) is not int or self.maximum_parallel_calls <= 0
		):
			raise daily_blog.agents.EditorialTerminalError("Run capacity must be positive.")

	@classmethod
	def for_run(
		cls, config: daily_blog.config.DailyBlogConfig, repository_count: int,
	) -> "RunCapacityPlan":
		"""Admit all configured stage envelopes before any editorial dispatch."""
		if type(config) is not daily_blog.config.DailyBlogConfig:
			raise daily_blog.agents.EditorialTerminalError("Run capacity requires DailyBlogConfig.")
		if type(repository_count) is not int or repository_count < 0:
			raise daily_blog.agents.EditorialTerminalError("Repository count must be nonnegative.")
		stages = (
			config.repository_outline, config.repository_story, config.daily_outline,
			config.complete_post, config.final_synthesis,
		)
		try:
			# Each Stage 6 recovery rung is one whole-post route request with the
			# complete-post retry envelope.  They execute sequentially, but both must
			# be admitted because the first can exhaust without yielding an eligible
			# post.  The primary Stage 6 cap covers only its normal writer/editor/review
			# work.
			recovery_reserve = (
				_STAGE6_SEQUENTIAL_WHOLE_POST_RECOVERY_CALLS
				* (config.complete_post.route_retry_attempts + 1)
			)
			calls = (
				repository_count * (
					config.repository_outline.max_route_calls
					+ config.repository_story.max_route_calls
				)
				+ config.daily_outline.max_route_calls + config.complete_post.max_route_calls
				+ config.final_synthesis.max_route_calls + recovery_reserve
			)
			parallel = max(item.max_parallel_calls for item in stages)
		except (AttributeError, TypeError, ValueError) as error:
			raise daily_blog.agents.EditorialTerminalError(
				"Configured editorial capacity is invalid."
			) from error
		if calls <= 0:
			raise daily_blog.agents.EditorialTerminalError("Configured editorial capacity admits no work.")
		return cls(calls, parallel)

	def new_budget(self) -> daily_blog.agents.RouteBudget:
		"""Create the one run-owned budget after admission succeeds."""
		return daily_blog.agents.RouteBudget(self.maximum_calls, self.maximum_parallel_calls)

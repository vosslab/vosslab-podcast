"""Bounded, isolated configuration for Stage 7 final synthesis."""

# Standard Library
import dataclasses

# local repo modules
from podlib import pipeline_settings
from daily_blog.editorial_stage_config import (
	HERMES_EDITORIAL_ROUTE,
	RoleRoute,
	_role_route,
	_validate_role_command,
)

DEFAULT_FINAL_SYNTHESIS_RELIABILITY = {
	"synthesizer_count": 2,
	"reviewer_count": 1,
	"maximum_parallel_calls": 2,
	"route_retry_attempts": 1,
}
DEFAULT_FINAL_SYNTHESIS_PROMPT_LIMITS = {
	"incumbent_chars": 120000,
	"alternatives_chars": 180000,
	"review_facts_chars": 30000,
	"rubric_chars": 30000,
	"evidence_chars": 90000,
	"provenance_chars": 30000,
	"rendered_prompt_chars": 470000,
}
MAX_FINAL_SYNTHESIS_REPLICAS = 16
MAX_FINAL_SYNTHESIS_REVIEWERS = 16
MAX_FINAL_SYNTHESIS_PARALLEL_CALLS = 16
MAX_FINAL_SYNTHESIS_RETRY_ATTEMPTS = 3
MAX_FINAL_SYNTHESIS_PROMPT_CHARS = 470000


#============================================
def _default_final_synthesis_route(name: str) -> RoleRoute:
	"""Return one named sealed route for an independent Stage 7 role."""
	return RoleRoute(name=name, command=HERMES_EDITORIAL_ROUTE)


@dataclasses.dataclass(frozen=True)
class FinalSynthesisConfig:
	"""Frozen Stage 7 synthesis, complete-set review, and route-budget policy."""

	synthesizer_count: int = DEFAULT_FINAL_SYNTHESIS_RELIABILITY["synthesizer_count"]
	reviewer_count: int = DEFAULT_FINAL_SYNTHESIS_RELIABILITY["reviewer_count"]
	maximum_parallel_calls: int = DEFAULT_FINAL_SYNTHESIS_RELIABILITY["maximum_parallel_calls"]
	route_retry_attempts: int = DEFAULT_FINAL_SYNTHESIS_RELIABILITY["route_retry_attempts"]
	synthesis_route: RoleRoute = dataclasses.field(
		default_factory=lambda: _default_final_synthesis_route("final_synthesis_writer")
	)
	reviewer_route: RoleRoute = dataclasses.field(
		default_factory=lambda: _default_final_synthesis_route("final_synthesis_reviewer")
	)
	prompt_limits: dict[str, int] = dataclasses.field(
		default_factory=lambda: dict(DEFAULT_FINAL_SYNTHESIS_PROMPT_LIMITS)
	)

	#============================================
	def __post_init__(self) -> None:
		"""Reject unsafe Stage 7 policy before any synthesis or review route starts."""
		self._require(self.synthesizer_count, "synthesizer_count", 2, MAX_FINAL_SYNTHESIS_REPLICAS)
		self._require(self.reviewer_count, "reviewer_count", 1, MAX_FINAL_SYNTHESIS_REVIEWERS)
		self._require(self.maximum_parallel_calls, "maximum_parallel_calls", 1, MAX_FINAL_SYNTHESIS_PARALLEL_CALLS)
		self._require(self.route_retry_attempts, "route_retry_attempts", 0, MAX_FINAL_SYNTHESIS_RETRY_ATTEMPTS)
		if self.maximum_parallel_calls > max(self.synthesizer_count, self.review_source_count):
			raise RuntimeError("Final-synthesis maximum_parallel_calls cannot exceed one stage work pool.")
		routes = (self.synthesis_route, self.reviewer_route)
		if any(not isinstance(route, RoleRoute) for route in routes):
			raise RuntimeError("Final-synthesis routes must be RoleRoute values.")
		if len({route.name for route in routes}) != len(routes):
			raise RuntimeError("Final-synthesis route names must be distinct by role.")
		for role, route in zip(("synthesis", "reviewer"), routes, strict=True):
			if not route.name:
				raise RuntimeError(f"Final-synthesis {role} route requires a name.")
			_validate_role_command(route.command, f"daily_blog.final_synthesis.routes.{role}")
		if not isinstance(self.prompt_limits, dict):
			raise RuntimeError("Final-synthesis prompt_limits must be a mapping.")
		if set(self.prompt_limits) != set(DEFAULT_FINAL_SYNTHESIS_PROMPT_LIMITS):
			raise RuntimeError("Final-synthesis prompt_limits keys are invalid.")
		for key, value in self.prompt_limits.items():
			self._require(value, f"prompt_limits.{key}", 1, MAX_FINAL_SYNTHESIS_PROMPT_CHARS)

	#============================================
	@staticmethod
	def _require(value: object, label: str, minimum: int, maximum: int) -> None:
		"""Require one exact bounded integer rather than a bool or coercible value."""
		if type(value) is not int or value < minimum or value > maximum:
			raise RuntimeError(
				f"Final-synthesis {label} must be an integer from {minimum} through {maximum}."
			)

	#============================================
	@property
	def review_source_count(self) -> int:
		"""Return one complete-set call per independent reviewer."""
		return self.reviewer_count

	#============================================
	@property
	def repair_source_count(self) -> int:
		"""Candidate-set verdict failure preserves the incumbent without repair."""
		return 0

	#============================================
	@property
	def route_source_count(self) -> int:
		"""Return synthesis, ordered reviews, and repairs before retry multiplication."""
		return self.synthesizer_count + self.review_source_count + self.repair_source_count

	#============================================
	@property
	def required_route_calls(self) -> int:
		"""Return ``(synthesizers + reviewers) * (retry + 1)`` exactly."""
		return self.route_source_count * (self.route_retry_attempts + 1)

	#============================================
	@property
	def max_parallel_calls(self) -> int:
		"""Provide the RouteBudget-compatible name for the stage parallel cap."""
		return self.maximum_parallel_calls


#============================================
def _load_final_synthesis_config(settings: dict) -> FinalSynthesisConfig:
	"""Load the isolated Stage 7 policy without changing earlier-stage policy."""
	configured = pipeline_settings.get_nested_value(settings, ["daily_blog", "final_synthesis"], {})
	if not isinstance(configured, dict):
		raise RuntimeError("daily_blog.final_synthesis must be a mapping.")
	known = set(DEFAULT_FINAL_SYNTHESIS_RELIABILITY) | {"routes", "prompt_limits"}
	unknown = set(configured) - known
	if unknown:
		names = ", ".join(sorted(unknown))
		raise RuntimeError(f"Unknown daily_blog.final_synthesis keys: {names}")
	values = dict(DEFAULT_FINAL_SYNTHESIS_RELIABILITY)
	values.update({key: configured[key] for key in DEFAULT_FINAL_SYNTHESIS_RELIABILITY if key in configured})
	routes_value = configured.get("routes", {})
	if not isinstance(routes_value, dict):
		raise RuntimeError("daily_blog.final_synthesis.routes must be a mapping.")
	roles = ("synthesis", "reviewer")
	unknown_routes = set(routes_value) - set(roles)
	if unknown_routes:
		names = ", ".join(sorted(unknown_routes))
		raise RuntimeError(f"Unknown daily_blog.final_synthesis.routes keys: {names}")
	routes = {
		role: _role_route(routes_value[role], f"daily_blog.final_synthesis.routes.{role}")
		if role in routes_value else _default_final_synthesis_route(f"final_synthesis_{role}")
		for role in roles
	}
	prompt_limits = dict(DEFAULT_FINAL_SYNTHESIS_PROMPT_LIMITS)
	configured_limits = configured.get("prompt_limits", {})
	if not isinstance(configured_limits, dict):
		raise RuntimeError("daily_blog.final_synthesis.prompt_limits must be a mapping.")
	unknown_limits = set(configured_limits) - set(prompt_limits)
	if unknown_limits:
		names = ", ".join(sorted(unknown_limits))
		raise RuntimeError(f"Unknown daily_blog.final_synthesis.prompt_limits keys: {names}")
	prompt_limits.update(configured_limits)
	return FinalSynthesisConfig(
		**values,
		synthesis_route=routes["synthesis"],
		reviewer_route=routes["reviewer"],
		prompt_limits=prompt_limits,
	)

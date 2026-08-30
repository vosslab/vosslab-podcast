"""Stage-local daily-blog editorial configuration.

This module owns bounded replication policy and sealed editorial routes for
repository-outline, repository-story, and complete-post stages.
"""

# Standard Library
import dataclasses

# local repo modules
from podlib import pipeline_settings

DEFAULT_REPOSITORY_OUTLINE_RELIABILITY = {
	"generator_count": 2,
	"merger_count": 2,
	"reviewer_count": 1,
	"maximum_parallel_calls": 6,
	"route_retry_attempts": 1,
}
DEFAULT_REPOSITORY_OUTLINE_PROMPT_LIMITS = {
	"generator_chars": 48000,
	"merger_chars": 64000,
	"reviewer_chars": 72000,
	"repair_chars": 72000,
}
DEFAULT_REPOSITORY_STORY_RELIABILITY = {
	"writer_count": 2,
	"editor_count": 2,
	"reviewer_count": 1,
	"maximum_parallel_calls": 6,
	"route_retry_attempts": 1,
}
DEFAULT_REPOSITORY_STORY_PROMPT_LIMITS = {
	"writer_chars": 64000,
	"editor_chars": 72000,
	"reviewer_chars": 84000,
	"repair_chars": 84000,
}
DEFAULT_COMPLETE_POST_RELIABILITY = {
	"writer_count": 2,
	"editor_count": 2,
	"reviewer_count": 1,
	"maximum_parallel_calls": 6,
	"max_route_calls": 88,
	"route_retry_attempts": 1,
}
DEFAULT_COMPLETE_POST_PROMPT_LIMITS = {
	"writer_chars": 72000,
	"editor_chars": 185000,
	"reviewer_chars": 88000,
	"repair_chars": 88000,
}
DEFAULT_DAILY_OUTLINE_RELIABILITY = {
	"ranker_count": 3,
	"outline_writer_count": 3,
	"reviewer_count": 2,
	"maximum_parallel_calls": 6,
	"max_route_calls": 84,
	"route_retry_attempts": 1,
}
DEFAULT_DAILY_OUTLINE_PROMPT_LIMITS = {
	"ranking_chars": 120000,
	"writer_chars": 300000,
	"reviewer_chars": 300000,
	"repair_chars": 300000,
}
MAX_REPOSITORY_OUTLINE_REPLICAS = 16
MAX_REPOSITORY_OUTLINE_REVIEWERS = 16
MAX_REPOSITORY_OUTLINE_PARALLEL_CALLS = 16
MAX_REPOSITORY_OUTLINE_RETRY_ATTEMPTS = 3
MAX_REPOSITORY_OUTLINE_PROMPT_CHARS = 120000
MAX_REPOSITORY_STORY_REPLICAS = 16
MAX_REPOSITORY_STORY_REVIEWERS = 16
MAX_REPOSITORY_STORY_PARALLEL_CALLS = 16
MAX_REPOSITORY_STORY_RETRY_ATTEMPTS = 3
MAX_REPOSITORY_STORY_PROMPT_CHARS = 120000
MAX_STAGE6_REPLICAS = 16
MAX_STAGE6_REVIEWERS = 16
MAX_STAGE6_PARALLEL_CALLS = 16
MAX_STAGE6_RETRY_ATTEMPTS = 3
MAX_COMPLETE_POST_PROMPT_CHARS = {
	"writer_chars": 120000,
	"editor_chars": 185000,
	"reviewer_chars": 120000,
	"repair_chars": 120000,
}
MAX_DAILY_OUTLINE_REPLICAS = 16
MAX_DAILY_OUTLINE_REVIEWERS = 16
MAX_DAILY_OUTLINE_PARALLEL_CALLS = 16
MAX_DAILY_OUTLINE_RETRY_ATTEMPTS = 3
MAX_DAILY_OUTLINE_ROUTE_CALLS = 4096
MAX_DAILY_OUTLINE_PROMPT_CHARS = 300000
# ASVS 1.2.5 and 16.5.1: fixed argv plus quiet stdout separates payloads from diagnostics.
HERMES_EDITORIAL_ROUTE = (
	"hermes",
	"chat",
	"--provider",
	"openai-codex",
	"--query-file",
	"-",
	"--ignore-rules",
	"--quiet",
)
HERMES_MODEL_ARGUMENTS = {"--model", "-m", "model"}
DAILY_BLOG_SETTING_KEYS = {
	"collection_limits",
	"complete_post",
	"daily_outline",
	"editorial_reliability",
	"identity_emails",
	"identity_names",
	"mirror_cache_root",
	"projection_limits",
	"prompt_limits",
	"repository_outline",
	"repository_story",
	"report_timezone",
	"repository_path",
	"routes",
}



@dataclasses.dataclass(frozen=True)
class RoleRoute:
	"""One isolated command route for an editorial role."""

	name: str
	command: tuple[str, ...]



@dataclasses.dataclass(frozen=True)
class RepositoryOutlineConfig:
	"""Frozen, stage-local reliability and route policy for repository outlines."""

	generator_count: int = DEFAULT_REPOSITORY_OUTLINE_RELIABILITY["generator_count"]
	merger_count: int = DEFAULT_REPOSITORY_OUTLINE_RELIABILITY["merger_count"]
	reviewer_count: int = DEFAULT_REPOSITORY_OUTLINE_RELIABILITY["reviewer_count"]
	maximum_parallel_calls: int = DEFAULT_REPOSITORY_OUTLINE_RELIABILITY[
		"maximum_parallel_calls"
	]
	route_retry_attempts: int = DEFAULT_REPOSITORY_OUTLINE_RELIABILITY[
		"route_retry_attempts"
	]
	generator_route: RoleRoute = dataclasses.field(
		default_factory=lambda: _default_repository_outline_route("repository_outline_generator")
	)
	merger_route: RoleRoute = dataclasses.field(
		default_factory=lambda: _default_repository_outline_route("repository_outline_merger")
	)
	reviewer_route: RoleRoute = dataclasses.field(
		default_factory=lambda: _default_repository_outline_route("repository_outline_reviewer")
	)
	prompt_limits: dict[str, int] = dataclasses.field(
		default_factory=lambda: dict(DEFAULT_REPOSITORY_OUTLINE_PROMPT_LIMITS)
	)

	#============================================
	def __post_init__(self) -> None:
		"""Reject unsafe replicas, routes, and prompt sizes before any route starts."""
		self._require_bounded_count(
			self.generator_count,
			"generator_count",
			2,
			MAX_REPOSITORY_OUTLINE_REPLICAS,
		)
		self._require_bounded_count(
			self.merger_count,
			"merger_count",
			2,
			MAX_REPOSITORY_OUTLINE_REPLICAS,
		)
		self._require_bounded_count(
			self.reviewer_count,
			"reviewer_count",
			1,
			MAX_REPOSITORY_OUTLINE_REVIEWERS,
		)
		self._require_bounded_count(
			self.maximum_parallel_calls,
			"maximum_parallel_calls",
			1,
			MAX_REPOSITORY_OUTLINE_PARALLEL_CALLS,
		)
		self._require_bounded_count(
			self.route_retry_attempts,
			"route_retry_attempts",
			0,
			MAX_REPOSITORY_OUTLINE_RETRY_ATTEMPTS,
		)
		if self.maximum_parallel_calls > max(
			self.generator_count,
			self.merger_count,
			self.review_source_count,
		):
			raise RuntimeError(
				"Repository-outline maximum_parallel_calls cannot exceed one stage work pool."
			)
		routes = (self.generator_route, self.merger_route, self.reviewer_route)
		if any(not isinstance(route, RoleRoute) for route in routes):
			raise RuntimeError("Repository-outline routes must be RoleRoute values.")
		if len({route.name for route in routes}) != len(routes):
			raise RuntimeError("Repository-outline route names must be distinct by role.")
		for role, route in zip(("generator", "merger", "reviewer"), routes, strict=True):
			if not route.name:
				raise RuntimeError(f"Repository-outline {role} route requires a name.")
			_validate_role_command(route.command, f"daily_blog.repository_outline.routes.{role}")
		if not isinstance(self.prompt_limits, dict):
			raise RuntimeError("Repository-outline prompt_limits must be a mapping.")
		unknown = set(self.prompt_limits) - set(DEFAULT_REPOSITORY_OUTLINE_PROMPT_LIMITS)
		missing = set(DEFAULT_REPOSITORY_OUTLINE_PROMPT_LIMITS) - set(self.prompt_limits)
		if unknown or missing:
			parts = []
			if unknown:
				parts.append("unknown: " + ", ".join(sorted(unknown)))
			if missing:
				parts.append("missing: " + ", ".join(sorted(missing)))
			raise RuntimeError("Repository-outline prompt_limits keys are invalid (" + "; ".join(parts) + ").")
		for key, value in self.prompt_limits.items():
			self._require_bounded_count(value, f"prompt_limits.{key}", 1, MAX_REPOSITORY_OUTLINE_PROMPT_CHARS)

	#============================================
	@staticmethod
	def _require_bounded_count(value: object, label: str, minimum: int, maximum: int) -> None:
		"""Require one real integer inside the frozen safe operating envelope."""
		if type(value) is not int or value < minimum or value > maximum:
			raise RuntimeError(
				f"Repository-outline {label} must be an integer from {minimum} through {maximum}."
			)

	#============================================
	@property
	def review_peer_count(self) -> int:
		"""Reserve the largest promotion pool: generators or mergers plus incumbent."""
		return max(self.generator_count, self.merger_count) + 1

	#============================================
	@property
	def reviewer_pair_count(self) -> int:
		"""Return every unordered pair in the largest eligible promotion pool."""
		return self.review_peer_count * (self.review_peer_count - 1) // 2

	#============================================
	@property
	def review_source_count(self) -> int:
		"""Return balanced reviewer responses across every eligible promotion pair."""
		return self.reviewer_pair_count * self.reviewer_count * 2

	#============================================
	@property
	def structured_source_count(self) -> int:
		"""Return every primary source including the largest review-promotion pool."""
		return self.generator_count + self.merger_count + self.review_source_count

	#============================================
	@property
	def maximum_route_calls(self) -> int:
		"""Return the exact worst case: retries plus one repair per structured source."""
		return self.structured_source_count * 2 * (self.route_retry_attempts + 1)

	#============================================
	@property
	def max_route_calls(self) -> int:
		"""Provide the RouteBudget-compatible name for the derived stage budget."""
		return self.maximum_route_calls

	#============================================
	@property
	def max_parallel_calls(self) -> int:
		"""Provide the RouteBudget-compatible name for the stage parallel cap."""
		return self.maximum_parallel_calls


@dataclasses.dataclass(frozen=True)
class RepositoryStoryConfig:
	"""Frozen, stage-local reliability and route policy for repository stories."""

	writer_count: int = DEFAULT_REPOSITORY_STORY_RELIABILITY["writer_count"]
	editor_count: int = DEFAULT_REPOSITORY_STORY_RELIABILITY["editor_count"]
	reviewer_count: int = DEFAULT_REPOSITORY_STORY_RELIABILITY["reviewer_count"]
	maximum_parallel_calls: int = DEFAULT_REPOSITORY_STORY_RELIABILITY[
		"maximum_parallel_calls"
	]
	route_retry_attempts: int = DEFAULT_REPOSITORY_STORY_RELIABILITY[
		"route_retry_attempts"
	]
	writer_route: RoleRoute = dataclasses.field(
		default_factory=lambda: _default_repository_story_route("repository_story_writer")
	)
	editor_route: RoleRoute = dataclasses.field(
		default_factory=lambda: _default_repository_story_route("repository_story_editor")
	)
	reviewer_route: RoleRoute = dataclasses.field(
		default_factory=lambda: _default_repository_story_route("repository_story_reviewer")
	)
	prompt_limits: dict[str, int] = dataclasses.field(
		default_factory=lambda: dict(DEFAULT_REPOSITORY_STORY_PROMPT_LIMITS)
	)

	#============================================
	def __post_init__(self) -> None:
		"""Reject unsafe Stage 4 fan-out, routes, and prompt sizes before execution."""
		self._require_bounded_count(
			self.writer_count, "writer_count", 2, MAX_REPOSITORY_STORY_REPLICAS,
		)
		self._require_bounded_count(
			self.editor_count, "editor_count", 2, MAX_REPOSITORY_STORY_REPLICAS,
		)
		self._require_bounded_count(
			self.reviewer_count, "reviewer_count", 1, MAX_REPOSITORY_STORY_REVIEWERS,
		)
		self._require_bounded_count(
			self.maximum_parallel_calls, "maximum_parallel_calls", 1,
			MAX_REPOSITORY_STORY_PARALLEL_CALLS,
		)
		self._require_bounded_count(
			self.route_retry_attempts, "route_retry_attempts", 0,
			MAX_REPOSITORY_STORY_RETRY_ATTEMPTS,
		)
		if self.maximum_parallel_calls > max(
			self.writer_count, self.editor_count, self.review_source_count,
		):
			raise RuntimeError(
				"Repository-story maximum_parallel_calls cannot exceed one stage work pool."
			)
		routes = (self.writer_route, self.editor_route, self.reviewer_route)
		if any(not isinstance(route, RoleRoute) for route in routes):
			raise RuntimeError("Repository-story routes must be RoleRoute values.")
		if len({route.name for route in routes}) != len(routes):
			raise RuntimeError("Repository-story route names must be distinct by role.")
		for role, route in zip(("writer", "editor", "reviewer"), routes, strict=True):
			if not route.name:
				raise RuntimeError(f"Repository-story {role} route requires a name.")
			_validate_role_command(route.command, f"daily_blog.repository_story.routes.{role}")
		if not isinstance(self.prompt_limits, dict):
			raise RuntimeError("Repository-story prompt_limits must be a mapping.")
		unknown = set(self.prompt_limits) - set(DEFAULT_REPOSITORY_STORY_PROMPT_LIMITS)
		missing = set(DEFAULT_REPOSITORY_STORY_PROMPT_LIMITS) - set(self.prompt_limits)
		if unknown or missing:
			parts = []
			if unknown:
				parts.append("unknown: " + ", ".join(sorted(unknown)))
			if missing:
				parts.append("missing: " + ", ".join(sorted(missing)))
			raise RuntimeError("Repository-story prompt_limits keys are invalid (" + "; ".join(parts) + ").")
		for key, value in self.prompt_limits.items():
			self._require_bounded_count(
				value, f"prompt_limits.{key}", 1, MAX_REPOSITORY_STORY_PROMPT_CHARS,
			)

	#============================================
	@staticmethod
	def _require_bounded_count(value: object, label: str, minimum: int, maximum: int) -> None:
		"""Require one real integer inside the frozen Stage 4 operating envelope."""
		if type(value) is not int or value < minimum or value > maximum:
			raise RuntimeError(
				f"Repository-story {label} must be an integer from {minimum} through {maximum}."
			)

	#============================================
	@property
	def review_peer_count(self) -> int:
		"""Reserve the largest edited peer pool and one eligible incumbent."""
		return max(self.writer_count, self.editor_count) + 1

	#============================================
	@property
	def reviewer_pair_count(self) -> int:
		"""Return all unordered comparisons in the largest possible promotion pool."""
		return self.review_peer_count * (self.review_peer_count - 1) // 2

	#============================================
	@property
	def review_source_count(self) -> int:
		"""Return balanced A/B verdict sources for every reviewer replica."""
		return self.reviewer_pair_count * self.reviewer_count * 2

	#============================================
	@property
	def maximum_route_calls(self) -> int:
		"""Return writers/editors plus every verdict and its one retry-bounded repair."""
		primary_sources = self.writer_count + self.editor_count
		structured_sources = self.review_source_count
		return (primary_sources + (structured_sources * 2)) * (
			self.route_retry_attempts + 1
		)

	#============================================
	@property
	def max_route_calls(self) -> int:
		"""Provide the RouteBudget-compatible name for the derived stage budget."""
		return self.maximum_route_calls

	#============================================
	@property
	def max_parallel_calls(self) -> int:
		"""Provide the RouteBudget-compatible name for the stage parallel cap."""
		return self.maximum_parallel_calls


@dataclasses.dataclass(frozen=True)
class DailyOutlineConfig:
	"""Frozen Stage 5 ranking, authored-outline, and review policy."""

	ranker_count: int = DEFAULT_DAILY_OUTLINE_RELIABILITY["ranker_count"]
	outline_writer_count: int = DEFAULT_DAILY_OUTLINE_RELIABILITY["outline_writer_count"]
	reviewer_count: int = DEFAULT_DAILY_OUTLINE_RELIABILITY["reviewer_count"]
	maximum_parallel_calls: int = DEFAULT_DAILY_OUTLINE_RELIABILITY["maximum_parallel_calls"]
	max_route_calls: int = DEFAULT_DAILY_OUTLINE_RELIABILITY["max_route_calls"]
	route_retry_attempts: int = DEFAULT_DAILY_OUTLINE_RELIABILITY["route_retry_attempts"]
	ranking_route: RoleRoute = dataclasses.field(
		default_factory=lambda: _default_daily_outline_route("daily_outline_ranking")
	)
	outline_writer_route: RoleRoute = dataclasses.field(
		default_factory=lambda: _default_daily_outline_route("daily_outline_writer")
	)
	outline_reviewer_route: RoleRoute = dataclasses.field(
		default_factory=lambda: _default_daily_outline_route("daily_outline_reviewer")
	)
	prompt_limits: dict[str, int] = dataclasses.field(
		default_factory=lambda: dict(DEFAULT_DAILY_OUTLINE_PROMPT_LIMITS)
	)

	#============================================
	def __post_init__(self) -> None:
		"""Validate every Stage 5 admission control before route execution."""
		self._require(self.ranker_count, "ranker_count", 2, MAX_DAILY_OUTLINE_REPLICAS)
		self._require(self.outline_writer_count, "outline_writer_count", 2, MAX_DAILY_OUTLINE_REPLICAS)
		self._require(self.reviewer_count, "reviewer_count", 1, MAX_DAILY_OUTLINE_REVIEWERS)
		self._require(self.maximum_parallel_calls, "maximum_parallel_calls", 1, MAX_DAILY_OUTLINE_PARALLEL_CALLS)
		self._require(self.route_retry_attempts, "route_retry_attempts", 0, MAX_DAILY_OUTLINE_RETRY_ATTEMPTS)
		if self.maximum_parallel_calls > self.largest_work_pool:
			raise RuntimeError("Daily-outline maximum_parallel_calls cannot exceed one stage work pool.")
		self._require(self.max_route_calls, "max_route_calls", self.required_route_calls, MAX_DAILY_OUTLINE_ROUTE_CALLS)
		routes = (self.ranking_route, self.outline_writer_route, self.outline_reviewer_route)
		if any(not isinstance(route, RoleRoute) for route in routes):
			raise RuntimeError("Daily-outline routes must be RoleRoute values.")
		if len({route.name for route in routes}) != len(routes):
			raise RuntimeError("Daily-outline route names must be distinct by role.")
		for role, route in zip(("ranking", "outline_writer", "outline_reviewer"), routes, strict=True):
			if not route.name:
				raise RuntimeError(f"Daily-outline {role} route requires a name.")
			_validate_role_command(route.command, f"daily_blog.daily_outline.routes.{role}")
		if not isinstance(self.prompt_limits, dict):
			raise RuntimeError("Daily-outline prompt_limits must be a mapping.")
		if set(self.prompt_limits) != set(DEFAULT_DAILY_OUTLINE_PROMPT_LIMITS):
			raise RuntimeError("Daily-outline prompt_limits keys are invalid.")
		for key, value in self.prompt_limits.items():
			self._require(value, f"prompt_limits.{key}", 1, MAX_DAILY_OUTLINE_PROMPT_CHARS)

	#============================================
	@staticmethod
	def _require(value: object, label: str, minimum: int, maximum: int) -> None:
		"""Require one exact, bounded integer configuration value."""
		if type(value) is not int or value < minimum or value > maximum:
			raise RuntimeError(f"Daily-outline {label} must be an integer from {minimum} through {maximum}.")

	#============================================
	@property
	def ranking_review_source_count(self) -> int:
		"""Reserve one structured promotion review for each independent ranking."""
		return self.ranker_count * self.reviewer_count

	#============================================
	@property
	def outline_reviewer_pair_count(self) -> int:
		"""Return every unordered pair in the largest eligible outline pool."""
		return self.outline_writer_count * (self.outline_writer_count - 1) // 2

	#============================================
	@property
	def outline_review_source_count(self) -> int:
		"""Reserve both anonymous display orders for every outline comparison."""
		return self.outline_reviewer_pair_count * self.reviewer_count * 2

	#============================================
	@property
	def repair_source_count(self) -> int:
		"""Reserve one repair for every structured ranking or outline review."""
		return self.ranking_review_source_count + self.outline_review_source_count

	#============================================
	@property
	def largest_work_pool(self) -> int:
		"""Return the largest same-rung pool admitted by this stage policy."""
		return max(self.ranker_count, self.outline_writer_count, self.ranking_review_source_count, self.outline_review_source_count)

	#============================================
	@property
	def route_source_count(self) -> int:
		"""Return all Stage 5 requests before retry multiplication."""
		return self.ranker_count + self.outline_writer_count + self.repair_source_count + self.ranking_review_source_count + self.outline_review_source_count

	#============================================
	@property
	def required_route_calls(self) -> int:
		"""Return the exact worst-case route budget including every retry."""
		return self.route_source_count * (self.route_retry_attempts + 1)

	#============================================
	@property
	def maximum_route_calls(self) -> int:
		"""Provide a derived-name view for stage-budget callers."""
		return self.max_route_calls

	#============================================
	@property
	def max_parallel_calls(self) -> int:
		"""Provide the RouteBudget-compatible name for the stage parallel cap."""
		return self.maximum_parallel_calls


@dataclasses.dataclass(frozen=True)
class CompletePostConfig:
	"""Frozen Stage 6 replication, review, and route-budget policy."""

	writer_count: int = DEFAULT_COMPLETE_POST_RELIABILITY["writer_count"]
	editor_count: int = DEFAULT_COMPLETE_POST_RELIABILITY["editor_count"]
	reviewer_count: int = DEFAULT_COMPLETE_POST_RELIABILITY["reviewer_count"]
	maximum_parallel_calls: int = DEFAULT_COMPLETE_POST_RELIABILITY[
		"maximum_parallel_calls"
	]
	max_route_calls: int = DEFAULT_COMPLETE_POST_RELIABILITY["max_route_calls"]
	route_retry_attempts: int = DEFAULT_COMPLETE_POST_RELIABILITY[
		"route_retry_attempts"
	]
	writer_route: RoleRoute = dataclasses.field(
		default_factory=lambda: _default_complete_post_route("complete_post_writer")
	)
	editor_route: RoleRoute = dataclasses.field(
		default_factory=lambda: _default_complete_post_route("complete_post_editor")
	)
	reviewer_route: RoleRoute = dataclasses.field(
		default_factory=lambda: _default_complete_post_route("complete_post_reviewer")
	)
	prompt_limits: dict[str, int] = dataclasses.field(
		default_factory=lambda: dict(DEFAULT_COMPLETE_POST_PROMPT_LIMITS)
	)

	#============================================
	def __post_init__(self) -> None:
		"""Reject unsafe Stage 6 fan-out, routes, and prompt sizes before execution."""
		self._require_bounded_count(self.writer_count, "writer_count", 2, MAX_STAGE6_REPLICAS)
		self._require_bounded_count(self.editor_count, "editor_count", 2, MAX_STAGE6_REPLICAS)
		self._require_bounded_count(self.reviewer_count, "reviewer_count", 1, MAX_STAGE6_REVIEWERS)
		self._require_bounded_count(
			self.maximum_parallel_calls, "maximum_parallel_calls", 1, MAX_STAGE6_PARALLEL_CALLS,
		)
		self._require_bounded_count(
			self.route_retry_attempts, "route_retry_attempts", 0, MAX_STAGE6_RETRY_ATTEMPTS,
		)
		if self.maximum_parallel_calls > max(
			self.writer_count, self.editor_count, self.review_source_count,
		):
			raise RuntimeError(
				"Complete-post maximum_parallel_calls cannot exceed one stage work pool."
			)
		if type(self.max_route_calls) is not int or self.max_route_calls < self.required_route_calls:
			raise RuntimeError(
				"Complete-post route budget cannot cover writers, editors, retries, review, "
				"repair, and incumbent comparison."
			)
		routes = (self.writer_route, self.editor_route, self.reviewer_route)
		if any(not isinstance(route, RoleRoute) for route in routes):
			raise RuntimeError("Complete-post routes must be RoleRoute values.")
		if len({route.name for route in routes}) != len(routes):
			raise RuntimeError("Complete-post route names must be distinct by role.")
		for role, route in zip(("writer", "editor", "reviewer"), routes, strict=True):
			if not route.name:
				raise RuntimeError(f"Complete-post {role} route requires a name.")
			_validate_role_command(route.command, f"daily_blog.complete_post.routes.{role}")
		if not isinstance(self.prompt_limits, dict):
			raise RuntimeError("Complete-post prompt_limits must be a mapping.")
		unknown = set(self.prompt_limits) - set(DEFAULT_COMPLETE_POST_PROMPT_LIMITS)
		missing = set(DEFAULT_COMPLETE_POST_PROMPT_LIMITS) - set(self.prompt_limits)
		if unknown or missing:
			parts = []
			if unknown:
				parts.append("unknown: " + ", ".join(sorted(unknown)))
			if missing:
				parts.append("missing: " + ", ".join(sorted(missing)))
			raise RuntimeError("Complete-post prompt_limits keys are invalid (" + "; ".join(parts) + ").")
		for key, value in self.prompt_limits.items():
			self._require_bounded_count(
				value, f"prompt_limits.{key}", 1, MAX_COMPLETE_POST_PROMPT_CHARS[key],
			)

	#============================================
	@staticmethod
	def _require_bounded_count(value: object, label: str, minimum: int, maximum: int) -> None:
		"""Require one real integer inside the Stage 6 operating envelope."""
		if type(value) is not int or value < minimum or value > maximum:
			raise RuntimeError(
				f"Complete-post {label} must be an integer from {minimum} through {maximum}."
			)

	#============================================
	@property
	def review_peer_count(self) -> int:
		"""Reserve writers, editors, and one optional eligible complete-post incumbent."""
		return self.writer_count + self.editor_count + 1

	#============================================
	@property
	def reviewer_pair_count(self) -> int:
		"""Return every unordered eligible complete-post comparison pair."""
		return self.review_peer_count * (self.review_peer_count - 1) // 2

	#============================================
	@property
	def review_source_count(self) -> int:
		"""Return both A/B orders for every reviewer and comparison pair."""
		return self.reviewer_pair_count * self.reviewer_count * 2

	#============================================
	@property
	def repair_source_count(self) -> int:
		"""Reserve one verdict repair for every structured review presentation."""
		return self.review_source_count

	#============================================
	@property
	def primary_source_count(self) -> int:
		"""Return all independent complete-post writers and editors."""
		return self.writer_count + self.editor_count

	#============================================
	@property
	def route_source_count(self) -> int:
		"""Return every Stage 6 route source before bounded retry multiplication."""
		return self.primary_source_count + self.review_source_count + self.repair_source_count

	#============================================
	@property
	def required_route_calls(self) -> int:
		"""Return the full Stage 6 budget including retries on every route request."""
		return self.route_source_count * (self.route_retry_attempts + 1)

	#============================================
	@property
	def max_parallel_calls(self) -> int:
		"""Provide the RouteBudget-compatible name for the stage parallel cap."""
		return self.maximum_parallel_calls





def _string_list(value: object, label: str) -> tuple[str, ...]:
	"""Validate and normalize one YAML string list."""
	if not isinstance(value, list):
		raise RuntimeError(f"{label} must be a list.")
	items = []
	for item in value:
		text = str(item).strip()
		if text:
			items.append(text)
	result = tuple(items)
	return result


#============================================
def _role_route(value: object, label: str) -> RoleRoute:
	"""Validate one role command route."""
	if not isinstance(value, dict):
		raise RuntimeError(f"{label} must be a mapping.")
	name = str(value.get("name") or "").strip()
	command_value = value.get("command")
	if not name:
		raise RuntimeError(f"{label}.name is required.")
	command = _string_list(command_value, f"{label}.command")
	if not command:
		raise RuntimeError(f"{label}.command requires at least one argument.")
	_validate_role_command(command, label)
	route = RoleRoute(name=name, command=command)
	return route


#============================================
def _validate_role_command(command: tuple[str, ...], label: str) -> None:
	"""Require the sealed Hermes stdin transport contract for every editorial role."""
	if command[:2] != ("hermes", "chat"):
		raise RuntimeError(f"{label}.command must invoke hermes chat.")
	for argument in command:
		name = argument.split("=", 1)[0]
		if name in HERMES_MODEL_ARGUMENTS:
			raise RuntimeError(
				f"{label}.command must leave model selection to Hermes: {name}"
			)
	if command != HERMES_EDITORIAL_ROUTE:
		raise RuntimeError(
			f"{label}.command must exactly match the sealed Hermes editorial route."
		)


#============================================
def _default_command() -> list[str]:
	"""Return the isolated Hermes stdin transport route."""
	command = list(HERMES_EDITORIAL_ROUTE)
	return command


#============================================
def _default_repository_outline_route(name: str) -> RoleRoute:
	"""Return one named sealed route for an independent outline-stage role."""
	return RoleRoute(name=name, command=tuple(_default_command()))


#============================================
def _default_repository_story_route(name: str) -> RoleRoute:
	"""Return one named sealed route for an independent story-stage role."""
	return RoleRoute(name=name, command=tuple(_default_command()))


#============================================
def _default_complete_post_route(name: str) -> RoleRoute:
	"""Return one named sealed route for an independent complete-post role."""
	return RoleRoute(name=name, command=tuple(_default_command()))


#============================================
def _default_daily_outline_route(name: str) -> RoleRoute:
	"""Return one named sealed route for an independent Stage 5 role."""
	return RoleRoute(name=name, command=tuple(_default_command()))


#============================================
def _load_routes(settings: dict) -> tuple[tuple[RoleRoute, ...], RoleRoute]:
	"""Load exactly two author routes and one separately named referee route."""
	routes = pipeline_settings.get_nested_value(settings, ["daily_blog", "routes"], {})
	if not routes:
		command = _default_command()
		_validate_role_command(tuple(command), "daily_blog.routes.default")
		authors = (
			RoleRoute("author_one", tuple(command)),
			RoleRoute("author_two", tuple(command)),
		)
		referee = RoleRoute("referee", tuple(command))
		return authors, referee
	if not isinstance(routes, dict):
		raise RuntimeError("daily_blog.routes must be a mapping.")
	author_values = routes.get("authors")
	if not isinstance(author_values, list) or len(author_values) != 2:
		raise RuntimeError("daily_blog.routes.authors requires exactly two routes.")
	authors = tuple(
		_role_route(value, f"daily_blog.routes.authors[{index}]")
		for index, value in enumerate(author_values)
	)
	if authors[0].name == authors[1].name:
		raise RuntimeError("Author route names must be distinct.")
	referee = _role_route(routes.get("referee"), "daily_blog.routes.referee")
	if referee.name in {route.name for route in authors}:
		raise RuntimeError("Referee route name must be distinct from author route names.")
	return authors, referee


#============================================
def _load_repository_outline_config(settings: dict) -> RepositoryOutlineConfig:
	"""Load the independent repository-outline policy without widening post policy."""
	configured = pipeline_settings.get_nested_value(
		settings,
		["daily_blog", "repository_outline"],
		{},
	)
	if not isinstance(configured, dict):
		raise RuntimeError("daily_blog.repository_outline must be a mapping.")
	known = set(DEFAULT_REPOSITORY_OUTLINE_RELIABILITY) | {"routes", "prompt_limits"}
	unknown = set(configured) - known
	if unknown:
		names = ", ".join(sorted(unknown))
		raise RuntimeError(f"Unknown daily_blog.repository_outline keys: {names}")
	values = dict(DEFAULT_REPOSITORY_OUTLINE_RELIABILITY)
	values.update({key: configured[key] for key in DEFAULT_REPOSITORY_OUTLINE_RELIABILITY if key in configured})
	routes_value = configured.get("routes", {})
	if not isinstance(routes_value, dict):
		raise RuntimeError("daily_blog.repository_outline.routes must be a mapping.")
	unknown_routes = set(routes_value) - {"generator", "merger", "reviewer"}
	if unknown_routes:
		names = ", ".join(sorted(unknown_routes))
		raise RuntimeError(f"Unknown daily_blog.repository_outline.routes keys: {names}")
	routes = {}
	for role in ("generator", "merger", "reviewer"):
		if role in routes_value:
			routes[role] = _role_route(
				routes_value[role],
				f"daily_blog.repository_outline.routes.{role}",
			)
		else:
			routes[role] = _default_repository_outline_route(f"repository_outline_{role}")
	prompt_limits = dict(DEFAULT_REPOSITORY_OUTLINE_PROMPT_LIMITS)
	configured_limits = configured.get("prompt_limits", {})
	if not isinstance(configured_limits, dict):
		raise RuntimeError("daily_blog.repository_outline.prompt_limits must be a mapping.")
	unknown_limits = set(configured_limits) - set(prompt_limits)
	if unknown_limits:
		names = ", ".join(sorted(unknown_limits))
		raise RuntimeError(f"Unknown daily_blog.repository_outline.prompt_limits keys: {names}")
	prompt_limits.update(configured_limits)
	return RepositoryOutlineConfig(
		**values,
		generator_route=routes["generator"],
		merger_route=routes["merger"],
		reviewer_route=routes["reviewer"],
		prompt_limits=prompt_limits,
	)


#============================================
def _load_repository_story_config(settings: dict) -> RepositoryStoryConfig:
	"""Load the independent repository-story policy without inheriting Stage 3 behavior."""
	configured = pipeline_settings.get_nested_value(
		settings, ["daily_blog", "repository_story"], {},
	)
	if not isinstance(configured, dict):
		raise RuntimeError("daily_blog.repository_story must be a mapping.")
	known = set(DEFAULT_REPOSITORY_STORY_RELIABILITY) | {"routes", "prompt_limits"}
	unknown = set(configured) - known
	if unknown:
		names = ", ".join(sorted(unknown))
		raise RuntimeError(f"Unknown daily_blog.repository_story keys: {names}")
	values = dict(DEFAULT_REPOSITORY_STORY_RELIABILITY)
	values.update({key: configured[key] for key in DEFAULT_REPOSITORY_STORY_RELIABILITY if key in configured})
	routes_value = configured.get("routes", {})
	if not isinstance(routes_value, dict):
		raise RuntimeError("daily_blog.repository_story.routes must be a mapping.")
	unknown_routes = set(routes_value) - {"writer", "editor", "reviewer"}
	if unknown_routes:
		names = ", ".join(sorted(unknown_routes))
		raise RuntimeError(f"Unknown daily_blog.repository_story.routes keys: {names}")
	routes = {}
	for role in ("writer", "editor", "reviewer"):
		if role in routes_value:
			routes[role] = _role_route(
				routes_value[role], f"daily_blog.repository_story.routes.{role}",
			)
		else:
			routes[role] = _default_repository_story_route(f"repository_story_{role}")
	prompt_limits = dict(DEFAULT_REPOSITORY_STORY_PROMPT_LIMITS)
	configured_limits = configured.get("prompt_limits", {})
	if not isinstance(configured_limits, dict):
		raise RuntimeError("daily_blog.repository_story.prompt_limits must be a mapping.")
	unknown_limits = set(configured_limits) - set(prompt_limits)
	if unknown_limits:
		names = ", ".join(sorted(unknown_limits))
		raise RuntimeError(f"Unknown daily_blog.repository_story.prompt_limits keys: {names}")
	prompt_limits.update(configured_limits)
	return RepositoryStoryConfig(
		**values,
		writer_route=routes["writer"],
		editor_route=routes["editor"],
		reviewer_route=routes["reviewer"],
		prompt_limits=prompt_limits,
	)


#============================================
def _load_complete_post_config(settings: dict) -> CompletePostConfig:
	"""Load the current Stage 6 editorial policy from configured settings."""
	configured = pipeline_settings.get_nested_value(
		settings, ["daily_blog", "complete_post"], {},
	)
	if not isinstance(configured, dict):
		raise RuntimeError("daily_blog.complete_post must be a mapping.")
	known = set(DEFAULT_COMPLETE_POST_RELIABILITY) | {"routes", "prompt_limits"}
	unknown = set(configured) - known
	if unknown:
		names = ", ".join(sorted(unknown))
		raise RuntimeError(f"Unknown daily_blog.complete_post keys: {names}")
	values = dict(DEFAULT_COMPLETE_POST_RELIABILITY)
	values.update({
		key: configured[key]
		for key in DEFAULT_COMPLETE_POST_RELIABILITY
		if key in configured
	})
	routes_value = configured.get("routes", {})
	if not isinstance(routes_value, dict):
		raise RuntimeError("daily_blog.complete_post.routes must be a mapping.")
	unknown_routes = set(routes_value) - {"writer", "editor", "reviewer"}
	if unknown_routes:
		names = ", ".join(sorted(unknown_routes))
		raise RuntimeError(f"Unknown daily_blog.complete_post.routes keys: {names}")
	routes = {}
	for role in ("writer", "editor", "reviewer"):
		if role in routes_value:
			routes[role] = _role_route(
				routes_value[role], f"daily_blog.complete_post.routes.{role}",
			)
		else:
			routes[role] = _default_complete_post_route(f"complete_post_{role}")
	prompt_limits = dict(DEFAULT_COMPLETE_POST_PROMPT_LIMITS)
	configured_limits = configured.get("prompt_limits", {})
	if not isinstance(configured_limits, dict):
		raise RuntimeError("daily_blog.complete_post.prompt_limits must be a mapping.")
	unknown_limits = set(configured_limits) - set(prompt_limits)
	if unknown_limits:
		names = ", ".join(sorted(unknown_limits))
		raise RuntimeError(f"Unknown daily_blog.complete_post.prompt_limits keys: {names}")
	prompt_limits.update(configured_limits)
	return CompletePostConfig(
		**values,
		writer_route=routes["writer"],
		editor_route=routes["editor"],
		reviewer_route=routes["reviewer"],
		prompt_limits=prompt_limits,
	)


#============================================
def _load_daily_outline_config(settings: dict) -> DailyOutlineConfig:
	"""Load the isolated Stage 5 policy and its three sealed route identities."""
	configured = pipeline_settings.get_nested_value(settings, ["daily_blog", "daily_outline"], {})
	if not isinstance(configured, dict):
		raise RuntimeError("daily_blog.daily_outline must be a mapping.")
	known = set(DEFAULT_DAILY_OUTLINE_RELIABILITY) | {"routes", "prompt_limits"}
	unknown = set(configured) - known
	if unknown:
		names = ", ".join(sorted(unknown))
		raise RuntimeError(f"Unknown daily_blog.daily_outline keys: {names}")
	values = dict(DEFAULT_DAILY_OUTLINE_RELIABILITY)
	values.update({key: configured[key] for key in DEFAULT_DAILY_OUTLINE_RELIABILITY if key in configured})
	routes_value = configured.get("routes", {})
	if not isinstance(routes_value, dict):
		raise RuntimeError("daily_blog.daily_outline.routes must be a mapping.")
	roles = ("ranking", "outline_writer", "outline_reviewer")
	unknown_routes = set(routes_value) - set(roles)
	if unknown_routes:
		names = ", ".join(sorted(unknown_routes))
		raise RuntimeError(f"Unknown daily_blog.daily_outline.routes keys: {names}")
	routes = {
		role: _role_route(routes_value[role], f"daily_blog.daily_outline.routes.{role}")
		if role in routes_value else _default_daily_outline_route(f"daily_outline_{role}")
		for role in roles
	}
	prompt_limits = dict(DEFAULT_DAILY_OUTLINE_PROMPT_LIMITS)
	configured_limits = configured.get("prompt_limits", {})
	if not isinstance(configured_limits, dict):
		raise RuntimeError("daily_blog.daily_outline.prompt_limits must be a mapping.")
	unknown_limits = set(configured_limits) - set(prompt_limits)
	if unknown_limits:
		names = ", ".join(sorted(unknown_limits))
		raise RuntimeError(f"Unknown daily_blog.daily_outline.prompt_limits keys: {names}")
	prompt_limits.update(configured_limits)
	return DailyOutlineConfig(
		**values,
		ranking_route=routes["ranking"],
		outline_writer_route=routes["outline_writer"],
		outline_reviewer_route=routes["outline_reviewer"],
		prompt_limits=prompt_limits,
	)


#============================================

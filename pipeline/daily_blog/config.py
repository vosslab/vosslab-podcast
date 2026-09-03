"""Settings-backed aggregate runtime configuration and loading."""

# Standard Library
import dataclasses
import os
import re

# local repo modules
from podlib import pipeline_settings
import daily_blog.editorial_stage_config
import daily_blog.final_synthesis_config

DEFAULT_COLLECTION_LIMITS = {
	"changed_documentation_chars": 16000,
	"diff_chars": 24000,
	"readme_context_chars": 6000,
	"commit_metadata_chars": 6000,
	"per_item_chars": 8000,
	"supporting_total_chars": 48000,
	"screenshot_count": 12,
}
DEFAULT_PROJECTION_LIMITS = {
	"context_chars": 60000,
	"excerpt_chars": 6000,
	"commit_subject_chars": 480,
}
DEFAULT_PROMPT_LIMITS = {
	"author_chars": 72000,
	"referee_chars": 88000,
}
DEFAULT_EDITORIAL_RELIABILITY = {
	"candidate_count": 2,
	"reviewer_count": 1,
	"max_parallel_calls": 1,
	"route_retry_attempts": 1,
}
_GITHUB_OWNER_RE = re.compile(r"^[A-Za-z0-9-]+$")
DAILY_BLOG_SETTING_KEYS = {
	"collection_limits",
	"complete_post",
	"daily_outline",
	"editorial_reliability",
	"final_synthesis",
	"logging",
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
class EditorialReliabilityConfig:
	"""Bounded replication and concurrency settings for subjective stages."""

	candidate_count: int = DEFAULT_EDITORIAL_RELIABILITY["candidate_count"]
	reviewer_count: int = DEFAULT_EDITORIAL_RELIABILITY["reviewer_count"]
	max_parallel_calls: int = DEFAULT_EDITORIAL_RELIABILITY["max_parallel_calls"]
	route_retry_attempts: int = DEFAULT_EDITORIAL_RELIABILITY["route_retry_attempts"]

	#============================================
	def __post_init__(self) -> None:
		"""Require enough alternatives and explicit global resource bounds."""
		values = (
			self.candidate_count,
			self.reviewer_count,
			self.max_parallel_calls,
		)
		if any(type(value) is not int or value <= 0 for value in values):
			raise RuntimeError("Editorial reliability settings must be positive integers.")
		if type(self.route_retry_attempts) is not int or self.route_retry_attempts < 0:
			raise RuntimeError("Editorial route retry attempts must be a nonnegative integer.")
		if self.candidate_count < 2:
			raise RuntimeError("Editorial generation requires at least two independent candidates.")

@dataclasses.dataclass(frozen=True)
class DailyBlogLoggingConfig:
	"""Optional bound for the one report-date-owned operational journal."""

	max_events_per_run: int | None = None

	#============================================
	def __post_init__(self) -> None:
		"""Require explicitly configured limits to be positive exact integers."""
		for name, value in (("max_events_per_run", self.max_events_per_run),):
			if value is not None and (type(value) is not int or value <= 0):
				raise RuntimeError(f"daily_blog.logging.{name} must be a positive integer.")



@dataclasses.dataclass(frozen=True)
class DailyBlogConfig:
	"""Complete runtime configuration for one daily publication run."""

	settings_path: str
	output_root: str
	output_owner: str
	report_timezone: str
	daily_blog_repository: str
	mirror_cache_root: str
	author_routes: tuple[daily_blog.editorial_stage_config.RoleRoute, ...]
	referee_route: daily_blog.editorial_stage_config.RoleRoute
	collection_limits: dict[str, int]
	projection_limits: dict[str, int]
	prompt_limits: dict[str, int]
	editorial_reliability: EditorialReliabilityConfig = dataclasses.field(
		default_factory=EditorialReliabilityConfig
	)
	repository_outline: daily_blog.editorial_stage_config.RepositoryOutlineConfig = dataclasses.field(
		default_factory=daily_blog.editorial_stage_config.RepositoryOutlineConfig
	)
	repository_story: daily_blog.editorial_stage_config.RepositoryStoryConfig = dataclasses.field(
		default_factory=daily_blog.editorial_stage_config.RepositoryStoryConfig
	)
	complete_post: daily_blog.editorial_stage_config.CompletePostConfig = dataclasses.field(
		default_factory=daily_blog.editorial_stage_config.CompletePostConfig
	)
	daily_outline: daily_blog.editorial_stage_config.DailyOutlineConfig = dataclasses.field(
		default_factory=daily_blog.editorial_stage_config.DailyOutlineConfig
	)
	final_synthesis: daily_blog.final_synthesis_config.FinalSynthesisConfig = dataclasses.field(
		default_factory=daily_blog.final_synthesis_config.FinalSynthesisConfig
	)
	logging: DailyBlogLoggingConfig = dataclasses.field(
		default_factory=DailyBlogLoggingConfig
	)



#============================================
def _load_limits(
	settings: dict,
	name: str,
	defaults: dict[str, int],
) -> dict[str, int]:
	"""Load one positive daily-blog limit mapping with explicit known keys."""
	configured = pipeline_settings.get_nested_value(settings, ["daily_blog", name], {})
	if not isinstance(configured, dict):
		raise RuntimeError(f"daily_blog.{name} must be a mapping.")
	unknown = set(configured) - set(defaults)
	if unknown:
		names = ", ".join(sorted(unknown))
		raise RuntimeError(f"Unknown daily_blog.{name} keys: {names}")
	limits = dict(defaults)
	for key, value in configured.items():
		if type(value) is not int or value <= 0:
			raise RuntimeError(f"daily_blog.{name}.{key} must be positive.")
		limits[key] = value
	return limits


#============================================
def _load_editorial_reliability(settings: dict) -> EditorialReliabilityConfig:
	"""Load bounded replication, concurrency, and transport retry policy."""
	configured = pipeline_settings.get_nested_value(
		settings, ["daily_blog", "editorial_reliability"], {},
	)
	if not isinstance(configured, dict):
		raise RuntimeError("daily_blog.editorial_reliability must be a mapping.")
	unknown = set(configured) - set(DEFAULT_EDITORIAL_RELIABILITY)
	if unknown:
		names = ", ".join(sorted(unknown))
		raise RuntimeError(f"Unknown daily_blog.editorial_reliability keys: {names}")
	values = dict(DEFAULT_EDITORIAL_RELIABILITY)
	values.update(configured)
	return EditorialReliabilityConfig(**values)


#============================================
def _load_logging_config(settings: dict) -> DailyBlogLoggingConfig:
	"""Load explicit logging controls without imposing an unmeasured default."""
	configured = pipeline_settings.get_nested_value(
		settings,
		["daily_blog", "logging"],
		{},
	)
	if not isinstance(configured, dict):
		raise RuntimeError("daily_blog.logging must be a mapping.")
	allowed = {"max_events_per_run"}
	unknown = set(configured) - allowed
	if unknown:
		names = ", ".join(sorted(unknown))
		raise RuntimeError(f"Unknown daily_blog.logging keys: {names}")
	return DailyBlogLoggingConfig(max_events_per_run=configured.get("max_events_per_run"))


def load_config(settings_path: str = "settings.yaml", output_root: str = "out") -> DailyBlogConfig:
	"""Load and validate the complete daily-blog producer configuration."""
	settings, resolved_path = pipeline_settings.load_settings(settings_path)
	daily_blog_settings = pipeline_settings.get_nested_value(settings, ["daily_blog"], {})
	if not isinstance(daily_blog_settings, dict):
		raise RuntimeError("daily_blog must be a mapping.")
	unknown_settings = set(daily_blog_settings) - DAILY_BLOG_SETTING_KEYS
	if unknown_settings:
		names = ", ".join(sorted(unknown_settings))
		raise RuntimeError(f"Unknown daily_blog settings: {names}")
	output_owner = pipeline_settings.get_github_username(settings)
	# This identifier becomes a durable output-path component.  Keep the
	# grammar broad enough for GitHub owners while excluding path syntax.
	if type(output_owner) is not str or _GITHUB_OWNER_RE.fullmatch(output_owner) is None:
		raise RuntimeError("GitHub output owner must use only ASCII letters, digits, or hyphens.")
	report_timezone = pipeline_settings.get_setting_str(
		settings,
		["daily_blog", "report_timezone"],
		"America/Chicago",
	)
	daily_blog_repository = pipeline_settings.get_setting_str(
		settings,
		["daily_blog", "repository_path"],
		"/home/vosslab/nsh/vosslab-daily-blog",
	)
	mirror_cache_root = pipeline_settings.get_setting_str(
		settings,
		["daily_blog", "mirror_cache_root"],
		"/home/vosslab/repo-mirrors",
	)
	author_routes, referee_route = daily_blog.editorial_stage_config._load_routes(settings)
	config = DailyBlogConfig(
		settings_path=resolved_path,
		output_root=os.path.abspath(output_root),
		output_owner=output_owner,
		report_timezone=report_timezone,
		daily_blog_repository=os.path.abspath(daily_blog_repository),
		mirror_cache_root=os.path.abspath(mirror_cache_root),
		author_routes=author_routes,
		referee_route=referee_route,
		collection_limits=_load_limits(
			settings,
			"collection_limits",
			DEFAULT_COLLECTION_LIMITS,
		),
		projection_limits=_load_limits(
			settings,
			"projection_limits",
			DEFAULT_PROJECTION_LIMITS,
		),
		prompt_limits=_load_limits(
			settings,
			"prompt_limits",
			DEFAULT_PROMPT_LIMITS,
		),
		editorial_reliability=_load_editorial_reliability(settings),
		repository_outline=daily_blog.editorial_stage_config._load_repository_outline_config(settings),
		repository_story=daily_blog.editorial_stage_config._load_repository_story_config(settings),
		complete_post=daily_blog.editorial_stage_config._load_complete_post_config(settings),
		daily_outline=daily_blog.editorial_stage_config._load_daily_outline_config(settings),
		final_synthesis=daily_blog.final_synthesis_config._load_final_synthesis_config(settings),
		logging=_load_logging_config(settings),
	)
	return config

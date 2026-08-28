"""Settings-backed configuration for producer and publisher ownership."""

# Standard Library
import os
import dataclasses

# local repo modules
from podlib import pipeline_settings


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
HERMES_INSTRUCTION_SOURCE_ARGUMENTS = {
	"--continue",
	"--query",
	"--resume",
	"--skills",
	"-c",
	"-q",
	"-r",
	"-s",
	"-z",
}
DAILY_BLOG_SETTING_KEYS = {
	"collection_limits",
	"identity_emails",
	"identity_names",
	"mirror_cache_root",
	"projection_limits",
	"prompt_limits",
	"report_timezone",
	"repository_path",
	"repository_urls",
	"routes",
	"schedule_start_date",
	"shadow_evaluation",
}


@dataclasses.dataclass(frozen=True)
class RoleRoute:
	"""One isolated command route for an author or referee role."""

	name: str
	command: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class DailyBlogConfig:
	"""Complete runtime configuration for one daily publication run."""

	settings_path: str
	output_root: str
	output_owner: str
	report_timezone: str
	daily_blog_repository: str
	mirror_cache_root: str
	repository_urls: tuple[str, ...]
	identity_names: tuple[str, ...]
	identity_emails: tuple[str, ...]
	author_routes: tuple[RoleRoute, ...]
	referee_route: RoleRoute
	collection_limits: dict[str, int]
	projection_limits: dict[str, int]
	prompt_limits: dict[str, int]
	schedule_start_date: str = ""
	allow_shadow_model_data_sharing: bool = False


#============================================
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
	"""Keep Hermes routes isolated from mutable profile instructions and sessions."""
	if os.path.basename(command[0]) != "hermes":
		return
	for argument in command:
		name = argument.split("=", 1)[0]
		if name in HERMES_INSTRUCTION_SOURCE_ARGUMENTS:
			raise RuntimeError(
				f"{label}.command includes an external instruction source or saved session: {name}"
			)
	if "--ignore-rules" not in command:
		raise RuntimeError(
			f"{label}.command must use --ignore-rules so repository templates own instructions."
		)
	if "--query-file" not in command:
		raise RuntimeError(f"{label}.command must receive its prompt through --query-file stdin.")
	index = command.index("--query-file")
	if index + 1 >= len(command) or command[index + 1] not in {"-", "/dev/stdin"}:
		raise RuntimeError(f"{label}.command query file must be stdin.")


#============================================
def _default_command() -> list[str]:
	"""Return the isolated Hermes stdin transport route."""
	command = [
		"hermes",
		"chat",
		"--in",
		"{generator_repository}",
		"--query-file",
		"-",
		"--ignore-rules",
		"--quiet",
	]
	return command


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
def _load_limits(
	settings: dict,
	name: str,
	defaults: dict[str, int],
) -> dict[str, int]:
	"""Load one positive daily-blog limit mapping with explicit known keys."""
	configured = pipeline_settings.get_nested_value(
		settings,
		["daily_blog", name],
		{},
	)
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
	report_timezone = pipeline_settings.get_setting_str(
		settings,
		["daily_blog", "report_timezone"],
		"America/Chicago",
	)
	schedule_start_date = pipeline_settings.get_setting_str(
		settings,
		["daily_blog", "schedule_start_date"],
		"",
	)
	daily_blog_repository = pipeline_settings.get_setting_str(
		settings,
		["daily_blog", "repository_path"],
		"/home/vosslab/nsh/vosslab-daily-blog",
	)
	mirror_cache_root = pipeline_settings.get_setting_str(
		settings,
		["daily_blog", "mirror_cache_root"],
		"/home/vosslab/repo-mirrors/vosslab",
	)
	repository_urls = _string_list(
		pipeline_settings.get_nested_value(settings, ["daily_blog", "repository_urls"], []),
		"daily_blog.repository_urls",
	)
	default_name = pipeline_settings.get_github_identity_login(settings)
	identity_names = _string_list(
		pipeline_settings.get_nested_value(
			settings,
			["daily_blog", "identity_names"],
			[default_name],
		),
		"daily_blog.identity_names",
	)
	identity_emails = _string_list(
		pipeline_settings.get_nested_value(
			settings,
			["daily_blog", "identity_emails"],
			pipeline_settings.get_github_allowed_emails(settings),
		),
		"daily_blog.identity_emails",
	)
	if not identity_names and not identity_emails:
		raise RuntimeError("Daily-blog attribution requires identity_names or identity_emails.")
	author_routes, referee_route = _load_routes(settings)
	config = DailyBlogConfig(
		settings_path=resolved_path,
		output_root=os.path.abspath(output_root),
		output_owner=output_owner,
		report_timezone=report_timezone,
		daily_blog_repository=os.path.abspath(daily_blog_repository),
		mirror_cache_root=os.path.abspath(mirror_cache_root),
		repository_urls=repository_urls,
		identity_names=identity_names,
		identity_emails=identity_emails,
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
		schedule_start_date=schedule_start_date,
		allow_shadow_model_data_sharing=pipeline_settings.get_setting_bool(
			settings,
			["daily_blog", "shadow_evaluation", "external_model_data_sharing"],
			False,
		),
	)
	return config

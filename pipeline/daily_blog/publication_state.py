"""Classify one date-owned publication from the renderer's durable outputs."""

# Standard Library
import dataclasses
import datetime
import os

# local repo modules
import daily_blog.config
import daily_blog.publisher


class PublicationStateIntegrityError(RuntimeError):
	"""One expected on-disk publication-integrity failure."""


@dataclasses.dataclass(frozen=True)
class PublicationInspection:
	"""One occupied-date inspection for deterministic caller policy."""

	state: str
	reason: str = ""


#============================================
def publication_source_path(config: daily_blog.config.DailyBlogConfig, report_date: str) -> str:
	"""Return the renderer-owned Markdown path for one report date."""
	root = os.path.abspath(config.daily_blog_repository)
	return os.path.join(root, "docs", "blog", "posts", f"{report_date}.md")


#============================================
def _parse_report_date(value: str, label: str) -> datetime.date:
	"""Parse one strict ISO report date with a bounded error."""
	try:
		parsed = datetime.date.fromisoformat(value)
	except ValueError as error:
		raise RuntimeError(f"{label} must use YYYY-MM-DD format.") from error
	if parsed.isoformat() != value:
		raise RuntimeError(f"{label} must use YYYY-MM-DD format.")
	return parsed


#============================================
def publication_exists(config: daily_blog.config.DailyBlogConfig, report_date: str) -> bool:
	"""Return whether one coherent current publication exists for the report date."""
	inspection = inspect_publication(config, report_date)
	if inspection.state == "missing":
		return False
	if inspection.state == "invalid":
		raise RuntimeError(f"Publisher publication state is invalid: {inspection.reason}")
	return True


#============================================
def inspect_publication(
	config: daily_blog.config.DailyBlogConfig, report_date: str,
) -> PublicationInspection:
	"""Classify a date as missing, current, or occupied-invalid without trusting it."""
	_parse_report_date(report_date, "Report date")
	root = os.path.abspath(config.daily_blog_repository)
	path = publication_source_path(config, report_date)
	release = os.path.join(root, "generated", "releases", report_date)
	assets = os.path.join(root, "docs", "blog", "posts", report_date)
	occupied_paths = (path, release, assets)
	if not any(os.path.lexists(candidate) for candidate in occupied_paths):
		return PublicationInspection("missing")
	try:
		# ASVS 5.3.2: report_date selects only code-owned post and release paths.
		if not os.path.isfile(path) or os.path.islink(path):
			raise PublicationStateIntegrityError(f"Publisher post must be one physical file: {path}")
		if not os.path.isdir(release) or os.path.islink(release):
			raise PublicationStateIntegrityError(
				f"Publisher release must be one physical directory: {release}"
			)
		daily_blog.publisher._confined_file(root, os.path.relpath(path, root), 2 * 1024 * 1024, "post")
	except (OSError, RuntimeError, PublicationStateIntegrityError) as error:
		return PublicationInspection("invalid", str(error))
	return PublicationInspection("current")

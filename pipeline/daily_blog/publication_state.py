"""Classify one date-owned publisher publication through a shared integrity check."""

# Standard Library
import dataclasses
import datetime
import json
import os

# local repo modules
import daily_blog.config
import daily_blog.io_utils
import daily_blog.publisher


PUBLICATION_SCHEMA_VERSION = daily_blog.publisher.PUBLISHER_PUBLICATION_RECORD_SCHEMA_VERSION
PUBLICATION_RECORD_FIELDS = daily_blog.publisher.PUBLISHER_PUBLICATION_RECORD_FIELDS


class PublicationStateIntegrityError(RuntimeError):
	"""One expected on-disk publication-integrity failure."""


@dataclasses.dataclass(frozen=True)
class PublicationInspection:
	"""One occupied-date inspection for deterministic caller policy."""

	state: str
	reason: str = ""


#============================================
def _archive_root(root: str, report_date: str) -> str:
	"""Return the one publisher-owned archive directory for a report date."""
	return os.path.join(root, "data", "publication_bundles", report_date)


#============================================
def publication_record_path(config: daily_blog.config.DailyBlogConfig, report_date: str) -> str:
	"""Return the publisher-owned success record for one report date."""
	root = os.path.abspath(config.daily_blog_repository)
	return os.path.join(root, "data", "publications", f"{report_date}.json")


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
def _validate_publication_state(
	config: daily_blog.config.DailyBlogConfig, report_date: str, value: dict, path: str,
) -> None:
	"""Delegate archive, record, and installed-post integrity to the one primitive."""
	if set(value) != PUBLICATION_RECORD_FIELDS:
		raise PublicationStateIntegrityError(f"Publisher record fields are unsupported: {path}")
	try:
		daily_blog.publisher.validate_committed_publication(
			config.daily_blog_repository, report_date, value["bundle_sha256"],
			expected_timezone=config.report_timezone,
		)
	except RuntimeError as error:
		raise PublicationStateIntegrityError(str(error)) from error


#============================================

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
	path = publication_record_path(config, report_date)
	occupied_paths = (
		path, _archive_root(root, report_date),
		os.path.join(root, "docs", "blog", "posts", f"{report_date}.md"),
		os.path.join(root, "generated", "releases", report_date),
	)
	if not any(os.path.lexists(candidate) for candidate in occupied_paths):
		return PublicationInspection("missing")
	try:
		if not os.path.isfile(path) or os.path.islink(path):
			raise PublicationStateIntegrityError(f"Publisher record must be one physical file: {path}")
		value = daily_blog.io_utils.read_json(path)
		if not isinstance(value, dict):
			raise PublicationStateIntegrityError(f"Publisher record must be an object: {path}")
		if value.get("schema_version") != PUBLICATION_SCHEMA_VERSION:
			raise PublicationStateIntegrityError(f"Publisher record schema is unsupported: {path}")
		if value.get("report_date") != report_date:
			raise PublicationStateIntegrityError(f"Publisher record date does not match its path: {path}")
		_validate_publication_state(config, report_date, value, path)
	except (
		OSError, UnicodeDecodeError, json.JSONDecodeError, PublicationStateIntegrityError,
	) as error:
		return PublicationInspection("invalid", str(error))
	return PublicationInspection("current")

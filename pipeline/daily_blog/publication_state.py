"""Classify one date-owned publisher publication through a shared integrity check."""

# Standard Library
import dataclasses
import datetime
import json
import os
import re
import zoneinfo

# local repo modules
import daily_blog.config
import daily_blog.io_utils
import daily_blog.publisher


PUBLICATION_SCHEMA_VERSION = daily_blog.publisher.PUBLISHER_PUBLICATION_RECORD_SCHEMA_VERSION
PUBLICATION_RECORD_FIELDS = daily_blog.publisher.PUBLISHER_PUBLICATION_RECORD_FIELDS
HISTORICAL_PUBLICATION_SCHEMA_VERSION = "vosslab.daily-blog.publication.v3"
HISTORICAL_PUBLICATION_RECORD_FIELDS = frozenset({
	"bundle_sha256", "editorial_projection_manifest", "evidence_manifest", "generator_revision",
	"generator_run", "imported_at", "post_path", "report_date", "schema_version", "timezone",
})
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


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
def _validate_historical_record(value: dict, report_date: str, path: str) -> None:
	"""Accept only the exact v3 record layout retained by the publisher."""
	if set(value) != HISTORICAL_PUBLICATION_RECORD_FIELDS:
		raise PublicationStateIntegrityError(
			f"Historical publisher record fields are unsupported: {path}"
		)
	if value["report_date"] != report_date:
		raise PublicationStateIntegrityError(f"Publisher record date does not match its path: {path}")
	bundle_sha256 = value["bundle_sha256"]
	if (
		not isinstance(bundle_sha256, str)
		or daily_blog.publisher.SHA256_RE.fullmatch(bundle_sha256) is None
	):
		raise PublicationStateIntegrityError("Historical publisher record bundle checksum is invalid.")
	generator_revision = value["generator_revision"]
	if (
		not isinstance(generator_revision, str)
		or daily_blog.publisher.SHA256_RE.fullmatch(generator_revision) is None
	):
		raise PublicationStateIntegrityError("Historical publisher record generator revision is invalid.")
	generator_run = value["generator_run"]
	if not isinstance(generator_run, str) or _RUN_ID_RE.fullmatch(generator_run) is None:
		raise PublicationStateIntegrityError("Historical publisher record generator run is invalid.")
	if not isinstance(value["timezone"], str) or not value["timezone"]:
		raise PublicationStateIntegrityError("Historical publisher record timezone is invalid.")
	try:
		zoneinfo.ZoneInfo(value["timezone"])
	except zoneinfo.ZoneInfoNotFoundError as error:
		raise PublicationStateIntegrityError(
			"Historical publisher record timezone is invalid."
		) from error
	expected_paths = {
		"editorial_projection_manifest": (
			f"data/publication_bundles/{report_date}/editorial_projection.json"
		),
		"evidence_manifest": f"data/publication_bundles/{report_date}/evidence.json",
		"post_path": f"docs/blog/posts/{report_date}.md",
	}
	if any(value[field] != expected for field, expected in expected_paths.items()):
		raise PublicationStateIntegrityError("Historical publisher record paths are inconsistent.")
	imported_at = value["imported_at"]
	if not isinstance(imported_at, str) or not imported_at.endswith("Z"):
		raise PublicationStateIntegrityError("Historical publisher record import time is invalid.")
	try:
		moment = datetime.datetime.fromisoformat(imported_at.replace("Z", "+00:00"))
	except ValueError as error:
		raise PublicationStateIntegrityError(
			"Historical publisher record import time is invalid."
		) from error
	canonical = moment.astimezone(datetime.UTC).replace(microsecond=0).isoformat()
	canonical = canonical.replace("+00:00", "Z")
	if moment.microsecond or canonical != imported_at:
		raise PublicationStateIntegrityError("Historical publisher record import time is invalid.")


#============================================
def _historical_archive_object(contents: bytes, label: str) -> dict:
	"""Decode one bounded v3 archive object without accepting another JSON shape."""
	try:
		value = json.loads(contents.decode("utf-8"))
	except (UnicodeDecodeError, json.JSONDecodeError) as error:
		raise PublicationStateIntegrityError(
			f"Historical publisher {label} is not valid JSON."
		) from error
	if not isinstance(value, dict):
		raise PublicationStateIntegrityError(f"Historical publisher {label} must be an object.")
	return value


#============================================
def _validate_historical_publication_state(
	config: daily_blog.config.DailyBlogConfig, report_date: str, value: dict, path: str,
) -> None:
	"""Verify the finite v3 archive surface allowed only for existing-date policy."""
	_validate_historical_record(value, report_date, path)
	if value["timezone"] != config.report_timezone:
		raise PublicationStateIntegrityError("Historical publisher record timezone is inconsistent.")
	try:
		with daily_blog.publisher.open_publication_archive(
			config.daily_blog_repository, report_date,
		) as archive:
			if archive.entry_names() != {
				"bundle.json", "evidence.json", "editorial_projection.json", "post.md",
			}:
				raise PublicationStateIntegrityError("Historical publisher archive shape is unsupported.")
			bundle = _historical_archive_object(
				archive.read_json_artifact("bundle.json", "historical bundle manifest"), "bundle manifest",
			)
			evidence = _historical_archive_object(
				archive.read_historical_v3_evidence(), "evidence",
			)
			projection = _historical_archive_object(
				archive.read_json_artifact("editorial_projection.json", "historical editorial projection"),
				"editorial projection",
			)
			archived_post = archive.read_post()
	except RuntimeError as error:
		if isinstance(error, PublicationStateIntegrityError):
			raise
		raise PublicationStateIntegrityError(str(error)) from error
	if bundle.get("schema_version") != "vosslab.daily-blog.bundle.v2":
		raise PublicationStateIntegrityError("Historical publisher bundle schema is unsupported.")
	if bundle.get("bundle_sha256") != value["bundle_sha256"] or (
		daily_blog.publication_contract.bundle_sha256(bundle) != value["bundle_sha256"]
	):
		raise PublicationStateIntegrityError("Historical publisher bundle checksum is inconsistent.")
	if bundle.get("report_date") != report_date or bundle.get("timezone") != value["timezone"]:
		raise PublicationStateIntegrityError("Historical publisher bundle date or timezone is inconsistent.")
	generator = bundle.get("generator")
	if (
		not isinstance(generator, dict)
		or generator.get("revision") != value["generator_revision"]
		or generator.get("run_id") != value["generator_run"]
	):
		raise PublicationStateIntegrityError("Historical publisher bundle generator is inconsistent.")
	for manifest, artifact, label, expected_path in (
		(bundle.get("evidence"), evidence, "evidence", "evidence.json"),
		(
			bundle.get("editorial_projection"), projection, "editorial projection",
			"editorial_projection.json",
		),
	):
		if (
			not isinstance(manifest, dict)
			or manifest.get("path") != expected_path
			or manifest.get("sha256") != daily_blog.io_utils.hash_value(artifact)
		):
			raise PublicationStateIntegrityError(f"Historical publisher {label} checksum is inconsistent.")
		if artifact.get("report_date") != report_date or artifact.get("timezone") != value["timezone"]:
			raise PublicationStateIntegrityError(
				f"Historical publisher {label} date or timezone is inconsistent."
			)
	if bundle.get("post") != {
		"path": "post.md", "sha256": daily_blog.io_utils.sha256_bytes(archived_post),
	}:
		raise PublicationStateIntegrityError("Historical publisher post checksum is inconsistent.")
	try:
		installed_post = daily_blog.publisher._confined_file(
			daily_blog.publisher._trusted_root(config.daily_blog_repository), value["post_path"],
			daily_blog.publisher.MAX_POST_BYTES, "historical installed post",
		)
	except RuntimeError as error:
		raise PublicationStateIntegrityError(str(error)) from error
	if installed_post != archived_post:
		raise PublicationStateIntegrityError(
			"Historical archived post does not match the installed post."
		)


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
		if value.get("schema_version") == PUBLICATION_SCHEMA_VERSION:
			if value.get("report_date") != report_date:
				raise PublicationStateIntegrityError(f"Publisher record date does not match its path: {path}")
			_validate_publication_state(config, report_date, value, path)
		elif value.get("schema_version") == HISTORICAL_PUBLICATION_SCHEMA_VERSION:
			_validate_historical_publication_state(config, report_date, value, path)
		else:
			raise PublicationStateIntegrityError(f"Publisher record schema is unsupported: {path}")
	except (
		OSError, UnicodeDecodeError, json.JSONDecodeError, PublicationStateIntegrityError,
	) as error:
		return PublicationInspection("invalid", str(error))
	return PublicationInspection("current")

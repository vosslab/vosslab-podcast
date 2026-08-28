"""Validate the publisher-owned current publication for one report date."""

# Standard Library
import datetime
import os
import pathlib
import dataclasses

# local repo modules
import daily_blog.bundles
import daily_blog.config
import daily_blog.io_utils
import daily_blog.repository_contracts
import daily_blog.schema


PUBLICATION_SCHEMA_VERSION = "vosslab.daily-blog.publication.v3"
PUBLICATION_RECORD_FIELDS = {
	"bundle_sha256",
	"editorial_projection_manifest",
	"evidence_manifest",
	"generator_revision",
	"generator_run",
	"imported_at",
	"post_path",
	"report_date",
	"schema_version",
	"timezone",
}


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
def _path_is_regular(path: str) -> bool:
	"""Return whether one path is a physical regular file."""
	return os.path.isfile(path) and not os.path.islink(path)


#============================================
def _read_declared_artifact(archive: str, relative_path: str, label: str) -> bytes:
	"""Read one confined physical archive artifact."""
	if not isinstance(relative_path, str):
		raise RuntimeError(f"Publisher bundle {label} path is invalid.")
	pure = pathlib.PurePosixPath(relative_path)
	if (
		pure.is_absolute()
		or ".." in pure.parts
		or not pure.parts
	):
		raise RuntimeError(f"Publisher bundle {label} path is invalid.")
	path = os.path.join(archive, *pure.parts)
	if os.path.commonpath((archive, os.path.realpath(path))) != archive:
		raise RuntimeError(f"Publisher bundle {label} path escapes its archive.")
	if not _path_is_regular(path):
		raise RuntimeError(f"Publisher bundle {label} artifact is unavailable.")
	with open(path, "rb") as handle:
		return handle.read()


#============================================
def _manifest_artifact(
	archive: str,
	manifest: object,
	label: str,
	required_fields: set[str],
) -> tuple[dict, bytes]:
	"""Validate and load one named manifest artifact."""
	if not isinstance(manifest, dict) or set(manifest) != required_fields:
		raise RuntimeError(f"Publisher bundle {label} manifest is invalid.")
	path = manifest.get("path")
	checksum = manifest.get("sha256")
	if not isinstance(path, str) or not _is_sha256(checksum):
		raise RuntimeError(f"Publisher bundle {label} manifest is invalid.")
	return manifest, _read_declared_artifact(archive, path, label)


#============================================
def publication_record_path(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
) -> str:
	"""Return the publisher-owned success record for one report date."""
	return os.path.join(
		os.path.abspath(config.daily_blog_repository),
		"data",
		"publications",
		f"{report_date}.json",
	)


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
def _is_sha256(value: object) -> bool:
	"""Return whether one value is lowercase SHA-256 text."""
	return (
		isinstance(value, str)
		and len(value) == 64
		and not (set(value) - set("0123456789abcdef"))
	)


#============================================
def _validate_imported_at(value: object, path: str) -> None:
	"""Require the publisher's canonical whole-second UTC timestamp."""
	if not isinstance(value, str) or not value.endswith("Z"):
		raise RuntimeError(f"Publisher record imported_at is invalid: {path}")
	try:
		moment = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
	except ValueError as error:
		raise RuntimeError(f"Publisher record imported_at is invalid: {path}") from error
	canonical = moment.astimezone(datetime.timezone.utc).replace(microsecond=0)
	if moment.microsecond or value != canonical.isoformat().replace("+00:00", "Z"):
		raise RuntimeError(f"Publisher record imported_at is invalid: {path}")


#============================================
def _validate_publication_state(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
	value: dict,
	path: str,
) -> None:
	"""Require one coherent date-keyed record, archive, post, and release."""
	if set(value) != PUBLICATION_RECORD_FIELDS:
		raise RuntimeError(f"Publisher record fields are unsupported: {path}")
	root = os.path.abspath(config.daily_blog_repository)
	archive_relative = f"data/publication_bundles/{report_date}"
	archive = _archive_root(root, report_date)
	expected_paths = {
		"evidence_manifest": f"{archive_relative}/evidence.json",
		"editorial_projection_manifest": f"{archive_relative}/editorial_projection.json",
		"post_path": f"docs/blog/posts/{report_date}.md",
	}
	for field, expected in expected_paths.items():
		if value.get(field) != expected:
			raise RuntimeError(f"Publisher record {field} is inconsistent: {path}")
	if value.get("timezone") != config.report_timezone:
		raise RuntimeError(f"Publisher record timezone is inconsistent: {path}")
	if not isinstance(value.get("generator_run"), str) or not value["generator_run"]:
		raise RuntimeError(f"Publisher record generator run is invalid: {path}")
	if not _is_sha256(value.get("generator_revision")):
		raise RuntimeError(f"Publisher record generator source fingerprint is invalid: {path}")
	if not _is_sha256(value.get("bundle_sha256")):
		raise RuntimeError(f"Publisher record bundle checksum is invalid: {path}")
	_validate_imported_at(value.get("imported_at"), path)
	if not os.path.isdir(archive) or os.path.islink(archive):
		raise RuntimeError(f"Publisher publication state is incomplete: {path}")
	bundle_path = os.path.join(archive, "bundle.json")
	if not _path_is_regular(bundle_path):
		raise RuntimeError(f"Publisher bundle manifest is unavailable: {path}")
	bundle = daily_blog.io_utils.read_json(bundle_path)
	if not isinstance(bundle, dict):
		raise RuntimeError(f"Publisher bundle manifest must be an object: {path}")
	_validate_bundle(config, report_date, value, bundle, archive)
	installed_post_path = os.path.join(root, expected_paths["post_path"])
	if not _path_is_regular(installed_post_path):
		raise RuntimeError(f"Publisher installed post is unavailable: {path}")
	with open(installed_post_path, "rb") as handle:
		installed_post = handle.read()
	archived_post = _read_declared_artifact(archive, "post.md", "post")
	if installed_post != archived_post:
		raise RuntimeError(f"Publisher archived post does not match installed source: {path}")
	if not _path_is_regular(os.path.join(root, "generated", "releases", report_date, "index.html")):
		raise RuntimeError(f"Publisher installed release is unavailable: {path}")


#============================================
def _validate_bundle(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
	record: dict,
	bundle: dict,
	archive: str,
) -> None:
	"""Verify every date-owned bundle artifact and its typed contracts."""
	if bundle.get("schema_version") != daily_blog.schema.BUNDLE_SCHEMA_VERSION:
		raise RuntimeError("Publisher bundle schema is unsupported.")
	if bundle.get("report_date") != report_date:
		raise RuntimeError("Publisher bundle date does not match its archive.")
	if bundle.get("timezone") != config.report_timezone:
		raise RuntimeError("Publisher bundle timezone is inconsistent.")
	if not _is_sha256(bundle.get("bundle_sha256")):
		raise RuntimeError("Publisher bundle checksum is invalid.")
	if bundle.get("bundle_sha256") != daily_blog.bundles.bundle_sha256(bundle):
		raise RuntimeError("Publisher bundle checksum does not match its manifest.")
	if bundle["bundle_sha256"] != record["bundle_sha256"]:
		raise RuntimeError("Publisher record checksum does not match its bundle.")
	evidence_manifest, _evidence_bytes = _manifest_artifact(
		archive, bundle.get("evidence"), "evidence", {"path", "packet_id", "sha256"}
	)
	roster_manifest, _roster_bytes = _manifest_artifact(
		archive, bundle.get("repository_roster"), "repository roster",
		{"path", "roster_id", "sha256"},
	)
	projection_manifest, _projection_bytes = _manifest_artifact(
		archive, bundle.get("editorial_projection"), "editorial projection",
		{"path", "projection_id", "sha256"},
	)
	post_manifest, post_bytes = _manifest_artifact(
		archive, bundle.get("post"), "post", {"path", "sha256"}
	)
	if evidence_manifest["path"] != "evidence.json":
		raise RuntimeError("Publisher bundle evidence path is invalid.")
	if roster_manifest["path"] != "repository_roster.json":
		raise RuntimeError("Publisher bundle repository roster path is invalid.")
	if projection_manifest["path"] != "editorial_projection.json":
		raise RuntimeError("Publisher bundle editorial projection path is invalid.")
	if post_manifest["path"] != "post.md":
		raise RuntimeError("Publisher bundle post path is invalid.")
	evidence = daily_blog.schema.EvidencePacket.from_dict(
		daily_blog.io_utils.read_json(os.path.join(archive, evidence_manifest["path"]))
	)
	roster = daily_blog.repository_contracts.RepositoryRoster.from_dict(
		daily_blog.io_utils.read_json(os.path.join(archive, roster_manifest["path"]))
	)
	projection = daily_blog.schema.EditorialProjection.from_dict(
		daily_blog.io_utils.read_json(os.path.join(archive, projection_manifest["path"]))
	)
	if daily_blog.io_utils.hash_value(evidence.to_dict()) != evidence_manifest["sha256"]:
		raise RuntimeError("Publisher bundle evidence checksum does not match its artifact.")
	if daily_blog.io_utils.hash_value(roster.to_dict()) != roster_manifest["sha256"]:
		raise RuntimeError("Publisher bundle repository roster checksum does not match its artifact.")
	if daily_blog.io_utils.hash_value(projection.to_dict()) != projection_manifest["sha256"]:
		raise RuntimeError("Publisher bundle editorial projection checksum does not match its artifact.")
	if evidence.report_date != report_date or evidence.timezone != config.report_timezone or not evidence.complete:
		raise RuntimeError("Publisher bundle evidence packet is not current and complete.")
	if evidence.packet_id != evidence_manifest["packet_id"]:
		raise RuntimeError("Publisher bundle evidence identity is inconsistent.")
	if roster.roster_id != roster_manifest["roster_id"]:
		raise RuntimeError("Publisher bundle repository roster identity is inconsistent.")
	if projection.projection_id != projection_manifest["projection_id"]:
		raise RuntimeError("Publisher bundle editorial projection identity is inconsistent.")
	if (
		projection.packet_id != evidence.packet_id
		or projection.report_date != report_date
		or projection.timezone != config.report_timezone
	):
		raise RuntimeError("Publisher bundle projection does not match its evidence packet.")
	if not {activity.repository for activity in evidence.activity} <= {
		item.repository for item in roster.repositories
	}:
		raise RuntimeError("Publisher bundle evidence exceeds its repository roster.")
	evidence_by_id = {item.evidence_id: item for item in evidence.items}
	if not {excerpt.evidence_id for excerpt in projection.excerpts} <= set(evidence_by_id):
		raise RuntimeError("Publisher bundle projection cites unavailable evidence.")
	if not {card.repository for card in projection.repositories} <= {
		item.repository for item in roster.repositories
	}:
		raise RuntimeError("Publisher bundle projection exceeds its repository roster.")
	if daily_blog.io_utils.sha256_bytes(post_bytes) != post_manifest["sha256"]:
		raise RuntimeError("Publisher bundle post checksum does not match its artifact.")
	_asset_paths: set[str] = set()
	assets = bundle.get("assets")
	if not isinstance(assets, list):
		raise RuntimeError("Publisher bundle assets manifest is invalid.")
	for asset in assets:
		if not isinstance(asset, dict) or set(asset) != {
			"path", "sha256", "evidence_id", "git_blob_hash", "publish_path"
		}:
			raise RuntimeError("Publisher bundle asset manifest is invalid.")
		asset_path = asset["path"]
		if not isinstance(asset_path, str) or asset_path in _asset_paths or not _is_sha256(asset["sha256"]):
			raise RuntimeError("Publisher bundle asset manifest is invalid.")
		_asset_paths.add(asset_path)
		contents = _read_declared_artifact(archive, asset_path, "asset")
		if daily_blog.io_utils.sha256_bytes(contents) != asset["sha256"]:
			raise RuntimeError("Publisher bundle asset checksum does not match its artifact.")
		evidence_item = evidence_by_id.get(asset["evidence_id"])
		if (
			evidence_item is None
			or evidence_item.asset_path != asset_path
			or evidence_item.blob_hash != asset["git_blob_hash"]
			or evidence_item.publish_path != asset["publish_path"]
		):
			raise RuntimeError("Publisher bundle asset provenance is inconsistent.")


#============================================
def publication_exists(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
) -> bool:
	"""Return whether one coherent current publication exists for the report date."""
	inspection = inspect_publication(config, report_date)
	if inspection.state == "missing":
		return False
	if inspection.state == "invalid":
		raise RuntimeError(f"Publisher publication state is invalid: {inspection.reason}")
	return True


#============================================
def inspect_publication(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
) -> PublicationInspection:
	"""Classify a date as missing, current, or occupied-invalid without trusting it."""
	_parse_report_date(report_date, "Report date")
	root = os.path.abspath(config.daily_blog_repository)
	path = publication_record_path(config, report_date)
	occupied_paths = (
		path,
		_archive_root(root, report_date),
		os.path.join(root, "docs", "blog", "posts", f"{report_date}.md"),
		os.path.join(root, "generated", "releases", report_date),
	)
	if not any(os.path.lexists(candidate) for candidate in occupied_paths):
		return PublicationInspection("missing")
	try:
		if not _path_is_regular(path):
			raise RuntimeError(f"Publisher record must be one physical file: {path}")
		value = daily_blog.io_utils.read_json(path)
		if not isinstance(value, dict):
			raise RuntimeError(f"Publisher record must be an object: {path}")
		if value.get("schema_version") != PUBLICATION_SCHEMA_VERSION:
			raise RuntimeError(f"Publisher record schema is unsupported: {path}")
		if value.get("report_date") != report_date:
			raise RuntimeError(f"Publisher record date does not match its path: {path}")
		_validate_publication_state(config, report_date, value, path)
	except Exception as error:
		return PublicationInspection("invalid", str(error))
	return PublicationInspection("current")

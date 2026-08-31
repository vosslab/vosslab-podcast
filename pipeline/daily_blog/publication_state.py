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
import daily_blog.publication_article_projection
import daily_blog.publication_contract
import daily_blog.publisher
import daily_blog.repository_contracts
import daily_blog.schema
import daily_blog.artifacts


PUBLICATION_SCHEMA_VERSION = daily_blog.publisher.PUBLISHER_PUBLICATION_RECORD_SCHEMA_VERSION
PUBLICATION_RECORD_FIELDS = daily_blog.publisher.PUBLISHER_PUBLICATION_RECORD_FIELDS
HISTORICAL_PUBLICATION_SCHEMA_VERSION = "vosslab.daily-blog.publication.v3"
HISTORICAL_PUBLICATION_RECORD_FIELDS = frozenset({
	"bundle_sha256", "editorial_projection_manifest", "evidence_manifest", "generator_revision",
	"generator_run", "imported_at", "post_path", "report_date", "schema_version", "timezone",
})
HISTORICAL_V5_PUBLICATION_SCHEMA_VERSION = "vosslab.daily-blog.publication.v5"
HISTORICAL_V5_PUBLICATION_RECORD_FIELDS = frozenset({
	"article_body_sha256", "best_artifact_id", "bundle_sha256", "editorial_projection_manifest",
	"evidence_manifest", "generator_revision", "generator_run", "imported_at", "post_path",
	"report_date", "schema_version", "timezone",
})
HISTORICAL_V5_BUNDLE_FIELDS = frozenset({
	"assets", "best_artifact_id", "bundle_sha256", "contracts", "created_at",
	"editorial_projection", "editorial_prompt_contract", "evidence", "generator",
	"maker_activation", "post", "report_date", "repository_roster", "schema_version", "timezone",
})
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class PublicationStateIntegrityError(RuntimeError):
	"""One expected on-disk publication-integrity failure."""


@dataclasses.dataclass(frozen=True)
class PublicationInspection:
	"""One occupied-date inspection for deterministic caller policy."""

	state: str
	reason: str = ""


@dataclasses.dataclass(frozen=True)
class _HistoricalV5Archive:
	"""Held v5/v8 bytes accepted only for occupied-date integrity inspection."""

	bundle: dict
	evidence: dict
	projection: dict
	roster: dict
	post: bytes
	asset_contents: dict[str, bytes]


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
def _validate_historical_v5_record(value: dict, report_date: str, path: str) -> None:
	"""Validate the exact v5 receipt retained only for read-only date inspection.

	V5 receipts keep an already occupied report date auditable.  New imports use
	the current schema and never accept this historical record shape.
	"""
	if set(value) != HISTORICAL_V5_PUBLICATION_RECORD_FIELDS:
		raise PublicationStateIntegrityError(
			f"Historical v5 publisher record fields are unsupported: {path}"
		)
	if value["report_date"] != report_date:
		raise PublicationStateIntegrityError(f"Historical v5 record date does not match its path: {path}")
	for field, label in (
		("bundle_sha256", "bundle checksum"),
		("generator_revision", "generator revision"),
		("article_body_sha256", "article body checksum"),
	):
		if (
			type(value[field]) is not str
			or daily_blog.publisher.SHA256_RE.fullmatch(value[field]) is None
		):
			raise PublicationStateIntegrityError(f"Historical v5 record {label} is invalid.")
	if (
		type(value["best_artifact_id"]) is not str
		or daily_blog.artifacts.ARTIFACT_ID_RE.fullmatch(value["best_artifact_id"]) is None
	):
		raise PublicationStateIntegrityError("Historical v5 record selected artifact is invalid.")
	if type(value["generator_run"]) is not str or _RUN_ID_RE.fullmatch(value["generator_run"]) is None:
		raise PublicationStateIntegrityError("Historical v5 record generator run is invalid.")
	if type(value["timezone"]) is not str or not value["timezone"]:
		raise PublicationStateIntegrityError("Historical v5 record timezone is invalid.")
	try:
		zoneinfo.ZoneInfo(value["timezone"])
	except zoneinfo.ZoneInfoNotFoundError as error:
		raise PublicationStateIntegrityError("Historical v5 record timezone is invalid.") from error
	expected_paths = {
		"editorial_projection_manifest": (
			f"data/publication_bundles/{report_date}/editorial_projection.json"
		),
		"evidence_manifest": f"data/publication_bundles/{report_date}/evidence.json",
		"post_path": f"docs/blog/posts/{report_date}.md",
	}
	if any(value[field] != expected for field, expected in expected_paths.items()):
		raise PublicationStateIntegrityError("Historical v5 record paths are inconsistent.")
	imported_at = value["imported_at"]
	if type(imported_at) is not str or not imported_at.endswith("Z"):
		raise PublicationStateIntegrityError("Historical v5 record import time is invalid.")
	try:
		moment = datetime.datetime.fromisoformat(imported_at.replace("Z", "+00:00"))
	except ValueError as error:
		raise PublicationStateIntegrityError("Historical v5 record import time is invalid.") from error
	canonical = (
		moment.astimezone(datetime.UTC).replace(microsecond=0).isoformat()
		.replace("+00:00", "Z")
	)
	if moment.microsecond or canonical != imported_at:
		raise PublicationStateIntegrityError("Historical v5 record import time is invalid.")


#============================================
def _canonical_historical_v5_json(contents: bytes, label: str) -> dict:
	"""Decode one exact JSON artifact from a held v5 occupied-date archive."""
	value = _historical_archive_object(contents, f"v5 {label}")
	if contents != daily_blog.io_utils.stable_json_text(value).encode("utf-8"):
		raise PublicationStateIntegrityError(f"Historical v5 {label} JSON is not canonical.")
	return value


#============================================
def _read_historical_v5_archive(
	config: daily_blog.config.DailyBlogConfig, report_date: str,
) -> _HistoricalV5Archive:
	"""Read the finite v5/v8 archive shape held for occupied-date inspection.

	This reader never produces a transfer for a new import; it only supplies
	immutable archive bytes to the historical integrity validator.
	"""
	try:
		with daily_blog.publisher.open_publication_archive(
			config.daily_blog_repository, report_date,
		) as archive:
			bundle = _canonical_historical_v5_json(
				archive.read_json_artifact("bundle.json", "historical v5 bundle manifest"), "bundle manifest",
			)
			if set(bundle) != HISTORICAL_V5_BUNDLE_FIELDS:
				raise PublicationStateIntegrityError("Historical v5 publisher bundle fields are unsupported.")
			assets = bundle["assets"]
			if type(assets) is not list:
				raise PublicationStateIntegrityError("Historical v5 bundle assets manifest is invalid.")
			core_entries = {
				"bundle.json", "evidence.json", "editorial_projection.json", "repository_roster.json", "post.md",
			}
			expected_entries = core_entries | ({"assets"} if assets else set())
			allowed_entries = {frozenset(expected_entries)}
			if not assets:
				allowed_entries.add(frozenset(core_entries | {"assets"}))
			if archive.entry_names() not in allowed_entries:
				raise PublicationStateIntegrityError("Historical v5 publisher archive shape is unsupported.")
			evidence_value = _canonical_historical_v5_json(
				archive.read_json_artifact("evidence.json", "historical v5 evidence"), "evidence",
			)
			projection_value = _canonical_historical_v5_json(
				archive.read_json_artifact("editorial_projection.json", "historical v5 editorial projection"),
				"editorial projection",
			)
			roster_value = _canonical_historical_v5_json(
				archive.read_json_artifact("repository_roster.json", "historical v5 repository roster"),
				"repository roster",
			)
			archived_post = archive.read_post()
			asset_contents: dict[str, bytes] = {}
			for item in assets:
				if type(item) is not dict or set(item) != {
					"evidence_id", "git_blob_hash", "path", "publish_path", "sha256",
				}:
					raise PublicationStateIntegrityError("Historical v5 bundle assets manifest is invalid.")
				asset_path = daily_blog.schema.validate_bundle_asset_path(item["path"])
				if not asset_path or asset_path in asset_contents:
					raise PublicationStateIntegrityError("Historical v5 bundle assets manifest is invalid.")
				if (
					type(item["sha256"]) is not str
					or daily_blog.publisher.SHA256_RE.fullmatch(item["sha256"]) is None
				):
					raise PublicationStateIntegrityError("Historical v5 bundle asset checksum is invalid.")
				asset_contents[asset_path] = archive.read_asset(asset_path)
			if "assets" in archive.entry_names() and archive.asset_names() != {
				item["path"].removeprefix("assets/") for item in assets
			}:
				raise PublicationStateIntegrityError("Historical v5 archive assets do not match its manifest.")
	except RuntimeError as error:
		if isinstance(error, PublicationStateIntegrityError):
			raise
		raise PublicationStateIntegrityError(str(error)) from error
	return _HistoricalV5Archive(
		bundle, evidence_value, projection_value, roster_value, archived_post, asset_contents,
	)


#============================================
def _validate_historical_v5_bundle_identity(
	receipt: dict, report_date: str, archive: _HistoricalV5Archive,
) -> None:
	"""Bind a held v5/v8 bundle, manifests, and assets to its exact receipt."""
	_validate_historical_v5_bundle_metadata(receipt, report_date, archive.bundle)
	packet = _validate_historical_v5_manifests(receipt, report_date, archive)
	_validate_historical_v5_generator(receipt, archive.bundle)
	_validate_historical_v5_post_and_assets(receipt, archive.bundle, packet, archive)


#============================================
def _validate_historical_v5_bundle_metadata(
	receipt: dict, report_date: str, bundle: dict,
) -> None:
	"""Verify a held v5/v8 bundle's schema, digest, date, and timezone."""
	if bundle["schema_version"] != "vosslab.daily-blog.bundle.v8":
		raise PublicationStateIntegrityError("Historical v5 publisher bundle schema is unsupported.")
	if bundle["bundle_sha256"] != receipt["bundle_sha256"] or (
		daily_blog.publication_contract.bundle_sha256(bundle) != receipt["bundle_sha256"]
	):
		raise PublicationStateIntegrityError("Historical v5 publisher bundle checksum is inconsistent.")
	if bundle["report_date"] != report_date or bundle["timezone"] != receipt["timezone"]:
		raise PublicationStateIntegrityError("Historical v5 publisher bundle date or timezone is inconsistent.")


#============================================
def _validate_historical_v5_manifests(
	receipt: dict, report_date: str, archive: _HistoricalV5Archive,
) -> daily_blog.schema.EvidencePacket:
	"""Verify typed evidence, projection, and roster manifests in a held archive."""
	bundle = archive.bundle
	try:
		daily_blog.publication_contract.validate_bundle_identity_fields(bundle)
		packet = daily_blog.schema.EvidencePacket.from_dict(archive.evidence)
		projection = daily_blog.schema.EditorialProjection.from_dict(archive.projection)
		roster = daily_blog.repository_contracts.RepositoryRoster.from_dict(archive.roster)
	except RuntimeError as error:
		raise PublicationStateIntegrityError(str(error)) from error
	if packet.report_date != report_date or packet.timezone != receipt["timezone"]:
		raise PublicationStateIntegrityError("Historical v5 evidence date or timezone is inconsistent.")
	if projection.report_date != report_date or projection.timezone != receipt["timezone"] or (
		projection.packet_id != packet.packet_id
	):
		raise PublicationStateIntegrityError("Historical v5 editorial projection is inconsistent.")
	if not {activity.repository for activity in packet.activity} <= {
		item.repository for item in roster.repositories
	}:
		raise PublicationStateIntegrityError("Historical v5 activity exceeds its repository roster.")
	manifest_bindings = (
		("evidence", "evidence.json", "packet_id", packet.packet_id, archive.evidence),
		(
			"editorial_projection", "editorial_projection.json", "projection_id",
			projection.projection_id, archive.projection,
		),
		(
			"repository_roster", "repository_roster.json", "roster_id", roster.roster_id,
			archive.roster,
		),
	)
	for name, expected_path, identity_name, identity, artifact in manifest_bindings:
		if bundle[name] != {
			"path": expected_path, identity_name: identity,
			"sha256": daily_blog.io_utils.hash_value(artifact),
		}:
			raise PublicationStateIntegrityError(f"Historical v5 bundle {name} manifest is inconsistent.")
	return packet


#============================================
def _validate_historical_v5_generator(receipt: dict, bundle: dict) -> None:
	"""Bind held v5 generator metadata to the exact occupied-date receipt."""
	generator = bundle["generator"]
	if (
		type(generator) is not dict or set(generator) != {"revision", "run_id", "version"}
		or generator["revision"] != receipt["generator_revision"]
		or generator["run_id"] != receipt["generator_run"]
		or generator["version"] != daily_blog.schema.GENERATOR_VERSION
	):
		raise PublicationStateIntegrityError("Historical v5 bundle generator is inconsistent.")
	if type(bundle["created_at"]) is not str or not bundle["created_at"].endswith("Z"):
		raise PublicationStateIntegrityError("Historical v5 bundle creation time is invalid.")
	try:
		created_at = datetime.datetime.fromisoformat(bundle["created_at"].replace("Z", "+00:00"))
	except ValueError as error:
		raise PublicationStateIntegrityError("Historical v5 bundle creation time is invalid.") from error
	canonical_created_at = (
		created_at.astimezone(datetime.UTC).replace(microsecond=0).isoformat()
		.replace("+00:00", "Z")
	)
	if created_at.microsecond or canonical_created_at != bundle["created_at"]:
		raise PublicationStateIntegrityError("Historical v5 bundle creation time is invalid.")


#============================================
def _validate_historical_v5_post_and_assets(
	receipt: dict, bundle: dict, packet: daily_blog.schema.EvidencePacket,
	archive: _HistoricalV5Archive,
) -> None:
	"""Bind the held post and every held asset to the bundle and evidence packet."""
	post_manifest = bundle["post"]
	if (
		type(post_manifest) is not dict or set(post_manifest) != {"artifact_id", "path", "sha256"}
		or post_manifest["path"] != "post.md"
		or post_manifest["artifact_id"] != bundle["best_artifact_id"]
		or post_manifest["artifact_id"] != receipt["best_artifact_id"]
		or daily_blog.io_utils.sha256_bytes(archive.post) != post_manifest["sha256"]
	):
		raise PublicationStateIntegrityError("Historical v5 selected post binding is inconsistent.")
	packet_items = {item.evidence_id: item for item in packet.items}
	for item in bundle["assets"]:
		evidence = packet_items.get(item["evidence_id"])
		if (
			evidence is None or evidence.kind != "screenshot"
			or evidence.asset_path != item["path"] or evidence.publish_path != item["publish_path"]
			or evidence.blob_hash != item["git_blob_hash"]
			or daily_blog.io_utils.sha256_bytes(archive.asset_contents[item["path"]]) != item["sha256"]
		):
			raise PublicationStateIntegrityError("Historical v5 bundle asset is inconsistent.")


#============================================
def _validate_historical_v5_installed_article(
	config: daily_blog.config.DailyBlogConfig, receipt: dict, archived_post: bytes,
) -> None:
	"""Bind the installed v5 article and its rendered body digest to archive bytes."""
	try:
		installed_post = daily_blog.publisher._confined_file(
			daily_blog.publisher._trusted_root(config.daily_blog_repository), receipt["post_path"],
			daily_blog.publisher.MAX_POST_BYTES, "historical v5 installed post",
		)
		mkdocs_config = daily_blog.publisher._confined_file(
			daily_blog.publisher._trusted_root(config.daily_blog_repository), "mkdocs.yml",
			daily_blog.publisher.MAX_RECORD_BYTES, "historical v5 MkDocs configuration",
		).decode("utf-8")
		article_digest = daily_blog.publication_article_projection.article_body_sha256(
			daily_blog.publication_article_projection.source_article_projection(
				archived_post.decode("utf-8"), mkdocs_config,
			)
		)
	except (RuntimeError, UnicodeDecodeError) as error:
		raise PublicationStateIntegrityError(str(error)) from error
	if installed_post != archived_post:
		raise PublicationStateIntegrityError("Historical v5 archived post does not match the installed post.")
	if article_digest != receipt["article_body_sha256"]:
		raise PublicationStateIntegrityError("Historical v5 article body checksum is inconsistent.")


#============================================
def _validate_historical_v5_publication_state(
	config: daily_blog.config.DailyBlogConfig, report_date: str, value: dict, path: str,
) -> None:
	"""Inspect held v5/v8 state only; new imports require the current schema."""
	_validate_historical_v5_record(value, report_date, path)
	if value["timezone"] != config.report_timezone:
		raise PublicationStateIntegrityError("Historical v5 record timezone is inconsistent.")
	archive = _read_historical_v5_archive(config, report_date)
	_validate_historical_v5_bundle_identity(value, report_date, archive)
	_validate_historical_v5_installed_article(config, value, archive.post)


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
		elif value.get("schema_version") == HISTORICAL_V5_PUBLICATION_SCHEMA_VERSION:
			_validate_historical_v5_publication_state(config, report_date, value, path)
		elif value.get("schema_version") == HISTORICAL_PUBLICATION_SCHEMA_VERSION:
			_validate_historical_publication_state(config, report_date, value, path)
		else:
			raise PublicationStateIntegrityError(f"Publisher record schema is unsupported: {path}")
	except (
		OSError, UnicodeDecodeError, json.JSONDecodeError, PublicationStateIntegrityError,
	) as error:
		return PublicationInspection("invalid", str(error))
	return PublicationInspection("current")

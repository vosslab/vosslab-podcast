"""Shared schema and identity contract for sealed prompt-experiment fixtures."""

# Standard Library
import datetime
import re

# local repo modules
import daily_blog.io_utils
import daily_blog.repositories
import daily_blog.repository_contracts
import daily_blog.roster_snapshots


FIXTURE_SCHEMA_VERSION = "vosslab.daily-blog.experiment-fixture.v2"
FIXTURE_ROOT_NAME = "daily_blog_experiment_fixtures_v2"
FIXTURE_PAYLOAD_NAMES = ("evidence.json", "editorial_projection.json")
FIXTURE_FILE_NAMES = (*FIXTURE_PAYLOAD_NAMES, "manifest.json")
CONFIG_IDENTITY_FIELDS = (
	"collection_limits",
	"projection_limits",
	"report_timezone",
	"settings_name",
)
MANIFEST_IDENTITY_FIELDS = frozenset(
	{
		"config_identity",
		"evidence_count",
		"evidence_packet_id",
		"files",
		"mirrors",
		"projection_id",
		"projection_rendered_chars",
		"report_date",
		"repository_count",
		"repository_roster_snapshot",
		"schema_version",
		"source_repository",
	}
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SOURCE_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


#============================================
def _valid_sha256(value: object) -> bool:
	"""Return whether a value is one lowercase SHA-256 digest."""
	return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


#============================================
def _validate_config_identity(value: object) -> None:
	"""Validate the bounded, non-secret producer configuration identity."""
	if (
		not isinstance(value, dict)
		or set(value) != {"fields", "sha256"}
		or value["fields"] != list(CONFIG_IDENTITY_FIELDS)
		or not _valid_sha256(value["sha256"])
	):
		raise RuntimeError("Experiment fixture configuration identity is invalid.")


#============================================
def _validate_file_declarations(value: object) -> None:
	"""Validate the exact payload byte and digest declarations."""
	if not isinstance(value, dict) or set(value) != set(FIXTURE_PAYLOAD_NAMES):
		raise RuntimeError("Experiment fixture file declarations are invalid.")
	for declaration in value.values():
		if (
			not isinstance(declaration, dict)
			or set(declaration) != {"bytes", "sha256"}
			or type(declaration["bytes"]) is not int
			or declaration["bytes"] <= 0
			or not _valid_sha256(declaration["sha256"])
		):
			raise RuntimeError("Experiment fixture file identity is invalid.")


#============================================
def _validate_mirrors(value: object) -> None:
	"""Validate the sorted, path-free mirror identity list."""
	if not isinstance(value, list):
		raise RuntimeError("Experiment fixture mirror identities are invalid.")
	repositories = []
	for mirror in value:
		if not isinstance(mirror, dict) or set(mirror) != {
			"default_revision", "ref_fingerprint", "repository", "repository_url",
		}:
			raise RuntimeError("Experiment fixture mirror identity is invalid.")
		repository = mirror["repository"]
		if (
			not isinstance(repository, str)
			or REPOSITORY_RE.fullmatch(repository) is None
			or not isinstance(mirror["repository_url"], str)
			or mirror["repository_url"] != "https://github.com/" + repository
			or not isinstance(mirror["default_revision"], str)
			or re.fullmatch(r"[0-9a-f]{40}", mirror["default_revision"]) is None
			or not isinstance(mirror["ref_fingerprint"], str)
			or not _valid_sha256(mirror["ref_fingerprint"])
		):
			raise RuntimeError("Experiment fixture mirror value is invalid.")
		repositories.append(repository)
	normalized_repositories = [repository.casefold() for repository in repositories]
	if normalized_repositories != sorted(set(normalized_repositories)):
		raise RuntimeError("Experiment fixture mirrors are not uniquely authority-ordered.")


#============================================
def fixture_mirror_identities(mirrors: list[dict[str, object]]) -> list[dict[str, object]]:
	"""Return the exact path-free mirror identity stored by a fixture manifest."""
	result = [
		{
			"default_revision": mirror.get("default_revision", ""),
			"ref_fingerprint": mirror.get("ref_fingerprint", ""),
			"repository": mirror.get("repository", ""),
			"repository_url": mirror.get("repository_url", ""),
		}
		for mirror in sorted(mirrors, key=lambda item: str(item.get("repository", "")).casefold())
	]
	_validate_mirrors(result)
	return result


#============================================
def _validate_roster_identity(value: object, mirror_count: int) -> None:
	"""Validate the exact authoritative-roster identity copied into the fixture."""
	if not isinstance(value, dict) or set(value) != {
		"captured_utc", "repository_count", "roster_id", "schema_version", "source",
	}:
		raise RuntimeError("Experiment fixture roster identity is invalid.")
	if (
		value["schema_version"]
		!= daily_blog.roster_snapshots.ROSTER_SNAPSHOT_SCHEMA_VERSION
		or not _valid_sha256(value["roster_id"])
		or type(value["repository_count"]) is not int
		or value["repository_count"] != mirror_count
		or value["source"] != {
			"fresh": True,
			"kind": "github_owner_repositories",
			"policy": daily_blog.repositories.REPOSITORY_POLICY_VERSION,
		}
	):
		raise RuntimeError("Experiment fixture roster declaration is inconsistent.")
	daily_blog.repository_contracts.canonical_utc_timestamp(
		value["captured_utc"],
		"Experiment fixture roster capture time",
	)


#============================================
def validate_fixture_manifest_identity(value: object) -> dict[str, object]:
	"""Validate and return one unhashed fixture-manifest identity.

	Args:
		value: JSON-compatible manifest fields excluding ``fixture_id``.

	Returns:
		A shallow copy safe to hash or combine into a sealed manifest.

	Raises:
		RuntimeError: Any schema, type, range, ordering, or contextual rule fails.
	"""
	# ASVS 1.5.2 and 2.2.1: both writer and reader use the same positive JSON allowlist.
	if not isinstance(value, dict) or set(value) != MANIFEST_IDENTITY_FIELDS:
		raise RuntimeError("Experiment fixture manifest identity fields are invalid.")
	if value["schema_version"] != FIXTURE_SCHEMA_VERSION:
		raise RuntimeError("Experiment fixture manifest schema is invalid.")
	try:
		report_date = datetime.date.fromisoformat(value["report_date"])
	except (TypeError, ValueError) as error:
		raise RuntimeError("Experiment fixture report date is invalid.") from error
	if report_date.isoformat() != value["report_date"]:
		raise RuntimeError("Experiment fixture report date is not canonical.")
	if (
		not _valid_sha256(value["evidence_packet_id"])
		or not _valid_sha256(value["projection_id"])
		or type(value["evidence_count"]) is not int
		or value["evidence_count"] < 0
		or type(value["repository_count"]) is not int
		or value["repository_count"] < 0
		or type(value["projection_rendered_chars"]) is not int
		or value["projection_rendered_chars"] < 0
		or not isinstance(value["source_repository"], str)
		or SOURCE_REPOSITORY_RE.fullmatch(value["source_repository"]) is None
		or value["source_repository"] in {".", ".."}
	):
		raise RuntimeError("Experiment fixture manifest values are invalid.")
	_validate_config_identity(value["config_identity"])
	_validate_file_declarations(value["files"])
	_validate_mirrors(value["mirrors"])
	_validate_roster_identity(value["repository_roster_snapshot"], len(value["mirrors"]))
	return dict(value)


#============================================
def seal_fixture_manifest(identity: object) -> dict[str, object]:
	"""Validate and content-address one writer-produced fixture identity."""
	validated = validate_fixture_manifest_identity(identity)
	# ASVS 11.4.3: the complete canonical identity receives a collision-resistant digest.
	return {**validated, "fixture_id": daily_blog.io_utils.hash_value(validated)}


#============================================
def validate_fixture_manifest(value: object) -> dict[str, object]:
	"""Validate one sealed manifest and return its verified unhashed identity."""
	if not isinstance(value, dict) or value.get("schema_version") != FIXTURE_SCHEMA_VERSION:
		raise RuntimeError("Fixture manifest does not use the active capture schema.")
	if set(value) != MANIFEST_IDENTITY_FIELDS | {"fixture_id"}:
		raise RuntimeError("Experiment fixture manifest fields are invalid.")
	identity = {key: item for key, item in value.items() if key != "fixture_id"}
	validated = validate_fixture_manifest_identity(identity)
	if value["fixture_id"] != daily_blog.io_utils.hash_value(validated):
		raise RuntimeError("Experiment fixture manifest identity is invalid.")
	return validated

"""Immutable authoritative repository-roster snapshot storage."""

# Standard Library
import os
import re
import json
import stat
import uuid
import fcntl

# local repo modules
import daily_blog.schema
import daily_blog.io_utils
import daily_blog.repositories
import daily_blog.private_artifacts
import daily_blog.repository_contracts


ROSTER_SNAPSHOT_SCHEMA_VERSION = "vosslab.daily-blog.repository-roster-snapshot.v1"
ROSTER_SNAPSHOT_ROOT_NAME = "daily_blog_repository_rosters"
ROSTER_FILE_NAME = "repository_roster.json"
MANIFEST_FILE_NAME = "manifest.json"
SNAPSHOT_FILES = (MANIFEST_FILE_NAME, ROSTER_FILE_NAME)
MAX_SNAPSHOT_ARTIFACT_BYTES = 2_000_000

_LOCK_OPEN_FLAGS = (
	os.O_RDWR
	| os.O_CREAT
	| getattr(os, "O_NOFOLLOW", 0)
	| getattr(os, "O_CLOEXEC", 0)
)


#============================================
def _require_controlled_directory(fd: int, label: str) -> None:
	"""Require one held directory descriptor to be private and physical."""
	try:
		daily_blog.private_artifacts.require_directory(fd, 0o077)
	except RuntimeError:
		raise RuntimeError(f"Repository roster snapshot {label} must be producer-controlled.")


#============================================
def _open_directory_at(parent_fd: int, name: str, label: str) -> int:
	"""Open one direct physical child directory without resolving a symlink."""
	try:
		fd = daily_blog.private_artifacts.open_directory_at(parent_fd, name)
	except (OSError, RuntimeError) as error:
		if label == "directory":
			raise RuntimeError("Repository roster snapshot must use a physical root.") from error
		raise RuntimeError(f"Repository roster snapshot {label} is unavailable.") from error
	return fd


#============================================
def _open_physical_directory(path: str, *, create: bool) -> int:
	"""Open an absolute directory by physical components, retaining its descriptor."""
	try:
		fd = daily_blog.private_artifacts.open_physical_directory(
			path,
			create=create,
			intermediate_mode=0o777,
			leaf_mode=0o700,
		)
	except (OSError, RuntimeError) as error:
		raise RuntimeError("Repository roster snapshot parent is unavailable.") from error
	return fd


#============================================
def _snapshot_root_path(output_root: str, owner: str) -> str:
	"""Return the one validated logical roster-snapshot root path."""
	if not re.fullmatch(r"[A-Za-z0-9-]+", owner):
		raise RuntimeError("Repository roster snapshot owner is invalid.")
	root = os.path.abspath(os.path.join(output_root, owner, ROSTER_SNAPSHOT_ROOT_NAME))
	return root


#============================================
def _open_snapshot_root(output_root: str, owner: str, *, create: bool) -> tuple[str, int]:
	"""Return the logical root and a held producer-controlled root descriptor."""
	root = _snapshot_root_path(output_root, owner)
	root_fd = _open_physical_directory(root, create=create)
	try:
		# ASVS 2.2.1, 5.3.2, and 5.3.8: owner-derived paths are opened component-by-component,
		# and the private root descriptor remains authoritative for every child operation.
		_require_controlled_directory(root_fd, "root")
	except BaseException:
		os.close(root_fd)
		raise
	return root, root_fd


#============================================
def _snapshot_name(snapshot_path: str, root: str) -> str:
	"""Return one direct hash-addressed snapshot child name or reject the path."""
	if not snapshot_path or not os.path.isabs(snapshot_path):
		raise RuntimeError("Repository roster snapshot path must be explicit and absolute.")
	path = os.path.abspath(snapshot_path)
	if os.path.dirname(path) != root:
		raise RuntimeError("Repository roster snapshot is outside its configured physical root.")
	name = os.path.basename(path)
	if not re.fullmatch(r"[0-9a-f]{64}", name):
		raise RuntimeError("Repository roster snapshot identity path is invalid.")
	return name


#============================================
def _read_regular_bytes_at(parent_fd: int, name: str) -> bytes:
	"""Read a held-directory child after opening it without symlink following."""
	try:
		contents = daily_blog.private_artifacts.read_regular_bytes_at(
			parent_fd,
			name,
			maximum_bytes=MAX_SNAPSHOT_ARTIFACT_BYTES,
			forbidden_mode=0o077,
		)
	except (OSError, RuntimeError) as error:
		raise RuntimeError("Repository roster snapshot contains an unsafe artifact.") from error
	return contents


#============================================
def _write_regular_bytes_at(parent_fd: int, name: str, contents: bytes) -> None:
	"""Create one private regular child file without path replacement exposure."""
	daily_blog.private_artifacts.write_regular_bytes_at(parent_fd, name, contents)


#============================================
def _acquire_root_lock(root_fd: int, root: str) -> int:
	"""Acquire the capture lock beneath the held private root descriptor."""
	fd = os.open(".capture.lock", _LOCK_OPEN_FLAGS, 0o600, dir_fd=root_fd)
	try:
		status = os.fstat(fd)
		if not stat.S_ISREG(
			status.st_mode
		) or not daily_blog.private_artifacts.is_controlled(status, 0o077):
			raise RuntimeError("Repository roster snapshot capture lock is unsafe.")
		fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
	except BlockingIOError as error:
		os.close(fd)
		raise RuntimeError(f"Daily publication lock is already held: {root}") from error
	except BaseException:
		os.close(fd)
		raise
	return fd


#============================================
def _release_root_lock(lock_fd: int) -> None:
	"""Release one capture lock after the snapshot transaction ends."""
	fcntl.flock(lock_fd, fcntl.LOCK_UN)
	os.close(lock_fd)


#============================================
def _after_snapshot_directory_opened(_snapshot_fd: int) -> None:
	"""Provide a controlled replacement seam for the descriptor-race regression."""


#============================================
def _snapshot_source() -> dict[str, object]:
	"""Return the exact acquisition policy bound to every roster snapshot."""
	value = {
		"fresh": True,
		"kind": "github_owner_repositories",
		"policy": daily_blog.repositories.REPOSITORY_POLICY_VERSION,
	}
	return value


#============================================
def _snapshot_manifest(
	roster: daily_blog.repository_contracts.RepositoryRoster,
	captured_utc: str,
	roster_bytes: bytes,
) -> dict:
	"""Build the exact inspectable manifest for one roster artifact."""
	value = {
		"captured_utc": daily_blog.repository_contracts.canonical_utc_timestamp(
			captured_utc,
			"Repository roster snapshot capture time",
		),
		"files": {
			ROSTER_FILE_NAME: {
				"bytes": len(roster_bytes),
				"sha256": daily_blog.io_utils.sha256_bytes(roster_bytes),
			}
		},
		"owner": roster.owner,
		"roster_id": roster.roster_id,
		"schema_version": ROSTER_SNAPSHOT_SCHEMA_VERSION,
		"source": _snapshot_source(),
	}
	return value


#============================================
def _load_snapshot_from_root_fd(
	root_fd: int,
	owner: str,
	name: str,
) -> tuple[daily_blog.repository_contracts.RepositoryRoster, dict]:
	"""Load one direct child snapshot while root and child descriptors stay held.

	Args:
		root_fd: Held descriptor for the configured snapshot root.
		owner: Expected roster owner.
		name: Exact content-addressed direct child identity.

	Returns:
		Validated typed roster and public snapshot identity.

	Raises:
		RuntimeError: Descriptor, schema, hash, owner, or identity validation fails.
	"""
	snapshot_fd = _open_directory_at(root_fd, name, "directory")
	try:
		_require_controlled_directory(snapshot_fd, "directory")
		# ASVS 2.3.1, 5.3.2, and 5.3.8: pin this directory before any artifact read so a
		# pathname replacement cannot redirect a verified snapshot transaction.
		_after_snapshot_directory_opened(snapshot_fd)
		manifest_bytes = _read_regular_bytes_at(snapshot_fd, MANIFEST_FILE_NAME)
		roster_bytes = _read_regular_bytes_at(snapshot_fd, ROSTER_FILE_NAME)
	finally:
		os.close(snapshot_fd)
	try:
		manifest = json.loads(manifest_bytes)
		roster_value = json.loads(roster_bytes)
	except (UnicodeDecodeError, json.JSONDecodeError) as error:
		raise RuntimeError("Repository roster snapshot JSON is invalid.") from error
	manifest_fields = {
		"captured_utc",
		"files",
		"owner",
		"roster_id",
		"schema_version",
		"source",
	}
	if not isinstance(manifest, dict) or set(manifest) != manifest_fields:
		raise RuntimeError("Repository roster snapshot manifest fields are invalid.")
	if (
		manifest["schema_version"] != ROSTER_SNAPSHOT_SCHEMA_VERSION
		or manifest["source"] != _snapshot_source()
		or manifest["owner"] != owner
	):
		raise RuntimeError("Repository roster snapshot manifest contract is invalid.")
	daily_blog.repository_contracts.canonical_utc_timestamp(
		manifest["captured_utc"],
		"Repository roster snapshot capture time",
	)
	files = manifest["files"]
	if not isinstance(files, dict) or set(files) != {ROSTER_FILE_NAME}:
		raise RuntimeError("Repository roster snapshot file manifest is invalid.")
	file_identity = files[ROSTER_FILE_NAME]
	if not isinstance(file_identity, dict) or set(file_identity) != {"bytes", "sha256"}:
		raise RuntimeError("Repository roster snapshot file identity is invalid.")
	if (
		type(file_identity["bytes"]) is not int
		or file_identity["bytes"] != len(roster_bytes)
		or file_identity["sha256"] != daily_blog.io_utils.sha256_bytes(roster_bytes)
	):
		raise RuntimeError("Repository roster snapshot file integrity is invalid.")
	if not isinstance(roster_value, dict):
		raise RuntimeError("Repository roster snapshot roster must be an object.")
	roster = daily_blog.repository_contracts.RepositoryRoster.from_dict(roster_value)
	if roster.owner != owner or roster.roster_id != manifest["roster_id"] or name != roster.roster_id:
		raise RuntimeError("Repository roster snapshot identity is invalid.")
	identity = {
		"captured_utc": manifest["captured_utc"],
		"repository_count": len(roster.repositories),
		"roster_id": roster.roster_id,
		"schema_version": ROSTER_SNAPSHOT_SCHEMA_VERSION,
		"source": _snapshot_source(),
	}
	return roster, identity


#============================================
def load_repository_roster_snapshot(
	output_root: str,
	owner: str,
	snapshot_path: str,
) -> tuple[daily_blog.repository_contracts.RepositoryRoster, dict]:
	"""Load and fully verify one immutable authoritative roster snapshot."""
	root, root_fd = _open_snapshot_root(output_root, owner, create=False)
	try:
		name = _snapshot_name(snapshot_path, root)
		roster, identity = _load_snapshot_from_root_fd(root_fd, owner, name)
	finally:
		os.close(root_fd)
	return roster, identity


#============================================
def _remove_stage(root_fd: int, stage_name: str) -> None:
	"""Remove the known incomplete private stage through the held root descriptor."""
	daily_blog.private_artifacts.remove_known_stage(root_fd, stage_name, SNAPSHOT_FILES)


#============================================
def write_repository_roster_snapshot(
	output_root: str,
	owner: str,
	roster: daily_blog.repository_contracts.RepositoryRoster,
	*,
	captured_utc: str | None = None,
) -> tuple[str, dict]:
	"""Atomically persist or reuse one immutable typed roster snapshot.

	Args:
		output_root: Configured producer output root.
		owner: Expected owner for both namespace and roster.
		roster: Complete typed owner roster.
		captured_utc: Optional acquisition time supplied by capture orchestration.

	Returns:
		Absolute immutable snapshot path and verified public identity.

	Raises:
		RuntimeError: Ownership, locking, filesystem, schema, or reuse validation fails.
	"""
	roster = daily_blog.repository_contracts.RepositoryRoster.from_dict(roster.to_dict())
	if roster.owner != owner:
		raise RuntimeError("Repository roster snapshot owner does not match its roster.")
	root, root_fd = _open_snapshot_root(output_root, owner, create=True)
	destination = os.path.join(root, roster.roster_id)
	lock_fd = _acquire_root_lock(root_fd, root)
	identity = None
	try:
		try:
			existing_fd = _open_directory_at(root_fd, roster.roster_id, "directory")
		except RuntimeError:
			existing_fd = None
		if existing_fd is not None:
			os.close(existing_fd)
			_existing, identity = _load_snapshot_from_root_fd(root_fd, owner, roster.roster_id)
		else:
			stage_name = f".{roster.roster_id}.{uuid.uuid4().hex}.tmp"
			os.mkdir(stage_name, 0o700, dir_fd=root_fd)
			try:
				stage_fd = _open_directory_at(root_fd, stage_name, "stage")
				try:
					_require_controlled_directory(stage_fd, "stage")
					roster_bytes = daily_blog.io_utils.stable_json_text(roster.to_dict()).encode("utf-8")
					manifest = _snapshot_manifest(
						roster,
						captured_utc or daily_blog.schema.utc_now(),
						roster_bytes,
					)
					manifest_bytes = daily_blog.io_utils.stable_json_text(manifest).encode("utf-8")
					_write_regular_bytes_at(stage_fd, ROSTER_FILE_NAME, roster_bytes)
					_write_regular_bytes_at(stage_fd, MANIFEST_FILE_NAME, manifest_bytes)
					os.fsync(stage_fd)
				finally:
					os.close(stage_fd)
				os.rename(stage_name, roster.roster_id, src_dir_fd=root_fd, dst_dir_fd=root_fd)
			except BaseException:
				_remove_stage(root_fd, stage_name)
				raise
			_loaded, identity = _load_snapshot_from_root_fd(root_fd, owner, roster.roster_id)
	finally:
		_release_root_lock(lock_fd)
		os.close(root_fd)
	_loaded, public_identity = load_repository_roster_snapshot(output_root, owner, destination)
	if identity != public_identity:
		raise RuntimeError("Repository roster snapshot verification changed after creation.")
	identity = public_identity
	return destination, identity


#============================================
def capture_fresh_repository_roster(
	owner: str,
	output_root: str,
) -> tuple[str, dict]:
	"""Fetch and persist one fresh complete owner roster without raw payloads."""
	roster = daily_blog.repositories.discover_owner_repositories(owner, output_root)
	return write_repository_roster_snapshot(output_root, owner, roster)

#!/usr/bin/env python3
"""Capture an offline, non-publishing daily-blog experiment fixture."""

# Standard Library
import argparse
import dataclasses
import datetime
import json
import os
import pathlib
import stat
import subprocess
import sys
import uuid

# local repo modules
import daily_blog.activity
import daily_blog.config
import daily_blog.evidence
import daily_blog.io_utils
import daily_blog.projection
import daily_blog.private_artifacts
import daily_blog.roster_snapshots
import daily_blog.repository_contracts
import daily_blog.schema


FIXTURE_SCHEMA_VERSION = "vosslab.daily-blog.experiment-fixture.v2"
FIXTURE_ROOT_NAME = "daily_blog_experiment_fixtures_v2"
FIXTURE_FILE_NAMES = ("evidence.json", "editorial_projection.json", "manifest.json")
EXPERIMENT_REPORT_DATES = frozenset(("2026-08-23", "2026-08-26"))
MAX_PROJECTION_CONTEXT_CHARS = 60000
MAX_FIXTURE_ARTIFACT_BYTES = 4_000_000


@dataclasses.dataclass(frozen=True)
class PreparedFixture:
	"""Validated in-memory fixture bytes and identity awaiting private installation."""

	evidence: dict
	projection: dict
	manifest: dict
	destination_name: str
	projection_limit: int


#============================================
def _validate_report_date(report_date: str) -> None:
	"""Require a canonical calendar date before it becomes a directory name."""
	try:
		parsed = datetime.date.fromisoformat(report_date)
	except ValueError as error:
		raise RuntimeError("report date must use YYYY-MM-DD.") from error
	if parsed.isoformat() != report_date:
		raise RuntimeError("report date must use canonical YYYY-MM-DD form.")
	if report_date not in EXPERIMENT_REPORT_DATES:
		raise RuntimeError("Experiment fixture capture is sealed to its approved report dates.")


#============================================
def _contains_symlink(path: str) -> bool:
	"""Return whether an existing path component is a symbolic link."""
	current = os.path.sep
	for part in pathlib.PurePath(os.path.abspath(path)).parts[1:]:
		current = os.path.join(current, part)
		if os.path.lexists(current) and os.path.islink(current):
			return True
	return False


#============================================
def _open_fixture_root(root: str) -> tuple[int, os.stat_result]:
	"""Open the pre-existing narrow fixture root without following its final component."""
	if not root or not os.path.isabs(root):
		raise RuntimeError("Fixture root must be an explicit absolute path.")
	if ".." in pathlib.PurePath(root).parts:
		raise RuntimeError("Fixture root must not contain traversal components.")
	path = os.path.abspath(root)
	if os.path.basename(path) != FIXTURE_ROOT_NAME:
		raise RuntimeError(f"Fixture root must be named {FIXTURE_ROOT_NAME}.")
	if _contains_symlink(path):
		raise RuntimeError("Fixture root must not contain symbolic links.")
	if not os.path.lexists(path):
		raise RuntimeError("Fixture root must already exist before capture.")
	flags = os.O_RDONLY | os.O_DIRECTORY
	if hasattr(os, "O_NOFOLLOW"):
		flags |= os.O_NOFOLLOW
	try:
		fd = os.open(path, flags)
	except OSError as error:
		raise RuntimeError("Fixture root must be a real non-symbolic directory.") from error
	root_stat = os.fstat(fd)
	if not stat.S_ISDIR(root_stat.st_mode):
		os.close(fd)
		raise RuntimeError("Fixture root must be a directory.")
	return fd, root_stat


#============================================
def _configured_fixture_root(config: daily_blog.config.DailyBlogConfig, root: str) -> str:
	"""Allow only the narrow fixture root owned by this configured producer output."""
	expected = os.path.abspath(
		os.path.join(config.output_root, config.output_owner, FIXTURE_ROOT_NAME)
	)
	if os.path.abspath(root) != expected:
		raise RuntimeError("Fixture root must be the configured daily-blog experiment-fixture root.")
	if _contains_symlink(os.path.dirname(expected)):
		raise RuntimeError("Configured fixture parent must not contain symbolic links.")
	return expected


#============================================
def _before_fixture_child_creation() -> None:
	"""Provide a test seam immediately before fd-anchored staging creation."""


#============================================
def _before_fixture_install(_destination_name: str) -> None:
	"""Provide a test seam immediately before the no-replace final installation."""


#============================================
def _resolve_repository_roster(
	config: daily_blog.config.DailyBlogConfig,
	snapshot_path: str | None,
) -> tuple[daily_blog.repository_contracts.RepositoryRoster, dict]:
	"""Require and load one verified authoritative roster snapshot."""
	if snapshot_path is None:
		raise RuntimeError("Offline capture requires a repository roster snapshot.")
	return daily_blog.roster_snapshots.load_repository_roster_snapshot(
		config.output_root,
		config.output_owner,
		snapshot_path,
	)


#============================================
def _read_only_git(cache_path: str, arguments: list[str]) -> subprocess.CompletedProcess:
	"""Run only a fixed local Git inspection command against an existing cache."""
	allowed = (
		arguments == ["rev-parse", "--is-inside-work-tree"]
		or (
			len(arguments) == 3
			and arguments[:2] == ["rev-parse", "--verify"]
			and arguments[2].endswith("^{commit}")
		)
	)
	if not allowed:
		raise RuntimeError("Offline mirror inspector rejected a non-read-only Git command.")
	return subprocess.run(
		["git", "-C", cache_path, *arguments],
		check=False,
		text=True,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		timeout=60,
	)


#============================================
def _read_only_mirror_entry(
	record: daily_blog.repository_contracts.RepositoryRecord,
	cache_path: str,
	roster_id: str,
) -> dict:
	"""Build a mirror manifest entry strictly from local immutable Git state."""
	inside = _read_only_git(cache_path, ["rev-parse", "--is-inside-work-tree"])
	if inside.returncode or inside.stdout.strip() != "true":
		raise RuntimeError("Offline capture requires configured paths to be Git working trees.")
	revision = ""
	for reference in (
		"refs/remotes/origin/HEAD",
		"refs/remotes/origin/main",
		"refs/remotes/origin/master",
		"HEAD",
	):
		result = _read_only_git(cache_path, ["rev-parse", "--verify", f"{reference}^{{commit}}"])
		if result.returncode == 0 and result.stdout.strip():
			revision = result.stdout.strip()
			break
	if not revision:
		raise RuntimeError("Offline capture requires a locally resolvable mirror revision.")
	return {
		"cache_path": cache_path,
		"default_revision": revision,
		"object_available": True,
		"ref_fingerprint": daily_blog.io_utils.hash_value([revision]),
		"refresh_error": "",
		"refresh_result": "skipped",
		"refreshed_at": "",
		"repository": record.repository,
		"repository_url": record.repository_url,
		"clone_url": record.clone_url,
		"created_at": record.created_at,
		"is_fork": record.is_fork,
		"roster_id": roster_id,
	}


#============================================
def _offline_mirror_entries(
	config: daily_blog.config.DailyBlogConfig,
	roster: daily_blog.repository_contracts.RepositoryRoster,
) -> list[dict]:
	"""Inspect exactly rostered existing caches without clone, fetch, locks, or discovery."""
	roster = daily_blog.repository_contracts.RepositoryRoster.from_dict(roster.to_dict())
	root = os.path.abspath(config.mirror_cache_root)
	if not os.path.isdir(root) or os.path.islink(root) or _contains_symlink(root):
		raise RuntimeError("Offline capture requires a real existing mirror-cache root.")
	expected_paths = []
	for record in roster.repositories:
		owner, name = record.repository.split("/", 1)
		path = os.path.join(root, owner, name)
		if os.path.commonpath((root, path)) != root or os.path.islink(path):
			raise RuntimeError("Configured mirror cache path is unsafe.")
		if not os.path.isdir(path):
			raise RuntimeError("Offline capture requires every configured mirror cache to exist.")
		expected_paths.append(path)
	entries = [
		_read_only_mirror_entry(record, path, roster.roster_id)
		for record, path in zip(roster.repositories, expected_paths)
	]
	entries.sort(key=lambda item: item["repository"].casefold())
	return entries


#============================================
def _collect_offline_evidence(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
	roster: daily_blog.repository_contracts.RepositoryRoster,
) -> tuple[list[dict], daily_blog.schema.EvidencePacket]:
	"""Reuse production evidence assembly while forbidding its refresh/clone entry point."""
	mirrors = _offline_mirror_entries(config, roster)
	activity = daily_blog.activity.locate_activity(
		report_date,
		config.report_timezone,
		mirrors,
		config.identity_names,
		config.identity_emails,
	)
	assembler = daily_blog.evidence.EvidenceAssembler(
		report_date,
		config.report_timezone,
		config.collection_limits,
	)
	packet, _assets = assembler.assemble(mirrors, activity)
	if not packet.complete:
		raise RuntimeError("Offline evidence assembly is incomplete.")
	return mirrors, packet


#============================================
def _validate_artifacts(
	packet: daily_blog.schema.EvidencePacket,
	projection: daily_blog.schema.EditorialProjection,
	report_date: str,
	projection_limit: int,
) -> str:
	"""Reparse immutable artifacts and prove their identities and context bound."""
	verified_packet = daily_blog.schema.EvidencePacket.from_dict(packet.to_dict())
	verified_projection = daily_blog.schema.EditorialProjection.from_dict(projection.to_dict())
	if not verified_packet.complete:
		raise RuntimeError("Experiment fixture evidence packet is incomplete.")
	if verified_packet.report_date != report_date:
		raise RuntimeError("Evidence packet report date differs from the requested date.")
	if verified_projection.packet_id != verified_packet.packet_id:
		raise RuntimeError("Editorial projection does not belong to the evidence packet.")
	if verified_projection.report_date != verified_packet.report_date:
		raise RuntimeError("Editorial projection report date differs from the evidence packet.")
	if verified_projection.timezone != verified_packet.timezone:
		raise RuntimeError("Editorial projection timezone differs from the evidence packet.")
	daily_blog.projection._validate_exact_slices(verified_packet, verified_projection)
	context = verified_projection.render_context()
	if len(context) > projection_limit:
		raise RuntimeError("Editorial projection exceeds the configured context limit.")
	return context


#============================================
def _safe_config_identity(config: daily_blog.config.DailyBlogConfig) -> dict:
	"""Return a digest of relevant settings without routes, sessions, or credentials."""
	identity = {
		"collection_limits": config.collection_limits,
		"projection_limits": config.projection_limits,
		"report_timezone": config.report_timezone,
		"settings_name": os.path.basename(config.settings_path),
	}
	return {
		"fields": sorted(identity),
		"sha256": daily_blog.io_utils.hash_value(identity),
	}


#============================================
def _mirror_manifest(mirrors: list[dict]) -> list[dict]:
	"""Keep source identity and refs, omitting local cache paths and refresh errors."""
	result = []
	for mirror in sorted(mirrors, key=lambda item: str(item["repository"]).casefold()):
		result.append(
			{
				"default_revision": mirror.get("default_revision", ""),
				"ref_fingerprint": mirror.get("ref_fingerprint", ""),
				"repository": mirror.get("repository", ""),
				"repository_url": mirror.get("repository_url", ""),
			}
		)
	return result


#============================================
#============================================
def _write_fixture(
	root_fd: int,
	destination_name: str,
	evidence: dict,
	projection: dict,
	manifest: dict,
) -> None:
	"""Install a fully fsynced hidden stage through held fds, then atomically reveal it."""
	stage = f".{destination_name}.{uuid.uuid4().hex}.tmp"
	_before_fixture_child_creation()
	try:
		os.mkdir(stage, 0o700, dir_fd=root_fd)
	except FileExistsError as error:
		raise RuntimeError("Experiment fixture staging name already exists.") from error
	stage_fd = -1
	committed = False
	try:
		stage_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
		os.chmod(stage, 0o700, dir_fd=root_fd, follow_symlinks=False)
		for name, value in (
			("evidence.json", evidence),
			("editorial_projection.json", projection),
			("manifest.json", manifest),
		):
			daily_blog.private_artifacts.write_regular_bytes_at(
				stage_fd,
				name,
				daily_blog.io_utils.stable_json_text(value).encode("utf-8"),
			)
		if set(os.listdir(stage_fd)) != set(FIXTURE_FILE_NAMES):
			raise RuntimeError("Experiment fixture staging contents are incomplete.")
		os.fsync(stage_fd)
		_before_fixture_install(destination_name)
		try:
			daily_blog.private_artifacts.rename_directory_noreplace_at(
				root_fd,
				stage,
				destination_name,
			)
		except FileExistsError as error:
			raise RuntimeError("Experiment fixture destination already exists.") from error
		os.fsync(root_fd)
		committed = True
	finally:
		if stage_fd >= 0:
			os.close(stage_fd)
		if not committed:
			daily_blog.private_artifacts.remove_known_stage(
				root_fd,
				stage,
				FIXTURE_FILE_NAMES,
			)


#============================================
def _verify_persisted_contents(
	contents: dict[str, bytes],
	manifest: dict,
	projection_limit: int,
) -> None:
	"""Prove hashes plus full schema coherence for already-read persisted bytes."""
	persisted_manifest = json.loads(contents["manifest.json"].decode("utf-8"))
	if persisted_manifest != manifest:
		raise RuntimeError("Persisted experiment fixture manifest does not match its capture.")
	for name in ("evidence.json", "editorial_projection.json"):
		expected = manifest["files"][name]
		if expected["bytes"] != len(contents[name]):
			raise RuntimeError("Persisted experiment fixture byte count does not match manifest.")
		if expected["sha256"] != daily_blog.io_utils.sha256_bytes(contents[name]):
			raise RuntimeError("Persisted experiment fixture hash does not match manifest.")
	packet = daily_blog.schema.EvidencePacket.from_dict(json.loads(contents["evidence.json"]))
	projection = daily_blog.schema.EditorialProjection.from_dict(
		json.loads(contents["editorial_projection.json"])
	)
	_validate_artifacts(packet, projection, packet.report_date, projection_limit)


#============================================
def _verify_persisted_fixture_fd(directory_fd: int, manifest: dict, projection_limit: int) -> None:
	"""Reopen installed artifacts only through the held fixture-directory descriptor."""
	contents = {}
	for name in FIXTURE_FILE_NAMES:
		try:
			contents[name] = daily_blog.private_artifacts.read_regular_bytes_at(
				directory_fd,
				name,
				maximum_bytes=MAX_FIXTURE_ARTIFACT_BYTES,
				forbidden_mode=0o077,
			)
		except (OSError, RuntimeError) as error:
			raise RuntimeError(
				"Persisted experiment fixture contains an unsafe artifact."
			) from error
	_verify_persisted_contents(contents, manifest, projection_limit)


#============================================
def _verify_persisted_fixture(path: str, manifest: dict, projection_limit: int) -> None:
	"""Test-only convenience wrapper for validating an already-resolved fixture path."""
	fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
	try:
		_verify_persisted_fixture_fd(fd, manifest, projection_limit)
	finally:
		os.close(fd)


#============================================
def _root_path_matches(path: str, expected: os.stat_result) -> bool:
	"""Return whether the displayed root path still names the held root directory."""
	flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
	try:
		fd = os.open(path, flags)
	except OSError:
		return False
	try:
		current = os.fstat(fd)
		return current.st_dev == expected.st_dev and current.st_ino == expected.st_ino
	finally:
		os.close(fd)


#============================================
def capture_fixture(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
	fixture_root: str,
	*,
	validate_only: bool = False,
	repository_roster_snapshot: str | None = None,
) -> dict:
	"""Capture one complete offline packet and projection without publication side effects."""
	_validate_report_date(report_date)
	configured_root = _configured_fixture_root(config, fixture_root)
	root_fd, root_stat = _open_fixture_root(configured_root)
	try:
		return _capture_fixture_with_root(
			config,
			report_date,
			configured_root,
			root_fd,
			root_stat,
			validate_only,
			repository_roster_snapshot,
		)
	finally:
		os.close(root_fd)


#============================================
def _capture_fixture_with_root(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
	root_path: str,
	root_fd: int,
	root_stat: os.stat_result,
	validate_only: bool,
	repository_roster_snapshot: str | None,
) -> dict:
	"""Prepare and optionally install one fixture below a pinned private root.

	Args:
		config: Evidence, projection, repository, and output ownership settings.
		report_date: Approved quiet or busy fixture date.
		root_path: Configured display path for the held root descriptor.
		root_fd: Held descriptor for the private fixture root.
		root_stat: Original root identity used for final display-path verification.
		validate_only: Whether to stop after complete in-memory validation.
		repository_roster_snapshot: Required immutable owner-roster artifact.

	Returns:
		Manifest and either an empty path or the installed immutable fixture path.
	"""
	prepared = _prepare_fixture(config, report_date, repository_roster_snapshot)
	if validate_only:
		return {"manifest": prepared.manifest, "path": ""}
	path = _install_prepared_fixture(root_path, root_fd, root_stat, prepared)
	return {"manifest": prepared.manifest, "path": path}


#============================================
def _prepare_fixture(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
	repository_roster_snapshot: str | None,
) -> PreparedFixture:
	"""Build and validate one content-addressed fixture entirely in memory.

	Args:
		config: Offline evidence, projection, and repository settings.
		report_date: Approved report date bound into every artifact.
		repository_roster_snapshot: Required immutable owner-roster artifact.

	Returns:
		Complete fixture data, manifest identity, and projection verification limit.
	"""
	roster, roster_identity = _resolve_repository_roster(
		config, repository_roster_snapshot
	)
	mirrors, packet = _collect_offline_evidence(config, report_date, roster)
	projection = daily_blog.projection.build_projection(packet, config.projection_limits)
	projection_limit = min(
		config.projection_limits["context_chars"],
		MAX_PROJECTION_CONTEXT_CHARS,
	)
	context = _validate_artifacts(
		packet,
		projection,
		report_date,
		projection_limit,
	)
	evidence = packet.to_dict()
	projection_value = projection.to_dict()
	files = {
		"evidence.json": daily_blog.io_utils.stable_json_text(evidence).encode("utf-8"),
		"editorial_projection.json": daily_blog.io_utils.stable_json_text(projection_value).encode(
			"utf-8"
		),
	}
	manifest_identity = {
		"config_identity": _safe_config_identity(config),
		"evidence_count": len(packet.items),
		"evidence_packet_id": packet.packet_id,
		"files": {
			name: {"bytes": len(contents), "sha256": daily_blog.io_utils.sha256_bytes(contents)}
			for name, contents in files.items()
		},
		"mirrors": _mirror_manifest(mirrors),
		"projection_rendered_chars": len(context),
		"projection_id": projection.projection_id,
		"report_date": report_date,
		"repository_count": len(projection.repositories),
		"repository_roster_snapshot": roster_identity,
		"schema_version": FIXTURE_SCHEMA_VERSION,
		"source_repository": os.path.basename(os.path.abspath(config.daily_blog_repository)),
	}
	fixture_id = daily_blog.io_utils.hash_value(manifest_identity)
	manifest = {**manifest_identity, "fixture_id": fixture_id}
	destination_name = f"{report_date}--{fixture_id}"
	return PreparedFixture(
		evidence,
		projection_value,
		manifest,
		destination_name,
		projection_limit,
	)


#============================================
def _install_prepared_fixture(
	root_path: str,
	root_fd: int,
	root_stat: os.stat_result,
	prepared: PreparedFixture,
) -> str:
	"""Atomically install, reopen, and verify one prepared fixture transaction.

	Args:
		root_path: Configured display path for the held root descriptor.
		root_fd: Held descriptor for the private fixture root.
		root_stat: Original root identity used after installation.
		prepared: Complete content-addressed fixture data.

	Returns:
		Absolute path to the verified immutable fixture directory.

	Raises:
		RuntimeError: Installation, persisted verification, or root identity fails.
	"""
	_write_fixture(
		root_fd,
		prepared.destination_name,
		prepared.evidence,
		prepared.projection,
		prepared.manifest,
	)
	child_fd = daily_blog.private_artifacts.open_directory_at(
		root_fd,
		prepared.destination_name,
	)
	try:
		_verify_persisted_fixture_fd(
			child_fd,
			prepared.manifest,
			prepared.projection_limit,
		)
	finally:
		os.close(child_fd)
	if not _root_path_matches(root_path, root_stat):
		daily_blog.private_artifacts.remove_known_stage(
			root_fd,
			prepared.destination_name,
			FIXTURE_FILE_NAMES,
		)
		raise RuntimeError("Experiment fixture root changed during capture.")
	# ASVS 2.3.3 and 15.4.2: return only after the committed inode and display root agree.
	path = os.path.join(root_path, prepared.destination_name)
	return path


#============================================
def parse_args() -> argparse.Namespace:
	"""Parse the explicit offline capture request."""
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--date", dest="report_date", required=True)
	parser.add_argument("--fixture-root", required=True)
	parser.add_argument("--settings", dest="settings_path", default="settings.yaml")
	parser.add_argument(
		"--repository-roster-snapshot",
		required=True,
		help="Verified immutable owner-roster snapshot used for offline evidence collection.",
	)
	parser.add_argument(
		"--validate-only",
		action="store_true",
		help="Collect and validate offline artifacts without writing a fixture directory.",
	)
	return parser.parse_args()


#============================================
def main() -> int:
	"""Run one explicit non-publishing capture and print only its safe result path."""
	try:
		args = parse_args()
		config = daily_blog.config.load_config(args.settings_path)
		result = capture_fixture(
			config,
			args.report_date,
			args.fixture_root,
			validate_only=args.validate_only,
			repository_roster_snapshot=args.repository_roster_snapshot,
		)
	except (OSError, RuntimeError, ValueError):
		print("Experiment fixture capture failed; no fixture was written.", file=sys.stderr)
		return 2
	if args.validate_only:
		print("Daily-blog experiment fixture validated without writing artifacts.")
	else:
		print(f"Daily-blog experiment fixture: {result['path']}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

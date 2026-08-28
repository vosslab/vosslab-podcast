"""Immutable authoritative repository-roster snapshot tests."""

# Standard Library
import os
import json
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.schema
import daily_blog.repository_contracts
import daily_blog.roster_snapshots
import daily_blog.private_artifacts


#============================================
def example_roster() -> daily_blog.repository_contracts.RepositoryRoster:
	"""Return a complete roster containing active and quiet repositories."""
	records = [
		daily_blog.repository_contracts.RepositoryRecord.from_dict({
			"repository": "vosslab/cancer-clicker",
			"repository_url": "https://github.com/vosslab/cancer-clicker",
			"clone_url": "https://github.com/vosslab/cancer-clicker.git",
			"created_at": "2026-08-27T02:10:27Z",
			"is_fork": False,
		}),
		daily_blog.repository_contracts.RepositoryRecord.from_dict({
			"repository": "vosslab/quiet-tool",
			"repository_url": "https://github.com/vosslab/quiet-tool",
			"clone_url": "https://github.com/vosslab/quiet-tool.git",
			"created_at": "2025-01-02T03:04:05Z",
			"is_fork": False,
		}),
	]
	return daily_blog.repository_contracts.RepositoryRoster.create("vosslab", records)


#============================================
def test_snapshot_round_trip_is_immutable_and_idempotent(tmp_path: pathlib.Path) -> None:
	"""One roster identity owns one verified snapshot directory forever."""
	output_root = str(tmp_path / "out")
	roster = example_roster()
	first_capture = "2026-08-28T06:00:00Z"
	path, identity = daily_blog.roster_snapshots.write_repository_roster_snapshot(
		output_root,
		"vosslab",
		roster,
		captured_utc=first_capture,
	)
	reused_path, reused_identity = (
		daily_blog.roster_snapshots.write_repository_roster_snapshot(
			output_root,
			"vosslab",
			roster,
			captured_utc="2026-08-28T07:00:00Z",
		)
	)
	loaded, loaded_identity = daily_blog.roster_snapshots.load_repository_roster_snapshot(
		output_root, "vosslab", path
	)

	assert loaded == roster
	assert path == reused_path
	assert identity == reused_identity == loaded_identity
	assert identity["captured_utc"] == first_capture


#============================================
def test_snapshot_rejects_tampered_roster_bytes(tmp_path: pathlib.Path) -> None:
	"""A changed roster file cannot retain its immutable snapshot identity."""
	output_root = str(tmp_path / "out")
	path, _identity = daily_blog.roster_snapshots.write_repository_roster_snapshot(
		output_root,
		"vosslab",
		example_roster(),
		captured_utc="2026-08-28T06:00:00Z",
	)
	roster_path = pathlib.Path(path) / daily_blog.roster_snapshots.ROSTER_FILE_NAME
	value = json.loads(roster_path.read_text(encoding="utf-8"))
	value["repositories"][0]["is_fork"] = True
	roster_path.write_text(json.dumps(value), encoding="utf-8")

	with pytest.raises(RuntimeError, match="file integrity"):
		daily_blog.roster_snapshots.load_repository_roster_snapshot(
			output_root, "vosslab", path
		)


#============================================
def test_snapshot_rejects_symbolic_directory(tmp_path: pathlib.Path) -> None:
	"""A snapshot path cannot redirect reads outside its configured physical root."""
	output_root = tmp_path / "out"
	root = output_root / "vosslab" / daily_blog.roster_snapshots.ROSTER_SNAPSHOT_ROOT_NAME
	root.mkdir(parents=True)
	outside = tmp_path / "outside"
	outside.mkdir()
	link = root / ("a" * 64)
	link.symlink_to(outside, target_is_directory=True)

	os.chmod(root, 0o700)
	with pytest.raises(RuntimeError):
		daily_blog.roster_snapshots.load_repository_roster_snapshot(
			str(output_root), "vosslab", str(link)
		)


#============================================
def test_snapshot_load_holds_directory_after_path_replacement(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A replacement after directory validation cannot redirect artifact reads."""
	output_root = str(tmp_path / "out")
	roster = example_roster()
	path, _identity = daily_blog.roster_snapshots.write_repository_roster_snapshot(
		output_root,
		"vosslab",
		roster,
		captured_utc="2026-08-28T06:00:00Z",
	)
	parked = tmp_path / "parked_snapshot"

	def replace_path(_snapshot_fd: int) -> None:
		os.rename(path, parked)
		os.mkdir(path, 0o700)

	monkeypatch.setattr(
		daily_blog.roster_snapshots,
		"_after_snapshot_directory_opened",
		replace_path,
	)
	loaded, identity = daily_blog.roster_snapshots.load_repository_roster_snapshot(
		output_root, "vosslab", path
	)

	assert loaded == roster
	assert identity["roster_id"] == roster.roster_id


#============================================
def test_private_artifact_read_rejects_growth_during_descriptor_pinned_read(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A read limit remains effective when a held file grows after initial validation."""
	directory = tmp_path / "private"
	directory.mkdir(mode=0o700)
	artifact = directory / "artifact.json"
	artifact.write_bytes(b"{}")
	os.chmod(artifact, 0o600)
	original_read = os.read
	grew = False

	def read_then_grow(fd: int, count: int) -> bytes:
		nonlocal grew
		chunk = original_read(fd, count)
		if chunk and not grew:
			grew = True
			with artifact.open("ab") as handle:
				handle.write(b"x")
		return chunk

	monkeypatch.setattr(os, "read", read_then_grow)
	directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
	try:
		with pytest.raises(RuntimeError, match="changed during"):
			daily_blog.private_artifacts.read_regular_bytes_at(
				directory_fd,
				"artifact.json",
				maximum_bytes=100,
				forbidden_mode=0o077,
			)
	finally:
		os.close(directory_fd)


#============================================
def test_private_artifact_rejects_parent_traversal(tmp_path: pathlib.Path) -> None:
	"""Descriptor-relative helpers accept only one direct child component."""
	directory = tmp_path / "private"
	directory.mkdir(mode=0o700)
	directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
	try:
		with pytest.raises(RuntimeError, match="direct child"):
			daily_blog.private_artifacts.open_directory_at(directory_fd, "../outside")
	finally:
		os.close(directory_fd)

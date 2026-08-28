"""Private artifact transaction behavior."""

# Standard Library
import os
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.private_artifacts


#============================================
def open_root(path: pathlib.Path) -> int:
	"""Open a controlled test root through the production helper."""
	path.mkdir()
	return daily_blog.private_artifacts.open_physical_directory(str(path), create=False, intermediate_mode=0o700, leaf_mode=0o700)


#============================================
def test_rename_directory_noreplace_reveals_completed_stage(tmp_path: pathlib.Path) -> None:
	"""A completed private stage becomes visible only at its final name."""
	root = tmp_path / "root"
	root_fd = open_root(root)
	try:
		(root / ".stage").mkdir()
		(root / ".stage" / "artifact.txt").write_text("ready", encoding="utf-8")
		daily_blog.private_artifacts.rename_directory_noreplace_at(root_fd, ".stage", "final")
		assert (root / "final" / "artifact.txt").read_text(encoding="utf-8") == "ready"
	finally:
		os.close(root_fd)


#============================================
def test_rename_directory_noreplace_preserves_existing_destination(tmp_path: pathlib.Path) -> None:
	"""A competing completed artifact is never replaced."""
	root = tmp_path / "root"
	root_fd = open_root(root)
	try:
		(root / ".stage").mkdir()
		(root / "final").mkdir()
		(root / "final" / "existing.txt").write_text("preserve", encoding="utf-8")
		with pytest.raises(FileExistsError):
			daily_blog.private_artifacts.rename_directory_noreplace_at(root_fd, ".stage", "final")
		assert (root / "final" / "existing.txt").read_text(encoding="utf-8") == "preserve"
	finally:
		os.close(root_fd)

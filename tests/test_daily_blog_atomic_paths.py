"""Atomic replacement tests for date-owned producer publication directories."""

# Standard Library
import pathlib
import platform

# PIP3 modules
import pytest

# local repo modules
import daily_blog.atomic_paths


#============================================
def _write_directory(path: pathlib.Path, text: str) -> None:
	"""Create one small physical directory with identifiable content."""
	path.mkdir()
	(path / "value.txt").write_text(text, encoding="utf-8")


#============================================
def test_exchange_directories_keeps_both_names_visible(tmp_path: pathlib.Path) -> None:
	"""A kernel exchange leaves each live directory name continuously resolvable."""
	stable = tmp_path / "publication"
	staged = tmp_path / ".run.staging"
	_write_directory(stable, "old")
	_write_directory(staged, "new")

	daily_blog.atomic_paths.exchange_directories(str(stable), str(staged))

	assert stable.is_dir() and (stable / "value.txt").read_text(encoding="utf-8") == "new"
	assert staged.is_dir() and (staged / "value.txt").read_text(encoding="utf-8") == "old"


#============================================
def test_exchange_failure_preserves_existing_directory_names(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A rejected atomic operation leaves the old stable publication untouched."""
	stable = tmp_path / "publication"
	staged = tmp_path / ".run.staging"
	_write_directory(stable, "old")
	_write_directory(staged, "new")

	def fail_exchange(parent_fd: int, first: bytes, second: bytes) -> None:
		"""Represent one kernel rejection before a directory entry changes."""
		raise RuntimeError("synthetic atomic exchange failure")

	if platform.system() == "Linux":
		monkeypatch.setattr(daily_blog.atomic_paths, "_exchange_linux", fail_exchange)
	elif platform.system() == "Darwin":
		monkeypatch.setattr(daily_blog.atomic_paths, "_exchange_darwin", fail_exchange)
	else:
		pytest.skip("The producer supports atomic exchange only on Linux and macOS.")
	with pytest.raises(RuntimeError, match="synthetic atomic exchange failure"):
		daily_blog.atomic_paths.exchange_directories(str(stable), str(staged))

	assert stable.is_dir() and (stable / "value.txt").read_text(encoding="utf-8") == "old"
	assert staged.is_dir() and (staged / "value.txt").read_text(encoding="utf-8") == "new"

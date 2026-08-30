"""Durable repository cache refresh and lock tests."""

# Standard Library
import pathlib
import subprocess

# PIP3 modules
import pytest

# local repo modules
import daily_blog.locks
import daily_blog.config
import daily_blog.editorial_stage_config
import daily_blog.orchestrator
import daily_blog.mirrors
import daily_blog.schema
import daily_blog.repository_contracts


#============================================
def repository_record() -> daily_blog.repository_contracts.RepositoryRecord:
	"""Return one valid owner-qualified mirror identity."""
	return daily_blog.repository_contracts.RepositoryRecord.from_dict({
		"repository": "vosslab/sample",
		"repository_url": "https://github.com/vosslab/sample",
		"clone_url": "https://github.com/vosslab/sample.git",
		"created_at": "2020-01-01T00:00:00Z",
		"is_fork": False,
	})


#============================================
def test_per_cache_lock_rejects_overlapping_refresh_owner(tmp_path: pathlib.Path) -> None:
	"""Manual and scheduled refreshes cannot concurrently own one cache."""
	cache_root = tmp_path / "mirrors"
	repository = cache_root / "vosslab" / "sample"
	repository.mkdir(parents=True)
	record = repository_record()
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [record])
	manager = daily_blog.mirrors.MirrorManager(str(cache_root), roster)
	lock_path = cache_root / ".locks" / "vosslab" / "sample.lock"

	with daily_blog.locks.FileLock(str(lock_path)):
		with pytest.raises(RuntimeError, match="already held"):
			manager._refresh_one(str(repository), record, refresh=False)


#============================================
def test_mirror_rejects_symlinked_owner_path(tmp_path: pathlib.Path) -> None:
	"""A roster path cannot follow an owner-directory symlink outside its cache root."""
	cache_root = tmp_path / "mirrors"
	cache_root.mkdir()
	outside = tmp_path / "outside"
	outside.mkdir()
	(cache_root / "vosslab").symlink_to(outside, target_is_directory=True)
	record = repository_record()
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [record])
	manager = daily_blog.mirrors.MirrorManager(str(cache_root), roster)

	with pytest.raises(RuntimeError, match="must not contain symlinks"):
		manager._cache_path(record)


#============================================
def test_mirror_rejects_symlinked_cache_root(tmp_path: pathlib.Path) -> None:
	"""The configured cache root itself must be a physical directory."""
	target = tmp_path / "target"
	target.mkdir()
	cache_root = tmp_path / "mirrors"
	cache_root.symlink_to(target, target_is_directory=True)
	record = repository_record()
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [record])

	with pytest.raises(RuntimeError, match="cache root must not be a symlink"):
		daily_blog.mirrors.MirrorManager(str(cache_root), roster)


#============================================
def test_mirror_rejects_origin_url_that_is_not_exact_roster_clone_url(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: pathlib.Path,
) -> None:
	"""A same-repository URL variant cannot substitute for the roster clone origin."""
	cache_root = tmp_path / "mirrors"
	repository = cache_root / "vosslab" / "sample"
	repository.mkdir(parents=True)
	record = repository_record()
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [record])
	manager = daily_blog.mirrors.MirrorManager(str(cache_root), roster)

	def remote_url(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
		return subprocess.CompletedProcess([], 0, "https://github.com/vosslab/sample\n", "")

	monkeypatch.setattr(daily_blog.mirrors, "_run_git", remote_url)

	with pytest.raises(RuntimeError, match="does not exactly match"):
		manager._refresh_one(str(repository), record, refresh=False)


#============================================
def test_per_date_lock_rejects_overlapping_publication_owner(tmp_path: pathlib.Path) -> None:
	"""Manual and scheduled commands cannot concurrently own one report date."""
	config = daily_blog.config.DailyBlogConfig(
		settings_path="settings.yaml",
		output_root=str(tmp_path / "out"),
		output_owner="vosslab",
		report_timezone="America/Chicago",
		daily_blog_repository=str(tmp_path / "publisher"),
		mirror_cache_root=str(tmp_path / "mirrors"),
		identity_names=("Author",),
		identity_emails=(),
		author_routes=(
			daily_blog.editorial_stage_config.RoleRoute("one", ("fake",)),
			daily_blog.editorial_stage_config.RoleRoute("two", ("fake",)),
		),
		referee_route=daily_blog.editorial_stage_config.RoleRoute("judge", ("fake",)),
		collection_limits={},
		projection_limits={},
		prompt_limits={},
	)
	lock_path = tmp_path / "out" / "vosslab" / "daily_blog_locks" / "2026-08-23.lock"

	with daily_blog.locks.FileLock(str(lock_path)):
		with pytest.raises(RuntimeError, match="already held"):
			daily_blog.orchestrator.run_daily_publication(config, "2026-08-23")

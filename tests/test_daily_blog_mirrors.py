"""Durable repository cache refresh and lock tests."""

# Standard Library
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.locks
import daily_blog.config
import daily_blog.orchestrator


#============================================
def test_per_cache_lock_rejects_overlapping_refresh_owner(tmp_path: pathlib.Path) -> None:
	"""Manual and scheduled refreshes cannot concurrently own one cache."""
	cache_root = tmp_path / "mirrors"
	repository = cache_root / "sample"
	repository.mkdir(parents=True)
	manager = daily_blog.mirrors.MirrorManager(str(cache_root), ())
	lock_path = cache_root / ".locks" / "sample.lock"

	with daily_blog.locks.FileLock(str(lock_path)):
		with pytest.raises(RuntimeError, match="already held"):
			manager._refresh_one(str(repository), refresh=False)


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
		repository_urls=(),
		identity_names=("Author",),
		identity_emails=(),
		author_routes=(
			daily_blog.config.RoleRoute("one", ("fake",)),
			daily_blog.config.RoleRoute("two", ("fake",)),
		),
		referee_route=daily_blog.config.RoleRoute("judge", ("fake",)),
		collection_limits={},
		projection_limits={},
		prompt_limits={},
	)
	lock_path = tmp_path / "out" / "vosslab" / "daily_blog_locks" / "2026-08-23.lock"

	with daily_blog.locks.FileLock(str(lock_path)):
		with pytest.raises(RuntimeError, match="already held"):
			daily_blog.orchestrator.run_daily_publication(config, "2026-08-23")

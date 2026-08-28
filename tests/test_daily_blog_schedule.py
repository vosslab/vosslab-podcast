"""Explicit publication entry-boundary tests."""

# Standard Library
import argparse
import types

# PIP3 modules
import pytest

# local repo modules
import automation.publish_daily_blog


#============================================
def test_explicit_date_stops_before_generation_when_publication_exists(
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
) -> None:
	"""A coherent immutable date receipt prevents model work and reports the installed bundle."""
	bundle_id = "a" * 64
	config = types.SimpleNamespace(daily_blog_repository="/publisher")
	args = argparse.Namespace(report_date="2026-08-26", settings_path="settings.yaml")

	def fail_generation(_config: object, _report_date: str) -> tuple[str, dict]:
		raise AssertionError("Generation must not run for an already-published immutable date.")

	monkeypatch.setattr(automation.publish_daily_blog, "parse_args", lambda: args)
	monkeypatch.setattr(automation.publish_daily_blog.daily_blog.config, "load_config", lambda _path: config)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.schedule,
		"published_bundle_id",
		lambda _config, _date: bundle_id,
	)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator,
		"run_daily_publication",
		fail_generation,
	)

	automation.publish_daily_blog.main()

	output = capsys.readouterr().out
	assert f"/publisher/data/publication_bundles/{bundle_id}" in output
	assert f"Bundle ID: {bundle_id}" in output
	assert "Publication status: already published" in output

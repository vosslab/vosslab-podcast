"""Durable public configuration boundaries for daily-blog observability."""

# Standard Library
from pathlib import Path

# PIP3 modules
import pytest
import yaml

# local repo modules
import daily_blog.config


#============================================
def write_settings(
	tmp_path: Path, logging: dict[str, object] | None = None, owner: str = "vosslab",
) -> Path:
	"""Write the smallest production-shaped settings document."""
	daily_blog: dict[str, object] = {}
	if logging is not None:
		daily_blog["logging"] = logging
	path = tmp_path / "settings.yaml"
	path.write_text(yaml.safe_dump({
		"github": {"username": owner, "identity_login": "vosslab"},
		"daily_blog": daily_blog,
	}, sort_keys=False), encoding="utf-8")
	return path


#============================================
def test_logging_policy_accepts_explicit_positive_limits(tmp_path: Path) -> None:
	"""Operator-selected bounded observability limits are accepted by the loader."""
	daily_blog.config.load_config(str(write_settings(tmp_path, {
		"detailed_retention_days": 14,
		"max_events_per_run": 200,
	})))


#============================================
@pytest.mark.parametrize("logging", (
	{"detailed_retention_days": True},
	{"max_events_per_run": 0},
	{"unknown": 1},
))
def test_logging_policy_fails_closed_for_invalid_settings(
	tmp_path: Path, logging: dict[str, object],
) -> None:
	"""Unsafe, nonpositive, and misspelled logging controls cannot silently apply."""
	with pytest.raises(RuntimeError):
		daily_blog.config.load_config(str(write_settings(tmp_path, logging)))


#============================================
@pytest.mark.parametrize("owner", ("../outside", "owner/name", "owner name"))
def test_output_owner_rejects_path_or_selector_syntax(tmp_path: Path, owner: str) -> None:
	"""The configured owner is safe as a durable output-path component."""
	with pytest.raises(RuntimeError):
		daily_blog.config.load_config(str(write_settings(tmp_path, owner=owner)))

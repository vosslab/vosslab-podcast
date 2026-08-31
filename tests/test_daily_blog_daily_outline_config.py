"""Settings contracts for replicated Stage 5 ranking and daily outlines."""

# Standard Library
import pathlib

# PIP3 modules
import pytest
import yaml

# local repo modules
import daily_blog.config
import daily_blog.editorial_stage_config


#============================================
def write_settings(tmp_path: pathlib.Path, daily_outline: dict[str, object]) -> pathlib.Path:
	"""Write the smallest production settings document with Stage 5 policy."""
	settings_path = tmp_path / "settings.yaml"
	settings_path.write_text(yaml.safe_dump({
		"github": {"username": "vosslab", "identity_login": "vosslab"},
		"daily_blog": {"daily_outline": daily_outline},
	}, sort_keys=False), encoding="utf-8")
	return settings_path


#============================================
@pytest.mark.parametrize(
	("daily_outline", "match"),
	(
		({"unexpected": 1}, "Unknown daily_blog.daily_outline keys"),
		({"routes": {"unexpected": {}}}, "Unknown daily_blog.daily_outline.routes keys"),
		({"prompt_limits": {"unexpected_chars": 1}}, "Unknown daily_blog.daily_outline.prompt_limits keys"),
		({"prompt_limits": {"ranking_chars": True}}, "prompt_limits.ranking_chars"),
	),
)
def test_daily_outline_settings_reject_unknown_or_unsafe_values(
	tmp_path: pathlib.Path, daily_outline: dict[str, object], match: str,
) -> None:
	"""Strict YAML keeps typos and unsafe prompt values outside the route policy."""
	with pytest.raises(RuntimeError, match=match):
		daily_blog.config.load_config(str(write_settings(tmp_path, daily_outline)))

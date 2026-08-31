"""Configuration contracts for the independent repository-story stage."""

# Standard Library
import pathlib

# PIP3 modules
import pytest
import yaml

# local repo modules
import daily_blog.config


#============================================
def write_settings(tmp_path: pathlib.Path, repository_story: dict[str, object]) -> pathlib.Path:
	"""Write the smallest settings document accepted by the producer loader."""
	settings_path = tmp_path / "settings.yaml"
	settings_path.write_text(
		yaml.safe_dump({
			"github": {"username": "vosslab", "identity_login": "vosslab"},
			"daily_blog": {"repository_story": repository_story},
		}, sort_keys=False),
		encoding="utf-8",
	)
	return settings_path


#============================================
@pytest.mark.parametrize(
	("repository_story", "match"),
	(
		({"unexpected": 1}, "Unknown daily_blog.repository_story keys"),
		({"routes": {"unexpected": {}}}, "Unknown daily_blog.repository_story.routes keys"),
		({"prompt_limits": {"unexpected_chars": 1}}, "Unknown daily_blog.repository_story.prompt_limits keys"),
		({"prompt_limits": {"writer_chars": True}}, "prompt_limits.writer_chars"),
	),
)
def test_repository_story_settings_reject_unknown_or_unsafe_values(
	tmp_path: pathlib.Path,
	repository_story: dict[str, object],
	match: str,
) -> None:
	"""Strict YAML rejects typoed route and prompt policy before execution."""
	with pytest.raises(RuntimeError, match=match):
		daily_blog.config.load_config(str(write_settings(tmp_path, repository_story)))

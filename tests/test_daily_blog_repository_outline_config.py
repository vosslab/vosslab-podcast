"""Configuration contracts for the independent repository-outline stage."""

# Standard Library
import pathlib

# PIP3 modules
import pytest
import yaml

# local repo modules
import daily_blog.config


#============================================
def write_settings(tmp_path: pathlib.Path, repository_outline: dict[str, object]) -> pathlib.Path:
	"""Write the smallest settings document accepted by the producer loader."""
	settings_path = tmp_path / "settings.yaml"
	settings_path.write_text(
		yaml.safe_dump({
			"github": {"username": "vosslab", "identity_login": "vosslab"},
			"daily_blog": {"repository_outline": repository_outline},
		}, sort_keys=False),
		encoding="utf-8",
	)
	return settings_path


#============================================
@pytest.mark.parametrize(
	("repository_outline", "match"),
	(
		({"unexpected": 1}, "Unknown daily_blog.repository_outline keys"),
		({"routes": {"unexpected": {}}}, "Unknown daily_blog.repository_outline.routes keys"),
		({"prompt_limits": {"unexpected_chars": 1}}, "Unknown daily_blog.repository_outline.prompt_limits keys"),
		({"prompt_limits": {"generator_chars": True}}, "prompt_limits.generator_chars"),
	),
)
def test_repository_outline_settings_reject_unknown_or_unsafe_values(
	tmp_path: pathlib.Path,
	repository_outline: dict[str, object],
	match: str,
) -> None:
	"""Stage-local YAML is strict so typoed route and size policy never silently expands."""
	with pytest.raises(RuntimeError, match=match):
		daily_blog.config.load_config(str(write_settings(tmp_path, repository_outline)))

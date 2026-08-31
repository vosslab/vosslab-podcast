"""Durable configuration boundaries for Stage 7 final synthesis."""

# Standard Library
from pathlib import Path

# PIP3 modules
import pytest
import yaml

# local repo modules
import daily_blog.config
import daily_blog.editorial_stage_config


#============================================
def write_settings(tmp_path: Path, final_synthesis: dict[str, object]) -> Path:
	"""Write the smallest production-shaped settings document."""
	path = tmp_path / "settings.yaml"
	path.write_text(yaml.safe_dump({
		"github": {"username": "vosslab", "identity_login": "vosslab"},
		"daily_blog": {"final_synthesis": final_synthesis},
	}, sort_keys=False), encoding="utf-8")
	return path


#============================================
def test_final_synthesis_loader_consumes_an_isolated_route_override(tmp_path: Path) -> None:
	"""A Stage 7 route override is accepted as its own stage-local policy."""
	command = list(daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE)
	loaded = daily_blog.config.load_config(str(write_settings(tmp_path, {
		"routes": {"reviewer": {"name": "independent-review", "command": command}},
	})))

	assert loaded.final_synthesis.reviewer_route.name == "independent-review"


#============================================
@pytest.mark.parametrize("final_synthesis", (
	{"unexpected": 1},
	{"routes": {"reviewer": {"name": "", "command": []}}},
))
def test_final_synthesis_loader_fails_closed_for_unknown_or_malformed_settings(
	tmp_path: Path, final_synthesis: dict[str, object],
) -> None:
	"""Typos and unusable routes cannot silently become editorial policy."""
	with pytest.raises(RuntimeError):
		daily_blog.config.load_config(str(write_settings(tmp_path, final_synthesis)))

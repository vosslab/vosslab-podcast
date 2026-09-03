"""Stable configuration boundaries for Stage 6 complete-post editors."""

# Standard Library
import pathlib

# PIP3 modules
import pytest
import yaml

# local repo modules
import daily_blog.config
import daily_blog.editorial_stage_config


#============================================
def write_settings(tmp_path: pathlib.Path, daily_blog: dict[str, object]) -> pathlib.Path:
	"""Write the smallest settings document accepted by the production loader."""
	settings_path = tmp_path / "settings.yaml"
	settings_path.write_text(
		yaml.safe_dump({
			"github": {"username": "vosslab", "identity_login": "vosslab"},
			"daily_blog": daily_blog,
		}, sort_keys=False),
		encoding="utf-8",
	)
	return settings_path


#============================================
@pytest.mark.parametrize(
	("complete_post", "match"),
	(
		({"unexpected": 1}, "Unknown daily_blog.complete_post keys"),
		({
			"routes": {
				"writer": {"name": "same", "command": list(daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE)},
				"editor": {"name": "same", "command": list(daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE)},
			},
		}, "distinct by role"),
	),
)
def test_stage6_settings_reject_unsafe_configuration(
	tmp_path: pathlib.Path, complete_post: dict[str, object], match: str,
) -> None:
	"""The strict loader rejects unknown keys and overlapping role identities."""
	with pytest.raises(RuntimeError, match=match):
		daily_blog.config.load_config(str(write_settings(tmp_path, {"complete_post": complete_post})))

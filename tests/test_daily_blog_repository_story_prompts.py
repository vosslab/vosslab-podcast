"""Offline behavior tests for Stage 4 prompt rendering."""

import pytest

import daily_blog.repository_story_prompts


def test_repository_story_renderer_keeps_its_bounded_input_contract() -> None:
	with pytest.raises(RuntimeError, match="outline context"):
		daily_blog.repository_story_prompts.render_repository_story_writer("", '{"evidence":true}', "writer-1")

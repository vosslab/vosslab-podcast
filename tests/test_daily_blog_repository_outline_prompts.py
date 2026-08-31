"""Offline behavior tests for Stage 3 prompt rendering."""

import pytest

import daily_blog.repository_outline_prompts


def test_repository_outline_renderer_keeps_its_bounded_input_contract() -> None:
	with pytest.raises(RuntimeError, match="evidence context"):
		daily_blog.repository_outline_prompts.render_repository_outline_generator("", "generator-1")

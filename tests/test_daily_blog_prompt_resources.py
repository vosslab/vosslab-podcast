"""Neutral daily-blog prompt-resource ownership tests."""

# PIP3 modules
import pytest

# local repo modules
import daily_blog.prompt_resources


#============================================
def test_instruction_prompt_loader_requires_consumer_allowlisting() -> None:
	"""Shared loading preserves bare-name, allowlist, and positive-instruction checks."""
	allowed_names = frozenset({"daily_blog_shadow_evaluator_v1.txt"})
	text = daily_blog.prompt_resources.load_allowlisted_instruction_prompt(
		"daily_blog_shadow_evaluator_v1.txt",
		allowed_names,
		"test consumer",
	)
	assert text
	with pytest.raises(RuntimeError, match="allowlisted"):
		daily_blog.prompt_resources.load_allowlisted_instruction_prompt(
			"daily_blog_shadow_evaluator_repair_v1.txt",
			allowed_names,
			"test consumer",
		)
	with pytest.raises(RuntimeError, match="allowlisted|bare trusted filename"):
		daily_blog.prompt_resources.load_allowlisted_instruction_prompt(
			"../../source_me.sh",
			allowed_names,
			"test consumer",
		)

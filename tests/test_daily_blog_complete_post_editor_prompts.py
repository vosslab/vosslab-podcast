"""Offline behavior tests for the registry-owned Stage 6 editor prompt."""

# local repo modules
import daily_blog.complete_post_editor_prompts
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.loader


#============================================
def _editor_prompt_set() -> daily_blog.prompt_registry.loader.LoadedPromptSet:
	"""Load the canonical Stage 6 prompt through the central registry."""
	return daily_blog.prompt_registry.loader.load_prompt_set(
		daily_blog.prompt_registry.definitions.COMPLETE_POST_EDITOR_PROMPT_SET,
	)


#============================================
def test_complete_post_editor_prompt_uses_issued_canonical_set() -> None:
	"""Rendering preserves supplied typed values through the registered resource."""
	rendered = daily_blog.complete_post_editor_prompts.render_complete_post_editor_prompt(
		'{"daily_outline":{}}', '{"candidates":[]}', "editor-1", _editor_prompt_set(),
	)
	assert '{"daily_outline":{}}' in rendered
	assert '{"candidates":[]}' in rendered


#============================================

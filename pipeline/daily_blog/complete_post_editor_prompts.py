"""Bounded renderer for the registry-owned Stage 6 whole-post editor prompt."""

# Standard Library
import re

# local repo modules
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.loader


MAX_TYPED_CONTEXT_CHARS = 60000
MAX_CANDIDATE_POSTS_CHARS = 160000
MAX_RENDERED_PROMPT_CHARS = 225000
_REPLICA_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")


#============================================
def _loaded_prompt_set(
	value: daily_blog.prompt_registry.loader.LoadedPromptSet,
) -> daily_blog.prompt_registry.loader.LoadedPromptSet:
	"""Require the issued loaded view for the canonical Stage 6 declaration."""
	return daily_blog.prompt_registry.loader.resolve_loaded_prompt_set(
		value, daily_blog.prompt_registry.definitions.COMPLETE_POST_EDITOR_PROMPT_SET,
	)


#============================================
def complete_post_editor_prompt_identity(
	prompt_set: daily_blog.prompt_registry.loader.LoadedPromptSet,
) -> dict[str, object]:
	"""Return the current Stage 6 cache identity from the registry-owned asset."""
	return _loaded_prompt_set(prompt_set).identity_dict()


#============================================
def _bounded_text(value: object, label: str, maximum: int) -> str:
	"""Require one exact context component within its owned budget."""
	if type(value) is not str or not value or len(value) > maximum:
		raise RuntimeError(f"Complete-post editor {label} is invalid or exceeds its limit.")
	return value


#============================================
def _replica_id(value: object) -> str:
	"""Require an assignment identity without editorial ordering meaning."""
	if type(value) is not str or _REPLICA_ID_RE.fullmatch(value) is None:
		raise RuntimeError("Complete-post editor replica identity is invalid.")
	return value


#============================================
def render_complete_post_editor_prompt(
	typed_context_json: str,
	candidate_posts_json: str,
	replica_id: str,
	prompt_set: daily_blog.prompt_registry.loader.LoadedPromptSet,
) -> str:
	"""Render one bounded anonymous whole-CompletePost editing assignment."""
	loaded = _loaded_prompt_set(prompt_set)
	context = _bounded_text(typed_context_json, "typed context", MAX_TYPED_CONTEXT_CHARS)
	candidates = _bounded_text(candidate_posts_json, "candidate posts", MAX_CANDIDATE_POSTS_CHARS)
	assignment = _replica_id(replica_id)
	rendered = loaded.render(daily_blog.prompt_registry.definitions.COMPLETE_POST_EDITOR_RESOURCE, {
		"typed_context_json": context,
		"candidate_posts_json": candidates,
		"replica_id": assignment,
	})
	if len(rendered) > MAX_RENDERED_PROMPT_CHARS:
		raise RuntimeError("Complete-post editor rendered prompt exceeds its configured limit.")
	return rendered

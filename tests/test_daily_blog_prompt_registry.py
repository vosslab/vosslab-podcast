"""Behavioral integrity checks for the central daily-blog prompt registry."""

# Standard Library
import dataclasses

# PIP3 modules
import pytest

# local repo modules
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.loader


#============================================
def test_prompt_set_resolution_rejects_equal_valued_forgery() -> None:
	"""A caller cannot substitute an equal declaration for the canonical object."""
	forged = dataclasses.replace(daily_blog.prompt_registry.definitions.REPOSITORY_OUTLINE_PROMPT_SET)
	with pytest.raises(RuntimeError, match="trusted registry"):
		daily_blog.prompt_registry.loader.resolve_prompt_set(forged)


#============================================
def test_unissued_loaded_prompt_view_is_rejected() -> None:
	"""Only the loader can issue a usable prompt view."""
	forged = object.__new__(daily_blog.prompt_registry.loader.LoadedPromptSet)
	with pytest.raises(RuntimeError, match="issued"):
		daily_blog.prompt_registry.loader.resolve_loaded_prompt_set(
			forged, daily_blog.prompt_registry.definitions.REPOSITORY_OUTLINE_PROMPT_SET,
		)


#============================================
def test_wrong_stage_issued_prompt_view_is_rejected() -> None:
	"""A valid view cannot cross an editorial-stage boundary."""
	loaded = daily_blog.prompt_registry.loader.load_prompt_set(
		daily_blog.prompt_registry.definitions.REPOSITORY_OUTLINE_PROMPT_SET,
	)
	with pytest.raises(RuntimeError, match="does not match"):
		daily_blog.prompt_registry.loader.resolve_loaded_prompt_set(
			loaded, daily_blog.prompt_registry.definitions.REPOSITORY_STORY_PROMPT_SET,
		)


#============================================
def test_resource_from_another_issued_set_is_rejected() -> None:
	"""A stage can access only resources in its own trusted set."""
	loaded = daily_blog.prompt_registry.loader.load_prompt_set(
		daily_blog.prompt_registry.definitions.REPOSITORY_OUTLINE_PROMPT_SET,
	)
	with pytest.raises(RuntimeError, match="does not belong"):
		loaded.resource(daily_blog.prompt_registry.definitions.REPOSITORY_STORY_WRITER_RESOURCE)

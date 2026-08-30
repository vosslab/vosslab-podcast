"""Offline behavior tests for the Stage 6 whole-post editor prompt."""

# Standard Library
import dataclasses

# PIP3 modules
import pytest

# local repo modules
import daily_blog.complete_post_editor_prompts


#============================================
def _contract() -> daily_blog.complete_post_editor_prompts.CompletePostEditorPromptContract:
	"""Load the real pinned asset for each focused assertion."""
	contract = daily_blog.complete_post_editor_prompts.load_complete_post_editor_prompt_contract()
	return contract


#============================================
def test_complete_post_editor_prompt_rejects_forged_asset() -> None:
	"""A changed asset cannot masquerade as this pinned version."""
	contract = _contract()
	tampered = dataclasses.replace(contract, template=contract.template + "\nExtra.")
	with pytest.raises(RuntimeError, match="text and bytes conflict"):
		daily_blog.complete_post_editor_prompts.complete_post_editor_prompt_identity(tampered)


#============================================

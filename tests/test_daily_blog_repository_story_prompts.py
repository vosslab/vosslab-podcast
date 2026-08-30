"""Offline contracts for the owned Stage 4 repository-story prompt assets."""

# Standard Library
import dataclasses

# PIP3 modules
import pytest

# local repo modules
import daily_blog.repository_story_prompts


#============================================
def _contract() -> daily_blog.repository_story_prompts.RepositoryStoryPromptContract:
	"""Load one real Stage 4 prompt contract for each focused assertion."""
	return daily_blog.repository_story_prompts.load_repository_story_prompt_contract()


#============================================
def test_repository_story_prompt_loader_rejects_tampered_pinned_asset(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A changed v1 resource requires a new name, version, and pinned digest."""
	loader = (
		daily_blog.repository_story_prompts.daily_blog.prompt_resources
		.load_allowlisted_instruction_prompt_with_bytes
	)

	def tampered_loader(name: str, names: frozenset[str], role: str) -> tuple[str, bytes]:
		"""Simulate a controlled on-disk byte change after trusted path resolution."""
		text, contents = loader(name, names, role)
		if name == "daily_blog_repository_story_writer_v1.txt":
			return text, contents + b" "
		return text, contents

	monkeypatch.setattr(
		daily_blog.repository_story_prompts.daily_blog.prompt_resources,
		"load_allowlisted_instruction_prompt_with_bytes", tampered_loader,
	)
	with pytest.raises(RuntimeError, match="do not match the pinned asset"):
		daily_blog.repository_story_prompts.load_repository_story_prompt_contract()


#============================================
def test_repository_story_prompt_contract_rejects_tampered_text_or_identity() -> None:
	"""Renderers reject a forged template body or a stale content identity."""
	contract = _contract()
	templates = dict(contract.templates)
	templates["daily_blog_repository_story_writer_v1.txt"] += "\nExtra text."
	tampered_text = dataclasses.replace(contract, templates=tuple(sorted(templates.items())))
	with pytest.raises(RuntimeError, match="text and bytes conflict"):
		daily_blog.repository_story_prompts.repository_story_prompt_identity(tampered_text)
	tampered_identity = dataclasses.replace(contract, integrity_sha256="0" * 64)
	with pytest.raises(RuntimeError, match="integrity"):
		daily_blog.repository_story_prompts.repository_story_prompt_identity(tampered_identity)

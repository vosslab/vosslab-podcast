import os
import sys

import file_utils as git_file_utils


REPO_ROOT = git_file_utils.get_repo_root()
PIPELINE_DIR = os.path.join(REPO_ROOT, "pipeline")
if PIPELINE_DIR not in sys.path:
	sys.path.insert(0, PIPELINE_DIR)

from podlib import prompt_loader


def test_load_prompt_missing_file_raises() -> None:
	"""
	load_prompt should raise FileNotFoundError for missing prompt files.
	"""
	raised = False
	try:
		prompt_loader.load_prompt("nonexistent_prompt_file.txt")
	except FileNotFoundError:
		raised = True
	assert raised


#============================================
def test_render_prompt_replaces_tokens() -> None:
	"""
	render_prompt should replace {{token}} placeholders with values.
	"""
	template = "Hello {{name}}, you have {{count}} items."
	result = prompt_loader.render_prompt(template, {
		"name": "Alice",
		"count": "42",
	})
	assert result == "Hello Alice, you have 42 items."


#============================================
def test_render_prompt_preserves_unreplaced_tokens() -> None:
	"""
	render_prompt should leave unknown tokens intact.
	"""
	template = "Value: {{known}} and {{unknown}}"
	result = prompt_loader.render_prompt(template, {"known": "yes"})
	assert result == "Value: yes and {{unknown}}"

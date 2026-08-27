# Standard Library
import os
import re
import subprocess


_PROMPT_CACHE = {}
_REPO_ROOT = ""
NON_POSITIVE_INSTRUCTION_PATTERNS = (
	(
		"direct negation",
		re.compile(
			r"\b(?:do\s+not|don't|must\s+not|not|cannot|can't|never|avoid|without|"
			r"refrain\s+from|prohibit(?:ed)?|forbid(?:den)?)\b",
			flags=re.IGNORECASE,
		),
	),
	(
		"negative constraint",
		re.compile(r"(?:^|[.!?]\s+|\(\s*|-\s+)no\s+[a-z]", flags=re.IGNORECASE | re.MULTILINE),
	),
	(
		"deferred ownership",
		re.compile(
			r"\bleave\s+.{1,80}\s+to\s+(?:the\s+)?(?:manager|operator|maintainer|owner)\b",
			flags=re.IGNORECASE,
		),
	),
)


#============================================
def validate_positive_instructions(text: str, prompt_name: str) -> str:
	"""Require direct desired outcomes in one model-facing instruction template."""
	for label, pattern in NON_POSITIVE_INSTRUCTION_PATTERNS:
		match = pattern.search(text)
		if match is not None:
			excerpt = " ".join(match.group(0).split())
			raise RuntimeError(
				f"Prompt {prompt_name} uses {label} language ({excerpt}). "
				+ "State the desired outcome directly."
			)
	return text


#============================================
def _run_git(args: list[str]) -> str:
	"""
	Run git and return stdout.
	"""
	result = subprocess.run(
		["git"] + args,
		capture_output=True,
		text=True,
		check=False,
	)
	if result.returncode != 0:
		err_text = result.stderr.strip() or "unknown git error"
		raise RuntimeError(f"git {' '.join(args)} failed: {err_text}")
	return result.stdout.strip()


#============================================
def _get_repo_root() -> str:
	"""
	Resolve the repository root path with git.
	"""
	global _REPO_ROOT
	if _REPO_ROOT:
		return _REPO_ROOT
	root = _run_git(["rev-parse", "--show-toplevel"])
	if not root:
		raise RuntimeError("git rev-parse --show-toplevel returned empty output")
	_REPO_ROOT = root
	return root


#============================================
def load_prompt(prompt_name: str) -> str:
	"""
	Load a prompt template from pipeline/prompts/.
	"""
	if not prompt_name:
		raise ValueError("prompt_name is required")
	# prompts live under pipeline/prompts/ in this repo
	prompt_root = os.path.join(_get_repo_root(), "pipeline", "prompts")
	path = os.path.join(prompt_root, prompt_name)
	if path in _PROMPT_CACHE:
		return _PROMPT_CACHE[path]
	if not os.path.exists(path):
		raise FileNotFoundError(f"Prompt file not found: {path}")
	with open(path, "r", encoding="utf-8") as handle:
		text = handle.read()
	text = validate_positive_instructions(text, prompt_name)
	_PROMPT_CACHE[path] = text
	return text


#============================================
def render_prompt(template: str, values: dict[str, str]) -> str:
	"""
	Replace {{token}} placeholders with supplied values.
	"""
	if not template:
		return ""
	rendered = template
	for key, value in values.items():
		token = "{{" + key + "}}"
		replacement = value if value is not None else ""
		rendered = rendered.replace(token, replacement)
	return rendered


#============================================
def render_prompt_with_target(
	template: str,
	values: dict[str, str],
	target_value: str,
	unit: str,
	document_name: str,
) -> str:
	"""
	Render a prompt template and append a closing target reminder.

	Adds 'Target {target_value} {unit} for this {document_name}.' at the end
	so the LLM sees the length constraint both near the top and as the final line.

	Args:
		template: raw prompt template with {{token}} placeholders.
		values: token substitution dict passed to render_prompt.
		target_value: the numeric target as a string (e.g. '750').
		unit: 'words' or 'characters'.
		document_name: short label like 'blog post' or 'repo outline'.

	Returns:
		Fully rendered prompt string with closing target line.
	"""
	rendered = render_prompt(template, values)
	# append closing target reminder
	closing = f"\nTarget {target_value} {unit} for this {document_name}."
	rendered = rendered.rstrip() + closing
	return rendered

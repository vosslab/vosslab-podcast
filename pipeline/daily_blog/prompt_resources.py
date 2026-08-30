"""Trusted versioned prompt-resource loading for daily blog consumers."""

# Standard Library
import os
import pathlib

# local repo modules
import podlib.prompt_loader


#============================================
def prompt_resource_path(name: str) -> str:
	"""Return the trusted prompt path for one bare resource filename."""
	if not isinstance(name, str):
		raise RuntimeError("Prompt resource name must be a bare trusted filename.")
	pure = pathlib.PurePosixPath(name)
	if pure.is_absolute() or len(pure.parts) != 1 or pure.name != name:
		raise RuntimeError("Prompt resource name must be a bare trusted filename.")
	package_dir = os.path.dirname(os.path.abspath(__file__))
	path = os.path.join(os.path.dirname(package_dir), "prompts", name)
	return path


#============================================
def load_allowlisted_instruction_prompt(
	name: str,
	names: frozenset[str],
	role: str,
) -> str:
	"""Read and validate one affirmative prompt from a consumer-owned allowlist."""
	if name not in names:
		raise RuntimeError(f"Prompt template name is not allowlisted for {role}.")
	path = prompt_resource_path(name)
	with open(path, "r", encoding="utf-8") as handle:
		text = handle.read().strip()
	if not text:
		raise RuntimeError(f"Prompt template is empty: {name}")
	text = podlib.prompt_loader.validate_positive_instructions(text, name)
	return text


#============================================
def load_allowlisted_instruction_prompt_with_bytes(
	name: str,
	names: frozenset[str],
	role: str,
) -> tuple[str, bytes]:
	"""Read one trusted prompt while retaining exact bytes for its identity."""
	if name not in names:
		raise RuntimeError(f"Prompt template name is not allowlisted for {role}.")
	path = prompt_resource_path(name)
	with open(path, "rb") as handle:
		contents = handle.read()
	try:
		text = contents.decode("utf-8").strip()
	except UnicodeDecodeError as error:
		raise RuntimeError(f"Prompt template is not UTF-8: {name}") from error
	if not text:
		raise RuntimeError(f"Prompt template is empty: {name}")
	text = podlib.prompt_loader.validate_positive_instructions(text, name)
	return text, contents

"""Runtime-only credentials for pipeline network clients."""

# Standard Library
import os
import pathlib


GITHUB_TOKEN_NAME = "GITHUB_TOKEN"


#============================================
def _validate_credential(name: str, value: str) -> str:
	"""Return one header-safe credential value or fail without exposing it."""
	token = value.strip()
	if not token or not token.isascii() or any(character.isspace() for character in token):
		raise RuntimeError(f"{name} must be one non-empty ASCII value.")
	return token


#============================================
def _dotenv_value(value_text: str, name: str) -> str:
	"""Parse the small dotenv value surface used by GitHub access tokens."""
	value = value_text.strip()
	if value.startswith(("'", '"')):
		quote = value[0]
		closing_index = value.find(quote, 1)
		if closing_index < 0:
			raise RuntimeError(f"{name} has an invalid quoted value.")
		tail = value[closing_index + 1:].strip()
		if tail and not tail.startswith("#"):
			raise RuntimeError(f"{name} has content after its quoted value.")
		value = value[1:closing_index]
	else:
		comment_index = value.find(" #")
		if comment_index >= 0:
			value = value[:comment_index]
	return _validate_credential(name, value)


#============================================
def hermes_environment_path() -> pathlib.Path:
	"""Return the active Hermes profile's dotenv path."""
	hermes_home = os.environ.get("HERMES_HOME", "").strip()
	if hermes_home:
		root = pathlib.Path(hermes_home).expanduser()
	else:
		root = pathlib.Path.home() / ".hermes"
	return root / ".env"


#============================================
def _read_dotenv_credential(path: pathlib.Path, name: str) -> str:
	"""Read exactly one named credential without exporting neighboring values."""
	if not path.is_file():
		raise RuntimeError(f"Runtime credential file is missing: {path}")
	matched_value = None
	with path.open("r", encoding="utf-8") as handle:
		for line in handle:
			text = line.strip()
			if not text or text.startswith("#") or "=" not in text:
				continue
			if text.startswith("export "):
				text = text[7:].lstrip()
			key, value_text = text.split("=", 1)
			if key.strip() != name:
				continue
			if matched_value is not None:
				raise RuntimeError(f"Runtime credential file defines {name} more than once.")
			matched_value = _dotenv_value(value_text, name)
	if matched_value is None:
		raise RuntimeError(f"Runtime credential file does not define {name}: {path}")
	return matched_value


#============================================
def get_github_token() -> str:
	"""Resolve GitHub authentication without placing the token in process environment."""
	environment_value = os.environ.get(GITHUB_TOKEN_NAME, "")
	if environment_value.strip():
		return _validate_credential(GITHUB_TOKEN_NAME, environment_value)
	path = hermes_environment_path()
	return _read_dotenv_credential(path, GITHUB_TOKEN_NAME)

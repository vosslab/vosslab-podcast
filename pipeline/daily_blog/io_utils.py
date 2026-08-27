"""Stable hashing and atomic file helpers for daily publication artifacts."""

# Standard Library
import os
import json
import uuid
import hashlib
import subprocess


#============================================
def repository_root(start_path: str) -> str:
	"""Resolve the owning repository through Git from one source path."""
	start = os.path.abspath(start_path)
	if os.path.isfile(start):
		start = os.path.dirname(start)
	result = subprocess.run(
		["git", "-C", start, "rev-parse", "--show-toplevel"],
		check=False,
		text=True,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		timeout=60,
	)
	if result.returncode:
		message = result.stderr.strip() or result.stdout.strip()
		raise RuntimeError(f"Repository root is unavailable from {start}: {message}")
	root = result.stdout.strip()
	if not os.path.isabs(root):
		raise RuntimeError("Git repository root must be absolute.")
	return root


#============================================
def canonical_json_bytes(value: object) -> bytes:
	"""Return deterministic UTF-8 JSON bytes for one schema value."""
	text = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
	contents = text.encode("utf-8")
	return contents


#============================================
def sha256_bytes(contents: bytes) -> str:
	"""Return one lowercase SHA-256 digest."""
	digest = hashlib.sha256(contents).hexdigest()
	return digest


#============================================
def sha256_text(text: str) -> str:
	"""Return the SHA-256 digest of UTF-8 text."""
	digest = sha256_bytes(text.encode("utf-8"))
	return digest


#============================================
def hash_value(value: object) -> str:
	"""Hash one JSON-compatible value canonically."""
	digest = sha256_bytes(canonical_json_bytes(value))
	return digest


#============================================
def stable_json_text(value: object) -> str:
	"""Render inspectable stable JSON with one final newline."""
	text = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
	return text


#============================================
def atomic_write_bytes(path: str, contents: bytes) -> None:
	"""Atomically replace one regular file on its destination filesystem."""
	parent = os.path.dirname(os.path.abspath(path))
	os.makedirs(parent, exist_ok=True)
	temporary = os.path.join(parent, f".{os.path.basename(path)}.{uuid.uuid4().hex}.tmp")
	with open(temporary, "wb") as handle:
		handle.write(contents)
	os.replace(temporary, path)


#============================================
def atomic_write_text(path: str, text: str) -> None:
	"""Atomically replace one UTF-8 text file."""
	atomic_write_bytes(path, text.encode("utf-8"))


#============================================
def atomic_write_json(path: str, value: object) -> None:
	"""Atomically replace one stable JSON file."""
	text = stable_json_text(value)
	atomic_write_text(path, text)


#============================================
def read_json(path: str) -> object:
	"""Read one UTF-8 JSON document."""
	with open(path, "r", encoding="utf-8") as handle:
		value = json.load(handle)
	return value

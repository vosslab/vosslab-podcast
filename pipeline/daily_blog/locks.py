"""Process locks and hash-addressed artifact cache for daily publication runs."""

# Standard Library
import os
import fcntl

# local repo modules
import daily_blog.io_utils


PHASE_CACHE_SCHEMA_VERSION = "vosslab.daily-blog.phase-cache.v1"


class FileLock:
	"""One non-blocking advisory lock retained for a context lifetime."""

	#============================================
	def __init__(self, path: str) -> None:
		"""Remember the lock path before acquisition."""
		self.path = os.path.abspath(path)
		self.handle = None

	#============================================
	def __enter__(self) -> "FileLock":
		"""Acquire exclusive ownership or fail with the exact lock path."""
		os.makedirs(os.path.dirname(self.path), exist_ok=True)
		self.handle = open(self.path, "a+", encoding="utf-8")
		try:
			fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
		except BlockingIOError as error:
			self.handle.close()
			self.handle = None
			raise RuntimeError(f"Daily publication lock is already held: {self.path}") from error
		self.handle.seek(0)
		self.handle.truncate()
		self.handle.write(f"pid={os.getpid()}\n")
		self.handle.flush()
		return self

	#============================================
	def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
		"""Release lock ownership and close its descriptor."""
		if self.handle is None:
			return
		fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
		self.handle.close()
		self.handle = None


class PhaseCache:
	"""Hash-addressed JSON and asset cache shared by immutable reruns."""

	#============================================
	def __init__(self, root: str) -> None:
		"""Set the cache root."""
		self.root = os.path.abspath(root)

	#============================================
	def phase_dir(self, phase: str, input_hash: str) -> str:
		"""Return one confined phase cache directory."""
		if not phase.replace("_", "").isalnum():
			raise RuntimeError("Invalid phase cache name.")
		if len(input_hash) != 64 or not input_hash.isalnum():
			raise RuntimeError("Invalid phase cache identity.")
		path = os.path.join(self.root, phase, input_hash)
		return path

	#============================================
	def load_json(self, phase: str, input_hash: str, name: str) -> dict | list | None:
		"""Load and hash-verify one complete cached JSON artifact."""
		path = os.path.join(self.phase_dir(phase, input_hash), name)
		if not os.path.isfile(path):
			return None
		envelope = daily_blog.io_utils.read_json(path)
		if not isinstance(envelope, dict):
			raise RuntimeError("Cached phase envelope must be an object.")
		if envelope.get("schema_version") != PHASE_CACHE_SCHEMA_VERSION:
			raise RuntimeError("Cached phase schema is unsupported.")
		if envelope.get("input_hash") != input_hash:
			raise RuntimeError("Cached phase input identity does not match its path.")
		value = envelope.get("value")
		if not isinstance(value, (dict, list)):
			raise RuntimeError("Cached phase artifact must be a mapping or list.")
		if envelope.get("output_hash") != daily_blog.io_utils.hash_value(value):
			raise RuntimeError("Cached phase output identity does not match its content.")
		return value

	#============================================
	def store_json(self, phase: str, input_hash: str, name: str, value: object) -> str:
		"""Store one hash-verified JSON artifact atomically."""
		if not isinstance(value, (dict, list)):
			raise RuntimeError("Cached phase artifact must be a mapping or list.")
		path = os.path.join(self.phase_dir(phase, input_hash), name)
		envelope = {
			"schema_version": PHASE_CACHE_SCHEMA_VERSION,
			"input_hash": input_hash,
			"output_hash": daily_blog.io_utils.hash_value(value),
			"value": value,
		}
		daily_blog.io_utils.atomic_write_json(path, envelope)
		return path

	#============================================
	def asset_dir(self, phase: str, input_hash: str) -> str:
		"""Return the cache asset directory for one phase identity."""
		path = os.path.join(self.phase_dir(phase, input_hash), "assets")
		return path

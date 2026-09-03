"""Descriptor-owned storage for one date-keyed publication bundle."""

# Standard Library
import contextlib
import collections.abc
import ctypes
import datetime
import errno
import json
import os
import platform
import re
import stat
import uuid


MAX_JSON_BYTES = 128 * 1024
MAX_EVIDENCE_BYTES = 128 * 1024 * 1024
MAX_POST_BYTES = 2 * 1024 * 1024
MAX_ASSET_BYTES = 8 * 1024 * 1024
_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
_FILE_READ_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
_SAFE_OWNER_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")
_SAFE_RUN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")


#============================================
def _direct_name(value: object, label: str) -> str:
	"""Require an opaque direct child name before descriptor selection."""
	if type(value) is not str or value in {"", ".", ".."} or os.path.basename(value) != value:
		raise RuntimeError(f"Publication {label} is invalid.")
	return value


#============================================
def _selectors(output_root: object, owner: object, report_date: object, run_id: object) -> tuple[str, str, str, str]:
	"""Validate stable publication selectors before opening the hierarchy."""
	if type(output_root) is not str or not output_root:
		raise RuntimeError("Publication output root is invalid.")
	if type(owner) is not str or _SAFE_OWNER_RE.fullmatch(owner) is None:
		raise RuntimeError("Publication owner is invalid.")
	if type(report_date) is not str:
		raise RuntimeError("Publication report date is invalid.")
	try:
		if datetime.date.fromisoformat(report_date).isoformat() != report_date:
			raise ValueError
	except ValueError as error:
		raise RuntimeError("Publication report date is invalid.") from error
	if type(run_id) is not str or _SAFE_RUN_RE.fullmatch(run_id) is None:
		raise RuntimeError("Publication run identifier is invalid.")
	return os.path.abspath(output_root), owner, report_date, run_id


#============================================
@contextlib.contextmanager
def _directory(
	parent_fd: int | None, name: str, create: bool,
) -> collections.abc.Generator[int, None, None]:
	"""Hold one direct no-follow directory, creating only that direct child."""
	if create:
		try:
			if parent_fd is None:
				raise RuntimeError("Publication output root must already exist.")
			os.mkdir(name, 0o700, dir_fd=parent_fd)
		except FileExistsError:
			pass
	kwargs = {} if parent_fd is None else {"dir_fd": parent_fd}
	try:
		fd = os.open(name, _DIRECTORY_FLAGS, **kwargs)
	except OSError as error:
		raise RuntimeError("Publication storage directory is unavailable.") from error
	try:
		if not stat.S_ISDIR(os.fstat(fd).st_mode):
			raise RuntimeError("Publication storage directory is invalid.")
		yield fd
	finally:
		os.close(fd)


#============================================
@contextlib.contextmanager
def _date_directory(
	output_root: str, owner: str, report_date: str, create: bool,
) -> collections.abc.Generator[int, None, None]:
	"""Hold root/owner/daily_blog/report_date without following any component."""
	with _directory(None, output_root, False) as root_fd:
		with _directory(root_fd, owner, create) as owner_fd:
			with _directory(owner_fd, "daily_blog", create) as blog_fd:
				with _directory(blog_fd, report_date, create) as date_fd:
					yield date_fd


#============================================
def _read_regular_at(directory_fd: int, name: str, maximum_bytes: int) -> bytes:
	"""Read one bounded, non-symlink regular direct child."""
	_direct_name(name, "file name")
	try:
		fd = os.open(name, _FILE_READ_FLAGS, dir_fd=directory_fd)
	except OSError as error:
		raise RuntimeError("Publication artifact is unavailable.") from error
	try:
		metadata = os.fstat(fd)
		if not stat.S_ISREG(metadata.st_mode):
			raise RuntimeError("Publication artifact is not a regular file.")
		if metadata.st_size > maximum_bytes:
			raise RuntimeError("Publication artifact exceeds its schema envelope.")
		contents = os.read(fd, maximum_bytes + 1)
		if len(contents) > maximum_bytes or len(contents) != metadata.st_size:
			raise RuntimeError("Publication artifact changed while it was read.")
		return contents
	finally:
		os.close(fd)


#============================================
def _read_json_at(directory_fd: int, name: str) -> object:
	"""Read one bounded JSON artifact through the held bundle descriptor."""
	try:
		maximum = MAX_EVIDENCE_BYTES if name == "evidence.json" else MAX_JSON_BYTES
		return json.loads(_read_regular_at(directory_fd, name, maximum).decode("utf-8"))
	except (UnicodeDecodeError, json.JSONDecodeError) as error:
		raise RuntimeError("Publication JSON artifact is invalid.") from error


#============================================
def _write_regular_at(directory_fd: int, name: str, contents: bytes, maximum_bytes: int) -> None:
	"""Durably create one known regular direct child through a held descriptor."""
	_direct_name(name, "file name")
	if type(contents) is not bytes or len(contents) > maximum_bytes:
		raise RuntimeError("Publication artifact exceeds its schema envelope.")
	temporary = f".{name}.{uuid.uuid4().hex}.tmp"
	try:
		flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
		fd = os.open(temporary, flags, 0o600, dir_fd=directory_fd)
		try:
			if not stat.S_ISREG(os.fstat(fd).st_mode):
				raise RuntimeError("Publication temporary artifact is invalid.")
			view = memoryview(contents)
			while view:
				written = os.write(fd, view)
				if written <= 0:
					raise RuntimeError("Publication artifact write failed.")
				view = view[written:]
			os.fsync(fd)
		finally:
			os.close(fd)
		os.replace(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
		os.fsync(directory_fd)
	except BaseException:
		try:
			os.unlink(temporary, dir_fd=directory_fd)
		except FileNotFoundError:
			pass
		raise


#============================================
def _exchange_at(directory_fd: int, first: str, second: str) -> None:
	"""Atomically exchange two direct children of the held date directory."""
	if platform.system() == "Linux":
		try:
			function = ctypes.CDLL(None, use_errno=True).renameat2
		except AttributeError as error:
			raise RuntimeError("Atomic bundle replacement requires Linux renameat2.") from error
		function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
		function.restype = ctypes.c_int
		if function(directory_fd, os.fsencode(first), directory_fd, os.fsencode(second), 0x2) == 0:
			return
	elif platform.system() == "Darwin":
		try:
			function = ctypes.CDLL(None, use_errno=True).renameatx_np
		except AttributeError as error:
			raise RuntimeError("Atomic bundle replacement requires Darwin renameatx_np.") from error
		function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
		function.restype = ctypes.c_int
		if function(directory_fd, os.fsencode(first), directory_fd, os.fsencode(second), 0x2) == 0:
			return
	else:
		raise RuntimeError("Atomic bundle replacement requires Linux or macOS kernel support.")
	if ctypes.get_errno() == errno.EXDEV:
		raise RuntimeError("Atomic bundle replacement requires one filesystem.")
	raise RuntimeError("Atomic bundle replacement was rejected by the operating system.")


#============================================
def _remove_tree_at(parent_fd: int, name: str) -> None:
	"""Remove one known staging direct child, never traversing a path string."""
	_direct_name(name, "staging name")
	with _directory(parent_fd, name, False) as directory_fd:
		for child in os.listdir(directory_fd):
			_direct_name(child, "staging child")
			info = os.stat(child, dir_fd=directory_fd, follow_symlinks=False)
			if stat.S_ISDIR(info.st_mode):
				_remove_tree_at(directory_fd, child)
			else:
				os.unlink(child, dir_fd=directory_fd)
	os.rmdir(name, dir_fd=parent_fd)


class PublicationStorage:
	"""Persist and reopen a fully sealed bundle using one held descriptor tree."""

	#============================================
	def __init__(self, output_root: str, owner: str, report_date: str, run_id: str) -> None:
		self.output_root, self.owner, self.report_date, self.run_id = _selectors(
			output_root, owner, report_date, run_id,
		)

	#============================================
	def write(self, artifacts: dict[str, bytes]) -> str:
		"""Stage fixed artifacts and assets then atomically name `publication`."""
		required = {
			"bundle.json", "evidence.json", "repository_roster.json", "daily_active_roster.json",
			"editorial_projection.json",
			"publication_surface.json", "post.md",
		}
		if not required <= set(artifacts):
			raise RuntimeError("Publication bundle artifacts are incomplete.")
		if any(not (name in required or name.startswith("assets/")) for name in artifacts):
			raise RuntimeError("Publication bundle artifact name is invalid.")
		stage = f".{self.run_id}.staging-{uuid.uuid4().hex}"
		with _date_directory(self.output_root, self.owner, self.report_date, True) as date_fd:
			with _directory(date_fd, stage, True) as stage_fd:
				with _directory(stage_fd, "assets", True) as assets_fd:
					for name, contents in artifacts.items():
						if name.startswith("assets/"):
							leaf = name.removeprefix("assets/")
							_direct_name(leaf, "asset name")
							_write_regular_at(assets_fd, leaf, contents, MAX_ASSET_BYTES)
						else:
							maximum = (
								MAX_POST_BYTES if name == "post.md"
								else MAX_EVIDENCE_BYTES if name == "evidence.json"
								else MAX_JSON_BYTES
							)
							_write_regular_at(stage_fd, name, contents, maximum)
				os.fsync(stage_fd)
			try:
				publication_info = os.stat("publication", dir_fd=date_fd, follow_symlinks=False)
			except FileNotFoundError:
				os.replace(stage, "publication", src_dir_fd=date_fd, dst_dir_fd=date_fd)
			else:
				if not stat.S_ISDIR(publication_info.st_mode) or stat.S_ISLNK(publication_info.st_mode):
					raise RuntimeError("Publication bundle path must be one physical directory.")
				_exchange_at(date_fd, stage, "publication")
			os.fsync(date_fd)
			try:
				stage_info = os.stat(stage, dir_fd=date_fd, follow_symlinks=False)
			except FileNotFoundError:
				stage_info = None
			if stage_info is not None:
				if not stat.S_ISDIR(stage_info.st_mode) or stat.S_ISLNK(stage_info.st_mode):
					raise RuntimeError("Publication staging cleanup is invalid.")
				_remove_tree_at(date_fd, stage)
		return os.path.join(self.output_root, self.owner, "daily_blog", self.report_date, "publication")

	#============================================
	def read(self) -> dict[str, bytes]:
		"""Read every fixed artifact and asset through one held publication descriptor."""
		with _date_directory(self.output_root, self.owner, self.report_date, False) as date_fd:
			with _directory(date_fd, "publication", False) as publication_fd:
				result = {
					"bundle.json": _read_regular_at(publication_fd, "bundle.json", MAX_JSON_BYTES),
					"evidence.json": _read_regular_at(publication_fd, "evidence.json", MAX_EVIDENCE_BYTES),
					"repository_roster.json": _read_regular_at(publication_fd, "repository_roster.json", MAX_JSON_BYTES),
					"daily_active_roster.json": _read_regular_at(publication_fd, "daily_active_roster.json", MAX_JSON_BYTES),
					"editorial_projection.json": _read_regular_at(publication_fd, "editorial_projection.json", MAX_JSON_BYTES),
					"publication_surface.json": _read_regular_at(publication_fd, "publication_surface.json", MAX_JSON_BYTES),
					"post.md": _read_regular_at(publication_fd, "post.md", MAX_POST_BYTES),
				}
				with _directory(publication_fd, "assets", False) as assets_fd:
					for leaf in os.listdir(assets_fd):
						_direct_name(leaf, "asset name")
						result[f"assets/{leaf}"] = _read_regular_at(assets_fd, leaf, MAX_ASSET_BYTES)
				return result


#============================================
def storage_for_date_root(date_root: object) -> PublicationStorage:
	"""Resolve a date-root selector into the same descriptor-owned storage owner."""
	if type(date_root) is not str or not date_root:
		raise RuntimeError("Publication date root is invalid.")
	date_path = os.path.abspath(date_root)
	if os.path.basename(date_path) in {"", ".", ".."}:
		raise RuntimeError("Publication date root is invalid.")
	blog_path = os.path.dirname(date_path)
	owner_path = os.path.dirname(blog_path)
	if os.path.basename(blog_path) != "daily_blog":
		raise RuntimeError("Publication date root is invalid.")
	return PublicationStorage(os.path.dirname(owner_path), os.path.basename(owner_path), os.path.basename(date_path), "reuse")


#============================================
def json_artifact(contents: bytes) -> object:
	"""Decode a bounded storage result as one JSON value."""
	try:
		return json.loads(contents.decode("utf-8"))
	except (UnicodeDecodeError, json.JSONDecodeError) as error:
		raise RuntimeError("Publication JSON artifact is invalid.") from error

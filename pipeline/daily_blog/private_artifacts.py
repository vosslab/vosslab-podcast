"""Descriptor-pinned primitives for private daily-blog artifacts."""

# Standard Library
import ctypes
import errno
import os
import pathlib
import platform
import stat


DIRECTORY_OPEN_FLAGS = (
	os.O_RDONLY
	| getattr(os, "O_DIRECTORY", 0)
	| getattr(os, "O_NOFOLLOW", 0)
	| getattr(os, "O_CLOEXEC", 0)
)
FILE_OPEN_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
WRITE_OPEN_FLAGS = (
	os.O_WRONLY
	| os.O_CREAT
	| os.O_EXCL
	| getattr(os, "O_NOFOLLOW", 0)
	| getattr(os, "O_CLOEXEC", 0)
)
_RENAME_NOREPLACE = 1
_DARWIN_RENAME_EXCL = 0x00000004


#============================================
def is_controlled(status: os.stat_result, forbidden_mode: int) -> bool:
	"""Return whether an opened inode is owned locally and has no forbidden bits.

	Args:
		status: Metadata obtained from the held descriptor.
		forbidden_mode: Permission bits that a controlled artifact must not expose.

	Returns:
		Whether the inode meets the ownership and permission contract.
	"""
	value = status.st_uid == os.geteuid() and not stat.S_IMODE(status.st_mode) & forbidden_mode
	return value


#============================================
def require_directory(fd: int, forbidden_mode: int) -> None:
	"""Require a held descriptor to name a controlled physical directory.

	Args:
		fd: Open directory descriptor.
		forbidden_mode: Permission bits that the directory must not expose.

	Raises:
		RuntimeError: The descriptor is not a controlled directory.
	"""
	# ASVS 5.3.2: validate the opened inode rather than a mutable path string.
	status = os.fstat(fd)
	if not stat.S_ISDIR(status.st_mode) or not is_controlled(status, forbidden_mode):
		raise RuntimeError("Private artifact directory is unsafe.")


#============================================
def open_directory_at(parent_fd: int, name: str) -> int:
	"""Open one direct physical child directory without following symbolic links.

	Args:
		parent_fd: Held descriptor for the parent directory.
		name: One direct child directory name selected by the caller.

	Returns:
		A descriptor for the opened child directory.
	"""
	_require_direct_name(name)
	# ASVS 5.3.2: dir_fd and O_NOFOLLOW keep caller-approved names beneath the held parent.
	fd = os.open(name, DIRECTORY_OPEN_FLAGS, dir_fd=parent_fd)
	try:
		if not stat.S_ISDIR(os.fstat(fd).st_mode):
			raise RuntimeError("Private artifact child is not a directory.")
	except BaseException:
		os.close(fd)
		raise
	return fd


#============================================
def _require_direct_name(name: str) -> None:
	"""Require one non-traversing direct child name.

	Args:
		name: Candidate child name.

	Raises:
		RuntimeError: The name is not exactly one child component.
	"""
	if not name or name in (".", "..") or os.path.basename(name) != name:
		raise RuntimeError("Private artifact name is not a direct child.")


#============================================
def open_physical_directory(
	path: str,
	*,
	create: bool,
	intermediate_mode: int,
	leaf_mode: int,
) -> int:
	"""Open an absolute directory through physical components and retain its descriptor.

	Args:
		path: Absolute or relative filesystem path selected by the caller.
		create: Whether missing components may be created.
		intermediate_mode: Creation mode for non-leaf components.
		leaf_mode: Creation mode for the final component.

	Returns:
		A descriptor for the final physical directory.
	"""
	parts = pathlib.PurePath(os.path.abspath(path)).parts
	fd = os.open(os.path.sep, DIRECTORY_OPEN_FLAGS)
	try:
		for index, component in enumerate(parts[1:]):
			if create:
				mode = leaf_mode if index == len(parts) - 2 else intermediate_mode
				try:
					os.mkdir(component, mode, dir_fd=fd)
				except FileExistsError:
					pass
			next_fd = open_directory_at(fd, component)
			os.close(fd)
			fd = next_fd
	except BaseException:
		os.close(fd)
		raise
	return fd


#============================================
def read_regular_bytes_at(
	parent_fd: int,
	name: str,
	maximum_bytes: int,
	forbidden_mode: int,
) -> bytes:
	"""Read a bounded controlled regular file and reject replacement races.

	Args:
		parent_fd: Held descriptor for the parent directory.
		name: One direct child filename selected by the caller.
		maximum_bytes: Largest accepted file size in bytes.
		forbidden_mode: Permission bits the file must not expose.

	Returns:
		Complete file contents.

	Raises:
		RuntimeError: The file is unsafe, too large, or changed while being read.
	"""
	if maximum_bytes < 0:
		raise RuntimeError("Private artifact read limit is invalid.")
	_require_direct_name(name)
	fd = os.open(name, FILE_OPEN_FLAGS, dir_fd=parent_fd)
	try:
		# ASVS 2.2.1 and 5.3.2: bound and validate the descriptor before processing bytes.
		status = os.fstat(fd)
		if (
			not stat.S_ISREG(status.st_mode)
			or not is_controlled(status, forbidden_mode)
			or status.st_size > maximum_bytes
		):
			raise RuntimeError("Private artifact file is unsafe.")
		chunks = []
		remaining = maximum_bytes + 1
		while remaining:
			chunk = os.read(fd, min(remaining, 64 * 1024))
			if not chunk:
				break
			chunks.append(chunk)
			remaining -= len(chunk)
		contents = b"".join(chunks)
		final_status = os.fstat(fd)
		identity = (status.st_dev, status.st_ino, status.st_size, status.st_mtime_ns)
		final_identity = (
			final_status.st_dev,
			final_status.st_ino,
			final_status.st_size,
			final_status.st_mtime_ns,
		)
		if (
			final_identity != identity
			or len(contents) != status.st_size
			or len(contents) > maximum_bytes
		):
			raise RuntimeError("Private artifact file changed during its read.")
	finally:
		os.close(fd)
	return contents


#============================================
def write_regular_bytes_at(parent_fd: int, name: str, contents: bytes) -> None:
	"""Create and sync one private regular file below a held descriptor.

	Args:
		parent_fd: Held descriptor for the parent directory.
		name: One direct child filename selected by the caller.
		contents: Exact bytes to write once.
	"""
	_require_direct_name(name)
	# ASVS 5.3.2 and 2.3.3: exclusive creation and fsync make the staged write non-replaceable.
	fd = os.open(name, WRITE_OPEN_FLAGS, 0o600, dir_fd=parent_fd)
	try:
		written = 0
		while written < len(contents):
			chunk_bytes = os.write(fd, contents[written:])
			if chunk_bytes == 0:
				raise OSError("Private artifact write made no progress.")
			written += chunk_bytes
		os.fsync(fd)
	finally:
		os.close(fd)


#============================================
def create_private_stage_at(root_fd: int, stage_name: str, forbidden_mode: int) -> int:
	"""Create and open one empty private staging directory below a held root.

	Args:
		root_fd: Held descriptor for the private transaction root.
		stage_name: Internally generated direct-child staging directory name.
		forbidden_mode: Permission bits the new stage must not expose.

	Returns:
		An open descriptor for the new, validated staging directory. The caller owns it.

	Raises:
		FileExistsError: The generated staging name already exists.
		RuntimeError: The newly created directory fails its private ownership contract.

	The helper removes an empty stage if opening or validating it fails. A caller that
	writes artifacts into the returned directory owns later declared-file cleanup.
	"""
	_require_direct_name(stage_name)
	created = False
	fd = -1
	try:
		os.mkdir(stage_name, 0o700, dir_fd=root_fd)
		created = True
		fd = open_directory_at(root_fd, stage_name)
		require_directory(fd, forbidden_mode)
		return fd
	except BaseException:
		if fd >= 0:
			os.close(fd)
		if created:
			try:
				# ASVS 5.3.2: cleanup remains pinned below the held private root.
				os.rmdir(stage_name, dir_fd=root_fd)
			except OSError:
				pass
		raise


#============================================
def _raise_rename_error(destination: str, error_number: int) -> None:
	"""Raise a stable domain error for one failed no-replace installation."""
	if error_number in (errno.EEXIST, errno.ENOTEMPTY):
		raise FileExistsError(destination)
	raise RuntimeError("Private artifact installation requires an atomic OS commit.")


#============================================
def _rename_linux_noreplace(
	root_fd: int,
	source: bytes,
	destination: bytes,
	destination_name: str,
) -> None:
	"""Install one directory with Linux renameat2 RENAME_NOREPLACE."""
	try:
		function = ctypes.CDLL(None, use_errno=True).renameat2
	except AttributeError as error:
		raise RuntimeError("Private artifact installation requires Linux renameat2.") from error
	function.argtypes = [
		ctypes.c_int,
		ctypes.c_char_p,
		ctypes.c_int,
		ctypes.c_char_p,
		ctypes.c_uint,
	]
	function.restype = ctypes.c_int
	if function(root_fd, source, root_fd, destination, _RENAME_NOREPLACE) == 0:
		return
	_raise_rename_error(destination_name, ctypes.get_errno())


#============================================
def _rename_darwin_noreplace(
	root_fd: int,
	source: bytes,
	destination: bytes,
	destination_name: str,
) -> None:
	"""Install one directory with Darwin renameatx_np RENAME_EXCL."""
	try:
		function = ctypes.CDLL(None, use_errno=True).renameatx_np
	except AttributeError as error:
		raise RuntimeError("Private artifact installation requires Darwin renameatx_np.") from error
	function.argtypes = [
		ctypes.c_int,
		ctypes.c_char_p,
		ctypes.c_int,
		ctypes.c_char_p,
		ctypes.c_uint,
	]
	function.restype = ctypes.c_int
	if function(root_fd, source, root_fd, destination, _DARWIN_RENAME_EXCL) == 0:
		return
	_raise_rename_error(destination_name, ctypes.get_errno())


#============================================
def rename_directory_noreplace_at(root_fd: int, source: str, destination: str) -> None:
	"""Atomically reveal one completed direct-child directory without replacement.

	Args:
		root_fd: Held descriptor for the private transaction root.
		source: Internally generated direct-child staging directory.
		destination: Caller-owned direct-child identity for the completed artifact.

	Raises:
		FileExistsError: The immutable destination already exists.
		RuntimeError: The supported operating system lacks its atomic installation primitive.
	"""
	_require_direct_name(source)
	_require_direct_name(destination)
	source_bytes = os.fsencode(source)
	destination_bytes = os.fsencode(destination)
	system = platform.system()
	# ASVS 2.3.3: OS no-replace commits preserve a competing final identity.
	if system == "Linux":
		_rename_linux_noreplace(root_fd, source_bytes, destination_bytes, destination)
		return
	if system == "Darwin":
		_rename_darwin_noreplace(root_fd, source_bytes, destination_bytes, destination)
		return
	raise RuntimeError(
		"Private artifact installation requires atomic no-replace support on this operating system."
	)


#============================================
def remove_known_tree(
	root_fd: int,
	stage_name: str,
	file_names: tuple[str, ...],
	child_files: tuple[tuple[str, tuple[str, ...]], ...],
) -> None:
	"""Remove only declared files and child directories from an incomplete stage.

	Args:
		root_fd: Held descriptor for the private transaction root.
		stage_name: Generated direct-child stage directory name.
		file_names: Exact files allowed directly below the stage.
		child_files: Exact child directories and their allowed file names.
	"""
	_require_direct_name(stage_name)
	try:
		stage_fd = open_directory_at(root_fd, stage_name)
	except (OSError, RuntimeError):
		return
	try:
		for child_name, names in child_files:
			_require_direct_name(child_name)
			try:
				child_fd = open_directory_at(stage_fd, child_name)
			except (OSError, RuntimeError):
				continue
			try:
				for file_name in names:
					_require_direct_name(file_name)
					try:
						os.unlink(file_name, dir_fd=child_fd)
					except FileNotFoundError:
						pass
			finally:
				os.close(child_fd)
			os.rmdir(child_name, dir_fd=stage_fd)
		for file_name in file_names:
			_require_direct_name(file_name)
			try:
				os.unlink(file_name, dir_fd=stage_fd)
			except FileNotFoundError:
				pass
	finally:
		os.close(stage_fd)
	os.rmdir(stage_name, dir_fd=root_fd)


#============================================
def remove_known_stage(root_fd: int, stage_name: str, file_names: tuple[str, ...]) -> None:
	"""Remove a flat known incomplete direct-child stage after a failed transaction."""
	remove_known_tree(root_fd, stage_name, file_names, ())

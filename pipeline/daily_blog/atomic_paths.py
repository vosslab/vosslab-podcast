"""Kernel-owned atomic replacement operations for daily-blog directories."""

# Standard Library
import ctypes
import errno
import os
import platform


_LINUX_RENAME_EXCHANGE = 0x2
_DARWIN_RENAME_SWAP = 0x00000002
_DIRECTORY_OPEN_FLAGS = (
	os.O_RDONLY
	| getattr(os, "O_DIRECTORY", 0)
	| getattr(os, "O_NOFOLLOW", 0)
	| getattr(os, "O_CLOEXEC", 0)
)


#============================================
def _exchange_linux(parent_fd: int, first: bytes, second: bytes) -> None:
	"""Exchange names through Linux renameat2 RENAME_EXCHANGE."""
	try:
		function = ctypes.CDLL(None, use_errno=True).renameat2
	except AttributeError as error:
		raise RuntimeError("Atomic bundle replacement requires Linux renameat2.") from error
	function.argtypes = [
		ctypes.c_int,
		ctypes.c_char_p,
		ctypes.c_int,
		ctypes.c_char_p,
		ctypes.c_uint,
	]
	function.restype = ctypes.c_int
	if function(parent_fd, first, parent_fd, second, _LINUX_RENAME_EXCHANGE) == 0:
		return
	if ctypes.get_errno() == errno.EXDEV:
		raise RuntimeError("Atomic bundle replacement requires one filesystem.")
	raise RuntimeError("Atomic bundle replacement was rejected by the operating system.")


#============================================
def _exchange_darwin(parent_fd: int, first: bytes, second: bytes) -> None:
	"""Exchange names through Darwin renameatx_np RENAME_SWAP."""
	try:
		function = ctypes.CDLL(None, use_errno=True).renameatx_np
	except AttributeError as error:
		raise RuntimeError("Atomic bundle replacement requires Darwin renameatx_np.") from error
	function.argtypes = [
		ctypes.c_int,
		ctypes.c_char_p,
		ctypes.c_int,
		ctypes.c_char_p,
		ctypes.c_uint,
	]
	function.restype = ctypes.c_int
	if function(parent_fd, first, parent_fd, second, _DARWIN_RENAME_SWAP) == 0:
		return
	if ctypes.get_errno() == errno.EXDEV:
		raise RuntimeError("Atomic bundle replacement requires one filesystem.")
	raise RuntimeError("Atomic bundle replacement was rejected by the operating system.")


#============================================
def exchange_directories(first: str, second: str) -> None:
	"""Atomically exchange two physical directories without hiding either name.

	The directory names may be beneath different child paths of one common parent.
	Supported Linux and macOS kernels exchange both names in one operation; other
	platforms fail closed because a remove-then-install replacement is unsafe.
	"""
	first_path = os.path.abspath(first)
	second_path = os.path.abspath(second)
	parent = os.path.commonpath((first_path, second_path))
	if parent in (os.path.sep, first_path, second_path):
		raise RuntimeError("Atomic bundle replacement requires a controlled common parent.")
	if (
		not os.path.isdir(first_path)
		or os.path.islink(first_path)
		or not os.path.isdir(second_path)
		or os.path.islink(second_path)
	):
		raise RuntimeError("Atomic bundle replacement requires two physical directories.")
	first_name = os.path.relpath(first_path, parent)
	second_name = os.path.relpath(second_path, parent)
	parent_fd = os.open(parent, _DIRECTORY_OPEN_FLAGS)
	try:
		system = platform.system()
		if system == "Linux":
			_exchange_linux(parent_fd, os.fsencode(first_name), os.fsencode(second_name))
			return
		if system == "Darwin":
			_exchange_darwin(parent_fd, os.fsencode(first_name), os.fsencode(second_name))
			return
		raise RuntimeError("Atomic bundle replacement requires Linux or macOS kernel support.")
	finally:
		os.close(parent_fd)

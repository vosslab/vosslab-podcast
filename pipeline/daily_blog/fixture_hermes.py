"""Install a no-egress Hermes fixture executable for deterministic pipeline harnesses."""

# Standard Library
import dataclasses
import functools
import hashlib
import json
import os
import pathlib
import secrets
import stat
import sys

# local repo modules
import daily_blog.config
import daily_blog.routes


EXTERNAL_HERMES = "external_hermes"
FIXTURE_HERMES_SHIM = "fixture_hermes_shim"
FIXTURE_EXTERNAL_ROUTE_USED = False
FIXTURE_SCHEMA_VERSION = "vosslab.daily-blog.fixture-hermes.v1"
MAX_REGISTERED_RESPONSES = 64
MAX_PROMPT_BYTES = 262144
MAX_RESPONSE_BYTES = 262144
MAX_MAPPING_BYTES = 1048576
_HASH_LENGTH = 64
_INSTALL_ATTEMPTS = 8
_MAPPING_PREFIX = "responses_"


@dataclasses.dataclass(frozen=True)
class FixtureHermesInstallation:
	"""Private disposable shim installation and its inherited-process environment."""

	root: str
	executable: str
	mapping_path: str
	path: str
	environment: dict[str, str]
	executable_sha256: str
	mapping_sha256: str
	response_map_id: str
	allowed_route: tuple[str, ...]
	provenance: str = FIXTURE_HERMES_SHIM
	external_route_used: bool = FIXTURE_EXTERNAL_ROUTE_USED


	#============================================
	def create_route_runner(self) -> daily_blog.routes.CommandRouteRunner:
		"""Return a runner that revalidates this exact private shim before every child route."""
		provenance = validate_fixture_installation(self)
		validator = functools.partial(_validate_runner_provenance, self)
		runner = daily_blog.routes.CommandRouteRunner(
			path_override=self.path,
			fixture_provenance=provenance,
			fixture_validator=validator,
		)
		return runner


#============================================
def _valid_sha256(value: object) -> bool:
	"""Return whether one value is a lower-case SHA-256 hexadecimal digest."""
	if not isinstance(value, str) or len(value) != _HASH_LENGTH:
		return False
	valid = all(character in "0123456789abcdef" for character in value)
	return valid


#============================================
def _registered_responses(prompt_responses: object) -> dict[str, str]:
	"""Hash bounded prompt-response pairs into the private executable mapping."""
	if not isinstance(prompt_responses, dict) or not prompt_responses:
		raise RuntimeError("Fixture Hermes responses must be a non-empty mapping.")
	if len(prompt_responses) > MAX_REGISTERED_RESPONSES:
		raise RuntimeError("Fixture Hermes response mapping exceeds its bounded capacity.")
	registered = {}
	for prompt, response in prompt_responses.items():
		if not isinstance(prompt, str) or not isinstance(response, str):
			raise RuntimeError("Fixture Hermes prompts and responses must be text.")
		prompt_bytes = prompt.encode("utf-8")
		response_bytes = response.encode("utf-8")
		if not prompt_bytes or len(prompt_bytes) > MAX_PROMPT_BYTES:
			raise RuntimeError("Fixture Hermes prompt size is invalid.")
		if not response_bytes or len(response_bytes) > MAX_RESPONSE_BYTES:
			raise RuntimeError("Fixture Hermes response size is invalid.")
		digest = hashlib.sha256(prompt_bytes).hexdigest()
		if digest in registered:
			raise RuntimeError("Fixture Hermes prompt identity is duplicated.")
		registered[digest] = response
	return registered


#============================================
def _mapping_bytes(responses: dict[str, str]) -> bytes:
	"""Encode the exact strict JSON mapping consumed by an installed shim."""
	mapping = {
		"schema_version": FIXTURE_SCHEMA_VERSION,
		"responses": responses,
	}
	payload = json.dumps(mapping, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
	encoded = payload.encode("utf-8")
	if len(encoded) > MAX_MAPPING_BYTES:
		raise RuntimeError("Fixture Hermes response mapping exceeds its byte limit.")
	return encoded


#============================================
def _response_map_id(responses: dict[str, str]) -> str:
	"""Return a stable non-secret identity for a registered prompt-hash response map."""
	payload = json.dumps(responses, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
	identity = hashlib.sha256(payload.encode("utf-8")).hexdigest()
	return identity


#============================================
def _strict_json_object(pairs: list[tuple[object, object]]) -> dict[str, object]:
	"""Build one JSON object while rejecting duplicate or non-text member names."""
	value = {}
	for key, item in pairs:
		if not isinstance(key, str) or key in value:
			raise ValueError("Fixture Hermes JSON object is invalid.")
		value[key] = item
	return value


#============================================
def _reject_json_constant(_value: str) -> None:
	"""Reject JSON extensions such as NaN instead of accepting a loose parser dialect."""
	raise ValueError("Fixture Hermes JSON constant is invalid.")


#============================================
def _parse_mapping_bytes(payload: bytes) -> dict[str, str] | None:
	"""Strictly parse and validate one already-bounded private response-map payload."""
	try:
		value = json.loads(
			payload.decode("utf-8"),
			object_pairs_hook=_strict_json_object,
			parse_constant=_reject_json_constant,
		)
	except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
		return None
	if not isinstance(value, dict) or set(value) != {"schema_version", "responses"}:
		return None
	if value["schema_version"] != FIXTURE_SCHEMA_VERSION:
		return None
	responses = value["responses"]
	if not isinstance(responses, dict) or not responses or len(responses) > MAX_REGISTERED_RESPONSES:
		return None
	for digest, response in responses.items():
		if not _valid_sha256(digest) or not isinstance(response, str):
			return None
		if not response or len(response.encode("utf-8")) > MAX_RESPONSE_BYTES:
			return None
	return responses


#============================================
def _write_all(file_descriptor: int, payload: bytes) -> None:
	"""Write a complete in-memory payload to one already-private descriptor."""
	offset = 0
	while offset < len(payload):
		written = os.write(file_descriptor, payload[offset:])
		if written <= 0:
			raise OSError("Fixture Hermes file write failed.")
		offset += written


#============================================
def _write_private_file(directory_fd: int, name: str, payload: bytes, mode: int) -> None:
	"""Create and durably write one internally named direct child file."""
	# ASVS 5.3.2: names are generated here and opened beneath the private directory fd.
	flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
	if hasattr(os, "O_NOFOLLOW"):
		flags |= os.O_NOFOLLOW
	file_descriptor = os.open(name, flags, mode, dir_fd=directory_fd)
	try:
		_write_all(file_descriptor, payload)
		os.fsync(file_descriptor)
	finally:
		os.close(file_descriptor)


#============================================
def _installation_directory(parent: pathlib.Path) -> tuple[pathlib.Path, int]:
	"""Create a mode-private, internally named direct child installation directory."""
	parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
	try:
		for _attempt in range(_INSTALL_ATTEMPTS):
			name = f"fixture_hermes_{secrets.token_hex(16)}"
			try:
				os.mkdir(name, 0o700, dir_fd=parent_fd)
			except FileExistsError:
				continue
			root = parent / name
			flags = os.O_RDONLY | os.O_DIRECTORY
			if hasattr(os, "O_NOFOLLOW"):
				flags |= os.O_NOFOLLOW
			root_fd = os.open(name, flags, dir_fd=parent_fd)
			return root, root_fd
	finally:
		os.close(parent_fd)
	raise RuntimeError("Fixture Hermes could not allocate a private installation directory.")


#============================================
def _executable_bytes(mapping_path: str) -> bytes:
	"""Return a minimal executable that delegates to the reviewed Python shim."""
	# ASVS 1.5.2: the generated program receives only a quoted trusted mapping path.
	mapping_literal = json.dumps(mapping_path, ensure_ascii=True)
	program = (
		"#!/usr/bin/env python3\n"
		"import sys\n"
		"import daily_blog.fixture_hermes\n"
		f"raise SystemExit(daily_blog.fixture_hermes.run_installed_shim({mapping_literal}))\n"
	)
	encoded = program.encode("ascii")
	return encoded


#============================================
def install_fixture_hermes(
	parent_directory: str,
	prompt_responses: dict[str, str],
) -> FixtureHermesInstallation:
	"""Install a disposable, no-egress ``hermes`` command beneath one trusted directory.

	Args:
		parent_directory: Existing directory that will contain an internally named installation.
		prompt_responses: Complete UTF-8 prompts mapped to the response each must receive.

	Returns:
		Private executable paths plus a PATH mapping for an inherited CommandRouteRunner process.

	Raises:
		RuntimeError: The trusted parent or bounded prompt-response registration is invalid.
	"""
	if not isinstance(parent_directory, str):
		raise RuntimeError("Fixture Hermes parent must be a directory path.")
	responses = _registered_responses(prompt_responses)
	parent = pathlib.Path(parent_directory).resolve(strict=True)
	if not parent.is_dir():
		raise RuntimeError("Fixture Hermes parent must be an existing directory.")
	mapping_payload = _mapping_bytes(responses)
	mapping_sha256 = hashlib.sha256(mapping_payload).hexdigest()
	response_map_id = _response_map_id(responses)
	root, root_fd = _installation_directory(parent)
	try:
		mapping_name = f"{_MAPPING_PREFIX}{secrets.token_hex(16)}.json"
		mapping_path = root / mapping_name
		_write_private_file(root_fd, mapping_name, mapping_payload, 0o600)
		executable_payload = _executable_bytes(str(mapping_path))
		executable_sha256 = hashlib.sha256(executable_payload).hexdigest()
		_write_private_file(root_fd, "hermes", executable_payload, 0o700)
		os.fsync(root_fd)
	finally:
		os.close(root_fd)
	previous_path = os.environ.get("PATH", "")
	path = str(root)
	if previous_path:
		path = f"{path}{os.pathsep}{previous_path}"
	environment = {"PATH": path}
	installation = FixtureHermesInstallation(
		root=str(root),
		executable=str(root / "hermes"),
		mapping_path=str(mapping_path),
		path=path,
		environment=environment,
		executable_sha256=executable_sha256,
		mapping_sha256=mapping_sha256,
		response_map_id=response_map_id,
		allowed_route=daily_blog.config.HERMES_EDITORIAL_ROUTE,
	)
	return installation


#============================================
def _read_private_child(
	directory_fd: int,
	name: str,
	maximum_bytes: int,
	expected_mode: int,
) -> bytes | None:
	"""Read one regular private direct child through the held installation descriptor."""
	# ASVS 5.3.2: validate generated child names and no-follow descriptors beneath one root fd.
	flags = os.O_RDONLY
	if hasattr(os, "O_NOFOLLOW"):
		flags |= os.O_NOFOLLOW
	try:
		file_descriptor = os.open(name, flags, dir_fd=directory_fd)
	except OSError:
		return None
	try:
		status = os.fstat(file_descriptor)
		private_mode = stat.S_IMODE(status.st_mode) & 0o077 == 0
		if (
			not stat.S_ISREG(status.st_mode)
			or not private_mode
			or status.st_size > maximum_bytes
			or status.st_size < 1
			or stat.S_IMODE(status.st_mode) & expected_mode != expected_mode
		):
			return None
		payload = b""
		while len(payload) < status.st_size:
			chunk = os.read(file_descriptor, status.st_size - len(payload))
			if not chunk:
				return None
			payload += chunk
	finally:
		os.close(file_descriptor)
	return payload


#============================================
def _installation_root(installation: FixtureHermesInstallation) -> tuple[pathlib.Path, int]:
	"""Open a verified private installation root without following a replacement symlink."""
	root = pathlib.Path(installation.root).resolve(strict=True)
	if (
		pathlib.Path(installation.executable).parent != root
		or pathlib.Path(installation.mapping_path).parent != root
	):
		raise RuntimeError("Fixture Hermes installation paths are invalid.")
	flags = os.O_RDONLY | os.O_DIRECTORY
	if hasattr(os, "O_NOFOLLOW"):
		flags |= os.O_NOFOLLOW
	try:
		root_fd = os.open(root, flags)
	except OSError:
		raise RuntimeError("Fixture Hermes installation is unavailable.") from None
	status = os.fstat(root_fd)
	if not stat.S_ISDIR(status.st_mode) or stat.S_IMODE(status.st_mode) & 0o077:
		os.close(root_fd)
		raise RuntimeError("Fixture Hermes installation is unavailable.")
	return root, root_fd


#============================================
def validate_fixture_installation(
	installation: FixtureHermesInstallation,
) -> daily_blog.routes.FixtureRouteProvenance:
	"""Descriptor-validate the current private shim and return its non-secret route attestation."""
	# ASVS 1.5.2, 2.2.1-2.2.3, and 11.4.3: validate structure and SHA-256 identities at use.
	if not isinstance(installation, FixtureHermesInstallation):
		raise RuntimeError("Fixture Hermes installation is invalid.")
	root, root_fd = _installation_root(installation)
	try:
		executable = _read_private_child(root_fd, "hermes", MAX_MAPPING_BYTES, 0o700)
		mapping_name = pathlib.Path(installation.mapping_path).name
		mapping = _read_private_child(root_fd, mapping_name, MAX_MAPPING_BYTES, 0o600)
	finally:
		os.close(root_fd)
	if executable is None or mapping is None:
		raise RuntimeError("Fixture Hermes installation is unavailable.")
	if hashlib.sha256(executable).hexdigest() != installation.executable_sha256:
		raise RuntimeError("Fixture Hermes installation identity is invalid.")
	if hashlib.sha256(mapping).hexdigest() != installation.mapping_sha256:
		raise RuntimeError("Fixture Hermes installation identity is invalid.")
	responses = _parse_mapping_bytes(mapping)
	if responses is None or _response_map_id(responses) != installation.response_map_id:
		raise RuntimeError("Fixture Hermes installation identity is invalid.")
	if installation.allowed_route != daily_blog.config.HERMES_EDITORIAL_ROUTE:
		raise RuntimeError("Fixture Hermes route identity is invalid.")
	provenance = daily_blog.routes.FixtureRouteProvenance(
		schema_version=FIXTURE_SCHEMA_VERSION,
		execution_mode=FIXTURE_HERMES_SHIM,
		external_route_used=FIXTURE_EXTERNAL_ROUTE_USED,
		executable_sha256=installation.executable_sha256,
		mapping_sha256=installation.mapping_sha256,
		response_map_id=installation.response_map_id,
		allowed_route=installation.allowed_route,
	)
	return provenance


#============================================
def _validate_runner_provenance(
	installation: FixtureHermesInstallation,
	provenance: daily_blog.routes.FixtureRouteProvenance,
) -> None:
	"""Revalidate an installation and reject any runner provenance identity drift."""
	current = validate_fixture_installation(installation)
	if current != provenance:
		raise RuntimeError("Fixture Hermes runner provenance is invalid.")


#============================================
def _read_mapping(mapping_path: str) -> dict[str, str] | None:
	"""Load one bounded strict JSON mapping without following a replacement link."""
	# ASVS 5.3.2 and 11.4.3: trusted path ownership and SHA-256 identities protect responses.
	flags = os.O_RDONLY
	if hasattr(os, "O_NOFOLLOW"):
		flags |= os.O_NOFOLLOW
	try:
		file_descriptor = os.open(mapping_path, flags)
	except OSError:
		return None
	try:
		status = os.fstat(file_descriptor)
		if not stat.S_ISREG(status.st_mode) or status.st_size > MAX_MAPPING_BYTES:
			return None
		payload = b""
		while len(payload) < status.st_size:
			chunk = os.read(file_descriptor, status.st_size - len(payload))
			if not chunk:
				return None
			payload += chunk
	finally:
		os.close(file_descriptor)
	responses = _parse_mapping_bytes(payload)
	return responses


#============================================
def fixture_response(
	arguments: object,
	prompt_bytes: bytes,
	mapping_path: str,
) -> tuple[int, bytes, str]:
	"""Return a fixture response for the sealed Hermes argv and complete stdin payload.

	The return tuple is ``(exit_code, stdout, stderr)`` so the executable can expose only
	stable diagnostics.  This boundary never invokes a network client or reads credentials.
	"""
	# ASVS 2.1.1-2.1.3 and 2.2.1-2.2.3: exact argv, bounded stdin, and mapping schema form one contract.
	if (
		not isinstance(arguments, (list, tuple))
		or not all(isinstance(argument, str) for argument in arguments)
		or tuple(arguments) != daily_blog.config.HERMES_EDITORIAL_ROUTE
	):
		return 2, b"", "fixture-hermes: command rejected\n"
	if not isinstance(prompt_bytes, bytes) or len(prompt_bytes) > MAX_PROMPT_BYTES:
		return 2, b"", "fixture-hermes: input rejected\n"
	if not isinstance(mapping_path, str):
		return 2, b"", "fixture-hermes: unavailable\n"
	responses = _read_mapping(mapping_path)
	if responses is None:
		return 2, b"", "fixture-hermes: unavailable\n"
	# ASVS 11.4.3: SHA-256 binds the complete received UTF-8 byte stream to one response.
	digest = hashlib.sha256(prompt_bytes).hexdigest()
	response = responses.get(digest)
	if response is None:
		# ASVS 2.3.1: an unregistered prompt cannot advance this deterministic fixture route.
		return 2, b"", "fixture-hermes: unknown prompt\n"
	return 0, response.encode("utf-8"), ""


#============================================
def run_installed_shim(mapping_path: str) -> int:
	"""Run the installed command process with binary stdin and redacted diagnostics."""
	prompt_bytes = sys.stdin.buffer.read(MAX_PROMPT_BYTES + 1)
	# ASVS 2.2.3: sys.argv omits executable argv[0], so restore the sealed route identity.
	arguments = ("hermes", *sys.argv[1:])
	code, stdout, stderr = fixture_response(arguments, prompt_bytes, mapping_path)
	if stdout:
		sys.stdout.buffer.write(stdout)
	if stderr:
		sys.stderr.write(stderr)
	return code

"""Isolated stdin command routes for author and referee roles."""

# Standard Library
import collections.abc
import dataclasses
import os
import subprocess

# local repo modules
import daily_blog.config


@dataclasses.dataclass(frozen=True)
class FixtureRouteProvenance:
	"""Non-secret attestation binding one fixture runner to its exact local command route."""

	schema_version: str
	execution_mode: str
	external_route_used: bool
	executable_sha256: str
	mapping_sha256: str
	response_map_id: str
	allowed_route: tuple[str, ...]


class CommandRouteRunner:
	"""Run every LLM role in a fresh process with its prompt on stdin."""

	#============================================
	def __init__(
		self,
		path_override: str | None = None,
		fixture_provenance: FixtureRouteProvenance | None = None,
		fixture_validator: collections.abc.Callable[[FixtureRouteProvenance], None] | None = None,
	) -> None:
		"""Optionally pin PATH for this runner's child processes only.

		Args:
			path_override: Complete PATH value for this runner's isolated child processes.
			fixture_provenance: Immutable non-secret shim identity required with a child PATH.
			fixture_validator: Descriptor-backed validator invoked immediately before a shim route.

		Raises:
			RuntimeError: The child-route identity cannot be verified before process execution.
		"""
		invalid_path = (
			path_override is not None
			and (not isinstance(path_override, str) or not path_override)
		)
		invalid_fixture = (
			(path_override is None) != (fixture_provenance is None)
			or (fixture_provenance is None) != (fixture_validator is None)
		)
		if invalid_path or invalid_fixture:
			raise RuntimeError("Editorial route child PATH must be a non-empty string.")
		self.path_override = path_override
		self.fixture_provenance = fixture_provenance
		self.fixture_validator = fixture_validator


	#============================================
	def _child_environment(self) -> dict[str, str] | None:
		"""Return an inherited per-process environment with only PATH overridden."""
		if self.path_override is None:
			return None
		# ASVS 2.2.1 and 2.3.1: derive an isolated child environment, never global PATH.
		environment = os.environ.copy()
		environment["PATH"] = self.path_override
		return environment


	#============================================
	def run(
		self,
		route: daily_blog.config.RoleRoute,
		prompt: str,
		generator_repository: str,
	) -> str:
		"""Execute one configured route and return its stdout response."""
		command = tuple(
			argument.format(generator_repository=generator_repository)
			for argument in route.command
		)
		if self.fixture_provenance is not None:
			# ASVS 2.3.1: validate the sealed local route before each fixture child process.
			self.fixture_validator(self.fixture_provenance)
			if command != self.fixture_provenance.allowed_route:
				raise RuntimeError("Editorial fixture route does not match its attestation.")
		environment = self._child_environment()
		try:
			result = subprocess.run(
				command,
				cwd=generator_repository,
				input=prompt,
				check=False,
				text=True,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				timeout=1200,
				env=environment,
			)
		except subprocess.TimeoutExpired:
			# ASVS 16.5.1: expose one stable category, not the command or payload.
			raise TimeoutError("Editorial route timed out.") from None
		except OSError:
			# ASVS 16.5.1: filesystem and process details remain outside public errors.
			raise OSError("Editorial route could not start.") from None
		if result.returncode:
			# ASVS 14.2.4, 16.2.5, and 16.5.1: external output may contain credentials,
			# account labels, paths, or prompt material and must not reach logs or exceptions.
			raise RuntimeError("Editorial route failed with a nonzero exit status.")
		response = result.stdout.strip()
		if not response:
			raise RuntimeError("Editorial route returned an empty response.")
		return response

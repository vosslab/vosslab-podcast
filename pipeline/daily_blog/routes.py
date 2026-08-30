"""Isolated stdin command routes for author and referee roles."""

# Standard Library
import pathlib
import subprocess

# local repo modules
import daily_blog.editorial_stage_config


class EditorialRouteTimeout(TimeoutError):
	"""The isolated model process exceeded its bounded execution time."""


class EditorialRouteStartError(OSError):
	"""The isolated model process could not be started."""


class EditorialRouteProcessError(RuntimeError):
	"""The isolated model process returned a nonzero status."""


class EditorialRouteEmptyResponse(RuntimeError):
	"""The isolated model process returned no usable stdout payload."""


class CommandRouteRunner:
	"""Run every LLM role in a fresh process with its prompt on stdin."""

	#============================================
	def run(
		self,
		route: daily_blog.editorial_stage_config.RoleRoute,
		prompt: str,
		generator_repository: str,
	) -> str:
		"""Execute one configured route and return its stdout response."""
		if type(route) is not daily_blog.editorial_stage_config.RoleRoute:
			raise RuntimeError("Editorial route runner requires an exact RoleRoute.")
		daily_blog.editorial_stage_config._validate_role_command(
			route.command,
			"daily_blog.route_runner",
		)
		if type(prompt) is not str:
			raise RuntimeError("Editorial route prompt must be a string.")
		if type(generator_repository) is not str:
			raise RuntimeError("Editorial route working directory must be a string.")
		working_directory = pathlib.Path(generator_repository)
		if not working_directory.is_absolute():
			raise RuntimeError(
				"Editorial route working directory must be an absolute existing directory."
			)
		try:
			working_directory = working_directory.resolve(strict=True)
		except OSError:
			raise RuntimeError(
				"Editorial route working directory must be an existing directory."
			) from None
		if not working_directory.is_absolute() or not working_directory.is_dir():
			raise RuntimeError(
				"Editorial route working directory must be an absolute existing directory."
			)
		command = tuple(
			argument.format(generator_repository=str(working_directory))
			for argument in route.command
		)
		try:
			# ASVS 1.2.5: sealed argv direct execution/no shell.
			result = subprocess.run(
				command,
				cwd=str(working_directory),
				input=prompt,
				check=False,
				shell=False,
				text=True,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				timeout=1200,
			)
		except subprocess.TimeoutExpired:
			# ASVS 16.5.1: expose one stable category, not the command or payload.
			raise EditorialRouteTimeout("Editorial route timed out.") from None
		except OSError:
			# ASVS 16.5.1: filesystem and process details remain outside public errors.
			raise EditorialRouteStartError("Editorial route could not start.") from None
		if result.returncode:
			# ASVS 14.2.4, 16.2.5, and 16.5.1: external output may contain credentials,
			# account labels, paths, or prompt material and must not reach logs or exceptions.
			raise EditorialRouteProcessError(
				"Editorial route failed with a nonzero exit status."
			)
		response = result.stdout.strip()
		if not response:
			raise EditorialRouteEmptyResponse("Editorial route returned an empty response.")
		return response

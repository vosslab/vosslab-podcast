"""Isolated stdin command routes for author and referee roles."""

# Standard Library
import subprocess

# local repo modules
import daily_blog.config


class CommandRouteRunner:
	"""Run every LLM role in a fresh process with its prompt on stdin."""

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
		result = subprocess.run(
			command,
			cwd=generator_repository,
			input=prompt,
			check=False,
			text=True,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			timeout=1200,
		)
		if result.returncode:
			message = result.stderr.strip() or result.stdout.strip()
			raise RuntimeError(f"Role route {route.name} failed: {message}")
		response = result.stdout.strip()
		if not response:
			raise RuntimeError(f"Role route {route.name} returned an empty response.")
		return response

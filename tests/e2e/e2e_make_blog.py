#!/usr/bin/env python3
"""Exercise the repository-root blog command without publishing a post."""

# Standard Library
import os
import pathlib
# Direct subprocess execution is the subject of this executable-boundary E2E.
import subprocess  # nosec B404


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
COMMAND = REPO_ROOT / "make_blog.py"


#============================================
def run_command(*arguments: str) -> subprocess.CompletedProcess[str]:
	"""Run the executable from outside its virtual environment.

	Args:
		arguments: Command arguments that stop before publication work.

	Returns:
		The bounded command result for contract assertions.
	"""
	environment = os.environ.copy()
	environment["PATH"] = "/usr/local/bin:/usr/bin:/bin"
	for name in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
		environment.pop(name, None)
	# The repository-owned executable receives separate bounded arguments without a shell.
	return subprocess.run(  # nosec B603
		[str(COMMAND), *arguments],
		cwd=REPO_ROOT,
		check=False,
		capture_output=True,
		text=True,
		timeout=30,
		env=environment,
	)


#============================================
def main() -> None:
	"""Verify relaunch, help, and invalid-date behavior without model or importer work."""
	help_result = run_command("--help")
	if help_result.returncode != 0:
		raise AssertionError(help_result.stderr)
	for selector in ("-Y", "--yesterday", "-y", "--yes", "--date"):
		if selector not in help_result.stdout:
			raise AssertionError(f"Missing selector from help output: {selector}")

	invalid_result = run_command("--date", "2026-99-99")
	if invalid_result.returncode != 2:
		raise AssertionError(
			f"Invalid date returned {invalid_result.returncode}: {invalid_result.stderr}"
		)
	if "real calendar day" not in invalid_result.stderr:
		raise AssertionError("Invalid date did not produce the bounded parser error.")


if __name__ == "__main__":
	main()

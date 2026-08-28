#!/usr/bin/env python3
"""Make one evidence-bound daily blog post for yesterday or an explicit date."""

# Standard Library
import argparse
import datetime
import os
import pathlib
import re
import subprocess
import sys
import zoneinfo


#============================================
def repository_root() -> pathlib.Path:
	"""Return the physical Git repository root containing this command."""
	result = subprocess.run(  # nosec B603
		["git", "rev-parse", "--show-toplevel"],
		cwd=pathlib.Path(__file__).resolve().parent,
		check=False,
		capture_output=True,
		text=True,
	)
	if result.returncode:
		raise RuntimeError("make_blog.py requires a Git repository root.")
	root = pathlib.Path(result.stdout.strip())
	if not root.is_absolute() or not root.is_dir() or root.is_symlink():
		raise RuntimeError("make_blog.py requires one physical absolute Git repository root.")
	return root


REPO_ROOT = repository_root()
REPO_VENV = REPO_ROOT / ".venv"
PIPELINE_DIR = REPO_ROOT / "pipeline"
SETTINGS_PATH = REPO_ROOT / "settings.yaml"
OUTPUT_ROOT = REPO_ROOT / "out"
DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
REQUIRED_PYTHON = (3, 12)


#============================================
def _restart_with_repo_python() -> None:
	"""Relaunch through the repository's physical Python environment when needed."""
	if REPO_VENV.is_symlink() or not REPO_VENV.is_dir():
		raise RuntimeError("make_blog.py requires the physical repository-local .venv.")
	python_path = REPO_VENV / "bin" / "python3"
	if not python_path.is_file() or not os.access(python_path, os.X_OK):
		raise RuntimeError("make_blog.py requires an executable .venv/bin/python3.")
	if os.path.realpath(sys.prefix) == os.path.realpath(REPO_VENV):
		if sys.version_info[:2] != REQUIRED_PYTHON:
			raise RuntimeError("make_blog.py requires repository Python 3.12.")
		return
	arguments = [str(python_path), str(REPO_ROOT / "make_blog.py"), *sys.argv[1:]]
	# ASVS 1.2.5: pass a fixed executable and separate arguments directly, without a shell.
	# Bandit B606 is accepted because the executable is the fixed, verified repository Python.
	os.execv(str(python_path), arguments)  # nosec B606


if __name__ == "__main__":
	_restart_with_repo_python()

if str(PIPELINE_DIR) not in sys.path:
	sys.path.insert(0, str(PIPELINE_DIR))

# local repo modules
import automation.publish_daily_blog  # type: ignore[import-untyped]  # noqa: E402
import daily_blog.config  # type: ignore[import-untyped]  # noqa: E402


#============================================
def normalize_report_date(value: str) -> str:
	"""Return one real calendar date in the publisher's canonical ISO form.

	Args:
		value: ISO ``YYYY-MM-DD`` or unambiguous ``YYYY-DD-MM`` input.

	Returns:
		The selected date formatted as ``YYYY-MM-DD``.

	Raises:
		argparse.ArgumentTypeError: The input is malformed or not a real calendar date.
	"""
	# ASVS 2.2.1: positively require the exact bounded numeric date shape.
	if DATE_PATTERN.fullmatch(value) is None:
		raise argparse.ArgumentTypeError(
			"Date must use YYYY-MM-DD or unambiguous YYYY-DD-MM, such as 2026-21-08."
		)
	try:
		selected = datetime.date.fromisoformat(value)
	except ValueError:
		year_text, day_text, month_text = value.split("-")
		try:
			selected = datetime.date(
				int(year_text),
				int(month_text),
				int(day_text),
			)
		except ValueError as error:
			raise argparse.ArgumentTypeError(
				"Date must name a real calendar day in YYYY-MM-DD or YYYY-DD-MM form."
			) from error
	canonical = selected.isoformat()
	return canonical


#============================================
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
	"""Parse one required and mutually exclusive report-date selector.

	Args:
		argv: Optional explicit argument list for tests and programmatic callers.

	Returns:
		Validated command-line arguments with any explicit date canonicalized.
	"""
	parser = argparse.ArgumentParser(description=__doc__)
	# ASVS 2.3.1: one mutually exclusive selector prevents a skipped or conflicting date flow.
	date_group = parser.add_mutually_exclusive_group(required=True)
	date_group.add_argument(
		"-Y",
		"--yesterday",
		dest="yesterday",
		action="store_true",
		help="Publish yesterday in the configured report timezone.",
	)
	date_group.add_argument(
		"-d",
		"--date",
		dest="report_date",
		type=normalize_report_date,
		help="Publish YYYY-MM-DD; also accepts unambiguous YYYY-DD-MM.",
	)
	parser.add_argument(
		"-y",
		"--yes",
		action="store_true",
		help="Replace an occupied publication date without an interactive prompt.",
	)
	args = parser.parse_args(argv)
	return args


#============================================
def yesterday_for_timezone(timezone_name: str) -> str:
	"""Return yesterday's completed report date in the configured timezone."""
	timezone = zoneinfo.ZoneInfo(timezone_name)
	current = datetime.datetime.now(timezone).date()
	return (current - datetime.timedelta(days=1)).isoformat()


#============================================
def selected_report_date(args: argparse.Namespace, timezone_name: str) -> str:
	"""Resolve the validated CLI selection to one canonical report date.

	Args:
		args: Parsed mutually exclusive date-selection arguments.
		timezone_name: Validated IANA report timezone from repository settings.

	Returns:
		Canonical ``YYYY-MM-DD`` report date.
	"""
	if args.yesterday:
		report_date = yesterday_for_timezone(timezone_name)
	else:
		report_date = args.report_date
	return report_date


#============================================
def confirm_replacement(report_date: str) -> bool:
	"""Ask a terminal operator to replace one existing publication, defaulting to preserve.

	Args:
		report_date: Sole identity of the existing publication.

	Returns:
		True only for one explicit ``y`` response from an interactive terminal.
	"""
	if not sys.stdin.isatty():
		print("Existing publication detected; non-interactive run preserves it.")
		return False
	response = input(f"Overwrite {report_date}? [N/y]: ")
	# ASVS 2.2.1: replacement has one intentionally narrow affirmative value.
	return response == "y"


#============================================
def preauthorized_replacement(_report_date: str) -> bool:
	"""Authorize an explicitly requested replacement without terminal input."""
	# ASVS 2.3.1: this callback is selected only from the parsed --yes intent.
	return True


#============================================
def main(argv: list[str] | None = None) -> None:
	"""Select one date and run the date-owned publication workflow.

	Args:
		argv: Optional explicit argument list for tests and programmatic callers.
	"""
	args = parse_args(argv)
	config = daily_blog.config.load_config(str(SETTINGS_PATH), output_root=str(OUTPUT_ROOT))
	report_date = selected_report_date(args, config.report_timezone)
	print(f"Selected report date: {report_date}")
	replacement_decider = preauthorized_replacement if args.yes else confirm_replacement
	automation.publish_daily_blog.publish_report_date(
		config,
		report_date,
		replacement_decider=replacement_decider,
	)


if __name__ == "__main__":
	main()

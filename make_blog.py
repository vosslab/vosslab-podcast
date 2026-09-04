#!/usr/bin/env python3
"""Make one evidence-bound daily blog post for yesterday or an explicit date."""

# Standard Library
import argparse
import collections.abc
import datetime
import json
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
PIPELINE_DIR = REPO_ROOT / "pipeline"
SETTINGS_PATH = REPO_ROOT / "settings.yaml"
OUTPUT_ROOT = REPO_ROOT / "output-pipeline"
DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
if str(PIPELINE_DIR) not in sys.path:
	sys.path.insert(0, str(PIPELINE_DIR))

# local repo modules
import automation.publish_daily_blog  # type: ignore[import-untyped]  # noqa: E402
import daily_blog.config  # type: ignore[import-untyped]  # noqa: E402
import daily_blog.recovery  # type: ignore[import-untyped]  # noqa: E402


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
	parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
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
		dest="yes",
		action="store_true",
		help="Replace an existing explicitly selected date without prompting.",
	)
	args = parser.parse_args(argv)
	if args.yesterday and args.yes:
		parser.error("--yes applies only with --date; --yesterday replaces automatically.")
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
def _prepare_publication(argv: list[str] | None) -> tuple[object, str, argparse.Namespace]:
	"""Parse one command selection and report the canonical date before publishing.

	Args:
		argv: Optional explicit argument list for tests and command callers.

	Returns:
		The loaded configuration, canonical selected report date, and validated CLI request.
	"""
	args = parse_args(argv)
	config = daily_blog.config.load_config(str(SETTINGS_PATH), output_root=str(OUTPUT_ROOT))
	report_date = selected_report_date(args, config.report_timezone)
	return config, report_date, args


#============================================
def _publish(
	config: object,
	report_date: str,
	runtime: object | None,
	*,
	replace_existing: bool,
	confirm_replace: collections.abc.Callable[[str], str] | None,
) -> bool:
	"""Run the configured date-owned publication service under one replacement policy."""
	if runtime is None:
		return automation.publish_daily_blog.publish_report_date(
			config, report_date, replace_existing=replace_existing, confirm_replace=confirm_replace,
		)
	return automation.publish_daily_blog.publish_report_date(
		config, report_date, runtime=runtime, replace_existing=replace_existing,
		confirm_replace=confirm_replace,
	)


#============================================
def _replacement_policy(
	args: argparse.Namespace,
	confirmation: collections.abc.Callable[[str], str] | None,
) -> tuple[bool, collections.abc.Callable[[str], str] | None]:
	"""Return the date-selection-owned authorization policy for an occupied publication."""
	if args.yesterday or args.yes:
		return True, None
	return False, confirmation if confirmation is not None else input


#============================================
def main(
	argv: list[str] | None = None,
	*,
	runtime: object | None = None,
	confirmation: collections.abc.Callable[[str], str] | None = None,
) -> None:
	"""Select one date and run the date-owned publication workflow.

	Args:
		argv: Optional explicit argument list for tests and programmatic callers.
	"""
	config, report_date, args = _prepare_publication(argv)
	replace_existing, confirm_replace = _replacement_policy(args, confirmation)
	_publish(
		config, report_date, runtime, replace_existing=replace_existing, confirm_replace=confirm_replace,
	)


#============================================
def command(
	argv: list[str] | None = None,
	*,
	runtime: object | None = None,
	confirmation: collections.abc.Callable[[str], str] | None = None,
) -> int:
	"""Run the public command and serialize only a diagnosed terminal pipeline fault.

	Args:
		argv: Optional explicit argument list for command callers.
		runtime: Optional deterministic runtime for tests and controlled execution.

	Returns:
		Zero after publication or a declined replacement, or two after one typed terminal pipeline fault.

	Raises:
		SystemExit: The argparse parser retains its native validation status.
		Exception: Unexpected configuration and implementation defects remain visible.
	"""
	config, report_date, args = _prepare_publication(argv)
	replace_existing, confirm_replace = _replacement_policy(args, confirmation)
	try:
		_publish(
			config, report_date, runtime, replace_existing=replace_existing,
			confirm_replace=confirm_replace,
		)
	except daily_blog.recovery.PipelineFaultError as error:
		# The fault object has already validated every field below. This is the sole CLI projection.
		payload = {
			"artifact_name": error.artifact_name,
			"category": error.category.value,
			"digest_sha256": error.digest_sha256,
			"report_date": report_date,
			"status": "pipeline_fault",
		}
		print(json.dumps(payload, sort_keys=True, separators=(",", ":")), file=sys.stderr)
		return 2
	return 0


if __name__ == "__main__":
	raise SystemExit(command())

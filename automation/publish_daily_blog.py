#!/usr/bin/env python3
"""Generate, judge, bundle, and locally publish one explicit Central-calendar date."""

# Standard Library
import argparse
import collections.abc

# local repo modules
import daily_blog.config
import daily_blog.orchestrator
import daily_blog.publication_state
import daily_blog.publisher
import daily_blog.publication_workflow
import daily_blog.io_utils


#============================================
def parse_args() -> argparse.Namespace:
	"""Parse the one public daily publication command."""
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"-d",
		"--date",
		dest="report_date",
		required=True,
		help="Required report date in YYYY-MM-DD format.",
	)
	parser.add_argument(
		"-s",
		"--settings",
		dest="settings_path",
		default="settings.yaml",
		help="Repository settings path.",
	)
	args = parser.parse_args()
	return args


#============================================
def publish_report_date(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
	*,
	runtime: daily_blog.publication_workflow.PublicationRuntime | None = None,
	replace_existing: bool = True,
	confirm_replace: collections.abc.Callable[[str], str] | None = None,
) -> bool:
	"""Generate and publish one canonical date under its date-owned replacement policy.

	Args:
		config: Validated producer and local-publisher configuration.
		report_date: Canonical ISO calendar date selected by the caller.
		replace_existing: Authorize noninteractive replacement when the date is occupied.
		confirm_replace: Optional narrow terminal callback for an unapproved occupied date.

	Returns:
		True after an import, replacement, or verified no-activity completion; False when the
		user declines replacement.

	Raises:
		RuntimeError: The date, existing receipt, generation, bundle, or import is invalid.
	"""
	command_started_at = daily_blog.io_utils.utc_now()
	with daily_blog.orchestrator.publication_date_lock(config, report_date):
		inspection = daily_blog.publication_state.inspect_publication(config, report_date)
		occupied = inspection.state != "missing"
		should_replace = occupied and replace_existing
		if occupied and not should_replace and confirm_replace is not None:
			# ASVS 2.3.1/2.3.4: inspect, authorize, and mutate while one date lock is held.
			should_replace = confirm_replace(f"Overwrite {report_date}? [N/y]: ") == "y"
		if occupied and not should_replace:
			print(f"Publication cancelled: {report_date} remains unchanged.")
			return False
		if runtime is None:
			bundle_path, _bundle = daily_blog.orchestrator.run_daily_publication_locked(
				config, report_date, publisher_function=daily_blog.publisher.import_bundle,
				force_regeneration=should_replace,
				command_started_at=command_started_at,
			)
		else:
			bundle_path, _bundle = daily_blog.orchestrator.run_daily_publication_locked(
				config, report_date, force_regeneration=should_replace, runtime=runtime,
				command_started_at=command_started_at,
			)
		if _bundle.get("status") == "no_activity":
			print(f"No report-day activity for {report_date}; no publication created.")
			return True
		print(f"Daily publication: {bundle_path}")
		print(f"Report date: {report_date}")
		print(f"Publication status: {'replaced' if should_replace else 'imported'}")
		return True


#============================================
def main() -> None:
	"""Run the complete producer-to-local-publisher workflow."""
	args = parse_args()
	config = daily_blog.config.load_config(args.settings_path)
	publish_report_date(config, args.report_date)


if __name__ == "__main__":
	main()

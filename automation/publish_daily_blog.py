#!/usr/bin/env python3
"""Generate, judge, bundle, and locally publish one explicit Central-calendar date."""

# Standard Library
import argparse
import collections.abc
import functools
import os

# local repo modules
import daily_blog.config
import daily_blog.orchestrator
import daily_blog.publication_state
import daily_blog.publisher


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
	replacement_decider: collections.abc.Callable[[str], bool] | None = None,
) -> None:
	"""Publish, replace, or report the current result for one canonical date.

	Args:
		config: Validated producer and local-publisher configuration.
		report_date: Canonical ISO calendar date selected by the caller.
		replacement_decider: Optional interactive decision for the selected report date.

	Raises:
		RuntimeError: The date, existing receipt, generation, bundle, or import is invalid.
	"""
	with daily_blog.orchestrator.publication_date_lock(config, report_date):
		inspection = daily_blog.publication_state.inspect_publication(config, report_date)
		if inspection.state != "missing":
			replace_existing = (
				replacement_decider is not None and replacement_decider(report_date)
			)
			if not replace_existing and inspection.state == "invalid":
				raise RuntimeError(
					"Existing publication is invalid and requires confirmed replacement: "
					f"{inspection.reason}"
				)
			if not replace_existing:
				publication_path = os.path.join(
					os.path.abspath(config.daily_blog_repository),
					"data",
					"publication_bundles",
					report_date,
				)
				print(f"Daily publication: {publication_path}")
				print(f"Report date: {report_date}")
				print("Publication status: already published")
				return
			publisher_function = functools.partial(
				daily_blog.publisher.import_bundle,
				replace_existing=True,
			)
			bundle_path, _bundle = daily_blog.orchestrator.run_daily_publication_locked(
				config,
				report_date,
				publisher_function=publisher_function,
				force_regeneration=True,
			)
			print(f"Daily publication: {bundle_path}")
			print(f"Report date: {report_date}")
			print("Publication status: replaced")
			return
		bundle_path, _bundle = daily_blog.orchestrator.run_daily_publication_locked(
			config,
			report_date,
		)
		print(f"Daily publication: {bundle_path}")
		print(f"Report date: {report_date}")
		print("Publication status: imported")


#============================================
def main() -> None:
	"""Run the complete producer-to-local-publisher workflow."""
	args = parse_args()
	config = daily_blog.config.load_config(args.settings_path)
	publish_report_date(config, args.report_date)


if __name__ == "__main__":
	main()

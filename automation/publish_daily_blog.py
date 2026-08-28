#!/usr/bin/env python3
"""Generate, judge, bundle, and locally publish one explicit Central-calendar date."""

# Standard Library
import argparse

# local repo modules
import daily_blog.config
import daily_blog.orchestrator


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
def main() -> None:
	"""Run the complete producer-to-local-publisher workflow."""
	args = parse_args()
	config = daily_blog.config.load_config(args.settings_path)
	bundle_path, bundle = daily_blog.orchestrator.run_daily_publication(
		config,
		args.report_date,
	)
	print(f"Daily publication bundle: {bundle_path}")
	print(f"Bundle ID: {bundle['bundle_id']}")


if __name__ == "__main__":
	main()

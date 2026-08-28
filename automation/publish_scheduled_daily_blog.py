#!/usr/bin/env python3
"""Reconcile and publish the bounded backlog through yesterday in Central time."""

# Standard Library
import argparse
import datetime
import zoneinfo

# local repo modules
import daily_blog.config
import daily_blog.schedule


#============================================
def parse_args() -> argparse.Namespace:
	"""Parse the scheduled publication settings path."""
	parser = argparse.ArgumentParser(description=__doc__)
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
def yesterday_for_timezone(timezone_name: str) -> str:
	"""Return yesterday's completed report date in the configured timezone."""
	timezone = zoneinfo.ZoneInfo(timezone_name)
	current = datetime.datetime.now(timezone).date()
	report_date = current - datetime.timedelta(days=1)
	return report_date.isoformat()


#============================================
def main() -> None:
	"""Drain one bounded oldest-first schedule slice and report remaining work."""
	args = parse_args()
	config = daily_blog.config.load_config(args.settings_path)
	target_date = yesterday_for_timezone(config.report_timezone)
	attempted, remaining = daily_blog.schedule.run_scheduled_backlog(config, target_date)
	print(f"Scheduled publication target: {target_date}")
	print(f"Generated dates: {','.join(attempted) if attempted else 'none'}")
	print(f"Backlog remains: {'yes' if remaining else 'no'}")


if __name__ == "__main__":
	main()

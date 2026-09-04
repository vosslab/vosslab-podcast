#!/usr/bin/env python3
"""Render an advisory daily-blog reliability report from terminal summaries."""

# Standard Library
import argparse
import json
import sys

# local repo modules
import daily_blog.reliability_report


#============================================
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
	"""Parse the deliberately small, read-only reporting interface."""
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--owner", required=True, help="Configured output owner.")
	parser.add_argument(
		"--report-date", required=True, help="Report date in YYYY-MM-DD format.",
	)
	parser.add_argument("--output-root", default="output-pipeline", help="Output root (default: output-pipeline).")
	parser.add_argument(
		"--json", action="store_true", dest="as_json", help="Emit canonical JSON.",
	)
	return parser.parse_args(argv)


#============================================
def main(argv: list[str] | None = None) -> int:
	"""Print a valid advisory report or return a bounded input-error status."""
	args = parse_args(argv)
	try:
		report = daily_blog.reliability_report.report_for_date(
			args.output_root, args.owner, args.report_date,
		)
	except RuntimeError:
		print("Reliability report input is unavailable or invalid.", file=sys.stderr)
		return 2
	if args.as_json:
		print(json.dumps(report, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
	else:
		print(daily_blog.reliability_report.render_text_report(report))
	return 0


if __name__ == "__main__":
	sys.exit(main())

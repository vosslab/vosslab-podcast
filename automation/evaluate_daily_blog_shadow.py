#!/usr/bin/env python3
"""Evaluate one historical daily post through the current non-publishing editorial route."""

# Standard Library
import argparse

# local repo modules
import daily_blog.config
import daily_blog.evaluation


#============================================
def parse_args() -> argparse.Namespace:
	"""Parse the explicit date, reference, and cache-refresh choice."""
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--date", dest="report_date", required=True)
	parser.add_argument("--reference", dest="reference_path", required=True)
	parser.add_argument("--settings", dest="settings_path", default="settings.yaml")
	parser.add_argument(
		"--reuse-caches",
		action="store_true",
		help="Use the current exact Git cache objects for an offline historical evaluation.",
	)
	args = parser.parse_args()
	return args


#============================================
def main() -> None:
	"""Run the historical comparison and print its immutable artifact identity."""
	args = parse_args()
	config = daily_blog.config.load_config(args.settings_path)
	shadow_path, scorecard = daily_blog.evaluation.run_shadow_evaluation(
		config,
		args.report_date,
		args.reference_path,
		refresh_mirrors=not args.reuse_caches,
	)
	print(f"Daily publication shadow: {shadow_path}")
	print(f"Verdict: {scorecard['semantic_assessment']['verdict']}")
	print("Review the scorecard and both posts before enabling scheduled publication.")


if __name__ == "__main__":
	main()

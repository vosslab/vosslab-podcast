#!/usr/bin/env python3
"""Run the autonomous no-egress historical maker-rubric calibration."""

# Standard Library
import argparse
import sys

# local repo modules
import daily_blog.config
import daily_blog.rubric_calibration


#============================================
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
	"""Parse only the bounded diagnostic procedure for fixture-backed evidence."""
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"-s",
		"--settings",
		dest="settings_path",
		default="settings.yaml",
		help="Path to the pipeline settings YAML file.",
	)
	parser.add_argument(
		"--repetitions",
		type=int,
		default=daily_blog.rubric_calibration.DEFAULT_REPETITIONS,
		help="Bounded diagnostic scorecards per historical post; recorded in the artifact.",
	)
	parser.add_argument(
		"--maximum-criterion-score-span",
		type=int,
		default=daily_blog.rubric_calibration.DEFAULT_MAXIMUM_CRITERION_SCORE_SPAN,
		help="Largest run-to-run score span accepted by this recorded procedure.",
	)
	parser.add_argument(
		"--minimum-band-separation",
		type=float,
		default=daily_blog.rubric_calibration.DEFAULT_MINIMUM_AGGREGATE_BAND_SEPARATION,
		help="Minimum positive-reference versus negative-reference separation for this run.",
	)
	return parser.parse_args(argv)


#============================================
def main(argv: list[str] | None = None) -> int:
	"""Produce mandatory autonomous calibration evidence through the fixture Hermes shim."""
	args = parse_args(argv)
	try:
		config = daily_blog.config.load_config(args.settings_path)
		code, _path, report = daily_blog.rubric_calibration.run_fixture_calibration(
			config,
			repetitions=args.repetitions,
			maximum_criterion_score_span=args.maximum_criterion_score_span,
			minimum_positive_negative_mean_separation=args.minimum_band_separation,
		)
		print("Fixture rubric calibration status: " + report["aggregate"]["status"])
		return code
	except (OSError, RuntimeError, ValueError):
		# ASVS 16.5.1: errors exclude local paths, prompts, fixture mappings, and post text.
		print("Fixture rubric calibration failed; inspect private artifacts.", file=sys.stderr)
		return 2


if __name__ == "__main__":
	raise SystemExit(main())

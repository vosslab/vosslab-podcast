#!/usr/bin/env python3
"""Prepare or run the private, non-publishing maker-rubric calibration."""

# Standard Library
import sys
import argparse

# local repo modules
import daily_blog.config
import daily_blog.rubric_calibration


#============================================
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
	"""Parse the explicit calibration mode and bounded repetition count."""
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"-s",
		"--settings",
		dest="settings_path",
		default="settings.yaml",
		help="Path to the pipeline settings YAML file.",
	)
	parser.add_argument(
		"--prepare-only",
		action="store_true",
		help="Profile and hash the fixed historical inputs without invoking a model route.",
	)
	parser.add_argument(
		"--approve-historical-post-sharing",
		action="store_true",
		help="Confirm this invocation may send the five public historical posts to the referee route.",
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
		help="Largest per-criterion run-to-run score span accepted by this evidence procedure.",
	)
	parser.add_argument(
		"--minimum-band-separation",
		type=float,
		default=daily_blog.rubric_calibration.DEFAULT_MINIMUM_AGGREGATE_BAND_SEPARATION,
		help="Minimum positive-reference versus negative-reference mean separation for this run.",
	)
	return parser.parse_args(argv)


#============================================
def main(
	argv: list[str] | None = None,
	runner: object | None = None,
) -> int:
	"""Prepare local evidence or run an explicitly approved live calibration."""
	args = parse_args(argv)
	try:
		config = daily_blog.config.load_config(args.settings_path)
		procedure = daily_blog.rubric_calibration.calibration_procedure(
			repetitions=args.repetitions,
			maximum_criterion_score_span=args.maximum_criterion_score_span,
			minimum_positive_negative_mean_separation=args.minimum_band_separation,
		)
		if args.prepare_only:
			if args.approve_historical_post_sharing:
				raise daily_blog.rubric_calibration.CalibrationBlockedError(
					"Preparation mode and live sharing approval are separate operations."
				)
			_path, report = daily_blog.rubric_calibration.prepare_calibration(config, procedure)
			print("Rubric calibration preparation: " + report["preparation_id"])
			return 0
		code, _path, report = daily_blog.rubric_calibration.run_live_calibration(
			config,
			operator_approved=args.approve_historical_post_sharing,
			repetitions=procedure.repetitions,
			maximum_criterion_score_span=procedure.maximum_criterion_score_span,
			minimum_positive_negative_mean_separation=(
				procedure.minimum_positive_negative_mean_separation
			),
			runner=runner,
		)
		print("Rubric calibration status: " + report["aggregate"]["status"])
		return code
	except daily_blog.rubric_calibration.CalibrationBlockedError:
		print(
			"Rubric calibration blocked: explicit historical-post sharing approval and "
			"configuration are required.",
			file=sys.stderr,
		)
		return 2
	except (OSError, RuntimeError, ValueError):
		# ASVS 16.5.1: CLI errors omit paths, route stderr, prompts, and historical text.
		print("Rubric calibration failed; inspect private configuration and artifacts.", file=sys.stderr)
		return 2


if __name__ == "__main__":
	raise SystemExit(main())

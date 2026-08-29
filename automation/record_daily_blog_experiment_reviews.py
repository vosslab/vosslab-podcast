#!/usr/bin/env python3
"""Record immutable non-publishing F4 evidence from sealed independent reviews."""

# Standard Library
import argparse
import sys

# local repo modules
import daily_blog.config
import daily_blog.experiment_review_artifacts


#============================================
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
	"""Parse only artifact inputs; model, publishing, schedule, and activation stay unavailable."""
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--attestation", required=True, help="Absolute sealed attestation directory.")
	parser.add_argument(
		"--submission",
		action="append",
		required=True,
		help="Absolute independent-review JSON artifact; repeat for each configured reviewer.",
	)
	parser.add_argument(
		"-s",
		"--settings-path",
		default="settings.yaml",
		help="Pipeline settings YAML path.",
	)
	args = parser.parse_args(argv)
	return args


#============================================
def main(argv: list[str] | None = None) -> int:
	"""Record F4 evidence and map its accepted/revise outcome to a stable exit code."""
	args = parse_args(argv)
	try:
		config = daily_blog.config.load_config(args.settings_path)
		code, path = daily_blog.experiment_review_artifacts.create_review_evidence(
			config,
			args.attestation,
			args.submission,
		)
		print("Prompt experiment review evidence: " + path.name)
		return code
	except (OSError, RuntimeError, ValueError):
		# ASVS 1.5.2 and 2.2.1: reveal no private paths, posts, or review prose to callers.
		print("Prompt experiment review evidence failed; inspect private artifacts.", file=sys.stderr)
		return 2



if __name__ == "__main__":
	raise SystemExit(main())

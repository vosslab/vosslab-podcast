#!/usr/bin/env python3
"""Create a private deterministic acceptance attestation for one sealed experiment."""

# Standard Library
import argparse
import sys

# local repo modules
import daily_blog.config
import daily_blog.experiment_attestation


#============================================
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
	"""Parse direct private artifact references without accepting route options."""
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--capture", required=True, help="Absolute sealed capture directory.")
	parser.add_argument(
		"--calibration",
		required=True,
		help="Absolute passing live calibration directory.",
	)
	parser.add_argument(
		"-s",
		"--settings-path",
		default="settings.yaml",
		help="Pipeline settings YAML path.",
	)
	return parser.parse_args(argv)


#============================================
def main(argv: list[str] | None = None) -> int:
	"""Attest a capture/calibration join and map its deterministic status to exit codes."""
	args = parse_args(argv)
	try:
		config = daily_blog.config.load_config(args.settings_path)
		code, path = daily_blog.experiment_attestation.create_attestation(
			config, args.capture, args.calibration,
		)
		print("Prompt experiment attestation: " + path.name)
		return code
	except (OSError, RuntimeError, ValueError):
		# ASVS 2.2.1: reject invalid artifact references without emitting private paths or prose.
		print("Prompt experiment attestation failed; inspect private artifacts.", file=sys.stderr)
		return 2


if __name__ == "__main__":
	raise SystemExit(main())

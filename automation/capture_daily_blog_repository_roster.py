#!/usr/bin/env python3
"""Capture one fresh authoritative repository-roster snapshot."""

# Standard Library
import sys
import argparse

# local repo modules
import daily_blog.config
import daily_blog.roster_snapshots


#============================================
def parse_args() -> argparse.Namespace:
	"""Parse the explicit settings path for one fresh owner acquisition."""
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"-s",
		"--settings",
		dest="settings_path",
		default="settings.yaml",
		help="Path to the pipeline settings YAML file.",
	)
	return parser.parse_args()


#============================================
def main() -> int:
	"""Capture the configured owner's roster and print only its safe local path."""
	try:
		args = parse_args()
		config = daily_blog.config.load_config(args.settings_path)
		path, identity = daily_blog.roster_snapshots.capture_fresh_repository_roster(
			config.output_owner,
			config.output_root,
		)
	except (OSError, RuntimeError, ValueError):
		print("Repository roster capture failed; no snapshot was installed.", file=sys.stderr)
		return 2
	print(f"Repository roster snapshot: {path}")
	print(f"Roster identity: {identity['roster_id']}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

#!/usr/bin/env python3
import argparse
import os

from podlib import daily_github_blog
from podlib import pipeline_settings


#============================================
def parse_args() -> argparse.Namespace:
	"""
	Parse the daily GitHub blog authoring and promotion command arguments.
	"""
	parser = argparse.ArgumentParser(
		description="Author, validate, and promote one claim-backed daily GitHub blog post."
	)
	parser.add_argument(
		"-d",
		"--date",
		dest="date_text",
		required=True,
		help="Required M2 local calendar date in YYYY-MM-DD format.",
	)
	parser.add_argument(
		"-s",
		"--settings",
		dest="settings_path",
		default="settings.yaml",
		help="YAML settings path for the default user-scoped run directory.",
	)
	parser.add_argument(
		"-o",
		"--output-root",
		dest="output_root",
		default="out",
		help="Output root for the default <root>/<user>/daily/<date> M2 run directory.",
	)
	parser.add_argument(
		"-r",
		"--run-dir",
		dest="run_dir",
		default="",
		help="Explicit existing M2 run directory override.",
	)
	mode_group = parser.add_mutually_exclusive_group()
	mode_group.add_argument(
		"--dry-run",
		dest="dry_run",
		action="store_true",
		help="Write deterministic synthetic author artifacts without Hermes, a model, or network.",
	)
	mode_group.add_argument(
		"--validate-only",
		dest="validate_only",
		action="store_true",
		help="Validate existing agent artifacts without authoring or promotion.",
	)
	mode_group.add_argument(
		"--promote-only",
		dest="promote_only",
		action="store_true",
		help="Validate and promote existing agent artifacts without authoring.",
	)
	args = parser.parse_args()
	return args


#============================================
def resolve_run_dir(args: argparse.Namespace) -> str:
	"""
	Resolve the explicit or user-scoped M2 run directory.
	"""
	if args.run_dir:
		return os.path.abspath(args.run_dir)
	settings, _ = pipeline_settings.load_settings(args.settings_path)
	username = pipeline_settings.get_github_username(settings)
	run_dir = os.path.abspath(os.path.join(args.output_root, username, "daily", args.date_text))
	return run_dir


#============================================
def main() -> None:
	"""
	Run one independent Hermes authoring or deterministic validation workflow.
	"""
	args = parse_args()
	run_dir = resolve_run_dir(args)
	if args.validate_only:
		result = daily_github_blog.validate_author_artifacts(run_dir)
		if not result["valid"]:
			raise RuntimeError("draft validation failed; inspect validation_failures/validation_report.json")
		print(f"Daily GitHub blog draft is valid: {run_dir}")
		return
	if args.promote_only:
		post_path = daily_github_blog.promote_valid_draft(run_dir)
		print(f"Daily GitHub blog promoted: {post_path}")
		return
	if args.dry_run:
		daily_github_blog.write_dry_run_authoring(run_dir)
	else:
		daily_github_blog.run_hermes_author(run_dir)
	post_path = daily_github_blog.promote_valid_draft(run_dir)
	print(f"Daily GitHub blog promoted: {post_path}")


if __name__ == "__main__":
	main()

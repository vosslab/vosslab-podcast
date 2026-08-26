#!/usr/bin/env python3
import argparse
import os

from podlib import daily_github_site
from podlib import pipeline_settings


#============================================
def parse_args() -> argparse.Namespace:
	"""
	Parse static archive build arguments.
	"""
	parser = argparse.ArgumentParser(
		description="Build a deterministic private static archive from promoted daily GitHub posts."
	)
	parser.add_argument(
		"-s",
		"--settings",
		dest="settings_path",
		default="settings.yaml",
		help="YAML settings path used to resolve the user-scoped daily artifact root.",
	)
	parser.add_argument(
		"-o",
		"--output-root",
		dest="output_root",
		default="out",
		help="Output root containing <root>/<user>/daily/ source runs.",
	)
	parser.add_argument(
		"--site-root",
		dest="site_root",
		default="",
		help="Explicit static-site destination; default is <root>/<user>/daily_site/.",
	)
	args = parser.parse_args()
	return args


#============================================
def main() -> None:
	"""
	Build the user-scoped daily static archive without making GitHub or model calls.
	"""
	args = parse_args()
	settings, _ = pipeline_settings.load_settings(args.settings_path)
	username = pipeline_settings.get_github_username(settings)
	result = daily_github_site.build_static_site(args.output_root, username, args.site_root)
	print(f"Daily GitHub static archive wrote: {result['site_root']}")
	print(f"Daily source runs discovered: {len(result['runs'])}")
	if not os.path.isdir(result["site_root"]):
		raise RuntimeError("Static archive build did not create its destination directory.")


if __name__ == "__main__":
	main()

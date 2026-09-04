#!/usr/bin/env python3
"""Verify the daily-blog producer's narrow authenticated GitHub dependency."""

# Standard Library
import argparse
import dataclasses
import os
import re
import sys
from datetime import datetime
from datetime import timezone

# local repo modules
import podlib.github_client
import podlib.pipeline_settings
import podlib.runtime_credentials


#============================================
def parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
	"""Parse only the settings source needed to locate the GitHub cache root."""
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"-s",
		"--settings",
		dest="settings_path",
		default="settings.yaml",
		help="Path to the pipeline settings YAML file.",
	)
	parser.add_argument(
		"--output-root",
		default="output-pipeline",
		help="Trusted producer output root used only for the GitHub client cache directory.",
	)
	return parser.parse_args(arguments)


#============================================
@dataclasses.dataclass(frozen=True)
class ProducerPreflightConfig:
	"""The minimal trusted configuration surface required for this preflight."""

	output_root: str
	output_owner: str


#============================================
def load_preflight_config(settings_path: str, output_root: str) -> ProducerPreflightConfig:
	"""Load only owner identity needed for authenticated GitHub quota evidence."""
	settings, _resolved_path = podlib.pipeline_settings.load_settings(settings_path)
	owner = podlib.pipeline_settings.get_github_username(settings)
	# OWASP ASVS v5.0.0 2.2.1: owner and output-root inputs control a cache path.
	if not re.fullmatch(r"[A-Za-z0-9-]+", owner) or not output_root.strip():
		raise RuntimeError("Daily-blog producer preflight configuration is invalid.")
	return ProducerPreflightConfig(
		output_root=os.path.abspath(output_root),
		output_owner=owner,
	)


#============================================
def authenticated_quota_metadata(config: ProducerPreflightConfig) -> dict[str, object]:
	"""Return the minimal successful GitHub authentication evidence for one run."""
	# OWASP ASVS v5.0.0 13.3.2: read only the named runtime credential and retain it
	# locally for the authenticated client construction; it is never returned or stored.
	token = podlib.runtime_credentials.get_github_token()
	# OWASP ASVS v5.0.0 5.3.2: this cache path uses only trusted settings-derived path components.
	cache_dir = os.path.join(config.output_root, config.output_owner, "daily_blog_cache", "github_preflight")
	client = podlib.github_client.GitHubClient(token, cache_dir=cache_dir)
	remaining, reset_utc = client.get_core_rate_limit_snapshot()
	# OWASP ASVS v5.0.0 2.2.1: quota metadata is accepted only in the bounded shape required by this gate.
	if isinstance(remaining, bool) or not isinstance(remaining, int) or remaining < 0:
		raise RuntimeError("GitHub authenticated quota metadata is invalid.")
	if not isinstance(reset_utc, datetime) or reset_utc.tzinfo is None:
		raise RuntimeError("GitHub authenticated quota metadata is invalid.")
	return {
		"github_token_available": True,
		"github_core_remaining": remaining,
		"github_core_reset_utc": reset_utc.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
	}


#============================================
def main(arguments: list[str] | None = None) -> int:
	"""Print redacted authenticated-quota evidence or one safe failure message."""
	try:
		args = parse_args(arguments)
		config = load_preflight_config(args.settings_path, args.output_root)
		metadata = authenticated_quota_metadata(config)
	# OWASP ASVS v5.0.0 16.5.1: external authentication failures remain intentionally generic.
	except Exception:
		# OWASP ASVS v5.0.0 14.2.6 and 16.2.5: diagnostics disclose only gate state, never token text or paths.
		print("Daily-blog producer preflight failed; authenticated GitHub quota is unavailable.", file=sys.stderr)
		return 2
	for name in ("github_token_available", "github_core_remaining", "github_core_reset_utc"):
		print(f"{name}={metadata[name]}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

#!/usr/bin/env python3
import argparse
import json
from datetime import datetime
from datetime import timezone

from podlib import daily_github_evidence
from podlib import github_client
from podlib import pipeline_settings


#============================================
def parse_args() -> argparse.Namespace:
	"""
	Parse explicit-date daily evidence command arguments.
	"""
	parser = argparse.ArgumentParser(
		description="Collect or normalize one date of GitHub commit evidence."
	)
	parser.add_argument(
		"-d",
		"--date",
		dest="date_text",
		required=True,
		help="Required local calendar date in YYYY-MM-DD format.",
	)
	parser.add_argument(
		"-s",
		"--settings",
		dest="settings_path",
		default="settings.yaml",
		help="YAML settings path.",
	)
	parser.add_argument(
		"-z",
		"--timezone",
		dest="timezone_name",
		default="",
		help="IANA timezone override; defaults to github.timezone in settings.",
	)
	source_group = parser.add_mutually_exclusive_group(required=True)
	source_group.add_argument(
		"-i",
		"--input",
		dest="input_path",
		default="",
		help="Offline JSON records or raw commit-record file.",
	)
	source_group.add_argument(
		"-r",
		"--repo",
		dest="repositories",
		action="append",
		default=[],
		help="Repository full name to collect live; repeat for more repositories.",
	)
	parser.add_argument(
		"-o",
		"--output-root",
		dest="output_root",
		default="out",
		help="Output root; artifacts are written under <root>/<user>/daily/<date>/.",
	)
	parser.add_argument(
		"--collected-at",
		dest="collected_at",
		default="",
		help="ISO-8601 retrieval time override for deterministic synthetic runs.",
	)
	args = parser.parse_args()
	return args


#============================================
def read_input_payload(path: str) -> tuple[list[dict], dict]:
	"""
	Read accepted offline raw records and collection metadata from JSON.
	"""
	with open(path, "r", encoding="utf-8") as handle:
		payload = json.load(handle)
	if isinstance(payload, list):
		return payload, {
			"expected_pages": 0,
			"received_pages": 0,
			"errors": ["Offline record-list input must include collection pagination metadata."],
			"complete": False,
			"pagination": [],
		}
	if not isinstance(payload, dict):
		raise RuntimeError("Input JSON must be a list of records or a mapping with records.")
	records = payload.get("records")
	if not isinstance(records, list):
		raise RuntimeError("Input mapping must contain a records list.")
	if "collection" not in payload:
		return records, {
			"expected_pages": 0,
			"received_pages": 0,
			"errors": ["Input mapping must include collection pagination metadata."],
			"complete": False,
			"pagination": [],
		}
	metadata = payload["collection"]
	if not isinstance(metadata, dict):
		return records, {
			"expected_pages": 0,
			"received_pages": 0,
			"errors": ["Input collection metadata must be a mapping."],
			"complete": False,
		}
	return records, metadata


#============================================
def collect_live_records(
	repositories: list[str],
	start,
	end,
	token: str,
	cache_dir: str,
	client_factory=github_client.GitHubClient,
) -> tuple[list[dict], dict]:
	"""
	Collect raw commits from named repositories without generating prose.
	"""
	records = []
	errors = []
	pagination = []
	try:
		client = client_factory(token, cache_dir=cache_dir)
	except Exception as error:
		for repository in repositories:
			pagination.append(
				{
					"repository": repository,
					"expected_pages": 1,
					"received_pages": 0,
					"complete": False,
				}
			)
			errors.append(f"GitHub client initialization failed: {error}")
		client = None
	for repository in repositories:
		try:
			daily_github_evidence.validate_repository_name(repository)
		except RuntimeError as error:
			pagination.append(
				{
					"repository": repository,
					"expected_pages": 1,
					"received_pages": 0,
					"complete": False,
				}
			)
			errors.append(f"Invalid GitHub repository {repository}: {error}")
			continue
		if client is None:
			continue
		page_state = {
			"repository": repository,
			"expected_pages": 0,
			"received_pages": 0,
			"complete": False,
		}
		try:
			repository_object = client.get_repo(repository)
			client.sleep_request_jitter(f"GET /repos/{repository}/commits")
			client.record_api_call(f"GET /repos/{repository}/commits")
			commit_pages = repository_object.get_commits(
				since=start.astimezone(timezone.utc),
				until=end.astimezone(timezone.utc),
			)
		except Exception as error:
			page_state["expected_pages"] = 1
			errors.append(f"GitHub commit collection failed for {repository}: {error}")
			pagination.append(page_state)
			continue
		page_index = 0
		while True:
			try:
				client.sleep_request_jitter(
					f"GET /repos/{repository}/commits?page={page_index + 1}"
				)
				client.record_api_call(f"GET /repos/{repository}/commits?page={page_index + 1}")
				page = commit_pages.get_page(page_index)
				if not isinstance(page, list):
					raise RuntimeError("GitHub commit page must be a list.")
			except Exception as error:
				page_state["expected_pages"] = page_state["received_pages"] + 1
				errors.append(
					f"GitHub commit page {page_index + 1} failed for {repository}: {error}"
				)
				break
			if not page:
				page_state["expected_pages"] = page_state["received_pages"]
				page_state["complete"] = True
				break
			for commit in page:
				raw_record = commit if isinstance(commit, dict) else getattr(commit, "raw_data", None)
				if not isinstance(raw_record, dict):
					page_state["expected_pages"] = page_state["received_pages"] + 1
					errors.append(
						f"GitHub commit page {page_index + 1} for {repository} has malformed data."
					)
					break
				normalized_record = dict(raw_record)
				normalized_record["repo_full_name"] = repository
				records.append(normalized_record)
			else:
				page_state["received_pages"] += 1
				page_index += 1
				continue
			break
		pagination.append(page_state)
	expected_pages = sum(item["expected_pages"] for item in pagination)
	received_pages = sum(item["received_pages"] for item in pagination)
	complete = bool(repositories) and all(item["complete"] for item in pagination) and not errors
	if not repositories:
		complete = True
	usage = {"api_call_count": 0}
	if client is not None:
		try:
			usage = client.api_usage_snapshot()
		except Exception as error:
			errors.append(f"GitHub API usage reporting failed: {error}")
			complete = False
	metadata = {
		"expected_pages": expected_pages,
		"received_pages": received_pages,
		"errors": errors,
		"complete": complete,
		"pagination": pagination,
		"rate_limit": {"status": "not_queried", "usage": usage},
	}
	return records, metadata


#============================================
def get_collected_at(value: str) -> str:
	"""
	Return supplied timestamp or a current UTC timestamp for live collection.
	"""
	text = value.strip()
	if text:
		daily_github_evidence.parse_iso_timestamp(text)
		return text
	current = datetime.now(timezone.utc).isoformat()
	return current


#============================================
def main() -> None:
	"""
	Create one complete or explicitly incomplete daily GitHub evidence run.
	"""
	args = parse_args()
	settings, settings_path = pipeline_settings.load_settings(args.settings_path)
	output_user = pipeline_settings.get_github_username(settings)
	identity_login = pipeline_settings.get_github_identity_login(settings)
	allowed_emails = pipeline_settings.get_github_allowed_emails(settings)
	timezone_name = args.timezone_name.strip()
	if not timezone_name:
		timezone_name = pipeline_settings.get_setting_str(
			settings,
			["github", "timezone"],
			"America/Chicago",
		)
	start, end = daily_github_evidence.build_local_date_window(args.date_text, timezone_name)
	collected_at = get_collected_at(args.collected_at)
	if args.input_path:
		raw_records, collection_metadata = read_input_payload(args.input_path)
		collection_metadata["input_path"] = args.input_path
	else:
		token = pipeline_settings.get_setting_str(settings, ["github", "token"], "")
		cache_dir = f"{args.output_root}/{output_user}/cache/github_api"
		raw_records, collection_metadata = collect_live_records(
			args.repositories,
			start,
			end,
			token,
			cache_dir,
		)
	raw_snapshot, claim_packet, manifest = daily_github_evidence.create_evidence_artifacts(
		args.date_text,
		timezone_name,
		identity_login,
		allowed_emails,
		raw_records,
		collection_metadata,
		collected_at,
	)
	manifest["settings_path"] = settings_path
	output_dir = daily_github_evidence.write_evidence_artifacts(
		args.output_root,
		output_user,
		args.date_text,
		raw_snapshot,
		claim_packet,
		manifest,
	)
	print(f"Daily GitHub evidence wrote: {output_dir}")
	print(
		"Claims: "
		+ f"confirmed={manifest['counts']['confirmed']}, "
		+ f"ambiguous={manifest['counts']['ambiguous']}, "
		+ f"excluded={manifest['counts']['excluded']}, "
		+ f"complete={manifest['complete']}"
	)


if __name__ == "__main__":
	main()

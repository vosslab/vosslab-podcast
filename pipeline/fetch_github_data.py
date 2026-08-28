#!/usr/bin/env python3
import argparse
import os
from datetime import datetime

from podlib import fetch_github_support
from podlib import github_client
from podlib import pipeline_settings
from podlib import runtime_credentials

try:
	import rich.console
except ModuleNotFoundError:
	rich = None


RICH_CONSOLE = rich.console.Console() if rich is not None else None


#============================================
def log_step(message: str) -> None:
	"""
	Print one timestamped progress line.
	"""
	now_text = datetime.now().strftime("%H:%M:%S")
	line = f"[fetch_github_data {now_text}] {message}"
	if RICH_CONSOLE is None:
		print(line, flush=True)
		return
	lower = message.lower()
	style = "cyan"
	if ("failed" in lower) or ("error" in lower):
		style = "bold red"
	elif ("rate limit" in lower) or ("skipping" in lower):
		style = "yellow"
	elif ("wrote " in lower) or ("collected" in lower):
		style = "green"
	RICH_CONSOLE.print(line, style=style)


#============================================
def parse_args() -> argparse.Namespace:
	"""
	Parse command-line arguments.
	"""
	parser = argparse.ArgumentParser(
		description="Fetch weekly GitHub data and write JSONL records."
	)
	parser.add_argument(
		"--user",
		default="",
		help="GitHub username to fetch (falls back to settings.yaml then vosslab).",
	)
	parser.add_argument(
		"--settings",
		default="settings.yaml",
		help="YAML settings path for defaults.",
	)
	window_group = parser.add_mutually_exclusive_group()
	window_group.add_argument(
		"--last-day",
		action="store_true",
		help="Fetch activity from the last 1 day (default).",
	)
	window_group.add_argument(
		"--last-week",
		action="store_true",
		help="Fetch activity from the last 7 days.",
	)
	window_group.add_argument(
		"--last-month",
		action="store_true",
		help="Fetch activity from the last 30 days.",
	)
	parser.add_argument(
		"--output",
		default="out/github_data.jsonl",
		help="Path to JSONL output file.",
	)
	fork_group = parser.add_mutually_exclusive_group()
	fork_group.add_argument(
		"--include-forks",
		dest="include_forks",
		action="store_true",
		help="Include forked repos in fetch results (default).",
	)
	fork_group.add_argument(
		"--no-include-forks",
		dest="include_forks",
		action="store_false",
		help="Exclude forked repos from fetch results.",
	)
	parser.set_defaults(include_forks=True)
	parser.add_argument(
		"--max-repos",
		type=int,
		default=0,
		help="Optional cap for repos processed (0 means no cap).",
	)
	parser.add_argument(
		"--skip-changelog",
		action="store_true",
		help="Skip fetching docs/CHANGELOG.md records for relevant repos.",
	)
	parser.add_argument(
		"--daily-cache-dir",
		default="out/daily_cache",
		help="Directory for per-day JSONL cache files.",
	)
	args = parser.parse_args()
	return args


#============================================
def main() -> None:
	"""
	Run the weekly GitHub fetch and write JSONL output.
	"""
	args = parse_args()
	settings, settings_path = pipeline_settings.load_settings(args.settings)
	default_user = pipeline_settings.get_github_username(settings, "vosslab")
	user = args.user.strip() or default_user
	log_step(f"Using settings file: {settings_path}")
	log_step(f"Using GitHub user: {user}")
	window_days = fetch_github_support.resolve_window_days(args)
	day_reset_tz = fetch_github_support.resolve_day_reset_timezone()
	day_reset_tz_name = fetch_github_support.resolve_day_reset_timezone_name()
	window_start, window_end = fetch_github_support.compute_completed_window_utc(
		window_days,
		reset_tz=day_reset_tz,
	)
	window_start_local = window_start.astimezone(day_reset_tz)
	window_end_local = window_end.astimezone(day_reset_tz)
	log_step(
		f"Active window: {window_start.isoformat()} -> {window_end.isoformat()} "
		+ f"({window_days} day(s))"
	)
	log_step(
		"Reset window: "
		+ f"{window_start_local.isoformat()} -> {window_end_local.isoformat()} "
		+ f"(reset at {fetch_github_support.DAY_RESET_HOUR_LOCAL:02d}:00 {day_reset_tz_name})"
	)

	token = runtime_credentials.get_github_token()
	log_step("Using authenticated GitHub API mode via runtime GITHUB_TOKEN.")
	api_cache_dir = pipeline_settings.resolve_user_scoped_out_path(
		os.path.join("out", "cache", "github_api"),
		os.path.join("out", "cache", "github_api"),
		user,
	)

	try:
		client = github_client.GitHubClient(token, log_fn=log_step, cache_dir=api_cache_dir)
	except RuntimeError as error:
		log_step(str(error))
		log_step("Aborting fetch run before network calls.")
		return
	stopped_due_to_rate_limit = False
	stopped_reason = ""
	log_step("Fetching repository list.")
	repos: list[dict] = fetch_github_support.load_repo_list_cache(user, window_end)
	if repos:
		log_step(
			"Repository list cache hit: "
			+ f"{len(repos)} repo(s) from {fetch_github_support.repo_list_cache_path(user)}"
		)
	else:
		stale_repos = fetch_github_support.load_repo_list_cache(
			user,
			window_end,
			max_age_seconds=None,
		)
		if stale_repos:
			repos = stale_repos
			log_step(
				"Repository list stale-cache fallback: "
				+ f"{len(repos)} repo(s) from "
				+ fetch_github_support.repo_list_cache_path(user)
			)
		else:
			try:
				repo_iter = client.list_repos(user)
				repo_objects = list(repo_iter)
				repos = [
					fetch_github_support.repo_to_dict(repo_obj)
					for repo_obj in repo_objects
				]
				cache_path = fetch_github_support.save_repo_list_cache(
					user,
					window_end,
					repos,
				)
				log_step(f"Repository list cache refreshed: {len(repos)} repo(s) -> {cache_path}")
			except github_client.RateLimitError as error:
				stopped_due_to_rate_limit = True
				stopped_reason = str(error)
				log_step(stopped_reason)
				log_step("Repository listing stopped by rate limit; writing summary-only output.")
	if args.max_repos > 0:
		repos = repos[: args.max_repos]
		log_step(f"Applied --max-repos cap: {len(repos)} repo(s).")
	else:
		log_step(f"Repository candidates: {len(repos)}.")

	scoped_output_arg = pipeline_settings.resolve_user_scoped_out_path(
		args.output,
		"out/github_data.jsonl",
		user,
	)
	scoped_daily_cache_dir = pipeline_settings.resolve_user_scoped_out_path(
		args.daily_cache_dir,
		"out/daily_cache",
		user,
	)
	date_text = window_start_local.date().isoformat()
	dated_output = fetch_github_support.date_stamp_output_path(scoped_output_arg, date_text)
	output_path = os.path.abspath(dated_output)
	output_dir = os.path.dirname(output_path)
	os.makedirs(output_dir, exist_ok=True)
	log_step(f"Using local date stamp for fetch output filename: {date_text}")
	log_step(f"Writing JSONL output to: {output_path}")

	record_counts = {
		"repo": 0,
		"commit": 0,
		"issue": 0,
		"pull_request": 0,
		"repo_changelog": 0,
	}
	repo_commit_totals: list[tuple[str, int]] = []
	daily_buckets: dict[str, list[dict]] = {}
	day_keys = fetch_github_support.build_window_day_keys(
		window_start,
		window_days,
		reset_tz=day_reset_tz,
	)
	fallback_day = day_keys[-1] if day_keys else date_text

	with open(output_path, "w", encoding="utf-8") as handle:
		start_record = {
			"record_type": "run_metadata",
			"user": user,
			"window_start": window_start.isoformat(),
			"window_end": window_end.isoformat(),
			"window_days": window_days,
			"fetched_at": window_end.isoformat(),
			"source": "fetch_github_data.py",
			"daily_cache_dir": os.path.abspath(scoped_daily_cache_dir),
		}
		fetch_github_support.write_jsonl_line(handle, start_record)

		for repo in repos:
			if repo.get("fork") and not args.include_forks:
				log_step(f"Skipped repo: {repo.get('full_name') or '(unknown)'}")
				continue
			repo_full_name = repo.get("full_name") or ""
			repo_name = repo.get("name") or ""
			if not repo_full_name:
				continue

			updated_marker = (
				repo.get("updated_at")
				or repo.get("pushed_at")
				or repo.get("created_at")
				or ""
			)
			repo_recent = fetch_github_support.in_window(
				updated_marker,
				window_start,
				window_end,
			)
			if not repo_recent:
				log_step(f"Skipped repo: {repo_full_name}")
				continue
			log_step(f"Processing repo: {repo_full_name}")
			repo_activity_count = 0
			repo_commit_count = 0

			try:
				commits = client.list_commits(repo_full_name, window_start, window_end)
			except github_client.RateLimitError as error:
				stopped_due_to_rate_limit = True
				stopped_reason = str(error)
				log_step(stopped_reason)
				log_step(f"Skipped repo: {repo_full_name}")
				continue
			for commit_obj in commits:
				commit = fetch_github_support.commit_to_dict(commit_obj)
				repo_commit_count += 1
				if repo_commit_count == 1:
					repo_record = fetch_github_support.build_repo_record(
						user,
						window_start,
						window_end,
						repo,
					)
					fetch_github_support.write_jsonl_line(handle, repo_record)
					fetch_github_support.add_record_to_daily_bucket(
						daily_buckets,
						repo_record,
						fallback_day,
						reset_tz=day_reset_tz,
					)
					record_counts["repo"] += 1
				commit_record = fetch_github_support.build_commit_record(
					user,
					window_start,
					window_end,
					repo_full_name,
					repo_name,
					commit,
				)
				fetch_github_support.write_jsonl_line(handle, commit_record)
				fetch_github_support.add_record_to_daily_bucket(
					daily_buckets,
					commit_record,
					fallback_day,
					reset_tz=day_reset_tz,
				)
				record_counts["commit"] += 1
				repo_activity_count += 1
			log_step(f"Repo {repo_full_name}: collected {repo_commit_count} commit record(s).")
			if repo_commit_count < 1:
				log_step(f"Skipped repo: {repo_full_name}")
				continue
			repo_commit_totals.append((repo_full_name, repo_commit_count))

			if (not args.skip_changelog) and (repo_recent or repo_activity_count > 0):
				ref_name = repo.get("default_branch") or ""
				try:
					changelog_info = fetch_github_support.fetch_repo_changelog_content(
						client,
						repo_full_name,
						ref_name,
					)
				except github_client.RateLimitError as error:
					stopped_due_to_rate_limit = True
					stopped_reason = str(error)
					log_step(stopped_reason)
					log_step(f"Skipped repo: {repo_full_name}")
					continue
				if changelog_info:
					changelog_records = fetch_github_support.build_changelog_records(
						user,
						window_start,
						window_end,
						repo_full_name,
						repo_name,
						changelog_info,
					)
					for changelog_record in changelog_records:
						fetch_github_support.write_jsonl_line(handle, changelog_record)
						fetch_github_support.add_record_to_daily_bucket(
							daily_buckets,
							changelog_record,
							fallback_day,
							reset_tz=day_reset_tz,
						)
						record_counts["repo_changelog"] += 1

		end_record = {
			"record_type": "run_summary",
			"user": user,
			"window_start": window_start.isoformat(),
			"window_end": window_end.isoformat(),
			"window_days": window_days,
			"fetched_at": fetch_github_support.utc_now().isoformat(),
			"record_counts": record_counts,
			"daily_cache_dir": os.path.abspath(scoped_daily_cache_dir),
			"stopped_due_to_rate_limit": stopped_due_to_rate_limit,
			"stop_reason": stopped_reason,
		}
		fetch_github_support.write_jsonl_line(handle, end_record)

	written_daily_files = fetch_github_support.write_daily_cache_files(
		scoped_daily_cache_dir,
		user,
		window_start,
		window_end,
		day_keys,
		daily_buckets,
	)
	total_records = (
		record_counts["repo"]
		+ record_counts["commit"]
		+ record_counts["issue"]
		+ record_counts["pull_request"]
		+ record_counts["repo_changelog"]
		+ 2
	)
	log_step(f"Wrote {output_path} ({total_records} records)")
	if repo_commit_totals:
		log_step("Repo commit summary:")
		for repo_full_name, commit_count in repo_commit_totals:
			log_step(f"{repo_full_name} ({commit_count} commits)")
	else:
		log_step("Repo commit summary: no repos with commits in this window.")
	log_step(
		"Daily cache files written: "
		+ f"{len(written_daily_files)} in {os.path.abspath(scoped_daily_cache_dir)}"
	)
	if stopped_due_to_rate_limit:
		log_step("Run finished with partial data due to GitHub API rate limiting.")
	usage = client.api_usage_snapshot()
	log_step(
		"GitHub API usage: "
		+ f"calls={usage.get('api_call_count', 0)}, "
		+ f"cache_hits={usage.get('cache_hit_count', 0)}, "
		+ f"cache_misses={usage.get('cache_miss_count', 0)}"
	)


if __name__ == "__main__":
	main()

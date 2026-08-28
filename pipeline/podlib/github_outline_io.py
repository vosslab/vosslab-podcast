"""Deterministic parsing and artifact I/O for GitHub activity outlines."""

# Standard Library
import os
import re
import glob
import json
import math
import collections.abc
from datetime import datetime
from datetime import timezone


REPO_SLUG_RE = re.compile(r"[^a-z0-9._-]+")
DAILY_GLOBAL_TARGET_WORDS = 2000
MIN_REPO_TARGET_WORDS = 750


#============================================
def parse_iso(ts: str) -> datetime:
	"""Parse an ISO timestamp into a timezone-aware datetime."""
	if not ts:
		return datetime(1970, 1, 1, tzinfo=timezone.utc)
	parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
	return parsed


#============================================
def resolve_latest_fetch_input(input_path: str) -> str:
	"""Return the newest dated fetch file when the default input is absent."""
	if os.path.isfile(input_path):
		return input_path
	directory = os.path.dirname(input_path)
	pattern = os.path.join(directory, "github_data_*.jsonl")
	candidates = []
	for candidate in glob.glob(pattern):
		filename = os.path.basename(candidate)
		if filename == "github_data.jsonl":
			continue
		if os.path.isfile(candidate):
			candidates.append(candidate)
	if not candidates:
		return input_path
	candidates.sort(key=os.path.getmtime, reverse=True)
	return candidates[0]


#============================================
def truncate_changelog_entries(
	entries: list[dict],
	max_entries: int = 3,
	total_char_budget: int = 2500,
) -> list[dict]:
	"""Limit changelog context to a fixed entry count and character budget."""
	result: list[dict] = []
	chars_used = 0
	for entry in entries[:max_entries]:
		text = entry.get("entry_text", "")
		remaining = total_char_budget - chars_used
		if remaining <= 0:
			break
		if len(text) > remaining:
			text = text[:remaining] + "..."
		chars_used += len(text)
		result.append({
			"heading": entry.get("heading", ""),
			"entry_text": text,
			"date": entry.get("date", ""),
		})
	return result


#============================================
def build_repo_context(bucket: dict, changelog_char_budget: int = 8000) -> dict:
	"""Build compact repository context for an LLM prompt."""
	context = {
		"repo_full_name": bucket.get("repo_full_name", ""),
		"repo_name": bucket.get("repo_name", ""),
		"description": bucket.get("description", ""),
		"language": bucket.get("language", ""),
		"commit_count": bucket.get("commit_count", 0),
		"issue_count": bucket.get("issue_count", 0),
		"pull_request_count": bucket.get("pull_request_count", 0),
		"total_activity": bucket.get("total_activity", 0),
		"latest_event_time": bucket.get("latest_event_time", ""),
		"commit_messages": list(bucket.get("commit_messages", []))[:30],
		"issue_titles": list(bucket.get("issue_titles", []))[:30],
		"pull_request_titles": list(bucket.get("pull_request_titles", []))[:30],
		"changelog_entries": truncate_changelog_entries(
			bucket.get("changelog_entries", []),
			total_char_budget=changelog_char_budget,
		),
	}
	return context


#============================================
def compute_repo_outline_target_words(repo_count: int) -> int:
	"""Compute the per-repository outline ceiling."""
	if repo_count <= 1:
		return DAILY_GLOBAL_TARGET_WORDS
	calculated = math.ceil(DAILY_GLOBAL_TARGET_WORDS / (repo_count - 1))
	return max(MIN_REPO_TARGET_WORDS, calculated)


#============================================
def compute_repo_word_target(bucket: dict, ceiling: int) -> int:
	"""Scale the repository word target to the available source material."""
	chars_per_word = 5
	message_chars = sum(len(message) for message in bucket.get("commit_messages", []))
	issue_chars = sum(len(title) for title in bucket.get("issue_titles", []))
	pull_request_chars = sum(len(title) for title in bucket.get("pull_request_titles", []))
	entries = truncate_changelog_entries(bucket.get("changelog_entries", []))
	changelog_chars = sum(len(entry.get("entry_text", "")) for entry in entries)
	input_chars = message_chars + issue_chars + pull_request_chars + changelog_chars
	input_words = input_chars // chars_per_word
	if input_words < 1500:
		scaled = max(100, input_words // 2)
	else:
		scaled = ceiling
	return min(scaled, ceiling)


#============================================
def ensure_repo_bucket(repo_map: dict[str, dict], repo_full_name: str, repo_name: str) -> dict:
	"""Create or return a repository aggregation bucket."""
	if repo_full_name not in repo_map:
		repo_map[repo_full_name] = {
			"repo_full_name": repo_full_name,
			"repo_name": repo_name or repo_full_name,
			"html_url": "",
			"description": "",
			"language": "",
			"commit_count": 0,
			"issue_count": 0,
			"pull_request_count": 0,
			"commit_messages": [],
			"issue_titles": [],
			"pull_request_titles": [],
			"changelog_entries": [],
			"latest_event_time": "",
		}
	return repo_map[repo_full_name]


#============================================
def update_latest_event(bucket: dict, event_time: str) -> None:
	"""Update the latest event marker for one repository bucket."""
	if not event_time:
		return
	current = bucket.get("latest_event_time", "")
	if not current:
		bucket["latest_event_time"] = event_time
		return
	if parse_iso(event_time) > parse_iso(current):
		bucket["latest_event_time"] = event_time


#============================================
def parse_jsonl_to_outline(input_path: str) -> dict:
	"""Parse JSONL records and aggregate outline data."""
	if not os.path.isfile(input_path):
		raise FileNotFoundError(f"Missing JSONL input: {input_path}")

	repo_map: dict[str, dict] = {}
	user = ""
	window_start = ""
	window_end = ""
	run_metadata_count = 0
	run_summary_count = 0
	totals = {
		"repo_records": 0,
		"commit_records": 0,
		"issue_records": 0,
		"pull_request_records": 0,
		"changelog_records": 0,
	}

	with open(input_path, "r", encoding="utf-8") as handle:
		for raw_line in handle:
			line = raw_line.strip()
			if not line:
				continue
			record = json.loads(line)
			record_type = record.get("record_type", "")
			if record.get("user"):
				user = record["user"]
			if record.get("window_start"):
				window_start = record["window_start"]
			if record.get("window_end"):
				window_end = record["window_end"]

			if record_type == "run_metadata":
				run_metadata_count += 1
				continue
			if record_type == "run_summary":
				run_summary_count += 1
				continue

			repo_full_name = record.get("repo_full_name") or ""
			repo_name = record.get("repo_name") or repo_full_name
			if not repo_full_name:
				continue
			bucket = ensure_repo_bucket(repo_map, repo_full_name, repo_name)
			update_latest_event(bucket, record.get("event_time", ""))

			if record_type == "repo":
				totals["repo_records"] += 1
				data = record.get("data") or {}
				bucket["repo_name"] = data.get("name") or bucket["repo_name"]
				bucket["html_url"] = data.get("html_url") or bucket["html_url"]
				bucket["description"] = data.get("description") or bucket["description"]
				bucket["language"] = data.get("language") or bucket["language"]
				continue

			if record_type == "commit":
				totals["commit_records"] += 1
				bucket["commit_count"] += 1
				message = record.get("message") or ""
				raw_lines = [value.strip() for value in message.splitlines() if value.strip()]
				kept = " ".join(raw_lines[:3])
				if kept:
					bucket["commit_messages"].append(kept)
				continue

			if record_type == "issue":
				totals["issue_records"] += 1
				bucket["issue_count"] += 1
				title = (record.get("title") or "").strip()
				if title:
					bucket["issue_titles"].append(title)
				continue

			if record_type == "pull_request":
				totals["pull_request_records"] += 1
				bucket["pull_request_count"] += 1
				title = (record.get("title") or "").strip()
				if title:
					bucket["pull_request_titles"].append(title)
				continue

			if record_type == "repo_changelog":
				totals["changelog_records"] += 1
				heading = (record.get("latest_heading") or "").strip()
				entry_text = (record.get("latest_entry") or "").strip()
				entry_date = (record.get("event_time") or "").strip()
				if entry_text:
					bucket["changelog_entries"].append({
						"heading": heading,
						"entry_text": entry_text,
						"date": entry_date,
					})

	for bucket in repo_map.values():
		bucket["total_activity"] = (
			bucket["commit_count"]
			+ bucket["issue_count"]
			+ bucket["pull_request_count"]
		)

	repos = []
	for bucket in repo_map.values():
		if bucket.get("commit_count", 0) < 1:
			continue
		repos.append(bucket)
	repos.sort(
		key=lambda item: (item["total_activity"], item["commit_count"], item["repo_full_name"]),
		reverse=True,
	)

	notable_commit_messages = []
	for bucket in repos:
		for message in bucket["commit_messages"]:
			if message not in notable_commit_messages:
				notable_commit_messages.append(message)
			if len(notable_commit_messages) >= 30:
				break
		if len(notable_commit_messages) >= 30:
			break

	outline = {
		"generated_at": datetime.now(timezone.utc).isoformat(),
		"source_jsonl": os.path.abspath(input_path),
		"user": user or "unknown",
		"window_start": window_start,
		"window_end": window_end,
		"totals": {
			"repos": len(repos),
			"repo_records": totals["repo_records"],
			"commit_records": totals["commit_records"],
			"issue_records": totals["issue_records"],
			"pull_request_records": totals["pull_request_records"],
			"changelog_records": totals["changelog_records"],
			"run_metadata_records": run_metadata_count,
			"run_summary_records": run_summary_count,
		},
		"repo_activity": repos,
		"notable_commit_messages": notable_commit_messages,
	}
	return outline


#============================================
def render_outline_text(outline: dict) -> str:
	"""Render an unlimited-length Markdown outline."""
	user = outline.get("user", "unknown")
	window_start = outline.get("window_start", "")
	window_end = outline.get("window_end", "")
	totals = outline.get("totals", {})
	repos = outline.get("repo_activity", [])

	lines = [
		"# GitHub Daily Outline",
		"",
		f"- User: {user}",
		f"- Window: {window_start} -> {window_end}",
		"",
		"## Totals",
		f"- Repos with activity: {totals.get('repos', 0)}",
		f"- Repo records: {totals.get('repo_records', 0)}",
		f"- Commit records: {totals.get('commit_records', 0)}",
		f"- Issue records: {totals.get('issue_records', 0)}",
		f"- Pull request records: {totals.get('pull_request_records', 0)}",
		"",
		"## Repository Activity",
	]

	for index, bucket in enumerate(repos, 1):
		lines.append(f"### {index}. {bucket.get('repo_full_name', '')}")
		lines.append(f"- Total activity: {bucket.get('total_activity', 0)}")
		lines.append(f"- Commits: {bucket.get('commit_count', 0)}")
		lines.append(f"- Issues: {bucket.get('issue_count', 0)}")
		lines.append(f"- Pull requests: {bucket.get('pull_request_count', 0)}")
		description = (bucket.get("description") or "").strip()
		if description:
			lines.append(f"- Description: {description}")
		language = (bucket.get("language") or "").strip()
		if language:
			lines.append(f"- Language: {language}")
		if bucket.get("commit_messages"):
			lines.append("- Commit messages:")
			for commit_message in bucket["commit_messages"]:
				lines.append(f"  - {commit_message}")
		if bucket.get("issue_titles"):
			lines.append("- Issues:")
			for title in bucket["issue_titles"]:
				lines.append(f"  - {title}")
		if bucket.get("pull_request_titles"):
			lines.append("- Pull requests:")
			for title in bucket["pull_request_titles"]:
				lines.append(f"  - {title}")
		lines.append("")

	lines.append("## Cross-Repo Commit Highlights")
	for message in outline.get("notable_commit_messages", []):
		lines.append(f"- {message}")
	lines.append("")
	global_outline = (outline.get("llm_global_outline") or "").strip()
	if global_outline:
		lines.append("## LLM Narrative Outline")
		lines.append(global_outline)

	rendered = "\n".join(lines).strip() + "\n"
	return rendered


#============================================
def outline_day_stamp(outline: dict) -> str:
	"""Resolve a date stamp from the outline window end."""
	window_end = str(outline.get("window_end", "")).strip()
	if len(window_end) >= 10 and window_end[4] == "-" and window_end[7] == "-":
		return window_end[:10]
	return datetime.now().astimezone().strftime("%Y-%m-%d")


#============================================
def write_daily_outline_snapshot(outline: dict, daily_outlines_dir: str) -> tuple[str, str]:
	"""Write one date-stamped daily outline JSON and Markdown snapshot."""
	day_stamp = outline_day_stamp(outline)
	base_dir = os.path.abspath(daily_outlines_dir)
	os.makedirs(base_dir, exist_ok=True)
	json_path = os.path.join(base_dir, f"github_outline-{day_stamp}.json")
	markdown_path = os.path.join(base_dir, f"github_outline-{day_stamp}.md")
	with open(json_path, "w", encoding="utf-8") as handle:
		json.dump(outline, handle, indent=2)
		handle.write("\n")
	with open(markdown_path, "w", encoding="utf-8") as handle:
		handle.write(render_outline_text(outline))
	return json_path, markdown_path


#============================================
def sanitize_repo_slug(repo_full_name: str) -> str:
	"""Build a filesystem-safe repository slug."""
	text = repo_full_name.strip().lower().replace("/", "__")
	text = REPO_SLUG_RE.sub("_", text)
	text = text.strip("._-")
	if not text:
		return "repo"
	return text


#============================================
def render_repo_outline_text(outline: dict, bucket: dict, rank: int, repo_total: int) -> str:
	"""Render one repository-scoped outline text shard."""
	lines = [
		"GitHub Repo Outline",
		f"User: {outline.get('user', 'unknown')}",
		f"Window: {outline.get('window_start', '')} -> {outline.get('window_end', '')}",
		f"Rank: {rank} of {repo_total}",
		f"Repo: {bucket.get('repo_full_name', '')}",
		f"Total activity: {bucket.get('total_activity', 0)}",
		f"Commits: {bucket.get('commit_count', 0)}",
		f"Issues: {bucket.get('issue_count', 0)}",
		f"Pull requests: {bucket.get('pull_request_count', 0)}",
	]
	description = (bucket.get("description") or "").strip()
	if description:
		lines.append(f"Description: {description}")
	language = (bucket.get("language") or "").strip()
	if language:
		lines.append(f"Language: {language}")
	lines.append("")
	if bucket.get("commit_messages"):
		lines.append("Commit messages:")
		for message in bucket["commit_messages"]:
			lines.append(f"- {message}")
		lines.append("")
	if bucket.get("issue_titles"):
		lines.append("Issue titles:")
		for title in bucket["issue_titles"]:
			lines.append(f"- {title}")
		lines.append("")
	if bucket.get("pull_request_titles"):
		lines.append("Pull request titles:")
		for title in bucket["pull_request_titles"]:
			lines.append(f"- {title}")
		lines.append("")
	repo_outline = (bucket.get("llm_repo_outline") or "").strip()
	if repo_outline:
		lines.append("LLM Repo Outline")
		lines.append(repo_outline)
		lines.append("")
	rendered = "\n".join(lines).strip() + "\n"
	return rendered


#============================================
def write_repo_outline_shards(outline: dict, repo_shards_dir: str) -> str:
	"""Write one JSON and text shard per repository plus an index manifest."""
	repos = outline.get("repo_activity", [])
	shards_path = os.path.abspath(repo_shards_dir)
	os.makedirs(shards_path, exist_ok=True)

	manifest_items = []
	repo_total = len(repos)
	for index, bucket in enumerate(repos, start=1):
		repo_full_name = bucket.get("repo_full_name", "")
		repo_slug = sanitize_repo_slug(repo_full_name)
		base_name = f"{index:03d}_{repo_slug}"
		repo_json_path = os.path.join(shards_path, base_name + ".json")
		repo_txt_path = os.path.join(shards_path, base_name + ".txt")
		repo_outline = {
			"generated_at": outline.get("generated_at", ""),
			"user": outline.get("user", "unknown"),
			"window_start": outline.get("window_start", ""),
			"window_end": outline.get("window_end", ""),
			"repo_rank": index,
			"repo_total": repo_total,
			"repo_activity": bucket,
		}
		with open(repo_json_path, "w", encoding="utf-8") as json_handle:
			json.dump(repo_outline, json_handle, indent=2)
			json_handle.write("\n")
		repo_text = render_repo_outline_text(outline, bucket, index, repo_total)
		with open(repo_txt_path, "w", encoding="utf-8") as text_handle:
			text_handle.write(repo_text)
		manifest_items.append({
			"repo_full_name": repo_full_name,
			"repo_name": bucket.get("repo_name", ""),
			"repo_rank": index,
			"total_activity": bucket.get("total_activity", 0),
			"json_path": repo_json_path,
			"txt_path": repo_txt_path,
		})

	manifest = {
		"generated_at": outline.get("generated_at", ""),
		"user": outline.get("user", "unknown"),
		"window_start": outline.get("window_start", ""),
		"window_end": outline.get("window_end", ""),
		"repo_count": repo_total,
		"repo_shards": manifest_items,
	}
	manifest_path = os.path.join(shards_path, "index.json")
	with open(manifest_path, "w", encoding="utf-8") as handle:
		json.dump(manifest, handle, indent=2)
		handle.write("\n")
	return manifest_path


#============================================
def write_outline_outputs(
	outline: dict,
	outline_json_path: str,
	outline_txt_path: str,
	repo_shards_dir: str,
	skip_repo_shards: bool,
	log_fn: collections.abc.Callable[[str], None] | None = None,
) -> None:
	"""Write the primary outline files and optional repository shards."""
	json_path = os.path.abspath(outline_json_path)
	text_path = os.path.abspath(outline_txt_path)
	os.makedirs(os.path.dirname(json_path), exist_ok=True)
	os.makedirs(os.path.dirname(text_path), exist_ok=True)

	with open(json_path, "w", encoding="utf-8") as json_handle:
		json.dump(outline, json_handle, indent=2)
		json_handle.write("\n")
	with open(text_path, "w", encoding="utf-8") as text_handle:
		text_handle.write(render_outline_text(outline))

	if log_fn is not None:
		log_fn(f"Wrote outline JSON: {json_path}")
		log_fn(f"Wrote outline text: {text_path}")
	if skip_repo_shards:
		if log_fn is not None:
			log_fn("Skipping repo shard output by request.")
		return

	manifest_path = write_repo_outline_shards(outline, repo_shards_dir)
	if log_fn is not None:
		log_fn(f"Wrote repo shard manifest: {manifest_path}")

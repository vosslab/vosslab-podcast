"""Discover and locate Git commits within one Central-calendar report day."""

# Standard Library
import datetime
import os
import re
import subprocess
import zoneinfo

# local repo modules
import daily_blog.schema
import daily_blog.repository_contracts
import daily_blog.io_utils
import podlib.github_client
import podlib.runtime_credentials


COMMIT_MESSAGE_PREVIEW_CHARS = 160


#============================================
def build_date_window(report_date: str, timezone_name: str) -> tuple[datetime.datetime, datetime.datetime]:
	"""Return one exact local calendar-day interval."""
	try:
		selected = datetime.date.fromisoformat(report_date)
	except ValueError as error:
		raise RuntimeError(f"Invalid report date: {report_date}. Use YYYY-MM-DD.") from error
	try:
		timezone_value = zoneinfo.ZoneInfo(timezone_name)
	except zoneinfo.ZoneInfoNotFoundError as error:
		raise RuntimeError(f"Invalid report timezone: {timezone_name}") from error
	start = datetime.datetime.combine(selected, datetime.time.min, tzinfo=timezone_value)
	end = start + datetime.timedelta(days=1)
	return start, end


#============================================
def _run_git(cache_path: str, arguments: list[str], check: bool = True) -> subprocess.CompletedProcess:
	"""Run one read-only Git query for activity location."""
	result = subprocess.run(
		["git", "-C", cache_path, *arguments],
		check=False,
		text=True,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		timeout=300,
	)
	if check and result.returncode:
		message = result.stderr.strip() or result.stdout.strip()
		raise RuntimeError(f"Git activity query failed in {cache_path}: {message}")
	return result


#============================================
def _commit_record(cache_path: str, sha: str) -> daily_blog.schema.CommitActivity:
	"""Read one exact commit object into the typed activity schema."""
	result = _run_git(
		cache_path,
		[
			"show",
			"--quiet",
			"--format=%H%n%P%n%aI%n%cI%n%aN%n%aE%n%B",
			sha,
		],
	)
	parts = result.stdout.split("\n", 6)
	if len(parts) != 7:
		raise RuntimeError(f"Git commit metadata is incomplete: {sha}")
	commit = daily_blog.schema.CommitActivity(
		sha=parts[0].strip(),
		parents=tuple(parts[1].strip().split()),
		author_timestamp=parts[2].strip(),
		committer_timestamp=parts[3].strip(),
		author_name=parts[4].strip(),
		author_email=parts[5].strip(),
		message=parts[6].strip(),
	)
	return commit


#============================================
def _within_window(
	commit: daily_blog.schema.CommitActivity,
	start: datetime.datetime,
	end: datetime.datetime,
) -> bool:
	"""Return whether the commit author time belongs to the selected local day."""
	moment = datetime.datetime.fromisoformat(commit.author_timestamp.replace("Z", "+00:00"))
	if moment.tzinfo is None:
		raise RuntimeError(f"Commit author timestamp lacks timezone: {commit.sha}")
	local_moment = moment.astimezone(start.tzinfo)
	return start <= local_moment < end


#============================================
def _creation_event(
	mirror: dict,
	start: datetime.datetime,
	end: datetime.datetime,
) -> daily_blog.repository_contracts.RepositoryLifecycleEvent:
	"""Type one roster creation timestamp against the selected local day."""
	created_at = daily_blog.repository_contracts.canonical_utc_timestamp(
		mirror["created_at"], "Mirror repository creation time"
	)
	moment = datetime.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
	local_moment = moment.astimezone(start.tzinfo)
	return daily_blog.repository_contracts.RepositoryLifecycleEvent(
		event_type="repository_created",
		occurred_at=created_at,
		occurred_in_report_window=start <= local_moment < end,
		source="github_owner_roster",
	)


#============================================
def _is_ancestor(cache_path: str, ancestor: str, descendant: str) -> bool:
	"""Return whether one selected commit is an ancestor of another."""
	result = _run_git(
		cache_path,
		["merge-base", "--is-ancestor", ancestor, descendant],
		check=False,
	)
	return result.returncode == 0


#============================================
def _revision_ranges(
	commits: list[daily_blog.schema.CommitActivity],
) -> tuple[daily_blog.schema.RevisionRange, ...]:
	"""Represent every exact attributed commit-to-parent boundary."""
	ranges = []
	for commit in commits:
		for parent in commit.parents or ("",):
			ranges.append(daily_blog.schema.RevisionRange(parent, commit.sha))
	return tuple(ranges)


#============================================
def _snapshot_commits(
	cache_path: str,
	commits: list[daily_blog.schema.CommitActivity],
) -> tuple[str, ...]:
	"""Return every attributed branch tip for exact context snapshots."""
	tips = []
	for commit in commits:
		is_tip = not any(
			other.sha != commit.sha and _is_ancestor(cache_path, commit.sha, other.sha)
			for other in commits
		)
		if is_tip:
			tips.append(commit.sha)
	return tuple(tips)


#============================================
def discover_daily_commits(owner: str, report_date: str, output_root: str) -> list[dict]:
	"""Return one fresh GitHub account/date commit-search snapshot."""
	if re.fullmatch(r"[A-Za-z0-9-]+", owner) is None:
		raise RuntimeError("Daily commit discovery owner is invalid.")
	datetime.date.fromisoformat(report_date)
	token = podlib.runtime_credentials.get_github_token()
	cache_dir = os.path.join(output_root, owner, "daily_blog_cache", "github_commit_search_api")
	client = podlib.github_client.GitHubClient(token, cache_dir=cache_dir)
	return client.search_owner_commits(owner, report_date, use_cache=False)


#============================================
def _commit_reference(value: object, owner: str) -> tuple[str, str]:
	"""Return the owner-qualified repository and SHA from one search result."""
	if type(value) is not dict:
		raise RuntimeError("GitHub commit search returned a non-object result.")
	repository = value.get("repository")
	sha = value.get("sha")
	if (
		type(repository) is not str
		or not repository.casefold().startswith(owner.casefold() + "/")
		or daily_blog.repository_contracts.REPOSITORY_NAME_RE.fullmatch(repository) is None
		or type(sha) is not str
		or re.fullmatch(r"[0-9a-f]{40}", sha) is None
	):
		raise RuntimeError("GitHub commit search returned an invalid repository or SHA.")
	return repository, sha


#============================================
def _message_preview(value: object) -> str:
	"""Return one compact single-line commit-message preview."""
	lines = str(value or "").splitlines()
	message = " ".join((lines[0] if lines else "").split())
	if len(message) > COMMIT_MESSAGE_PREVIEW_CHARS:
		message = message[:COMMIT_MESSAGE_PREVIEW_CHARS - 3].rstrip() + "..."
	return message or "(no commit message)"


#============================================
def build_daily_active_roster(
	owner: str, report_date: str, repository_roster_id: str, commits: list[dict],
) -> dict[str, object]:
	"""Build the canonical machine-owned active roster for one report day."""
	datetime.date.fromisoformat(report_date)
	rows: dict[str, list[dict[str, str]]] = {}
	for value in commits:
		repository, sha = _commit_reference(value, owner)
		rows.setdefault(repository, []).append({
			"sha": sha,
			"author_timestamp": str(value.get("author_timestamp") or ""),
			"author_name": _message_preview(value.get("author_name")),
			"message": _message_preview(value.get("message")),
			"url": f"https://github.com/{repository}/commit/{sha}",
		})
	repositories = []
	for repository in sorted(rows, key=str.casefold):
		commit_rows = sorted(rows[repository], key=lambda item: (item["author_timestamp"], item["sha"]))
		repositories.append({"repository": repository, "commits": commit_rows})
	content: dict[str, object] = {
		"owner": owner,
		"report_date": report_date,
		"repository_roster_id": repository_roster_id,
		"repositories": repositories,
	}
	return {**content, "active_roster_id": daily_blog.io_utils.hash_value(content)}


#============================================
def validate_daily_active_roster(value: object) -> dict[str, object]:
	"""Validate and return one canonical machine-owned daily roster."""
	if not isinstance(value, dict) or set(value) != {
		"owner", "report_date", "repository_roster_id", "repositories", "active_roster_id"
	}:
		raise RuntimeError("Daily active roster fields are invalid.")
	if type(value["owner"]) is not str or re.fullmatch(r"[A-Za-z0-9-]+", value["owner"]) is None:
		raise RuntimeError("Daily active roster owner is invalid.")
	datetime.date.fromisoformat(str(value["report_date"]))
	if type(value["repository_roster_id"]) is not str or re.fullmatch(
		r"[0-9a-f]{64}", value["repository_roster_id"],
	) is None:
		raise RuntimeError("Daily active roster source identity is invalid.")
	if not isinstance(value["repositories"], list):
		raise RuntimeError("Daily active roster repositories are invalid.")
	previous = ""
	for repository_entry in value["repositories"]:
		if not isinstance(repository_entry, dict) or set(repository_entry) != {"repository", "commits"}:
			raise RuntimeError("Daily active roster repository entry is invalid.")
		repository = repository_entry["repository"]
		if type(repository) is not str or repository.casefold() <= previous or not isinstance(repository_entry["commits"], list):
			raise RuntimeError("Daily active roster repository order is invalid.")
		previous = repository.casefold()
		for commit in repository_entry["commits"]:
			if not isinstance(commit, dict) or set(commit) != {
				"sha", "author_timestamp", "author_name", "message", "url"
			} or re.fullmatch(r"[0-9a-f]{40}", str(commit.get("sha"))) is None:
				raise RuntimeError("Daily active roster commit entry is invalid.")
	content = {
		key: value[key]
		for key in ("owner", "report_date", "repository_roster_id", "repositories")
	}
	if value["active_roster_id"] != daily_blog.io_utils.hash_value(content):
		raise RuntimeError("Daily active roster identity is invalid.")
	return dict(value)


#============================================
def commit_repositories(owner: str, commits: list[dict]) -> tuple[str, ...]:
	"""Return the canonical owner repositories named by Step 0."""
	return tuple(sorted({_commit_reference(value, owner)[0] for value in commits}))


#============================================
def locate_activity(
	report_date: str,
	timezone_name: str,
	mirror_entries: list[dict],
	commit_references: list[dict],
	owner: str,
) -> list[daily_blog.schema.RepositoryActivity]:
	"""Resolve GitHub-discovered report-day commits against refreshed mirrors."""
	start, end = build_date_window(report_date, timezone_name)
	by_repository: dict[str, list[str]] = {}
	for value in commit_references:
		repository, sha = _commit_reference(value, owner)
		shas = by_repository.setdefault(repository, [])
		if sha not in shas:
			shas.append(sha)
	activities = []
	for mirror in mirror_entries:
		if mirror.get("refresh_result") == "failed":
			continue
		repository = mirror["repository"]
		if repository not in by_repository:
			continue
		commits = []
		for sha in by_repository[repository]:
			commit = _commit_record(mirror["cache_path"], sha)
			if not _within_window(commit, start, end):
				continue
			commits.append(commit)
		commits.sort(key=lambda item: (item.author_timestamp, item.sha))
		if not commits:
			continue
		is_fork = mirror["is_fork"]
		if type(is_fork) is not bool:
			raise RuntimeError(
				f"Mirror fork state is missing or invalid: {mirror['repository']}"
			)
		activity = daily_blog.schema.RepositoryActivity(
			repository=mirror["repository"],
			repository_url=mirror["repository_url"],
			cache_path=mirror["cache_path"],
			default_revision=mirror["default_revision"],
			commits=tuple(commits),
			revision_ranges=_revision_ranges(commits),
			snapshot_commits=_snapshot_commits(mirror["cache_path"], commits),
			is_fork=is_fork,
			lifecycle_events=(_creation_event(mirror, start, end),),
		)
		activities.append(activity)
	activities.sort(key=lambda item: item.repository.casefold())
	return activities

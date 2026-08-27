"""Locate attributed Git commits within one Central-calendar report day."""

# Standard Library
import datetime
import subprocess
import zoneinfo

# local repo modules
import daily_blog.schema


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
def _candidate_shas(cache_path: str, start: datetime.datetime, end: datetime.datetime) -> list[str]:
	"""Locate nearby reachable commits before exact author-date filtering."""
	padded_start = start - datetime.timedelta(days=2)
	padded_end = end + datetime.timedelta(days=2)
	result = _run_git(
		cache_path,
		[
			"rev-list",
			"--all",
			f"--since={padded_start.isoformat()}",
			f"--until={padded_end.isoformat()}",
		],
	)
	shas = [line.strip() for line in result.stdout.splitlines() if line.strip()]
	return shas


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
def _matches_identity(
	commit: daily_blog.schema.CommitActivity,
	identity_names: tuple[str, ...],
	identity_emails: tuple[str, ...],
) -> bool:
	"""Return whether author metadata exactly matches configured identity evidence."""
	names = {name.casefold() for name in identity_names}
	emails = {email.casefold() for email in identity_emails}
	matched = commit.author_name.casefold() in names or commit.author_email.casefold() in emails
	return matched


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
def locate_activity(
	report_date: str,
	timezone_name: str,
	mirror_entries: list[dict],
	identity_names: tuple[str, ...],
	identity_emails: tuple[str, ...],
) -> list[daily_blog.schema.RepositoryActivity]:
	"""Locate and type all attributed commits for the report day."""
	if not identity_names and not identity_emails:
		raise RuntimeError("Activity attribution requires configured names or emails.")
	start, end = build_date_window(report_date, timezone_name)
	activities = []
	for mirror in mirror_entries:
		if not mirror["object_available"]:
			raise RuntimeError(f"Mirror default object is unavailable: {mirror['repository']}")
		commits = []
		for sha in _candidate_shas(mirror["cache_path"], start, end):
			commit = _commit_record(mirror["cache_path"], sha)
			if not _within_window(commit, start, end):
				continue
			if not _matches_identity(commit, identity_names, identity_emails):
				continue
			commits.append(commit)
		commits.sort(key=lambda item: (item.author_timestamp, item.sha))
		if not commits:
			continue
		activity = daily_blog.schema.RepositoryActivity(
			repository=mirror["repository"],
			repository_url=mirror["repository_url"],
			cache_path=mirror["cache_path"],
			default_revision=mirror["default_revision"],
			commits=tuple(commits),
			revision_ranges=_revision_ranges(commits),
			snapshot_commits=_snapshot_commits(mirror["cache_path"], commits),
		)
		activities.append(activity)
	activities.sort(key=lambda item: item.repository.casefold())
	return activities

"""Fast contract tests for authoritative daily-blog repository discovery."""

# Standard Library
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.activity
import daily_blog.repositories
import daily_blog.repository_contracts


#============================================
def github_entry(repository: str, created_at: str = "2020-01-01T00:00:00Z", **states: bool) -> dict:
	"""Return a complete GitHub-shaped owner repository record."""
	owner = repository.split("/", 1)[0]
	return {
		"archived": states.get("archived", False), "clone_url": f"https://github.com/{repository}.git",
		"created_at": created_at, "disabled": states.get("disabled", False), "fork": states.get("fork", False),
		"full_name": repository, "html_url": f"https://github.com/{repository}", "owner": {"login": owner},
		"private": states.get("private", False),
	}


#============================================
def test_roster_filters_ineligible_repositories() -> None:
	"""Discovery retains public owner repositories and records forks explicitly."""
	payload = [
		github_entry("vosslab/active"), github_entry("vosslab/fork", fork=True),
		github_entry("vosslab/private", private=True), github_entry("vosslab/archived", archived=True),
		github_entry("vosslab/disabled", disabled=True),
	]

	roster = daily_blog.repositories.repository_payload_to_roster("vosslab", payload)

	assert [item.repository for item in roster.repositories] == ["vosslab/active", "vosslab/fork"]


#============================================
@pytest.mark.parametrize(
	("created_at", "expected"),
	(
		("2026-08-26T04:59:59Z", False), ("2026-08-26T05:00:00Z", True),
		("2026-08-27T04:59:59Z", True), ("2026-08-27T05:00:00Z", False),
	),
)
def test_repository_creation_uses_central_report_day_boundaries(created_at: str, expected: bool) -> None:
	"""Creation time is salient only inside the selected Central report day."""
	start, end = daily_blog.activity.build_date_window("2026-08-26", "America/Chicago")

	assert daily_blog.activity._creation_event({"created_at": created_at}, start, end).occurred_in_report_window is expected


#============================================
def test_discovery_requests_a_fresh_owner_roster(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
	"""The selected report day starts from the owner roster rather than stale cache data."""
	calls: list[bool] = []

	class FakeGitHubClient:
		"""Offline stand-in for the owner-list request."""

		#============================================
		def __init__(self, _token: str, *, cache_dir: str) -> None:
			"""Construct the stand-in."""

		#============================================
		def list_repos(self, _owner: str, use_cache: bool = True) -> list[dict]:
			"""Record the requested cache boundary."""
			calls.append(use_cache)
			return [github_entry("vosslab/project")]

	monkeypatch.setattr(daily_blog.repositories.podlib.github_client, "GitHubClient", FakeGitHubClient)
	monkeypatch.setattr(daily_blog.repositories.podlib.runtime_credentials, "get_github_token", lambda: "test-token")

	daily_blog.repositories.discover_owner_repositories("vosslab", str(tmp_path))

	assert calls == [False]


#============================================
def test_discovery_never_constructs_an_anonymous_github_client(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
	"""Production owner discovery fails before transport when its runtime token is unavailable."""
	constructed = False

	class FakeGitHubClient:
		"""Stand-in that records whether anonymous transport was attempted."""

		#============================================
		def __init__(self, *_args: object, **_kwargs: object) -> None:
			nonlocal constructed
			constructed = True

	monkeypatch.setattr(
		daily_blog.repositories.podlib.runtime_credentials,
		"get_github_token",
		lambda: (_ for _ in ()).throw(RuntimeError("runtime token unavailable")),
	)
	monkeypatch.setattr(daily_blog.repositories.podlib.github_client, "GitHubClient", FakeGitHubClient)

	with pytest.raises(RuntimeError, match="runtime token unavailable"):
		daily_blog.repositories.discover_owner_repositories("vosslab", str(tmp_path))

	assert constructed is False

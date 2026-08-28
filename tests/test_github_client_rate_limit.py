import os
import sys
import pathlib
from types import SimpleNamespace

# PIP3 modules
import pytest

import file_utils as git_file_utils


REPO_ROOT = git_file_utils.get_repo_root()
PIPELINE_DIR = os.path.join(REPO_ROOT, "pipeline")
if PIPELINE_DIR not in sys.path:
	sys.path.insert(0, PIPELINE_DIR)

from podlib import github_client


#============================================
def test_client_requires_runtime_authentication(tmp_path: pathlib.Path) -> None:
	"""GitHub access must fail locally instead of making anonymous requests."""
	with pytest.raises(RuntimeError, match="requires the runtime GITHUB_TOKEN"):
		github_client.GitHubClient("", cache_dir=str(tmp_path))


#============================================
def make_stub_client(overview_object: object) -> github_client.GitHubClient:
	"""
	Build GitHubClient instance with mocked get_rate_limit response.
	"""
	client = github_client.GitHubClient.__new__(github_client.GitHubClient)
	client.log_fn = None
	client._rate_check_count = 0
	client._low_remaining_threshold = 5
	client.client = SimpleNamespace(get_rate_limit=lambda: overview_object)
	return client


#============================================
def test_fresh_repository_list_translates_lazy_rate_limit_error() -> None:
	"""Fresh owner discovery must retain the client's bounded 403 contract."""
	overview = SimpleNamespace(core=SimpleNamespace(remaining=0, reset="2026-08-28T07:30:00+00:00"))

	class FakeGithubError(Exception):
		"""Minimal PyGithub-shaped rate-limit exception."""

		status = 403

	class LazyRepository:
		"""Raise when PyGithub materializes a missing paginated-list field."""

		@property
		def archived(self) -> bool:
			"""Simulate a field completion exhausting the API limit."""
			raise FakeGithubError("rate limited")

	user = SimpleNamespace(get_repos=lambda **_kwargs: [LazyRepository()])
	client = make_stub_client(overview)
	client.client.get_user = lambda _owner: user
	client._github_exception_class = FakeGithubError
	client._max_proactive_sleep_seconds = 0
	client.sleep_request_jitter = lambda _context: None

	with pytest.raises(github_client.RateLimitError, match="GET /users/vosslab/repos"):
		client.list_repos("vosslab", use_cache=False)


#============================================
@pytest.mark.parametrize("raw_remaining", (True, "5000", 5000.0, -1))
def test_rate_limit_snapshot_rejects_noncanonical_provider_quota(raw_remaining: object) -> None:
	"""Provider quota values must not be coerced into valid authenticated evidence."""
	overview = SimpleNamespace(
		core=SimpleNamespace(remaining=raw_remaining, reset="2026-08-28T07:30:00+00:00"),
	)
	client = make_stub_client(overview)

	with pytest.raises(RuntimeError, match="invalid core remaining"):
		client.get_core_rate_limit_snapshot()

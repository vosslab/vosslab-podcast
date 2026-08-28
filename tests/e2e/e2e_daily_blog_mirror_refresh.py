#!/usr/bin/env python3
"""Verify durable mirror identity against a temporary physical Git cache."""

# Standard Library
import os
import pathlib
import tempfile
import subprocess

# local repo modules
import daily_blog.mirrors
import daily_blog.repository_contracts


#============================================
def run_git(repository: pathlib.Path, arguments: list[str], environment: dict | None = None) -> str:
	"""Run one Git command against a temporary cache."""
	process_environment = os.environ.copy()
	if environment:
		process_environment.update(environment)
	result = subprocess.run(
		["git", "-C", str(repository), *arguments],
		check=True,
		text=True,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		env=process_environment,
	)
	return result.stdout.strip()


#============================================
def make_cache(root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
	"""Create one physical cache with an exact default object and GitHub origin."""
	cache_root = root / "mirrors"
	repository = cache_root / "vosslab" / "sample"
	repository.mkdir(parents=True)
	run_git(repository, ["init", "-b", "main"])
	run_git(repository, ["config", "user.name", "Dr. Neil R Voss"])
	run_git(repository, ["config", "user.email", "vosslab@users.noreply.github.com"])
	run_git(repository, ["remote", "add", "origin", "https://github.com/vosslab/sample.git"])
	(repository / "README.md").write_text("# Sample\n", encoding="utf-8")
	environment = {
		"GIT_AUTHOR_DATE": "2026-08-23T12:00:00-05:00",
		"GIT_COMMITTER_DATE": "2026-08-23T12:00:00-05:00",
	}
	run_git(repository, ["add", "."], environment)
	run_git(repository, ["commit", "-m", "Create sample"], environment)
	return cache_root, repository


#============================================
def main() -> None:
	"""Verify the manifest names the exact available default object."""
	with tempfile.TemporaryDirectory(prefix="daily-blog-mirror-e2e-") as temporary:
		cache_root, repository = make_cache(pathlib.Path(temporary))
		record = daily_blog.repository_contracts.RepositoryRecord.from_dict({
			"repository": "vosslab/sample",
			"repository_url": "https://github.com/vosslab/sample",
			"clone_url": "https://github.com/vosslab/sample.git",
			"created_at": "2020-01-01T00:00:00Z",
			"is_fork": False,
		})
		roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [record])
		manager = daily_blog.mirrors.MirrorManager(str(cache_root), roster)
		entry = manager.refresh_all(refresh=False)[0]
		assert entry["repository"] == "vosslab/sample"
		assert (
			entry["default_revision"] == run_git(repository, ["rev-parse", "HEAD"])
			and entry["object_available"]
			and entry["refresh_result"] == "skipped"
		)
	print("Daily blog mirror refresh E2E passed.")


if __name__ == "__main__":
	main()

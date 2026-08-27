#!/usr/bin/env python3
"""Exact Git-object evidence provider tests against temporary repositories."""

# Standard Library
import os
import subprocess
import pathlib
import tempfile

# local repo modules
import daily_blog.activity
import daily_blog.evidence
import daily_blog.schema


#============================================
def run_git(
	repository: pathlib.Path,
	arguments: list[str],
	environment: dict | None = None,
) -> str:
	"""Run one Git command against a temporary repository."""
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
def commit(repository: pathlib.Path, message: str, timestamp: str) -> str:
	"""Commit all temporary content with stable authorship."""
	environment = {"GIT_AUTHOR_DATE": timestamp, "GIT_COMMITTER_DATE": timestamp}
	run_git(repository, ["add", "."], environment)
	run_git(repository, ["commit", "-m", message], environment)
	return run_git(repository, ["rev-parse", "HEAD"])


#============================================
def make_repository(
	tmp_path: pathlib.Path,
	include_changelog: bool = True,
) -> tuple[pathlib.Path, dict, daily_blog.schema.RepositoryActivity]:
	"""Create a baseline and two selected-date commits with representative evidence."""
	repository = tmp_path / "evidence-repository"
	repository.mkdir()
	run_git(repository, ["init", "-b", "main"])
	run_git(repository, ["config", "user.name", "Dr. Neil R Voss"])
	run_git(repository, ["config", "user.email", "vosslab@users.noreply.github.com"])
	run_git(
		repository,
		["remote", "add", "origin", "https://github.com/vosslab/evidence-repository.git"],
	)
	(repository / "docs" / "screenshots").mkdir(parents=True)
	(repository / "README.md").write_text(
		"# Evidence repository\n\nBaseline context.\n",
		encoding="utf-8",
	)
	(repository / "baseline.txt").write_text("prior day\n", encoding="utf-8")
	commit(repository, "Create baseline", "2026-08-22T12:00:00-05:00")
	if include_changelog:
		(repository / "docs" / "CHANGELOG.md").write_text(
			"## 2026-08-23\n\n- Added exact evidence.\n\n"
			+ "## Release notes\n\nUnrelated prose.\n",
			encoding="utf-8",
		)
	(repository / "src.py").write_text("VALUE = 1\n", encoding="utf-8")
	commit(repository, "Add exact evidence", "2026-08-23T09:00:00-05:00")
	if include_changelog:
		(repository / "docs" / "CHANGELOG.md").write_text(
			"## 2026-08-23\n\n- Added exact evidence.\n\n"
			+ "## 2026-08-23 continued\n\n- Added atomic staging.\n\n"
			+ "## 2026-08-22\n\n- Older account.\n",
			encoding="utf-8",
		)
	(repository / "docs" / "DESIGN.md").write_text(
		"# Design\n\nThe bundle is the repository boundary.\n",
		encoding="utf-8",
	)
	(repository / "docs" / "screenshots" / "proof.png").write_bytes(b"\x89PNG\r\n\x1a\nproof")
	final_commit = commit(repository, "Add atomic staging", "2026-08-23T15:00:00-05:00")
	mirror = {
		"repository": "vosslab/evidence-repository",
		"repository_url": "https://github.com/vosslab/evidence-repository.git",
		"cache_path": str(repository),
		"refresh_result": "skipped",
		"refresh_error": "",
		"default_revision": final_commit,
		"object_available": True,
		"ref_fingerprint": "f" * 64,
		"refreshed_at": "2026-08-24T08:00:00Z",
	}
	activities = daily_blog.activity.locate_activity(
		"2026-08-23",
		"America/Chicago",
		[mirror],
		("Dr. Neil R Voss",),
		("vosslab@users.noreply.github.com",),
	)
	return repository, mirror, activities[0]


#============================================
def budgets() -> dict[str, int]:
	"""Return complete explicit provider budgets."""
	return {
		"changed_documentation_chars": 8000,
		"diff_chars": 12000,
		"readme_context_chars": 4000,
		"commit_metadata_chars": 4000,
		"per_item_chars": 6000,
		"supporting_total_chars": 24000,
		"author_context_chars": 48000,
		"referee_context_chars": 64000,
		"screenshot_count": 4,
	}


#============================================
def verify_changelog_contract(
	repository: pathlib.Path,
	activity: daily_blog.schema.RepositoryActivity,
	changelog: list[daily_blog.schema.EvidenceItem],
) -> None:
	"""Verify exact-revision dated sections and their blob identity."""
	assert (
		"Added exact evidence" in changelog[0].content
		and "Added atomic staging" in changelog[0].content
		and "Older account" not in changelog[0].content
	)
	assert changelog[0].blob_hash == run_git(
		repository, ["rev-parse", f"{changelog[0].commit}:docs/CHANGELOG.md"]
	)


#============================================
def verify_supporting_contract(
	activity: daily_blog.schema.RepositoryActivity,
	documentation: list[daily_blog.schema.EvidenceItem],
	diff: list[daily_blog.schema.EvidenceItem],
	metadata: list[daily_blog.schema.EvidenceItem],
) -> None:
	"""Verify supporting sources stay within the selected commit boundary."""
	assert {item.kind for item in documentation} == {"changed_documentation", "readme_context"}
	assert (
		any("docs/DESIGN.md" in item.content for item in diff)
		and all("baseline.txt" not in item.content for item in diff)
		and {item.commit for item in metadata} == {commit.sha for commit in activity.commits}
	)


#============================================
def verify_binary_contract(
	screenshots: list[daily_blog.schema.EvidenceItem],
	assets: dict[str, bytes],
) -> None:
	"""Verify a selected screenshot retains its exact bundle asset bytes."""
	assert screenshots
	assert assets[screenshots[0].asset_path].startswith(b"\x89PNG")


#============================================
def verify_providers(root: pathlib.Path) -> None:
	"""Exercise every provider against exact selected Git objects."""
	repository, _mirror, activity = make_repository(root)
	snapshot = daily_blog.evidence.GitSnapshot(activity)
	changelog = daily_blog.evidence.ChangelogEvidenceProvider("2026-08-23").collect(
		activity, snapshot
	)
	documentation = daily_blog.evidence.DocumentationEvidenceProvider().collect(
		activity, snapshot
	)
	diff = daily_blog.evidence.DiffEvidenceProvider(12000).collect(activity, snapshot)
	screenshots, assets = daily_blog.evidence.ScreenshotEvidenceProvider("2026-08-23").collect(
		activity, snapshot
	)
	metadata = daily_blog.evidence.CommitMetadataEvidenceProvider().collect(activity, snapshot)

	verify_changelog_contract(repository, activity, changelog)
	verify_supporting_contract(activity, documentation, diff, metadata)
	verify_binary_contract(screenshots, assets)


#============================================
def verify_secondary_evidence(root: pathlib.Path) -> None:
	"""A complete packet remains useful when no dated changelog section exists."""
	_repository, mirror, activity = make_repository(root, include_changelog=False)
	assembler = daily_blog.evidence.EvidenceAssembler(
		"2026-08-23", "America/Chicago", budgets()
	)

	packet, assets = assembler.assemble([mirror], [activity])

	assert packet.complete and all(item.kind != "dated_changelog" for item in packet.items)
	assert (
		packet.items[0].kind == "changed_documentation"
		and any(item.kind == "diff" for item in packet.items)
		and assets
	)


#============================================
def verify_non_linear_activity(root: pathlib.Path) -> None:
	"""Independent same-day branches retain both exact parent diffs."""
	repository = root / "branched-repository"
	repository.mkdir()
	run_git(repository, ["init", "-b", "main"])
	run_git(repository, ["config", "user.name", "Dr. Neil R Voss"])
	run_git(repository, ["config", "user.email", "vosslab@users.noreply.github.com"])
	run_git(
		repository,
		["remote", "add", "origin", "https://github.com/vosslab/branched-repository.git"],
	)
	(repository / "README.md").write_text("# Branched evidence\n", encoding="utf-8")
	baseline = commit(repository, "Create baseline", "2026-08-22T12:00:00-05:00")
	(repository / "branch-a.txt").write_text("branch A\n", encoding="utf-8")
	branch_a = commit(repository, "Record branch A", "2026-08-23T09:00:00-05:00")
	run_git(repository, ["checkout", "-b", "branch-b", baseline])
	(repository / "docs").mkdir()
	(repository / "docs" / "BRANCH_B.md").write_text("# Branch B\n", encoding="utf-8")
	branch_b = commit(repository, "Record branch B", "2026-08-23T10:00:00-05:00")
	mirror = {
		"repository": "vosslab/branched-repository",
		"repository_url": "https://github.com/vosslab/branched-repository.git",
		"cache_path": str(repository),
		"refresh_result": "skipped",
		"refresh_error": "",
		"default_revision": branch_b,
		"object_available": True,
		"ref_fingerprint": "f" * 64,
		"refreshed_at": "2026-08-24T08:00:00Z",
	}
	activity = daily_blog.activity.locate_activity(
		"2026-08-23",
		"America/Chicago",
		[mirror],
		("Dr. Neil R Voss",),
		("vosslab@users.noreply.github.com",),
	)[0]
	packet, _assets = daily_blog.evidence.EvidenceAssembler(
		"2026-08-23", "America/Chicago", budgets()
	).assemble([mirror], [activity])
	diff_content = "\n".join(item.content for item in packet.items if item.kind == "diff")

	assert set(activity.snapshot_commits) == {branch_a, branch_b}
	assert "branch-a.txt" in diff_content and "docs/BRANCH_B.md" in diff_content


#============================================
def main() -> None:
	"""Run durable exact-Git evidence provider checks outside the pytest fast lane."""
	with tempfile.TemporaryDirectory(prefix="daily-blog-evidence-e2e-") as temporary:
		root = pathlib.Path(temporary)
		primary = root / "primary"
		secondary = root / "secondary"
		non_linear = root / "non-linear"
		primary.mkdir()
		secondary.mkdir()
		non_linear.mkdir()
		verify_providers(primary)
		verify_secondary_evidence(secondary)
		verify_non_linear_activity(non_linear)
	print("Daily blog exact-Git evidence E2E passed.")


if __name__ == "__main__":
	main()

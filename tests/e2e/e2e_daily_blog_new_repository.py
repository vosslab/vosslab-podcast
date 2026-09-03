#!/usr/bin/env python3
"""Exercise the offline Aug. 26 new-repository discovery regression with real Git."""

# Standard Library
import os
import pathlib
import subprocess
import tempfile

# local repo modules
import daily_blog.activity
import daily_blog.evidence
import daily_blog.mirrors
import daily_blog.projection
import daily_blog.repositories


#============================================
def run_git(repository: pathlib.Path, arguments: list[str], environment: dict | None = None) -> str:
	"""Run one bounded Git command against an E2E-owned repository."""
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
def make_source(root: pathlib.Path, name: str, message: str) -> pathlib.Path:
	"""Create one local bare source that Git resolves from the canonical GitHub URL."""
	worktree = root / "worktrees" / name
	worktree.mkdir(parents=True)
	run_git(worktree, ["init", "-b", "main"])
	run_git(worktree, ["config", "user.name", "Dr. Neil R Voss"])
	run_git(worktree, ["config", "user.email", "vosslab@users.noreply.github.com"])
	(worktree / "docs").mkdir()
	(worktree / "README.md").write_text(f"# {name}\n", encoding="utf-8")
	(worktree / "docs" / "CHANGELOG.md").write_text(
		f"## 2026-08-26\n\n- {message}.\n", encoding="utf-8"
	)
	environment = {
		"GIT_AUTHOR_DATE": "2026-08-26T21:20:00-05:00",
		"GIT_COMMITTER_DATE": "2026-08-26T21:20:00-05:00",
	}
	run_git(worktree, ["add", "."], environment)
	run_git(worktree, ["commit", "-m", message], environment)
	source = root / "sources" / f"{name}.git"
	source.parent.mkdir(exist_ok=True)
	result = subprocess.run(
		["git", "clone", "--bare", str(worktree), str(source)],
		check=True,
		text=True,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
	)
	if result.returncode:
		raise RuntimeError("Unable to create E2E Git source.")
	return source


#============================================
def collection_limits() -> dict[str, int]:
	"""Return compact deterministic evidence limits for the focused E2E."""
	return {
		"changed_documentation_chars": 4000,
		"diff_chars": 6000,
		"readme_context_chars": 2000,
		"commit_metadata_chars": 2000,
		"per_item_chars": 4000,
		"supporting_total_chars": 12000,
		"screenshot_count": 1,
	}


#============================================
def install_github_url_rewrite(root: pathlib.Path) -> tuple[str | None, pathlib.Path]:
	"""Map canonical GitHub clone URLs to E2E-local bare repositories without network access."""
	config_path = root / "gitconfig"
	config_path.write_text(
		"[url \"file://" + str(root / "sources") + "/\"]\n"
		+ "\tinsteadOf = https://github.com/vosslab/\n",
		encoding="utf-8",
	)
	previous = os.environ.get("GIT_CONFIG_GLOBAL")
	os.environ["GIT_CONFIG_GLOBAL"] = str(config_path)
	return previous, config_path


#============================================
def restore_github_url_rewrite(previous: str | None) -> None:
	"""Restore the parent process environment after the E2E-local URL mapping."""
	if previous is None:
		os.environ.pop("GIT_CONFIG_GLOBAL", None)
	else:
		os.environ["GIT_CONFIG_GLOBAL"] = previous


#============================================
def main() -> None:
	"""Prove a roster-only new game is cloned, surfaced, and story-prioritized."""
	with tempfile.TemporaryDirectory(prefix="daily-blog-new-repository-e2e-") as temporary:
		root = pathlib.Path(temporary)
		make_source(root, "cancer-clicker", "Create the StVC cancer clicker game")
		make_source(root, "routine-tools", "Tidy routine test helpers")
		cache_root = root / "mirrors"
		legacy_cache = cache_root / "cancer-clicker"
		legacy_cache.mkdir(parents=True)
		run_git(legacy_cache, ["init", "-b", "main"])
		payload = [
			{
				"archived": False,
				"clone_url": "https://github.com/vosslab/routine-tools.git",
				"created_at": "2020-01-01T00:00:00Z",
				"disabled": False,
				"fork": False,
				"full_name": "vosslab/routine-tools",
				"html_url": "https://github.com/vosslab/routine-tools",
				"owner": {"login": "vosslab"},
				"private": False,
			},
			{
				"archived": False,
				"clone_url": "https://github.com/vosslab/cancer-clicker.git",
				"created_at": "2026-08-27T02:10:27Z",
				"disabled": False,
				"fork": False,
				"full_name": "vosslab/cancer-clicker",
				"html_url": "https://github.com/vosslab/cancer-clicker",
				"owner": {"login": "vosslab"},
				"private": False,
			},
		]
		roster = daily_blog.repositories.repository_payload_to_roster("vosslab", payload)
		previous, _config_path = install_github_url_rewrite(root)
		try:
			manager = daily_blog.mirrors.MirrorManager(str(cache_root), roster)
			manager._ensure_roster_clones()
		finally:
			restore_github_url_rewrite(previous)
		for record in roster.repositories:
			run_git(
				cache_root / "vosslab" / record.repository.split("/", 1)[1],
				["remote", "set-url", "origin", record.clone_url],
			)
		mirrors = manager.refresh_all(refresh=False)

		created_cache = cache_root / "vosslab" / "cancer-clicker"
		assert daily_blog.mirrors.is_git_cache(str(legacy_cache))
		assert daily_blog.mirrors.is_git_cache(str(created_cache))
		assert [entry["repository"] for entry in mirrors] == [
			"vosslab/cancer-clicker", "vosslab/routine-tools",
		]
		assert all(entry["cache_path"].startswith(str(cache_root / "vosslab")) for entry in mirrors)

		activities = daily_blog.activity.locate_activity(
			"2026-08-26",
			"America/Chicago",
			mirrors,
			[
				{"repository": mirror["repository"], "sha": sha}
				for mirror in mirrors
				for sha in run_git(
					pathlib.Path(mirror["cache_path"]), ["rev-list", "--all"],
				).splitlines()
			],
			"vosslab",
		)
		packet, _assets = daily_blog.evidence.EvidenceAssembler(
			"2026-08-26", "America/Chicago", collection_limits()
		).assemble(mirrors, activities)
		projection = daily_blog.projection.build_projection(
			packet,
			{"context_chars": 30000, "excerpt_chars": 3000, "commit_subject_chars": 240},
		)

		assert projection.repositories[0].repository == "vosslab/cancer-clicker"
		assert projection.repositories[0].story_signals == ("new_source_repository",)
		assert "2026-08-27T02:10:27Z" in projection.render_context()

		run_git(created_cache, ["remote", "set-url", "origin", "https://github.com/other/game.git"])
		try:
			manager.refresh_all(refresh=False)
		except RuntimeError as error:
			assert "owner roster" in str(error)
		else:
			raise RuntimeError("Roster origin mismatch was accepted.")
	print("Daily-blog new-repository E2E passed.")


if __name__ == "__main__":
	main()

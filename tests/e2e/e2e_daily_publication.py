#!/usr/bin/env python3
"""Run a synthetic date through evidence, bundle, import, and strict MkDocs build."""

# Standard Library
import os
import shutil
import pathlib
import tempfile
import subprocess

# local repo modules
import daily_blog.schema
import daily_blog.repository_contracts
import daily_blog.activity
import daily_blog.evidence
import daily_blog.projection
import daily_blog.publisher
import daily_blog.bundles
import daily_blog.editorial
import daily_blog.io_utils


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PUBLISHER_ROOT = REPO_ROOT.parent / "vosslab-daily-blog"


#============================================
def run_git(repository: pathlib.Path, arguments: list[str], environment: dict | None = None) -> str:
	"""Run one synthetic repository command and return stdout."""
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
	"""Commit all synthetic content under one deterministic identity and time."""
	environment = {
		"GIT_AUTHOR_DATE": timestamp,
		"GIT_COMMITTER_DATE": timestamp,
	}
	run_git(repository, ["add", "."], environment)
	run_git(repository, ["commit", "-m", message], environment)
	return run_git(repository, ["rev-parse", "HEAD"])


#============================================
def make_repository(root: pathlib.Path) -> tuple[pathlib.Path, str]:
	"""Create two same-day commits with changelog, documentation, and image evidence."""
	repository = root / "vosslab" / "synthetic-project"
	repository.mkdir(parents=True)
	run_git(repository, ["init", "-b", "main"])
	run_git(repository, ["config", "user.name", "Dr. Neil R Voss"])
	run_git(repository, ["config", "user.email", "vosslab@users.noreply.github.com"])
	run_git(
		repository,
		["remote", "add", "origin", "https://github.com/vosslab/synthetic-project.git"],
	)
	(repository / "docs" / "screenshots").mkdir(parents=True)
	(repository / "README.md").write_text(
		"# Synthetic project\n\nExact evidence demo.\n",
		encoding="utf-8",
	)
	(repository / "docs" / "CHANGELOG.md").write_text(
		"## 2026-08-23\n\n- Added the first durable contract.\n",
		encoding="utf-8",
	)
	commit(repository, "Add durable publication contract", "2026-08-23T10:00:00-05:00")
	(repository / "docs" / "CHANGELOG.md").write_text(
		"## 2026-08-23\n\n- Added the first durable contract.\n\n"
		+ "## 2026-08-23 continued\n\n- Added atomic publisher staging.\n",
		encoding="utf-8",
	)
	(repository / "docs" / "DESIGN.md").write_text(
		"# Design\n\nThe bundle is the complete repository boundary.\n",
		encoding="utf-8",
	)
	(repository / "docs" / "screenshots" / "proof.png").write_bytes(b"\x89PNG\r\n\x1a\nproof")
	final_commit = commit(
		repository,
		"Stage the complete publisher tree",
		"2026-08-23T15:00:00-05:00",
	)
	return repository, final_commit


#============================================
def synthetic_roster() -> daily_blog.repository_contracts.RepositoryRoster:
	"""Return the authoritative synthetic owner roster used by the E2E."""
	record = daily_blog.repository_contracts.RepositoryRecord.from_dict({
		"repository": "vosslab/synthetic-project",
		"repository_url": "https://github.com/vosslab/synthetic-project",
		"clone_url": "https://github.com/vosslab/synthetic-project.git",
		"created_at": "2020-01-01T00:00:00Z",
		"is_fork": False,
	})
	return daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [record])


#============================================
def collection_limits() -> dict[str, int]:
	"""Return explicit compact E2E evidence collection limits."""
	return {
		"changed_documentation_chars": 8000,
		"diff_chars": 12000,
		"readme_context_chars": 4000,
		"commit_metadata_chars": 4000,
		"per_item_chars": 6000,
		"supporting_total_chars": 24000,
		"screenshot_count": 4,
	}


#============================================
def projection_limits() -> dict[str, int]:
	"""Return deterministic E2E editorial projection limits."""
	return {
		"context_chars": 32000,
		"excerpt_chars": 4000,
		"commit_subject_chars": 240,
	}


#============================================
def prompt_limits() -> dict[str, int]:
	"""Return complete author and referee prompt envelope limits."""
	return {"author_chars": 48000, "referee_chars": 64000}


#============================================
def valid_post(
	packet: daily_blog.schema.EvidencePacket,
	projection: daily_blog.schema.EditorialProjection,
	run_id: str,
	title: str,
) -> str:
	"""Return one complete final article for reusable editorial E2E work."""
	evidence_id = packet.items[0].evidence_id
	intro_sentence = (
		"I connected exact evidence to durable ownership and explained why the verified change "
		"matters to readers now. "
	)
	detail_sentence = (
		"I followed the strongest development thread through the concrete decision, its practical "
		"effect, and the current state of the work. "
	)
	intro = (intro_sentence * 3).strip()
	first_section = (detail_sentence * 9).strip()
	second_section = (detail_sentence * 9).strip()
	repositories = ", ".join(activity.repository for activity in packet.activity)
	post = (
		"---\n"
		+ f"date: {packet.report_date}\n"
		+ "slug: durable-bundles\n"
		+ f"generator_run: {run_id}\n"
		+ "evidence_manifest: evidence.json\n"
		+ "editorial_projection: editorial_projection.json\n"
		+ "---\n\n"
		+ f"# {title}\n\n"
		+ f"{intro} <!-- evidence: {evidence_id} -->\n\n"
		+ "<!-- more -->\n\n"
		+ "## Durable ownership\n\n"
		+ f"{first_section} <!-- evidence: {evidence_id} -->\n\n"
		+ "## Where the work stands\n\n"
		+ f"{second_section} <!-- evidence: {evidence_id} -->\n\n"
		+ "## Project coverage\n\n"
		+ f"I recorded {repositories} in the evidence packet. "
		+ f"<!-- evidence: {evidence_id} -->\n"
	)
	return post


#============================================
def initialize_publisher(root: pathlib.Path) -> None:
	"""Create the complete minimal MkDocs source tree owned by the importer."""
	shutil.copytree(PUBLISHER_ROOT / "scripts", root / "scripts")
	shutil.copy2(PUBLISHER_ROOT / "source_me.sh", root / "source_me.sh")
	(root / "docs" / "blog" / "posts").mkdir(parents=True)
	(root / "docs" / "stylesheets").mkdir()
	(root / "docs" / "index.md").write_text("# Daily work log\n", encoding="utf-8")
	(root / "docs" / "status.md").write_text("# Publication status\n", encoding="utf-8")
	(root / "docs" / "operations.md").write_text("# Operations\n", encoding="utf-8")
	(root / "docs" / "CODE_ARCHITECTURE.md").write_text(
		"# Code architecture\n", encoding="utf-8"
	)
	(root / "docs" / "blog" / "index.md").write_text("# Work log\n", encoding="utf-8")
	(root / "docs" / "stylesheets" / "extra.css").write_text("body {}\n", encoding="utf-8")
	(root / "data" / "publications").mkdir(parents=True)
	(root / "generated" / "staging").mkdir(parents=True)
	(root / "generated" / "releases" / "old").mkdir(parents=True)
	(root / "generated" / "releases" / "old" / "index.html").write_text(
		"old", encoding="utf-8"
	)
	(root / "site").symlink_to("generated/releases/old")
	shutil.copy2(PUBLISHER_ROOT / "mkdocs.yml", root / "mkdocs.yml")
	subprocess.run(
		["git", "init", "--quiet", str(root)],
		check=True,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
	)


#============================================
def main() -> None:
	"""Exercise the complete cross-repository publication contract."""
	if not (PUBLISHER_ROOT / "scripts" / "import_publication_bundle.py").is_file():
		raise RuntimeError("Sibling daily-blog importer is unavailable.")
	with tempfile.TemporaryDirectory(prefix="daily-publication-e2e-") as temporary:
		root = pathlib.Path(temporary)
		repository, final_commit = make_repository(root)
		mirror_entry = {
			"repository": "vosslab/synthetic-project",
			"repository_url": "https://github.com/vosslab/synthetic-project",
			"clone_url": "https://github.com/vosslab/synthetic-project.git",
			"created_at": "2020-01-01T00:00:00Z",
			"is_fork": False,
			"roster_id": synthetic_roster().roster_id,
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
			[mirror_entry],
			("Dr. Neil R Voss",),
			("vosslab@users.noreply.github.com",),
		)
		assembler = daily_blog.evidence.EvidenceAssembler(
			"2026-08-23", "America/Chicago", collection_limits()
		)
		packet, assets = assembler.assemble([mirror_entry], activities)
		projection = daily_blog.projection.build_projection(packet, projection_limits())
		post = valid_post(packet, projection, "synthetic-run", "Exact ownership survives")
		decision = daily_blog.editorial.EditorialDecision(
			winner="A",
			reason="Candidate A follows the exact evidence and complete editorial contract.",
			evidence_quality="high",
			confidence=1.0,
			projection_id=projection.projection_id,
			post=post,
			anonymous_mapping={"A": 0},
		)
		approved_candidate = daily_blog.editorial.CandidateResult(
			private_route="synthetic",
			projection_id=projection.projection_id,
			post=post,
			post_hash=daily_blog.io_utils.sha256_text(post),
			valid=True,
			issues=(),
		)
		writer = daily_blog.bundles.BundleWriter(
			str(root / "output"),
			"vosslab",
			daily_blog.bundles.generator_revision(str(REPO_ROOT)),
		)
		bundle_path, bundle = writer.write(
			"synthetic-run",
			packet,
			projection,
			assets,
			[approved_candidate, approved_candidate],
			decision,
			synthetic_roster(),
		)
		publisher_root = root / "publisher"
		publisher_root.mkdir()
		initialize_publisher(publisher_root)
		result = daily_blog.publisher.import_bundle(str(publisher_root), bundle_path)
		assert result["bundle_sha256"] == bundle["bundle_sha256"]
		archive = publisher_root / "data" / "publication_bundles" / bundle["report_date"]
		for name in ("bundle.json", "evidence.json", "repository_roster.json", "editorial_projection.json", "post.md"):
			assert (archive / name).read_bytes() == (pathlib.Path(bundle_path) / name).read_bytes()
		assert (
			publisher_root / "docs" / "blog" / "posts" / f"{bundle['report_date']}.md"
		).read_bytes() == (pathlib.Path(bundle_path) / "post.md").read_bytes()
		release = publisher_root / "generated" / "releases" / bundle["report_date"]
		assert (publisher_root / "site").is_symlink()
		assert (publisher_root / "site").resolve() == release.resolve()
		assert (release / "index.html").is_file()
		for asset in bundle["assets"]:
			asset_name = pathlib.PurePosixPath(asset["path"]).name
			installed = (
				publisher_root
				/ "docs"
				/ "assets"
				/ "publications"
				/ bundle["report_date"]
				/ asset_name
			)
			assert installed.is_file()
		print("Daily publication E2E passed.")


if __name__ == "__main__":
	main()

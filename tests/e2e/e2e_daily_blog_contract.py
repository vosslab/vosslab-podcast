#!/usr/bin/env python3
"""Exercise the active v3 producer bundle at the sibling importer boundary."""

# Standard Library
import importlib.util
import json
import pathlib
import shutil
import sys
import tempfile

# local repo modules
import daily_blog.bundles
import daily_blog.contracts
import daily_blog.editorial
import daily_blog.io_utils
import daily_blog.repository_contracts
import daily_blog.schema


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PUBLISHER_ROOT = REPO_ROOT.parent / "vosslab-daily-blog"
REPORT_DATE = "2026-08-23"


#============================================
def publisher_importer() -> object:
	"""Load the sibling's public importer through its package boundary."""
	publisher_root = str(PUBLISHER_ROOT)
	if publisher_root not in sys.path:
		sys.path.insert(0, publisher_root)
	importer_path = PUBLISHER_ROOT / "scripts" / "import_publication_bundle.py"
	spec = importlib.util.spec_from_file_location("offline_publisher_importer", importer_path)
	if spec is None or spec.loader is None:
		raise RuntimeError("Publisher importer is unavailable for contract testing.")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


#============================================
def make_packet_and_projection() -> tuple[
	daily_blog.schema.EvidencePacket,
	daily_blog.schema.EditorialProjection,
	daily_blog.repository_contracts.RepositoryRoster,
]:
	"""Create complete v3 evidence with the importer-required Git provenance."""
	repository = "vosslab/synthetic-maker"
	repository_url = "https://github.com/vosslab/synthetic-maker"
	roster_record = daily_blog.repository_contracts.RepositoryRecord.from_dict({
		"repository": repository,
		"repository_url": repository_url,
		"clone_url": repository_url + ".git",
		"created_at": "2020-01-01T00:00:00Z",
		"is_fork": False,
	})
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [roster_record])
	commit = "c" * 40
	parent = "d" * 40
	content = "## 2026-08-23\n\n- Bound the preview to the saved document state.\n"
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", repository, commit, "docs/CHANGELOG.md", "b" * 40,
		content, "offline-contract",
	)
	activity = daily_blog.schema.RepositoryActivity(
		repository=repository,
		repository_url=repository_url,
		cache_path="/synthetic/mirrors/vosslab/synthetic-maker",
		default_revision=commit,
		commits=(daily_blog.schema.CommitActivity(
			sha=commit, parents=(parent,), author_name="Neil",
			author_email="neil@example.invalid",
			author_timestamp="2026-08-23T12:00:00-05:00",
			committer_timestamp="2026-08-23T12:00:00-05:00",
			message="Bind preview state to the saved document",
		),),
		revision_ranges=(daily_blog.schema.RevisionRange(parent, commit),),
		snapshot_commits=(commit,),
		is_fork=False,
		lifecycle_events=(daily_blog.repository_contracts.RepositoryLifecycleEvent(
			"repository_created", "2020-01-01T00:00:00Z", False, "github_owner_roster",
		),),
	)
	mirror = {
		"repository": repository, "repository_url": repository_url,
		"clone_url": repository_url + ".git", "created_at": "2020-01-01T00:00:00Z",
		"is_fork": False, "roster_id": roster.roster_id, "cache_path": activity.cache_path,
		"refresh_result": "skipped", "refresh_error": "", "default_revision": commit,
		"object_available": True, "ref_fingerprint": "e" * 64,
		"refreshed_at": "2026-08-23T12:00:00Z",
	}
	packet = daily_blog.schema.EvidencePacket.create(
		REPORT_DATE, "America/Chicago", True,
		{
			"changed_documentation_chars": 1000,
			"diff_chars": 1000,
			"readme_context_chars": 1000,
			"commit_metadata_chars": 1000,
			"per_item_chars": 1000,
			"supporting_total_chars": 1000,
			"screenshot_count": 0,
		},
		[mirror], [activity], [item],
	)
	projection = daily_blog.schema.EditorialProjection.create(
		packet.packet_id, REPORT_DATE, "America/Chicago",
		{"context_chars": 10000, "excerpt_chars": 1000, "commit_subject_chars": 240},
		[daily_blog.schema.RepositoryCard(
			repository, repository_url, 1, (commit,), (activity.commits[0].message,),
			"2020-01-01T00:00:00Z", False, False, (),
		)],
		[daily_blog.schema.EvidenceExcerpt.create(item, 0, len(content))],
	)
	return packet, projection, roster


#============================================
def valid_post(packet: daily_blog.schema.EvidencePacket, run_id: str) -> str:
	"""Return a fully cited v3 post accepted by the active public contract."""
	evidence_id = packet.items[0].evidence_id
	story = (
		"I spent the morning following the preview promise back to its saved state, and "
		"the smaller boundary made the whole editing flow easier to trust. "
	)
	return (
		"---\n"
		+ f"date: {REPORT_DATE}\nslug: binding-the-preview\ngenerator_run: {run_id}\n"
		+ "evidence_manifest: evidence.json\neditorial_projection: editorial_projection.json\n---\n\n"
		+ "# Binding the Preview\n\n"
		+ story + f"<!-- evidence: {evidence_id} -->\n\n"
		+ "<!-- more -->\n\n## The saved edge\n\n"
		+ (story * 10) + f"<!-- evidence: {evidence_id} -->\n\n"
		+ "## What I learned\n\n"
		+ (story * 10) + f"<!-- evidence: {evidence_id} -->\n\n"
		+ "## Project coverage\n\n"
		+ f"I worked in vosslab/synthetic-maker today. <!-- evidence: {evidence_id} -->\n"
	)


#============================================
def initialize_publisher_site(root: pathlib.Path) -> None:
	"""Create the disposable publisher-owned tree used by the real importer."""
	(root / "docs" / "blog" / "posts").mkdir(parents=True)
	(root / "docs" / "assets").mkdir()
	(root / "docs" / "index.md").write_text("# Offline site\n", encoding="utf-8")
	(root / "docs" / "status.md").write_text("# Status\n", encoding="utf-8")
	(root / "docs" / "blog" / "index.md").write_text("# Work log\n", encoding="utf-8")
	(root / "mkdocs.yml").write_text("site_name: Offline contract\n", encoding="utf-8")
	(root / "data" / "publications").mkdir(parents=True)
	(root / "generated" / "releases" / "old").mkdir(parents=True)
	(root / "generated" / "releases" / "old" / "index.html").write_text("old\n", encoding="utf-8")
	(root / "generated" / "staging").mkdir()
	(root / "site").symlink_to("generated/releases/old")


#============================================
def fake_publisher_build(_stage_root: str, site_dir: str, _root: str) -> None:
	"""Create the smallest static release needed to cross the importer boundary."""
	pathlib.Path(site_dir).mkdir()
	(pathlib.Path(site_dir) / "index.html").write_text("offline release\n", encoding="utf-8")


#============================================
def experimental_v4_bundle(bundle_path: str) -> str:
	"""Copy a valid bundle and identify it as the still-inactive v4 experiment."""
	copy_path = bundle_path + "-v4"
	shutil.copytree(bundle_path, copy_path)
	manifest_path = pathlib.Path(copy_path) / "bundle.json"
	manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
	policy = daily_blog.contracts.V4_MAKER_VALIDATION_POLICY
	manifest["contracts"] = {
		"evidence_schema": daily_blog.schema.EVIDENCE_SCHEMA_VERSION,
		"editorial_projection_schema": daily_blog.schema.PROJECTION_SCHEMA_VERSION,
		"prompt_version": "daily-blog-prompts-v4", "rubric_version": "daily-blog-rubric-v4",
		"candidate_validation": {"name": policy.name, "version": policy.version, "sha256": policy.sha256()},
	}
	manifest["bundle_sha256"] = daily_blog.bundles.bundle_sha256(manifest)
	manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
	return copy_path


#============================================
def main() -> None:
	"""Publish an active v3 bundle and prove inactive v4 is rejected at that seam."""
	if not (PUBLISHER_ROOT / "scripts" / "import_publication_bundle.py").is_file():
		raise RuntimeError("Sibling daily-blog importer is unavailable.")
	with tempfile.TemporaryDirectory(prefix="daily-blog-contract-") as temporary:
		root = pathlib.Path(temporary)
		packet, projection, roster = make_packet_and_projection()
		run_id = "offline-v3-import"
		post = valid_post(packet, run_id)
		candidate = daily_blog.editorial.CandidateResult(
			"offline-author", projection.projection_id, post, daily_blog.io_utils.sha256_text(post), True, (),
		)
		decision = daily_blog.editorial.EditorialDecision(
			"A", "The cited first-person account preserves the active v3 shape.", "high", 0.9,
			projection.projection_id, post, {"A": 0},
		)
		writer = daily_blog.bundles.BundleWriter(
			str(root / "producer"), "offline", "a" * 64,
			contract=daily_blog.contracts.V3_EDITORIAL_CONTRACT,
		)
		bundle_path, _bundle = writer.write(run_id, packet, projection, {}, [candidate, candidate], decision, roster)
		importer = publisher_importer()
		publisher_root = root / "publisher"
		initialize_publisher_site(publisher_root)
		result = importer.import_publication_bundle(bundle_path, str(publisher_root), fake_publisher_build)
		assert result["status"] == "imported"
		assert (publisher_root / "docs" / "blog" / "posts" / f"{REPORT_DATE}.md").read_text(encoding="utf-8") == post
		rejected_root = root / "publisher-v4"
		initialize_publisher_site(rejected_root)
		try:
			importer.import_publication_bundle(experimental_v4_bundle(bundle_path), str(rejected_root), fake_publisher_build)
		except RuntimeError:
			pass
		else:
			raise AssertionError("Inactive v4 experimental bundle reached public import.")
	print("Daily blog contract E2E passed.")


if __name__ == "__main__":
	main()

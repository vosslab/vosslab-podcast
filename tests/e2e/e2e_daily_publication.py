#!/usr/bin/env python3
"""Run a synthetic date through evidence, bundle, import, and strict MkDocs build."""

# Standard Library
import os
import re
import json
import sys
import shutil
import pathlib
import tempfile
import subprocess
import importlib.util

# local repo modules
import daily_blog.schema
import daily_blog.config
import daily_blog.activity
import daily_blog.evidence
import daily_blog.bundles
import daily_blog.editorial
import daily_blog.candidates
import daily_blog.orchestrator


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
	repository = root / "synthetic-project"
	repository.mkdir()
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
def evidence_budgets() -> dict[str, int]:
	"""Return explicit compact E2E context budgets."""
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
def valid_post(
	packet: daily_blog.schema.EvidencePacket,
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
		+ "publication_quality: final\n"
		+ f"generator_run: {run_id}\n"
		+ "evidence_manifest: evidence.json\n"
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


class ReuseRunner:
	"""Return valid candidates once and expose later unintended model calls."""

	#============================================
	def __init__(self, packet: daily_blog.schema.EvidencePacket) -> None:
		"""Bind the exact packet and initialize the call count."""
		self.packet = packet
		self.calls = 0

	#============================================
	def run(self, route: daily_blog.config.RoleRoute, prompt: str, _repository: str) -> str:
		"""Return route-specific deterministic author or referee output."""
		self.calls += 1
		if route.name == "referee":
			return json.dumps(
				{
					"winner": "A",
					"reason": "Candidate A follows the exact evidence.",
					"evidence_quality": "high",
					"confidence": 0.9,
				}
			)
		match = re.search(r"^generator_run:\s*(\S+)", prompt, flags=re.MULTILINE)
		if match is None:
			raise RuntimeError("Author prompt is missing its artifact identity.")
		title = "Exact evidence wins" if route.name == "author_one" else "Ownership stays durable"
		return valid_post(self.packet, match.group(1), title)


class IdempotentPublisher:
	"""Model the publisher's exact-bundle idempotency contract."""

	#============================================
	def __init__(self) -> None:
		"""Initialize the installed bundle identity."""
		self.bundle_id = ""

	#============================================
	def __call__(self, _repository: str, bundle_path: str) -> dict:
		"""Import one bundle once and report later exact imports as reused."""
		with open(os.path.join(bundle_path, "bundle.json"), "r", encoding="utf-8") as handle:
			bundle = json.load(handle)
		status = "idempotent" if self.bundle_id == bundle["bundle_id"] else "imported"
		self.bundle_id = bundle["bundle_id"]
		return {
			"status": status,
			"bundle_id": bundle["bundle_id"],
			"report_date": bundle["report_date"],
		}


#============================================
def verify_phase_reuse(
	root: pathlib.Path,
	packet: daily_blog.schema.EvidencePacket,
) -> None:
	"""A matching rerun reuses every safe artifact and checks publication idempotency."""
	config = daily_blog.config.DailyBlogConfig(
		settings_path="settings.yaml",
		output_root=str(root / "orchestrator-output"),
		output_owner="vosslab",
		report_timezone="America/Chicago",
		daily_blog_repository=str(root / "publisher-route"),
		mirror_cache_root=str(root),
		repository_urls=(),
		identity_names=("Dr. Neil R Voss",),
		identity_emails=("vosslab@users.noreply.github.com",),
		author_routes=(
			daily_blog.config.RoleRoute("author_one", ("synthetic",)),
			daily_blog.config.RoleRoute("author_two", ("synthetic",)),
		),
		referee_route=daily_blog.config.RoleRoute("referee", ("synthetic",)),
		evidence_budgets=evidence_budgets(),
	)
	runner = ReuseRunner(packet)
	publisher = IdempotentPublisher()
	first = daily_blog.orchestrator.DailyPublicationOrchestrator(
		config,
		"2026-08-23",
		route_runner=runner,
		publisher_function=publisher,
		refresh_mirrors=False,
	)
	first_path, first_bundle = first.run()
	second = daily_blog.orchestrator.DailyPublicationOrchestrator(
		config,
		"2026-08-23",
		route_runner=runner,
		publisher_function=publisher,
		refresh_mirrors=False,
	)
	second_path, second_bundle = second.run()
	reusable_phases = daily_blog.schema.LEGAL_PHASES[1:]
	reuse_status = {name: second.record.phases[name].reused for name in reusable_phases}

	assert first_path == second_path and first_bundle["bundle_id"] == second_bundle["bundle_id"]
	assert runner.calls == 3 and all(reuse_status.values()), (runner.calls, reuse_status)


#============================================
def initialize_publisher(root: pathlib.Path) -> None:
	"""Create the complete minimal MkDocs source tree owned by the importer."""
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
			"repository_url": "https://github.com/vosslab/synthetic-project.git",
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
			"2026-08-23", "America/Chicago", evidence_budgets()
		)
		packet, assets = assembler.assemble([mirror_entry], activities)
		post = daily_blog.candidates.provisional_post(packet, "synthetic-run")
		decision = daily_blog.editorial.EditorialDecision(
			winner="NONE",
			reason="The synthetic E2E uses the deterministic provisional account.",
			evidence_quality="high",
			confidence=1.0,
			publication_quality="provisional",
			post=post,
			anonymous_mapping={},
		)
		invalid_candidate = daily_blog.editorial.CandidateResult(
			private_route="synthetic",
			post="",
			post_hash="0" * 64,
			valid=False,
			issues=("synthetic provisional path",),
		)
		writer = daily_blog.bundles.BundleWriter(
			str(root / "output"), "vosslab", str(REPO_ROOT)
		)
		bundle_path, bundle = writer.write(
			"synthetic-run",
			packet,
			assets,
			[invalid_candidate, invalid_candidate],
			decision,
		)
		publisher_root = root / "publisher"
		publisher_root.mkdir()
		initialize_publisher(publisher_root)
		sys.path.insert(0, str(PUBLISHER_ROOT))
		module_path = PUBLISHER_ROOT / "scripts" / "import_publication_bundle.py"
		specification = importlib.util.spec_from_file_location(
			"publication_bundle_import",
			module_path,
		)
		if specification is None or specification.loader is None:
			raise RuntimeError("Sibling daily-blog importer could not be loaded.")
		importer = importlib.util.module_from_spec(specification)
		specification.loader.exec_module(importer)

		result = importer.import_publication_bundle(
			bundle_path,
			str(publisher_root),
		)
		assert result["bundle_id"] == bundle["bundle_id"]
		assert (publisher_root / "site" / "index.html").is_file()
		verify_phase_reuse(root, packet)
		print("Daily publication E2E passed.")


if __name__ == "__main__":
	main()

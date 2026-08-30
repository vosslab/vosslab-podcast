#!/usr/bin/env python3
"""Controlled end-to-end proof of daily publication behavior.

This uses disposable local roots and a fail-closed model fixture. It protects
reader-visible publication behavior, not editorial implementation topology.
"""

# Standard Library
import contextlib
import hashlib
import io
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest.mock

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))

# local repo modules
import make_blog
import daily_blog.artifacts
import daily_blog.daily_outline_workflow
import daily_blog.publication_workflow
import daily_blog.publisher
import daily_blog.recovery
import daily_blog.repository_contracts
import daily_blog.schema


PUBLISHER_ROOT = REPO_ROOT.parent / "vosslab-daily-blog"
REPORT_DATE = "2026-08-23"
REVISION = "a" * 40


#============================================
def _initialize_publisher(root: pathlib.Path) -> None:
	"""Copy the tracked publisher into a disposable import target."""
	shutil.copytree(PUBLISHER_ROOT, root, ignore=shutil.ignore_patterns(
		".git", ".venv", "generated", "site", "data", "__pycache__",
	))
	prior_post = root / "docs" / "blog" / "posts" / (REPORT_DATE + ".md")
	if prior_post.exists():
		prior_post.unlink()
	(root / "data" / "publications").mkdir(parents=True)
	(root / "data" / "publication_bundles").mkdir()
	(root / "generated" / "staging").mkdir(parents=True)
	(root / "generated" / "releases" / "prior").mkdir(parents=True)
	(root / "generated" / "releases" / "prior" / "index.html").write_text("prior", encoding="utf-8")
	(root / "site").symlink_to("generated/releases/prior")
	result = subprocess.run(["git", "init", "--quiet", str(root)], check=False, text=True,
		stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	if result.returncode:
		raise RuntimeError("Could not initialize the disposable publisher repository.")


#============================================
def _write_settings(path: pathlib.Path, publisher: pathlib.Path, mirrors: pathlib.Path) -> None:
	"""Write the smallest legal public-command configuration."""
	path.write_text(
		"github:\n  username: vosslab\n  identity_login: vosslab\n  allowed_emails: []\n"
		"daily_blog:\n"
		f"  repository_path: {json.dumps(str(publisher))}\n"
		f"  mirror_cache_root: {json.dumps(str(mirrors))}\n"
		"  report_timezone: America/Chicago\n  identity_names: [vosslab]\n  identity_emails: []\n",
		encoding="utf-8",
	)


#============================================
def _source(root: pathlib.Path) -> tuple[
	daily_blog.repository_contracts.RepositoryRoster,
	list[dict],
	list[daily_blog.schema.RepositoryActivity],
	daily_blog.schema.EvidencePacket,
]:
	"""Build complete global evidence for two independently edited repositories."""
	repositories = tuple(daily_blog.repository_contracts.RepositoryRecord.from_dict({
		"repository": repository, "repository_url": "https://github.com/" + repository,
		"clone_url": "https://github.com/" + repository + ".git", "created_at": "2020-01-01T00:00:00Z", "is_fork": False,
	}) for repository in ("vosslab/fixture", "vosslab/second-fixture"))
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", repositories)
	mirrors, activities, items = [], [], []
	for index, repository in enumerate(repositories):
		revision = ("a" if index == 0 else "d") * 40
		mirror = {"repository": repository.repository, "repository_url": repository.repository_url,
			"clone_url": repository.clone_url, "created_at": repository.created_at, "is_fork": False,
			"roster_id": roster.roster_id, "cache_path": str(root / "mirrors" / repository.repository),
			"default_revision": revision, "object_available": True, "ref_fingerprint": ("b" if index == 0 else "e") * 64,
			"refresh_result": "refreshed", "refresh_error": "", "refreshed_at": "2026-08-23T12:00:00Z"}
		commit = daily_blog.schema.CommitActivity(revision, (), "vosslab", "vosslab@example.test",
			"2026-08-23T12:00:00Z", "2026-08-23T12:00:00Z", "Fixture evidence-grounded work")
		activity = daily_blog.schema.RepositoryActivity(repository.repository, repository.repository_url,
			mirror["cache_path"], revision, (commit,), (daily_blog.schema.RevisionRange("", revision),), (revision,), False,
			(daily_blog.repository_contracts.RepositoryLifecycleEvent(
				"repository_created", repository.created_at, False, "github_owner_roster"),))
		item = daily_blog.schema.EvidenceItem.create("dated_changelog", repository.repository, revision,
			"docs/CHANGELOG.md", ("c" if index == 0 else "f") * 40,
			"Fixture change: daily publication is observable.", "fixture")
		mirrors.append(mirror)
		activities.append(activity)
		items.append(item)
	packet = daily_blog.schema.EvidencePacket.create(REPORT_DATE, "America/Chicago", True, {}, mirrors, activities, items)
	return roster, mirrors, activities, packet


#============================================
def _post(title: str, evidence_ids: tuple[str, ...]) -> str:
	"""Return a publisher-valid grounded post for the sealed offline runner."""
	paragraph = " ".join("I checked the dated changelog and kept the reader-visible result concrete." for _ in range(36))
	citations = " ".join("<!-- evidence: " + item + " -->" for item in evidence_ids)
	return ("---\ndate: 2026-08-23\nslug: " + title.lower().replace(" ", "-")
		+ "\ngenerator_run: controlled-e2e\nevidence_manifest: evidence.json\neditorial_projection: editorial_projection.json\n---\n"
		+ f"# {title}\n\nOn {REPORT_DATE} I opened [vosslab/fixture](https://github.com/vosslab/fixture) and traced the durable publication seam. {citations}\n\n"
		"<!-- more -->\n\n"
		f"## What I followed\n\n{paragraph} {citations}\n\n"
		"## Project coverage\n\n- vosslab/fixture\n- vosslab/second-fixture\n")


class _OfflineRunner:
	"""Deterministic local substitute for the model response boundaries."""

	def __init__(self, evidence_ids: tuple[str, ...]) -> None:
		self.evidence_ids = evidence_ids

	def _evidence_id(self, prompt: str) -> str:
		match = re.search(r"ev-[0-9a-f]+", prompt)
		return match.group(0) if match is not None else self.evidence_ids[0]

	def _story_ids(self, prompt: str) -> tuple[str, ...]:
		"""Decode the supplied story boundary without assuming editorial order."""
		marker = "<<BEGIN_UNTRUSTED_REPOSITORY_STORIES_DATA>>\n"
		if marker not in prompt:
			raise RuntimeError("Controlled response lacks the required story boundary.")
		payload = prompt.split(marker, 1)[1].split("\n", 1)[0]
		try:
			stories = json.loads(json.loads(payload)["literal_content"])["stories"]
		except (KeyError, TypeError, json.JSONDecodeError) as error:
			raise RuntimeError("Controlled response has an invalid story boundary.") from error
		return tuple(item["artifact_id"] for item in stories)

	def _all_citations(self) -> str:
		return " ".join("<!-- evidence: " + item + " -->" for item in self.evidence_ids)

	def run(self, _route: object, prompt: str, _working: str) -> str:
		"""Return a valid response from the requested result form, never a route name."""
		evidence_id = self._evidence_id(prompt)
		if all(token in prompt for token in ("`artifact_ids`", "`scores`", "`rationale`")):
			identifiers = self._story_ids(prompt)
			return json.dumps({"artifact_ids": list(identifiers), "scores": {item: 90 for item in identifiers}, "rationale": "grounded"})
		if all(token in prompt for token in ("`winner`", "`evidence_quality`", "`confidence`")):
			return '{"winner":"A","reason":"grounded","evidence_quality":"high","confidence":1}'
		if all(token in prompt for token in ("`decision`", "`score`", "`reason`")):
			return '{"decision":"ACCEPT","score":90,"reason":"grounded"}'
		if (
			"eligible CompletePost" in prompt
			or all(token in prompt for token in (
				"generator_run:", "evidence_manifest:", "editorial_projection:",
			))
		):
			return _post("Publication fixture", self.evidence_ids)
		if "daily-outline-scope:" in prompt:
			return "<!-- daily-outline-scope: [\"vosslab/fixture\",\"vosslab/second-fixture\"] -->\n# Fixture outline\n\n" + self._all_citations() + "\n"
		if "<!-- evidence:" in prompt:
			return "# Grounded repository material\n\nConcrete work. <!-- evidence: " + evidence_id + " -->\n"
		raise RuntimeError("Controlled response lacks a mechanically valid result boundary.")


#============================================
def _page_fault() -> daily_blog.recovery.PipelineFaultError:
	"""Return the public structured fault used for the controlled failure branch."""
	category = daily_blog.recovery.TerminalFaultCategory.IMPLEMENTATION_DEFECT
	observation = daily_blog.recovery.GenerationObservation("page_verification", 0, 0, (), category)
	fault = daily_blog.recovery.PipelineFault(category, 1, "", "", (observation,))
	return daily_blog.recovery.PipelineFaultError(fault, "d" * 64)


#============================================
def _runtime(
	root: pathlib.Path, publisher: pathlib.Path, fail_page: bool,
) -> tuple[daily_blog.publication_workflow.PublicationRuntime, _OfflineRunner]:
	"""Bind the public command to controlled external dependencies only."""
	roster, mirrors, activities, packet = _source(root)
	runner = _OfflineRunner(tuple(item.evidence_id for item in packet.items))

	def page_verifier(repository: str, receipt: dict) -> dict:
		if fail_page:
			raise _page_fault()
		return daily_blog.publisher.verify_published_page(repository, receipt)

	return daily_blog.publication_workflow.PublicationRuntime(
		repository_loader=lambda _owner, _output: roster,
		mirror_refresh=lambda *_args: mirrors, activity_locator=lambda *_args: activities,
		evidence_assembler=lambda *_args: (packet, {}),
		route_runner=runner,
		publisher_function=lambda repository, bundle_path, **kwargs: daily_blog.publisher.import_bundle(
			repository, bundle_path, replace_existing=kwargs["replace_existing"]),
		page_verifier=page_verifier,
	), runner


#============================================
def _run_record(root: pathlib.Path, run_id: str) -> dict:
	"""Read one immutable record from the controlled run directory."""
	path = root / "out" / "vosslab" / "daily_blog" / REPORT_DATE / "runs" / run_id / "run_state.json"
	return json.loads(path.read_text(encoding="utf-8"))


#============================================
def _assert_date_summary_retains_run(root: pathlib.Path, run_id: str) -> None:
	"""Require the date-level operational summary to retain this terminal run."""
	path = root / "out" / "vosslab" / "daily_blog" / REPORT_DATE / "summary.jsonl"
	if not path.is_file():
		raise RuntimeError("Terminal run did not produce a date summary.")
	if not any(json.loads(line).get("run_id") == run_id for line in path.read_text(encoding="utf-8").splitlines()):
		raise RuntimeError("Date summary does not retain the terminal run.")


#============================================
def _assert_published(root: pathlib.Path, publisher: pathlib.Path, record: dict) -> None:
	"""Check selected editorial identity through the imported reader page."""
	post = root / "out" / "vosslab" / "daily_blog" / REPORT_DATE / "post.md"
	bundle = json.loads((post.parent / "publication" / "bundle.json").read_text(encoding="utf-8"))
	if {"candidates", "referee"} & set(bundle):
		raise RuntimeError("Publication bundle retains retired editorial topology.")
	receipt = record["publication_bundle"]["site_import"]
	page = record["publication_bundle"]["page_verification"]
	artifact_id = record["best_artifact_id"]
	if not artifact_id or artifact_id != bundle["best_artifact_id"] or artifact_id != bundle["post"]["artifact_id"]:
		raise RuntimeError("Publication does not preserve its selected editorial artifact.")
	if artifact_id != receipt["best_artifact_id"] or artifact_id != page["best_artifact_id"]:
		raise RuntimeError("Publisher receipts do not bind the selected editorial artifact.")
	if receipt["bundle_sha256"] != bundle["bundle_sha256"]:
		raise RuntimeError("Import receipt does not bind the sealed publication bundle.")
	if bundle["post"]["sha256"] != hashlib.sha256(post.read_bytes()).hexdigest():
		raise RuntimeError("Producer bundle digest does not bind the selected post.")
	installed = publisher / receipt["post_path"]
	rendered = publisher / receipt["rendered_page_path"]
	if not (installed.is_file() and rendered.is_file()):
		raise RuntimeError("Imported publication is not available to readers.")
	if hashlib.sha256(installed.read_bytes()).hexdigest() != bundle["post"]["sha256"]:
		raise RuntimeError("Publisher receipt does not preserve selected post bytes.")
	if page["rendered_page_sha256"] != hashlib.sha256(rendered.read_bytes()).hexdigest():
		raise RuntimeError("Page verification receipt does not bind its rendered page.")


#============================================
def _success_and_overwrite() -> None:
	"""Publish once, then replace the same fixed date."""
	with tempfile.TemporaryDirectory(prefix="daily-publication-e2e-") as temporary:
		root, publisher = pathlib.Path(temporary), pathlib.Path(temporary) / "publisher"
		_initialize_publisher(publisher)
		(root / "out").mkdir()
		_write_settings(root / "settings.yaml", publisher, root / "mirrors")
		with contextlib.ExitStack() as stack:
			stack.enter_context(unittest.mock.patch.object(make_blog, "SETTINGS_PATH", root / "settings.yaml"))
			stack.enter_context(unittest.mock.patch.object(make_blog, "OUTPUT_ROOT", root / "out"))
			first_runtime, _first_runner = _runtime(root, publisher, False)
			with unittest.mock.patch("daily_blog.orchestrator.new_run_id", return_value="controlled-first"):
				if make_blog.command(["--date", REPORT_DATE], runtime=first_runtime) != 0:
					raise RuntimeError("Controlled publication command failed.")
			_assert_published(root, publisher, _run_record(root, "controlled-first"))
			_assert_date_summary_retains_run(root, "controlled-first")
			replacement_root = root / "replacement"
			replacement_root.mkdir()
			(replacement_root / "out").mkdir()
			_write_settings(replacement_root / "settings.yaml", publisher, replacement_root / "mirrors")
			replacement_runtime, _replacement_runner = _runtime(replacement_root, publisher, False)
			stack.enter_context(unittest.mock.patch.object(make_blog, "SETTINGS_PATH", replacement_root / "settings.yaml"))
			stack.enter_context(unittest.mock.patch.object(make_blog, "OUTPUT_ROOT", replacement_root / "out"))
			with unittest.mock.patch("daily_blog.orchestrator.new_run_id", return_value="controlled-replacement"):
				if make_blog.command(["--date", REPORT_DATE, "--yes"], runtime=replacement_runtime) != 0:
					raise RuntimeError("Same-date replacement command failed.")
			replacement = _run_record(replacement_root, "controlled-replacement")
			if replacement["publication_bundle"]["site_import"]["status"] != "replaced":
				raise RuntimeError("Same-date publication was not replaced.")
			_assert_published(replacement_root, publisher, replacement)
			_assert_date_summary_retains_run(replacement_root, "controlled-replacement")


#============================================
def _post_import_failure() -> None:
	"""Require one typed verification failure to retain the committed publication."""
	with tempfile.TemporaryDirectory(prefix="daily-publication-e2e-") as temporary:
		root, publisher = pathlib.Path(temporary), pathlib.Path(temporary) / "publisher"
		_initialize_publisher(publisher)
		(root / "out").mkdir()
		_write_settings(root / "settings.yaml", publisher, root / "mirrors")
		runtime, _runner = _runtime(root, publisher, True)
		with contextlib.ExitStack() as stack:
			stack.enter_context(unittest.mock.patch.object(make_blog, "SETTINGS_PATH", root / "settings.yaml"))
			stack.enter_context(unittest.mock.patch.object(make_blog, "OUTPUT_ROOT", root / "out"))
			stack.enter_context(unittest.mock.patch("daily_blog.orchestrator.new_run_id", return_value="controlled-page-failure"))
			with contextlib.redirect_stderr(io.StringIO()) as stderr:
				status = make_blog.command(["--date", REPORT_DATE], runtime=runtime)
		if status != 2:
			raise RuntimeError("Post-import verification failure did not return the public nonzero status.")
		fault = json.loads(stderr.getvalue())
		if fault["status"] != "pipeline_fault" or fault["report_date"] != REPORT_DATE:
			raise RuntimeError("Post-import verification failure did not return a structured fault.")
		record = _run_record(root, "controlled-page-failure")
		if record["state"] != "failed" or record["phases"]["page_verification"]["status"] != "failed":
			raise RuntimeError("Post-import verification failure did not persist its failed phase.")
		_assert_date_summary_retains_run(root, "controlled-page-failure")
		post = root / "out" / "vosslab" / "daily_blog" / REPORT_DATE / "post.md"
		bundle = publisher / "data" / "publication_bundles" / REPORT_DATE / "bundle.json"
		publication = publisher / "data" / "publications" / (REPORT_DATE + ".json")
		if not (post.is_file() and bundle.is_file() and publication.is_file()):
			raise RuntimeError("Post-import verification failure did not retain the committed artifact.")


#============================================
def main() -> int:
	"""Run the single permanent controlled publication E2E."""
	try:
		_success_and_overwrite()
		_post_import_failure()
	except (AssertionError, OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError):
		print("Daily publication E2E failed.", file=sys.stderr)
		return 2
	print("Daily publication E2E passed.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

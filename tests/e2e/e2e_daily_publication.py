#!/usr/bin/env python3
"""Controlled end-to-end proof of daily publication behavior.

This uses disposable local roots and a fail-closed model fixture. It protects
reader-visible publication behavior, not editorial implementation topology.
"""

# Standard Library
import contextlib
import hashlib
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
import daily_blog.editorial_stage_config
import daily_blog.observability
import daily_blog.publication_workflow
import daily_blog.publisher
import daily_blog.publication_source_safety
import daily_blog.repository_contracts
import daily_blog.schema


PUBLISHER_ROOT = REPO_ROOT.parent / "vosslab-daily-blog"
REPORT_DATE = "2026-08-23"
REVISION = "a" * 40
SELECTED_ASSET_PATH = "assets/selected.png"
UNSELECTED_ASSET_PATH = "assets/unselected.png"
SELECTED_PUBLISH_PATH = f"../../assets/publications/{REPORT_DATE}/selected.png"
UNSELECTED_PUBLISH_PATH = f"../../assets/publications/{REPORT_DATE}/unselected.png"
PUBLISHER_READER_FILES = (
	pathlib.PurePosixPath("index.md"),
	pathlib.PurePosixPath("status.md"),
	pathlib.PurePosixPath("stylesheets/extra.css"),
)


#============================================
def _publisher_copy_ignores(directory: str, names: list[str]) -> set[str]:
	"""Exclude mutable and generated publisher state from the controlled copy."""
	ignored = set(shutil.ignore_patterns(
		".git", ".venv", "generated", "site", "data", "__pycache__",
	)(directory, names))
	if pathlib.Path(directory) == PUBLISHER_ROOT:
		# ASVS 15.2.2: the E2E exercises the real publisher runtime without
		# multiplying its unbounded historical reader corpus in every stage.
		ignored.add("docs")
	return ignored


#============================================
def _initialize_reader_source(root: pathlib.Path) -> None:
	"""Create the fixed minimal MkDocs source surface used by this E2E."""
	docs_source = PUBLISHER_ROOT / "docs"
	docs_target = root / "docs"
	# ASVS 5.3.2: every copied path is an internal constant beneath the two
	# trusted repository roots; no external filename controls a destination.
	for relative in PUBLISHER_READER_FILES:
		source = docs_source.joinpath(*relative.parts)
		destination = docs_target.joinpath(*relative.parts)
		destination.parent.mkdir(parents=True, exist_ok=True)
		shutil.copy2(source, destination)
	shutil.copytree(docs_source / "assets" / "brand", docs_target / "assets" / "brand")
	(docs_target / "blog" / "posts").mkdir(parents=True)


#============================================
def _initialize_publisher(root: pathlib.Path) -> None:
	"""Copy the tracked publisher into a disposable import target."""
	shutil.copytree(PUBLISHER_ROOT, root, ignore=_publisher_copy_ignores)
	_initialize_reader_source(root)
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
def _assert_source_safety_parity(publisher: pathlib.Path) -> None:
	"""Require the copied publisher to execute the sealed safety corpus independently."""
	program = """import hashlib
import json
import scripts.publication_source_safety as safety

vector = safety.policy_vector_bytes()
result = {
    'sha256': hashlib.sha256(vector).hexdigest(),
    'vector': vector.decode('ascii'),
    'valid': [not safety.validate_post_source(case['post'], safety.POLICY_VECTOR['approved_paths']) for case in safety.POLICY_VECTOR['cases']],
}
print(json.dumps(result, sort_keys=True))
"""
	completed = subprocess.run(
		[sys.executable, "-c", program], cwd=publisher, capture_output=True, check=True, text=True,
	)
	try:
		actual = json.loads(completed.stdout)
	except json.JSONDecodeError as error:
		raise RuntimeError("Disposable publisher did not return a safety-corpus result.") from error
	vector = daily_blog.publication_source_safety.policy_vector_bytes()
	if actual["vector"].encode("ascii") != vector:
		raise RuntimeError("Producer and disposable publisher safety corpora differ.")
	if actual["sha256"] != hashlib.sha256(vector).hexdigest():
		raise RuntimeError("Disposable publisher safety-corpus digest is invalid.")
	if actual["valid"] != [case["valid"] for case in daily_blog.publication_source_safety.CANONICAL_VECTOR["cases"]]:
		raise RuntimeError("Producer and disposable publisher safety semantics differ.")


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
	dict[str, bytes],
]:
	"""Build two survivors plus one aggregate screenshot outside their surface."""
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
	items.extend((
		daily_blog.schema.EvidenceItem.create(
			"screenshot", repositories[0].repository, "a" * 40, "selected.png", "1" * 40,
			"Selected survivor screenshot.", "fixture", asset_path=SELECTED_ASSET_PATH,
			publish_path=SELECTED_PUBLISH_PATH,
		),
		daily_blog.schema.EvidenceItem.create(
			"screenshot", repositories[0].repository, "a" * 40, "unselected.png", "2" * 40,
			"Aggregate screenshot outside the survivor surface.", "fixture",
			asset_path=UNSELECTED_ASSET_PATH, publish_path=UNSELECTED_PUBLISH_PATH,
		),
	))
	packet = daily_blog.schema.EvidencePacket.create(REPORT_DATE, "America/Chicago", True, {}, mirrors, activities, items)
	return roster, mirrors, activities, packet, {
		SELECTED_ASSET_PATH: b"selected-image",
		UNSELECTED_ASSET_PATH: b"unselected-image",
	}


#============================================
def _post(title: str, evidence_ids: tuple[str, ...]) -> str:
	"""Return a publisher-valid grounded post for the sealed offline runner."""
	fixture_evidence, second_evidence, screenshot_evidence = evidence_ids
	opening = (
		"On 2026-08-23 I followed the change trail in "
		"[vosslab/fixture](https://github.com/vosslab/fixture), then compared it with "
		"[vosslab/second-fixture](https://github.com/vosslab/second-fixture). "
		"The two dated changelog entries turn a broad publication claim into work a reader can verify. "
		"<!-- evidence: " + fixture_evidence + " -->"
	)
	fixture_story = " ".join((
		"The fixture repository records that the daily publication is observable.",
		"I treated that as a reader-facing contract rather than a private implementation detail.",
		"The useful question was whether a published post can identify the work, retain its evidence, and still be understandable after the run ends.",
		"That led me to keep the explanation close to the dated change instead of inventing a larger product narrative.",
		"A reader following the repository link can inspect the same small, durable claim that shaped this post.",
		"<!-- evidence: " + fixture_evidence + " -->",
	))
	second_story = " ".join((
		"The second fixture provides an independent check on the same publication path.",
		"Its dated change confirms that the evidence set is not a single-repository anecdote.",
		"I used the pair to describe the seam between collected activity and the page a reader receives.",
		"That seam matters because replacement, receipts, and page verification should preserve the selected editorial artifact without silently changing its provenance.",
		"The result is deliberately modest: two concrete repositories, two dated sources, and one traceable publication decision.",
		"<!-- evidence: " + second_evidence + " -->",
	))
	closing = " ".join((
		"For this fixture, the practical lesson is to make the proof visible at the same boundary where publication becomes durable.",
		"I can point to the evidence comments, repository links, sealed post, and imported page without relying on an unstated model judgment.",
		"That makes a replacement run intelligible as well: it may install a new selected artifact, but it must leave a receipt that binds the date and bytes together.",
		"The surrounding pipeline can degrade editorially when a candidate fails, while an import or page failure remains an operational event with an explicit record.",
		"I also kept the publication example small enough that the evidence trail remains visible without a separate dashboard.",
		"The dated sources support the observed change, while the receipt supports the later claim that those selected bytes were imported.",
		"Those are different facts, and the fixture keeps them separate so an editorial success cannot disguise an operational failure.",
		"A future reader can therefore inspect the exact repository history and the final page as two connected but distinct forms of evidence.",
		"That distinction is what makes a repeatable daily run more useful than a one-off generated summary.",
		"<!-- evidence: " + fixture_evidence + " --> <!-- evidence: " + second_evidence + " -->",
	))
	return ("---\ndate: 2026-08-23\nslug: " + title.lower().replace(" ", "-")
		+ "\ngenerator_run: controlled-e2e\nevidence_manifest: evidence.json\neditorial_projection: editorial_projection.json\n---\n"
		+ f"# {title}\n\n{opening}\n\n"
		"<!-- more -->\n\n"
		f"## Following the fixture\n\n{fixture_story}\n\n"
		f"## Comparing the second repository\n\n{second_story}\n\n"
		"## Inspecting the selected result\n\n"
		"![Selected survivor screenshot](" + SELECTED_PUBLISH_PATH + ") "
		"<!-- evidence: " + screenshot_evidence + " -->\n\n"
		f"## Keeping publication legible\n\n{closing}\n\n"
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

	def run(
		self,
		route: daily_blog.editorial_stage_config.RoleRoute,
		prompt: str,
		_working: str,
	) -> str:
		"""Return a response by the typed route identity, not mutable prompt prose."""
		if type(route) is not daily_blog.editorial_stage_config.RoleRoute:
			raise RuntimeError("Controlled runner requires one exact typed editorial route.")
		name = route.name
		if name == "daily_outline_ranking":
			identifiers = self._story_ids(prompt)
			return json.dumps({"artifact_ids": list(identifiers), "scores": {item: 90 for item in identifiers}, "rationale": "grounded"})
		if name == "final_synthesis_reviewer":
			return '{"winner":"A","reason":"grounded","evidence_quality":"high","confidence":1}'
		if name in {
			"repository_outline_reviewer", "repository_story_reviewer",
			"daily_outline_outline_reviewer", "complete_post_reviewer",
		}:
			return '{"decision":"ACCEPT","score":90,"reason":"grounded"}'
		if name in {
			"complete_post_writer", "complete_post_editor", "final_synthesis_synthesis",
		}:
			return _post("Publication fixture", self.evidence_ids)
		if name == "daily_outline_outline_writer":
			return (
				"<!-- daily-outline-scope: [\"vosslab/fixture\",\"vosslab/second-fixture\"] -->\n"
				"# Fixture outline\n\n" + self._all_citations() + "\n\n"
				"![Selected survivor screenshot](" + SELECTED_PUBLISH_PATH + ")\n"
			)
		if name in {
			"repository_outline_generator", "repository_outline_merger",
			"repository_story_writer", "repository_story_editor",
		}:
			return "# Grounded repository material\n\nConcrete work. <!-- evidence: " + self._evidence_id(prompt) + " -->\n"
		raise RuntimeError("Controlled response uses an unsupported typed editorial route.")


#============================================
def _runtime(
	root: pathlib.Path, publisher: pathlib.Path, fail_page: bool,
) -> tuple[daily_blog.publication_workflow.PublicationRuntime, _OfflineRunner]:
	"""Bind the public command to controlled external dependencies only."""
	roster, mirrors, activities, packet, assets = _source(root)
	change_ids = tuple(
		next(item.evidence_id for item in packet.items
			if item.kind == "dated_changelog" and item.repository == repository)
		for repository in ("vosslab/fixture", "vosslab/second-fixture")
	)
	selected_screenshot_id = next(
		item.evidence_id for item in packet.items if item.asset_path == SELECTED_ASSET_PATH
	)
	runner = _OfflineRunner(change_ids + (selected_screenshot_id,))

	def page_verifier(repository: str, receipt: dict) -> dict:
		if fail_page:
			# A reader-page filesystem failure is operational: it must retain the
			# committed import while remaining visible to the public command.
			raise OSError("Controlled reader page is unavailable.")
		return daily_blog.publisher.verify_published_page(repository, receipt)

	return daily_blog.publication_workflow.PublicationRuntime(
		repository_loader=lambda _owner, _output: roster,
		mirror_refresh=lambda *_args: mirrors, activity_locator=lambda *_args: activities,
		evidence_assembler=lambda *_args: (packet, assets),
		route_runner=runner,
	publisher_function=lambda repository, transfer, **kwargs: daily_blog.publisher.import_bundle(
		repository, transfer, replace_existing=kwargs["replace_existing"]),
		publisher_validator=daily_blog.publisher.validate_bundle_transfer,
		page_verifier=page_verifier,
	), runner


#============================================
def _run_record(root: pathlib.Path, run_id: str) -> dict:
	"""Read one immutable record from the controlled run directory."""
	path = root / "out" / "vosslab" / "daily_blog" / REPORT_DATE / "runs" / run_id / "run_state.json"
	return json.loads(path.read_text(encoding="utf-8"))


#============================================
def _assert_date_summary_retains_run(root: pathlib.Path, run_id: str) -> dict:
	"""Return this run's parser-validated bounded terminal summary."""
	path = root / "out" / "vosslab" / "daily_blog" / REPORT_DATE / "summary.jsonl"
	if not path.is_file():
		raise RuntimeError("Terminal run did not produce a date summary.")
	for line in path.read_text(encoding="utf-8").splitlines():
		# The public parser enforces the terminal-summary byte envelope.
		summary = daily_blog.observability.parse_terminal_summary_line(line)
		if summary["run_id"] == run_id:
			return summary
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
	surface = json.loads(
		(post.parent / "publication" / "publication_surface.json").read_text(encoding="utf-8"),
	)
	if [item["publish_path"] for item in surface["allowed_images"]] != [SELECTED_PUBLISH_PATH]:
		raise RuntimeError("Publication surface did not preserve the selected image authority.")
	archive_assets = publisher / "data" / "publication_bundles" / REPORT_DATE / "assets"
	installed_assets = publisher / "docs" / "assets" / "publications" / REPORT_DATE
	if not (archive_assets / "selected.png").is_file() or not (installed_assets / "selected.png").is_file():
		raise RuntimeError("Selected survivor image did not cross the publisher boundary.")
	if (archive_assets / "unselected.png").exists() or (installed_assets / "unselected.png").exists():
		raise RuntimeError("Unselected aggregate image crossed the survivor boundary.")


#============================================
def _success_and_overwrite() -> None:
	"""Publish once, then replace the same fixed date."""
	with tempfile.TemporaryDirectory(prefix="daily-publication-e2e-") as temporary:
		root, publisher = pathlib.Path(temporary), pathlib.Path(temporary) / "publisher"
		_initialize_publisher(publisher)
		_assert_source_safety_parity(publisher)
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
	"""Require an operational verification failure to retain the committed publication."""
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
			try:
				make_blog.command(["--date", REPORT_DATE], runtime=runtime)
			except OSError as error:
				if str(error) != "Controlled reader page is unavailable.":
					raise RuntimeError("Public command propagated the wrong verification error.") from error
			else:
				raise RuntimeError("Operational page verification failure did not propagate.")
		record = _run_record(root, "controlled-page-failure")
		if record["state"] != "failed" or record["phases"]["page_verification"]["status"] != "failed":
			raise RuntimeError("Post-import verification failure did not persist its failed phase.")
		summary = _assert_date_summary_retains_run(root, "controlled-page-failure")
		if (
			summary["failure_phase"] != "page_verification"
			or summary["operational_failure_kind"] != "external_resource_error"
			or summary["terminal_fault_category"]
		):
			raise RuntimeError("Terminal summary did not retain the bounded operational failure.")
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

#!/usr/bin/env python3
"""Prove one sealed maker post reaches a strict disposable MkDocs release.

This is one-time implementation evidence, not a pytest module. It intentionally
uses the accepted August 26 fixture/capture rather than inventing an article or
calling a live model.
"""

# Standard Library
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

# local repo modules
import daily_blog.activation
import daily_blog.bundles
import daily_blog.config
import daily_blog.contracts
import daily_blog.editorial
import daily_blog.evidence
import daily_blog.experiment_capture_artifacts
import daily_blog.io_utils
import daily_blog.private_artifacts
import daily_blog.publisher
import daily_blog.roster_snapshots


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PUBLISHER_ROOT = REPO_ROOT.parent / "vosslab-daily-blog"
FIXTURE_PATH = (
	REPO_ROOT
	/ "out/vosslab/daily_blog_experiment_fixtures_v2"
	/ "2026-08-26--04fd7a045538662e5c6b48ad79e08dd608de1b5a10c1c8857c7b12042bad41da"
)
CAPTURE_PATH = REPO_ROOT / "out/vosslab/daily_blog_experiments/prompt-experiment-fixture-maker-v10"
ROSTER_PATH = (
	REPO_ROOT
	/ "out/vosslab/daily_blog_repository_rosters"
	/ "0f79bcfea4d3fb783258df4a37effef5996b6fdb9736ff6944fd17051570b8a1"
	/ "repository_roster.json"
)
EXPECTED_POST_HASH = "52d796534299f2a52db265b6b3bba091cb4cd5729e549f3e4ba8a32d8d997d42"
EXPECTED_TITLE = "Letting Cancer Clicker show its mutations"
EXPECTED_PASSAGES = (
	"the game answered with a wonderfully messy endless tumor.",
	"The Playwright pass supplied the less glamorous but equally useful surprises.",
	"Next I want to price the weak upgrades against the newly visible mutation bursts",
)
EXPECTED_ROUTE = (
	"hermes", "chat", "--provider", "openai-codex", "--query-file", "-",
	"--ignore-rules", "--quiet",
)


#============================================
def selected_busy_record(capture: daily_blog.experiment_capture_artifacts.ExperimentCapture) -> dict:
	"""Return the exact accepted busy arm without depending on experiment counts."""
	records = capture.report.get("records")
	if not isinstance(records, list):
		raise RuntimeError("Sealed capture records are unavailable.")
	matches = [
		record for record in records
		if isinstance(record, dict)
		and record.get("fixture") == "busy"
		and record.get("arm") == "v4-three-examples-corpus-v2"
		and record.get("repetition") == 0
	]
	if len(matches) != 1:
		raise RuntimeError("Sealed capture does not contain the accepted busy post.")
	record = matches[0]
	selected = record.get("selected")
	if not isinstance(selected, dict) or selected.get("post_hash") != EXPECTED_POST_HASH:
		raise RuntimeError("Sealed capture selected-post identity is invalid.")
	return record


#============================================
def read_selected_post(capture: daily_blog.experiment_capture_artifacts.ExperimentCapture, record: dict) -> str:
	"""Read the already-validated selected post through the sealed capture descriptor."""
	selected = record["selected"]
	if not isinstance(selected, dict) or selected.get("path") != "selected.md":
		raise RuntimeError("Sealed capture selected post declaration is invalid.")
	root_fd = daily_blog.private_artifacts.open_physical_directory(
		str(capture.path), create=False, intermediate_mode=0o755, leaf_mode=0o700
	)
	try:
		child_fd = daily_blog.private_artifacts.open_directory_at(
			root_fd, "busy-v4-three-examples-corpus-v2-0"
		)
		try:
			contents = daily_blog.private_artifacts.read_regular_bytes_at(
				child_fd, "selected.md", 4_000_000, 0o077
			)
		finally:
			os.close(child_fd)
	finally:
		os.close(root_fd)
	try:
		post = contents.decode("utf-8")
	except UnicodeDecodeError as error:
		raise RuntimeError("Sealed capture selected post is not UTF-8.") from error
	if daily_blog.io_utils.sha256_text(post) != EXPECTED_POST_HASH:
		raise RuntimeError("Sealed capture selected post bytes do not match its identity.")
	return post


#============================================
def fixture_assets(fixture: daily_blog.experiment_capture_artifacts.ExperimentFixture) -> dict[str, bytes]:
	"""Recover only screenshot blobs already pinned by the sealed evidence packet."""
	activities = {activity.repository: activity for activity in fixture.packet.activity}
	assets = {}
	for item in fixture.packet.items:
		if not item.asset_path:
			continue
		activity = activities.get(item.repository)
		if activity is None or item.kind != "screenshot":
			raise RuntimeError("Fixture screenshot evidence has no matching activity record.")
		snapshot = daily_blog.evidence.GitSnapshot(activity)
		if (
			not snapshot.object_exists(item.commit, item.path)
			or snapshot.blob_hash(item.commit, item.path) != item.blob_hash
		):
			raise RuntimeError("Fixture screenshot blob no longer matches its sealed provenance.")
		assets[item.asset_path] = snapshot.read_bytes(item.commit, item.path)
	return assets


#============================================
def initialize_publisher(root: pathlib.Path) -> None:
	"""Create a disposable publisher root using its tracked public importer."""
	shutil.copytree(PUBLISHER_ROOT / "scripts", root / "scripts")
	for name in ("source_me.sh", "mkdocs.yml", "daily_blog_maker_activation.json"):
		shutil.copy2(PUBLISHER_ROOT / name, root / name)
	(root / "docs" / "blog" / "posts").mkdir(parents=True)
	(root / "docs" / "stylesheets").mkdir()
	for name, contents in {
		"index.md": "# Daily work log\n",
		"status.md": "# Publication status\n",
		"operations.md": "# Operations\n",
		"CODE_ARCHITECTURE.md": "# Code architecture\n",
		"blog/index.md": "# Work log\n",
		"stylesheets/extra.css": "body {}\n",
	}.items():
		(root / "docs" / name).write_text(contents, encoding="utf-8")
	(root / "data" / "publications").mkdir(parents=True)
	(root / "generated" / "staging").mkdir(parents=True)
	(root / "generated" / "releases" / "old").mkdir(parents=True)
	(root / "generated" / "releases" / "old" / "index.html").write_text("old", encoding="utf-8")
	(root / "site").symlink_to("generated/releases/old")
	subprocess.run(
		["git", "init", "--quiet", str(root)], check=True,
		stdout=subprocess.PIPE, stderr=subprocess.PIPE,
	)


#============================================
def rendered_article(release: pathlib.Path) -> pathlib.Path:
	"""Find the dated reader page by its published title and substantive passages."""
	matches = []
	for page in release.rglob("*.html"):
		contents = page.read_text(encoding="utf-8")
		if EXPECTED_TITLE in contents and all(passage in contents for passage in EXPECTED_PASSAGES):
			matches.append(page)
	if len(matches) != 1:
		raise RuntimeError("Strict MkDocs release does not contain one rendered maker article.")
	page = matches[0]
	relative = page.relative_to(release).as_posix()
	if not all(part in relative.split("/") for part in ("2026", "08", "26")):
		raise RuntimeError("Rendered maker article is not published at its dated page route.")
	return page


#============================================
def verify_published_assets(
	bundle_path: pathlib.Path,
	bundle: dict,
	publisher_root: pathlib.Path,
	archive: pathlib.Path,
) -> None:
	"""Prove every validated asset survives archive and public-source installation."""
	post_source = publisher_root / "docs" / "blog" / "posts" / f"{bundle['report_date']}.md"
	docs_root = (publisher_root / "docs").resolve()
	assets = bundle.get("assets")
	if not isinstance(assets, list):
		raise RuntimeError("Bundle asset declaration is unavailable.")
	for asset in assets:
		if not isinstance(asset, dict):
			raise RuntimeError("Bundle asset declaration is invalid.")
		relative_path = pathlib.PurePosixPath(str(asset.get("path") or ""))
		publish_path = pathlib.PurePosixPath(str(asset.get("publish_path") or ""))
		if relative_path.is_absolute() or ".." in relative_path.parts or publish_path.is_absolute():
			raise RuntimeError("Bundle asset paths are invalid.")
		producer_asset = bundle_path.joinpath(*relative_path.parts)
		archive_asset = archive.joinpath(*relative_path.parts)
		public_asset = (post_source.parent / pathlib.Path(*publish_path.parts)).resolve()
		try:
			public_asset.relative_to(docs_root)
		except ValueError as error:
			raise RuntimeError("Bundle asset publication path escapes the docs tree.") from error
		contents = producer_asset.read_bytes()
		if daily_blog.io_utils.sha256_bytes(contents) != asset.get("sha256"):
			raise RuntimeError("Producer bundle asset bytes do not match their declaration.")
		if archive_asset.read_bytes() != contents or public_asset.read_bytes() != contents:
			raise RuntimeError("Publisher did not preserve a declared asset byte-for-byte.")


#============================================
def main() -> None:
	"""Run the fixture-backed producer-to-publisher release proof once."""
	if tuple(daily_blog.config.HERMES_EDITORIAL_ROUTE) != EXPECTED_ROUTE:
		raise RuntimeError("The producer Hermes author route no longer matches the approved boundary.")
	if not (PUBLISHER_ROOT / "scripts" / "import_publication_bundle.py").is_file():
		raise RuntimeError("Sibling daily-blog importer is unavailable.")
	fixture = daily_blog.experiment_capture_artifacts.load_fixture(str(FIXTURE_PATH))
	capture = daily_blog.experiment_capture_artifacts.load_capture(str(CAPTURE_PATH))
	if capture.manifest.get("execution_mode") != "fixture_hermes_shim" or capture.manifest.get("external_route_used") is not False:
		raise RuntimeError("Sealed capture does not prove the required no-egress Hermes route.")
	record = selected_busy_record(capture)
	if record.get("fixture_identity", {}).get("packet_id") != fixture.packet.packet_id:
		raise RuntimeError("Sealed capture busy record does not bind the loaded fixture evidence.")
	post = read_selected_post(capture, record)
	assets = fixture_assets(fixture)
	run_id = record.get("run_id")
	if not isinstance(run_id, str):
		raise RuntimeError("Sealed capture selected post run identity is invalid.")
	roster, roster_identity = daily_blog.roster_snapshots.load_repository_roster_snapshot(
		str(REPO_ROOT / "out"), "vosslab", str(ROSTER_PATH.parent)
	)
	if roster.roster_id != fixture.roster_id or roster_identity["roster_id"] != fixture.roster_id:
		raise RuntimeError("Sealed roster does not match the captured busy fixture.")
	contract = daily_blog.contracts.active_contract()
	snapshot = daily_blog.editorial.load_prompt_contract_snapshot(contract)
	if contract is not daily_blog.contracts.V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT:
		raise RuntimeError("Maker v4 contract is not active for the publication proof.")
	raw_candidates = [
		{
			"private_route": str(record["selected"]["route"]),
			"projection_id": fixture.projection.projection_id,
			"post": post,
			"post_hash": EXPECTED_POST_HASH,
			"generation_error": "",
		},
		{
			"private_route": "author_two",
			"projection_id": fixture.projection.projection_id,
			"post": post,
			"post_hash": EXPECTED_POST_HASH,
			"generation_error": "",
		},
	]
	candidates = daily_blog.editorial.validate_candidates(
		raw_candidates, fixture.packet, fixture.projection, run_id,
		contract=contract, snapshot=snapshot,
	)
	if not all(candidate.valid for candidate in candidates):
		raise RuntimeError("Accepted complete maker post no longer satisfies the active policy.")
	decision = daily_blog.editorial.EditorialDecision(
		winner="A", reason=str(record["selection"]["reason"]), evidence_quality="high",
		confidence=float(record["selection"]["confidence"]),
		projection_id=fixture.projection.projection_id, post=post,
		anonymous_mapping={"A": 0, "B": 1},
	)
	with tempfile.TemporaryDirectory(prefix="daily-publication-e2e-") as temporary:
		root = pathlib.Path(temporary)
		identity = daily_blog.bundles.generator_contract_identity(str(REPO_ROOT), None, contract, snapshot)
		writer = daily_blog.bundles.BundleWriter(str(root / "output"), "vosslab", identity, contract, snapshot)
		bundle_path, bundle = writer.write(
			run_id, fixture.packet, fixture.projection, assets, candidates, decision, roster
		)
		activation = daily_blog.activation.load_maker_activation()
		if bundle.get("maker_activation", {}).get("activation_id") != activation.activation_id:
			raise RuntimeError("Bundle is not bound to the active maker activation receipt.")
		publisher_root = root / "publisher"
		publisher_root.mkdir()
		initialize_publisher(publisher_root)
		result = daily_blog.publisher.import_bundle(str(publisher_root), bundle_path)
		if result["bundle_sha256"] != bundle["bundle_sha256"] or result["report_date"] != fixture.date:
			raise RuntimeError("Publisher receipt does not match the created v4 bundle.")
		archive = publisher_root / "data" / "publication_bundles" / fixture.date
		for name in (
			"bundle.json", "evidence.json", "repository_roster.json",
			"editorial_projection.json", "post.md",
		):
			if (archive / name).read_bytes() != (pathlib.Path(bundle_path) / name).read_bytes():
				raise RuntimeError("Publisher archive does not preserve the verified bundle artifact.")
		verify_published_assets(pathlib.Path(bundle_path), bundle, publisher_root, archive)
		if (publisher_root / "docs" / "blog" / "posts" / f"{fixture.date}.md").read_bytes() != post.encode("utf-8"):
			raise RuntimeError("Publisher source post does not preserve the accepted complete post bytes.")
		release = publisher_root / "generated" / "releases" / fixture.date
		if not (publisher_root / "site").is_symlink() or (publisher_root / "site").resolve() != release.resolve():
			raise RuntimeError("Publisher did not atomically point the site at the dated release.")
		page = rendered_article(release)
		evidence = {
			"status": "passed",
			"fixture": {"id": fixture.fixture_id, "packet_id": fixture.packet.packet_id},
			"capture": {"id": capture.manifest["capture_id"], "execution_mode": capture.manifest["execution_mode"], "route": list(EXPECTED_ROUTE)},
			"post": {"sha256": EXPECTED_POST_HASH, "title": EXPECTED_TITLE},
			"bundle": {"sha256": bundle["bundle_sha256"], "report_date": fixture.date},
			"asset_count": len(bundle["assets"]),
			"activation_id": activation.activation_id,
			"rendered_page": page.relative_to(release).as_posix(),
		}
		print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
	main()

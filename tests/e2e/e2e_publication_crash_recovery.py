#!/usr/bin/env python3
"""One-time abrupt-process recovery proof for the publisher transaction.

This is implementation evidence, not a pytest module.  It uses the accepted
fixture-backed maker post and a disposable copy of the public publisher.  The
minimal release builder deliberately proves transaction recovery only; the
strict MkDocs and rendered-page proof lives in ``e2e_daily_publication.py``.
"""

# Standard Library
import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import tempfile
import types

# local repo modules
import daily_blog.activation
import daily_blog.bundles
import daily_blog.config
import daily_blog.contracts
import daily_blog.editorial
import daily_blog.experiment_capture_artifacts
import daily_blog.roster_snapshots


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PUBLISHER_ROOT = REPO_ROOT.parent / "vosslab-daily-blog"
DAILY_PUBLICATION_E2E = REPO_ROOT / "tests" / "e2e" / "e2e_daily_publication.py"
BOUNDARIES = ("marker", "release", "archive", "docs", "site", "record")


#============================================
def load_daily_publication_e2e() -> types.ModuleType:
	"""Load the accepted fixture helpers without turning this harness into pytest."""
	specification = importlib.util.spec_from_file_location(
		"daily_publication_e2e", DAILY_PUBLICATION_E2E
	)
	if specification is None or specification.loader is None:
		raise RuntimeError("The accepted daily-publication E2E helpers are unavailable.")
	module = importlib.util.module_from_spec(specification)
	specification.loader.exec_module(module)
	return module


#============================================
def publisher_python_command() -> list[str]:
	"""Return a verified Python 3.13 command for the copied publisher process."""
	if os.name == "nt":
		launcher = shutil.which("py")
		command = [launcher, "-3.13"] if launcher else []
	else:
		interpreter = shutil.which("python3.13")
		command = [interpreter] if interpreter else []
	if not command:
		raise RuntimeError("A Python 3.13 interpreter is required for publisher recovery evidence.")
	result = subprocess.run(
		[*command, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
		check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
	)
	if result.returncode != 0 or result.stdout.strip() != "3.13":
		raise RuntimeError("The discovered publisher interpreter is not exactly Python 3.13.")
	return command


#============================================
def maker_bundle(work_root: pathlib.Path, run_id: str) -> tuple[str, dict]:
	"""Build one valid bundle from the accepted busy maker post and sealed fixture."""
	helpers = load_daily_publication_e2e()
	if tuple(daily_blog.config.HERMES_EDITORIAL_ROUTE) != helpers.EXPECTED_ROUTE:
		raise RuntimeError("The approved Hermes author route has changed.")
	fixture = daily_blog.experiment_capture_artifacts.load_fixture(str(helpers.FIXTURE_PATH))
	capture = daily_blog.experiment_capture_artifacts.load_capture(str(helpers.CAPTURE_PATH))
	record = helpers.selected_busy_record(capture)
	post = helpers.read_selected_post(capture, record)
	source_run_id = record.get("run_id")
	if not isinstance(source_run_id, str):
		raise RuntimeError("The captured maker post has no valid generator run identity.")
	post = post.replace(
		f"generator_run: {source_run_id}", f"generator_run: {run_id}", 1
	)
	post_hash = daily_blog.io_utils.sha256_text(post)
	assets = helpers.fixture_assets(fixture)
	roster, identity = daily_blog.roster_snapshots.load_repository_roster_snapshot(
		str(REPO_ROOT / "out"), "vosslab", str(helpers.ROSTER_PATH.parent)
	)
	if roster.roster_id != fixture.roster_id or identity["roster_id"] != fixture.roster_id:
		raise RuntimeError("The sealed roster does not match the captured maker fixture.")
	contract = daily_blog.contracts.active_contract()
	snapshot = daily_blog.editorial.load_prompt_contract_snapshot(contract)
	if contract is not daily_blog.contracts.V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT:
		raise RuntimeError("The accepted maker contract is not active.")
	raw_candidates = [
		{
			"private_route": str(record["selected"]["route"]),
			"projection_id": fixture.projection.projection_id,
			"post": post,
			"post_hash": post_hash,
			"generation_error": "",
		},
		{
			"private_route": "author_two",
			"projection_id": fixture.projection.projection_id,
			"post": post,
			"post_hash": post_hash,
			"generation_error": "",
		},
	]
	candidates = daily_blog.editorial.validate_candidates(
		raw_candidates, fixture.packet, fixture.projection, run_id,
		contract=contract, snapshot=snapshot,
	)
	if not all(candidate.valid for candidate in candidates):
		raise RuntimeError("The accepted maker post no longer satisfies the active policy.")
	decision = daily_blog.editorial.EditorialDecision(
		winner="A", reason=str(record["selection"]["reason"]), evidence_quality="high",
		confidence=float(record["selection"]["confidence"]),
		projection_id=fixture.projection.projection_id, post=post,
		anonymous_mapping={"A": 0, "B": 1},
	)
	identity = daily_blog.bundles.generator_contract_identity(str(REPO_ROOT), None, contract, snapshot)
	writer = daily_blog.bundles.BundleWriter(
		str(work_root / run_id), "vosslab", identity, contract, snapshot
	)
	return writer.write(
		run_id, fixture.packet, fixture.projection, assets, candidates, decision, roster
	)


#============================================
def load_publisher(root: pathlib.Path) -> types.ModuleType:
	"""Import the copied publisher rather than the sibling working tree."""
	for name in list(sys.modules):
		if name == "scripts" or name.startswith("scripts."):
			del sys.modules[name]
	sys.path.insert(0, str(root))
	try:
		import scripts.import_publication_bundle
		return scripts.import_publication_bundle
	finally:
		sys.path.pop(0)


#============================================
def recovery_build(stage_root: str, site_dir: str, _root: str) -> None:
	"""Build a deterministic minimal release for this recovery-only transaction proof."""
	with open(os.path.join(stage_root, "publication.json"), "r", encoding="utf-8") as handle:
		record = json.load(handle)
	os.makedirs(site_dir)
	with open(os.path.join(site_dir, "index.html"), "w", encoding="utf-8") as handle:
		handle.write("recovery release " + record["bundle_sha256"] + "\n")


#============================================
def tree_hash(path: pathlib.Path) -> str:
	"""Return one exact physical-tree identity for disposable-state comparisons."""
	if not path.exists() or path.is_symlink():
		return "absent"
	hasher = hashlib.sha256()
	for current, directories, files in os.walk(path):
		directories.sort()
		for name in directories:
			child = pathlib.Path(current) / name
			if child.is_symlink():
				raise RuntimeError("Recovery proof state unexpectedly contains a directory link.")
			hasher.update(("D:" + str(child.relative_to(path)) + "\n").encode("utf-8"))
		for name in sorted(files):
			child = pathlib.Path(current) / name
			if child.is_symlink():
				raise RuntimeError("Recovery proof state unexpectedly contains a file link.")
			hasher.update(("F:" + str(child.relative_to(path)) + "\n").encode("utf-8"))
			hasher.update(child.read_bytes())
	return hasher.hexdigest()


#============================================
def state(root: pathlib.Path, report_date: str) -> dict:
	"""Capture the stable paths that define one publisher transaction."""
	record = root / "data" / "publications" / f"{report_date}.json"
	return {
		"docs": tree_hash(root / "docs"),
		"release": tree_hash(root / "generated" / "releases" / report_date),
		"archive": tree_hash(root / "data" / "publication_bundles" / report_date),
		"post": hashlib.sha256(
			(root / "docs" / "blog" / "posts" / f"{report_date}.md").read_bytes()
		).hexdigest()
		if (root / "docs" / "blog" / "posts" / f"{report_date}.md").is_file()
		else "absent",
		"record": hashlib.sha256(record.read_bytes()).hexdigest() if record.is_file() else "absent",
		"site": os.readlink(root / "site") if (root / "site").is_symlink() else "not-a-link",
		"staging": tuple(sorted(path.name for path in (root / "generated" / "staging").iterdir())),
	}


#============================================
def bundle_sha256(bundle_path: str) -> str:
	"""Read the asserted bundle identity without depending on its directory name."""
	with open(os.path.join(bundle_path, "bundle.json"), "r", encoding="utf-8") as handle:
		return json.load(handle)["bundle_sha256"]


#============================================
def child_crash(
	root: pathlib.Path, bundle_path: str, replace_existing: bool, boundary: str,
) -> None:
	"""Run a real import and SIGKILL immediately after one persisted commit transition."""
	if boundary not in BOUNDARIES:
		raise RuntimeError("Unknown crash-recovery boundary.")
	importer = load_publisher(root)
	import scripts.atomic_paths
	import scripts.publication_transaction
	real_marker = scripts.publication_transaction.write_transaction_marker
	real_exchange = scripts.atomic_paths.exchange_directories
	real_replace = scripts.publication_transaction.os.replace
	stage_root: str | None = None

	def kill_after(label: str) -> None:
		if label == boundary:
			os.kill(os.getpid(), signal.SIGKILL)

	def marker(stage: str, record: dict, expected: dict | None = None) -> None:
		nonlocal stage_root
		stage_root = stage
		real_marker(stage, record, expected)
		if expected is not None:
			kill_after("marker")

	def exchange(first: str, second: str) -> None:
		real_exchange(first, second)
		if stage_root is None:
			return
		pairs = {
			"release": {
				os.path.join(root, "generated", "releases", "2026-08-26"),
				os.path.join(stage_root, "site"),
			},
			"archive": {
				os.path.join(root, "data", "publication_bundles", "2026-08-26"),
				os.path.join(stage_root, "publication_archive"),
			},
			"docs": {os.path.join(root, "docs"), os.path.join(stage_root, "docs")},
		}
		for label, expected in pairs.items():
			if {first, second} == expected:
				kill_after(label)

	def replace(source: str, destination: str) -> None:
		real_replace(source, destination)
		if stage_root is None:
			return
		paths = {
			"release": (
				os.path.join(stage_root, "site"),
				os.path.join(root, "generated", "releases", "2026-08-26"),
			),
			"archive": (
				os.path.join(stage_root, "publication_archive"),
				os.path.join(root, "data", "publication_bundles", "2026-08-26"),
			),
			"site": (
				os.path.join(root, f".site-next-{os.path.basename(stage_root)}"),
				os.path.join(root, "site"),
			),
			"record": (
				os.path.join(stage_root, "publication.json"),
				os.path.join(root, "data", "publications", "2026-08-26.json"),
			),
		}
		for label, expected in paths.items():
			if (source, destination) == expected:
				kill_after(label)

	scripts.publication_transaction.write_transaction_marker = marker
	scripts.atomic_paths.exchange_directories = exchange
	scripts.publication_transaction.os.replace = replace
	importer.import_publication_bundle(bundle_path, str(root), recovery_build, replace_existing)
	raise RuntimeError("Crash boundary was not reached.")


#============================================
def child_recover(root: pathlib.Path) -> None:
	"""Invoke the publisher's actual recovery owner in a clean process."""
	load_publisher(root)
	import scripts.publication_transaction
	scripts.publication_transaction.reconcile_interrupted_staging(str(root))


#============================================
def child_retry(root: pathlib.Path, bundle_path: str, replace_existing: bool) -> None:
	"""Retry through the real public importer after recovery."""
	importer = load_publisher(root)
	result = importer.import_publication_bundle(
		bundle_path, str(root), recovery_build, replace_existing
	)
	print(json.dumps(result, sort_keys=True))


#============================================
def run_child(arguments: list[str]) -> subprocess.CompletedProcess[str]:
	"""Run one publisher action in a separate Python 3.13 process."""
	return subprocess.run(
		[*publisher_python_command(), str(pathlib.Path(__file__).resolve()), *arguments],
		check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
	)


#============================================
def completed_identity(root: pathlib.Path, report_date: str, expected_bundle: str) -> bool:
	"""Return whether one date is fully coherent for its exact new bundle identity."""
	record_path = root / "data" / "publications" / f"{report_date}.json"
	archive = root / "data" / "publication_bundles" / report_date
	release = root / "generated" / "releases" / report_date
	post = root / "docs" / "blog" / "posts" / f"{report_date}.md"
	if not all((record_path.is_file(), archive.is_dir(), release.is_dir(), post.is_file())):
		return False
	try:
		record = json.loads(record_path.read_text(encoding="utf-8"))
	except json.JSONDecodeError:
		return False
	return (
		record.get("bundle_sha256") == expected_bundle
		and (archive / "bundle.json").is_file()
		and (release / "index.html").is_file()
		and (root / "site").is_symlink()
		and os.path.realpath(root / "site") == os.path.realpath(release)
		and not tuple((root / "generated" / "staging").iterdir())
	)


#============================================
def proof_case(
	work_root: pathlib.Path,
	first_bundle: str,
	second_bundle: str,
	mode: str,
	boundary: str,
) -> dict:
	"""Prove one clean or replacement crash state recovers and retries coherently."""
	helpers = load_daily_publication_e2e()
	root = work_root / f"publisher-{mode}-{boundary}"
	root.mkdir()
	helpers.initialize_publisher(root)
	report_date = "2026-08-26"
	replace_existing = mode == "replacement"
	bundle = second_bundle if replace_existing else first_bundle
	if replace_existing:
		initial = run_child(["--retry", str(root), first_bundle])
		if initial.returncode != 0 or json.loads(initial.stdout).get("status") != "imported":
			raise RuntimeError("Replacement setup did not create the prior coherent publication.")
	prior = state(root, report_date)
	crash = run_child([
		"--child", str(root), bundle, boundary,
		"--replace-existing" if replace_existing else "--new-publication",
	])
	if crash.returncode != -signal.SIGKILL:
		raise RuntimeError(
			f"{mode}/{boundary} did not terminate by SIGKILL: {crash.returncode}; {crash.stderr.strip()}"
		)
	recovery = run_child(["--recover", str(root)])
	if recovery.returncode != 0:
		raise RuntimeError(f"{mode}/{boundary} recovery failed: {recovery.stderr.strip()}")
	new_identity = bundle_sha256(bundle)
	if boundary == "record":
		classification = "completed-new"
		if not completed_identity(root, report_date, new_identity):
			raise RuntimeError(f"{mode}/{boundary} did not retain the completed coherent publication.")
	else:
		classification = "retryable-clean" if mode == "clean" else "restored-prior"
		if state(root, report_date) != prior:
			raise RuntimeError(f"{mode}/{boundary} did not restore its exact prior coherent state.")
	retry = run_child([
		"--retry", str(root), bundle,
		"--replace-existing" if replace_existing else "--new-publication",
	])
	if retry.returncode != 0:
		raise RuntimeError(f"{mode}/{boundary} retry failed: {retry.stderr.strip()}")
	result = json.loads(retry.stdout)
	expected_statuses = {"replaced", "idempotent"} if replace_existing else {"imported", "idempotent"}
	if (
		result.get("status") not in expected_statuses
		or not completed_identity(root, report_date, new_identity)
	):
		raise RuntimeError(f"{mode}/{boundary} retry did not establish the expected coherent identity.")
	return {
		"mode": mode,
		"boundary": boundary,
		"killed_exit_status": crash.returncode,
		"recovery": classification,
		"retry_status": result["status"],
		"final_bundle_sha256": new_identity,
	}


#============================================
def main() -> None:
	"""Run every durable commit-boundary proof and emit concise JSON evidence."""
	parser = argparse.ArgumentParser()
	parser.add_argument("--child", nargs=3, metavar=("ROOT", "BUNDLE", "BOUNDARY"))
	parser.add_argument("--recover", metavar="ROOT")
	parser.add_argument("--retry", nargs=2, metavar=("ROOT", "BUNDLE"))
	parser.add_argument("--replace-existing", action="store_true")
	parser.add_argument("--new-publication", action="store_true")
	args = parser.parse_args()
	if args.child:
		child_crash(pathlib.Path(args.child[0]), args.child[1], args.replace_existing, args.child[2])
		return
	if args.recover:
		child_recover(pathlib.Path(args.recover))
		return
	if args.retry:
		child_retry(pathlib.Path(args.retry[0]), args.retry[1], args.replace_existing)
		return
	if args.replace_existing or args.new_publication:
		raise RuntimeError("Publication intent applies only to child or retry mode.")
	publisher_python_command()
	with tempfile.TemporaryDirectory(prefix="daily-publication-crash-recovery-") as temporary:
		work_root = pathlib.Path(temporary)
		first_bundle, first = maker_bundle(work_root, "crash-recovery-first")
		second_bundle, second = maker_bundle(work_root, "crash-recovery-replacement")
		if first["bundle_sha256"] == second["bundle_sha256"]:
			raise RuntimeError("Distinct deterministic run identities did not yield distinct bundles.")
		evidence = [
			proof_case(work_root, first_bundle, second_bundle, mode, boundary)
			for mode in ("clean", "replacement")
			for boundary in BOUNDARIES
		]
		print(json.dumps({"status": "passed", "cases": evidence}, sort_keys=True))


if __name__ == "__main__":
	main()

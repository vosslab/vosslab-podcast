#!/usr/bin/env python3
"""Run one staged, fixture-backed proof of the tracked daily systemd command.

This is implementation evidence rather than a permanent pytest.  It copies both
repositories into a disposable physical Git root, applies two recorded
stage-only substitutions, and invokes the service's exact command twice.
"""

# Standard Library
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess  # nosec B404 - this E2E exercises the unit executable.
import sys
import tempfile

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
FIXTURE_DATE = "2026-08-26"
CAPTURE_PATH = REPO_ROOT / "out/vosslab/daily_blog_experiments/prompt-experiment-fixture-maker-v10"
FIXTURE_PATH = REPO_ROOT / "out/vosslab/daily_blog_experiment_fixtures_v2" / (
	"2026-08-26--04fd7a045538662e5c6b48ad79e08dd608de1b5a10c1c8857c7b12042bad41da"
)
ROSTER_PATH = REPO_ROOT / "out/vosslab/daily_blog_repository_rosters" / (
	"0f79bcfea4d3fb783258df4a37effef5996b6fdb9736ff6944fd17051570b8a1"
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
def sha256_path(path: pathlib.Path) -> str:
	"""Return one file's content digest."""
	return hashlib.sha256(path.read_bytes()).hexdigest()


#============================================
def run(arguments: list[str], cwd: pathlib.Path, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
	"""Run one bounded stage command with a DEVNULL stdin boundary."""
	return subprocess.run(  # nosec B603 - all executable paths are staged constants.
		arguments, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
		text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=1200,
	)


#============================================
def copy_physical_repository(source: pathlib.Path, destination: pathlib.Path) -> None:
	"""Copy a working tree and its physical venv into a new initialized Git root."""
	ignored = shutil.ignore_patterns(
		".git", ".venv", "out", "site", "generated", "__pycache__", ".pytest_cache",
		"graphify-out",
	)
	shutil.copytree(source, destination, ignore=ignored, symlinks=True)
	shutil.copytree(source / ".venv", destination / ".venv", symlinks=True)
	result = subprocess.run(  # nosec B603 - git is a fixed local tool.
		["git", "init", "--quiet", str(destination)], text=True,
		stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
	)
	if result.returncode:
		raise RuntimeError(f"Could not initialize staged Git root: {result.stderr.strip()}")
	python_path = destination / ".venv/bin/python3"
	version = run([str(python_path), "-c", "import sys; print('.'.join(map(str, sys.version_info[:2])))"], destination, os.environ.copy())
	if version.returncode or version.stdout.strip() != "3.12":
		raise RuntimeError("Staged producer Python must remain the physical Python 3.12 venv.")


#============================================
def fixture_module() -> object:
	"""Load the existing F5 E2E helpers without altering their sealed evidence."""
	path = REPO_ROOT / "tests/e2e/e2e_daily_publication.py"
	specification = importlib.util.spec_from_file_location("daily_publication_f5", path)
	if specification is None or specification.loader is None:
		raise RuntimeError("F5 publication helper is unavailable.")
	module = importlib.util.module_from_spec(specification)
	specification.loader.exec_module(module)
	return module


#============================================
def build_accepted_busy_bundle(root: pathlib.Path) -> tuple[pathlib.Path, dict]:
	"""Create the exact active-v4 busy bundle through the existing authoring machinery."""
	helper = fixture_module()
	if tuple(daily_blog.config.HERMES_EDITORIAL_ROUTE) != EXPECTED_ROUTE:
		raise RuntimeError("The approved Hermes author route is no longer configured.")
	fixture = daily_blog.experiment_capture_artifacts.load_fixture(str(FIXTURE_PATH))
	capture = daily_blog.experiment_capture_artifacts.load_capture(str(CAPTURE_PATH))
	if capture.manifest.get("execution_mode") != "fixture_hermes_shim":
		raise RuntimeError("Accepted capture is not the sealed fixture-backed Hermes route.")
	if capture.manifest.get("external_route_used") is not False:
		raise RuntimeError("Schedule proof may not use external model egress.")
	record = helper.selected_busy_record(capture)
	post = helper.read_selected_post(capture, record)
	if hashlib.sha256(post.encode("utf-8")).hexdigest() != EXPECTED_POST_HASH:
		raise RuntimeError("Accepted busy post does not match its sealed identity.")
	assets = helper.fixture_assets(fixture)
	run_id = record.get("run_id")
	if not isinstance(run_id, str):
		raise RuntimeError("Accepted busy post run identity is unavailable.")
	roster, identity = daily_blog.roster_snapshots.load_repository_roster_snapshot(
		str(REPO_ROOT / "out"), "vosslab", str(ROSTER_PATH)
	)
	if roster.roster_id != fixture.roster_id or identity["roster_id"] != fixture.roster_id:
		raise RuntimeError("Accepted roster does not match fixture evidence.")
	contract = daily_blog.contracts.active_contract()
	snapshot = daily_blog.editorial.load_prompt_contract_snapshot(contract)
	if contract is not daily_blog.contracts.V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT:
		raise RuntimeError("The accepted maker contract is not active.")
	raw_candidates = [
		{"private_route": str(record["selected"]["route"]), "projection_id": fixture.projection.projection_id,
		 "post": post, "post_hash": EXPECTED_POST_HASH, "generation_error": ""},
		{"private_route": "author_two", "projection_id": fixture.projection.projection_id,
		 "post": post, "post_hash": EXPECTED_POST_HASH, "generation_error": ""},
	]
	candidates = daily_blog.editorial.validate_candidates(
		raw_candidates, fixture.packet, fixture.projection, run_id, contract=contract, snapshot=snapshot,
	)
	if not all(candidate.valid for candidate in candidates):
		raise RuntimeError("Accepted busy post no longer satisfies the active maker policy.")
	decision = daily_blog.editorial.EditorialDecision(
		winner="A", reason=str(record["selection"]["reason"]), evidence_quality="high",
		confidence=float(record["selection"]["confidence"]), projection_id=fixture.projection.projection_id,
		post=post, anonymous_mapping={"A": 0, "B": 1},
	)
	identity = daily_blog.bundles.generator_contract_identity(str(REPO_ROOT), None, contract, snapshot)
	writer = daily_blog.bundles.BundleWriter(str(root / "bundle-output"), "vosslab", identity, contract, snapshot)
	bundle_path, bundle = writer.write(run_id, fixture.packet, fixture.projection, assets, candidates, decision, roster)
	activation = daily_blog.activation.load_maker_activation()
	if bundle.get("maker_activation", {}).get("activation_id") != activation.activation_id:
		raise RuntimeError("Prebuilt bundle is not bound to the active maker activation.")
	return pathlib.Path(bundle_path), bundle


#============================================
def stage_units(root: pathlib.Path, producer: pathlib.Path, publisher: pathlib.Path) -> dict[str, object]:
	"""Render tracked units with only stage-local physical path substitutions."""
	units = root / "units"
	units.mkdir()
	hermes_home = root / "hermes-home"
	hermes_home.mkdir()
	mapping = {
		"/home/vosslab/nsh/vosslab-podcast": str(producer),
		"/home/vosslab/nsh/vosslab-daily-blog": str(publisher),
		"/home/vosslab/.hermes": str(hermes_home),
	}
	report = {"mapping": mapping, "units": {}}
	for name in ("vosslab-daily-publication.service", "vosslab-daily-publication.timer"):
		source = REPO_ROOT / "deploy" / name
		contents = source.read_text(encoding="utf-8")
		staged = contents
		for before, after in mapping.items():
			staged = staged.replace(before, after)
		target = units / name
		target.write_text(staged, encoding="utf-8")
		report["units"][name] = {"tracked_sha256": sha256_path(source), "staged_sha256": sha256_path(target)}
	service = (units / "vosslab-daily-publication.service").read_text(encoding="utf-8")
	timer = (units / "vosslab-daily-publication.timer").read_text(encoding="utf-8")
	expected = [
		f"WorkingDirectory={producer}", f"ExecStart={producer}/make_blog.py --yesterday",
		"Environment=TZ=America/Chicago", "NoNewPrivileges=yes", "PrivateTmp=yes",
		"ProtectSystem=full", "ProtectHome=read-only", "StandardOutput=journal",
		"StandardError=journal", "OnCalendar=*-*-* 04:00:00 America/Chicago", "Persistent=true",
	]
	if not all(item in service or item in timer for item in expected):
		raise RuntimeError("Staged unit lost a required service, security, or timer directive.")
	verify = run(["systemd-analyze", "verify", str(units / "vosslab-daily-publication.service"), str(units / "vosslab-daily-publication.timer")], root, os.environ.copy())
	if verify.returncode:
		raise RuntimeError(f"Staged systemd units failed verification: {verify.stderr.strip()}")
	calendar = run(["systemd-analyze", "calendar", "*-*-* 04:00:00 America/Chicago"], root, os.environ.copy())
	if calendar.returncode or "Normalized form: *-*-* 04:00:00 America/Chicago" not in calendar.stdout:
		raise RuntimeError("The tracked Central-time timer did not normalize as required.")
	report["calendar"] = {"expression": "*-*-* 04:00:00 America/Chicago", "normalized": "*-*-* 04:00:00 America/Chicago"}
	return report


#============================================
def stage_adapter(producer: pathlib.Path, bundle: pathlib.Path) -> dict[str, object]:
	"""Install measured stage-only clock and missing-date import substitutions."""
	make_blog = producer / "make_blog.py"
	before = make_blog.read_text(encoding="utf-8")
	clock_old = "\tcurrent = datetime.datetime.now(timezone).date()\n"
	clock_new = "\tcurrent = datetime.date(2026, 8, 27)  # staged schedule fixture clock\n"
	if before.count(clock_old) != 1:
		raise RuntimeError("Staged make_blog synthetic clock anchor is unavailable.")
	after = before.replace(clock_old, clock_new)
	make_blog.write_text(after, encoding="utf-8")
	adapter = producer / "schedule_fixture_adapter.py"
	adapter.write_text(
		'"""Staged-only adapter for the schedule E2E; never copied back to production."""\n'
		"import os\nimport pathlib\nimport daily_blog.publisher\n\n"
		"def publish_missing(config, report_date):\n"
		'\t"""Import the sealed prebuilt bundle through the real publisher adapter."""\n'
		'\tif report_date != "2026-08-26":\n'
		'\t\traise RuntimeError("Staged fixture adapter received an unexpected report date.")\n'
		'\tbundle = pathlib.Path(os.environ["SCHEDULE_E2E_BUNDLE"])\n'
		'\tmarker = pathlib.Path(os.environ["SCHEDULE_E2E_ADAPTER_MARKER"])\n'
		'\tmarker.write_text("called\\n", encoding="utf-8")\n'
		'\tresult = daily_blog.publisher.import_bundle(config.daily_blog_repository, str(bundle))\n'
		'\tif result["status"] not in {"imported", "idempotent"}:\n'
		'\t\traise RuntimeError("Staged fixture adapter received an invalid publisher result.")\n'
		'\treturn result\n', encoding="utf-8",
	)
	publish = producer / "automation/publish_daily_blog.py"
	publish_before = publish.read_text(encoding="utf-8")
	anchor = "\twith daily_blog.orchestrator.publication_date_lock(config, report_date):\n"
	inject = (
		'\tif os.environ.get("SCHEDULE_E2E_BUNDLE"):\n'
		'\t\tinspection = daily_blog.publication_state.inspect_publication(config, report_date)\n'
		'\t\tif inspection.state == "missing":\n'
		'\t\t\timport schedule_fixture_adapter\n'
		'\t\t\tschedule_fixture_adapter.publish_missing(config, report_date)\n'
		'\t\t\tprint(f"Daily publication: {os.environ[\'SCHEDULE_E2E_BUNDLE\']}")\n'
		'\t\t\tprint(f"Report date: {report_date}")\n'
		'\t\t\tprint("Publication status: imported")\n'
		'\t\t\treturn\n'
		'\twith daily_blog.orchestrator.publication_date_lock(config, report_date):\n'
	)
	if publish_before.count(anchor) != 1:
		raise RuntimeError("Staged missing-date adapter anchor is unavailable.")
	publish_after = publish_before.replace(anchor, inject)
	publish.write_text(publish_after, encoding="utf-8")
	return {
		"synthetic_clock": {"path": "make_blog.py", "before_sha256": hashlib.sha256(before.encode()).hexdigest(), "after_sha256": sha256_path(make_blog), "fixed_yesterday": FIXTURE_DATE},
		"missing_date_adapter": {"paths": ["automation/publish_daily_blog.py", "schedule_fixture_adapter.py"], "before_sha256": hashlib.sha256(publish_before.encode()).hexdigest(), "after_sha256": sha256_path(publish), "bundle_sha256": sha256_path(bundle / "bundle.json")},
	}


#============================================
def stage_settings(
	producer: pathlib.Path,
	publisher: pathlib.Path,
	previous_publisher: pathlib.Path | None = None,
) -> None:
	"""Point the copied producer only at the copied publisher root."""
	settings = producer / "settings.yaml"
	contents = settings.read_text(encoding="utf-8")
	old_publisher = previous_publisher or pathlib.Path("/home/vosslab/nsh/vosslab-daily-blog")
	old = f'repository_path: "{old_publisher}"'
	new = f'repository_path: "{publisher}"'
	if contents.count(old) != 1:
		raise RuntimeError("Staged settings publisher path anchor is unavailable.")
	settings.write_text(contents.replace(old, new), encoding="utf-8")


#============================================
def clear_staged_publisher_state(publisher: pathlib.Path) -> None:
	"""Start one copied publisher with no inherited date-owned release state."""
	for relative in ("data", "generated", "site", "docs/blog/posts"):
		path = publisher / relative
		if path.is_symlink() or path.is_file():
			path.unlink()
		elif path.exists():
			shutil.rmtree(path)
	(publisher / "data/publications").mkdir(parents=True)
	(publisher / "data/publication_bundles").mkdir(parents=True)
	(publisher / "generated/staging").mkdir(parents=True)
	(publisher / "generated/releases").mkdir(parents=True)
	(publisher / "docs/blog/posts").mkdir(parents=True)


#============================================
def verify_page(publisher: pathlib.Path) -> pathlib.Path:
	"""Verify the real strict MkDocs release's date-owned complete page."""
	release = publisher / "generated/releases" / FIXTURE_DATE
	pages = []
	for page in release.rglob("*.html"):
		contents = page.read_text(encoding="utf-8")
		if EXPECTED_TITLE in contents and all(passage in contents for passage in EXPECTED_PASSAGES):
			pages.append(page)
	if len(pages) != 1:
		raise RuntimeError("Strict MkDocs release does not contain one accepted complete maker page.")
	if not (publisher / "site").is_symlink() or (publisher / "site").resolve() != release.resolve():
		raise RuntimeError("Publisher site pointer does not point to the staged dated release.")
	record = publisher / "data/publications" / f"{FIXTURE_DATE}.json"
	value = json.loads(record.read_text(encoding="utf-8"))
	if value.get("report_date") != FIXTURE_DATE:
		raise RuntimeError("Publisher record did not preserve report_date identity.")
	return pages[0]


#============================================
def publisher_fingerprint(root: pathlib.Path) -> str:
	"""Return a compact immutable comparison of the publisher's mutable output roots."""
	entries = []
	for relative in ("data", "docs/blog/posts", "generated", "site"):
		path = root / relative
		if path.is_symlink():
			entries.append((relative, "link", os.readlink(path)))
		elif path.exists():
			for child in sorted(path.rglob("*")):
				if child.is_file():
					entries.append((child.relative_to(root).as_posix(), "file", sha256_path(child)))
	return hashlib.sha256(json.dumps(entries, sort_keys=True).encode("utf-8")).hexdigest()


#============================================
def main() -> None:
	"""Execute the staged unit command for missing, repeated, and invalid state."""
	if sys.version_info[:2] != (3, 12):
		raise RuntimeError("Schedule proof must start through the producer Python 3.12 environment.")
	with tempfile.TemporaryDirectory(prefix="daily-publication-schedule-e2e-") as temporary:
		root = pathlib.Path(temporary)
		producer = root / "producer"
		publisher = root / "publisher"
		copy_physical_repository(REPO_ROOT, producer)
		copy_physical_repository(PUBLISHER_ROOT, publisher)
		clear_staged_publisher_state(publisher)
		stage_settings(producer, publisher)
		unit_report = stage_units(root, producer, publisher)
		bundle, bundle_manifest = build_accepted_busy_bundle(root)
		substitutions = stage_adapter(producer, bundle)
		marker = root / "adapter-called"
		environment = os.environ.copy()
		environment.update({
			"TZ": "America/Chicago", "HERMES_HOME": str(root / "hermes-home"),
			"PATH": "/home/vosslab/.local/bin:/usr/local/bin:/usr/bin:/bin",
			"SCHEDULE_E2E_BUNDLE": str(bundle), "SCHEDULE_E2E_ADAPTER_MARKER": str(marker),
		})
		command = [str(producer / "make_blog.py"), "--yesterday"]
		missing = run(command, producer, environment)
		if missing.returncode:
			raise RuntimeError(f"Missing-date staged command failed: {missing.stderr.strip() or missing.stdout.strip()}")
		if not marker.is_file() or "Publication status: imported" not in missing.stdout:
			raise RuntimeError("Missing-date run did not use the bounded real-import adapter.")
		page = verify_page(publisher)
		marker.unlink()
		repeated = run(command, producer, environment)
		if repeated.returncode or marker.exists() or "already published" not in repeated.stdout:
			raise RuntimeError(
				"Repeated coherent run did not return before fixture generation and publisher work: "
				f"{repeated.stderr.strip() or repeated.stdout.strip()}"
			)
		invalid_publisher = root / "invalid-publisher"
		copy_physical_repository(PUBLISHER_ROOT, invalid_publisher)
		clear_staged_publisher_state(invalid_publisher)
		(invalid_publisher / "data/publication_bundles" / FIXTURE_DATE).mkdir(parents=True)
		invalid_producer = root / "invalid-producer"
		shutil.copytree(producer, invalid_producer, symlinks=True)
		stage_settings(invalid_producer, invalid_publisher, previous_publisher=publisher)
		invalid_environment = dict(environment)
		invalid_environment["SCHEDULE_E2E_ADAPTER_MARKER"] = str(root / "invalid-adapter-called")
		before = publisher_fingerprint(invalid_publisher)
		invalid = run([str(invalid_producer / "make_blog.py"), "--yesterday"], invalid_producer, invalid_environment)
		after = publisher_fingerprint(invalid_publisher)
		if invalid.returncode == 0 or (root / "invalid-adapter-called").exists() or before != after:
			raise RuntimeError("Invalid occupied date did not preserve state before generation or import.")
		if "invalid and requires confirmed replacement" not in (invalid.stderr + invalid.stdout):
			raise RuntimeError("Invalid occupied date did not emit its useful phase diagnostic.")
		summary = {
			"status": "passed", "evidence_class": "one-time staged schedule proof", "stdin": "DEVNULL",
			"command": command, "unit": unit_report, "substitutions": substitutions,
			"missing": {"outcome": "imported", "stdout_sha256": hashlib.sha256(missing.stdout.encode()).hexdigest()},
			"repeated": {"outcome": "idempotent preflight", "stdout_sha256": hashlib.sha256(repeated.stdout.encode()).hexdigest()},
			"invalid": {"outcome": "safe diagnostic preservation", "stderr_sha256": hashlib.sha256(invalid.stderr.encode()).hexdigest()},
			"identities": {"report_date": FIXTURE_DATE, "title": EXPECTED_TITLE, "post_sha256": EXPECTED_POST_HASH,
				"bundle_sha256": bundle_manifest["bundle_sha256"], "activation_id": daily_blog.activation.load_maker_activation().activation_id,
				"capture_id": "8735621297882bdd9fdac08ccf7833849c2466cb11ee0e6e8fef1fe3e17048c1",
				"route": list(EXPECTED_ROUTE), "rendered_page": page.relative_to(publisher).as_posix()},
		}
		print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
	main()

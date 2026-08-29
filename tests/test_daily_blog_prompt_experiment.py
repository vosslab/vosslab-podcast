"""Sealed prompt-experiment artifact and isolation tests."""

# Standard Library
import dataclasses
import json
import pathlib
import types

# PIP3 modules
import pytest

# local repo modules
import daily_blog.config
import daily_blog.experiment_fixture_contract
import daily_blog.io_utils
import daily_blog.projection
import daily_blog.repositories
import daily_blog.roster_snapshots
import daily_blog.schema
from automation import experiment_daily_blog_prompts as experiment
from automation import run_daily_blog_fixture_capture as fixture_capture


TEST_ROSTER_ID = "c" * 64


#============================================
def packet_for(date: str) -> daily_blog.schema.EvidencePacket:
	"""Create one small, identity-valid captured evidence packet."""
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/project", "a" * 40, "docs/CHANGELOG.md", "b" * 40,
		f"## {date}\n\n- Built an exact experiment fixture.\n", "test",
	)
	mirror = {
		"default_revision": "d" * 40,
		"ref_fingerprint": daily_blog.io_utils.hash_value(["d" * 40]),
		"repository": "vosslab/project",
		"repository_url": "https://github.com/vosslab/project",
		"roster_id": TEST_ROSTER_ID,
	}
	return daily_blog.schema.EvidencePacket.create(
		date, "America/Chicago", True, {}, [mirror], [], [item],
	)


#============================================
def test_capture_scorecards_require_exact_selected_post_passages() -> None:
	"""The sealed capture rejects referee grounding invented outside the selected post."""
	post = "# A maker note\n\nI built the artifact.\n"
	fields = (
		experiment.daily_blog.rubric_calibration.CALIBRATION_CONTRACT.expected_criteria
	)
	scorecard = {
		"status": "scored",
		"scores": {field: 3 for field, _title, _weight in fields},
		"passages": {field: "I built the artifact." for field, _title, _weight in fields},
		"reasons": {field: "The passage shows maker work." for field, _title, _weight in fields},
		"weighted_score": 3.0,
		"overall_reason": "The exact passage supports the score.",
	}

	assert experiment.daily_blog.experiment_capture_artifacts._valid_scorecard(scorecard, post)
	scorecard["passages"][fields[0][0]] = "This passage is absent."
	assert not experiment.daily_blog.experiment_capture_artifacts._valid_scorecard(scorecard, post)


#============================================
def fixture(root: pathlib.Path, date: str, publisher_bundle: bool = False) -> pathlib.Path:
	"""Write a v2 capture fixture or one deliberately retired bundle-shaped input."""
	root.mkdir()
	packet = packet_for(date)
	projection = daily_blog.projection.build_projection(
		packet,
		{"context_chars": 12000, "excerpt_chars": 2000, "commit_subject_chars": 160},
	)
	evidence = root / "evidence.json"
	context = root / "editorial_projection.json"
	evidence.write_text(json.dumps(packet.to_dict()), encoding="utf-8")
	context.write_text(json.dumps(projection.to_dict()), encoding="utf-8")
	if publisher_bundle:
		manifest = {
			"schema_version": daily_blog.schema.BUNDLE_SCHEMA_VERSION,
			"report_date": date,
			"contracts": {},
			"generator": {},
			"evidence": {
				"path": "evidence.json",
				"packet_id": packet.packet_id,
				"sha256": daily_blog.io_utils.hash_value(packet.to_dict()),
			},
			"editorial_projection": {
				"path": "editorial_projection.json",
				"projection_id": projection.projection_id,
				"sha256": daily_blog.io_utils.hash_value(projection.to_dict()),
			},
		}
		manifest["bundle_sha256"] = daily_blog.io_utils.hash_value(manifest)
		(root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
	else:
		identity = {
			"config_identity": {
				"fields": list(daily_blog.experiment_fixture_contract.CONFIG_IDENTITY_FIELDS),
				"sha256": daily_blog.io_utils.hash_value({}),
			},
			"evidence_count": len(packet.items),
			"evidence_packet_id": packet.packet_id,
			"files": {
				"evidence.json": {
					"bytes": evidence.stat().st_size,
					"sha256": experiment._sha256(evidence),
				},
				"editorial_projection.json": {
					"bytes": context.stat().st_size,
					"sha256": experiment._sha256(context),
				},
			},
			"mirrors": daily_blog.experiment_fixture_contract.fixture_mirror_identities(
				[mirror.to_dict() for mirror in packet.mirrors]
			),
			"projection_id": projection.projection_id,
			"projection_rendered_chars": len(projection.render_context()),
			"report_date": date,
			"repository_count": len(projection.repositories),
			"repository_roster_snapshot": {
				"captured_utc": "2026-08-28T00:00:00Z",
				"repository_count": len(packet.mirrors),
				"roster_id": TEST_ROSTER_ID,
				"schema_version": daily_blog.roster_snapshots.ROSTER_SNAPSHOT_SCHEMA_VERSION,
				"source": {
					"fresh": True,
					"kind": "github_owner_repositories",
					"policy": daily_blog.repositories.REPOSITORY_POLICY_VERSION,
				},
			},
			"schema_version": experiment.FIXTURE_SCHEMA,
			"source_repository": "vosslab-daily-blog",
		}
		manifest = daily_blog.experiment_fixture_contract.seal_fixture_manifest(identity)
		(root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
	for artifact in root.iterdir():
		artifact.chmod(0o600)
	root.chmod(0o700)
	if publisher_bundle:
		return root
	destination = root.with_name(f"{date}--{manifest['fixture_id']}")
	root.rename(destination)
	root = destination
	return root


#============================================
def approved_identities(
	busy: experiment.ExperimentFixture,
	quiet: experiment.ExperimentFixture,
) -> dict[str, tuple[str, str, str]]:
	"""Return the test-only allowlist for two locally generated sealed captures."""
	return {
		"busy": (busy.date, busy.fixture_id, busy.roster_id),
		"quiet": (quiet.date, quiet.fixture_id, quiet.roster_id),
	}


#============================================
def config(tmp_path: pathlib.Path) -> daily_blog.config.DailyBlogConfig:
	"""Use fake isolated routes; dependency injection keeps tests offline."""
	return daily_blog.config.DailyBlogConfig(
		settings_path="settings.yaml", output_root=str(tmp_path), output_owner="Neil",
		report_timezone="America/Chicago", daily_blog_repository=str(tmp_path),
		mirror_cache_root=str(tmp_path / "mirrors"), identity_names=("Neil",), identity_emails=(),
		author_routes=(
			daily_blog.config.RoleRoute("one", ("fake",)),
			daily_blog.config.RoleRoute("two", ("fake",)),
		),
		referee_route=daily_blog.config.RoleRoute("judge", ("fake",)),
		collection_limits={},
		projection_limits={},
		prompt_limits={"author_chars": 72000, "referee_chars": 88000},
	)


#============================================
def test_rejects_symlink_and_existing_output_target(tmp_path: pathlib.Path) -> None:
	"""Fixture containment and atomic output creation reject unsafe reuse."""
	source = fixture(tmp_path / "source", "2026-08-22")
	link = tmp_path / "link"
	link.symlink_to(source, target_is_directory=True)
	with pytest.raises((OSError, RuntimeError)):
		experiment.load_fixture(str(link))
	(tmp_path / "out").mkdir(mode=0o700)
	(tmp_path / "out" / "prompt-experiment-again").mkdir()
	with pytest.raises(RuntimeError, match="already exists"):
		experiment._open_output_transaction(str(tmp_path / "out"), "prompt-experiment-again")


#============================================
def test_route_metadata_redacts_sensitive_arguments() -> None:
	"""Artifacts expose route identity without retaining route secrets."""
	route = daily_blog.config.RoleRoute(
		"author",
		("hermes", "--api-key=do-not-store", "--query-file", "-"),
	)
	metadata = experiment._route_metadata(route)
	assert metadata["executable"] == "hermes"
	assert "command" not in metadata


#============================================
def test_compare_normalizes_a_positional_verdict_to_canonical_arms(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A displayed-A verdict maps to the correct canonical arm in both orders."""
	monkeypatch.setattr(
		experiment.daily_blog.editorial,
		"_referee_verdict",
		lambda *_args, **_kwargs: {
			"winner": "A", "reason": "Selected displayed A.",
			"evidence_quality": "high", "confidence": 1.0,
		},
	)
	forward = experiment._compare(
		object(), object(), object(), object(), object(), object(), False,
	)
	reverse = experiment._compare(
		object(), object(), object(), object(), object(), object(), True,
	)
	assert (forward["order"], forward["verdict"]) == ("AB", "A")
	assert (reverse["order"], reverse["verdict"]) == ("BA", "B")


#============================================
def test_pairwise_comparisons_run_both_orders_for_every_generated_pair(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Every fixed candidate pair is judged once in each displayed position."""
	calls = []

	def compare(
		_left: object,
		_right: object,
		_projection: object,
		_config: object,
		_runner: object,
		_snapshot: object,
		reverse: bool,
	) -> dict[str, object]:
		"""Record the positional arm and return one normalized successful verdict."""
		calls.append(reverse)
		return {
			"order": "BA" if reverse else "AB",
			"verdict": "B",
			"parsed": True,
			"details": {"winner": "A" if reverse else "B"},
		}

	monkeypatch.setattr(experiment, "_compare", compare)
	monkeypatch.setattr(
		experiment.daily_blog.editorial,
		"load_prompt_contract_snapshot",
		lambda _contract: object(),
	)
	selected = {
		arm: (object(), {"arm": arm})
		for arm in experiment.DEFAULT_ARMS
	}
	fixture_value = types.SimpleNamespace(projection=object())
	comparisons = experiment._run_pairwise_comparisons(
		selected, "busy", fixture_value, 1, object(), object(),
	)
	assert len(comparisons) == len(
		experiment.daily_blog.experiment_capture_artifacts.COMPARISON_PAIRS
	) * 2
	assert calls == [False, True] * len(
		experiment.daily_blog.experiment_capture_artifacts.COMPARISON_PAIRS
	)
	for pair in experiment.daily_blog.experiment_capture_artifacts.COMPARISON_PAIRS:
		matching = [item for item in comparisons if item["pair"] == pair]
		assert [item["order"] for item in matching] == ["AB", "BA"]
		assert all(item["repetition"] == 1 for item in matching)


#============================================
def failed_capture_matrix(
	fixtures: dict[str, experiment.ExperimentFixture],
) -> tuple[
	list[dict[str, object]],
	list[dict[str, object]],
	list[dict[str, object]],
]:
	"""Build one complete, redacted capture matrix whose route calls all failed."""
	records = []
	comparisons = []
	errors = []
	repetitions = experiment.daily_blog.rubric_calibration.MIN_REPETITIONS
	for fixture_name, fixture_value in fixtures.items():
		for repetition in range(repetitions):
			for arm in experiment.DEFAULT_ARMS:
				snapshot = experiment.daily_blog.editorial.load_prompt_contract_snapshot(
					experiment.daily_blog.contracts.resolve_maker_experiment_contract(arm)
				)
				diagnostic = {"stage": "author_generation", "code": "ExpectedFailure"}
				records.append({
					"fixture": fixture_name,
					"fixture_hashes": fixture_value.hashes,
					"fixture_identity": {
						"fixture_id": fixture_value.fixture_id,
						"roster_id": fixture_value.roster_id,
						"packet_id": fixture_value.packet.packet_id,
						"projection_id": fixture_value.projection.projection_id,
					},
					"arm": arm,
					"repetition": repetition,
					"run_id": f"{fixture_name}-{arm}-{repetition}",
					"prompt_identity": experiment.daily_blog.editorial.prompt_contract_identity(
						snapshot=snapshot
					),
					"snapshot_digest": snapshot.integrity_sha256,
					"candidate_records": [],
					"selection": {
						"winner": "UNAVAILABLE",
						"publication_invalid": True,
						"reason": "No candidate was available.",
					},
					"selected": None,
					"scorecard": {"status": "unavailable"},
					"diagnostic": diagnostic,
					"seconds": 0.0,
				})
				errors.append({
					"fixture": fixture_name,
					"arm": arm,
					"repetition": repetition,
					"diagnostic": diagnostic,
				})
			for pair in (
				experiment.daily_blog.experiment_capture_artifacts.COMPARISON_PAIRS
			):
				for order in ("AB", "BA"):
					comparisons.append({
						"fixture": fixture_name,
						"repetition": repetition,
						"pair": pair,
						"order": order,
						"verdict": "ERROR",
						"parsed": False,
						"details": None,
						"selected_candidates": [None, None],
					})
	return records, comparisons, errors


#============================================
def persist_failed_capture(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
	case: str,
) -> pathlib.Path:
	"""Persist one deliberately malformed counterbalanced comparison matrix."""
	busy = experiment.load_fixture(str(fixture(tmp_path / "busy", "2026-08-26")))
	quiet = experiment.load_fixture(str(fixture(tmp_path / "quiet", "2026-08-23")))
	fixtures = {"busy": busy, "quiet": quiet}
	monkeypatch.setattr(
		experiment.daily_blog.experiment_capture_artifacts,
		"APPROVED_FIXTURE_ROTATION",
		approved_identities(busy, quiet),
	)
	records, comparisons, errors = failed_capture_matrix(fixtures)
	first_ba = next(
		index for index, comparison in enumerate(comparisons)
		if comparison["order"] == "BA"
	)
	if case == "missing_ba":
		comparisons.pop(first_ba)
	elif case == "duplicate_ab":
		comparisons[first_ba]["order"] = "AB"
	elif case == "wrong_ba_verdict":
		comparisons[first_ba].update({
			"verdict": "A",
			"parsed": True,
			"details": {"winner": "A"},
		})
	transaction = experiment._open_output_transaction(
		str(tmp_path / "captures"),
		f"prompt-experiment-{case.replace('_', '-')}",
	)
	try:
		code, output = experiment._commit_experiment_report(
			transaction,
			transaction.output_name,
			fixtures,
			experiment.DEFAULT_ARMS,
			experiment.daily_blog.rubric_calibration.MIN_REPETITIONS,
			[
				experiment._route_metadata(daily_blog.config.RoleRoute(
					"one", daily_blog.config.HERMES_EDITORIAL_ROUTE,
				)),
				experiment._route_metadata(daily_blog.config.RoleRoute(
					"two", daily_blog.config.HERMES_EDITORIAL_ROUTE,
				)),
				experiment._route_metadata(daily_blog.config.RoleRoute(
					"judge", daily_blog.config.HERMES_EDITORIAL_ROUTE,
				)),
			],
			records,
			comparisons,
			errors,
			experiment.daily_blog.experiment_capture_artifacts.EXTERNAL_HERMES,
			None,
		)
		assert code == 1
		return output
	finally:
		experiment.os.close(transaction.stage_fd)
		experiment.os.close(transaction.root_fd)


#============================================
@pytest.mark.parametrize(
	("case", "message"),
	(
		("missing_ba", "matrix is incomplete"),
		("duplicate_ab", "duplicate comparisons"),
		("wrong_ba_verdict", "canonical verdict"),
	),
)
def test_persisted_capture_rejects_unbalanced_or_noncanonical_comparisons(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
	case: str,
	message: str,
) -> None:
	"""The disk loader enforces both orders and canonicalizes positional winners."""
	path = persist_failed_capture(tmp_path, monkeypatch, case)
	with pytest.raises(RuntimeError, match=message):
		experiment.daily_blog.experiment_capture_artifacts.load_capture(str(path))


#============================================
@pytest.mark.parametrize(
	("artifact_name", "ambiguous_json"),
	(
		("manifest.json", b'{"schema_version":"one","schema_version":"two"}'),
		("report.json", b'{"schema_version":NaN}'),
	),
)
def test_capture_loader_rejects_ambiguous_sealed_json(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
	artifact_name: str,
	ambiguous_json: bytes,
) -> None:
	"""Capture artifact loading rejects duplicate names and non-finite JSON values."""
	path = persist_failed_capture(tmp_path, monkeypatch, "missing_ba")
	(path / artifact_name).write_bytes(ambiguous_json)
	with pytest.raises(RuntimeError, match="Experiment capture (manifest|report) is invalid"):
		experiment.daily_blog.experiment_capture_artifacts.load_capture(str(path))


#============================================
def test_preflight_routes_returns_only_safe_metadata(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Real-run preflight verifies both authors and the referee before generation."""
	monkeypatch.setattr(experiment.shutil, "which", lambda _value: "/usr/bin/fake")
	metadata = experiment.preflight_routes(config(tmp_path))
	assert [item["name"] for item in metadata] == ["one", "two", "judge"]
	bad = config(tmp_path)
	object.__setattr__(bad, "author_routes", (bad.author_routes[0],))
	with pytest.raises(RuntimeError, match="exactly two"):
		experiment.preflight_routes(bad)
	monkeypatch.setattr(experiment.shutil, "which", lambda _value: None)
	with pytest.raises(RuntimeError, match="unavailable"):
		experiment.preflight_routes(config(tmp_path))


#============================================
def test_injected_runner_still_validates_the_exact_route_roster_before_output(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Dependency injection bypasses command execution, not route-contract validation."""
	busy_path = fixture(tmp_path / "busy", "2026-08-26")
	quiet_path = fixture(tmp_path / "quiet", "2026-08-23")
	busy = experiment.load_fixture(str(busy_path))
	quiet = experiment.load_fixture(str(quiet_path))
	monkeypatch.setattr(experiment, "PRODUCTION_APPROVED_FIXTURES", approved_identities(busy, quiet))
	bad = config(tmp_path)
	object.__setattr__(bad, "author_routes", (bad.author_routes[0],))
	with pytest.raises(RuntimeError, match="exactly two"):
		experiment.run_experiment(
			bad,
			str(busy_path),
			str(quiet_path),
			runner=object(),
		)
	assert not (tmp_path / "Neil" / experiment.EXPERIMENT_ROOT_NAME).exists()


#============================================
def test_prompt_experiment_rejects_retired_publisher_bundle_input(tmp_path: pathlib.Path) -> None:
	"""The private runner accepts only the first-class capture schema after cutover."""
	bundle = fixture(tmp_path / "bundle", "2026-08-22", publisher_bundle=True)
	with pytest.raises(RuntimeError, match="active capture schema"):
		experiment.load_fixture(str(bundle))


#============================================
def test_consumer_rejects_unapproved_fixture_date_identity_and_roster(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The experiment consumer admits only the selected immutable fixture identities."""
	busy = experiment.load_fixture(str(fixture(tmp_path / "busy", "2026-08-26")))
	quiet = experiment.load_fixture(str(fixture(tmp_path / "quiet", "2026-08-23")))
	monkeypatch.setattr(experiment, "PRODUCTION_APPROVED_FIXTURES", approved_identities(busy, quiet))
	with pytest.raises(experiment.FixtureSelectionError, match="approved sealed identity"):
		experiment._validate_fixture_selection(
			{"busy": dataclasses.replace(busy, date="2026-08-25"), "quiet": quiet}
		)
	with pytest.raises(experiment.FixtureSelectionError, match="approved sealed identity"):
		experiment._validate_fixture_selection(
			{"busy": dataclasses.replace(busy, fixture_id="wrong-fixture"), "quiet": quiet}
		)
	with pytest.raises(experiment.FixtureSelectionError, match="approved sealed identity"):
		experiment._validate_fixture_selection(
			{"busy": dataclasses.replace(busy, roster_id="wrong-roster"), "quiet": quiet}
		)


#============================================
def test_consumer_rejects_unapproved_input_before_creating_output(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Identity rejection happens before any private experiment directory is created."""
	busy_path = fixture(tmp_path / "busy", "2026-08-26")
	quiet_path = fixture(tmp_path / "quiet", "2026-08-23")
	busy = experiment.load_fixture(str(busy_path))
	quiet = experiment.load_fixture(str(quiet_path))
	allowlist = approved_identities(busy, quiet)
	allowlist["busy"] = (busy.date, "wrong-fixture", busy.roster_id)
	monkeypatch.setattr(experiment, "PRODUCTION_APPROVED_FIXTURES", allowlist)
	with pytest.raises(experiment.FixtureSelectionError, match="approved sealed identity"):
		experiment.run_experiment(
			config(tmp_path),
			str(busy_path),
			str(quiet_path),
			runner=object(),
		)
	assert not (tmp_path / "Neil" / experiment.EXPERIMENT_ROOT_NAME).exists()


#============================================
def test_main_distinguishes_fixture_selection_without_leaking_diagnostics(
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
) -> None:
	"""The CLI reports the sealed-rotation boundary without exposing input diagnostics."""
	secret = "/private/fixture --api-key=not-for-stderr"
	args = [
		"--busy-fixture",
		"/abs/busy",
		"--quiet-fixture",
		"/abs/quiet",
	]
	monkeypatch.setattr(experiment.daily_blog.config, "load_config", lambda _path: object())
	monkeypatch.setattr(
		experiment,
		"run_experiment",
		lambda *_args, **_kwargs: (_ for _ in ()).throw(experiment.FixtureSelectionError(secret)),
	)
	assert experiment.main(args) == 2
	fixture_message = capsys.readouterr().err
	monkeypatch.setattr(
		experiment,
		"run_experiment",
		lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(secret)),
	)
	assert experiment.main(args) == 2
	generic_message = capsys.readouterr().err
	assert fixture_message == (
		"Prompt experiment blocked: fixture selection does not match the reviewed sealed rotation.\n"
	)
	assert generic_message == (
		"Prompt experiment blocked; inspect the private artifact or configuration.\n"
	)
	assert secret not in fixture_message + generic_message


#============================================
def test_repository_root_discovery_uses_git_response(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: pathlib.Path,
) -> None:
	"""Executable bootstrap accepts the repository root discovered by Git."""
	class Result:
		returncode = 0
		stdout = str(tmp_path) + "\n"
		stderr = ""
	monkeypatch.setattr(experiment.subprocess, "run", lambda *_args, **_kwargs: Result())
	assert experiment._repository_root_from_git("independent-script-path.py") == tmp_path


#============================================
def test_rejects_unsafe_arms_hashless_manifest_and_relative_paths(tmp_path: pathlib.Path) -> None:
	"""The sealed runner rejects caller-controlled arms and unbound fixture bytes."""
	good = fixture(tmp_path / "good", "2026-08-22")
	(good / "manifest.json").write_text("{}", encoding="utf-8")
	with pytest.raises(RuntimeError, match="active capture schema"):
		experiment.load_fixture(str(good))
	with pytest.raises(RuntimeError, match="absolute"):
		experiment.load_fixture("relative-fixture")
	with pytest.raises(RuntimeError, match="strict"):
		experiment._open_output_transaction(str(tmp_path / "out"), "not-a-prompt-experiment")
	with pytest.raises(RuntimeError, match="strict"):
		experiment._open_output_transaction(str(tmp_path / "out"), "../escape")


#============================================
def test_fixture_capture_rejects_self_asserted_shim_mode_before_input_access(
	tmp_path: pathlib.Path,
) -> None:
	"""A caller cannot claim no-egress provenance with only a PATH-shaped runner."""
	with pytest.raises(RuntimeError, match="attested shim installation"):
		experiment.run_experiment(
			config(tmp_path),
			"/unread/busy",
			"/unread/quiet",
			execution_mode=(
				experiment.daily_blog.experiment_capture_artifacts.FIXTURE_HERMES_SHIM
			),
		)


#============================================
def test_fixture_capture_requires_the_sealed_hermes_route_before_input_access(
	tmp_path: pathlib.Path,
) -> None:
	"""An attested fixture shim still rejects direct or alternate route configuration."""
	installation = experiment.daily_blog.fixture_hermes.install_fixture_hermes(
		str(tmp_path), {"fixture prompt": "fixture response"},
	)
	with pytest.raises(RuntimeError, match="sealed Hermes editorial route"):
		experiment.run_experiment(
			config(tmp_path),
			"/unread/busy",
			"/unread/quiet",
			runner=installation.create_route_runner(),
			execution_mode=(
				experiment.daily_blog.experiment_capture_artifacts.FIXTURE_HERMES_SHIM
			),
			fixture_installation=installation,
		)


#============================================
def test_fixture_capture_rejects_a_tampered_attested_shim_before_input_access(
	tmp_path: pathlib.Path,
) -> None:
	"""Fixture provenance is revalidated before any sealed evidence path is consumed."""
	installation = experiment.daily_blog.fixture_hermes.install_fixture_hermes(
		str(tmp_path), {"fixture prompt": "fixture response"},
	)
	runner = installation.create_route_runner()
	pathlib.Path(installation.executable).write_text("tampered", encoding="utf-8")
	sealed = config(tmp_path)
	object.__setattr__(
		sealed,
		"author_routes",
		(
			daily_blog.config.RoleRoute("one", daily_blog.config.HERMES_EDITORIAL_ROUTE),
			daily_blog.config.RoleRoute("two", daily_blog.config.HERMES_EDITORIAL_ROUTE),
		),
	)
	object.__setattr__(
		sealed,
		"referee_route",
		daily_blog.config.RoleRoute("judge", daily_blog.config.HERMES_EDITORIAL_ROUTE),
	)
	with pytest.raises(RuntimeError, match="installation identity"):
		experiment.run_experiment(
			sealed,
			"/unread/busy",
			"/unread/quiet",
			runner=runner,
			execution_mode=(
				experiment.daily_blog.experiment_capture_artifacts.FIXTURE_HERMES_SHIM
			),
			fixture_installation=installation,
		)


#============================================
def test_fixture_capture_cli_redacts_private_failure(
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
) -> None:
	"""The autonomous fixture command exposes one stable error without artifact details."""
	secret = "/private/fixture-hermes/responses.json"
	monkeypatch.setattr(fixture_capture.daily_blog.config, "load_config", lambda _path: object())
	monkeypatch.setattr(
		fixture_capture,
		"run_fixture_capture",
		lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(secret)),
	)
	assert fixture_capture.main([]) == 2
	message = capsys.readouterr().err
	assert message == "Fixture prompt capture blocked; inspect the private artifact or configuration.\n"
	assert secret not in message


#============================================
def test_fixture_referee_selects_the_same_stronger_post_in_either_display_order() -> None:
	"""Counterbalanced display order cannot change the semantic fixture winner."""
	weaker = "I thought I was tuning a small binning rule."
	stronger = "The part I want to remember is the small reversal that started the investigation."
	forward = fixture_capture._referee_response(
		f"## Candidate A\n\n{weaker}\n\n## Candidate B\n\n{stronger}"
	)
	reverse = fixture_capture._referee_response(
		f"## Candidate A\n\n{stronger}\n\n## Candidate B\n\n{weaker}"
	)
	assert json.loads(forward)["winner"] == "B"
	assert json.loads(reverse)["winner"] == "A"


#============================================
def test_output_transaction_removes_a_stage_when_stage_validation_fails(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A stage-opening failure leaves no hidden transaction directory behind."""
	original = experiment.daily_blog.private_artifacts.open_directory_at

	def fail_for_stage(parent_fd: int, name: str) -> int:
		"""Simulate a failure after the transaction has created its empty stage."""
		if name.startswith(".prompt-experiment-cleanup-"):
			raise RuntimeError("stage cannot be opened")
		fd = original(parent_fd, name)
		return fd

	monkeypatch.setattr(
		experiment.daily_blog.private_artifacts,
		"open_directory_at",
		fail_for_stage,
	)
	with pytest.raises(RuntimeError, match="stage cannot be opened"):
		experiment._open_output_transaction(
			str(tmp_path / "out"),
			"prompt-experiment-cleanup",
		)
	assert not list((tmp_path / "out").glob(".prompt-experiment-cleanup-*.stage"))

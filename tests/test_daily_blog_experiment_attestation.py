"""Fast deterministic checks for private prompt-experiment attestations."""

# Standard Library
import pathlib
import unittest.mock

# PIP3 modules
import pytest

# local repo modules
import automation.attest_daily_blog_prompt_experiment
import daily_blog.config
import daily_blog.experiment_attestation
import daily_blog.experiment_capture_artifacts
import daily_blog.experiment_review_contract
import daily_blog.io_utils
import daily_blog.prompt_resources
import daily_blog.rubric_calibration


#============================================
def _config(root: pathlib.Path) -> daily_blog.config.DailyBlogConfig:
	"""Return an isolated configuration that contains no usable model route."""
	return daily_blog.config.DailyBlogConfig(
		settings_path="settings.yaml", output_root=str(root), output_owner="vosslab",
		report_timezone="America/Chicago", daily_blog_repository=str(root),
		mirror_cache_root=str(root), identity_names=("Neil",), identity_emails=(),
		author_routes=(), referee_route=daily_blog.config.RoleRoute("unused", ("unused",)),
		collection_limits={}, projection_limits={}, prompt_limits={},
	)


#============================================
def _scorecard(score: int) -> dict[str, object]:
	"""Return one valid fixed scorecard for every maker criterion."""
	fields = daily_blog.rubric_calibration.CALIBRATION_CONTRACT.expected_criteria
	return {
		"status": "scored", "scores": {field: score for field, _title, _weight in fields},
		"passages": {field: "I built the artifact." for field, _title, _weight in fields},
		"reasons": {field: "The passage shows maker work." for field, _title, _weight in fields},
		"weighted_score": float(score), "overall_reason": "Stable offline score.",
	}


#============================================
def _selected_post(fixture: str, arm: str, repetition: int) -> str:
	"""Return one distinct complete post body for a sealed capture sample."""
	return f"# {fixture} maker post\n\nI built the artifact.\n\n{arm} sample {repetition}.\n"


#============================================
def _capture(
	path: pathlib.Path,
	*,
	passing: bool,
	position_biased: bool = False,
) -> daily_blog.experiment_capture_artifacts.ExperimentCapture:
	"""Return a complete in-memory capture whose data exercises the real acceptance gates."""
	arms = ("v3", "v4-instruction-only", "v4-one-example", "v4-three-examples-corpus-v2")
	records = [
		{
			"fixture": fixture,
			"arm": arm,
			"repetition": repetition,
			"selected": {
				"path": "selected.md",
				"post_hash": daily_blog.io_utils.sha256_text(
					_selected_post(fixture, arm, repetition)
				),
			},
			"scorecard": _scorecard(3 if arm == "v3" else 4),
		}
		for fixture in ("busy", "quiet")
		for arm in arms
		for repetition in range(2)
	]
	comparisons = [
		{
			"fixture": fixture,
			"pair": "v3:" + arm,
			"repetition": repetition,
			"order": order,
			"verdict": (
				"A"
				if not passing or position_biased and order == "BA"
				else "B"
			),
			"parsed": True,
		}
		for fixture in ("busy", "quiet")
		for arm in arms[1:]
		for repetition in range(2)
		for order in ("AB", "BA")
	]
	return daily_blog.experiment_capture_artifacts.ExperimentCapture(
		path,
		{
			"experiment_id": "prompt-experiment-offline",
			"capture_id": "capture-id",
			"report_sha256": "a" * 64,
			"execution_mode": daily_blog.experiment_capture_artifacts.FIXTURE_HERMES_SHIM,
			"external_route_used": False,
			"fixture_shim": {"installation_attested": "fixture"},
			"arms": list(arms),
			"repetitions": 2,
			"fixtures": {
				fixture: {
					"label": f"2026-08-{26 if fixture == 'busy' else 23}--fixture-{fixture}",
					"fixture_id": f"fixture-{fixture}",
					"packet_id": f"packet-{fixture}",
					"projection_id": f"projection-{fixture}",
				}
				for fixture in ("busy", "quiet")
			},
		},
		{"records": records, "comparisons": comparisons},
	)


#============================================
def _evidence() -> daily_blog.rubric_calibration.CalibrationEvidence:
	"""Return a structurally valid passing historical calibration evidence object."""
	return daily_blog.rubric_calibration.CalibrationEvidence(
		"rubric-calibration-offline", "b" * 64, "c" * 64, "d" * 64,
		(("2026-08-22", 3.0), ("2026-08-23", 3.0)), 3.0,
	)


#============================================
def _review_submission(
	reviewer_id: str,
	contract: dict[str, object],
	posts: dict[str, str],
	conclusion: str = "pass",
) -> dict[str, object]:
	"""Return one complete passage-grounded artifact-only reviewer submission."""
	dimensions = daily_blog.experiment_review_contract.REVIEW_DIMENSIONS
	return {
		"schema_version": daily_blog.experiment_review_contract.REVIEW_SUBMISSION_SCHEMA,
		"reviewer_id": reviewer_id,
		"review_contract_sha256": daily_blog.io_utils.hash_value(contract),
		"fixtures": {
			fixture: {
				"post_sha256": daily_blog.io_utils.sha256_text(post),
				"complete_post_read": True,
				"conclusion": conclusion,
				"dimensions": {
					field: {
						"passage": "I built the artifact.",
						"assessment": f"The passage answers {field}.",
					}
					for field, _question in dimensions
				},
				"overall_reason": "The complete post reads as a maker's account.",
			}
			for fixture, post in posts.items()
		},
	}


#============================================
def test_independent_review_contract_preserves_the_central_question_and_artifact_basis(
	tmp_path: pathlib.Path,
) -> None:
	"""The F4 handoff gives reviewers the immutable question and sealed evidence only."""
	capture = _capture(tmp_path / "capture", passing=True)
	contract = daily_blog.experiment_review_contract.build_review_contract(
		{"review_ready": True, "selected_arm": "v4-one-example"},
		capture.manifest,
		capture.report,
	)
	question = daily_blog.experiment_review_contract.CENTRAL_MAKER_QUESTION

	assert (contract["central_question"], contract["review_basis"]) == (
		question, "sealed_artifacts_only",
	)
	assert contract["independence"]["other_reviewer_work_visible"] is False


#============================================
def test_review_contract_binds_the_predeclared_sample_independently_of_score(
	tmp_path: pathlib.Path,
) -> None:
	"""Later diagnostic scores cannot steer qualitative review to a different sample."""
	capture = _capture(tmp_path / "capture", passing=True)
	for record in capture.report["records"]:
		if record["arm"] == "v4-one-example" and record["repetition"] == 0:
			record["scorecard"] = _scorecard(5)
	contract = daily_blog.experiment_review_contract.build_review_contract(
		{"review_ready": True, "selected_arm": "v4-one-example"},
		capture.manifest,
		capture.report,
	)

	assert all(
		reference["selected_post"]["post_sha256"]
		== daily_blog.io_utils.sha256_text(_selected_post(fixture, "v4-one-example", 0))
		for fixture, reference in contract["fixtures"].items()
	)


#============================================
def test_independent_review_rejects_a_fabricated_passage(
	tmp_path: pathlib.Path,
) -> None:
	"""A reviewer conclusion cannot cite prose absent from the sealed selected post."""
	capture = _capture(tmp_path / "capture", passing=True)
	contract = daily_blog.experiment_review_contract.build_review_contract(
		{"review_ready": True, "selected_arm": "v4-one-example"},
		capture.manifest,
		capture.report,
	)
	posts = {
		fixture: _selected_post(fixture, "v4-one-example", 0)
		for fixture in ("busy", "quiet")
	}
	submission = _review_submission("reviewer-alpha", contract, posts)
	field = daily_blog.experiment_review_contract.REVIEW_DIMENSIONS[0][0]
	submission["fixtures"]["busy"]["dimensions"][field]["passage"] = "Fabricated passage."

	with pytest.raises(RuntimeError, match="not passage-grounded"):
		daily_blog.experiment_review_contract.validate_review_submission(
			submission,
			contract,
			posts,
		)


#============================================
def test_independent_review_rejects_a_complete_post_outside_the_sealed_contract(
	tmp_path: pathlib.Path,
) -> None:
	"""Caller-consistent hashes cannot substitute prose the attestation did not select."""
	capture = _capture(tmp_path / "capture", passing=True)
	contract = daily_blog.experiment_review_contract.build_review_contract(
		{"review_ready": True, "selected_arm": "v4-one-example"},
		capture.manifest,
		capture.report,
	)
	posts = {
		fixture: _selected_post(fixture, "v4-one-example", 0)
		for fixture in ("busy", "quiet")
	}
	posts["busy"] += "\nUnsealed replacement.\n"
	submission = _review_submission("reviewer-alpha", contract, posts)

	with pytest.raises(RuntimeError, match="not the sealed review target"):
		daily_blog.experiment_review_contract.validate_review_submission(
			submission,
			contract,
			posts,
		)


#============================================
def test_review_post_loader_reads_only_the_two_attested_complete_posts(
	tmp_path: pathlib.Path,
) -> None:
	"""Descriptor reads reproduce the exact post hashes selected for qualitative review."""
	capture_path = tmp_path / "capture"
	capture_path.mkdir(mode=0o700)
	capture = _capture(capture_path, passing=True)
	contract = daily_blog.experiment_review_contract.build_review_contract(
		{"review_ready": True, "selected_arm": "v4-one-example"},
		capture.manifest,
		capture.report,
	)
	for fixture, reference in contract["fixtures"].items():
		selected = reference["selected_post"]
		artifact = pathlib.PurePosixPath(selected["artifact"])
		directory = capture_path / artifact.parent
		directory.mkdir(mode=0o700)
		post = _selected_post(fixture, "v4-one-example", selected["repetition"])
		path = directory / artifact.name
		path.write_text(post, encoding="utf-8")
		path.chmod(0o600)

	posts = daily_blog.experiment_attestation._load_review_posts_from_capture(
		capture,
		contract,
	)

	assert {
		fixture: daily_blog.io_utils.sha256_text(post)
		for fixture, post in posts.items()
	} == {
		fixture: reference["selected_post"]["post_sha256"]
		for fixture, reference in contract["fixtures"].items()
	}
	busy_artifact = pathlib.PurePosixPath(
		contract["fixtures"]["busy"]["selected_post"]["artifact"]
	)
	(capture_path / busy_artifact).write_text("# Changed after attestation\n", encoding="utf-8")
	with pytest.raises(RuntimeError, match="identity is invalid"):
		daily_blog.experiment_attestation._load_review_posts_from_capture(capture, contract)


#============================================
def test_attestation_requires_strict_reference_floor_and_revalidates_sources(
	tmp_path: pathlib.Path,
) -> None:
	"""A passing join loads back only while exact capture and calibration evidence agree."""
	config = _config(tmp_path)
	capture_path = tmp_path / "vosslab" / "daily_blog_experiments" / "prompt-experiment-offline"
	calibration_path = (
		tmp_path / "vosslab" / "daily_blog_rubric_calibrations" / "rubric-calibration-offline"
	)
	capture_path.mkdir(parents=True)
	calibration_path.mkdir(parents=True)
	with unittest.mock.patch(
		"daily_blog.experiment_capture_artifacts.load_capture",
		return_value=_capture(capture_path, passing=True),
	), unittest.mock.patch(
		"daily_blog.rubric_calibration.load_fixture_calibration_evidence", return_value=_evidence(),
	):
		code, path = daily_blog.experiment_attestation.create_attestation(
			config,
			str(capture_path),
			str(calibration_path),
		)
		loaded = daily_blog.experiment_attestation.load_attestation(config, str(path))
	assert (code, loaded.report["acceptance"]["review_ready"]) == (0, True)
	assert loaded.report["review_contract"]["central_question"] == (
		daily_blog.experiment_review_contract.CENTRAL_MAKER_QUESTION
	)


#============================================
def test_attestation_preserves_failed_acceptance_without_activating(
	tmp_path: pathlib.Path,
) -> None:
	"""A complete but losing v4 comparison persists as a valid non-activation result."""
	config = _config(tmp_path)
	capture_path = tmp_path / "vosslab" / "daily_blog_experiments" / "prompt-experiment-offline"
	calibration_path = (
		tmp_path / "vosslab" / "daily_blog_rubric_calibrations" / "rubric-calibration-offline"
	)
	capture_path.mkdir(parents=True)
	calibration_path.mkdir(parents=True)
	with unittest.mock.patch(
		"daily_blog.experiment_capture_artifacts.load_capture",
		return_value=_capture(capture_path, passing=False),
	), unittest.mock.patch(
		"daily_blog.rubric_calibration.load_fixture_calibration_evidence", return_value=_evidence(),
	):
		code, path = daily_blog.experiment_attestation.create_attestation(
			config,
			str(capture_path),
			str(calibration_path),
		)
		with pytest.raises(RuntimeError, match="not ready for review"):
			daily_blog.experiment_attestation.load_review_posts(config, str(path))
	assert code == 1 and path.is_dir()


#============================================
def test_attestation_cli_redacts_an_invalid_private_artifact(
	tmp_path: pathlib.Path,
	capsys: pytest.CaptureFixture[str],
) -> None:
	"""The command boundary hides invalid artifact paths and loader diagnostics."""
	config = _config(tmp_path)
	invalid_capture = tmp_path / "private-input" / "capture"
	invalid_calibration = tmp_path / "private-input" / "calibration"
	with unittest.mock.patch("daily_blog.config.load_config", return_value=config):
		code = automation.attest_daily_blog_prompt_experiment.main(
			["--capture", str(invalid_capture), "--calibration", str(invalid_calibration)],
		)
	message = capsys.readouterr().err

	assert code == 2
	assert message == "Prompt experiment attestation failed; inspect private artifacts.\n"
	assert str(invalid_capture) not in message


#============================================
def test_attestation_rejects_external_capture_provenance(tmp_path: pathlib.Path) -> None:
	"""F4 accepts only the autonomous fixture-backed capture mode."""
	config = _config(tmp_path)
	capture_path = tmp_path / "vosslab" / "daily_blog_experiments" / "prompt-experiment-offline"
	calibration_path = (
		tmp_path / "vosslab" / "daily_blog_rubric_calibrations" / "rubric-calibration-offline"
	)
	capture_path.mkdir(parents=True)
	calibration_path.mkdir(parents=True)
	capture = _capture(capture_path, passing=True)
	capture.manifest["execution_mode"] = "external_hermes"
	capture.manifest["external_route_used"] = True
	with unittest.mock.patch(
		"daily_blog.experiment_capture_artifacts.load_capture",
		return_value=capture,
	):
		with pytest.raises(RuntimeError, match="fixture-backed capture"):
			daily_blog.experiment_attestation.create_attestation(
				config,
				str(capture_path),
				str(calibration_path),
			)


#============================================
@pytest.mark.parametrize("ambiguous_json", (
	b'{"schema_version":"one","schema_version":"two"}',
	b'{"schema_version":NaN}',
))
def test_attestation_rejects_ambiguous_sealed_json(
	tmp_path: pathlib.Path,
	ambiguous_json: bytes,
) -> None:
	"""The public loader rejects duplicate members and non-finite sealed JSON."""
	config = _config(tmp_path)
	capture_path = tmp_path / "vosslab" / "daily_blog_experiments" / "prompt-experiment-offline"
	calibration_path = (
		tmp_path / "vosslab" / "daily_blog_rubric_calibrations" / "rubric-calibration-offline"
	)
	capture_path.mkdir(parents=True)
	calibration_path.mkdir(parents=True)
	with unittest.mock.patch(
		"daily_blog.experiment_capture_artifacts.load_capture",
		return_value=_capture(capture_path, passing=True),
	), unittest.mock.patch(
		"daily_blog.rubric_calibration.load_fixture_calibration_evidence",
		return_value=_evidence(),
	):
		_code, path = daily_blog.experiment_attestation.create_attestation(
			config,
			str(capture_path),
			str(calibration_path),
		)
		(path / "manifest.json").write_bytes(ambiguous_json)
		with pytest.raises(RuntimeError, match="JSON is invalid"):
			daily_blog.experiment_attestation.load_attestation(config, str(path))


#============================================
def test_attestation_rejects_a_referee_that_favors_one_displayed_position(
	tmp_path: pathlib.Path,
) -> None:
	"""A positional winner cannot become a review-ready canonical preference."""
	config = _config(tmp_path)
	capture_path = tmp_path / "vosslab" / "daily_blog_experiments" / "prompt-experiment-offline"
	calibration_path = (
		tmp_path / "vosslab" / "daily_blog_rubric_calibrations" / "rubric-calibration-offline"
	)
	capture_path.mkdir(parents=True)
	calibration_path.mkdir(parents=True)
	with unittest.mock.patch(
		"daily_blog.experiment_capture_artifacts.load_capture",
		return_value=_capture(capture_path, passing=True, position_biased=True),
	), unittest.mock.patch(
		"daily_blog.rubric_calibration.load_fixture_calibration_evidence", return_value=_evidence(),
	):
		code, path = daily_blog.experiment_attestation.create_attestation(
			config,
			str(capture_path),
			str(calibration_path),
		)
	assert code == 1 and path.is_dir()


#============================================
def test_attestation_ignores_a_stale_legacy_stage_name(tmp_path: pathlib.Path) -> None:
	"""A stale deterministic stage cannot block a distinct transaction-owned stage."""
	config = _config(tmp_path)
	capture_path = tmp_path / "vosslab" / "daily_blog_experiments" / "prompt-experiment-offline"
	calibration_path = (
		tmp_path / "vosslab" / "daily_blog_rubric_calibrations" / "rubric-calibration-offline"
	)
	capture_path.mkdir(parents=True)
	calibration_path.mkdir(parents=True)
	with unittest.mock.patch(
		"daily_blog.experiment_capture_artifacts.load_capture",
		return_value=_capture(capture_path, passing=True),
	), unittest.mock.patch(
		"daily_blog.rubric_calibration.load_fixture_calibration_evidence",
		return_value=_evidence(),
	):
		_code, path = daily_blog.experiment_attestation.create_attestation(
			config,
			str(capture_path),
			str(calibration_path),
		)
		legacy_stage = path.parent / ("." + path.name + ".stage")
		legacy_stage.mkdir()
		code, repeated_path = daily_blog.experiment_attestation.create_attestation(
			config,
			str(capture_path),
			str(calibration_path),
		)
	assert code == 0
	assert repeated_path == path
	assert legacy_stage.is_dir()

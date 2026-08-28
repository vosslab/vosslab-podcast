"""Fast deterministic checks for private prompt-experiment attestations."""

# Standard Library
import pathlib
import unittest.mock

# local repo modules
import daily_blog.config
import daily_blog.experiment_attestation
import daily_blog.experiment_capture_artifacts
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
		"evidence": {field: "Visible maker evidence." for field, _title, _weight in fields},
		"weighted_score": float(score), "overall_reason": "Stable offline score.",
	}


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
		{"fixture": fixture, "arm": arm, "scorecard": _scorecard(3 if arm == "v3" else 4)}
		for fixture in ("busy", "quiet") for arm in arms for _repetition in range(2)
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
			"arms": list(arms),
			"repetitions": 2,
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
		"daily_blog.rubric_calibration.load_live_calibration_evidence", return_value=_evidence(),
	):
		code, path = daily_blog.experiment_attestation.create_attestation(
			config,
			str(capture_path),
			str(calibration_path),
		)
		loaded = daily_blog.experiment_attestation.load_attestation(config, str(path))
	assert code == 0 and loaded.report["acceptance"]["activation_ready"] is True


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
		"daily_blog.rubric_calibration.load_live_calibration_evidence", return_value=_evidence(),
	):
		code, path = daily_blog.experiment_attestation.create_attestation(
			config,
			str(capture_path),
			str(calibration_path),
		)
	assert code == 1 and path.is_dir()


#============================================
def test_attestation_rejects_a_referee_that_favors_one_displayed_position(
	tmp_path: pathlib.Path,
) -> None:
	"""A positional winner cannot become an activation-ready canonical preference."""
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
		"daily_blog.rubric_calibration.load_live_calibration_evidence", return_value=_evidence(),
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
		"daily_blog.rubric_calibration.load_live_calibration_evidence",
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

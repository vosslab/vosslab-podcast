"""Historical maker-rubric calibration contracts and private artifact tests."""

# Standard Library
import json
import os
import pathlib
import dataclasses

# PIP3 modules
import pytest

# local repo modules
import daily_blog.config
import daily_blog.io_utils
import daily_blog.rubric_calibration
import daily_blog.rubric_calibration_artifacts
import automation.calibrate_daily_blog_rubric


#============================================
def make_config(
	tmp_path: pathlib.Path,
	*,
	sharing: bool,
) -> daily_blog.config.DailyBlogConfig:
	"""Return one isolated configuration with a fake referee route."""
	return daily_blog.config.DailyBlogConfig(
		settings_path="settings.yaml",
		output_root=str(tmp_path / "out"),
		output_owner="vosslab",
		report_timezone="America/Chicago",
		daily_blog_repository=str(tmp_path / "blog"),
		mirror_cache_root=str(tmp_path / "mirrors"),
		identity_names=("Neil",),
		identity_emails=(),
		author_routes=(
			daily_blog.config.RoleRoute("one", ("fake",)),
			daily_blog.config.RoleRoute("two", ("fake",)),
		),
		referee_route=daily_blog.config.RoleRoute("judge", ("fake",)),
		collection_limits={},
		projection_limits={},
		prompt_limits={"author_chars": 72000, "referee_chars": 88000},
		allow_shadow_model_data_sharing=sharing,
	)


#============================================
def calibration_artifact_root(
	config: daily_blog.config.DailyBlogConfig,
) -> pathlib.Path:
	"""Return the private root used by one isolated calibration configuration."""
	return pathlib.Path(
		config.output_root,
		config.output_owner,
		daily_blog.rubric_calibration.CALIBRATION_ROOT_NAME,
	)


#============================================
def write_calibration_artifact(
	path: pathlib.Path,
	manifest: dict,
	report: dict,
) -> None:
	"""Write one controlled completed artifact for a no-replace race test."""
	path.mkdir(mode=0o700)
	for name, value in (("manifest.json", manifest), ("report.json", report)):
		artifact = path / name
		artifact.write_text(daily_blog.io_utils.stable_json_text(value), encoding="utf-8")
		artifact.chmod(0o600)


#============================================
def test_calibration_artifact_commit_is_idempotent_and_rejects_conflicts(
	tmp_path: pathlib.Path,
) -> None:
	"""One calibration identity retains exactly one immutable completed artifact."""
	config = make_config(tmp_path, sharing=True)
	calibration_id = "rubric-calibration-preparation-content-addressed"
	manifest = {"calibration_id": calibration_id, "version": 1}
	report = {"status": "prepared", "value": 1}

	path = daily_blog.rubric_calibration_artifacts.install_calibration_artifacts(
		config, calibration_id, manifest, report,
	)
	assert pathlib.Path(path).is_dir()
	assert daily_blog.rubric_calibration_artifacts.install_calibration_artifacts(
		config, calibration_id, manifest, report,
	) == path
	with pytest.raises(RuntimeError, match="identity conflicts"):
		daily_blog.rubric_calibration_artifacts.install_calibration_artifacts(
			config, calibration_id, manifest, {"status": "different"},
		)


#============================================
def test_calibration_artifact_lost_commit_race_accepts_only_same_artifact(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A competing target wins only when its completed content is exactly identical."""
	config = make_config(tmp_path, sharing=True)
	calibration_id = "rubric-calibration-preparation-race-safe"
	manifest = {"calibration_id": calibration_id, "version": 1}
	report = {"status": "prepared", "value": 1}
	root = calibration_artifact_root(config)

	def lose_to_same_target(_root_fd: int, _stage_name: str, destination: str) -> None:
		write_calibration_artifact(root / destination, manifest, report)
		raise FileExistsError(destination)

	monkeypatch.setattr(
		daily_blog.private_artifacts,
		"rename_directory_noreplace_at",
		lose_to_same_target,
	)
	path = daily_blog.rubric_calibration_artifacts.install_calibration_artifacts(
		config, calibration_id, manifest, report,
	)
	assert pathlib.Path(path, "report.json").is_file()
	assert not list(root.glob("*.stage"))


#============================================
def test_calibration_artifact_lost_commit_race_rejects_conflicting_artifact(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A competing target with different bytes remains a visible identity conflict."""
	config = make_config(tmp_path, sharing=True)
	calibration_id = "rubric-calibration-preparation-race-conflict"
	manifest = {"calibration_id": calibration_id, "version": 1}
	report = {"status": "prepared", "value": 1}
	root = calibration_artifact_root(config)

	def lose_to_conflicting_target(_root_fd: int, _stage_name: str, destination: str) -> None:
		write_calibration_artifact(root / destination, manifest, {"status": "different"})
		raise FileExistsError(destination)

	monkeypatch.setattr(
		daily_blog.private_artifacts,
		"rename_directory_noreplace_at",
		lose_to_conflicting_target,
	)
	with pytest.raises(RuntimeError, match="identity conflicts"):
		daily_blog.rubric_calibration_artifacts.install_calibration_artifacts(
			config, calibration_id, manifest, report,
		)
	assert not list(root.glob("*.stage"))


#============================================
def test_calibration_artifact_unsafe_competing_target_fails_closed(
	tmp_path: pathlib.Path,
) -> None:
	"""A file at the final identity is unsafe rather than a benign absent target."""
	config = make_config(tmp_path, sharing=True)
	calibration_id = "rubric-calibration-preparation-unsafe-target"
	root = calibration_artifact_root(config)
	root.mkdir(parents=True, mode=0o700)
	root.chmod(0o700)
	unsafe_target = root / calibration_id
	unsafe_target.write_text("not a directory", encoding="utf-8")
	unsafe_target.chmod(0o600)

	with pytest.raises(RuntimeError, match="target is unsafe"):
		daily_blog.rubric_calibration_artifacts.install_calibration_artifacts(
			config,
			calibration_id,
			{"calibration_id": calibration_id},
			{"status": "prepared"},
		)


#============================================
def response_with_score(
	score: int,
	passage: str = "I built a parser today.",
) -> str:
	"""Return one complete passage-grounded calibration response."""
	scores = {
		field: {
			"score": score,
			"passage": passage,
			"reason": f"This passage supports {field}.",
		}
		for field, _title, _weight in (
			daily_blog.rubric_calibration.CALIBRATION_CONTRACT.expected_criteria
		)
	}
	return json.dumps({"scores": scores, "overall_reason": "A grounded maker assessment."})


#============================================
def historical_posts() -> tuple[daily_blog.rubric_calibration.HistoricalPost, ...]:
	"""Return the five fixed dates with one exact grounding passage apiece."""
	posts = []
	for report_date in daily_blog.rubric_calibration.CALIBRATION_DATES:
		text = (
			f"---\ndate: {report_date}\n---\n\n# Maker note\n\n"
			f"I built the calibration for {report_date}.\n"
		)
		posts.append(
			daily_blog.rubric_calibration.HistoricalPost(
				report_date,
				text,
				daily_blog.io_utils.sha256_text(text),
				len(text.encode("utf-8")),
				{},
			)
		)
	return tuple(posts)


#============================================
def calibration_record(
	post: daily_blog.rubric_calibration.HistoricalPost,
	repetition: int,
	score: int,
) -> dict:
	"""Return one complete scorecard bound to an exact post passage."""
	fields = daily_blog.rubric_calibration.CALIBRATION_CONTRACT.expected_criteria
	passage = f"I built the calibration for {post.report_date}."
	return {
		"report_date": post.report_date,
		"post_sha256": post.sha256,
		"repetition": repetition,
		"status": "scored",
		"scores": {field: score for field, _title, _weight in fields},
		"passages": {field: passage for field, _title, _weight in fields},
		"reasons": {
			field: f"The exact passage supports {field}."
			for field, _title, _weight in fields
		},
		"weighted_score": float(score),
		"overall_reason": "The cited work supports the aggregate score.",
	}


#============================================
def calibration_records(
	posts: tuple[daily_blog.rubric_calibration.HistoricalPost, ...],
	procedure: daily_blog.rubric_calibration.CalibrationProcedure,
) -> list[dict]:
	"""Return one complete grounded matrix for an artifact-recorded procedure."""
	records = []
	for post in posts:
		if post.report_date in {"2026-08-22", "2026-08-23"}:
			score = 3
		elif post.report_date in {"2026-08-24", "2026-08-25"}:
			score = 2
		else:
			score = 3
		for repetition in range(procedure.repetitions):
			records.append(calibration_record(post, repetition, score))
	return records


class FixedRunner:
	"""Return date-independent structured calibration responses and count invocations."""

	#============================================
	def __init__(self, response: str) -> None:
		"""Retain one fixed response and start with no route calls."""
		self.response = response
		self.calls = 0

	#============================================
	def run(
		self,
		route: daily_blog.config.RoleRoute,
		prompt: str,
		repository: str,
	) -> str:
		"""Return the fixed response and record one route invocation."""
		del route, prompt, repository
		self.calls += 1
		return self.response


class RepairRunner:
	"""Return one malformed response followed by one complete scorecard."""

	#============================================
	def __init__(self, first_response: str = "{}") -> None:
		"""Retain the first response and count the primary and repair requests."""
		self.first_response = first_response
		self.calls = 0

	#============================================
	def run(
		self,
		_route: daily_blog.config.RoleRoute,
		_prompt: str,
		_repository: str,
	) -> str:
		"""Return malformed JSON once, then a valid repaired scorecard."""
		self.calls += 1
		if self.calls == 1:
			return self.first_response
		return response_with_score(3)


#============================================
@pytest.mark.parametrize(
	("sharing", "approved"),
	((False, True), (True, False), (False, False)),
)
def test_live_calibration_requires_both_durable_and_invocation_approval(
	tmp_path: pathlib.Path,
	sharing: bool,
	approved: bool,
) -> None:
	"""No route or output begins with only one side of the sharing decision."""
	config = make_config(tmp_path, sharing=sharing)
	runner = FixedRunner(response_with_score(3))
	with pytest.raises(
		daily_blog.rubric_calibration.CalibrationBlockedError,
		match="explicit model-data-sharing approval",
	):
		daily_blog.rubric_calibration.run_live_calibration(
			config,
			operator_approved=approved,
			runner=runner,
		)
	assert runner.calls == 0
	assert not (tmp_path / "out").exists()


#============================================
def test_malformed_response_uses_one_bounded_repair_attempt(tmp_path: pathlib.Path) -> None:
	"""A valid second response becomes a scored result after one structured repair."""
	config = make_config(tmp_path, sharing=True)
	runner = RepairRunner()

	result = daily_blog.rubric_calibration.score_maker_post(
		"---\ndate: 2026-08-23\n---\n\n# A maker note\n\nI built a parser today.\n",
		config,
		runner,
		"historical_calibration",
	)

	assert result["status"] == "scored" and runner.calls == 2


#============================================
def test_calibration_result_rejects_a_fabricated_grounding_passage() -> None:
	"""Every criterion anchor must occur exactly in the complete reviewed post."""
	_rubric, _template, criteria = daily_blog.rubric_calibration.calibration_resources()
	post = "# Maker note\n\nI built a parser today.\n"

	with pytest.raises(RuntimeError, match="passage is not present"):
		daily_blog.rubric_calibration.parse_calibration_result(
			response_with_score(3, "I shipped a feature that is not in this post."),
			criteria,
			post,
		)


#============================================
def test_calibration_result_rejects_ambiguous_json_members() -> None:
	"""Model scorecards cannot use duplicate names to hide a conflicting score."""
	_rubric, _template, criteria = daily_blog.rubric_calibration.calibration_resources()
	post = "# Maker note\n\nI built a parser today.\n"

	with pytest.raises(ValueError, match="Duplicate JSON member"):
		daily_blog.rubric_calibration.parse_calibration_result(
			'{"scores":{},"scores":{},"overall_reason":"grounded"}', criteria, post,
		)


#============================================
def test_private_calibration_json_rejects_non_finite_constants(tmp_path: pathlib.Path) -> None:
	"""A sealed manifest or report rejects JSON constants outside the JSON data model."""
	directory = tmp_path / "calibration"
	directory.mkdir(mode=0o700)
	(directory / "report.json").write_text('{"score":NaN}', encoding="utf-8")
	(directory / "report.json").chmod(0o600)
	directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
	try:
		with pytest.raises(RuntimeError, match="artifact JSON is invalid"):
			daily_blog.rubric_calibration_artifacts._read_private_json(directory_fd, "report.json")
	finally:
		os.close(directory_fd)


#============================================
def test_calibration_aggregate_rejects_ungrounded_reasons() -> None:
	"""A complete score matrix cannot pass when a cited passage is absent from its post."""
	posts = historical_posts()
	criteria = tuple(
		daily_blog.rubric_calibration.RubricCriterion(*value)
		for value in daily_blog.rubric_calibration.CALIBRATION_CONTRACT.expected_criteria
	)
	procedure = daily_blog.rubric_calibration.calibration_procedure()
	records = calibration_records(posts, procedure)
	field = criteria[0].field
	records[0]["passages"][field] = "This sentence was never in the post."

	aggregate = daily_blog.rubric_calibration.aggregate_calibration(
		records,
		criteria,
		posts,
		procedure,
	)

	assert aggregate["passage_grounded"] is False


#============================================
def test_fixture_scorecard_keeps_the_evidence_failure_exactly_grounded() -> None:
	"""The autonomous Aug. 26 mapping stays a grounded discovery-failure diagnostic."""
	post = daily_blog.rubric_calibration.HistoricalPost(
		"2026-08-26",
		"---\ndate: 2026-08-26\n---\n\n# Maker note\n\nI found the missing evidence today.\n",
		"a" * 64,
		76,
		{},
	)
	criteria = tuple(
		daily_blog.rubric_calibration.RubricCriterion(*value)
		for value in daily_blog.rubric_calibration.CALIBRATION_CONTRACT.expected_criteria
	)

	response = daily_blog.rubric_calibration_artifacts._fixture_scorecard_response(post, criteria)
	result = daily_blog.rubric_calibration.parse_calibration_result(response, criteria, post.text)

	assert result["weighted_score"] == 1.0
	assert "evidence and discovery failure" in result["overall_reason"]


#============================================
def test_fixture_evidence_recomputes_and_cannot_be_loaded_as_external(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A verified fixture artifact retains its false external-route provenance."""
	config = dataclasses.replace(
		make_config(tmp_path, sharing=False),
		referee_route=daily_blog.config.RoleRoute(
			"judge", daily_blog.config.HERMES_EDITORIAL_ROUTE,
		),
	)
	posts = historical_posts()
	procedure = daily_blog.rubric_calibration.calibration_procedure()
	rubric, _template, criteria = daily_blog.rubric_calibration.calibration_resources()
	identity = daily_blog.rubric_calibration._preparation_identity(posts, rubric, procedure)
	report = daily_blog.rubric_calibration._calibration_report(
		config,
		"rubric-calibration-fixture-test-evidence",
		procedure,
		identity,
		criteria,
		calibration_records(posts, procedure),
		daily_blog.rubric_calibration.aggregate_calibration(
			calibration_records(posts, procedure), criteria, posts, procedure,
		),
		mode="fixture_hermes_shim",
		external_route_used=False,
		fixture=daily_blog.rubric_calibration_artifacts._fixture_identity(
			daily_blog.rubric_calibration_artifacts._fixture_prompt_responses(
				posts, config, criteria,
			)
		),
	)
	manifest = daily_blog.rubric_calibration._calibration_manifest(
		report["calibration_id"], identity, posts, report,
	)
	path = daily_blog.rubric_calibration_artifacts.install_calibration_artifacts(
		config, report["calibration_id"], manifest, report,
	)
	monkeypatch.setattr(
		daily_blog.rubric_calibration_artifacts,
		"load_historical_posts",
		lambda _repository: posts,
	)

	evidence = daily_blog.rubric_calibration.load_fixture_calibration_evidence(config, path)

	assert evidence.reference_floor == 3.0
	with pytest.raises(RuntimeError, match="wrong route provenance"):
		daily_blog.rubric_calibration.load_live_calibration_evidence(config, path)


#============================================
def test_fixture_calibration_rejects_a_non_hermes_referee_route(
	tmp_path: pathlib.Path,
) -> None:
	"""The fixture provenance label requires the same sealed command as production Hermes."""

	with pytest.raises(RuntimeError, match="sealed Hermes referee route"):
		daily_blog.rubric_calibration.run_fixture_calibration(
			make_config(tmp_path, sharing=False),
		)


#============================================
def test_cli_blocks_live_mode_with_a_stable_redacted_message(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
) -> None:
	"""The command exposes the approval action without exposing private configuration."""
	config = make_config(tmp_path, sharing=False)
	monkeypatch.setattr(
		automation.calibrate_daily_blog_rubric.daily_blog.config,
		"load_config",
		lambda _path: config,
	)

	code = automation.calibrate_daily_blog_rubric.main([])
	stderr = capsys.readouterr().err

	assert code == 2
	assert "explicit historical-post sharing approval" in stderr
	assert str(tmp_path) not in stderr

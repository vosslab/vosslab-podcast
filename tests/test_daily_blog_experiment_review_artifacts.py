"""Behavior tests for immutable route-free F4 independent-review evidence."""

# Standard Library
import json
import pathlib
import unittest.mock

# Third Party
import pytest

# local repo modules
import automation.record_daily_blog_experiment_reviews
import daily_blog.config
import daily_blog.experiment_attestation
import daily_blog.experiment_review_artifacts
import daily_blog.experiment_review_contract
import daily_blog.io_utils


#============================================
def _config(root: pathlib.Path) -> daily_blog.config.DailyBlogConfig:
	"""Return isolated local output ownership for one offline review-evidence test."""
	config = daily_blog.config.DailyBlogConfig(
		settings_path="settings.yaml",
		output_root=str(root),
		output_owner="vosslab",
		report_timezone="America/Chicago",
		daily_blog_repository=str(root),
		mirror_cache_root=str(root),
		identity_names=("Neil",),
		identity_emails=(),
		author_routes=(),
		referee_route=daily_blog.config.RoleRoute("unused", ("unused",)),
		collection_limits={},
		projection_limits={},
		prompt_limits={},
	)
	return config


#============================================
def _review_inputs(root: pathlib.Path) -> tuple[
	daily_blog.experiment_attestation.ExperimentAttestation,
	dict[str, str],
	list[dict[str, object]],
]:
	"""Build one ready attestation contract, its sealed posts, and independent reviews."""
	posts = {
		"busy": "# Busy\n\nI built the parser and liked the small surprise in its output.\n",
		"quiet": "# Quiet\n\nI built the parser and want to try the next edge tomorrow.\n",
	}
	arm = "v4-one-example"
	records = [
		{
			"fixture": fixture,
			"arm": arm,
			"repetition": 0,
			"selected": {
				"path": "selected.md",
				"post_hash": daily_blog.io_utils.sha256_text(post),
			},
		}
		for fixture, post in posts.items()
	]
	contract = daily_blog.experiment_review_contract.build_review_contract(
		{"review_ready": True, "selected_arm": arm},
		{
			"repetitions": 1,
			"fixtures": {
				fixture: {
					"label": fixture + "-fixture",
					"fixture_id": fixture + "-id",
					"packet_id": fixture + "-packet",
					"projection_id": fixture + "-projection",
				}
				for fixture in posts
			},
		},
		{"records": records},
		reviewer_count=1,
	)
	attestation_path = root / "vosslab" / "daily_blog_experiment_attestations" / (
		"prompt-experiment-attestation-" + "a" * 64
	)
	attestation = daily_blog.experiment_attestation.ExperimentAttestation(
		attestation_path,
		{"attestation_id": attestation_path.name, "report_sha256": "b" * 64},
		{"review_contract": contract},
	)
	passage = "I built the parser"
	submissions = []
	for reviewer_id in ("reviewer-alpha",):
		submissions.append(
			{
				"schema_version": daily_blog.experiment_review_contract.REVIEW_SUBMISSION_SCHEMA,
				"reviewer_id": reviewer_id,
				"review_contract_sha256": daily_blog.io_utils.hash_value(contract),
				"fixtures": {
					fixture: {
						"post_sha256": daily_blog.io_utils.sha256_text(post),
						"complete_post_read": True,
						"conclusion": "pass",
						"dimensions": {
							field: {
								"passage": passage,
								"assessment": "The post contains a concrete maker detail.",
							}
							for field, _question in daily_blog.experiment_review_contract.REVIEW_DIMENSIONS
						},
						"overall_reason": "The complete post reads as a maker's account.",
					}
					for fixture, post in posts.items()
				},
			}
		)
	return attestation, posts, submissions


#============================================
def _write_submissions(root: pathlib.Path, submissions: list[dict[str, object]]) -> list[str]:
	"""Write inline JSON reviewer inputs under the test-owned temporary directory."""
	paths = []
	for index, submission in enumerate(submissions):
		path = root / f"review-{index}.json"
		path.write_text(daily_blog.io_utils.stable_json_text(submission), encoding="utf-8")
		path.chmod(0o600)
		paths.append(str(path))
	return paths


#============================================
def test_review_evidence_is_content_addressed_and_idempotent(
	tmp_path: pathlib.Path,
) -> None:
	"""The same sealed sources produce one immutable F4 artifact with its aggregate outcome."""
	config = _config(tmp_path)
	attestation, posts, submissions = _review_inputs(tmp_path)
	first_stage = tmp_path / "first-stage"
	second_stage = tmp_path / "second-stage"
	first_stage.mkdir(mode=0o700)
	second_stage.mkdir(mode=0o700)
	paths = _write_submissions(first_stage, submissions)
	second_paths = _write_submissions(second_stage, submissions)
	with unittest.mock.patch(
		"daily_blog.experiment_attestation.load_review_posts",
		return_value=(attestation, posts),
	):
		first_code, first_path = daily_blog.experiment_review_artifacts.create_review_evidence(
			config, str(attestation.path), paths,
		)
		second_code, second_path = daily_blog.experiment_review_artifacts.create_review_evidence(
			config, str(attestation.path), second_paths,
		)
		for path_value in paths:
			pathlib.Path(path_value).unlink()
		loaded = daily_blog.experiment_review_artifacts.load_review_evidence(config, str(first_path))

	assert (first_code, second_code, first_path, loaded.path) == (0, 0, second_path, first_path)


#============================================
def test_review_evidence_rejects_a_tampered_aggregate(tmp_path: pathlib.Path) -> None:
	"""A sealed report cannot claim a different F4 aggregate after installation."""
	config = _config(tmp_path)
	attestation, posts, submissions = _review_inputs(tmp_path)
	paths = _write_submissions(tmp_path, submissions)
	with unittest.mock.patch(
		"daily_blog.experiment_attestation.load_review_posts",
		return_value=(attestation, posts),
	):
		_code, path = daily_blog.experiment_review_artifacts.create_review_evidence(
			config, str(attestation.path), paths,
		)
		report_path = path / "report.json"
		report = json.loads(report_path.read_text(encoding="utf-8"))
		report["aggregate"]["f4_accepted"] = False
		report_path.write_text(daily_blog.io_utils.stable_json_text(report), encoding="utf-8")
		with pytest.raises(RuntimeError, match="identity is invalid"):
			daily_blog.experiment_review_artifacts.load_review_evidence(config, str(path))


#============================================
def test_review_evidence_rejects_drift_in_the_attested_complete_post(
	tmp_path: pathlib.Path,
) -> None:
	"""Loading recomputes passage-grounded review against the exact attested posts."""
	config = _config(tmp_path)
	attestation, posts, submissions = _review_inputs(tmp_path)
	paths = _write_submissions(tmp_path, submissions)
	with unittest.mock.patch(
		"daily_blog.experiment_attestation.load_review_posts",
		return_value=(attestation, posts),
	):
		_code, path = daily_blog.experiment_review_artifacts.create_review_evidence(
			config, str(attestation.path), paths,
		)
	changed_posts = dict(posts)
	changed_posts["busy"] = "# Busy\n\nThe sealed post was replaced.\n"
	with unittest.mock.patch(
		"daily_blog.experiment_attestation.load_review_posts",
		return_value=(attestation, changed_posts),
	), pytest.raises(RuntimeError, match="sealed review target"):
		daily_blog.experiment_review_artifacts.load_review_evidence(config, str(path))


#============================================
def test_review_cli_redacts_duplicate_key_and_malformed_object_failures(
	tmp_path: pathlib.Path,
	capsys: pytest.CaptureFixture[str],
) -> None:
	"""Malformed reviewer JSON reaches the stable CLI failure boundary without a traceback."""
	config = _config(tmp_path)
	attestation, posts, _submissions = _review_inputs(tmp_path)
	bad_inputs = (
		'{"reviewer_id":"reviewer-alpha","reviewer_id":"reviewer-beta"}',
		"{}",
	)
	paths = []
	for index, contents in enumerate(bad_inputs):
		path = tmp_path / f"bad-{index}.json"
		path.write_text(contents, encoding="utf-8")
		path.chmod(0o600)
		paths.append(path)
	with unittest.mock.patch(
		"daily_blog.config.load_config",
		return_value=config,
	), unittest.mock.patch(
		"daily_blog.experiment_attestation.load_review_posts",
		return_value=(attestation, posts),
	):
		codes = [
			automation.record_daily_blog_experiment_reviews.main(
				["--attestation", str(attestation.path), "--submission", str(path)],
			)
			for path in paths
		]
	message = capsys.readouterr().err

	assert codes == [2, 2] and message == (
		"Prompt experiment review evidence failed; inspect private artifacts.\n"
		"Prompt experiment review evidence failed; inspect private artifacts.\n"
	)


#============================================
def test_review_evidence_rejects_an_unsafe_existing_private_root(tmp_path: pathlib.Path) -> None:
	"""Installation refuses a pre-existing review root exposed with 0755 permissions."""
	config = _config(tmp_path)
	attestation, posts, submissions = _review_inputs(tmp_path)
	paths = _write_submissions(tmp_path, submissions)
	root = tmp_path / "vosslab" / daily_blog.experiment_review_artifacts.REVIEW_EVIDENCE_ROOT_NAME
	root.mkdir(parents=True, mode=0o755)
	root.chmod(0o755)
	with unittest.mock.patch(
		"daily_blog.experiment_attestation.load_review_posts",
		return_value=(attestation, posts),
	), pytest.raises(RuntimeError, match="Private artifact directory is unsafe"):
		daily_blog.experiment_review_artifacts.create_review_evidence(
			config, str(attestation.path), paths,
		)

"""Private historical-post and artifact I/O for maker-rubric calibration."""

from __future__ import annotations

# Standard Library
import os
import re
import json
import uuid
import pathlib
import dataclasses
import tempfile

# local repo modules
import daily_blog.candidates
import daily_blog.config
import daily_blog.evaluation
import daily_blog.io_utils
import daily_blog.private_artifacts
import daily_blog.rubric_calibration
import daily_blog.routes
import daily_blog.fixture_hermes


CALIBRATION_PROVENANCE = {
	"external_hermes": True,
	"fixture_hermes_shim": False,
}


#============================================
def strict_json_loads(value: str | bytes) -> object:
	"""Parse a JSON document without duplicate names or non-finite constants."""
	def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
		result = {}
		for key, item in pairs:
			if key in result:
				raise ValueError("Duplicate JSON member.")
			result[key] = item
		return result
	return json.loads(
		value,
		object_pairs_hook=unique_object,
		parse_constant=_reject_json_constant,
	)


#============================================
def _reject_json_constant(_value: str) -> None:
	"""Reject JSON extensions such as NaN at every calibration boundary."""
	raise ValueError("Non-finite JSON constant.")


#============================================
def _open_directory_at(parent_fd: int, name: str, *, controlled: bool) -> int:
	"""Open one fixed direct child directory without following symbolic links."""
	try:
		fd = daily_blog.private_artifacts.open_directory_at(parent_fd, name)
	except (OSError, RuntimeError) as error:
		raise RuntimeError("Calibration source contains an unsafe directory.") from error
	if controlled:
		try:
			daily_blog.private_artifacts.require_directory(fd, 0o022)
		except RuntimeError as error:
			os.close(fd)
			raise RuntimeError("Calibration directory is not producer-controlled.") from error
	return fd


#============================================
def _open_physical_directory(path: str, *, create: bool, private_leaf: bool) -> int:
	"""Open an absolute directory component-by-component and retain its descriptor."""
	fd = None
	try:
		fd = daily_blog.private_artifacts.open_physical_directory(
			path,
			create=create,
			intermediate_mode=0o755,
			leaf_mode=0o700 if private_leaf else 0o755,
		)
		daily_blog.private_artifacts.require_directory(
			fd,
			0o077 if private_leaf else 0o022,
		)
	except (OSError, RuntimeError) as error:
		if fd is not None:
			os.close(fd)
		raise RuntimeError("Calibration root is not producer-controlled.") from error
	return fd


#============================================
def _read_regular_file_at(parent_fd: int, name: str) -> bytes:
	"""Read one bounded, producer-owned regular child through a held directory."""
	try:
		contents = daily_blog.private_artifacts.read_regular_bytes_at(
			parent_fd,
			name,
			maximum_bytes=daily_blog.rubric_calibration.MAX_POST_BYTES,
			forbidden_mode=0o002,
		)
	except (OSError, RuntimeError) as error:
		raise RuntimeError("Historical calibration post is unavailable or unsafe.") from error
	return contents


#============================================
def _post_date(text: str) -> str:
	"""Return the exact created date from one historical post's front matter."""
	front_matter, _body = daily_blog.candidates.parse_front_matter(text)
	value = front_matter["date"]
	if isinstance(value, dict):
		return str(value.get("created") or "")
	return str(value)


#============================================
def load_historical_posts(
	repository_path: str,
) -> tuple[daily_blog.rubric_calibration.HistoricalPost, ...]:
	"""Load the five fixed calibration posts without caller-selected filenames."""
	repository_fd = _open_physical_directory(
		repository_path,
		create=False,
		private_leaf=False,
	)
	try:
		docs_fd = _open_directory_at(repository_fd, "docs", controlled=True)
		try:
			blog_fd = _open_directory_at(docs_fd, "blog", controlled=True)
			try:
				posts_fd = _open_directory_at(blog_fd, "posts", controlled=True)
			finally:
				os.close(blog_fd)
		finally:
			os.close(docs_fd)
	finally:
		os.close(repository_fd)
	posts = []
	try:
		for report_date in daily_blog.rubric_calibration.CALIBRATION_DATES:
			contents = _read_regular_file_at(posts_fd, report_date + ".md")
			try:
				text = contents.decode("utf-8")
			except UnicodeDecodeError as error:
				raise RuntimeError("Historical calibration post must be UTF-8.") from error
			if _post_date(text) != report_date:
				raise RuntimeError("Historical calibration post date does not match its fixed slot.")
			posts.append(
				daily_blog.rubric_calibration.HistoricalPost(
					report_date,
					text,
					daily_blog.io_utils.sha256_text(text),
					len(contents),
					daily_blog.evaluation.article_profile(text),
				)
			)
	finally:
		os.close(posts_fd)
	return tuple(posts)


#============================================
def _write_private_json(directory_fd: int, name: str, value: object) -> None:
	"""Create one private immutable JSON artifact beneath a held stage descriptor."""
	contents = daily_blog.io_utils.stable_json_text(value).encode("utf-8")
	daily_blog.private_artifacts.write_regular_bytes_at(directory_fd, name, contents)


#============================================
def _read_private_json(directory_fd: int, name: str) -> dict:
	"""Read and validate one bounded private JSON artifact from a held directory."""
	try:
		contents = daily_blog.private_artifacts.read_regular_bytes_at(
			directory_fd,
			name,
			maximum_bytes=daily_blog.rubric_calibration.MAX_ARTIFACT_BYTES,
			forbidden_mode=0o077,
		)
	except (OSError, RuntimeError) as error:
		raise RuntimeError("Private rubric calibration artifact is unavailable.") from error
	try:
		value = strict_json_loads(contents)
	except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
		raise RuntimeError("Private rubric calibration artifact JSON is invalid.") from error
	if not isinstance(value, dict):
		raise RuntimeError("Private rubric calibration artifact must be an object.")
	return value


#============================================
def _live_calibration_artifact_name(
	config: daily_blog.config.DailyBlogConfig,
	path_value: str,
) -> tuple[str, str]:
	"""Validate one caller-selected live artifact against the configured private root."""
	path = pathlib.Path(path_value)
	root = os.path.abspath(
		os.path.join(
			config.output_root,
			config.output_owner,
			daily_blog.rubric_calibration.CALIBRATION_ROOT_NAME,
		)
	)
	if not path.is_absolute() or ".." in path.parts or str(path.parent) != root:
		raise RuntimeError("Live calibration path is outside the configured private root.")
	if not daily_blog.rubric_calibration.CALIBRATION_ID_RE.fullmatch(path.name):
		raise RuntimeError("Live calibration path has an invalid artifact identity.")
	return root, path.name


#============================================
def _validated_reference_scores(report: dict) -> tuple[tuple[str, float], ...]:
	"""Return positive-reference means from one passing grounded aggregate."""
	aggregate = report.get("aggregate")
	required = {
		"band_four_unclaimed", "band_separation", "band_separation_met", "complete", "dates",
		"passage_grounded", "qualitative_consistency", "status", "targets_met",
	}
	if not isinstance(aggregate, dict) or set(aggregate) != required:
		raise RuntimeError("Live calibration aggregate fields are invalid.")
	if (
		aggregate["status"] != "pass"
		or aggregate["complete"] is not True
		or aggregate["passage_grounded"] is not True
		or aggregate["qualitative_consistency"] is not True
		or aggregate["targets_met"] is not True
		or aggregate["band_separation_met"] is not True
		or aggregate["band_four_unclaimed"] is not True
	):
		raise RuntimeError("Live calibration has not passed its historical targets.")
	dates = aggregate["dates"]
	if not isinstance(dates, dict) or set(dates) != set(
		daily_blog.rubric_calibration.CALIBRATION_DATES
	):
		raise RuntimeError("Live calibration date aggregates are invalid.")
	values = []
	for report_date in daily_blog.rubric_calibration.target_contract()["positive_passable"]["dates"]:
		entry = dates[report_date]
		if not isinstance(entry, dict):
			raise RuntimeError("Live calibration positive-reference aggregate is invalid.")
		score = entry.get("mean_weighted_score")
		if not isinstance(score, (int, float)) or isinstance(score, bool):
			raise RuntimeError("Live calibration positive-reference score is invalid.")
		if not 1 <= score <= 4:
			raise RuntimeError("Live calibration positive-reference score is invalid.")
		values.append((report_date, float(score)))
	return tuple(values)


#============================================
def _calibration_mode(value: object, *, expected: str | None = None) -> tuple[str, bool]:
	"""Validate one declared route provenance without inferring it from a name."""
	if value not in CALIBRATION_PROVENANCE:
		raise RuntimeError("Calibration route provenance is invalid.")
	mode = str(value)
	if expected is not None and mode != expected:
		raise RuntimeError("Calibration artifact has the wrong route provenance.")
	return mode, CALIBRATION_PROVENANCE[mode]


#============================================
def load_calibration_evidence(
	config: daily_blog.config.DailyBlogConfig,
	path_value: str,
	*,
	expected_mode: str | None = None,
) -> daily_blog.rubric_calibration.CalibrationEvidence:
	"""Load one passing, current, descriptor-pinned calibration with known provenance."""
	root, calibration_id = _live_calibration_artifact_name(config, path_value)
	root_fd = _open_physical_directory(root, create=False, private_leaf=True)
	try:
		artifact_fd = _open_directory_at(root_fd, calibration_id, controlled=True)
		try:
			manifest = _read_private_json(artifact_fd, "manifest.json")
			report = _read_private_json(artifact_fd, "report.json")
		finally:
			os.close(artifact_fd)
	finally:
		os.close(root_fd)
	manifest_keys = {
		"calibration_id", "fixture", "mode", "post_hashes", "report_sha256", "rubric_sha256",
		"schema_version",
	}
	report_keys = {
		"aggregate", "calibration_id", "criteria", "external_route_used", "mode",
		"fixture", "non_publishing", "preparation_id", "records", "repetitions", "route",
		"schema_version",
		"target_contract",
	}
	if set(manifest) != manifest_keys or set(report) != report_keys:
		raise RuntimeError("Live calibration artifact fields are invalid.")
	if (
		manifest["schema_version"] != daily_blog.rubric_calibration.CALIBRATION_SCHEMA_VERSION
		or report["schema_version"] != daily_blog.rubric_calibration.CALIBRATION_SCHEMA_VERSION
		or manifest["calibration_id"] != calibration_id
		or report["calibration_id"] != calibration_id
		or report["non_publishing"] is not True
	):
		raise RuntimeError("Calibration artifact identity is invalid.")
	if manifest["fixture"] != report["fixture"]:
		raise RuntimeError("Calibration artifact fixture identity is inconsistent.")
	manifest_mode, manifest_external = _calibration_mode(manifest["mode"], expected=expected_mode)
	report_mode, report_external = _calibration_mode(report["mode"], expected=expected_mode)
	if (
		manifest_mode != report_mode
		or manifest_external != report_external
		or report["external_route_used"] is not report_external
	):
		raise RuntimeError("Calibration artifact route provenance is inconsistent.")
	route = report["route"]
	if (
		not isinstance(route, dict)
		or set(route) != {"name", "command"}
		or route["name"] != config.referee_route.name
		or route["command"] != list(config.referee_route.command)
	):
		raise RuntimeError("Calibration artifact route identity is inconsistent.")
	rubric, _template, criteria = daily_blog.rubric_calibration.calibration_resources()
	posts = load_historical_posts(config.daily_blog_repository)
	if report_mode == daily_blog.fixture_hermes.FIXTURE_HERMES_SHIM:
		if config.referee_route.command != daily_blog.config.HERMES_EDITORIAL_ROUTE:
			raise RuntimeError("Fixture calibration route identity is invalid.")
		expected_fixture = _fixture_identity(_fixture_prompt_responses(posts, config, criteria))
		if report["fixture"] != expected_fixture:
			raise RuntimeError("Calibration fixture shim identity changed.")
	elif report["fixture"] is not None:
		raise RuntimeError("External calibration must not claim fixture provenance.")
	procedure = daily_blog.rubric_calibration.procedure_from_target_contract(
		report["target_contract"]
	)
	if report["repetitions"] != procedure.repetitions:
		raise RuntimeError("Live calibration repetition declaration is inconsistent.")
	recomputed_aggregate = daily_blog.rubric_calibration.aggregate_calibration(
		report["records"],
		criteria,
		posts,
		procedure,
	)
	preparation_id = daily_blog.io_utils.hash_value(
		daily_blog.rubric_calibration._preparation_identity(posts, rubric, procedure)
	)
	report_sha256 = daily_blog.io_utils.sha256_text(daily_blog.io_utils.stable_json_text(report))
	post_hashes = {post.report_date: post.sha256 for post in posts}
	if (
		manifest["rubric_sha256"] != daily_blog.rubric_calibration.CALIBRATION_CONTRACT.rubric_sha256
		or manifest["report_sha256"] != report_sha256
		or manifest["post_hashes"] != post_hashes
		or report["preparation_id"] != preparation_id
		or report["criteria"] != [dataclasses.asdict(criterion) for criterion in criteria]
		or report["target_contract"] != daily_blog.rubric_calibration.target_contract(procedure)
		or report["aggregate"] != recomputed_aggregate
	):
		raise RuntimeError("Live calibration artifact does not match current inputs.")
	reference_scores = _validated_reference_scores(report)
	return daily_blog.rubric_calibration.CalibrationEvidence(
		calibration_id,
		preparation_id,
		report_sha256,
		daily_blog.rubric_calibration.CALIBRATION_CONTRACT.rubric_sha256,
		reference_scores,
		max(score for _date, score in reference_scores),
	)


#============================================
def load_live_calibration_evidence(
	config: daily_blog.config.DailyBlogConfig,
	path_value: str,
) -> daily_blog.rubric_calibration.CalibrationEvidence:
	"""Load external-Hermes corroboration without accepting fixture evidence as live."""
	return load_calibration_evidence(
		config,
		path_value,
		expected_mode="external_hermes",
	)


#============================================
def load_fixture_calibration_evidence(
	config: daily_blog.config.DailyBlogConfig,
	path_value: str,
) -> daily_blog.rubric_calibration.CalibrationEvidence:
	"""Load the autonomous fixture-Hermes acceptance evidence by exact provenance."""
	return load_calibration_evidence(
		config,
		path_value,
		expected_mode="fixture_hermes_shim",
	)


#============================================
def _fixture_grounding_passage(post: daily_blog.rubric_calibration.HistoricalPost) -> str:
	"""Choose one bounded exact body line to make every fixture scorecard grounded."""
	_front_matter, body = daily_blog.candidates.parse_front_matter(post.text)
	for line in body.splitlines():
		passage = line.strip()
		if passage and not passage.startswith(("#", "```", "---")):
			return passage[:daily_blog.rubric_calibration.MAX_PASSAGE_CHARS]
	raise RuntimeError("Historical calibration post has no fixture grounding passage.")


#============================================
def _fixture_score(report_date: str) -> tuple[int, str]:
	"""Give the fixed historical roles stable diagnostic score bands and reasons."""
	if report_date in {"2026-08-22", "2026-08-23"}:
		return 3, "This positive voice reference is passable maker writing."
	if report_date in {"2026-08-24", "2026-08-25"}:
		return 2, "This historical post exposes the documented maker-voice failure."
	if report_date == "2026-08-26":
		return 1, "This historical post exposes the evidence and discovery failure."
	raise RuntimeError("Fixture calibration date is outside the fixed historical set.")


#============================================
def _fixture_scorecard_response(
	post: daily_blog.rubric_calibration.HistoricalPost,
	criteria: tuple[daily_blog.rubric_calibration.RubricCriterion, ...],
) -> str:
	"""Build one bounded exact-passage response for the configured referee prompt."""
	score, reason = _fixture_score(post.report_date)
	passage = _fixture_grounding_passage(post)
	return daily_blog.io_utils.stable_json_text(
		{
			"scores": {
				criterion.field: {
					"score": score,
					"passage": passage,
					"reason": reason,
				}
				for criterion in criteria
			},
			"overall_reason": reason,
		}
	)


#============================================
def _fixture_prompt_responses(
	posts: tuple[daily_blog.rubric_calibration.HistoricalPost, ...],
	config: daily_blog.config.DailyBlogConfig,
	criteria: tuple[daily_blog.rubric_calibration.RubricCriterion, ...],
) -> dict[str, str]:
	"""Map each exact configured referee prompt to its deterministic scorecard."""
	responses = {}
	for post in posts:
		prompt, rendered_criteria = daily_blog.rubric_calibration.render_calibration_prompt(
			post.text,
			config.prompt_limits["referee_chars"],
		)
		if rendered_criteria != criteria:
			raise RuntimeError("Fixture calibration criterion rendering drifted.")
		responses[prompt] = _fixture_scorecard_response(post, criteria)
	return responses


#============================================
def _fixture_identity(responses: dict[str, str]) -> dict[str, object]:
	"""Bind a fixture artifact to its schema, sealed route, and complete response map."""
	registered = daily_blog.fixture_hermes._registered_responses(responses)
	mapping_sha256 = daily_blog.io_utils.sha256_bytes(
		daily_blog.fixture_hermes._mapping_bytes(registered)
	)
	response_map_id = daily_blog.fixture_hermes._response_map_id(registered)
	identity: dict[str, object] = {
		"schema_version": daily_blog.fixture_hermes.FIXTURE_SCHEMA_VERSION,
		"mapping_sha256": mapping_sha256,
		"response_map_id": response_map_id,
		"allowed_route": list(daily_blog.config.HERMES_EDITORIAL_ROUTE),
	}
	identity["identity"] = daily_blog.io_utils.hash_value(identity)
	return identity


#============================================
def _fixture_runner_matches_identity(
	runner: daily_blog.routes.CommandRouteRunner,
	fixture: dict[str, object],
) -> bool:
	"""Return whether an installation-attested runner matches the sealed fixture identity."""
	provenance = runner.fixture_provenance
	return (
		provenance is not None
		and provenance.schema_version == fixture["schema_version"]
		and provenance.execution_mode == daily_blog.fixture_hermes.FIXTURE_HERMES_SHIM
		and provenance.external_route_used is False
		and provenance.mapping_sha256 == fixture["mapping_sha256"]
		and provenance.response_map_id == fixture["response_map_id"]
		and list(provenance.allowed_route) == fixture["allowed_route"]
	)


#============================================
def run_fixture_calibration(
	config: daily_blog.config.DailyBlogConfig,
	*,
	repetitions: int | None = None,
	maximum_criterion_score_span: int | None = None,
	minimum_positive_negative_mean_separation: float | None = None,
) -> tuple[int, str, dict]:
	"""Run mandatory offline calibration through a fresh exact-route fixture process.

	The temporary shim owns no account or network capability.  The configured referee
	route remains the sealed Hermes command, and ``CommandRouteRunner`` starts one real
	child process for each scorecard so this verifies the production route boundary.
	"""
	if config.referee_route.command != daily_blog.config.HERMES_EDITORIAL_ROUTE:
		raise RuntimeError("Fixture calibration requires the sealed Hermes referee route.")
	if repetitions is None:
		repetitions = daily_blog.rubric_calibration.DEFAULT_REPETITIONS
	if maximum_criterion_score_span is None:
		maximum_criterion_score_span = (
			daily_blog.rubric_calibration.DEFAULT_MAXIMUM_CRITERION_SCORE_SPAN
		)
	if minimum_positive_negative_mean_separation is None:
		minimum_positive_negative_mean_separation = (
			daily_blog.rubric_calibration.DEFAULT_MINIMUM_AGGREGATE_BAND_SEPARATION
		)
	procedure = daily_blog.rubric_calibration.calibration_procedure(
		repetitions=repetitions,
		maximum_criterion_score_span=maximum_criterion_score_span,
		minimum_positive_negative_mean_separation=(
			minimum_positive_negative_mean_separation
		),
	)
	posts = load_historical_posts(config.daily_blog_repository)
	rubric, _template, criteria = daily_blog.rubric_calibration.calibration_resources()
	preparation_identity = daily_blog.rubric_calibration._preparation_identity(
		posts,
		rubric,
		procedure,
	)
	responses = _fixture_prompt_responses(posts, config, criteria)
	fixture = _fixture_identity(responses)
	calibration_id = "rubric-calibration-fixture-" + daily_blog.io_utils.hash_value(
		{"fixture": fixture, "preparation": preparation_identity}
	)[:24]
	with tempfile.TemporaryDirectory(prefix="daily_blog_fixture_hermes_") as temporary_root:
		installation = daily_blog.fixture_hermes.install_fixture_hermes(
			temporary_root,
			responses,
		)
		runner = installation.create_route_runner()
		if not _fixture_runner_matches_identity(runner, fixture):
			raise RuntimeError("Fixture calibration runner identity is invalid.")
		records = daily_blog.rubric_calibration._score_records(
			posts,
			config,
			runner,
			procedure.repetitions,
		)
	aggregate = daily_blog.rubric_calibration.aggregate_calibration(
		records,
		criteria,
		posts,
		procedure,
	)
	report = daily_blog.rubric_calibration._calibration_report(
		config,
		calibration_id,
		procedure,
		preparation_identity,
		criteria,
		records,
		aggregate,
		mode=daily_blog.fixture_hermes.FIXTURE_HERMES_SHIM,
		external_route_used=daily_blog.fixture_hermes.FIXTURE_EXTERNAL_ROUTE_USED,
		fixture=fixture,
	)
	manifest = daily_blog.rubric_calibration._calibration_manifest(
		calibration_id,
		preparation_identity,
		posts,
		report,
	)
	path = install_calibration_artifacts(config, calibration_id, manifest, report)
	return (0 if aggregate["status"] == "pass" else 1), path, report


#============================================
def _remove_stage(root_fd: int, stage_name: str) -> None:
	"""Remove one known incomplete stage through its held private root."""
	daily_blog.private_artifacts.remove_known_stage(
		root_fd, stage_name, ("manifest.json", "report.json"),
	)


#============================================
def _open_existing_calibration_artifact(root_fd: int, calibration_id: str) -> int | None:
	"""Open a completed target, distinguish absence, and reject unsafe entries.

	A missing target is normal before the no-replace commit. Any other failure to
	open a target is unsafe: the caller must not treat a symbolic link, file, or
	permission failure as an available identity.
	"""
	try:
		artifact_fd = daily_blog.private_artifacts.open_directory_at(root_fd, calibration_id)
	except FileNotFoundError:
		return None
	except (OSError, RuntimeError) as error:
		raise RuntimeError("Calibration artifact target is unsafe.") from error
	try:
		daily_blog.private_artifacts.require_directory(artifact_fd, 0o022)
	except RuntimeError as error:
		os.close(artifact_fd)
		raise RuntimeError("Calibration artifact target is not producer-controlled.") from error
	return artifact_fd


#============================================
def _existing_artifact_matches(
	root_fd: int,
	calibration_id: str,
	manifest: dict,
	report: dict,
) -> bool:
	"""Return whether a completed immutable target has the requested exact bytes."""
	artifact_fd = _open_existing_calibration_artifact(root_fd, calibration_id)
	if artifact_fd is None:
		raise RuntimeError("Calibration artifact target disappeared during commit.")
	try:
		existing_manifest = _read_private_json(artifact_fd, "manifest.json")
		existing_report = _read_private_json(artifact_fd, "report.json")
	finally:
		os.close(artifact_fd)
	return existing_manifest == manifest and existing_report == report


#============================================
def install_calibration_artifacts(
	config: daily_blog.config.DailyBlogConfig,
	calibration_id: str,
	manifest: dict,
	report: dict,
) -> str:
	"""Atomically install one immutable private calibration directory."""
	if not daily_blog.rubric_calibration.CALIBRATION_ID_RE.fullmatch(calibration_id):
		raise RuntimeError("Rubric calibration ID is invalid.")
	if not re.fullmatch(r"[A-Za-z0-9-]+", config.output_owner):
		raise RuntimeError("Rubric calibration output owner is invalid.")
	root = os.path.abspath(
		os.path.join(
			config.output_root,
			config.output_owner,
			daily_blog.rubric_calibration.CALIBRATION_ROOT_NAME,
		)
	)
	root_fd = _open_physical_directory(root, create=True, private_leaf=True)
	stage_name = "." + calibration_id + "." + uuid.uuid4().hex + ".stage"
	try:
		stage_fd = daily_blog.private_artifacts.create_private_stage_at(
			root_fd, stage_name, 0o022,
		)
		try:
			try:
				_write_private_json(stage_fd, "manifest.json", manifest)
				_write_private_json(stage_fd, "report.json", report)
				os.fsync(stage_fd)
			finally:
				os.close(stage_fd)
			daily_blog.private_artifacts.rename_directory_noreplace_at(
				root_fd, stage_name, calibration_id,
			)
			os.fsync(root_fd)
		except FileExistsError:
			_remove_stage(root_fd, stage_name)
			if not _existing_artifact_matches(root_fd, calibration_id, manifest, report):
				raise RuntimeError("Immutable rubric calibration output identity conflicts.")
		except BaseException:
			_remove_stage(root_fd, stage_name)
			raise
	finally:
		os.close(root_fd)
	return os.path.join(root, calibration_id)

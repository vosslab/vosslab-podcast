"""Private historical-post and artifact I/O for maker-rubric calibration."""

from __future__ import annotations

# Standard Library
import os
import re
import json
import uuid
import pathlib
import dataclasses

# local repo modules
import daily_blog.candidates
import daily_blog.config
import daily_blog.evaluation
import daily_blog.io_utils
import daily_blog.private_artifacts
import daily_blog.rubric_calibration


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
		value = json.loads(contents)
	except (UnicodeDecodeError, json.JSONDecodeError) as error:
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
	"""Return exact stable positive-reference scores from one passing aggregate."""
	aggregate = report.get("aggregate")
	required = {
		"band_four_unclaimed", "complete", "dates", "stable", "status", "targets_met",
	}
	if not isinstance(aggregate, dict) or set(aggregate) != required:
		raise RuntimeError("Live calibration aggregate fields are invalid.")
	if (
		aggregate["status"] != "pass"
		or aggregate["complete"] is not True
		or aggregate["stable"] is not True
		or aggregate["targets_met"] is not True
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
		if type(score) not in {int, float} or not 1 <= score <= 4:
			raise RuntimeError("Live calibration positive-reference score is invalid.")
		values.append((report_date, float(score)))
	return tuple(values)


#============================================
def load_live_calibration_evidence(
	config: daily_blog.config.DailyBlogConfig,
	path_value: str,
) -> daily_blog.rubric_calibration.CalibrationEvidence:
	"""Load one passing, current, descriptor-pinned historical calibration artifact."""
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
		"calibration_id", "mode", "post_hashes", "report_sha256", "rubric_sha256", "schema_version",
	}
	report_keys = {
		"aggregate", "calibration_id", "criteria", "external_route_used", "mode",
		"non_publishing", "preparation_id", "records", "repetitions", "route", "schema_version",
		"target_contract",
	}
	if set(manifest) != manifest_keys or set(report) != report_keys:
		raise RuntimeError("Live calibration artifact fields are invalid.")
	if (
		manifest["schema_version"] != daily_blog.rubric_calibration.CALIBRATION_SCHEMA_VERSION
		or report["schema_version"] != daily_blog.rubric_calibration.CALIBRATION_SCHEMA_VERSION
		or manifest["calibration_id"] != calibration_id
		or report["calibration_id"] != calibration_id
		or manifest["mode"] != "live"
		or report["mode"] != "live"
		or report["non_publishing"] is not True
		or report["external_route_used"] is not True
	):
		raise RuntimeError("Live calibration artifact identity is invalid.")
	rubric, _template, criteria = daily_blog.rubric_calibration.calibration_resources()
	posts = load_historical_posts(config.daily_blog_repository)
	preparation_id = daily_blog.io_utils.hash_value(
		daily_blog.rubric_calibration._preparation_identity(posts, rubric)
	)
	report_sha256 = daily_blog.io_utils.sha256_text(daily_blog.io_utils.stable_json_text(report))
	post_hashes = {post.report_date: post.sha256 for post in posts}
	if (
		manifest["rubric_sha256"] != daily_blog.rubric_calibration.CALIBRATION_CONTRACT.rubric_sha256
		or manifest["report_sha256"] != report_sha256
		or manifest["post_hashes"] != post_hashes
		or report["preparation_id"] != preparation_id
		or report["criteria"] != [dataclasses.asdict(criterion) for criterion in criteria]
		or report["target_contract"] != daily_blog.rubric_calibration.target_contract()
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

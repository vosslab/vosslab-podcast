"""Immutable, route-free acceptance attestations for prompt-experiment captures."""

# Standard Library
import dataclasses
import json
import os
import pathlib
import re
import uuid

# local repo modules
import daily_blog.config
import daily_blog.experiment_acceptance
import daily_blog.experiment_capture_artifacts
import daily_blog.io_utils
import daily_blog.private_artifacts
import daily_blog.rubric_calibration


ATTESTATION_SCHEMA = "vosslab.daily-blog.prompt-experiment-attestation.v2"
ATTESTATION_ROOT_NAME = "daily_blog_experiment_attestations"
EXPERIMENT_ROOT_NAME = "daily_blog_experiments"
ATTESTATION_ID_RE = re.compile(r"^prompt-experiment-attestation-[0-9a-f]{64}$")
OWNER_RE = re.compile(r"^[A-Za-z0-9-]+$")
MAX_ARTIFACT_BYTES = 4_000_000


@dataclasses.dataclass(frozen=True)
class ExperimentAttestation:
	"""One verified, non-publishing record of a capture and calibration join."""

	path: pathlib.Path
	manifest: dict[str, object]
	report: dict[str, object]


#============================================
def _json_bytes(value: object) -> bytes:
	"""Return the canonical bytes used for an immutable private JSON artifact."""
	return daily_blog.io_utils.stable_json_text(value).encode("utf-8")


#============================================
def _private_root(config: daily_blog.config.DailyBlogConfig, name: str) -> str:
	"""Return one configured owner-qualified private root after strict validation."""
	if not OWNER_RE.fullmatch(config.output_owner):
		raise RuntimeError("Prompt experiment output owner is invalid.")
	return os.path.abspath(os.path.join(config.output_root, config.output_owner, name))


#============================================
def _artifact_name(path_value: str, root: str, pattern: re.Pattern[str], label: str) -> str:
	"""Require an absolute direct-child artifact under its configured private root."""
	# ASVS 2.2.1: accept only one allowlisted artifact identity below the configured root.
	path = pathlib.Path(path_value)
	if (
		not path.is_absolute()
		or ".." in path.parts
		or str(path.parent) != root
		or not pattern.fullmatch(path.name)
	):
		raise RuntimeError(f"{label} path is outside its configured private root.")
	return path.name


#============================================
def _capture_reference(
	config: daily_blog.config.DailyBlogConfig,
	path_value: str,
) -> tuple[str, daily_blog.experiment_capture_artifacts.ExperimentCapture]:
	"""Load a capture only from its configured direct-child experiment root."""
	name = _artifact_name(
		path_value,
		_private_root(config, EXPERIMENT_ROOT_NAME),
		daily_blog.experiment_capture_artifacts.EXPERIMENT_ID_RE,
		"Prompt experiment capture",
	)
	capture = daily_blog.experiment_capture_artifacts.load_capture(path_value)
	if capture.path.name != name:
		raise RuntimeError("Prompt experiment capture identity drifted during load.")
	return name, capture


#============================================
def _calibration_reference(
	config: daily_blog.config.DailyBlogConfig,
	path_value: str,
) -> tuple[str, daily_blog.rubric_calibration.CalibrationEvidence]:
	"""Load a passing live calibration only from its configured direct-child root."""
	name = _artifact_name(
		path_value,
		_private_root(config, daily_blog.rubric_calibration.CALIBRATION_ROOT_NAME),
		daily_blog.rubric_calibration.CALIBRATION_ID_RE,
		"Live calibration",
	)
	evidence = daily_blog.rubric_calibration.load_live_calibration_evidence(config, path_value)
	if evidence.calibration_id != name:
		raise RuntimeError("Live calibration identity drifted during load.")
	return name, evidence


#============================================
def _acceptance(
	capture: daily_blog.experiment_capture_artifacts.ExperimentCapture,
	calibration: daily_blog.rubric_calibration.CalibrationEvidence,
) -> dict[str, object]:
	"""Recompute the deterministic experiment decision from verified source artifacts."""
	manifest = capture.manifest
	report = capture.report
	result = daily_blog.experiment_acceptance.build_acceptance_result(
		report["records"], report["comparisons"], manifest["repetitions"], calibration,
		tuple(manifest["arms"]),
	)
	if result.get("schema_version") != daily_blog.experiment_acceptance.ACCEPTANCE_SCHEMA:
		raise RuntimeError("Prompt experiment acceptance schema is invalid.")
	return result


#============================================
def _report(
	capture_name: str,
	capture: daily_blog.experiment_capture_artifacts.ExperimentCapture,
	calibration_name: str,
	calibration: daily_blog.rubric_calibration.CalibrationEvidence,
	acceptance: dict[str, object],
) -> dict[str, object]:
	"""Build the exact route-free attestation evidence object."""
	return {
		"schema_version": ATTESTATION_SCHEMA,
		"experiment_id": capture.manifest["experiment_id"],
		"capture": {
			"artifact": capture_name,
			"capture_id": capture.manifest["capture_id"],
			"report_sha256": capture.manifest["report_sha256"],
		},
		"calibration": {"artifact": calibration_name, "evidence": calibration.to_dict()},
		"acceptance_schema": daily_blog.experiment_acceptance.ACCEPTANCE_SCHEMA,
		"acceptance": acceptance,
		"non_publishing": True,
	}


#============================================
def _manifest(report_bytes: bytes, report: dict[str, object]) -> dict[str, object]:
	"""Build the content-addressed immutable manifest for one attestation report."""
	identity = {
		"schema_version": ATTESTATION_SCHEMA,
		"experiment_id": report["experiment_id"],
		"capture": report["capture"],
		"calibration": report["calibration"],
		"acceptance_schema": report["acceptance_schema"],
		"acceptance": report["acceptance"],
		"report_sha256": daily_blog.io_utils.sha256_bytes(report_bytes),
		"non_publishing": True,
	}
	return {
		**identity,
		"attestation_id": "prompt-experiment-attestation-"
		+ daily_blog.io_utils.hash_value(identity),
	}


#============================================
def _read_json(directory_fd: int, name: str) -> dict[str, object]:
	"""Read one bounded private JSON object through a held descriptor."""
	contents = daily_blog.private_artifacts.read_regular_bytes_at(
		directory_fd, name, MAX_ARTIFACT_BYTES, 0o077,
	)
	try:
		value = json.loads(contents.decode("utf-8"))
	except (UnicodeDecodeError, ValueError) as error:
		raise RuntimeError("Prompt experiment attestation JSON is invalid.") from error
	if not isinstance(value, dict):
		raise RuntimeError("Prompt experiment attestation must be a JSON object.")
	return value


#============================================
def _validate_report_and_manifest(
	manifest: dict[str, object], report: dict[str, object], report_bytes: bytes, name: str,
) -> None:
	"""Validate the complete attestation schema and its directory identity."""
	manifest_keys = {
		"schema_version", "experiment_id", "capture", "calibration", "acceptance_schema",
		"acceptance", "report_sha256", "non_publishing", "attestation_id",
	}
	report_keys = {
		"schema_version", "experiment_id", "capture", "calibration", "acceptance_schema",
		"acceptance", "non_publishing",
	}
	if set(manifest) != manifest_keys or set(report) != report_keys:
		raise RuntimeError("Prompt experiment attestation fields are invalid.")
	if (
		manifest.get("schema_version") != ATTESTATION_SCHEMA
		or report.get("schema_version") != ATTESTATION_SCHEMA
	):
		raise RuntimeError("Prompt experiment attestation schema is invalid.")
	if manifest.get("non_publishing") is not True or report.get("non_publishing") is not True:
		raise RuntimeError("Prompt experiment attestation must remain non-publishing.")
	if manifest.get("report_sha256") != daily_blog.io_utils.sha256_bytes(report_bytes):
		raise RuntimeError("Prompt experiment attestation report digest is invalid.")
	if {key: manifest[key] for key in report_keys} != report:
		raise RuntimeError("Prompt experiment attestation manifest and report differ.")
	identity = {key: value for key, value in manifest.items() if key != "attestation_id"}
	expected = "prompt-experiment-attestation-" + daily_blog.io_utils.hash_value(identity)
	if (
		manifest.get("attestation_id") != expected
		or name != expected
		or not ATTESTATION_ID_RE.fullmatch(name)
	):
		raise RuntimeError("Prompt experiment attestation identity is invalid.")
	if report.get("acceptance_schema") != daily_blog.experiment_acceptance.ACCEPTANCE_SCHEMA:
		raise RuntimeError("Prompt experiment attestation acceptance schema is invalid.")


#============================================
def _source_paths(
	config: daily_blog.config.DailyBlogConfig, report: dict[str, object],
) -> tuple[str, str]:
	"""Recover only approved direct-child source references from an attestation report."""
	capture = report.get("capture")
	calibration = report.get("calibration")
	if not isinstance(capture, dict) or set(capture) != {"artifact", "capture_id", "report_sha256"}:
		raise RuntimeError("Prompt experiment attestation capture reference is invalid.")
	if not isinstance(calibration, dict) or set(calibration) != {"artifact", "evidence"}:
		raise RuntimeError("Prompt experiment attestation calibration reference is invalid.")
	capture_name = capture.get("artifact")
	calibration_name = calibration.get("artifact")
	if (
		not isinstance(capture_name, str)
		or not daily_blog.experiment_capture_artifacts.EXPERIMENT_ID_RE.fullmatch(capture_name)
	):
		raise RuntimeError("Prompt experiment attestation capture artifact is invalid.")
	if (
		not isinstance(calibration_name, str)
		or not daily_blog.rubric_calibration.CALIBRATION_ID_RE.fullmatch(calibration_name)
	):
		raise RuntimeError("Prompt experiment attestation calibration artifact is invalid.")
	return (
		os.path.join(_private_root(config, EXPERIMENT_ROOT_NAME), capture_name),
		os.path.join(
			_private_root(config, daily_blog.rubric_calibration.CALIBRATION_ROOT_NAME),
			calibration_name,
		),
	)


#============================================
def _install(
	config: daily_blog.config.DailyBlogConfig,
	manifest: dict[str, object],
	report: dict[str, object],
) -> pathlib.Path:
	"""Atomically install one descriptor-pinned immutable attestation directory."""
	name = manifest["attestation_id"]
	if not isinstance(name, str) or not ATTESTATION_ID_RE.fullmatch(name):
		raise RuntimeError("Prompt experiment attestation ID is invalid.")
	root = _private_root(config, ATTESTATION_ROOT_NAME)
	root_fd = daily_blog.private_artifacts.open_physical_directory(
		root,
		create=True,
		intermediate_mode=0o755,
		leaf_mode=0o700,
	)
	# ASVS 2.3.3: each transaction exclusively owns its UUID stage; stale peer
	# stages cannot prevent an independent attempt from reaching the final commit.
	stage_name = "." + name + "." + uuid.uuid4().hex + ".stage"
	try:
		stage_fd = daily_blog.private_artifacts.create_private_stage_at(root_fd, stage_name, 0o077)
		try:
			daily_blog.private_artifacts.write_regular_bytes_at(
				stage_fd, "manifest.json", _json_bytes(manifest)
			)
			daily_blog.private_artifacts.write_regular_bytes_at(
				stage_fd, "report.json", _json_bytes(report)
			)
			os.fsync(stage_fd)
		finally:
			os.close(stage_fd)
		try:
			# ASVS 2.3.3: reveal a fully synced stage with an OS no-replace commit.
			daily_blog.private_artifacts.rename_directory_noreplace_at(root_fd, stage_name, name)
		except FileExistsError:
			daily_blog.private_artifacts.remove_known_stage(
				root_fd,
				stage_name,
				("manifest.json", "report.json"),
			)
			return pathlib.Path(root) / name
		os.fsync(root_fd)
	finally:
		os.close(root_fd)
	return pathlib.Path(root) / name


#============================================
def create_attestation(
	config: daily_blog.config.DailyBlogConfig,
	capture_path: str,
	calibration_path: str,
) -> tuple[int, pathlib.Path]:
	"""Create a deterministic attestation without loading or invoking any model route."""
	capture_name, capture = _capture_reference(config, capture_path)
	calibration_name, calibration = _calibration_reference(config, calibration_path)
	acceptance = _acceptance(capture, calibration)
	report = _report(capture_name, capture, calibration_name, calibration, acceptance)
	manifest = _manifest(_json_bytes(report), report)
	path = _install(config, manifest, report)
	loaded = load_attestation(config, str(path))
	# ASVS 2.3.3: an immutable final is idempotent only when its descriptor-read
	# contents equal the newly computed source-bound result; never replace it.
	if loaded.manifest != manifest or loaded.report != report:
		raise RuntimeError("Existing prompt experiment attestation differs from this result.")
	return (0 if loaded.report["acceptance"]["activation_ready"] else 1), path


#============================================
def load_attestation(
	config: daily_blog.config.DailyBlogConfig,
	path_value: str,
) -> ExperimentAttestation:
	"""Load, independently recompute, and verify an immutable attestation every time."""
	root = _private_root(config, ATTESTATION_ROOT_NAME)
	name = _artifact_name(path_value, root, ATTESTATION_ID_RE, "Prompt experiment attestation")
	# ASVS 1.5.2 and 2.2.1: descriptor reads and exact JSON schemas fail closed on tampering.
	root_fd = daily_blog.private_artifacts.open_physical_directory(
		root,
		create=False,
		intermediate_mode=0o755,
		leaf_mode=0o700,
	)
	try:
		daily_blog.private_artifacts.require_directory(root_fd, 0o077)
		artifact_fd = daily_blog.private_artifacts.open_directory_at(root_fd, name)
		try:
			daily_blog.private_artifacts.require_directory(artifact_fd, 0o077)
			manifest = _read_json(artifact_fd, "manifest.json")
			report_bytes = daily_blog.private_artifacts.read_regular_bytes_at(
				artifact_fd,
				"report.json",
				MAX_ARTIFACT_BYTES,
				0o077,
			)
			try:
				report = json.loads(report_bytes.decode("utf-8"))
			except (UnicodeDecodeError, ValueError) as error:
				raise RuntimeError("Prompt experiment attestation JSON is invalid.") from error
			if not isinstance(report, dict):
				raise RuntimeError("Prompt experiment attestation must be a JSON object.")
		finally:
			os.close(artifact_fd)
	finally:
		os.close(root_fd)
	_validate_report_and_manifest(manifest, report, report_bytes, name)
	capture_path, calibration_path = _source_paths(config, report)
	capture_name, capture = _capture_reference(config, capture_path)
	calibration_name, calibration = _calibration_reference(config, calibration_path)
	expected = _report(
		capture_name,
		capture,
		calibration_name,
		calibration,
		_acceptance(capture, calibration),
	)
	if report != expected:
		raise RuntimeError("Prompt experiment attestation source evidence drifted.")
	return ExperimentAttestation(pathlib.Path(path_value), manifest, report)

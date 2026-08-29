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
import daily_blog.experiment_review_contract
import daily_blog.io_utils
import daily_blog.private_artifacts
import daily_blog.rubric_calibration


ATTESTATION_SCHEMA = "vosslab.daily-blog.prompt-experiment-attestation.v4"
ATTESTATION_ROOT_NAME = "daily_blog_experiment_attestations"
EXPERIMENT_ROOT_NAME = "daily_blog_experiments"
ATTESTATION_ID_RE = re.compile(r"^prompt-experiment-attestation-[0-9a-f]{64}$")
OWNER_RE = re.compile(r"^[A-Za-z0-9-]+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
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
	"""Load the sealed fixture-Hermes capture required for autonomous F4."""
	name = _artifact_name(
		path_value,
		_private_root(config, EXPERIMENT_ROOT_NAME),
		daily_blog.experiment_capture_artifacts.EXPERIMENT_ID_RE,
		"Prompt experiment capture",
	)
	capture = daily_blog.experiment_capture_artifacts.load_capture(path_value)
	if capture.path.name != name:
		raise RuntimeError("Prompt experiment capture identity drifted during load.")
	if (
		capture.manifest["execution_mode"]
		!= daily_blog.experiment_capture_artifacts.FIXTURE_HERMES_SHIM
		or capture.manifest["external_route_used"] is not False
	):
		raise RuntimeError("Prompt experiment attestation requires fixture-backed capture evidence.")
	_fixture_shim_identity(capture)
	return name, capture


#============================================
def _fixture_shim_identity(
	capture: daily_blog.experiment_capture_artifacts.ExperimentCapture,
) -> str:
	"""Return the stable digest of the capture loader's installation attestation."""
	fixture_shim = capture.manifest.get("fixture_shim")
	if not isinstance(fixture_shim, dict) or not fixture_shim:
		raise RuntimeError("Prompt experiment capture fixture-shim provenance is invalid.")
	identity = daily_blog.io_utils.hash_value(fixture_shim)
	if not SHA256_RE.fullmatch(identity):
		raise RuntimeError("Prompt experiment capture fixture-shim identity is invalid.")
	return identity


#============================================
def _calibration_reference(
	config: daily_blog.config.DailyBlogConfig,
	path_value: str,
) -> tuple[str, daily_blog.rubric_calibration.CalibrationEvidence]:
	"""Load the fixture-Hermes calibration required for autonomous F4."""
	name = _artifact_name(
		path_value,
		_private_root(config, daily_blog.rubric_calibration.CALIBRATION_ROOT_NAME),
		daily_blog.rubric_calibration.CALIBRATION_ID_RE,
		"Fixture calibration",
	)
	evidence = daily_blog.rubric_calibration.load_fixture_calibration_evidence(config, path_value)
	if evidence.calibration_id != name:
		raise RuntimeError("Fixture calibration identity drifted during load.")
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
	reviewer_count: int,
) -> dict[str, object]:
	"""Build the exact route-free attestation evidence object."""
	return {
		"schema_version": ATTESTATION_SCHEMA,
		"experiment_id": capture.manifest["experiment_id"],
		"capture": {
			"artifact": capture_name,
			"capture_id": capture.manifest["capture_id"],
			"report_sha256": capture.manifest["report_sha256"],
			"execution_mode": capture.manifest["execution_mode"],
			"external_route_used": capture.manifest["external_route_used"],
			"fixture_shim_identity": _fixture_shim_identity(capture),
		},
		"calibration": {
			"artifact": calibration_name,
			"mode": daily_blog.experiment_capture_artifacts.FIXTURE_HERMES_SHIM,
			"external_route_used": False,
			"evidence": calibration.to_dict(),
		},
		"acceptance_schema": daily_blog.experiment_acceptance.ACCEPTANCE_SCHEMA,
		"acceptance": acceptance,
		"review_contract": daily_blog.experiment_review_contract.build_review_contract(
			acceptance,
			capture.manifest,
			capture.report,
			reviewer_count,
		),
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
		"review_contract": report["review_contract"],
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
		value = _strict_json_loads(contents)
	except (UnicodeDecodeError, ValueError) as error:
		raise RuntimeError("Prompt experiment attestation JSON is invalid.") from error
	if not isinstance(value, dict):
		raise RuntimeError("Prompt experiment attestation must be a JSON object.")
	return value


#============================================
def _strict_json_loads(contents: bytes) -> object:
	"""Parse sealed JSON without ambiguous duplicate names or non-finite values."""
	def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
		result = {}
		for key, value in pairs:
			if key in result:
				raise ValueError("Duplicate JSON member.")
			result[key] = value
		return result
	return json.loads(
		contents.decode("utf-8"),
		object_pairs_hook=unique_object,
		parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("Non-finite JSON constant.")),
	)


#============================================
def _validate_report_and_manifest(
	manifest: dict[str, object], report: dict[str, object], report_bytes: bytes, name: str,
) -> None:
	"""Validate the complete attestation schema and its directory identity."""
	manifest_keys = {
		"schema_version", "experiment_id", "capture", "calibration", "acceptance_schema",
		"acceptance", "review_contract", "report_sha256", "non_publishing", "attestation_id",
	}
	report_keys = {
		"schema_version", "experiment_id", "capture", "calibration", "acceptance_schema",
		"acceptance", "review_contract", "non_publishing",
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
	if not isinstance(capture, dict) or set(capture) != {
		"artifact", "capture_id", "report_sha256", "execution_mode", "external_route_used",
		"fixture_shim_identity",
	}:
		raise RuntimeError("Prompt experiment attestation capture reference is invalid.")
	if not isinstance(calibration, dict) or set(calibration) != {
		"artifact", "mode", "external_route_used", "evidence",
	}:
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
	if (
		capture["execution_mode"]
		!= daily_blog.experiment_capture_artifacts.FIXTURE_HERMES_SHIM
		or capture["external_route_used"] is not False
		or calibration["mode"] != daily_blog.experiment_capture_artifacts.FIXTURE_HERMES_SHIM
		or calibration["external_route_used"] is not False
		or not isinstance(capture["fixture_shim_identity"], str)
		or not SHA256_RE.fullmatch(capture["fixture_shim_identity"])
	):
		raise RuntimeError("Prompt experiment attestation provenance is invalid.")
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
	reviewer_count: int = daily_blog.experiment_review_contract.DEFAULT_REVIEWER_COUNT,
) -> tuple[int, pathlib.Path]:
	"""Create a deterministic attestation without loading or invoking any model route."""
	capture_name, capture = _capture_reference(config, capture_path)
	calibration_name, calibration = _calibration_reference(config, calibration_path)
	acceptance = _acceptance(capture, calibration)
	report = _report(
		capture_name, capture, calibration_name, calibration, acceptance, reviewer_count,
	)
	manifest = _manifest(_json_bytes(report), report)
	path = _install(config, manifest, report)
	loaded = load_attestation(config, str(path))
	# ASVS 2.3.3: an immutable final is idempotent only when its descriptor-read
	# contents equal the newly computed source-bound result; never replace it.
	if loaded.manifest != manifest or loaded.report != report:
		raise RuntimeError("Existing prompt experiment attestation differs from this result.")
	return (0 if loaded.report["acceptance"]["review_ready"] else 1), path


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
				report = _strict_json_loads(report_bytes)
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
	review_contract = report.get("review_contract")
	if not isinstance(review_contract, dict):
		raise RuntimeError("Prompt experiment review contract is invalid.")
	reviewer_count = review_contract.get("reviewer_count")
	expected = _report(
		capture_name,
		capture,
		calibration_name,
		calibration,
		_acceptance(capture, calibration),
		reviewer_count,
	)
	if report != expected:
		raise RuntimeError("Prompt experiment attestation source evidence drifted.")
	return ExperimentAttestation(pathlib.Path(path_value), manifest, report)


#============================================
def _load_review_posts_from_capture(
	capture: daily_blog.experiment_capture_artifacts.ExperimentCapture,
	contract: dict[str, object],
) -> dict[str, str]:
	"""Read the two exact complete posts sealed into a ready review contract."""
	validated = daily_blog.experiment_review_contract.validate_review_contract(contract)
	if validated["status"] != "ready":
		raise RuntimeError("Prompt experiment attestation is not ready for review.")
	root_fd = daily_blog.private_artifacts.open_physical_directory(
		str(capture.path),
		create=False,
		intermediate_mode=0o755,
		leaf_mode=0o700,
	)
	posts = {}
	try:
		daily_blog.private_artifacts.require_directory(root_fd, 0o077)
		for fixture in ("busy", "quiet"):
			reference = validated["fixtures"][fixture]["selected_post"]
			artifact = pathlib.PurePosixPath(reference["artifact"])
			if len(artifact.parts) != 2 or artifact.name != "selected.md":
				raise RuntimeError("Independent review selected-post path is invalid.")
			# ASVS 5.3.2: the sealed contract generates one direct child and fixed filename.
			arm_fd = daily_blog.private_artifacts.open_directory_at(root_fd, artifact.parts[0])
			try:
				contents = daily_blog.private_artifacts.read_regular_bytes_at(
					arm_fd,
					"selected.md",
					MAX_ARTIFACT_BYTES,
					0o077,
				)
			finally:
				os.close(arm_fd)
			try:
				post = contents.decode("utf-8")
			except UnicodeDecodeError as error:
				raise RuntimeError("Independent review selected post is invalid UTF-8.") from error
			# ASVS 11.4.3: reviewers receive only bytes matching the sealed SHA-256 identity.
			if daily_blog.io_utils.sha256_text(post) != reference["post_sha256"]:
				raise RuntimeError("Independent review selected-post identity is invalid.")
			posts[fixture] = post
	finally:
		os.close(root_fd)
	return posts


#============================================
def load_review_posts(
	config: daily_blog.config.DailyBlogConfig,
	attestation_path: str,
) -> tuple[ExperimentAttestation, dict[str, str]]:
	"""Load a verified attestation and the exact busy and quiet posts it binds."""
	attestation = load_attestation(config, attestation_path)
	capture_path, _calibration_path = _source_paths(config, attestation.report)
	_capture_name, capture = _capture_reference(config, capture_path)
	contract = attestation.report.get("review_contract")
	if not isinstance(contract, dict):
		raise RuntimeError("Prompt experiment review contract is invalid.")
	return attestation, _load_review_posts_from_capture(capture, contract)

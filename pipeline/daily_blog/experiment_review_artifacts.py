"""Immutable, route-free F4 evidence from independent maker-post reviews."""

# Standard Library
import dataclasses
import json
import os
import pathlib
import re
import uuid

# local repo modules
import daily_blog.config
import daily_blog.experiment_attestation
import daily_blog.experiment_review_contract
import daily_blog.io_utils
import daily_blog.private_artifacts


REVIEW_EVIDENCE_SCHEMA = "vosslab.daily-blog.prompt-experiment-review-evidence.v1"
REVIEW_EVIDENCE_ROOT_NAME = "daily_blog_experiment_review_evidence"
REVIEW_EVIDENCE_ID_RE = re.compile(r"^prompt-experiment-review-evidence-[0-9a-f]{64}$")
OWNER_RE = re.compile(r"^[A-Za-z0-9-]+$")
MAX_ARTIFACT_BYTES = 4_000_000
MAX_SUBMISSION_BYTES = 1_000_000


@dataclasses.dataclass(frozen=True)
class ReviewEvidence:
	"""One verified immutable F4 result that cannot publish or activate anything."""

	path: pathlib.Path
	manifest: dict[str, object]
	report: dict[str, object]


#============================================
def _json_bytes(value: object) -> bytes:
	"""Return canonical bytes for one immutable private JSON artifact."""
	contents = daily_blog.io_utils.stable_json_text(value).encode("utf-8")
	return contents


#============================================
def _private_root(config: daily_blog.config.DailyBlogConfig) -> str:
	"""Return the configured owner-qualified private review-evidence root."""
	if not OWNER_RE.fullmatch(config.output_owner):
		raise RuntimeError("Prompt experiment output owner is invalid.")
	root = os.path.abspath(
		os.path.join(config.output_root, config.output_owner, REVIEW_EVIDENCE_ROOT_NAME)
	)
	return root


#============================================
def _artifact_name(path_value: str, root: str, pattern: re.Pattern[str], label: str) -> str:
	"""Require an absolute direct-child artifact beneath one configured private root."""
	path = pathlib.Path(path_value)
	# ASVS 2.2.1: accept only one allowlisted direct child below the configured root.
	if (
		not path.is_absolute()
		or ".." in path.parts
		or str(path.parent) != root
		or not pattern.fullmatch(path.name)
	):
		raise RuntimeError(f"{label} path is outside its configured private root.")
	name = path.name
	return name


#============================================
def _read_json_bytes(contents: bytes, label: str) -> dict[str, object]:
	"""Decode one bounded JSON object without exposing its private contents on failure."""
	# ASVS 2.1.1-2.1.3: parse one declared syntax and reject non-object input at the boundary.
	try:
		value = json.loads(
			contents.decode("utf-8"),
			object_pairs_hook=_unique_object,
			parse_constant=_reject_json_constant,
		)
	except (UnicodeDecodeError, ValueError) as error:
		raise RuntimeError(f"{label} is invalid.") from error
	if not isinstance(value, dict):
		raise RuntimeError(f"{label} must be a JSON object.")
	return value


#============================================
def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
	"""Build one JSON object while refusing ambiguous duplicate member names."""
	value = {}
	for key, item in pairs:
		if key in value:
			raise ValueError("Duplicate JSON key.")
		value[key] = item
	return value


#============================================
def _reject_json_constant(value: str) -> None:
	"""Reject non-standard JSON numeric constants instead of silently accepting them."""
	raise ValueError("Invalid JSON constant: " + value)


#============================================
def _read_submission(path_value: str) -> dict[str, object]:
	"""Read one bounded local submission through physical descriptor checks."""
	path = pathlib.Path(path_value)
	if (
		not path.is_absolute()
		or ".." in path.parts
		or path.suffix != ".json"
		or path.name != os.path.basename(path_value)
	):
		raise RuntimeError("Independent review submission path is invalid.")
	parent_fd = -1
	try:
		parent_fd = daily_blog.private_artifacts.open_physical_directory(
			str(path.parent),
			create=False,
			intermediate_mode=0o755,
			leaf_mode=0o700,
		)
		# ASVS 2.2.1 and 5.3.2: bound and validate opened parent and child, not path strings.
		daily_blog.private_artifacts.require_directory(parent_fd, 0o077)
		contents = daily_blog.private_artifacts.read_regular_bytes_at(
			parent_fd,
			path.name,
			MAX_SUBMISSION_BYTES,
			0o077,
		)
	except (OSError, RuntimeError) as error:
		raise RuntimeError("Independent review submission is unavailable or unsafe.") from error
	finally:
		if parent_fd >= 0:
			os.close(parent_fd)
	submission = _read_json_bytes(contents, "Independent review submission")
	return submission


#============================================
def _load_submissions(
	paths: list[str],
	contract: dict[str, object],
	posts: dict[str, str],
) -> list[dict[str, object]]:
	"""Load, validate, and seal canonical submissions without retaining staging paths."""
	validated_contract = daily_blog.experiment_review_contract.validate_review_contract(contract)
	reviewer_count = validated_contract["reviewer_count"]
	if not isinstance(paths, list) or len(paths) != reviewer_count:
		raise RuntimeError("Independent review submission count differs from its contract.")
	if any(not isinstance(path_value, str) for path_value in paths) or len(set(paths)) != len(paths):
		raise RuntimeError("Independent review submission paths must be distinct.")
	loaded = [_read_submission(path_value) for path_value in paths]
	validated = [
		daily_blog.experiment_review_contract.validate_review_submission(
			submission, validated_contract, posts,
		)
		for submission in loaded
	]
	result = sorted(
		[
			{
				"reviewer_id": submission["reviewer_id"],
				"sha256": daily_blog.io_utils.hash_value(submission),
				"submission": submission,
			}
			for submission in validated
		],
		key=lambda entry: entry["reviewer_id"],
	)
	return result


#============================================
def _attestation_reference(
	config: daily_blog.config.DailyBlogConfig,
	attestation_path: str,
) -> tuple[daily_blog.experiment_attestation.ExperimentAttestation, dict[str, str]]:
	"""Load only the configured direct-child attestation and its sealed complete posts."""
	if not OWNER_RE.fullmatch(config.output_owner):
		raise RuntimeError("Prompt experiment output owner is invalid.")
	root = os.path.abspath(
		os.path.join(
			config.output_root,
			config.output_owner,
			daily_blog.experiment_attestation.ATTESTATION_ROOT_NAME,
		)
	)
	_artifact_name(
		attestation_path,
		root,
		daily_blog.experiment_attestation.ATTESTATION_ID_RE,
		"Prompt experiment attestation",
	)
	attestation, posts = daily_blog.experiment_attestation.load_review_posts(config, attestation_path)
	if not isinstance(attestation, daily_blog.experiment_attestation.ExperimentAttestation):
		raise RuntimeError("Prompt experiment attestation is invalid.")
	if attestation.path != pathlib.Path(attestation_path):
		raise RuntimeError("Prompt experiment attestation identity drifted during load.")
	return attestation, posts


#============================================
def _validated_contract_and_posts(
	attestation: daily_blog.experiment_attestation.ExperimentAttestation,
	posts: object,
) -> tuple[dict[str, object], dict[str, str]]:
	"""Validate the attestation-owned review contract and two complete sealed posts."""
	if not isinstance(attestation.report, dict):
		raise RuntimeError("Prompt experiment attestation report is invalid.")
	contract = attestation.report.get("review_contract")
	if not isinstance(contract, dict):
		raise RuntimeError("Prompt experiment review contract is invalid.")
	if (
		not isinstance(posts, dict)
		or set(posts) != {"busy", "quiet"}
		or any(not isinstance(post, str) for post in posts.values())
	):
		raise RuntimeError("Prompt experiment review posts are invalid.")
	validated_contract = daily_blog.experiment_review_contract.validate_review_contract(contract)
	return validated_contract, posts


#============================================
def _review_report(
	attestation: daily_blog.experiment_attestation.ExperimentAttestation,
	posts: dict[str, str],
	submissions: list[dict[str, object]],
) -> dict[str, object]:
	"""Build the complete non-publishing F4 result from revalidated evidence."""
	validated_contract, validated_posts = _validated_contract_and_posts(attestation, posts)
	# ASVS 2.1.1-2.1.3: the shared contract validates every reviewer-controlled value.
	if not isinstance(submissions, list):
		raise RuntimeError("Prompt experiment review submissions are invalid.")
	validated_submissions = []
	for entry in submissions:
		if (
			not isinstance(entry, dict)
			or not isinstance(entry.get("reviewer_id"), str)
			or not isinstance(entry.get("sha256"), str)
			or not isinstance(entry.get("submission"), dict)
		):
			raise RuntimeError("Prompt experiment review submissions are invalid.")
		submission = daily_blog.experiment_review_contract.validate_review_submission(
			entry["submission"], validated_contract, validated_posts,
		)
		if (
			entry["reviewer_id"] != submission["reviewer_id"]
			or entry["sha256"] != daily_blog.io_utils.hash_value(submission)
		):
			raise RuntimeError("Prompt experiment review submission identity is invalid.")
		validated_submissions.append(submission)
	# ASVS 11.4.3: aggregate only after each exact sealed post identity is revalidated.
	aggregate = daily_blog.experiment_review_contract.aggregate_independent_reviews(
		validated_submissions,
		validated_contract,
		validated_posts,
	)
	manifest = attestation.manifest
	if not isinstance(manifest, dict):
		raise RuntimeError("Prompt experiment attestation manifest is invalid.")
	attestation_id = manifest.get("attestation_id")
	report_sha256 = manifest.get("report_sha256")
	if (
		not isinstance(attestation_id, str)
		or not daily_blog.experiment_attestation.ATTESTATION_ID_RE.fullmatch(attestation_id)
		or not isinstance(report_sha256, str)
		or not re.fullmatch(r"[0-9a-f]{64}", report_sha256)
	):
		raise RuntimeError("Prompt experiment attestation identity is invalid.")
	report = {
		"schema_version": REVIEW_EVIDENCE_SCHEMA,
		"attestation": {
			"artifact": attestation.path.name,
			"attestation_id": attestation_id,
			"report_sha256": report_sha256,
		},
		"review_contract_sha256": daily_blog.io_utils.hash_value(validated_contract),
		"submissions": submissions,
		"post_sha256": {
			fixture: daily_blog.io_utils.sha256_text(post)
			for fixture, post in sorted(validated_posts.items())
		},
		"aggregate": aggregate,
		"non_publishing": True,
	}
	return report


#============================================
def _manifest(report_bytes: bytes, report: dict[str, object]) -> dict[str, object]:
	"""Build the content-addressed immutable manifest for one F4 review result."""
	identity = {
		"schema_version": REVIEW_EVIDENCE_SCHEMA,
		"attestation": report["attestation"],
		"review_contract_sha256": report["review_contract_sha256"],
		"submissions": report["submissions"],
		"post_sha256": report["post_sha256"],
		"aggregate": report["aggregate"],
		"report_sha256": daily_blog.io_utils.sha256_bytes(report_bytes),
		"non_publishing": True,
	}
	manifest = {
		**identity,
		"review_evidence_id": "prompt-experiment-review-evidence-"
		+ daily_blog.io_utils.hash_value(identity),
	}
	return manifest


#============================================
def _validate_report_and_manifest(
	manifest: dict[str, object],
	report: dict[str, object],
	report_bytes: bytes,
	name: str,
) -> None:
	"""Validate immutable evidence identity and prohibit publishing behavior."""
	manifest_keys = {
		"schema_version", "attestation", "review_contract_sha256", "submissions", "post_sha256",
		"aggregate", "report_sha256", "non_publishing", "review_evidence_id",
	}
	report_keys = {
		"schema_version", "attestation", "review_contract_sha256", "submissions", "post_sha256",
		"aggregate", "non_publishing",
	}
	# ASVS 2.2.2 and 2.2.3: reject undeclared fields instead of accepting ambiguous artifacts.
	if set(manifest) != manifest_keys or set(report) != report_keys:
		raise RuntimeError("Prompt experiment review evidence fields are invalid.")
	if (
		manifest["schema_version"] != REVIEW_EVIDENCE_SCHEMA
		or report["schema_version"] != REVIEW_EVIDENCE_SCHEMA
		or manifest["non_publishing"] is not True
		or report["non_publishing"] is not True
		or manifest["report_sha256"] != daily_blog.io_utils.sha256_bytes(report_bytes)
	):
		raise RuntimeError("Prompt experiment review evidence identity is invalid.")
	if {key: manifest[key] for key in report_keys} != report:
		raise RuntimeError("Prompt experiment review evidence manifest and report differ.")
	identity = {key: value for key, value in manifest.items() if key != "review_evidence_id"}
	expected = "prompt-experiment-review-evidence-" + daily_blog.io_utils.hash_value(identity)
	if name != expected or manifest["review_evidence_id"] != expected:
		raise RuntimeError("Prompt experiment review evidence identity is invalid.")


#============================================
def _install(
	config: daily_blog.config.DailyBlogConfig,
	manifest: dict[str, object],
	report: dict[str, object],
) -> pathlib.Path:
	"""Atomically install one descriptor-pinned immutable F4 review artifact."""
	name = manifest["review_evidence_id"]
	if not isinstance(name, str) or not REVIEW_EVIDENCE_ID_RE.fullmatch(name):
		raise RuntimeError("Prompt experiment review evidence ID is invalid.")
	root = _private_root(config)
	root_fd = daily_blog.private_artifacts.open_physical_directory(
		root,
		create=True,
		intermediate_mode=0o755,
		leaf_mode=0o700,
	)
	# ASVS 2.3.1: never stage beside an existing root that is not private and owner-controlled.
	daily_blog.private_artifacts.require_directory(root_fd, 0o077)
	stage_name = "." + name + "." + uuid.uuid4().hex + ".stage"
	try:
		stage_fd = daily_blog.private_artifacts.create_private_stage_at(root_fd, stage_name, 0o077)
		try:
			# ASVS 2.3.1 and 2.3.3: write a synced, private stage before one no-replace commit.
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
			daily_blog.private_artifacts.rename_directory_noreplace_at(root_fd, stage_name, name)
		except FileExistsError:
			daily_blog.private_artifacts.remove_known_stage(
				root_fd,
				stage_name,
				("manifest.json", "report.json"),
			)
			result = pathlib.Path(root) / name
			return result
		os.fsync(root_fd)
	finally:
		os.close(root_fd)
	result = pathlib.Path(root) / name
	return result


#============================================
def create_review_evidence(
	config: daily_blog.config.DailyBlogConfig,
	attestation_path: str,
	submission_paths: list[str],
) -> tuple[int, pathlib.Path]:
	"""Record one immutable F4 outcome without invoking routes or publishing artifacts."""
	attestation, posts = _attestation_reference(config, attestation_path)
	contract, validated_posts = _validated_contract_and_posts(attestation, posts)
	submissions = _load_submissions(submission_paths, contract, validated_posts)
	report = _review_report(attestation, validated_posts, submissions)
	manifest = _manifest(_json_bytes(report), report)
	path = _install(config, manifest, report)
	loaded = load_review_evidence(config, str(path))
	# ASVS 2.3.3: an existing content identity is usable only when source-backed bytes agree.
	if loaded.manifest != manifest or loaded.report != report:
		raise RuntimeError("Existing prompt experiment review evidence differs from this result.")
	code = 0 if report["aggregate"]["f4_accepted"] else 1
	return code, path


#============================================
def load_review_evidence(
	config: daily_blog.config.DailyBlogConfig,
	path_value: str,
) -> ReviewEvidence:
	"""Reopen every source and reject an F4 artifact whose evidence has drifted."""
	root = _private_root(config)
	name = _artifact_name(
		path_value,
		root,
		REVIEW_EVIDENCE_ID_RE,
		"Prompt experiment review evidence",
	)
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
			manifest_bytes = daily_blog.private_artifacts.read_regular_bytes_at(
				artifact_fd, "manifest.json", MAX_ARTIFACT_BYTES, 0o077,
			)
			report_bytes = daily_blog.private_artifacts.read_regular_bytes_at(
				artifact_fd, "report.json", MAX_ARTIFACT_BYTES, 0o077,
			)
		finally:
			os.close(artifact_fd)
	finally:
		os.close(root_fd)
	manifest = _read_json_bytes(manifest_bytes, "Prompt experiment review evidence")
	report = _read_json_bytes(report_bytes, "Prompt experiment review evidence")
	_validate_report_and_manifest(manifest, report, report_bytes, name)
	attestation_ref = report["attestation"]
	if not isinstance(attestation_ref, dict):
		raise RuntimeError("Prompt experiment review attestation reference is invalid.")
	attestation_name = attestation_ref.get("artifact")
	if not isinstance(attestation_name, str):
		raise RuntimeError("Prompt experiment review attestation reference is invalid.")
	attestation_path = os.path.join(
		os.path.abspath(
			os.path.join(
				config.output_root,
				config.output_owner,
				daily_blog.experiment_attestation.ATTESTATION_ROOT_NAME,
			)
		),
		attestation_name,
	)
	attestation, posts = _attestation_reference(config, attestation_path)
	expected = _review_report(attestation, posts, report["submissions"])
	if expected != report:
		raise RuntimeError("Prompt experiment review source evidence drifted.")
	return ReviewEvidence(pathlib.Path(path_value), manifest, report)

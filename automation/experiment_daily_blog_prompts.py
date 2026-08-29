#!/usr/bin/env python3
"""Run a sealed, non-publishing prompt-contract experiment for daily blogs.

This program deliberately has no importer, publisher, mirror, or shadow-evaluation
dependency.  It writes private experiment artifacts only.
"""

# Standard Library
import argparse
import dataclasses
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import uuid


#============================================
def _repository_root_from_git(start_path: str) -> pathlib.Path:
	"""Return the Git-owned repository root.

	Args:
		start_path: Existing script path from which Git discovers the repository.

	Returns:
		Absolute repository root reported by Git.
	"""
	start = os.path.abspath(start_path)
	if os.path.isfile(start):
		start = os.path.dirname(start)
	result = subprocess.run(
		["git", "-C", start, "rev-parse", "--show-toplevel"],
		check=False,
		text=True,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		timeout=60,
	)
	root = result.stdout.strip()
	if result.returncode or not os.path.isabs(root):
		raise RuntimeError("Experiment runner must run inside an absolute Git repository.")
	return pathlib.Path(root)


#============================================
REPO_ROOT = _repository_root_from_git(__file__)
PIPELINE_DIR = REPO_ROOT / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
	sys.path.insert(0, str(PIPELINE_DIR))

# local repo modules
import daily_blog.config  # type: ignore[import-untyped]
import daily_blog.contracts  # type: ignore[import-untyped]
import daily_blog.editorial  # type: ignore[import-untyped]
import daily_blog.evaluation  # type: ignore[import-untyped]
import daily_blog.experiment_capture_artifacts  # type: ignore[import-untyped]
import daily_blog.experiment_output  # type: ignore[import-untyped]
import daily_blog.fixture_hermes  # type: ignore[import-untyped]
import daily_blog.io_utils  # type: ignore[import-untyped]
import daily_blog.private_artifacts  # type: ignore[import-untyped]
import daily_blog.rubric_calibration  # type: ignore[import-untyped]
import daily_blog.routes  # type: ignore[import-untyped]
import daily_blog.schema  # type: ignore[import-untyped]


DEFAULT_ARMS = (
	*daily_blog.experiment_capture_artifacts.DEFAULT_ARMS,
)
EXPERIMENT_ID_RE = re.compile(r"^prompt-experiment-[a-z0-9][a-z0-9-]{0,95}$")
FIXTURE_SCHEMA = daily_blog.experiment_capture_artifacts.FIXTURE_SCHEMA
EXPERIMENT_ROOT_NAME = "daily_blog_experiments"
PRODUCTION_APPROVED_FIXTURES = daily_blog.experiment_capture_artifacts.APPROVED_FIXTURE_ROTATION


class FixtureSelectionError(RuntimeError):
	"""Raised when experiment inputs differ from the reviewed sealed fixture rotation."""


ExperimentFixture = daily_blog.experiment_capture_artifacts.ExperimentFixture


@dataclasses.dataclass(frozen=True)
class ExperimentExecutionContext:
	"""Fixed route, contract, output, and identity ownership for one experiment."""

	config: daily_blog.config.DailyBlogConfig
	runner: object
	output: "daily_blog.experiment_output.ExperimentOutputTransaction"
	experiment_id: str
	contracts: tuple[daily_blog.contracts.EditorialContract, ...]


@dataclasses.dataclass(frozen=True)
class ExperimentBatch:
	"""Immutable records assembled by one bounded experiment execution slice."""

	records: tuple[dict[str, object], ...]
	comparisons: tuple[dict[str, object], ...]
	errors: tuple[dict[str, object], ...]


#============================================
def _sha256(path: pathlib.Path) -> str:
	"""Return the SHA-256 digest for one artifact file."""
	return hashlib.sha256(path.read_bytes()).hexdigest()


#============================================
def load_fixture(path_value: str) -> ExperimentFixture:
	"""Load one captured packet/projection pair without contacting any service."""
	return daily_blog.experiment_capture_artifacts.load_fixture(path_value)


#============================================
def _validate_fixture_selection(fixtures: dict[str, ExperimentFixture]) -> None:
	"""Require the exact reviewed role, date, fixture, and declared roster identity tuple."""
	if set(fixtures) != set(PRODUCTION_APPROVED_FIXTURES):
		raise FixtureSelectionError("Prompt experiment fixture roles are invalid.")
	for role, expected in PRODUCTION_APPROVED_FIXTURES.items():
		fixture = fixtures[role]
		actual = (fixture.date, fixture.fixture_id, fixture.roster_id)
		if actual != expected:
			raise FixtureSelectionError(
				f"Prompt experiment {role} fixture does not match the approved sealed identity."
			)


#============================================
def _route_metadata(route: daily_blog.config.RoleRoute) -> dict[str, str]:
	"""Return the non-secret identity of one configured route."""
	return {
		"name": route.name,
		"executable": os.path.basename(route.command[0]),
		"command_sha256": daily_blog.io_utils.sha256_text("\x00".join(route.command)),
	}


#============================================
def _error_metadata(stage: str, error: BaseException, route: str = "") -> dict[str, str]:
	"""Keep diagnostics actionable without serializing route output or exception text."""
	value = {"stage": stage, "code": type(error).__name__}
	if route:
		value["route"] = route
	return value


#============================================
def _fixture_shim_metadata(
	provenance: daily_blog.routes.FixtureRouteProvenance,
) -> dict[str, str]:
	"""Return the non-secret fixture-shim identity sealed into a capture artifact."""
	return {
		"schema_version": provenance.schema_version,
		"executable_sha256": provenance.executable_sha256,
		"mapping_sha256": provenance.mapping_sha256,
		"response_map_id": provenance.response_map_id,
		"route_sha256": daily_blog.io_utils.sha256_text("\x00".join(provenance.allowed_route)),
	}


#============================================
def preflight_routes(
	config: daily_blog.config.DailyBlogConfig,
	verify_executables: bool = True,
) -> list[dict[str, str]]:
	"""Verify route structure and executable availability without executing routes."""
	routes = list(config.author_routes) + [config.referee_route]
	if len(config.author_routes) != 2:
		raise RuntimeError("Prompt experiment requires exactly two author routes.")
	if (
		len(routes) != 3
		or len({route.name for route in routes}) != 3
		or any(
			not isinstance(route.name, str)
			or not route.name
			or not isinstance(route.command, tuple)
			or not route.command
			or not isinstance(route.command[0], str)
			or not route.command[0]
			for route in routes
		)
	):
		raise RuntimeError("Prompt experiment routes must have three unique executable names.")
	metadata = [_route_metadata(route) for route in routes]
	for route in routes:
		if verify_executables and shutil.which(route.command[0]) is None:
			raise RuntimeError(f"Configured route executable is unavailable: {route.name}")
	return metadata


#============================================
def _json_bytes(value: object) -> bytes:
	"""Return one deterministic human-readable private JSON artifact."""
	return json.dumps(value, sort_keys=True, indent=2).encode("utf-8") + b"\n"


#============================================
def _open_output_transaction(
	output_root: str,
	experiment_id: str,
) -> daily_blog.experiment_output.ExperimentOutputTransaction:
	"""Open one private root and exclusive hidden stage through retained descriptors."""
	if not EXPERIMENT_ID_RE.fullmatch(experiment_id):
		raise RuntimeError("Experiment ID must use the strict prompt-experiment slug format.")
	transaction = daily_blog.experiment_output.open_output_transaction(
		output_root,
		experiment_id,
	)
	return transaction


#============================================
def _configured_output_root(config: daily_blog.config.DailyBlogConfig) -> str:
	"""Return the sole private experiment namespace owned by configuration."""
	root = os.path.abspath(
		os.path.join(config.output_root, config.output_owner, EXPERIMENT_ROOT_NAME)
	)
	return root


#============================================
def _candidate_record(
	candidate: daily_blog.editorial.CandidateResult,
	directory_fd: int,
	label: str,
) -> dict[str, object]:
	"""Write one candidate artifact and return redacted analysis metadata.

	Args:
		candidate: Candidate whose exact post bytes are kept in the private artifact.
		directory_fd: Held private arm directory receiving the candidate Markdown file.
		label: Stable artifact stem within the private arm directory.

	Returns:
		Persistable candidate metadata without raw route exception text.
	"""
	name = f"{label}.md"
	daily_blog.private_artifacts.write_regular_bytes_at(
		directory_fd,
		name,
		candidate.post.encode("utf-8"),
	)
	try:
		profile = daily_blog.evaluation.article_profile(candidate.post)
	except RuntimeError as error:
		# Invalid raw candidates are retained for analysis, even when profile parsing cannot run.
		profile = {"diagnostic": _error_metadata("article_profile", error)}
	return {
		"route": candidate.private_route,
		"valid": candidate.valid,
		"issues": list(candidate.issues),
		"post_hash": candidate.post_hash,
		"path": name,
		"article_profile": profile,
	}


#============================================
def _select_for_analysis(
	candidates: list[daily_blog.editorial.CandidateResult],
	packet: daily_blog.schema.EvidencePacket,
	projection: daily_blog.schema.EditorialProjection,
	config: daily_blog.config.DailyBlogConfig,
	runner: object,
	snapshot: daily_blog.editorial.PromptContractSnapshot,
) -> tuple[daily_blog.editorial.CandidateResult, dict[str, object]]:
	"""Select one candidate after the shared validity gate has passed."""
	if not candidates or not all(item.valid for item in candidates):
		raise RuntimeError("Experiment selection requires only valid candidates.")
	valid = candidates
	try:
		decision = daily_blog.editorial.select_candidate(
			packet, projection, "experiment", candidates, config, runner, snapshot=snapshot
		)
		selected = next(item for item in candidates if item.post == decision.post)
		return selected, {
			"winner": decision.winner,
			"publication_invalid": False,
			"reason": decision.reason,
			"confidence": decision.confidence,
		}
	except daily_blog.editorial.EditorialBlockedError as error:
		return valid[0], {
			"winner": "RAW",
			"publication_invalid": not valid[0].valid,
			"diagnostic": _error_metadata("within_arm_referee", error),
		}


#============================================
def _compare(
	left: daily_blog.editorial.CandidateResult,
	right: daily_blog.editorial.CandidateResult,
	projection: daily_blog.schema.EditorialProjection,
	config: daily_blog.config.DailyBlogConfig,
	runner: object,
	snapshot: daily_blog.editorial.PromptContractSnapshot,
	reverse: bool,
) -> dict[str, object]:
	"""Run a counterbalanced anonymous referee comparison without publishing.

	Args:
		left: Candidate assigned to canonical comparison side A.
		right: Candidate assigned to canonical comparison side B.
		projection: Evidence projection supplied to the referee.
		config: Complete route configuration for the private comparison.
		runner: Injected or command-backed route runner.
		snapshot: Immutable referee prompt contract snapshot.
		reverse: Whether prompt ordering reverses the canonical A/B sides.

	Returns:
		Persistable referee verdict or a redacted expected-failure diagnostic.
	"""
	ordered = [right, left] if reverse else [left, right]
	mapping = {"A": 0, "B": 1}
	try:
		verdict = daily_blog.editorial._referee_verdict(
			projection, ordered, mapping, config, runner, snapshot=snapshot
		)
		winner = verdict["winner"]
		canonical = winner
		if reverse and winner in {"A", "B"}:
			canonical = "B" if winner == "A" else "A"
		return {
			"order": "BA" if reverse else "AB",
			"verdict": canonical,
			"parsed": True,
			"details": verdict,
		}
	except daily_blog.editorial.EditorialBlockedError:
		return {
			"order": "BA" if reverse else "AB",
			"verdict": "ERROR",
			"parsed": False,
			"details": None,
		}


#============================================
def _record_candidates_valid(record: dict[str, object]) -> bool:
	"""Read persisted candidate validity only after checking artifact record shapes."""
	candidates = record.get("candidate_records")
	if not isinstance(candidates, list) or not candidates:
		return False
	result = all(
		isinstance(candidate, dict) and candidate.get("valid") is True
		for candidate in candidates
	)
	return result


#============================================

def _run_arm_generation(
	fixture_name: str,
	fixture: ExperimentFixture,
	repetition: int,
	contract: daily_blog.contracts.EditorialContract,
	config: daily_blog.config.DailyBlogConfig,
	runner: object,
	transaction: daily_blog.experiment_output.ExperimentOutputTransaction,
	experiment_id: str,
) -> tuple[dict[str, object], daily_blog.editorial.CandidateResult | None, dict[str, str] | None]:
	"""Generate, validate, and record one arm without hiding programming defects.

	Args:
		fixture_name: Stable label for the sealed fixture.
		fixture: Packet and projection used by this arm.
		repetition: Zero-based repetition number.
		contract: Registered editorial contract being evaluated.
		config: Complete daily-blog configuration.
		runner: Injected or command-backed route runner.
		transaction: Held private output transaction for candidate artifacts.
		experiment_id: Immutable experiment identifier.

	Returns:
		Persistable record, selected candidate when available, and expected failure metadata.
	"""
	snapshot = daily_blog.editorial.load_prompt_contract_snapshot(contract)
	# The experiment identity is unique. Stable child identities let a sealed fixture shim
	# precompute the exact stdin prompts without weakening the fresh-process route boundary.
	run_id = f"experiment-{experiment_id}-{fixture_name}-{contract.name}-{repetition}"
	started = time.monotonic()
	try:
		raw = daily_blog.editorial.generate_candidates(
			fixture.packet, fixture.projection, run_id, config, runner, snapshot=snapshot
		)
		candidates = daily_blog.editorial.validate_candidates(
			raw, fixture.packet, fixture.projection, run_id, snapshot=snapshot
		)
		if not candidates or not all(item.valid for item in candidates):
			winner = None
			selection: dict[str, object] = {
				"winner": "UNAVAILABLE",
				"publication_invalid": True,
				"reason": "Candidate validation failed; referee skipped.",
			}
			execution_error = {"stage": "candidate_validation", "code": "InvalidCandidate"}
		else:
			winner, selection = _select_for_analysis(
				candidates, fixture.packet, fixture.projection, config, runner, snapshot
			)
			diagnostic = selection.get("diagnostic")
			execution_error = diagnostic if isinstance(diagnostic, dict) else {}
	except daily_blog.editorial.EditorialBlockedError as error:
		candidates = []
		winner = None
		selection = {
			"winner": "UNAVAILABLE",
			"publication_invalid": True,
			"reason": "Author generation failed; referee skipped.",
		}
		execution_error = _error_metadata("author_generation", error)
	entry_name = f"{fixture_name}-{contract.name}-{repetition}"
	os.mkdir(entry_name, 0o700, dir_fd=transaction.stage_fd)
	entry_fd = daily_blog.private_artifacts.open_directory_at(
		transaction.stage_fd,
		entry_name,
	)
	try:
		daily_blog.private_artifacts.require_directory(entry_fd, 0o077)
		candidate_records = [
			_candidate_record(item, entry_fd, f"candidate-{index}")
			for index, item in enumerate(candidates)
		]
		selected_record = (
			_candidate_record(winner, entry_fd, "selected")
			if winner is not None
			else None
		)
		os.fsync(entry_fd)
	finally:
		os.close(entry_fd)
	if winner is not None:
		scorecard = daily_blog.rubric_calibration.score_maker_post(
			winner.post,
			config,
			runner,
			"prompt_experiment",
		)
		if scorecard.get("status") != "scored":
			diagnostic = scorecard.get("diagnostic")
			execution_error = (
				diagnostic
				if isinstance(diagnostic, dict)
				else {"stage": "prompt_experiment_score", "code": "InvalidScorecard"}
			)
	else:
		scorecard = {"status": "unavailable"}
	record = {
		"fixture": fixture_name,
		"fixture_hashes": fixture.hashes,
		"fixture_identity": {
			"fixture_id": fixture.fixture_id,
			"roster_id": fixture.roster_id,
			"packet_id": fixture.packet.packet_id,
			"projection_id": fixture.projection.projection_id,
		},
		"arm": contract.name,
		"repetition": repetition,
		"run_id": run_id,
		"prompt_identity": daily_blog.editorial.prompt_contract_identity(snapshot=snapshot),
		"snapshot_digest": snapshot.integrity_sha256,
		"candidate_records": candidate_records,
		"selection": selection,
		"selected": selected_record,
		"scorecard": scorecard,
		"diagnostic": execution_error,
		"seconds": round(time.monotonic() - started, 3),
	}
	return record, winner, execution_error or None


#============================================
def _run_pairwise_comparisons(
	selected: dict[str, tuple[daily_blog.editorial.CandidateResult, dict[str, object]]],
	fixture_name: str,
	fixture: ExperimentFixture,
	repetition: int,
	config: daily_blog.config.DailyBlogConfig,
	runner: object,
) -> list[dict[str, object]]:
	"""Compare selected arms using counterbalanced anonymous referee order.

	Args:
		selected: Valid selected candidate keyed by registered arm name.
		fixture_name: Stable label for the sealed fixture.
		fixture: Projection context for anonymous comparison.
		repetition: Zero-based repetition number.
		config: Complete daily-blog configuration.
		runner: Injected or command-backed route runner.

	Returns:
		Pairwise referee records for this fixture repetition.
	"""
	comparison_snapshot = daily_blog.editorial.load_prompt_contract_snapshot(
		daily_blog.contracts.resolve_maker_experiment_contract("v4-instruction-only")
	)
	comparisons = []
	for pair in daily_blog.experiment_capture_artifacts.COMPARISON_PAIRS:
		left_arm, right_arm = pair.split(":")
		left = selected.get(left_arm)
		right = selected.get(right_arm)
		available = left is not None and right is not None
		for reverse in (False, True):
			comparison = (
				_compare(
					left[0], right[0], fixture.projection, config, runner,
					comparison_snapshot, reverse,
				)
				if available
				else {
					"order": "BA" if reverse else "AB",
					"verdict": "ERROR",
					"parsed": False,
					"details": None,
				}
			)
			comparisons.append({
				"fixture": fixture_name, "repetition": repetition, "pair": pair,
				"selected_candidates": [
					left[1] if left else None,
					right[1] if right else None,
				],
				**comparison,
			})
	return comparisons


#============================================
def _run_repetition(
	context: ExperimentExecutionContext,
	fixture_name: str,
	fixture: ExperimentFixture,
	repetition: int,
) -> ExperimentBatch:
	"""Run every registered arm and comparison for one fixture repetition.

	Args:
		context: Fixed route, contract, identity, and private-stage ownership.
		fixture_name: Approved busy or quiet role.
		fixture: Sealed evidence and projection for this role.
		repetition: Zero-based sample number.

	Returns:
		Complete generated records, comparisons, and expected diagnostics for this slice.
	"""
	records = []
	errors = []
	selected: dict[str, tuple[daily_blog.editorial.CandidateResult, dict[str, object]]] = {}
	for contract in context.contracts:
		record, winner, execution_error = _run_arm_generation(
			fixture_name,
			fixture,
			repetition,
			contract,
			context.config,
			context.runner,
			context.output,
			context.experiment_id,
		)
		if execution_error is not None:
			errors.append(
				{
					"fixture": fixture_name,
					"arm": contract.name,
					"repetition": repetition,
					"diagnostic": execution_error,
				}
			)
		if winner is not None:
			selected[contract.name] = (winner, record["selected"])
		records.append(record)
	comparisons = _run_pairwise_comparisons(
		selected,
		fixture_name,
		fixture,
		repetition,
		context.config,
		context.runner,
	)
	return ExperimentBatch(tuple(records), tuple(comparisons), tuple(errors))


#============================================
def _run_all_repetitions(
	context: ExperimentExecutionContext,
	fixtures: dict[str, ExperimentFixture],
	repetitions: int,
) -> ExperimentBatch:
	"""Run the documented fixture-then-repetition sequence without skipping a slice."""
	records = []
	comparisons = []
	errors = []
	# ASVS 2.3.1: every approved fixture and repetition executes in one fixed order.
	for fixture_name, fixture in fixtures.items():
		for repetition in range(repetitions):
			batch = _run_repetition(context, fixture_name, fixture, repetition)
			records.extend(batch.records)
			comparisons.extend(batch.comparisons)
			errors.extend(batch.errors)
	return ExperimentBatch(tuple(records), tuple(comparisons), tuple(errors))


#============================================
def _remove_uncommitted_stage(
	transaction: daily_blog.experiment_output.ExperimentOutputTransaction,
	fixtures: dict[str, ExperimentFixture],
	arms: tuple[str, ...],
	repetitions: int,
) -> None:
	"""Remove only the declared files and arm directories from an uncommitted stage."""
	artifact_names = ("candidate-0.md", "candidate-1.md", "selected.md")
	children = tuple(
		(
			f"{fixture}-{arm}-{repetition}",
			artifact_names,
		)
		for fixture in fixtures
		for repetition in range(repetitions)
		for arm in arms
	)
	daily_blog.private_artifacts.remove_known_tree(
		transaction.root_fd,
		transaction.stage_name,
		("manifest.json", "report.json"),
		children,
	)


#============================================
def _commit_experiment_report(
	transaction: daily_blog.experiment_output.ExperimentOutputTransaction,
	experiment_id: str,
	fixtures: dict[str, ExperimentFixture],
	arms: tuple[str, ...],
	repetitions: int,
	route_metadata: list[dict[str, str]],
	records: list[dict[str, object]],
	comparisons: list[dict[str, object]],
	errors: list[dict[str, object]],
	execution_mode: str,
	fixture_shim: dict[str, str] | None,
) -> tuple[int, pathlib.Path]:
	"""Write the sealed report and atomically commit its private directory.

	Args:
		transaction: Held private root and complete staging directory.
		experiment_id: Immutable experiment identifier.
		fixtures: Captured fixtures included in the experiment.
		arms: Registered contract arms in evaluation order.
		repetitions: Number of repetitions per fixture and arm.
		route_metadata: Non-secret configured route identities.
		records: Per-arm generation records.
		comparisons: Counterbalanced referee comparison records.
		errors: Expected route or editorial-block diagnostics.

	Returns:
		Process status and committed output path.
	"""
	all_candidates_valid = all(
		len(record["candidate_records"]) == 2 and _record_candidates_valid(record)
		for record in records
	)
	complete = len(records) == len(fixtures) * repetitions * len(arms)
	expected_comparisons = (
		len(fixtures)
		* repetitions
		* len(daily_blog.experiment_capture_artifacts.COMPARISON_PAIRS)
		* 2
	)
	parsed = len(comparisons) == expected_comparisons and all(item["parsed"] for item in comparisons)
	selected = all(
		record["selected"] is not None
		and "diagnostic" not in record["selection"]
		for record in records
	)
	scored = all(record["scorecard"].get("status") == "scored" for record in records)
	status = (
		"complete"
		if complete and all_candidates_valid and selected and scored and parsed and not errors
		else "complete_with_failures"
	)
	report = {
		"schema_version": daily_blog.experiment_capture_artifacts.CAPTURE_SCHEMA,
		"experiment_id": experiment_id,
		"routes": route_metadata,
		"records": records,
		"comparisons": comparisons,
		"errors": errors,
		"capture_status": status,
		"activation_status": "pending_calibration_attestation",
		"non_publishing": True,
		"contains_full_prompts": False,
		"execution_mode": execution_mode,
		"external_route_used": (
			daily_blog.experiment_capture_artifacts.EXECUTION_PROVENANCE[execution_mode]
		),
		"fixture_shim": fixture_shim,
	}
	report_bytes = _json_bytes(report)
	daily_blog.private_artifacts.write_regular_bytes_at(
		transaction.stage_fd,
		"report.json",
		report_bytes,
	)
	manifest = {
		"schema_version": daily_blog.experiment_capture_artifacts.CAPTURE_SCHEMA,
		"experiment_id": experiment_id,
		"fixtures": {
			name: {
				"label": value.label,
				"date": value.date,
				"fixture_id": value.fixture_id,
				"roster_id": value.roster_id,
				"packet_id": value.packet.packet_id,
				"projection_id": value.projection.projection_id,
				"hashes": value.hashes,
			}
			for name, value in fixtures.items()
		},
		"arms": list(arms),
		"repetitions": repetitions,
		"report_sha256": daily_blog.io_utils.sha256_bytes(report_bytes),
		"activation_status": "pending_calibration_attestation",
		"non_publishing": True,
		"execution_mode": execution_mode,
		"external_route_used": (
			daily_blog.experiment_capture_artifacts.EXECUTION_PROVENANCE[execution_mode]
		),
		"fixture_shim": fixture_shim,
	}
	manifest["capture_id"] = daily_blog.io_utils.hash_value(manifest)
	daily_blog.private_artifacts.write_regular_bytes_at(
		transaction.stage_fd,
		"manifest.json",
		_json_bytes(manifest),
	)
	os.fsync(transaction.stage_fd)
	try:
		daily_blog.private_artifacts.rename_directory_noreplace_at(
			transaction.root_fd,
			transaction.stage_name,
			transaction.output_name,
		)
	except FileExistsError as error:
		raise RuntimeError("Experiment output target already exists.") from error
	os.fsync(transaction.root_fd)
	code = 0 if status == "complete" else 1
	return code, transaction.output_path


#============================================
def run_experiment(
	config: daily_blog.config.DailyBlogConfig,
	busy_fixture: str,
	quiet_fixture: str,
	repetitions: int = 3,
	arms: tuple[str, ...] = DEFAULT_ARMS,
	runner: object | None = None,
	experiment_id: str | None = None,
	execution_mode: str = daily_blog.experiment_capture_artifacts.EXTERNAL_HERMES,
	fixture_installation: daily_blog.fixture_hermes.FixtureHermesInstallation | None = None,
) -> tuple[int, pathlib.Path]:
	"""Run the full sealed generated-prose experiment.

	Args:
		config: Author, referee, prompt-limit, repository, and private output settings.
		busy_fixture: Absolute path to the approved busy capture.
		quiet_fixture: Absolute path to the approved quiet capture.
		repetitions: Required samples for every fixture and registered arm.
		arms: Exact registered arm sequence; caller-selected subsets are rejected.
		runner: Optional isolated route runner for offline verification.
		experiment_id: Optional validated immutable output identity.
		execution_mode: Owned execution provenance for this sealed capture.
		fixture_installation: Descriptor-verifiable no-egress shim installation for fixture mode.

	Returns:
		Process status and committed private experiment directory.

	Raises:
		RuntimeError: Any input, route, artifact, or transaction violates its contract.
	"""
	if (
		type(repetitions) is not int
		or not 1
		<= repetitions
		<= daily_blog.rubric_calibration.MAX_REPETITIONS
		or tuple(arms) != DEFAULT_ARMS
	):
		raise RuntimeError("Experiment repetitions and registered arms must be explicit and valid.")
	if (
		not isinstance(execution_mode, str)
		or execution_mode not in daily_blog.experiment_capture_artifacts.EXECUTION_PROVENANCE
	):
		raise RuntimeError("Prompt experiment execution provenance is invalid.")
	if execution_mode == daily_blog.experiment_capture_artifacts.FIXTURE_HERMES_SHIM:
		routes = (*config.author_routes, config.referee_route)
		if (
			not isinstance(runner, daily_blog.routes.CommandRouteRunner)
			or fixture_installation is None
		):
			raise RuntimeError("Fixture Hermes captures require an attested shim installation.")
		fixture_provenance = daily_blog.fixture_hermes.validate_fixture_installation(
			fixture_installation
		)
		if (
			runner.fixture_provenance != fixture_provenance
			or runner.path_override != fixture_installation.path
			or runner.fixture_validator is None
		):
			raise RuntimeError("Fixture Hermes runner does not match its attested installation.")
		if any(route.command != daily_blog.config.HERMES_EDITORIAL_ROUTE for route in routes):
			raise RuntimeError("Fixture Hermes captures require the sealed Hermes editorial route.")
		fixture_shim = _fixture_shim_metadata(fixture_provenance)
	else:
		if fixture_installation is not None:
			raise RuntimeError("External Hermes captures cannot declare a fixture installation.")
		fixture_shim = None
	fixtures: dict[str, ExperimentFixture] = {
		"busy": load_fixture(busy_fixture),
		"quiet": load_fixture(quiet_fixture),
	}
	_validate_fixture_selection(fixtures)
	contracts = tuple(
		daily_blog.contracts.resolve_maker_experiment_contract(name)
		for name in arms
	)
	route_metadata = (
		preflight_routes(config, verify_executables=runner is None)
	)
	experiment_id = experiment_id or f"prompt-experiment-{uuid.uuid4().hex}"
	transaction = _open_output_transaction(
		_configured_output_root(config),
		experiment_id,
	)
	runner = runner or daily_blog.routes.CommandRouteRunner()
	context = ExperimentExecutionContext(
		config,
		runner,
		transaction,
		experiment_id,
		contracts,
	)
	try:
		batch = _run_all_repetitions(context, fixtures, repetitions)
		# ASVS 2.3.3: commit only after every required generation and verdict is assembled.
		return _commit_experiment_report(
			transaction,
			experiment_id,
			fixtures,
			arms,
			repetitions,
			route_metadata,
			list(batch.records),
			list(batch.comparisons),
			list(batch.errors),
			execution_mode,
			fixture_shim,
		)
	finally:
		os.close(transaction.stage_fd)
		try:
			_remove_uncommitted_stage(transaction, fixtures, arms, repetitions)
		finally:
			os.close(transaction.root_fd)


#============================================
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
	"""Parse the sealed experiment command-line arguments."""
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--busy-fixture", required=True)
	parser.add_argument("--quiet-fixture", required=True)
	parser.add_argument("--settings-path", default="settings.yaml")
	parser.add_argument("--repetitions", type=int, default=3)
	parser.add_argument("--arm", action="append", dest="arms")
	return parser.parse_args(argv)


#============================================
def main(argv: list[str] | None = None, runner: object | None = None) -> int:
	"""Load configuration and run one private prompt-contract experiment."""
	args = parse_args(argv)
	try:
		config = daily_blog.config.load_config(args.settings_path)
		code, _ = run_experiment(
			config=config,
			busy_fixture=args.busy_fixture,
			quiet_fixture=args.quiet_fixture,
			repetitions=args.repetitions,
			arms=tuple(args.arms or DEFAULT_ARMS),
			runner=runner,
		)
		return code
	except FixtureSelectionError:
		print(
			"Prompt experiment blocked: fixture selection does not match the reviewed sealed rotation.",
			file=sys.stderr,
		)
		return 2
	except RuntimeError:
		print(
			"Prompt experiment blocked; inspect the private artifact or configuration.",
			file=sys.stderr,
		)
		return 2


if __name__ == "__main__":
	raise SystemExit(main())

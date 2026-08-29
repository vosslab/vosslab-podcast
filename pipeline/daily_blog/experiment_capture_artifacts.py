"""Load and verify immutable non-publishing prompt-experiment captures."""

# Standard Library
import dataclasses
import hashlib
import json
import os
import pathlib
import re

# local repo modules
import daily_blog.contracts
import daily_blog.config
import daily_blog.editorial
import daily_blog.experiment_fixture_contract
import daily_blog.fixture_hermes
import daily_blog.io_utils
import daily_blog.private_artifacts
import daily_blog.projection
import daily_blog.rubric_calibration
import daily_blog.schema


FIXTURE_SCHEMA = daily_blog.experiment_fixture_contract.FIXTURE_SCHEMA_VERSION
CAPTURE_SCHEMA = "vosslab.daily-blog.prompt-experiment-capture.v5"
MAX_ARTIFACT_BYTES = 4_000_000
EXPERIMENT_ID_RE = re.compile(r"^prompt-experiment-[a-z0-9][a-z0-9-]{0,95}$")
DEFAULT_ARMS = daily_blog.contracts.PROMPT_EXPERIMENT_ARMS
COMPARISON_PAIRS = daily_blog.contracts.PROMPT_EXPERIMENT_COMPARISON_PAIRS
EXTERNAL_HERMES = "external_hermes"
FIXTURE_HERMES_SHIM = "fixture_hermes_shim"
EXECUTION_PROVENANCE = {
	EXTERNAL_HERMES: True,
	FIXTURE_HERMES_SHIM: False,
}
APPROVED_FIXTURE_ROTATION = {
	"quiet": ("2026-08-23", "4adcb80db0cdde222fbc6a7a53ec008d1198d0cc03f9cecc16c12ddbca24522e", "0f79bcfea4d3fb783258df4a37effef5996b6fdb9736ff6944fd17051570b8a1"),
	"busy": ("2026-08-26", "04fd7a045538662e5c6b48ad79e08dd608de1b5a10c1c8857c7b12042bad41da", "0f79bcfea4d3fb783258df4a37effef5996b6fdb9736ff6944fd17051570b8a1"),
}


@dataclasses.dataclass(frozen=True)
class ExperimentFixture:
	"""Validated sealed fixture admitted to the reviewed experiment rotation."""

	label: str
	packet: daily_blog.schema.EvidencePacket
	projection: daily_blog.schema.EditorialProjection
	date: str
	fixture_id: str
	roster_id: str
	hashes: dict[str, str]


@dataclasses.dataclass(frozen=True)
class ExperimentCapture:
	"""Descriptor-verified completed capture and its non-activation status."""

	path: pathlib.Path
	manifest: dict[str, object]
	report: dict[str, object]


#============================================
def _reject_json_constant(_value: str) -> None:
	"""Reject non-standard non-finite JSON values in sealed artifacts."""
	raise ValueError("Non-finite JSON constant.")


#============================================
def _strict_json_loads(contents: bytes) -> object:
	"""Parse sealed JSON without duplicate names or non-finite constants."""
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
		parse_constant=_reject_json_constant,
	)


#============================================
def _read_json_bytes(contents: bytes, label: str) -> dict[str, object]:
	"""Decode one bounded JSON object from a descriptor-pinned artifact."""
	try:
		value = _strict_json_loads(contents)
	except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
		raise RuntimeError(f"Experiment {label} is invalid.") from error
	if not isinstance(value, dict):
		raise RuntimeError(f"Experiment {label} must be a JSON object.")
	return value


#============================================
def _read_json_at(directory_fd: int, name: str, label: str) -> dict[str, object]:
	"""Read one bounded, private JSON artifact through a held directory descriptor."""
	contents = daily_blog.private_artifacts.read_regular_bytes_at(
		directory_fd, name, MAX_ARTIFACT_BYTES, 0o077
	)
	return _read_json_bytes(contents, label)


#============================================
def _fixture_declarations(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
	"""Validate the exact v2 fixture declaration structure before reading payloads."""
	# ASVS 1.5.2 and 2.2.1: the consumer uses the writer-owned positive schema.
	identity = daily_blog.experiment_fixture_contract.validate_fixture_manifest(manifest)
	return identity["files"]


#============================================
def _fixture_file(
	directory_fd: int,
	name: str,
	declarations: dict[str, dict[str, object]],
) -> bytes:
	"""Read one declared fixture payload and verify its byte identity."""
	entry = declarations.get(name)
	if not isinstance(entry, dict):
		raise RuntimeError(f"Fixture manifest declaration is invalid: {name}")
	contents = daily_blog.private_artifacts.read_regular_bytes_at(
		directory_fd, name, MAX_ARTIFACT_BYTES, 0o077
	)
	if entry.get("sha256") != hashlib.sha256(contents).hexdigest() or entry.get("bytes") != len(contents):
		raise RuntimeError(f"Fixture bytes or hash do not match declared metadata: {name}")
	return contents


#============================================
def load_fixture(path_value: str) -> ExperimentFixture:
	"""Load a v2 fixture through descriptors and validate every declared identity."""
	if not os.path.isabs(path_value) or ".." in pathlib.PurePath(path_value).parts:
		raise RuntimeError("Experiment paths must be absolute and direct.")
	root_fd = daily_blog.private_artifacts.open_physical_directory(
		path_value, create=False, intermediate_mode=0o755, leaf_mode=0o700
	)
	try:
		daily_blog.private_artifacts.require_directory(root_fd, 0o077)
		manifest_bytes = daily_blog.private_artifacts.read_regular_bytes_at(
			root_fd, "manifest.json", MAX_ARTIFACT_BYTES, 0o077
		)
		manifest = _read_json_bytes(manifest_bytes, "fixture manifest")
		declarations = _fixture_declarations(manifest)
		evidence = _fixture_file(root_fd, "evidence.json", declarations)
		projection_bytes = _fixture_file(root_fd, "editorial_projection.json", declarations)
		packet = daily_blog.schema.EvidencePacket.from_dict(_read_json_bytes(evidence, "evidence"))
		projection = daily_blog.schema.EditorialProjection.from_dict(
			_read_json_bytes(projection_bytes, "editorial projection")
		)
	finally:
		os.close(root_fd)
	if not packet.complete:
		raise RuntimeError("Fixture evidence packet is incomplete.")
	if packet.packet_id != projection.packet_id or packet.report_date != projection.report_date:
		raise RuntimeError("Fixture packet and editorial projection are incoherent.")
	daily_blog.projection._validate_exact_slices(packet, projection)
	context = projection.render_context()
	if len(context) > 60000:
		raise RuntimeError("Fixture projection exceeds the 60000 character experiment limit.")
	roster = manifest["repository_roster_snapshot"]
	packet_mirrors = [mirror.to_dict() for mirror in packet.mirrors]
	packet_roster_ids = {mirror.get("roster_id") for mirror in packet_mirrors}
	if packet_mirrors and packet_roster_ids != {roster["roster_id"]}:
		raise RuntimeError("Fixture packet does not belong to its declared repository roster.")
	if (
		manifest["report_date"] != packet.report_date
		or manifest["evidence_packet_id"] != packet.packet_id
		or manifest["projection_id"] != projection.projection_id
		or manifest["evidence_count"] != len(packet.items)
		or manifest["repository_count"] != len(projection.repositories)
		or manifest["projection_rendered_chars"] != len(context)
		or manifest["mirrors"]
		!= daily_blog.experiment_fixture_contract.fixture_mirror_identities(packet_mirrors)
	):
		raise RuntimeError("Fixture manifest does not match its packet and projection identities.")
	fixture_id = manifest["fixture_id"]
	if not isinstance(fixture_id, str) or pathlib.Path(path_value).name != f"{packet.report_date}--{fixture_id}":
		raise RuntimeError("Fixture directory name does not match its content identity.")
	return ExperimentFixture(
		pathlib.Path(path_value).name, packet, projection, packet.report_date, fixture_id,
		roster["roster_id"], {
			"evidence.json": hashlib.sha256(evidence).hexdigest(),
			"editorial_projection.json": hashlib.sha256(projection_bytes).hexdigest(),
			"manifest": hashlib.sha256(manifest_bytes).hexdigest(),
		},
	)


#============================================
def _capture_identity(manifest: dict[str, object]) -> dict[str, object]:
	"""Return the fields that content-address one completed prompt capture."""
	return {key: value for key, value in manifest.items() if key != "capture_id"}


#============================================
def _valid_diagnostic(value: object) -> bool:
	"""Return whether one persisted diagnostic uses only redacted stable fields."""
	return (
		isinstance(value, dict)
		and set(value) in ({"stage", "code"}, {"stage", "code", "route"})
		and all(isinstance(item, str) and item for item in value.values())
	)


#============================================
def _valid_scorecard(value: object, post: str | None) -> bool:
	"""Return whether one private scorecard is exact and grounded in its selected post."""
	if not isinstance(value, dict) or not isinstance(value.get("status"), str):
		return False
	if value["status"] == "unavailable":
		return set(value) == {"status"}
	if value["status"] == "error":
		return set(value) == {"status", "diagnostic"} and _valid_diagnostic(value["diagnostic"])
	criteria = tuple(
		daily_blog.rubric_calibration.RubricCriterion(*item)
		for item in daily_blog.rubric_calibration.CALIBRATION_CONTRACT.expected_criteria
	)
	return (
		post is not None
		and set(value) == {
			"status", "scores", "passages", "reasons", "weighted_score", "overall_reason",
		}
		and daily_blog.rubric_calibration.scored_result_is_grounded(value, criteria, post)
	)


#============================================
def _valid_article_profile(value: object) -> bool:
	"""Return whether sealed article-profile telemetry has its bounded exact shape."""
	if isinstance(value, dict) and set(value) == {"diagnostic"}:
		return _valid_diagnostic(value["diagnostic"])
	keys = {
		"title", "h2_headings", "narrative_h2_count", "narrative_words", "opening_words",
		"first_person", "has_project_coverage", "narrative_prose_block_count",
		"mean_narrative_paragraph_words", "standalone_short_single_sentence_paragraph_count",
		"sentence_length_variance", "sentences_under_eight_visible_words", "question_count",
		"inline_markdown_link_count", "words_per_inline_markdown_link",
		"uncited_narrative_prose_block_count",
		"narrative_prose_blocks_without_concrete_surface_signal",
		"first_person_sentence_count", "distinct_first_person_action_surfaces",
		"distinct_first_person_action_surface_count",
		"first_person_action_surface_diversity_ratio",
	}
	integer_keys = {
		"narrative_h2_count", "narrative_words", "opening_words", "narrative_prose_block_count",
		"standalone_short_single_sentence_paragraph_count", "sentences_under_eight_visible_words",
		"question_count", "inline_markdown_link_count", "uncited_narrative_prose_block_count",
		"narrative_prose_blocks_without_concrete_surface_signal", "first_person_sentence_count",
		"distinct_first_person_action_surface_count",
	}
	float_keys = {
		"mean_narrative_paragraph_words", "sentence_length_variance",
		"first_person_action_surface_diversity_ratio",
	}
	return (
		isinstance(value, dict)
		and set(value) == keys
		and isinstance(value["title"], str)
		and isinstance(value["h2_headings"], list)
		and all(isinstance(item, str) for item in value["h2_headings"])
		and type(value["first_person"]) is bool
		and type(value["has_project_coverage"]) is bool
		and all(type(value[key]) is int and value[key] >= 0 for key in integer_keys)
		and all(type(value[key]) in {int, float} and value[key] >= 0 for key in float_keys)
		and (
			value["words_per_inline_markdown_link"] is None
			or (
				type(value["words_per_inline_markdown_link"]) in {int, float}
				and value["words_per_inline_markdown_link"] >= 0
			)
		)
		and isinstance(value["distinct_first_person_action_surfaces"], list)
		and all(isinstance(item, str) for item in value["distinct_first_person_action_surfaces"])
		and value["distinct_first_person_action_surface_count"]
		== len(value["distinct_first_person_action_surfaces"])
	)


#============================================
def _valid_candidate(
	value: object,
	expected_path: str,
	allowed_routes: set[str],
) -> bool:
	"""Return whether one persisted CandidateResult has its exact sealed record shape."""
	return (
		isinstance(value, dict)
		and set(value) == {"route", "valid", "issues", "post_hash", "path", "article_profile"}
		and isinstance(value["route"], str)
		and value["route"] in allowed_routes
		and type(value["valid"]) is bool
		and isinstance(value["issues"], list)
		and all(isinstance(item, str) and item for item in value["issues"])
		and isinstance(value["post_hash"], str)
		and re.fullmatch(r"[0-9a-f]{64}", value["post_hash"]) is not None
		and value["path"] == expected_path
		and _valid_article_profile(value["article_profile"])
	)


#============================================
def _valid_selection(value: object, selected: object) -> bool:
	"""Return whether selection metadata proves the selected artifact was obtained."""
	if selected is None:
		return (
			isinstance(value, dict)
			and set(value) == {"winner", "publication_invalid", "reason"}
			and value["winner"] == "UNAVAILABLE"
			and value["publication_invalid"] is True
			and isinstance(value["reason"], str)
			and value["reason"]
		)
	if not isinstance(value, dict) or value.get("publication_invalid") is not False:
		return False
	if set(value) == {"winner", "publication_invalid", "reason", "confidence"}:
		return (
			isinstance(value["winner"], str) and value["winner"]
			and isinstance(value["reason"], str) and value["reason"]
			and type(value["confidence"]) in {int, float}
		)
	return (
		set(value) == {"winner", "publication_invalid", "diagnostic"}
		and value["winner"] == "RAW"
		and _valid_diagnostic(value["diagnostic"])
	)


#============================================
def load_capture(path_value: str) -> ExperimentCapture:
	"""Load a completed capture and verify its report, candidates, and execution matrix."""
	if not os.path.isabs(path_value) or ".." in pathlib.PurePath(path_value).parts:
		raise RuntimeError("Experiment paths must be absolute and direct.")
	root_fd = daily_blog.private_artifacts.open_physical_directory(
		path_value, create=False, intermediate_mode=0o755, leaf_mode=0o700
	)
	try:
		daily_blog.private_artifacts.require_directory(root_fd, 0o077)
		manifest = _read_json_at(root_fd, "manifest.json", "capture manifest")
		report_bytes = daily_blog.private_artifacts.read_regular_bytes_at(
			root_fd, "report.json", MAX_ARTIFACT_BYTES, 0o077
		)
		report = _read_json_bytes(report_bytes, "capture report")
		_validate_capture(root_fd, pathlib.Path(path_value).name, manifest, report, report_bytes)
	finally:
		os.close(root_fd)
	return ExperimentCapture(pathlib.Path(path_value), manifest, report)


#============================================
def _sealed_route_sha256() -> str:
	"""Return the public digest of the exact Hermes argv required by editorial routes."""
	return daily_blog.io_utils.sha256_text("\x00".join(daily_blog.config.HERMES_EDITORIAL_ROUTE))


#============================================
def _valid_fixture_shim(value: object) -> bool:
	"""Return whether persisted no-egress provenance binds the private shim identity."""
	return (
		isinstance(value, dict)
		and set(value) == {
			"schema_version", "executable_sha256", "mapping_sha256", "response_map_id",
			"route_sha256",
		}
		and value["schema_version"] == daily_blog.fixture_hermes.FIXTURE_SCHEMA_VERSION
		and all(
			isinstance(value[field], str) and re.fullmatch(r"[0-9a-f]{64}", value[field])
			is not None
			for field in (
				"executable_sha256", "mapping_sha256", "response_map_id", "route_sha256",
			)
		)
		and value["route_sha256"] == _sealed_route_sha256()
	)


#============================================
def _validate_capture(
	root_fd: int,
	directory_name: str,
	manifest: dict[str, object],
	report: dict[str, object],
	report_bytes: bytes,
) -> None:
	"""Validate capture identity, declared matrix, and every stored candidate hash."""
	manifest_keys = {
		"schema_version", "experiment_id", "fixtures", "arms", "repetitions", "report_sha256",
		"activation_status", "non_publishing", "execution_mode", "external_route_used",
		"fixture_shim", "capture_id",
	}
	report_keys = {
		"schema_version", "experiment_id", "routes", "records", "comparisons", "errors",
		"capture_status", "activation_status", "non_publishing", "contains_full_prompts",
		"execution_mode", "external_route_used", "fixture_shim",
	}
	if set(manifest) != manifest_keys or set(report) != report_keys:
		raise RuntimeError("Prompt experiment capture fields are invalid.")
	if manifest.get("schema_version") != CAPTURE_SCHEMA or report.get("schema_version") != CAPTURE_SCHEMA:
		raise RuntimeError("Prompt experiment capture schema is invalid.")
	if manifest.get("experiment_id") != report.get("experiment_id") or not isinstance(manifest["experiment_id"], str) or not EXPERIMENT_ID_RE.fullmatch(manifest["experiment_id"]):
		raise RuntimeError("Prompt experiment capture experiment identity is invalid.")
	if manifest.get("non_publishing") is not True or report.get("non_publishing") is not True or report.get("contains_full_prompts") is not False:
		raise RuntimeError("Prompt experiment capture must remain non-publishing and redacted.")
	# ASVS 1.5.2 and 2.2.1: capture provenance is an owned enum, not a caller label.
	execution_mode = manifest.get("execution_mode")
	if (
		not isinstance(execution_mode, str)
		or execution_mode not in EXECUTION_PROVENANCE
		or report.get("execution_mode") != execution_mode
		or manifest.get("external_route_used")
		is not EXECUTION_PROVENANCE[execution_mode]
		or report.get("external_route_used")
		is not EXECUTION_PROVENANCE[execution_mode]
		or (
			execution_mode == FIXTURE_HERMES_SHIM
			and not _valid_fixture_shim(manifest.get("fixture_shim"))
		)
		or (
			execution_mode == EXTERNAL_HERMES
			and manifest.get("fixture_shim") is not None
		)
		or report.get("fixture_shim") != manifest.get("fixture_shim")
	):
		raise RuntimeError("Prompt experiment capture execution provenance is invalid.")
	if manifest.get("activation_status") != "pending_calibration_attestation" or report.get("activation_status") != "pending_calibration_attestation":
		raise RuntimeError("Prompt experiment capture activation status is invalid.")
	if report.get("capture_status") not in {"complete", "complete_with_failures"}:
		raise RuntimeError("Prompt experiment capture status is invalid.")
	if manifest.get("report_sha256") != daily_blog.io_utils.sha256_bytes(report_bytes):
		raise RuntimeError("Prompt experiment capture report digest is invalid.")
	capture_id = manifest.get("capture_id")
	if not isinstance(capture_id, str) or capture_id != daily_blog.io_utils.hash_value(_capture_identity(manifest)):
		raise RuntimeError("Prompt experiment capture manifest identity is invalid.")
	if directory_name != manifest.get("experiment_id") or not isinstance(directory_name, str):
		raise RuntimeError("Prompt experiment capture directory identity is invalid.")
	fixtures = manifest["fixtures"]
	arms = manifest["arms"]
	repetitions = manifest["repetitions"]
	records = report["records"]
	comparisons = report["comparisons"]
	errors = report["errors"]
	routes = report["routes"]
	if (
		not isinstance(fixtures, dict) or set(fixtures) != set(APPROVED_FIXTURE_ROTATION)
		or arms != list(DEFAULT_ARMS)
		or type(repetitions) is not int
		or not 1
		<= repetitions
		<= daily_blog.rubric_calibration.MAX_REPETITIONS
		or not isinstance(records, list) or not isinstance(comparisons, list)
		or not isinstance(errors, list) or not isinstance(routes, list)
	):
		raise RuntimeError("Prompt experiment capture matrix is invalid.")
	for name, fixture in fixtures.items():
		if not isinstance(fixture, dict) or set(fixture) != {"label", "date", "fixture_id", "roster_id", "packet_id", "projection_id", "hashes"}:
			raise RuntimeError("Prompt experiment capture fixture declaration is invalid.")
		if (fixture["date"], fixture["fixture_id"], fixture["roster_id"]) != APPROVED_FIXTURE_ROTATION[name]:
			raise RuntimeError("Prompt experiment capture fixture rotation is invalid.")
		if fixture["label"] != f"{fixture['date']}--{fixture['fixture_id']}" or not isinstance(fixture["hashes"], dict) or set(fixture["hashes"]) != {"evidence.json", "editorial_projection.json", "manifest"}:
			raise RuntimeError("Prompt experiment capture fixture identity is invalid.")
	if (
		len(routes) != 3
		or any(
			not isinstance(route, dict)
			or set(route) != {"name", "executable", "command_sha256"}
			or not all(isinstance(value, str) and value for value in route.values())
			for route in routes
		)
		or len({route["name"] for route in routes}) != 3
	):
		raise RuntimeError("Prompt experiment capture routes are invalid.")
	expected_route_hash = _sealed_route_sha256()
	if any(
		route["executable"] != "hermes" or route["command_sha256"] != expected_route_hash
		for route in routes
	):
		raise RuntimeError("Prompt experiment capture route identity is invalid.")
	author_routes = {route["name"] for route in routes[:2]}
	expected = {(fixture, arm, repetition) for fixture in fixtures for arm in arms for repetition in range(repetitions)}
	actual = set()
	failed_record_diagnostics: dict[tuple[object, object, object], dict[str, str]] = {}
	for record in records:
		record_keys = {"fixture", "fixture_hashes", "fixture_identity", "arm", "repetition", "run_id", "prompt_identity", "snapshot_digest", "candidate_records", "selection", "selected", "scorecard", "diagnostic", "seconds"}
		if not isinstance(record, dict) or set(record) != record_keys:
			raise RuntimeError("Prompt experiment capture record is invalid.")
		key = (record.get("fixture"), record.get("arm"), record.get("repetition"))
		if key in actual:
			raise RuntimeError("Prompt experiment capture contains duplicate records.")
		actual.add(key)
		if record.get("fixture_hashes") != fixtures.get(key[0], {}).get("hashes"):
			raise RuntimeError("Prompt experiment capture fixture identity is invalid.")
		fixture = fixtures.get(key[0])
		if not isinstance(fixture, dict) or record.get("fixture_identity") != {
			"fixture_id": fixture.get("fixture_id"),
			"roster_id": fixture.get("roster_id"),
			"packet_id": fixture.get("packet_id"),
			"projection_id": fixture.get("projection_id"),
		}:
			raise RuntimeError("Prompt experiment capture fixture identity is invalid.")
		try:
			snapshot = daily_blog.editorial.load_prompt_contract_snapshot(
				daily_blog.contracts.resolve_maker_experiment_contract(key[1])
			)
			expected_prompt_identity = daily_blog.editorial.prompt_contract_identity(snapshot=snapshot)
		except (KeyError, RuntimeError) as error:
			raise RuntimeError("Prompt experiment capture contract snapshot is invalid.") from error
		if record.get("prompt_identity") != expected_prompt_identity or record.get("snapshot_digest") != snapshot.integrity_sha256:
			raise RuntimeError("Prompt experiment capture contract snapshot is invalid.")
		candidates = record.get("candidate_records")
		if not isinstance(candidates, list) or len(candidates) not in {0, 2}:
			raise RuntimeError("Prompt experiment candidate declaration is invalid.")
		selected = record.get("selected")
		if selected is not None and not isinstance(selected, dict):
			raise RuntimeError("Prompt experiment selected candidate declaration is invalid.")
		if (
			not _valid_selection(record["selection"], selected)
			or not isinstance(record["diagnostic"], dict)
			or record["diagnostic"] and not _valid_diagnostic(record["diagnostic"])
			or type(record["seconds"]) not in {int, float}
			or record["seconds"] < 0
		):
			raise RuntimeError("Prompt experiment capture analysis declarations are invalid.")
		if any(
			not _valid_candidate(candidate, f"candidate-{index}.md", author_routes)
			for index, candidate in enumerate(candidates)
		):
			raise RuntimeError("Prompt experiment candidate declaration is invalid.")
		if len(candidates) == 2 and {candidate["route"] for candidate in candidates} != author_routes:
			raise RuntimeError("Prompt experiment candidate routes are invalid.")
		if selected is not None:
			if not _valid_candidate(selected, "selected.md", author_routes):
				raise RuntimeError("Prompt experiment selected candidate declaration is invalid.")
			if not any(
				candidate["valid"] is True
				and all(candidate[name] == selected[name] for name in ("route", "valid", "issues", "post_hash", "article_profile"))
				for candidate in candidates
			):
				raise RuntimeError("Prompt experiment selected candidate is not derived from a valid candidate.")
		if selected is None and record["scorecard"].get("status") != "unavailable":
			raise RuntimeError("Prompt experiment unavailable selection has a scorecard.")
		if selected is not None and record["scorecard"].get("status") == "unavailable":
			raise RuntimeError("Prompt experiment selected candidate has no scorecard.")
		if record["diagnostic"]:
			failed_record_diagnostics[key] = record["diagnostic"]
		declared_candidates = candidates + ([] if selected is None else [selected])
		selected_post = None
		for candidate in declared_candidates:
			if not isinstance(candidate, dict):
				raise RuntimeError("Prompt experiment candidate declaration is invalid.")
			arm_fd = daily_blog.private_artifacts.open_directory_at(
				root_fd, f"{key[0]}-{key[1]}-{key[2]}"
			)
			try:
				contents = daily_blog.private_artifacts.read_regular_bytes_at(
					arm_fd, candidate["path"], MAX_ARTIFACT_BYTES, 0o077
				)
			finally:
				os.close(arm_fd)
			post = contents.decode("utf-8")
			if candidate.get("post_hash") != daily_blog.io_utils.sha256_text(post):
				raise RuntimeError("Prompt experiment candidate hash is invalid.")
			if candidate.get("path") == "selected.md":
				selected_post = post
		if not _valid_scorecard(record["scorecard"], selected_post):
			raise RuntimeError("Prompt experiment scorecard is invalid or ungrounded.")
	if actual != expected or len(records) != len(expected):
		raise RuntimeError("Prompt experiment capture matrix is incomplete.")
	_expected_comparisons = {
		(fixture, pair, repetition, order)
		for fixture in fixtures
		for pair in COMPARISON_PAIRS
		for repetition in range(repetitions)
		for order in ("AB", "BA")
	}
	actual_comparisons = set()
	selected_by_key = {(record["fixture"], record["arm"], record["repetition"]): record["selected"] for record in records}
	for comparison in comparisons:
		if not isinstance(comparison, dict) or set(comparison) != {"fixture", "repetition", "pair", "order", "verdict", "parsed", "details", "selected_candidates"}:
			raise RuntimeError("Prompt experiment comparison declaration is invalid.")
		key = (
			comparison["fixture"], comparison["pair"], comparison["repetition"],
			comparison["order"],
		)
		if key in actual_comparisons:
			raise RuntimeError("Prompt experiment capture contains duplicate comparisons.")
		actual_comparisons.add(key)
		if key not in _expected_comparisons or type(comparison["parsed"]) is not bool:
			raise RuntimeError("Prompt experiment comparison declaration is invalid.")
		left, right = comparison["pair"].split(":")
		expected_selected = [selected_by_key[(key[0], arm, key[2])] for arm in (left, right)]
		if comparison["selected_candidates"] != expected_selected:
			raise RuntimeError("Prompt experiment comparison candidates are invalid.")
		if comparison["parsed"]:
			if comparison["verdict"] not in {"A", "B", "NONE"} or not isinstance(comparison["details"], dict):
				raise RuntimeError("Prompt experiment parsed comparison is invalid.")
			positional_winner = comparison["details"].get("winner")
			if positional_winner not in {"A", "B", "NONE"}:
				raise RuntimeError("Prompt experiment positional verdict is invalid.")
			expected_verdict = positional_winner
			if key[3] == "BA" and positional_winner in {"A", "B"}:
				expected_verdict = "B" if positional_winner == "A" else "A"
			if comparison["verdict"] != expected_verdict:
				raise RuntimeError("Prompt experiment canonical verdict is invalid.")
		elif comparison["verdict"] != "ERROR" or comparison["details"] is not None:
			raise RuntimeError("Prompt experiment failed comparison is invalid.")
	if actual_comparisons != _expected_comparisons or len(comparisons) != len(_expected_comparisons):
		raise RuntimeError("Prompt experiment comparison matrix is incomplete.")
	error_diagnostics: dict[tuple[object, object, object], dict[str, str]] = {}
	for error in errors:
		if not isinstance(error, dict) or set(error) != {"fixture", "arm", "repetition", "diagnostic"} or not _valid_diagnostic(error["diagnostic"]):
			raise RuntimeError("Prompt experiment capture errors are invalid.")
		key = (error["fixture"], error["arm"], error["repetition"])
		if key not in expected or key in error_diagnostics:
			raise RuntimeError("Prompt experiment capture errors are invalid.")
		error_diagnostics[key] = error["diagnostic"]
	if error_diagnostics != failed_record_diagnostics:
		raise RuntimeError("Prompt experiment capture errors do not match record diagnostics.")
	all_candidates_complete = all(
		len(record["candidate_records"]) == 2
		and all(candidate["valid"] is True for candidate in record["candidate_records"])
		for record in records
	)
	all_selected_complete = all(
		record["selected"] is not None
		and _valid_selection(record["selection"], record["selected"])
		and "diagnostic" not in record["selection"]
		for record in records
	)
	all_scorecards_scored = all(record["scorecard"].get("status") == "scored" for record in records)
	all_comparisons_parsed = all(comparison["parsed"] for comparison in comparisons)
	complete = (
		all_candidates_complete
		and all_selected_complete
		and all_scorecards_scored
		and all_comparisons_parsed
		and not failed_record_diagnostics
	)
	if report["capture_status"] == "complete" and not complete:
		raise RuntimeError("Prompt experiment complete capture is incomplete.")
	if report["capture_status"] == "complete_with_failures" and complete:
		raise RuntimeError("Prompt experiment failure status is incoherent.")

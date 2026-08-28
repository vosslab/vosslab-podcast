"""Pure contract tests for daily-blog evidence and run schemas."""

# Standard Library
import json
import pathlib
import unittest.mock

# PIP3 modules
import pytest

# local repo modules
import daily_blog.schema
import daily_blog.locks
import daily_blog.evidence
import daily_blog.run_state
import daily_blog.orchestrator


#============================================
def test_extracts_every_exact_date_section_until_any_next_h2() -> None:
	"""Matching changelog entries retain full text and respect level-two boundaries."""
	changelog = (
		"## 2026-08-23\n\n- first account\n\n"
		+ "## Release notes\n\nSeparate section.\n\n"
		+ "## 2026-08-23 continued\n\n- second account\n\n"
		+ "## 2026-08-22\n\n- older\n"
	)

	result = daily_blog.evidence.extract_dated_sections(changelog, "2026-08-23")

	assert "- first account" in result
	assert "Separate section" not in result


#============================================
def test_evidence_packet_orders_authority_independently_from_input() -> None:
	"""Typed authority controls evidence order before any prompt rendering."""
	commit = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/repo", "a" * 40, "", "", "locator", "git show"
	)
	changelog = daily_blog.schema.EvidenceItem.create(
		"dated_changelog",
		"vosslab/repo",
		"a" * 40,
		"docs/CHANGELOG.md",
		"b" * 40,
		"## 2026-08-23\n\n- completed work\n",
		"git show",
	)

	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [commit, changelog]
	)

	assert packet.items[0].kind == "dated_changelog"
	assert packet.items[-1].kind == "commit_metadata"


#============================================
def test_evidence_packet_identity_inputs_are_immutable_after_creation() -> None:
	"""Caller dictionaries cannot mutate content after packet identity is computed."""
	limits = {"per_item_chars": 100}
	mirror = {"repository": "vosslab/repo", "object_available": True}
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23",
		"America/Chicago",
		True,
		limits,
		[mirror],
		[],
		[],
	)
	original = packet.to_dict()

	limits["per_item_chars"] = 1
	mirror["repository"] = "changed/repo"

	assert packet.to_dict() == original
	with pytest.raises(TypeError):
		packet.collection_limits["per_item_chars"] = 2
	with pytest.raises(TypeError):
		packet.mirrors[0]["repository"] = "changed/again"


#============================================
def test_run_record_rejects_completed_state_with_pending_phases() -> None:
	"""A terminal success record cannot serialize incomplete phase state."""
	record = daily_blog.schema.RunRecord.create("run-one", "2026-08-23")
	record.state = "completed"
	record.evidence_packet = {"packet_id": "packet"}
	record.publication_bundle = {"bundle_id": "bundle"}

	with pytest.raises(RuntimeError, match="unfinished phase"):
		record.to_dict()


#============================================
def test_phase_cache_reuses_json_by_exact_input_hash(tmp_path: pathlib.Path) -> None:
	"""Matching phase inputs resolve to the same cached artifact."""
	cache = daily_blog.locks.PhaseCache(str(tmp_path / "cache"))
	identity = "a" * 64
	value = {"result": "complete"}

	cache.store_json("evidence_assembly", identity, "evidence.json", value)
	loaded = cache.load_json("evidence_assembly", identity, "evidence.json")
	other = cache.load_json("evidence_assembly", "b" * 64, "evidence.json")

	assert loaded == value
	assert other is None


#============================================
def test_run_record_round_trip_preserves_legal_phase_order() -> None:
	"""Typed serialization round-trips an active record without schema drift."""
	record = daily_blog.schema.RunRecord.create("run-two", "2026-08-23")
	value = record.to_dict()

	restored = daily_blog.schema.RunRecord.from_dict(value)

	assert restored.to_dict() == value


#============================================
def test_failed_run_record_serializes_original_phase_failure() -> None:
	"""A failed phase becomes a valid terminal record instead of masking its error."""
	record = daily_blog.schema.RunRecord.create("run-failed", "2026-08-23")
	record.start_phase("mirror_refresh", "a" * 64)
	record.fail_phase("mirror_refresh", "RuntimeError", "network unavailable")

	value = record.to_dict()

	assert (
		value["state"], value["current_phase"], value["failure"]["phase"]
	) == ("failed", "", "mirror_refresh")


#============================================
def test_evidence_packet_rejects_string_completeness_state() -> None:
	"""Typed packet loading rejects truthy strings at the schema boundary."""
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/repo", "a" * 40, "", "", "locator", "git show"
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item]
	).to_dict()
	packet["complete"] = "false"

	with pytest.raises(RuntimeError, match="Boolean"):
		daily_blog.schema.EvidencePacket.from_dict(packet)


#============================================
def test_run_record_rejects_out_of_order_phase_start() -> None:
	"""Typed phase ownership cannot skip an incomplete prerequisite."""
	record = daily_blog.schema.RunRecord.create("run-sequence", "2026-08-23")

	with pytest.raises(RuntimeError, match="prerequisites"):
		record.start_phase("evidence_assembly", "a" * 64)


#============================================
def test_run_store_persists_safe_structured_phase_event(
	tmp_path: pathlib.Path,
	capsys: pytest.CaptureFixture,
) -> None:
	"""The durable file and stdout receive the same scheduler-safe event."""
	store = daily_blog.run_state.RunStore(str(tmp_path), "vosslab", "2026-08-23", "run-log")

	store.append_event(
		"daily_publication.phase_failed",
		{"phase": "mirror_refresh", "error_class": "RuntimeError"},
	)

	event_path = tmp_path / "vosslab" / "daily_blog_runs" / "2026-08-23" / "run-log" / "events.jsonl"
	with open(event_path, "r", encoding="utf-8") as handle:
		event = json.loads(handle.read())
	stdout_event = json.loads(capsys.readouterr().out)
	assert event["event"] == "daily_publication.phase_failed"
	assert (event["run_id"], event["phase"], event["error_class"]) == (
		"run-log",
		"mirror_refresh",
		"RuntimeError",
	)
	assert stdout_event == event


#============================================
def test_run_store_file_sink_failure_is_nonfatal(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A failed secondary event file cannot overturn authoritative publication state."""
	store = daily_blog.run_state.RunStore(str(tmp_path), "vosslab", "2026-08-23", "file-fail")
	monkeypatch.setattr(
		"builtins.open",
		unittest.mock.Mock(side_effect=OSError("event-file-sentinel")),
	)

	store.append_event("daily_publication.phase_started", {"phase": "mirror_refresh"})


#============================================
def test_run_store_stdout_sink_failure_is_nonfatal(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A broken journal stream cannot overturn authoritative publication state."""
	store = daily_blog.run_state.RunStore(str(tmp_path), "vosslab", "2026-08-23", "stdout-fail")
	monkeypatch.setattr(
		"builtins.print",
		unittest.mock.Mock(side_effect=BrokenPipeError("stdout-sentinel")),
	)

	store.append_event("daily_publication.phase_started", {"phase": "mirror_refresh"})
	with open(store.event_path, "r", encoding="utf-8") as handle:
		event = json.loads(handle.read())
	assert event["phase"] == "mirror_refresh"


#============================================
def test_site_import_receipt_requires_known_status_and_identity() -> None:
	"""A malformed publisher receipt cannot complete the external-import phase."""
	with pytest.raises(RuntimeError, match="status"):
		daily_blog.schema.validate_site_import_result({}, "bundle-one", "2026-08-23")
	with pytest.raises(RuntimeError, match="bundle identity"):
		daily_blog.schema.validate_site_import_result(
			{"status": "imported", "bundle_id": "bundle-two", "report_date": "2026-08-23"},
			"bundle-one",
			"2026-08-23",
		)


#============================================
def test_failure_boundary_keeps_raw_message_out_of_lifecycle_events(
	tmp_path: pathlib.Path,
	capsys: pytest.CaptureFixture,
) -> None:
	"""Private state retains the error while durable and stdout events expose only its class."""
	record = daily_blog.schema.RunRecord.create("run-failure", "2026-08-23")
	record.start_phase("mirror_refresh", "a" * 64)
	store = daily_blog.run_state.RunStore(
		str(tmp_path),
		"vosslab",
		"2026-08-23",
		"run-failure",
	)
	orchestrator = object.__new__(daily_blog.orchestrator.DailyPublicationOrchestrator)
	orchestrator.record = record
	orchestrator.store = store

	orchestrator._fail_current(RuntimeError("private-failure-sentinel"))

	with open(store.record_path, "r", encoding="utf-8") as handle:
		run_state_text = handle.read()
	with open(store.event_path, "r", encoding="utf-8") as handle:
		event_text = handle.read()
	stdout_text = capsys.readouterr().out
	assert "private-failure-sentinel" in run_state_text
	assert "private-failure-sentinel" not in event_text + stdout_text

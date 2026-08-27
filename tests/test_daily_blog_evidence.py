"""Pure contract tests for daily-blog evidence and run schemas."""

# Standard Library
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.schema
import daily_blog.locks
import daily_blog.evidence


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

"""Durable bounds, summaries, and safe expiry for daily-publication runs."""

# Standard Library
import json
import os
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.io_utils
import daily_blog.observability
import daily_blog.replication
import daily_blog.run_contracts
import daily_blog.run_state


FIXED_TIME = "2026-08-29T12:00:00Z"
REPORT_DATE = "2026-08-29"
OWNER = "vosslab"
POST_ID = "artifact-0123456789abcdef01234567"


#============================================
def _fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Keep durable test records independent of wall-clock time."""
	monkeypatch.setattr(daily_blog.io_utils, "utc_now", lambda: FIXED_TIME)


#============================================
def _completed_record(
	run_id: str, created_at: str = FIXED_TIME,
) -> daily_blog.run_contracts.RunRecord:
	"""Return a small terminal record with the publication facts summaries require."""
	record = daily_blog.run_contracts.RunRecord.create(run_id, REPORT_DATE, created_at)
	for phase in daily_blog.run_contracts.LEGAL_PHASES:
		record.start_phase(phase, "a" * 64)
		record.complete_phase(phase, "b" * 64)
	record.add_editorial_step(
		daily_blog.replication.StepReliability(
			"stage6.4", "succeeded", 1, 1, 0, 0, 0, 0, POST_ID, (),
		),
		daily_blog.run_contracts.EstablishIncumbent(POST_ID),
	)
	record.repository_roster = {
		"roster_id": "c" * 64,
		"snapshot_path": f"{OWNER}/daily_blog_repository_rosters/" + "c" * 64,
	}
	record.evidence_packet = {"packet_id": "packet"}
	record.publication_bundle = {
		"path": f"{OWNER}/daily_blog/{REPORT_DATE}/publication",
		"page_verification": {"rendered_page_sha256": "d" * 64},
	}
	record.complete()
	return record


#============================================
def _failed_record(run_id: str, created_at: str = FIXED_TIME) -> daily_blog.run_contracts.RunRecord:
	"""Return one fixed-time classified terminal failure."""
	record = daily_blog.run_contracts.RunRecord.create(run_id, REPORT_DATE, created_at)
	record.start_phase("repository_discovery", "a" * 64)
	record.fail_phase("repository_discovery", "route_unavailable")
	return record


#============================================
def _store(tmp_path: pathlib.Path, run_id: str) -> daily_blog.run_state.RunStore:
	"""Create one store under the stable test date."""
	return daily_blog.run_state.RunStore(str(tmp_path), OWNER, REPORT_DATE, run_id)


#============================================
def test_terminal_summaries_are_idempotent_and_bind_terminal_facts(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Repeated finalization preserves one exact current terminal receipt."""
	_fixed_clock(monkeypatch)
	success_store = _store(tmp_path, "run-success")
	success = _completed_record("run-success")
	success_store.save(success)
	success_store.finalize_summary(success)
	first_receipt = pathlib.Path(success_store.summary_path).read_bytes()
	success_store.finalize_summary(success)
	second_receipt = pathlib.Path(success_store.summary_path).read_bytes()
	receipt = daily_blog.observability.parse_terminal_summary_line(
		second_receipt.decode("utf-8").strip(),
	)

	assert second_receipt == first_receipt
	assert receipt["verified_page_sha256"] == "d" * 64


#============================================
def test_terminal_summary_preserves_safe_namespaced_step(
	tmp_path: pathlib.Path,
) -> None:
	"""A typed terminal fault retains its bounded logical step observation."""
	store = _store(tmp_path, "run-namespaced-fault")
	record = _failed_record("run-namespaced-fault")
	record.add_editorial_step(
		daily_blog.replication.StepReliability(
			"repair/task/worker",
			"succeeded", 1, 1, 0, 0, 0, 0, "", (),
		),
		daily_blog.run_contracts.ObserveIncumbent(),
	)
	store.save(record)
	store.finalize_summary(record)
	receipt = daily_blog.observability.parse_terminal_summary_line(
		pathlib.Path(store.summary_path).read_text(encoding="utf-8").strip(),
	)

	assert receipt["terminal_fault_category"] == "route_unavailable"
	assert receipt["editorial_steps"][0]["step"] == "repair/task/worker"


#============================================
def test_rerun_replaces_the_report_date_owned_artifact_set(tmp_path: pathlib.Path) -> None:
	"""Execution identities remain records rather than durable directory selectors."""
	first = _store(tmp_path, "execution-one")
	first.write_artifact("first_only.json", {"execution": "one"})
	first.append_event("daily_publication.run_started", {"state": "running"})
	publication = pathlib.Path(first.date_dir) / "publication"
	publication.mkdir()
	(publication / "bundle.json").write_text("{}\n", encoding="utf-8")

	second = _store(tmp_path, "execution-two")
	second.append_event("daily_publication.run_started", {"state": "running"})

	assert first.run_dir == second.run_dir == first.date_dir
	assert not (pathlib.Path(second.run_dir) / "first_only.json").exists()
	assert (publication / "bundle.json").read_text(encoding="utf-8") == "{}\n"
	event = json.loads(pathlib.Path(second.event_path).read_text(encoding="utf-8"))
	assert event["run_id"] == "execution-two"


#============================================
def test_finalize_summary_rejects_a_newline_free_oversized_existing_receipt(
	tmp_path: pathlib.Path,
) -> None:
	"""Terminal-summary replay bounds corrupted durable journal input."""
	store = _store(tmp_path, "run-summary-bound")
	record = _completed_record("run-summary-bound")
	store.save(record)
	pathlib.Path(store.summary_path).write_bytes(
		b"x" * (daily_blog.observability.MAX_SUMMARY_LINE_BYTES + 2),
	)
	with pytest.raises(RuntimeError):
		store.finalize_summary(record)


#============================================
def test_observability_rejects_diagnostic_data_outside_its_bounded_contract(
	tmp_path: pathlib.Path,
) -> None:
	"""Nested, secret-like, and unclassified diagnostics cannot enter receipts."""
	summary = {
		"schema_version": daily_blog.observability.TERMINAL_SUMMARY_SCHEMA,
		"summary_id": daily_blog.io_utils.sha256_text("run-safe:" + "b" * 64), "terminal_record_sha256": "b" * 64,
		"report_date": REPORT_DATE, "run_id": "run-safe", "created_at": FIXED_TIME,
		"completed_at": FIXED_TIME, "state": "failed", "outcome": "failed",
		"best_artifact_id": "", "failure_phase": "repository_discovery",
		"terminal_fault_category": "unknown_fault", "operational_failure_kind": "",
		"terminal_fault_subtype": "", "terminal_fault_owner": "",
		"publication_completed": False, "verified_page_sha256": "",
		"incumbent_replacement_count": 0, "editorial_steps": [],
	}
	sink = daily_blog.observability.RunEventSink(REPORT_DATE, "run-safe")
	with pytest.raises(RuntimeError):
		daily_blog.observability.validate_terminal_summary(summary)
	summary["terminal_fault_category"] = "route_unavailable"
	summary["failure_phase"] = "unknown_retired_phase"
	with pytest.raises(RuntimeError):
		daily_blog.observability.validate_terminal_summary(summary)
	summary["failure_phase"] = "repository_discovery"
	summary["summary_id"] = "a" * 64
	with pytest.raises(RuntimeError):
		daily_blog.observability.validate_terminal_summary(summary)
	with pytest.raises(RuntimeError):
		sink.validate_details(
			"daily_publication.phase_started", {"phase": {"secret": "/private/token"}},
			frozenset({"phase"}),
		)


#============================================
def test_event_sink_accepts_namespaced_editorial_steps_without_path_data(
	tmp_path: pathlib.Path,
) -> None:
	"""A logical substep may be namespaced, but event facts never accept a path."""
	sink = daily_blog.observability.RunEventSink(REPORT_DATE, "run-safe")
	sink.validate_details(
		"daily_publication.editorial_step_completed", {"step": "repair/task/worker"},
		frozenset({"step"}),
	)
	with pytest.raises(RuntimeError):
		sink.validate_details(
		"daily_publication.editorial_step_completed", {"step": "repair/../private"},
			frozenset({"step"}),
		)
	with pytest.raises(RuntimeError):
		sink.validate_details(
			"daily_publication.editorial_step_completed",
			{"step": "repair/sk-proj-example-value"},
			frozenset({"step"}),
		)


#============================================
def test_event_cap_preserves_terminal_state_progress(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A bounded event sink cannot prevent a record from reaching a terminal state."""
	_fixed_clock(monkeypatch)
	logging = daily_blog.config.DailyBlogLoggingConfig(max_events_per_run=2)
	store = daily_blog.run_state.RunStore(
		str(tmp_path), OWNER, REPORT_DATE, "run-capped", logging.max_events_per_run,
	)
	record = daily_blog.run_contracts.RunRecord.create("run-capped", REPORT_DATE, FIXED_TIME)
	record.start_phase("repository_discovery", "a" * 64)
	store.append_event("daily_publication.run_started", {"state": "running"})
	store.append_event("daily_publication.phase_started", {"phase": "repository_discovery"})
	record.fail_phase("repository_discovery", "route_unavailable")
	store.save(record)
	store.append_event(
		"daily_publication.phase_failed",
		{"failure_kind": "route_unavailable", "phase": "repository_discovery"},
	)
	store.finalize_summary(record)
	events = pathlib.Path(store.event_path).read_text(encoding="utf-8")
	reopened = daily_blog.run_state.RunStore.reopen(str(tmp_path), OWNER, REPORT_DATE, "run-capped")
	assert daily_blog.run_contracts.RunRecord.from_dict(
		json.loads(pathlib.Path(reopened.record_path).read_text(encoding="utf-8")),
	).state == "failed"
	assert "event_stream_truncated" in events
	assert daily_blog.observability.parse_terminal_summary_line(
		pathlib.Path(store.summary_path).read_text(encoding="utf-8").strip(),
	)["outcome"] == "failed"


#============================================
def test_event_sink_rejects_a_symlinked_journal(
	tmp_path: pathlib.Path,
) -> None:
	"""A durable event append cannot be redirected outside its run directory."""
	run_dir = tmp_path / "run"
	run_dir.mkdir()
	outside = tmp_path / "outside.jsonl"
	outside.write_text("keep\n", encoding="utf-8")
	os.symlink(outside, run_dir / f"runlog-{REPORT_DATE}.jsonl")
	sink = daily_blog.observability.RunEventSink(REPORT_DATE, "run-safe")
	line = sink.line("daily_publication.run_started", {"state": "running"}, frozenset({"state"}))
	run_fd = os.open(run_dir, os.O_RDONLY | os.O_DIRECTORY)
	try:
		with pytest.raises(OSError):
			sink.append_at(run_fd, line)
	finally:
		os.close(run_fd)
	assert outside.read_text(encoding="utf-8") == "keep\n"


#============================================
def test_event_sink_rejects_a_newline_free_oversized_existing_record(
	tmp_path: pathlib.Path,
) -> None:
	"""Capacity inspection bounds malformed durable event input before append."""
	run_dir = tmp_path / "run"
	run_dir.mkdir()
	(run_dir / f"runlog-{REPORT_DATE}.jsonl").write_bytes(
		b"x" * (daily_blog.observability.MAX_EVENT_LINE_BYTES + 2),
	)
	sink = daily_blog.observability.RunEventSink(REPORT_DATE, "run-safe")
	line = sink.line("daily_publication.run_started", {"state": "running"}, frozenset({"state"}))
	run_fd = os.open(run_dir, os.O_RDONLY | os.O_DIRECTORY)
	try:
		with pytest.raises(ValueError):
			sink.append_at(run_fd, line)
	finally:
		os.close(run_fd)


#============================================
@pytest.mark.parametrize("owner, report_date, run_id", (
	("../outside", REPORT_DATE, "run-safe"),
	(OWNER, "2026-8-29", "run-safe"),
	(OWNER, REPORT_DATE, "../run-safe"),
))
def test_run_store_rejects_path_bearing_public_selectors(
	tmp_path: pathlib.Path, owner: str, report_date: str, run_id: str,
) -> None:
	"""Public RunStore selectors cannot redirect mutable state outside its root."""
	with pytest.raises(RuntimeError):
		daily_blog.run_state.RunStore(str(tmp_path), owner, report_date, run_id)


#============================================
def test_run_store_rejects_an_empty_output_root_before_creation() -> None:
	"""An empty output selector cannot be interpreted as a current directory."""
	with pytest.raises(RuntimeError):
		daily_blog.run_state.RunStore("", OWNER, REPORT_DATE, "run-safe")


#============================================
def test_finalize_summary_uses_only_the_saved_terminal_record(
	tmp_path: pathlib.Path,
) -> None:
	"""A caller cannot attach a receipt for a different in-memory record."""
	store = _store(tmp_path, "run-authoritative")
	saved = _failed_record("run-authoritative")
	store.save(saved)
	caller = daily_blog.run_contracts.RunRecord.create(
		"run-authoritative", REPORT_DATE, FIXED_TIME,
	)
	caller.start_phase("repository_discovery", "a" * 64)
	caller.fail_phase("repository_discovery", "external_resource_error")
	with pytest.raises(RuntimeError):
		store.finalize_summary(caller)
	assert not pathlib.Path(store.summary_path).exists()


#============================================
def test_store_rejects_symlinked_summary_component(tmp_path: pathlib.Path) -> None:
	"""A summary journal cannot be redirected through a symlink."""
	store = _store(tmp_path, "run-summary-link")
	redirect = tmp_path / "redirected-summary.jsonl"
	os.symlink(redirect, store.summary_path)
	record = _failed_record("run-summary-link")
	store.save(record)
	with pytest.raises(RuntimeError):
		store.finalize_summary(record)


#============================================
@pytest.mark.parametrize(("seconds", "expected"), (
	(54, "54 sec"),
	(174, "2m54s"),
	(3723, "1h02m03s"),
))
def test_human_elapsed_time_uses_compact_whole_second_units(
	seconds: float, expected: str,
) -> None:
	"""Human timing stays compact without exposing wall-clock timestamps."""
	assert daily_blog.observability.format_elapsed(seconds) == expected


#============================================
def test_human_progress_times_coordinator_owned_steps(
	tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str],
) -> None:
	"""A coordinator start and result render one measured completion suffix."""
	progress = daily_blog.observability.HumanProgress(
		REPORT_DATE, str(tmp_path / "runlog.jsonl"),
	)
	clock = iter((10.0, 64.0))
	progress._clock = clock.__next__
	progress.note("A2", "Searching GitHub commits...")
	progress.note("A2", "Found 1 commit across 1 repo", "green")

	assert "A2 | Found 1 commit across 1 repo; completed in 54 sec" in capsys.readouterr().out


#============================================
def test_mirror_progress_reports_selected_and_unavailable_repositories(
	tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str],
) -> None:
	"""Mirror progress distinguishes search selection from unavailable refreshes."""
	progress = daily_blog.observability.HumanProgress(
		REPORT_DATE, str(tmp_path / "runlog.jsonl"),
	)
	progress.phase_result("mirror_refresh", [
		{"refresh_result": "refreshed"}, {"refresh_result": "failed"},
	], False)

	assert "A3 | Checked 2 repos selected from report-day commits; 1 unavailable" in capsys.readouterr().out


#============================================
def test_human_progress_prints_phase_completion_time(
	tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str],
) -> None:
	"""A phase without a separate result line receives a completion line."""
	progress = daily_blog.observability.HumanProgress(
		REPORT_DATE, str(tmp_path / "runlog.jsonl"),
	)
	clock = iter((10.0, 184.0))
	progress._clock = clock.__next__
	progress.event("daily_publication.phase_started", {"phase": "bundle_creation"})
	progress.event("daily_publication.phase_completed", {"phase": "bundle_creation"})

	assert "G2 | Completed in 2m54s" in capsys.readouterr().out


#============================================
def test_editorial_observations_do_not_repeat_owning_phase_duration(
	tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str],
) -> None:
	"""Concurrent child observations do not masquerade as independently timed work."""
	progress = daily_blog.observability.HumanProgress(
		REPORT_DATE, str(tmp_path / "runlog.jsonl"),
	)
	clock = iter((10.0, 184.0))
	progress._clock = clock.__next__
	progress.event("daily_publication.phase_started", {"phase": "repository_editorial"})
	progress.event("daily_publication.editorial_step_completed", {
		"step": "3.1", "outcome": "succeeded", "attempted": 6,
		"succeeded": 6, "failed": 0, "reused": 0, "repaired": 0,
		"disagreements": 0, "selected_artifact_id": "", "reasons": [],
	})
	progress.event("daily_publication.editorial_step_completed", {
		"step": "4.4", "outcome": "succeeded", "attempted": 3,
		"succeeded": 3, "failed": 0, "reused": 0, "repaired": 0,
		"disagreements": 0, "selected_artifact_id": "", "reasons": [],
	})
	progress.event("daily_publication.phase_completed", {
		"phase": "repository_editorial", "reused": False,
	})
	output = capsys.readouterr().out

	assert "B1 | 6 repository outlines received\n" in output
	assert "C4 | 3 repository summaries promoted\n" in output
	assert output.count("completed in 2m54s") == 0
	assert "B | Completed in 2m54s" in output


#============================================

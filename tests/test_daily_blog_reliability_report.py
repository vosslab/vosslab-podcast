"""Durable behavior tests for date-level daily-blog reliability reports."""

# Standard Library
import json
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.observability
import daily_blog.reliability_report
import daily_blog.run_contracts


#============================================
def terminal_summary(
	run_id: str,
	*,
	report_date: str = "2026-08-29",
	terminal_record_sha256: str = "b" * 64,
	state: str = "completed",
	outcome: str = "succeeded",
	terminal_fault_category: str = "",
	operational_failure_kind: str = "",
	steps: list[dict[str, object]] | None = None,
) -> dict[str, object]:
	"""Build a validated, fixed terminal receipt for reporter behavior tests."""
	failed = state == "failed"
	value: dict[str, object] = {
		"schema_version": daily_blog.observability.TERMINAL_SUMMARY_SCHEMA_VERSION,
		"terminal_record_sha256": terminal_record_sha256,
		"report_date": report_date,
		"run_id": run_id,
		"created_at": "2026-08-29T04:00:00Z",
		"completed_at": "2026-08-29T04:01:00Z",
		"state": state,
		"outcome": outcome,
		"best_artifact_id": "" if failed else "artifact-0123456789abcdef01234567",
		"failure_phase": "repository_editorial" if failed else "",
		"terminal_fault_category": terminal_fault_category,
		"operational_failure_kind": operational_failure_kind,
		"terminal_fault_subtype": "",
		"terminal_fault_owner": "",
		"publication_completed": not failed,
		"verified_page_sha256": "" if failed else "c" * 64,
		"incumbent_replacement_count": 0,
		"editorial_steps": steps if steps is not None else [],
	}
	value["summary_id"] = daily_blog.io_utils.sha256_text(
		f"{run_id}:{value['terminal_record_sha256']}",
	)
	return daily_blog.observability.validate_terminal_summary(value)


#============================================
def write_summary(
	tmp_path: pathlib.Path,
	summaries: tuple[dict[str, object], ...],
) -> pathlib.Path:
	"""Write canonical receipts at the only reporter input location."""
	path = tmp_path / "vosslab" / "daily_blog" / "2026-08-29" / "summary.jsonl"
	path.parent.mkdir(parents=True, exist_ok=True)
	lines = [
		json.dumps(summary, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
		for summary in summaries
	]
	path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
	return path


#============================================
def test_report_keeps_editorial_degradation_pipeline_faults_and_operational_failures_distinct() -> None:
	"""Advisory totals retain the materially different terminal outcomes."""
	fault = next(iter(daily_blog.run_contracts.TERMINAL_FAULT_KINDS))
	report = daily_blog.reliability_report.build_reliability_report((
		terminal_summary("run-succeeded"),
		terminal_summary("run-degraded", outcome="degraded"),
		terminal_summary("run-pipeline", state="failed", outcome="failed", terminal_fault_category=fault),
		terminal_summary("run-operational", state="failed", outcome="failed", operational_failure_kind="runtime_error"),
	))
	assert {
		"completed_succeeded": report["run_totals"]["completed_succeeded"],
		"completed_editorial_degradation": report["run_totals"]["completed_editorial_degradation"],
		"classified_pipeline_faults": report["run_totals"]["classified_pipeline_faults"],
		"incomplete_operational_failures": report["run_totals"]["incomplete_operational_failures"],
	} == {
		"completed_succeeded": 1,
		"completed_editorial_degradation": 1,
		"classified_pipeline_faults": 1,
		"incomplete_operational_failures": 1,
	}


#============================================
def test_report_discovers_opaque_steps_and_marks_absent_rate_denominators() -> None:
	"""A future editorial step remains visible without invented percentage data."""
	step = {
		"step": "future.stage:alpha",
		"outcome": "succeeded",
		"attempted": 0,
		"succeeded": 0,
		"failed": 0,
		"reused": 0,
		"repaired": 0,
		"disagreements": 0,
	}
	report = daily_blog.reliability_report.build_reliability_report((
		terminal_summary("run-future", steps=[step]),
	))
	row = report["steps"]["future.stage:alpha"]
	assert row["candidate_success_rate"] == {"numerator": 0, "denominator": 0, "rate": None}
	assert "success 0/0 (n/a)" in daily_blog.reliability_report.render_text_report(report)


#============================================
def test_report_reads_summary_after_its_detailed_run_directory_is_gone(tmp_path: pathlib.Path) -> None:
	"""Retention of detailed records cannot erase date-level reliability advice."""
	write_summary(tmp_path, (terminal_summary("run-retained-summary"),))
	run_dir = tmp_path / "vosslab" / "daily_blog" / "2026-08-29" / "runs" / "run-retained-summary"
	run_dir.mkdir(parents=True)
	run_dir.rmdir()
	report = daily_blog.reliability_report.report_for_date(str(tmp_path), "vosslab", "2026-08-29")
	assert report["run_totals"]["runs_observed"] == 1


#============================================
def test_present_empty_summary_is_a_valid_zero_observation_report(tmp_path: pathlib.Path) -> None:
	"""A newly created date journal is useful before its first terminal run."""
	write_summary(tmp_path, ())
	report = daily_blog.reliability_report.report_for_date(str(tmp_path), "vosslab", "2026-08-29")
	assert report["run_totals"]["runs_observed"] == 0


#============================================
def test_report_rejects_cross_date_or_duplicate_run_receipts(tmp_path: pathlib.Path) -> None:
	"""A date journal is one exact run population, not an advisory blend."""
	write_summary(tmp_path, (terminal_summary("run-other-date", report_date="2026-08-28"),))
	with pytest.raises(RuntimeError):
		daily_blog.reliability_report.report_for_date(str(tmp_path), "vosslab", "2026-08-29")
	write_summary(tmp_path, (
		terminal_summary("run-duplicate"),
		terminal_summary("run-duplicate", terminal_record_sha256="d" * 64),
	))
	with pytest.raises(RuntimeError):
		daily_blog.reliability_report.report_for_date(str(tmp_path), "vosslab", "2026-08-29")


#============================================
def test_report_rejects_summary_line_beyond_observability_envelope(tmp_path: pathlib.Path) -> None:
	"""A hostile line is bounded before it can become parsed report state."""
	path = write_summary(tmp_path, ())
	path.write_bytes(b"x" * (daily_blog.observability.MAX_SUMMARY_LINE_BYTES + 1) + b"\n")
	with pytest.raises(RuntimeError):
		daily_blog.reliability_report.report_for_date(str(tmp_path), "vosslab", "2026-08-29")


#============================================
@pytest.mark.parametrize("input_kind", ("corrupt", "noncanonical", "symlink"))
def test_report_rejects_untrusted_summary_inputs(tmp_path: pathlib.Path, input_kind: str) -> None:
	"""Malformed or redirected journals never become advisory facts."""
	path = write_summary(tmp_path, (terminal_summary("run-untrusted"),))
	if input_kind == "corrupt":
		path.write_text("not-json\n", encoding="utf-8")
	elif input_kind == "noncanonical":
		path.write_text(json.dumps(terminal_summary("run-untrusted")) + "\n", encoding="utf-8")
	else:
		target = tmp_path / "outside-summary.jsonl"
		target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
		path.unlink()
		path.symlink_to(target)
	with pytest.raises(RuntimeError):
		daily_blog.reliability_report.report_for_date(str(tmp_path), "vosslab", "2026-08-29")

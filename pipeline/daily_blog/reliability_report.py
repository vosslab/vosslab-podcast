"""Read-only advisory aggregation for bounded daily-blog terminal summaries."""

# Standard Library
import collections
import datetime
import json
import os
import pathlib
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager

# local repo modules
import daily_blog.observability


OWNER_RE = re.compile(r"^[A-Za-z0-9-]+$")
REPORT_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RELIABILITY_REPORT_SCHEMA_VERSION = "vosslab.daily-blog.reliability-report.v1"


#============================================
def _input_error() -> RuntimeError:
	"""Return one bounded diagnostic that cannot disclose input paths or data."""
	return RuntimeError("Reliability report input is unavailable or invalid.")


#============================================
def _validate_identity(owner: object, report_date: object) -> None:
	"""Reject unsafe owner/date selectors before constructing a path."""
	if type(owner) is not str or OWNER_RE.fullmatch(owner) is None:
		raise _input_error()
	if type(report_date) is not str or REPORT_DATE_RE.fullmatch(report_date) is None:
		raise _input_error()
	try:
		datetime.date.fromisoformat(report_date)
	except ValueError as error:
		raise _input_error() from error


#============================================
def summary_path(output_root: str, owner: str, report_date: str) -> pathlib.Path:
	"""Return the one safe date-level summary path beneath a controlled root."""
	_validate_identity(owner, report_date)
	if type(output_root) is not str or not output_root.strip():
		raise _input_error()
	try:
		root = pathlib.Path(output_root).resolve(strict=False)
		candidate = root / owner / "daily_blog" / report_date / "summary.jsonl"
		resolved_parent = candidate.parent.resolve(strict=False)
		if os.path.commonpath((str(root), str(resolved_parent))) != str(root):
			raise _input_error()
	except (OSError, ValueError) as error:
		raise _input_error() from error
	return candidate


#============================================
@contextmanager
def _open_summary_file(
	output_root: str,
	owner: str,
	report_date: str,
) -> Iterator[object]:
	"""Open one journal through no-follow directory-relative components."""
	path = summary_path(output_root, owner, report_date)
	try:
		root = pathlib.Path(output_root).resolve(strict=True)
		no_follow = os.O_NOFOLLOW
		directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | no_follow
		file_flags = os.O_RDONLY | os.O_CLOEXEC | no_follow
		root_fd = os.open(root, directory_flags)
		opened_dirs = [root_fd]
		try:
			current_fd = root_fd
			for component in (owner, "daily_blog", report_date):
				current_fd = os.open(component, directory_flags, dir_fd=current_fd)
				opened_dirs.append(current_fd)
			file_fd = os.open(path.name, file_flags, dir_fd=current_fd)
			try:
				if not stat.S_ISREG(os.fstat(file_fd).st_mode):
					raise _input_error()
				with os.fdopen(file_fd, "rb", closefd=True) as handle:
					yield handle
			except BaseException:
				# fdopen owns the descriptor only after it has succeeded.
				if "handle" not in locals():
					os.close(file_fd)
				raise
		finally:
			for directory_fd in reversed(opened_dirs):
				os.close(directory_fd)
	except (AttributeError, OSError, ValueError) as error:
		raise _input_error() from error


#============================================
def load_terminal_summaries(
	output_root: str, owner: str, report_date: str,
) -> Iterator[dict[str, object]]:
	"""Load only canonical terminal summaries for one date.

	No event log, run state, or artifact is read.  A present empty regular file is
	a valid zero-observation input; a missing, symlinked, or malformed file is not.
	"""
	_validate_identity(owner, report_date)
	maximum_raw_line_bytes = daily_blog.observability.MAX_SUMMARY_LINE_BYTES + 1
	seen_run_ids: set[str] = set()
	try:
		with _open_summary_file(output_root, owner, report_date) as handle:
			while raw_line := handle.readline(maximum_raw_line_bytes + 1):
				if len(raw_line) > maximum_raw_line_bytes or not raw_line.endswith(b"\n"):
					raise _input_error()
				try:
					line = raw_line[:-1].decode("ascii")
				except UnicodeDecodeError as error:
					raise _input_error() from error
				summary = daily_blog.observability.parse_terminal_summary_line(line)
				if summary["report_date"] != report_date:
					raise _input_error()
				run_id = summary["run_id"]
				if run_id in seen_run_ids:
					raise _input_error()
				seen_run_ids.add(run_id)
				yield summary
	except (OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as error:
		raise _input_error() from error


#============================================
def _rate(numerator: int, denominator: int) -> dict[str, int | float | None]:
	"""Represent one rate honestly when its population is absent."""
	return {
		"numerator": numerator,
		"denominator": denominator,
		"rate": None if denominator == 0 else numerator / denominator,
	}


#============================================
def _step_rollup(step: str) -> dict[str, object]:
	"""Create a dynamic roll-up without presuming current editorial topology."""
	return {
		"step": step,
		"runs_observed": 0,
		"attempted_total": 0,
		"succeeded_total": 0,
		"failed_total": 0,
		"reused_total": 0,
		"repaired_total": 0,
		"disagreements_total": 0,
		"degraded_runs": 0,
		"runs_with_disagreement": 0,
	}


#============================================
def _step_value(item: dict[str, object], name: str) -> int:
	"""Read one validator-guaranteed nonnegative count without guessing defaults."""
	value = item.get(name)
	if type(value) is not int or value < 0:
		raise _input_error()
	return value


#============================================
def _classify_run(summary: dict[str, object], totals: dict[str, object]) -> None:
	"""Keep completed degradation, closed faults, and operational loss distinct."""
	state = summary["state"]
	outcome = summary["outcome"]
	fault = summary["terminal_fault_category"]
	if state == "completed" and outcome == "succeeded":
		totals["completed_succeeded"] += 1
	elif state == "completed" and outcome == "degraded":
		totals["completed_editorial_degradation"] += 1
	elif type(fault) is str and fault:
		totals["classified_pipeline_faults"] += 1
		totals["pipeline_fault_categories"][fault] += 1
	else:
		totals["incomplete_operational_failures"] += 1


#============================================
def _explicit_incumbent_replacements(summary: dict[str, object]) -> tuple[int, int]:
	"""Return count/run facts only from the summary's explicit count field."""
	value = summary.get("incumbent_replacement_count")
	if type(value) is not int or value < 0:
		raise _input_error()
	# Every valid terminal summary supplies this count, so the observed-summary
	# population is the explicit occurrence denominator for this aggregate.
	return value, 1


#============================================
def build_reliability_report(summaries: object) -> dict[str, object]:
	"""Aggregate valid summaries into an advisory, topology-neutral report."""
	if isinstance(summaries, (str, bytes, dict)):
		raise _input_error()
	totals: dict[str, object] = {
		"runs_observed": 0,
		"completed_succeeded": 0,
		"completed_editorial_degradation": 0,
		"classified_pipeline_faults": 0,
		"pipeline_fault_categories": collections.Counter(),
		"incomplete_operational_failures": 0,
	}
	steps: dict[str, dict[str, object]] = {}
	replacement_numerator = 0
	replacement_denominator = 0
	seen_run_ids: set[str] = set()
	try:
		for value in summaries:
			summary = daily_blog.observability.validate_terminal_summary(value)
			run_id = summary["run_id"]
			if run_id in seen_run_ids:
				raise _input_error()
			seen_run_ids.add(run_id)
			totals["runs_observed"] += 1
			_classify_run(summary, totals)
			items = summary["editorial_steps"]
			for item in items:
				row = steps.setdefault(item["step"], _step_rollup(item["step"]))
				row["runs_observed"] += 1
				for source, target in (
					("attempted", "attempted_total"), ("succeeded", "succeeded_total"),
					("failed", "failed_total"), ("reused", "reused_total"),
					("repaired", "repaired_total"), ("disagreements", "disagreements_total"),
				):
					row[target] += _step_value(item, source)
				if item.get("outcome") == "degraded":
					row["degraded_runs"] += 1
				if _step_value(item, "disagreements") > 0:
					row["runs_with_disagreement"] += 1
			observations = _explicit_incumbent_replacements(summary)
			replacement_numerator += observations[0]
			replacement_denominator += observations[1]
	except (RuntimeError, TypeError, ValueError) as error:
		raise _input_error() from error
	for row in steps.values():
		row["candidate_success_rate"] = _rate(row["succeeded_total"], row["attempted_total"])
		row["candidate_failure_rate"] = _rate(row["failed_total"], row["attempted_total"])
		row["degraded_run_rate"] = _rate(row["degraded_runs"], row["runs_observed"])
		row["disagreement_run_rate"] = _rate(
			row["runs_with_disagreement"], row["runs_observed"],
		)
	return {
		"schema_version": RELIABILITY_REPORT_SCHEMA_VERSION,
		"run_totals": {
			"runs_observed": totals["runs_observed"],
			"completed_succeeded": totals["completed_succeeded"],
			"completed_editorial_degradation": totals["completed_editorial_degradation"],
			"classified_pipeline_faults": totals["classified_pipeline_faults"],
			"pipeline_fault_categories": dict(
				sorted(totals["pipeline_fault_categories"].items()),
			),
			"incomplete_operational_failures": totals["incomplete_operational_failures"],
		},
		"steps": dict(sorted(steps.items())),
		"incumbent_replacements": (
			{"available": True, "rate": _rate(replacement_numerator, replacement_denominator)}
		),
	}


#============================================
def report_for_date(output_root: str, owner: str, report_date: str) -> dict[str, object]:
	"""Load and aggregate the one requested date without mutating durable state."""
	return build_reliability_report(
		load_terminal_summaries(output_root, owner, report_date),
	)


#============================================
def _format_rate(value: dict[str, int | float | None]) -> str:
	"""Render a raw pair plus advisory rate."""
	rate = value["rate"]
	text = "n/a" if rate is None else f"{float(rate):.3f}"
	return f"{value['numerator']}/{value['denominator']} ({text})"


#============================================
def render_text_report(report: dict[str, object]) -> str:
	"""Render a concise human report while retaining every raw denominator."""
	totals = report["run_totals"]
	lines = [
		"Daily blog reliability (advisory)",
		f"runs observed: {totals['runs_observed']}",
		f"completed succeeded: {totals['completed_succeeded']}",
		f"completed editorial degradation: {totals['completed_editorial_degradation']}",
		f"classified pipeline faults: {totals['classified_pipeline_faults']}",
		f"incomplete operational failures: {totals['incomplete_operational_failures']}",
	]
	for category, count in totals["pipeline_fault_categories"].items():
		lines.append(f"pipeline fault {category}: {count}")
	for step, row in report["steps"].items():
		lines.append(
			f"step {step}: runs {row['runs_observed']}; attempts {row['attempted_total']}; "
			f"success {_format_rate(row['candidate_success_rate'])}; "
			f"failure {_format_rate(row['candidate_failure_rate'])}; "
			f"reused {row['reused_total']}; repaired {row['repaired_total']}; "
			f"degraded {_format_rate(row['degraded_run_rate'])}; "
			f"disagreement {_format_rate(row['disagreement_run_rate'])}"
		)
	incumbent = report["incumbent_replacements"]
	lines.append(
		f"incumbent replacements per observed run: {_format_rate(incumbent['rate'])}",
	)
	return "\n".join(lines)

"""Persistent run records and inspectable per-phase artifacts."""

# Standard Library
import os
import sys
import json
import datetime

# local repo modules
import daily_blog.schema
import daily_blog.io_utils


class RunStore:
	"""Own one run's mutable record until it reaches a terminal immutable state."""

	EVENT_FIELDS = {
		"daily_publication.phase_completed": frozenset({"phase", "reused"}),
		"daily_publication.phase_failed": frozenset({"error_class", "phase"}),
		"daily_publication.phase_started": frozenset({"phase"}),
		"daily_publication.run_completed": frozenset(
			{"bundle_id", "site_import_status", "state"}
		),
		"daily_publication.run_started": frozenset({"state"}),
	}

	#============================================
	def __init__(self, output_root: str, owner: str, report_date: str, run_id: str) -> None:
		"""Create the unique run-state directory."""
		self.report_date = report_date
		self.run_id = run_id
		self.run_dir = os.path.join(
			os.path.abspath(output_root),
			owner,
			"daily_blog_runs",
			report_date,
			run_id,
		)
		if os.path.exists(self.run_dir):
			raise RuntimeError(f"Immutable run-state directory already exists: {self.run_dir}")
		os.makedirs(self.run_dir)
		self.record_path = os.path.join(self.run_dir, "run_state.json")
		self.event_path = os.path.join(self.run_dir, "events.jsonl")

	#============================================
	def _validate_event_details(self, event: str, details: dict[str, object]) -> None:
		"""Require the exact bounded fields and values for one lifecycle event."""
		if event not in self.EVENT_FIELDS:
			raise RuntimeError("Unsupported daily-publication event name.")
		if set(details) != self.EVENT_FIELDS[event]:
			raise RuntimeError("Daily-publication event fields do not match the event schema.")
		if "phase" in details and details["phase"] not in daily_blog.schema.LEGAL_PHASES:
			raise RuntimeError("Daily-publication event phase is unsupported.")
		if "reused" in details and type(details["reused"]) is not bool:
			raise RuntimeError("Daily-publication reused state must be Boolean.")
		if "error_class" in details:
			error_class = details["error_class"]
			if (
				not isinstance(error_class, str)
				or len(error_class) > 100
				or not error_class.isidentifier()
			):
				raise RuntimeError("Daily-publication error class must be a bounded identifier.")
		if "bundle_id" in details:
			bundle_id = details["bundle_id"]
			if not isinstance(bundle_id, str) or len(bundle_id) != 64 or not bundle_id.isalnum():
				raise RuntimeError("Daily-publication bundle identity is invalid.")
		if "site_import_status" in details:
			if details["site_import_status"] not in {"idempotent", "imported"}:
				raise RuntimeError("Daily-publication import status is unsupported.")
		if "state" in details:
			expected_state = "completed" if event.endswith("run_completed") else "running"
			if details["state"] != expected_state:
				raise RuntimeError("Daily-publication run state does not match the event.")

	#============================================
	def _event_line(self, event: str, details: dict[str, object]) -> str:
		"""Validate and serialize one scheduler-safe lifecycle event."""
		self._validate_event_details(event, details)
		timestamp = datetime.datetime.now(datetime.UTC).isoformat()
		value: dict[str, object] = {
			"event": event,
			"occurred_at": timestamp,
			"report_date": self.report_date,
			"run_id": self.run_id,
			"run_state_path": self.record_path,
		}
		value.update(details)
		line = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
		return line

	#============================================
	def _append_event_file(self, line: str) -> None:
		"""Append one serialized event to the per-run JSONL sink."""
		with open(self.event_path, "a", encoding="utf-8") as handle:
			handle.write(line + "\n")
			handle.flush()

	#============================================
	def _write_sink_warning(self, sink: str, error: Exception) -> None:
		"""Report a bounded sink failure without exposing raw exception text."""
		value = {
			"error_class": error.__class__.__name__,
			"event": "daily_publication.event_sink_failed",
			"report_date": self.report_date,
			"run_id": self.run_id,
			"sink": sink,
		}
		line = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
		try:
			sys.stderr.write(line + "\n")
			sys.stderr.flush()
		except (OSError, ValueError):
			return

	#============================================
	def append_event(self, event: str, details: dict[str, object]) -> None:
		"""Send one validated event to independent best-effort file and stdout sinks."""
		try:
			line = self._event_line(event, details)
		except (RuntimeError, TypeError, ValueError) as error:
			self._write_sink_warning("validation", error)
			return
		try:
			self._append_event_file(line)
		except (OSError, ValueError) as error:
			self._write_sink_warning("events.jsonl", error)
		try:
			print(line, flush=True)
		except (OSError, ValueError) as error:
			self._write_sink_warning("stdout", error)

	#============================================
	def save(self, record: daily_blog.schema.RunRecord) -> None:
		"""Atomically persist the authoritative typed run record."""
		daily_blog.io_utils.atomic_write_json(self.record_path, record.to_dict())

	#============================================
	def write_artifact(self, name: str, value: object) -> str:
		"""Write one stable inspectable JSON artifact inside this run."""
		if os.path.basename(name) != name or not name.endswith(".json"):
			raise RuntimeError("Run artifacts must use one direct JSON filename.")
		path = os.path.join(self.run_dir, name)
		daily_blog.io_utils.atomic_write_json(path, value)
		return path

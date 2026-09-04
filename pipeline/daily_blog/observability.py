"""Bounded, path-safe observability values for daily-publication runs."""

# Standard Library
import contextlib
import datetime
import json
import os
import re
import stat
import time
from collections.abc import Iterator

# PIP3 modules
import rich.text
import rich.console

# local repo modules
import daily_blog.io_utils
import daily_blog.recovery
import daily_blog.replication
import daily_blog.run_contracts


TERMINAL_SUMMARY_SCHEMA = "vosslab.daily-blog.terminal-summary"
MAX_EVENT_LINE_BYTES = 4096
MAX_SUMMARY_LINE_BYTES = 16384
# The authoritative record is a retained, inspectable artifact. Keep every
# consumer behind this one byte envelope so malformed retained state cannot
# turn either recovery or retention into an unbounded parse.
MAX_RUN_STATE_BYTES = 131072
MAX_EVENT_IDENTIFIER_CHARS = 160
MAX_SUMMARY_STEPS = 512
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_OPAQUE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_FORBIDDEN_TEXT_RE = re.compile(r"(?:https?://|(?:api|secret|access)[_-]?key|token|password|/|\\\\)", re.I)
# Recognizable production credential prefixes are unsafe even when they happen
# to fit the deliberately small opaque-identifier grammar.  Keep this bounded
# to stable prefix families so ordinary editorial identifiers remain usable.
_CREDENTIAL_VALUE_RE = re.compile(
	r"^(?:sk-(?:proj|ant)-|ghp_|github_pat_|xox[bpras]-)",
)
_SUMMARY_FIELDS = frozenset({
	"schema_version", "summary_id", "terminal_record_sha256", "report_date", "run_id",
	"created_at", "completed_at", "state", "outcome", "best_artifact_id",
	"failure_phase", "terminal_fault_category", "operational_failure_kind",
	"terminal_fault_subtype", "terminal_fault_owner",
	"publication_completed", "verified_page_sha256", "incumbent_replacement_count",
	"editorial_steps",
})
_SUMMARY_STEP_FIELDS = frozenset({
	"step", "outcome", "attempted", "succeeded", "failed", "reused", "repaired",
	"disagreements",
})


class EventJournalError(ValueError):
	"""A rejected durable event journal remains a best-effort sink failure."""


@contextlib.contextmanager
def _directory_descriptor(
	name: str,
	flags: int,
	directory_fd: int | None = None,
) -> Iterator[int]:
	"""Hold one verified, no-follow directory descriptor for a filesystem operation."""
	kwargs = {} if directory_fd is None else {"dir_fd": directory_fd}
	descriptor = os.open(name, flags, **kwargs)
	try:
		if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
			raise RuntimeError("Daily-publication retention layout is invalid.")
		yield descriptor
	finally:
		os.close(descriptor)


def read_bounded_regular_json_at(directory_fd: int, name: str, maximum_bytes: int) -> object:
	"""Read one direct regular JSON child through a held descriptor.

	Callers retain ownership of their error policy; this shared primitive keeps
	recovery and retention on the same no-follow, bounded byte boundary.
	"""
	if (
		type(name) is not str
		or name in {"", ".", ".."}
		or os.path.basename(name) != name
		or type(maximum_bytes) is not int
		or maximum_bytes <= 0
	):
		raise RuntimeError("Daily-publication state file selection is invalid.")
	flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
	with os.fdopen(os.open(name, flags, dir_fd=directory_fd), "rb") as handle:
		if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
			raise RuntimeError("Daily-publication state file is invalid.")
		if os.fstat(handle.fileno()).st_size > maximum_bytes:
			raise RuntimeError("Daily-publication state file exceeds its schema envelope.")
		payload = handle.read(maximum_bytes + 1)
	if len(payload) > maximum_bytes:
		raise RuntimeError("Daily-publication state file exceeds its schema envelope.")
	try:
		return json.loads(payload.decode("utf-8"))
	except (UnicodeDecodeError, TypeError, ValueError) as error:
		raise RuntimeError("Daily-publication state file is invalid.") from error


def _canonical_line(value: dict[str, object], maximum_bytes: int) -> str:
	"""Return a canonical ASCII JSONL value within its storage budget."""
	line = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
	if "\n" in line or "\r" in line or len(line.encode("ascii")) > maximum_bytes:
		raise RuntimeError("Observability record exceeds its bounded JSONL envelope.")
	return line


def _utc_timestamp(value: object, label: str, allow_empty: bool = False) -> str:
	if allow_empty and value == "":
		return ""
	if type(value) is not str:
		raise RuntimeError(f"{label} is invalid.")
	daily_blog.run_contracts.RunRecord._validate_utc_timestamp(value, label)
	return value


def _opaque(value: object, label: str, allow_empty: bool = False) -> str:
	if allow_empty and value == "":
		return ""
	if type(value) is not str or _OPAQUE_ID_RE.fullmatch(value) is None:
		raise RuntimeError(f"{label} is invalid.")
	if _FORBIDDEN_TEXT_RE.search(value) or _CREDENTIAL_VALUE_RE.search(value):
		raise RuntimeError(f"{label} contains unsafe diagnostic text.")
	return value


def _editorial_step(value: object) -> str:
	"""Allow a bounded logical step namespace without admitting path data.

	Editorial recovery can name a narrow substep (for example,
	``stage6/no_artifact/6.writer``).  It is an observation label, never a
	filesystem path: each slash-delimited component must independently satisfy
	the opaque identifier policy and cannot be ``.`` or ``..``.  This keeps the
	event's redaction and path-safety boundary explicit.  # ASVS 2.2.1, 5.3.2
	"""
	if type(value) is not str or not value or len(value) > MAX_EVENT_IDENTIFIER_CHARS:
		raise RuntimeError("Daily-publication editorial step is invalid.")
	parts = value.split("/")
	if any(part in {".", ".."} for part in parts):
		raise RuntimeError("Daily-publication editorial step is invalid.")
	for part in parts:
		_opaque(part, "Daily-publication editorial step")
	return value


def _sha256(value: object, label: str, allow_empty: bool = False) -> str:
	if allow_empty and value == "":
		return ""
	if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
		raise RuntimeError(f"{label} is invalid.")
	return value


def _report_date(value: object) -> str:
	"""Require the canonical calendar date used as publication identity."""
	value = _opaque(value, "Terminal summary report date")
	try:
		if datetime.date.fromisoformat(value).isoformat() != value:
			raise ValueError
	except ValueError as error:
		raise RuntimeError("Terminal summary report date is invalid.") from error
	return value


def validate_terminal_summary(value: object) -> dict[str, object]:
	"""Return a normalized exact terminal-summary copy or reject unsafe input."""
	if type(value) is not dict or set(value) != _SUMMARY_FIELDS:
		raise RuntimeError("Terminal summary uses unsupported fields.")
	if value["schema_version"] != TERMINAL_SUMMARY_SCHEMA:
		raise RuntimeError("Terminal summary schema is unsupported.")
	result: dict[str, object] = {
		"schema_version": TERMINAL_SUMMARY_SCHEMA,
		"summary_id": _sha256(value["summary_id"], "Terminal summary identity"),
		"terminal_record_sha256": _sha256(value["terminal_record_sha256"], "Terminal record identity"),
		"report_date": _report_date(value["report_date"]),
		"run_id": _opaque(value["run_id"], "Terminal summary run identity"),
		"created_at": _utc_timestamp(value["created_at"], "Terminal summary creation time"),
		"completed_at": _utc_timestamp(value["completed_at"], "Terminal summary completion time"),
		"state": value["state"],
		"outcome": value["outcome"],
		"best_artifact_id": _opaque(value["best_artifact_id"], "Terminal artifact identity", True),
		"failure_phase": _opaque(value["failure_phase"], "Terminal failure phase", True),
		"terminal_fault_category": _opaque(value["terminal_fault_category"], "Terminal fault category", True),
		"operational_failure_kind": _opaque(value["operational_failure_kind"], "Operational failure kind", True),
		"terminal_fault_subtype": _opaque(value["terminal_fault_subtype"], "Terminal fault subtype", True),
		"terminal_fault_owner": _opaque(value["terminal_fault_owner"], "Terminal fault owner", True),
		"publication_completed": value["publication_completed"],
		"verified_page_sha256": _sha256(value["verified_page_sha256"], "Verified page identity", True),
		"incumbent_replacement_count": value["incumbent_replacement_count"],
	}
	if result["summary_id"] != daily_blog.io_utils.sha256_text(
		f"{result['run_id']}:{result['terminal_record_sha256']}",
	):
		raise RuntimeError("Terminal summary identity does not bind its terminal record.")
	if result["completed_at"] < result["created_at"]:
		raise RuntimeError("Terminal summary completion precedes its creation.")
	if result["state"] not in {"completed", "failed"} or result["outcome"] not in {
		"succeeded", "degraded", "failed",
	}:
		raise RuntimeError("Terminal summary state or outcome is invalid.")
	if type(result["publication_completed"]) is not bool:
		raise RuntimeError("Terminal summary publication status is invalid.")
	if type(result["incumbent_replacement_count"]) is not int or result["incumbent_replacement_count"] < 0:
		raise RuntimeError("Terminal summary replacement count is invalid.")
	if result["best_artifact_id"] and (
		daily_blog.run_contracts.PUBLISHABLE_ARTIFACT_ID_RE.fullmatch(
			result["best_artifact_id"],
		) is None
	):
		raise RuntimeError("Terminal artifact identity is invalid.")
	if result["terminal_fault_category"] and result["terminal_fault_category"] not in (
		daily_blog.run_contracts.TERMINAL_FAULT_KINDS
	):
		raise RuntimeError("Terminal fault category is invalid.")
	if bool(result["terminal_fault_subtype"]) != bool(result["terminal_fault_owner"]):
		raise RuntimeError("Terminal fault subtype and owner must be paired.")
	if result["terminal_fault_subtype"]:
		try:
			fault = daily_blog.recovery.TerminalFaultDigest(
				daily_blog.recovery.TerminalFaultCategory(result["terminal_fault_category"]),
				daily_blog.recovery.TerminalFaultSubtype(result["terminal_fault_subtype"]),
				result["terminal_fault_owner"],
			)
		except (TypeError, ValueError, daily_blog.recovery.RecoveryConfigurationError) as error:
			raise RuntimeError("Terminal fault subtype is invalid.") from error
		if fault.category.value != result["terminal_fault_category"]:
			raise RuntimeError("Terminal fault subtype conflicts with category.")
	if result["operational_failure_kind"] and result["operational_failure_kind"] not in (
		daily_blog.run_contracts.OPERATIONAL_FAILURE_KINDS
	):
		raise RuntimeError("Operational failure kind is invalid.")
	if result["state"] == "completed":
		if result["outcome"] not in {"succeeded", "degraded"}:
			raise RuntimeError("Completed terminal summary has an invalid outcome.")
		if result["terminal_fault_category"] or result["operational_failure_kind"] or result["failure_phase"]:
			raise RuntimeError("Completed terminal summary has failure facts.")
	else:
		if result["outcome"] != "failed":
			raise RuntimeError("Failed terminal summary has an invalid outcome.")
		if bool(result["terminal_fault_category"]) == bool(result["operational_failure_kind"]):
			raise RuntimeError("Failed terminal summary must have one failure classification.")
		if result["operational_failure_kind"] and result["terminal_fault_subtype"]:
			raise RuntimeError("Operational failure cannot retain a terminal subtype.")
		if result["failure_phase"] not in daily_blog.run_contracts.LEGAL_PHASES:
			raise RuntimeError("Failed terminal summary requires its failure phase.")
	if result["publication_completed"] != bool(result["verified_page_sha256"]):
		raise RuntimeError("Terminal summary publication facts are inconsistent.")
	if result["state"] == "completed" and not result["publication_completed"]:
		raise RuntimeError("Completed terminal summary requires verified publication.")
	steps = value["editorial_steps"]
	if type(steps) is not list or len(steps) > MAX_SUMMARY_STEPS:
		raise RuntimeError("Terminal summary editorial steps are invalid.")
	normal_steps: list[dict[str, object]] = []
	for step in steps:
		if type(step) is not dict or set(step) != _SUMMARY_STEP_FIELDS:
			raise RuntimeError("Terminal summary editorial step uses unsupported fields.")
		# Summary receipts project the same logical step identity that the
		# event boundary already accepts.  It remains a bounded observation,
		# never a filesystem path.  # ASVS 2.2.1, 14.2.4
		normal = {"step": _editorial_step(step["step"]), "outcome": step["outcome"]}
		if normal["outcome"] not in {"succeeded", "degraded"}:
			raise RuntimeError("Terminal summary editorial outcome is invalid.")
		for name in _SUMMARY_STEP_FIELDS - {"step", "outcome"}:
			item = step[name]
			if type(item) is not int or item < 0:
				raise RuntimeError("Terminal summary editorial count is invalid.")
			normal[name] = item
		if normal["succeeded"] + normal["failed"] != normal["attempted"]:
			raise RuntimeError("Terminal summary editorial counts are inconsistent.")
		if normal["reused"] > normal["succeeded"] or normal["repaired"] > normal["succeeded"]:
			raise RuntimeError("Terminal summary editorial reuse or repair count is inconsistent.")
		normal_steps.append(normal)
	if len({item["step"] for item in normal_steps}) != len(normal_steps):
		raise RuntimeError("Terminal summary has duplicate editorial steps.")
	result["editorial_steps"] = normal_steps
	_canonical_line(result, MAX_SUMMARY_LINE_BYTES)
	return result


def parse_terminal_summary_line(line: str) -> dict[str, object]:
	"""Parse one canonical ASCII terminal-summary JSONL line."""
	if type(line) is not str or "\n" in line or "\r" in line:
		raise RuntimeError("Terminal summary line is invalid.")
	try:
		line.encode("ascii")
		value = json.loads(line)
	except (UnicodeEncodeError, TypeError, ValueError) as error:
		raise RuntimeError("Terminal summary line is invalid.") from error
	result = validate_terminal_summary(value)
	if _canonical_line(result, MAX_SUMMARY_LINE_BYTES) != line:
		raise RuntimeError("Terminal summary line is not canonical.")
	return result


class RunEventSink:
	"""Validate and append only bounded, redacted lifecycle observations."""

	def __init__(self, report_date: str, run_id: str, max_events: int | None = None) -> None:
		"""Create a descriptor-consuming sink for one selected run."""
		self.report_date = _opaque(report_date, "Event report date")
		self.run_id = _opaque(run_id, "Event run identity")
		self.journal_name = f"runlog-{self.report_date}.jsonl"
		if max_events is None:
			self.max_events = 513
		elif type(max_events) is int and max_events > 0:
			self.max_events = max_events
		else:
			raise RuntimeError("Daily-publication event capacity is invalid.")

	def validate_details(self, event: str, details: dict[str, object], fields: frozenset[str]) -> None:
		if type(event) is not str or not event.startswith("daily_publication.") or set(details) != fields:
			raise RuntimeError("Daily-publication event uses unsupported fields.")
		for name, value in details.items():
			if type(value) is dict or isinstance(value, (list, tuple, set)):
				raise RuntimeError("Daily-publication event facts must be scalar.")
			if type(value) is str:
				if name == "step":
					_editorial_step(value)
				else:
					_opaque(value, "Daily-publication event fact", allow_empty=True)

	def line(self, event: str, details: dict[str, object], fields: frozenset[str]) -> str:
		self.validate_details(event, details, fields)
		value: dict[str, object] = {
			"event": event, "occurred_at": daily_blog.io_utils.utc_now(),
			"report_date": self.report_date, "run_id": self.run_id,
			"run_state_artifact": "run_state.json",
		}
		value.update(details)
		return _canonical_line(value, MAX_EVENT_LINE_BYTES)

	def _line_count_from_descriptor(self, descriptor: int) -> int:
		"""Count a bounded valid prefix through the descriptor selected for append."""
		# At capacity no later record can change the append decision, so do not
		# allocate or inspect an attacker-controlled tail.  # ASVS 5.3.2, 16.2.5
		os.lseek(descriptor, 0, os.SEEK_SET)
		count = 0
		with os.fdopen(os.dup(descriptor), "rb") as handle:
			while count < self.max_events:
				raw_line = handle.readline(MAX_EVENT_LINE_BYTES + 2)
				if not raw_line:
					break
				if (
					not raw_line.endswith(b"\n")
					or len(raw_line) > MAX_EVENT_LINE_BYTES + 1
				):
					raise EventJournalError("Daily-publication event journal is invalid.")
				try:
					line = raw_line[:-1].decode("ascii")
					value = json.loads(line)
				except (UnicodeDecodeError, TypeError, ValueError) as error:
					raise EventJournalError("Daily-publication event journal is invalid.") from error
				if type(value) is not dict or _canonical_line(value, MAX_EVENT_LINE_BYTES) != line:
					raise EventJournalError("Daily-publication event journal is invalid.")
				count += 1
		return count

	def _replay_editorial_from_descriptor(self, descriptor: int, line: str) -> bool:
		"""Reconcile one required editorial event through its held descriptor.

		The pending-transition caller must be able to prove that its exact event
		was written, rather than merely that the journal accepted some record at
		capacity.  Read only the bounded prefix that can affect that decision and
		keep this descriptor for a possible append.  # ASVS 2.2.1, 2.3.1, 5.3.2
		"""
		try:
			expected = json.loads(line)
		except (TypeError, ValueError) as error:
			raise EventJournalError("Pending editorial event is invalid.") from error
		if (
			type(expected) is not dict
			or _canonical_line(expected, MAX_EVENT_LINE_BYTES) != line
			or expected.get("event") != "daily_publication.editorial_step_completed"
			or expected.get("report_date") != self.report_date
			or expected.get("run_id") != self.run_id
		):
			raise EventJournalError("Pending editorial event is invalid.")
		_editorial_step(expected.get("step"))

		os.lseek(descriptor, 0, os.SEEK_SET)
		count = exact_matches = 0
		with os.fdopen(os.dup(descriptor), "rb") as handle:
			while count < self.max_events:
				raw_line = handle.readline(MAX_EVENT_LINE_BYTES + 2)
				if not raw_line:
					break
				if (
					not raw_line.endswith(b"\n")
					or len(raw_line) > MAX_EVENT_LINE_BYTES + 1
				):
					raise EventJournalError("Daily-publication event journal is invalid.")
				try:
					stored_line = raw_line[:-1].decode("ascii")
					stored = json.loads(stored_line)
				except (UnicodeDecodeError, TypeError, ValueError) as error:
					raise EventJournalError("Daily-publication event journal is invalid.") from error
				if type(stored) is not dict or _canonical_line(stored, MAX_EVENT_LINE_BYTES) != stored_line:
					raise EventJournalError("Daily-publication event journal is invalid.")
				if (
					stored.get("event") == expected["event"]
					and stored.get("step") == expected["step"]
				):
					if stored_line != line:
						raise EventJournalError("Pending editorial event diverges from event sink.")
					exact_matches += 1
				count += 1
		if exact_matches > 1:
			raise EventJournalError("Pending editorial event is duplicated.")
		if exact_matches == 1:
			return False
		if count >= self.max_events:
			raise EventJournalError("Daily-publication event journal has no room for editorial replay.")
		if count == self.max_events - 1:
			truncation = _canonical_line({
				"event": "daily_publication.event_stream_truncated",
				"occurred_at": daily_blog.io_utils.utc_now(), "report_date": self.report_date,
				"run_id": self.run_id, "run_state_artifact": "run_state.json",
			}, MAX_EVENT_LINE_BYTES)
			os.write(descriptor, (truncation + "\n").encode("ascii"))
			os.fsync(descriptor)
			raise EventJournalError("Daily-publication event journal has no room for editorial replay.")
		os.write(descriptor, (line + "\n").encode("ascii"))
		os.fsync(descriptor)
		return True

	@contextlib.contextmanager
	def _event_descriptor_at(self, run_fd: int) -> Iterator[int]:
		"""Open the direct journal below a RunStore-held run descriptor."""
		file_flags = os.O_RDWR | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
		descriptor = os.open(self.journal_name, file_flags, 0o600, dir_fd=run_fd)
		try:
			if not stat.S_ISREG(os.fstat(descriptor).st_mode):
				raise EventJournalError("Daily-publication event journal is invalid.")
			yield descriptor
		finally:
			os.close(descriptor)

	def append_at(self, run_fd: int, line: str) -> bool:
		"""Append an accepted line, retaining one truncation marker at capacity."""
		# Keep the held descriptor through inspection and append.  Reopening the
		# pathname after validation would reintroduce a replacement race.
		with self._event_descriptor_at(run_fd) as descriptor:
			count = self._line_count_from_descriptor(descriptor)
			if count >= self.max_events:
				return False
			if count == self.max_events - 1:
				line = _canonical_line({
					"event": "daily_publication.event_stream_truncated",
					"occurred_at": daily_blog.io_utils.utc_now(), "report_date": self.report_date,
					"run_id": self.run_id, "run_state_artifact": "run_state.json",
				}, MAX_EVENT_LINE_BYTES)
			os.write(descriptor, (line + "\n").encode("ascii"))
			os.fsync(descriptor)
			return True

	def replay_editorial_at(self, run_fd: int, line: str) -> bool:
		"""Append one pending editorial event once, or acknowledge its exact prior append."""
		# This intentionally does not delegate to ``append``: replay inspection
		# and append must share one no-follow descriptor.  # ASVS 2.3.1, 5.3.2
		with self._event_descriptor_at(run_fd) as descriptor:
			return self._replay_editorial_from_descriptor(descriptor, line)


def format_elapsed(seconds: float) -> str:
	"""Return one compact whole-second duration for human progress output."""
	total = max(0, round(seconds))
	minutes, remainder = divmod(total, 60)
	if not minutes:
		return f"{remainder} sec"
	hours, minutes = divmod(minutes, 60)
	if not hours:
		return f"{minutes}m{remainder:02d}s"
	return f"{hours}h{minutes:02d}m{remainder:02d}s"


class HumanProgress:
	"""Render validated publication progress without owning workflow decisions."""

	_STEP_LABELS = {
		"3.1": "repository outlines received", "3.2": "repository outlines merged",
		"3.3": "repository outlines reviewed", "3.4": "repository outlines promoted",
		"4.1": "repository summaries received", "4.2": "repository summaries edited",
		"4.3": "repository summaries reviewed", "4.4": "repository summaries promoted",
		"5.1": "daily rankings received", "5.2": "daily rankings reviewed",
		"5.3": "daily outlines received", "5.4": "daily outlines reviewed",
		"5.5": "daily outline promoted", "6.1": "complete posts received",
		"6.2": "complete posts edited", "6.3": "complete posts reviewed",
		"6.4": "complete post promoted", "7.1": "final syntheses received",
		"7.2": "final syntheses reviewed", "7.3": "final post selected",
		"publication_validation": "publication-ready posts prepared",
		"repository_job": "repository editorial jobs completed",
		"stage6_complete_post": "complete-post candidates processed",
	}
	_STEP_CODES = {
		"3.1": "B1", "3.2": "B2", "3.3": "B3", "3.4": "B4",
		"repository_job": "C5",
		"4.1": "C1", "4.2": "C2", "4.3": "C3", "4.4": "C4",
		"5.1": "D1", "5.2": "D2", "5.3": "D3", "5.4": "D4", "5.5": "D5",
		"6.1": "E1", "6.2": "E2", "6.3": "E3", "6.4": "E4",
		"stage6_complete_post": "E5",
		"7.1": "F1", "7.2": "F2", "7.3": "F3",
		"publication_validation": "G1",
	}
	_PHASE_STARTS = {
		"repository_discovery": "Finding the account repository roster",
		"mirror_refresh": "Refreshing repositories selected from report-day commits",
		"activity_location": "Locating exact report-day commits",
		"evidence_assembly": "Summarizing repository commits and changelogs",
		"repository_editorial": "Preparing repository outlines and summaries",
		"stage5_daily_outline": "Building the daily outline",
		"stage6_complete_post": "Writing complete blog candidates",
		"stage7_final_synthesis": "Optionally improving the publishable post",
		"publication_validation": "Preparing publication metadata",
		"bundle_creation": "Sealing the publication bundle",
		"post_write": "Writing the selected post", "site_import": "Importing the post",
		"page_verification": "Verifying the rendered page",
	}
	_PHASE_CODES = {
		"repository_discovery": "A1", "mirror_refresh": "A3",
		"activity_location": "A4", "evidence_assembly": "A5",
		"repository_editorial": "B", "stage5_daily_outline": "D",
		"stage6_complete_post": "E", "stage7_final_synthesis": "F",
		"publication_validation": "G1", "bundle_creation": "G2",
		"post_write": "G3", "site_import": "G4", "page_verification": "G5",
	}
	_PHASE_RESULT_LINES = frozenset({
		"repository_discovery", "mirror_refresh", "activity_location", "evidence_assembly",
	})
	def __init__(self, report_date: str, journal_path: str) -> None:
		"""Create one terminal renderer for a validated date and confined journal path."""
		self.report_date = _opaque(report_date, "Progress report date")
		self.journal_path = os.path.abspath(journal_path)
		self.console = rich.console.Console(highlight=False)
		self._clock = time.monotonic
		self._started: dict[str, float] = {}
		self._phase_elapsed: dict[str, float] = {}
		self._run_started = 0.0

	def _write(self, message: str, style: str = "") -> None:
		"""Encode plain display text at the final terminal boundary. ASVS 1.1.2."""
		self.console.print(rich.text.Text(message, style=style), soft_wrap=True)

	def announce(self) -> None:
		"""Announce durable machine output before reporting human progress."""
		self._run_started = self._clock()
		self._write(f"JSON run log: {self.journal_path}", "bold cyan")
		self._write(f"Preparing daily blog for {self.report_date}", "bold")

	def note(self, step: str, message: str, style: str = "cyan") -> None:
		"""Render one coordinator-owned human step without creating a machine event."""
		if message.endswith("..."):
			self._started[step] = self._clock()
		elif step in self._started:
			elapsed = self._clock() - self._started.pop(step)
			message += f"; completed in {format_elapsed(elapsed)}"
		self._write(f"{step} | {message}", style)

	def event(self, event: str, details: dict[str, object]) -> None:
		"""Render one validated lifecycle or editorial event."""
		if event == "daily_publication.phase_started":
			phase = str(details["phase"])
			self._started[phase] = self._clock()
			message = self._PHASE_STARTS.get(phase)
			if message:
				self._write(f"{self._PHASE_CODES[phase]} | {message}...", "cyan")
		elif event == "daily_publication.phase_completed":
			phase = str(details["phase"])
			now = self._clock()
			elapsed = now - self._started.pop(phase, now)
			if phase in self._PHASE_RESULT_LINES:
				self._phase_elapsed[phase] = elapsed
			elif phase != "publication_validation":
				self._write(
					f"{self._PHASE_CODES[phase]} | Completed in {format_elapsed(elapsed)}", "green",
				)
		elif event == "daily_publication.editorial_step_completed":
			step = str(details["step"])
			if step == "project_coverage":
				return
			code = self._STEP_CODES.get(step, step)
			label = self._STEP_LABELS.get(step, "editorial results received")
			message = f"{code} | {details['succeeded']} {label}"
			if details["failed"]:
				message += f"; {details['failed']} unavailable"
			if details["reused"]:
				message += f"; {details['reused']} reused"
			self._write(message, "green" if details["succeeded"] else "yellow")
		elif event == "daily_publication.phase_failed":
			phase = str(details["phase"])
			now = self._clock()
			duration = format_elapsed(now - self._started.get(phase, now))
			self._write(
				f"Stopped during {phase}: {details['failure_kind']} after {duration}", "bold red",
			)
		elif event == "daily_publication.run_completed":
			duration = format_elapsed(self._clock() - self._run_started)
			self._write(
				f"Published {self.report_date}: {details['site_import_status']} "
				f"({details['outcome']}); completed in {duration}",
				"bold green",
			)

	def phase_result(self, phase: str, output: object, reused: bool) -> None:
		"""Summarize one coordinator-owned phase result without affecting control flow."""
		suffix = " (reused)" if reused else ""
		if phase in self._phase_elapsed:
			suffix += f"; completed in {format_elapsed(self._phase_elapsed.pop(phase))}"
		if phase == "repository_discovery" and isinstance(output, dict):
			self.note(
				"A1",
				f"Found {len(output.get('repositories', ()))} repositories in the account roster{suffix}",
				"green",
			)
		elif phase == "mirror_refresh" and isinstance(output, list):
			unavailable = sum(
				item.get("refresh_result") == "failed"
				for item in output if isinstance(item, dict)
			)
			message = f"Checked {len(output)} repos selected from report-day commits"
			if unavailable:
				message += f"; {unavailable} unavailable"
			self.note(
				"A3",
				message + suffix, "bold green",
			)
		elif phase == "activity_location" and isinstance(output, list):
			commits = sum(len(item.get("commits", ())) for item in output if isinstance(item, dict))
			self.note("A4", f"Located {commits} exact commits across {len(output)} repos{suffix}", "green")
		elif phase == "evidence_assembly" and isinstance(output, dict):
			self.note("A5", f"Prepared {len(output.get('items', ()))} evidence items{suffix}", "green")

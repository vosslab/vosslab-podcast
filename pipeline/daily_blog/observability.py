"""Bounded, path-safe observability values for daily-publication runs."""

# Standard Library
import contextlib
import datetime
import json
import os
import re
import shutil
import stat
from collections.abc import Callable, Iterator

# local repo modules
import daily_blog.io_utils
import daily_blog.attempt_ledger
import daily_blog.recovery
import daily_blog.replication
import daily_blog.run_contracts


TERMINAL_SUMMARY_SCHEMA_VERSION = "vosslab.daily-blog.terminal-summary.v2"
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
	"terminal_fault_subtype", "terminal_fault_owner", "attempt_summary",
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
	if value["schema_version"] != TERMINAL_SUMMARY_SCHEMA_VERSION:
		raise RuntimeError("Terminal summary schema is unsupported.")
	result: dict[str, object] = {
		"schema_version": TERMINAL_SUMMARY_SCHEMA_VERSION,
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
	if type(value["attempt_summary"]) is not dict:
		raise RuntimeError("Terminal summary attempt reliability is invalid.")
	if value["attempt_summary"]:
		result["attempt_summary"] = daily_blog.attempt_ledger.AttemptReliabilitySummary.from_dict(
			value["attempt_summary"],
		).to_dict()
	else:
		result["attempt_summary"] = {}
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
		descriptor = os.open("events.jsonl", file_flags, 0o600, dir_fd=run_fd)
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


class RetentionResult:
	"""Typed, bounded result of one contained detailed-run expiry pass."""

	def __init__(self, removed: int, skipped: int, warnings: tuple[str, ...]) -> None:
		self.removed, self.skipped, self.warnings = removed, skipped, warnings


class RetentionManager:
	"""Expire validated terminal children through held date and runs descriptors."""

	def __init__(self, date_fd: int, runs_fd: int, retention_days: int | None, warning: Callable[[str], None] | None = None) -> None:
		self.date_fd = date_fd
		self.runs_fd = runs_fd
		self.retention_days = retention_days
		self.warning = warning

	def _summary_receipts(self, report_date: str) -> dict[tuple[str, str], int]:
		"""Read one exact canonical receipt index, rejecting incomplete journals."""
		receipts: dict[tuple[str, str], int] = {}
		run_ids: set[str] = set()
		flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
		with os.fdopen(os.open("summary.jsonl", flags, dir_fd=self.date_fd), "rb") as handle:
			if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
				raise RuntimeError("Terminal summary journal is invalid.")
			while raw_line := handle.readline(MAX_SUMMARY_LINE_BYTES + 2):
				if (
					not raw_line.endswith(b"\n")
					or len(raw_line) > MAX_SUMMARY_LINE_BYTES + 1
				):
					raise RuntimeError("Terminal summary journal is invalid.")
				try:
					line = raw_line[:-1].decode("ascii")
				except UnicodeDecodeError as error:
					raise RuntimeError("Terminal summary journal is invalid.") from error
				receipt = parse_terminal_summary_line(line)
				if receipt["report_date"] != report_date:
					raise RuntimeError("Terminal summary journal is invalid.")
				if receipt["run_id"] in run_ids:
					raise RuntimeError("Terminal summary journal is invalid.")
				run_ids.add(receipt["run_id"])
				key = (receipt["run_id"], receipt["terminal_record_sha256"])
				receipts[key] = receipts.get(key, 0) + 1
		return receipts

	def prune(self, report_date: str, command_started_at: str) -> RetentionResult:
		_utc_timestamp(command_started_at, "Retention command start")
		if self.retention_days is None:
			return RetentionResult(0, 0, ())
		if type(self.retention_days) is not int or self.retention_days <= 0:
			raise RuntimeError("Detailed run retention must be a positive day count.")
		if not shutil.rmtree.avoids_symlink_attacks:
			raise RuntimeError("Descriptor-safe detailed run removal is unavailable.")
		started = datetime.datetime.strptime(command_started_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.UTC)
		warnings: list[str] = []
		removed = skipped = 0
		try:
			receipts = self._summary_receipts(report_date)
		except (OSError, RuntimeError, TypeError, ValueError):
			return RetentionResult(0, 0, ("retention_skipped_invalid_summary_journal",))
		for name in os.listdir(self.runs_fd):
			try:
				if not _OPAQUE_ID_RE.fullmatch(name) or os.path.sep in name:
					raise RuntimeError("unsafe run child")
				info = os.stat(name, dir_fd=self.runs_fd, follow_symlinks=False)
				if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
					raise RuntimeError("unsafe run child")
				child_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
				with _directory_descriptor(name, child_flags, self.runs_fd) as child_fd:
					record = daily_blog.run_contracts.RunRecord.from_dict(
						read_bounded_regular_json_at(child_fd, "run_state.json", MAX_RUN_STATE_BYTES),
					)
					try:
						os.stat("pending_terminal_summary.json", dir_fd=child_fd, follow_symlinks=False)
					except FileNotFoundError:
						pass
					else:
						raise RuntimeError("terminal summary remains pending")
				if record.run_id != name or record.report_date != report_date or record.state not in {"completed", "failed"}:
					raise RuntimeError("nonterminal or mismatched run")
				record_hash = daily_blog.io_utils.hash_value(record.to_dict())
				if receipts.get((record.run_id, record_hash), 0) != 1:
					raise RuntimeError("terminal summary receipt is missing or duplicated")
				created = datetime.datetime.strptime(record.created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.UTC)
				if (started - created).days < self.retention_days:
					continue
				# The removal implementation independently opens and verifies this child
				# relative to the still-held parent descriptor before deleting it.
				info = os.stat(name, dir_fd=self.runs_fd, follow_symlinks=False)
				if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
					raise RuntimeError("unsafe run child")
				shutil.rmtree(name, dir_fd=self.runs_fd)
				removed += 1
			except (OSError, TypeError, ValueError, RuntimeError):
				skipped += 1
				if len(warnings) < 32:
					warnings.append("retention_skipped_unsafe_or_invalid_run")
		for item in warnings:
			if self.warning is not None:
				self.warning(item)
		return RetentionResult(removed, skipped, tuple(warnings))

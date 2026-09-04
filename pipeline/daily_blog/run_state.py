"""Persistent run records and inspectable per-phase artifacts."""

# Standard Library
import os
import sys
import json
import datetime
import collections.abc
import re
import stat
import contextlib
import uuid
import shutil

# local repo modules
import daily_blog.schema
import daily_blog.io_utils
import daily_blog.run_contracts
import daily_blog.replication
import daily_blog.observability


class RunStore:
	"""Own one run's mutable record until it reaches a terminal immutable state."""

	RUN_STATE_ARTIFACT = "run_state.json"
	PENDING_EDITORIAL_STEP_ARTIFACT = "pending_editorial_step.json"
	PENDING_EDITORIAL_STEP_SCHEMA = "vosslab.daily-blog.pending-editorial-step.v1"
	PENDING_TERMINAL_SUMMARY_ARTIFACT = "pending_terminal_summary.json"
	PENDING_TERMINAL_SUMMARY_SCHEMA = "vosslab.daily-blog.pending-terminal-summary.v1"
	# The retained full publication measured 60,766 direct-run bytes.  This
	# schema limit leaves over twice that observed footprint for the authoritative
	# record while preventing an unbounded durable-state parse. It is shared
	# with retention so both consumers enforce the same state envelope.
	MAX_RUN_STATE_BYTES = daily_blog.observability.MAX_RUN_STATE_BYTES
	# Journals contain one bounded JSONL payload plus a fixed replay envelope.
	MAX_PENDING_EDITORIAL_BYTES = 8192
	MAX_PENDING_TERMINAL_BYTES = 32768
	_OWNER_RE = re.compile(r"^[A-Za-z0-9-]+$")
	_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")

	EVENT_FIELDS = {
		"daily_publication.editorial_step_completed": frozenset({
			"attempted",
			"best_artifact_id",
			"disagreements",
			"failed",
			"outcome",
			"repaired",
			"reused",
			"response_chars",
			"step",
			"succeeded",
			"transition_artifact_id",
			"transition_kind",
			"transition_prior_artifact_id",
		}),
		"daily_publication.phase_completed": frozenset({"phase", "reused"}),
		"daily_publication.phase_failed": frozenset({"failure_kind", "phase"}),
		"daily_publication.phase_started": frozenset({"phase"}),
		"daily_publication.run_completed": frozenset(
			{
				"best_artifact_id",
				"bundle_sha256",
				"outcome",
				"site_import_status",
				"state",
				"verified_page_sha256",
			}
		),
		"daily_publication.run_started": frozenset({"state"}),
	}

	#============================================
	def __init__(
		self,
		output_root: str,
		owner: str,
		report_date: str,
		run_id: str,
		max_events_per_run: int | None = None,
		progress: daily_blog.observability.HumanProgress | None = None,
	) -> None:
		"""Create the report-date-owned canonical run state."""
		self._initialize_layout(output_root, owner, report_date, run_id)
		with self._layout_descriptors(create=True) as (date_fd, _, _):
			self._reset_date_state_at(date_fd)
		self.record_path = os.path.join(self.run_dir, "run_state.json")
		self.event_path = os.path.join(self.run_dir, f"runlog-{report_date}.jsonl")
		self.progress = progress
		self.pending_editorial_step_path = os.path.join(
			self.run_dir, self.PENDING_EDITORIAL_STEP_ARTIFACT,
		)
		self.pending_terminal_summary_path = os.path.join(
			self.run_dir, self.PENDING_TERMINAL_SUMMARY_ARTIFACT,
		)
		self.event_sink = daily_blog.observability.RunEventSink(report_date, run_id, max_events_per_run)

	#============================================
	@classmethod
	def reopen(
		cls,
		output_root: str,
		owner: str,
		report_date: str,
		run_id: str,
		max_events_per_run: int | None = None,
	) -> "RunStore":
		"""Reopen one existing run directory for bounded editorial reconciliation."""
		store = cls.__new__(cls)
		store._initialize_layout(output_root, owner, report_date, run_id)
		store.record_path = os.path.join(store.run_dir, cls.RUN_STATE_ARTIFACT)
		store.event_path = os.path.join(store.run_dir, f"runlog-{report_date}.jsonl")
		store.progress = None
		store.pending_editorial_step_path = os.path.join(
			store.run_dir, cls.PENDING_EDITORIAL_STEP_ARTIFACT,
		)
		store.pending_terminal_summary_path = os.path.join(
			store.run_dir, cls.PENDING_TERMINAL_SUMMARY_ARTIFACT,
		)
		store.event_sink = daily_blog.observability.RunEventSink(report_date, run_id, max_events_per_run)
		try:
			with store._layout_descriptors(create=False) as (date_fd, _, run_fd):
				try:
					os.stat(
						store.PENDING_TERMINAL_SUMMARY_ARTIFACT,
						dir_fd=run_fd,
						follow_symlinks=False,
					)
				except FileNotFoundError:
					pass
				else:
					store._finalize_summary_at(date_fd, run_fd)
		except (FileNotFoundError, NotADirectoryError, OSError) as error:
			raise RuntimeError("Daily-publication run-state directory is unavailable.") from error
		return store

	#============================================
	@classmethod
	def _validate_selectors(cls, output_root: object, owner: object, report_date: object, run_id: object) -> tuple[str, str, str, str]:
		"""Validate public filesystem selectors before constructing any path."""
		if type(output_root) is not str or not output_root.strip():
			raise RuntimeError("Daily-publication output root is invalid.")
		if type(owner) is not str or cls._OWNER_RE.fullmatch(owner) is None:
			raise RuntimeError("Daily-publication output owner is invalid.")
		if type(run_id) is not str or cls._RUN_ID_RE.fullmatch(run_id) is None:
			raise RuntimeError("Daily-publication run identity is invalid.")
		if type(report_date) is not str:
			raise RuntimeError("Daily-publication report date is invalid.")
		try:
			if datetime.date.fromisoformat(report_date).isoformat() != report_date:
				raise ValueError
		except ValueError as error:
			raise RuntimeError("Daily-publication report date is invalid.") from error
		return os.path.realpath(os.path.abspath(output_root)), owner, report_date, run_id

	#============================================
	@staticmethod
	def _require_contained(root: str, path: str) -> None:
		"""Prove a resolved path remains below the explicit canonical root."""
		try:
			if os.path.commonpath((root, os.path.realpath(path))) != root:
				raise RuntimeError("Daily-publication storage path escapes its output root.")
		except ValueError as error:
			raise RuntimeError("Daily-publication storage path escapes its output root.") from error

	#============================================
	@staticmethod
	def _require_directory(path: str) -> None:
		"""Require a direct, nonsymlinked directory component."""
		info = os.lstat(path)
		if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
			raise RuntimeError("Daily-publication storage directory is invalid.")

	#============================================
	def _initialize_layout(self, output_root: object, owner: object, report_date: object, run_id: object) -> None:
		"""Build diagnostic paths; durable selection occurs through descriptors."""
		self.output_root, self.owner, self.report_date, self.run_id = self._validate_selectors(
			output_root, owner, report_date, run_id,
		)
		self.date_dir = os.path.join(self.output_root, self.owner, "daily_blog", self.report_date)
		self.summary_path = os.path.join(self.date_dir, "summary.jsonl")
		self.run_dir = self.date_dir
		for path in (self.output_root, self.date_dir, self.run_dir):
			self._require_contained(self.output_root, path)

	#============================================
	@contextlib.contextmanager
	def _layout_descriptors(
		self, create: bool, include_run: bool = True,
	) -> collections.abc.Iterator[tuple[int, int, int | None]]:
		"""Hold the complete no-follow hierarchy for one durable operation."""
		flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
		if create:
			os.makedirs(self.output_root, mode=0o700, exist_ok=True)
		with daily_blog.observability._directory_descriptor(self.output_root, flags) as root_fd:
			with self._child_directory(root_fd, self.owner, create) as owner_fd:
				with self._child_directory(owner_fd, "daily_blog", create) as blog_fd:
					with self._child_directory(blog_fd, self.report_date, create) as date_fd:
						yield date_fd, date_fd, date_fd if include_run else None

	#============================================
	def _reset_date_state_at(self, date_fd: int) -> None:
		"""Replace direct working artifacts while preserving promoted publication bytes."""
		with os.scandir(date_fd) as entries:
			for entry in entries:
				metadata = entry.stat(follow_symlinks=False)
				if stat.S_ISREG(metadata.st_mode) and entry.name.endswith((".json", ".jsonl", ".md")):
					os.unlink(entry.name, dir_fd=date_fd)
				elif stat.S_ISLNK(metadata.st_mode):
					raise RuntimeError("Daily-publication date storage contains an unsafe link.")
		os.fsync(date_fd)

	#============================================
	@contextlib.contextmanager
	def _child_directory(
		self, parent_fd: int, name: str, create: bool,
	) -> collections.abc.Iterator[int]:
		"""Select one fixed direct child directory through its held parent."""
		if create:
			try:
				os.mkdir(name, 0o700, dir_fd=parent_fd)
			except FileExistsError:
				pass
		flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
		with daily_blog.observability._directory_descriptor(name, flags, parent_fd) as descriptor:
			yield descriptor

	#============================================
	@staticmethod
	def _direct_name(name: str) -> None:
		"""Require an internal direct-child filename."""
		if type(name) is not str or name in {"", ".", ".."} or os.path.basename(name) != name:
			raise RuntimeError("Daily-publication state filename is invalid.")

	#============================================
	def _read_regular_json_at(self, directory_fd: int, name: str, maximum_bytes: int) -> object:
		"""Read one bounded regular JSON file selected below a held descriptor."""
		self._direct_name(name)
		return daily_blog.observability.read_bounded_regular_json_at(
			directory_fd, name, maximum_bytes,
		)

	#============================================
	def _read_run_json(self, name: str, maximum_bytes: int) -> object:
		"""Read bounded state using the sole descriptor-owned selection path."""
		with self._layout_descriptors(create=False) as (_, _, run_fd):
			return self._read_regular_json_at(run_fd, name, maximum_bytes)

	#============================================
	def _atomic_write_bytes_at(self, directory_fd: int, name: str, payload: bytes) -> None:
		"""Durably replace one direct regular-file child through the held parent."""
		self._direct_name(name)
		temporary = f".{name}.{uuid.uuid4().hex}.tmp"
		try:
			# ASVS 5.3.2: create and replace only below the already held run directory.
			flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
			with os.fdopen(os.open(temporary, flags, 0o600, dir_fd=directory_fd), "wb") as handle:
				if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
					raise RuntimeError("Daily-publication temporary state file is invalid.")
				handle.write(payload)
				handle.flush()
				os.fsync(handle.fileno())
			os.replace(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
			os.fsync(directory_fd)
		except BaseException:
			try:
				os.unlink(temporary, dir_fd=directory_fd)
			except FileNotFoundError:
				pass
			raise

	#============================================
	def _atomic_write_json_at(self, directory_fd: int, name: str, value: object) -> None:
		"""Durably replace one direct JSON child through the held parent."""
		payload = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True).encode("ascii") + b"\n"
		self._atomic_write_bytes_at(directory_fd, name, payload)

	#============================================
	def _unlink_optional_at(self, directory_fd: int, name: str) -> None:
		"""Remove one known direct journal after its transaction is complete."""
		self._direct_name(name)
		try:
			os.unlink(name, dir_fd=directory_fd)
		except FileNotFoundError:
			return

	#============================================
	def derive_output_logical_path(self, path: str) -> str:
		"""Convert one contained absolute producer path into durable logical state."""
		if type(path) is not str or not os.path.isabs(path):
			raise RuntimeError("Producer path must be explicit and absolute.")
		absolute_path = os.path.abspath(path)
		try:
			if os.path.commonpath((self.output_root, absolute_path)) != self.output_root:
				raise RuntimeError("Producer path is outside the configured output root.")
		except ValueError as error:
			raise RuntimeError("Producer path is outside the configured output root.") from error
		logical_path = os.path.relpath(absolute_path, self.output_root).replace(os.sep, "/")
		return daily_blog.run_contracts.canonical_logical_path(logical_path, "producer path")

	#============================================
	def resolve_output_logical_path(self, logical_path: str) -> str:
		"""Resolve one validated durable logical path for ephemeral producer I/O."""
		logical_path = daily_blog.run_contracts.canonical_logical_path(
			logical_path, "producer path",
		)
		absolute_path = os.path.abspath(
			os.path.join(self.output_root, *logical_path.split("/")),
		)
		try:
			if os.path.commonpath((self.output_root, absolute_path)) != self.output_root:
				raise RuntimeError("Producer path is outside the configured output root.")
		except ValueError as error:
			raise RuntimeError("Producer path is outside the configured output root.") from error
		return absolute_path

	#============================================
	def _validate_event_details(self, event: str, details: dict[str, object]) -> None:
		"""Require the exact bounded fields and values for one lifecycle event."""
		if event not in self.EVENT_FIELDS:
			raise RuntimeError("Unsupported daily-publication event name.")
		legacy_editorial_fields = self.EVENT_FIELDS["daily_publication.editorial_step_completed"] - {
			"response_chars",
		}
		if (
			set(details) != self.EVENT_FIELDS[event]
			and not (
				event == "daily_publication.editorial_step_completed"
				and set(details) == legacy_editorial_fields
			)
		):
			raise RuntimeError("Daily-publication event fields do not match the event schema.")
		if "phase" in details and details["phase"] not in daily_blog.run_contracts.LEGAL_PHASES:
			raise RuntimeError("Daily-publication event phase is unsupported.")
		if "reused" in details and type(details["reused"]) is not bool:
			if event != "daily_publication.editorial_step_completed":
				raise RuntimeError("Daily-publication reused state must be Boolean.")
		if event == "daily_publication.editorial_step_completed":
			count_fields = {
				"attempted",
				"disagreements",
				"failed",
				"repaired",
				"reused",
				"succeeded",
			}
			if "response_chars" in details:
				count_fields.add("response_chars")
			if any(type(details[name]) is not int or details[name] < 0 for name in count_fields):
				raise RuntimeError("Daily-publication editorial counts are invalid.")
			if details["succeeded"] + details["failed"] != details["attempted"]:
				raise RuntimeError("Daily-publication editorial counts are inconsistent.")
			if type(details["step"]) is not str or not details["step"]:
				raise RuntimeError("Daily-publication editorial step is invalid.")
			if details["outcome"] not in daily_blog.replication.STEP_OUTCOMES:
				raise RuntimeError("Daily-publication editorial outcome is unsupported.")
			if not isinstance(details["best_artifact_id"], str):
				raise RuntimeError("Daily-publication editorial artifact identity is invalid.")
			transition_value = {
				"step": details["step"],
				"kind": details["transition_kind"],
				"artifact_id": details["transition_artifact_id"],
				"prior_artifact_id": details["transition_prior_artifact_id"],
			}
			transition_step, transition = daily_blog.run_contracts.parse_incumbent_transition(
				transition_value,
			)
			if transition_step != details["step"]:
				raise RuntimeError("Daily-publication editorial transition is invalid.")
			summary = daily_blog.replication.StepReliability(
				details["step"], details["outcome"], details["attempted"],
				details["succeeded"], details["failed"], details["reused"],
				details["repaired"], details["disagreements"],
				details["best_artifact_id"], (), response_chars=details.get("response_chars", 0),
			)
			prior_artifact_id = ""
			if type(transition) in {
				daily_blog.run_contracts.ReplaceIncumbent,
				daily_blog.run_contracts.RepairPublicationIncumbent,
			}:
				prior_artifact_id = transition.prior_artifact_id
			daily_blog.run_contracts.validate_incumbent_transition(
				summary, transition, prior_artifact_id,
			)
		if "failure_kind" in details:
			failure_kind = details["failure_kind"]
			if failure_kind not in daily_blog.run_contracts.FAILURE_KINDS:
				raise RuntimeError("Daily-publication failure kind is unsupported.")
		if "bundle_sha256" in details:
			checksum = details["bundle_sha256"]
			if (
				not isinstance(checksum, str)
				or len(checksum) != 64
				or set(checksum) - set("0123456789abcdef")
			):
				raise RuntimeError("Daily-publication bundle checksum is invalid.")
		if "best_artifact_id" in details:
			artifact_id = details["best_artifact_id"]
			if type(artifact_id) is not str:
				raise RuntimeError("Daily-publication best artifact identity is invalid.")
			if event == "daily_publication.editorial_step_completed":
				if artifact_id and (
					daily_blog.run_contracts.PUBLISHABLE_ARTIFACT_ID_RE.fullmatch(artifact_id) is None
					and daily_blog.run_contracts.RANKING_PROMOTION_ID_RE.fullmatch(artifact_id) is None
				):
					raise RuntimeError("Daily-publication editorial artifact identity is invalid.")
			elif daily_blog.run_contracts.PUBLISHABLE_ARTIFACT_ID_RE.fullmatch(artifact_id) is None:
				raise RuntimeError("Daily-publication best artifact identity is invalid.")
		if "verified_page_sha256" in details:
			page_identity = details["verified_page_sha256"]
			if (
				type(page_identity) is not str
				or len(page_identity) != 64
				or set(page_identity) - set("0123456789abcdef")
			):
				raise RuntimeError("Daily-publication rendered page identity is invalid.")
		if "site_import_status" in details:
			if details["site_import_status"] not in {"idempotent", "imported", "replaced"}:
				raise RuntimeError("Daily-publication import status is unsupported.")
		if "state" in details:
			expected_state = "completed" if event.endswith("run_completed") else "running"
			if details["state"] != expected_state:
				raise RuntimeError("Daily-publication run state does not match the event.")
		if "outcome" in details and event.endswith("run_completed"):
			if details["outcome"] not in {"succeeded", "degraded"}:
				raise RuntimeError("Daily-publication run outcome is unsupported.")

	def _event_line(self, event: str, details: dict[str, object]) -> str:
		"""Validate and serialize one lifecycle-safe publication event."""
		self._validate_event_details(event, details)
		return self.event_sink.line(event, details, self.EVENT_FIELDS[event])

	#============================================
	def _validate_event_identity(self, value: dict[str, object]) -> None:
		"""Require the bounded logical identity used by every lifecycle event."""
		artifact = value.get("run_state_artifact")
		if type(artifact) is not str or artifact != "run_state.json" or os.path.isabs(artifact):
			raise RuntimeError("Daily-publication run-state artifact identity is invalid.")

	#============================================
	def _append_event_file(self, line: str) -> None:
		"""Append one serialized event to the per-run JSONL sink."""
		with self._layout_descriptors(create=False) as (_, _, run_fd):
			self.event_sink.append_at(run_fd, line)

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
			self._write_sink_warning(self.event_sink.journal_name, error)
		try:
			if self.progress is None:
				print(line, flush=True)
			else:
				self.progress.event(event, details)
		except (OSError, ValueError) as error:
			self._write_sink_warning("stdout", error)

	#============================================
	def _append_required_event(self, event: str, details: dict[str, object]) -> None:
		"""Write an editorial completion event without best-effort downgrade.

		A coordinator cannot acknowledge an editorial step when either observable
		sink fails. This keeps the step's reported completion tied to its durable
		record transition.
		"""
		line = self._event_line(event, details)
		self._append_event_file(line)
		if self.progress is None:
			print(line, flush=True)
		else:
			self.progress.event(event, details)

	#============================================
	def _record_hash(self, record: daily_blog.run_contracts.RunRecord) -> str:
		"""Return the canonical identity of one validated authoritative record."""
		return daily_blog.io_utils.hash_value(record.to_dict())

	#============================================
	def _pending_editorial_intent(
		self,
		before: daily_blog.run_contracts.RunRecord,
		after: daily_blog.run_contracts.RunRecord,
		line: str,
	) -> dict[str, str]:
		"""Build the bounded replay intent for one record/event transition."""
		value = {
			"after_record_sha256": self._record_hash(after),
			"after_updated_at": after.updated_at,
			"before_record_sha256": self._record_hash(before),
			"event_id": daily_blog.io_utils.sha256_text(line),
			"event_line": line,
			"schema_version": self.PENDING_EDITORIAL_STEP_SCHEMA,
		}
		self._validate_pending_editorial_intent(value)
		return value

	#============================================
	def _validate_pending_editorial_intent(self, value: object) -> None:
		"""Reject unbounded, divergent, or noncanonical editorial replay intent."""
		expected = {
			"after_record_sha256", "after_updated_at", "before_record_sha256",
			"event_id", "event_line", "schema_version",
		}
		if type(value) is not dict or set(value) != expected:
			raise RuntimeError("Pending editorial intent uses unsupported fields.")
		if value["schema_version"] != self.PENDING_EDITORIAL_STEP_SCHEMA:
			raise RuntimeError("Pending editorial intent schema is unsupported.")
		for name in ("after_record_sha256", "before_record_sha256", "event_id"):
			item = value[name]
			if type(item) is not str or len(item) != 64 or set(item) - set("0123456789abcdef"):
				raise RuntimeError("Pending editorial intent identity is invalid.")
		if type(value["after_updated_at"]) is not str or not value["after_updated_at"]:
			raise RuntimeError("Pending editorial intent timestamp is invalid.")
		line = value["event_line"]
		if type(line) is not str or "\n" in line or "\r" in line:
			raise RuntimeError("Pending editorial intent event is invalid.")
		if value["event_id"] != daily_blog.io_utils.sha256_text(line):
			raise RuntimeError("Pending editorial intent event identity is invalid.")
		try:
			event_value = json.loads(line)
		except (TypeError, ValueError) as error:
			raise RuntimeError("Pending editorial intent event is invalid.") from error
		if (
			type(event_value) is not dict
			or json.dumps(event_value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) != line
			or event_value.get("event") != "daily_publication.editorial_step_completed"
			or event_value.get("report_date") != self.report_date
			or event_value.get("run_id") != self.run_id
		):
			raise RuntimeError("Pending editorial intent event is invalid.")
		details = {
			name: event_value[name]
			for name in self.EVENT_FIELDS["daily_publication.editorial_step_completed"]
			if name in event_value
		}
		self._validate_event_details("daily_publication.editorial_step_completed", details)

	#============================================
	def _load_pending_editorial_intent_at(self, run_fd: int) -> dict[str, str] | None:
		"""Load the one bounded journal entry, if a prior call needs replay."""
		try:
			value = self._read_regular_json_at(
				run_fd, self.PENDING_EDITORIAL_STEP_ARTIFACT, self.MAX_PENDING_EDITORIAL_BYTES,
			)
		except FileNotFoundError:
			return None
		try:
			self._validate_pending_editorial_intent(value)
		except (TypeError, ValueError, RuntimeError) as error:
			raise RuntimeError("Pending editorial intent could not be read.") from error
		return value

	#============================================
	def _save_pending_editorial_intent_at(self, run_fd: int, value: dict[str, str]) -> None:
		"""Persist the replay journal before changing the authoritative record."""
		self._validate_pending_editorial_intent(value)
		self._atomic_write_json_at(run_fd, self.PENDING_EDITORIAL_STEP_ARTIFACT, value)

	#============================================
	def _remove_pending_editorial_intent_at(self, run_fd: int) -> None:
		"""Retire a journal entry only after its record and event agree."""
		self._unlink_optional_at(run_fd, self.PENDING_EDITORIAL_STEP_ARTIFACT)

	#============================================
	def _append_pending_event_at(self, run_fd: int, intent: dict[str, str]) -> None:
		"""Append the journaled event once, or prove its exact prior append."""
		appended = self.event_sink.replay_editorial_at(run_fd, intent["event_line"])
		if appended:
			if self.progress is None:
				print(intent["event_line"], flush=True)
			else:
				value = json.loads(intent["event_line"])
				details = {
					name: value[name]
					for name in self.EVENT_FIELDS["daily_publication.editorial_step_completed"]
					if name in value
				}
				self.progress.event("daily_publication.editorial_step_completed", details)

	#============================================
	def _replace_record(
		self, target: daily_blog.run_contracts.RunRecord,
		source: daily_blog.run_contracts.RunRecord,
	) -> None:
		"""Synchronize the caller's exact record only after durable agreement."""
		target.__dict__.clear()
		target.__dict__.update(source.__dict__)

	#============================================
	def _validate_output_path_layouts(self, record: daily_blog.run_contracts.RunRecord) -> None:
		"""Bind durable producer references to this store's configured output root."""
		record.validate()
		if record.repository_roster:
			roster_id = record.repository_roster.get("roster_id")
			if (
				type(roster_id) is not str
				or len(roster_id) != 64
				or set(roster_id) - set("0123456789abcdef")
			):
				raise RuntimeError("Repository roster reference identity is invalid.")
			snapshot_path = daily_blog.run_contracts.canonical_logical_path(
				record.repository_roster.get("snapshot_path"), "Repository roster snapshot",
			)
			expected_snapshot_path = "/".join((
				self.owner, "daily_blog_repository_rosters", roster_id,
			))
			if snapshot_path != expected_snapshot_path:
				raise RuntimeError("Repository roster snapshot logical path does not match this store.")
		if record.publication_bundle:
			if record.report_date != self.report_date:
				raise RuntimeError("Publication bundle report date does not match this store.")
			bundle_path = daily_blog.run_contracts.canonical_logical_path(
				record.publication_bundle.get("path"), "Publication bundle",
			)
			expected_bundle_path = "/".join((
				self.owner, "daily_blog", self.report_date, "publication",
			))
			if bundle_path != expected_bundle_path:
				raise RuntimeError("Publication bundle logical path does not match this store.")

	#============================================
	def record_editorial_step(
		self,
		record: daily_blog.run_contracts.RunRecord,
		summary: daily_blog.replication.StepReliability,
		transition: daily_blog.run_contracts.IncumbentTransition,
	) -> None:
		"""Commit one exact editorial summary and its bounded event recoverably.

		The coordinator owns this seam, so route workers cannot independently mutate
		the run record or claim a completed step. Reasons are intentionally omitted
		from the event because they can contain model or provider diagnostics.
		"""
		# ASVS 1.5.2, 2.2.1, and 2.3.1: validate trusted types and state first.
		if type(record) is not daily_blog.run_contracts.RunRecord:
			raise RuntimeError("Editorial step record must be an exact RunRecord.")
		if type(summary) is not daily_blog.replication.StepReliability:
			raise RuntimeError("Editorial step summary must be an exact StepReliability.")
		if record.state != "running":
			raise RuntimeError("Terminal run records cannot accept editorial steps.")
		self._validate_output_path_layouts(record)
		summary.validate()
		transition_projection = daily_blog.run_contracts.project_incumbent_transition(
			summary, transition, record.best_artifact_id,
		)
		details = {
			"attempted": summary.attempted,
			"best_artifact_id": summary.best_artifact_id,
			"disagreements": summary.disagreements,
			"failed": summary.failed,
			"outcome": summary.outcome,
			"repaired": summary.repaired,
			"reused": summary.reused,
			"response_chars": summary.response_chars,
			"step": summary.step,
			"succeeded": summary.succeeded,
			"transition_artifact_id": transition_projection["artifact_id"],
			"transition_kind": transition_projection["kind"],
			"transition_prior_artifact_id": transition_projection["prior_artifact_id"],
		}
		# Validate before mutation so malformed event data cannot poison run state.
		self._validate_event_details("daily_publication.editorial_step_completed", details)
		before = daily_blog.run_contracts.RunRecord.from_dict(record.to_dict())
		after = daily_blog.run_contracts.RunRecord.from_dict(record.to_dict())
		with self._layout_descriptors(create=False) as (_, _, run_fd):
			pending = self._load_pending_editorial_intent_at(run_fd)
			if pending is None:
				line = self._event_line("daily_publication.editorial_step_completed", details)
				after.add_editorial_step(summary, transition)
				intent = self._pending_editorial_intent(before, after, line)
				self._save_pending_editorial_intent_at(run_fd, intent)
			else:
				intent = pending
				event_value = json.loads(intent["event_line"])
				intent_details = {
					name: event_value[name]
					for name in self.EVENT_FIELDS["daily_publication.editorial_step_completed"]
					if name in event_value
				}
				expected_details = {
					name: value for name, value in details.items() if name in intent_details
				}
				if intent_details != expected_details:
					raise RuntimeError("Pending editorial intent diverges from this step.")
				before_hash = self._record_hash(before)
				if before_hash == intent["before_record_sha256"]:
					after.add_editorial_step(summary, transition)
					after.updated_at = intent["after_updated_at"]
				elif before_hash == intent["after_record_sha256"]:
					after = before
				else:
					raise RuntimeError("Pending editorial intent diverges from run state.")
				if self._record_hash(after) != intent["after_record_sha256"]:
					raise RuntimeError("Pending editorial intent does not reproduce run state.")
			try:
				persisted = daily_blog.run_contracts.RunRecord.from_dict(
					self._read_regular_json_at(run_fd, self.RUN_STATE_ARTIFACT, self.MAX_RUN_STATE_BYTES),
				)
			except FileNotFoundError:
				persisted = None
			except (OSError, TypeError, ValueError, RuntimeError) as error:
				raise RuntimeError("Authoritative run record could not be reconciled.") from error
			if persisted is not None:
				self._validate_output_path_layouts(persisted)
				persisted_hash = self._record_hash(persisted)
				if persisted_hash not in {intent["before_record_sha256"], intent["after_record_sha256"]}:
					raise RuntimeError("Pending editorial intent diverges from durable record.")
				if persisted_hash == intent["before_record_sha256"]:
					self._atomic_write_json_at(run_fd, self.RUN_STATE_ARTIFACT, after.to_dict())
				else:
					after = persisted
			else:
				self._atomic_write_json_at(run_fd, self.RUN_STATE_ARTIFACT, after.to_dict())
			try:
				self._append_pending_event_at(run_fd, intent)
			except (OSError, ValueError):
				raise RuntimeError("Editorial step event could not be persisted.") from None
			try:
				self._remove_pending_editorial_intent_at(run_fd)
			except OSError:
				raise RuntimeError("Editorial step journal could not be cleared.") from None
		self._replace_record(record, after)

	#============================================
	def save(self, record: daily_blog.run_contracts.RunRecord) -> None:
		"""Atomically persist the authoritative typed run record."""
		if type(record) is not daily_blog.run_contracts.RunRecord:
			raise RuntimeError("Run record must be an exact RunRecord.")
		self._validate_output_path_layouts(record)
		if record.run_id != self.run_id or record.report_date != self.report_date:
			raise RuntimeError("Run record identity does not match this store.")
		with self._layout_descriptors(create=False) as (_, _, run_fd):
			self._atomic_write_json_at(run_fd, self.RUN_STATE_ARTIFACT, record.to_dict())

	#============================================
	def _terminal_summary(self, record: daily_blog.run_contracts.RunRecord) -> dict[str, object]:
		"""Project one saved terminal record into its bounded date-level receipt."""
		if type(record) is not daily_blog.run_contracts.RunRecord or record.state not in {"completed", "failed"}:
			raise RuntimeError("Terminal summary requires an exact terminal RunRecord.")
		value = record.to_dict()
		record_hash = daily_blog.io_utils.hash_value(value)
		failure = value["failure"]
		typed_fault = value["terminal_fault"]
		failure_kind = failure.get("kind", "") if value["state"] == "failed" else ""
		terminal_category = failure_kind if failure_kind in daily_blog.run_contracts.TERMINAL_FAULT_KINDS else ""
		operational_kind = "" if terminal_category else failure_kind
		fault_subtype = typed_fault.get("subtype", "") if typed_fault else ""
		fault_owner = typed_fault.get("owner", "") if typed_fault else ""
		bundle = value["publication_bundle"]
		verification = bundle.get("page_verification", {}) if type(bundle) is dict else {}
		page_sha = verification.get("rendered_page_sha256", "") if type(verification) is dict else ""
		if type(page_sha) is not str:
			page_sha = ""
		steps = [{
			"step": item["step"], "outcome": item["outcome"], "attempted": item["attempted"],
			"succeeded": item["succeeded"], "failed": item["failed"], "reused": item["reused"],
			"repaired": item["repaired"], "disagreements": item["disagreements"],
		} for item in value["editorial_steps"]]
		summary = {
			"schema_version": daily_blog.observability.TERMINAL_SUMMARY_SCHEMA,
			"summary_id": daily_blog.io_utils.sha256_text(f"{self.run_id}:{record_hash}"),
			"terminal_record_sha256": record_hash,
			"report_date": self.report_date, "run_id": self.run_id,
			"created_at": value["created_at"], "completed_at": value["completed_at"],
			"state": value["state"], "outcome": value["outcome"],
			"best_artifact_id": value["best_artifact_id"],
			"failure_phase": failure.get("phase", "") if value["state"] == "failed" else "",
			"terminal_fault_category": terminal_category,
			"operational_failure_kind": operational_kind,
			"terminal_fault_subtype": fault_subtype,
			"terminal_fault_owner": fault_owner,
			"publication_completed": bool(page_sha),
			"verified_page_sha256": page_sha,
			"incumbent_replacement_count": sum(
				transition["kind"] == "replace"
				for transition in value["editorial_transitions"]
			),
			"editorial_steps": steps,
		}
		return daily_blog.observability.validate_terminal_summary(summary)

	#============================================
	def finalize_summary(self, record: daily_blog.run_contracts.RunRecord | None = None) -> None:
		"""Durably append one terminal summary exactly once, with replay intent."""
		with self._layout_descriptors(create=False) as (date_fd, _, run_fd):
			self._finalize_summary_at(date_fd, run_fd, record)

	#============================================
	def discard_completed_working_artifacts(self) -> None:
		"""Keep terminal diagnostics while discarding successful-run working material."""
		keep = {f"runlog-{self.report_date}.jsonl", "summary.jsonl"}
		with self._layout_descriptors(create=False) as (date_fd, _, _):
			with os.scandir(date_fd) as entries:
				for entry in entries:
					if entry.name in keep:
						continue
					metadata = entry.stat(follow_symlinks=False)
					if stat.S_ISLNK(metadata.st_mode):
						raise RuntimeError("Completed run storage contains an unsafe link.")
					if stat.S_ISDIR(metadata.st_mode):
						directory_path = os.path.join(self.date_dir, entry.name)
						self._require_contained(self.output_root, directory_path)
						shutil.rmtree(directory_path)
					elif stat.S_ISREG(metadata.st_mode):
						os.unlink(entry.name, dir_fd=date_fd)
					else:
						raise RuntimeError("Completed run storage contains an unsupported entry.")
			os.fsync(date_fd)

	#============================================
	def _finalize_summary_at(
		self,
		date_fd: int,
		run_fd: int,
		record: daily_blog.run_contracts.RunRecord | None = None,
	) -> None:
		"""Finalize through the exact date/run descriptors selected by the caller."""
		try:
			persisted = daily_blog.run_contracts.RunRecord.from_dict(
				self._read_regular_json_at(run_fd, self.RUN_STATE_ARTIFACT, self.MAX_RUN_STATE_BYTES),
			)
		except (OSError, TypeError, ValueError, RuntimeError) as error:
			raise RuntimeError("Authoritative terminal run record is unavailable.") from error
		if persisted.run_id != self.run_id or persisted.report_date != self.report_date:
			raise RuntimeError("Authoritative terminal run record does not match this store.")
		persisted_hash = self._record_hash(persisted)
		if record is not None:
			if type(record) is not daily_blog.run_contracts.RunRecord:
				raise RuntimeError("Terminal summary record must be an exact RunRecord.")
			if self._record_hash(record) != persisted_hash:
				raise RuntimeError("Terminal summary record diverges from the saved run record.")
		summary = self._terminal_summary(persisted)
		line = json.dumps(summary, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
		intent = {
			"schema_version": self.PENDING_TERMINAL_SUMMARY_SCHEMA,
			"run_id": self.run_id,
			"terminal_record_sha256": summary["terminal_record_sha256"],
			"summary_id": summary["summary_id"],
			"summary_line": line,
			"summary_line_sha256": daily_blog.io_utils.sha256_text(line),
			"summary_filename": "summary.jsonl",
		}
		try:
			pending = self._read_regular_json_at(
				run_fd, self.PENDING_TERMINAL_SUMMARY_ARTIFACT, self.MAX_PENDING_TERMINAL_BYTES,
			)
		except FileNotFoundError:
			self._atomic_write_json_at(run_fd, self.PENDING_TERMINAL_SUMMARY_ARTIFACT, intent)
		else:
			if pending != intent:
				raise RuntimeError("Pending terminal summary diverges from terminal record.")
		matches = self._summary_matches_at(date_fd, line)
		if matches > 1:
			raise RuntimeError("Terminal summary is duplicated.")
		if matches == 0:
			self._append_summary_at(date_fd, line)
		self._unlink_optional_at(run_fd, self.PENDING_TERMINAL_SUMMARY_ARTIFACT)

	#============================================
	def _summary_matches_at(self, date_fd: int, line: str) -> int:
		"""Scan receipt identity through the date descriptor selected for this transaction."""
		try:
			flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
			descriptor = os.open("summary.jsonl", flags, dir_fd=date_fd)
		except FileNotFoundError:
			return 0
		except OSError as error:
			raise RuntimeError("Daily-publication summary journal is invalid.") from error
		matches = 0
		with os.fdopen(descriptor, "rb") as handle:
			if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
				raise RuntimeError("Daily-publication summary journal is invalid.")
			while raw_line := handle.readline(daily_blog.observability.MAX_SUMMARY_LINE_BYTES + 2):
				if not raw_line.endswith(b"\n") or len(raw_line) > daily_blog.observability.MAX_SUMMARY_LINE_BYTES + 1:
					raise RuntimeError("Daily-publication summary journal is invalid.")
				try:
					stored = raw_line[:-1].decode("ascii")
					parsed = daily_blog.observability.parse_terminal_summary_line(stored)
				except (UnicodeDecodeError, RuntimeError) as error:
					raise RuntimeError("Daily-publication summary journal is invalid.") from error
				if parsed["run_id"] == self.run_id:
					if stored != line:
						raise RuntimeError("Terminal summary diverges for this run identity.")
					matches += 1
		return matches

	#============================================
	def _append_summary_at(self, date_fd: int, line: str) -> None:
		"""Replace the one canonical receipt through the selected date descriptor."""
		flags = os.O_WRONLY | os.O_TRUNC | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
		with os.fdopen(os.open("summary.jsonl", flags, 0o600, dir_fd=date_fd), "wb") as handle:
			if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
				raise RuntimeError("Daily-publication summary journal is invalid.")
			handle.write((line + "\n").encode("ascii"))
			handle.flush()
			os.fsync(handle.fileno())
		os.fsync(date_fd)

	#============================================
	def write_artifact(self, name: str, value: object) -> str:
		"""Write one stable inspectable JSON artifact inside this run."""
		if os.path.basename(name) != name or not name.endswith(".json"):
			raise RuntimeError("Run artifacts must use one direct JSON filename.")
		with self._layout_descriptors(create=False) as (_, _, run_fd):
			self._atomic_write_json_at(run_fd, name, value)
		path = os.path.join(self.run_dir, name)
		return path

	#============================================
	def write_document(self, name: str, value: str) -> str:
		"""Write one stable local Markdown document inside this run."""
		if os.path.basename(name) != name or not name.endswith(".md") or type(value) is not str:
			raise RuntimeError("Run documents must use one direct Markdown filename and text value.")
		with self._layout_descriptors(create=False) as (_, _, run_fd):
			self._atomic_write_bytes_at(run_fd, name, value.encode("utf-8"))
		return os.path.join(self.run_dir, name)

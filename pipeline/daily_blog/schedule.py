"""Durable oldest-first reconciliation for scheduled daily publications."""

# Standard Library
import os
import re
import sys
import json
import datetime
import collections.abc

# local repo modules
import daily_blog.config
import daily_blog.locks
import daily_blog.io_utils
import daily_blog.orchestrator


SCHEDULE_SCHEMA_VERSION = "vosslab.daily-blog.schedule.v2"
PUBLICATION_SCHEMA_VERSION = "vosslab.daily-blog.publication.v2"
MAX_DATES_PER_ACTIVATION = 7
PUBLICATION_RECORD_FIELDS = {
	"bundle_id",
	"editorial_projection_manifest",
	"evidence_manifest",
	"generator_revision",
	"generator_run",
	"imported_at",
	"post_path",
	"release_id",
	"report_date",
	"schema_version",
	"timezone",
}


class ScheduleEventSink:
	"""Emit a schema-validated schedule trace to independent file and stdout sinks."""

	EVENT_FIELDS = {
		"daily_publication.schedule_completed": frozenset(
			{"attempted_count", "remaining", "target_date"}
		),
		"daily_publication.schedule_cursor_advanced": frozenset({"bundle_id", "report_date"}),
		"daily_publication.schedule_cursor_reconciled": frozenset(
			{"bundle_id", "cursor_date"}
		),
		"daily_publication.schedule_date_completed": frozenset({"bundle_id", "report_date"}),
		"daily_publication.schedule_date_skipped": frozenset({"bundle_id", "report_date"}),
		"daily_publication.schedule_date_started": frozenset({"report_date"}),
		"daily_publication.schedule_failed": frozenset({"error_class", "target_date"}),
		"daily_publication.schedule_started": frozenset({"target_date"}),
	}

	#============================================
	def __init__(self, config: daily_blog.config.DailyBlogConfig) -> None:
		"""Bind the durable schedule-level JSONL path."""
		self.path = schedule_event_path(config)
		self.state_path = schedule_state_path(config)

	#============================================
	def _validate_details(self, event: str, details: dict[str, object]) -> None:
		"""Require the exact bounded fields and values for one schedule event."""
		if event not in self.EVENT_FIELDS or set(details) != self.EVENT_FIELDS[event]:
			raise RuntimeError("Schedule event fields do not match a supported schema.")
		for field in ("target_date", "report_date", "cursor_date"):
			if field in details:
				value = details[field]
				if not isinstance(value, str):
					raise RuntimeError("Schedule event date must be text.")
				_parse_report_date(value, f"Schedule event {field}")
		if "bundle_id" in details:
			bundle_id = details["bundle_id"]
			if bundle_id != "" and not _is_lower_hex(bundle_id, {64}):
				raise RuntimeError("Schedule event bundle identity is invalid.")
		if "attempted_count" in details:
			count = details["attempted_count"]
			if type(count) is not int or not 0 <= count <= MAX_DATES_PER_ACTIVATION:
				raise RuntimeError("Schedule event attempted count is invalid.")
		if "remaining" in details and type(details["remaining"]) is not bool:
			raise RuntimeError("Schedule event remaining state must be Boolean.")
		if "error_class" in details:
			error_class = details["error_class"]
			if (
				not isinstance(error_class, str)
				or len(error_class) > 100
				or not error_class.isidentifier()
			):
				raise RuntimeError("Schedule event error class must be a bounded identifier.")

	#============================================
	def _event_line(self, event: str, details: dict[str, object]) -> str:
		"""Serialize one validated scheduler-safe event."""
		self._validate_details(event, details)
		value: dict[str, object] = {
			"event": event,
			"occurred_at": datetime.datetime.now(datetime.UTC).isoformat(),
			"schedule_state_path": self.state_path,
		}
		value.update(details)
		return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)

	#============================================
	def _append_event_file(self, line: str) -> None:
		"""Append one serialized event to the durable schedule JSONL sink."""
		os.makedirs(os.path.dirname(self.path), exist_ok=True)
		with open(self.path, "a", encoding="utf-8") as handle:
			handle.write(line + "\n")
			handle.flush()

	#============================================
	def _write_sink_warning(self, sink: str, error: Exception) -> None:
		"""Report a bounded sink failure without exposing raw exception text."""
		value = {
			"error_class": error.__class__.__name__,
			"event": "daily_publication.schedule_event_sink_failed",
			"sink": sink,
		}
		line = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
		try:
			sys.stderr.write(line + "\n")
			sys.stderr.flush()
		except (OSError, ValueError):
			return

	#============================================
	def append(self, event: str, details: dict[str, object]) -> None:
		"""Send one event to independent best-effort file and stdout sinks."""
		try:
			line = self._event_line(event, details)
		except (RuntimeError, TypeError, ValueError) as error:
			self._write_sink_warning("validation", error)
			return
		try:
			self._append_event_file(line)
		except (OSError, ValueError) as error:
			self._write_sink_warning("daily_blog_schedule_events.jsonl", error)
		try:
			print(line, flush=True)
		except (OSError, ValueError) as error:
			self._write_sink_warning("stdout", error)


#============================================
def _is_lower_hex(value: object, lengths: set[int]) -> bool:
	"""Return whether one value is exact lowercase hexadecimal text at an allowed length."""
	valid = (
		isinstance(value, str)
		and len(value) in lengths
		and re.fullmatch(r"[0-9a-f]+", value) is not None
	)
	return valid


#============================================
def schedule_state_path(config: daily_blog.config.DailyBlogConfig) -> str:
	"""Return the durable schedule cursor path."""
	path = os.path.join(
		os.path.abspath(config.output_root),
		config.output_owner,
		"daily_blog_schedule.json",
	)
	return path


#============================================
def schedule_lock_path(config: daily_blog.config.DailyBlogConfig) -> str:
	"""Return the single-owner schedule reconciliation lock path."""
	path = os.path.join(
		os.path.abspath(config.output_root),
		config.output_owner,
		"daily_blog_schedule.lock",
	)
	return path


#============================================
def schedule_event_path(config: daily_blog.config.DailyBlogConfig) -> str:
	"""Return the durable schedule-level event stream path."""
	path = os.path.join(
		os.path.abspath(config.output_root),
		config.output_owner,
		"daily_blog_schedule_events.jsonl",
	)
	return path


#============================================
def publication_record_path(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
) -> str:
	"""Return the publisher-owned success record for one report date."""
	path = os.path.join(
		os.path.abspath(config.daily_blog_repository),
		"data",
		"publications",
		f"{report_date}.json",
	)
	return path


#============================================
def _parse_report_date(value: str, label: str) -> datetime.date:
	"""Parse one strict ISO report date with a bounded error."""
	try:
		parsed = datetime.date.fromisoformat(value)
	except ValueError as error:
		raise RuntimeError(f"{label} must use YYYY-MM-DD format.") from error
	if parsed.isoformat() != value:
		raise RuntimeError(f"{label} must use YYYY-MM-DD format.")
	return parsed


#============================================
def _load_cursor(
	state_path: str,
	target: datetime.date,
	schedule_start_date: str,
) -> tuple[datetime.date, str]:
	"""Load the receipt-bound cursor or initialize immediately before the first target."""
	if not os.path.isfile(state_path):
		if not schedule_start_date:
			raise RuntimeError("Missing schedule cursor requires daily_blog.schedule_start_date.")
		start = _parse_report_date(schedule_start_date, "Schedule start date")
		if start > target:
			raise RuntimeError("Schedule target is earlier than daily_blog.schedule_start_date.")
		return start - datetime.timedelta(days=1), ""
	value = daily_blog.io_utils.read_json(state_path)
	if not isinstance(value, dict):
		raise RuntimeError("Daily-publication schedule state must be an object.")
	if "schema_version" not in value or value["schema_version"] != SCHEDULE_SCHEMA_VERSION:
		raise RuntimeError("Daily-publication schedule schema is unsupported.")
	if "last_completed_date" not in value or not isinstance(value["last_completed_date"], str):
		raise RuntimeError("Daily-publication schedule cursor is missing.")
	if "last_completed_bundle_id" not in value:
		raise RuntimeError("Daily-publication schedule bundle identity is missing.")
	bundle_id = value["last_completed_bundle_id"]
	if not _is_lower_hex(bundle_id, {64}):
		raise RuntimeError("Daily-publication schedule bundle identity is invalid.")
	cursor = _parse_report_date(value["last_completed_date"], "Schedule cursor")
	if cursor > target:
		raise RuntimeError("Daily-publication schedule cursor is later than the target date.")
	return cursor, bundle_id


#============================================
def _write_cursor(state_path: str, report_date: datetime.date, bundle_id: str) -> None:
	"""Atomically advance the durable cursor with its publisher receipt identity."""
	value = {
		"last_completed_bundle_id": bundle_id,
		"last_completed_date": report_date.isoformat(),
		"schema_version": SCHEDULE_SCHEMA_VERSION,
	}
	daily_blog.io_utils.atomic_write_json(state_path, value)


#============================================
def _validate_imported_at(value: object, path: str) -> None:
	"""Require the publisher's canonical whole-second UTC timestamp."""
	if not isinstance(value, str) or not value.endswith("Z"):
		raise RuntimeError(f"Publisher record imported_at is invalid: {path}")
	try:
		moment = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
	except ValueError as error:
		raise RuntimeError(f"Publisher record imported_at is invalid: {path}") from error
	canonical = moment.astimezone(datetime.timezone.utc).replace(microsecond=0)
	canonical_text = canonical.isoformat().replace("+00:00", "Z")
	if moment.microsecond or canonical_text != value:
		raise RuntimeError(f"Publisher record imported_at is invalid: {path}")


#============================================
def _validate_publication_state(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
	bundle_id: str,
	value: dict,
	path: str,
) -> None:
	"""Require one coherent v2 record, archive, post, and installed release."""
	if set(value) != PUBLICATION_RECORD_FIELDS:
		raise RuntimeError(f"Publisher record fields are unsupported: {path}")
	root = os.path.abspath(config.daily_blog_repository)
	expected_paths = {
		"evidence_manifest": f"data/publication_bundles/{bundle_id}/evidence.json",
		"editorial_projection_manifest": (
			f"data/publication_bundles/{bundle_id}/editorial_projection.json"
		),
		"post_path": f"docs/blog/posts/{report_date}.md",
	}
	for field, expected in expected_paths.items():
		if value.get(field) != expected:
			raise RuntimeError(f"Publisher record {field} is inconsistent: {path}")
	if value.get("release_id") != bundle_id:
		raise RuntimeError(f"Publisher record release identity is inconsistent: {path}")
	if value.get("timezone") != config.report_timezone:
		raise RuntimeError(f"Publisher record timezone is inconsistent: {path}")
	if not isinstance(value.get("generator_run"), str) or not value["generator_run"]:
		raise RuntimeError(f"Publisher record generator run is invalid: {path}")
	if not _is_lower_hex(value.get("generator_revision"), {64}):
		raise RuntimeError(f"Publisher record generator source fingerprint is invalid: {path}")
	_validate_imported_at(value.get("imported_at"), path)
	required_files = [
		os.path.join(root, expected_paths["evidence_manifest"]),
		os.path.join(root, expected_paths["editorial_projection_manifest"]),
		os.path.join(root, expected_paths["post_path"]),
		os.path.join(root, "data", "publication_bundles", bundle_id, "bundle.json"),
		os.path.join(root, "data", "publication_bundles", bundle_id, "post.md"),
		os.path.join(root, "generated", "releases", bundle_id, "index.html"),
	]
	if any(not os.path.isfile(required_path) for required_path in required_files):
		raise RuntimeError(f"Publisher publication state is incomplete: {path}")
	installed_post_path = os.path.join(root, expected_paths["post_path"])
	archived_post_path = os.path.join(
		root,
		"data",
		"publication_bundles",
		bundle_id,
		"post.md",
	)
	with open(installed_post_path, "rb") as handle:
		installed_post = handle.read()
	with open(archived_post_path, "rb") as handle:
		archived_post = handle.read()
	if installed_post != archived_post:
		raise RuntimeError(f"Publisher archived post does not match installed source: {path}")


#============================================
def _record_bundle_id(config: daily_blog.config.DailyBlogConfig, report_date: str) -> str | None:
	"""Return the exact bundle from one valid publisher success record, when present."""
	path = publication_record_path(config, report_date)
	if not os.path.isfile(path):
		return None
	if os.path.islink(path):
		raise RuntimeError(f"Publisher record must be one physical file: {path}")
	value = daily_blog.io_utils.read_json(path)
	if not isinstance(value, dict):
		raise RuntimeError(f"Publisher record must be an object: {path}")
	if value.get("schema_version") != PUBLICATION_SCHEMA_VERSION:
		raise RuntimeError(f"Publisher record schema is unsupported: {path}")
	if "report_date" not in value or value["report_date"] != report_date:
		raise RuntimeError(f"Publisher record date does not match its path: {path}")
	if "bundle_id" not in value:
		raise RuntimeError(f"Publisher record bundle identity is missing: {path}")
	bundle_id = value["bundle_id"]
	if not _is_lower_hex(bundle_id, {64}):
		raise RuntimeError(f"Publisher record bundle identity is invalid: {path}")
	_validate_publication_state(config, report_date, bundle_id, value, path)
	return bundle_id


#============================================
def _pending_dates(cursor: datetime.date, target: datetime.date) -> list[datetime.date]:
	"""Return one bounded oldest-first activation slice."""
	pending = []
	current = cursor + datetime.timedelta(days=1)
	while current <= target and len(pending) < MAX_DATES_PER_ACTIVATION:
		pending.append(current)
		current += datetime.timedelta(days=1)
	return pending


#============================================
def _reconcile_locked(
	config: daily_blog.config.DailyBlogConfig,
	target: datetime.date,
	events: ScheduleEventSink,
	publication_function: collections.abc.Callable[
		[daily_blog.config.DailyBlogConfig, str], tuple[str, dict]
	],
) -> tuple[list[str], bool]:
	"""Reconcile one bounded activation while the caller owns the schedule lock."""
	state_path = schedule_state_path(config)
	attempted = []
	cursor, cursor_bundle_id = _load_cursor(state_path, target, config.schedule_start_date)
	if cursor_bundle_id:
		actual_bundle_id = _record_bundle_id(config, cursor.isoformat())
		if actual_bundle_id is None:
			raise RuntimeError("Daily-publication cursor publisher record is missing.")
		if actual_bundle_id != cursor_bundle_id:
			raise RuntimeError("Daily-publication cursor bundle identity does not match publisher state.")
	events.append(
		"daily_publication.schedule_cursor_reconciled",
		{"bundle_id": cursor_bundle_id, "cursor_date": cursor.isoformat()},
	)
	for report_day in _pending_dates(cursor, target):
		report_date = report_day.isoformat()
		bundle_id = _record_bundle_id(config, report_date)
		if bundle_id is None:
			events.append("daily_publication.schedule_date_started", {"report_date": report_date})
			publication_function(config, report_date)
			attempted.append(report_date)
			bundle_id = _record_bundle_id(config, report_date)
			if bundle_id is not None:
				events.append(
					"daily_publication.schedule_date_completed",
					{"bundle_id": bundle_id, "report_date": report_date},
				)
		else:
			events.append(
				"daily_publication.schedule_date_skipped",
				{"bundle_id": bundle_id, "report_date": report_date},
			)
		if bundle_id is None:
			raise RuntimeError(
				f"Daily publication completed without a publisher record: {report_date}"
			)
		_write_cursor(state_path, report_day, bundle_id)
		events.append(
			"daily_publication.schedule_cursor_advanced",
			{"bundle_id": bundle_id, "report_date": report_date},
		)
		cursor = report_day
	remaining = cursor < target
	return attempted, remaining


#============================================
def run_scheduled_backlog(
	config: daily_blog.config.DailyBlogConfig,
	target_date: str,
	publication_function: collections.abc.Callable[
		[daily_blog.config.DailyBlogConfig, str], tuple[str, dict]
	] = daily_blog.orchestrator.run_daily_publication,
) -> tuple[list[str], bool]:
	"""Reconcile and publish a bounded oldest-first slice through one durable cursor."""
	target = _parse_report_date(target_date, "Schedule target")
	events = ScheduleEventSink(config)
	events.append("daily_publication.schedule_started", {"target_date": target_date})
	try:
		with daily_blog.locks.FileLock(schedule_lock_path(config)):
			attempted, remaining = _reconcile_locked(
				config,
				target,
				events,
				publication_function,
			)
	except Exception as error:
		events.append(
			"daily_publication.schedule_failed",
			{"error_class": error.__class__.__name__, "target_date": target_date},
		)
		raise
	events.append(
		"daily_publication.schedule_completed",
		{
			"attempted_count": len(attempted),
			"remaining": remaining,
			"target_date": target_date,
		},
	)
	return attempted, remaining

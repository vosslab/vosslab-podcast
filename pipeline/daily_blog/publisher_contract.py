"""Strict, bounded producer-side contracts for the publisher subprocess."""

# Standard Library
import json
import re

# local repo modules
import daily_blog.io_utils


IMPORT_FAILURE_SCHEMA_VERSION = "vosslab.daily-blog.import-failure.v1"
MAX_PROTOCOL_BYTES = 1024
IMPORT_FAILURE_FIELDS = frozenset({"category", "phase", "schema_version"})
IMPORT_RESULT_FIELDS = frozenset({"bundle_sha256", "report_date", "status"})
IMPORT_FAILURE_CATEGORIES = frozenset({
	"snapshot_rejected", "publication_conflict", "staged_build_failed", "commit_failed",
	"publisher_implementation_defect",
})
IMPORT_FAILURE_PHASES = frozenset({"receive", "validate", "preflight", "stage", "commit"})
IMPORT_STATUSES = frozenset({"idempotent", "imported", "replaced"})
PUBLISHER_PROTOCOL_FAILURE = "publisher_protocol_failure"
PUBLISHER_TIMEOUT = "publisher_timeout"
PUBLISHER_START_FAILURE = "publisher_start_failure"
PUBLISHER_COMMAND_CATEGORIES = IMPORT_FAILURE_CATEGORIES | frozenset({
	PUBLISHER_PROTOCOL_FAILURE, PUBLISHER_TIMEOUT, PUBLISHER_START_FAILURE,
})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


#============================================
class PublisherCommandError(RuntimeError):
	"""One safe, typed publisher subprocess outcome without foreign diagnostics."""

	#============================================
	def __init__(self, category: str, phase: str) -> None:
		"""Preserve only allowlisted operational classification at this boundary."""
		if type(category) is str and category in PUBLISHER_COMMAND_CATEGORIES and (
			type(phase) is str and phase in IMPORT_FAILURE_PHASES
		):
			safe_category = category
			safe_phase = phase
		else:
			safe_category = PUBLISHER_PROTOCOL_FAILURE
			safe_phase = "receive"
		self.category = safe_category
		self.phase = safe_phase
		message = f"Daily-blog publisher {safe_category} during {safe_phase}."
		super().__init__(message)


#============================================
def protocol_failure() -> PublisherCommandError:
	"""Return the sole classification for malformed publisher protocol data."""
	error = PublisherCommandError(PUBLISHER_PROTOCOL_FAILURE, "receive")
	return error


#============================================
def _canonical_object(contents: object) -> dict:
	"""Decode one canonical, bounded UTF-8 JSON object at the subprocess boundary."""
	# ASVS 1.5.2, 2.2.1: accept only the versioned allowlisted JSON envelope.
	if type(contents) is not bytes or not contents or len(contents) > MAX_PROTOCOL_BYTES:
		raise protocol_failure()
	try:
		text = contents.decode("utf-8")
		value = json.loads(text)
	except (UnicodeDecodeError, json.JSONDecodeError) as error:
		raise protocol_failure() from error
	if type(value) is not dict or contents != daily_blog.io_utils.stable_json_text(value).encode("utf-8"):
		raise protocol_failure()
	object_value = value
	return object_value


#============================================
def parse_import_failure(contents: object) -> PublisherCommandError:
	"""Parse only the exact text-free failure envelope emitted by the publisher."""
	value = _canonical_object(contents)
	if set(value) != IMPORT_FAILURE_FIELDS or value["schema_version"] != IMPORT_FAILURE_SCHEMA_VERSION:
		raise protocol_failure()
	if type(value["category"]) is not str or type(value["phase"]) is not str:
		raise protocol_failure()
	if value["category"] not in IMPORT_FAILURE_CATEGORIES or value["phase"] not in IMPORT_FAILURE_PHASES:
		raise protocol_failure()
	error = PublisherCommandError(value["category"], value["phase"])
	return error


#============================================
def parse_import_result(contents: object, *, report_date: str, bundle_sha256: str) -> dict:
	"""Return only a canonical import result bound to the one sealed transfer."""
	value = _canonical_object(contents)
	if set(value) != IMPORT_RESULT_FIELDS or any(type(value[key]) is not str for key in IMPORT_RESULT_FIELDS):
		raise protocol_failure()
	if (
		value["status"] not in IMPORT_STATUSES
		or value["report_date"] != report_date
		or value["bundle_sha256"] != bundle_sha256
		or SHA256_RE.fullmatch(bundle_sha256) is None
	):
		raise protocol_failure()
	result = dict(value)
	return result

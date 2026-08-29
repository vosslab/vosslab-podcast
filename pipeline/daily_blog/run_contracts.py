"""Typed, versioned contracts for durable daily-publication run state."""

# Standard Library
import dataclasses

# local repo modules
import daily_blog.io_utils


RUN_SCHEMA_VERSION = "vosslab.daily-blog.run.v4"

LEGAL_PHASES = (
	"repository_discovery",
	"mirror_refresh",
	"activity_location",
	"evidence_assembly",
	"editorial_projection",
	"author_generation",
	"candidate_validation",
	"referee_selection",
	"bundle_creation",
	"site_import",
)
PHASE_STATUSES = {"pending", "running", "completed", "failed"}
RUN_STATES = {"running", "completed", "failed"}
FAILURE_KINDS = frozenset({
	"external_resource_error",
	"invalid_input",
	"runtime_error",
	"timeout",
	"unexpected_error",
})


#============================================
def classify_exception(error: BaseException) -> str:
	"""Return one bounded diagnostic category without retaining exception text.

	ASVS 14.2.4, 16.2.5, 16.5.1: persisted diagnostics retain only the phase
	and a fixed category, never exception text that could contain credentials.
	"""
	if isinstance(error, TimeoutError):
		return "timeout"
	if isinstance(error, OSError):
		return "external_resource_error"
	if isinstance(error, (TypeError, ValueError)):
		return "invalid_input"
	if isinstance(error, RuntimeError):
		return "runtime_error"
	return "unexpected_error"


@dataclasses.dataclass
class PhaseRecord:
	"""Mutable status for one legal run phase."""

	status: str = "pending"
	started_at: str = ""
	completed_at: str = ""
	input_hash: str = ""
	output_hash: str = ""
	reused: bool = False
	failure: str = ""

	#============================================
	def to_dict(self) -> dict:
		"""Serialize one phase record."""
		value = dataclasses.asdict(self)
		return value


@dataclasses.dataclass
class RunRecord:
	"""Single authoritative, resumable run-state record."""

	run_id: str
	report_date: str
	state: str
	current_phase: str
	phases: dict[str, PhaseRecord]
	repository_roster: dict
	evidence_packet: dict
	editorial_projection: dict
	publication_bundle: dict
	failure: dict
	started_at: str
	updated_at: str
	completed_at: str
	schema_version: str = RUN_SCHEMA_VERSION

	#============================================
	@classmethod
	def create(cls, run_id: str, report_date: str) -> "RunRecord":
		"""Create a new running record with every legal phase pending."""
		now = daily_blog.io_utils.utc_now()
		phases = {name: PhaseRecord() for name in LEGAL_PHASES}
		record = cls(
			run_id=run_id,
			report_date=report_date,
			state="running",
			current_phase="",
			phases=phases,
			repository_roster={},
			evidence_packet={},
			editorial_projection={},
			publication_bundle={},
			failure={},
			started_at=now,
			updated_at=now,
			completed_at="",
		)
		return record

	#============================================
	def start_phase(self, phase: str, input_hash: str) -> None:
		"""Mark one pending phase as running."""
		if phase not in LEGAL_PHASES:
			raise RuntimeError(f"Illegal run phase: {phase}")
		record = self.phases[phase]
		if record.status != "pending":
			raise RuntimeError(f"Run phase is already owned: {phase}")
		phase_index = LEGAL_PHASES.index(phase)
		if any(self.phases[name].status != "completed" for name in LEGAL_PHASES[:phase_index]):
			raise RuntimeError(f"Run phase prerequisites are incomplete: {phase}")
		if any(self.phases[name].status != "pending" for name in LEGAL_PHASES[phase_index + 1:]):
			raise RuntimeError(f"Later run phase already has state: {phase}")
		now = daily_blog.io_utils.utc_now()
		record.status = "running"
		record.started_at = now
		record.input_hash = input_hash
		self.current_phase = phase
		self.updated_at = now

	#============================================
	def complete_phase(self, phase: str, output_hash: str, reused: bool = False) -> None:
		"""Complete the currently running phase with an output identity."""
		record = self.phases[phase]
		if self.current_phase != phase or record.status != "running":
			raise RuntimeError(f"Run phase is not running: {phase}")
		now = daily_blog.io_utils.utc_now()
		record.status = "completed"
		record.completed_at = now
		record.output_hash = output_hash
		record.reused = reused
		self.current_phase = ""
		self.updated_at = now

	#============================================
	def fail_phase(self, phase: str, failure_kind: str) -> None:
		"""Fail the currently running phase with one safe diagnostic category."""
		record = self.phases[phase]
		if self.current_phase != phase or record.status != "running":
			raise RuntimeError(f"Run phase is not running: {phase}")
		if failure_kind not in FAILURE_KINDS:
			raise RuntimeError("Run failure kind is not supported.")
		now = daily_blog.io_utils.utc_now()
		record.status = "failed"
		record.completed_at = now
		record.failure = failure_kind
		self.state = "failed"
		self.failure = {"phase": phase, "kind": failure_kind}
		self.current_phase = ""
		self.updated_at = now
		self.completed_at = now

	#============================================
	def complete(self) -> None:
		"""Mark a fully completed run immutable."""
		for phase in LEGAL_PHASES:
			if self.phases[phase].status != "completed":
				raise RuntimeError(f"Cannot complete run with unfinished phase: {phase}")
		now = daily_blog.io_utils.utc_now()
		self.state = "completed"
		self.current_phase = ""
		self.updated_at = now
		self.completed_at = now

	#============================================
	def validate(self) -> None:
		"""Reject incomplete or internally inconsistent run-state records."""
		if self.schema_version != RUN_SCHEMA_VERSION:
			raise RuntimeError("Unsupported run record schema.")
		if self.state not in RUN_STATES:
			raise RuntimeError("Invalid run state.")
		if tuple(self.phases) != LEGAL_PHASES:
			raise RuntimeError("Run record phases do not match the legal ordered phase set.")
		for phase in self.phases.values():
			if phase.status not in PHASE_STATUSES:
				raise RuntimeError("Invalid phase status.")
		running = [name for name, phase in self.phases.items() if phase.status == "running"]
		failed = [name for name, phase in self.phases.items() if phase.status == "failed"]
		if len(running) > 1 or len(failed) > 1:
			raise RuntimeError("Run record contains conflicting phase ownership.")
		if self.current_phase:
			if self.phases[self.current_phase].status != "running":
				raise RuntimeError("Current phase must be running.")
		if running != ([self.current_phase] if self.current_phase else []):
			raise RuntimeError("Running phase must match current phase.")
		if self.state == "running" and failed:
			raise RuntimeError("Running run contains a failed phase.")
		if self.state == "failed":
			if (
				not failed
				or set(self.failure) != {"phase", "kind"}
				or self.failure.get("phase") != failed[0]
				or self.failure.get("kind") not in FAILURE_KINDS
				or self.phases[failed[0]].failure != self.failure["kind"]
			):
				raise RuntimeError("Failed run requires matching failure details.")
		if self.state != "failed" and self.failure:
			raise RuntimeError("Non-failed run cannot retain failure details.")
		if self.state == "completed":
			if any(phase.status != "completed" for phase in self.phases.values()):
				raise RuntimeError("Completed run contains an unfinished phase.")
			if (
				not self.repository_roster
				or not self.evidence_packet
				or not self.editorial_projection
				or not self.publication_bundle
			):
				raise RuntimeError("Completed run requires evidence, projection, and bundle references.")
		seen_open_phase = False
		for name in LEGAL_PHASES:
			status = self.phases[name].status
			if status == "completed" and seen_open_phase:
				raise RuntimeError("Run phases do not follow legal execution order.")
			if status != "completed":
				seen_open_phase = True

	#============================================
	def to_dict(self) -> dict:
		"""Serialize and validate the complete run record."""
		self.validate()
		value = dataclasses.asdict(self)
		return value

	#============================================
	@classmethod
	def from_dict(cls, value: dict) -> "RunRecord":
		"""Deserialize and validate one run record from exact JSON object shapes."""
		# ASVS 1.5.2 and 2.2.1: reject type-confused JSON before it becomes run state.
		if type(value) is not dict:
			raise RuntimeError("Run record must be an object.")
		field_names = {field.name for field in dataclasses.fields(cls)}
		if set(value) != field_names:
			raise RuntimeError("Run record uses unsupported fields.")
		if type(value["phases"]) is not dict:
			raise RuntimeError("Run record phases must be an object.")
		if tuple(value["phases"]) != LEGAL_PHASES:
			raise RuntimeError("Run record phases do not match the legal ordered phase set.")
		phase_fields = {field.name for field in dataclasses.fields(PhaseRecord)}
		phases = {}
		for name, phase_value in value["phases"].items():
			if type(phase_value) is not dict:
				raise RuntimeError(f"Run record phase must be an object: {name}")
			if set(phase_value) != phase_fields:
				raise RuntimeError(f"Run record phase uses unsupported fields: {name}")
			if any(
				type(phase_value[field]) is not str
				for field in phase_fields - {"reused"}
			) or type(phase_value["reused"]) is not bool:
				raise RuntimeError(f"Run record phase has invalid field types: {name}")
			phases[name] = PhaseRecord(**phase_value)
		structured_fields = (
			"repository_roster",
			"evidence_packet",
			"editorial_projection",
			"publication_bundle",
			"failure",
		)
		for field in structured_fields:
			if type(value[field]) is not dict:
				raise RuntimeError(f"Run record {field} must be an object.")
		string_fields = (
			"run_id",
			"report_date",
			"state",
			"current_phase",
			"started_at",
			"updated_at",
			"completed_at",
			"schema_version",
		)
		if any(type(value[field]) is not str for field in string_fields):
			raise RuntimeError("Run record scalar fields must be strings.")
		record = cls(
			run_id=value["run_id"],
			report_date=value["report_date"],
			state=value["state"],
			current_phase=value["current_phase"],
			phases=phases,
			repository_roster=value["repository_roster"].copy(),
			evidence_packet=value["evidence_packet"].copy(),
			editorial_projection=value["editorial_projection"].copy(),
			publication_bundle=value["publication_bundle"].copy(),
			failure=value["failure"].copy(),
			started_at=value["started_at"],
			updated_at=value["updated_at"],
			completed_at=value["completed_at"],
			schema_version=value["schema_version"],
		)
		record.validate()
		return record

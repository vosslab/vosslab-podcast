"""Typed, versioned contracts for durable daily-publication run state."""

# Standard Library
import dataclasses
import datetime
import pathlib
import re

# local repo modules
import daily_blog.io_utils
import daily_blog.replication
import daily_blog.editorial
import daily_blog.publisher_contract
import daily_blog.recovery


RUN_SCHEMA_VERSION = "vosslab.daily-blog.run.v13"
UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

LEGAL_PHASES = (
	"repository_discovery",
	"mirror_refresh",
	"activity_location",
	"evidence_assembly",
	"repository_editorial",
	"stage5_daily_outline",
	"stage6_complete_post",
	"stage7_final_synthesis",
	"publication_validation",
	"bundle_creation",
	"publisher_preflight",
	"post_write",
	"site_import",
	"page_verification",
)
PHASE_STATUSES = {"pending", "running", "completed", "failed"}
RUN_STATES = {"running", "completed", "failed"}
RUN_OUTCOMES = {"pending", "succeeded", "degraded", "failed"}
LEGACY_FAILURE_KINDS = frozenset({
	"editorial_blocked",
	"external_resource_error",
	"invalid_input",
	"runtime_error",
	"timeout",
	"unexpected_error",
})
# Publisher subprocess outcomes are intentionally operational categories, not
# editorial faults.  Keep the exact protocol allowlist in the producer-owned
# contract so durable records accept only text-free boundary classifications.
PUBLISHER_FAILURE_KINDS = (
	daily_blog.publisher_contract.IMPORT_FAILURE_CATEGORIES
	| frozenset({
		daily_blog.publisher_contract.PUBLISHER_PROTOCOL_FAILURE,
		daily_blog.publisher_contract.PUBLISHER_TIMEOUT,
		daily_blog.publisher_contract.PUBLISHER_START_FAILURE,
	})
)
OPERATIONAL_FAILURE_KINDS = LEGACY_FAILURE_KINDS | PUBLISHER_FAILURE_KINDS
TERMINAL_FAULT_KINDS = frozenset(
	category.value for category in daily_blog.recovery.TerminalFaultCategory
)
FAILURE_KINDS = OPERATIONAL_FAILURE_KINDS | TERMINAL_FAULT_KINDS
PUBLISHABLE_ARTIFACT_ID_RE = re.compile(r"^artifact-[0-9a-f]{24}$")
RANKING_PROMOTION_ID_RE = re.compile(r"^ranking-promotion-[0-9a-f]{24}$")
MAX_LOGICAL_PATH_CHARS = 1024
MAX_EDITORIAL_STEP_CHARS = 256


class RunRegenerationRequiredError(RuntimeError):
	"""Signal that pre-production mutable state must be regenerated, not resumed."""

	def __init__(self, schema_version: str) -> None:
		super().__init__("Daily-publication run state requires regeneration.")
		self.schema_version = schema_version


#============================================
def classify_run_schema(value: object) -> str:
	"""Classify only the outer schema identity before any mutable-state decode.

	ASVS 1.5 and 16.1: old or malformed pre-production state is never coerced
	into current resumable state.  Sealed bundle bytes are separate immutable
	artifacts and are intentionally not opened by this classifier.
	"""
	if type(value) is not dict:
		return "invalid"
	schema_version = value.get("schema_version")
	if schema_version == RUN_SCHEMA_VERSION:
		return "current"
	if type(schema_version) is str:
		return "regenerate_required"
	return "invalid"


@dataclasses.dataclass(frozen=True)
class ObserveIncumbent:
	"""Persist a reliability observation without changing the incumbent."""


@dataclasses.dataclass(frozen=True)
class EstablishIncumbent:
	"""Persist the first eligible selected whole post."""

	artifact_id: str


@dataclasses.dataclass(frozen=True)
class ReplaceIncumbent:
	"""Persist an editorially adjudicated successor to the incumbent."""

	prior_artifact_id: str
	artifact_id: str


@dataclasses.dataclass(frozen=True)
class RepairPublicationIncumbent:
	"""Persist a publication-validation repair distinct from editorial promotion."""

	prior_artifact_id: str
	artifact_id: str


IncumbentTransition = (
	ObserveIncumbent | EstablishIncumbent | ReplaceIncumbent | RepairPublicationIncumbent
)


#============================================
def _validate_publishable_artifact_id(value: object, label: str) -> str:
	"""Return one canonical publishable artifact identity."""
	if type(value) is not str or PUBLISHABLE_ARTIFACT_ID_RE.fullmatch(value) is None:
		raise RuntimeError(f"{label} must be a canonical publishable artifact identity.")
	return value


#============================================
def validate_incumbent_transition(
	summary: daily_blog.replication.StepReliability,
	transition: IncumbentTransition,
	prior_best_artifact_id: str,
) -> str:
	"""Validate one exact transition and return its replayed incumbent identity.

	ASVS 2.2.1 and 2.3.1: the trusted record boundary accepts only exact,
	contextually valid transition types and rejects skipped or replayed promotion.
	"""
	if type(summary) is not daily_blog.replication.StepReliability:
		raise RuntimeError("Editorial transition requires an exact StepReliability.")
	if type(transition) not in {
		ObserveIncumbent,
		EstablishIncumbent,
		ReplaceIncumbent,
		RepairPublicationIncumbent,
	}:
		raise RuntimeError("Editorial transition requires one exact typed operation.")
	if type(prior_best_artifact_id) is not str:
		raise RuntimeError("Editorial transition prior incumbent must be text.")
	if prior_best_artifact_id:
		_validate_publishable_artifact_id(prior_best_artifact_id, "Editorial transition prior incumbent")
	summary.validate()
	if type(summary.step) is not str or len(summary.step) > MAX_EDITORIAL_STEP_CHARS:
		raise RuntimeError("Editorial transition summary step exceeds its bounded envelope.")
	identity = summary.best_artifact_id
	if identity and (
		PUBLISHABLE_ARTIFACT_ID_RE.fullmatch(identity) is None
		and RANKING_PROMOTION_ID_RE.fullmatch(identity) is None
	):
		raise RuntimeError("Editorial transition summary artifact identity is invalid.")
	if type(transition) is ObserveIncumbent:
		return prior_best_artifact_id
	if type(transition) is EstablishIncumbent:
		artifact_id = _validate_publishable_artifact_id(
			transition.artifact_id, "Editorial establishment artifact",
		)
		if prior_best_artifact_id or identity != artifact_id:
			raise RuntimeError("Editorial establishment does not match an empty incumbent and summary.")
		return artifact_id
	artifact_id = _validate_publishable_artifact_id(
		transition.artifact_id, "Editorial successor artifact",
	)
	prior_artifact_id = _validate_publishable_artifact_id(
		transition.prior_artifact_id, "Editorial successor predecessor",
	)
	if (
		not prior_best_artifact_id
		or prior_artifact_id != prior_best_artifact_id
		or artifact_id == prior_artifact_id
		or identity != artifact_id
	):
		raise RuntimeError("Editorial successor does not match its incumbent and summary.")
	return artifact_id


#============================================
def project_incumbent_transition(
	summary: daily_blog.replication.StepReliability,
	transition: IncumbentTransition,
	prior_best_artifact_id: str,
) -> dict[str, str]:
	"""Return the bounded durable projection for one validated transition."""
	validate_incumbent_transition(summary, transition, prior_best_artifact_id)
	if type(transition) is ObserveIncumbent:
		kind = "observe"
		artifact_id = ""
		prior_artifact_id = ""
	elif type(transition) is EstablishIncumbent:
		kind = "establish"
		artifact_id = transition.artifact_id
		prior_artifact_id = ""
	elif type(transition) is ReplaceIncumbent:
		kind = "replace"
		artifact_id = transition.artifact_id
		prior_artifact_id = transition.prior_artifact_id
	else:
		kind = "repair_publication"
		artifact_id = transition.artifact_id
		prior_artifact_id = transition.prior_artifact_id
	return {
		"step": summary.step,
		"kind": kind,
		"artifact_id": artifact_id,
		"prior_artifact_id": prior_artifact_id,
	}


#============================================
def parse_incumbent_transition(value: object) -> tuple[str, IncumbentTransition]:
	"""Parse one exact bounded durable transition projection without inference.

	ASVS 1.5.2 and 2.2.1: this allowlisted parser rejects unrecognized JSON
	shapes before they reach durable workflow state.
	"""
	if type(value) is not dict or set(value) != {
		"step", "kind", "artifact_id", "prior_artifact_id",
	} or any(type(item) is not str for item in value.values()):
		raise RuntimeError("Editorial transition uses unsupported fields.")
	step = value["step"]
	if not step or len(step) > MAX_EDITORIAL_STEP_CHARS:
		raise RuntimeError("Editorial transition step is outside its bounded envelope.")
	kind = value["kind"]
	artifact_id = value["artifact_id"]
	prior_artifact_id = value["prior_artifact_id"]
	if kind == "observe" and not artifact_id and not prior_artifact_id:
		return step, ObserveIncumbent()
	if kind == "establish" and not prior_artifact_id:
		return step, EstablishIncumbent(artifact_id)
	if kind == "replace":
		return step, ReplaceIncumbent(prior_artifact_id, artifact_id)
	if kind == "repair_publication":
		return step, RepairPublicationIncumbent(prior_artifact_id, artifact_id)
	raise RuntimeError("Editorial transition operation is unsupported.")


#============================================
def canonical_logical_path(value: object, label: str) -> str:
	"""Return one bounded canonical POSIX path suitable for durable state."""
	if type(value) is not str or not value or len(value) > MAX_LOGICAL_PATH_CHARS:
		raise RuntimeError(f"{label} must be a bounded logical POSIX path.")
	if "\\" in value:
		raise RuntimeError(f"{label} must be a canonical logical POSIX path.")
	pure = pathlib.PurePosixPath(value)
	if (
		pure.is_absolute()
		or not pure.parts
		or "" in pure.parts
		or "." in pure.parts
		or ".." in pure.parts
		or pure.as_posix() != value
	):
		raise RuntimeError(f"{label} must be a canonical logical POSIX path.")
	path = pure.as_posix()
	return path


#============================================
def classify_exception(error: BaseException) -> str:
	"""Return one bounded diagnostic category without retaining exception text.

	ASVS 14.2.4, 16.2.5, 16.5.1: persisted diagnostics retain only the phase
	and a fixed category, never exception text that could contain credentials.
	"""
	if isinstance(error, daily_blog.recovery.PipelineFaultError):
		return error.category.value
	if isinstance(error, daily_blog.publisher_contract.PublisherCommandError):
		if error.category in PUBLISHER_FAILURE_KINDS:
			return error.category
		return daily_blog.publisher_contract.PUBLISHER_PROTOCOL_FAILURE
	if isinstance(error, daily_blog.editorial.EditorialBlockedError):
		return "editorial_blocked"
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
	editorial_steps: list[dict]
	editorial_transitions: list[dict]
	best_artifact_id: str
	publication_bundle: dict
	failure: dict
	outcome: str
	created_at: str
	updated_at: str
	completed_at: str
	terminal_fault: dict
	schema_version: str = RUN_SCHEMA_VERSION

	#============================================
	@classmethod
	def create(
		cls, run_id: str, report_date: str, created_at: str | None = None,
	) -> "RunRecord":
		"""Create a new running record with every legal phase pending."""
		now = created_at if created_at is not None else daily_blog.io_utils.utc_now()
		cls._validate_utc_timestamp(now, "Run creation timestamp")
		phases = {name: PhaseRecord() for name in LEGAL_PHASES}
		record = cls(
			run_id=run_id,
			report_date=report_date,
			state="running",
			current_phase="",
			phases=phases,
			repository_roster={},
			evidence_packet={},
			editorial_steps=[],
			editorial_transitions=[],
			best_artifact_id="",
			publication_bundle={},
			failure={},
			outcome="pending",
			created_at=now,
			updated_at=now,
			completed_at="",
			terminal_fault={},
		)
		return record

	#============================================
	@staticmethod
	def _validate_utc_timestamp(value: object, label: str) -> None:
		"""Require one canonical, bounded UTC timestamp in durable run state."""
		if type(value) is not str or UTC_TIMESTAMP_RE.fullmatch(value) is None:
			raise RuntimeError(f"{label} must be a canonical UTC timestamp.")
		try:
			datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
		except ValueError as error:
			raise RuntimeError(f"{label} must be a canonical UTC timestamp.") from error

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
	def add_editorial_step(
		self,
		summary: daily_blog.replication.StepReliability,
		transition: IncumbentTransition,
	) -> None:
		"""Persist one exact typed step result and replay its incumbent effect."""
		if any(value["step"] == summary.step for value in self.editorial_steps):
			raise RuntimeError("Editorial reliability step is already recorded.")
		projection = project_incumbent_transition(summary, transition, self.best_artifact_id)
		self.editorial_steps.append(summary.to_dict())
		self.editorial_transitions.append(projection)
		self.best_artifact_id = validate_incumbent_transition(
			summary, transition, self.best_artifact_id,
		)
		if summary.outcome == "degraded":
			self.outcome = "degraded"
		self.updated_at = daily_blog.io_utils.utc_now()

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
	def fail_phase(
		self, phase: str, failure_kind: str,
		terminal_fault: daily_blog.recovery.TerminalFaultDigest | None = None,
	) -> None:
		"""Fail the currently running phase with one safe diagnostic category."""
		record = self.phases[phase]
		if self.current_phase != phase or record.status != "running":
			raise RuntimeError(f"Run phase is not running: {phase}")
		if failure_kind not in FAILURE_KINDS:
			raise RuntimeError("Run failure kind is not supported.")
		if terminal_fault is not None and (
			type(terminal_fault) is not daily_blog.recovery.TerminalFaultDigest
			or terminal_fault.category.value != failure_kind
		):
			raise RuntimeError("Run terminal fault does not match its failure category.")
		now = daily_blog.io_utils.utc_now()
		record.status = "failed"
		record.completed_at = now
		record.failure = failure_kind
		self.state = "failed"
		self.outcome = "failed"
		self.failure = {"phase": phase, "kind": failure_kind}
		self.terminal_fault = {} if terminal_fault is None else terminal_fault.to_dict()
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
		if self.outcome == "pending":
			self.outcome = "succeeded"
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
		if self.outcome not in RUN_OUTCOMES:
				raise RuntimeError("Invalid run outcome.")
		for label, value in (
			("Run creation timestamp", self.created_at),
			("Run update timestamp", self.updated_at),
		):
			self._validate_utc_timestamp(value, label)
		if self.completed_at:
			self._validate_utc_timestamp(self.completed_at, "Run completion timestamp")
		if (
			type(self.repository_roster) is dict
			and "snapshot_path" in self.repository_roster
		):
			canonical_logical_path(
				self.repository_roster["snapshot_path"],
				"Repository roster snapshot",
			)
		if (
			type(self.publication_bundle) is dict
			and "path" in self.publication_bundle
		):
			canonical_logical_path(
				self.publication_bundle["path"],
				"Publication bundle",
			)
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
		if type(self.terminal_fault) is not dict:
			raise RuntimeError("Run terminal fault must be an object.")
		if self.terminal_fault:
			fault = daily_blog.recovery.TerminalFaultDigest.from_dict(self.terminal_fault)
			if self.state != "failed" or self.failure.get("kind") != fault.category.value:
				raise RuntimeError("Run terminal fault conflicts with failure state.")
		if self.state == "failed" and self.outcome != "failed":
			raise RuntimeError("Failed run requires a failed outcome.")
		if self.state != "failed" and self.outcome == "failed":
			raise RuntimeError("Non-failed run cannot retain a failed outcome.")
		if self.state == "completed" and any(
			phase.status != "completed" for phase in self.phases.values()
		):
			raise RuntimeError("Completed run contains an unfinished phase.")
		if self.state == "completed" and self.outcome not in {"succeeded", "degraded"}:
			raise RuntimeError("Completed run requires a successful or degraded outcome.")
		if type(self.editorial_transitions) is not list:
			raise RuntimeError("Run editorial transitions must be a list.")
		steps = []
		for value in self.editorial_steps:
			summary = daily_blog.replication.StepReliability.from_dict(value)
			identity = summary.best_artifact_id
			if (
				type(identity) is not str
				or (
					identity
					and PUBLISHABLE_ARTIFACT_ID_RE.fullmatch(identity) is None
					and RANKING_PROMOTION_ID_RE.fullmatch(identity) is None
				)
			):
				raise RuntimeError("Run editorial step has invalid artifact identity.")
			steps.append(summary)
		if len({summary.step for summary in steps}) != len(steps):
			raise RuntimeError("Run record contains duplicate editorial reliability steps.")
		if len(self.editorial_transitions) != len(steps):
			raise RuntimeError("Run editorial transitions must align with every editorial summary.")
		best_artifact_id = ""
		for summary, value in zip(steps, self.editorial_transitions, strict=True):
			step, transition = parse_incumbent_transition(value)
			if step != summary.step:
				raise RuntimeError("Run editorial transition does not match its summary.")
			best_artifact_id = validate_incumbent_transition(
				summary, transition, best_artifact_id,
			)
		if self.best_artifact_id != best_artifact_id:
			raise RuntimeError("Run incumbent does not match its replayed editorial transitions.")
		if self.state == "completed":
			if (
				not self.repository_roster
				or not self.evidence_packet
				or not self.editorial_steps
				or not self.best_artifact_id
				or not self.publication_bundle
			):
				raise RuntimeError("Completed run requires evidence, editorial steps, and bundle references.")
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
		classification = classify_run_schema(value)
		if classification == "regenerate_required":
			raise RunRegenerationRequiredError(value["schema_version"])
		if classification != "current":
			raise RuntimeError("Unsupported run record schema.")
		field_names = {field.name for field in dataclasses.fields(cls)}
		if set(value) != field_names:
			raise RuntimeError("Run record uses unsupported fields.")
		if type(value["phases"]) is not dict:
			raise RuntimeError("Run record phases must be an object.")
		if set(value["phases"]) != set(LEGAL_PHASES):
			raise RuntimeError("Run record phases do not match the legal ordered phase set.")
		phase_fields = {field.name for field in dataclasses.fields(PhaseRecord)}
		phases = {}
		for name in LEGAL_PHASES:
			phase_value = value["phases"][name]
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
			"publication_bundle",
			"failure",
			"terminal_fault",
		)
		for field in structured_fields:
			if type(value[field]) is not dict:
				raise RuntimeError(f"Run record {field} must be an object.")
		if type(value["editorial_steps"]) is not list:
			raise RuntimeError("Run record editorial_steps must be a list.")
		if any(type(item) is not dict for item in value["editorial_steps"]):
			raise RuntimeError("Run record editorial steps must be objects.")
		if type(value["editorial_transitions"]) is not list:
			raise RuntimeError("Run record editorial transitions must be a list.")
		string_fields = (
			"run_id",
			"report_date",
			"state",
			"current_phase",
			"created_at",
			"updated_at",
			"completed_at",
			"best_artifact_id",
			"outcome",
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
			editorial_steps=[item.copy() for item in value["editorial_steps"]],
			editorial_transitions=[item.copy() for item in value["editorial_transitions"]],
			best_artifact_id=value["best_artifact_id"],
			publication_bundle=value["publication_bundle"].copy(),
			failure=value["failure"].copy(),
			outcome=value["outcome"],
			created_at=value["created_at"],
			updated_at=value["updated_at"],
			completed_at=value["completed_at"],
			terminal_fault=value["terminal_fault"].copy(),
			schema_version=value["schema_version"],
		)
		record.validate()
		return record

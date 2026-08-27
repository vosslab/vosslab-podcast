"""Typed, versioned contracts for the daily publication workflow."""

# Standard Library
import dataclasses
import datetime

# local repo modules
import daily_blog.io_utils


BUNDLE_SCHEMA_VERSION = "vosslab.daily-blog.bundle.v1"
EVIDENCE_SCHEMA_VERSION = "vosslab.daily-blog.evidence.v2"
RUN_SCHEMA_VERSION = "vosslab.daily-blog.run.v1"
GENERATOR_VERSION = "daily-blog-generator-v1"
PROMPT_VERSION = "daily-blog-prompts-v2"
RUBRIC_VERSION = "daily-blog-rubric-v2"

LEGAL_PHASES = (
	"mirror_refresh",
	"activity_location",
	"evidence_assembly",
	"author_generation",
	"candidate_validation",
	"referee_selection",
	"bundle_creation",
	"site_import",
)
PHASE_STATUSES = {"pending", "running", "completed", "failed"}
RUN_STATES = {"running", "completed", "failed"}
AUTHORITY_ORDER = {
	"dated_changelog": 600,
	"changed_documentation": 500,
	"diff": 400,
	"readme_context": 300,
	"screenshot": 200,
	"commit_metadata": 100,
}
AUTHORITY_LEVELS = {
	"dated_changelog": "primary_narrative",
	"changed_documentation": "strong_support",
	"diff": "technical_support",
	"readme_context": "repository_context",
	"screenshot": "visual_support",
	"commit_metadata": "locator_provenance",
}


#============================================
def utc_now() -> str:
	"""Return a stable UTC timestamp without microseconds."""
	moment = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
	text = moment.isoformat().replace("+00:00", "Z")
	return text


@dataclasses.dataclass(frozen=True)
class CommitActivity:
	"""One attributed exact Git commit inside the report day."""

	sha: str
	parents: tuple[str, ...]
	author_name: str
	author_email: str
	author_timestamp: str
	committer_timestamp: str
	message: str

	#============================================
	def to_dict(self) -> dict:
		"""Serialize the immutable commit record."""
		value = dataclasses.asdict(self)
		value["parents"] = list(self.parents)
		return value

	#============================================
	@classmethod
	def from_dict(cls, value: dict) -> "CommitActivity":
		"""Deserialize and validate one commit record."""
		required = (
			"sha",
			"parents",
			"author_name",
			"author_email",
			"author_timestamp",
			"committer_timestamp",
			"message",
		)
		for key in required:
			if key not in value:
				raise RuntimeError(f"Commit activity is missing {key}.")
		commit = cls(
			sha=str(value["sha"]),
			parents=tuple(str(item) for item in value["parents"]),
			author_name=str(value["author_name"]),
			author_email=str(value["author_email"]),
			author_timestamp=str(value["author_timestamp"]),
			committer_timestamp=str(value["committer_timestamp"]),
			message=str(value["message"]),
		)
		return commit


@dataclasses.dataclass(frozen=True)
class RevisionRange:
	"""One exact parent-to-commit evidence boundary."""

	base_commit: str
	final_commit: str

	#============================================
	def to_dict(self) -> dict:
		"""Serialize one exact revision boundary."""
		return dataclasses.asdict(self)

	#============================================
	@classmethod
	def from_dict(cls, value: dict) -> "RevisionRange":
		"""Deserialize one exact revision boundary."""
		for key in ("base_commit", "final_commit"):
			if key not in value:
				raise RuntimeError(f"Revision range is missing {key}.")
		range_value = cls(
			base_commit=str(value["base_commit"]),
			final_commit=str(value["final_commit"]),
		)
		if not range_value.final_commit:
			raise RuntimeError("Revision range requires a final commit.")
		return range_value


@dataclasses.dataclass(frozen=True)
class RepositoryActivity:
	"""Attributed activity, exact parent ranges, and branch-tip snapshots."""

	repository: str
	repository_url: str
	cache_path: str
	default_revision: str
	commits: tuple[CommitActivity, ...]
	revision_ranges: tuple[RevisionRange, ...]
	snapshot_commits: tuple[str, ...]

	#============================================
	def to_dict(self) -> dict:
		"""Serialize one repository activity record."""
		value = dataclasses.asdict(self)
		value["commits"] = [commit.to_dict() for commit in self.commits]
		value["revision_ranges"] = [item.to_dict() for item in self.revision_ranges]
		value["snapshot_commits"] = list(self.snapshot_commits)
		return value

	#============================================
	@classmethod
	def from_dict(cls, value: dict) -> "RepositoryActivity":
		"""Deserialize and validate one repository activity record."""
		required = (
			"repository",
			"repository_url",
			"cache_path",
			"default_revision",
			"commits",
			"revision_ranges",
			"snapshot_commits",
		)
		for key in required:
			if key not in value:
				raise RuntimeError(f"Repository activity is missing {key}.")
		commits = tuple(CommitActivity.from_dict(item) for item in value["commits"])
		if not commits:
			raise RuntimeError("Repository activity requires at least one attributed commit.")
		ranges = tuple(RevisionRange.from_dict(item) for item in value["revision_ranges"])
		if not ranges:
			raise RuntimeError("Repository activity requires exact revision ranges.")
		snapshot_commits = tuple(str(item) for item in value["snapshot_commits"])
		if not snapshot_commits or len(set(snapshot_commits)) != len(snapshot_commits):
			raise RuntimeError("Repository activity requires unique snapshot commits.")
		commits_by_id = {commit.sha: commit for commit in commits}
		if len(commits_by_id) != len(commits):
			raise RuntimeError("Repository activity contains duplicate commits.")
		expected_ranges = {
			(base_commit, commit.sha)
			for commit in commits
			for base_commit in (commit.parents or ("",))
		}
		actual_ranges = {(item.base_commit, item.final_commit) for item in ranges}
		if len(actual_ranges) != len(ranges) or actual_ranges != expected_ranges:
			raise RuntimeError("Repository activity revision ranges do not match commit parents.")
		if any(commit not in commits_by_id for commit in snapshot_commits):
			raise RuntimeError("Repository activity snapshot commit is not attributed.")
		activity = cls(
			repository=str(value["repository"]),
			repository_url=str(value["repository_url"]),
			cache_path=str(value["cache_path"]),
			default_revision=str(value["default_revision"]),
			commits=commits,
			revision_ranges=ranges,
			snapshot_commits=snapshot_commits,
		)
		return activity


@dataclasses.dataclass(frozen=True)
class EvidenceItem:
	"""One authority-ranked evidence item with exact Git provenance."""

	evidence_id: str
	kind: str
	authority_level: str
	authority_rank: int
	repository: str
	commit: str
	path: str
	blob_hash: str
	content: str
	content_hash: str
	acquisition_source: str
	truncated: bool = False
	asset_path: str = ""
	publish_path: str = ""

	#============================================
	def to_dict(self) -> dict:
		"""Serialize one immutable evidence item."""
		value = dataclasses.asdict(self)
		return value

	#============================================
	@classmethod
	def create(
		cls,
		kind: str,
		repository: str,
		commit: str,
		path: str,
		blob_hash: str,
		content: str,
		acquisition_source: str,
		truncated: bool = False,
		asset_path: str = "",
		publish_path: str = "",
	) -> "EvidenceItem":
		"""Create an evidence item with deterministic identity and authority."""
		if kind not in AUTHORITY_ORDER:
			raise RuntimeError(f"Unsupported evidence kind: {kind}")
		identity_value = {
			"kind": kind,
			"repository": repository,
			"commit": commit,
			"path": path,
			"blob_hash": blob_hash,
			"content_hash": daily_blog.io_utils.sha256_text(content),
		}
		evidence_id = "ev-" + daily_blog.io_utils.hash_value(identity_value)[:16]
		item = cls(
			evidence_id=evidence_id,
			kind=kind,
			authority_level=AUTHORITY_LEVELS[kind],
			authority_rank=AUTHORITY_ORDER[kind],
			repository=repository,
			commit=commit,
			path=path,
			blob_hash=blob_hash,
			content=content,
			content_hash=daily_blog.io_utils.sha256_text(content),
			acquisition_source=acquisition_source,
			truncated=truncated,
			asset_path=asset_path,
			publish_path=publish_path,
		)
		return item

	#============================================
	@classmethod
	def from_dict(cls, value: dict) -> "EvidenceItem":
		"""Deserialize and validate one evidence item."""
		field_names = {field.name for field in dataclasses.fields(cls)}
		for key in field_names:
			if key not in value:
				raise RuntimeError(f"Evidence item is missing {key}.")
		item = cls(**{key: value[key] for key in field_names})
		if item.kind not in AUTHORITY_ORDER:
			raise RuntimeError(f"Unsupported evidence kind: {item.kind}")
		if item.authority_level != AUTHORITY_LEVELS[item.kind]:
			raise RuntimeError("Evidence authority level does not match its kind.")
		if item.authority_rank != AUTHORITY_ORDER[item.kind]:
			raise RuntimeError("Evidence authority rank does not match its kind.")
		if type(item.truncated) is not bool:
			raise RuntimeError("Evidence truncation state must be Boolean.")
		if item.content_hash != daily_blog.io_utils.sha256_text(item.content):
			raise RuntimeError("Evidence content hash does not match its content.")
		expected = cls.create(
			item.kind,
			item.repository,
			item.commit,
			item.path,
			item.blob_hash,
			item.content,
			item.acquisition_source,
			item.truncated,
			item.asset_path,
			item.publish_path,
		)
		if item.evidence_id != expected.evidence_id:
			raise RuntimeError("Evidence identity does not match its provenance.")
		return item


@dataclasses.dataclass(frozen=True)
class EvidencePacket:
	"""Immutable ordered evidence packet shared by both author roles."""

	report_date: str
	timezone: str
	complete: bool
	budgets: dict
	mirrors: tuple[dict, ...]
	activity: tuple[RepositoryActivity, ...]
	items: tuple[EvidenceItem, ...]
	packet_id: str
	schema_version: str = EVIDENCE_SCHEMA_VERSION

	#============================================
	def content_dict(self) -> dict:
		"""Return packet content whose hash defines packet identity."""
		value = {
			"schema_version": self.schema_version,
			"report_date": self.report_date,
			"timezone": self.timezone,
			"complete": self.complete,
			"budgets": self.budgets,
			"mirrors": list(self.mirrors),
			"activity": [item.to_dict() for item in self.activity],
			"items": [item.to_dict() for item in self.items],
		}
		return value

	#============================================
	def to_dict(self) -> dict:
		"""Serialize the complete packet including its content identity."""
		value = self.content_dict()
		value["packet_id"] = self.packet_id
		return value

	#============================================
	@classmethod
	def create(
		cls,
		report_date: str,
		timezone_name: str,
		complete: bool,
		budgets: dict,
		mirrors: list[dict],
		activity: list[RepositoryActivity],
		items: list[EvidenceItem],
	) -> "EvidencePacket":
		"""Create one authority-ordered packet and compute its immutable identity."""
		ordered = sorted(
			items,
			key=lambda item: (
				-item.authority_rank,
				item.repository.casefold(),
				item.path.casefold(),
				item.evidence_id,
			),
		)
		packet = cls(
			report_date=report_date,
			timezone=timezone_name,
			complete=complete,
			budgets=dict(budgets),
			mirrors=tuple(mirrors),
			activity=tuple(activity),
			items=tuple(ordered),
			packet_id="",
		)
		packet_id = daily_blog.io_utils.hash_value(packet.content_dict())
		packet = dataclasses.replace(packet, packet_id=packet_id)
		return packet

	#============================================
	@classmethod
	def from_dict(cls, value: dict) -> "EvidencePacket":
		"""Deserialize and verify an evidence packet and its identity."""
		if value.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
			raise RuntimeError("Unsupported evidence packet schema.")
		if type(value.get("complete")) is not bool:
			raise RuntimeError("Evidence packet completeness must be Boolean.")
		if not isinstance(value.get("budgets"), dict):
			raise RuntimeError("Evidence packet budgets must be an object.")
		if not isinstance(value.get("mirrors"), list):
			raise RuntimeError("Evidence packet mirrors must be a list.")
		if not isinstance(value.get("activity"), list):
			raise RuntimeError("Evidence packet activity must be a list.")
		if not isinstance(value.get("items"), list):
			raise RuntimeError("Evidence packet items must be a list.")
		activity = [RepositoryActivity.from_dict(item) for item in value["activity"]]
		items = [EvidenceItem.from_dict(item) for item in value["items"]]
		packet = cls.create(
			str(value["report_date"]),
			str(value["timezone"]),
			value["complete"],
			dict(value["budgets"]),
			list(value["mirrors"]),
			activity,
			items,
		)
		if packet.packet_id != value.get("packet_id"):
			raise RuntimeError("Evidence packet identity does not match its content.")
		return packet


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
	evidence_packet: dict
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
		now = utc_now()
		phases = {name: PhaseRecord() for name in LEGAL_PHASES}
		record = cls(
			run_id=run_id,
			report_date=report_date,
			state="running",
			current_phase="",
			phases=phases,
			evidence_packet={},
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
		now = utc_now()
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
		now = utc_now()
		record.status = "completed"
		record.completed_at = now
		record.output_hash = output_hash
		record.reused = reused
		self.current_phase = ""
		self.updated_at = now

	#============================================
	def fail_phase(self, phase: str, failure_kind: str, message: str) -> None:
		"""Fail the currently running phase with inspectable bounded details."""
		record = self.phases[phase]
		if self.current_phase != phase or record.status != "running":
			raise RuntimeError(f"Run phase is not running: {phase}")
		now = utc_now()
		record.status = "failed"
		record.completed_at = now
		record.failure = failure_kind
		self.state = "failed"
		self.failure = {"phase": phase, "kind": failure_kind, "message": message[:2000]}
		self.current_phase = ""
		self.updated_at = now
		self.completed_at = now

	#============================================
	def complete(self) -> None:
		"""Mark a fully completed run immutable."""
		for phase in LEGAL_PHASES:
			if self.phases[phase].status != "completed":
				raise RuntimeError(f"Cannot complete run with unfinished phase: {phase}")
		now = utc_now()
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
			if not failed or self.failure.get("phase") != failed[0]:
				raise RuntimeError("Failed run requires matching failure details.")
		if self.state == "completed":
			if any(phase.status != "completed" for phase in self.phases.values()):
				raise RuntimeError("Completed run contains an unfinished phase.")
			if not self.evidence_packet or not self.publication_bundle:
				raise RuntimeError("Completed run requires evidence and bundle references.")
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
		"""Deserialize and validate one run record."""
		phases = {
			name: PhaseRecord(**phase_value)
			for name, phase_value in value["phases"].items()
		}
		record = cls(
			run_id=str(value["run_id"]),
			report_date=str(value["report_date"]),
			state=str(value["state"]),
			current_phase=str(value["current_phase"]),
			phases=phases,
			evidence_packet=dict(value["evidence_packet"]),
			publication_bundle=dict(value["publication_bundle"]),
			failure=dict(value["failure"]),
			started_at=str(value["started_at"]),
			updated_at=str(value["updated_at"]),
			completed_at=str(value["completed_at"]),
			schema_version=str(value["schema_version"]),
		)
		record.validate()
		return record

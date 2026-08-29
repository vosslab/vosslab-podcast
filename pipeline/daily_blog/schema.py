"""Typed, versioned contracts for the daily publication workflow."""

# Standard Library
import dataclasses
import collections.abc

# local repo modules
import daily_blog.io_utils
import daily_blog.json_contracts
import daily_blog.repository_contracts


BUNDLE_SCHEMA_VERSION = "vosslab.daily-blog.bundle.v4"
EVIDENCE_SCHEMA_VERSION = "vosslab.daily-blog.evidence.v4"
PROJECTION_SCHEMA_VERSION = "vosslab.daily-blog.editorial-projection.v2"
GENERATOR_VERSION = "daily-blog-generator-v2"
PROMPT_VERSION = "daily-blog-prompts-v3"
RUBRIC_VERSION = "daily-blog-rubric-v3"

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
def validate_site_import_result(value: object, bundle_sha256: str, report_date: str) -> dict:
	"""Validate the publisher receipt before completing the external-import phase."""
	if not isinstance(value, dict):
		raise RuntimeError("Site importer result must be an object.")
	for key in ("status", "bundle_sha256", "report_date"):
		if key not in value:
			raise RuntimeError(f"Site importer result is missing {key}.")
	if value["status"] not in {"idempotent", "imported", "replaced"}:
		raise RuntimeError("Site importer returned an unsupported status.")
	if value["bundle_sha256"] != bundle_sha256:
		raise RuntimeError("Site importer bundle checksum does not match the requested bundle.")
	if value["report_date"] != report_date:
		raise RuntimeError("Site importer report date does not match the requested date.")
	return value


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
	is_fork: bool
	lifecycle_events: tuple[daily_blog.repository_contracts.RepositoryLifecycleEvent, ...]

	#============================================
	def to_dict(self) -> dict:
		"""Serialize one repository activity record."""
		value = dataclasses.asdict(self)
		value["commits"] = [commit.to_dict() for commit in self.commits]
		value["revision_ranges"] = [item.to_dict() for item in self.revision_ranges]
		value["snapshot_commits"] = list(self.snapshot_commits)
		value["lifecycle_events"] = [item.to_dict() for item in self.lifecycle_events]
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
			"is_fork",
			"lifecycle_events",
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
		if type(value["is_fork"]) is not bool:
			raise RuntimeError("Repository activity fork state must be Boolean.")
		if not isinstance(value["lifecycle_events"], list):
			raise RuntimeError("Repository activity lifecycle events must be a list.")
		lifecycle_events = tuple(
			daily_blog.repository_contracts.RepositoryLifecycleEvent.from_dict(item)
			for item in value["lifecycle_events"]
		)
		if len(lifecycle_events) != 1:
			raise RuntimeError("Repository activity requires one creation lifecycle event.")
		activity = cls(
			repository=str(value["repository"]),
			repository_url=str(value["repository_url"]),
			cache_path=str(value["cache_path"]),
			default_revision=str(value["default_revision"]),
			commits=commits,
			revision_ranges=ranges,
			snapshot_commits=snapshot_commits,
			is_fork=value["is_fork"],
			lifecycle_events=lifecycle_events,
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
	"""Immutable authoritative evidence packet retained without editorial reduction."""

	report_date: str
	timezone: str
	complete: bool
	collection_limits: daily_blog.json_contracts.FrozenMapping
	mirrors: tuple[daily_blog.json_contracts.FrozenMapping, ...]
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
			"collection_limits": self.collection_limits.to_dict(),
			"mirrors": [mirror.to_dict() for mirror in self.mirrors],
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
		collection_limits: collections.abc.Mapping[str, object],
		mirrors: (
			list[collections.abc.Mapping[str, object]]
			| tuple[collections.abc.Mapping[str, object], ...]
		),
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
			collection_limits=daily_blog.json_contracts.FrozenMapping.create(collection_limits),
			mirrors=tuple(
				daily_blog.json_contracts.FrozenMapping.create(mirror)
				for mirror in mirrors
			),
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
		if not isinstance(value.get("collection_limits"), dict):
			raise RuntimeError("Evidence packet collection_limits must be an object.")
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
			dict(value["collection_limits"]),
			list(value["mirrors"]),
			activity,
			items,
		)
		if packet.packet_id != value.get("packet_id"):
			raise RuntimeError("Evidence packet identity does not match its content.")
		return packet


@dataclasses.dataclass(frozen=True)
class RepositoryCard:
	"""Compact immutable activity context retained for every active repository."""

	repository: str
	repository_url: str
	commit_count: int
	commit_shas: tuple[str, ...]
	commit_subjects: tuple[str, ...]
	created_at: str
	created_in_report_window: bool
	is_fork: bool
	story_signals: tuple[str, ...]

	#============================================
	def to_dict(self) -> dict:
		"""Serialize one compact repository card."""
		value = dataclasses.asdict(self)
		value["commit_shas"] = list(self.commit_shas)
		value["commit_subjects"] = list(self.commit_subjects)
		value["story_signals"] = list(self.story_signals)
		return value

	#============================================
	@classmethod
	def from_dict(cls, value: dict) -> "RepositoryCard":
		"""Deserialize and validate one repository card."""
		required = (
			"repository",
			"repository_url",
			"commit_count",
			"commit_shas",
			"commit_subjects",
			"created_at",
			"created_in_report_window",
			"is_fork",
			"story_signals",
		)
		for key in required:
			if key not in value:
				raise RuntimeError(f"Repository card is missing {key}.")
		if type(value["commit_count"]) is not int:
			raise RuntimeError("Repository card commit count must be an integer.")
		if not isinstance(value["commit_shas"], list):
			raise RuntimeError("Repository card commit IDs must be a list.")
		if not isinstance(value["commit_subjects"], list):
			raise RuntimeError("Repository card commit subjects must be a list.")
		if type(value["created_in_report_window"]) is not bool:
			raise RuntimeError("Repository card creation-window state must be Boolean.")
		if type(value["is_fork"]) is not bool:
			raise RuntimeError("Repository card fork state must be Boolean.")
		if not isinstance(value["story_signals"], list):
			raise RuntimeError("Repository card story signals must be a list.")
		card = cls(
			repository=str(value["repository"]),
			repository_url=str(value["repository_url"]),
			commit_count=value["commit_count"],
			commit_shas=tuple(str(item) for item in value["commit_shas"]),
			commit_subjects=tuple(str(item) for item in value["commit_subjects"]),
			created_at=daily_blog.repository_contracts.canonical_utc_timestamp(
				value["created_at"], "Repository card creation time"
			),
			created_in_report_window=value["created_in_report_window"],
			is_fork=value["is_fork"],
			story_signals=tuple(str(item) for item in value["story_signals"]),
		)
		if not card.repository or card.commit_count <= 0:
			raise RuntimeError("Repository card requires active repository identity.")
		if card.commit_count < len(card.commit_shas):
			raise RuntimeError("Repository card includes more commit IDs than recorded activity.")
		if len(card.commit_shas) != len(card.commit_subjects):
			raise RuntimeError("Repository card commit IDs and subjects do not align.")
		expected_signals = (
			("new_source_repository",)
			if card.created_in_report_window and not card.is_fork
			else ()
		)
		if card.story_signals != expected_signals:
			raise RuntimeError("Repository card story signals do not match lifecycle evidence.")
		return card


@dataclasses.dataclass(frozen=True)
class EvidenceExcerpt:
	"""One exact immutable slice of an authoritative evidence item."""

	excerpt_id: str
	evidence_id: str
	repository: str
	kind: str
	authority_level: str
	authority_rank: int
	commit: str
	path: str
	start: int
	end: int
	source_content_hash: str
	content_hash: str
	content: str

	#============================================
	def identity_dict(self) -> dict:
		"""Return the exact slice fields that define excerpt identity."""
		value = dataclasses.asdict(self)
		value.pop("excerpt_id")
		return value

	#============================================
	def to_dict(self) -> dict:
		"""Serialize one exact evidence slice."""
		value = dataclasses.asdict(self)
		return value

	#============================================
	@classmethod
	def create(
		cls,
		item: EvidenceItem,
		start: int,
		end: int,
	) -> "EvidenceExcerpt":
		"""Create one identity-bound exact source slice."""
		if start < 0 or end <= start or end > len(item.content):
			raise RuntimeError("Evidence excerpt offsets are outside the source item.")
		content = item.content[start:end]
		excerpt = cls(
			excerpt_id="",
			evidence_id=item.evidence_id,
			repository=item.repository,
			kind=item.kind,
			authority_level=item.authority_level,
			authority_rank=item.authority_rank,
			commit=item.commit,
			path=item.path,
			start=start,
			end=end,
			source_content_hash=item.content_hash,
			content_hash=daily_blog.io_utils.sha256_text(content),
			content=content,
		)
		excerpt_id = "ex-" + daily_blog.io_utils.hash_value(excerpt.identity_dict())[:16]
		return dataclasses.replace(excerpt, excerpt_id=excerpt_id)

	#============================================
	@classmethod
	def from_dict(cls, value: dict) -> "EvidenceExcerpt":
		"""Deserialize and validate one exact evidence slice."""
		field_names = {field.name for field in dataclasses.fields(cls)}
		for key in field_names:
			if key not in value:
				raise RuntimeError(f"Evidence excerpt is missing {key}.")
		if type(value["authority_rank"]) is not int:
			raise RuntimeError("Evidence excerpt authority rank must be an integer.")
		if type(value["start"]) is not int or type(value["end"]) is not int:
			raise RuntimeError("Evidence excerpt offsets must be integers.")
		excerpt = cls(**{key: value[key] for key in field_names})
		if excerpt.kind not in AUTHORITY_ORDER:
			raise RuntimeError("Evidence excerpt kind is unsupported.")
		if excerpt.authority_level != AUTHORITY_LEVELS[excerpt.kind]:
			raise RuntimeError("Evidence excerpt authority level does not match its kind.")
		if excerpt.authority_rank != AUTHORITY_ORDER[excerpt.kind]:
			raise RuntimeError("Evidence excerpt authority rank does not match its kind.")
		if excerpt.start < 0 or excerpt.end <= excerpt.start:
			raise RuntimeError("Evidence excerpt offsets are invalid.")
		if excerpt.end - excerpt.start != len(excerpt.content):
			raise RuntimeError("Evidence excerpt offsets do not match its content length.")
		if excerpt.content_hash != daily_blog.io_utils.sha256_text(excerpt.content):
			raise RuntimeError("Evidence excerpt content hash does not match its content.")
		expected_id = "ex-" + daily_blog.io_utils.hash_value(excerpt.identity_dict())[:16]
		if excerpt.excerpt_id != expected_id:
			raise RuntimeError("Evidence excerpt identity does not match its exact slice.")
		return excerpt


@dataclasses.dataclass(frozen=True)
class EditorialProjection:
	"""Versioned immutable context projection derived from one evidence packet."""

	packet_id: str
	report_date: str
	timezone: str
	projection_limits: daily_blog.json_contracts.FrozenMapping
	repositories: tuple[RepositoryCard, ...]
	excerpts: tuple[EvidenceExcerpt, ...]
	projection_id: str
	schema_version: str = PROJECTION_SCHEMA_VERSION

	#============================================
	def content_dict(self) -> dict:
		"""Return projection content whose canonical hash defines its identity."""
		value = {
			"schema_version": self.schema_version,
			"packet_id": self.packet_id,
			"report_date": self.report_date,
			"timezone": self.timezone,
			"projection_limits": self.projection_limits.to_dict(),
			"repositories": [card.to_dict() for card in self.repositories],
			"excerpts": [excerpt.to_dict() for excerpt in self.excerpts],
		}
		return value

	#============================================
	def to_dict(self) -> dict:
		"""Serialize the complete projection including its immutable identity."""
		value = self.content_dict()
		value["projection_id"] = self.projection_id
		return value

	#============================================
	def render_context(self, evidence_ids: set[str] | None = None) -> str:
		"""Render bounded JSON while retaining every repository card."""
		excerpts = self.excerpts
		if evidence_ids is not None:
			excerpts = tuple(
				excerpt for excerpt in excerpts if excerpt.evidence_id in evidence_ids
			)
		value = {
			"schema_version": self.schema_version,
			"projection_id": self.projection_id,
			"packet_id": self.packet_id,
			"report_date": self.report_date,
			"timezone": self.timezone,
			"authority_order": list(AUTHORITY_ORDER),
			"repositories": [card.to_dict() for card in self.repositories],
			"excerpts": [excerpt.to_dict() for excerpt in excerpts],
		}
		text = daily_blog.io_utils.canonical_json_bytes(value).decode("utf-8")
		limit = self.projection_limits["context_chars"]
		if type(limit) is not int:
			raise RuntimeError("Editorial projection context limit must be an integer.")
		if len(text) > limit:
			raise RuntimeError(
				f"Editorial projection context requires {len(text)} characters "
				+ f"and exceeds its {limit} limit."
			)
		return text

	#============================================
	@classmethod
	def create(
		cls,
		packet_id: str,
		report_date: str,
		timezone_name: str,
		projection_limits: collections.abc.Mapping[str, object],
		repositories: list[RepositoryCard],
		excerpts: list[EvidenceExcerpt],
	) -> "EditorialProjection":
		"""Create one immutable projection and compute its canonical identity."""
		projection = cls(
			packet_id=packet_id,
			report_date=report_date,
			timezone=timezone_name,
			projection_limits=daily_blog.json_contracts.FrozenMapping.create(projection_limits),
			repositories=tuple(repositories),
			excerpts=tuple(excerpts),
			projection_id="",
		)
		projection_id = daily_blog.io_utils.hash_value(projection.content_dict())
		return dataclasses.replace(projection, projection_id=projection_id)

	#============================================
	@classmethod
	def from_dict(cls, value: dict) -> "EditorialProjection":
		"""Deserialize and verify one immutable projection."""
		if value.get("schema_version") != PROJECTION_SCHEMA_VERSION:
			raise RuntimeError("Unsupported editorial projection schema.")
		if not isinstance(value.get("projection_limits"), dict):
			raise RuntimeError("Editorial projection limits must be an object.")
		if set(value["projection_limits"]) != {
			"commit_subject_chars",
			"context_chars",
			"excerpt_chars",
		}:
			raise RuntimeError("Editorial projection limits use unsupported fields.")
		if any(
			type(limit) is not int or limit <= 0
			for limit in value["projection_limits"].values()
		):
			raise RuntimeError("Editorial projection limits must be positive integers.")
		if not isinstance(value.get("repositories"), list):
			raise RuntimeError("Editorial projection repositories must be a list.")
		if not isinstance(value.get("excerpts"), list) or not value["excerpts"]:
			raise RuntimeError("Editorial projection requires exact excerpts.")
		cards = [RepositoryCard.from_dict(item) for item in value["repositories"]]
		excerpts = [EvidenceExcerpt.from_dict(item) for item in value["excerpts"]]
		if len({card.repository for card in cards}) != len(cards):
			raise RuntimeError("Editorial projection contains duplicate repository cards.")
		if len({excerpt.excerpt_id for excerpt in excerpts}) != len(excerpts):
			raise RuntimeError("Editorial projection contains duplicate exact excerpts.")
		projection = cls.create(
			str(value["packet_id"]),
			str(value["report_date"]),
			str(value["timezone"]),
			dict(value["projection_limits"]),
			cards,
			excerpts,
		)
		if projection.projection_id != value.get("projection_id"):
			raise RuntimeError("Editorial projection identity does not match its content.")
		projection.render_context()
		return projection

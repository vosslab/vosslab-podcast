"""Typed repository roster and lifecycle contracts."""

# Standard Library
import dataclasses
import datetime
import re

# local repo modules
import daily_blog.io_utils


REPOSITORY_ROSTER_SCHEMA_VERSION = "vosslab.daily-blog.repository-roster.v1"
REPOSITORY_NAME_RE = re.compile(
	r"^(?P<owner>[A-Za-z0-9-]+)/(?P<name>[A-Za-z0-9._-]+)$"
)


#============================================
def canonical_utc_timestamp(value: object, label: str) -> str:
	"""Require and return one canonical whole-second UTC timestamp."""
	if not isinstance(value, str) or not value:
		raise RuntimeError(f"{label} must be a UTC timestamp.")
	try:
		moment = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
	except ValueError as error:
		raise RuntimeError(f"{label} must be a UTC timestamp.") from error
	if moment.tzinfo is None:
		raise RuntimeError(f"{label} must include a timezone.")
	canonical = moment.astimezone(datetime.timezone.utc).replace(microsecond=0)
	text = canonical.isoformat().replace("+00:00", "Z")
	if text != value:
		raise RuntimeError(f"{label} must use canonical whole-second UTC form.")
	return text


@dataclasses.dataclass(frozen=True)
class RepositoryRecord:
	"""One validated public owner repository eligible for daily publication."""

	repository: str
	repository_url: str
	clone_url: str
	created_at: str
	is_fork: bool

	#============================================
	def to_dict(self) -> dict:
		"""Serialize one repository record."""
		return dataclasses.asdict(self)

	#============================================
	@classmethod
	def from_dict(cls, value: dict) -> "RepositoryRecord":
		"""Deserialize and validate one repository record."""
		required = {"repository", "repository_url", "clone_url", "created_at", "is_fork"}
		if not isinstance(value, dict) or set(value) != required:
			raise RuntimeError("Repository record fields do not match the roster contract.")
		repository = str(value["repository"])
		match = REPOSITORY_NAME_RE.fullmatch(repository)
		if match is None or ".." in match.group("name"):
			raise RuntimeError("Repository record identity is invalid.")
		expected_page = f"https://github.com/{repository}"
		expected_clone = expected_page + ".git"
		if value["repository_url"] != expected_page:
			raise RuntimeError("Repository page URL is not canonical HTTPS GitHub identity.")
		if value["clone_url"] != expected_clone:
			raise RuntimeError("Repository clone URL is not canonical HTTPS GitHub identity.")
		if type(value["is_fork"]) is not bool:
			raise RuntimeError("Repository fork state must be Boolean.")
		return cls(
			repository=repository,
			repository_url=expected_page,
			clone_url=expected_clone,
			created_at=canonical_utc_timestamp(
				value["created_at"], "Repository creation time"
			),
			is_fork=value["is_fork"],
		)


@dataclasses.dataclass(frozen=True)
class RepositoryRoster:
	"""Immutable eligible GitHub owner roster with a content-derived identity."""

	owner: str
	repositories: tuple[RepositoryRecord, ...]
	roster_id: str
	schema_version: str = REPOSITORY_ROSTER_SCHEMA_VERSION

	#============================================
	def content_dict(self) -> dict:
		"""Return roster content whose canonical hash defines its identity."""
		return {
			"schema_version": self.schema_version,
			"owner": self.owner,
			"repositories": [item.to_dict() for item in self.repositories],
		}

	#============================================
	def to_dict(self) -> dict:
		"""Serialize the complete roster including its immutable identity."""
		value = self.content_dict()
		value["roster_id"] = self.roster_id
		return value

	#============================================
	@classmethod
	def create(cls, owner: str, repositories: list[RepositoryRecord]) -> "RepositoryRoster":
		"""Create one ordered roster and compute its canonical identity."""
		if not re.fullmatch(r"[A-Za-z0-9-]+", owner):
			raise RuntimeError("Repository roster owner is invalid.")
		ordered = sorted(repositories, key=lambda item: item.repository.casefold())
		identities = [item.repository.casefold() for item in ordered]
		if not ordered:
			raise RuntimeError("Repository roster has no eligible public repositories.")
		if len(set(identities)) != len(identities):
			raise RuntimeError("Repository roster contains duplicate identities.")
		if any(item.repository.split("/", 1)[0].casefold() != owner.casefold() for item in ordered):
			raise RuntimeError("Repository roster contains an owner mismatch.")
		roster = cls(owner=owner, repositories=tuple(ordered), roster_id="")
		roster_id = daily_blog.io_utils.hash_value(roster.content_dict())
		return dataclasses.replace(roster, roster_id=roster_id)

	#============================================
	@classmethod
	def from_dict(cls, value: dict) -> "RepositoryRoster":
		"""Deserialize and verify one immutable owner roster."""
		if not isinstance(value, dict) or set(value) != {
			"schema_version", "owner", "repositories", "roster_id"
		}:
			raise RuntimeError("Repository roster fields do not match the schema.")
		if value["schema_version"] != REPOSITORY_ROSTER_SCHEMA_VERSION:
			raise RuntimeError("Unsupported repository roster schema.")
		if not isinstance(value["repositories"], list):
			raise RuntimeError("Repository roster repositories must be a list.")
		records = [RepositoryRecord.from_dict(item) for item in value["repositories"]]
		roster = cls.create(str(value["owner"]), records)
		if roster.roster_id != value["roster_id"]:
			raise RuntimeError("Repository roster identity does not match its content.")
		return roster


@dataclasses.dataclass(frozen=True)
class RepositoryLifecycleEvent:
	"""One exact repository lifecycle event carried from the owner roster."""

	event_type: str
	occurred_at: str
	occurred_in_report_window: bool
	source: str

	#============================================
	def to_dict(self) -> dict:
		"""Serialize one repository lifecycle event."""
		return dataclasses.asdict(self)

	#============================================
	@classmethod
	def from_dict(cls, value: dict) -> "RepositoryLifecycleEvent":
		"""Deserialize and validate one repository lifecycle event."""
		required = {
			"event_type", "occurred_at", "occurred_in_report_window", "source"
		}
		if not isinstance(value, dict) or set(value) != required:
			raise RuntimeError("Repository lifecycle event fields do not match the contract.")
		if value["event_type"] != "repository_created":
			raise RuntimeError("Repository lifecycle event type is unsupported.")
		if value["source"] != "github_owner_roster":
			raise RuntimeError("Repository lifecycle event source is unsupported.")
		if type(value["occurred_in_report_window"]) is not bool:
			raise RuntimeError("Repository lifecycle report-window state must be Boolean.")
		return cls(
			event_type="repository_created",
			occurred_at=canonical_utc_timestamp(
				value["occurred_at"], "Repository lifecycle occurrence time"
			),
			occurred_in_report_window=value["occurred_in_report_window"],
			source="github_owner_roster",
		)

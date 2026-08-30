"""Immutable editorial artifacts and deterministic eligibility decisions."""

# Standard Library
import collections.abc
import dataclasses
import datetime
import os
import re

# local repo modules
import daily_blog.io_utils
import daily_blog.schema


ARTIFACT_SCHEMA_VERSION = "vosslab.daily-blog.editorial-artifact.v1"
ELIGIBILITY_REASONS = frozenset({
	"unknown_evidence_reference", "evidence_outside_repository_scope",
	"evidence_report_date_mismatch", "packet_provenance_mismatch",
	"unapproved_image_path", "report_date_mismatch", "publication_identity_mismatch",
	"output_path_outside_root", "invalid_machine_metadata", "insufficient_evidence_density",
})
NO_ARTIFACT_REASONS = frozenset({
	"route_unavailable", "no_eligible_generation", "evidence_unavailable", "configuration",
	"implementation_defect", "no_eligible_ranking_review",
})
DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
ARTIFACT_ID_RE = re.compile(r"artifact-[0-9a-f]{24}\Z")
EVIDENCE_COMMENT_RE = re.compile(r"<!--\s*evidence:\s*([^>]+?)\s*-->")
INLINE_IMAGE_RE = re.compile(r"!\[[^]]*\]\(([^)]*)\)")
REFERENCE_IMAGE_RE = re.compile(r"!\[[^]]*\]\[([^]]*)\]")
REFERENCE_DEFINITION_RE = re.compile(r"^\s*\[([^]]+)\]:\s*(?:<([^>]+)>|(\S+))", re.MULTILINE)
HTML_IMAGE_TAG_RE = re.compile(r"<(?:img|source)\b[^>]*>", re.IGNORECASE)
HTML_IMAGE_START_RE = re.compile(r"<(?:img|source)\b", re.IGNORECASE)
HTML_ATTRIBUTE_RE = re.compile(
	r"\b(src|srcset)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))",
	re.IGNORECASE,
)
MARKDOWN_IMAGE_START_RE = re.compile(r"!\[")
INVALID_IMAGE_PATH = "__invalid_embedded_image_syntax__"


#============================================
def _require_text(value: object, field: str) -> str:
	"""Return one nonempty exact text value for machine-owned state."""
	if type(value) is not str or not value:
		raise RuntimeError(f"Artifact {field} must be nonempty text.")
	return value


#============================================
def _require_date(value: object, field: str) -> str:
	"""Return one canonical publication date without coercing model values."""
	if type(value) is not str or DATE_RE.fullmatch(value) is None:
		raise RuntimeError(f"Artifact {field} must be canonical YYYY-MM-DD text.")
	try:
		datetime.date.fromisoformat(value)
	except ValueError as error:
		raise RuntimeError(f"Artifact {field} must be a real calendar date.") from error
	return value


#============================================
def _require_text_tuple(value: object, field: str) -> tuple[str, ...]:
	"""Return one nonempty canonical unique text tuple."""
	if type(value) is not tuple or not value:
		raise RuntimeError(f"Artifact {field} must be a nonempty tuple of text.")
	if any(type(item) is not str or not item for item in value):
		raise RuntimeError(f"Artifact {field} must contain nonempty text.")
	if tuple(sorted(value)) != value or len(set(value)) != len(value):
		raise RuntimeError(f"Artifact {field} must be sorted and unique.")
	return value


#============================================
def _safe_text_tuple(value: object) -> tuple[str, ...]:
	"""Return valid candidate text values while evaluating a malformed peer."""
	if type(value) is not tuple:
		return ()
	return tuple(item for item in value if type(item) is str and item)


#============================================
def evidence_references(content: str) -> tuple[str, ...]:
	"""Extract canonical evidence identifiers from model-authored Markdown comments."""
	if type(content) is not str:
		return ()
	identifiers = set()
	for match in EVIDENCE_COMMENT_RE.finditer(content):
		identifiers.update(value.strip() for value in match.group(1).split(",") if value.strip())
	return tuple(sorted(identifiers))


#============================================
def _image_destination(value: str) -> str | None:
	"""Extract one Markdown destination while rejecting malformed image syntax."""
	value = value.strip()
	if not value:
		return None
	if value.startswith("<"):
		closing = value.find(">")
		return value[1:closing] if closing > 1 else None
	return value.split(maxsplit=1)[0]


#============================================
def referenced_image_paths(content: str) -> tuple[str, ...]:
	"""Extract every supported embedded image destination from authored content.

	ASVS 5.1.3: unparseable image-like syntax becomes an explicit unapproved
	value, so malformed Markdown or HTML cannot silently bypass image provenance.
	"""
	if type(content) is not str:
		return (INVALID_IMAGE_PATH,)
	paths = set()
	references = {
		match.group(1).casefold(): (match.group(2) or match.group(3) or "").strip()
		for match in REFERENCE_DEFINITION_RE.finditer(content)
	}
	markdown_images = tuple(INLINE_IMAGE_RE.finditer(content))
	markdown_images += tuple(REFERENCE_IMAGE_RE.finditer(content))
	if len(MARKDOWN_IMAGE_START_RE.findall(content)) != len(markdown_images):
		paths.add(INVALID_IMAGE_PATH)
	for match in INLINE_IMAGE_RE.finditer(content):
		path = _image_destination(match.group(1))
		paths.add(path if path else INVALID_IMAGE_PATH)
	for match in REFERENCE_IMAGE_RE.finditer(content):
		paths.add(references.get(match.group(1).casefold(), INVALID_IMAGE_PATH))
	html_tags = tuple(HTML_IMAGE_TAG_RE.finditer(content))
	if len(HTML_IMAGE_START_RE.findall(content)) != len(html_tags):
		paths.add(INVALID_IMAGE_PATH)
	for match in html_tags:
		tag = match.group(0)
		attributes = list(HTML_ATTRIBUTE_RE.finditer(tag))
		if not attributes:
			paths.add(INVALID_IMAGE_PATH)
		for attribute in attributes:
			value = next(group for group in attribute.groups()[1:] if group is not None).strip()
			if attribute.group(1).casefold() == "srcset":
				candidates = [part.strip().split(maxsplit=1)[0] for part in value.split(",") if part.strip()]
				paths.update(candidates or [INVALID_IMAGE_PATH])
			else:
				paths.add(value or INVALID_IMAGE_PATH)
	return tuple(sorted(paths))


#============================================
def _canonical_packet_ids(
	packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket], report_date: str,
) -> tuple[str, ...]:
	"""Return packet identities only after exact report-scope validation."""
	if not packets or any(type(packet) is not daily_blog.schema.EvidencePacket for packet in packets):
		raise RuntimeError("Artifact provenance requires nonempty EvidencePacket values.")
	if any(packet.report_date != report_date for packet in packets):
		raise RuntimeError("Artifact evidence packets must use the artifact report date.")
	packet_ids = tuple(sorted(packet.packet_id for packet in packets))
	if len(set(packet_ids)) != len(packet_ids):
		raise RuntimeError("Artifact provenance cannot repeat an evidence packet.")
	return packet_ids


@dataclasses.dataclass(frozen=True)
class _Artifact:
	"""Common immutable storage for one typed rung in the editorial ladder."""
	report_date: str
	packet_ids: tuple[str, ...]
	repositories: tuple[str, ...]
	content: str
	content_hash: str
	evidence_ids: tuple[str, ...]
	image_paths: tuple[str, ...]
	artifact_id: str
	schema_version: str = ARTIFACT_SCHEMA_VERSION

	#============================================
	@classmethod
	def artifact_type(cls) -> str:
		"""Return one stable explicit type label for canonical artifact identity."""
		return cls.__name__

	#============================================
	def identity_dict(self) -> dict:
		"""Return exact machine-owned fields that determine artifact identity."""
		return {
			"artifact_type": self.artifact_type(),
			"schema_version": self.schema_version,
			"report_date": self.report_date,
			"packet_ids": list(self.packet_ids),
			"repositories": list(self.repositories),
			"content_hash": self.content_hash,
			"evidence_ids": list(self.evidence_ids),
			"image_paths": list(self.image_paths),
		}

	#============================================
	def to_dict(self) -> dict:
		"""Serialize one typed artifact including its machine-owned identity."""
		value = self.identity_dict()
		value.update({"content": self.content, "artifact_id": self.artifact_id})
		return value

	#============================================
	@classmethod
	def _create(
		cls, report_date: str,
		packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket],
		repositories: tuple[str, ...], content: str, evidence_ids: tuple[str, ...],
		image_paths: tuple[str, ...], **extra: str,
	) -> "_Artifact":
		"""Build one artifact after canonicalizing all caller-owned inputs."""
		_require_date(report_date, "report_date")
		_require_text(content, "content")
		_require_text_tuple(repositories, "repositories")
		_require_text_tuple(evidence_ids, "evidence_ids")
		if (
			type(image_paths) is not tuple
			or any(type(item) is not str or not item for item in image_paths)
		):
			raise RuntimeError("Artifact image_paths must be a tuple of nonempty text.")
		if tuple(sorted(image_paths)) != image_paths or len(set(image_paths)) != len(image_paths):
			raise RuntimeError("Artifact image_paths must be sorted and unique.")
		if evidence_references(content) != evidence_ids:
			raise RuntimeError("Artifact evidence_ids must exactly match evidence comments.")
		if referenced_image_paths(content) != image_paths:
			raise RuntimeError("Artifact image paths must exactly match embedded images.")
		packet_ids = _canonical_packet_ids(packets, report_date)
		artifact = cls(
			report_date, packet_ids, repositories, content,
			daily_blog.io_utils.sha256_text(content), evidence_ids, image_paths, "", **extra,
		)
		return dataclasses.replace(
			artifact,
			artifact_id="artifact-" + daily_blog.io_utils.hash_value(artifact.identity_dict())[:24],
		)

	#============================================
	@classmethod
	def from_dict(cls, value: dict) -> "_Artifact":
		"""Restore one artifact only when every machine-owned value verifies exactly."""
		if type(value) is not dict:
			raise RuntimeError("Artifact type is unsupported.")
		base = {
			"artifact_type", "schema_version", "report_date", "packet_ids", "repositories",
			"content", "content_hash", "evidence_ids", "image_paths", "artifact_id",
		}
		extra = cls._extra_from_dict(value, base)
		if value["artifact_type"] != cls.artifact_type():
			raise RuntimeError("Artifact type is unsupported.")
		if value["schema_version"] != ARTIFACT_SCHEMA_VERSION:
			raise RuntimeError("Artifact schema is unsupported.")
		if any(
			type(value[name]) is not list
			for name in ("packet_ids", "repositories", "evidence_ids", "image_paths")
		):
			raise RuntimeError("Artifact list fields must be JSON arrays.")
		artifact = cls(
			value["report_date"], tuple(value["packet_ids"]), tuple(value["repositories"]),
			value["content"], value["content_hash"], tuple(value["evidence_ids"]),
			tuple(value["image_paths"]), value["artifact_id"],
			value["schema_version"], **extra,
		)
		artifact._validate_machine_state()
		return artifact

	#============================================
	@classmethod
	def _extra_from_dict(cls, value: dict, base_fields: set[str]) -> dict:
		"""Return subclass-owned fields after an exact JSON shape check."""
		if set(value) != base_fields:
			raise RuntimeError("Artifact uses unsupported fields.")
		return {}

	#============================================
	def _validate_machine_state(self) -> None:
		"""Raise only for malformed coordinator-owned identity or content state."""
		_require_date(self.report_date, "report_date")
		_require_text(self.content, "content")
		_require_text_tuple(self.packet_ids, "packet_ids")
		_require_text_tuple(self.repositories, "repositories")
		_require_text_tuple(self.evidence_ids, "evidence_ids")
		if (
			type(self.image_paths) is not tuple
			or tuple(sorted(self.image_paths)) != self.image_paths
			or any(type(item) is not str or not item for item in self.image_paths)
		):
			raise RuntimeError("Artifact image paths are malformed.")
		if (
			evidence_references(self.content) != self.evidence_ids
			or referenced_image_paths(self.content) != self.image_paths
		):
			raise RuntimeError("Artifact content bindings are malformed.")
		if (
			type(self.schema_version) is not str
			or self.schema_version != ARTIFACT_SCHEMA_VERSION
		):
			raise RuntimeError("Artifact schema is unsupported.")
		if (
			type(self.content_hash) is not str
			or SHA256_RE.fullmatch(self.content_hash) is None
			or self.content_hash != daily_blog.io_utils.sha256_text(self.content)
		):
			raise RuntimeError("Artifact content hash is malformed.")
		if type(self.artifact_id) is not str or ARTIFACT_ID_RE.fullmatch(self.artifact_id) is None:
			raise RuntimeError("Artifact identity is malformed.")
		if self.artifact_id != (
			"artifact-" + daily_blog.io_utils.hash_value(self.identity_dict())[:24]
		):
			raise RuntimeError("Artifact identity does not match its machine-owned metadata.")


@dataclasses.dataclass(frozen=True)
class RepoOutline(_Artifact):
	"""One evidence-grounded outline for a single repository."""

	#============================================
	@classmethod
	def create(
		cls, report_date: str, packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket],
		repository: str, content: str, evidence_ids: tuple[str, ...],
		image_paths: tuple[str, ...] = (),
	) -> "RepoOutline":
		return cls._create(
			report_date, packets, (repository,), content, evidence_ids, image_paths,
		)


@dataclasses.dataclass(frozen=True)
class RepoStory(_Artifact):
	"""One evidence-grounded story for a single repository."""

	#============================================
	@classmethod
	def create(
		cls, report_date: str, packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket],
		repository: str, content: str, evidence_ids: tuple[str, ...],
		image_paths: tuple[str, ...] = (),
	) -> "RepoStory":
		return cls._create(
			report_date, packets, (repository,), content, evidence_ids, image_paths,
		)


@dataclasses.dataclass(frozen=True)
class DailyOutline(_Artifact):
	"""One cross-repository daily narrative outline."""

	#============================================
	@classmethod
	def create(
		cls, report_date: str, packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket],
		repositories: tuple[str, ...], content: str, evidence_ids: tuple[str, ...],
		image_paths: tuple[str, ...] = (),
	) -> "DailyOutline":
		return cls._create(report_date, packets, repositories, content, evidence_ids, image_paths)


@dataclasses.dataclass(frozen=True)
class CompletePost(_Artifact):
	"""One publication-ready post with its exact date-owned destination identity."""
	publication_id: str = ""
	output_path: str = ""

	#============================================
	def identity_dict(self) -> dict:
		value = super().identity_dict()
		value.update({"publication_id": self.publication_id, "output_path": self.output_path})
		return value

	#============================================
	@classmethod
	def create(
		cls, report_date: str, packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket],
		repositories: tuple[str, ...], content: str, evidence_ids: tuple[str, ...],
		publication_id: str, output_path: str, image_paths: tuple[str, ...] = (),
	) -> "CompletePost":
		_require_text(publication_id, "publication_id")
		_require_text(output_path, "output_path")
		return cls._create(
			report_date, packets, repositories, content, evidence_ids, image_paths,
			publication_id=publication_id, output_path=output_path,
		)

	#============================================
	@classmethod
	def _extra_from_dict(cls, value: dict, base_fields: set[str]) -> dict:
		if set(value) != base_fields | {"publication_id", "output_path"}:
			raise RuntimeError("Complete post uses unsupported fields.")
		return {
			"publication_id": value["publication_id"],
			"output_path": value["output_path"],
		}

	#============================================
	def _validate_machine_state(self) -> None:
		super()._validate_machine_state()
		_require_text(self.publication_id, "publication_id")
		_require_text(self.output_path, "output_path")


EditorialArtifact = RepoOutline | RepoStory | DailyOutline | CompletePost
ARTIFACT_TYPES = (RepoOutline, RepoStory, DailyOutline, CompletePost)


@dataclasses.dataclass(frozen=True)
class EligibilityResult:
	"""One pure mechanical eligibility decision, never a taste or quality score."""
	eligible: bool
	reasons: tuple[str, ...]

	#============================================
	def __post_init__(self) -> None:
		if type(self.eligible) is not bool or type(self.reasons) is not tuple:
			raise RuntimeError("Eligibility result types are invalid.")
		if (
			tuple(sorted(set(self.reasons))) != self.reasons
			or any(reason not in ELIGIBILITY_REASONS for reason in self.reasons)
		):
			raise RuntimeError("Eligibility reasons are unsupported.")
		if self.eligible != (not self.reasons):
			raise RuntimeError("Eligibility state must exactly match its reasons.")


#============================================
def _authoritative_packet_index(
	packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket],
) -> tuple[dict[str, daily_blog.schema.EvidencePacket], dict[str, str]]:
	"""Return evidence ownership after validating shared authoritative input.

	ASVS 1.2.5 and 5.3.2: duplicate evidence IDs are terminal evidence-input faults.
	"""
	if type(packets) not in (tuple, list) or not packets:
		raise RuntimeError("Eligibility requires nonempty EvidencePacket values.")
	by_packet = {}
	owner = {}
	for packet in packets:
		if type(packet) is not daily_blog.schema.EvidencePacket:
			raise RuntimeError("Eligibility requires exact EvidencePacket values.")
		if type(packet.packet_id) is not str or not packet.packet_id:
			raise RuntimeError("Eligibility packet identity is malformed.")
		if packet.packet_id in by_packet:
			raise RuntimeError("Eligibility packets cannot repeat a packet identity.")
		if daily_blog.io_utils.hash_value(packet.content_dict()) != packet.packet_id:
			raise RuntimeError("Eligibility packet identity does not match content.")
		by_packet[packet.packet_id] = packet
		for item in packet.items:
			if item.evidence_id in owner:
				raise RuntimeError("Eligibility packets cannot repeat an evidence identity.")
			owner[item.evidence_id] = packet.packet_id
	return by_packet, owner


#============================================
def _approved_roots(roots: tuple[str, ...]) -> tuple[str, ...]:
	"""Normalize trusted shared output roots before candidate path evaluation."""
	if type(roots) is not tuple or not roots:
		raise RuntimeError(
			"Approved output roots must be a nonempty tuple of existing absolute directories."
		)
	canonical = []
	for root in roots:
		if type(root) is not str or not os.path.isabs(root):
			raise RuntimeError("Approved output roots must contain absolute directory paths.")
		resolved = os.path.realpath(root)
		if not os.path.isdir(resolved):
			raise RuntimeError("Approved output root must be an existing directory.")
		canonical.append(resolved)
	return tuple(sorted(set(canonical)))


#============================================
def _path_within_roots(path: object, roots: tuple[str, ...]) -> bool:
	"""Require a descendant after resolving existing symlink parents.

	ASVS 5.3.2: canonicalize trusted root and candidate before containment checks.
	"""
	if type(path) is not str or not os.path.isabs(path):
		return False
	resolved = os.path.realpath(path)
	for root in roots:
		try:
			if os.path.commonpath((resolved, root)) == root and resolved != root:
				return True
		except ValueError:
			continue
	return False


#============================================
def _candidate_machine_valid(artifact: EditorialArtifact) -> bool:
	"""Validate candidate state, allowing one malformed peer to be filtered."""
	try:
		artifact._validate_machine_state()
	except (AttributeError, RuntimeError, TypeError):
		return False
	return True


#============================================
def evaluate_eligibility(
	artifact: EditorialArtifact,
	packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket],
	approved_output_roots: tuple[str, ...] = (),
) -> EligibilityResult:
	"""Return all deterministic candidate defects without stopping peer filtering."""
	if type(artifact) not in ARTIFACT_TYPES:
		raise RuntimeError("Eligibility requires one supported editorial artifact type.")
	by_packet, evidence_owner = _authoritative_packet_index(packets)
	reasons = set()
	if not _candidate_machine_valid(artifact):
		reasons.add("invalid_machine_metadata")
	report_date = artifact.report_date if type(artifact.report_date) is str else ""
	packet_ids = _safe_text_tuple(artifact.packet_ids)
	if not packet_ids or not set(packet_ids).issubset(by_packet):
		reasons.add("packet_provenance_mismatch")
	if any(packet.report_date != report_date for packet in by_packet.values()):
		reasons.update({"report_date_mismatch", "evidence_report_date_mismatch"})
	content = artifact.content if type(artifact.content) is str else ""
	content_ids = evidence_references(content)
	declared_ids = _safe_text_tuple(artifact.evidence_ids)
	if content_ids != declared_ids:
		reasons.add("invalid_machine_metadata")
	used_ids = tuple(sorted(set(content_ids) | set(declared_ids)))
	repositories = set(_safe_text_tuple(artifact.repositories))
	resolved = []
	for evidence_id in used_ids:
		owner_id = evidence_owner.get(evidence_id)
		if owner_id is None:
			reasons.add("unknown_evidence_reference")
			continue
		if owner_id not in packet_ids:
			reasons.add("packet_provenance_mismatch")
			continue
		item = next(item for item in by_packet[owner_id].items if item.evidence_id == evidence_id)
		resolved.append(item)
		if item.repository not in repositories:
			reasons.add("evidence_outside_repository_scope")
	for repository in repositories:
		if not any(item.repository == repository for item in resolved):
			reasons.add("insufficient_evidence_density")
	parsed_images = referenced_image_paths(content)
	declared_images = _safe_text_tuple(artifact.image_paths)
	if parsed_images != declared_images:
		reasons.add("invalid_machine_metadata")
	approved_images = {
		item.publish_path
		for packet_id in packet_ids if packet_id in by_packet
		for item in by_packet[packet_id].items
		if item.kind == "screenshot" and type(item.publish_path) is str and item.publish_path
	}
	if any(path not in approved_images for path in set(parsed_images) | set(declared_images)):
		reasons.add("unapproved_image_path")
	if type(artifact) is CompletePost:
		if artifact.publication_id != report_date:
			reasons.add("publication_identity_mismatch")
		roots = _approved_roots(approved_output_roots)
		if not _path_within_roots(artifact.output_path, roots):
			reasons.add("output_path_outside_root")
	return EligibilityResult(not reasons, tuple(sorted(reasons)))


#============================================
def eligible_artifacts(
	artifacts: collections.abc.Iterable[object],
	packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket],
	approved_output_roots: tuple[str, ...] = (),
) -> list[EditorialArtifact]:
	"""Filter candidate peers after validating shared authoritative input once."""
	_authoritative_packet_index(packets)
	eligible = []
	for artifact in artifacts:
		if type(artifact) not in ARTIFACT_TYPES:
			continue
		if evaluate_eligibility(artifact, packets, approved_output_roots).eligible:
			eligible.append(artifact)
	return eligible


#============================================
def _require_expected_type(artifact: EditorialArtifact, expected_type: type) -> None:
	"""Enforce exact same-rung promotion instead of a compatible subclass."""
	if expected_type not in ARTIFACT_TYPES or type(artifact) is not expected_type:
		raise RuntimeError("Stage outcome artifact does not have the expected exact type.")


@dataclasses.dataclass(frozen=True)
class SelectedPeer:
	artifact: EditorialArtifact
	expected_type: type
	kind: str = dataclasses.field(init=False, default="selected_peer")

	#============================================
	def __post_init__(self) -> None:
		_require_expected_type(self.artifact, self.expected_type)


@dataclasses.dataclass(frozen=True)
class PreservedArtifact:
	artifact: EditorialArtifact
	expected_type: type
	kind: str = dataclasses.field(init=False, default="preserved_artifact")

	#============================================
	def __post_init__(self) -> None:
		_require_expected_type(self.artifact, self.expected_type)


@dataclasses.dataclass(frozen=True)
class DegradedPromotion:
	artifact: EditorialArtifact
	expected_type: type
	reasons: tuple[str, ...]
	kind: str = dataclasses.field(init=False, default="degraded_promotion")

	#============================================
	def __post_init__(self) -> None:
		_require_expected_type(self.artifact, self.expected_type)
		if (
			type(self.reasons) is not tuple or not self.reasons
			or any(type(reason) is not str or not reason for reason in self.reasons)
		):
			raise RuntimeError("Degraded promotion requires explicit reason text.")


@dataclasses.dataclass(frozen=True)
class NoArtifact:
	expected_type: type
	reason: str
	kind: str = dataclasses.field(init=False, default="no_artifact")

	#============================================
	def __post_init__(self) -> None:
		if self.expected_type not in ARTIFACT_TYPES or self.reason not in NO_ARTIFACT_REASONS:
			raise RuntimeError("No-artifact outcome is unsupported.")

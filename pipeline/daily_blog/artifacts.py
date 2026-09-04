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
import daily_blog.publication_source_safety


ARTIFACT_SCHEMA_VERSION = "vosslab.daily-blog.editorial-artifact.v1"
ELIGIBILITY_REASONS = frozenset({
	"unknown_evidence_reference", "evidence_outside_repository_scope",
	"evidence_report_date_mismatch", "packet_provenance_mismatch",
	"unapproved_image_path", "report_date_mismatch", "publication_identity_mismatch",
	"output_path_outside_root", "invalid_machine_metadata", "insufficient_evidence_density",
	"unsafe_publication_source",
	"repository_scope_mismatch", "unapproved_screenshot_path",
	"project_coverage_mismatch",
})
NO_ARTIFACT_REASONS = frozenset({
	"route_unavailable", "no_eligible_generation", "evidence_unavailable", "configuration",
	"implementation_defect",
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
OPENING_FRONT_MATTER_RE = re.compile(r"\A---\n(?:[^\n]*\n)*?---\n")
PUBLICATION_MACHINE_METADATA_FIELDS = (
	"date", "slug", "generator_run", "evidence_manifest", "editorial_projection",
)
_FRONT_MATTER_DELIMITER_RE = re.compile(r"(?m)^---[ \t]*$")
_MACHINE_METADATA_KEY_RE = (
	r"(?:date|slug|generator_run|evidence_manifest|editorial_projection)"
)
_MACHINE_METADATA_LINE_RE = re.compile(
	r"(?im)^[ \t]*(?:" + _MACHINE_METADATA_KEY_RE
	+ r"|'" + _MACHINE_METADATA_KEY_RE + r"'|\"" + _MACHINE_METADATA_KEY_RE
	+ r"\")[ \t]*:"
)
_FLOW_MAPPING_RE = re.compile(r"\{[^{}\n]*\}")
_FLOW_MACHINE_METADATA_KEY_RE = re.compile(
	r"(?i)(?:\A\{|,)[ \t]*(?:" + _MACHINE_METADATA_KEY_RE
	+ r"|'" + _MACHINE_METADATA_KEY_RE + r"'|\"" + _MACHINE_METADATA_KEY_RE
	+ r"\")[ \t]*:"
)


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
def _complete_post_envelope(report_date: str, metadata: dict[str, str] | None = None) -> str:
	"""Render one exact trusted CompletePost opening envelope."""
	if metadata is None:
		metadata = {"date": report_date}
	fields = ("date",) if set(metadata) == {"date"} else PUBLICATION_MACHINE_METADATA_FIELDS
	if set(metadata) != set(fields) or metadata.get("date") != report_date:
		raise RuntimeError("Complete post machine envelope is unsupported.")
	if any(type(metadata[field]) is not str or not metadata[field] or "\n" in metadata[field] or "\r" in metadata[field] for field in fields):
		raise RuntimeError("Complete post machine envelope values are invalid.")
	return "---\n" + "".join(field + ": " + metadata[field] + "\n" for field in fields) + "---\n"


#============================================
def _complete_post_content(report_date: str, content: str) -> str:
	"""Replace one exact authored opening header with the trusted date envelope."""
	match = OPENING_FRONT_MATTER_RE.match(content)
	body = content[match.end():] if match else content
	return _complete_post_envelope(report_date) + body


#============================================
def _complete_post_envelope_metadata(report_date: str, content: str) -> tuple[str, ...]:
	"""Validate one exact permitted machine envelope and return its field names."""
	match = OPENING_FRONT_MATTER_RE.match(content)
	if match is None:
		raise RuntimeError("Complete post must begin with its exact date-owned envelope.")
	metadata = {}
	for line in content[4:match.end() - 4].splitlines():
		field, separator, value = line.partition(":")
		if not separator or field not in PUBLICATION_MACHINE_METADATA_FIELDS or not value.startswith(" "):
			raise RuntimeError("Complete post machine envelope is malformed.")
		value = value[1:]
		if not value or field in metadata:
			raise RuntimeError("Complete post machine envelope is malformed.")
		metadata[field] = value
	fields = tuple(metadata)
	if fields not in (("date",), PUBLICATION_MACHINE_METADATA_FIELDS):
		raise RuntimeError("Complete post machine envelope is unsupported.")
	if metadata.get("date") != report_date or match.group() != _complete_post_envelope(report_date, metadata):
		raise RuntimeError("Complete post must begin with its exact date-owned envelope.")
	if OPENING_FRONT_MATTER_RE.match(content[match.end():]):
		raise RuntimeError("Complete post cannot contain a second opening front matter block.")
	if _embedded_machine_metadata(content[match.end():]):
		raise RuntimeError("Complete post cannot contain embedded machine metadata.")
	return fields


#============================================
def _embedded_machine_metadata(body: str) -> bool:
	"""Detect a later active front-matter-shaped block without inspecting code samples."""
	inert_body = daily_blog.publication_source_safety.inert_source(body)
	delimiters = tuple(_FRONT_MATTER_DELIMITER_RE.finditer(inert_body))
	for opening, closing in zip(delimiters, delimiters[1:]):
		block = inert_body[opening.end():closing.start()]
		if _MACHINE_METADATA_LINE_RE.search(block):
			return True
		if any(_FLOW_MACHINE_METADATA_KEY_RE.search(match.group()) for match in _FLOW_MAPPING_RE.finditer(block)):
			return True
	return False


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
def ensure_evidence_references(
	content: str, fallback_evidence_ids: tuple[str, ...],
) -> tuple[str, tuple[str, ...]]:
	"""Normalize authored provenance to the caller-owned evidence authority.

	Model-authored evidence tokens are untrusted presentation metadata. Keep usable
	references, remove unknown ones, and attach the trusted fallback set when the model
	provides no usable reference. Artifact eligibility remains the backstop for corrupt
	or incorrectly constructed machine-owned state.
	"""
	identifiers = _require_text_tuple(fallback_evidence_ids, "fallback evidence_ids")
	allowed = set(identifiers)

	def normalized_comment(match: re.Match[str]) -> str:
		values = tuple(sorted({
			value.strip() for value in match.group(1).split(",")
			if value.strip() in allowed
		}))
		return "" if not values else "<!-- evidence: " + ", ".join(values) + " -->"

	normalized = EVIDENCE_COMMENT_RE.sub(normalized_comment, content)
	existing = evidence_references(normalized)
	if existing:
		return normalized, existing
	closed = normalized.rstrip() + "\n\n<!-- evidence: " + ", ".join(identifiers) + " -->\n"
	return closed, identifiers


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
		_require_date(report_date, "report_date")
		_require_text(content, "content")
		# CompletePost owns its structural publication envelope. Editorial roles author
		# only the body, so an authored opening header cannot choose a different date
		# or smuggle extra metadata into a promotion candidate.
		content = _complete_post_content(report_date, content)
		return cls._create(
			report_date, packets, repositories, content, evidence_ids, image_paths,
			publication_id=publication_id, output_path=output_path,
		)

	#============================================
	@classmethod
	def create_publication_derivative(
		cls, report_date: str,
		packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket],
		repositories: tuple[str, ...], body: str, evidence_ids: tuple[str, ...],
		publication_id: str, output_path: str, metadata: dict[str, str],
		image_paths: tuple[str, ...] = (),
	) -> "CompletePost":
		"""Create Stage 8's trusted full-metadata derivative from exact body bytes."""
		_require_date(report_date, "report_date")
		_require_text(body, "content")
		if OPENING_FRONT_MATTER_RE.match(body):
			raise RuntimeError("Publication derivative body cannot begin with front matter.")
		content = _complete_post_envelope(report_date, metadata) + body
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
		_complete_post_envelope_metadata(self.report_date, self.content)


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
class EvidenceScopeError(RuntimeError):
	"""Describe one candidate evidence-scope defect without trusting its declaration."""
	def __init__(self, reason: str) -> None:
		if reason not in ELIGIBILITY_REASONS:
			raise RuntimeError("Evidence scope reason is unsupported.")
		self.reason = reason
		super().__init__(reason)


#============================================
def _repository_scope(value: object, field: str) -> tuple[str, ...]:
	"""Return one trusted canonical repository scope without inferring from prose."""
	if type(value) is tuple:
		repositories = value
	elif type(value) is frozenset:
		repositories = tuple(sorted(value))
	else:
		raise RuntimeError(f"{field} must be a tuple or frozenset of repository names.")
	if not repositories or any(
		type(repository) is not str or not repository for repository in repositories
	):
		raise RuntimeError(f"{field} must contain nonempty repository names.")
	if (
		tuple(sorted(repositories)) != repositories
		or len(set(repositories)) != len(repositories)
	):
		raise RuntimeError(f"{field} must be sorted and unique.")
	return repositories


#============================================
def _packet_union_scope(
	packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket],
) -> tuple[str, ...]:
	"""Return the authoritative repository ceiling when no narrower scope is supplied."""
	return tuple(sorted({item.repository for packet in packets for item in packet.items}))


#============================================
def resolve_evidence_scope(
	evidence_ids: tuple[str, ...],
	packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket],
	allowed_repositories: tuple[str, ...] | frozenset[str],
	packet_ids: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
	"""Derive cited repository scope from authoritative evidence and a trusted ceiling.

	Raises:
		EvidenceScopeError: If candidate evidence cannot support the requested scope.
		RuntimeError: If trusted packet or allowed-scope input is malformed.
	"""
	by_packet, evidence_owner = _authoritative_packet_index(packets)
	allowed_scope = _repository_scope(allowed_repositories, "Allowed repository scope")
	if type(evidence_ids) is not tuple or tuple(sorted(set(evidence_ids))) != evidence_ids:
		raise EvidenceScopeError("invalid_machine_metadata")
	if any(type(evidence_id) is not str or not evidence_id for evidence_id in evidence_ids):
		raise EvidenceScopeError("invalid_machine_metadata")
	if packet_ids is None:
		permitted_packets = frozenset(by_packet)
	else:
		if type(packet_ids) is not tuple or any(
			type(packet_id) is not str or not packet_id for packet_id in packet_ids
		):
			raise EvidenceScopeError("packet_provenance_mismatch")
		permitted_packets = frozenset(packet_ids)
		if not permitted_packets or not permitted_packets.issubset(by_packet):
			raise EvidenceScopeError("packet_provenance_mismatch")
	resolved_repositories = set()
	for evidence_id in evidence_ids:
		owner_id = evidence_owner.get(evidence_id)
		if owner_id is None:
			raise EvidenceScopeError("unknown_evidence_reference")
		if owner_id not in permitted_packets:
			raise EvidenceScopeError("packet_provenance_mismatch")
		packet = by_packet[owner_id]
		item = next(item for item in packet.items if item.evidence_id == evidence_id)
		resolved_repositories.add(item.repository)
	derived_scope = tuple(sorted(resolved_repositories))
	if not derived_scope:
		raise EvidenceScopeError("insufficient_evidence_density")
	if not set(derived_scope).issubset(allowed_scope):
		raise EvidenceScopeError("evidence_outside_repository_scope")
	return derived_scope


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
	allowed_repositories: tuple[str, ...] | frozenset[str] | None = None,
) -> EligibilityResult:
	"""Return all deterministic candidate defects without stopping peer filtering."""
	if type(artifact) not in ARTIFACT_TYPES:
		raise RuntimeError("Eligibility requires one supported editorial artifact type.")
	by_packet, _ = _authoritative_packet_index(packets)
	if allowed_repositories is None:
		allowed_repositories = _packet_union_scope(packets)
	else:
		_repository_scope(allowed_repositories, "Allowed repository scope")
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
	try:
		derived_scope = resolve_evidence_scope(
			used_ids, packets, allowed_repositories, packet_ids,
		)
	except EvidenceScopeError as error:
		reasons.add(error.reason)
	else:
		if _safe_text_tuple(artifact.repositories) != derived_scope:
			reasons.add("evidence_outside_repository_scope")
		if type(artifact) in (RepoOutline, RepoStory) and len(derived_scope) != 1:
			reasons.add("evidence_outside_repository_scope")
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
		if daily_blog.publication_source_safety.validate_post_source(content, approved_images):
			reasons.add("unsafe_publication_source")
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
	allowed_repositories: tuple[str, ...] | frozenset[str] | None = None,
) -> list[EditorialArtifact]:
	"""Filter candidate peers after validating shared authoritative input once."""
	_authoritative_packet_index(packets)
	eligible = []
	for artifact in artifacts:
		if type(artifact) not in ARTIFACT_TYPES:
			continue
		if evaluate_eligibility(
			artifact, packets, approved_output_roots, allowed_repositories,
		).eligible:
			eligible.append(artifact)
	return eligible


#============================================
def _require_expected_type(artifact: EditorialArtifact, expected_type: type) -> None:
	"""Enforce exact same-rung promotion instead of a compatible subclass."""
	if expected_type not in ARTIFACT_TYPES or type(artifact) is not expected_type:
		raise RuntimeError("Stage outcome artifact does not have the expected exact type.")
	artifact._validate_machine_state()


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

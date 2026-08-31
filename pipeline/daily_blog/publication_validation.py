"""Deterministic Stage 8 validation and machine-metadata repair."""

# Standard Library
import collections.abc
import dataclasses
import os
import re

# local repo modules
import daily_blog.artifacts
import daily_blog.candidates
import daily_blog.schema
import daily_blog.publication_admission


MACHINE_METADATA_FIELDS = daily_blog.artifacts.PUBLICATION_MACHINE_METADATA_FIELDS
MACHINE_METADATA_REASONS = frozenset({
	"machine_metadata_constructed", "machine_metadata_repaired",
})
FRONT_MATTER_RE = re.compile(r"\A---\n(?P<metadata>.*?)\n---\n", re.DOTALL)
H1_RE = re.compile(r"^#\s+(?P<title>\S.*?)\s*$", re.MULTILINE)


#============================================
@dataclasses.dataclass(frozen=True)
class PublicationValidationResult:
	"""One exact Stage 8 outcome, including the identity change it made."""
	source_post: daily_blog.artifacts.CompletePost
	post: daily_blog.artifacts.CompletePost
	before_artifact_id: str
	after_artifact_id: str
	repaired: bool
	reasons: tuple[str, ...]

	#============================================
	def __post_init__(self) -> None:
		if (
			type(self.source_post) is not daily_blog.artifacts.CompletePost
			or type(self.post) is not daily_blog.artifacts.CompletePost
		):
			raise RuntimeError("Publication validation requires an exact CompletePost.")
		if type(self.before_artifact_id) is not str or not self.before_artifact_id:
			raise RuntimeError("Publication validation requires a source artifact identity.")
		if (
			self.before_artifact_id != self.source_post.artifact_id
			or self.after_artifact_id != self.post.artifact_id
		):
			raise RuntimeError("Publication validation result has an inconsistent artifact identity.")
		if type(self.repaired) is not bool or type(self.reasons) is not tuple:
			raise RuntimeError("Publication validation result state is invalid.")
		if tuple(sorted(set(self.reasons))) != self.reasons:
			raise RuntimeError("Publication validation reasons must be canonical.")
		if any(reason not in MACHINE_METADATA_REASONS for reason in self.reasons):
			raise RuntimeError("Publication validation reason is unsupported.")
		if self.repaired != bool(self.reasons):
			raise RuntimeError("Publication validation repair state is inconsistent.")
		if not self.reasons:
			if self.post is not self.source_post or self.after_artifact_id != self.before_artifact_id:
				raise RuntimeError("Publication validation no-op must preserve the exact source post.")
			return
		if self.post is self.source_post or self.after_artifact_id == self.before_artifact_id:
			raise RuntimeError("Publication validation repair must create a distinct derivative.")
		for field in (
			"report_date", "packet_ids", "repositories", "evidence_ids", "publication_id",
			"output_path", "image_paths",
		):
			if getattr(self.post, field) != getattr(self.source_post, field):
				raise RuntimeError("Publication validation repair changed trusted provenance.")
		source_body, _source_metadata = _body_and_metadata(self.source_post.content)
		post_body, post_metadata = _body_and_metadata(self.post.content)
		if source_body != post_body or set(post_metadata or ()) != set(MACHINE_METADATA_FIELDS):
			raise RuntimeError("Publication validation repair changed authored post bytes.")


#============================================
def _require_output_root(value: object) -> str:
	"""Return one trusted existing absolute output root."""
	if type(value) is not str or not os.path.isabs(value):
		raise RuntimeError("Publication validation output root must be an absolute directory.")
	root = os.path.realpath(value)
	if not os.path.isdir(root):
		raise RuntimeError("Publication validation output root must be an existing directory.")
	return root


#============================================
def _require_generator_run(value: object) -> str:
	"""Return one bounded publisher-compatible producer run identity."""
	if type(value) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value) is None:
		raise RuntimeError("Publication validation generator run is invalid.")
	return value


#============================================
def _body_and_metadata(content: str) -> tuple[str, dict[str, str] | None]:
	"""Split an optional unambiguous machine-owned opening region from prose."""
	if not content.startswith("---"):
		return content, None
	match = FRONT_MATTER_RE.match(content)
	if match is None:
		raise RuntimeError("Publication machine metadata is malformed or ambiguous.")
	metadata = {}
	for line in match.group("metadata").splitlines():
		key, separator, value = line.partition(":")
		if not separator or not key or key.strip() != key or not value.startswith(" "):
			raise RuntimeError("Publication machine metadata is malformed or ambiguous.")
		value = value[1:]
		if not value or "\r" in value or "\n" in value or key in metadata:
			raise RuntimeError("Publication machine metadata is malformed or ambiguous.")
		metadata[key] = value
	if set(metadata) - set(MACHINE_METADATA_FIELDS):
		raise RuntimeError("Publication machine metadata contains unsupported fields.")
	return content[match.end():], metadata


#============================================
def _metadata(report_date: str, title: str, generator_run: str) -> dict[str, str]:
	"""Construct the one closed publisher metadata mapping from trusted inputs."""
	slug = daily_blog.candidates.slug_from_title(title)
	if not slug or daily_blog.candidates.SLUG_RE.fullmatch(slug) is None:
		raise RuntimeError("Publication title cannot produce a publisher slug.")
	return {
		"date": report_date,
		"slug": slug,
		"generator_run": generator_run,
		"evidence_manifest": "evidence.json",
		"editorial_projection": "editorial_projection.json",
	}


#============================================
def _packet_scope(
	packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket],
) -> tuple[str, ...]:
	"""Return the authoritative maximum repository scope for Stage 8 input."""
	return tuple(sorted({item.repository for packet in packets for item in packet.items}))


#============================================
def _semantic_scope(
	post: daily_blog.artifacts.CompletePost,
	packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket],
) -> tuple[str, ...]:
	"""Derive publication provenance from unchanged citations and packets.

	ASVS 2.2.1: publication never trusts a post's declared repository tuple as
	the authority for a repairable metadata transition.
	"""
	try:
		return daily_blog.artifacts.resolve_evidence_scope(
			post.evidence_ids, packets, _packet_scope(packets), post.packet_ids,
		)
	except daily_blog.artifacts.EvidenceScopeError as error:
		raise RuntimeError(
			"Publication validation complete post evidence scope is invalid: " + error.reason
		) from error


#============================================
def _render_metadata(metadata: dict[str, str]) -> str:
	"""Render canonical metadata without touching authored post bytes."""
	return "---\n" + "".join(
		field + ": " + metadata[field] + "\n" for field in MACHINE_METADATA_FIELDS
	) + "---\n"


#============================================
def validate_result_for_inputs(
	result: object,
	*,
	source_post: daily_blog.artifacts.CompletePost,
	report_date: str,
	packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket],
	approved_output_root: str,
	generator_run: str,
) -> PublicationValidationResult:
	"""Verify one Stage-8 parent/derivative link against trusted run inputs."""
	if type(result) is not PublicationValidationResult or result.source_post is not source_post:
		raise RuntimeError("Publication validation result does not bind the exact source post.")
	if type(report_date) is not str or daily_blog.artifacts.DATE_RE.fullmatch(report_date) is None:
		raise RuntimeError("Publication validation report date is invalid.")
	root = _require_output_root(approved_output_root)
	run_id = _require_generator_run(generator_run)
	for post in (result.source_post, result.post):
		try:
			post._validate_machine_state()
		except (AttributeError, TypeError, RuntimeError) as error:
			raise RuntimeError("Publication validation result artifact is malformed.") from error
		if post.report_date != report_date or post.publication_id != report_date:
			raise RuntimeError("Publication validation report date does not match the complete post.")
		semantic_scope = _semantic_scope(post, packets)
		eligibility = daily_blog.artifacts.evaluate_eligibility(
			post, packets, (root,), semantic_scope,
		)
		if not eligibility.eligible:
			raise RuntimeError(
				"Publication validation rejected complete post: " + ", ".join(eligibility.reasons)
			)
	if result.repaired:
		body, metadata = _body_and_metadata(result.post.content)
		titles = tuple(match.group("title") for match in H1_RE.finditer(body))
		if len(titles) != 1 or metadata != _metadata(report_date, titles[0], run_id):
			raise RuntimeError("Publication validation repair metadata is not canonical.")
	return result


#============================================
def validate_and_repair_complete_post(
	post: daily_blog.artifacts.CompletePost,
	*,
	report_date: str,
	packets: collections.abc.Sequence[daily_blog.schema.EvidencePacket],
	approved_output_root: str,
	generator_run: str,
	surface: daily_blog.publication_admission.PublicationSurface,
) -> PublicationValidationResult:
	"""Return one eligible post with canonical publisher metadata.

	ASVS 2.2.1 and 2.3.1: validate exact rung, date, provenance, and path at
	the Stage 8 boundary before a date-owned publication flow may continue.
	"""
	if type(post) is not daily_blog.artifacts.CompletePost:
		raise RuntimeError("Publication validation requires an exact CompletePost.")
	if type(report_date) is not str or daily_blog.artifacts.DATE_RE.fullmatch(report_date) is None:
		raise RuntimeError("Publication validation report date is invalid.")
	try:
		post._validate_machine_state()
	except (AttributeError, TypeError, RuntimeError) as error:
		raise RuntimeError("Publication validation input artifact is malformed.") from error
	if post.report_date != report_date or post.publication_id != report_date:
		raise RuntimeError("Publication validation report date does not match the complete post.")
	root = _require_output_root(approved_output_root)
	run_id = _require_generator_run(generator_run)
	# ASVS 2.2.1: metadata repair cannot substitute a different evidence source,
	# publication path, or candidate provenance before the new artifact is bound.
	semantic_scope = _semantic_scope(post, packets)
	source_eligibility = daily_blog.artifacts.evaluate_eligibility(
		post, packets, (root,), semantic_scope,
	)
	if not source_eligibility.eligible:
		raise RuntimeError(
			"Publication validation rejected complete post: "
			+ ", ".join(source_eligibility.reasons)
		)
	# ASVS 2.2.3 and 2.3.1: Stage 8 receives the same authority that supplied
	# editorial context; a packet-only validation path cannot bypass it.
	if (
		type(surface) is not daily_blog.publication_admission.PublicationSurface
		or surface.source_packets != tuple(sorted(packets, key=lambda item: item.packet_id))
	):
		raise RuntimeError("Publication validation surface does not match the exact packet union.")
	# ASVS 2.3.1: Stage 8 is a defense-in-depth admission boundary.  Earlier
	# editorial paths retain grounded drafts for repair; only a fully reviewed,
	# readable post may cross into the publisher-owned workflow.
	if daily_blog.publication_admission.complete_post_policy_issues(post, surface):
		raise RuntimeError("Publication validation rejected complete post: publication_policy_mismatch")
	body, existing_metadata = _body_and_metadata(post.content)
	titles = tuple(match.group("title") for match in H1_RE.finditer(body))
	if len(titles) != 1:
		raise RuntimeError("Publication content must contain exactly one descriptive H1.")
	canonical_metadata = _metadata(report_date, titles[0], run_id)
	repaired = existing_metadata != canonical_metadata
	if existing_metadata is None:
		reasons = ("machine_metadata_constructed",)
	elif repaired:
		reasons = ("machine_metadata_repaired",)
	else:
		reasons = ()
	validated = post if not reasons else daily_blog.artifacts.CompletePost.create_publication_derivative(
		report_date, packets, semantic_scope, body, post.evidence_ids,
		report_date, post.output_path, canonical_metadata, post.image_paths,
	)
	result = PublicationValidationResult(
		post, validated, post.artifact_id, validated.artifact_id, bool(reasons), reasons,
	)
	return validate_result_for_inputs(
		result, source_post=post, report_date=report_date, packets=packets,
		approved_output_root=root, generator_run=run_id,
	)

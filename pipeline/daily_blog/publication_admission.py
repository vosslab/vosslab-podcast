"""One survivor-scoped evidence surface for final-post editorial admission."""

# Standard Library
import dataclasses
import json
import re

# local repo modules
import daily_blog.artifacts
import daily_blog.candidates
import daily_blog.io_utils
import daily_blog.projection
import daily_blog.schema
import daily_blog.stage6_context


REPAIR_FEEDBACK_SCHEMA_VERSION = "vosslab.daily-blog.repair-feedback.v1"
_REPAIR_FEEDBACK_FIELDS = frozenset({
	"candidate_sha256", "reason_codes", "objective_codes",
	"authorized_evidence_refs", "authorized_artifact_ids",
})
_SAFE_FEEDBACK_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,95}$")
_REPAIR_OBJECTIVES = {
	"citation_density_mismatch": "add_authorized_citations",
	"evidence_grounding_mismatch": "ground_claims_in_authorized_evidence",
	"image_authority_mismatch": "use_authorized_images",
	"presentation_policy_mismatch": "meet_presentation_requirements",
}


#============================================
@dataclasses.dataclass(frozen=True)
class RepairFeedbackEnvelope:
	"""One candidate-local, positive repair assignment from admission facts."""

	candidate_sha256: str
	reason_codes: tuple[str, ...]
	objective_codes: tuple[str, ...]
	authorized_evidence_refs: tuple[str, ...]
	authorized_artifact_ids: tuple[str, ...]

	#============================================
	def __post_init__(self) -> None:
		"""Validate the closed schema before it enters a prompt or cache key."""
		if type(self.candidate_sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", self.candidate_sha256) is None:
			raise RuntimeError("Repair feedback candidate identity must be a lowercase SHA-256 digest.")
		self._validate_codes(self.reason_codes, tuple(sorted(_REPAIR_OBJECTIVES)), 1, 16, "reason")
		self._validate_codes(self.objective_codes, tuple(sorted(_REPAIR_OBJECTIVES.values())), 1, 16, "objective")
		if self.objective_codes != tuple(sorted(_REPAIR_OBJECTIVES[item] for item in self.reason_codes)):
			raise RuntimeError("Repair feedback objectives must match its closed reason mapping.")
		self._validate_ids(self.authorized_evidence_refs, "evidence reference")
		self._validate_ids(self.authorized_artifact_ids, "artifact identity")

	#============================================
	@staticmethod
	def _validate_codes(
		values: object, allowed: tuple[str, ...], minimum: int, maximum: int, label: str,
	) -> None:
		"""Require a bounded canonical subset of one closed code vocabulary."""
		if (
			type(values) is not tuple or not minimum <= len(values) <= maximum
			or values != tuple(sorted(set(values)))
			or any(type(item) is not str or item not in allowed for item in values)
		):
			raise RuntimeError("Repair feedback " + label + " codes are malformed.")

	#============================================
	@staticmethod
	def _validate_ids(values: object, label: str) -> None:
		"""Require a bounded canonical sequence of safe authority identifiers."""
		if (
			type(values) is not tuple or len(values) > 256
			or values != tuple(sorted(set(values)))
			or any(type(item) is not str or _SAFE_FEEDBACK_ID_RE.fullmatch(item) is None for item in values)
		):
			raise RuntimeError("Repair feedback " + label + " identifiers are malformed.")

	#============================================
	def to_dict(self) -> dict[str, object]:
		"""Return the exact JSON envelope without parallel schema aliases."""
		return {
			"candidate_sha256": self.candidate_sha256,
			"reason_codes": list(self.reason_codes),
			"objective_codes": list(self.objective_codes),
			"authorized_evidence_refs": list(self.authorized_evidence_refs),
			"authorized_artifact_ids": list(self.authorized_artifact_ids),
		}

	#============================================
	@classmethod
	def from_dict(cls, value: object) -> "RepairFeedbackEnvelope":
		"""Restore only the exact current closed JSON representation."""
		if type(value) is not dict or set(value) != _REPAIR_FEEDBACK_FIELDS:
			raise RuntimeError("Repair feedback envelope fields are unsupported.")
		if type(value["candidate_sha256"]) is not str or any(
			type(value[name]) is not list for name in _REPAIR_FEEDBACK_FIELDS - {"candidate_sha256"}
		):
			raise RuntimeError("Repair feedback envelope JSON types are malformed.")
		return cls(
			value["candidate_sha256"], tuple(value["reason_codes"]), tuple(value["objective_codes"]),
			tuple(value["authorized_evidence_refs"]), tuple(value["authorized_artifact_ids"]),
		)

	#============================================
	def canonical_json(self) -> str:
		"""Render the validated five-field envelope in its sole canonical form."""
		return json.dumps(self.to_dict(), ensure_ascii=True, separators=(",", ":"), sort_keys=True)

	#============================================
	def sha256(self) -> str:
		"""Hash only the canonical, validated envelope bytes."""
		return daily_blog.io_utils.sha256_text(self.canonical_json())


#============================================
@dataclasses.dataclass(frozen=True)
class PublicationSurface:
	"""Exact editorial survivors and the material allowed into publication."""

	source_packets: tuple[daily_blog.schema.EvidencePacket, ...]
	evidence_context: daily_blog.schema.BoundedEvidenceContext
	stage6_prompt_context: daily_blog.stage6_context.Stage6PromptContext
	coverage_repositories: tuple[str, ...]
	source_artifacts: tuple[daily_blog.artifacts.EditorialArtifact, ...]
	daily_outline: daily_blog.artifacts.DailyOutline = dataclasses.field(init=False)
	repo_stories: tuple[daily_blog.artifacts.RepoStory, ...] = dataclasses.field(init=False)
	narrative_repo_stories: tuple[daily_blog.artifacts.RepoStory, ...] = dataclasses.field(init=False)
	narrative_repositories: tuple[str, ...] = dataclasses.field(init=False)
	packet: daily_blog.schema.EvidencePacket = dataclasses.field(init=False)
	projection: daily_blog.schema.EditorialProjection = dataclasses.field(init=False)
	allowed_evidence_ids: tuple[str, ...] = dataclasses.field(init=False)
	allowed_images: tuple[daily_blog.stage6_context.PublicationImage, ...] = dataclasses.field(
		init=False,
	)

	#============================================
	@property
	def allowed_image_paths(self) -> tuple[str, ...]:
		"""Return the legacy post-body view derived from typed image authority."""
		return tuple(sorted(image.publish_path for image in self.allowed_images))

	#============================================
	def __post_init__(self) -> None:
		"""Reject direct construction that separates provenance from publication evidence."""
		if (
			type(self.source_packets) is not tuple
			or not self.source_packets
			or any(type(item) is not daily_blog.schema.EvidencePacket for item in self.source_packets)
		):
			raise RuntimeError("Publication surface must bind one exact survivor evidence union.")
		source_packet_ids = tuple(item.packet_id for item in self.source_packets)
		if (
			source_packet_ids != tuple(sorted(source_packet_ids))
			or len(set(source_packet_ids)) != len(source_packet_ids)
			or type(self.evidence_context) is not daily_blog.schema.BoundedEvidenceContext
			or type(self.stage6_prompt_context) is not daily_blog.stage6_context.Stage6PromptContext
			or type(self.coverage_repositories) is not tuple
			or not self.coverage_repositories
			or self.coverage_repositories != tuple(sorted(set(self.coverage_repositories)))
			or type(self.source_artifacts) is not tuple
			or not self.source_artifacts
			or any(type(item) not in {
				daily_blog.artifacts.DailyOutline, daily_blog.artifacts.RepoStory,
			} for item in self.source_artifacts)
		):
			raise RuntimeError("Publication surface must bind one exact survivor evidence union.")
		artifact_ids = tuple(item.artifact_id for item in self.source_artifacts)
		if artifact_ids != tuple(sorted(artifact_ids)) or len(set(artifact_ids)) != len(artifact_ids):
			raise RuntimeError("Publication surface source artifacts must be canonical and unique.")
		packet = _aggregate_packet(self.source_packets)
		packet_repositories = {item.repository for item in packet.activity} or {
			item.repository for item in packet.items
		}
		if packet_repositories != set(self.coverage_repositories):
			raise RuntimeError("Publication surface packets do not exactly cover the survivor scope.")
		# ASVS 2.2.3: validate the bounded model view and its packet union as one
		# combined authority before either editorial generation or admission uses it.
		outline = tuple(
			item for item in self.source_artifacts
			if type(item) is daily_blog.artifacts.DailyOutline
		)
		stories = tuple(
			item for item in self.source_artifacts
			if type(item) is daily_blog.artifacts.RepoStory
		)
		if len(outline) != 1 or not stories:
			raise RuntimeError("Publication surface requires one outline and survivor stories.")
		narrative_stories = tuple(
			item for item in stories if item.repositories[0] in outline[0].repositories
		)
		narrative_packet_ids = set(outline[0].packet_ids)
		narrative_packets = tuple(
			item for item in self.source_packets if item.packet_id in narrative_packet_ids
		)
		if (
			outline[0].packet_ids != tuple(item.packet_id for item in narrative_packets)
			or tuple(sorted({repository for item in narrative_stories for repository in item.repositories}))
			!= outline[0].repositories
			or tuple(sorted({repository for item in stories for repository in item.repositories}))
			!= self.coverage_repositories
		):
			raise RuntimeError("Publication surface artifacts do not match its survivor scope.")
		if not daily_blog.artifacts.evaluate_eligibility(
			outline[0], narrative_packets, allowed_repositories=outline[0].repositories,
		).eligible or any(not daily_blog.artifacts.evaluate_eligibility(
			item, self.source_packets, allowed_repositories=self.coverage_repositories,
		).eligible for item in stories):
			raise RuntimeError("Publication surface source artifacts are not mechanically grounded.")
		daily_blog.projection.validate_bounded_evidence_context(narrative_packets, self.evidence_context)
		context_repositories = tuple(sorted(card.repository for card in self.evidence_context.repositories))
		if not set(context_repositories).issubset(outline[0].repositories):
			raise RuntimeError("Publication surface context exceeds its narrative scope.")
		if self.stage6_prompt_context.evidence_context != self.evidence_context:
			raise RuntimeError("Publication surface prompt and admission evidence disagree.")
		self.stage6_prompt_context.validate_against(
			outline[0], tuple(sorted(narrative_stories, key=lambda item: item.artifact_id)),
			narrative_packets, tuple(sorted(stories, key=lambda item: item.artifact_id)),
			self.source_packets,
		)
		allowed_images = _resolve_artifact_images(packet, outline[0], narrative_stories)
		if self.stage6_prompt_context.allowed_images != allowed_images:
			raise RuntimeError("Publication surface prompt image authority disagrees.")
		artifact_evidence_ids = {
			evidence_id for artifact in (outline[0],) + narrative_stories
			for evidence_id in artifact.evidence_ids
		}
		allowed_ids = {
			excerpt.evidence_id for excerpt in self.evidence_context.excerpts
		} | artifact_evidence_ids | {image.evidence_id for image in allowed_images}
		packet_ids = {item.evidence_id for item in packet.items}
		if not allowed_ids or not allowed_ids.issubset(packet_ids):
			raise RuntimeError("Publication surface exposes evidence outside its survivor packets.")
		items_by_id = {item.evidence_id: item for item in packet.items}
		excerpts = list(self.evidence_context.excerpts)
		excerpt_ids = {item.evidence_id for item in excerpts}
		for evidence_id in sorted(artifact_evidence_ids - excerpt_ids):
			item = items_by_id[evidence_id]
			end = min(len(item.content), self.evidence_context.projection_limits["excerpt_chars"])
			excerpts.append(daily_blog.schema.EvidenceExcerpt.create(item, 0, end))
		projection = daily_blog.schema.EditorialProjection.create(
			packet.packet_id, self.evidence_context.report_date, self.evidence_context.timezone,
			dict(self.evidence_context.projection_limits),
			list(self.evidence_context.repositories), excerpts,
		)
		# The bounded prompt view can omit a raw slice already represented by a
		# promoted artifact.  The sealed projection retains one exact packet slice
		# for every such model-visible ID so downstream admission uses this authority.
		projection.render_context()
		if {item.evidence_id for item in projection.excerpts} != allowed_ids:
			raise RuntimeError("Publication surface projection does not cover its allowed evidence.")
		# ASVS 2.2.3: later editorial stages read the cross-validated artifacts
		# from this authority instead of accepting a parallel outline/story copy.
		object.__setattr__(self, "daily_outline", outline[0])
		object.__setattr__(self, "narrative_repositories", outline[0].repositories)
		object.__setattr__(self, "repo_stories", tuple(sorted(
			stories, key=lambda item: item.repositories[0],
		)))
		object.__setattr__(self, "narrative_repo_stories", tuple(sorted(
			narrative_stories, key=lambda item: item.repositories[0],
		)))
		object.__setattr__(self, "packet", packet)
		object.__setattr__(self, "projection", projection)
		object.__setattr__(self, "allowed_evidence_ids", tuple(sorted(allowed_ids)))
		object.__setattr__(self, "allowed_images", allowed_images)

#============================================
def build_surface(
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
	coverage_repositories: tuple[str, ...],
	projection_limits: dict[str, int],
	source_artifacts: tuple[daily_blog.artifacts.EditorialArtifact, ...],
) -> PublicationSurface:
	"""Bind one model-visible survivor context to its exact admission authority."""
	if type(packets) is not tuple or not packets or any(
		type(item) is not daily_blog.schema.EvidencePacket for item in packets
	):
		raise RuntimeError("Publication surface requires exact survivor evidence packets.")
	if (
		type(coverage_repositories) is not tuple
		or not coverage_repositories
		or coverage_repositories != tuple(sorted(set(coverage_repositories)))
	):
		raise RuntimeError("Publication surface requires a canonical survivor repository scope.")
	source_packets = tuple(sorted(packets, key=lambda item: item.packet_id))
	if type(source_artifacts) is not tuple:
		raise RuntimeError("Publication surface requires exact source artifacts.")
	ordered_artifacts = tuple(sorted(source_artifacts, key=lambda item: item.artifact_id))
	outlines = tuple(
		item for item in ordered_artifacts if type(item) is daily_blog.artifacts.DailyOutline
	)
	stories = tuple(
		item for item in ordered_artifacts if type(item) is daily_blog.artifacts.RepoStory
	)
	if len(outlines) != 1 or not stories:
		raise RuntimeError("Publication surface requires one outline and survivor stories.")
	narrative_packet_ids = set(outlines[0].packet_ids)
	narrative_packets = tuple(
		item for item in source_packets if item.packet_id in narrative_packet_ids
	)
	narrative_stories = tuple(
		item for item in stories if item.repositories[0] in outlines[0].repositories
	)
	allowed_images = _resolve_artifact_images(
		_aggregate_packet(source_packets), outlines[0], narrative_stories,
	)
	stage6_prompt_context = daily_blog.stage6_context.build_stage6_prompt_context(
		outlines[0], narrative_stories, narrative_packets, stories, source_packets,
		allowed_images, coverage_repositories, projection_limits,
	)
	return PublicationSurface(
		source_packets, stage6_prompt_context.evidence_context, stage6_prompt_context,
		coverage_repositories, ordered_artifacts,
	)


#============================================
def _aggregate_packet(
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
) -> daily_blog.schema.EvidencePacket:
	"""Recompute the only aggregate packet permitted for exact survivor packets."""
	if type(packets) is not tuple or not packets or any(
		type(item) is not daily_blog.schema.EvidencePacket for item in packets
	):
		raise RuntimeError("Publication surface requires exact survivor evidence packets.")
	first = packets[0]
	if any(
		item.report_date != first.report_date or item.timezone != first.timezone
		or not item.complete or item.collection_limits != first.collection_limits
		for item in packets
	):
		raise RuntimeError("Publication surface survivor packets disagree on trusted collection facts.")
	if any(
		({activity.repository for activity in packet.activity} and {
			activity.repository for activity in packet.activity
		} != {item.repository for item in packet.items})
		or len({item.repository for item in packet.items}) != 1
		for packet in packets
	):
		raise RuntimeError("Publication surface requires one repository per survivor packet.")
	return daily_blog.schema.EvidencePacket.create(
		first.report_date, first.timezone, True, first.collection_limits.to_dict(),
		[mirror.to_dict() for item in packets for mirror in item.mirrors],
		[activity for item in packets for activity in item.activity],
		[evidence for item in packets for evidence in item.items],
	)


#============================================
def _packet_screenshot_images(
	packet: daily_blog.schema.EvidencePacket,
) -> tuple[daily_blog.stage6_context.PublicationImage, ...]:
	"""Return a packet's one-to-one screenshot identity triples.

	ASVS 2.2.3: reject ambiguous evidence-to-file mappings before a model can
	observe the surface, so writer, bundle, and publisher all inherit one mapping.
	"""
	images = []
	seen_evidence_ids: set[str] = set()
	seen_assets: set[str] = set()
	seen_publish_paths: set[str] = set()
	for item in packet.items:
		if item.kind != "screenshot":
			continue
		image = daily_blog.stage6_context.PublicationImage(
			item.evidence_id, _image_description(item), item.asset_path, item.publish_path,
		)
		if (
			image.evidence_id in seen_evidence_ids
			or image.asset_path in seen_assets
			or image.publish_path in seen_publish_paths
		):
			raise RuntimeError("Publication surface screenshot paths must be one-to-one.")
		seen_evidence_ids.add(image.evidence_id)
		seen_assets.add(image.asset_path)
		seen_publish_paths.add(image.publish_path)
		images.append(image)
	return tuple(sorted(images, key=lambda image: (
		image.evidence_id, image.asset_path, image.publish_path,
	)))


#============================================
def _image_description(item: daily_blog.schema.EvidenceItem) -> str:
	"""Return a compact stable screenshot description for the Stage 6 frame."""
	# Screenshot evidence text commonly contains its checkout-relative source path.
	# Retain only the filename-derived label, never its directory or asset location.
	filename = item.path.rsplit("/", 1)[-1]
	stem = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ")
	label = " ".join(stem.split()) or "image"
	return "Screenshot: " + label + " (" + item.repository + ")."


#============================================
def _resolve_artifact_images(
	packet: daily_blog.schema.EvidencePacket,
	outline: daily_blog.artifacts.DailyOutline,
	narrative_stories: tuple[daily_blog.artifacts.RepoStory, ...],
) -> tuple[daily_blog.stage6_context.PublicationImage, ...]:
	"""Resolve cited or embedded narrative screenshots against survivor packets."""
	all_images = _packet_screenshot_images(packet)
	by_evidence_id = {item.evidence_id: item for item in all_images}
	by_publish_path = {item.publish_path: item for item in all_images}
	artifacts = (outline,) + narrative_stories
	cited_screenshots = {
		evidence_id for artifact in artifacts for evidence_id in artifact.evidence_ids
		if evidence_id in by_evidence_id
	}
	embedded_paths = {
		path for artifact in artifacts for path in artifact.image_paths
	}
	if not embedded_paths.issubset(by_publish_path):
		raise RuntimeError("Publication surface exposes an unapproved survivor image.")
	selected = {
		by_evidence_id[evidence_id] for evidence_id in cited_screenshots
	} | {by_publish_path[path] for path in embedded_paths}
	return tuple(sorted(selected, key=lambda item: (
		item.evidence_id, item.asset_path, item.publish_path,
	)))


#============================================
def survivor_assets(surface: PublicationSurface, assets: dict[str, bytes]) -> dict[str, bytes]:
	"""Return only survivor screenshot bytes admitted by the sealed surface."""
	if type(surface) is not PublicationSurface or type(assets) is not dict:
		raise RuntimeError("Publication surface assets require exact typed inputs.")
	required = {image.asset_path for image in surface.allowed_images}
	if any(path not in assets or type(assets[path]) is not bytes for path in required):
		raise RuntimeError("Publication surface is missing a survivor screenshot asset.")
	return {path: assets[path] for path in sorted(required)}


#============================================
def complete_post_eligibility(
	post: daily_blog.artifacts.CompletePost,
	surface: PublicationSurface,
	output_root: str,
	*,
	recovery: bool = False,
) -> daily_blog.artifacts.EligibilityResult:
	"""Admit mechanically safe, evidence-grounded complete posts."""
	return complete_post_mechanical_eligibility(
		post, surface, output_root, recovery=recovery,
	)


#============================================
def complete_post_policy_issues(
	post: daily_blog.artifacts.CompletePost,
	surface: PublicationSurface,
	*,
	recovery: bool = False,
) -> tuple[str, ...]:
	"""Return explicit repair instructions against the exact model-visible surface."""
	if type(post) is not daily_blog.artifacts.CompletePost or type(surface) is not PublicationSurface:
		raise RuntimeError("Complete-post policy requires exact typed inputs.")
	allowed_evidence_ids = (
		tuple(sorted(item.evidence_id for item in surface.packet.items))
		if recovery else surface.allowed_evidence_ids
	)
	issues = daily_blog.candidates.validate_complete_post_body(
		post.content, surface.packet, surface.projection,
		allowed_evidence_ids=allowed_evidence_ids,
		allowed_screenshot_paths=surface.allowed_image_paths,
		coverage_repositories=surface.coverage_repositories,
	)
	return tuple(issues)


#============================================
def complete_post_repair_feedback(
	post: daily_blog.artifacts.CompletePost,
	surface: PublicationSurface, output_root: str,
	*, recovery: bool = False,
) -> RepairFeedbackEnvelope | None:
	"""Project one mechanically grounded policy finding into positive repair work."""
	if type(post) is not daily_blog.artifacts.CompletePost or type(surface) is not PublicationSurface:
		raise RuntimeError("Repair feedback requires exact complete-post admission inputs.")
	if not complete_post_mechanical_eligibility(post, surface, output_root, recovery=recovery).eligible:
		return None
	reasons = _repair_feedback_reasons(complete_post_policy_issues(post, surface, recovery=recovery))
	if not reasons:
		return None
	allowed_evidence_refs = (
		tuple(sorted(item.evidence_id for item in surface.packet.items))
		if recovery else surface.allowed_evidence_ids
	)
	image_evidence_ids = {
		item.evidence_id for item in surface.allowed_images if item.publish_path in post.image_paths
	}
	return RepairFeedbackEnvelope(
		post.content_hash, reasons, tuple(sorted(_REPAIR_OBJECTIVES[item] for item in reasons)),
		_bounded_authorized_ids(post.evidence_ids + tuple(sorted(image_evidence_ids)), allowed_evidence_refs),
		_bounded_authorized_ids((), tuple(item.artifact_id for item in surface.source_artifacts)),
	)


#============================================
def repair_feedback_digest(
	posts: tuple[daily_blog.artifacts.CompletePost, ...], surface: PublicationSurface, output_root: str,
	*, recovery: bool = False,
) -> str:
	"""Return one canonical candidate-local envelope witness for an editor."""
	if type(posts) is not tuple or type(surface) is not PublicationSurface:
		raise RuntimeError("Repair feedback digest requires exact candidate and surface values.")
	envelopes = tuple(
		item for item in (
			complete_post_repair_feedback(post, surface, output_root, recovery=recovery) for post in posts
		) if item is not None
	)
	if not envelopes:
		return ""
	# The cache contract admits a feedback *envelope* digest, not a newly
	# invented collection wrapper.  Additional envelopes are already determined
	# by the editor's exact candidate witnesses and the surface-bound prompt.
	return min(envelopes, key=lambda item: item.candidate_sha256).sha256()


#============================================
def _bounded_authorized_ids(used: tuple[str, ...], admitted: tuple[str, ...]) -> tuple[str, ...]:
	"""Select at most 256 safe authority IDs, preserving used-ID membership first."""
	if type(used) is not tuple or type(admitted) is not tuple:
		raise RuntimeError("Repair feedback authority requires exact identifier tuples.")
	selected: list[str] = []
	for value in used + admitted:
		if value not in selected:
			selected.append(value)
		if len(selected) == 256:
			break
	return tuple(sorted(selected))


#============================================
def _repair_feedback_reasons(issues: tuple[str, ...]) -> tuple[str, ...]:
	"""Classify detailed policy findings into the closed positive repair vocabulary."""
	if type(issues) is not tuple or any(type(item) is not str for item in issues):
		raise RuntimeError("Repair feedback requires exact policy findings.")
	reasons = set()
	for issue in issues:
		folded = issue.casefold()
		if "image" in folded:
			reasons.add("image_authority_mismatch")
		elif "cite" in folded:
			reasons.add("citation_density_mismatch")
		elif "evidence" in folded:
			reasons.add("evidence_grounding_mismatch")
		else:
			reasons.add("presentation_policy_mismatch")
	return tuple(sorted(reasons))


#============================================
def complete_post_mechanical_eligibility(
	post: daily_blog.artifacts.CompletePost,
	surface: PublicationSurface,
	output_root: str,
	*,
	recovery: bool = False,
) -> daily_blog.artifacts.EligibilityResult:
	"""Verify provenance and output ownership without applying authored-body taste."""
	if type(surface) is not PublicationSurface:
		raise RuntimeError("Complete-post admission requires the frozen publication surface.")
	allowed_repositories = (
		surface.coverage_repositories if recovery else surface.narrative_repositories
	)
	base = daily_blog.artifacts.evaluate_eligibility(
		post, surface.source_packets, (output_root,), allowed_repositories,
	)
	reasons = set(base.reasons)
	used_ids = set(daily_blog.artifacts.evidence_references(post.content)) | set(post.evidence_ids)
	allowed_evidence_ids = (
		{item.evidence_id for item in surface.packet.items}
		if recovery else set(surface.allowed_evidence_ids)
	)
	if not used_ids.issubset(allowed_evidence_ids):
		reasons.add("unknown_evidence_reference")
	used_images = set(daily_blog.artifacts.referenced_image_paths(post.content)) | set(post.image_paths)
	if not used_images.issubset(surface.allowed_image_paths):
		reasons.update({"unapproved_image_path", "unapproved_screenshot_path"})
	if "evidence_outside_repository_scope" in reasons:
		reasons.add("repository_scope_mismatch")
	return daily_blog.artifacts.EligibilityResult(not reasons, tuple(sorted(reasons)))

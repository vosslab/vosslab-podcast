"""One survivor-scoped evidence surface for final-post editorial admission."""

# Standard Library
import dataclasses

# local repo modules
import daily_blog.artifacts
import daily_blog.candidates
import daily_blog.projection
import daily_blog.schema


#============================================
@dataclasses.dataclass(frozen=True)
class PublicationImage:
	"""One exact screenshot authority admitted with a publication surface."""

	evidence_id: str
	asset_path: str
	publish_path: str

	#============================================
	def __post_init__(self) -> None:
		"""Keep the surface image authority typed and path-confined."""
		if (
			type(self.evidence_id) is not str or not self.evidence_id
			or type(self.asset_path) is not str or not self.asset_path
			or type(self.publish_path) is not str or not self.publish_path
		):
			raise RuntimeError("Publication image authority is invalid.")
		# ASVS 5.3.2: asset paths cross a repository-to-publication file boundary.
		daily_blog.schema.validate_bundle_asset_path(self.asset_path)


#============================================
@dataclasses.dataclass(frozen=True)
class PublicationSurface:
	"""Exact editorial survivors and the material allowed into publication."""

	source_packets: tuple[daily_blog.schema.EvidencePacket, ...]
	evidence_context: daily_blog.schema.BoundedEvidenceContext
	repositories: tuple[str, ...]
	source_artifacts: tuple[daily_blog.artifacts.EditorialArtifact, ...]
	daily_outline: daily_blog.artifacts.DailyOutline = dataclasses.field(init=False)
	repo_stories: tuple[daily_blog.artifacts.RepoStory, ...] = dataclasses.field(init=False)
	packet: daily_blog.schema.EvidencePacket = dataclasses.field(init=False)
	projection: daily_blog.schema.EditorialProjection = dataclasses.field(init=False)
	allowed_evidence_ids: tuple[str, ...] = dataclasses.field(init=False)
	allowed_images: tuple[PublicationImage, ...] = dataclasses.field(init=False)

	#============================================
	@property
	def allowed_image_paths(self) -> tuple[str, ...]:
		"""Return the legacy post-body view derived from typed image authority."""
		return tuple(image.publish_path for image in self.allowed_images)

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
			or type(self.repositories) is not tuple
			or not self.repositories
			or self.repositories != tuple(sorted(set(self.repositories)))
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
		if packet_repositories != set(self.repositories):
			raise RuntimeError("Publication surface packets do not exactly cover the survivor scope.")
		# ASVS 2.2.3: validate the bounded model view and its packet union as one
		# combined authority before either editorial generation or admission uses it.
		daily_blog.projection.validate_bounded_evidence_context(
			self.source_packets, self.evidence_context,
		)
		context_repositories = tuple(sorted(card.repository for card in self.evidence_context.repositories))
		if context_repositories != self.repositories:
			raise RuntimeError("Publication surface context does not match its survivor scope.")
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
		if (
			outline[0].repositories != self.repositories
			or outline[0].packet_ids != source_packet_ids
			or tuple(sorted({repository for item in stories for repository in item.repositories}))
			!= self.repositories
		):
			raise RuntimeError("Publication surface artifacts do not match its survivor scope.")
		if any(not daily_blog.artifacts.evaluate_eligibility(
			item, self.source_packets, allowed_repositories=self.repositories,
		).eligible for item in self.source_artifacts):
			raise RuntimeError("Publication surface source artifacts are not mechanically grounded.")
		artifact_evidence_ids = {
			evidence_id for artifact in self.source_artifacts
			for evidence_id in artifact.evidence_ids
		}
		allowed_ids = {
			excerpt.evidence_id for excerpt in self.evidence_context.excerpts
		} | artifact_evidence_ids
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
		all_screenshot_images = _packet_screenshot_images(packet)
		artifact_images = {
			path for artifact in self.source_artifacts for path in artifact.image_paths
		}
		context_images = {
			image.publish_path for image in all_screenshot_images
			if image.evidence_id in allowed_ids
		}
		allowed_image_paths = artifact_images | context_images
		images_by_publish_path = {
			image.publish_path: image for image in all_screenshot_images
		}
		if not allowed_image_paths.issubset(images_by_publish_path):
			raise RuntimeError("Publication surface exposes an unapproved survivor image.")
		allowed_images = tuple(sorted(
			(images_by_publish_path[path] for path in allowed_image_paths),
			key=lambda image: (image.evidence_id, image.asset_path, image.publish_path),
		))
		# ASVS 2.2.3: later editorial stages read the cross-validated artifacts
		# from this authority instead of accepting a parallel outline/story copy.
		object.__setattr__(self, "daily_outline", outline[0])
		object.__setattr__(self, "repo_stories", tuple(sorted(
			stories, key=lambda item: item.artifact_id,
		)))
		object.__setattr__(self, "packet", packet)
		object.__setattr__(self, "projection", projection)
		object.__setattr__(self, "allowed_evidence_ids", tuple(sorted(allowed_ids)))
		object.__setattr__(self, "allowed_images", allowed_images)

#============================================
def build_surface(
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
	repositories: tuple[str, ...],
	evidence_context: daily_blog.schema.BoundedEvidenceContext,
	source_artifacts: tuple[daily_blog.artifacts.EditorialArtifact, ...],
) -> PublicationSurface:
	"""Bind one model-visible survivor context to its exact admission authority."""
	if type(packets) is not tuple or not packets or any(
		type(item) is not daily_blog.schema.EvidencePacket for item in packets
	):
		raise RuntimeError("Publication surface requires exact survivor evidence packets.")
	if (
		type(repositories) is not tuple
		or not repositories
		or repositories != tuple(sorted(set(repositories)))
	):
		raise RuntimeError("Publication surface requires a canonical survivor repository scope.")
	source_packets = tuple(sorted(packets, key=lambda item: item.packet_id))
	if type(source_artifacts) is not tuple:
		raise RuntimeError("Publication surface requires exact source artifacts.")
	ordered_artifacts = tuple(sorted(source_artifacts, key=lambda item: item.artifact_id))
	return PublicationSurface(source_packets, evidence_context, repositories, ordered_artifacts)


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
) -> tuple[PublicationImage, ...]:
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
		image = PublicationImage(item.evidence_id, item.asset_path, item.publish_path)
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
) -> daily_blog.artifacts.EligibilityResult:
	"""Combine mechanical provenance and active final-post body policy."""
	mechanical = complete_post_mechanical_eligibility(post, surface, output_root)
	policy_issues = complete_post_policy_issues(post, surface)
	reasons = set(mechanical.reasons)
	if policy_issues:
		reasons.add("publication_policy_mismatch")
		reasons.update(_policy_rejection_codes(policy_issues))
	return daily_blog.artifacts.EligibilityResult(not reasons, tuple(sorted(reasons)))


#============================================
def complete_post_policy_issues(
	post: daily_blog.artifacts.CompletePost,
	surface: PublicationSurface,
) -> tuple[str, ...]:
	"""Return explicit repair instructions against the exact model-visible surface."""
	if type(post) is not daily_blog.artifacts.CompletePost or type(surface) is not PublicationSurface:
		raise RuntimeError("Complete-post policy requires exact typed inputs.")
	issues = daily_blog.candidates.validate_complete_post_body(
		post.content, surface.packet, surface.projection,
		allowed_evidence_ids=surface.allowed_evidence_ids,
		allowed_screenshot_paths=surface.allowed_image_paths,
	)
	return tuple(issues)


#============================================
def _policy_rejection_codes(issues: tuple[str, ...]) -> tuple[str, ...]:
	"""Map detailed editor instructions to bounded operational categories."""
	codes = set()
	for issue in issues:
		if issue.startswith("Post cites unknown evidence IDs:"):
			codes.add("unknown_evidence_reference")
		elif "image path outside projected evidence" in issue:
			codes.add("unapproved_screenshot_path")
		elif issue.startswith("Project coverage") or "missing active repositories" in issue:
			codes.add("project_coverage_mismatch")
		elif "cite" in issue.casefold() or "evidence" in issue.casefold():
			codes.add("citation_density_mismatch")
		else:
			codes.add("presentation_policy_mismatch")
	return tuple(sorted(codes))


#============================================
def complete_post_mechanical_eligibility(
	post: daily_blog.artifacts.CompletePost,
	surface: PublicationSurface,
	output_root: str,
) -> daily_blog.artifacts.EligibilityResult:
	"""Verify provenance and output ownership without applying authored-body taste."""
	if type(surface) is not PublicationSurface:
		raise RuntimeError("Complete-post admission requires the frozen publication surface.")
	base = daily_blog.artifacts.evaluate_eligibility(
		post, surface.source_packets, (output_root,), surface.repositories,
	)
	reasons = set(base.reasons)
	used_ids = set(daily_blog.artifacts.evidence_references(post.content)) | set(post.evidence_ids)
	if not used_ids.issubset(surface.allowed_evidence_ids):
		reasons.add("unknown_evidence_reference")
	used_images = set(daily_blog.artifacts.referenced_image_paths(post.content)) | set(post.image_paths)
	if not used_images.issubset(surface.allowed_image_paths):
		reasons.update({"unapproved_image_path", "unapproved_screenshot_path"})
	if "evidence_outside_repository_scope" in reasons:
		reasons.add("repository_scope_mismatch")
	return daily_blog.artifacts.EligibilityResult(not reasons, tuple(sorted(reasons)))

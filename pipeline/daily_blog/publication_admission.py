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
class PublicationSurface:
	"""Exact editorial survivors and the material allowed into publication."""

	source_packets: tuple[daily_blog.schema.EvidencePacket, ...]
	packet: daily_blog.schema.EvidencePacket
	projection: daily_blog.schema.EditorialProjection
	repositories: tuple[str, ...]

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
		packet_repositories = (
			{item.repository for item in self.packet.activity}
			or {item.repository for item in self.packet.items}
		) if type(self.packet) is daily_blog.schema.EvidencePacket else set()
		if (
			source_packet_ids != tuple(sorted(source_packet_ids))
			or len(set(source_packet_ids)) != len(source_packet_ids)
			or type(self.packet) is not daily_blog.schema.EvidencePacket
			or type(self.projection) is not daily_blog.schema.EditorialProjection
			or type(self.repositories) is not tuple
			or not self.repositories
			or self.repositories != tuple(sorted(set(self.repositories)))
			or packet_repositories != set(self.repositories)
			or self.projection.packet_id != self.packet.packet_id
		):
			raise RuntimeError("Publication surface must bind one exact survivor evidence union.")
		if self.packet != _aggregate_packet(self.source_packets):
			raise RuntimeError(
				"Publication surface aggregate packet does not match its survivor provenance."
			)
		if self.projection != daily_blog.projection.build_projection(
			self.packet, dict(self.projection.projection_limits),
		):
			raise RuntimeError("Publication surface projection does not match its survivor evidence.")

#============================================
def build_surface(
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
	repositories: tuple[str, ...],
	projection_limits: dict[str, int],
) -> PublicationSurface:
	"""Aggregate exactly the Stage-6 survivor packets into one sealed surface."""
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
	packet = _aggregate_packet(source_packets)
	packet_repositories = tuple(sorted({
		repository for source in source_packets
		for repository in ({activity.repository for activity in source.activity}
			or {item.repository for item in source.items})
	}))
	if packet_repositories != repositories:
		raise RuntimeError("Publication surface packets do not exactly cover the survivor scope.")
	return PublicationSurface(
		source_packets, packet,
		daily_blog.projection.build_projection(packet, projection_limits), repositories,
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
def survivor_assets(surface: PublicationSurface, assets: dict[str, bytes]) -> dict[str, bytes]:
	"""Return only screenshot bytes referenced by the exact survivor packet."""
	if type(surface) is not PublicationSurface or type(assets) is not dict:
		raise RuntimeError("Publication surface assets require exact typed inputs.")
	required = {
		item.asset_path for item in surface.packet.items
		if item.kind == "screenshot" and type(item.asset_path) is str and item.asset_path
	}
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
	policy_issues = daily_blog.candidates.validate_complete_post_body(
		post.content, surface.packet, surface.projection,
	)
	reasons = set(mechanical.reasons)
	if policy_issues:
		reasons.add("publication_policy_mismatch")
	return daily_blog.artifacts.EligibilityResult(not reasons, tuple(sorted(reasons)))


#============================================
def complete_post_mechanical_eligibility(
	post: daily_blog.artifacts.CompletePost,
	surface: PublicationSurface,
	output_root: str,
) -> daily_blog.artifacts.EligibilityResult:
	"""Verify provenance and output ownership without applying authored-body taste."""
	if type(surface) is not PublicationSurface:
		raise RuntimeError("Complete-post admission requires the frozen publication surface.")
	return daily_blog.artifacts.evaluate_eligibility(
		post, surface.source_packets, (output_root,), surface.repositories,
	)

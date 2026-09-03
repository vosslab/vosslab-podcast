"""Portable survivor-scoped authority carried through the publication boundary."""

# Standard Library
import re

# local repo modules
import daily_blog.artifacts
import daily_blog.io_utils
import daily_blog.publication_admission
import daily_blog.schema


PUBLICATION_SURFACE_SCHEMA_VERSION = "vosslab.daily-blog.publication-surface.v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


#============================================
def publication_surface_value(
	surface: daily_blog.publication_admission.PublicationSurface,
) -> dict[str, object]:
	"""Serialize the sole survivor-scoped authority carried across publication.

	ASVS 2.2.1 and 2.2.3: this strict, canonical projection binds every
	consumer to the same evidence, repository, and image scope.
	"""
	if type(surface) is not daily_blog.publication_admission.PublicationSurface:
		raise RuntimeError("Publication surface serialization requires an exact surface.")
	value: dict[str, object] = {
		"schema_version": PUBLICATION_SURFACE_SCHEMA_VERSION,
		"surface_id": "",
		"report_date": surface.packet.report_date,
		"timezone": surface.packet.timezone,
		"aggregate_packet_id": surface.packet.packet_id,
		"source_packet_ids": list(packet.packet_id for packet in surface.source_packets),
		"repositories": list(surface.coverage_repositories),
		"source_artifacts": [
			{
				"kind": type(artifact).__name__, "artifact_id": artifact.artifact_id,
				"content_hash": artifact.content_hash,
			}
			for artifact in surface.source_artifacts
		],
		"editorial_projection_id": surface.projection.projection_id,
		"allowed_evidence_ids": list(surface.allowed_evidence_ids),
		"allowed_images": [
			{
				"evidence_id": image.evidence_id,
				"asset_path": image.asset_path,
				"publish_path": image.publish_path,
			}
			for image in surface.allowed_images
		],
	}
	value["surface_id"] = publication_surface_id(value)
	validate_publication_surface_value(value, surface.packet, surface.projection)
	return value


#============================================
def publication_surface_id(value: dict[str, object]) -> str:
	"""Return the canonical content identity excluding its self-referential ID."""
	if type(value) is not dict:
		raise RuntimeError("Publication surface identity requires an object.")
	content = dict(value)
	content.pop("surface_id", None)
	return daily_blog.io_utils.hash_value(content)


#============================================
def validate_publication_surface_value(
	value: object,
	packet: daily_blog.schema.EvidencePacket,
	projection: daily_blog.schema.EditorialProjection,
) -> dict[str, object]:
	"""Validate a portable surface against the packet and projection it seals.

	ASVS 1.5.2, 2.2.1-2.2.3, and 5.3.2: reject unexpected shape, incoherent
	provenance, or unconfined asset names at the producer/publisher trust boundary.
	"""
	if type(value) is not dict or type(packet) is not daily_blog.schema.EvidencePacket or (
		type(projection) is not daily_blog.schema.EditorialProjection
	):
		raise RuntimeError("Publication surface is invalid.")
	required = {
		"schema_version", "surface_id", "report_date", "timezone", "aggregate_packet_id",
		"source_packet_ids", "repositories", "source_artifacts", "editorial_projection_id",
		"allowed_evidence_ids", "allowed_images",
	}
	if set(value) != required or value.get("schema_version") != PUBLICATION_SURFACE_SCHEMA_VERSION:
		raise RuntimeError("Publication surface schema is unsupported.")
	if (
		type(value["surface_id"]) is not str or SHA256_RE.fullmatch(value["surface_id"]) is None
		or value["surface_id"] != publication_surface_id(value)
		or value["report_date"] != packet.report_date or value["timezone"] != packet.timezone
		or value["aggregate_packet_id"] != packet.packet_id
		or projection.packet_id != packet.packet_id
		or value["editorial_projection_id"] != projection.projection_id
	):
		raise RuntimeError("Publication surface identity is inconsistent.")
	for name in ("source_packet_ids", "repositories", "allowed_evidence_ids"):
		items = value[name]
		if not isinstance(items, list) or not items or any(type(item) is not str or not item for item in items):
			raise RuntimeError("Publication surface list is invalid.")
		if items != sorted(set(items)):
			raise RuntimeError("Publication surface list is not canonical.")
	if any(SHA256_RE.fullmatch(packet_id) is None for packet_id in value["source_packet_ids"]):
		raise RuntimeError("Publication surface source packet IDs are invalid.")
	packet_repositories = {item.repository for item in packet.activity} or {
		item.repository for item in packet.items
	}
	if value["repositories"] != sorted(packet_repositories):
		raise RuntimeError("Publication surface repositories are inconsistent.")
	# ASVS 2.2.3: source-packet IDs are provenance, not decorative metadata.  The
	# aggregate must reconstruct exactly the packet for each survivor repository.
	if value["source_packet_ids"] != list(_source_packet_ids_from_aggregate(
		packet, tuple(value["repositories"]),
	)):
		raise RuntimeError("Publication surface source packets do not match aggregate evidence.")
	if not isinstance(value["source_artifacts"], list) or not value["source_artifacts"]:
		raise RuntimeError("Publication surface source artifacts are invalid.")
	artifact_keys = []
	artifact_kinds = []
	for artifact in value["source_artifacts"]:
		if not isinstance(artifact, dict) or set(artifact) != {"kind", "artifact_id", "content_hash"}:
			raise RuntimeError("Publication surface source artifact is invalid.")
		if (
			type(artifact["kind"]) is not str or artifact["kind"] not in {"DailyOutline", "RepoStory"}
			or type(artifact["artifact_id"]) is not str
			or daily_blog.artifacts.ARTIFACT_ID_RE.fullmatch(artifact["artifact_id"]) is None
			or type(artifact["content_hash"]) is not str or SHA256_RE.fullmatch(artifact["content_hash"]) is None
		):
			raise RuntimeError("Publication surface source artifact is invalid.")
		artifact_keys.append(artifact["artifact_id"])
		artifact_kinds.append(artifact["kind"])
	if artifact_keys != sorted(set(artifact_keys)):
		raise RuntimeError("Publication surface source artifacts are not canonical.")
	if artifact_kinds.count("DailyOutline") != 1 or not artifact_kinds.count("RepoStory"):
		raise RuntimeError("Publication surface source artifacts do not describe an editorial survivor set.")
	if not isinstance(value["allowed_images"], list):
		raise RuntimeError("Publication surface images are invalid.")
	packet_items = {item.evidence_id: item for item in packet.items}
	seen_evidence_ids: set[str] = set()
	seen_assets: set[str] = set()
	seen_publish_paths: set[str] = set()
	image_keys = []
	for image in value["allowed_images"]:
		if not isinstance(image, dict) or set(image) != {"evidence_id", "asset_path", "publish_path"}:
			raise RuntimeError("Publication surface image is invalid.")
		evidence_id = image["evidence_id"]
		asset_path = image["asset_path"]
		publish_path = image["publish_path"]
		if type(evidence_id) is not str or type(asset_path) is not str or type(publish_path) is not str:
			raise RuntimeError("Publication surface image is invalid.")
		daily_blog.schema.validate_bundle_asset_path(asset_path)
		item = packet_items.get(evidence_id)
		if (
			item is None or item.kind != "screenshot" or item.asset_path != asset_path
			or item.publish_path != publish_path or evidence_id not in value["allowed_evidence_ids"]
		):
			raise RuntimeError("Publication surface image provenance is invalid.")
		if (
			evidence_id in seen_evidence_ids or asset_path in seen_assets
			or publish_path in seen_publish_paths
		):
			raise RuntimeError("Publication surface images are not one-to-one.")
		seen_evidence_ids.add(evidence_id)
		seen_assets.add(asset_path)
		seen_publish_paths.add(publish_path)
		image_keys.append((evidence_id, asset_path, publish_path))
	if image_keys != sorted(image_keys):
		raise RuntimeError("Publication surface images are not canonical.")
	projection_ids = {excerpt.evidence_id for excerpt in projection.excerpts}
	if value["allowed_evidence_ids"] != sorted(projection_ids | seen_evidence_ids):
		raise RuntimeError("Publication surface evidence scope does not equal its evidence channels.")
	return dict(value)


#============================================
def _source_packet_ids_from_aggregate(
	packet: daily_blog.schema.EvidencePacket,
	repositories: tuple[str, ...],
) -> tuple[str, ...]:
	"""Reconstruct exact repository packets from a survivor aggregate packet."""
	if type(packet) is not daily_blog.schema.EvidencePacket or (
		type(repositories) is not tuple or not repositories
	):
		raise RuntimeError("Publication surface aggregate reconstruction is invalid.")
	packet_ids = []
	for repository in repositories:
		mirrors = [
			mirror.to_dict() for mirror in packet.mirrors
			if mirror.to_dict().get("repository") == repository
		]
		activity = [item for item in packet.activity if item.repository == repository]
		items = [item for item in packet.items if item.repository == repository]
		if not items or {item.repository for item in items} != {repository}:
			raise RuntimeError("Publication surface aggregate evidence lacks a survivor repository.")
		reconstructed = daily_blog.schema.EvidencePacket.create(
			packet.report_date, packet.timezone, packet.complete,
			packet.collection_limits.to_dict(), mirrors, activity, items,
		)
		packet_ids.append(reconstructed.packet_id)
	return tuple(sorted(packet_ids))

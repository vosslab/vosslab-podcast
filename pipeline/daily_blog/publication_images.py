"""Resolve editorial image choices into one publication-owned asset set."""

# Standard Library
import dataclasses
import json
import pathlib
import re

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.editorial_stage_config
import daily_blog.io_utils
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.loader
import daily_blog.publication_admission
import daily_blog.schema


MAX_DECORATOR_IMAGES = 3


@dataclasses.dataclass(frozen=True)
class ImagePlacement:
	"""One editorial image identity and deterministic prose-block location."""

	image_id: str
	after_block: int
	alt_text: str


@dataclasses.dataclass(frozen=True)
class ImageDecorationPlan:
	"""Bounded advisory image choices returned by an editorial decorator."""

	placements: tuple[ImagePlacement, ...]

	#============================================
	def __post_init__(self) -> None:
		"""Reject ambiguous or unbounded placements before deterministic insertion."""
		if (
			type(self.placements) is not tuple
			or len(self.placements) > MAX_DECORATOR_IMAGES
			or len({item.image_id for item in self.placements}) != len(self.placements)
			or any(
				type(item.image_id) is not str or not item.image_id
				or type(item.after_block) is not int or item.after_block < 0
				or type(item.alt_text) is not str or not item.alt_text.strip()
				or len(item.alt_text) > 160
				for item in self.placements
			)
		):
			raise RuntimeError("Image decoration plan is invalid.")


#============================================
def parse_image_decoration(
	response: str,
	catalog: "PublicationImageCatalog",
	block_count: int,
) -> ImageDecorationPlan | None:
	"""Tolerantly parse a bounded decorator response; malformed output means no change."""
	if type(response) is not str or type(catalog) is not PublicationImageCatalog:
		raise RuntimeError("Image decoration parsing requires exact typed inputs.")
	if type(block_count) is not int or block_count < 1:
		raise RuntimeError("Image decoration requires a positive prose-block count.")
	# ASVS 1.5.2 and 2.2.1: deserialize only JSON and allowlist its complete
	# bounded shape before any editorial value reaches publication construction.
	try:
		value = json.loads(response.strip())
	except (json.JSONDecodeError, TypeError):
		return None
	if not isinstance(value, dict) or set(value) != {"placements"}:
		return None
	items = value["placements"]
	if not isinstance(items, list) or len(items) > MAX_DECORATOR_IMAGES:
		return None
	allowed = {item.evidence_id for item in catalog.images}
	placements = []
	for item in items:
		if not isinstance(item, dict) or set(item) != {"image_id", "after_block", "alt_text"}:
			return None
		if item["image_id"] not in allowed or not 0 <= item["after_block"] < block_count:
			return None
		try:
			placements.append(ImagePlacement(
				item["image_id"], item["after_block"], item["alt_text"],
			))
		except (TypeError, RuntimeError):
			return None
	try:
		return ImageDecorationPlan(tuple(placements))
	except RuntimeError:
		return None


#============================================
def decoratable_blocks(post: daily_blog.artifacts.CompletePost) -> tuple[str, ...]:
	"""Return stable nonempty Markdown blocks addressable by the decorator."""
	if type(post) is not daily_blog.artifacts.CompletePost:
		raise RuntimeError("Image decoration requires one complete post.")
	body = re.sub(r"\A---\n.*?\n---\n", "", post.content, count=1, flags=re.DOTALL)
	return tuple(block for block in body.split("\n\n") if block.strip())


#============================================
def apply_image_decoration(
	post: daily_blog.artifacts.CompletePost,
	catalog: "PublicationImageCatalog",
	plan: ImageDecorationPlan | None,
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
) -> daily_blog.artifacts.CompletePost:
	"""Insert resolved image paths, preserving the incumbent on absent or unusable advice."""
	if (
		type(post) is not daily_blog.artifacts.CompletePost
		or type(catalog) is not PublicationImageCatalog
		or type(packets) is not tuple
		or tuple(sorted(packet.packet_id for packet in packets)) != post.packet_ids
	):
		raise RuntimeError("Image decoration requires exact typed inputs.")
	if plan is None or not plan.placements or post.image_paths:
		return post
	blocks = list(decoratable_blocks(post))
	by_id = {item.evidence_id: item for item in catalog.images}
	if any(item.image_id not in by_id or item.after_block >= len(blocks) for item in plan.placements):
		return post
	insertions: dict[int, list[str]] = {}
	for placement in plan.placements:
		image = by_id[placement.image_id]
		# ASVS 1.1.2: escape at the final Markdown construction boundary; paths
		# remain trusted machine catalog values rather than decorator output.
		alt = re.sub(r"[\[\]\r\n]+", " ", placement.alt_text).strip()
		if not alt:
			return post
		insertions.setdefault(placement.after_block, []).append(
			f"![{alt}]({image.markdown_path}) <!-- evidence: {image.evidence_id} -->"
		)
	decorated = []
	for index, block in enumerate(blocks):
		decorated.append(block)
		decorated.extend(insertions.get(index, ()))
	content = "\n\n".join(decorated) + "\n"
	evidence_ids = tuple(sorted(set(post.evidence_ids) | {item.image_id for item in plan.placements}))
	image_paths = tuple(sorted(by_id[item.image_id].markdown_path for item in plan.placements))
	return daily_blog.artifacts.CompletePost.create(
		post.report_date, packets, post.repositories, content, evidence_ids,
		post.publication_id, post.output_path, image_paths,
	)


#============================================
def decorate_post(
	post: daily_blog.artifacts.CompletePost,
	catalog: "PublicationImageCatalog",
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
	runner: object,
	budget: daily_blog.agents.RouteBudget,
	route: daily_blog.editorial_stage_config.RoleRoute,
	working_directory: str,
	*, retry_attempts: int,
	maximum_parallel_calls: int,
) -> daily_blog.artifacts.CompletePost:
	"""Attempt one optional image-decoration call and preserve the post on any LLM failure."""
	if not catalog.images or post.image_paths:
		return post
	prompts = daily_blog.prompt_registry.loader.load_prompt_set(
		daily_blog.prompt_registry.definitions.IMAGE_DECORATION_PROMPT_SET,
	)
	catalog_json = json.dumps({
		"images": [
			{
				"image_id": item.evidence_id,
				"repository": item.repository,
				"description": item.description,
			}
			for item in catalog.images
		],
		"prose_block_count": len(decoratable_blocks(post)),
	}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
	prompt = prompts.render(
		daily_blog.prompt_registry.definitions.IMAGE_DECORATION_RESOURCE,
		{"post": post.content, "catalog": catalog_json},
	)
	identity = daily_blog.io_utils.hash_value({
		"post": post.content_hash,
		"catalog": catalog.to_dict(),
		"prompt": prompts.identity_dict(),
	})
	request = daily_blog.agents.RouteRequest(
		"image_decorator_" + identity[:24], "image_decoration", route, prompt,
		working_directory, role="image_decorator", retry_attempts=retry_attempts,
		maximum_parallel_calls=maximum_parallel_calls, input_hash=identity,
		contract_version=daily_blog.prompt_registry.definitions.IMAGE_DECORATION_PROMPT_SET.version,
		cache_input_hash=identity,
	)
	result = daily_blog.agents.execute_requests(
		[request], runner, 1, budget,
	)[0]
	if not result.ok:
		return post
	plan = parse_image_decoration(result.text, catalog, len(decoratable_blocks(post)))
	return apply_image_decoration(post, catalog, plan, packets)


@dataclasses.dataclass(frozen=True)
class CatalogImage:
	"""One machine-discovered image available for editorial selection."""

	evidence_id: str
	repository: str
	source_path: str
	git_blob_hash: str
	asset_path: str
	markdown_path: str
	description: str

	#============================================
	def to_dict(self) -> dict[str, str]:
		"""Return bounded image metadata without embedding image bytes."""
		return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class PublicationImageCatalog:
	"""Stable producer-side image choices discovered for one report date."""

	report_date: str
	images: tuple[CatalogImage, ...]

	#============================================
	def __post_init__(self) -> None:
		"""Require canonical one-to-one evidence, asset, and Markdown identities."""
		if (
			type(self.report_date) is not str
			or type(self.images) is not tuple
			or tuple(sorted(self.images, key=lambda item: item.evidence_id)) != self.images
			or len({item.evidence_id for item in self.images}) != len(self.images)
			or len({item.asset_path for item in self.images}) != len(self.images)
			or len({item.markdown_path for item in self.images}) != len(self.images)
		):
			raise RuntimeError("Publication image catalog is inconsistent.")

	#============================================
	def to_dict(self) -> dict:
		"""Return the inspectable byte-free candidate catalog."""
		return {
			"report_date": self.report_date,
			"images": [item.to_dict() for item in self.images],
		}


#============================================
def build_image_catalog(
	packet: daily_blog.schema.EvidencePacket,
	available_assets: dict[str, bytes],
) -> PublicationImageCatalog:
	"""Catalog every discovered screenshot without publishing any of its bytes."""
	if type(packet) is not daily_blog.schema.EvidencePacket or type(available_assets) is not dict:
		raise RuntimeError("Publication image catalog requires exact evidence inputs.")
	images = []
	for item in packet.items:
		if item.kind != "screenshot":
			continue
		asset_path = daily_blog.schema.validate_bundle_asset_path(item.asset_path)
		if type(available_assets.get(asset_path)) is not bytes:
			raise RuntimeError("Publication image catalog is missing discovered image bytes.")
		pure = pathlib.PurePosixPath(item.publish_path)
		if (
			pure.is_absolute() or len(pure.parts) != 2
			or pure.parts[0] != packet.report_date or pure.name in {"", ".", ".."}
		):
			raise RuntimeError("Publication image catalog route is not date-owned.")
		images.append(CatalogImage(
			item.evidence_id, item.repository, item.path, item.blob_hash,
			asset_path, item.publish_path, item.content,
		))
	return PublicationImageCatalog(
		packet.report_date,
		tuple(sorted(images, key=lambda item: item.evidence_id)),
	)


@dataclasses.dataclass(frozen=True)
class SelectedPublicationImage:
	"""One stable evidence image selected by the final Markdown."""

	evidence_id: str
	source_asset_path: str
	markdown_path: str
	destination_path: str

	#============================================
	def to_dict(self) -> dict[str, str]:
		"""Return the inspectable producer-owned routing decision."""
		return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class PublicationImageSelection:
	"""Exact images and bytes required by one final post."""

	report_date: str
	images: tuple[SelectedPublicationImage, ...]
	assets: dict[str, bytes]

	#============================================
	def __post_init__(self) -> None:
		"""Require canonical one-to-one selected image routes."""
		if (
			type(self.report_date) is not str
			or type(self.images) is not tuple
			or type(self.assets) is not dict
			or tuple(sorted(self.images, key=lambda item: item.markdown_path)) != self.images
			or len({item.evidence_id for item in self.images}) != len(self.images)
			or len({item.markdown_path for item in self.images}) != len(self.images)
			or {item.source_asset_path for item in self.images} != set(self.assets)
			or any(type(contents) is not bytes for contents in self.assets.values())
		):
			raise RuntimeError("Publication image selection is inconsistent.")

	#============================================
	def to_dict(self) -> dict:
		"""Return selection identities and routes without duplicating image bytes."""
		return {
			"report_date": self.report_date,
			"images": [item.to_dict() for item in self.images],
		}


#============================================
def resolve_final_post_images(
	surface: daily_blog.publication_admission.PublicationSurface,
	post: daily_blog.artifacts.CompletePost,
	available_assets: dict[str, bytes],
) -> PublicationImageSelection:
	"""Resolve only final Markdown references against machine-known image identities."""
	if (
		type(surface) is not daily_blog.publication_admission.PublicationSurface
		or type(post) is not daily_blog.artifacts.CompletePost
		or type(available_assets) is not dict
	):
		raise RuntimeError("Final publication image resolution requires exact typed inputs.")
	by_markdown_path = {image.publish_path: image for image in surface.allowed_images}
	if not set(post.image_paths).issubset(by_markdown_path):
		raise RuntimeError("Final post references an image outside its machine-owned catalog.")
	selected = []
	assets = {}
	for markdown_path in post.image_paths:
		image = by_markdown_path[markdown_path]
		asset_path = daily_blog.schema.validate_bundle_asset_path(image.asset_path)
		contents = available_assets.get(asset_path)
		if type(contents) is not bytes:
			raise RuntimeError("Final post references an image whose bytes are unavailable.")
		pure = pathlib.PurePosixPath(markdown_path)
		if (
			pure.is_absolute()
			or len(pure.parts) != 2
			or pure.parts[0] != post.report_date
			or pure.name in {"", ".", ".."}
		):
			raise RuntimeError("Final post image route is not date-owned.")
		selected.append(SelectedPublicationImage(
			image.evidence_id,
			asset_path,
			markdown_path,
			f"docs/blog/posts/{markdown_path}",
		))
		assets[asset_path] = contents
	return PublicationImageSelection(
		post.report_date,
		tuple(sorted(selected, key=lambda item: item.markdown_path)),
		assets,
	)

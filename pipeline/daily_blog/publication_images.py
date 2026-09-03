"""Resolve editorial image choices into one publication-owned asset set."""

# Standard Library
import dataclasses
import pathlib

# local repo modules
import daily_blog.artifacts
import daily_blog.publication_admission
import daily_blog.schema


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

"""Bounded, identity-bound repository editorial context for Stage 5 prompts."""

# Standard Library
import dataclasses

# local repo modules
import daily_blog.artifacts
import daily_blog.bounded_artifact_context
import daily_blog.io_utils
import daily_blog.schema


STORY_CONTEXT_SCHEMA_VERSION = (
	daily_blog.bounded_artifact_context.BOUNDED_ARTIFACT_CONTEXT_SCHEMA_VERSION
)


@dataclasses.dataclass(frozen=True)
class BoundedRepositoryEditorialContext:
	"""One immutable Stage 5 authority for story and outline prompt frames."""

	story_context: daily_blog.bounded_artifact_context.BoundedArtifactContext
	outline_context: daily_blog.bounded_artifact_context.BoundedArtifactContext
	context_id: str
	model_context_id: str
	schema_version: str = STORY_CONTEXT_SCHEMA_VERSION

	def content_dict(self) -> dict[str, object]:
		return {
			"schema_version": self.schema_version,
			"story_context": self.story_context.to_dict(),
			"outline_context": self.outline_context.to_dict(),
		}

	def to_dict(self) -> dict[str, object]:
		value = self.content_dict()
		value["context_id"] = self.context_id
		value["model_context_id"] = self.model_context_id
		return value

	@classmethod
	def create(
		cls,
		stories: tuple[daily_blog.artifacts.RepoStory, ...],
		outlines: tuple[daily_blog.artifacts.RepoOutline, ...],
		packets: tuple[daily_blog.schema.EvidencePacket, ...],
		story_context_chars: int,
		outline_context_chars: int,
	) -> "BoundedRepositoryEditorialContext":
		"""Seal both prompt frames from one exact survivor universe."""
		model_packet_ids = {
			item.packet_id: daily_blog.schema.model_cache_packet_identity(item)
			for item in packets
		}
		story_context = daily_blog.bounded_artifact_context.BoundedArtifactContext.create(
			stories, story_context_chars, "story", model_packet_ids,
		)
		outline_context = daily_blog.bounded_artifact_context.BoundedArtifactContext.create(
			outlines, outline_context_chars, "outline", model_packet_ids,
		)
		if (
			tuple(item.repository for item in story_context.stories)
			!= tuple(item.repository for item in outline_context.stories)
		):
			raise RuntimeError("Bounded editorial context sources do not share repository scope.")
		value = cls(story_context, outline_context, "", "")
		return dataclasses.replace(
			value,
			context_id=daily_blog.io_utils.hash_value(value.content_dict()),
			model_context_id=daily_blog.io_utils.hash_value({
				"schema_version": value.schema_version,
				"story_model_context_id": story_context.model_context_id,
				"outline_model_context_id": outline_context.model_context_id,
			}),
		)

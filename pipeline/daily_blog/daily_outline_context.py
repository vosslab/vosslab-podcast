"""Bounded, identity-bound repository-story context for Stage 5 prompts."""

# Standard Library
import dataclasses

# local repo modules
import daily_blog.artifacts
import daily_blog.bounded_artifact_context
import daily_blog.daily_outline_prompts
import daily_blog.io_utils
import daily_blog.projection
import daily_blog.prompt_registry.loader
import daily_blog.schema


STORY_CONTEXT_SCHEMA_VERSION = (
	daily_blog.bounded_artifact_context.BOUNDED_ARTIFACT_CONTEXT_SCHEMA_VERSION
)
COMPARISON_CONTEXT_PROJECTION_VERSION = "daily-outline-comparison-fair-scale.v1"
_SCALE_DENOMINATOR = 1000


#============================================
@dataclasses.dataclass(frozen=True)
class BoundedRepositoryEditorialContext:
	"""One immutable Stage 5 authority for story and outline prompt frames."""

	story_context: daily_blog.bounded_artifact_context.BoundedArtifactContext
	outline_context: daily_blog.bounded_artifact_context.BoundedArtifactContext
	context_id: str
	model_context_id: str
	schema_version: str = STORY_CONTEXT_SCHEMA_VERSION

	#============================================
	def content_dict(self) -> dict[str, object]:
		return {
			"schema_version": self.schema_version,
			"story_context": self.story_context.to_dict(),
			"outline_context": self.outline_context.to_dict(),
		}

	#============================================
	def to_dict(self) -> dict[str, object]:
		value = self.content_dict()
		value["context_id"] = self.context_id
		value["model_context_id"] = self.model_context_id
		return value

	#============================================
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


#============================================
@dataclasses.dataclass(frozen=True)
class DailyOutlineComparisonContext:
	"""A pair-specific, fair bounded view for one Stage 5 outline review."""

	story_context: daily_blog.bounded_artifact_context.BoundedArtifactContext
	outline_context: daily_blog.bounded_artifact_context.BoundedArtifactContext
	evidence_context: daily_blog.schema.BoundedEvidenceContext
	candidate_a_sha256: str
	candidate_b_sha256: str
	shared_scale: int
	context_id: str
	model_context_id: str
	projection_version: str = COMPARISON_CONTEXT_PROJECTION_VERSION

	#============================================
	def content_dict(self) -> dict[str, object]:
		"""Return durable provenance for the exact comparison projection."""
		return {
			"projection_version": self.projection_version,
			"story_context": self.story_context.to_dict(),
			"outline_context": self.outline_context.to_dict(),
			"evidence_context": self.evidence_context.to_dict(),
			"candidate_a_sha256": self.candidate_a_sha256,
			"candidate_b_sha256": self.candidate_b_sha256,
			"shared_scale": self.shared_scale,
		}

	#============================================
	def model_content_dict(self) -> dict[str, object]:
		"""Return the route-visible identities that define cache reuse."""
		return {
			"projection_version": self.projection_version,
			"story_model_context_id": self.story_context.model_context_id,
			"outline_model_context_id": self.outline_context.model_context_id,
			"evidence_model_context_id": self.evidence_context.model_context_id,
			"candidate_a_sha256": self.candidate_a_sha256,
			"candidate_b_sha256": self.candidate_b_sha256,
			"shared_scale": self.shared_scale,
		}

	#============================================
	def cache_identity(self) -> dict[str, object]:
		"""Return the complete role-view cache identity."""
		return {
			"projection_version": self.projection_version,
			"model_context_id": self.model_context_id,
			**self.model_content_dict(),
		}

	#============================================
	@classmethod
	def create(
		cls,
		stories: tuple[daily_blog.artifacts.RepoStory, ...],
		outlines: tuple[daily_blog.artifacts.RepoOutline, ...],
		packets: tuple[daily_blog.schema.EvidencePacket, ...],
		evidence_context: daily_blog.schema.BoundedEvidenceContext,
		candidate_a: str,
		candidate_b: str,
		prompts: daily_blog.prompt_registry.loader.LoadedPromptSet,
	) -> "DailyOutlineComparisonContext":
		"""Maximize a common source scale under the actual reviewer prompt limit."""
		if type(candidate_a) is not str or type(candidate_b) is not str:
			raise RuntimeError("Daily-outline comparison candidates must be text.")
		packet_ids = {
			item.packet_id: daily_blog.schema.model_cache_packet_identity(item)
			for item in packets
		}
		story_minimum = daily_blog.bounded_artifact_context.minimum_artifact_context(
			stories, "story", packet_ids,
			daily_blog.daily_outline_prompts.MAX_STORIES_CONTEXT_CHARS,
		)
		outline_minimum = daily_blog.bounded_artifact_context.minimum_artifact_context(
			outlines, "outline", packet_ids,
			daily_blog.daily_outline_prompts.MAX_REPOSITORY_OUTLINES_CONTEXT_CHARS,
		)
		evidence_minimum = daily_blog.projection.minimum_evidence_context(
			packets, evidence_context,
		)
		# Projection caches avoid rebuilding equal caps during the bounded search.
		story_by_cap = {story_minimum.context_chars: story_minimum}
		outline_by_cap = {outline_minimum.context_chars: outline_minimum}
		evidence_by_cap = {evidence_minimum.context_chars: evidence_minimum}

		def build(scale: int) -> "DailyOutlineComparisonContext":
			story_cap = max(story_minimum.context_chars, _scaled_cap(
				daily_blog.daily_outline_prompts.MAX_STORIES_CONTEXT_CHARS, scale,
			))
			story = story_by_cap.get(story_cap)
			if story is None:
				story = daily_blog.bounded_artifact_context.BoundedArtifactContext.create(
					stories, story_cap, "story", packet_ids,
				)
				story_by_cap[story_cap] = story
			outline_cap = max(outline_minimum.context_chars, _scaled_cap(
				daily_blog.daily_outline_prompts.MAX_REPOSITORY_OUTLINES_CONTEXT_CHARS, scale,
			))
			outline = outline_by_cap.get(outline_cap)
			if outline is None:
				outline = daily_blog.bounded_artifact_context.BoundedArtifactContext.create(
					outlines, outline_cap, "outline", packet_ids,
				)
				outline_by_cap[outline_cap] = outline
			evidence_cap = max(evidence_minimum.context_chars, _scaled_cap(
				daily_blog.daily_outline_prompts.MAX_EVIDENCE_CONTEXT_CHARS, scale,
			))
			evidence = evidence_by_cap.get(evidence_cap)
			if evidence is None:
				evidence = daily_blog.projection.build_bounded_evidence_context(
					packets, dict(evidence_context.projection_limits), evidence_cap,
				)
				evidence_by_cap[evidence_cap] = evidence
			value = cls(
				story, outline, evidence, daily_blog.io_utils.sha256_text(candidate_a),
				daily_blog.io_utils.sha256_text(candidate_b), scale, "", "",
			)
			return dataclasses.replace(
				value,
				context_id=daily_blog.io_utils.hash_value(value.content_dict()),
				model_context_id=daily_blog.io_utils.hash_value(value.model_content_dict()),
			)

		def fits(scale: int) -> DailyOutlineComparisonContext | None:
			context = build(scale)
			try:
				daily_blog.daily_outline_prompts.render_daily_outline_comparison(
					context.story_context.render_context(), context.outline_context.render_context(),
					context.evidence_context.render_context(context.evidence_context.context_chars),
					candidate_a, candidate_b, prompts,
				)
			except daily_blog.daily_outline_prompts.DailyOutlinePromptOverflow:
				return None
			return context

		minimum = fits(0)
		if minimum is None:
			raise RuntimeError("Daily-outline comparison cannot fit every survivor under its prompt limit.")
		# The fitting scale is monotonic, so binary search finds the greatest shared view.
		low, high, best = 0, _SCALE_DENOMINATOR, minimum
		while low < high:
			middle = (low + high + 1) // 2
			candidate = fits(middle)
			if candidate is None:
				high = middle - 1
			else:
				low, best = middle, candidate
		return best


#============================================
def _scaled_cap(maximum: int, scale: int) -> int:
	"""Return one deterministic common-scale component cap."""
	return maximum * scale // _SCALE_DENOMINATOR

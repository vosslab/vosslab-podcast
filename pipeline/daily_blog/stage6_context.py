"""One bounded survivor-scoped model view for Stage 6 and recovery."""

# Standard Library
import dataclasses
import json

# local repo modules
import daily_blog.artifacts
import daily_blog.bounded_artifact_context
import daily_blog.io_utils
import daily_blog.projection
import daily_blog.recovery
import daily_blog.schema


MAX_STAGE6_CONTEXT_CHARS = 60000
STAGE6_CONTEXT_PROJECTION_VERSION = "stage6-survivor-fair-scale.v1"
_SCALE_DENOMINATOR = 1000


class Stage6ContextCapacityError(RuntimeError):
	"""Every survivor cannot fit inside the complete Stage 6 model frame."""


#============================================
def canonical_context(value: object) -> str:
	"""Return one canonical complete prompt frame without partial serialized data."""
	return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


#============================================
@dataclasses.dataclass(frozen=True)
class Stage6PromptContext:
	"""Exact bounded artifact and evidence projections from one survivor authority."""

	daily_outline_context: daily_blog.bounded_artifact_context.BoundedArtifactContext
	repo_story_context: daily_blog.bounded_artifact_context.BoundedArtifactContext
	evidence_context: daily_blog.schema.BoundedEvidenceContext
	shared_scale: int
	context_id: str
	model_context_id: str
	projection_version: str = STAGE6_CONTEXT_PROJECTION_VERSION

	def content_dict(self) -> dict[str, object]:
		"""Return portable provenance for every Stage 6 model-visible source."""
		return {
			"projection_version": self.projection_version,
			"daily_outline_context": self.daily_outline_context.to_dict(),
			"repo_story_context": self.repo_story_context.to_dict(),
			"evidence_context": self.evidence_context.to_dict(),
			"shared_scale": self.shared_scale,
		}

	def model_content_dict(self) -> dict[str, object]:
		"""Return the portable identities which define semantic route reuse."""
		return {
			"projection_version": self.projection_version,
			"daily_outline_model_context_id": self.daily_outline_context.model_context_id,
			"repo_story_model_context_id": self.repo_story_context.model_context_id,
			"evidence_model_context_id": self.evidence_context.model_context_id,
			"shared_scale": self.shared_scale,
		}

	def to_dict(self) -> dict[str, object]:
		"""Serialize the bounded context with both verifiable identities."""
		value = self.content_dict()
		value["context_id"] = self.context_id
		value["model_context_id"] = self.model_context_id
		return value

	def cache_identity(self) -> dict[str, object]:
		"""Return the host-portable semantic identity used for route reuse."""
		return {
			"projection_version": self.projection_version,
			"model_context_id": self.model_context_id,
			**self.model_content_dict(),
		}

	def _artifact_value(
		self, context: daily_blog.bounded_artifact_context.BoundedArtifactContext,
	) -> dict[str, object]:
		"""Return one exact model frame with its independently verifiable identity."""
		value = context.model_content_dict()
		value["model_context_id"] = context.model_context_id
		return value

	def frame(self) -> dict[str, object]:
		"""Return the complete primary writer/editor source frame."""
		return {
			"daily_outline": self._artifact_value(self.daily_outline_context),
			"evidence": json.loads(
				self.evidence_context.render_context(self.evidence_context.context_chars),
			),
			"repo_stories": self._artifact_value(self.repo_story_context),
		}

	def render_context(self) -> str:
		"""Render the primary Stage 6 frame within its declared total envelope."""
		context = canonical_context(self.frame())
		if len(context) > MAX_STAGE6_CONTEXT_CHARS:
			raise Stage6ContextCapacityError(
				"Stage 6 survivor context exceeds its complete bounded limit."
			)
		return context

	def render_recovery_context(self, rung: daily_blog.recovery.RecoveryRung) -> str:
		"""Render one lower editorial path from the same bounded source authority."""
		if rung is daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION:
			value = {"daily_outline": self._artifact_value(self.daily_outline_context)}
		elif rung is daily_blog.recovery.RecoveryRung.REPOSITORY_STORY_MERGE:
			value = {"repo_stories": self._artifact_value(self.repo_story_context)}
		else:
			raise RuntimeError("Stage 6 recovery context rung is unsupported.")
		value["evidence"] = json.loads(
			self.evidence_context.render_context(self.evidence_context.context_chars),
		)
		context = canonical_context(value)
		if len(context) > MAX_STAGE6_CONTEXT_CHARS:
			raise Stage6ContextCapacityError(
				"Stage 6 recovery survivor context exceeds its complete bounded limit."
			)
		return context

	def validate_against(
		self,
		daily_outline: daily_blog.artifacts.DailyOutline,
		repo_stories: tuple[daily_blog.artifacts.RepoStory, ...],
		packets: tuple[daily_blog.schema.EvidencePacket, ...],
	) -> None:
		"""Prove every prompt projection is an exact slice of the survivor sources."""
		if (
			self.projection_version != STAGE6_CONTEXT_PROJECTION_VERSION
			or type(self.shared_scale) is not int
			or not 0 <= self.shared_scale <= _SCALE_DENOMINATOR
			or self.daily_outline_context.artifact_kind != "daily_outline"
			or self.repo_story_context.artifact_kind != "story"
		):
			raise RuntimeError("Stage 6 prompt context is invalid.")
		model_packet_ids = {
			packet.packet_id: daily_blog.schema.model_cache_packet_identity(packet)
			for packet in packets
		}
		self.daily_outline_context.validate_against((daily_outline,), model_packet_ids)
		self.repo_story_context.validate_against(repo_stories, model_packet_ids)
		daily_blog.projection.validate_bounded_evidence_context(
			packets, self.evidence_context,
		)
		if self.context_id != daily_blog.io_utils.hash_value(self.content_dict()):
			raise RuntimeError("Stage 6 prompt context identity is inconsistent.")
		if self.model_context_id != daily_blog.io_utils.hash_value(self.model_content_dict()):
			raise RuntimeError("Stage 6 prompt model identity is inconsistent.")
		self.render_context()
		self.render_recovery_context(daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION)
		self.render_recovery_context(daily_blog.recovery.RecoveryRung.REPOSITORY_STORY_MERGE)


#============================================
def build_stage6_prompt_context(
	daily_outline: daily_blog.artifacts.DailyOutline,
	repo_stories: tuple[daily_blog.artifacts.RepoStory, ...],
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
	projection_limits: dict[str, int],
) -> Stage6PromptContext:
	"""Maximize one fair survivor view under the complete Stage 6 frame limit."""
	if (
		type(daily_outline) is not daily_blog.artifacts.DailyOutline
		or type(repo_stories) is not tuple or not repo_stories
		or any(type(item) is not daily_blog.artifacts.RepoStory for item in repo_stories)
		or type(packets) is not tuple or not packets
	):
		raise RuntimeError("Stage 6 prompt context requires exact survivor sources.")
	model_packet_ids = {
		packet.packet_id: daily_blog.schema.model_cache_packet_identity(packet)
		for packet in packets
	}
	full_evidence = daily_blog.projection.build_bounded_evidence_context(
		packets, projection_limits,
		min(MAX_STAGE6_CONTEXT_CHARS, projection_limits["context_chars"]),
	)
	full_outline = daily_blog.bounded_artifact_context.BoundedArtifactContext.create(
		(daily_outline,), MAX_STAGE6_CONTEXT_CHARS, "daily_outline", model_packet_ids,
	)
	full_stories = daily_blog.bounded_artifact_context.BoundedArtifactContext.create(
		repo_stories, MAX_STAGE6_CONTEXT_CHARS, "story", model_packet_ids,
	)
	full = Stage6PromptContext(full_outline, full_stories, full_evidence, _SCALE_DENOMINATOR, "", "")
	full = dataclasses.replace(
		full,
		context_id=daily_blog.io_utils.hash_value(full.content_dict()),
		model_context_id=daily_blog.io_utils.hash_value(full.model_content_dict()),
	)
	if _fits_complete_frame(full):
		full.validate_against(daily_outline, repo_stories, packets)
		return full
	minimum_outline = daily_blog.bounded_artifact_context.minimum_artifact_context(
		(daily_outline,), "daily_outline", model_packet_ids, MAX_STAGE6_CONTEXT_CHARS,
	)
	minimum_stories = daily_blog.bounded_artifact_context.minimum_artifact_context(
		repo_stories, "story", model_packet_ids, MAX_STAGE6_CONTEXT_CHARS,
	)
	minimum_evidence = daily_blog.projection.minimum_evidence_context(
		packets, full_evidence,
	)
	# Projection caches avoid rebuilding component frames across scale probes.
	outline_by_cap = {
		minimum_outline.context_chars: minimum_outline,
		full_outline.context_chars: full_outline,
	}
	stories_by_cap = {
		minimum_stories.context_chars: minimum_stories,
		full_stories.context_chars: full_stories,
	}
	evidence_by_cap = {
		minimum_evidence.context_chars: minimum_evidence,
		full_evidence.context_chars: full_evidence,
	}

	def build(scale: int) -> Stage6PromptContext:
		outline_cap = max(
			minimum_outline.context_chars,
			MAX_STAGE6_CONTEXT_CHARS * scale // _SCALE_DENOMINATOR,
		)
		outline = outline_by_cap.get(outline_cap)
		if outline is None:
			outline = daily_blog.bounded_artifact_context.BoundedArtifactContext.create(
				(daily_outline,), outline_cap, "daily_outline", model_packet_ids,
			)
			outline_by_cap[outline_cap] = outline
		story_cap = max(
			minimum_stories.context_chars,
			MAX_STAGE6_CONTEXT_CHARS * scale // _SCALE_DENOMINATOR,
		)
		stories = stories_by_cap.get(story_cap)
		if stories is None:
			stories = daily_blog.bounded_artifact_context.BoundedArtifactContext.create(
				repo_stories, story_cap, "story", model_packet_ids,
			)
			stories_by_cap[story_cap] = stories
		evidence_cap = max(
			minimum_evidence.context_chars,
			min(full_evidence.context_chars,
				MAX_STAGE6_CONTEXT_CHARS * scale // _SCALE_DENOMINATOR),
		)
		evidence = evidence_by_cap.get(evidence_cap)
		if evidence is None:
			evidence = daily_blog.projection.build_bounded_evidence_context(
				packets, projection_limits, evidence_cap,
			)
			evidence_by_cap[evidence_cap] = evidence
		value = Stage6PromptContext(outline, stories, evidence, scale, "", "")
		return dataclasses.replace(
			value,
			context_id=daily_blog.io_utils.hash_value(value.content_dict()),
			model_context_id=daily_blog.io_utils.hash_value(value.model_content_dict()),
		)

	def fits(scale: int) -> Stage6PromptContext | None:
		context = build(scale)
		try:
			context.render_context()
		except Stage6ContextCapacityError:
			return None
		return context

	minimum = fits(0)
	if minimum is None:
		raise Stage6ContextCapacityError(
			"Stage 6 cannot retain every survivor artifact and citable evidence."
		)
	# The complete-frame fit is monotonic; find the greatest shared source scale.
	low, high, best = 0, _SCALE_DENOMINATOR, minimum
	while low < high:
		middle = (low + high + 1) // 2
		candidate = fits(middle)
		if candidate is None:
			high = middle - 1
		else:
			low, best = middle, candidate
	best.validate_against(daily_outline, repo_stories, packets)
	return best


def _fits_complete_frame(context: Stage6PromptContext) -> bool:
	"""Return whether a complete Stage 6 prompt context fits its total envelope."""
	try:
		context.render_context()
	except Stage6ContextCapacityError:
		return False
	return True

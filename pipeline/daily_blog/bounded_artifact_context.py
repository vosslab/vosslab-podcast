"""Stage-neutral, survivor-scoped bounded artifact prompt projections."""

# Standard Library
import dataclasses
import datetime

# local repo modules
import daily_blog.artifacts
import daily_blog.io_utils


BOUNDED_ARTIFACT_CONTEXT_SCHEMA_VERSION = "vosslab.daily-blog.bounded-story-context.v1"
BOUNDED_ARTIFACT_CONTEXT_PROJECTION_VERSION = "repo-story-exact-excerpt.v1"
MIN_ARTIFACT_EXCERPT_CHARS = 160

ArtifactSource = (
	daily_blog.artifacts.RepoStory
	| daily_blog.artifacts.RepoOutline
	| daily_blog.artifacts.DailyOutline
)


#============================================
@dataclasses.dataclass(frozen=True)
class BoundedRepositoryArtifact:
	"""One model-visible, authority-preserving projection of a source artifact."""

	model_alias: str
	repository: str
	repositories: tuple[str, ...]
	artifact_id: str
	packet_ids: tuple[str, ...]
	model_packet_ids: tuple[str, ...]
	evidence_ids: tuple[str, ...]
	image_paths: tuple[str, ...]
	content_sha256: str
	full_source_chars: int
	content_excerpt: str

	#============================================
	def model_dict(self) -> dict[str, object]:
		"""Return the compact, canonical prompt representation."""
		return {
			"artifact_id": self.model_alias,
			"repository": self.repository,
			"repositories": list(self.repositories),
			"packet_ids": list(self.model_packet_ids),
			"evidence_ids": list(self.evidence_ids),
			"image_paths": list(self.image_paths),
			"full_source_chars": self.full_source_chars,
			"content_excerpt": self.content_excerpt,
		}

	#============================================
	def provenance_dict(self) -> dict[str, object]:
		"""Return model data plus the canonical source binding kept off-route."""
		value = self.model_dict()
		value["canonical_artifact_id"] = self.artifact_id
		value["canonical_packet_ids"] = list(self.packet_ids)
		value["content_sha256"] = self.content_sha256
		return value


#============================================
def _artifact_collection_key(artifact_kind: str) -> str:
	"""Return the canonical collection name for a bounded artifact kind."""
	return {
		"story": "stories",
		"outline": "outlines",
		"daily_outline": "daily_outlines",
	}[artifact_kind]


#============================================
@dataclasses.dataclass(frozen=True)
class BoundedArtifactContext:
	"""A deterministic prompt frame representing every survivor artifact."""

	report_date: str
	context_chars: int
	projection_version: str
	artifact_kind: str
	stories: tuple[BoundedRepositoryArtifact, ...]
	context_id: str
	model_context_id: str
	schema_version: str = BOUNDED_ARTIFACT_CONTEXT_SCHEMA_VERSION

	#============================================
	def content_dict(self) -> dict[str, object]:
		"""Return complete portable provenance whose digest is ``context_id``."""
		return {
			"schema_version": self.schema_version,
			"report_date": self.report_date,
			"context_chars": self.context_chars,
			"projection_version": self.projection_version,
			"artifact_kind": self.artifact_kind,
			_artifact_collection_key(self.artifact_kind): [
				item.provenance_dict() for item in self.stories
			],
		}

	#============================================
	def model_content_dict(self) -> dict[str, object]:
		"""Return the exact model-visible body whose digest keys route reuse."""
		return {
			"schema_version": self.schema_version,
			"report_date": self.report_date,
			"context_chars": self.context_chars,
			"projection_version": self.projection_version,
			"artifact_kind": self.artifact_kind,
			_artifact_collection_key(self.artifact_kind): [
				item.model_dict() for item in self.stories
			],
		}

	#============================================
	def to_dict(self) -> dict[str, object]:
		"""Serialize identities with the bounded model frame."""
		value = self.content_dict()
		value["context_id"] = self.context_id
		value["model_context_id"] = self.model_context_id
		return value

	#============================================
	def render_context(self) -> str:
		"""Render the sealed prompt body within its declared cap."""
		value = self.model_content_dict()
		value["model_context_id"] = self.model_context_id
		text = daily_blog.io_utils.canonical_json_bytes(value).decode("utf-8")
		if len(text) > self.context_chars:
				raise RuntimeError("Bounded artifact context exceeds its declared prompt cap.")
		return text

	#============================================
	@classmethod
	def create(
		cls,
		stories: tuple[ArtifactSource, ...],
		context_chars: int,
		artifact_kind: str,
		model_packet_ids: dict[str, str],
	) -> "BoundedArtifactContext":
		"""Project exact survivor sources with a fair deterministic excerpt budget."""
		artifact_types = {
			"story": daily_blog.artifacts.RepoStory,
			"outline": daily_blog.artifacts.RepoOutline,
			"daily_outline": daily_blog.artifacts.DailyOutline,
		}
		if (
			type(stories) is not tuple or not stories
			or artifact_kind not in artifact_types
			or any(type(key) is not str or type(item) is not str for key, item in model_packet_ids.items())
			or any(type(item) is not artifact_types[artifact_kind] for item in stories)
			or type(context_chars) is not int or context_chars <= 0
		):
			raise RuntimeError(
				"Bounded artifact context requires exact survivor sources and a positive cap."
			)
		ordered = tuple(sorted(stories, key=lambda item: (item.repositories[0], item.content_hash)))
		if len({item.repositories[0] for item in ordered}) != len(ordered):
			raise RuntimeError("Bounded artifact context requires one survivor per repository.")
		if len({item.report_date for item in ordered}) != 1:
			raise RuntimeError("Bounded artifact context survivor dates must align.")
		width = max(2, len(str(len(ordered))))
		alias_kind = artifact_kind.replace("_", "-")
		aliases = tuple(
			alias_kind + "-" + str(index).zfill(width)
			for index in range(1, len(ordered) + 1)
		)
		base = tuple(
			BoundedRepositoryArtifact(
				alias, story.repositories[0], story.repositories, story.artifact_id, story.packet_ids,
				tuple(sorted(model_packet_ids[item] for item in story.packet_ids)),
				story.evidence_ids, story.image_paths, story.content_hash, len(story.content), "",
			)
			for alias, story in zip(aliases, ordered, strict=True)
		)
		probe = cls(
			ordered[0].report_date, context_chars, BOUNDED_ARTIFACT_CONTEXT_PROJECTION_VERSION,
			artifact_kind, base, "0" * 64, "0" * 64,
		)
		overhead = len(probe.render_context())
		available = context_chars - overhead
		minimum = min(MIN_ARTIFACT_EXCERPT_CHARS, min(len(item.content) for item in ordered))
		if available < minimum * len(ordered):
			raise RuntimeError(
				"Bounded artifact context cannot preserve a meaningful excerpt for every survivor."
			)
		allocations = _allocate_excerpts(ordered, available, minimum)
		projected = tuple(
			dataclasses.replace(item, content_excerpt=story.content[:count])
			for item, story, count in zip(base, ordered, allocations, strict=True)
		)
		projected = _trim_to_rendered_cap(
			ordered[0].report_date, context_chars, artifact_kind, projected, minimum,
		)
		context = cls(
			ordered[0].report_date, context_chars, BOUNDED_ARTIFACT_CONTEXT_PROJECTION_VERSION,
			artifact_kind, projected, "", "",
		)
		context_id = daily_blog.io_utils.hash_value(context.content_dict())
		model_context_id = daily_blog.io_utils.hash_value(context.model_content_dict())
		value = dataclasses.replace(context, context_id=context_id, model_context_id=model_context_id)
		value.validate_against(stories, model_packet_ids)
		value.render_context()
		return value

	#============================================
	def validate_against(
		self,
		stories: tuple[ArtifactSource, ...],
		model_packet_ids: dict[str, str],
	) -> None:
		"""Prove this frame is an exact bounded projection of canonical sources."""
		artifact_types = {
			"story": daily_blog.artifacts.RepoStory,
			"outline": daily_blog.artifacts.RepoOutline,
			"daily_outline": daily_blog.artifacts.DailyOutline,
		}
		if (
			self.schema_version != BOUNDED_ARTIFACT_CONTEXT_SCHEMA_VERSION
			or self.projection_version != BOUNDED_ARTIFACT_CONTEXT_PROJECTION_VERSION
			or type(self.context_chars) is not int or self.context_chars <= 0
			or self.artifact_kind not in artifact_types
			or type(self.stories) is not tuple or not self.stories
			or len(self.stories) != len(stories)
			or type(stories) is not tuple
			or type(model_packet_ids) is not dict
			or any(
				type(key) is not str or type(value) is not str
				for key, value in model_packet_ids.items()
			)
			or any(type(item) is not artifact_types[self.artifact_kind] for item in stories)
		):
			raise RuntimeError("Bounded artifact context is invalid.")
		try:
			datetime.date.fromisoformat(self.report_date)
		except (TypeError, ValueError) as error:
			raise RuntimeError("Bounded artifact context report date is invalid.") from error
		ordered = tuple(sorted(stories, key=lambda item: (item.repositories[0], item.content_hash)))
		if tuple(item.repository for item in self.stories) != tuple(
			item.repositories[0] for item in ordered
		):
			raise RuntimeError("Bounded artifact context repositories do not match survivor sources.")
		width = max(2, len(str(len(ordered))))
		alias_kind = self.artifact_kind.replace("_", "-")
		for index, (projected, source) in enumerate(zip(self.stories, ordered, strict=True), start=1):
			try:
				expected_model_packet_ids = tuple(sorted(
					model_packet_ids[item] for item in source.packet_ids
				))
			except KeyError as error:
				raise RuntimeError(
					"Bounded artifact context lacks survivor packet identity authority."
				) from error
			if (
				projected.model_alias != alias_kind + "-" + str(index).zfill(width)
				or projected.repositories != source.repositories
				or projected.artifact_id != source.artifact_id
				or projected.packet_ids != source.packet_ids
				or projected.model_packet_ids != expected_model_packet_ids
				or projected.evidence_ids != source.evidence_ids
				or projected.image_paths != source.image_paths
				or projected.content_sha256 != source.content_hash
				or projected.full_source_chars != len(source.content)
				or not projected.content_excerpt
				or projected.content_excerpt != source.content[:len(projected.content_excerpt)]
			):
				raise RuntimeError("Bounded artifact context does not match survivor sources.")
		if self.context_id != daily_blog.io_utils.hash_value(self.content_dict()):
			raise RuntimeError("Bounded artifact context identity does not match its content.")
		if self.model_context_id != daily_blog.io_utils.hash_value(self.model_content_dict()):
			raise RuntimeError("Bounded artifact context model identity does not match its content.")


#============================================
def minimum_artifact_context(
	stories: tuple[ArtifactSource, ...],
	artifact_kind: str,
	model_packet_ids: dict[str, str],
	maximum_context_chars: int,
) -> BoundedArtifactContext:
	"""Derive the exact meaningful all-survivor artifact frame under ``maximum_context_chars``."""
	full = BoundedArtifactContext.create(
		stories, maximum_context_chars, artifact_kind, model_packet_ids,
	)
	minimum_stories = tuple(
		dataclasses.replace(
			item,
			content_excerpt=item.content_excerpt[:min(MIN_ARTIFACT_EXCERPT_CHARS, item.full_source_chars)],
		)
		for item in full.stories
	)
	cap = 1
	while True:
		probe = BoundedArtifactContext(
			full.report_date, cap, BOUNDED_ARTIFACT_CONTEXT_PROJECTION_VERSION,
			artifact_kind, minimum_stories, "", "",
		)
		probe = dataclasses.replace(
			probe,
			context_id=daily_blog.io_utils.hash_value(probe.content_dict()),
			model_context_id=daily_blog.io_utils.hash_value(probe.model_content_dict()),
		)
		model_value = probe.model_content_dict()
		model_value["model_context_id"] = probe.model_context_id
		next_cap = len(daily_blog.io_utils.canonical_json_bytes(model_value))
		if next_cap == cap:
			probe.validate_against(stories, model_packet_ids)
			probe.render_context()
			return probe
		cap = next_cap


#============================================
def _trim_to_rendered_cap(
	report_date: str,
	context_chars: int,
	artifact_kind: str,
	artifacts: tuple[BoundedRepositoryArtifact, ...],
	minimum: int,
) -> tuple[BoundedRepositoryArtifact, ...]:
	"""Trim exact suffixes fairly when JSON escaping consumes part of the cap."""
	probe = BoundedArtifactContext(
		report_date, context_chars, BOUNDED_ARTIFACT_CONTEXT_PROJECTION_VERSION,
		artifact_kind, artifacts, "", "0" * 64,
	)
	model_value = probe.model_content_dict()
	model_value["model_context_id"] = probe.model_context_id
	rendered_chars = len(daily_blog.io_utils.canonical_json_bytes(model_value))
	value = artifacts
	while rendered_chars > context_chars:
		maximums = tuple(len(item.content_excerpt) for item in value)
		if all(length == minimum for length in maximums):
			raise RuntimeError(
				"Bounded artifact context cannot preserve a meaningful excerpt for every survivor."
			)
		target = max(minimum * len(value), sum(maximums) - (rendered_chars - context_chars))
		allocations = _fair_allocations(maximums, target, minimum)
		value = tuple(
			dataclasses.replace(item, content_excerpt=item.content_excerpt[:count])
			for item, count in zip(value, allocations, strict=True)
		)
		probe = dataclasses.replace(probe, stories=value)
		model_value = probe.model_content_dict()
		model_value["model_context_id"] = probe.model_context_id
		rendered_chars = len(daily_blog.io_utils.canonical_json_bytes(model_value))
	return value


#============================================
def _allocate_excerpts(
	artifacts: tuple[ArtifactSource, ...], available: int, minimum: int,
) -> tuple[int, ...]:
	"""Distribute a bounded body fairly without dropping any survivor."""
	return _fair_allocations(
		tuple(len(artifact.content) for artifact in artifacts), available, minimum,
	)


#============================================
def _fair_allocations(
	maximums: tuple[int, ...], available: int, minimum: int,
) -> tuple[int, ...]:
	"""Water-fill exact character budgets in canonical source order."""
	allocation = [minimum] * len(maximums)
	remaining = available - sum(allocation)
	active = [index for index, maximum in enumerate(maximums) if maximum > minimum]
	while remaining > 0 and active:
		whole_rounds = remaining // len(active)
		if whole_rounds == 0:
			for index in active[:remaining]:
				allocation[index] += 1
			break
		step = min(whole_rounds, min(maximums[index] - allocation[index] for index in active))
		for index in active:
			allocation[index] += step
		remaining -= step * len(active)
		active = [index for index in active if allocation[index] < maximums[index]]
	return tuple(allocation)

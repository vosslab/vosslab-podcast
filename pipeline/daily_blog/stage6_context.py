"""Exact bounded evidence frames for Stage 6 and its recovery rungs."""

# Standard Library
import json

# local repo modules
import daily_blog.artifacts
import daily_blog.projection
import daily_blog.recovery
import daily_blog.schema


MAX_STAGE6_CONTEXT_CHARS = 60000


#============================================
def canonical_context(value: object) -> str:
	"""Return one canonical complete prompt frame without partial serialized data."""
	return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


#============================================
def stage6_frame(
	daily_outline: daily_blog.artifacts.DailyOutline,
	repo_stories: tuple[daily_blog.artifacts.RepoStory, ...], evidence: object,
) -> dict[str, object]:
	"""Return the complete non-evidence Stage 6 prompt frame in canonical order."""
	return {
		"daily_outline": daily_blog.schema.model_cache_artifact(daily_outline.to_dict()),
		"evidence": evidence,
		"repo_stories": [daily_blog.schema.model_cache_artifact(item.to_dict())
			for item in sorted(repo_stories, key=lambda item: (item.repositories, item.content_hash))],
	}


#============================================
def build_stage6_evidence_context(
	daily_outline: daily_blog.artifacts.DailyOutline,
	repo_stories: tuple[daily_blog.artifacts.RepoStory, ...],
	packets: tuple[daily_blog.schema.EvidencePacket, ...], projection_limits: dict[str, int],
) -> daily_blog.schema.BoundedEvidenceContext:
	"""Build one exact Stage 6 evidence context within the complete frame cap."""
	available = min(
		MAX_STAGE6_CONTEXT_CHARS - len(canonical_context(stage6_frame(daily_outline, repo_stories, {}))) + 2,
		projection_limits["context_chars"],
	)
	if available <= 0:
		raise RuntimeError("Stage 6 artifact frame leaves no bounded evidence capacity.")
	context = daily_blog.projection.build_bounded_evidence_context(packets, projection_limits, available)
	context.render_context(available)
	return context


#============================================
def recovery_frame(
	rung: daily_blog.recovery.RecoveryRung,
	source_artifacts: tuple[daily_blog.artifacts.DailyOutline | daily_blog.artifacts.RepoStory, ...],
	evidence: object,
) -> dict[str, object]:
	"""Return the exact non-evidence frame for one lower editorial path."""
	if rung is daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION:
		return {"daily_outline": daily_blog.schema.model_cache_artifact(source_artifacts[0].to_dict()),
			"evidence": evidence}
	return {"evidence": evidence, "repo_stories": [
		daily_blog.schema.model_cache_artifact(item.to_dict()) for item in source_artifacts]}

"""Behavior tests for survivor-scoped bounded evidence prompt contexts."""

# Standard Library
import dataclasses
import json
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.artifacts
import daily_blog.bounded_artifact_context
import daily_blog.daily_outline_workflow
import daily_blog.io_utils
import daily_blog.projection
import daily_blog.recovery
import daily_blog.repository_contracts
import daily_blog.schema
import daily_blog.stage6


LIMITS = {
	"context_chars": 8000,
	"excerpt_chars": 360,
	"commit_subject_chars": 120,
}


#============================================
def _packet(
	repository: str,
	marker: str,
	cache_path: str,
	content: str | None = None,
) -> daily_blog.schema.EvidencePacket:
	"""Return one complete packet with citable evidence and active repository activity."""
	sha = marker * 40
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog",
		repository,
		sha,
		"docs/CHANGELOG.md",
		"b" * 40,
		content or f"## {marker} " + marker * 1500,
		"git show",
	)
	commit = daily_blog.schema.CommitActivity(
		sha=sha,
		parents=("c" * 40,),
		author_name="Author",
		author_email="author@example.com",
		author_timestamp="2026-08-28T12:00:00-05:00",
		committer_timestamp="2026-08-28T12:00:00-05:00",
		message=f"Document {marker}",
	)
	activity = daily_blog.schema.RepositoryActivity(
		repository=repository,
		repository_url=f"https://github.com/{repository}",
		cache_path=cache_path,
		default_revision=sha,
		commits=(commit,),
		revision_ranges=(daily_blog.schema.RevisionRange("c" * 40, sha),),
		snapshot_commits=(sha,),
		is_fork=False,
		lifecycle_events=(daily_blog.repository_contracts.RepositoryLifecycleEvent(
			"repository_created", "2020-01-01T00:00:00Z", False, "github_owner_roster",
		),),
	)
	return daily_blog.schema.EvidencePacket.create(
		"2026-08-28", "America/Chicago", True, {}, [], [activity], [item],
	)


#============================================
def _stage5_input(
	tmp_path: pathlib.Path,
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
	context: daily_blog.schema.BoundedEvidenceContext,
) -> daily_blog.daily_outline_workflow.DailyOutlineInput:
	"""Build complete per-repository Stage 5 inputs from survivor packets."""
	stories = tuple(sorted((
		daily_blog.artifacts.RepoStory.create(
			packet.report_date, (packet,), packet.items[0].repository,
			"Story " + packet.items[0].repository + " <!-- evidence: "
			+ packet.items[0].evidence_id + " -->", (packet.items[0].evidence_id,),
		)
		for packet in packets
	), key=lambda item: item.artifact_id))
	outlines = tuple(
		daily_blog.artifacts.RepoOutline.create(
			packet.report_date, (packet,), packet.items[0].repository,
			"Outline " + packet.items[0].repository + " <!-- evidence: "
			+ packet.items[0].evidence_id + " -->", (packet.items[0].evidence_id,),
		)
		for packet in packets
	)
	return daily_blog.daily_outline_workflow.DailyOutlineInput(
		stories, outlines, packets, context, str(tmp_path),
	)


#============================================
def _ranking(stories: tuple[daily_blog.artifacts.RepoStory, ...]) -> daily_blog.daily_outline_workflow.PromotedRanking:
	"""Return the minimum exact Stage-5 ranking provenance required by Stage 6."""
	content_hash = "a" * 64
	payload = {
		"candidate_id": "ranking-1",
		"accepted_review_ids": ["review-1"],
		"ranking_content_sha256": content_hash,
	}
	return daily_blog.daily_outline_workflow.PromotedRanking(
		"ranking-promotion-" + daily_blog.io_utils.sha256_text(
			json.dumps(payload, sort_keys=True, separators=(",", ":")),
		)[:24],
		"ranking-1", content_hash, tuple(sorted(item.content_hash for item in stories)),
		tuple(sorted((item.content_hash, 100) for item in stories)),
		"Grounded ranking rationale.", ("review-1",),
	)


#============================================
def test_bounded_context_fits_complete_exact_frames_for_every_survivor() -> None:
	"""Aggregate model context remains capped without dropping survivor coverage."""
	packets = (
		_packet("vosslab/alpha", "a", "/one"),
		_packet("vosslab/beta", "d", "/two"),
	)
	context = daily_blog.projection.build_bounded_evidence_context(packets, LIMITS, 5000)

	assert len(context.render_context(5000)) <= 5000
	assert {card.repository for card in context.repositories} == {"vosslab/alpha", "vosslab/beta"}


#============================================
def test_bounded_context_round_trip_keeps_exact_source_provenance() -> None:
	"""Serialized contexts preserve exact excerpt offsets and survivor identities."""
	packets = (
		_packet("vosslab/alpha", "a", "/one"),
		_packet("vosslab/beta", "d", "/two"),
	)
	context = daily_blog.projection.build_bounded_evidence_context(packets, LIMITS, 5000)
	loaded = daily_blog.schema.BoundedEvidenceContext.from_dict(context.to_dict())

	daily_blog.projection.validate_bounded_evidence_context(packets, loaded)
	assert loaded.context_id == context.context_id


#============================================
def test_model_identity_excludes_host_local_packet_provenance() -> None:
	"""Host-local mirror paths affect audit provenance, not the portable model frame."""
	original = _packet("vosslab/alpha", "a", "/one")
	relocated = dataclasses.replace(
		original,
		mirrors=original.mirrors,
		activity=(dataclasses.replace(original.activity[0], cache_path="/other"),),
		packet_id="",
	)
	relocated = daily_blog.schema.EvidencePacket.create(
		relocated.report_date,
		relocated.timezone,
		relocated.complete,
		relocated.collection_limits.to_dict(),
		[],
		list(relocated.activity),
		list(relocated.items),
	)
	first = daily_blog.projection.build_bounded_evidence_context((original,), LIMITS, 5000)
	second = daily_blog.projection.build_bounded_evidence_context((relocated,), LIMITS, 5000)

	assert first.context_id != second.context_id
	assert first.model_context_id == second.model_context_id


#============================================
def test_effective_cap_is_bound_to_the_rendered_context_identity() -> None:
	"""The selected frame cannot be silently reused under another consumer budget."""
	packet = _packet("vosslab/alpha", "a", "/one")
	first = daily_blog.projection.build_bounded_evidence_context((packet,), LIMITS, 5000)
	second = daily_blog.projection.build_bounded_evidence_context((packet,), LIMITS, 5100)

	with pytest.raises(RuntimeError, match="selection budget"):
		first.render_context(5100)
	assert first.model_context_id != second.model_context_id


#============================================
def test_authoritative_validation_rejects_tampered_card_or_exact_excerpt() -> None:
	"""Survivor-source validation detects mutations even when a typed value is forged."""
	packet = _packet("vosslab/alpha", "a", "/one")
	context = daily_blog.projection.build_bounded_evidence_context((packet,), LIMITS, 5000)
	tampered = dataclasses.replace(
		context,
		excerpts=(dataclasses.replace(context.excerpts[0], commit="wrong"),),
	)

	with pytest.raises(RuntimeError, match="exact source slice"):
		daily_blog.projection.validate_bounded_evidence_context((packet,), tampered)


#============================================
def test_authoritative_validation_rejects_tampered_repository_card() -> None:
	"""Cards remain an exact bounded projection of repository activity."""
	packet = _packet("vosslab/alpha", "a", "/one")
	context = daily_blog.projection.build_bounded_evidence_context((packet,), LIMITS, 5000)
	tampered = dataclasses.replace(
		context,
		repositories=(dataclasses.replace(context.repositories[0], commit_count=2),),
	)

	with pytest.raises(RuntimeError, match="card does not match"):
		daily_blog.projection.validate_bounded_evidence_context((packet,), tampered)


#============================================
def test_stage5_uses_a_bounded_exact_context_for_only_surviving_repositories(
		tmp_path: pathlib.Path,
) -> None:
	"""Stage 5 prompt context contains survivors and excludes failed repositories."""
	survivors = (
		_packet("vosslab/alpha", "a", "/one", "alpha-source"),
		_packet("vosslab/beta", "b", "/two", "beta-source"),
	)
	non_survivor = _packet(
		"vosslab/failed", "c", "/failed", "failed-source",
	)
	limits = {**LIMITS, "context_chars": 8000, "excerpt_chars": 1000}
	context = daily_blog.projection.build_bounded_evidence_context(survivors, limits, 8000)
	value = _stage5_input(tmp_path, survivors, context)
	rendered = value.render_evidence()

	assert (
		{card.repository for card in context.repositories} == {"vosslab/alpha", "vosslab/beta"}
		and "vosslab/failed" not in rendered
		and {excerpt.repository for excerpt in context.excerpts} == {"vosslab/alpha", "vosslab/beta"}
		and non_survivor.packet_id not in context.packet_ids
	)


#============================================
def test_stage6_and_recovery_preserve_every_survivor_in_one_bounded_context(
		tmp_path: pathlib.Path,
) -> None:
	"""Primary and recovery routes use bounded views from one survivor authority."""
	packets = (_packet("vosslab/alpha", "a", "/one", "alpha-source"),)
	limits = {**LIMITS, "context_chars": 6000, "excerpt_chars": 1000}
	stage5_context = daily_blog.projection.build_bounded_evidence_context(
		packets, limits, limits["context_chars"],
	)
	stage5 = _stage5_input(tmp_path, packets, stage5_context)
	evidence_ids = tuple(sorted(packet.items[0].evidence_id for packet in packets))
	daily_outline = daily_blog.artifacts.DailyOutline.create(
		packets[0].report_date, packets, stage5.repositories,
		"Outline " + "o" * 31000 + " <!-- evidence: " + ", ".join(evidence_ids) + " -->",
		evidence_ids,
	)
	stories = tuple(sorted((
		daily_blog.artifacts.RepoStory.create(
			packet.report_date, (packet,), packet.items[0].repository,
			"Story " + "s" * 31000 + " <!-- evidence: "
			+ packet.items[0].evidence_id + " -->",
			(packet.items[0].evidence_id,),
		)
		for packet in packets
	), key=lambda item: item.artifact_id))
	sources = daily_blog.stage6.Stage6RecoverySources(
		stories, stage5.repo_outlines, packets, _ranking(stories),
		min(stories, key=lambda item: item.artifact_id).artifact_id,
	)
	surface = daily_blog.stage6.build_stage6_publication_surface(
		daily_outline, stories, packets, limits,
	)
	context = surface.stage6_prompt_context
	value = daily_blog.stage6.Stage6Input(
		str(tmp_path), str(tmp_path / daily_outline.report_date / "post.md"), sources, surface,
	)
	recovery = daily_blog.stage6.CompletePostRecoveryInput(
		value, daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION,
	)
	story_recovery = daily_blog.stage6.CompletePostRecoveryInput(
		value, daily_blog.recovery.RecoveryRung.REPOSITORY_STORY_MERGE,
	)
	evidence_context = context.evidence_context
	primary = value.render_context()
	daily_recovery = recovery.render_context()
	story_merge = story_recovery.render_context()
	assert (
		{item.repository for item in context.repo_story_context.stories} == set(stage5.repositories)
		and context.daily_outline_context.stories[0].repositories == stage5.repositories
		and {excerpt.repository for excerpt in evidence_context.excerpts} == set(stage5.repositories)
		and (
			context.daily_outline_context.stories[0].content_excerpt != daily_outline.content
			or context.repo_story_context.stories[0].content_excerpt != stories[0].content
		)
	)
	outline_id = context.daily_outline_context.model_context_id
	story_id = context.repo_story_context.model_context_id
	evidence_id = context.evidence_context.model_context_id
	recovery_outline_id = context.recovery_daily_outline_context.model_context_id
	recovery_story_id = context.recovery_repo_story_context.model_context_id
	recovery_evidence_id = context.recovery_evidence_context.model_context_id
	assert (
		outline_id in primary and recovery_outline_id in daily_recovery
		and story_id in primary and recovery_story_id in story_merge
		and evidence_id in primary
		and recovery_evidence_id in daily_recovery and recovery_evidence_id in story_merge
	)


#============================================
def test_bounded_artifact_context_rejects_a_forged_semantic_packet_identity() -> None:
	"""A rehashed prompt projection still binds the survivor packet's semantic identity."""
	packet = _packet("vosslab/alpha", "a", "/one", "alpha-source")
	story = daily_blog.artifacts.RepoStory.create(
		packet.report_date, (packet,), packet.items[0].repository,
		"Story <!-- evidence: " + packet.items[0].evidence_id + " -->",
		(packet.items[0].evidence_id,),
	)

	model_packet_ids = {
		packet.packet_id: daily_blog.schema.model_cache_packet_identity(packet),
	}
	context = daily_blog.bounded_artifact_context.BoundedArtifactContext.create(
		(story,), 4000, "story", model_packet_ids,
	)
	tampered_item = dataclasses.replace(
		context.stories[0], model_packet_ids=("f" * 64,),
	)
	tampered = dataclasses.replace(
		context, stories=(tampered_item,), context_id="", model_context_id="",
	)
	tampered = dataclasses.replace(
		tampered,
		context_id=daily_blog.io_utils.hash_value(tampered.content_dict()),
		model_context_id=daily_blog.io_utils.hash_value(tampered.model_content_dict()),
	)
	with pytest.raises(RuntimeError, match="does not match survivor sources"):
		tampered.validate_against((story,), model_packet_ids)

"""Behavior tests for survivor-scoped bounded evidence prompt contexts."""

# Standard Library
import dataclasses
import json
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.artifacts
import daily_blog.daily_outline_workflow
import daily_blog.io_utils
import daily_blog.projection
import daily_blog.recovery
import daily_blog.repository_contracts
import daily_blog.schema
import daily_blog.stage6
import daily_blog.stage6_context


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
def _raw_model_packets(packets: tuple[daily_blog.schema.EvidencePacket, ...]) -> str:
	"""Return the pre-boundary model packet body that caused the live failure."""
	return json.dumps(
		[daily_blog.schema.model_cache_packet_content(packet) for packet in packets],
		sort_keys=True, separators=(",", ":"), ensure_ascii=True,
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
	"""Large survivor packets remain authoritative while Stage 5 sees exact bounded slices."""
	survivors = (
		_packet("vosslab/alpha", "a", "/one", "alpha-source " + "a" * 36000),
		_packet("vosslab/beta", "b", "/two", "beta-source " + "b" * 36000),
	)
	non_survivor = _packet("vosslab/failed", "c", "/three", "failed-source " + "c" * 36000)
	limits = {**LIMITS, "context_chars": 60000, "excerpt_chars": 1000}
	context = daily_blog.projection.build_bounded_evidence_context(survivors, limits, 60000)
	value = _stage5_input(tmp_path, survivors, context)
	rendered = value.render_evidence()

	assert len(_raw_model_packets(survivors)) > 60000 and len(rendered) <= 60000
	assert (
		{card.repository for card in context.repositories} == {"vosslab/alpha", "vosslab/beta"}
		and "vosslab/failed" not in rendered
		and {excerpt.repository for excerpt in context.excerpts} == {"vosslab/alpha", "vosslab/beta"}
		and non_survivor.packet_id not in context.packet_ids
	)


#============================================
def test_stage6_and_recovery_bound_large_evidence_after_editorial_frame_overhead(
		tmp_path: pathlib.Path,
) -> None:
	"""Stage 6 and recovery reserve evidence capacity after their real editorial frames."""
	packets = tuple(sorted((
		_packet("vosslab/alpha", "a", "/one", "alpha-source " + "a" * 36000),
		_packet("vosslab/beta", "b", "/two", "beta-source " + "b" * 36000),
		_packet("vosslab/gamma", "c", "/three", "gamma-source " + "c" * 36000),
		_packet("vosslab/delta", "d", "/four", "delta-source " + "d" * 36000),
	), key=lambda item: item.packet_id))
	limits = {**LIMITS, "context_chars": 60000, "excerpt_chars": 6000}
	stage5_context = daily_blog.projection.build_bounded_evidence_context(
		packets, limits, 60000,
	)
	stage5 = _stage5_input(tmp_path, packets, stage5_context)
	evidence_ids = tuple(sorted(packet.items[0].evidence_id for packet in packets))
	daily_outline = daily_blog.artifacts.DailyOutline.create(
		packets[0].report_date, packets, stage5.repositories,
		"Outline " + "o" * 8000 + " <!-- evidence: " + ", ".join(evidence_ids) + " -->",
		evidence_ids,
	)
	stories = tuple(sorted((
		daily_blog.artifacts.RepoStory.create(
			packet.report_date, (packet,), packet.items[0].repository,
			"Story " + "s" * 7000 + " <!-- evidence: " + packet.items[0].evidence_id + " -->",
			(packet.items[0].evidence_id,),
		)
		for packet in packets
	), key=lambda item: item.artifact_id))
	sources = daily_blog.stage6.Stage6RecoverySources(
		stories, stage5.repo_outlines, packets, _ranking(stories),
		min(stories, key=lambda item: item.artifact_id).artifact_id,
	)
	context = daily_blog.stage6.build_stage6_evidence_context(
		daily_outline, stories, packets, limits,
	)
	rebuilt = daily_blog.stage6.build_stage6_evidence_context(
		daily_outline, stories, packets, limits,
	)
	value = daily_blog.stage6.Stage6Input(
		daily_outline, stories, packets, str(tmp_path),
		str(tmp_path / daily_outline.report_date / "post.md"), sources, context,
	)
	recovery = daily_blog.stage6.CompletePostRecoveryInput(
		value, daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION,
	)
	raw_stage6 = daily_blog.stage6_context.canonical_context(
		daily_blog.stage6_context.stage6_frame(
			daily_outline, stories,
			json.loads(_raw_model_packets(packets)),
		),
	)
	forged = daily_blog.schema.BoundedEvidenceContext.create(
		context.report_date, context.timezone, context.context_chars,
		context.effective_excerpt_chars - 1, dict(context.projection_limits),
		list(context.packet_ids), list(context.model_packet_ids),
		list(context.repositories), list(context.excerpts),
	)

	assert len(raw_stage6) > 60000 and len(value.render_context()) <= 60000 and len(recovery.render_context()) <= 60000
	assert (
		{excerpt.repository for excerpt in context.excerpts} == set(stage5.repositories)
		and context.effective_excerpt_chars < context.projection_limits["excerpt_chars"]
		and context.projection_limits["excerpt_chars"] == limits["excerpt_chars"]
		and daily_blog.schema.BoundedEvidenceContext.from_dict(context.to_dict()) == context
		and rebuilt.context_id == context.context_id
	)
	with pytest.raises(RuntimeError, match="not maximal"):
		daily_blog.projection.validate_bounded_evidence_context(packets, forged)

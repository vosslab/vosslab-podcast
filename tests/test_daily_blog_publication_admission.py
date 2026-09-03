"""Permanent offline coverage for survivor-scoped publication admission."""

# Standard Library
import json
from pathlib import Path

# PIP3 modules
import pytest

# local repo modules
import daily_blog.activation
import daily_blog.artifacts
import daily_blog.activity
import daily_blog.daily_outline_workflow
import daily_blog.editorial
import daily_blog.io_utils
import daily_blog.publication_contract
import daily_blog.publication_finalization
import daily_blog.publication_admission
import daily_blog.projection
import daily_blog.prompt_registry.editorial_contracts
import daily_blog.recovery
import daily_blog.repository_contracts
import daily_blog.schema
import daily_blog.stage6


_LIMITS = {"commit_subject_chars": 120, "context_chars": 12000, "excerpt_chars": 1000}


#============================================
def _packet(repository: str, asset_name: str) -> daily_blog.schema.EvidencePacket:
	"""Build one independently collected survivor packet with a screenshot asset."""
	activity = daily_blog.schema.RepositoryActivity(
		repository, "https://github.com/" + repository, "/fixture/" + asset_name,
		"a" * 40,
		(daily_blog.schema.CommitActivity(
			"a" * 40, (), "Fixture", "fixture@example.com",
			"2026-08-29T12:00:00-05:00", "2026-08-29T12:00:00-05:00",
			"Grounded fixture work",
		),),
		(daily_blog.schema.RevisionRange("", "a" * 40),), ("a" * 40,), False,
		(daily_blog.repository_contracts.RepositoryLifecycleEvent(
			"repository_created", "2020-01-01T00:00:00Z", False, "github_owner_roster",
		),),
	)
	change = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", repository, "a" * 40, "CHANGELOG.md", "b" * 40,
		"Grounded change.", "fixture",
	)
	screenshot = daily_blog.schema.EvidenceItem.create(
		"screenshot", repository, "a" * 40, "image.png", "c" * 40,
		"Screenshot.", "fixture", asset_path="assets/" + asset_name,
		publish_path="../../assets/publications/2026-08-29/" + asset_name,
	)
	return daily_blog.schema.EvidencePacket.create(
		"2026-08-29", "America/Chicago", True, {}, [], [activity], [change, screenshot],
	)


#============================================
def _identity() -> daily_blog.publication_contract.PublicationIdentity:
	"""Build the active deterministic producer identity without route execution."""
	contract = daily_blog.prompt_registry.editorial_contracts.active_contract()
	policy = daily_blog.prompt_registry.editorial_contracts.policy_for_contract(contract)
	snapshot = daily_blog.editorial.resolve_snapshot(contract, None, None)
	activation = daily_blog.activation.load_maker_activation().receipt
	return daily_blog.publication_contract.publication_identity(
		str(Path(__file__).resolve().parents[1]), None,
		prompt_paths=daily_blog.prompt_registry.editorial_contracts.prompt_paths(contract),
		contracts={
			"evidence_schema": daily_blog.schema.EVIDENCE_SCHEMA_VERSION,
			"editorial_projection_schema": daily_blog.schema.PROJECTION_SCHEMA_VERSION,
			"prompt_version": contract.prompt_version, "rubric_version": contract.rubric_version,
			"candidate_validation": {"name": policy.name, "version": policy.version, "sha256": policy.sha256()},
		}, editorial_prompt_contract=daily_blog.editorial.prompt_contract_identity(snapshot=snapshot),
		activation_receipt={
			"activation_id": activation["activation_id"],
			"editorial_prompt_contract_sha256": activation["editorial_prompt_contract_sha256"],
		},
	)


#============================================
def _surface(
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
) -> daily_blog.publication_admission.PublicationSurface:
	"""Build one model-visible surface with grounded outline and story sources."""
	canonical = tuple(sorted(packets, key=lambda item: item.packet_id))
	repositories = tuple(sorted(packet.items[0].repository for packet in canonical))
	stories = []
	all_ids = []
	all_images = []
	for packet in canonical:
		evidence_ids = tuple(sorted(item.evidence_id for item in packet.items))
		images = tuple(sorted(item.publish_path for item in packet.items if item.publish_path))
		content = "Story " + " ".join(
			"<!-- evidence: " + evidence_id + " -->" for evidence_id in evidence_ids
		)
		content += "".join("\n![fixture](" + path + ")" for path in images)
		stories.append(daily_blog.artifacts.RepoStory.create(
			packet.report_date, (packet,), packet.items[0].repository,
			content, evidence_ids, images,
		))
		all_ids.extend(evidence_ids)
		all_images.extend(images)
	ids = tuple(sorted(all_ids))
	images = tuple(sorted(all_images))
	outline_content = "Outline " + " ".join(
		"<!-- evidence: " + evidence_id + " -->" for evidence_id in ids
	)
	outline_content += "".join("\n![fixture](" + path + ")" for path in images)
	outline = daily_blog.artifacts.DailyOutline.create(
		canonical[0].report_date, canonical, repositories, outline_content, ids, images,
	)
	return daily_blog.publication_admission.build_surface(
		canonical, repositories, _LIMITS, (outline,) + tuple(stories),
	)


#============================================
def _stage6_sources(
	story: daily_blog.artifacts.RepoStory,
	packet: daily_blog.schema.EvidencePacket,
) -> daily_blog.stage6.Stage6RecoverySources:
	"""Build the reviewed single-repository material required by Stage 6."""
	repository_outline = daily_blog.artifacts.RepoOutline.create(
		packet.report_date, (packet,), story.repositories[0], story.content,
		story.evidence_ids, story.image_paths,
	)
	ranking_hash = "a" * 64
	promoted = daily_blog.daily_outline_workflow.PromotedRanking(
		"ranking-1", ranking_hash, (story.content_hash,), ((story.content_hash, 100),),
		"Grounded ranking rationale.", ("review-1",),
	)
	return daily_blog.stage6.Stage6RecoverySources(
		(story,), (repository_outline,), (packet,), promoted, story.artifact_id,
	)


def test_surface_uses_exact_survivors_and_only_their_bundle_asset_paths(tmp_path: Path) -> None:
	"""Stage 6 context and bundle sealing retain one survivor-scoped authority."""
	base = _packet("vosslab/first", "selected.png")
	unselected = daily_blog.schema.EvidenceItem.create(
		"screenshot", "vosslab/first", "a" * 40, "unselected.png", "d" * 40,
		"Unselected screenshot.", "fixture", asset_path="assets/unselected.png",
		publish_path="../../assets/publications/2026-08-29/unselected.png",
	)
	packet = daily_blog.schema.EvidencePacket.create(
		base.report_date, base.timezone, True, {}, [], list(base.activity),
		list(base.items) + [unselected],
	)
	selected = tuple(item for item in packet.items if item is not unselected)
	selected_ids = tuple(sorted(item.evidence_id for item in selected))
	selected_screenshot = next(item for item in selected if item.kind == "screenshot")
	selected_path = selected_screenshot.publish_path
	story_content = (
		"Story " + " ".join("<!-- evidence: " + item + " -->" for item in selected_ids)
	)
	story = daily_blog.artifacts.RepoStory.create(
		packet.report_date, (packet,), "vosslab/first", story_content, selected_ids,
		(),
	)
	outline = daily_blog.artifacts.DailyOutline.create(
		packet.report_date, (packet,), ("vosslab/first",), story_content, selected_ids,
		(),
	)
	limits = {**_LIMITS, "context_chars": 1800}
	surface = daily_blog.publication_admission.build_surface(
		(packet,), ("vosslab/first",), limits, (outline, story),
	)
	stage6_input = daily_blog.stage6.Stage6Input(
		str(tmp_path), str(tmp_path / packet.report_date / "post.md"),
		_stage6_sources(story, packet), surface,
	)
	rendered_context = stage6_input.render_context()
	recovery_context = surface.stage6_prompt_context.render_recovery_context(
		daily_blog.recovery.RecoveryRung.REPOSITORY_STORY_MERGE,
	)
	assets = daily_blog.publication_admission.survivor_assets(surface, {
		"assets/selected.png": b"selected", "assets/unselected.png": b"unselected",
	})

	post = daily_blog.artifacts.CompletePost.create(
		packet.report_date, surface.source_packets, surface.narrative_repositories,
		"# Visible survivor evidence\n\nI used the approved screenshot. <!-- evidence: "
		+ ", ".join(surface.allowed_evidence_ids) + " -->\n\n"
		+ "\n".join("![fixture](" + path + ")" for path in surface.allowed_image_paths),
		surface.allowed_evidence_ids, packet.report_date, str(tmp_path / "post.md"),
		surface.allowed_image_paths,
	)
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [
		daily_blog.repository_contracts.RepositoryRecord.from_dict({
			"repository": "vosslab/first", "repository_url": "https://github.com/vosslab/first",
			"clone_url": "https://github.com/vosslab/first.git",
			"created_at": "2020-01-01T00:00:00Z", "is_fork": False,
		}),
	])
	_bundle_path, _bundle, transfer = daily_blog.publication_contract.BundleWriter(
		str(tmp_path), "vosslab", _identity(),
	).write("run-1", surface, assets, roster, post, daily_blog.activity.build_daily_active_roster(
		"vosslab", packet.report_date, roster.roster_id, [{
			"repository": "vosslab/first", "sha": "a" * 40,
			"author_timestamp": packet.report_date + "T12:00:00Z",
			"author_name": "Fixture", "message": "Fixture work",
		}],
	))
	transfer_entries = {item.path: item.contents for item in transfer.entries}
	portable_surface = json.loads(transfer_entries["publication_surface.json"])

	assert (
		selected_screenshot.evidence_id in rendered_context and selected_path in rendered_context
		and unselected.evidence_id not in rendered_context
		and unselected.publish_path not in rendered_context
		and "assets/selected.png" not in rendered_context
		and selected_path in recovery_context
		and "assets/selected.png" not in recovery_context
	)
	assert (
		{path for path in transfer_entries if path.startswith("assets/")}
		== {"assets/selected.png"}
		and portable_surface["allowed_evidence_ids"] == list(surface.allowed_evidence_ids)
		and portable_surface["allowed_images"][0]["publish_path"] == selected_path
	)


#============================================
def test_aggregate_publication_packet_does_not_replace_survivor_artifact_provenance(
	tmp_path: Path,
) -> None:
	"""A two-repository post keeps per-repository source packet identities through admission."""
	first, second = _packet("vosslab/first", "z.png"), _packet("vosslab/second", "a.png")
	sources = tuple(sorted((first, second), key=lambda item: item.packet_id))
	surface = _surface(sources)
	first_id, second_id = first.items[0].evidence_id, second.items[0].evidence_id
	opening = (
		"I connected [vosslab/first](https://github.com/vosslab/first) and "
		"[vosslab/second](https://github.com/vosslab/second) to the same useful boundary. "
	) * 4
	detail = (
		"I followed the implementation through its useful constraint, the behavior it changed, "
		"and the next question worth testing with the grounded evidence in view. "
	) * 18
	content = (
		"# Survivor provenance\n\n" + opening.strip() + "<!-- evidence: " + first_id + " -->\n\n"
		+ "<!-- more -->\n\n## The useful boundary\n\n" + detail.strip()
		+ "<!-- evidence: " + second_id + " -->\n\n## Project coverage\n\n"
		+ "I recorded vosslab/first and vosslab/second. <!-- evidence: " + first_id + " -->\n"
	)
	post = daily_blog.artifacts.CompletePost.create(
		first.report_date, sources, ("vosslab/first", "vosslab/second"), content,
		tuple(sorted((first_id, second_id))), first.report_date, str(tmp_path / "post.md"),
	)

	assert daily_blog.publication_admission.complete_post_eligibility(
		post, surface, str(tmp_path),
	).eligible
	assert post.packet_ids != (surface.packet.packet_id,)


#============================================
def test_surface_rejects_a_claimed_scope_missing_its_survivor_packet() -> None:
	"""Publication scope is authoritative packet membership, never a caller assertion."""
	first = _packet("vosslab/first", "first.png")
	surface = _surface((first,))

	with pytest.raises(RuntimeError, match="do not exactly cover"):
		daily_blog.publication_admission.build_surface(
			surface.source_packets,
			("vosslab/first", "vosslab/second"),
			dict(surface.evidence_context.projection_limits),
			surface.source_artifacts,
		)


#============================================
def test_direct_surface_rejects_duplicate_source_packet_identity() -> None:
	"""A direct constructor cannot inflate provenance by repeating one survivor packet."""
	first = _packet("vosslab/first", "first.png")
	surface = _surface((first,))

	with pytest.raises(RuntimeError, match="exact survivor evidence union"):
		daily_blog.publication_admission.PublicationSurface(
			(first, first), surface.evidence_context, surface.stage6_prompt_context,
			("vosslab/first",),
			surface.source_artifacts,
		)


#============================================
def test_direct_surface_rejects_a_context_from_different_survivors() -> None:
	"""A valid bounded context cannot be paired with a different packet union."""
	first = _packet("vosslab/first", "first.png")
	second = _packet("vosslab/second", "second.png")
	surface = _surface((first,))

	with pytest.raises(RuntimeError):
		daily_blog.publication_admission.PublicationSurface(
			(second,), surface.evidence_context, surface.stage6_prompt_context,
			("vosslab/second",), surface.source_artifacts,
		)


#============================================
def test_direct_surface_rejects_source_artifacts_outside_survivor_scope() -> None:
	"""Grounded artifacts from another repository cannot expand admission scope."""
	first = _packet("vosslab/first", "first.png")
	second = _packet("vosslab/second", "second.png")
	first_surface = _surface((first,))
	second_surface = _surface((second,))

	with pytest.raises(RuntimeError):
		daily_blog.publication_admission.PublicationSurface(
			first_surface.source_packets, first_surface.evidence_context,
			first_surface.stage6_prompt_context, first_surface.coverage_repositories,
			second_surface.source_artifacts,
		)


#============================================
def test_surface_canonicalizes_survivor_packet_order_before_aggregation() -> None:
	"""Equivalent Stage-6 survivor tuples retain one stable aggregate identity."""
	first, second = _packet("vosslab/first", "first.png"), _packet("vosslab/second", "second.png")
	forward = _surface((first, second))
	reversed_surface = _surface((second, first))

	assert reversed_surface == forward


#============================================
def test_survivor_assets_rejects_a_missing_required_screenshot_byte() -> None:
	"""A sealed survivor packet cannot name an asset absent from the exact byte map."""
	first = _packet("vosslab/first", "first.png")
	surface = _surface((first,))

	with pytest.raises(RuntimeError, match="missing a survivor screenshot"):
		daily_blog.publication_admission.survivor_assets(surface, {})
	with pytest.raises(RuntimeError, match="missing a survivor screenshot"):
		daily_blog.publication_admission.survivor_assets(surface, {"assets/first.png": "not-bytes"})


#============================================
def test_surface_rejects_ambiguous_assets_and_decorative_source_packet_ids() -> None:
	"""Portable authority keeps one screenshot mapping and reconstructible provenance."""
	first = _packet("vosslab/first", "first.png")
	duplicate = daily_blog.schema.EvidenceItem.create(
		"screenshot", "vosslab/first", "a" * 40, "duplicate.png", "d" * 40,
		"Duplicate screenshot.", "fixture", asset_path="assets/first.png",
		publish_path="../../assets/publications/2026-08-29/duplicate.png",
	)
	ambiguous = daily_blog.schema.EvidencePacket.create(
		first.report_date, first.timezone, True, {}, [], list(first.activity),
		list(first.items) + [duplicate],
	)
	with pytest.raises(RuntimeError, match="screenshot paths must be one-to-one"):
		_surface((ambiguous,))

	surface = _surface((first,))
	portable = daily_blog.publication_surface_contract.publication_surface_value(surface)
	portable["source_packet_ids"] = ["0" * 64]
	portable["surface_id"] = daily_blog.publication_surface_contract.publication_surface_id(portable)
	with pytest.raises(RuntimeError, match="source packets do not match"):
		daily_blog.publication_surface_contract.validate_publication_surface_value(
			portable, surface.packet, surface.projection,
		)


#============================================
def test_sealed_input_keeps_full_roster_while_its_evidence_surface_is_survivor_only(
	tmp_path: Path,
) -> None:
	"""Publication provenance retains all configured repositories without failed-repo evidence."""
	first = _packet("vosslab/first", "first.png")
	surface = _surface((first,))
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [
		daily_blog.repository_contracts.RepositoryRecord.from_dict({
			"repository": "vosslab/first", "repository_url": "https://github.com/vosslab/first",
			"clone_url": "https://github.com/vosslab/first.git", "created_at": "2020-01-01T00:00:00Z", "is_fork": False,
		}),
		daily_blog.repository_contracts.RepositoryRecord.from_dict({
			"repository": "vosslab/failed", "repository_url": "https://github.com/vosslab/failed",
			"clone_url": "https://github.com/vosslab/failed.git", "created_at": "2020-01-01T00:00:00Z", "is_fork": False,
		}),
	])
	post = daily_blog.artifacts.CompletePost.create(
		first.report_date, (surface.packet,), ("vosslab/first",),
		"# Survivor\n\nGrounded. <!-- evidence: " + first.items[0].evidence_id + " -->\n",
		(first.items[0].evidence_id,), first.report_date, str(tmp_path / "post.md"),
	)
	value = daily_blog.publication_finalization.SealedPublicationInput(
		first.report_date, "run-1", str(tmp_path), "owner", str(tmp_path), _identity(), False,
		roster, surface,
		daily_blog.publication_admission.survivor_assets(surface, {"assets/first.png": b"first"}), post,
		daily_blog.activity.build_daily_active_roster("vosslab", first.report_date, roster.roster_id, [{
			"repository": "vosslab/first", "sha": "a" * 40,
			"author_timestamp": first.report_date + "T12:00:00Z",
			"author_name": "Fixture", "message": "Fixture work",
		}]),
	)

	assert [item.repository for item in value.roster.repositories] == ["vosslab/failed", "vosslab/first"]
	assert {item.repository for item in value.publication_surface.packet.activity} == {"vosslab/first"}
	assert value.assets == {"assets/first.png": b"first"}

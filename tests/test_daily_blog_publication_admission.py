"""Permanent offline coverage for survivor-scoped publication admission."""

# Standard Library
import dataclasses
from pathlib import Path

# PIP3 modules
import pytest

# local repo modules
import daily_blog.activation
import daily_blog.artifacts
import daily_blog.editorial
import daily_blog.publication_contract
import daily_blog.publication_finalization
import daily_blog.publication_admission
import daily_blog.prompt_registry.editorial_contracts
import daily_blog.repository_contracts
import daily_blog.schema


_LIMITS = {"commit_subject_chars": 120, "context_chars": 12000, "excerpt_chars": 1000}


#============================================
def _packet(repository: str, asset_name: str) -> daily_blog.schema.EvidencePacket:
	"""Build one independently collected survivor packet with a screenshot asset."""
	activity = daily_blog.schema.RepositoryActivity(
		repository, "https://github.com/" + repository, "/fixture/" + asset_name,
		"a" * 40, (), (), (), False,
		(daily_blog.repository_contracts.RepositoryLifecycleEvent(
			"repository_created", "2020-01-01T00:00:00Z", False, "fixture",
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
def test_surface_uses_exact_survivors_and_only_their_bundle_asset_paths() -> None:
	"""Failed acquisition assets cannot leak into a survivor-scoped sealed bundle."""
	first, second = _packet("vosslab/first", "first.png"), _packet("vosslab/second", "second.png")
	surface = daily_blog.publication_admission.build_surface(
		tuple(sorted((first, second), key=lambda item: item.packet_id)),
		("vosslab/first", "vosslab/second"), _LIMITS,
	)
	assets = daily_blog.publication_admission.survivor_assets(surface, {
		"assets/first.png": b"first", "assets/second.png": b"second", "assets/failed.png": b"failed",
	})

	assert {item.repository for item in surface.packet.activity} == {"vosslab/first", "vosslab/second"}
	assert assets == {"assets/first.png": b"first", "assets/second.png": b"second"}


#============================================
def test_aggregate_publication_packet_does_not_replace_survivor_artifact_provenance(
	tmp_path: Path,
) -> None:
	"""A two-repository post keeps per-repository source packet identities through admission."""
	first, second = _packet("vosslab/first", "first.png"), _packet("vosslab/second", "second.png")
	sources = tuple(sorted((first, second), key=lambda item: item.packet_id))
	surface = daily_blog.publication_admission.build_surface(
		sources, ("vosslab/first", "vosslab/second"), _LIMITS,
	)
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

	with pytest.raises(RuntimeError, match="do not exactly cover"):
		daily_blog.publication_admission.build_surface(
			(first,), ("vosslab/first", "vosslab/second"), _LIMITS,
		)


#============================================
def test_direct_surface_rejects_duplicate_source_packet_identity() -> None:
	"""A direct constructor cannot inflate provenance by repeating one survivor packet."""
	first = _packet("vosslab/first", "first.png")
	surface = daily_blog.publication_admission.build_surface(
		(first,), ("vosslab/first",), _LIMITS,
	)

	with pytest.raises(RuntimeError, match="exact survivor evidence union"):
		daily_blog.publication_admission.PublicationSurface(
			(first, first), surface.packet, surface.projection, ("vosslab/first",),
		)


#============================================
def test_direct_surface_rejects_an_aggregate_not_derived_from_its_sources() -> None:
	"""Projection identity alone cannot bind a forged aggregate packet to survivor provenance."""
	first = _packet("vosslab/first", "first.png")
	surface = daily_blog.publication_admission.build_surface(
		(first,), ("vosslab/first",), _LIMITS,
	)
	forged_packet = dataclasses.replace(surface.packet, packet_id="f" * 64)
	forged_projection = dataclasses.replace(surface.projection, packet_id=forged_packet.packet_id)

	with pytest.raises(RuntimeError, match="aggregate packet does not match"):
		daily_blog.publication_admission.PublicationSurface(
			surface.source_packets, forged_packet, forged_projection, surface.repositories,
		)


#============================================
def test_direct_surface_rejects_a_forged_projection_for_the_same_packet() -> None:
	"""The frozen projection is an exact rendering of the survivor packet, not just its id."""
	first = _packet("vosslab/first", "first.png")
	surface = daily_blog.publication_admission.build_surface(
		(first,), ("vosslab/first",), _LIMITS,
	)
	forged_projection = dataclasses.replace(surface.projection, excerpts=())

	with pytest.raises(RuntimeError, match="projection does not match"):
		daily_blog.publication_admission.PublicationSurface(
			surface.source_packets, surface.packet, forged_projection, surface.repositories,
		)


#============================================
def test_surface_canonicalizes_survivor_packet_order_before_aggregation() -> None:
	"""Equivalent Stage-6 survivor tuples retain one stable aggregate identity."""
	first, second = _packet("vosslab/first", "first.png"), _packet("vosslab/second", "second.png")
	forward = daily_blog.publication_admission.build_surface(
		(first, second), ("vosslab/first", "vosslab/second"), _LIMITS,
	)
	reversed_surface = daily_blog.publication_admission.build_surface(
		(second, first), ("vosslab/first", "vosslab/second"), _LIMITS,
	)

	assert reversed_surface == forward


#============================================
def test_survivor_assets_rejects_a_missing_required_screenshot_byte() -> None:
	"""A sealed survivor packet cannot name an asset absent from the exact byte map."""
	first = _packet("vosslab/first", "first.png")
	surface = daily_blog.publication_admission.build_surface(
		(first,), ("vosslab/first",), _LIMITS,
	)

	with pytest.raises(RuntimeError, match="missing a survivor screenshot"):
		daily_blog.publication_admission.survivor_assets(surface, {})
	with pytest.raises(RuntimeError, match="missing a survivor screenshot"):
		daily_blog.publication_admission.survivor_assets(surface, {"assets/first.png": "not-bytes"})


#============================================
def test_sealed_input_keeps_full_roster_while_its_evidence_surface_is_survivor_only(
	tmp_path: Path,
) -> None:
	"""Publication provenance retains all configured repositories without failed-repo evidence."""
	first = _packet("vosslab/first", "first.png")
	surface = daily_blog.publication_admission.build_surface(
		(first,), ("vosslab/first",), _LIMITS,
	)
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
		roster, surface.packet, surface.projection,
		daily_blog.publication_admission.survivor_assets(surface, {"assets/first.png": b"first"}), post,
	)

	assert [item.repository for item in value.roster.repositories] == ["vosslab/failed", "vosslab/first"]
	assert {item.repository for item in value.packet.activity} == {"vosslab/first"}
	assert value.assets == {"assets/first.png": b"first"}

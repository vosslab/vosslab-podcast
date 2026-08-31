"""Behavioral tests for immutable daily-blog editorial artifacts."""

# Standard Library
import dataclasses
import pathlib
# PIP3 modules
import pytest

# local repo modules
import daily_blog.artifacts
import daily_blog.io_utils
import daily_blog.schema


#============================================
def packet(
	repository: str = "vosslab/project", report_date: str = "2026-08-23",
	commit: str = "a" * 40,
) -> daily_blog.schema.EvidencePacket:
	"""Return one authoritative packet with textual and screenshot evidence."""
	text = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", repository, commit, "CHANGELOG.md", "b" * 40,
		"A grounded implementation change.", "git show",
	)
	image = daily_blog.schema.EvidenceItem.create(
		"screenshot", repository, commit, "image.png", "c" * 40, "image",
		"capture", publish_path="images/project.png",
	)
	return daily_blog.schema.EvidencePacket.create(
		report_date, "America/Chicago", True, {}, [], [], [text, image],
	)


#============================================
def content(source: daily_blog.schema.EvidencePacket, body: str = "Text") -> str:
	"""Return prose bound to the first authoritative evidence item."""
	return f"{body} <!-- evidence: {source.items[0].evidence_id} -->"


#============================================
def outline(
	source: daily_blog.schema.EvidencePacket, body: str = "Text",
) -> daily_blog.artifacts.RepoOutline:
	"""Return one valid repository outline."""
	return daily_blog.artifacts.RepoOutline.create(
		source.report_date, (source,), "vosslab/project", content(source, body),
		(source.items[0].evidence_id,),
	)


#============================================
def complete(
	source: daily_blog.schema.EvidencePacket, output_path: str,
) -> daily_blog.artifacts.CompletePost:
	"""Return one valid complete post for the supplied destination."""
	return daily_blog.artifacts.CompletePost.create(
		source.report_date, (source,), ("vosslab/project",),
		f"---\ndate: {source.report_date}\n---\n" + content(source),
		(source.items[0].evidence_id,), source.report_date, output_path,
	)


#============================================
def with_identity(artifact: daily_blog.artifacts.EditorialArtifact, **changes: object) -> object:
	"""Return a machine-valid artifact with selected canonical fields replaced."""
	updated = dataclasses.replace(artifact, **changes)
	updated = dataclasses.replace(
		updated, content_hash=daily_blog.io_utils.sha256_text(updated.content),
	)
	return dataclasses.replace(
		updated,
		artifact_id="artifact-" + daily_blog.io_utils.hash_value(
			updated.identity_dict(),
		)[:24],
	)


#============================================
def test_eligibility_accepts_matching_packet_instance() -> None:
	"""Eligibility is true when candidate and authoritative packet identities match."""
	source = packet()
	assert daily_blog.artifacts.evaluate_eligibility(outline(source), (source,)).eligible


#============================================
def test_complete_post_source_attack_is_ineligible_without_faulting_peers(tmp_path: pathlib.Path) -> None:
	"""Unsafe model Markdown is a normal ineligible CompletePost result."""
	source = packet()
	post = daily_blog.artifacts.CompletePost.create(
		source.report_date, (source,), ("vosslab/project",),
		content(source, "Grounded <script>"), (source.items[0].evidence_id,),
		source.report_date, str(tmp_path / "post.md"), (),
	)

	result = daily_blog.artifacts.evaluate_eligibility(post, (source,), (str(tmp_path),))

	assert "unsafe_publication_source" in result.reasons


#============================================
def test_complete_post_create_replaces_an_authored_header_with_its_trusted_date(
	tmp_path: pathlib.Path,
) -> None:
	"""The artifact boundary owns date metadata while retaining the authored body bytes."""
	source = packet()
	body = "# Grounded\n\nText <!-- evidence: " + source.items[0].evidence_id + " -->\n"
	post = daily_blog.artifacts.CompletePost.create(
		source.report_date, (source,), ("vosslab/project",),
		"---\ndate: 2026-08-24\ntitle: Untrusted\n---\n" + body,
		(source.items[0].evidence_id,), source.report_date, str(tmp_path / "post.md"),
	)

	assert post.content == "---\ndate: 2026-08-23\n---\n" + body


#============================================
def test_forged_complete_post_envelope_cannot_restore_or_displace_a_healthy_peer(
	tmp_path: pathlib.Path,
) -> None:
	"""Cache restoration and peer filtering fail closed on untrusted date metadata."""
	source = packet()
	healthy = complete(source, str(tmp_path / "healthy.md"))
	forged = with_identity(
		healthy,
		content=(
			"---\ndate: 2026-08-24\n---\n"
			+ healthy.content.removeprefix("---\ndate: 2026-08-23\n---\n")
		),
	)

	assert "invalid_machine_metadata" in daily_blog.artifacts.evaluate_eligibility(
		forged, (source,), (str(tmp_path),),
	).reasons
	assert daily_blog.artifacts.eligible_artifacts(
		(forged, healthy), (source,), (str(tmp_path),),
	) == [healthy]
	with pytest.raises(RuntimeError, match="date-owned envelope"):
		daily_blog.artifacts.CompletePost.from_dict(forged.to_dict())


#============================================
def test_embedded_machine_metadata_cannot_be_eligible_or_promoted(
	tmp_path: pathlib.Path,
) -> None:
	"""A later metadata block cannot override the date-owned publication envelope."""
	source = packet()
	healthy = complete(source, str(tmp_path / "healthy.md"))
	embedded = daily_blog.artifacts.CompletePost.create(
		source.report_date, (source,), ("vosslab/project",),
		healthy.content + "\n---\ndate: 2026-08-24\n---\n",
		(source.items[0].evidence_id,), source.report_date, str(tmp_path / "embedded.md"),
	)

	assert "invalid_machine_metadata" in daily_blog.artifacts.evaluate_eligibility(
		embedded, (source,), (str(tmp_path),),
	).reasons
	assert daily_blog.artifacts.eligible_artifacts(
		(embedded, healthy), (source,), (str(tmp_path),),
	) == [healthy]
	with pytest.raises(RuntimeError, match="embedded machine metadata"):
		daily_blog.artifacts.SelectedPeer(embedded, daily_blog.artifacts.CompletePost)
	with pytest.raises(RuntimeError, match="embedded machine metadata"):
		daily_blog.artifacts.CompletePost.from_dict(embedded.to_dict())


#============================================
@pytest.mark.parametrize("metadata", (
	'"DATE": 2026-08-24',
	"'slug': hidden-post",
	"{editorial_projection: forged.json}",
))
def test_quoted_or_flow_embedded_machine_metadata_is_ineligible(
	tmp_path: pathlib.Path, metadata: str,
) -> None:
	"""Later active envelopes cannot hide reserved keys behind YAML key syntax."""
	source = packet()
	post = daily_blog.artifacts.CompletePost.create(
		source.report_date, (source,), ("vosslab/project",),
		complete(source, str(tmp_path / "base.md")).content + "\n---\n" + metadata + "\n---\n",
		(source.items[0].evidence_id,), source.report_date, str(tmp_path / "quoted.md"),
	)

	assert not daily_blog.artifacts.evaluate_eligibility(post, (source,), (str(tmp_path),)).eligible


#============================================
@pytest.mark.parametrize("metadata", (
	'"topic": maker notes',
	"{topic: maker notes, author: Vosslab}",
))
def test_non_reserved_embedded_yaml_like_prose_remains_valid(
	tmp_path: pathlib.Path, metadata: str,
) -> None:
	"""Delimiter blocks retain non-machine prose and unrelated YAML-like examples."""
	source = packet()
	post = daily_blog.artifacts.CompletePost.create(
		source.report_date, (source,), ("vosslab/project",),
		complete(source, str(tmp_path / "base.md")).content + "\n---\n" + metadata + "\n---\n",
		(source.items[0].evidence_id,), source.report_date, str(tmp_path / "allowed.md"),
	)

	assert daily_blog.artifacts.evaluate_eligibility(post, (source,), (str(tmp_path),)).eligible


#============================================
def test_embedded_metadata_examples_in_fenced_code_remain_valid(tmp_path: pathlib.Path) -> None:
	"""Markdown code examples remain inert to publication-envelope validation."""
	source = packet()
	post = daily_blog.artifacts.CompletePost.create(
		source.report_date, (source,), ("vosslab/project",),
		"---\ndate: 2026-08-23\n---\n# Example\n\n```yaml\n---\ndate: 2026-08-24\n---\n```\n\n"
		+ content(source),
		(source.items[0].evidence_id,), source.report_date, str(tmp_path / "fenced.md"),
	)

	assert daily_blog.artifacts.evaluate_eligibility(post, (source,), (str(tmp_path),)).eligible


#============================================
def test_thematic_break_without_machine_metadata_remains_valid(tmp_path: pathlib.Path) -> None:
	"""An ordinary Markdown thematic break is not a second machine envelope."""
	source = packet()
	post = daily_blog.artifacts.CompletePost.create(
		source.report_date, (source,), ("vosslab/project",),
		"---\ndate: 2026-08-23\n---\n# Note\n\nFirst thought.\n\n---\n\n" + content(source),
		(source.items[0].evidence_id,), source.report_date, str(tmp_path / "break.md"),
	)

	assert daily_blog.artifacts.evaluate_eligibility(post, (source,), (str(tmp_path),)).eligible


#============================================
def test_bad_peer_is_filtered_while_good_peer_continues() -> None:
	"""One malformed candidate does not terminate the peer evaluation path."""
	source = packet()
	bad = dataclasses.replace(outline(source), evidence_ids=("ev-missing",))
	assert daily_blog.artifacts.eligible_artifacts(
		(bad, outline(source)), (source,),
	) == [outline(source)]


#============================================
def test_eligible_artifacts_skips_unsupported_peer_objects() -> None:
	"""Unsupported peers do not prevent promotion of an eligible typed artifact."""
	source = packet()
	assert daily_blog.artifacts.eligible_artifacts(
		(object(), outline(source)), (source,),
	) == [outline(source)]


#============================================
@pytest.mark.parametrize(("mutate", "reason"), [
	(
		lambda artifact: dataclasses.replace(artifact, report_date="23-08-2026"),
		"invalid_machine_metadata",
	),
	(
		lambda artifact: dataclasses.replace(artifact, report_date="2026-99-99"),
		"invalid_machine_metadata",
	),
	(
		lambda artifact: dataclasses.replace(
			artifact, repositories=("vosslab/project", "vosslab/project"),
		),
		"invalid_machine_metadata",
	),
	(
		lambda artifact: dataclasses.replace(artifact, content_hash="not-a-sha"),
		"invalid_machine_metadata",
	),
	(
		lambda artifact: dataclasses.replace(artifact, artifact_id="artifact-bad"),
		"invalid_machine_metadata",
	),
])
def test_malformed_machine_metadata_is_categorical(mutate: object, reason: str) -> None:
	"""Malformed candidate fields produce ineligibility rather than a crash."""
	source = packet()
	result = daily_blog.artifacts.evaluate_eligibility(mutate(outline(source)), (source,))
	assert reason in result.reasons


#============================================
def test_unknown_evidence_reference_is_reported() -> None:
	"""A content reference outside the declared authoritative input is rejected."""
	source = packet()
	bad = dataclasses.replace(
		outline(source), content="Text <!-- evidence: ev-missing -->",
		evidence_ids=("ev-missing",),
	)
	result = daily_blog.artifacts.evaluate_eligibility(bad, (source,))
	assert "unknown_evidence_reference" in result.reasons


#============================================
def test_wrong_repository_evidence_is_reported() -> None:
	"""Evidence cannot substantiate an artifact outside its owning repository."""
	source = packet("vosslab/other")
	bad = daily_blog.artifacts.RepoOutline.create(
		source.report_date, (source,), "vosslab/project", content(source),
		(source.items[0].evidence_id,),
	)
	result = daily_blog.artifacts.evaluate_eligibility(bad, (source,))
	assert "evidence_outside_repository_scope" in result.reasons


#============================================
def test_packet_provenance_mismatch_is_reported() -> None:
	"""Every artifact packet identity must be present in the authoritative run set."""
	first = packet()
	second = packet("vosslab/project-two")
	result = daily_blog.artifacts.evaluate_eligibility(outline(first), (second,))
	assert "packet_provenance_mismatch" in result.reasons


#============================================
def test_artifact_packet_subset_accepts_unrelated_run_packets() -> None:
	"""A repository artifact remains grounded when the run includes another packet."""
	first = packet()
	second = packet("vosslab/project-two")
	assert daily_blog.artifacts.evaluate_eligibility(
		outline(first), (first, second),
	).eligible


#============================================
def test_evidence_owned_by_undeclared_packet_is_provenance_mismatch() -> None:
	"""Used evidence must be owned by a packet declared by the artifact."""
	first = packet()
	second = packet(commit="d" * 40)
	artifact = with_identity(
		outline(first), content=content(second),
		evidence_ids=(second.items[0].evidence_id,),
	)
	result = daily_blog.artifacts.evaluate_eligibility(artifact, (first, second))
	assert "packet_provenance_mismatch" in result.reasons


#============================================
def test_duplicate_authoritative_evidence_is_terminal_input_fault() -> None:
	"""Duplicate immutable evidence identities require a corrected shared packet input."""
	source = packet()
	duplicate = daily_blog.schema.EvidencePacket.create(
		source.report_date, source.timezone, True, {}, [], [], [source.items[0]],
	)
	with pytest.raises(RuntimeError, match="repeat an evidence identity"):
		daily_blog.artifacts.evaluate_eligibility(outline(source), (source, duplicate))


#============================================
def test_invalid_shared_packet_is_terminal_before_peer_filtering() -> None:
	"""Malformed shared evidence remains a pipeline fault even with bad peers."""
	source = packet()
	duplicate = daily_blog.schema.EvidencePacket.create(
		source.report_date, source.timezone, True, {}, [], [], [source.items[0]],
	)
	with pytest.raises(RuntimeError, match="repeat an evidence identity"):
		daily_blog.artifacts.eligible_artifacts(
			(object(), outline(source)), (source, duplicate),
		)


#============================================
def test_packet_date_mismatch_is_reported() -> None:
	"""Authoritative evidence packets must belong to the artifact report date."""
	source = packet()
	other_date = packet(report_date="2026-08-24")
	assert "evidence_report_date_mismatch" in daily_blog.artifacts.evaluate_eligibility(
		outline(source), (other_date,),
	).reasons


#============================================
@pytest.mark.parametrize("body", [
	"![shot](images/project.png)",
	"![shot][proof]\n\n[proof]: images/project.png",
	'<img src="images/project.png">',
	'<source srcset="images/project.png 1x, images/project.png 2x">',
])
def test_supported_image_forms_bind_approved_screenshot(body: str) -> None:
	"""Every supported image syntax is bound to declared screenshot evidence."""
	source = packet()
	post = daily_blog.artifacts.RepoOutline.create(
		source.report_date, (source,), "vosslab/project", content(source, body),
		(source.items[0].evidence_id,), ("images/project.png",),
	)
	assert daily_blog.artifacts.evaluate_eligibility(post, (source,)).eligible


#============================================
@pytest.mark.parametrize("body", [
	"![bad](images/other.png)",
	"![bad]",
	'<img>',
	'<source srcset="">',
	'<img src="images/other.png"',
	'![good](images/project.png) and ![bad]',
])
def test_unapproved_or_malformed_image_syntax_cannot_bypass(body: str) -> None:
	"""Malformed and non-screenshot image paths remain categorically ineligible."""
	source = packet()
	bad = dataclasses.replace(
		outline(source), content=content(source, body),
		image_paths=daily_blog.artifacts.referenced_image_paths(content(source, body)),
	)
	result = daily_blog.artifacts.evaluate_eligibility(bad, (source,))
	assert "unapproved_image_path" in result.reasons


#============================================
def test_image_metadata_must_exactly_bind_parsed_images() -> None:
	"""Changing image metadata after parsing makes the candidate invalid."""
	source = packet()
	bad = dataclasses.replace(outline(source), image_paths=("images/project.png",))
	result = daily_blog.artifacts.evaluate_eligibility(bad, (source,))
	assert "invalid_machine_metadata" in result.reasons


#============================================
def test_cross_repository_scope_cannot_exceed_resolved_evidence() -> None:
	"""Cross-repository metadata cannot enlarge the evidence-derived scope."""
	source = packet()
	artifact = daily_blog.artifacts.DailyOutline.create(
		source.report_date, (source,), ("vosslab/other", "vosslab/project"),
		content(source), (source.items[0].evidence_id,),
	)
	result = daily_blog.artifacts.evaluate_eligibility(artifact, (source,))
	assert "evidence_outside_repository_scope" in result.reasons


#============================================
def test_forged_persisted_repository_scope_is_rejected() -> None:
	"""Persisted repository metadata is an assertion, never scope authority."""
	source = packet()
	forged = with_identity(outline(source), repositories=("vosslab/forged",))
	result = daily_blog.artifacts.evaluate_eligibility(forged, (source,))
	assert "evidence_outside_repository_scope" in result.reasons


#============================================
def test_cited_scope_cannot_expand_beyond_stage_owned_scope() -> None:
	"""Evidence admitted by one stage cannot leak into a narrower stage scope."""
	source = packet()
	result = daily_blog.artifacts.evaluate_eligibility(
		outline(source), (source,), allowed_repositories=("vosslab/other",),
	)
	assert "evidence_outside_repository_scope" in result.reasons


#============================================
def test_repository_artifact_rejects_multi_repository_citations() -> None:
	"""A repository-local artifact cannot claim evidence from two repositories."""
	first = packet()
	second = packet("vosslab/other")
	evidence_ids = tuple(sorted((first.items[0].evidence_id, second.items[0].evidence_id)))
	combined = "\n".join(
		f"Grounded <!-- evidence: {evidence_id} -->" for evidence_id in evidence_ids
	)
	artifact = daily_blog.artifacts.RepoOutline.create(
		first.report_date, (first, second), "vosslab/project", combined,
		evidence_ids,
	)
	result = daily_blog.artifacts.evaluate_eligibility(
		artifact, (first, second),
		allowed_repositories=("vosslab/other", "vosslab/project"),
	)
	assert "evidence_outside_repository_scope" in result.reasons


#============================================
def test_cross_repository_artifact_can_contract_to_its_cited_scope() -> None:
	"""A cross-repository stage may retain only the repositories it cites."""
	first = packet()
	second = packet("vosslab/other")
	artifact = daily_blog.artifacts.DailyOutline.create(
		first.report_date, (first, second), ("vosslab/project",), content(first),
		(first.items[0].evidence_id,),
	)
	result = daily_blog.artifacts.evaluate_eligibility(
		artifact, (first, second),
		allowed_repositories=("vosslab/other", "vosslab/project"),
	)
	assert result.eligible


#============================================
def test_editorial_preference_never_changes_machine_eligibility() -> None:
	"""Eligibility depends on artifacts and evidence, not a subjective score."""
	source = packet()
	result = daily_blog.artifacts.evaluate_eligibility(
		outline(source, "Wonderful prose"), (source,),
	)
	assert result.eligible


#============================================
def test_complete_post_with_valid_path_is_eligible(tmp_path: pathlib.Path) -> None:
	"""A complete post is eligible at its approved date-owned destination."""
	source = packet()
	result = daily_blog.artifacts.evaluate_eligibility(
		complete(source, str(tmp_path / "2026-08-23.md")),
		(source,),
		(str(tmp_path),),
	)
	assert result.eligible


#============================================
def test_complete_post_binds_publication_identity(tmp_path: pathlib.Path) -> None:
	"""A post cannot claim an identity other than its report date."""
	source = packet()
	post = dataclasses.replace(
		complete(source, str(tmp_path / "2026-08-23.md")), publication_id="other-date",
	)
	assert "publication_identity_mismatch" in daily_blog.artifacts.evaluate_eligibility(
		post, (source,), (str(tmp_path),),
	).reasons


#============================================
@pytest.mark.parametrize("candidate_path", ["relative.md", 7, None])
def test_invalid_output_candidate_path_is_filtered(
	tmp_path: pathlib.Path, candidate_path: object,
) -> None:
	"""Non-string and relative publication destinations are invalid candidates."""
	source = packet()
	bad = dataclasses.replace(
		complete(source, str(tmp_path / "post.md")), output_path=candidate_path,
	)
	assert "output_path_outside_root" in daily_blog.artifacts.evaluate_eligibility(
		bad, (source,), (str(tmp_path),),
	).reasons


#============================================
def test_output_path_must_be_descendant_not_root(tmp_path: pathlib.Path) -> None:
	"""The approved root itself is not a valid publication file destination."""
	source = packet()
	assert "output_path_outside_root" in daily_blog.artifacts.evaluate_eligibility(
		complete(source, str(tmp_path)), (source,), (str(tmp_path),),
	).reasons


#============================================
def test_output_dotdot_escape_is_rejected(tmp_path: pathlib.Path) -> None:
	"""Canonical path containment rejects lexical parent-directory escapes."""
	source = packet()
	escaped = str(tmp_path / "nested" / ".." / ".." / "outside.md")
	assert "output_path_outside_root" in daily_blog.artifacts.evaluate_eligibility(
		complete(source, escaped), (source,), (str(tmp_path),),
	).reasons


#============================================
def test_output_symlink_escape_is_rejected(tmp_path: pathlib.Path) -> None:
	"""Canonical containment resolves an existing symlink parent before approval."""
	outside = tmp_path.parent / "outside"
	outside.mkdir(exist_ok=True)
	link = tmp_path / "link"
	try:
		link.symlink_to(outside, target_is_directory=True)
	except OSError:
		pytest.skip("platform does not permit test symlinks")
	source = packet()
	assert "output_path_outside_root" in daily_blog.artifacts.evaluate_eligibility(
		complete(source, str(link / "post.md")), (source,), (str(tmp_path),),
	).reasons


#============================================
def test_invalid_shared_output_root_is_terminal_configuration_fault(
	tmp_path: pathlib.Path,
) -> None:
	"""Shared configuration defects are not candidate degradation."""
	source = packet()
	with pytest.raises(RuntimeError, match="Approved output root"):
		daily_blog.artifacts.evaluate_eligibility(
			complete(source, str(tmp_path / "post.md")), (source,),
			(str(tmp_path / "missing"),),
		)


#============================================
@pytest.mark.parametrize("artifact_type", [
	daily_blog.artifacts.RepoOutline, daily_blog.artifacts.RepoStory,
	daily_blog.artifacts.DailyOutline, daily_blog.artifacts.CompletePost,
])
def test_each_artifact_round_trips_and_rejects_identity_tampering(
	artifact_type: type, tmp_path: pathlib.Path,
) -> None:
	"""Every ladder rung serializes independently and verifies its exact identity."""
	source = packet()
	if artifact_type is daily_blog.artifacts.CompletePost:
		artifact = complete(source, str(tmp_path / "post.md"))
	elif artifact_type is daily_blog.artifacts.DailyOutline:
		artifact = artifact_type.create(
			source.report_date, (source,), ("vosslab/project",), content(source),
			(source.items[0].evidence_id,),
		)
	else:
		artifact = artifact_type.create(
			source.report_date, (source,), "vosslab/project", content(source),
			(source.items[0].evidence_id,),
		)
	tampered = artifact.to_dict() | {"artifact_id": "artifact-" + "0" * 24}
	with pytest.raises(RuntimeError):
		artifact_type.from_dict(tampered)
	assert artifact_type.from_dict(artifact.to_dict()) == artifact


#============================================
@pytest.mark.parametrize(("outcome", "kind"), [
	(
		lambda value: daily_blog.artifacts.SelectedPeer(
			value, daily_blog.artifacts.RepoOutline,
		),
		"selected_peer",
	),
	(
		lambda value: daily_blog.artifacts.PreservedArtifact(
			value, daily_blog.artifacts.RepoOutline,
		),
		"preserved_artifact",
	),
	(
		lambda value: daily_blog.artifacts.DegradedPromotion(
			value, daily_blog.artifacts.RepoOutline, ("route_timeout",),
		),
		"degraded_promotion",
	),
	(
		lambda value: daily_blog.artifacts.NoArtifact(
			daily_blog.artifacts.RepoOutline, "route_unavailable",
		),
		"no_artifact",
	),
])
def test_stage_outcomes_have_stable_behavioral_kinds(outcome: object, kind: str) -> None:
	"""Promotion state is identified by stable behavior rather than class topology."""
	assert outcome(outline(packet())).kind == kind


#============================================
def test_selected_peer_kind_cannot_be_spoofed() -> None:
	"""Selected candidates retain their machine-owned outcome label."""
	with pytest.raises(TypeError):
		daily_blog.artifacts.SelectedPeer(
			outline(packet()), daily_blog.artifacts.RepoOutline, kind="spoofed",
		)


#============================================
def test_preserved_artifact_kind_cannot_be_spoofed() -> None:
	"""Preserved artifacts retain their machine-owned outcome label."""
	with pytest.raises(TypeError):
		daily_blog.artifacts.PreservedArtifact(
			outline(packet()), daily_blog.artifacts.RepoOutline, kind="spoofed",
		)


#============================================
def test_degraded_promotion_kind_cannot_be_spoofed() -> None:
	"""Degraded promotions retain their machine-owned outcome label."""
	with pytest.raises(TypeError):
		daily_blog.artifacts.DegradedPromotion(
			outline(packet()), daily_blog.artifacts.RepoOutline,
			("route_timeout",), kind="spoofed",
		)


#============================================
def test_no_artifact_kind_cannot_be_spoofed() -> None:
	"""No-artifact faults retain their machine-owned outcome label."""
	with pytest.raises(TypeError):
		daily_blog.artifacts.NoArtifact(
			daily_blog.artifacts.RepoOutline, "route_unavailable", kind="spoofed",
		)


#============================================
def test_daily_outline_ranking_review_loss_has_a_typed_outcome() -> None:
	"""Stage 5 total ranking-review loss remains a machine-readable outcome."""
	outcome = daily_blog.artifacts.NoArtifact(
		daily_blog.artifacts.DailyOutline, "no_eligible_ranking_review",
	)
	assert outcome.reason == "no_eligible_ranking_review"
	with pytest.raises(RuntimeError):
		daily_blog.artifacts.NoArtifact(
			daily_blog.artifacts.DailyOutline, "unknown_reason",
		)


#============================================
def test_wrong_rung_outcome_is_rejected() -> None:
	"""Same-rung outcomes reject an artifact from a different editorial stage."""
	source = packet()
	story = daily_blog.artifacts.RepoStory.create(
		source.report_date, (source,), "vosslab/project", content(source),
		(source.items[0].evidence_id,),
	)
	with pytest.raises(RuntimeError):
		daily_blog.artifacts.SelectedPeer(story, daily_blog.artifacts.RepoOutline)

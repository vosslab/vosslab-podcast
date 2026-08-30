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
		source.report_date, (source,), ("vosslab/project",), content(source),
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
def test_each_repository_needs_resolved_evidence() -> None:
	"""Cross-repository artifacts need evidence density for each named repository."""
	source = packet()
	artifact = daily_blog.artifacts.DailyOutline.create(
		source.report_date, (source,), ("vosslab/other", "vosslab/project"),
		content(source), (source.items[0].evidence_id,),
	)
	result = daily_blog.artifacts.evaluate_eligibility(artifact, (source,))
	assert "insufficient_evidence_density" in result.reasons


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

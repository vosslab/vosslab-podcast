"""Permanent offline tests for the deterministic Stage 8 publication boundary."""

# Standard Library
import dataclasses
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.artifacts
import daily_blog.publication_admission
import daily_blog.publication_validation
import daily_blog.repository_contracts
import daily_blog.schema
import daily_blog.stage6


_CONTEXT_LIMITS = {
	"commit_subject_chars": 120,
	"context_chars": 60000,
	"excerpt_chars": 1000,
}


#============================================
def _packet(
	report_date: str = "2026-08-29", marker: str = "a",
) -> daily_blog.schema.EvidencePacket:
	"""Return one authoritative source packet for Stage 8 checks."""
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/project", marker * 40, "docs/CHANGELOG.md", "b" * 40,
		"A grounded change.", "git show",
	)
	activity = daily_blog.schema.RepositoryActivity(
		"vosslab/project", "https://github.com/vosslab/project", "/fixture/project",
		marker * 40, (), (), (), False,
		(daily_blog.repository_contracts.RepositoryLifecycleEvent(
			"repository_created", "2020-01-01T00:00:00Z", False, "fixture",
		),),
	)
	return daily_blog.schema.EvidencePacket.create(
		report_date, "America/Chicago", True, {}, [], [activity], [item],
	)


#============================================
def _post(
	tmp_path: pathlib.Path, content: str | None = None,
	packet: daily_blog.schema.EvidencePacket | None = None,
) -> daily_blog.artifacts.CompletePost:
	"""Build one exact pre-Stage-8 post with a real evidence binding."""
	packet = packet or _packet()
	evidence_id = packet.items[0].evidence_id
	narrative = (
		"I traced the implementation through its concrete boundary, then checked how the grounded change "
		"would shape the next useful decision for readers and maintainers alike. "
	) * 17
	post_content = content or (
		"# Making evidence visible\n\nI followed [vosslab/project](https://github.com/vosslab/project) "
		"through one clear, grounded boundary. <!-- evidence: " + evidence_id
		+ " -->\n\n<!-- more -->\n\n## The grounded boundary\n\n"
		+ narrative + "<!-- evidence: " + evidence_id + " -->\n\n## Project coverage\n\n"
		"vosslab/project supplied the grounded implementation evidence for this post. "
		"<!-- evidence: " + evidence_id + " -->\n"
	)
	if not post_content.startswith("---\n"):
		post_content = f"---\ndate: {packet.report_date}\n---\n" + post_content
	return daily_blog.artifacts.CompletePost.create(
		packet.report_date, (packet,), ("vosslab/project",), post_content,
		daily_blog.artifacts.evidence_references(post_content),
		packet.report_date, str(tmp_path / (packet.report_date + ".md")),
	)


#============================================
def _surface(
	packets: tuple[daily_blog.schema.EvidencePacket, ...],
) -> daily_blog.publication_admission.PublicationSurface:
	"""Build the exact Stage-6 authority required by Stage 8 admission."""
	ordered_packets = tuple(sorted(packets, key=lambda item: item.packet_id))
	stories = tuple(sorted((
		daily_blog.artifacts.RepoStory.create(
			packet.report_date, (packet,), packet.items[0].repository,
			"Story <!-- evidence: " + packet.items[0].evidence_id + " -->",
			(packet.items[0].evidence_id,),
		)
		for packet in ordered_packets
	), key=lambda item: item.artifact_id))
	repositories = tuple(sorted(item.repositories[0] for item in stories))
	evidence_ids = tuple(sorted(item.evidence_ids[0] for item in stories))
	outline = daily_blog.artifacts.DailyOutline.create(
		ordered_packets[0].report_date, ordered_packets, repositories,
		"Outline <!-- evidence: " + ", ".join(evidence_ids) + " -->", evidence_ids,
	)
	return daily_blog.stage6.build_stage6_publication_surface(
		outline, stories, ordered_packets, _CONTEXT_LIMITS,
	)


#============================================
def _validate(
	post: daily_blog.artifacts.CompletePost, tmp_path: pathlib.Path,
	packet: daily_blog.schema.EvidencePacket | None = None,
) -> daily_blog.publication_validation.PublicationValidationResult:
	"""Run one Stage 8 boundary with stable coordinator-owned inputs."""
	packets = (packet or _packet(),)
	return daily_blog.publication_validation.validate_and_repair_complete_post(
		post, report_date="2026-08-29", packets=packets,
		approved_output_root=str(tmp_path), generator_run="run-20260829",
		surface=_surface(packets),
	)


#============================================
def _different_packet_with_same_evidence() -> daily_blog.schema.EvidencePacket:
	"""Return a new authority packet whose evidence IDs deliberately overlap."""
	packet = _packet()
	return daily_blog.schema.EvidencePacket.create(
		packet.report_date, packet.timezone, packet.complete, {"changed": 1}, [], list(packet.activity),
		list(packet.items),
	)


#============================================
def test_constructs_closed_metadata_without_changing_authored_body(tmp_path: pathlib.Path) -> None:
	"""Stage 8 adds only its opening machine-owned region to author bytes."""
	post = _post(tmp_path)
	result = _validate(post, tmp_path)

	assert result.reasons == ("machine_metadata_repaired",)
	assert result.post.content.split("---\n", 2)[2].endswith(
		post.content.split("---\n", 2)[2],
	)


#============================================
def test_repairs_only_metadata_and_is_idempotent(tmp_path: pathlib.Path) -> None:
	"""A stale known header becomes canonical without prose rewriting on rerun."""
	post = _post(tmp_path)
	body, _metadata = daily_blog.publication_validation._body_and_metadata(post.content)
	stale = daily_blog.artifacts.CompletePost.create_publication_derivative(
		post.report_date, (_packet(),), post.repositories, body, post.evidence_ids,
		post.publication_id, post.output_path,
		{
			"date": post.report_date, "slug": "stale", "generator_run": "old",
			"evidence_manifest": "old.json", "editorial_projection": "old.json",
		}, post.image_paths,
	)
	first = _validate(stale, tmp_path)
	second = _validate(first.post, tmp_path)

	assert daily_blog.publication_validation._body_and_metadata(first.post.content)[0] == body
	assert second.reasons == () and second.post is first.post


#============================================
def test_rejects_packet_union_outside_the_survivor_publication_surface(tmp_path: pathlib.Path) -> None:
	"""Stage 8 cannot expand a survivor-scoped post through an aggregate packet union."""
	first = _packet()
	second_item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/second", "c" * 40, "docs/CHANGELOG.md", "d" * 40,
		"A second grounded change.", "git show",
	)
	second = daily_blog.schema.EvidencePacket.create(
		first.report_date, first.timezone, True, {}, [], [daily_blog.schema.RepositoryActivity(
			"vosslab/second", "https://github.com/vosslab/second", "/fixture/second",
			"c" * 40, (), (), (), False,
			(daily_blog.repository_contracts.RepositoryLifecycleEvent(
				"repository_created", "2020-01-01T00:00:00Z", False, "fixture",
			),),
		)], [second_item],
	)
	packets = tuple(sorted((first, second), key=lambda item: item.packet_id))
	evidence_id = first.items[0].evidence_id
	post = daily_blog.artifacts.CompletePost.create(
		first.report_date, packets, ("vosslab/project",),
		f"---\ndate: {first.report_date}\n---\n# Scoped repair\n\nGrounded. <!-- evidence: "
		+ evidence_id + " -->\n",
		(evidence_id,), first.report_date, str(tmp_path / "scoped.md"),
	)
	with pytest.raises(RuntimeError, match="surface does not match"):
		daily_blog.publication_validation.validate_and_repair_complete_post(
			post, report_date=first.report_date, packets=packets,
			approved_output_root=str(tmp_path), generator_run="run-20260829",
			surface=_surface((first,)),
		)


#============================================
def test_rejects_forged_noop_or_derivative_identity_links(tmp_path: pathlib.Path) -> None:
	"""Stage 8 cannot describe a clone or provenance-changing post as a repair."""
	post = _post(tmp_path)
	repaired = _validate(post, tmp_path)
	with pytest.raises(RuntimeError, match="no-op must preserve"):
		daily_blog.publication_validation.PublicationValidationResult(
			dataclasses.replace(repaired.post), repaired.post, repaired.post.artifact_id,
			repaired.post.artifact_id, False, (),
		)
	changed = daily_blog.artifacts.CompletePost.create(
		post.report_date, (_packet(),), post.repositories, repaired.post.content, post.evidence_ids,
		post.publication_id, str(tmp_path / "other.md"), post.image_paths,
	)
	with pytest.raises(RuntimeError, match="changed trusted provenance"):
		daily_blog.publication_validation.PublicationValidationResult(
			post, changed, post.artifact_id, changed.artifact_id, True,
			("machine_metadata_constructed",),
		)


#============================================
def test_rejects_unknown_evidence_without_rewriting_content(tmp_path: pathlib.Path) -> None:
	"""Evidence tampering remains a terminal eligibility failure."""
	post = _post(
		tmp_path, "# Making evidence visible\n\nI invented it. <!-- evidence: ev-missing -->\n",
	)

	with pytest.raises(RuntimeError, match="unknown_evidence_reference"):
		_validate(post, tmp_path)


#============================================
def test_rejects_wrong_date_path_and_packet_provenance(tmp_path: pathlib.Path) -> None:
	"""Stage 8 fail-closes date-owned artifact and authoritative-input mismatches."""
	post = _post(tmp_path)
	wrong_date = _post(tmp_path, packet=_packet("2026-08-28"))

	with pytest.raises(RuntimeError, match="report date"):
		_validate(wrong_date, tmp_path)
	with pytest.raises(RuntimeError, match="packet_provenance_mismatch"):
		_validate(post, tmp_path, _different_packet_with_same_evidence())


#============================================
def test_rejects_unconfined_path_and_ambiguous_metadata(tmp_path: pathlib.Path) -> None:
	"""Path traversal and an unparseable owned region cannot enter publication."""
	post = _post(tmp_path)
	outside = daily_blog.artifacts.CompletePost.create(
		post.report_date, (_packet(),), post.repositories, post.content, post.evidence_ids,
		post.publication_id, str(tmp_path.parent / "outside.md"), post.image_paths,
	)
	ambiguous = _post(tmp_path, "---\ndate: 2026-08-29\ndate: 2026-08-29\n---\n" + post.content)

	with pytest.raises(RuntimeError, match="output_path_outside_root"):
		_validate(outside, tmp_path)
	with pytest.raises(RuntimeError, match="input artifact is malformed"):
		_validate(ambiguous, tmp_path)

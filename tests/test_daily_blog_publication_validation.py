"""Permanent offline tests for the deterministic Stage 8 publication boundary."""

# Standard Library
import dataclasses
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.artifacts
import daily_blog.publication_validation
import daily_blog.schema


#============================================
def _packet(
	report_date: str = "2026-08-29", marker: str = "a",
) -> daily_blog.schema.EvidencePacket:
	"""Return one authoritative source packet for Stage 8 checks."""
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/project", marker * 40, "docs/CHANGELOG.md", "b" * 40,
		"A grounded change.", "git show",
	)
	return daily_blog.schema.EvidencePacket.create(
		report_date, "America/Chicago", True, {}, [], [], [item],
	)


#============================================
def _post(
	tmp_path: pathlib.Path, content: str | None = None,
	packet: daily_blog.schema.EvidencePacket | None = None,
) -> daily_blog.artifacts.CompletePost:
	"""Build one exact pre-Stage-8 post with a real evidence binding."""
	packet = packet or _packet()
	evidence_id = packet.items[0].evidence_id
	return daily_blog.artifacts.CompletePost.create(
		packet.report_date, (packet,), ("vosslab/project",), content or (
			"# Making evidence visible\n\nI kept the boundary explicit. <!-- evidence: "
			+ evidence_id + " -->\n"
		), daily_blog.artifacts.evidence_references(content) if content else (evidence_id,),
		packet.report_date, str(tmp_path / (packet.report_date + ".md")),
	)


#============================================
def _validate(
	post: daily_blog.artifacts.CompletePost, tmp_path: pathlib.Path,
	packet: daily_blog.schema.EvidencePacket | None = None,
) -> daily_blog.publication_validation.PublicationValidationResult:
	"""Run one Stage 8 boundary with stable coordinator-owned inputs."""
	return daily_blog.publication_validation.validate_and_repair_complete_post(
		post, report_date="2026-08-29", packets=(packet or _packet(),),
		approved_output_root=str(tmp_path), generator_run="run-20260829",
	)


#============================================
def _different_packet_with_same_evidence() -> daily_blog.schema.EvidencePacket:
	"""Return a new authority packet whose evidence IDs deliberately overlap."""
	packet = _packet()
	return daily_blog.schema.EvidencePacket.create(
		packet.report_date, packet.timezone, packet.complete, {"changed": 1}, [], [],
		list(packet.items),
	)


#============================================
def test_constructs_closed_metadata_without_changing_authored_body(tmp_path: pathlib.Path) -> None:
	"""Stage 8 adds only its opening machine-owned region to author bytes."""
	post = _post(tmp_path)
	result = _validate(post, tmp_path)

	assert result.reasons == ("machine_metadata_constructed",)
	assert result.post.content.endswith(post.content)


#============================================
def test_repairs_only_metadata_and_is_idempotent(tmp_path: pathlib.Path) -> None:
	"""A stale known header becomes canonical without prose rewriting on rerun."""
	post = _post(tmp_path)
	stale = _post(
		tmp_path, "---\ndate: 2026-08-28\nslug: stale\ngenerator_run: old\n"
		"evidence_manifest: old.json\neditorial_projection: old.json\n---\n" + post.content,
	)
	first = _validate(stale, tmp_path)
	second = _validate(first.post, tmp_path)

	assert first.post.content.endswith(post.content)
	assert second.reasons == () and second.post is first.post


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
	with pytest.raises(RuntimeError, match="malformed or ambiguous"):
		_validate(ambiguous, tmp_path)

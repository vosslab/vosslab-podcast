"""Offline tests for the shared complete-candidate-set prompt contract."""

# PIP3 modules
import pytest

# local repo modules
import daily_blog.artifacts
import daily_blog.candidate_set_prompts
import daily_blog.schema


#============================================
def _peers() -> tuple[daily_blog.artifacts.RepoOutline, ...]:
	"""Return three grounded peers with distinct identities."""
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "owner/repository", "a" * 40, "CHANGELOG.md", "b" * 40,
		"Grounded change.", "git show",
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-29", "America/Chicago", True, {}, [], [], [item],
	)
	return tuple(
		daily_blog.artifacts.RepoOutline.create(
			packet.report_date, (packet,), "owner/repository",
			f"Candidate {index}. <!-- evidence: {item.evidence_id} -->",
			(item.evidence_id,),
		)
		for index in range(3)
	)


#============================================
def test_renderer_labels_the_complete_set_once_and_parser_resolves_identity() -> None:
	"""The model sees every peer once and returns only an allowlisted anonymous label."""
	peers = _peers()
	prompt, labels = daily_blog.candidate_set_prompts.render_candidate_set_review(
		"Prefer the clearest grounded candidate.", '{"day":"fixture"}', peers,
	)

	assert tuple(labels) == ("C01", "C02", "C03")
	assert all(prompt.count(peer.content) == 1 for peer in peers)
	response = (
		'{"winner":"C02","reason":"clearest","evidence_quality":"high",'
		'"confidence":0.9}'
	)
	assert daily_blog.candidate_set_prompts.parse_candidate_set_verdict(
		response, labels,
	) == peers[1].artifact_id


#============================================
@pytest.mark.parametrize("winner", ('"UNKNOWN"', "[]", "null"))
def test_parser_rejects_winners_outside_the_supplied_label_set(winner: str) -> None:
	"""Malformed or invented winner values cannot choose a candidate."""
	labels = {"C01": "first", "C02": "second"}
	response = (
		'{"winner":' + winner + ',"reason":"choice","evidence_quality":"high",'
		'"confidence":1}'
	)
	with pytest.raises(daily_blog.candidate_set_prompts.CandidateSetVerdictParseError):
		daily_blog.candidate_set_prompts.parse_candidate_set_verdict(response, labels)

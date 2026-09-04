"""Tests for the deterministic report-day repository footer."""

# Standard Library
import pathlib

# local repo modules
import daily_blog.artifacts
import daily_blog.publication_coverage
import daily_blog.repository_contracts
import daily_blog.schema


#============================================
def _activity(repository: str, count: int) -> daily_blog.schema.RepositoryActivity:
	commits = tuple(
		daily_blog.schema.CommitActivity(
			sha=f"{index + 1:040x}", parents=("f" * 40,), author_name="Maker",
			author_email="maker@example.com", author_timestamp="2026-08-31T12:00:00-05:00",
			committer_timestamp="2026-08-31T12:00:00-05:00", message="Work",
		)
		for index in range(count)
	)
	return daily_blog.schema.RepositoryActivity(
		repository, "https://github.com/" + repository, "/fixture/" + repository,
		commits[-1].sha, commits,
		tuple(daily_blog.schema.RevisionRange("f" * 40, commit.sha) for commit in commits),
		tuple(commit.sha for commit in commits), False,
		(daily_blog.repository_contracts.RepositoryLifecycleEvent(
			"repository_created", "2020-01-01T00:00:00Z", False, "fixture",
		),),
	)


#============================================
def test_coverage_replaces_authored_subset_with_all_exact_activity(tmp_path: pathlib.Path) -> None:
	activities = (_activity("vosslab/alpha", 1), _activity("vosslab/beta", 3))
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/alpha", activities[0].commits[0].sha, "", "a" * 40,
		"Work", "fixture",
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-31", "America/Chicago", True, {}, [], activities, [item],
	)
	evidence_id = item.evidence_id
	post = daily_blog.artifacts.CompletePost.create(
		packet.report_date, (packet,), ("vosslab/alpha",),
		"# Work\n\nNarrative. <!-- evidence: " + evidence_id
		+ " -->\n\n## Project coverage\n\n- vosslab/alpha\n",
		(evidence_id,), packet.report_date, str(tmp_path / "post.md"),
	)

	result = daily_blog.publication_coverage.attach_project_coverage(
		post, (packet,), activities,
	)

	assert result.content.count("## Project coverage") == 1
	assert "<!-- evidence: " + evidence_id + " -->" in result.content
	assert result.content.endswith(
		"## Project coverage\n\n"
		"- [vosslab/beta](https://github.com/vosslab/beta) — 3 commits\n"
		"- [vosslab/alpha](https://github.com/vosslab/alpha) — 1 commit\n"
	)
	assert result.repositories == post.repositories
	assert result.evidence_ids == post.evidence_ids


#============================================
def test_coverage_rejects_activity_not_bound_to_evidence(tmp_path: pathlib.Path) -> None:
	activity = _activity("vosslab/alpha", 1)
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/alpha", activity.commits[0].sha, "", "a" * 40,
		"Work", "fixture",
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-31", "America/Chicago", True, {}, [], (activity,), (item,),
	)
	post = daily_blog.artifacts.CompletePost.create(
		packet.report_date, (packet,), ("vosslab/alpha",),
		"# Work\n\nNarrative. <!-- evidence: " + item.evidence_id + " -->\n",
		(item.evidence_id,), packet.report_date, str(tmp_path / "post.md"),
	)

	try:
		daily_blog.publication_coverage.attach_project_coverage(
			post, (packet,), (_activity("vosslab/beta", 1),),
		)
	except RuntimeError as error:
		assert "sealed evidence activity" in str(error)
	else:
		raise AssertionError("Unbound activity was accepted.")

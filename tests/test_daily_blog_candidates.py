"""Durable reader-visible validation tests for daily-blog candidates."""

# PIP3 modules
import pytest

# local repo modules
import daily_blog.candidates
import daily_blog.projection
import daily_blog.repository_contracts
import daily_blog.schema


V4_POLICY = daily_blog.prompt_registry.V4_MAKER_VALIDATION_POLICY


#============================================
def candidate_context() -> tuple[
	daily_blog.schema.EvidencePacket,
	daily_blog.schema.EditorialProjection,
	str,
]:
	"""Build a valid post whose reader-visible rules can be exercised."""
	commit = daily_blog.schema.CommitActivity(
		sha="a" * 40,
		parents=("b" * 40,),
		author_name="Author",
		author_email="author@example.com",
		author_timestamp="2026-08-23T12:00:00-05:00",
		committer_timestamp="2026-08-23T12:00:00-05:00",
		message="Make the story linkable",
	)
	activity = daily_blog.schema.RepositoryActivity(
		repository="vosslab/project",
		repository_url="https://github.com/vosslab/project",
		cache_path="/nonexistent/vosslab/project",
		default_revision="a" * 40,
		commits=(commit,),
		revision_ranges=(daily_blog.schema.RevisionRange("b" * 40, "a" * 40),),
		snapshot_commits=("a" * 40,),
		is_fork=False,
		lifecycle_events=(daily_blog.repository_contracts.RepositoryLifecycleEvent(
			"repository_created", "2020-01-01T00:00:00Z", False, "github_owner_roster",
		),),
	)
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/project", "a" * 40, "docs/CHANGELOG.md", "c" * 40,
		"## 2026-08-23\n\n- Made the story linkable.\n", "git show",
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [activity], [item]
	)
	projection = daily_blog.projection.build_projection(
		packet, {"context_chars": 12000, "excerpt_chars": 2000, "commit_subject_chars": 160},
	)
	intro = "I connected exact evidence to a small design decision and enjoyed the boundary becoming clear. " * 4
	detail = "I followed the implementation through its useful constraint, the behavior it changed, and the question I still want to test. " * 18
	post = (
		"---\ndate: 2026-08-23\nslug: story-link\ngenerator_run: run-123\n"
		"evidence_manifest: evidence.json\neditorial_projection: editorial_projection.json\n---\n\n"
		"# Making the story linkable\n\n"
		+ intro.strip() + f" <!-- evidence: {item.evidence_id} -->\n\n<!-- more -->\n\n"
		+ "## The useful boundary\n\n"
		+ detail.strip() + f" <!-- evidence: {item.evidence_id} -->\n\n"
		+ "## Project coverage\n\n"
		+ f"I recorded vosslab/project in the evidence packet. <!-- evidence: {item.evidence_id} -->\n"
	)
	return packet, projection, post


#============================================
def test_candidate_requires_first_repository_mention_to_be_a_direct_link() -> None:
	"""A reader can reach an active project from its first narrative mention."""
	packet, projection, post = candidate_context()
	post = post.replace(
		"I connected exact evidence",
		"I connected [vosslab/project](https://github.com/vosslab/project) to exact evidence",
		1,
	)

	assert daily_blog.candidates.validate_candidate(post, packet, projection, "run-123", V4_POLICY) == []


#============================================
def test_candidate_reports_unlinked_first_repository_mention() -> None:
	"""A bare project name cannot be mistaken for a reader-facing repository link."""
	packet, projection, post = candidate_context()
	post = post.replace("I connected exact evidence", "I connected vosslab/project to exact evidence", 1)

	issues = daily_blog.candidates.validate_candidate(post, packet, projection, "run-123", V4_POLICY)

	assert any("First narrative mention of vosslab/project" in issue for issue in issues)


#============================================
@pytest.mark.parametrize(
	("source", "expected"),
	(
		("[four readable words](https://example.test/a)", 3),
		("`hidden code words` visible words <!-- hidden comment words -->", 2),
	),
)
def test_visible_word_count_tracks_rendered_markdown(source: str, expected: int) -> None:
	"""Narrative limits count what a reader sees rather than Markdown machinery."""
	assert daily_blog.candidates.visible_word_count(source) == expected

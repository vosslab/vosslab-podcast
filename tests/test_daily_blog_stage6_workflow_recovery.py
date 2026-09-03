"""Offline behavior checks for the Stage 6 recovery write boundary."""

# Standard Library
import pathlib

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.config
import daily_blog.daily_outline_workflow
import daily_blog.editorial_stage_config
import daily_blog.io_utils
import daily_blog.routes
import daily_blog.schema
import daily_blog.stage6
import daily_blog.repository_contracts


_CONTEXT_LIMITS = {
	"commit_subject_chars": 120,
	"context_chars": 60000,
	"excerpt_chars": 1000,
}


def _input(root: pathlib.Path) -> daily_blog.stage6.Stage6Input:
	"""Build one fully grounded Stage 6 boundary with terminal story provenance."""
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/recovery", "a" * 40, "CHANGELOG.md", "b" * 40,
		"Grounded recovery change.", "git show",
	)
	activity = daily_blog.schema.RepositoryActivity(
		"vosslab/recovery", "https://github.com/vosslab/recovery", "/fixture/recovery",
		"a" * 40, (), (), (), False,
		(daily_blog.repository_contracts.RepositoryLifecycleEvent(
			"repository_created", "2020-01-01T00:00:00Z", False, "fixture",
		),),
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-29", "America/Chicago", True, {}, [], [activity], [item],
	)
	story = daily_blog.artifacts.RepoStory.create(
		packet.report_date, (packet,), "vosslab/recovery",
		"Story <!-- evidence: " + item.evidence_id + " -->", (item.evidence_id,),
	)
	repository_outline = daily_blog.artifacts.RepoOutline.create(
		packet.report_date, (packet,), "vosslab/recovery",
		"Outline <!-- evidence: " + item.evidence_id + " -->", (item.evidence_id,),
	)
	daily_outline = daily_blog.artifacts.DailyOutline.create(
		packet.report_date, (packet,), ("vosslab/recovery",),
		"Daily outline <!-- evidence: " + item.evidence_id + " -->", (item.evidence_id,),
	)
	ranking_hash = "a" * 64
	promoted = daily_blog.daily_outline_workflow.PromotedRanking(
		"ranking-1", ranking_hash, (story.content_hash,),
		((story.content_hash, 100),), "Grounded ranking rationale.", ("review-1",),
	)
	sources = daily_blog.stage6.Stage6RecoverySources(
		(story,), (repository_outline,), (packet,), promoted, story.artifact_id,
	)
	return daily_blog.stage6.Stage6Input(
		str(root), str(root / "owner" / "daily_blog" / packet.report_date / "post.md"), sources,
		daily_blog.stage6.build_stage6_publication_surface(
			daily_outline, (story,), (packet,), _CONTEXT_LIMITS,
		),
	)


def _config(root: pathlib.Path) -> daily_blog.config.DailyBlogConfig:
	"""Return a disposable configuration with a shared route cache root."""
	route = daily_blog.editorial_stage_config.RoleRoute(
		"writer", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE,
	)
	return daily_blog.config.DailyBlogConfig(
		"settings.yaml", str(root), "owner", "America/Chicago", str(root),
		str(root / "mirrors"), (route,), route, {}, {}, {},
		daily_blog.config.EditorialReliabilityConfig(2, 1, 1, 32),
	)


def test_stage6_exhaustion_records_real_writer_failure_provenance(
	tmp_path: pathlib.Path,
) -> None:
	"""A primary route outage remains typed degradation with its actual writer facts."""
	value = _input(tmp_path)

	class Runner:
		def run(
			self,
			_route: daily_blog.editorial_stage_config.RoleRoute,
			_prompt: str,
			_directory: str,
		) -> str:
			raise daily_blog.routes.EditorialRouteTimeout("fixture")

	result = daily_blog.stage6.run_stage6(
		value, "primary-outage", _config(tmp_path),
		daily_blog.agents.RouteBudget(32, 1), Runner(),
	)

	assert result.artifact is None and result.promotion.reason == "route_unavailable"
	assert result.generation.candidates and all(
		not candidate.result.ok for candidate in result.generation.candidates
	)

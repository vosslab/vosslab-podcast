"""Permanent offline tests for the typed Stage 6 complete-post boundary."""

# Standard Library
import dataclasses
from pathlib import Path
import types

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.config
import daily_blog.editorial_stage_config
import daily_blog.editorial
import daily_blog.routes
import daily_blog.repository_contracts
import daily_blog.schema
import daily_blog.stage6
import daily_blog.daily_outline_workflow
import daily_blog.io_utils


_CONTEXT_LIMITS = {
	"commit_subject_chars": 120,
	"context_chars": 60000,
	"excerpt_chars": 1000,
}


#============================================
def packet() -> daily_blog.schema.EvidencePacket:
	"""Return one exact authoritative packet for the Stage 6 contract."""
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/project", "a" * 40, "docs/CHANGELOG.md", "b" * 40,
		"Grounded change.", "git show",
	)
	activity = daily_blog.schema.RepositoryActivity(
		"vosslab/project", "https://github.com/vosslab/project", "/fixture/project",
		"a" * 40, (), (), (), False,
		(daily_blog.repository_contracts.RepositoryLifecycleEvent(
			"repository_created", "2020-01-01T00:00:00Z", False, "fixture",
		),),
	)
	return daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [activity], [item],
	)


#============================================
def complete_post(
	value: daily_blog.stage6.Stage6Input, suffix: str,
) -> daily_blog.artifacts.CompletePost:
	"""Build an exact eligible incumbent or expected selected post."""
	return daily_blog.artifacts.CompletePost.create(
		value.report_date, value.packets, value.daily_outline.repositories, post(value, suffix),
		value.daily_outline.evidence_ids, value.report_date, value.output_path,
	)


#============================================
def recovery_sources(
	story: daily_blog.artifacts.RepoStory,
	source: daily_blog.schema.EvidencePacket,
) -> daily_blog.stage6.Stage6RecoverySources:
	"""Return the reviewed repository material required by lower Stage 6 rungs."""
	evidence_id = source.items[0].evidence_id
	repository_outline = daily_blog.artifacts.RepoOutline.create(
		source.report_date, (source,), story.repositories[0],
		"Outline <!-- evidence: " + evidence_id + " -->", (evidence_id,),
	)
	ranking_hash = "a" * 64
	promoted = daily_blog.daily_outline_workflow.PromotedRanking(
		"ranking-1", ranking_hash, (story.content_hash,), ((story.content_hash, 100),),
		"Grounded ranking rationale.", ("review-1",),
	)
	return daily_blog.stage6.Stage6RecoverySources(
		(story,), (repository_outline,), (source,), promoted, story.artifact_id,
	)


#============================================
def input_value(tmp_path: Path) -> daily_blog.stage6.Stage6Input:
	"""Build the only permanent Stage 6 upstream artifact boundary."""
	source = packet()
	evidence_id = source.items[0].evidence_id
	story = daily_blog.artifacts.RepoStory.create(
		source.report_date, (source,), "vosslab/project",
		"Story <!-- evidence: " + evidence_id + " -->", (evidence_id,),
	)
	outline = daily_blog.artifacts.DailyOutline.create(
		source.report_date, (source,), ("vosslab/project",),
		"Outline <!-- evidence: " + evidence_id + " -->", (evidence_id,),
	)
	return daily_blog.stage6.Stage6Input(
		str(tmp_path), str(tmp_path / "2026-08-23" / "post.md"),
		recovery_sources(story, source), daily_blog.stage6.build_stage6_publication_surface(
			outline, (story,), (source,), _CONTEXT_LIMITS,
		),
	)


#============================================
def two_repository_input(tmp_path: Path) -> tuple[daily_blog.stage6.Stage6Input, str]:
	"""Build a valid broad Stage-6 ceiling with a separately cited repository."""
	first = packet()
	second_item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/second", "c" * 40, "docs/CHANGELOG.md", "d" * 40,
		"Second grounded change.", "git show",
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
	first_id, second_id = first.items[0].evidence_id, second.items[0].evidence_id
	stories = tuple(sorted((
		daily_blog.artifacts.RepoStory.create(
			first.report_date, (first,), "vosslab/project",
			"Story <!-- evidence: " + first_id + " -->", (first_id,),
		),
		daily_blog.artifacts.RepoStory.create(
			second.report_date, (second,), "vosslab/second",
			"Story <!-- evidence: " + second_id + " -->", (second_id,),
		),
	), key=lambda item: item.artifact_id))
	outline = daily_blog.artifacts.DailyOutline.create(
		first.report_date, packets, ("vosslab/project", "vosslab/second"),
		"Outline <!-- evidence: " + first_id + " --> <!-- evidence: " + second_id + " -->",
		tuple(sorted((first_id, second_id))),
	)
	repo_outlines = tuple(sorted((
		daily_blog.artifacts.RepoOutline.create(
			first.report_date, (first,), "vosslab/project",
			"Outline <!-- evidence: " + first_id + " -->", (first_id,),
		),
		daily_blog.artifacts.RepoOutline.create(
			second.report_date, (second,), "vosslab/second",
			"Outline <!-- evidence: " + second_id + " -->", (second_id,),
		),
	), key=lambda item: item.artifact_id))
	story_ids = tuple(sorted(item.content_hash for item in stories))
	ranking_hash = "a" * 64
	ranking = daily_blog.daily_outline_workflow.PromotedRanking(
		"ranking-2", ranking_hash, story_ids,
		tuple((item, 100) for item in story_ids), "Grounded ranking rationale.", ("review-2",),
	)
	recovery = daily_blog.stage6.Stage6RecoverySources(
		stories, repo_outlines, packets, ranking, min(stories, key=lambda item: item.artifact_id).artifact_id,
	)
	return daily_blog.stage6.Stage6Input(
		str(tmp_path), str(tmp_path / first.report_date / "post.md"), recovery,
		daily_blog.stage6.build_stage6_publication_surface(
			outline, stories, packets, _CONTEXT_LIMITS,
		),
	), first_id


#============================================
def config(tmp_path: Path, routes: int = 2) -> daily_blog.config.DailyBlogConfig:
	"""Return a small exact route configuration with capacity for balanced review."""
	reliability = daily_blog.config.EditorialReliabilityConfig(2, 1, 2, 0)
	complete_post = daily_blog.editorial_stage_config.CompletePostConfig(
		writer_count=2, editor_count=2, reviewer_count=1, maximum_parallel_calls=2,
		route_retry_attempts=0,
		writer_route=daily_blog.editorial_stage_config.RoleRoute("writer", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE),
		editor_route=daily_blog.editorial_stage_config.RoleRoute("editor", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE),
		reviewer_route=daily_blog.editorial_stage_config.RoleRoute("referee", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE),
	)
	return daily_blog.config.DailyBlogConfig(
		"settings", str(tmp_path), "owner", "America/Chicago", str(tmp_path), str(tmp_path / "mirrors"),
		tuple(daily_blog.editorial_stage_config.RoleRoute(
			"author-" + str(index), daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE,
		) for index in range(routes)), daily_blog.editorial_stage_config.RoleRoute(
			"referee", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE,
		),
		{}, {}, {"author_chars": 72000, "referee_chars": 88000}, reliability,
		complete_post=complete_post,
	)


#============================================
def post(value: daily_blog.stage6.Stage6Input, suffix: str = "one") -> str:
	"""Return one complete policy-valid writer response for offline promotion tests."""
	evidence_id = value.daily_outline.evidence_ids[0]
	introduction = (
		"I connected [vosslab/project](https://github.com/vosslab/project) to a small design "
		"decision and enjoyed seeing the boundary become clear. "
	) * 4
	detail = (
		"I followed the implementation through its useful constraint, the behavior it changed, "
		"and the next question worth testing with the grounded evidence in view. "
	) * 18
	return (
		"# " + suffix + "\n\n" + introduction.strip() + "<!-- evidence: " + evidence_id
		+ " -->\n\n<!-- more -->\n\n## The useful boundary\n\n" + detail.strip()
		+ "<!-- evidence: " + evidence_id + " -->\n\n## Project coverage\n\n"
		+ "I recorded vosslab/project in the evidence packet. <!-- evidence: " + evidence_id + " -->\n"
	)


#============================================
def test_stage6_post_scope_contracts_to_its_cited_allowed_repository(tmp_path: Path) -> None:
	"""A broad Stage-5 ceiling cannot inflate a writer post's stored scope."""
	value, evidence_id = two_repository_input(tmp_path)
	candidate = daily_blog.stage6._post(
		value, types.SimpleNamespace(
			text="# Contracted\n\nGrounded. <!-- evidence: " + evidence_id + " -->\n",
		),
	)

	assert candidate.repositories == ("vosslab/project",)
	assert daily_blog.artifacts.evaluate_eligibility(
		candidate, value.packets, (value.output_root,), value.daily_outline.repositories,
	).eligible


#============================================
#============================================
def test_stage6_partial_writer_failure_preserves_eligible_complete_post(tmp_path: Path) -> None:
	"""One author route failing leaves its independently generated post promoted."""
	value = input_value(tmp_path)
	class Runner:
		def run(self, route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, _directory: str) -> str:
			if route.name == "writer" and "-writer-2" in prompt:
				raise daily_blog.routes.EditorialRouteTimeout("offline")
			return post(value)
	result = daily_blog.stage6.run_stage6(
		value, "partial", config(tmp_path), daily_blog.agents.RouteBudget(2), Runner(),
	)
	assert type(result.artifact) is daily_blog.artifacts.CompletePost
	assert any(candidate.failure == "timeout" for candidate in result.generation.candidates)


#============================================
def test_stage6_balanced_reviewer_loss_preserves_a_peer(tmp_path: Path) -> None:
	"""Two generated posts survive total referee loss through generic promotion."""
	value = input_value(tmp_path)
	class Runner:
		def run(self, route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			if route.name == "referee":
				raise daily_blog.routes.EditorialRouteTimeout("offline")
			return post(value, route.name)
	result = daily_blog.stage6.run_stage6(
		value, "review-loss", config(tmp_path), daily_blog.agents.RouteBudget(2), Runner(),
	)
	assert type(result.artifact) is daily_blog.artifacts.CompletePost


#============================================
def test_stage6_reviewer_prompt_overflow_preserves_generated_peer(tmp_path: Path) -> None:
	"""An unavailable optional review wave cannot discard usable generated posts."""
	value = input_value(tmp_path)
	base = config(tmp_path)
	limits = dict(base.complete_post.prompt_limits)
	limits["reviewer_chars"] = 1
	limited = dataclasses.replace(base, complete_post=dataclasses.replace(
		base.complete_post, prompt_limits=limits,
	))

	class Runner:
		def run(
			self, route: daily_blog.editorial_stage_config.RoleRoute,
			_prompt: str, _directory: str,
		) -> str:
			return post(value, route.name)

	result = daily_blog.stage6.run_stage6(
		value, "review-overflow", limited, daily_blog.agents.RouteBudget(2), Runner(),
	)

	assert type(result.artifact) is daily_blog.artifacts.CompletePost
	assert not result.review.work
	assert all(
		item.role != "reviewer"
		for observation in result.primary_observations
		for item in observation.materialization.attempts
	)


#============================================
def test_stage6_editor_failure_preserves_grounded_peer_and_records_degradation(tmp_path: Path) -> None:
	"""One editor failure cannot discard independently eligible whole-post work."""
	value = input_value(tmp_path)
	class Runner:
		failed_editor = False

		def run(self, route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			if route.name == "editor" and not self.failed_editor:
				self.failed_editor = True
				raise daily_blog.routes.EditorialRouteTimeout("offline")
			return post(value, "grounded-peer")
	result = daily_blog.stage6.run_stage6(
		value, "editor-loss", config(tmp_path), daily_blog.agents.RouteBudget(2), Runner(),
	)
	assert type(result.artifact) is daily_blog.artifacts.CompletePost and result.artifact == complete_post(
		value, "grounded-peer",
	)
	assert result.reliability.outcome == "degraded" and "timeout" in result.reliability.reasons


#============================================
def test_stage6_preserves_a_separate_eligible_incumbent(tmp_path: Path) -> None:
	"""An eligible incumbent remains a same-rung candidate when writers all fail."""
	value = input_value(tmp_path)
	incumbent = daily_blog.artifacts.CompletePost.create(
		value.report_date, value.packets, value.daily_outline.repositories, post(value, "incumbent"),
		value.daily_outline.evidence_ids, value.report_date, value.output_path,
	)
	class Runner:
		def run(self, _route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			raise daily_blog.routes.EditorialRouteTimeout("offline")
	result = daily_blog.stage6.run_stage6(
		value, "incumbent", config(tmp_path), daily_blog.agents.RouteBudget(2), Runner(),
		incumbent=incumbent,
	)
	assert isinstance(result.promotion, daily_blog.artifacts.PreservedArtifact)
	assert result.artifact == incumbent


#============================================
def test_stage6_editor_can_improve_an_incumbent_after_total_writer_loss(tmp_path: Path) -> None:
	"""An editor receives the eligible incumbent when every writer route fails."""
	value = input_value(tmp_path)
	incumbent = complete_post(value, "incumbent")
	class Runner:
		reviewer_winners = iter(("A", "B"))

		def run(self, route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			if route.name == "writer":
				raise daily_blog.routes.EditorialRouteTimeout("offline")
			if route.name == "editor":
				return post(value, "editor-improvement")
			winner = next(self.reviewer_winners)
			return '{"winner":"' + winner + '","reason":"grounded","evidence_quality":"high","confidence":1}'
	result = daily_blog.stage6.run_stage6(
		value, "incumbent-editor", config(tmp_path), daily_blog.agents.RouteBudget(2), Runner(),
		incumbent=incumbent,
	)
	assert result.artifact in {
		incumbent, complete_post(value, "editor-improvement"),
	}

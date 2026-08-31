"""Permanent offline tests for the typed Stage 6 complete-post boundary."""

# Standard Library
import json
from pathlib import Path
import types

# PIP3 modules
import pytest

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
	payload = {
		"candidate_id": "ranking-1", "accepted_review_ids": ["review-1"],
		"ranking_content_sha256": ranking_hash,
	}
	promoted = daily_blog.daily_outline_workflow.PromotedRanking(
		"ranking-promotion-" + daily_blog.io_utils.sha256_text(
			json.dumps(payload, sort_keys=True, separators=(",", ":")),
		)[:24],
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
	payload = {
		"candidate_id": "ranking-2", "accepted_review_ids": ["review-2"],
		"ranking_content_sha256": ranking_hash,
	}
	ranking = daily_blog.daily_outline_workflow.PromotedRanking(
		"ranking-promotion-" + daily_blog.io_utils.sha256_text(
			json.dumps(payload, sort_keys=True, separators=(",", ":")),
		)[:24], "ranking-2", ranking_hash, story_ids,
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
	reliability = daily_blog.config.EditorialReliabilityConfig(2, 1, 2, 4, 0)
	complete_post = daily_blog.editorial_stage_config.CompletePostConfig(
		writer_count=2, editor_count=2, reviewer_count=1, maximum_parallel_calls=2,
		max_route_calls=44, route_retry_attempts=0,
		writer_route=daily_blog.editorial_stage_config.RoleRoute("writer", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE),
		editor_route=daily_blog.editorial_stage_config.RoleRoute("editor", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE),
		reviewer_route=daily_blog.editorial_stage_config.RoleRoute("referee", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE),
	)
	return daily_blog.config.DailyBlogConfig(
		"settings", str(tmp_path), "owner", "America/Chicago", str(tmp_path), str(tmp_path / "mirrors"),
		(), (), tuple(daily_blog.editorial_stage_config.RoleRoute(
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
		value, "partial", config(tmp_path), daily_blog.agents.RouteBudget(50, 2), Runner(),
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
		value, "review-loss", config(tmp_path), daily_blog.agents.RouteBudget(50, 2), Runner(),
	)
	assert type(result.artifact) is daily_blog.artifacts.CompletePost


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
		value, "editor-loss", config(tmp_path), daily_blog.agents.RouteBudget(50, 2), Runner(),
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
		value, "incumbent", config(tmp_path), daily_blog.agents.RouteBudget(50, 2), Runner(),
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
		value, "incumbent-editor", config(tmp_path), daily_blog.agents.RouteBudget(50, 2), Runner(),
		incumbent=incumbent,
	)
	assert result.artifact in {
		incumbent, complete_post(value, "editor-improvement"),
	}


#============================================
def test_stage6_no_eligible_writer_response_is_a_typed_no_artifact(tmp_path: Path) -> None:
	"""Ineligible route responses are a diagnosed editorial failure, never assembled prose."""
	value = input_value(tmp_path)
	class Runner:
		def run(self, _route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			return "# ungrounded\n"
	result = daily_blog.stage6.run_stage6(
		value, "none", config(tmp_path), daily_blog.agents.RouteBudget(50, 2), Runner(),
	)
	assert isinstance(result.promotion, daily_blog.artifacts.NoArtifact)
	assert result.promotion.reason == "no_eligible_generation"


#============================================
def test_stage6_policy_invalid_writer_degrades_while_valid_peer_is_promoted(tmp_path: Path) -> None:
	"""A structurally grounded but uncited writer peer cannot enter editorial voting."""
	value = input_value(tmp_path)
	class Runner:
		def __init__(self) -> None:
			self.responses = iter((
				post(value, "invalid") + "\n\n" + "A deliberately uncited editorial thought.\n\n" * 4,
				post(value, "valid-peer"),
				post(value, "valid-peer"),
				post(value, "valid-peer"),
				'{"winner":"A","reason":"grounded","evidence_quality":"high","confidence":1}',
				'{"winner":"A","reason":"grounded","evidence_quality":"high","confidence":1}',
				'{"winner":"A","reason":"grounded","evidence_quality":"high","confidence":1}',
			))

		def run(self, _route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			return next(self.responses)
	result = daily_blog.stage6.run_stage6(
		value, "policy-peer", config(tmp_path), daily_blog.agents.RouteBudget(50, 2), Runner(),
	)
	assert result.artifact.content.startswith("---\ndate: 2026-08-23\n---\n# valid-peer")
	writer_counts = result.step_reliability[0].rejection_counts
	assert writer_counts and result.reliability.rejection_counts == writer_counts


#============================================
def test_stage6_editors_refine_grounded_writer_drafts_that_miss_body_policy(
	tmp_path: Path,
) -> None:
	"""Policy-invalid grounded work reaches editors but cannot enter promotion unchanged."""
	value = input_value(tmp_path)
	invalid = post(value, "draft") + "\n\n" + "An intentionally uncited afterword.\n\n" * 4
	class Runner:
		editor_calls = 0

		def run(
			self, route: daily_blog.editorial_stage_config.RoleRoute,
			_prompt: str, _directory: str,
		) -> str:
			if route.name == "writer":
				return invalid
			if route.name == "editor":
				self.editor_calls += 1
				return post(value, "editor-refinement")
			return '{"winner":"A","reason":"grounded","evidence_quality":"high","confidence":1}'

	runner = Runner()
	result = daily_blog.stage6.run_stage6(
		value, "policy-editor", config(tmp_path),
		daily_blog.agents.RouteBudget(50, 2), runner,
	)
	assert runner.editor_calls > 0
	assert result.editing.eligible and result.artifact in result.editing.eligible
	assert all(
		candidate.eligibility is not None
		and "publication_policy_mismatch" in candidate.eligibility.reasons
		and set(candidate.eligibility.reasons) != {"publication_policy_mismatch"}
		for candidate in result.generation.candidates
	)


#============================================
#============================================
def test_stage6_propagates_non_referee_parser_defects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""Only bounded verdict syntax errors are repairable; implementation defects remain faults."""
	value = input_value(tmp_path)
	def broken_parser(_text: str, _allowed: set[str]) -> dict:
		raise RuntimeError("parser defect")
	monkeypatch.setattr(daily_blog.editorial, "parse_referee_verdict", broken_parser)
	class Runner:
		def run(self, route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			if route.name in {"writer", "editor"}:
				return post(value, route.name)
			return '{"winner":"A","reason":"grounded","evidence_quality":"high","confidence":1}'
	with pytest.raises(RuntimeError, match="parser defect"):
		daily_blog.stage6.run_stage6(
			value, "parser-defect", config(tmp_path), daily_blog.agents.RouteBudget(50, 2), Runner(),
		)

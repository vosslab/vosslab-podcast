"""Offline behavioral coverage for pure Stage 5 ranking and daily outlines."""

# Standard Library
import dataclasses
import json
import threading

# PIP3 modules
import pytest

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.editorial_stage_config
import daily_blog.daily_outline_prompts
import daily_blog.daily_outline_workflow
import daily_blog.projection
import daily_blog.repository_contracts
import daily_blog.routes
import daily_blog.schema
import daily_blog.stage6


def _activity(repository: str, marker: str) -> daily_blog.schema.RepositoryActivity:
	"""Return one repository activity record for survivor context projection."""
	commit = daily_blog.schema.CommitActivity(
		marker * 40, (), "Maker", "maker@example.com", "2026-08-29T12:00:00Z",
		"2026-08-29T12:00:00Z", "Grounded work.",
	)
	return daily_blog.schema.RepositoryActivity(
		repository, "https://github.com/" + repository, "/cache/" + marker, marker * 40,
		(commit,), (daily_blog.schema.RevisionRange("", marker * 40),), (marker * 40,), False,
		(daily_blog.repository_contracts.RepositoryLifecycleEvent(
			"repository_created", "2020-01-01T00:00:00Z", False, "github_owner_roster",
		),),
	)


def _context(packets: tuple[daily_blog.schema.EvidencePacket, ...]) -> daily_blog.schema.BoundedEvidenceContext:
	"""Build the production Stage 5 evidence frame from local survivors."""
	limits = {"context_chars": 60000, "excerpt_chars": 600, "commit_subject_chars": 120}
	return daily_blog.projection.build_bounded_evidence_context(packets, limits, limits["context_chars"])


def packets() -> tuple[daily_blog.schema.EvidencePacket, ...]:
	"""Return two authoritative, repository-isolated evidence packets."""
	values = []
	for index, repository in enumerate(("vosslab/alpha", "vosslab/beta")):
		item = daily_blog.schema.EvidenceItem.create("dated_changelog", repository, chr(97 + index) * 40,
			"CHANGELOG.md", chr(99 + index) * 40, repository + " change.", "git show")
		values.append(daily_blog.schema.EvidencePacket.create(
			"2026-08-29", "America/Chicago", True, {}, [], [_activity(repository, chr(97 + index))], [item],
		))
	return tuple(values)


def value(tmp_path: object) -> daily_blog.daily_outline_workflow.DailyOutlineInput:
	"""Construct aggregate Stage 5 input from repository-local artifact packets."""
	source = packets()
	stories = tuple(daily_blog.artifacts.RepoStory.create(source[0].report_date, (packet,), packet.items[0].repository,
		"# Story\n\n" + packet.items[0].repository + " <!-- evidence: " + packet.items[0].evidence_id + " -->\n",
		(packet.items[0].evidence_id,)) for packet in source)
	outlines = tuple(daily_blog.artifacts.RepoOutline.create(source[0].report_date, (packet,), packet.items[0].repository,
		"# Repository outline\n\n" + packet.items[0].repository + " <!-- evidence: " + packet.items[0].evidence_id + " -->\n",
		(packet.items[0].evidence_id,)) for packet in source)
	return daily_blog.daily_outline_workflow.DailyOutlineInput(
		stories, outlines, source, _context(source), str(tmp_path),
	)


def configuration() -> daily_blog.editorial_stage_config.DailyOutlineConfig:
	"""Use the smallest complete independent Stage 5 route pools."""
	return daily_blog.editorial_stage_config.DailyOutlineConfig(ranker_count=2, outline_writer_count=2,
		reviewer_count=1, maximum_parallel_calls=2, route_retry_attempts=0)


def ranking(
	source: daily_blog.daily_outline_workflow.DailyOutlineInput, rationale: str = "grounded priority",
) -> str:
	"""Return a complete structured ranking for all supplied stories."""
	ids = list(source.story_ranking_aliases.aliases)
	return json.dumps({"artifact_ids": ids, "scores": {item: 70 for item in ids}, "rationale": rationale})


def outline(source: daily_blog.daily_outline_workflow.DailyOutlineInput, title: str, repositories: tuple[str, ...] | None = None) -> str:
	"""Return one whole authored outline with explicit evidence-grounded scope."""
	chosen = repositories or source.repositories
	evidence = [packet.items[0].evidence_id for packet in source.packets if packet.items[0].repository in chosen]
	return "<!-- daily-outline-scope: " + json.dumps(list(chosen)) + " -->\n# " + title + "\n\n" + "\n".join("- " + item for item in chosen) + "\n\n<!-- evidence: " + ", ".join(evidence) + " -->\n"


def verdict(winner: str) -> str:
	"""Return one strict anonymous comparison result."""
	return json.dumps({"winner": winner, "reason": "grounded", "evidence_quality": "high", "confidence": 1})


def ranking_verdict(decision: str = "ACCEPT", score: int = 80) -> str:
	"""Return one strict ranking-promotion verdict."""
	return json.dumps({"decision": decision, "score": score, "reason": "grounded"})


class Runner:
	"""Thread-safe fake retaining all prompts and providing role-specific queues."""

	def __init__(self, responses: dict[str, list[object]]) -> None:
		self.responses = responses
		self.prompts: list[tuple[str, str]] = []
		self.lock = threading.Lock()

	def run(self, route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, working_directory: str) -> str:
		with self.lock:
			self.prompts.append((route.name, prompt))
			response = self.responses[route.name].pop(0)
		if isinstance(response, BaseException):
			raise response
		return response


def run(source: daily_blog.daily_outline_workflow.DailyOutlineInput, runner: Runner, **kwargs: object) -> daily_blog.daily_outline_workflow.DailyOutlineResult:
	"""Run under one externally supplied budget and optional shared cache hooks."""
	return daily_blog.daily_outline_workflow.run_daily_outline(source, configuration(), daily_blog.agents.RouteBudget(100, 4), runner, **kwargs)


def test_one_ranker_and_writer_failure_degrade_but_promote_surviving_whole_outline(tmp_path: object) -> None:
	"""Partial mechanism loss does not trigger Python Markdown assembly or discard a survivor."""
	source = value(tmp_path)
	runner = Runner({"daily_outline_ranking": [daily_blog.routes.EditorialRouteProcessError("down"), ranking(source)], "daily_outline_writer": [daily_blog.routes.EditorialRouteProcessError("down"), outline(source, "survivor")], "daily_outline_reviewer": [ranking_verdict()]})
	result = run(source, runner)

	assert type(result.artifact) is daily_blog.artifacts.DailyOutline
	assert isinstance(result.promotion, daily_blog.artifacts.DegradedPromotion)
	assert any(item.outcome == "degraded" for item in result.reliability)

def test_total_ranking_or_writer_loss_returns_typed_no_artifact(tmp_path: object) -> None:
	"""A total subjective mechanism loss stays a diagnosable typed outcome."""
	source = value(tmp_path)
	ranker_loss = Runner({"daily_outline_ranking": [daily_blog.routes.EditorialRouteProcessError("down")] * 4, "daily_outline_writer": [], "daily_outline_reviewer": []})
	assert isinstance(run(source, ranker_loss).promotion, daily_blog.artifacts.NoArtifact)
	writer_loss = Runner({"daily_outline_ranking": [ranking(source), ranking(source)], "daily_outline_writer": [daily_blog.routes.EditorialRouteProcessError("down"), daily_blog.routes.EditorialRouteProcessError("down")], "daily_outline_reviewer": [ranking_verdict(), ranking_verdict()]})
	assert isinstance(run(source, writer_loss).promotion, daily_blog.artifacts.NoArtifact)


def test_input_rejects_misaligned_scope_before_any_route(tmp_path: object) -> None:
	"""One story and outline per same repository identity is a strict boundary."""
	source = value(tmp_path)
	with pytest.raises(RuntimeError, match="identities cannot repeat"):
		daily_blog.daily_outline_workflow.DailyOutlineInput(source.repo_stories, (source.repo_outlines[0], source.repo_outlines[0]), source.packets, source.evidence_context, source.working_directory)


def test_model_story_aliases_are_exact_and_durable_ranking_stays_canonical(tmp_path: object) -> None:
	"""Stage 5 routes see aliases, while durable promotion records retain canonical hashes."""
	source = value(tmp_path)
	aliases = source.story_ranking_aliases
	story_context = source.render_stories()
	outline_context = source.render_outlines()
	assert aliases.aliases == ("story-01", "story-02")
	assert all(story.content_hash not in story_context for story in source.repo_stories)
	assert all(outline.content_hash not in outline_context for outline in source.repo_outlines)
	parsed = daily_blog.daily_outline_workflow._parse_model_ranking(
		ranking(source), aliases,
	)
	assert parsed["artifact_ids"] == aliases.content_hashes
	with pytest.raises(daily_blog.daily_outline_prompts.DailyOutlineRankingParseError):
		daily_blog.daily_outline_workflow._parse_model_ranking(json.dumps({
			"artifact_ids": [source.repo_stories[0].content_hash, aliases.aliases[1]],
			"scores": {source.repo_stories[0].content_hash: 90, aliases.aliases[1]: 80},
			"rationale": "grounded priority",
		}), aliases)
	with pytest.raises(daily_blog.daily_outline_prompts.DailyOutlineRankingParseError):
		daily_blog.daily_outline_workflow._parse_model_ranking(
			'{"artifact_ids":["story-01","story-02"],"scores":{"story-01":90,'
			'"story-02":80},"rationale":"one","rationale":"two"}', aliases,
		)


def test_stage5_model_prompts_use_aliases_while_stage6_sources_stay_canonical(tmp_path: object) -> None:
	"""Model-only Stage 5 aliases never replace the canonical recovery provenance."""
	source = value(tmp_path)
	runner = Runner({
		"daily_outline_ranking": [ranking(source), ranking(source)],
		"daily_outline_writer": [outline(source, "one"), outline(source, "two")],
		"daily_outline_reviewer": [ranking_verdict(), ranking_verdict(), verdict("A"), verdict("A")],
	})
	result = run(source, runner)
	assert result.promoted_ranking is not None
	prompt_groups = (
		[item for role, item in runner.prompts if role == "daily_outline_ranking"],
		[item for role, item in runner.prompts if role == "daily_outline_writer"],
		[item for role, item in runner.prompts if role == "daily_outline_reviewer" and "STORY_RANKING_REVIEW" in item],
	)
	for prompts in prompt_groups:
		assert prompts
		for prompt in prompts:
			assert all(alias in prompt for alias in source.story_ranking_aliases.aliases)
			assert all(story.content_hash not in prompt for story in source.repo_stories)
			assert all(outline.content_hash not in prompt for outline in source.repo_outlines)
	strongest = min(source.repo_stories, key=lambda item: item.artifact_id)
	recovery_sources = daily_blog.stage6.Stage6RecoverySources(
		source.repo_stories, source.repo_outlines, source.packets,
		result.promoted_ranking, strongest.artifact_id,
	)
	assert set(dict(recovery_sources.promoted_ranking.scores)) == {
		item.content_hash for item in source.repo_stories
	}


def test_partial_ranking_review_failure_keeps_a_reviewed_candidate(tmp_path: object) -> None:
	"""A route loss in one ranking review does not discard another reviewed ranking."""
	source = value(tmp_path)
	runner = Runner({"daily_outline_ranking": [ranking(source), ranking(source)],
		"daily_outline_writer": [outline(source, "one"), outline(source, "two")],
		"daily_outline_reviewer": [daily_blog.routes.EditorialRouteProcessError("down"), ranking_verdict(), verdict("A"), verdict("B")]})
	result = run(source, runner)

	assert result.artifact is not None
	assert result.promoted_ranking is not None
	assert any(item.outcome == "degraded" for item in result.reliability)


def test_ranking_fallback_retains_primary_observations_and_can_promote(tmp_path: object) -> None:
	"""Only a zero-candidate ranker wave earns one fresh independent fallback wave."""
	source = value(tmp_path)
	runner = Runner({
		"daily_outline_ranking": ["not json", "also not json", ranking(source), ranking(source)],
		"daily_outline_writer": [outline(source, "one"), outline(source, "two")],
		"daily_outline_reviewer": [ranking_verdict(), ranking_verdict(), verdict("A"), verdict("A")],
	})
	result = run(source, runner)

	assert result.promoted_ranking is not None
	assert any(item.failure == "invalid_json" for item in result.rankings)
	assert any(
		item.request.role == "ranker_fallback" and item.candidate is not None
		for item in result.rankings
	)
	ranking_summary = result.reliability[0]
	assert ranking_summary.outcome == "degraded"
	assert "ranking_fallback_used" in ranking_summary.reasons


def test_ranking_parser_category_is_safe_and_long_valid_rationale_promotes(tmp_path: object) -> None:
	"""Stage reliability retains parser categories without retaining model response text."""
	source = value(tmp_path)
	runner = Runner({
		"daily_outline_ranking": [
			'{"unexpected":true}', ranking(source, "grounded " * 120),
		],
		"daily_outline_writer": [outline(source, "one"), outline(source, "two")],
		"daily_outline_reviewer": [ranking_verdict(), verdict("A"), verdict("A")],
	})
	result = run(source, runner)

	assert result.promoted_ranking is not None
	assert any(item.failure == "invalid_fields" for item in result.rankings)
	assert "invalid_fields" in result.reliability[0].reasons
	assert all("unexpected" not in item.failure for item in result.rankings if item.failure)


def test_valid_primary_ranking_does_not_run_the_fallback_wave(tmp_path: object) -> None:
	"""A parsed primary candidate advances directly without a duplicate ranking wave."""
	source = value(tmp_path)
	runner = Runner({
		"daily_outline_ranking": [ranking(source), ranking(source)],
		"daily_outline_writer": [outline(source, "one"), outline(source, "two")],
		"daily_outline_reviewer": [ranking_verdict(), ranking_verdict(), verdict("A"), verdict("A")],
	})
	result = run(source, runner)

	assert result.promoted_ranking is not None
	assert not any(item.request.role == "ranker_fallback" for item in result.rankings)
	assert "ranking_fallback_used" not in result.reliability[0].reasons


def test_all_six_invalid_rankers_remain_no_eligible_generation(tmp_path: object) -> None:
	"""A fallback is editorial recovery, not a way to manufacture an invalid ranking."""
	source = value(tmp_path)
	config = daily_blog.editorial_stage_config.DailyOutlineConfig(
		ranker_count=3, outline_writer_count=2, reviewer_count=1,
		maximum_parallel_calls=3, route_retry_attempts=0,
	)
	runner = Runner({
		"daily_outline_ranking": ["not json"] * 6,
		"daily_outline_writer": [], "daily_outline_reviewer": [],
	})
	result = daily_blog.daily_outline_workflow.run_daily_outline(
		source, config, daily_blog.agents.RouteBudget(100, 4), runner,
	)

	assert isinstance(result.promotion, daily_blog.artifacts.NoArtifact)
	assert result.promotion.reason == "no_eligible_generation"
	assert result.reliability[0].outcome == "degraded"
	assert "ranking_fallback_used" in result.reliability[0].reasons


def test_ranking_fallback_candidates_resume_without_a_second_fallback_egress(
	tmp_path: object,
) -> None:
	"""Only parsed fallback rankings enter cache; their retry wave then resumes exactly."""
	source = value(tmp_path)
	cache: dict[str, daily_blog.agents.AgentResult] = {}
	first = Runner({
		"daily_outline_ranking": ["not json", "still not json", ranking(source), ranking(source)],
		"daily_outline_writer": [outline(source, "one"), outline(source, "two")],
		"daily_outline_reviewer": [ranking_verdict(), ranking_verdict(), verdict("A"), verdict("A")],
	})
	first_result = run(source, first, cache_load=lambda request: cache.get(request.cache_input_hash), cache_accept=lambda request, result: cache.__setitem__(request.cache_input_hash, result))
	assert first_result.artifact is not None

	second = Runner({
		"daily_outline_ranking": ["not json", "still not json"],
		"daily_outline_writer": [], "daily_outline_reviewer": [],
	})
	second_result = run(source, second, cache_load=lambda request: (
		dataclasses.replace(cached, resumed=True)
		if (cached := cache.get(request.cache_input_hash)) is not None else None
	), cache_accept=lambda request, result: cache.__setitem__(request.cache_input_hash, result))

	assert second_result.artifact is not None
	assert not second.responses["daily_outline_ranking"]
	assert any(
		item.request.role == "ranker_fallback" and item.result.resumed
		for item in second_result.rankings
	)

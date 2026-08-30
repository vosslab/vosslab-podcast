"""Offline behavioral coverage for pure Stage 5 ranking and daily outlines."""

# Standard Library
import json
import threading

# PIP3 modules
import pytest

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.editorial_stage_config
import daily_blog.daily_outline_workflow
import daily_blog.routes
import daily_blog.schema


def packets() -> tuple[daily_blog.schema.EvidencePacket, ...]:
	"""Return two authoritative, repository-isolated evidence packets."""
	values = []
	for index, repository in enumerate(("vosslab/alpha", "vosslab/beta")):
		item = daily_blog.schema.EvidenceItem.create("dated_changelog", repository, chr(97 + index) * 40,
			"CHANGELOG.md", chr(99 + index) * 40, repository + " change.", "git show")
		values.append(daily_blog.schema.EvidencePacket.create("2026-08-29", "America/Chicago", True, {}, [], [], [item]))
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
	return daily_blog.daily_outline_workflow.DailyOutlineInput(stories, outlines, source, str(tmp_path))


def configuration() -> daily_blog.editorial_stage_config.DailyOutlineConfig:
	"""Use the smallest complete independent Stage 5 route pools."""
	return daily_blog.editorial_stage_config.DailyOutlineConfig(ranker_count=2, outline_writer_count=2,
		reviewer_count=1, maximum_parallel_calls=2, route_retry_attempts=0)


def ranking(source: daily_blog.daily_outline_workflow.DailyOutlineInput) -> str:
	"""Return a complete structured ranking for all supplied stories."""
	ids = [item.content_hash for item in source.repo_stories]
	return json.dumps({"artifact_ids": ids, "scores": {item: 70 for item in ids}, "rationale": "grounded priority"})


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
	ranker_loss = Runner({"daily_outline_ranking": [daily_blog.routes.EditorialRouteProcessError("down"), daily_blog.routes.EditorialRouteProcessError("down")], "daily_outline_writer": [], "daily_outline_reviewer": []})
	assert isinstance(run(source, ranker_loss).promotion, daily_blog.artifacts.NoArtifact)
	writer_loss = Runner({"daily_outline_ranking": [ranking(source), ranking(source)], "daily_outline_writer": [daily_blog.routes.EditorialRouteProcessError("down"), daily_blog.routes.EditorialRouteProcessError("down")], "daily_outline_reviewer": [ranking_verdict(), ranking_verdict()]})
	assert isinstance(run(source, writer_loss).promotion, daily_blog.artifacts.NoArtifact)


def test_input_rejects_misaligned_scope_before_any_route(tmp_path: object) -> None:
	"""One story and outline per same repository identity is a strict boundary."""
	source = value(tmp_path)
	with pytest.raises(RuntimeError, match="identities cannot repeat"):
		daily_blog.daily_outline_workflow.DailyOutlineInput(source.repo_stories, (source.repo_outlines[0], source.repo_outlines[0]), source.packets, source.working_directory)


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

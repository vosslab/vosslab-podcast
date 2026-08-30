"""Offline failure behavior for the pure Stage 5 editorial path."""

# Standard Library
import json
import threading

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.editorial_stage_config
import daily_blog.daily_outline_workflow
import daily_blog.routes
import daily_blog.schema


def _input(tmp_path: object) -> daily_blog.daily_outline_workflow.DailyOutlineInput:
	"""Build two inline repository inputs with one packet identity set."""
	packets = []
	for index, repository in enumerate(("vosslab/alpha", "vosslab/beta")):
		item = daily_blog.schema.EvidenceItem.create(
			"dated_changelog", repository, chr(97 + index) * 40, "CHANGELOG.md",
			chr(99 + index) * 40, repository + " changed.", "git show",
		)
		packets.append(daily_blog.schema.EvidencePacket.create(
			"2026-08-29", "America/Chicago", True, {}, [], [], [item],
		))
	packet_tuple = tuple(packets)
	stories = tuple(daily_blog.artifacts.RepoStory.create(
		"2026-08-29", (packet,), packet.items[0].repository,
		"# Story\n\n<!-- evidence: " + packet.items[0].evidence_id + " -->\n",
		(packet.items[0].evidence_id,),
	) for packet in packet_tuple)
	outlines = tuple(daily_blog.artifacts.RepoOutline.create(
		"2026-08-29", (packet,), packet.items[0].repository,
		"# Outline\n\n<!-- evidence: " + packet.items[0].evidence_id + " -->\n",
		(packet.items[0].evidence_id,),
	) for packet in packet_tuple)
	return daily_blog.daily_outline_workflow.DailyOutlineInput(
		stories, outlines, packet_tuple, str(tmp_path),
	)


def _config() -> daily_blog.editorial_stage_config.DailyOutlineConfig:
	"""Return a small explicit policy independent of application defaults."""
	return daily_blog.editorial_stage_config.DailyOutlineConfig(
		ranker_count=2, outline_writer_count=2, reviewer_count=1,
		maximum_parallel_calls=2, route_retry_attempts=0,
	)


def _ranking(source: daily_blog.daily_outline_workflow.DailyOutlineInput) -> str:
	"""Rank every supplied story, deliberately placing the first one last."""
	ids = tuple(reversed(tuple(item.content_hash for item in source.repo_stories)))
	return json.dumps({"artifact_ids": list(ids), "scores": {
		artifact_id: 60 + index for index, artifact_id in enumerate(ids)
	}, "rationale": "evidence-grounded priority"})


def _outline(source: daily_blog.daily_outline_workflow.DailyOutlineInput, title: str) -> str:
	"""Return a complete authored outline rather than assembled prose."""
	evidence = ", ".join(packet.items[0].evidence_id for packet in source.packets)
	return "<!-- daily-outline-scope: " + json.dumps(list(source.repositories)) + " -->\n# " + title + "\n\n<!-- evidence: " + evidence + " -->\n"


class _Runner:
	"""Thread-safe, role-addressed fake route boundary."""

	def __init__(self, responses: dict[str, list[object]]) -> None:
		self.responses = responses
		self.calls: list[tuple[str, str]] = []
		self._lock = threading.Lock()

	def run(self, route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, working_directory: str) -> str:
		"""Return the next role result while retaining rendered editorial context."""
		with self._lock:
			self.calls.append((route.name, prompt))
			response = self.responses[route.name].pop(0)
		if callable(response):
			response = response(prompt)
		if isinstance(response, BaseException):
			raise response
		return response


def _run(source: daily_blog.daily_outline_workflow.DailyOutlineInput, runner: _Runner, config: daily_blog.editorial_stage_config.DailyOutlineConfig | None = None) -> daily_blog.daily_outline_workflow.DailyOutlineResult:
	"""Run with an explicit external budget and no process-backed route."""
	return daily_blog.daily_outline_workflow.run_daily_outline(
		source, config or _config(), daily_blog.agents.RouteBudget(60, 4), runner,
	)


def test_total_ranking_review_loss_returns_no_artifact_before_outline_assembly(tmp_path: object) -> None:
	"""Unreviewed rankings cannot mechanically start an outline-writing path."""
	source = _input(tmp_path)
	runner = _Runner({
		"daily_outline_ranking": [_ranking(source), _ranking(source)],
		"daily_outline_writer": [],
		"daily_outline_reviewer": ["bad verdict"] * 4,
	})
	result = _run(source, runner)

	assert isinstance(result.promotion, daily_blog.artifacts.NoArtifact)


def test_stage5_reliability_is_bounded_redacted_and_does_not_block_promotion(tmp_path: object) -> None:
	"""Every injected failure and repair becomes bounded, identity-bound facts."""
	source = _input(tmp_path)
	config = daily_blog.editorial_stage_config.DailyOutlineConfig(ranker_count=2, outline_writer_count=3,
		reviewer_count=2, maximum_parallel_calls=4, route_retry_attempts=0)
	accepted_ranking = json.dumps({"decision": "ACCEPT", "score": 91, "reason": "grounded"})
	accepted_outline = json.dumps({"winner": "A", "reason": "grounded", "evidence_quality": "high", "confidence": 1})
	runner = _Runner({
		"daily_outline_ranking": [daily_blog.routes.EditorialRouteProcessError("diagnostic not retained"), _ranking(source)],
		"daily_outline_writer": [daily_blog.routes.EditorialRouteProcessError("writer diagnostic"), _outline(source, "one"), _outline(source, "two")],
		"daily_outline_reviewer": ["bad ranking verdict", accepted_ranking, accepted_ranking,
			accepted_outline, accepted_outline, accepted_outline, accepted_outline],
	})
	result = _run(source, runner, config)

	assert type(result.artifact) is daily_blog.artifacts.DailyOutline
	assert result.reliability
	assert all(item.validate() is None for item in result.reliability)
	assert all("diagnostic" not in reason for item in result.reliability for reason in item.reasons)

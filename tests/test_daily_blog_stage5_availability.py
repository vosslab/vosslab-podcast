"""Offline availability and provenance behavior for pure Stage 5 inputs."""

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
import daily_blog.daily_outline_workflow
import daily_blog.schema
def _input(tmp_path: object) -> daily_blog.daily_outline_workflow.DailyOutlineInput:
	"""Build complete inline artifact and evidence provenance."""
	packets = []
	for index, repository in enumerate(("vosslab/alpha", "vosslab/beta")):
		item = daily_blog.schema.EvidenceItem.create("dated_changelog", repository,
			chr(97 + index) * 40, "CHANGELOG.md", chr(99 + index) * 40,
			repository + " changed.", "git show")
		packets.append(daily_blog.schema.EvidencePacket.create(
			"2026-08-29", "America/Chicago", True, {}, [], [], [item]))
	packet_tuple = tuple(packets)
	stories = tuple(daily_blog.artifacts.RepoStory.create("2026-08-29", (packet,),
		packet.items[0].repository, "# Story\n<!-- evidence: " + packet.items[0].evidence_id + " -->\n",
		(packet.items[0].evidence_id,)) for packet in packet_tuple)
	outlines = tuple(daily_blog.artifacts.RepoOutline.create("2026-08-29", (packet,),
		packet.items[0].repository, "# Outline\n<!-- evidence: " + packet.items[0].evidence_id + " -->\n",
		(packet.items[0].evidence_id,)) for packet in packet_tuple)
	return daily_blog.daily_outline_workflow.DailyOutlineInput(stories, outlines, packet_tuple, str(tmp_path))


def _config() -> daily_blog.editorial_stage_config.DailyOutlineConfig:
	"""Supply a compact fixed policy suitable for offline behavioral checks."""
	return daily_blog.editorial_stage_config.DailyOutlineConfig(ranker_count=2, outline_writer_count=2,
		reviewer_count=1, maximum_parallel_calls=2, route_retry_attempts=0)


def _ranking(source: daily_blog.daily_outline_workflow.DailyOutlineInput) -> str:
	"""Return one valid complete ranking with a deliberately low final story."""
	ids = [item.content_hash for item in source.repo_stories]
	low_ranked_id = ids[0]
	ranked_ids = [item for item in ids if item != low_ranked_id] + [low_ranked_id]
	scores = {item: 90 for item in ranked_ids}
	scores[low_ranked_id] = 10
	return json.dumps({"artifact_ids": ranked_ids, "scores": scores, "rationale": "grounded"})


def _outline(source: daily_blog.daily_outline_workflow.DailyOutlineInput, repositories: tuple[str, ...], title: str = "Authored") -> str:
	"""Return a scope-declared outline with evidence exactly matching that scope."""
	evidence = ", ".join(packet.items[0].evidence_id for packet in source.packets if packet.items[0].repository in repositories)
	return "<!-- daily-outline-scope: " + json.dumps(list(repositories)) + " -->\n# " + title + "\n\n<!-- evidence: " + evidence + " -->\n"


class _Runner:
	"""Thread-safe fake that proves routing did or did not occur."""

	def __init__(self, responses: dict[str, list[object]]) -> None:
		self.responses = responses
		self.calls: list[tuple[str, str]] = []
		self._lock = threading.Lock()

	def run(self, route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, working_directory: str) -> str:
		"""Return one queued response per configured role request."""
		with self._lock:
			self.calls.append((route.name, prompt))
			response = self.responses[route.name].pop(0)
		if isinstance(response, BaseException):
			raise response
		return response


def _run(source: daily_blog.daily_outline_workflow.DailyOutlineInput, runner: _Runner, config: daily_blog.editorial_stage_config.DailyOutlineConfig | None = None, **kwargs: object) -> daily_blog.daily_outline_workflow.DailyOutlineResult:
	"""Run the public API using only the thread-safe fake boundary."""
	return daily_blog.daily_outline_workflow.run_daily_outline(source, config or _config(),
		daily_blog.agents.RouteBudget(40, 2), runner, **kwargs)


def test_input_rejects_later_story_or_outline_with_incomplete_packet_provenance(tmp_path: object) -> None:
	"""Each repository artifact must bind its own matching local evidence packet."""
	source = _input(tmp_path)
	story = source.repo_stories[1]
	outline = source.repo_outlines[1]
	wrong_packet = next(packet for packet in source.packets if packet.packet_id not in story.packet_ids)
	broken_story = dataclasses.replace(story, packet_ids=(wrong_packet.packet_id,))
	broken_outline = dataclasses.replace(outline, packet_ids=(wrong_packet.packet_id,))

	with pytest.raises(RuntimeError, match="provenance"):
		daily_blog.daily_outline_workflow.DailyOutlineInput((source.repo_stories[0], broken_story), source.repo_outlines, source.packets, source.working_directory)
	with pytest.raises(RuntimeError, match="provenance"):
		daily_blog.daily_outline_workflow.DailyOutlineInput(source.repo_stories, (source.repo_outlines[0], broken_outline), source.packets, source.working_directory)


def test_explicit_narrower_scope_preserves_sources_and_selects_only_declared_repositories(tmp_path: object) -> None:
	"""Stage 6 receives all sources plus an evidence-agreeing declared subset."""
	source = _input(tmp_path)
	narrow = (source.repositories[0],)
	runner = _Runner({
		"daily_outline_ranking": [_ranking(source), _ranking(source)],
		"daily_outline_writer": [_outline(source, narrow), _outline(source, narrow)],
		"daily_outline_reviewer": [json.dumps({"decision": "ACCEPT", "score": 90, "reason": "grounded"}), json.dumps({"decision": "ACCEPT", "score": 90, "reason": "grounded"})],
	})
	result = _run(source, runner)

	assert result.source_stories == source.repo_stories
	assert result.artifact.repositories == narrow
	assert tuple(item.repositories[0] for item in result.selected_stories) == narrow


@pytest.mark.parametrize("scope", (("unknown/repo",), ("vosslab/alpha", "vosslab/alpha")))
def test_invalid_scope_is_ineligible_while_a_valid_peer_survives(tmp_path: object, scope: tuple[str, ...]) -> None:
	"""Unknown or duplicate scope cannot be inferred into a candidate artifact."""
	source = _input(tmp_path)
	valid = (source.repositories[0],)
	runner = _Runner({
		"daily_outline_ranking": [_ranking(source), _ranking(source)],
		"daily_outline_writer": [_outline(source, scope), _outline(source, valid)],
		"daily_outline_reviewer": [json.dumps({"decision": "ACCEPT", "score": 90, "reason": "grounded"}), json.dumps({"decision": "ACCEPT", "score": 90, "reason": "grounded"})],
	})
	result = _run(source, runner)

	assert type(result.artifact) is daily_blog.artifacts.DailyOutline
	assert result.artifact.repositories == valid


def test_evidence_disagreeing_scope_is_ineligible_while_a_valid_peer_survives(tmp_path: object) -> None:
	"""A declared repository set must agree with cited repository evidence."""
	source = _input(tmp_path)
	valid = (source.repositories[0],)
	wrong_evidence = next(packet.items[0].evidence_id for packet in source.packets if packet.items[0].repository != valid[0])
	invalid = "<!-- daily-outline-scope: [\"" + valid[0] + "\"] -->\n# Invalid\n\n<!-- evidence: " + wrong_evidence + " -->\n"
	runner = _Runner({
		"daily_outline_ranking": [_ranking(source), _ranking(source)],
		"daily_outline_writer": [invalid, _outline(source, valid)],
		"daily_outline_reviewer": [json.dumps({"decision": "ACCEPT", "score": 90, "reason": "grounded"}), json.dumps({"decision": "ACCEPT", "score": 90, "reason": "grounded"})],
	})
	result = _run(source, runner)

	assert type(result.artifact) is daily_blog.artifacts.DailyOutline
	assert result.artifact.repositories == valid

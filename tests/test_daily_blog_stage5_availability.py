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
import daily_blog.projection
import daily_blog.repository_contracts
import daily_blog.schema
import daily_blog.stage6


def _activity(repository: str, marker: str) -> daily_blog.schema.RepositoryActivity:
	"""Return the minimal active repository shape required by evidence projection."""
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
	"""Build the same survivor-only Stage 5 evidence frame used in production."""
	limits = {"context_chars": 60000, "excerpt_chars": 600, "commit_subject_chars": 120}
	return daily_blog.projection.build_bounded_evidence_context(packets, limits, limits["context_chars"])
def _input(tmp_path: object, repository_count: int = 2, oversized: bool = False) -> daily_blog.daily_outline_workflow.DailyOutlineInput:
	"""Build complete inline artifact and evidence provenance."""
	packets = []
	for index in range(repository_count):
		repository = "vosslab/repository-" + str(index).zfill(2)
		evidence_count = 4 if oversized else 1
		items = tuple(
			daily_blog.schema.EvidenceItem.create("dated_changelog", repository,
				chr(97 + index) * 40, "CHANGELOG-" + str(item_index) + ".md",
				chr(99 + index) * 40,
				repository + " changed. " + "exact citable evidence " * (30 if oversized else 0),
				"git show")
			for item_index in range(evidence_count)
		)
		packets.append(daily_blog.schema.EvidencePacket.create(
			"2026-08-29", "America/Chicago", True, {}, [], [_activity(repository, chr(97 + index))], items))
	packet_tuple = tuple(packets)
	stories = tuple(daily_blog.artifacts.RepoStory.create("2026-08-29", (packet,),
		packet.items[0].repository, "# Story\n" + ("grounded source " * 500 if oversized else "") + "<!-- evidence: " + packet.items[0].evidence_id + " -->\n",
		(packet.items[0].evidence_id,)) for packet in packet_tuple)
	outlines = tuple(daily_blog.artifacts.RepoOutline.create("2026-08-29", (packet,),
		packet.items[0].repository, "# Outline\n" + (("\"\\\n" * 100) + "grounded plan " * 500 if oversized else "") + "<!-- evidence: " + packet.items[0].evidence_id + " -->\n",
		(packet.items[0].evidence_id,)) for packet in packet_tuple)
	return daily_blog.daily_outline_workflow.DailyOutlineInput(
		stories, outlines, packet_tuple, _context(packet_tuple), str(tmp_path),
	)


def _config() -> daily_blog.editorial_stage_config.DailyOutlineConfig:
	"""Supply a compact fixed policy suitable for offline behavioral checks."""
	return daily_blog.editorial_stage_config.DailyOutlineConfig(ranker_count=2, outline_writer_count=2,
		reviewer_count=1, maximum_parallel_calls=2, route_retry_attempts=0)


def _ranking(source: daily_blog.daily_outline_workflow.DailyOutlineInput) -> str:
	"""Return one valid complete ranking with a deliberately low final story."""
	ids = list(source.story_ranking_aliases.aliases)
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
	outline = next(item for item in source.repo_outlines if item.repositories == story.repositories)
	wrong_packet = next(packet for packet in source.packets if packet.packet_id not in story.packet_ids)
	broken_story = dataclasses.replace(story, packet_ids=(wrong_packet.packet_id,))
	broken_outline = dataclasses.replace(outline, packet_ids=(wrong_packet.packet_id,))
	broken_stories = tuple(
		broken_story if item.artifact_id == story.artifact_id else item
		for item in source.repo_stories
	)
	broken_outlines = tuple(
		broken_outline if item.artifact_id == outline.artifact_id else item
		for item in source.repo_outlines
	)

	with pytest.raises(RuntimeError, match="provenance"):
		daily_blog.daily_outline_workflow.DailyOutlineInput(broken_stories, source.repo_outlines, source.packets, source.evidence_context, source.working_directory)
	with pytest.raises(RuntimeError, match="provenance"):
		daily_blog.daily_outline_workflow.DailyOutlineInput(source.repo_stories, broken_outlines, source.packets, source.evidence_context, source.working_directory)


def test_bounded_context_retains_every_source_and_stage6_uses_only_declared_scope(tmp_path: object) -> None:
	"""A pair-specific reviewer view fits while preserving every survivor."""
	source = _input(tmp_path, 3, True)
	narrow = (source.repositories[0],)
	large_candidate = "\n" + "candidate detail " * 2500
	runner = _Runner({
		"daily_outline_ranking": [_ranking(source), _ranking(source)],
		"daily_outline_writer": [
			_outline(source, narrow, "Candidate A") + large_candidate,
			_outline(source, narrow, "Candidate B") + large_candidate,
		],
		"daily_outline_reviewer": [
			json.dumps({"decision": "ACCEPT", "score": 90, "reason": "grounded"}),
			json.dumps({"decision": "ACCEPT", "score": 90, "reason": "grounded"}),
			json.dumps({"winner": "A", "reason": "grounded", "evidence_quality": "high", "confidence": 1}),
			json.dumps({"winner": "B", "reason": "grounded", "evidence_quality": "high", "confidence": 1}),
		],
	})
	result = _run(source, runner)
	surface = daily_blog.stage6.build_stage6_publication_surface(
		result.artifact, result.selected_stories, source.packets,
		dict(source.evidence_context.projection_limits),
	)

	reviewer_prompts = [prompt for role, prompt in runner.calls if role == "daily_outline_reviewer"]

	assert all(
		all(alias in prompt and repository in prompt for alias, repository in zip(
			source.story_ranking_aliases.aliases, source.repositories, strict=True,
		))
		for prompt in reviewer_prompts
	)
	assert (
		result.source_stories == source.repo_stories
		and tuple(item.repositories[0] for item in result.selected_stories) == narrow
		and surface.repositories == narrow
	)


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


def test_scope_marker_mismatch_loses_to_evidence_derived_peer(tmp_path: object) -> None:
	"""The model marker is an assertion, while cited evidence owns candidate scope."""
	source = _input(tmp_path)
	valid = (source.repositories[0],)
	evidence = next(packet.items[0].evidence_id for packet in source.packets if packet.items[0].repository == valid[0])
	invalid = "<!-- daily-outline-scope: " + json.dumps(list(source.repositories)) + " -->\n# Invalid\n\n<!-- evidence: " + evidence + " -->\n"
	runner = _Runner({
		"daily_outline_ranking": [_ranking(source), _ranking(source)],
		"daily_outline_writer": [invalid, _outline(source, valid)],
		"daily_outline_reviewer": [json.dumps({"decision": "ACCEPT", "score": 90, "reason": "grounded"}), json.dumps({"decision": "ACCEPT", "score": 90, "reason": "grounded"})],
	})
	result = _run(source, runner)

	assert type(result.artifact) is daily_blog.artifacts.DailyOutline
	assert result.artifact.repositories == valid

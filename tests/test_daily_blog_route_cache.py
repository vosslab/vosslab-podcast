"""Offline behavior tests for the coordinator-owned M12 route cache boundary."""

# Standard Library
import dataclasses
import json
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.config
import daily_blog.complete_post_editor_prompts
import daily_blog.daily_outline_workflow
import daily_blog.daily_outline_prompts
import daily_blog.editorial
import daily_blog.editorial_stage_config
import daily_blog.final_synthesis_config
import daily_blog.final_synthesis_prompts
import daily_blog.io_utils
import daily_blog.locks
import daily_blog.replication
import daily_blog.repository_contracts
import daily_blog.route_cache
import daily_blog.schema
import daily_blog.stage6
import daily_blog.stage7


def _request(name: str = "one", *, prompt: str = "trusted input") -> daily_blog.agents.RouteRequest:
	"""Return one route request whose physical execution directory is incidental."""
	return daily_blog.agents.RouteRequest(
		name, "test", daily_blog.editorial_stage_config.RoleRoute("route", ("fixture",)), prompt,
		"/physical/work", role="test", maximum_parallel_calls=2,
		cache_input_hash=daily_blog.io_utils.sha256_text("logical " + prompt),
	)


def _result(request: daily_blog.agents.RouteRequest, text: str = "eligible") -> daily_blog.agents.AgentResult:
	"""Return one fresh matching successful transport result."""
	return daily_blog.agents.AgentResult(
		request.role, text, True, "", 1, 0.0, request.is_repair, False,
		request.route.name, request.request_id, request.identity_sha256,
		daily_blog.io_utils.sha256_text(text),
	)


def _cache(tmp_path: pathlib.Path) -> daily_blog.route_cache.RouteResultCache:
	"""Return a disposable coordinator-owned PhaseCache adapter."""
	return daily_blog.route_cache.RouteResultCache(daily_blog.locks.PhaseCache(str(tmp_path)))


def _stage5_alias_input(
	root: pathlib.Path,
) -> tuple[daily_blog.daily_outline_workflow.DailyOutlineInput, daily_blog.artifacts.RepoStory]:
	"""Return one portable Stage 5 story plus its current runtime artifact."""
	root.mkdir()
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "owner/repository", "a" * 40, "CHANGELOG.md", "b" * 40,
		"Grounded change.", "git show",
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-29", "America/Chicago", True, {}, [], [], [item],
	)
	outline = daily_blog.artifacts.RepoOutline.create(
		packet.report_date, (packet,), item.repository,
		"Outline <!-- evidence: " + item.evidence_id + " -->", (item.evidence_id,),
	)
	story = daily_blog.artifacts.RepoStory.create(
		packet.report_date, (packet,), item.repository,
		"Story <!-- evidence: " + item.evidence_id + " -->", (item.evidence_id,),
	)
	return daily_blog.daily_outline_workflow.DailyOutlineInput((story,), (outline,), (packet,), str(root)), story


class _Stage5AliasRunner:
	"""Return whole ranked, reviewed, and written artifacts without route egress."""

	def __init__(self, ranking: str, outline: str) -> None:
		self.ranking = ranking
		self.outline = outline

	def run(
		self,
		route: daily_blog.editorial_stage_config.RoleRoute,
		_prompt: str,
		_working_directory: str,
	) -> str:
		if "ranking" in route.name:
			return self.ranking
		if "writer" in route.name:
			return self.outline
		return '{"decision":"ACCEPT","reason":"grounded","score":90}'


def _rendered_stage7_request(
	value: daily_blog.stage7.Stage7Input,
	config: daily_blog.final_synthesis_config.FinalSynthesisConfig,
	working_directory: str,
) -> daily_blog.agents.RouteRequest:
	"""Build one Stage 7 request through its real bounded prompt/provenance path."""
	resolved = daily_blog.editorial.resolve_snapshot(None, None, None)
	templates = daily_blog.editorial.validate_prompt_templates(snapshot=resolved)
	prompt_contract = daily_blog.final_synthesis_prompts.load_final_synthesis_prompt_contract()
	identity = {
		**daily_blog.final_synthesis_prompts.final_synthesis_prompt_identity(prompt_contract),
		"rubric_version": resolved.contract.prompt_version,
		"rubric_sha256": daily_blog.io_utils.sha256_text(templates["rubric"]),
		"v4_contract": resolved.contract.prompt_version,
	}
	limits = {
		"incumbent_chars": min(config.prompt_limits["incumbent_chars"], daily_blog.final_synthesis_prompts.MAX_INCUMBENT_POST_CHARS),
		"alternatives_chars": min(config.prompt_limits["alternatives_chars"], daily_blog.final_synthesis_prompts.MAX_ALTERNATIVE_POSTS_CHARS),
		"review_facts_chars": min(config.prompt_limits["review_facts_chars"], daily_blog.final_synthesis_prompts.MAX_STAGE6_REVIEW_CHARS),
		"rubric_chars": min(config.prompt_limits["rubric_chars"], daily_blog.final_synthesis_prompts.MAX_RUBRIC_CHARS),
		"evidence_chars": min(config.prompt_limits["evidence_chars"], daily_blog.final_synthesis_prompts.MAX_EVIDENCE_CHARS),
		"provenance_chars": min(config.prompt_limits["provenance_chars"], daily_blog.final_synthesis_prompts.MAX_PROVENANCE_CHARS),
	}
	alternatives = daily_blog.stage7._alternatives(value)
	prompt, synthesis_identity = daily_blog.stage7._prompt_data(value, alternatives, templates, identity, limits)
	return daily_blog.stage7._request(
		value, "execution-run", "7_1", "synthesizer", "1", config.synthesis_route, prompt, config,
		working_directory, resolved.contract.prompt_version, synthesis_identity,
		(value.incumbent.content_hash,) + tuple(item.content_hash for item in alternatives),
	)


def _real_stage_requests(
	root: pathlib.Path,
	cache_root: str,
	marker: str = "b",
) -> tuple[daily_blog.agents.RouteRequest, ...]:
	"""Build real Stage 5--7 requests from two repositories at one physical root."""
	root.mkdir()
	packets, outlines, sources, stories = [], [], [], []
	for repository in ("owner/alpha", "owner/beta"):
		item = daily_blog.schema.EvidenceItem.create(
			"dated_changelog", repository, "a" * 40, "CHANGELOG.md", marker * 40,
			"Grounded change " + repository + " " + marker + ".", "git show",
		)
		commit = daily_blog.schema.CommitActivity(
			"a" * 40, ("b" * 40,), "Author", "author@example.com",
			"2026-08-29T12:00:00-05:00", "2026-08-29T12:00:00-05:00", "Grounded change",
		)
		activity = daily_blog.schema.RepositoryActivity(
			repository, "https://github.com/" + repository,
			cache_root + "/" + repository.replace("/", "_"), "a" * 40,
			(commit,), (daily_blog.schema.RevisionRange("b" * 40, "a" * 40),), ("a" * 40,), False,
			(daily_blog.repository_contracts.RepositoryLifecycleEvent(
				"repository_created", "2020-01-01T00:00:00Z", False, "github_owner_roster",
			),),
		)
		packet = daily_blog.schema.EvidencePacket.create(
			"2026-08-29", "America/Chicago", True, {}, [], [activity], [item],
		)
		sources.append((repository, item, packet))
		packets.append(packet)
	packets = tuple(sorted(packets, key=lambda item: item.packet_id))
	for repository, item, packet in sources:
		outlines.append(daily_blog.artifacts.RepoOutline.create(
			"2026-08-29", (packet,), repository,
			"Outline <!-- evidence: " + item.evidence_id + " -->", (item.evidence_id,),
		))
		stories.append(daily_blog.artifacts.RepoStory.create(
			"2026-08-29", (packet,), repository,
			"Story <!-- evidence: " + item.evidence_id + " -->", (item.evidence_id,),
		))
	stories = tuple(sorted(stories, key=lambda item: item.artifact_id))
	outlines = tuple(sorted(outlines, key=lambda item: item.artifact_id))
	evidence_ids = tuple(sorted(item.evidence_id for packet in packets for item in packet.items))
	daily_outline = daily_blog.artifacts.DailyOutline.create(
		"2026-08-29", packets, tuple(sorted(item.repositories[0] for item in stories)),
		"Daily outline " + " ".join("<!-- evidence: " + item + " -->" for item in evidence_ids), evidence_ids,
	)
	stage5_input = daily_blog.daily_outline_workflow.DailyOutlineInput(stories, outlines, packets, str(root))
	stage6_input = daily_blog.stage6.Stage6Input(
		daily_outline, stories, packets, str(root), str(root / "2026-08-29" / "post.md"),
	)
	stage5_config = daily_blog.editorial_stage_config.DailyOutlineConfig()
	final_config = daily_blog.final_synthesis_config.FinalSynthesisConfig()
	stage5_contract = daily_blog.daily_outline_prompts.load_daily_outline_prompt_contract()
	stage5_identity = daily_blog.daily_outline_prompts.daily_outline_prompt_identity(stage5_contract)
	stage5 = daily_blog.daily_outline_workflow._request(
		stage5_input, "5_1", "ranker", "1", stage5_config.ranking_route,
		daily_blog.daily_outline_prompts.render_story_ranking(
			stage5_input.render_stories(), stage5_input.render_outlines(), stage5_input.render_evidence(),
			"ranker-1", stage5_contract,
		), stage5_config, stage5_identity, tuple(item.content_hash for item in stories),
	)
	post_config = daily_blog.editorial_stage_config.CompletePostConfig()
	resolved = daily_blog.editorial.resolve_snapshot(None, None, None)
	post_contract = daily_blog.complete_post_editor_prompts.load_complete_post_editor_prompt_contract()
	stage6 = daily_blog.stage6._request(
		stage6_input, "execution-run", "6_1", "writer", "1", post_config.writer_route,
		daily_blog.editorial.render_author_prompt(
			stage6_input, "stage6-" + daily_blog.io_utils.sha256_text(stage6_input.render_context())[:24] + "-writer-1",
			post_config.prompt_limits["writer_chars"], snapshot=resolved,
		), post_config, str(root), resolved.contract.prompt_version,
		daily_blog.complete_post_editor_prompts.complete_post_editor_prompt_identity(post_contract),
	)
	incumbent = daily_blog.artifacts.CompletePost.create(
		"2026-08-29", packets, daily_outline.repositories,
		"Post owner/alpha owner/beta " + " ".join(
			"<!-- evidence: " + item + " -->" for item in evidence_ids
		), evidence_ids,
		"2026-08-29", stage6_input.output_path,
	)
	seed = daily_blog.agents.RouteRequest(
		"stage6-seed", "stage6", post_config.writer_route, "seed", str(root),
		cache_input_hash=daily_blog.io_utils.sha256_text("seed"),
	)
	seed_result = _result(seed, incumbent.content)
	candidate = daily_blog.replication.ReplicatedCandidate(
		seed, seed_result, incumbent, daily_blog.artifacts.evaluate_eligibility(
			incumbent, packets, (str(root),),
		),
	)
	stage6_result = daily_blog.stage6.Stage6Result(
		promotion=daily_blog.artifacts.SelectedPeer(incumbent, daily_blog.artifacts.CompletePost),
		generation=daily_blog.replication.ReplicationResult(daily_blog.artifacts.CompletePost, (candidate,)),
		review=daily_blog.replication.ReviewResult((), ()),
		reliability=daily_blog.replication.StepReliability(
			"stage6", "succeeded", 0, 0, 0, 0, 0, 0, incumbent.artifact_id, ()),
		editing=daily_blog.replication.ReplicationResult(daily_blog.artifacts.CompletePost, ()),
		step_reliability=(daily_blog.replication.StepReliability(
			"stage6", "succeeded", 0, 0, 0, 0, 0, 0, incumbent.artifact_id, ()),),
	)
	stage7_input = daily_blog.stage7.Stage7Input(stage6_input, stage6_result)
	stage7 = _rendered_stage7_request(stage7_input, final_config, str(root))
	return stage5, stage6, stage7


def test_validated_effect_resumes_and_changed_input_does_not_reuse(tmp_path: pathlib.Path) -> None:
	"""Equivalent logical input resumes, while changed editorial input is fresh."""
	cache = _cache(tmp_path)
	request = _request()
	cache.commit((daily_blog.route_cache.RouteCacheEffect(request, _result(request)),))

	assert cache.load(dataclasses.replace(request, working_directory="/other/host")) is not None
	assert cache.load(_request(prompt="meaningfully changed input")) is None


def test_multi_repository_requests_resume_after_root_relocation_but_changed_evidence_misses(
	tmp_path: pathlib.Path,
) -> None:
	"""Semantic Stage 5--7 work resumes across relocated multi-repository evidence."""
	cache = _cache(tmp_path / "cache")
	original = _real_stage_requests(tmp_path / "first-root", "/portable/first")
	relocated = _real_stage_requests(tmp_path / "second-root", "/portable/reversed-2")
	for request in original:
		cache.commit((daily_blog.route_cache.RouteCacheEffect(request, _result(request)),))

	assert all(cache.load(request) is not None for request in relocated)
	changed_evidence = _real_stage_requests(tmp_path / "changed-root", "/portable/third", marker="c")
	assert cache.load(changed_evidence[0]) is None


def test_stage5_portable_rank_alias_selects_the_current_runtime_story(tmp_path: pathlib.Path) -> None:
	"""A portable ranking alias resolves to the current story rather than a stale artifact path."""
	value, story = _stage5_alias_input(tmp_path / "stage5")
	ranking = json.dumps({
		"artifact_ids": [story.content_hash], "scores": {story.content_hash: 90}, "rationale": "grounded",
	})
	outline = (
		'<!-- daily-outline-scope: ["owner/repository"] -->\n# Daily outline\n\n'
		"Grounded work. <!-- evidence: " + story.evidence_ids[0] + " -->\n"
	)
	result = daily_blog.daily_outline_workflow.run_daily_outline(
		value, daily_blog.editorial_stage_config.DailyOutlineConfig(), daily_blog.agents.RouteBudget(32, 2),
		_Stage5AliasRunner(ranking, outline),
	)

	assert result.promoted_ranking.artifact_ids == (story.content_hash,)
	assert result.selected_stories == (story,)


def test_corrupt_or_mismatched_cache_fails_closed(tmp_path: pathlib.Path) -> None:
	"""Malformed durable state is a terminal cache fault rather than a miss."""
	cache = _cache(tmp_path)
	request = _request()
	_identity, key = cache._identity(request)
	cache._cache.store_json("route_result", key, "result.json", {"unexpected": "value"})

	with pytest.raises(daily_blog.route_cache.RouteCacheIntegrityError):
		cache.load(request)


def test_conflicting_buffered_effect_fails_closed(tmp_path: pathlib.Path) -> None:
	"""One logical request cannot collect inconsistent validated outputs."""
	cache = _cache(tmp_path)
	buffer = daily_blog.route_cache.BufferedRouteEffects(cache)
	request = _request()
	buffer.accept(request, _result(request, "first"))

	with pytest.raises(daily_blog.route_cache.RouteCacheIntegrityError):
		buffer.accept(request, _result(request, "different"))


def test_conflicting_durable_effect_preserves_first_value(tmp_path: pathlib.Path) -> None:
	"""A later conflicting coordinator commit fails without replacing accepted work."""
	cache = _cache(tmp_path)
	request = _request()
	cache.commit((daily_blog.route_cache.RouteCacheEffect(request, _result(request, "first")),))
	with pytest.raises(daily_blog.route_cache.RouteCacheIntegrityError):
		cache.commit((daily_blog.route_cache.RouteCacheEffect(request, _result(request, "second")),))
	assert cache.load(request).text == "first"


def test_unparseable_generation_creates_no_cache_effect(tmp_path: pathlib.Path) -> None:
	"""A successful transport result is withheld until parsing and eligibility succeed."""
	cache = _cache(tmp_path)
	buffer = daily_blog.route_cache.BufferedRouteEffects(cache)
	request = _request()

	def parse(_result: daily_blog.agents.AgentResult) -> object:
		raise daily_blog.agents.RepairableStructuredOutput("unparseable")

	class Runner:
		def run(
			self,
			_route: daily_blog.editorial_stage_config.RoleRoute,
			_prompt: str,
			_working_directory: str,
		) -> str:
			return "not an artifact"

	daily_blog.replication.replicate(
		(request,), Runner(), daily_blog.agents.RouteBudget(1), daily_blog.artifacts.DailyOutline, parse,
		lambda _artifact: None, buffer.load, buffer.accept,
	)
	assert buffer.drain() == ()
	assert cache.load(request) is None

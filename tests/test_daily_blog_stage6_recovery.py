"""Focused offline tests for Stage 6 whole-post editorial recovery."""

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
import daily_blog.daily_outline_workflow
import daily_blog.editorial_stage_config
import daily_blog.io_utils
import daily_blog.recovery
import daily_blog.routes
import daily_blog.repository_contracts
import daily_blog.schema
import daily_blog.stage6


_CONTEXT_LIMITS = {
	"commit_subject_chars": 120,
	"context_chars": 60000,
	"excerpt_chars": 1000,
}


def _valid_post_body(value: daily_blog.stage6.Stage6Input) -> str:
	"""Return one V4-valid body using the exact recovery evidence scope."""
	repositories = [
		(activity.repository, activity.repository_url)
		for packet in value.packets for activity in packet.activity
	]
	links = ", ".join("[" + repository + "](" + url + ")" for repository, url in repositories)
	evidence = "<!-- evidence: " + ", ".join(value.daily_outline.evidence_ids) + " -->"
	narrative = (
		"I kept the small changes connected to their source material, checked how they fit the work "
		"already underway, and wrote down the practical consequence before moving to the next thread. "
	) * 12
	coverage = ", ".join(repository for repository, _url in repositories)
	return (
		"# A day of connected work\n\nI followed one grounded thread through the work, keeping the "
		"useful detail visible while leaving room for the next decision. " + evidence
		+ "\n\n<!-- more -->\n\n## Grounded notes\n\nToday I returned to " + links + ". "
		+ narrative + evidence + "\n\n## Project coverage\n\nI tracked active work in " + coverage + ".\n"
	)


#============================================
def _packet(repository: str = "vosslab/recovery") -> daily_blog.schema.EvidencePacket:
	"""Return one authoritative packet for a single whole-post recovery route."""
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", repository, "a" * 40, "CHANGELOG.md", "b" * 40,
		"Grounded recovery change.", "git show",
	)
	activity = daily_blog.schema.RepositoryActivity(
		repository, "https://github.com/" + repository, "/fixture/" + repository.replace("/", "_"),
		"a" * 40, (), (), (), False,
		(daily_blog.repository_contracts.RepositoryLifecycleEvent(
			"repository_created", "2020-01-01T00:00:00Z", False, "fixture",
		),),
	)
	return daily_blog.schema.EvidencePacket.create(
		"2026-08-29", "America/Chicago", True, {}, [], [activity], [item],
	)


#============================================
def _value(tmp_path: pathlib.Path) -> daily_blog.stage6.Stage6Input:
	"""Create an already validated typed Stage 6 input."""
	packet = _packet()
	evidence_id = packet.items[0].evidence_id
	outline = daily_blog.artifacts.DailyOutline.create(
		packet.report_date, (packet,), ("vosslab/recovery",),
		"Outline <!-- evidence: " + evidence_id + " -->", (evidence_id,),
	)
	story = daily_blog.artifacts.RepoStory.create(
		packet.report_date, (packet,), "vosslab/recovery",
		"Story <!-- evidence: " + evidence_id + " -->", (evidence_id,),
	)
	ranking_hash = "a" * 64
	promotion_payload = {
		"candidate_id": "ranking-1",
		"accepted_review_ids": ["review-1"],
		"ranking_content_sha256": ranking_hash,
	}
	promoted_ranking = daily_blog.daily_outline_workflow.PromotedRanking(
		"ranking-promotion-" + daily_blog.io_utils.sha256_text(
			json.dumps(promotion_payload, sort_keys=True, separators=(",", ":")),
		)[:24],
		"ranking-1", ranking_hash, (story.content_hash,), ((story.content_hash, 100),),
		"Grounded ranking rationale.", ("review-1",),
	)
	sources = daily_blog.stage6.Stage6RecoverySources(
		(story,), (daily_blog.artifacts.RepoOutline.create(
			packet.report_date, (packet,), "vosslab/recovery",
			"Outline <!-- evidence: " + evidence_id + " -->", (evidence_id,),
		),), (packet,), promoted_ranking, story.artifact_id,
	)
	return daily_blog.stage6.Stage6Input(
		str(tmp_path), str(tmp_path / packet.report_date / "post.md"), sources,
		daily_blog.stage6.build_stage6_publication_surface(
			outline, (story,), (packet,), _CONTEXT_LIMITS,
		),
	)


#============================================
def _config(tmp_path: pathlib.Path) -> daily_blog.config.DailyBlogConfig:
	"""Return a minimal Stage 6 configuration with one recovery writer route."""
	complete_post = daily_blog.editorial_stage_config.CompletePostConfig(
		writer_count=2, editor_count=2, reviewer_count=1, maximum_parallel_calls=1,
		max_route_calls=44, route_retry_attempts=0,
		writer_route=daily_blog.editorial_stage_config.RoleRoute("writer", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE),
		editor_route=daily_blog.editorial_stage_config.RoleRoute("editor", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE),
		reviewer_route=daily_blog.editorial_stage_config.RoleRoute("reviewer", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE),
	)
	return daily_blog.config.DailyBlogConfig(
		"settings.yaml", str(tmp_path), "owner", "America/Chicago", str(tmp_path),
		str(tmp_path / "mirrors"), (), (),
		(daily_blog.editorial_stage_config.RoleRoute("author", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE),),
		daily_blog.editorial_stage_config.RoleRoute("referee", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE), {}, {},
		{"author_chars": 72000, "referee_chars": 88000},
		daily_blog.config.EditorialReliabilityConfig(2, 1, 1, 44), complete_post=complete_post,
	)


#============================================
def _post(value: daily_blog.stage6.Stage6Input) -> str:
	"""Return a complete grounded model response, not locally assembled output."""
	return _valid_post_body(value)


#============================================
def _recovery_input(
	tmp_path: pathlib.Path,
	rung: daily_blog.recovery.RecoveryRung,
) -> daily_blog.stage6.CompletePostRecoveryInput:
	"""Return one exact, source-scoped whole-post recovery input."""
	return daily_blog.stage6.CompletePostRecoveryInput(_value(tmp_path), rung)


#============================================
def _contracted_story_recovery_input(tmp_path: pathlib.Path) -> daily_blog.stage6.CompletePostRecoveryInput:
	"""Build a two-repository source set whose promoted outline retains only one story."""
	packets = tuple(sorted((_packet("vosslab/a"), _packet("vosslab/z")), key=lambda item: item.packet_id))
	stories = tuple(sorted((
		daily_blog.artifacts.RepoStory.create(
			packet.report_date, (packet,), packet.items[0].repository,
			"Story <!-- evidence: " + packet.items[0].evidence_id + " -->", (packet.items[0].evidence_id,),
		)
		for packet in packets
	), key=lambda item: item.artifact_id))
	outlines = tuple(sorted((
		daily_blog.artifacts.RepoOutline.create(
			packet.report_date, (packet,), packet.items[0].repository,
			"Outline <!-- evidence: " + packet.items[0].evidence_id + " -->", (packet.items[0].evidence_id,),
		)
		for packet in packets
	), key=lambda item: item.artifact_id))
	selected = next(item for item in stories if item.repositories == ("vosslab/a",))
	strongest = next(item for item in stories if item.repositories == ("vosslab/z",))
	ranking_hash = "c" * 64
	promotion_payload = {
		"candidate_id": "ranking-3", "accepted_review_ids": ["review-3"],
		"ranking_content_sha256": ranking_hash,
	}
	ranking = daily_blog.daily_outline_workflow.PromotedRanking(
		"ranking-promotion-" + daily_blog.io_utils.sha256_text(
			json.dumps(promotion_payload, sort_keys=True, separators=(",", ":")),
		)[:24], "ranking-3", ranking_hash,
		tuple(sorted(item.content_hash for item in stories)),
		tuple(sorted((item.content_hash, 100 if item is strongest else 50) for item in stories)),
		"Grounded ranking rationale.", ("review-3",),
	)
	sources = daily_blog.stage6.Stage6RecoverySources(stories, outlines, packets, ranking, strongest.artifact_id)
	evidence_id = selected.evidence_ids[0]
	selected_packets = tuple(packet for packet in packets if packet.items[0].repository == "vosslab/a")
	daily_outline = daily_blog.artifacts.DailyOutline.create(
		packets[0].report_date, selected_packets, selected.repositories,
		"Outline <!-- evidence: " + evidence_id + " -->", (evidence_id,),
	)
	stage6_input = daily_blog.stage6.Stage6Input(
		str(tmp_path), str(tmp_path / daily_outline.report_date / "post.md"), sources,
		daily_blog.stage6.build_stage6_publication_surface(
			daily_outline, (selected,), packets, _CONTEXT_LIMITS,
		),
	)
	return daily_blog.stage6.CompletePostRecoveryInput(
		stage6_input, daily_blog.recovery.RecoveryRung.REPOSITORY_STORY_MERGE,
	)


#============================================
def test_recovery_sources_canonicalize_multirepository_pairs_and_stable_ties() -> None:
	"""Recovery sources align independently sorted Stage-5 pairs by repository identity."""
	packets = (_packet("vosslab/z"), _packet("vosslab/a"))
	stories = tuple(
		daily_blog.artifacts.RepoStory.create(
			packet.report_date, (packet,), packet.items[0].repository,
			"Story <!-- evidence: " + packet.items[0].evidence_id + " -->",
			(packet.items[0].evidence_id,),
		)
		for packet in packets
	)
	outlines = tuple(
		daily_blog.artifacts.RepoOutline.create(
			packet.report_date, (packet,), packet.items[0].repository,
			"Outline <!-- evidence: " + packet.items[0].evidence_id + " -->",
			(packet.items[0].evidence_id,),
		)
		for packet in packets
	)
	stories = tuple(reversed(sorted(stories, key=lambda item: item.artifact_id)))
	outlines = tuple(sorted(outlines, key=lambda item: item.artifact_id))
	ranking_hash = "b" * 64
	payload = {
		"candidate_id": "ranking-2", "accepted_review_ids": ["review-2"],
		"ranking_content_sha256": ranking_hash,
	}
	promoted = daily_blog.daily_outline_workflow.PromotedRanking(
		"ranking-promotion-" + daily_blog.io_utils.sha256_text(
			json.dumps(payload, sort_keys=True, separators=(",", ":")),
		)[:24],
		"ranking-2", ranking_hash, tuple(sorted(item.content_hash for item in stories)),
		tuple(sorted((item.content_hash, 100) for item in stories)),
		"Grounded ranking rationale.", ("review-2",),
	)
	strongest = min(stories, key=lambda item: item.artifact_id)
	sources = daily_blog.stage6.Stage6RecoverySources(
		stories, outlines, packets, promoted, strongest.artifact_id,
	)

	assert tuple(item.repositories[0] for item in sources.repo_stories) == ("vosslab/a", "vosslab/z")
	assert sources.strongest_story is strongest


#============================================
def test_story_recovery_contracts_sources_to_the_promoted_daily_outline(
		tmp_path: pathlib.Path,
) -> None:
	"""A lower recovery rung cannot re-expand a contracted promoted outline."""
	value = _contracted_story_recovery_input(tmp_path)

	assert value.repositories == ("vosslab/a",)
	assert value.strongest_story_within_scope.repositories == ("vosslab/a",)
	assert "vosslab/z" not in value.render_context()


#============================================
def test_daily_outline_recovery_authors_an_eligible_grounded_post(
		tmp_path: pathlib.Path,
) -> None:
	"""The outline recovery rung retains its independently authored eligible post."""
	value = _recovery_input(tmp_path, daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION)
	accepted = []
	class Runner:
		def run(self, _route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			return _post(value.stage6_input)
	attempt = daily_blog.stage6.recover_daily_outline_expansion(
		value, "run-1", _config(tmp_path), daily_blog.agents.RouteBudget(4, 1), Runner(),
		cache_load=lambda _request: None,
		cache_accept=lambda request, result: accepted.append((request, result)),
	)

	assert isinstance(attempt.outcome, daily_blog.artifacts.SelectedPeer)
	assert attempt.outcome.artifact.packet_ids == tuple(packet.packet_id for packet in value.packets)
	assert accepted and attempt.recovery_generation is not None


#============================================
def test_repository_story_recovery_authors_an_eligible_grounded_post(
		tmp_path: pathlib.Path,
) -> None:
	"""The story merge rung retains its independently authored eligible post."""
	value = _recovery_input(tmp_path, daily_blog.recovery.RecoveryRung.REPOSITORY_STORY_MERGE)
	budget, accepted = daily_blog.agents.RouteBudget(4, 1), []
	class Runner:
		def run(self, _route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			return _post(value.stage6_input)
	attempt = daily_blog.stage6.recover_repository_story_merge(
		value, "run-2", _config(tmp_path), budget, Runner(),
		cache_load=lambda _request: None,
		cache_accept=lambda request, result: accepted.append((request, result)),
	)

	assert isinstance(attempt.outcome, daily_blog.artifacts.SelectedPeer)
	assert attempt.outcome.artifact.repositories == value.repositories
	assert accepted and attempt.recovery_generation is not None


#============================================
def test_recovery_route_loss_is_classified_as_route_unavailable(
		tmp_path: pathlib.Path,
) -> None:
	"""A route exception remains an ordinary recovery-path outage."""
	value = _recovery_input(tmp_path, daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION)
	class Runner:
		def run(self, _route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			raise daily_blog.routes.EditorialRouteTimeout("fixture")
	attempt = daily_blog.stage6.recover_daily_outline_expansion(
		value, "run-5", _config(tmp_path), daily_blog.agents.RouteBudget(4, 1), Runner(),
	)

	assert isinstance(attempt.outcome, daily_blog.artifacts.NoArtifact)
	assert attempt.outcome.reason == daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE.value


#============================================
def test_recovery_ungrounded_response_is_classified_as_no_eligible_generation(
		tmp_path: pathlib.Path,
) -> None:
	"""A successful but ungrounded response stays editorial degradation."""
	value = _recovery_input(tmp_path, daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION)
	class Runner:
		def run(self, _route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			return "# Ungrounded recovery\n"
	attempt = daily_blog.stage6.recover_daily_outline_expansion(
		value, "run-6", _config(tmp_path), daily_blog.agents.RouteBudget(4, 1), Runner(),
	)

	assert isinstance(attempt.outcome, daily_blog.artifacts.NoArtifact)
	assert attempt.outcome.reason == daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION.value


#============================================
def test_recovery_editors_repair_grounded_author_drafts_that_miss_body_policy(
		tmp_path: pathlib.Path,
) -> None:
	"""Recovery preserves a grounded draft for an editor without promoting it unchanged."""
	value = _recovery_input(tmp_path, daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION)
	invalid = _post(value.stage6_input) + "\n\n" + "An intentionally uncited afterword.\n\n" * 4
	edited = _post(value.stage6_input).replace(
		"# A day of connected work", "# Recovery editorial repair",
	)
	class Runner:
		editor_prompts: list[str] = []

		def run(
			self, route: daily_blog.editorial_stage_config.RoleRoute,
			prompt: str, _directory: str,
		) -> str:
			if route.name == "writer":
				return invalid
			if route.name == "editor":
				self.editor_prompts.append(prompt)
				return edited
			return '{"winner":"A","reason":"grounded","evidence_quality":"high","confidence":1}'

	runner = Runner()
	attempt = daily_blog.stage6.recover_daily_outline_expansion(
		value, "recovery-editor", _config(tmp_path), daily_blog.agents.RouteBudget(20, 1), runner,
	)

	assert runner.editor_prompts and "Project coverage must use one compact paragraph or list." in runner.editor_prompts[0]
	assert isinstance(attempt.outcome, daily_blog.artifacts.SelectedPeer) and "Recovery editorial repair" in attempt.outcome.artifact.content


#============================================
def test_recovery_reviews_multiple_eligible_peers_before_promoting_one(
		tmp_path: pathlib.Path,
		monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Recovery promotion follows balanced review votes rather than author response order."""
	value = _recovery_input(tmp_path, daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION)
	first = _post(value.stage6_input).replace("# A day of connected work", "# First author response")
	chosen = _post(value.stage6_input).replace("# A day of connected work", "# Reviewed recovery choice")
	reviewed: list[daily_blog.artifacts.EditorialArtifact] = []

	def review_spy(
		candidates: object, _expected_type: type, *_args: object, **_kwargs: object,
	) -> daily_blog.replication.ReviewResult:
		peers = tuple(candidates)
		reviewed.extend(peers)
		winner = next(item for item in peers if "Reviewed recovery choice" in item.content)
		return daily_blog.replication.ReviewResult((), (
			daily_blog.replication.ReviewVote(
				"recovery-review", peers[0].artifact_id, peers[1].artifact_id,
				"succeeded", winner.artifact_id,
			),
		))

	monkeypatch.setattr(daily_blog.replication, "review", review_spy)

	class Runner:
		author_calls = 0

		def run(
			self, route: daily_blog.editorial_stage_config.RoleRoute,
			_prompt: str, _directory: str,
		) -> str:
			if route.name == "writer":
				self.author_calls += 1
				return first if self.author_calls == 1 else chosen
			if route.name == "editor":
				raise daily_blog.routes.EditorialRouteTimeout("offline")
			raise AssertionError("Typed review spy replaces referee route execution.")

	runner = Runner()
	attempt = daily_blog.stage6.recover_daily_outline_expansion(
		value, "recovery-review", _config(tmp_path), daily_blog.agents.RouteBudget(30, 1), runner,
	)

	assert any("First author response" in item.content for item in reviewed) and any(
		"Reviewed recovery choice" in item.content for item in reviewed
	)
	assert isinstance(attempt.outcome, daily_blog.artifacts.SelectedPeer) and "Reviewed recovery choice" in attempt.outcome.artifact.content


#============================================
def test_recovery_all_policy_invalid_author_and_editor_posts_are_typed_degradation(
		tmp_path: pathlib.Path,
) -> None:
	"""Recovery records every successful invalid editorial response without assembling a post."""
	value = _recovery_input(tmp_path, daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION)
	invalid = _post(value.stage6_input) + "\n\n" + "An intentionally uncited afterword.\n\n" * 4
	class Runner:
		def run(
			self, route: daily_blog.editorial_stage_config.RoleRoute,
			_prompt: str, _directory: str,
		) -> str:
			return invalid

	attempt = daily_blog.stage6.recover_daily_outline_expansion(
		value, "recovery-invalid", _config(tmp_path), daily_blog.agents.RouteBudget(20, 1), Runner(),
	)

	assert isinstance(attempt.outcome, daily_blog.artifacts.NoArtifact) and attempt.outcome.reason == "no_eligible_generation"
	assert attempt.recovery_generation is not None and (
		attempt.observation.successful_responses == len(attempt.recovery_generation.candidates)
		and not attempt.recovery_generation.eligible
	)


#============================================
def test_recovery_reports_real_writer_loss_and_repaired_disagreeing_reviews(
		tmp_path: pathlib.Path,
) -> None:
	"""Recovery retains bounded facts for real route loss, repair, and review disagreement."""
	value = _recovery_input(tmp_path, daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION)
	config = _config(tmp_path)
	initial_review_calls = 2

	class Runner:
		writer_calls = 0
		reviewer_calls = 0

		def run(
			self, route: daily_blog.editorial_stage_config.RoleRoute,
			_prompt: str, _directory: str,
		) -> str:
			if route.name == "writer":
				self.writer_calls += 1
				if self.writer_calls == 1:
					raise daily_blog.routes.EditorialRouteTimeout("fixture")
				return _post(value.stage6_input).replace("connected work", "writer recovery")
			if route.name == "editor":
				return _post(value.stage6_input).replace("connected work", "editor recovery " + str(self.writer_calls))
			self.reviewer_calls += 1
			return "unstructured verdict" if self.reviewer_calls <= initial_review_calls else "A"

	attempt = daily_blog.stage6.recover_daily_outline_expansion(
		value, "recovery-observability", config, daily_blog.agents.RouteBudget(44, 1), Runner(),
	)
	summaries = {item.step: item for item in attempt.step_reliability}

	assert isinstance(attempt.outcome, daily_blog.artifacts.DegradedPromotion)
	assert summaries["6.1"].failed == 1
	assert summaries["6.3"].repaired > 0
	assert summaries["6.3"].disagreements > 0
	assert "review_disagreement" in summaries["6.3"].reasons
	assert summaries["6.4"].best_artifact_id == attempt.outcome.artifact.artifact_id


#============================================
def test_recovery_reuses_grounded_writer_cache_when_editor_prompt_is_limited(
		tmp_path: pathlib.Path,
) -> None:
	"""A prompt-size degradation retains cache reuse and a categorical editor reason."""
	value = _recovery_input(tmp_path, daily_blog.recovery.RecoveryRung.DAILY_OUTLINE_EXPANSION)

	class Runner:
		def run(
			self, route: daily_blog.editorial_stage_config.RoleRoute,
			_prompt: str, _directory: str,
		) -> str:
			if route.name == "reviewer":
				return '{"winner":"A","reason":"grounded","evidence_quality":"high","confidence":1}'
			return _post(value.stage6_input)

	def cached(request: daily_blog.agents.RouteRequest) -> daily_blog.agents.AgentResult | None:
		if request.role not in {"recovery_author", "recovery_editor"}:
			return None
		text = _post(value.stage6_input)
		return daily_blog.agents.AgentResult(
			request.role, text, True, "", 1, 0.0, request.is_repair, True,
			request.route.name, request.request_id, request.identity_sha256,
			daily_blog.io_utils.sha256_text(text),
		)

	full = daily_blog.stage6.recover_daily_outline_expansion(
		value, "recovery-cache-source", _config(tmp_path), daily_blog.agents.RouteBudget(44, 1), Runner(),
		cache_load=cached,
	)
	full_summaries = {item.step: item for item in full.step_reliability}
	base = _config(tmp_path).complete_post
	limits = dict(base.prompt_limits)
	limits["editor_chars"] = 1
	limited_config = dataclasses.replace(_config(tmp_path), complete_post=dataclasses.replace(
		base, prompt_limits=limits,
	))
	attempt = daily_blog.stage6.recover_daily_outline_expansion(
		value, "recovery-cache-limited", limited_config, daily_blog.agents.RouteBudget(44, 1), Runner(),
		cache_load=cached,
	)
	summaries = {item.step: item for item in attempt.step_reliability}

	assert full_summaries["6.1"].reused > 0 and full_summaries["6.2"].reused > 0
	assert summaries["6.1"].reused > 0 and {
		"editor_prompt_limit", "editor_unavailable",
	}.issubset(summaries["6.2"].reasons)

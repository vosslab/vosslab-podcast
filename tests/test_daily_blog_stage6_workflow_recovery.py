"""Offline behavior checks for the Stage 6 recovery write boundary."""

# Standard Library
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
import daily_blog.orchestrator
import daily_blog.publication_admission
import daily_blog.publication_workflow
import daily_blog.recovery
import daily_blog.replication
import daily_blog.routes
import daily_blog.schema
import daily_blog.stage6
import daily_blog.repository_contracts


_CONTEXT_LIMITS = {
	"commit_subject_chars": 120,
	"context_chars": 60000,
	"excerpt_chars": 1000,
}


def _valid_post_body(value: daily_blog.stage6.Stage6Input) -> str:
	"""Return one V4-valid body using the exact Stage 6 recovery scope."""
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
	payload = {
		"candidate_id": "ranking-1", "accepted_review_ids": ["review-1"],
		"ranking_content_sha256": ranking_hash,
	}
	promoted = daily_blog.daily_outline_workflow.PromotedRanking(
		"ranking-promotion-" + daily_blog.io_utils.sha256_text(
			json.dumps(payload, sort_keys=True, separators=(",", ":")),
		)[:24], "ranking-1", ranking_hash, (story.content_hash,),
		((story.content_hash, 100),), "Grounded ranking rationale.", ("review-1",),
	)
	sources = daily_blog.stage6.Stage6RecoverySources(
		(story,), (repository_outline,), (packet,), promoted, story.artifact_id,
	)
	return daily_blog.stage6.Stage6Input(
		daily_outline, (story,), str(root),
		str(root / "owner" / "daily_blog" / packet.report_date / "post.md"), sources,
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
		str(root / "mirrors"), (), (), (route,), route, {}, {}, {},
		daily_blog.config.EditorialReliabilityConfig(2, 1, 1, 32),
	)


def _coordinator(root: pathlib.Path) -> tuple[object, daily_blog.stage6.Stage6Input]:
	"""Advance a disposable run to its sole Stage 6 execution boundary."""
	value = _input(root)
	coordinator = daily_blog.orchestrator.DailyPublicationOrchestrator(
		_config(root), value.report_date,
	)
	for phase in coordinator.record.phases:
		if phase == "stage6_complete_post":
			break
		coordinator._start(phase, {"fixture": phase})
		coordinator._complete(phase, {"fixture": phase})
	return coordinator, value


def _exhausted(root: pathlib.Path) -> daily_blog.stage6.Stage6Result:
	"""Return an ordinary no-artifact Stage 6 result eligible for editorial recovery."""
	route = daily_blog.editorial_stage_config.RoleRoute(
		"writer", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE,
	)
	request = daily_blog.agents.RouteRequest(
		"exhausted-stage6-writer", "stage6_6_1", route, "fixture", str(root),
		input_hash="a" * 64, contract_version="v4", role="writer",
		cache_input_hash="b" * 64,
	)
	response = daily_blog.agents.AgentResult(
		"writer", "", False, "timeout", 1, 0.0, False, False, route.name,
		request.request_id, request.identity_sha256, daily_blog.io_utils.sha256_text(""),
	)
	writing = daily_blog.replication.ReplicationResult(
		daily_blog.artifacts.CompletePost,
		(daily_blog.replication.ReplicatedCandidate(request, response, None, None, "timeout"),),
	)
	summary = daily_blog.replication.StepReliability(
		"stage6_complete_post", "degraded", 1, 0, 1, 0, 0, 0, "", ("route_unavailable", "timeout", "upstream_unavailable"),
	)
	writer = daily_blog.replication.StepReliability(
		"6.1", "degraded", 1, 0, 1, 0, 0, 0, "", ("timeout",),
	)
	return daily_blog.stage6.Stage6Result(
		promotion=daily_blog.artifacts.NoArtifact(
			daily_blog.artifacts.CompletePost,
			daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE.value,
		), generation=writing,
		review=daily_blog.replication.ReviewResult((), ()), reliability=summary,
		editing=daily_blog.replication.ReplicationResult(daily_blog.artifacts.CompletePost, ()),
		step_reliability=(writer, daily_blog.replication.StepReliability(
			"6.2", "succeeded", 0, 0, 0, 0, 0, 0, "", (),
		), daily_blog.replication.StepReliability(
			"6.3", "succeeded", 0, 0, 0, 0, 0, 0, "", (),
		), daily_blog.replication.StepReliability(
			"6.4", "succeeded", 0, 0, 0, 0, 0, 0, "", (),
		)),
	)


def _parsed_policy_ineligible(value: daily_blog.stage6.Stage6Input) -> daily_blog.stage6.Stage6Result:
	"""Return one mechanically grounded post rejected only by final body policy."""
	content = (
		"# Primary\n\nGrounded but intentionally too brief. <!-- evidence: "
		+ value.daily_outline.evidence_ids[0] + " -->\n"
	)
	primary = daily_blog.artifacts.CompletePost.create(
		value.report_date, value.packets, value.daily_outline.repositories, content,
		value.daily_outline.evidence_ids, value.report_date, value.output_path,
	)
	route = daily_blog.editorial_stage_config.RoleRoute(
		"writer", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE,
	)
	request = daily_blog.agents.RouteRequest(
		"ineligible-stage6-writer", "stage6_6_1", route, "fixture", value.output_root,
		input_hash="a" * 64, contract_version="v4", role="writer", cache_input_hash="b" * 64,
	)
	response = daily_blog.agents.AgentResult(
		"writer", content, True, "", 1, 0.0, False, False, route.name,
		request.request_id, request.identity_sha256, daily_blog.io_utils.sha256_text(content),
	)
	eligibility = daily_blog.publication_admission.complete_post_eligibility(
		primary, value.publication_surface, value.output_root,
	)
	assert "publication_policy_mismatch" in eligibility.reasons
	assert "presentation_policy_mismatch" in eligibility.reasons
	writing = daily_blog.replication.ReplicationResult(
		daily_blog.artifacts.CompletePost,
		(daily_blog.replication.ReplicatedCandidate(request, response, primary, eligibility, ""),),
	)
	writer = daily_blog.replication.StepReliability(
		"6.1", "degraded", 1, 0, 1, 0, 0, 0, "", ("ineligible_generation",),
	)
	steps = (writer,) + tuple(daily_blog.replication.StepReliability(
		"6." + str(index), "succeeded", 0, 0, 0, 0, 0, 0, "", (),
	) for index in range(2, 5))
	return daily_blog.stage6.Stage6Result(
		promotion=daily_blog.artifacts.NoArtifact(
			daily_blog.artifacts.CompletePost,
			daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION.value,
		),
		generation=writing, review=daily_blog.replication.ReviewResult((), ()),
		reliability=daily_blog.replication.StepReliability(
			"stage6_complete_post", "degraded", 1, 0, 1, 0, 0, 0, "",
			("no_eligible_generation",),
		),
		editing=daily_blog.replication.ReplicationResult(daily_blog.artifacts.CompletePost, ()),
		step_reliability=steps,
	)


def _post(value: daily_blog.stage6.Stage6Input) -> daily_blog.artifacts.CompletePost:
	"""Return one independently authored grounded whole post fixture."""
	return daily_blog.artifacts.CompletePost.create(
		value.report_date, value.packets, value.daily_outline.repositories,
		_valid_post_body(value),
		value.daily_outline.evidence_ids, value.report_date, value.output_path,
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


def test_stage6_normal_primary_promotes_the_grounded_artifact(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""An eligible primary post advances unchanged through the public Stage 6 boundary."""
	coordinator, value = _coordinator(tmp_path)
	post = _post(value)
	selected = daily_blog.stage6.Stage6Result(
		promotion=daily_blog.artifacts.SelectedPeer(post, daily_blog.artifacts.CompletePost),
		generation=daily_blog.replication.ReplicationResult(daily_blog.artifacts.CompletePost, ()),
		review=daily_blog.replication.ReviewResult((), ()),
		reliability=daily_blog.replication.StepReliability("stage6", "succeeded", 0, 0, 0, 0, 0, 0, post.artifact_id, ()),
		editing=daily_blog.replication.ReplicationResult(daily_blog.artifacts.CompletePost, ()),
		step_reliability=tuple(daily_blog.replication.StepReliability("6." + str(index), "succeeded", 0, 0, 0, 0, 0, 0, post.artifact_id, ()) for index in range(1, 5)),
	)
	monkeypatch.setattr(daily_blog.stage6, "run_stage6", lambda *_args, **_kwargs: selected)

	result = daily_blog.publication_workflow.run_typed_stage6(coordinator, value)
	assert result.artifact is post
	assert result.reliability.outcome == "succeeded"


def test_stage6_terminal_fault_commits_valid_buffered_route_result(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A typed terminal fault preserves an already validated reusable route result."""
	coordinator, value = _coordinator(tmp_path)
	request = daily_blog.agents.RouteRequest(
		"validated-stage6", "stage6", coordinator.config.complete_post.writer_route,
		"fixture", str(tmp_path), input_hash="a" * 64, contract_version="v4",
		role="writer", cache_input_hash="b" * 64,
	)
	result = daily_blog.agents.AgentResult(
		"writer", "validated", True, "", 1, 0, False, False, request.route.name,
		request.request_id, request.identity_sha256, daily_blog.io_utils.sha256_text("validated"),
	)

	def exhausted_with_effect(*_args: object, cache_load: object, cache_accept: object, **_kwargs: object) -> daily_blog.stage6.Stage6Result:
		assert callable(cache_load) and callable(cache_accept)
		if cache_load(request) is None:
			cache_accept(request, result)
		return _exhausted(tmp_path)

	monkeypatch.setattr(daily_blog.stage6, "run_stage6", exhausted_with_effect)

	class Runner:
		def run(
			self,
			_route: daily_blog.editorial_stage_config.RoleRoute,
			_prompt: str,
			_directory: str,
		) -> str:
			raise daily_blog.routes.EditorialRouteTimeout("fixture")

	coordinator.route_runner = Runner()

	with pytest.raises(daily_blog.recovery.PipelineFaultError):
		daily_blog.publication_workflow.run_typed_stage6(coordinator, value)
	assert coordinator.route_cache.load(request) is not None


def test_stage6_policy_rejection_descends_to_a_grounded_editorial_recovery(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Body-policy attrition activates an eligible whole-post editorial path."""
	coordinator, value = _coordinator(tmp_path)

	class Runner:
		def run(
			self,
			_route: daily_blog.editorial_stage_config.RoleRoute,
			_prompt: str,
			_directory: str,
		) -> str:
			return _post(value).content

	coordinator.route_runner = Runner()
	monkeypatch.setattr(
		daily_blog.stage6, "run_stage6", lambda *_args, **_kwargs: _parsed_policy_ineligible(value),
	)
	result = daily_blog.publication_workflow.run_typed_stage6(coordinator, value)

	assert result.artifact is not None and result.artifact.content == _post(value).content
	assert result.reliability.outcome == "degraded"
	assert result.recovery_generation is not None

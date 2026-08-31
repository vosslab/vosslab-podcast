"""Focused durable join checks for the typed Stage 7 publication bridge."""

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
import daily_blog.final_synthesis_config
import daily_blog.orchestrator
import daily_blog.publication_workflow
import daily_blog.replication
import daily_blog.run_contracts
import daily_blog.schema
import daily_blog.repository_contracts
import daily_blog.stage6
import daily_blog.stage7
import daily_blog.io_utils


_CONTEXT_LIMITS = {
	"commit_subject_chars": 120,
	"context_chars": 60000,
	"excerpt_chars": 1000,
}


def _valid_post_body(
	packets: tuple[object, ...], evidence_ids: tuple[str, ...], title: str = "A day of connected work",
) -> str:
	"""Return one V4-valid body using the exact Stage 7 evidence scope."""
	repositories = [
		(activity.repository, activity.repository_url)
		for packet in packets for activity in packet.activity
	]
	links = ", ".join("[" + repository + "](" + url + ")" for repository, url in repositories)
	evidence = "<!-- evidence: " + ", ".join(evidence_ids) + " -->"
	narrative = (
		"I kept the small changes connected to their source material, checked how they fit the work "
		"already underway, and wrote down the practical consequence before moving to the next thread. "
	) * 12
	coverage = ", ".join(repository for repository, _url in repositories)
	return (
		"# " + title + "\n\nI followed one grounded thread through the work, keeping the useful "
		"detail visible while leaving room for the next decision. " + evidence
		+ "\n\n<!-- more -->\n\n## Grounded notes\n\nToday I returned to " + links + ". "
		+ narrative + evidence + "\n\n## Project coverage\n\nI tracked active work in " + coverage + ".\n"
	)


def _recovery_sources(
	story: daily_blog.artifacts.RepoStory,
	packet: daily_blog.schema.EvidencePacket,
) -> daily_blog.stage6.Stage6RecoverySources:
	"""Return reviewed lower-rung sources for the shared Stage 6 boundary."""
	evidence_id = packet.items[0].evidence_id
	repository_outline = daily_blog.artifacts.RepoOutline.create(
		packet.report_date, (packet,), story.repositories[0],
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
		(story,), (repository_outline,), (packet,), promoted, story.artifact_id,
	)


def _source(tmp_path: pathlib.Path) -> tuple[
	daily_blog.orchestrator.DailyPublicationOrchestrator,
	daily_blog.schema.EvidencePacket,
	daily_blog.stage6.Stage6Input,
	daily_blog.stage6.Stage6Result,
	daily_blog.artifacts.CompletePost,
]:
	"""Build one exact Stage-6 incumbent eligible for the Stage-7 boundary."""
	item = daily_blog.schema.EvidenceItem.create("dated_changelog", "owner/repository", "a" * 40,
		"CHANGELOG.md", "b" * 40, "Grounded change.", "git show")
	activity = daily_blog.schema.RepositoryActivity(
		"owner/repository", "https://github.com/owner/repository", "/fixture/repository",
		"a" * 40, (), (), (), False,
		(daily_blog.repository_contracts.RepositoryLifecycleEvent(
			"repository_created", "2020-01-01T00:00:00Z", False, "fixture",
		),),
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-29", "America/Chicago", True, {}, [], [activity], [item],
	)
	output_path = str(tmp_path / "owner" / "daily_blog" / packet.report_date / "post.md")
	story = daily_blog.artifacts.RepoStory.create(packet.report_date, (packet,), "owner/repository",
		"Story <!-- evidence: " + item.evidence_id + " -->", (item.evidence_id,))
	outline = daily_blog.artifacts.DailyOutline.create(packet.report_date, (packet,), ("owner/repository",),
		"Outline <!-- evidence: " + item.evidence_id + " -->", (item.evidence_id,))
	value = daily_blog.stage6.Stage6Input(
		outline, (story,), str(tmp_path), output_path,
		_recovery_sources(story, packet), daily_blog.stage6.build_stage6_publication_surface(
			outline, (story,), (packet,), _CONTEXT_LIMITS,
		),
	)
	def post(title: str) -> daily_blog.artifacts.CompletePost:
		return daily_blog.artifacts.CompletePost.create(packet.report_date, (packet,), ("owner/repository",),
			_valid_post_body((packet,), (item.evidence_id,), title),
			(item.evidence_id,), packet.report_date, output_path)
	incumbent, alternative = post("INCUMBENT"), post("ALTERNATIVE")
	route = daily_blog.editorial_stage_config.RoleRoute("fixture", ("fixture",))
	request = daily_blog.agents.RouteRequest("stage6", "stage6", route, "fixture", str(tmp_path),
		input_hash="a" * 64, contract_version="fixture")
	result = daily_blog.agents.AgentResult("fixture", alternative.content, True, "", 1, 0, False, False,
		"fixture", request.request_id, request.identity_sha256, alternative.content_hash)
	eligible = daily_blog.artifacts.EligibilityResult(True, ())
	candidate = daily_blog.replication.ReplicatedCandidate(request, result, alternative, eligible)
	incumbent_request = dataclasses.replace(request, request_id="incumbent", input_hash="b" * 64)
	incumbent_result = dataclasses.replace(result, request_id="incumbent",
		request_identity_sha256=incumbent_request.identity_sha256, text=incumbent.content,
		text_sha256=incumbent.content_hash)
	incumbent_candidate = daily_blog.replication.ReplicatedCandidate(
		incumbent_request, incumbent_result, incumbent, eligible)
	stage6_result = daily_blog.stage6.Stage6Result(
		promotion=daily_blog.artifacts.SelectedPeer(incumbent, daily_blog.artifacts.CompletePost),
		generation=daily_blog.replication.ReplicationResult(
			daily_blog.artifacts.CompletePost, (candidate, incumbent_candidate)),
		review=daily_blog.replication.ReviewResult((), ()),
		reliability=daily_blog.replication.StepReliability(
			"stage6", "succeeded", 0, 0, 0, 0, 0, 0, incumbent.artifact_id, ()),
		editing=daily_blog.replication.ReplicationResult(daily_blog.artifacts.CompletePost, ()),
		step_reliability=(daily_blog.replication.StepReliability(
			"stage6", "succeeded", 0, 0, 0, 0, 0, 0, incumbent.artifact_id, ()),),
	)
	stage = daily_blog.final_synthesis_config.FinalSynthesisConfig(2, 1, 2, 14, 0,
		daily_blog.editorial_stage_config.RoleRoute(
			"synthesis", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE),
		daily_blog.editorial_stage_config.RoleRoute(
			"reviewer", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE))
	config = daily_blog.config.DailyBlogConfig("settings.yaml", str(tmp_path), "owner", "America/Chicago", str(tmp_path),
		str(tmp_path / "mirrors"), (), (), (route,), route, {}, {}, {},
		daily_blog.config.EditorialReliabilityConfig(2, 1, 1, 8), final_synthesis=stage)
	coordinator = daily_blog.orchestrator.DailyPublicationOrchestrator(config, packet.report_date)
	for phase in coordinator.record.phases:
		if phase == "stage7_final_synthesis":
			break
		coordinator._start(phase, {"fixture": phase})
		coordinator._complete(phase, {"fixture": phase})
	coordinator.store.record_editorial_step(
		coordinator.record, stage6_result.reliability,
		daily_blog.run_contracts.EstablishIncumbent(incumbent.artifact_id),
	)
	return coordinator, packet, value, stage6_result, incumbent


def _result(
	value: daily_blog.stage6.Stage6Input,
	incumbent: daily_blog.artifacts.CompletePost,
	challenger: daily_blog.artifacts.CompletePost | None = None,
) -> daily_blog.stage7.Stage7Result | None:
	"""Return a structurally valid result; selected peers are tested through Stage7Result itself."""
	selected = challenger or incumbent
	promotion = (daily_blog.artifacts.SelectedPeer(selected, daily_blog.artifacts.CompletePost)
		if challenger else daily_blog.artifacts.PreservedArtifact(incumbent, daily_blog.artifacts.CompletePost))
	steps = tuple(daily_blog.replication.StepReliability("7." + str(index), "succeeded", 1, 1, 0, 0, 0,
		0, selected.artifact_id, ()) for index in range(1, 4))
	if challenger is None:
		return daily_blog.stage7.Stage7Result(promotion,
			daily_blog.replication.ReplicationResult(daily_blog.artifacts.CompletePost, ()),
			daily_blog.replication.ReviewResult((), ()), steps, incumbent, 1)
	return None


def test_stage7_preservation_persists_only_nonadvancing_steps_and_bounded_reliability(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Ordinary final-synthesis degradation preserves the exact Stage-6 incumbent."""
	coordinator, _packet, value, stage6_result, incumbent = _source(tmp_path)
	result = _result(value, incumbent)
	def run(
		input_value: daily_blog.stage7.Stage7Input,
		_run_id: str,
		_config: daily_blog.config.DailyBlogConfig,
		budget: daily_blog.agents.RouteBudget,
		*,
		runner: object,
		cache_load: object,
		cache_accept: object,
	) -> daily_blog.stage7.Stage7Result:
		return result
	monkeypatch.setattr(daily_blog.stage7, "run_stage7", run)

	actual = daily_blog.publication_workflow.run_typed_stage7(coordinator, value, stage6_result)

	assert actual is result and coordinator.record.best_artifact_id == incumbent.artifact_id


def test_stage7_win_attests_and_advances_only_final_promotion_step(tmp_path: pathlib.Path) -> None:
	"""A direct peer win records the explicit Stage-7 replacement attestation."""
	coordinator, packet, value, stage6_result, incumbent = _source(tmp_path)
	challenger = daily_blog.artifacts.CompletePost.create(value.report_date, value.packets,
		value.daily_outline.repositories, _valid_post_body(
			value.packets, value.daily_outline.evidence_ids, "CHALLENGER",
		), value.daily_outline.evidence_ids,
		value.report_date, value.output_path)

	class Runner:
		def run(self, route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, _working: str) -> str:
			if route.name == "synthesis":
				return challenger.content
			left = prompt.index("# CHALLENGER") < prompt.index("# INCUMBENT")
			return json.dumps({"winner": "A" if left else "B", "reason": "better",
				"evidence_quality": "high", "confidence": 1})

	coordinator.route_runner = Runner()
	result = daily_blog.publication_workflow.run_typed_stage7(coordinator, value, stage6_result)

	assert result.artifact is not incumbent and coordinator.record.best_artifact_id == challenger.artifact_id

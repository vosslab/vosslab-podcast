"""Permanent offline proof for pure incumbent-preserving Stage 7 synthesis."""

# Standard Library
import dataclasses
from pathlib import Path

# PIP3 modules
import pytest

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.config
import daily_blog.daily_outline_workflow
import daily_blog.editorial_stage_config
import daily_blog.final_synthesis_config
import daily_blog.routes
import daily_blog.schema
import daily_blog.repository_contracts
import daily_blog.stage6
import daily_blog.stage7
import daily_blog.replication
import daily_blog.io_utils


_CONTEXT_LIMITS = {
	"commit_subject_chars": 120,
	"context_chars": 60000,
	"excerpt_chars": 1000,
}


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
	promoted = daily_blog.daily_outline_workflow.PromotedRanking(
		"ranking-1", ranking_hash, (story.content_hash,), ((story.content_hash, 100),),
		"Grounded ranking rationale.", ("review-1",),
	)
	return daily_blog.stage6.Stage6RecoverySources(
		(story,), (repository_outline,), (packet,), promoted, story.artifact_id,
	)


def _input(tmp_path: Path) -> daily_blog.stage6.Stage6Input:
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
	story = daily_blog.artifacts.RepoStory.create(packet.report_date, (packet,), "owner/repository",
		"Story <!-- evidence: " + item.evidence_id + " -->", (item.evidence_id,))
	outline: daily_blog.artifacts.DailyOutline = daily_blog.artifacts.DailyOutline.create(
		packet.report_date, (packet,), ("owner/repository",),
		"Outline <!-- evidence: " + item.evidence_id + " -->", (item.evidence_id,))
	return daily_blog.stage6.Stage6Input(
		str(tmp_path), str(tmp_path / packet.report_date / "post.md"), _recovery_sources(story, packet),
		daily_blog.stage6.build_stage6_publication_surface(
			outline, (story,), (packet,), _CONTEXT_LIMITS,
		),
	)


def _post(value: daily_blog.stage6.Stage6Input, title: str) -> daily_blog.artifacts.CompletePost:
	evidence_id = value.daily_outline.evidence_ids[0]
	introduction = (
		"I connected [owner/repository](https://github.com/owner/repository) to a small design "
		"decision and enjoyed seeing the boundary become clear. "
	) * 4
	detail = (
		"I followed the implementation through its useful constraint, the behavior it changed, "
		"and the next question worth testing with the grounded evidence in view. "
	) * 18
	return daily_blog.artifacts.CompletePost.create(value.report_date, value.packets,
		value.daily_outline.repositories, "# " + title + "\n\n" + introduction.strip()
		+ "<!-- evidence: " + evidence_id + " -->\n\n<!-- more -->\n\n## The useful boundary\n\n"
		+ detail.strip() + "<!-- evidence: " + evidence_id + " -->\n\n## Project coverage\n\n"
		+ "I recorded owner/repository in the evidence packet. <!-- evidence: " + evidence_id + " -->\n",
		value.daily_outline.evidence_ids,
		value.report_date, value.output_path)


def _stage7_input(
	tmp_path: Path,
) -> tuple[daily_blog.stage7.Stage7Input, daily_blog.artifacts.CompletePost]:
	value = _input(tmp_path)
	incumbent, alternative = _post(value, "INCUMBENT_MARK"), _post(value, "writer alternative")
	request = daily_blog.agents.RouteRequest("stage6-source", "stage6", daily_blog.editorial_stage_config.RoleRoute("writer", ("fixture",)),
		"prompt", str(tmp_path), input_hash="a" * 64, contract_version="v4")
	result: daily_blog.agents.AgentResult = daily_blog.agents.AgentResult(
		"writer", alternative.content, True, "", 1, 0, False,
		"writer", request.request_id, request.identity_sha256, daily_blog.io_utils.sha256_text(alternative.content))
	candidate = daily_blog.replication.ReplicatedCandidate(request, result, alternative,
		daily_blog.artifacts.evaluate_eligibility(alternative, value.packets, (value.output_root,)))
	incumbent_request = dataclasses.replace(request, request_id="stage6-incumbent", input_hash="b" * 64)
	incumbent_result = dataclasses.replace(result, request_id=incumbent_request.request_id,
		request_identity_sha256=incumbent_request.identity_sha256,
		text=incumbent.content, text_sha256=daily_blog.io_utils.sha256_text(incumbent.content))
	incumbent_candidate = daily_blog.replication.ReplicatedCandidate(incumbent_request, incumbent_result, incumbent,
		daily_blog.artifacts.evaluate_eligibility(incumbent, value.packets, (value.output_root,)))
	promotion = daily_blog.artifacts.SelectedPeer(incumbent, daily_blog.artifacts.CompletePost)
	stage6_result = daily_blog.stage6.Stage6Result(
		promotion=promotion,
		generation=daily_blog.replication.ReplicationResult(
			daily_blog.artifacts.CompletePost, (candidate, incumbent_candidate)),
		review=daily_blog.replication.CandidateSetReviewResult((), ()),
		reliability=daily_blog.replication.StepReliability(
			"stage6", "succeeded", 0, 0, 0, 0, 0, 0, incumbent.artifact_id, ()),
		editing=daily_blog.replication.ReplicationResult(daily_blog.artifacts.CompletePost, ()),
		step_reliability=(daily_blog.replication.StepReliability(
			"stage6", "succeeded", 0, 0, 0, 0, 0, 0, incumbent.artifact_id, ()),),
	)
	return daily_blog.stage7.Stage7Input(value, stage6_result), incumbent


#============================================
def test_stage7_retains_the_frozen_stage6_surface_but_uses_portable_model_identity(
	tmp_path: Path,
) -> None:
	"""One Stage-6 surface binds admission while relocated route cache keys stay semantic."""
	value, _incumbent = _stage7_input(tmp_path)
	surface = value.stage6_input.publication_surface
	identity = value.identity_dict()
	model_identity = value.model_identity_dict()

	assert identity["publication_surface_packet_id"] == surface.packet.packet_id
	assert identity["publication_surface_projection_id"] == surface.projection.projection_id
	assert "publication_surface_packet_id" not in model_identity
	assert "publication_surface_projection_id" not in model_identity


def _config(tmp_path: Path) -> daily_blog.config.DailyBlogConfig:
	stage = daily_blog.final_synthesis_config.FinalSynthesisConfig(synthesizer_count=2, reviewer_count=1,
		maximum_parallel_calls=2, route_retry_attempts=0,
		synthesis_route=daily_blog.editorial_stage_config.RoleRoute(
			"synthesis", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE),
		reviewer_route=daily_blog.editorial_stage_config.RoleRoute(
			"reviewer", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE))
	return daily_blog.config.DailyBlogConfig("settings", str(tmp_path), "owner", "America/Chicago", str(tmp_path),
		str(tmp_path / "mirrors"), (daily_blog.editorial_stage_config.RoleRoute("author", ("fixture",)),),
		daily_blog.editorial_stage_config.RoleRoute("referee", ("fixture",)), {}, {}, {"author_chars": 72000, "referee_chars": 88000},
		daily_blog.config.EditorialReliabilityConfig(2, 1, 1), final_synthesis=stage)


class _Runner:
	def __init__(self, value: daily_blog.stage7.Stage7Input, winner: bool = True,
		fail_synthesis: bool = False, synthesis_text: str | None = None) -> None:
		self.value, self.winner, self.fail_synthesis = value, winner, fail_synthesis
		self.synthesis_text, self.prompts, self.calls = synthesis_text, [], []
	def run(self, route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, _directory: str) -> str:
		self.prompts.append(prompt)
		self.calls.append(route.name)
		if route.name == "synthesis":
			if self.fail_synthesis:
				raise daily_blog.routes.EditorialRouteTimeout("offline")
			if self.synthesis_text is not None:
				return self.synthesis_text
			return _post(self.value.stage6_input, "CHALLENGER_MARK").content
		if "# CHALLENGER_MARK" in prompt:
			if "# INCUMBENT_MARK" not in prompt:
				return '{"winner":"A","reason":"peer","evidence_quality":"high","confidence":1}'
			left_challenger = prompt.index("# CHALLENGER_MARK") < prompt.index("# INCUMBENT_MARK")
			selected_challenger = left_challenger if self.winner else not left_challenger
			winner = "A" if selected_challenger else "B"
			return '{"winner":"' + winner + '","reason":"better","evidence_quality":"high","confidence":1}'
		return '{"winner":"A","reason":"keep","evidence_quality":"high","confidence":1}'



def test_stage7_total_synthesis_loss_preserves_exact_incumbent_object_and_hash(tmp_path: Path) -> None:
	"""Route loss is editorial degradation, not permission to reconstruct an incumbent."""
	value, incumbent = _stage7_input(tmp_path)
	result = daily_blog.stage7.run_stage7(value, "stage7", _config(tmp_path), daily_blog.agents.RouteBudget(2),
		_Runner(value, fail_synthesis=True))
	assert result.artifact is incumbent and not result.synthesis_won



def test_stage7_input_rejects_forged_stage6_lineage_before_routes(tmp_path: Path) -> None:
	"""A promoted post must be the exact eligible Stage 6 generation/editing object."""
	value, incumbent = _stage7_input(tmp_path)
	forged = _post(value.stage6_input, "FORGED")
	forged_result = dataclasses.replace(value.stage6_result,
		promotion=daily_blog.artifacts.SelectedPeer(forged, daily_blog.artifacts.CompletePost))
	with pytest.raises(RuntimeError, match="absent from eligible Stage 6 lineage"):
		daily_blog.stage7.Stage7Input(value.stage6_input, forged_result)
	assert incumbent is value.incumbent


@pytest.mark.parametrize("response", (
	"", "# no evidence\n", "# unknown\n<!-- evidence: evidence-unknown -->\n",
))
def test_stage7_ineligible_synthesis_is_degradation_and_preserves_exact_incumbent(
	tmp_path: Path, response: str,
) -> None:
	"""Malformed or ungrounded model output is a failed replica, not a pipeline fault."""
	value, incumbent = _stage7_input(tmp_path)
	result = daily_blog.stage7.run_stage7(value, "stage7", _config(tmp_path), daily_blog.agents.RouteBudget(2),
		_Runner(value, synthesis_text=response))
	assert result.artifact is incumbent and not result.synthesis_won

def test_stage7_trusted_scope_rejection_preserves_incumbent(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Defense-in-depth metadata rejection treats accepted-parser defects as degradation."""
	value, incumbent = _stage7_input(tmp_path)
	candidate = daily_blog.artifacts.CompletePost.create(value.report_date, value.stage6_input.packets,
		value.stage6_input.daily_outline.repositories, _post(value.stage6_input, "OUTSIDE_ROOT").content,
		value.stage6_input.daily_outline.evidence_ids, value.report_date,
		str(tmp_path.parent / "outside" / value.report_date / "post.md"))
	monkeypatch.setattr(daily_blog.stage7.daily_blog.final_synthesis_prompts,
		"parse_final_synthesis_complete_post", lambda *_args: candidate)
	runner = _Runner(value)
	result = daily_blog.stage7.run_stage7(value, "stage7", _config(tmp_path),
		daily_blog.agents.RouteBudget(2), runner)
	assert result.artifact is incumbent

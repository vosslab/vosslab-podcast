"""Focused offline tests for the Stage 6 writer recovery adapter."""

# Standard Library
import pathlib

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.config
import daily_blog.editorial_stage_config
import daily_blog.routes
import daily_blog.schema
import daily_blog.stage6


#============================================
def _packet() -> daily_blog.schema.EvidencePacket:
	"""Return one authoritative packet for a single whole-post recovery route."""
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/recovery", "a" * 40, "CHANGELOG.md", "b" * 40,
		"Grounded recovery change.", "git show",
	)
	return daily_blog.schema.EvidencePacket.create(
		"2026-08-29", "America/Chicago", True, {}, [], [], [item],
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
	return daily_blog.stage6.Stage6Input(
		outline, (story,), (packet,), str(tmp_path),
		str(tmp_path / packet.report_date / "post.md"),
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
	return "# Recovery\n\nGrounded. <!-- evidence: " + value.daily_outline.evidence_ids[0] + " -->\n"


#============================================
def test_writer_recovery_returns_eligible_whole_post(tmp_path: pathlib.Path) -> None:
	"""One successful recovery writer returns an eligible whole grounded post."""
	value, budget = _value(tmp_path), daily_blog.agents.RouteBudget(4, 1)
	class Runner:
		def run(self, _route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			return _post(value)
	attempt = daily_blog.stage6.recover_writer_complete_post(
		value, "run-1", _config(tmp_path), budget, Runner(),
	)

	assert isinstance(attempt.outcome, daily_blog.artifacts.SelectedPeer)
	assert isinstance(attempt.outcome.artifact, daily_blog.artifacts.CompletePost)


#============================================
def test_writer_recovery_returns_no_artifact_for_a_route_outage(
		tmp_path: pathlib.Path,
) -> None:
	"""An exhausted route produces no recovery artifact."""
	value = _value(tmp_path)
	class Runner:
		def run(self, _route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			raise daily_blog.routes.EditorialRouteTimeout("fixture")
	attempt = daily_blog.stage6.recover_writer_complete_post(
		value, "run-2", _config(tmp_path), daily_blog.agents.RouteBudget(4, 1), Runner(),
	)

	assert isinstance(attempt.outcome, daily_blog.artifacts.NoArtifact)

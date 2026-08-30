"""Permanent offline tests for the typed Stage 6 complete-post boundary."""

# Standard Library
from pathlib import Path

# PIP3 modules
import pytest

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.config
import daily_blog.editorial_stage_config
import daily_blog.editorial
import daily_blog.routes
import daily_blog.schema
import daily_blog.stage6


#============================================
def packet() -> daily_blog.schema.EvidencePacket:
	"""Return one exact authoritative packet for the Stage 6 contract."""
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/project", "a" * 40, "docs/CHANGELOG.md", "b" * 40,
		"Grounded change.", "git show",
	)
	return daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item],
	)


#============================================
def complete_post(
	value: daily_blog.stage6.Stage6Input, suffix: str,
) -> daily_blog.artifacts.CompletePost:
	"""Build an exact eligible incumbent or expected selected post."""
	return daily_blog.artifacts.CompletePost.create(
		value.report_date, value.packets, value.daily_outline.repositories, post(value, suffix),
		value.daily_outline.evidence_ids, value.report_date, value.output_path,
	)


#============================================
def input_value(tmp_path: Path) -> daily_blog.stage6.Stage6Input:
	"""Build the only permanent Stage 6 upstream artifact boundary."""
	source = packet()
	evidence_id = source.items[0].evidence_id
	story = daily_blog.artifacts.RepoStory.create(
		source.report_date, (source,), "vosslab/project",
		"Story <!-- evidence: " + evidence_id + " -->", (evidence_id,),
	)
	outline = daily_blog.artifacts.DailyOutline.create(
		source.report_date, (source,), ("vosslab/project",),
		"Outline <!-- evidence: " + evidence_id + " -->", (evidence_id,),
	)
	return daily_blog.stage6.Stage6Input(
		outline, (story,), (source,), str(tmp_path), str(tmp_path / "2026-08-23" / "post.md"),
	)


#============================================
def config(tmp_path: Path, routes: int = 2) -> daily_blog.config.DailyBlogConfig:
	"""Return a small exact route configuration with capacity for balanced review."""
	reliability = daily_blog.config.EditorialReliabilityConfig(2, 1, 2, 4, 0)
	complete_post = daily_blog.editorial_stage_config.CompletePostConfig(
		writer_count=2, editor_count=2, reviewer_count=1, maximum_parallel_calls=2,
		max_route_calls=44, route_retry_attempts=0,
		writer_route=daily_blog.editorial_stage_config.RoleRoute("writer", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE),
		editor_route=daily_blog.editorial_stage_config.RoleRoute("editor", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE),
		reviewer_route=daily_blog.editorial_stage_config.RoleRoute("referee", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE),
	)
	return daily_blog.config.DailyBlogConfig(
		"settings", str(tmp_path), "owner", "America/Chicago", str(tmp_path), str(tmp_path / "mirrors"),
		(), (), tuple(daily_blog.editorial_stage_config.RoleRoute(
			"author-" + str(index), daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE,
		) for index in range(routes)), daily_blog.editorial_stage_config.RoleRoute(
			"referee", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE,
		),
		{}, {}, {"author_chars": 72000, "referee_chars": 88000}, reliability,
		complete_post=complete_post,
	)


#============================================
def post(value: daily_blog.stage6.Stage6Input, suffix: str = "one") -> str:
	"""Return one minimally grounded writer response; no local prose assembly occurs in code."""
	return (
		"# " + suffix + "\n\nA grounded post. <!-- evidence: "
		+ value.daily_outline.evidence_ids[0] + " -->\n"
	)


#============================================
#============================================
def test_stage6_partial_writer_failure_preserves_eligible_complete_post(tmp_path: Path) -> None:
	"""One author route failing leaves its independently generated post promoted."""
	value = input_value(tmp_path)
	class Runner:
		def run(self, route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, _directory: str) -> str:
			if route.name == "writer" and "-writer-2" in prompt:
				raise daily_blog.routes.EditorialRouteTimeout("offline")
			return post(value)
	result = daily_blog.stage6.run_stage6(
		value, "partial", config(tmp_path), daily_blog.agents.RouteBudget(50, 2), Runner(),
	)
	assert type(result.artifact) is daily_blog.artifacts.CompletePost
	assert any(candidate.failure == "timeout" for candidate in result.generation.candidates)


#============================================
def test_stage6_balanced_reviewer_loss_preserves_a_peer(tmp_path: Path) -> None:
	"""Two generated posts survive total referee loss through generic promotion."""
	value = input_value(tmp_path)
	class Runner:
		def run(self, route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			if route.name == "referee":
				raise daily_blog.routes.EditorialRouteTimeout("offline")
			return post(value, route.name)
	result = daily_blog.stage6.run_stage6(
		value, "review-loss", config(tmp_path), daily_blog.agents.RouteBudget(50, 2), Runner(),
	)
	assert type(result.artifact) is daily_blog.artifacts.CompletePost


#============================================
def test_stage6_preserves_a_separate_eligible_incumbent(tmp_path: Path) -> None:
	"""An eligible incumbent remains a same-rung candidate when writers all fail."""
	value = input_value(tmp_path)
	incumbent = daily_blog.artifacts.CompletePost.create(
		value.report_date, value.packets, value.daily_outline.repositories, post(value, "incumbent"),
		value.daily_outline.evidence_ids, value.report_date, value.output_path,
	)
	class Runner:
		def run(self, _route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			raise daily_blog.routes.EditorialRouteTimeout("offline")
	result = daily_blog.stage6.run_stage6(
		value, "incumbent", config(tmp_path), daily_blog.agents.RouteBudget(50, 2), Runner(),
		incumbent=incumbent,
	)
	assert isinstance(result.promotion, daily_blog.artifacts.PreservedArtifact)
	assert result.artifact == incumbent


#============================================
def test_stage6_editor_can_improve_an_incumbent_after_total_writer_loss(tmp_path: Path) -> None:
	"""An editor receives the eligible incumbent when every writer route fails."""
	value = input_value(tmp_path)
	incumbent = complete_post(value, "incumbent")
	class Runner:
		reviewer_winners = iter(("A", "B"))

		def run(self, route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			if route.name == "writer":
				raise daily_blog.routes.EditorialRouteTimeout("offline")
			if route.name == "editor":
				return post(value, "editor-improvement")
			winner = next(self.reviewer_winners)
			return '{"winner":"' + winner + '","reason":"grounded","evidence_quality":"high","confidence":1}'
	result = daily_blog.stage6.run_stage6(
		value, "incumbent-editor", config(tmp_path), daily_blog.agents.RouteBudget(50, 2), Runner(),
		incumbent=incumbent,
	)
	assert type(result.promotion) is daily_blog.artifacts.SelectedPeer
	assert result.artifact == complete_post(value, "editor-improvement")


#============================================
def test_stage6_no_eligible_writer_response_is_a_typed_no_artifact(tmp_path: Path) -> None:
	"""Ineligible route responses are a diagnosed editorial failure, never assembled prose."""
	value = input_value(tmp_path)
	class Runner:
		def run(self, _route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			return "# ungrounded\n"
	result = daily_blog.stage6.run_stage6(
		value, "none", config(tmp_path), daily_blog.agents.RouteBudget(50, 2), Runner(),
	)
	assert isinstance(result.promotion, daily_blog.artifacts.NoArtifact)
	assert result.promotion.reason == "no_eligible_generation"


#============================================
#============================================
def test_stage6_propagates_non_referee_parser_defects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""Only bounded verdict syntax errors are repairable; implementation defects remain faults."""
	value = input_value(tmp_path)
	def broken_parser(_text: str, _allowed: set[str]) -> dict:
		raise RuntimeError("parser defect")
	monkeypatch.setattr(daily_blog.editorial, "parse_referee_verdict", broken_parser)
	class Runner:
		def run(self, route: daily_blog.editorial_stage_config.RoleRoute, _prompt: str, _directory: str) -> str:
			if route.name in {"writer", "editor"}:
				return post(value, route.name)
			return '{"winner":"A","reason":"grounded","evidence_quality":"high","confidence":1}'
	with pytest.raises(RuntimeError, match="parser defect"):
		daily_blog.stage6.run_stage6(
			value, "parser-defect", config(tmp_path), daily_blog.agents.RouteBudget(50, 2), Runner(),
		)

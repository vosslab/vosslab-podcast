"""Offline failure and provenance contracts for Stage 4 repository stories."""

# Standard Library
import os
import threading

# PIP3 modules
import pytest

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.editorial_stage_config
import daily_blog.io_utils
import daily_blog.repository_story_workflow
import daily_blog.routes
import daily_blog.schema


#============================================
def packet(repository: str = "vosslab/project") -> daily_blog.schema.EvidencePacket:
	"""Return one repository-isolated authoritative packet."""
	item = daily_blog.schema.EvidenceItem.create("dated_changelog", repository, "a" * 40, "CHANGELOG.md",
		"b" * 40, "Project change.", "git show")
	return daily_blog.schema.EvidencePacket.create("2026-08-29", "America/Chicago", True, {}, [], [], [item])


#============================================
def mixed_packet() -> daily_blog.schema.EvidencePacket:
	"""Return valid packet bytes that deliberately contain an unrelated repository."""
	first = packet().items[0]
	second = daily_blog.schema.EvidenceItem.create("dated_changelog", "vosslab/other", "c" * 40,
		"CHANGELOG.md", "d" * 40, "Other project change.", "git show")
	return daily_blog.schema.EvidencePacket.create("2026-08-29", "America/Chicago", True, {}, [], [],
		[first, second])


#============================================
def outline(source: daily_blog.schema.EvidencePacket) -> daily_blog.artifacts.RepoOutline:
	"""Return an exact eligible promoted outline."""
	return daily_blog.artifacts.RepoOutline.create(source.report_date, (source,), source.items[0].repository,
		"# Outline\n\nGrounded work. <!-- evidence: " + source.items[0].evidence_id + " -->\n",
		(source.items[0].evidence_id,))


#============================================
def value(
	source: daily_blog.schema.EvidencePacket | None = None,
) -> daily_blog.repository_story_workflow.RepositoryStoryInput:
	"""Return one physical Stage 4 evidence boundary."""
	source = source or packet()
	return daily_blog.repository_story_workflow.RepositoryStoryInput(
		outline(source), (source,), os.path.realpath(os.getcwd()),
	)


#============================================
def config(reviewers: int = 1, **changes: object) -> daily_blog.editorial_stage_config.RepositoryStoryConfig:
	"""Return bounded independent Stage 4 roles for deterministic fixtures."""
	values: dict[str, object] = {"reviewer_count": reviewers, "maximum_parallel_calls": min(16, reviewers * 2),
		"route_retry_attempts": 0}
	values.update(changes)
	return daily_blog.editorial_stage_config.RepositoryStoryConfig(**values)


#============================================
def rubric() -> tuple[str, str]:
	"""Return a caller-selected rubric and exact external identity."""
	text = "# Repository story rubric\n\nPrefer grounded maker substance.\n"
	return text, daily_blog.io_utils.sha256_text(text)


#============================================
def story(source: daily_blog.repository_story_workflow.RepositoryStoryInput, name: str) -> str:
	"""Return one whole mechanically grounded story response."""
	return "# " + name + "\n\nGrounded work. <!-- evidence: " + source.packets[0].items[0].evidence_id + " -->\n"


#============================================
def verdict(winner: str) -> str:
	"""Return one strict anonymous comparison verdict."""
	return '{"winner":"' + winner + '","reason":"grounded","evidence_quality":"high","confidence":1}'


class Runner:
	"""Thread-safe role queue fake retaining every exact route request."""

	#============================================
	def __init__(self, responses: dict[str, list[object]]) -> None:
		self.responses = responses
		self.requests: list[tuple[str, str, str]] = []
		self.lock = threading.Lock()

	#============================================
	def run(self, route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, working_directory: str) -> str:
		with self.lock:
			self.requests.append((route.name, prompt, working_directory))
			response = self.responses[route.name].pop(0)
		if isinstance(response, BaseException):
			raise response
		if type(response) is not str:
			raise RuntimeError("unsupported response type")
		return response


#============================================
def run(
	source: daily_blog.repository_story_workflow.RepositoryStoryInput,
	runner: Runner, stage_config: daily_blog.editorial_stage_config.RepositoryStoryConfig | None = None,
	**kwargs: object,
) -> daily_blog.repository_story_workflow.RepositoryStoryResult:
	"""Run one fixture with a generously shared, explicitly supplied budget."""
	text, digest = rubric()
	return daily_blog.repository_story_workflow.run_repository_story(source, stage_config or config(),
		daily_blog.agents.RouteBudget(200, 16), runner, rubric=text, rubric_sha256=digest, **kwargs)


#============================================
def test_writers_editors_review_and_promote_whole_eligible_story() -> None:
	"""Stage 4 promotes one complete grounded repository story."""
	source = value()
	runner = Runner({
		"repository_story_writer": [story(source, "writer one"), story(source, "writer two")],
		"repository_story_editor": [story(source, "editor one"), story(source, "editor two")],
		"repository_story_reviewer": [verdict("A"), verdict("B")],
	})
	result = run(source, runner)

	assert type(result.artifact) is daily_blog.artifacts.RepoStory


#============================================
def test_bad_rubric_digest_blocks_all_routes() -> None:
	"""A rubric identity fault is rejected before model execution."""
	source = value()
	runner = Runner({"repository_story_writer": [], "repository_story_editor": [], "repository_story_reviewer": []})
	text, digest = rubric()
	with pytest.raises(RuntimeError):
		daily_blog.repository_story_workflow.run_repository_story(source, config(), daily_blog.agents.RouteBudget(10), runner,
			rubric=text, rubric_sha256="0" * 64)
	assert not runner.requests


#============================================
def test_input_rejects_wrong_repository_packet() -> None:
	"""Stage 4 rejects an outline packet from a different repository."""
	source = value()
	wrong_packet = packet("vosslab/other")
	with pytest.raises(RuntimeError):
		daily_blog.repository_story_workflow.RepositoryStoryInput(source.outline, (wrong_packet,), source.working_directory)


#============================================
def test_input_rejects_mixed_repository_packet() -> None:
	"""Stage 4 rejects evidence packets that mix repository identities."""
	source = value()
	mixed = mixed_packet()
	with pytest.raises(RuntimeError):
		daily_blog.repository_story_workflow.RepositoryStoryInput(
			outline(mixed), (mixed,), source.working_directory,
		)


#============================================
def test_partial_writer_editor_and_reviewer_loss_degrades_without_assembly() -> None:
	"""Ordinary route loss preserves eligible whole peer work on the same rung."""
	source = value()
	runner = Runner({
		"repository_story_writer": [daily_blog.routes.EditorialRouteProcessError("x"), story(source, "writer")],
		"repository_story_editor": [daily_blog.routes.EditorialRouteProcessError("x")] * 2,
		"repository_story_reviewer": [daily_blog.routes.EditorialRouteProcessError("x")] * 2,
	})
	result = run(source, runner)

	assert type(result.artifact) is daily_blog.artifacts.RepoStory
	assert isinstance(result.promotion, daily_blog.artifacts.DegradedPromotion)


#============================================
def test_ineligible_editor_filter_preserves_incumbent_without_improvement_proof() -> None:
	"""An eligible incumbent is retained when no eligible editorial peer improves it."""
	source = value()
	incumbent = daily_blog.artifacts.RepoStory.create(source.report_date, source.packets, source.repository,
		story(source, "incumbent"), (source.packets[0].items[0].evidence_id,))
	runner = Runner({
		"repository_story_writer": [story(source, "writer one"), story(source, "writer two")],
		"repository_story_editor": ["# bad\n", "# also bad\n"],
		"repository_story_reviewer": [daily_blog.routes.EditorialRouteProcessError("x")] * 6,
	})
	result = run(source, runner, config(), incumbent=incumbent)

	assert isinstance(result.promotion, daily_blog.artifacts.PreservedArtifact)
	assert result.artifact == incumbent


#============================================
def test_no_eligible_generation_returns_typed_no_artifact() -> None:
	"""Ordinary ineligibility produces a typed editorial degradation."""
	source = value()
	runner = Runner({
		"repository_story_writer": ["# bad\n", "# bad\n"],
		"repository_story_editor": [], "repository_story_reviewer": [],
	})
	result = run(source, runner)
	assert isinstance(result.promotion, daily_blog.artifacts.NoArtifact)


#============================================
def test_implementation_defect_propagates() -> None:
	"""Unexpected runner defects remain pipeline faults rather than editorial loss."""
	source = value()
	defective = Runner({
		"repository_story_writer": [object(), story(source, "x")],
		"repository_story_editor": [], "repository_story_reviewer": [],
	})
	with pytest.raises(RuntimeError):
		run(source, defective)

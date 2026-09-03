"""Offline Stage 5 fault behavior at the serial cache write boundary."""

# Standard Library
import json
from pathlib import Path

# PIP3 modules
import pytest

# local repo modules
import daily_blog.artifacts
import daily_blog.config
import daily_blog.daily_outline_workflow
import daily_blog.editorial_stage_config
import daily_blog.orchestrator
import daily_blog.projection
import daily_blog.publication_workflow
import daily_blog.recovery
import daily_blog.repository_contracts
import daily_blog.run_contracts
import daily_blog.schema


def _activity(repository: str, marker: str) -> daily_blog.schema.RepositoryActivity:
	"""Return one active repository record for the bounded prompt frame."""
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
	"""Build a real survivor-scoped model frame for Stage 5 fault behavior."""
	limits = {"context_chars": 60000, "excerpt_chars": 600, "commit_subject_chars": 120}
	return daily_blog.projection.build_bounded_evidence_context(packets, limits, limits["context_chars"])


#============================================
def _input(root: Path) -> daily_blog.daily_outline_workflow.DailyOutlineInput:
	"""Build two independent repository artifacts with one packet each."""
	packets = []
	stories = []
	outlines = []
	for index, repository in enumerate(("owner/alpha", "owner/beta")):
		item = daily_blog.schema.EvidenceItem.create(
			"dated_changelog", repository, chr(97 + index) * 40, "CHANGELOG.md",
			chr(99 + index) * 40, "Grounded work.", "git show",
		)
		packet = daily_blog.schema.EvidencePacket.create(
			"2026-08-29", "America/Chicago", True, {}, [], [_activity(repository, chr(97 + index))], [item],
		)
		packets.append(packet)
		stories.append(daily_blog.artifacts.RepoStory.create(
			packet.report_date, (packet,), repository,
			"Story <!-- evidence: " + item.evidence_id + " -->", (item.evidence_id,),
		))
		outlines.append(daily_blog.artifacts.RepoOutline.create(
			packet.report_date, (packet,), repository,
			"Outline <!-- evidence: " + item.evidence_id + " -->", (item.evidence_id,),
		))
	return daily_blog.daily_outline_workflow.DailyOutlineInput(
		tuple(stories), tuple(outlines), tuple(packets), _context(tuple(packets)), str(root),
	)


#============================================
def _config(root: Path) -> daily_blog.config.DailyBlogConfig:
	"""Use explicit bounded Stage 5 routes and one disposable durable cache."""
	command = daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE
	route = daily_blog.editorial_stage_config.RoleRoute("fixture", command)
	daily_outline = daily_blog.editorial_stage_config.DailyOutlineConfig(
		ranker_count=2, outline_writer_count=2, reviewer_count=1,
		maximum_parallel_calls=2, route_retry_attempts=0,
		ranking_route=daily_blog.editorial_stage_config.RoleRoute("stage5_ranking", command),
		outline_writer_route=daily_blog.editorial_stage_config.RoleRoute("stage5_writer", command),
		outline_reviewer_route=daily_blog.editorial_stage_config.RoleRoute("stage5_reviewer", command),
	)
	return daily_blog.config.DailyBlogConfig(
		"settings.yaml", str(root), "owner", "America/Chicago", str(root),
		str(root / "mirrors"), (route,), route, {}, {}, {},
		daily_blog.config.EditorialReliabilityConfig(2, 1, 1, 16),
		daily_outline=daily_outline,
	)


#============================================
def _coordinator(
	root: Path, value: daily_blog.daily_outline_workflow.DailyOutlineInput,
) -> daily_blog.orchestrator.DailyPublicationOrchestrator:
	"""Advance a disposable run to the real Stage 5 boundary."""
	coordinator = daily_blog.orchestrator.DailyPublicationOrchestrator(
		_config(root), value.report_date,
	)
	for phase in daily_blog.run_contracts.LEGAL_PHASES:
		if phase == "stage5_daily_outline":
			break
		coordinator._start(phase, {"fixture": phase})
		coordinator._complete(phase, {"fixture": phase})
	return coordinator


class _TerminalRunner:
	"""Return accepted ranking work followed by ineligible outline drafts."""

	#============================================
	def __init__(self, value: daily_blog.daily_outline_workflow.DailyOutlineInput) -> None:
		self.calls: list[str] = []
		self._ranking = json.dumps({
			"artifact_ids": list(value.story_ranking_aliases.aliases),
			"scores": {item: 90 for item in value.story_ranking_aliases.aliases},
			"rationale": "Grounded priority.",
		})

	#============================================
	def run(
		self, route: daily_blog.editorial_stage_config.RoleRoute,
		_prompt: str, _working_directory: str,
	) -> str:
		self.calls.append(route.name)
		if route.name == "stage5_ranking":
			return self._ranking
		if route.name == "stage5_reviewer":
			return '{"decision":"ACCEPT","score":90,"reason":"grounded"}'
		return "# Outline without the required evidence scope\n"


#============================================
def test_stage5_terminal_fault_reuses_admitted_ranking_work_on_rerun(tmp_path: Path) -> None:
	"""A terminal no-outline fault retains eligible upstream route work for reruns."""
	root = tmp_path / "output"
	root.mkdir()
	value = _input(root)
	first = _TerminalRunner(value)
	first_coordinator = _coordinator(root, value)
	first_coordinator.route_runner = first

	with pytest.raises(daily_blog.recovery.PipelineFaultError):
		daily_blog.publication_workflow.run_typed_stage5(first_coordinator, value)

	second = _TerminalRunner(value)
	second_coordinator = _coordinator(root, value)
	second_coordinator.route_runner = second
	with pytest.raises(daily_blog.recovery.PipelineFaultError):
		daily_blog.publication_workflow.run_typed_stage5(second_coordinator, value)

	assert "stage5_ranking" in first.calls
	assert "stage5_ranking" not in second.calls

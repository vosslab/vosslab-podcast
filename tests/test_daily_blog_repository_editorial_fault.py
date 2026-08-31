"""Offline behavior for serial repository-editorial acceptance."""

# Standard Library
import dataclasses
import threading
from pathlib import Path

# PIP3 modules
import pytest

# local repo modules
import daily_blog.config
import daily_blog.editorial_stage_config
import daily_blog.editorial
import daily_blog.io_utils
import daily_blog.locks
import daily_blog.multi_repository_coordinator
import daily_blog.recovery
import daily_blog.repository_contracts
import daily_blog.repository_editorial_workflow
import daily_blog.route_cache
import daily_blog.run_contracts
import daily_blog.schema


#============================================
def _activity(repository: str, marker: str) -> daily_blog.schema.RepositoryActivity:
	"""Return one immutable repository activity record."""
	commit = daily_blog.schema.CommitActivity(
		marker * 40, (), "Maker", "maker@example.com", "2026-08-29T12:00:00Z",
		"2026-08-29T12:00:00Z", "Grounded work.",
	)
	creation = daily_blog.repository_contracts.RepositoryLifecycleEvent(
		"repository_created", "2020-01-01T00:00:00Z", False, "github_owner_roster",
	)
	return daily_blog.schema.RepositoryActivity(
		repository, "https://github.com/" + repository, "/cache/" + repository.replace("/", "_"),
		marker * 40, (commit,), (daily_blog.schema.RevisionRange("", marker * 40),),
		(marker * 40,), False, (creation,),
	)


#============================================
def _packet() -> daily_blog.schema.EvidencePacket:
	"""Build two frozen repository scopes with grounded evidence."""
	activities = (_activity("owner/alpha", "a"), _activity("owner/beta", "b"))
	items = tuple(daily_blog.schema.EvidenceItem.create(
		"dated_changelog", activity.repository, activity.default_revision, "CHANGELOG.md",
		activity.default_revision, "Grounded work in " + activity.repository + ".", "git show",
	) for activity in activities)
	return daily_blog.schema.EvidencePacket.create(
		"2026-08-29", "America/Chicago", True, {},
		[{"repository": activity.repository, "object_available": True} for activity in activities],
		activities, items,
	)


#============================================
def _config(tmp_path: Path) -> daily_blog.config.DailyBlogConfig:
	"""Use compact explicit routes and a disposable physical output root."""
	route = daily_blog.editorial_stage_config.RoleRoute("fixture", ("fixture",))
	return daily_blog.config.DailyBlogConfig(
		"settings.yaml", str(tmp_path), "owner", "America/Chicago", str(tmp_path),
		str(tmp_path / "mirrors"), (), (), (route,), route, {},
		{"context_chars": 8000, "excerpt_chars": 1000, "commit_subject_chars": 120},
		{"author_chars": 8000, "referee_chars": 8000},
		daily_blog.config.EditorialReliabilityConfig(2, 1, 1, 8),
		repository_outline=daily_blog.editorial_stage_config.RepositoryOutlineConfig(
			generator_count=2, merger_count=2, reviewer_count=1, maximum_parallel_calls=2,
			route_retry_attempts=0,
		),
		repository_story=daily_blog.editorial_stage_config.RepositoryStoryConfig(
			writer_count=2, editor_count=2, reviewer_count=1, maximum_parallel_calls=2,
			route_retry_attempts=0,
		),
	)


class _Runner:
	"""Thread-safe deterministic route adapter with optional Stage-4 loss."""

	#============================================
	def __init__(self, packet: daily_blog.schema.EvidencePacket, lose_stories: bool = False) -> None:
		self._evidence = {item.repository: item.evidence_id for item in packet.items}
		self._lose_stories = lose_stories
		self._lock = threading.Lock()

	#============================================
	def run(self, route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, _working_directory: str) -> str:
		with self._lock:
			if self._lose_stories and route.name.startswith("repository_story_"):
				return ""
			if route.name.endswith("reviewer"):
				return '{"winner":"A","reason":"grounded","evidence_quality":"high","confidence":1}'
			repository = "owner/alpha" if "owner/alpha" in prompt else "owner/beta"
			return "# Grounded\n\nEvidence-backed work. <!-- evidence: " + self._evidence[repository] + " -->\n"


#============================================
def _coordinator(
	tmp_path: Path,
	packet: daily_blog.schema.EvidencePacket,
	runner: _Runner,
) -> tuple[
	daily_blog.repository_editorial_workflow.RepositoryEditorialCoordinator,
	dict[str, dict[str, object]],
	list[tuple[daily_blog.replication.StepReliability, daily_blog.run_contracts.IncumbentTransition]],
	list[object],
]:
	"""Bind real cache and prompt identity with inline serial lifecycle fakes."""
	artifacts: dict[str, dict[str, object]] = {}
	summaries: list[tuple[
		daily_blog.replication.StepReliability,
		daily_blog.run_contracts.IncumbentTransition,
	]] = []
	completed: list[object] = []
	dependencies = daily_blog.repository_editorial_workflow.RepositoryEditorialDependencies(
		_config(tmp_path), packet.report_date, daily_blog.editorial.load_prompt_contract_snapshot(), runner,
		daily_blog.route_cache.RouteResultCache(daily_blog.locks.PhaseCache(str(tmp_path / "cache"))),
		str(tmp_path), lambda _phase, _value: "started",
		lambda _phase, value, _reused: completed.append(value) or "completed",
		lambda summary, transition: summaries.append((summary, transition)),
		lambda name, value: artifacts.setdefault(name, value) and name,
	)
	return daily_blog.repository_editorial_workflow.RepositoryEditorialCoordinator(dependencies), artifacts, summaries, completed


#============================================
def _assert_complete_projected_provenance(
	payload: dict[str, object], packet: daily_blog.schema.EvidencePacket,
) -> None:
	"""Check terminal storage retains every frozen local evidence projection."""
	projected = daily_blog.multi_repository_coordinator.project_repository_packets(packet)
	expected = {
		item.packet_id: (
			daily_blog.io_utils.hash_value(item.content_dict()),
			frozenset(value.evidence_id for value in item.items),
		)
		for item in projected
	}
	observed = {
		item["packet_id"]: (item["content_sha256"], frozenset(item["evidence_refs"]))
		for item in payload["packets"]
	}
	expected_repositories = {
		item.activity[0].repository for item in projected
	}
	assert observed == expected
	assert frozenset(payload["allowed_repositories"]) == expected_repositories
	assert b"injected worker defect" not in daily_blog.io_utils.canonical_json_bytes(payload)


#============================================
def _worker_pipeline_fault(
	category: daily_blog.recovery.TerminalFaultCategory,
) -> daily_blog.recovery.PipelineFaultError:
	"""Build a typed upstream worker fault from its real route outcome class."""
	if category is daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION:
		observation = daily_blog.recovery.GenerationObservation("upstream_route", 1, 1, ())
	else:
		observation = daily_blog.recovery.GenerationObservation(
			"upstream_route", 0, 0, (), category,
		)
	fault = daily_blog.recovery.PipelineFault(category, 0, "", "", (observation,))
	return daily_blog.recovery.PipelineFaultError(fault, "0" * 64)


#============================================
def test_eligible_paired_survivor_returns_stage5_input_and_only_observes_incumbent(tmp_path: Path) -> None:
	"""A complete grounded repository join becomes a typed Stage-5 handoff."""
	packet = _packet()
	coordinator, artifacts, summaries, completed = _coordinator(tmp_path, packet, _Runner(packet))

	result = coordinator.run(packet)

	assert (
		result.stage5_input.report_date == packet.report_date
		and result.stage5_input.repositories
		and artifacts["repository_editorial.json"]["survivor_packet_ids"]
		and completed
		and summaries
		and all(type(transition) is daily_blog.run_contracts.ObserveIncumbent for _summary, transition in summaries)
	)


#============================================
def test_unpaired_repository_fault_retains_strongest_grounded_outline(tmp_path: Path) -> None:
	"""A failed pairing records bounded retained evidence without a Stage-5 value."""
	packet = _packet()
	coordinator, artifacts, summaries, completed = _coordinator(tmp_path, packet, _Runner(packet, lose_stories=True))

	with pytest.raises(daily_blog.recovery.PipelineFaultError) as raised:
		coordinator.run(packet)

	fault = raised.value.fault
	recovery = artifacts["recovery_fault.json"]
	assert (
		raised.value.category is daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION
		and fault.strongest_artifact_type == "RepoOutline"
		and recovery["retained_artifact_id"] == fault.strongest_artifact_id
		and recovery["retained_artifact_id"] in recovery["promoted_artifact_ids"]
		and summaries
		and not completed
	)


#============================================
def test_typed_local_failure_degrades_repository_editorial_without_blocking_a_surviving_pair(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""One failed future records bounded diagnostics and hands survivors to Stage 5."""
	packet = _packet()
	coordinator, artifacts, summaries, completed = _coordinator(tmp_path, packet, _Runner(packet))
	original = daily_blog.multi_repository_coordinator.run_repository_editorial

	def terminal_join(*args) -> daily_blog.multi_repository_coordinator.RepositoryEditorialJoin:
		return dataclasses.replace(
			original(*args),
			terminal_fault=daily_blog.recovery.TerminalFaultCategory.CONFIGURATION,
		)

	monkeypatch.setattr(daily_blog.multi_repository_coordinator, "run_repository_editorial", terminal_join)
	result = coordinator.run(packet)

	assert (
		result.stage5_input.repositories == ("owner/alpha", "owner/beta")
		and artifacts["repository_editorial.json"]["survivor_packet_ids"]
		and "recovery_fault.json" not in artifacts
		and summaries
		and completed
	)


#============================================
def test_failed_repository_is_persisted_and_stage5_receives_only_healthy_siblings(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""One rejected future is degraded while its full healthy pair continues."""
	packet = _packet()
	coordinator, artifacts, summaries, completed = _coordinator(tmp_path, packet, _Runner(packet))
	original = daily_blog.multi_repository_coordinator._run_job

	def fail_alpha(
		value: daily_blog.multi_repository_coordinator.RepositoryJobInput,
	) -> daily_blog.multi_repository_coordinator.RepositoryJobResult:
		if value.repository == "owner/alpha":
			raise RuntimeError("injected worker defect")
		return original(value)

	monkeypatch.setattr(daily_blog.multi_repository_coordinator, "_run_job", fail_alpha)
	result = coordinator.run(packet)

	artifact = artifacts["repository_editorial.json"]
	job_reliability = next(item for item in artifact["reliability"] if item["step"] == "repository_job")
	assert (
		[(item["repository"], item["outcome"]) for item in artifact["repositories"]]
		== [("owner/alpha", "failed"), ("owner/beta", "succeeded")]
		and job_reliability["attempted"] == 2
		and job_reliability["succeeded"] == 1
		and job_reliability["failed"] == 1
		and result.stage5_input.repositories == ("owner/beta",)
		and tuple(card.repository for card in result.stage5_input.evidence_context.repositories)
		== ("owner/beta",)
		and artifacts["repository_editorial.json"]["stage5_evidence_context"]["packet_ids"]
		== [result.stage5_input.packets[0].packet_id]
		and "recovery_fault.json" not in artifacts
		and summaries
		and completed
	)


#============================================
def test_all_pair_loss_writes_a_canonical_terminal_digest_from_reversed_projections(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Terminal repository loss writes ordered packet and allowed-scope provenance."""
	packet = _packet()
	coordinator, artifacts, _summaries, completed = _coordinator(
		tmp_path, packet, _Runner(packet, lose_stories=True),
	)
	original = daily_blog.multi_repository_coordinator.project_repository_packets
	monkeypatch.setattr(
		daily_blog.multi_repository_coordinator,
		"project_repository_packets",
		lambda value: tuple(reversed(original(value))),
	)

	with pytest.raises(daily_blog.recovery.PipelineFaultError):
		coordinator.run(packet)

	recovery = artifacts["recovery_fault.json"]
	assert (
		[item["packet_id"] for item in recovery["packets"]]
		== sorted(item["packet_id"] for item in recovery["packets"])
		and recovery["allowed_repositories"] == ["owner/alpha", "owner/beta"]
		and not completed
	)


#============================================
@pytest.mark.parametrize(("category", "worker_error"), [
	(
		daily_blog.recovery.TerminalFaultCategory.IMPLEMENTATION_DEFECT,
		RuntimeError("injected worker defect"),
	),
	(
		daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE,
		_worker_pipeline_fault(daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE),
	),
	(
		daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION,
		_worker_pipeline_fault(daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION),
	),
])
def test_all_failed_workers_preserve_their_typed_terminal_category_and_evidence(
	category: daily_blog.recovery.TerminalFaultCategory,
	worker_error: Exception,
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Worker loss retains canonical evidence without fabricating an evidence fault."""
	packet = _packet()
	coordinator, artifacts, _summaries, completed = _coordinator(tmp_path, packet, _Runner(packet))

	def fail_all(_value: daily_blog.multi_repository_coordinator.RepositoryJobInput) -> object:
		raise worker_error

	monkeypatch.setattr(daily_blog.multi_repository_coordinator, "_run_job", fail_all)
	with pytest.raises(daily_blog.recovery.PipelineFaultError) as raised:
		coordinator.run(packet)

	assert raised.value.category is category
	assert not completed
	_assert_complete_projected_provenance(artifacts["recovery_fault.json"], packet)

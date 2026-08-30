"""Offline behavioral coverage for repository-scale editorial fan-out."""

# Standard Library
import dataclasses
import pathlib
import threading

# PIP3 modules
import pytest

# local repo modules
import daily_blog.agents
import daily_blog.config
import daily_blog.editorial_stage_config
import daily_blog.io_utils
import daily_blog.locks
import daily_blog.multi_repository_coordinator
import daily_blog.recovery
import daily_blog.repository_contracts
import daily_blog.route_cache
import daily_blog.schema


def _activity(repository: str, marker: str) -> daily_blog.schema.RepositoryActivity:
	"""Return one valid activity record associated with a local packet."""
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


def _packet(marker: str = "b") -> daily_blog.schema.EvidencePacket:
	"""Return two complete repository evidence scopes for coordinator behavior."""
	items = []
	activity = []
	for repository, commit_marker in (("owner/lost", "a"), ("owner/survivor", marker)):
		items.append(daily_blog.schema.EvidenceItem.create(
			"dated_changelog", repository, commit_marker * 40, "CHANGELOG.md", marker * 40,
			"Grounded change in " + repository + ".", "git show",
		))
		activity.append(_activity(repository, commit_marker))
	return daily_blog.schema.EvidencePacket.create(
		"2026-08-29", "America/Chicago", True, {},
		[{"repository": item.repository, "object_available": True} for item in activity], activity, items,
	)


def _config(tmp_path: pathlib.Path) -> daily_blog.config.DailyBlogConfig:
	"""Return compact real stage policies without relying on tunable defaults."""
	route = daily_blog.editorial_stage_config.RoleRoute("fixture", ("fixture",))
	return daily_blog.config.DailyBlogConfig(
		"settings.yaml", str(tmp_path), "owner", "America/Chicago", str(tmp_path), str(tmp_path / "mirrors"),
		(), (), (route,), route, {}, {"context_chars": 8000, "excerpt_chars": 1000, "commit_subject_chars": 120},
		{"author_chars": 8000, "referee_chars": 8000}, daily_blog.config.EditorialReliabilityConfig(2, 1, 1, 8),
		repository_outline=daily_blog.editorial_stage_config.RepositoryOutlineConfig(
			generator_count=2, merger_count=2, reviewer_count=1, maximum_parallel_calls=2, route_retry_attempts=0,
		),
		repository_story=daily_blog.editorial_stage_config.RepositoryStoryConfig(
			writer_count=2, editor_count=2, reviewer_count=1, maximum_parallel_calls=2, route_retry_attempts=0,
		),
	)


class _Runner:
	"""Thread-safe local runner that makes one repository lose Stage 3."""

	def __init__(self, packet: daily_blog.schema.EvidencePacket, lose_repository: bool = True) -> None:
		self.calls = 0
		self._lock = threading.Lock()
		self._lose_repository = lose_repository
		self._evidence = {item.repository: item.evidence_id for item in packet.items}

	def run(self, route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, _working_directory: str) -> str:
		with self._lock:
			self.calls += 1
		if self._lose_repository and "owner/lost" in prompt and route.name == "repository_outline_generator":
			return ""
		repository = "owner/survivor" if "owner/survivor" in prompt else "owner/lost"
		if route.name.endswith("reviewer"):
			return '{"winner":"A","reason":"grounded","evidence_quality":"high","confidence":1}'
		return "# Grounded\n\nEvidence-backed work. <!-- evidence: " + self._evidence[repository] + " -->\n"


def _cache(tmp_path: pathlib.Path) -> daily_blog.route_cache.RouteResultCache:
	"""Return one disposable coordinator-owned cache."""
	return daily_blog.route_cache.RouteResultCache(daily_blog.locks.PhaseCache(str(tmp_path / "cache")))


def _rogue_effect(value: daily_blog.multi_repository_coordinator.RepositoryJobInput) -> daily_blog.route_cache.RouteCacheEffect:
	"""Accept one identifiable valid-shaped effect through a job-local cache capability."""
	request = daily_blog.agents.RouteRequest(
		"rogue-worker-effect", "repository_editorial", daily_blog.editorial_stage_config.RoleRoute("rogue", ("fixture",)),
		"isolated invalid worker effect", value.working_directory, cache_input_hash=daily_blog.io_utils.sha256_text("rogue"),
	)
	result = daily_blog.agents.AgentResult(
		request.role, "accepted transport text", True, "", 1, 0.0, False, False, request.route.name,
		request.request_id, request.identity_sha256, daily_blog.io_utils.sha256_text("accepted transport text"),
	)
	value.cache_accept(request, result)
	return daily_blog.route_cache.RouteCacheEffect(request, result)


def _run(
	packet: daily_blog.schema.EvidencePacket,
	configuration: daily_blog.config.DailyBlogConfig,
	budget: daily_blog.agents.RouteBudget,
	runner: _Runner,
	cache: daily_blog.route_cache.RouteResultCache,
	tmp_path: pathlib.Path,
	rubric: str = "Prefer grounded work.",
) -> daily_blog.multi_repository_coordinator.RepositoryEditorialJoin:
	"""Run the real coordinator using frozen projections and an explicit rubric identity."""
	return daily_blog.multi_repository_coordinator.run_repository_editorial(
		packet, daily_blog.multi_repository_coordinator.project_repository_packets(packet), configuration,
		budget, runner, rubric, daily_blog.io_utils.sha256_text(rubric), cache, str(tmp_path),
	)


def test_surviving_repository_promotes_a_paired_local_artifact_within_shared_budget(tmp_path: pathlib.Path) -> None:
	"""One repository's route loss leaves another repository's eligible pair available."""
	packet = _packet()
	budget = daily_blog.agents.RouteBudget(80, 2)
	joined = _run(packet, _config(tmp_path), budget, _Runner(packet), _cache(tmp_path), tmp_path)

	assert tuple(item.repositories for item in joined.repo_stories) == (("owner/survivor",),)
	assert budget.used_calls <= budget.maximum_calls


def test_validated_cache_reuses_equivalent_work_but_rubric_change_requires_fresh_routes(tmp_path: pathlib.Path) -> None:
	"""Only logically identical accepted work resumes across independent coordinator runs."""
	packet = _packet()
	configuration = _config(tmp_path)
	cache = _cache(tmp_path)
	first_runner = _Runner(packet)
	first = _run(packet, configuration, daily_blog.agents.RouteBudget(80, 2), first_runner, cache, tmp_path)
	cache.commit(first.cache_effects)
	second_runner = _Runner(packet)
	_run(packet, configuration, daily_blog.agents.RouteBudget(80, 2), second_runner, cache, tmp_path)
	changed_runner = _Runner(packet)
	_run(packet, configuration, daily_blog.agents.RouteBudget(80, 2), changed_runner, cache, tmp_path,
		rubric="Prefer independently grounded maker work.")

	assert second_runner.calls < first_runner.calls
	assert changed_runner.calls > second_runner.calls


def test_malformed_worker_result_becomes_a_terminal_join_without_cache_effects(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""The fan-out join contains an invalid worker boundary before a caller can commit it."""
	packet = _packet()
	monkeypatch.setattr(daily_blog.multi_repository_coordinator, "_run_job", lambda _value: object())

	joined = _run(packet, _config(tmp_path), daily_blog.agents.RouteBudget(80, 2), _Runner(packet), _cache(tmp_path), tmp_path)

	assert joined.terminal_fault is not None
	assert not joined.cache_effects


def test_projection_rejects_duplicate_evidence_before_editorial_dispatch(tmp_path: pathlib.Path) -> None:
	"""One global evidence item cannot be assigned twice in a local repository scope."""
	packet = _packet()
	projected = daily_blog.multi_repository_coordinator.project_repository_packets(packet)
	local = projected[0]
	duplicated = daily_blog.schema.EvidencePacket.create(
		local.report_date, local.timezone, local.complete, dict(local.collection_limits),
		[dict(item) for item in local.mirrors], list(local.activity), [local.items[0], local.items[0]],
	)
	invalid_projection = (duplicated,) + projected[1:]

	with pytest.raises(RuntimeError):
		daily_blog.multi_repository_coordinator.run_repository_editorial(
			packet, invalid_projection, _config(tmp_path), daily_blog.agents.RouteBudget(80, 2), object(),
			"Prefer grounded work.", daily_blog.io_utils.sha256_text("Prefer grounded work."),
			_cache(tmp_path), str(tmp_path),
		)


def test_failed_worker_does_not_leak_buffered_effects_while_a_healthy_sibling_survives(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""Unexpected local failure remains terminal without discarding validated sibling work."""
	packet = _packet()
	original = daily_blog.multi_repository_coordinator._run_job

	def interrupted(
		value: daily_blog.multi_repository_coordinator.RepositoryJobInput,
	) -> daily_blog.multi_repository_coordinator.RepositoryJobResult:
		if value.repository == "owner/lost":
			_rogue_effect(value)
			raise RuntimeError("injected worker defect")
		return original(value)

	monkeypatch.setattr(daily_blog.multi_repository_coordinator, "_run_job", interrupted)
	joined = _run(packet, _config(tmp_path), daily_blog.agents.RouteBudget(80, 2), _Runner(packet), _cache(tmp_path), tmp_path)

	assert joined.terminal_fault is daily_blog.recovery.TerminalFaultCategory.IMPLEMENTATION_DEFECT
	assert joined.repo_stories and all(item.repositories == ("owner/survivor",) for item in joined.repo_stories)
	assert joined.cache_effects and all(effect.request.request_id != "rogue-worker-effect" for effect in joined.cache_effects)


def test_worker_cannot_substitute_a_changed_packet_for_its_frozen_repository_input(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""A type-valid result for changed same-repository evidence is terminal and non-contributing."""
	packet = _packet()
	original = daily_blog.multi_repository_coordinator._run_job
	replacement_runner = _Runner(packet, lose_repository=False)

	def substituted(
		value: daily_blog.multi_repository_coordinator.RepositoryJobInput,
	) -> daily_blog.multi_repository_coordinator.RepositoryJobResult:
		if value.repository != "owner/lost":
			return original(value)
		item = value.packet.items[0]
		changed_item = daily_blog.schema.EvidenceItem.create(
			item.kind, item.repository, item.commit, item.path, item.content_hash,
			"Materially changed local evidence.", item.source,
		)
		changed_packet = daily_blog.schema.EvidencePacket.create(
			value.packet.report_date, value.packet.timezone, value.packet.complete,
			dict(value.packet.collection_limits), [dict(item) for item in value.packet.mirrors],
			list(value.packet.activity), [changed_item],
		)
		replacement_runner._evidence["owner/lost"] = changed_item.evidence_id
		result = original(dataclasses.replace(value, packet=changed_packet, runner=replacement_runner))
		_rogue_effect(value)
		return result

	monkeypatch.setattr(daily_blog.multi_repository_coordinator, "_run_job", substituted)
	joined = _run(packet, _config(tmp_path), daily_blog.agents.RouteBudget(80, 2), _Runner(packet), _cache(tmp_path), tmp_path)

	assert joined.terminal_fault is daily_blog.recovery.TerminalFaultCategory.IMPLEMENTATION_DEFECT
	assert all(result.repository != "owner/lost" for result in joined.results)
	assert joined.cache_effects and all(effect.request.request_id != "rogue-worker-effect" for effect in joined.cache_effects)

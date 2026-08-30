"""Pure repository-scale editorial fan-out and canonical join."""

import concurrent.futures
import dataclasses
import os
import collections.abc

import daily_blog.agents
import daily_blog.artifacts
import daily_blog.config
import daily_blog.io_utils
import daily_blog.repository_outline_prompts
import daily_blog.repository_outline_workflow
import daily_blog.repository_story_prompts
import daily_blog.repository_story_workflow
import daily_blog.route_cache
import daily_blog.recovery
import daily_blog.schema


@dataclasses.dataclass(frozen=True)
class RepositoryJobInput:
	"""Immutable capabilities granted to one non-durable repository job."""
	repository: str
	packet: daily_blog.schema.EvidencePacket
	working_directory: str
	config: daily_blog.config.DailyBlogConfig
	budget: daily_blog.agents.RouteBudget
	runner: object | None
	rubric: str
	rubric_sha256: str
	outline_contract: daily_blog.repository_outline_prompts.RepositoryOutlinePromptContract
	story_contract: daily_blog.repository_story_prompts.RepositoryStoryPromptContract
	cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None]
	cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None]

	def __post_init__(self) -> None:
		if (
			type(self.repository) is not str or not self.repository
			or type(self.packet) is not daily_blog.schema.EvidencePacket
			or type(self.config) is not daily_blog.config.DailyBlogConfig
			or type(self.budget) is not daily_blog.agents.RouteBudget
			or type(self.working_directory) is not str
			or not os.path.isabs(self.working_directory)
			or os.path.realpath(self.working_directory) != self.working_directory
			or not os.path.isdir(self.working_directory)
			or type(self.rubric) is not str or not self.rubric
			or daily_blog.io_utils.sha256_text(self.rubric) != self.rubric_sha256
			or type(self.outline_contract) is not daily_blog.repository_outline_prompts.RepositoryOutlinePromptContract
			or type(self.story_contract) is not daily_blog.repository_story_prompts.RepositoryStoryPromptContract
			or not all(callable(item) for item in (self.cache_load, self.cache_accept))
		):
			raise RuntimeError("Repository editorial job input is invalid.")
		daily_blog.schema.EvidencePacket.from_dict(self.packet.to_dict())
		if {item.repository for item in self.packet.items} != {self.repository}:
			raise RuntimeError("Repository editorial job input packet scope conflicts.")


@dataclasses.dataclass(frozen=True)
class RepositoryJobResult:
	"""Typed local editorial outcome returned without durable side effects."""
	repository: str
	packet: daily_blog.schema.EvidencePacket
	outline_result: daily_blog.repository_outline_workflow.RepositoryOutlineResult
	story_result: daily_blog.repository_story_workflow.RepositoryStoryResult | None
	outline: daily_blog.artifacts.RepoOutline | None
	story: daily_blog.artifacts.RepoStory | None

	def __post_init__(self) -> None:
		if (
			type(self.repository) is not str or not self.repository
			or type(self.packet) is not daily_blog.schema.EvidencePacket
			or type(self.outline_result) is not daily_blog.repository_outline_workflow.RepositoryOutlineResult
			or self.story_result is not None and type(self.story_result) is not daily_blog.repository_story_workflow.RepositoryStoryResult
			or self.outline is not None and type(self.outline) is not daily_blog.artifacts.RepoOutline
			or self.story is not None and type(self.story) is not daily_blog.artifacts.RepoStory
		):
			raise RuntimeError("Repository editorial job result is invalid.")
		if self.outline is not self.outline_result.artifact or (
			self.story_result is None and self.story is not None
		) or (self.story_result is not None and self.story is not self.story_result.artifact):
			raise RuntimeError("Repository editorial job result artifacts conflict with observations.")
		for artifact in (self.outline, self.story):
			if artifact is not None and (
				artifact.repositories != (self.repository,)
				or artifact.packet_ids != (self.packet.packet_id,)
				or not daily_blog.artifacts.evaluate_eligibility(artifact, (self.packet,)).eligible
			):
				raise RuntimeError("Repository editorial job result provenance is invalid.")

	@property
	def degraded(self) -> bool:
		"""Identify ordinary local editorial loss without reclassifying faults."""
		return self.outline is None or self.story is None

	@property
	def reliability(self) -> tuple[object, ...]:
		"""Expose bounded Stage 3/4 summaries for the serial run owner."""
		values = list(self.outline_result.reliability)
		if self.story_result is not None:
			values.extend(self.story_result.reliability)
		return tuple(values)


@dataclasses.dataclass(frozen=True)
class RepositoryEditorialJoin:
	"""Canonical paired survivors and deferred cache effects for Stage 5."""
	results: tuple[RepositoryJobResult, ...]
	repo_stories: tuple[daily_blog.artifacts.RepoStory, ...]
	repo_outlines: tuple[daily_blog.artifacts.RepoOutline, ...]
	packets: tuple[daily_blog.schema.EvidencePacket, ...]
	cache_effects: tuple[daily_blog.route_cache.RouteCacheEffect, ...]
	terminal_fault: daily_blog.recovery.TerminalFaultCategory | None = None

	def __post_init__(self) -> None:
		if (
			type(self.results) is not tuple or type(self.repo_stories) is not tuple
			or type(self.repo_outlines) is not tuple or type(self.packets) is not tuple
			or type(self.cache_effects) is not tuple
			or any(type(item) is not RepositoryJobResult for item in self.results)
			or any(type(item) is not daily_blog.artifacts.RepoStory for item in self.repo_stories)
			or any(type(item) is not daily_blog.artifacts.RepoOutline for item in self.repo_outlines)
			or any(type(item) is not daily_blog.schema.EvidencePacket for item in self.packets)
			or any(type(item) is not daily_blog.route_cache.RouteCacheEffect for item in self.cache_effects)
		):
			raise RuntimeError("Repository editorial join is invalid.")
		if tuple(item.repository for item in self.results) != tuple(sorted((item.repository for item in self.results), key=str.casefold)):
			raise RuntimeError("Repository editorial join results are not canonical.")
		if len({item.repository for item in self.results}) != len(self.results):
			raise RuntimeError("Repository editorial join repeats a repository.")
		pairs = tuple(item for item in self.results if item.outline is not None and item.story is not None)
		expected_stories = tuple(sorted((item.story for item in pairs if item.story is not None), key=lambda item: item.artifact_id))
		expected_outlines = tuple(sorted((item.outline for item in pairs if item.outline is not None), key=lambda item: item.artifact_id))
		expected_packets = tuple(sorted((item.packet for item in pairs), key=lambda item: item.packet_id))
		if (
			self.repo_stories != expected_stories or self.repo_outlines != expected_outlines
			or self.packets != expected_packets
		):
			raise RuntimeError("Repository editorial join values conflict with job results.")
		if self.terminal_fault is not None and type(self.terminal_fault) is not daily_blog.recovery.TerminalFaultCategory:
			raise RuntimeError("Repository editorial join terminal fault is invalid.")


def _validate_projection_set(packet: daily_blog.schema.EvidencePacket, projected: tuple[daily_blog.schema.EvidencePacket, ...]) -> None:
	"""Verify one frozen local packet set covers exact global evidence once."""
	if type(packet) is not daily_blog.schema.EvidencePacket or type(projected) is not tuple:
		raise RuntimeError("Repository projections require exact packet values.")
	if any(type(item) is not daily_blog.schema.EvidencePacket for item in projected):
		raise RuntimeError("Repository projections require exact local packets.")
	if len({item.packet_id for item in projected}) != len(projected):
		raise RuntimeError("Repository projections cannot repeat packet identities.")
	global_ownership = {}
	for item in packet.items:
		if item.evidence_id in global_ownership:
			raise RuntimeError("Global evidence identities cannot repeat.")
		global_ownership[item.evidence_id] = item.repository
	local_ownership = {}
	repositories: set[str] = set()
	for local in projected:
		daily_blog.schema.EvidencePacket.from_dict(local.to_dict())
		if local.report_date != packet.report_date or local.timezone != packet.timezone or not local.items:
			raise RuntimeError("Repository projection date or evidence is invalid.")
		repository = local.activity[0].repository if len(local.activity) == 1 else ""
		if len(local.mirrors) != 1 or not repository or repository in repositories:
			raise RuntimeError("Repository projection scope is invalid.")
		if {item.repository for item in local.items} != {repository} or local.mirrors[0].to_dict()["repository"] != repository:
			raise RuntimeError("Repository projection local membership conflicts.")
		repositories.add(repository)
		for item in local.items:
			if item.evidence_id in local_ownership:
				raise RuntimeError("Repository projections repeat evidence ownership.")
			local_ownership[item.evidence_id] = repository
	if local_ownership != global_ownership:
		raise RuntimeError("Repository projections do not cover the global evidence exactly.")


def project_repository_packets(packet: daily_blog.schema.EvidencePacket) -> tuple[daily_blog.schema.EvidencePacket, ...]:
	"""Create exact one-repository packets from complete frozen global evidence."""
	if type(packet) is not daily_blog.schema.EvidencePacket:
		raise RuntimeError("Repository projection requires an exact EvidencePacket.")
	daily_blog.schema.EvidencePacket.from_dict(packet.to_dict())
	activities = {item.repository: item for item in packet.activity}
	if len(activities) != len(packet.activity):
		raise RuntimeError("Repository projection activity identities cannot repeat.")
	mirrors: dict[str, object] = {}
	for mirror in packet.mirrors:
		value = mirror.to_dict()
		repository = value["repository"]
		if type(repository) is not str or not repository or repository in mirrors:
			raise RuntimeError("Repository projection mirror identities are invalid.")
		mirrors[repository] = value
	by_repository: dict[str, list[daily_blog.schema.EvidenceItem]] = {}
	for item in packet.items:
		by_repository.setdefault(item.repository, []).append(item)
	if not set(by_repository).issubset(activities) or not set(by_repository).issubset(mirrors):
		raise RuntimeError("Repository projection source scope is incomplete.")
	values = []
	for repository in sorted(by_repository, key=str.casefold):
		items = by_repository[repository]
		local = daily_blog.schema.EvidencePacket.create(
			packet.report_date, packet.timezone, packet.complete,
			packet.collection_limits.to_dict(), [mirrors[repository]],
			[activities[repository]], items,
		)
		verified = daily_blog.schema.EvidencePacket.from_dict(local.to_dict())
		if (
			len(verified.activity) != 1 or len(verified.mirrors) != 1
			or not verified.items
			or {item.repository for item in verified.items} != {repository}
			or verified.activity[0].repository != repository
			or verified.mirrors[0].to_dict()["repository"] != repository
		):
			raise RuntimeError("Repository projection did not preserve strict local scope.")
		values.append(verified)
	return tuple(values)


def _run_job(value: RepositoryJobInput) -> RepositoryJobResult:
	"""Run Stage 3 then 4 with only route and in-memory cache capabilities."""
	if type(value) is not RepositoryJobInput:
		raise RuntimeError("Repository editorial job requires exact input.")
	if {item.repository for item in value.packet.items} != {value.repository}:
		raise RuntimeError("Repository editorial job packet scope conflicts with repository.")
	outline_value = daily_blog.repository_outline_workflow.RepositoryOutlineInput(
		value.packet, value.repository, value.working_directory,
	)
	outline_result = daily_blog.repository_outline_workflow.run_repository_outline(
		outline_value, value.config.repository_outline, value.budget, value.runner,
		contract=value.outline_contract, cache_load=value.cache_load, cache_accept=value.cache_accept,
	)
	outline = outline_result.artifact
	if outline is None:
		return RepositoryJobResult(value.repository, value.packet, outline_result, None, None, None)
	story_value = daily_blog.repository_story_workflow.RepositoryStoryInput(
		outline, (value.packet,), value.working_directory,
	)
	story_result = daily_blog.repository_story_workflow.run_repository_story(
		story_value, value.config.repository_story, value.budget, value.runner,
		rubric=value.rubric, rubric_sha256=value.rubric_sha256,
		contract=value.story_contract, cache_load=value.cache_load, cache_accept=value.cache_accept,
	)
	return RepositoryJobResult(value.repository, value.packet, outline_result, story_result,
		outline, story_result.artifact)


def _canonical_effects(
	cache: daily_blog.route_cache.RouteResultCache,
	buffers: list[daily_blog.route_cache.BufferedRouteEffects],
) -> tuple[daily_blog.route_cache.RouteCacheEffect, ...]:
	"""Validate coordinator-owned accepted effects before any durable commit."""
	values: dict[str, tuple[daily_blog.route_cache.RouteCacheEffect, dict[str, object]]] = {}
	for buffer in buffers:
		for effect in buffer.drain():
			_identity, key = cache._identity(effect.request)
			envelope = cache._envelope_value(effect)
			previous = values.get(key)
			if previous is not None and previous[1] != envelope:
				raise daily_blog.route_cache.RouteCacheIntegrityError(
				"Conflicting coordinator-owned route cache effects."
			)
			values[key] = (effect, envelope)
	return tuple(values[key][0] for key in sorted(values))


def run_repository_editorial(
	packet: daily_blog.schema.EvidencePacket, projected: tuple[daily_blog.schema.EvidencePacket, ...],
	config: daily_blog.config.DailyBlogConfig,
	budget: daily_blog.agents.RouteBudget, runner: object | None, rubric: str,
	rubric_sha256: str, cache: daily_blog.route_cache.RouteResultCache, working_directory: str,
) -> RepositoryEditorialJoin:
	"""Dispatch independent jobs, then validate a canonical non-durable join."""
	if type(config) is not daily_blog.config.DailyBlogConfig or type(budget) is not daily_blog.agents.RouteBudget:
		raise RuntimeError("Repository editorial coordinator requires exact config and RouteBudget.")
	if (
		type(working_directory) is not str or not os.path.isabs(working_directory)
		or os.path.realpath(working_directory) != working_directory
		or not os.path.isdir(working_directory)
	):
		raise RuntimeError("Repository editorial coordinator requires a physical working directory.")
	_validate_projection_set(packet, projected)
	outline_contract = daily_blog.repository_outline_prompts.load_repository_outline_prompt_contract()
	story_contract = daily_blog.repository_story_prompts.load_repository_story_prompt_contract()
	jobs = []
	for local in projected:
		buffer = daily_blog.route_cache.BufferedRouteEffects(cache)
		jobs.append((RepositoryJobInput(
			local.activity[0].repository, local, working_directory, config, budget, runner,
			rubric, rubric_sha256, outline_contract, story_contract,
			buffer.load, buffer.accept,
		), buffer))
	results = []
	accepted_buffers = []
	terminal_fault = None
	if jobs:
		with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(jobs), budget.maximum_parallel_calls)) as executor:
			futures = {
				executor.submit(_run_job, item): (item, buffer)
				for item, buffer in jobs
			}
			for future in concurrent.futures.as_completed(futures):
				item, buffer = futures[future]
				try:
					result = future.result()
					if type(result) is not RepositoryJobResult:
						raise RuntimeError("Repository editorial worker returned an invalid result.")
					if result.repository != item.repository or result.packet is not item.packet:
						raise RuntimeError("Repository editorial worker result conflicts with its submitted input.")
					results.append(result)
					accepted_buffers.append(buffer)
				except Exception as error:
					if isinstance(error, (
						daily_blog.agents.EditorialTerminalError,
						daily_blog.recovery.RecoveryConfigurationError,
					)):
						terminal_fault = daily_blog.recovery.TerminalFaultCategory.CONFIGURATION
					elif terminal_fault is None:
						terminal_fault = daily_blog.recovery.TerminalFaultCategory.IMPLEMENTATION_DEFECT
	ordered = tuple(sorted(results, key=lambda item: item.repository.casefold()))
	if len({item.repository for item in ordered}) != len(ordered):
		raise RuntimeError("Repository editorial results cannot repeat a repository.")
	pairs = []
	for result in ordered:
		if result.packet.activity[0].repository != result.repository:
			raise RuntimeError("Repository editorial result packet identity conflicts.")
		if result.outline is None or result.story is None:
			continue
		if (
			result.outline.repositories != (result.repository,)
			or result.story.repositories != (result.repository,)
			or result.outline.packet_ids != result.story.packet_ids
			or not result.outline.packet_ids
			or result.outline.packet_ids != (result.packet.packet_id,)
		):
			raise RuntimeError("Repository editorial paired artifacts have invalid provenance.")
		pairs.append(result)
	packets = tuple(sorted((item.packet for item in pairs), key=lambda item: item.packet_id))
	stories = tuple(sorted((item.story for item in pairs if item.story is not None), key=lambda item: item.artifact_id))
	outlines = tuple(sorted((item.outline for item in pairs if item.outline is not None), key=lambda item: item.artifact_id))
	effects = _canonical_effects(cache, accepted_buffers)
	return RepositoryEditorialJoin(ordered, stories, outlines, packets, effects, terminal_fault)

"""Pure repository-scale editorial fan-out and canonical join."""

import concurrent.futures
import dataclasses
import os
import collections.abc

import daily_blog.agents
import daily_blog.artifacts
import daily_blog.config
import daily_blog.io_utils
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.loader
import daily_blog.repository_outline_prompts
import daily_blog.repository_outline_workflow
import daily_blog.repository_story_prompts
import daily_blog.repository_story_workflow
import daily_blog.route_cache
import daily_blog.recovery
import daily_blog.schema


_PROJECTION_FAULT_OWNER = "daily_blog.multi_repository_coordinator.project_repository_packets"


class RepositoryProjectionFault(RuntimeError):
	"""Expose one fixed, safe diagnosis for rejected packet projection."""

	def __init__(self, terminal_fault: daily_blog.recovery.TerminalFaultDigest) -> None:
		if (
			type(terminal_fault) is not daily_blog.recovery.TerminalFaultDigest
			or terminal_fault.category is not daily_blog.recovery.TerminalFaultCategory.IMPLEMENTATION_DEFECT
			or terminal_fault.owner != _PROJECTION_FAULT_OWNER
		):
			raise RuntimeError("Repository projection terminal fault is invalid.")
		super().__init__("Repository projection failed.")
		self.terminal_fault = terminal_fault


def _projection_structural_facts(
	packet: object, include_missing: bool,
) -> tuple[tuple[str, int], ...]:
	"""Return bounded counts without retaining packet contents or repository labels."""
	items = packet.items if type(packet) is daily_blog.schema.EvidencePacket else ()
	activity = packet.activity if type(packet) is daily_blog.schema.EvidencePacket else ()
	mirrors = packet.mirrors if type(packet) is daily_blog.schema.EvidencePacket else ()
	repositories = {
		item.repository for item in items
		if type(item) is daily_blog.schema.EvidenceItem and type(item.repository) is str
	}
	activity_repositories = {
		item.repository for item in activity
		if type(item) is daily_blog.schema.RepositoryActivity and type(item.repository) is str
	}
	mirror_repositories = {
		item.to_dict().get("repository") for item in mirrors
		if hasattr(item, "to_dict") and type(item.to_dict()) is dict
	}
	values = {
		"activity_count": len(activity),
		"evidence_repository_count": len(repositories),
		"mirror_count": len(mirrors),
	}
	if include_missing:
		values["missing_activity_count"] = len(repositories - activity_repositories)
		values["missing_mirror_count"] = len(repositories - mirror_repositories)
	return tuple(sorted(values.items()))


def _projection_fault(
	packet: object, subtype: daily_blog.recovery.TerminalFaultSubtype,
	*, include_missing: bool,
) -> RepositoryProjectionFault:
	"""Build the sole typed projection failure without exception diagnostics."""
	return RepositoryProjectionFault(daily_blog.recovery.TerminalFaultDigest(
		daily_blog.recovery.TerminalFaultCategory.IMPLEMENTATION_DEFECT,
		subtype, _PROJECTION_FAULT_OWNER,
		_projection_structural_facts(packet, include_missing),
	))


def _invalid_projection_fault(packet: object) -> RepositoryProjectionFault:
	"""Classify every local packet-structure invariant under one safe subtype."""
	return _projection_fault(
		packet, daily_blog.recovery.TerminalFaultSubtype.PROJECTION_PACKET_INVALID,
		include_missing=False,
	)


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
	outline_prompts: daily_blog.prompt_registry.loader.LoadedPromptSet
	story_prompts: daily_blog.prompt_registry.loader.LoadedPromptSet
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
			or type(self.outline_prompts) is not daily_blog.prompt_registry.loader.LoadedPromptSet
			or type(self.story_prompts) is not daily_blog.prompt_registry.loader.LoadedPromptSet
			or not all(callable(item) for item in (self.cache_load, self.cache_accept))
		):
			raise RuntimeError("Repository editorial job input is invalid.")
		daily_blog.prompt_registry.loader.resolve_loaded_prompt_set(
			self.outline_prompts, daily_blog.prompt_registry.definitions.REPOSITORY_OUTLINE_PROMPT_SET,
		)
		daily_blog.prompt_registry.loader.resolve_loaded_prompt_set(
			self.story_prompts, daily_blog.prompt_registry.definitions.REPOSITORY_STORY_PROMPT_SET,
		)
		daily_blog.schema.EvidencePacket.from_dict(self.packet.to_dict())
		if {item.repository for item in self.packet.items} != {self.repository}:
			raise RuntimeError("Repository editorial job input packet scope conflicts.")


@dataclasses.dataclass(frozen=True)
class RepositoryJobResult:
	"""Typed local editorial outcome returned without durable side effects."""
	repository: str
	packet: daily_blog.schema.EvidencePacket
	outline_result: daily_blog.repository_outline_workflow.RepositoryOutlineResult | None
	story_result: daily_blog.repository_story_workflow.RepositoryStoryResult | None
	outline: daily_blog.artifacts.RepoOutline | None
	story: daily_blog.artifacts.RepoStory | None
	terminal_fault: daily_blog.recovery.TerminalFaultCategory | None = None
	terminal_fault_digest: daily_blog.recovery.TerminalFaultDigest | None = None

	def __post_init__(self) -> None:
		if (
			type(self.repository) is not str or not self.repository
			or type(self.packet) is not daily_blog.schema.EvidencePacket
			or self.outline_result is not None and type(self.outline_result) is not daily_blog.repository_outline_workflow.RepositoryOutlineResult
			or self.story_result is not None and type(self.story_result) is not daily_blog.repository_story_workflow.RepositoryStoryResult
			or self.outline is not None and type(self.outline) is not daily_blog.artifacts.RepoOutline
			or self.story is not None and type(self.story) is not daily_blog.artifacts.RepoStory
		):
			raise RuntimeError("Repository editorial job result is invalid.")
		if self.terminal_fault is not None and type(self.terminal_fault) is not daily_blog.recovery.TerminalFaultCategory:
			raise RuntimeError("Repository editorial job result terminal fault is invalid.")
		if self.terminal_fault_digest is not None and (
			type(self.terminal_fault_digest) is not daily_blog.recovery.TerminalFaultDigest
			or self.terminal_fault is not self.terminal_fault_digest.category
		):
			raise RuntimeError("Repository editorial job result terminal fault digest is invalid.")
		if self.outline_result is None:
			if any(item is not None for item in (self.story_result, self.outline, self.story)) or self.terminal_fault is None:
				raise RuntimeError("Repository editorial failed job result is invalid.")
			return
		if self.terminal_fault is not None:
			raise RuntimeError("Repository editorial successful job result cannot retain a terminal fault.")
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
		return self.terminal_fault is None and (self.outline is None or self.story is None)

	@property
	def reliability(self) -> tuple[object, ...]:
		"""Expose bounded Stage 3/4 summaries for the serial run owner."""
		if self.outline_result is None:
			return (daily_blog.replication.StepReliability(
				"repository_job", "degraded", 1, 0, 1, 0, 0, 0, "",
				("terminal_" + str(self.terminal_fault),),
			),)
		values = [daily_blog.replication.StepReliability(
			"repository_job", "succeeded", 1, 1, 0, 0, 0, 0, "", (),
		)]
		values.extend(self.outline_result.reliability)
		if self.story_result is not None:
			values.extend(self.story_result.reliability)
		return tuple(values)


def _failed_job_result(
	value: RepositoryJobInput, fault: daily_blog.recovery.TerminalFaultCategory,
	digest: daily_blog.recovery.TerminalFaultDigest | None = None,
) -> RepositoryJobResult:
	"""Record one bounded rejected worker outcome without retaining diagnostics."""
	return RepositoryJobResult(value.repository, value.packet, None, None, None, None, fault, digest)


#============================================
def _terminal_fault_from_error(error: Exception) -> daily_blog.recovery.TerminalFaultCategory:
	"""Project a worker exception into its bounded operator-facing diagnosis."""
	if isinstance(error, daily_blog.recovery.PipelineFaultError):
		return error.category
	if isinstance(error, (
		daily_blog.agents.EditorialTerminalError,
		daily_blog.recovery.RecoveryConfigurationError,
	)):
		return daily_blog.recovery.TerminalFaultCategory.CONFIGURATION
	return daily_blog.recovery.TerminalFaultCategory.IMPLEMENTATION_DEFECT


def _terminal_fault_digest_from_error(
	error: Exception,
) -> daily_blog.recovery.TerminalFaultDigest | None:
	"""Keep an upstream safe diagnosis or classify an untyped worker defect."""
	if isinstance(error, daily_blog.recovery.PipelineFaultError):
		return error.fault.terminal_fault
	if isinstance(error, (daily_blog.agents.EditorialTerminalError, daily_blog.recovery.RecoveryConfigurationError)):
		return None
	return daily_blog.recovery.TerminalFaultDigest(
		daily_blog.recovery.TerminalFaultCategory.IMPLEMENTATION_DEFECT,
		daily_blog.recovery.TerminalFaultSubtype.IMPLEMENTATION_UNCLASSIFIED,
		"daily_blog.multi_repository_coordinator._terminal_fault_from_error",
	)


#============================================
def _worst_terminal_fault(
	faults: collections.abc.Iterable[daily_blog.recovery.TerminalFaultCategory],
) -> daily_blog.recovery.TerminalFaultCategory | None:
	"""Choose a stable bounded diagnosis when independently isolated jobs fail."""
	values = frozenset(faults)
	for category in (
		daily_blog.recovery.TerminalFaultCategory.CONFIGURATION,
		daily_blog.recovery.TerminalFaultCategory.EVIDENCE_UNAVAILABLE,
		daily_blog.recovery.TerminalFaultCategory.IMPLEMENTATION_DEFECT,
		daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE,
		daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION,
	):
		if category in values:
			return category
	return None


def _accept_job_result(
	value: RepositoryJobInput, result: object,
) -> RepositoryJobResult:
	"""Validate one future result and its complete pair before accepting its cache."""
	if type(result) is not RepositoryJobResult:
		raise RuntimeError("Repository editorial worker returned an invalid result.")
	if result.repository != value.repository or result.packet is not value.packet:
		raise RuntimeError("Repository editorial worker result conflicts with its submitted input.")
	if result.terminal_fault is not None:
		raise RuntimeError("Repository editorial worker cannot return a terminal result.")
	if result.packet.activity[0].repository != result.repository:
		raise RuntimeError("Repository editorial result packet identity conflicts.")
	if result.outline is None or result.story is None:
		return result
	if (
		result.outline.repositories != (result.repository,)
		or result.story.repositories != (result.repository,)
		or result.outline.packet_ids != result.story.packet_ids
		or result.outline.packet_ids != (result.packet.packet_id,)
	):
		raise RuntimeError("Repository editorial paired artifacts have invalid provenance.")
	return result


@dataclasses.dataclass(frozen=True)
class RepositoryEditorialJoin:
	"""Canonical paired survivors and deferred cache effects for Stage 5."""
	results: tuple[RepositoryJobResult, ...]
	repo_stories: tuple[daily_blog.artifacts.RepoStory, ...]
	repo_outlines: tuple[daily_blog.artifacts.RepoOutline, ...]
	packets: tuple[daily_blog.schema.EvidencePacket, ...]
	cache_effects: tuple[daily_blog.route_cache.RouteCacheEffect, ...]
	terminal_fault: daily_blog.recovery.TerminalFaultCategory | None = None
	terminal_fault_digest: daily_blog.recovery.TerminalFaultDigest | None = None

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
		if self.terminal_fault_digest is not None and (
			type(self.terminal_fault_digest) is not daily_blog.recovery.TerminalFaultDigest
			or self.terminal_fault is not self.terminal_fault_digest.category
		):
			raise RuntimeError("Repository editorial join terminal fault digest is invalid.")


def _validate_projection_set(packet: daily_blog.schema.EvidencePacket, projected: tuple[daily_blog.schema.EvidencePacket, ...]) -> None:
	"""Verify one frozen local packet set covers exact global evidence once."""
	if type(packet) is not daily_blog.schema.EvidencePacket or type(projected) is not tuple:
		raise _invalid_projection_fault(packet)
	if any(type(item) is not daily_blog.schema.EvidencePacket for item in projected):
		raise _invalid_projection_fault(packet)
	if len({item.packet_id for item in projected}) != len(projected):
		raise _invalid_projection_fault(packet)
	global_ownership = {}
	for item in packet.items:
		if item.evidence_id in global_ownership:
			raise _invalid_projection_fault(packet)
		global_ownership[item.evidence_id] = item.repository
	local_ownership = {}
	repositories: set[str] = set()
	for local in projected:
		try:
			daily_blog.schema.EvidencePacket.from_dict(local.to_dict())
		except (RuntimeError, TypeError, ValueError, KeyError):
			raise _invalid_projection_fault(packet) from None
		if local.report_date != packet.report_date or local.timezone != packet.timezone or not local.items:
			raise _invalid_projection_fault(packet)
		repository = local.activity[0].repository if len(local.activity) == 1 else ""
		if len(local.mirrors) != 1 or not repository or repository in repositories:
			raise _invalid_projection_fault(packet)
		if {item.repository for item in local.items} != {repository} or local.mirrors[0].to_dict()["repository"] != repository:
			raise _invalid_projection_fault(packet)
		repositories.add(repository)
		for item in local.items:
			if item.evidence_id in local_ownership:
				raise _invalid_projection_fault(packet)
			local_ownership[item.evidence_id] = repository
	if local_ownership != global_ownership:
		raise _invalid_projection_fault(packet)


def project_repository_packets(packet: daily_blog.schema.EvidencePacket) -> tuple[daily_blog.schema.EvidencePacket, ...]:
	"""Create exact one-repository packets from complete frozen global evidence."""
	if type(packet) is not daily_blog.schema.EvidencePacket:
		raise _invalid_projection_fault(packet)
	try:
		packet = daily_blog.schema.EvidencePacket.from_dict(packet.to_dict())
	except (RuntimeError, TypeError, ValueError, KeyError):
		raise _invalid_projection_fault(packet) from None
	activities = {item.repository: item for item in packet.activity}
	if len(activities) != len(packet.activity):
		raise _invalid_projection_fault(packet)
	mirrors: dict[str, object] = {}
	for mirror in packet.mirrors:
		value = mirror.to_dict()
		repository = value["repository"]
		if type(repository) is not str or not repository or repository in mirrors:
			raise _invalid_projection_fault(packet)
		mirrors[repository] = value
	by_repository: dict[str, list[daily_blog.schema.EvidenceItem]] = {}
	for item in packet.items:
		by_repository.setdefault(item.repository, []).append(item)
	if not set(by_repository).issubset(activities) or not set(by_repository).issubset(mirrors):
		raise _projection_fault(
			packet, daily_blog.recovery.TerminalFaultSubtype.PROJECTION_SOURCE_SCOPE_INCOMPLETE,
			include_missing=True,
		)
	values = []
	for repository in sorted(by_repository, key=str.casefold):
		items = by_repository[repository]
		try:
			local = daily_blog.schema.EvidencePacket.create(
				packet.report_date, packet.timezone, packet.complete,
				packet.collection_limits.to_dict(), [mirrors[repository]],
				[activities[repository]], items,
			)
			verified = daily_blog.schema.EvidencePacket.from_dict(local.to_dict())
		except (RuntimeError, TypeError, ValueError, KeyError):
			raise _invalid_projection_fault(packet) from None
		if (
			len(verified.activity) != 1 or len(verified.mirrors) != 1
			or not verified.items
			or {item.repository for item in verified.items} != {repository}
			or verified.activity[0].repository != repository
			or verified.mirrors[0].to_dict()["repository"] != repository
		):
			raise _invalid_projection_fault(packet)
		values.append(verified)
	projected = tuple(values)
	_validate_projection_set(packet, projected)
	return projected


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
		loaded_prompts=value.outline_prompts, cache_load=value.cache_load, cache_accept=value.cache_accept,
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
		loaded_prompts=value.story_prompts, cache_load=value.cache_load, cache_accept=value.cache_accept,
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
	outline_prompts = daily_blog.prompt_registry.loader.load_prompt_set(
		daily_blog.prompt_registry.definitions.REPOSITORY_OUTLINE_PROMPT_SET,
	)
	story_prompts = daily_blog.prompt_registry.loader.load_prompt_set(
		daily_blog.prompt_registry.definitions.REPOSITORY_STORY_PROMPT_SET,
	)
	jobs = []
	for local in projected:
		buffer = daily_blog.route_cache.BufferedRouteEffects(cache)
		jobs.append((RepositoryJobInput(
			local.activity[0].repository, local, working_directory, config, budget, runner,
			rubric, rubric_sha256, outline_prompts, story_prompts,
			buffer.load, buffer.accept,
		), buffer))
	results = []
	accepted_buffers = []
	terminal_faults: set[daily_blog.recovery.TerminalFaultCategory] = set()
	terminal_fault_digests: list[daily_blog.recovery.TerminalFaultDigest] = []
	if jobs:
		with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(jobs), budget.maximum_parallel_calls)) as executor:
			futures = {
				executor.submit(_run_job, item): (item, buffer)
				for item, buffer in jobs
			}
			for future in concurrent.futures.as_completed(futures):
				item, buffer = futures[future]
				try:
					result = _accept_job_result(item, future.result())
					results.append(result)
					accepted_buffers.append(buffer)
				except Exception as error:
					fault = _terminal_fault_from_error(error)
					digest = _terminal_fault_digest_from_error(error)
					results.append(_failed_job_result(item, fault, digest))
					terminal_faults.add(fault)
					if digest is not None:
						terminal_fault_digests.append(digest)
	ordered = tuple(sorted(results, key=lambda item: item.repository.casefold()))
	if len({item.repository for item in ordered}) != len(ordered):
		raise RuntimeError("Repository editorial results cannot repeat a repository.")
	pairs = tuple(
		result for result in ordered
		if result.outline is not None and result.story is not None
	)
	packets = tuple(sorted((item.packet for item in pairs), key=lambda item: item.packet_id))
	stories = tuple(sorted((item.story for item in pairs if item.story is not None), key=lambda item: item.artifact_id))
	outlines = tuple(sorted((item.outline for item in pairs if item.outline is not None), key=lambda item: item.artifact_id))
	effects = _canonical_effects(cache, accepted_buffers)
	terminal_fault = _worst_terminal_fault(terminal_faults)
	matching_digests = tuple(sorted({
		item for item in terminal_fault_digests
		if terminal_fault is not None and item.category is terminal_fault
	}, key=lambda item: (item.subtype.value, item.owner, item.structural_facts)))
	terminal_fault_digest = matching_digests[0] if len(matching_digests) == 1 else None
	return RepositoryEditorialJoin(
		ordered, stories, outlines, packets, effects, terminal_fault, terminal_fault_digest,
	)

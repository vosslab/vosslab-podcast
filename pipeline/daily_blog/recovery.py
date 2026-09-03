"""Typed editorial recovery transitions and safe diagnostic digest payloads."""

# Standard Library
import collections.abc
import dataclasses
import datetime
import enum
import re

# local repo modules
import daily_blog.artifacts
import daily_blog.io_utils
import daily_blog.replication
import daily_blog.stage6_attempt_plan


RECOVERY_SCHEMA_VERSION = "vosslab.daily-blog.recovery.v6"
MAX_DIGEST_PACKETS = 256
MAX_DIGEST_EVIDENCE_REFS = 4096
MAX_DIGEST_OBSERVATIONS = 512
MAX_PROMOTED_ARTIFACT_IDS = 512
MAX_DIGEST_STEPS = 512
MAX_STEP_REASONS = 64
DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER_RE = re.compile(r"[a-z][a-z0-9_.:-]{0,127}\Z")
STAGE_KEY_RE = re.compile(
	r"(?:stage[346]/[a-z0-9_.:-]+/[a-z0-9_.:-]+"
	r"|recovery/[a-z0-9_.:-]+/[a-z0-9_.:-]+(?:/6\.[1-4])?"
	r"|stage5/daily_outline/(?:5\.[1-5]|terminal))\Z"
)
RANKING_PROMOTION_ID_RE = re.compile(r"ranking-promotion-[0-9a-f]{24}\Z")


#============================================
def _validate_stage6_observations(value: tuple[object, ...], label: str) -> None:
	"""Require exact Stage 6 batch facts after module initialization completes."""
	if not daily_blog.stage6_attempt_plan.has_canonical_observation_coordinates(value):
		raise RecoveryConfigurationError(f"{label} batch observations are not canonical.")


class TerminalFaultCategory(enum.StrEnum):
	"""The only terminal categories an operator may receive."""

	ROUTE_UNAVAILABLE = "route_unavailable"
	NO_ELIGIBLE_GENERATION = "no_eligible_generation"
	EVIDENCE_UNAVAILABLE = "evidence_unavailable"
	CONFIGURATION = "configuration"
	IMPLEMENTATION_DEFECT = "implementation_defect"


class TerminalFaultSubtype(enum.StrEnum):
	"""Closed causal subtypes safe for durable terminal diagnostics."""

	PROJECTION_SOURCE_SCOPE_INCOMPLETE = "projection_source_scope_incomplete"
	PROJECTION_PACKET_INVALID = "projection_packet_invalid"
	IMPLEMENTATION_UNCLASSIFIED = "implementation_unclassified"
	ROUTE_START_FAILURE = "route_start_failure"
	ROUTE_TIMEOUT = "route_timeout"
	ROUTE_PROCESS_FAILURE = "route_process_failure"
	PLAN_EXHAUSTED = "plan_exhausted"
	EVIDENCE_MISSING = "evidence_missing"
	CONFIGURATION_INVALID = "configuration_invalid"


_SUBTYPE_CATEGORIES = {
	TerminalFaultSubtype.PROJECTION_SOURCE_SCOPE_INCOMPLETE: TerminalFaultCategory.IMPLEMENTATION_DEFECT,
	TerminalFaultSubtype.PROJECTION_PACKET_INVALID: TerminalFaultCategory.IMPLEMENTATION_DEFECT,
	TerminalFaultSubtype.IMPLEMENTATION_UNCLASSIFIED: TerminalFaultCategory.IMPLEMENTATION_DEFECT,
	TerminalFaultSubtype.ROUTE_START_FAILURE: TerminalFaultCategory.ROUTE_UNAVAILABLE,
	TerminalFaultSubtype.ROUTE_TIMEOUT: TerminalFaultCategory.ROUTE_UNAVAILABLE,
	TerminalFaultSubtype.ROUTE_PROCESS_FAILURE: TerminalFaultCategory.ROUTE_UNAVAILABLE,
	TerminalFaultSubtype.PLAN_EXHAUSTED: TerminalFaultCategory.NO_ELIGIBLE_GENERATION,
	TerminalFaultSubtype.EVIDENCE_MISSING: TerminalFaultCategory.EVIDENCE_UNAVAILABLE,
	TerminalFaultSubtype.CONFIGURATION_INVALID: TerminalFaultCategory.CONFIGURATION,
}
_SAFE_FAULT_OWNER_RE = re.compile(r"[a-z][a-z0-9_.]{0,127}\Z")
_SAFE_FAULT_FACT_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
MAX_SAFE_FAULT_FACTS = 16


@dataclasses.dataclass(frozen=True)
class TerminalFaultDigest:
	"""Safe category/subtype evidence owned by the boundary that detects it.

	ASVS 1.5, 2.1-2.3, 13.4, and 16.2: this narrow type permits only fixed
	codes and small integer structure, preventing accidental persistence of
	exception text, paths, commands, prompts, responses, or credentials.
	"""

	category: TerminalFaultCategory
	subtype: TerminalFaultSubtype
	owner: str
	structural_facts: tuple[tuple[str, int], ...] = ()

	def __post_init__(self) -> None:
		if type(self.category) is not TerminalFaultCategory or type(self.subtype) is not TerminalFaultSubtype:
			raise RecoveryConfigurationError("Terminal fault category or subtype is invalid.")
		if _SUBTYPE_CATEGORIES[self.subtype] is not self.category:
			raise RecoveryConfigurationError("Terminal fault category and subtype conflict.")
		if type(self.owner) is not str or _SAFE_FAULT_OWNER_RE.fullmatch(self.owner) is None:
			raise RecoveryConfigurationError("Terminal fault owner is invalid.")
		if (type(self.structural_facts) is not tuple or len(self.structural_facts) > MAX_SAFE_FAULT_FACTS
			or tuple(sorted(self.structural_facts)) != self.structural_facts
			or len({key for key, _value in self.structural_facts}) != len(self.structural_facts)
			or any(type(key) is not str or _SAFE_FAULT_FACT_RE.fullmatch(key) is None
				or type(number) is not int or not 0 <= number <= 1000000
				for key, number in self.structural_facts)):
			raise RecoveryConfigurationError("Terminal fault structural facts are invalid.")

	def to_dict(self) -> dict[str, object]:
		return {
			"category": self.category.value,
			"subtype": self.subtype.value,
			"owner": self.owner,
			"structural_facts": [{"key": key, "value": value} for key, value in self.structural_facts],
		}

	@classmethod
	def from_dict(cls, value: object) -> "TerminalFaultDigest":
		if type(value) is not dict or set(value) != {"category", "subtype", "owner", "structural_facts"}:
			raise RecoveryConfigurationError("Terminal fault digest uses unsupported fields.")
		facts = value["structural_facts"]
		if type(facts) is not list or any(type(item) is not dict or set(item) != {"key", "value"} for item in facts):
			raise RecoveryConfigurationError("Terminal fault digest structural facts are invalid.")
		try:
			return cls(TerminalFaultCategory(value["category"]), TerminalFaultSubtype(value["subtype"]),
				value["owner"], tuple((item["key"], item["value"]) for item in facts))
		except (TypeError, ValueError) as error:
			raise RecoveryConfigurationError("Terminal fault digest is invalid.") from error


class RecoveryRung(enum.StrEnum):
	"""Closed, strictly descending plan order for editorial recovery paths."""

	FINAL_SYNTHESIS = "final_synthesis"
	EDITED_COMPLETE_POST = "edited_complete_post"
	WRITER_COMPLETE_POST = "writer_complete_post"
	DAILY_OUTLINE_EXPANSION = "daily_outline_expansion"
	REPOSITORY_STORY_MERGE = "repository_story_merge"
	STRONGEST_REPOSITORY_MATERIAL = "strongest_repository_material"


RUNG_ARTIFACT_TYPES: dict[RecoveryRung, type | None] = {
	RecoveryRung.FINAL_SYNTHESIS: daily_blog.artifacts.CompletePost,
	RecoveryRung.EDITED_COMPLETE_POST: daily_blog.artifacts.CompletePost,
	RecoveryRung.WRITER_COMPLETE_POST: daily_blog.artifacts.CompletePost,
	RecoveryRung.DAILY_OUTLINE_EXPANSION: daily_blog.artifacts.CompletePost,
	RecoveryRung.REPOSITORY_STORY_MERGE: daily_blog.artifacts.CompletePost,
	RecoveryRung.STRONGEST_REPOSITORY_MATERIAL: None,
}
RUNG_ORDER = tuple(RecoveryRung)
ORDINARY_NO_ARTIFACT = frozenset({
	TerminalFaultCategory.ROUTE_UNAVAILABLE,
	TerminalFaultCategory.NO_ELIGIBLE_GENERATION,
})


class RecoveryConfigurationError(RuntimeError):
	"""Typed configuration, eligibility, or provenance fault at a callable boundary."""


@dataclasses.dataclass(frozen=True)
class GenerationObservation:
	"""Bounded route facts with no response, prompt, secret, or exception text."""

	step: str
	attempted_routes: int
	successful_responses: int
	eligible_artifact_ids: tuple[str, ...]
	explicit_fault: TerminalFaultCategory | None = None

	#============================================
	def __post_init__(self) -> None:
		if type(self.step) is not str or IDENTIFIER_RE.fullmatch(self.step) is None:
			raise RecoveryConfigurationError("Recovery observation step is invalid.")
		if any(type(value) is not int or value < 0 for value in (
			self.attempted_routes, self.successful_responses,
		)) or self.successful_responses > self.attempted_routes:
			raise RecoveryConfigurationError("Recovery observation route counts are invalid.")
		if type(self.eligible_artifact_ids) is not tuple or len(self.eligible_artifact_ids) > MAX_DIGEST_EVIDENCE_REFS:
			raise RecoveryConfigurationError("Recovery observation artifact identities are invalid.")
		if any(
			type(item) is not str or daily_blog.artifacts.ARTIFACT_ID_RE.fullmatch(item) is None
			for item in self.eligible_artifact_ids
		):
			raise RecoveryConfigurationError("Recovery observation artifact identity is invalid.")
		if tuple(sorted(set(self.eligible_artifact_ids))) != self.eligible_artifact_ids:
			raise RecoveryConfigurationError("Recovery observation artifact identities are not canonical.")
		if self.explicit_fault is not None and type(self.explicit_fault) is not TerminalFaultCategory:
			raise RecoveryConfigurationError("Recovery observation terminal category is invalid.")
		if self.eligible_artifact_ids and self.successful_responses == 0:
			raise RecoveryConfigurationError("Eligible recovery artifacts require a successful response.")

	#============================================
	def to_digest_dict(self) -> dict[str, object]:
		"""Return the bounded diagnostic projection permitted in a digest."""
		return {
			"step": self.step,
			"attempted_routes": self.attempted_routes,
			"successful_responses": self.successful_responses,
			"eligible_artifact_ids": list(self.eligible_artifact_ids),
			"explicit_fault": self.explicit_fault.value if self.explicit_fault else "",
		}


#============================================
def _validate_observations(observations: tuple[GenerationObservation, ...]) -> None:
	"""Validate one bounded exact observation tuple before it is classified or written."""
	if type(observations) is not tuple or not observations or len(observations) > MAX_DIGEST_OBSERVATIONS:
		raise RecoveryConfigurationError("Recovery observations are invalid.")
	if any(type(item) is not GenerationObservation for item in observations):
		raise RecoveryConfigurationError("Recovery observations must be exact typed values.")


#============================================
def classify_pipeline_fault(observations: tuple[GenerationObservation, ...]) -> TerminalFaultCategory:
	"""Classify validated aggregate facts, never exception strings or authored text."""
	_validate_observations(observations)
	for category in (
		TerminalFaultCategory.CONFIGURATION,
		TerminalFaultCategory.EVIDENCE_UNAVAILABLE,
		TerminalFaultCategory.IMPLEMENTATION_DEFECT,
		TerminalFaultCategory.ROUTE_UNAVAILABLE,
		TerminalFaultCategory.NO_ELIGIBLE_GENERATION,
	):
		if any(item.explicit_fault is category for item in observations):
			return category
	attempted = sum(item.attempted_routes for item in observations)
	successful = sum(item.successful_responses for item in observations)
	eligible = sum(len(item.eligible_artifact_ids) for item in observations)
	if attempted > 0 and successful == 0 and eligible == 0:
		return TerminalFaultCategory.ROUTE_UNAVAILABLE
	if successful > 0 and eligible == 0:
		return TerminalFaultCategory.NO_ELIGIBLE_GENERATION
	return TerminalFaultCategory.IMPLEMENTATION_DEFECT


RecoveryOutcome = (
	daily_blog.artifacts.SelectedPeer | daily_blog.artifacts.PreservedArtifact |
	daily_blog.artifacts.DegradedPromotion | daily_blog.artifacts.NoArtifact
)


#============================================
def no_artifact_category(
	outcome: daily_blog.artifacts.NoArtifact, observation: GenerationObservation,
) -> TerminalFaultCategory:
	"""Bind a no-artifact result to the only route facts that may justify it."""
	if type(outcome) is not daily_blog.artifacts.NoArtifact or type(observation) is not GenerationObservation:
		raise RecoveryConfigurationError("Recovery no-artifact facts require exact typed values.")
	try:
		category = TerminalFaultCategory(outcome.reason)
	except ValueError as error:
		raise RecoveryConfigurationError("Recovery no-artifact category is invalid.") from error
	if observation.explicit_fault is not None and observation.explicit_fault is not category:
		raise RecoveryConfigurationError("Recovery no-artifact category conflicts with terminal facts.")
	if category is TerminalFaultCategory.ROUTE_UNAVAILABLE:
		if not (
			observation.attempted_routes > 0 and observation.successful_responses == 0
			and not observation.eligible_artifact_ids
		):
			raise RecoveryConfigurationError("Route-unavailable recovery facts are invalid.")
	elif category is TerminalFaultCategory.NO_ELIGIBLE_GENERATION:
		if not (
			observation.successful_responses > 0 and not observation.eligible_artifact_ids
		):
			raise RecoveryConfigurationError("No-eligible-generation recovery facts are invalid.")
	else:
		if observation.explicit_fault is not category or observation.eligible_artifact_ids:
			raise RecoveryConfigurationError("Terminal recovery facts are invalid.")
	return category


#============================================
def _validate_recovery_generation(
	generation: daily_blog.replication.ReplicationResult,
	expected_type: type,
	observation: GenerationObservation | None = None,
	selected_artifact: daily_blog.artifacts.EditorialArtifact | None = None,
) -> None:
	"""Bind optional retained generation facts to one recovery observation.

	The recovery seam keeps an exact ``ReplicationResult`` only when a newly
	generated peer wins.  Its bounded observation must therefore be derived from
	the same candidates rather than caller-supplied counters or identities.
	"""
	if type(generation) is not daily_blog.replication.ReplicationResult:
		raise RecoveryConfigurationError("Recovery generation must be an exact replication result.")
	if generation.expected_type is not expected_type or expected_type not in daily_blog.artifacts.ARTIFACT_TYPES:
		raise RecoveryConfigurationError("Recovery generation expected type is invalid.")
	if type(generation.candidates) is not tuple:
		raise RecoveryConfigurationError("Recovery generation candidates are invalid.")
	for candidate in generation.candidates:
		if (
			type(candidate) is not daily_blog.replication.ReplicatedCandidate
			or type(candidate.result) is not daily_blog.agents.AgentResult
			or (candidate.artifact is None) != (candidate.eligibility is None)
			or (candidate.artifact is not None and type(candidate.artifact) is not expected_type)
			or (candidate.eligibility is not None and type(candidate.eligibility) is not daily_blog.artifacts.EligibilityResult)
		):
			raise RecoveryConfigurationError("Recovery generation candidate shape is invalid.")
	eligible = tuple(item for item in generation.eligible if type(item) is expected_type)
	if observation is not None:
		if type(observation) is not GenerationObservation or (
			observation.attempted_routes != len(generation.candidates)
			or observation.successful_responses != sum(item.result.ok for item in generation.candidates)
			or observation.eligible_artifact_ids != tuple(sorted({item.artifact_id for item in eligible}))
		):
			raise RecoveryConfigurationError("Recovery generation conflicts with its observation.")
	if selected_artifact is not None and not any(item is selected_artifact for item in eligible):
		raise RecoveryConfigurationError("Recovery generation did not produce the selected artifact.")


@dataclasses.dataclass(frozen=True)
class RecoveryRungReliability:
	"""Bounded editorial facts from one invoked recovery rung."""

	rung: RecoveryRung
	summaries: tuple[daily_blog.replication.StepReliability, ...]

	def __post_init__(self) -> None:
		if type(self.rung) is not RecoveryRung or type(self.summaries) is not tuple or not self.summaries:
			raise RecoveryConfigurationError("Recovery rung reliability is invalid.")
		if any(type(item) is not daily_blog.replication.StepReliability for item in self.summaries):
			raise RecoveryConfigurationError("Recovery rung reliability summaries are invalid.")
		if len({item.step for item in self.summaries}) != len(self.summaries):
			raise RecoveryConfigurationError("Recovery rung reliability steps must be unique.")
		for item in self.summaries:
			item.validate()


def _validate_rung_reliability(
	value: tuple[RecoveryRungReliability, ...], observations: tuple[GenerationObservation, ...],
) -> None:
	"""Keep optional detailed facts aligned with invoked recovery paths."""
	if type(value) is not tuple or len(value) > len(observations):
		raise RecoveryConfigurationError("Recovery rung reliability is invalid.")
	if any(type(item) is not RecoveryRungReliability for item in value):
		raise RecoveryConfigurationError("Recovery rung reliability is invalid.")
	if len({item.rung for item in value}) != len(value):
		raise RecoveryConfigurationError("Recovery rung reliability repeats a rung.")


@dataclasses.dataclass(frozen=True)
class RecoveryAttempt:
	"""One typed rung outcome plus its exact bounded generation observation."""

	outcome: RecoveryOutcome
	observation: GenerationObservation
	recovery_generation: daily_blog.replication.ReplicationResult | None = None
	step_reliability: tuple[daily_blog.replication.StepReliability, ...] = ()
	stage6_observations: tuple["daily_blog.stage6.Stage6BatchObservation", ...] = ()

	#============================================
	def __post_init__(self) -> None:
		if type(self.outcome) not in (
			daily_blog.artifacts.SelectedPeer, daily_blog.artifacts.PreservedArtifact,
			daily_blog.artifacts.DegradedPromotion, daily_blog.artifacts.NoArtifact,
		) or type(self.observation) is not GenerationObservation:
			raise RecoveryConfigurationError("Recovery attempt uses an unsupported typed outcome.")
		if type(self.outcome) is daily_blog.artifacts.NoArtifact:
			no_artifact_category(self.outcome, self.observation)
		else:
			if self.observation.explicit_fault is not None or (
				self.observation.successful_responses == 0
				or self.outcome.artifact.artifact_id not in self.observation.eligible_artifact_ids
			):
				raise RecoveryConfigurationError(
					"Recovered artifact must match one successful non-terminal observation."
				)
		if self.recovery_generation is not None:
			_validate_recovery_generation(
				self.recovery_generation, self.outcome.expected_type, self.observation,
				None if type(self.outcome) is daily_blog.artifacts.NoArtifact else self.outcome.artifact,
			)
		if type(self.step_reliability) is not tuple or any(
			type(item) is not daily_blog.replication.StepReliability for item in self.step_reliability
		):
			raise RecoveryConfigurationError("Recovery attempt step reliability is invalid.")
		if len({item.step for item in self.step_reliability}) != len(self.step_reliability):
			raise RecoveryConfigurationError("Recovery attempt reliability steps must be unique.")
		for item in self.step_reliability:
			item.validate()
		_validate_stage6_observations(self.stage6_observations, "Recovery attempt")


@dataclasses.dataclass(frozen=True)
class RecoveryPath:
	"""One path on the closed editorial ladder; no callback owns durable writes."""

	rung: RecoveryRung
	invoke: collections.abc.Callable[[], RecoveryAttempt]

	#============================================
	def __post_init__(self) -> None:
		if type(self.rung) is not RecoveryRung or not callable(self.invoke):
			raise RecoveryConfigurationError("Recovery path shape is invalid.")


@dataclasses.dataclass(frozen=True)
class RecoveryIncumbent:
	"""An eligible artifact and the rung that established it as strongest."""

	artifact: daily_blog.artifacts.EditorialArtifact
	rung: RecoveryRung

	#============================================
	def __post_init__(self) -> None:
		if type(self.artifact) not in daily_blog.artifacts.ARTIFACT_TYPES or type(self.rung) is not RecoveryRung:
			raise RecoveryConfigurationError("Recovery incumbent is invalid.")
		expected_type = RUNG_ARTIFACT_TYPES[self.rung]
		if expected_type is not None and type(self.artifact) is not expected_type:
			raise RecoveryConfigurationError("Recovery incumbent does not match its rung.")
		if expected_type is None and type(self.artifact) not in {
			daily_blog.artifacts.RepoOutline, daily_blog.artifacts.RepoStory,
		}:
			raise RecoveryConfigurationError("Repository material incumbent must be repository-scoped.")


@dataclasses.dataclass(frozen=True)
class RecoveryResult:
	"""A retained or promoted whole publishable artifact plus closed-ladder depth.

	A result either follows an attempted rung, so it retains one observation per
	depth, or returns a higher incumbent before invoking the current lower rung,
	so it has exactly one fewer observation than its depth.
	"""

	artifact: daily_blog.artifacts.CompletePost
	depth: int
	observations: tuple[GenerationObservation, ...]
	recovery_generation: daily_blog.replication.ReplicationResult | None = None
	rung_reliability: tuple[RecoveryRungReliability, ...] = ()
	stage6_observations: tuple["daily_blog.stage6.Stage6BatchObservation", ...] = ()

	#============================================
	def __post_init__(self) -> None:
		if (
			type(self.artifact) is not daily_blog.artifacts.CompletePost
			or type(self.depth) is not int
			or not 0 < self.depth <= len(RUNG_ORDER)
		):
			raise RecoveryConfigurationError("Recovery result is invalid.")
		if type(self.observations) is not tuple or len(self.observations) > MAX_DIGEST_OBSERVATIONS:
			raise RecoveryConfigurationError("Recovery result observations are invalid.")
		if any(type(item) is not GenerationObservation for item in self.observations):
			raise RecoveryConfigurationError("Recovery result observations must be exact typed values.")
		if len(self.observations) not in {self.depth - 1, self.depth}:
			raise RecoveryConfigurationError("Recovery result depth conflicts with its observations.")
		if self.recovery_generation is not None:
			if len(self.observations) != self.depth:
				raise RecoveryConfigurationError("Retained recovery generation requires a selected attempt.")
			_validate_recovery_generation(
				self.recovery_generation, daily_blog.artifacts.CompletePost,
				self.observations[-1], self.artifact,
			)
		_validate_rung_reliability(self.rung_reliability, self.observations)
		_validate_stage6_observations(self.stage6_observations, "Recovery result")


@dataclasses.dataclass(frozen=True)
class PipelineFault:
	"""Terminal state retaining strongest prior provenance without publication.

	``depth`` is a closed-ladder position: zero records a pre-ladder terminal
	diagnosis and a positive value records no more calls than the closed ladder
	and its retained observations.  The category is always re-derived from those
	validated observations, including explicit terminal facts from a bounded
	upstream boundary.
	"""

	category: TerminalFaultCategory
	depth: int
	strongest_artifact_id: str
	strongest_artifact_type: str
	observations: tuple[GenerationObservation, ...]
	rung_reliability: tuple[RecoveryRungReliability, ...] = ()
	terminal_fault: TerminalFaultDigest | None = None
	stage6_observations: tuple["daily_blog.stage6.Stage6BatchObservation", ...] = ()

	#============================================
	def __post_init__(self) -> None:
		if (
			type(self.category) is not TerminalFaultCategory
			or type(self.depth) is not int
			or not 0 <= self.depth <= len(RUNG_ORDER)
		):
			raise RecoveryConfigurationError("Pipeline fault category or depth is invalid.")
		if type(self.strongest_artifact_id) is not str or type(self.strongest_artifact_type) is not str:
			raise RecoveryConfigurationError("Pipeline fault artifact identity is invalid.")
		if bool(self.strongest_artifact_id) != bool(self.strongest_artifact_type):
			raise RecoveryConfigurationError("Pipeline fault artifact identity is incomplete.")
		if self.strongest_artifact_id and daily_blog.artifacts.ARTIFACT_ID_RE.fullmatch(self.strongest_artifact_id) is None:
			raise RecoveryConfigurationError("Pipeline fault artifact identity is invalid.")
		if self.strongest_artifact_type and self.strongest_artifact_type not in {
			item.__name__ for item in daily_blog.artifacts.ARTIFACT_TYPES
		}:
			raise RecoveryConfigurationError("Pipeline fault artifact type is invalid.")
		_validate_observations(self.observations)
		_validate_rung_reliability(self.rung_reliability, self.observations)
		if self.depth > len(self.observations):
			raise RecoveryConfigurationError("Pipeline fault depth exceeds its observations.")
		if self.category is not classify_pipeline_fault(self.observations):
			raise RecoveryConfigurationError("Pipeline fault category conflicts with observations.")
		if self.terminal_fault is not None:
			if type(self.terminal_fault) is not TerminalFaultDigest or self.terminal_fault.category is not self.category:
				raise RecoveryConfigurationError("Pipeline fault safe diagnostic conflicts with its category.")
		_validate_stage6_observations(self.stage6_observations, "Pipeline fault")


class PipelineFaultError(RuntimeError):
	"""Expose one validated terminal pipeline diagnosis at a public boundary."""

	#============================================
	def __init__(self, fault: PipelineFault, digest_sha256: str,
		artifact_name: str = "recovery_fault.json") -> None:
		if type(fault) is not PipelineFault:
			raise RecoveryConfigurationError("Pipeline fault error requires an exact fault.")
		if type(digest_sha256) is not str or SHA256_RE.fullmatch(digest_sha256) is None:
			raise RecoveryConfigurationError("Pipeline fault error digest identity is invalid.")
		if type(artifact_name) is not str or artifact_name != "recovery_fault.json":
			raise RecoveryConfigurationError("Pipeline fault error artifact identity is invalid.")
		# Keep exception text fixed so a public exception cannot serialize model or route details.
		super().__init__("Daily blog pipeline fault.")
		self.fault = fault
		self.category = fault.category
		self.digest_sha256 = digest_sha256
		self.artifact_name = artifact_name


#============================================
def _validate_paths(paths: tuple[RecoveryPath, ...]) -> None:
	"""Permit plan-order subsequences while rejecting duplicated, upward, or terminal rungs."""
	if type(paths) is not tuple or not paths or len(paths) > len(RUNG_ORDER):
		raise RecoveryConfigurationError("Recovery ladder paths are invalid.")
	if any(type(path) is not RecoveryPath for path in paths):
		raise RecoveryConfigurationError("Recovery ladder paths must be exact typed values.")
	positions = tuple(RUNG_ORDER.index(path.rung) for path in paths)
	if positions != tuple(sorted(positions)) or len(set(positions)) != len(positions):
		raise RecoveryConfigurationError("Recovery ladder rungs must descend without repeats.")
	if RecoveryRung.STRONGEST_REPOSITORY_MATERIAL in tuple(path.rung for path in paths):
		raise RecoveryConfigurationError("Strongest repository material is terminal provenance, not a recovery call.")


#============================================
def _fault(category: TerminalFaultCategory, depth: int, incumbent: RecoveryIncumbent | None,
	observations: tuple[GenerationObservation, ...],
	rung_reliability: tuple[RecoveryRungReliability, ...] = (),
	stage6_observations: tuple["daily_blog.stage6.Stage6BatchObservation", ...] = (),
) -> PipelineFault:
	"""Build one validated terminal result without copying unsafe diagnostic text."""
	return PipelineFault(
		category, depth, "" if incumbent is None else incumbent.artifact.artifact_id,
		"" if incumbent is None else type(incumbent.artifact).__name__, observations, rung_reliability,
		None, stage6_observations,
	)


#============================================
def recover_ladder(
	paths: tuple[RecoveryPath, ...], incumbent: RecoveryIncumbent | None,
	eligible: collections.abc.Callable[[daily_blog.artifacts.EditorialArtifact], bool],
	promote: collections.abc.Callable[[daily_blog.artifacts.CompletePost | None, daily_blog.artifacts.CompletePost], daily_blog.artifacts.CompletePost],
) -> RecoveryResult | PipelineFault:
	"""Run ordered editorial paths; never concatenate or inspect authored Markdown."""
	_validate_paths(paths)
	if incumbent is not None and type(incumbent) is not RecoveryIncumbent:
		raise RecoveryConfigurationError("Recovery incumbent must be an exact typed value.")
	if not callable(eligible) or not callable(promote):
		raise RecoveryConfigurationError("Recovery policy callables are invalid.")
	if incumbent is not None and not eligible(incumbent.artifact):
		raise RecoveryConfigurationError("Recovery incumbent must remain mechanically eligible.")
	observations: list[GenerationObservation] = []
	rung_reliability: list[RecoveryRungReliability] = []
	stage6_observations: list[object] = []
	for depth, path in enumerate(paths, start=1):
		if incumbent is not None and RUNG_ORDER.index(incumbent.rung) < RUNG_ORDER.index(path.rung):
			if type(incumbent.artifact) is not daily_blog.artifacts.CompletePost:
				raise RecoveryConfigurationError("Lower recovery rung cannot replace repository material.")
			return RecoveryResult(incumbent.artifact, depth, tuple(observations))
		attempt = path.invoke()
		if type(attempt) is not RecoveryAttempt:
			raise RecoveryConfigurationError("Recovery path returned an invalid attempt.")
		observations.append(attempt.observation)
		stage6_observations.extend(attempt.stage6_observations)
		if attempt.step_reliability:
			rung_reliability.append(RecoveryRungReliability(path.rung, attempt.step_reliability))
		outcome = attempt.outcome
		expected_type = RUNG_ARTIFACT_TYPES[path.rung]
		if expected_type is None:
			raise RecoveryConfigurationError("Recovery terminal provenance cannot return an artifact.")
		if outcome.expected_type is not expected_type:
			raise RecoveryConfigurationError("Recovery path returned the wrong typed rung.")
		if type(outcome) is daily_blog.artifacts.NoArtifact:
			category = no_artifact_category(outcome, attempt.observation)
			if category not in ORDINARY_NO_ARTIFACT:
				return _fault(category, depth, incumbent, tuple(observations), tuple(rung_reliability), tuple(stage6_observations))
			continue
		candidate = outcome.artifact
		if type(candidate) is not expected_type or not eligible(candidate):
			raise RecoveryConfigurationError("Recovery path returned an ineligible artifact.")
		prior = None if incumbent is None else incumbent.artifact
		if prior is not None and type(prior) is not daily_blog.artifacts.CompletePost:
			# Repository material is lower-rung provenance, never a publishable peer.
			# A higher whole post may replace it without a cross-type comparison.
			return RecoveryResult(candidate, depth, tuple(observations), attempt.recovery_generation,
				tuple(rung_reliability), tuple(stage6_observations))
		chosen = promote(prior, candidate)
		if type(chosen) is not daily_blog.artifacts.CompletePost or not eligible(chosen):
			raise RecoveryConfigurationError("Recovery promotion returned an ineligible artifact.")
		allowed_ids = {candidate.artifact_id}
		if prior is not None:
			allowed_ids.add(prior.artifact_id)
		if chosen.artifact_id not in allowed_ids:
			raise RecoveryConfigurationError("Recovery promotion returned an unknown artifact.")
		return RecoveryResult(
			chosen, depth, tuple(observations),
			attempt.recovery_generation if chosen is candidate else None,
			tuple(rung_reliability), tuple(stage6_observations),
		)
	return _fault(classify_pipeline_fault(tuple(observations)), len(paths), incumbent, tuple(observations),
		tuple(rung_reliability), tuple(stage6_observations))


#============================================
def recover_at_outer_boundary(
	paths: tuple[RecoveryPath, ...], incumbent: RecoveryIncumbent | None,
	eligible: collections.abc.Callable[[daily_blog.artifacts.EditorialArtifact], bool],
	promote: collections.abc.Callable[[daily_blog.artifacts.CompletePost | None, daily_blog.artifacts.CompletePost], daily_blog.artifacts.CompletePost],
) -> RecoveryResult | PipelineFault:
	"""Contain only unexpected ordinary defects after typed errors are separated."""
	try:
		return recover_ladder(paths, incumbent, eligible, promote)
	except RecoveryConfigurationError:
		raise
	except Exception:
		observation = GenerationObservation("outer_boundary", 0, 0, (), TerminalFaultCategory.IMPLEMENTATION_DEFECT)
		return _fault(TerminalFaultCategory.IMPLEMENTATION_DEFECT, 0, incumbent, (observation,))


@dataclasses.dataclass(frozen=True)
class EvidenceDigestPacket:
	"""One packet identity and content hash permitted in a terminal digest."""

	packet_id: str
	content_sha256: str
	evidence_refs: tuple[str, ...]

	#============================================
	def __post_init__(self) -> None:
		if any(type(value) is not str or SHA256_RE.fullmatch(value) is None for value in (
			self.packet_id, self.content_sha256,
		)) or type(self.evidence_refs) is not tuple or len(self.evidence_refs) > MAX_DIGEST_EVIDENCE_REFS:
			raise RecoveryConfigurationError("Evidence digest packet identity is invalid.")
		if any(type(value) is not str or IDENTIFIER_RE.fullmatch(value) is None for value in self.evidence_refs):
			raise RecoveryConfigurationError("Evidence digest evidence reference is invalid.")
		if tuple(sorted(set(self.evidence_refs))) != self.evidence_refs:
			raise RecoveryConfigurationError("Evidence digest evidence references are not canonical.")


@dataclasses.dataclass(frozen=True)
class EvidenceDigestStep:
	"""One bounded namespaced mechanism summary without model-authored content."""

	step_key: str
	outcome: str
	attempted: int
	succeeded: int
	failed: int
	reused: int
	repaired: int
	disagreements: int
	best_artifact_id: str
	reasons: tuple[str, ...]

	#============================================
	def __post_init__(self) -> None:
		if type(self.step_key) is not str or STAGE_KEY_RE.fullmatch(self.step_key) is None:
			raise RecoveryConfigurationError("Evidence digest step key is invalid.")
		if type(self.outcome) is not str or self.outcome not in {"succeeded", "degraded"}:
			raise RecoveryConfigurationError("Evidence digest step outcome is invalid.")
		counts = (
			self.attempted, self.succeeded, self.failed, self.reused,
			self.repaired, self.disagreements,
		)
		if any(type(value) is not int or value < 0 for value in counts):
			raise RecoveryConfigurationError("Evidence digest step counts are invalid.")
		if self.succeeded + self.failed != self.attempted:
			raise RecoveryConfigurationError("Evidence digest step attempts are inconsistent.")
		if self.reused > self.succeeded or self.repaired > self.succeeded:
			raise RecoveryConfigurationError("Evidence digest step reuse or repair is invalid.")
		if type(self.best_artifact_id) is not str:
			raise RecoveryConfigurationError("Evidence digest step artifact identity is invalid.")
		if self.best_artifact_id and daily_blog.artifacts.ARTIFACT_ID_RE.fullmatch(self.best_artifact_id) is None:
			raise RecoveryConfigurationError("Evidence digest step artifact identity is invalid.")
		if type(self.reasons) is not tuple or len(self.reasons) > MAX_STEP_REASONS:
			raise RecoveryConfigurationError("Evidence digest step reasons are invalid.")
		if any(type(item) is not str or IDENTIFIER_RE.fullmatch(item) is None for item in self.reasons):
			raise RecoveryConfigurationError("Evidence digest step reason is invalid.")
		if tuple(sorted(set(self.reasons))) != self.reasons:
			raise RecoveryConfigurationError("Evidence digest step reasons are not canonical.")
		if self.outcome == "succeeded" and self.reasons:
			raise RecoveryConfigurationError("Successful evidence digest step has reasons.")

	#============================================
	def to_dict(self) -> dict[str, object]:
		"""Return one canonical, response-free summary record."""
		return {
			"step_key": self.step_key,
			"outcome": self.outcome,
			"attempted": self.attempted,
			"succeeded": self.succeeded,
			"failed": self.failed,
			"reused": self.reused,
			"repaired": self.repaired,
			"disagreements": self.disagreements,
			"best_artifact_id": self.best_artifact_id,
			"reasons": list(self.reasons),
		}


@dataclasses.dataclass(frozen=True)
class EvidenceDigestInput:
	"""All and only bounded non-secret fields for a coordinator-owned digest write."""

	report_date: str
	stage_key: str
	steps: tuple[EvidenceDigestStep, ...]
	packets: tuple[EvidenceDigestPacket, ...]
	prompt_identities: tuple[str, ...]
	rubric_identities: tuple[str, ...]
	fault: PipelineFault
	promoted_artifact_ids: tuple[str, ...] = ()
	ranking_promotion_ids: tuple[str, ...] = ()
	allowed_repositories: tuple[str, ...] = ()

	#============================================
	def __post_init__(self) -> None:
		if type(self.report_date) is not str or DATE_RE.fullmatch(self.report_date) is None:
			raise RecoveryConfigurationError("Evidence digest report date is invalid.")
		try:
			datetime.date.fromisoformat(self.report_date)
		except ValueError as error:
			raise RecoveryConfigurationError("Evidence digest report date is invalid.") from error
		if type(self.fault) is not PipelineFault:
			raise RecoveryConfigurationError("Evidence digest fault is invalid.")
		if type(self.stage_key) is not str or STAGE_KEY_RE.fullmatch(self.stage_key) is None:
			raise RecoveryConfigurationError("Evidence digest stage key is invalid.")
		if type(self.steps) is not tuple or len(self.steps) > MAX_DIGEST_STEPS:
			raise RecoveryConfigurationError("Evidence digest steps are invalid.")
		if any(type(item) is not EvidenceDigestStep for item in self.steps):
			raise RecoveryConfigurationError("Evidence digest steps must be exact typed values.")
		step_keys = tuple(item.step_key for item in self.steps)
		if tuple(sorted(step_keys)) != step_keys or len(set(step_keys)) != len(step_keys):
			raise RecoveryConfigurationError("Evidence digest step keys are not canonical.")
		if type(self.packets) is not tuple or len(self.packets) > MAX_DIGEST_PACKETS or any(type(item) is not EvidenceDigestPacket for item in self.packets):
			raise RecoveryConfigurationError("Evidence digest packets are invalid.")
		if not self.packets and self.fault.category is not TerminalFaultCategory.EVIDENCE_UNAVAILABLE:
			raise RecoveryConfigurationError("Only unavailable evidence may have no packet provenance.")
		if self.packets and (tuple(sorted(item.packet_id for item in self.packets)) != tuple(item.packet_id for item in self.packets) or len({item.packet_id for item in self.packets}) != len(self.packets)):
			raise RecoveryConfigurationError("Evidence digest packet identities are not canonical.")
		for values, field in ((self.prompt_identities, "prompt"), (self.rubric_identities, "rubric")):
			if type(values) is not tuple or len(values) > MAX_DIGEST_EVIDENCE_REFS or any(type(item) is not str or SHA256_RE.fullmatch(item) is None for item in values) or tuple(sorted(set(values))) != values:
				raise RecoveryConfigurationError(f"Evidence digest {field} identities are invalid.")
		if type(self.promoted_artifact_ids) is not tuple or len(self.promoted_artifact_ids) > MAX_PROMOTED_ARTIFACT_IDS or any(type(item) is not str or daily_blog.artifacts.ARTIFACT_ID_RE.fullmatch(item) is None for item in self.promoted_artifact_ids) or tuple(sorted(set(self.promoted_artifact_ids))) != self.promoted_artifact_ids:
			raise RecoveryConfigurationError("Evidence digest promoted artifacts are invalid.")
		if type(self.ranking_promotion_ids) is not tuple or len(self.ranking_promotion_ids) > MAX_PROMOTED_ARTIFACT_IDS or any(type(item) is not str or RANKING_PROMOTION_ID_RE.fullmatch(item) is None for item in self.ranking_promotion_ids) or tuple(sorted(set(self.ranking_promotion_ids))) != self.ranking_promotion_ids:
			raise RecoveryConfigurationError("Evidence digest ranking promotions are invalid.")
		if type(self.allowed_repositories) is not tuple or any(
			type(item) is not str or not item for item in self.allowed_repositories
		) or tuple(sorted(set(self.allowed_repositories))) != self.allowed_repositories:
			raise RecoveryConfigurationError("Evidence digest allowed repository scope is invalid.")


#============================================
def canonical_evidence_digest(value: EvidenceDigestInput) -> tuple[dict[str, object], str]:
	"""Return one canonical safe payload and SHA-256; the coordinator alone writes it."""
	if type(value) is not EvidenceDigestInput:
		raise RecoveryConfigurationError("Evidence digest input must be exact.")
	payload = {
		"schema_version": RECOVERY_SCHEMA_VERSION,
		"report_date": value.report_date,
		"stage_key": value.stage_key,
		"steps": [item.to_dict() for item in value.steps],
		"packets": [{"packet_id": item.packet_id, "content_sha256": item.content_sha256,
			"evidence_refs": list(item.evidence_refs)} for item in value.packets],
		"prompt_identities": list(value.prompt_identities),
		"rubric_identities": list(value.rubric_identities),
		"promoted_artifact_ids": list(value.promoted_artifact_ids),
		"ranking_promotion_ids": list(value.ranking_promotion_ids),
		"allowed_repositories": list(value.allowed_repositories),
		"retained_artifact_id": value.fault.strongest_artifact_id,
		"retained_artifact_type": value.fault.strongest_artifact_type,
		"ladder_depth": value.fault.depth,
		"category": value.fault.category.value,
		"terminal_fault": (
			{} if value.fault.terminal_fault is None else value.fault.terminal_fault.to_dict()
		),
		"attempts": [item.to_digest_dict() for item in value.fault.observations],
	}
	return payload, daily_blog.io_utils.hash_value(payload)

"""Pure, bounded Stage 6 complete-post attempt topology.

This module deliberately owns semantic slots only.  Route construction adds
actual candidate and repair-response hashes later; transport retries are a
bounded execution cost of the same immutable slot.
"""

# Standard Library
import dataclasses
import hashlib
import json
import re

STAGE6_ATTEMPT_PLAN_SCHEMA_VERSION = "vosslab.daily-blog.stage6-attempt-plan.v1"
STAGE6_COMPLETE_POST = "stage6/complete_post"
RUNG_ORDER = ("primary", "daily_outline_expansion", "repository_story_merge")
WORK_KINDS = frozenset({"generation", "review", "review_repair"})
ROLES = frozenset({"writer", "editor", "reviewer", "reviewer_repair"})
MAX_REPLICAS = 16
MAX_REVIEWERS = 16
MAX_TRANSPORT_RETRY_ATTEMPTS = 3
MAX_FRESH_BATCHES = 3
MAX_PAIR_INDEX = 528
MAX_PLANNED_ATTEMPTS = 10_000
MAX_ROUTE_CALLS = 40_000
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


#============================================
def _bounded_int(value: object, label: str, minimum: int, maximum: int) -> int:
	"""Return one exact bounded integer at this trusted allocation boundary."""
	if type(value) is not int or not minimum <= value <= maximum:
		raise RuntimeError(f"Stage 6 {label} must be an integer from {minimum} through {maximum}.")
	return value


#============================================
def _canonical_hash(value: object) -> str:
	"""Hash public plan coordinates without embedding prompt or candidate bytes."""
	encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
	return hashlib.sha256(encoded).hexdigest()


#============================================
def _prompt_identity(rung: str, role: str) -> str:
	"""Return the non-secret version label for one sealed prompt boundary."""
	return f"stage6/{rung}/{role}/prompt-v1"


#============================================
def _semantic_input_identity(
	rung: str, batch_index: int, role: str, replica_index: int,
	pair_index: int, display_order: int,
) -> str:
	"""Bind a fresh batch without admitting prompt or candidate contents."""
	return _canonical_hash({
		"stage": STAGE6_COMPLETE_POST,
		"rung": rung,
		"batch_index": batch_index,
		"role": role,
		"replica_index": replica_index,
		"pair_index": pair_index,
		"display_order": display_order,
	})


#============================================
@dataclasses.dataclass(frozen=True)
class Stage6AttemptPolicy:
	"""Bounded replication, retry, and fresh-sample policy for one run.

	ASVS 2.1/2.2 and 13.2: exact type and cross-field validation rejects an
	exhausting topology before allocating slots or invoking a route.
	"""

	writer_count: int
	editor_count: int
	reviewer_count: int
	transport_retry_attempts: int
	fresh_batch_count: int

	#============================================
	def __post_init__(self) -> None:
		"""Validate the complete finite policy envelope before expansion."""
		_bounded_int(self.writer_count, "writer_count", 2, MAX_REPLICAS)
		_bounded_int(self.editor_count, "editor_count", 2, MAX_REPLICAS)
		_bounded_int(self.reviewer_count, "reviewer_count", 1, MAX_REVIEWERS)
		_bounded_int(
			self.transport_retry_attempts,
			"transport_retry_attempts",
			0,
			MAX_TRANSPORT_RETRY_ATTEMPTS,
		)
		_bounded_int(self.fresh_batch_count, "fresh_batch_count", 1, MAX_FRESH_BATCHES)
		if self.planned_attempt_upper_bound > MAX_PLANNED_ATTEMPTS:
			raise RuntimeError("Stage 6 policy exceeds the planned-attempt ceiling.")
		if self.maximum_route_calls_upper_bound > MAX_ROUTE_CALLS:
			raise RuntimeError("Stage 6 policy exceeds the route-call ceiling.")

	#============================================
	@property
	def planned_attempt_upper_bound(self) -> int:
		"""Return every primary and recovery slot before plan allocation."""
		primary = _rung_attempt_count(self, includes_incumbent=True)
		recovery = _rung_attempt_count(self, includes_incumbent=False)
		return self.fresh_batch_count * (primary + (2 * recovery))

	#============================================
	@property
	def maximum_route_calls_upper_bound(self) -> int:
		"""Return physical route capacity including bounded same-slot retries."""
		return self.planned_attempt_upper_bound * (self.transport_retry_attempts + 1)


#============================================
@dataclasses.dataclass(frozen=True)
class PlannedStage6Attempt:
	"""One immutable semantic slot in the complete-post attempt topology.

	ASVS 2.3 and 15.4: workers receive an immutable validated slot.  The slot
	does not carry prompts, responses, paths, commands, or retry ordinals.
	"""

	stage: str
	rung: str
	batch_index: int
	work_kind: str
	role: str
	replica_index: int
	pair_index: int
	display_order: int
	prompt_identity: str
	semantic_input_identity: str
	repair_of_identity: str = ""

	#============================================
	def __post_init__(self) -> None:
		"""Reject malformed coordinates and forged repair linkage."""
		if self.stage != STAGE6_COMPLETE_POST or self.rung not in RUNG_ORDER:
			raise RuntimeError("Stage 6 attempt stage or rung is invalid.")
		if self.work_kind not in WORK_KINDS or self.role not in ROLES:
			raise RuntimeError("Stage 6 attempt work kind or role is invalid.")
		_bounded_int(self.batch_index, "batch_index", 0, MAX_FRESH_BATCHES - 1)
		if self.work_kind == "generation":
			if self.role not in {"writer", "editor"}:
				raise RuntimeError("Stage 6 generation role is invalid.")
			_bounded_int(self.replica_index, "replica_index", 1, MAX_REPLICAS)
			if self.pair_index != 0 or self.display_order != 0 or self.repair_of_identity:
				raise RuntimeError("Stage 6 generation coordinates are invalid.")
		else:
			expected_role = "reviewer" if self.work_kind == "review" else "reviewer_repair"
			if self.role != expected_role:
				raise RuntimeError("Stage 6 review role is invalid.")
			_bounded_int(self.replica_index, "replica_index", 1, MAX_REVIEWERS)
			_bounded_int(self.pair_index, "pair_index", 1, MAX_PAIR_INDEX)
			_bounded_int(self.display_order, "display_order", 1, 2)
			if self.work_kind == "review" and self.repair_of_identity:
				raise RuntimeError("Stage 6 review cannot name a repair source.")
		if type(self.prompt_identity) is not str or self.prompt_identity != _prompt_identity(self.rung, self.role):
			raise RuntimeError("Stage 6 prompt identity is invalid.")
		expected_input = _semantic_input_identity(
			self.rung,
			self.batch_index,
			self.role,
			self.replica_index,
			self.pair_index,
			self.display_order,
		)
		if type(self.semantic_input_identity) is not str or self.semantic_input_identity != expected_input:
			raise RuntimeError("Stage 6 semantic input identity is invalid.")
		if self.work_kind == "review_repair":
			expected_repair = _review_semantic_identity(
				self.rung,
				self.batch_index,
				self.replica_index,
				self.pair_index,
				self.display_order,
			)
			if type(self.repair_of_identity) is not str or self.repair_of_identity != expected_repair:
				raise RuntimeError("Stage 6 repair source semantic identity is invalid.")

	#============================================
	@property
	def semantic_identity(self) -> str:
		"""Return the stable slot identity; retries never change this digest."""
		return _canonical_hash(dataclasses.asdict(self))


#============================================
@dataclasses.dataclass(frozen=True)
class Stage6AttemptPlan:
	"""The exact immutable maximum topology admitted for one Stage 6 run."""

	policy: Stage6AttemptPolicy
	attempts: tuple[PlannedStage6Attempt, ...]

	#============================================
	def __post_init__(self) -> None:
		"""Accept only the complete ordered canonical topology for this policy."""
		if type(self.policy) is not Stage6AttemptPolicy or type(self.attempts) is not tuple:
			raise RuntimeError("Stage 6 plan requires exact immutable policy and attempts.")
		expected = _canonical_attempts(self.policy)
		if self.attempts != expected:
			raise RuntimeError("Stage 6 plan must equal its complete canonical topology.")
		identities = self.semantic_identities
		if len(identities) != len(set(identities)):
			raise RuntimeError("Stage 6 plan semantic identities must be unique.")

	#============================================
	@property
	def semantic_identities(self) -> tuple[str, ...]:
		"""Return the immutable canonical slot order used by AttemptLedger."""
		return tuple(attempt.semantic_identity for attempt in self.attempts)

	#============================================
	@property
	def maximum_attempts(self) -> int:
		"""Return maximum semantic reservations, distinct from realized dispatch."""
		return len(self.attempts)

	#============================================
	@property
	def maximum_route_calls(self) -> int:
		"""Reserve finite retry capacity before dispatch (ASVS 13.2 and 15.2)."""
		return self.maximum_attempts * (self.policy.transport_retry_attempts + 1)

	#============================================
	@property
	def terminal_bounds(self) -> dict[str, int]:
		"""Expose finite terminal limits without claiming any realized result."""
		return {
			"maximum_planned_attempts": self.maximum_attempts,
			"maximum_route_calls": self.maximum_route_calls,
			"global_planned_attempt_ceiling": MAX_PLANNED_ATTEMPTS,
			"global_route_call_ceiling": MAX_ROUTE_CALLS,
			"maximum_fresh_batches": self.policy.fresh_batch_count,
			"eligible_promotions_to_terminate": 1,
		}

	#============================================
	def attempts_for(self, rung: str, batch_index: int) -> tuple[PlannedStage6Attempt, ...]:
		"""Return maximum templates for one rung/batch, never realized facts."""
		self._validate_boundary(rung, batch_index)
		return tuple(
			attempt for attempt in self.attempts
			if attempt.rung == rung and attempt.batch_index == batch_index
		)

	#============================================
	def terminal_prefix(self, rung: str, batch_index: int) -> tuple[PlannedStage6Attempt, ...]:
		"""Return the ordered maximum prefix through a promotion barrier."""
		self._validate_boundary(rung, batch_index)
		boundary = (RUNG_ORDER.index(rung), batch_index)
		return tuple(attempt for attempt in self.attempts if _rung_batch_order(attempt) <= boundary)

	#============================================
	def remaining_after_promotion(
		self, rung: str, batch_index: int,
	) -> tuple[PlannedStage6Attempt, ...]:
		"""Return maximum templates after a barrier without fabricating skips."""
		prefix_length = len(self.terminal_prefix(rung, batch_index))
		return self.attempts[prefix_length:]

	#============================================
	def materialization_templates(
		self, rung: str, batch_index: int,
	) -> tuple[PlannedStage6Attempt, ...]:
		"""Expose candidate-dependent templates for later dispatch selection.

		Callers select only slots whose actual candidate inputs exist while
		retaining this order. This API exposes templates only: it records neither
		dispatch nor ``skipped_after_promotion`` facts.
		"""
		return self.attempts_for(rung, batch_index)

	#============================================
	def materialize(
		self,
		final_rung: str,
		final_batch_index: int,
		available_generation_slot_ids: tuple[str, ...],
		candidate_pair_bindings: tuple["Stage6CandidatePairBinding", ...] = (),
		repair_source_slot_ids: tuple[str, ...] = (),
	) -> "MaterializedStage6AttemptPlan":
		"""Build one ordered dispatch view from actual candidate availability.

		The canonical plan remains the reservation and topology authority.  This
		method admits generation slots directly, while it derives every review and
		repair from a typed pair witness for two actual candidate identities.  It
		cannot add work, reorder work, or reach past the named terminal
		materialization.  A bare review slot is deliberately not an API input.
		"""
		return MaterializedStage6AttemptPlan(
			self,
			final_rung,
			final_batch_index,
			available_generation_slot_ids,
			candidate_pair_bindings,
			_materialized_attempts(
				self,
				final_rung,
				final_batch_index,
				available_generation_slot_ids,
				candidate_pair_bindings,
				repair_source_slot_ids,
			),
			repair_source_slot_ids,
		)

	#============================================
	def _validate_boundary(self, rung: str, batch_index: int) -> None:
		"""Reject boundaries outside the pre-admitted rung/batch lattice."""
		if rung not in RUNG_ORDER or type(batch_index) is not int or not 0 <= batch_index < self.policy.fresh_batch_count:
			raise RuntimeError("Stage 6 terminal boundary is invalid.")


#============================================
@dataclasses.dataclass(frozen=True)
class Stage6CandidatePairBinding:
	"""Validated dynamic peer-pair witness for derived review work.

	``pair_index`` is assigned only after the caller sorts actual peer pairs by
	the two safe opaque candidate digests.  The maximum topology reserves all
	possible pair indices, but this binding identifies which concrete peers are
	present for a particular rung and fresh batch. Execution-time materialization
	proves that these digests bind to the actual candidate inputs.
	"""

	rung: str
	batch_index: int
	pair_index: int
	first_candidate_identity: str
	second_candidate_identity: str

	#============================================
	def __post_init__(self) -> None:
		"""Reject unsafe, unordered, or self-paired candidate witnesses."""
		if self.rung not in RUNG_ORDER:
			raise RuntimeError("Stage 6 candidate pair rung is invalid.")
		_bounded_int(self.batch_index, "candidate pair batch_index", 0, MAX_FRESH_BATCHES - 1)
		_bounded_int(self.pair_index, "candidate pair pair_index", 1, MAX_PAIR_INDEX)
		if any(type(value) is not str or SHA256_RE.fullmatch(value) is None for value in (
			self.first_candidate_identity,
			self.second_candidate_identity,
		)):
			raise RuntimeError("Stage 6 candidate pair identities must be SHA-256 digests.")
		if self.first_candidate_identity >= self.second_candidate_identity:
			raise RuntimeError("Stage 6 candidate pair members must be distinct canonical peers.")

	#============================================
	@property
	def canonical_key(self) -> tuple[str, str]:
		"""Return the safe dynamic ordering key used to number pair witnesses."""
		return (self.first_candidate_identity, self.second_candidate_identity)


#============================================
@dataclasses.dataclass(frozen=True)
class MaterializedStage6AttemptPlan:
	"""Immutable ordered execution subset of one canonical maximum plan.

	``attempts`` contains only slots whose concrete candidate or review input is
	available.  It never represents a skip: promotion skips are terminal ledger
	facts, and unavailable review pairs simply do not materialize.
	"""

	plan: Stage6AttemptPlan
	final_rung: str
	final_batch_index: int
	available_generation_slot_ids: tuple[str, ...]
	candidate_pair_bindings: tuple[Stage6CandidatePairBinding, ...]
	attempts: tuple[PlannedStage6Attempt, ...]
	repair_source_slot_ids: tuple[str, ...] = ()

	#============================================
	def __post_init__(self) -> None:
		"""Require an ordered, dependency-closed subset before dispatch."""
		if (type(self.plan) is not Stage6AttemptPlan
			or type(self.available_generation_slot_ids) is not tuple
			or type(self.candidate_pair_bindings) is not tuple
			or type(self.repair_source_slot_ids) is not tuple
			or type(self.attempts) is not tuple):
			raise RuntimeError("Stage 6 materialization requires exact immutable values.")
		self.plan._validate_boundary(self.final_rung, self.final_batch_index)
		if any(type(binding) is not Stage6CandidatePairBinding for binding in self.candidate_pair_bindings):
			raise RuntimeError("Stage 6 materialization requires exact candidate pair bindings.")
		expected = _materialized_attempts(
			self.plan,
			self.final_rung,
			self.final_batch_index,
			self.available_generation_slot_ids,
			self.candidate_pair_bindings,
			self.repair_source_slot_ids,
		)
		if self.attempts != expected:
			raise RuntimeError("Stage 6 materialization must derive its canonical dependency-closed slots.")

	#============================================
	@property
	def semantic_identities(self) -> tuple[str, ...]:
		"""Return the exact immutable ledger order for this execution view."""
		return tuple(attempt.semantic_identity for attempt in self.attempts)

	#============================================
	@property
	def is_final_ladder_materialization(self) -> bool:
		"""Return whether no later recovery/batch materialization can remain."""
		return (self.final_rung, self.final_batch_index) == (
			RUNG_ORDER[-1], self.plan.policy.fresh_batch_count - 1,
		)


#============================================
def _rung_attempt_count(policy: Stage6AttemptPolicy, includes_incumbent: bool) -> int:
	"""Return generation, reviews, and repairs for one bounded rung."""
	peers = policy.writer_count + policy.editor_count + int(includes_incumbent)
	pairs = peers * (peers - 1) // 2
	return policy.writer_count + policy.editor_count + (pairs * policy.reviewer_count * 4)


#============================================
def _rung_batch_order(attempt: PlannedStage6Attempt) -> tuple[int, int]:
	"""Keep all generation and review work for each rung/batch contiguous."""
	return (RUNG_ORDER.index(attempt.rung), attempt.batch_index)


#============================================
def _attempt_order(attempt: PlannedStage6Attempt) -> tuple[int, int, int, int, int, int, int]:
	"""Return the canonical generation, review, then repair work order."""
	work_order = {"generation": 0, "review": 1, "review_repair": 2}[attempt.work_kind]
	role_order = {"writer": 0, "editor": 1, "reviewer": 2, "reviewer_repair": 3}[attempt.role]
	return (
		RUNG_ORDER.index(attempt.rung), attempt.batch_index, work_order,
		attempt.pair_index, attempt.replica_index, attempt.display_order, role_order,
	)


#============================================
def _review_semantic_identity(
	rung: str, batch_index: int, reviewer_index: int, pair_index: int, display_order: int,
) -> str:
	"""Return the exact review slot digest required by its repair template."""
	review = PlannedStage6Attempt(
		STAGE6_COMPLETE_POST,
		rung,
		batch_index,
		"review",
		"reviewer",
		reviewer_index,
		pair_index,
		display_order,
		_prompt_identity(rung, "reviewer"),
		_semantic_input_identity(rung, batch_index, "reviewer", reviewer_index, pair_index, display_order),
	)
	return review.semantic_identity


#============================================
def _canonical_attempts(policy: Stage6AttemptPolicy) -> tuple[PlannedStage6Attempt, ...]:
	"""Expand the sole canonical maximum topology without I/O or mutation."""
	attempts: list[PlannedStage6Attempt] = []
	for rung in RUNG_ORDER:
		peers = policy.writer_count + policy.editor_count + int(rung == "primary")
		pair_count = peers * (peers - 1) // 2
		for batch_index in range(policy.fresh_batch_count):
			for role, count in (("writer", policy.writer_count), ("editor", policy.editor_count)):
				for replica_index in range(1, count + 1):
					attempts.append(PlannedStage6Attempt(
						STAGE6_COMPLETE_POST, rung, batch_index, "generation", role, replica_index,
						0, 0, _prompt_identity(rung, role),
						_semantic_input_identity(rung, batch_index, role, replica_index, 0, 0),
					))
			for pair_index in range(1, pair_count + 1):
				for reviewer_index in range(1, policy.reviewer_count + 1):
					for display_order in (1, 2):
						review = PlannedStage6Attempt(
							STAGE6_COMPLETE_POST, rung, batch_index, "review", "reviewer",
							reviewer_index, pair_index, display_order,
							_prompt_identity(rung, "reviewer"),
							_semantic_input_identity(
								rung, batch_index, "reviewer", reviewer_index, pair_index, display_order,
							),
						)
						attempts.append(review)
						attempts.append(PlannedStage6Attempt(
							STAGE6_COMPLETE_POST, rung, batch_index, "review_repair", "reviewer_repair",
							reviewer_index, pair_index, display_order,
							_prompt_identity(rung, "reviewer_repair"),
							_semantic_input_identity(
								rung, batch_index, "reviewer_repair", reviewer_index, pair_index, display_order,
							),
							review.semantic_identity,
						))
	return tuple(sorted(attempts, key=_attempt_order))


#============================================
def build_stage6_attempt_plan(policy: Stage6AttemptPolicy) -> Stage6AttemptPlan:
	"""Build the exact bounded primary plus two-rung recovery plan without I/O."""
	if type(policy) is not Stage6AttemptPolicy:
		raise RuntimeError("Stage 6 planner requires an exact Stage6AttemptPolicy.")
	return Stage6AttemptPlan(policy, _canonical_attempts(policy))


#============================================
def has_canonical_observation_coordinates(observations: tuple[object, ...]) -> bool:
	"""Recognize ordered Stage 6 observation materializations without a facade cycle."""
	if type(observations) is not tuple:
		return False
	coordinates = []
	for observation in observations:
		materialization = getattr(observation, "materialization", None)
		if type(materialization) is not MaterializedStage6AttemptPlan:
			return False
		coordinates.append((materialization.final_rung, materialization.final_batch_index))
	try:
		ordered = tuple((RUNG_ORDER.index(rung), batch) for rung, batch in coordinates)
	except ValueError:
		return False
	return ordered == tuple(sorted(ordered)) and len(ordered) == len(set(ordered))


#============================================
def _materialized_attempts(
	plan: Stage6AttemptPlan,
	final_rung: str,
	final_batch_index: int,
	available_generation_slot_ids: tuple[str, ...],
	candidate_pair_bindings: tuple[Stage6CandidatePairBinding, ...],
	repair_source_slot_ids: tuple[str, ...],
) -> tuple[PlannedStage6Attempt, ...]:
	"""Return the canonical, witness-derived subset through one boundary."""
	plan._validate_boundary(final_rung, final_batch_index)
	if (type(available_generation_slot_ids) is not tuple
		or any(type(item) is not str or SHA256_RE.fullmatch(item) is None for item in available_generation_slot_ids)):
		raise RuntimeError("Stage 6 available generation identities must be an exact digest tuple.")
	if len(available_generation_slot_ids) != len(set(available_generation_slot_ids)):
		raise RuntimeError("Stage 6 available generation identities must be unique.")
	if type(candidate_pair_bindings) is not tuple or any(
		type(item) is not Stage6CandidatePairBinding for item in candidate_pair_bindings
	):
		raise RuntimeError("Stage 6 candidate pair bindings must be an exact tuple.")
	if (type(repair_source_slot_ids) is not tuple
		or any(type(item) is not str or SHA256_RE.fullmatch(item) is None for item in repair_source_slot_ids)
		or len(repair_source_slot_ids) != len(set(repair_source_slot_ids))):
		raise RuntimeError("Stage 6 repair sources must be unique slot digests.")
	allowed = plan.terminal_prefix(final_rung, final_batch_index)
	allowed_generation_ids = {
		attempt.semantic_identity for attempt in allowed if attempt.work_kind == "generation"
	}
	available = set(available_generation_slot_ids)
	if not available <= allowed_generation_ids:
		raise RuntimeError("Stage 6 availability contains a noncanonical or post-terminal generation slot.")
	binding_coordinates = _validated_binding_coordinates(plan, allowed, candidate_pair_bindings)
	derived_review_coordinates = {
		(binding.rung, binding.batch_index, binding.pair_index)
		for binding in binding_coordinates
	}
	allowed_review_ids = {
		attempt.semantic_identity for attempt in allowed
		if attempt.work_kind == "review"
		and (attempt.rung, attempt.batch_index, attempt.pair_index) in derived_review_coordinates
	}
	if not set(repair_source_slot_ids) <= allowed_review_ids:
		raise RuntimeError("Stage 6 repair source is not a materialized review slot.")
	canonical_repair_source_slot_ids = tuple(
		attempt.semantic_identity for attempt in allowed
		if attempt.work_kind == "review" and attempt.semantic_identity in repair_source_slot_ids
	)
	if repair_source_slot_ids != canonical_repair_source_slot_ids:
		raise RuntimeError("Stage 6 repair sources must preserve canonical planned-review order.")
	return tuple(
		attempt for attempt in allowed
		if (attempt.work_kind == "generation" and attempt.semantic_identity in available)
		or (
			attempt.work_kind == "review"
			and (attempt.rung, attempt.batch_index, attempt.pair_index) in derived_review_coordinates
		)
		or (
			attempt.work_kind == "review_repair"
			and attempt.repair_of_identity in repair_source_slot_ids
		)
	)


#============================================
def _validated_binding_coordinates(
	plan: Stage6AttemptPlan,
	allowed: tuple[PlannedStage6Attempt, ...],
	bindings: tuple[Stage6CandidatePairBinding, ...],
) -> tuple[Stage6CandidatePairBinding, ...]:
	"""Validate canonical dynamic pair witnesses against maximum templates.

	Pair indices are assigned after concrete peers are known.  Requiring a
	contiguous, lexically ordered sequence per rung/batch gives later workers a
	deterministic, bounded mapping without claiming that static generation slots
	identify pair members.
	"""
	allowed_pair_coordinates = {
		(attempt.rung, attempt.batch_index, attempt.pair_index)
		for attempt in allowed if attempt.work_kind == "review"
	}
	if any(binding.batch_index >= plan.policy.fresh_batch_count for binding in bindings):
		raise RuntimeError("Stage 6 candidate pair binding batch is outside the policy.")
	if any((binding.rung, binding.batch_index, binding.pair_index) not in allowed_pair_coordinates for binding in bindings):
		raise RuntimeError("Stage 6 candidate pair binding is noncanonical or post-terminal.")
	grouped: dict[tuple[str, int], list[Stage6CandidatePairBinding]] = {}
	for binding in bindings:
		grouped.setdefault((binding.rung, binding.batch_index), []).append(binding)
	for coordinate, group in grouped.items():
		if tuple(binding.pair_index for binding in group) != tuple(range(1, len(group) + 1)):
			raise RuntimeError("Stage 6 candidate pair bindings require contiguous dynamic indices.")
		if tuple(binding.canonical_key for binding in group) != tuple(sorted(binding.canonical_key for binding in group)):
			raise RuntimeError("Stage 6 candidate pair bindings must use canonical peer order.")
		if len({binding.canonical_key for binding in group}) != len(group):
			raise RuntimeError("Stage 6 candidate pair bindings must be unique.")
		if coordinate not in {(attempt.rung, attempt.batch_index) for attempt in allowed}:
			raise RuntimeError("Stage 6 candidate pair binding is outside the terminal prefix.")
	ordered = tuple(sorted(
		bindings,
		key=lambda binding: (RUNG_ORDER.index(binding.rung), binding.batch_index, binding.pair_index),
	))
	if bindings != ordered:
		raise RuntimeError("Stage 6 candidate pair bindings must preserve canonical plan order.")
	return bindings

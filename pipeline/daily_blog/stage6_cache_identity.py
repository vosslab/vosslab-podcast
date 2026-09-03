"""Closed cache-identity contract for materialized Stage 6 route attempts."""

# Standard Library
import dataclasses
import json
import re

# local repo modules
import daily_blog.io_utils
import daily_blog.stage6_attempt_plan


ROUTE_CACHE_SCHEMA = "vosslab.daily-blog.route-cache"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ROUTE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
STAGE6_CACHE_IDENTITY_KEYS = (
	"route_cache_schema", "attempt_plan_schema", "slot_id", "stage", "rung",
	"batch_index", "work_kind", "role", "replica_index",
	"prompt_sha256", "planner_semantic_input_sha256", "actual_candidate_input_sha256",
	"route_name", "route_contract_sha256",
)


class Stage6CacheIdentityError(RuntimeError):
	"""A value fails the closed Stage 6 cache-identity contract."""


@dataclasses.dataclass(frozen=True, init=False)
class Stage6CacheIdentity:
	"""Validated digest-only cache witness for one materialized Stage 6 slot."""

	route_cache_schema: str
	attempt_plan_schema: str
	slot_id: str
	stage: str
	rung: str
	batch_index: int
	work_kind: str
	role: str
	replica_index: int
	planner_semantic_input_sha256: str
	prompt_sha256: str
	actual_candidate_input_sha256: str
	route_name: str
	route_contract_sha256: str

	#============================================
	def __init__(
		self, materialization: object, attempt: object, *, prompt: str,
		candidate_identities: tuple[str, ...] = (),
		route_name: str, route_contract_sha256: str,
	) -> None:
		"""Build one witness from an active materialization and canonical attempt."""
		limits = daily_blog.stage6_attempt_plan
		if (
			type(materialization) is not limits.MaterializedStage6AttemptPlan
			or type(attempt) is not limits.PlannedStage6Attempt
		):
			raise Stage6CacheIdentityError("Stage 6 identity requires a materialized planned attempt.")
		if type(materialization.plan) is not limits.Stage6AttemptPlan:
			raise Stage6CacheIdentityError("Stage 6 identity requires an exact active plan.")
		if not any(planned is attempt for planned in materialization.attempts):
			raise Stage6CacheIdentityError("Stage 6 identity slot is outside the materialization.")
		if type(prompt) is not str or type(candidate_identities) is not tuple:
			raise Stage6CacheIdentityError("Stage 6 identity requires exact materialized inputs.")
		if any(type(value) is not str or SHA256_RE.fullmatch(value) is None for value in candidate_identities):
			raise Stage6CacheIdentityError("Stage 6 candidate identities require SHA-256 witnesses.")
		if len(candidate_identities) != len(set(candidate_identities)):
			raise Stage6CacheIdentityError("Stage 6 candidate identities require unique witnesses.")
		if type(route_name) is not str or SAFE_ROUTE_NAME_RE.fullmatch(route_name) is None:
			raise Stage6CacheIdentityError("Stage 6 identity requires a safe route name.")
		if type(route_contract_sha256) is not str or SHA256_RE.fullmatch(route_contract_sha256) is None:
			raise Stage6CacheIdentityError("Stage 6 route contract requires a SHA-256 witness.")
		try:
			canonical = limits.PlannedStage6Attempt(**dataclasses.asdict(attempt))
		except (TypeError, ValueError, RuntimeError) as error:
			raise Stage6CacheIdentityError("Stage 6 identity has an invalid planned slot.") from error
		if canonical != attempt:
			raise Stage6CacheIdentityError("Stage 6 identity requires an exact planned slot.")
		candidate_digest = self.candidate_input_sha256(candidate_identities)
		if canonical.role == "writer":
			if candidate_identities:
				raise Stage6CacheIdentityError("Stage 6 writer identity has no materialized witnesses.")
			candidate_digest = ""
		elif canonical.role == "editor":
			if not candidate_identities:
				raise Stage6CacheIdentityError("Stage 6 editor identity requires candidates.")
		elif canonical.role == "reviewer":
			if not candidate_identities:
				raise Stage6CacheIdentityError("Stage 6 reviewer identity requires its displayed candidate set.")
			if set(candidate_identities) != set(self._candidate_set(materialization, canonical)):
				raise Stage6CacheIdentityError("Stage 6 reviewer candidates conflict with its materialization.")
			candidate_digest = self.candidate_input_sha256(candidate_identities)
		else:
			raise Stage6CacheIdentityError("Stage 6 identity role is invalid.")
		values = {
			"route_cache_schema": ROUTE_CACHE_SCHEMA,
			"attempt_plan_schema": limits.STAGE6_ATTEMPT_PLAN_SCHEMA,
			"slot_id": canonical.semantic_identity, "stage": canonical.stage, "rung": canonical.rung,
			"batch_index": canonical.batch_index, "work_kind": canonical.work_kind,
			"role": canonical.role, "replica_index": canonical.replica_index,
			"prompt_sha256": daily_blog.io_utils.sha256_text(prompt),
			"planner_semantic_input_sha256": canonical.semantic_input_identity,
			"actual_candidate_input_sha256": candidate_digest,
			"route_name": route_name, "route_contract_sha256": route_contract_sha256,
		}
		for name in STAGE6_CACHE_IDENTITY_KEYS:
			object.__setattr__(self, name, values[name])

	#============================================
	@staticmethod
	def _candidate_set(materialization: object, attempt: object) -> tuple[str, ...]:
		"""Derive one review's complete set from its materialization binding."""
		limits = daily_blog.stage6_attempt_plan
		if (
			type(materialization) is not limits.MaterializedStage6AttemptPlan
			or type(attempt) is not limits.PlannedStage6Attempt
		):
			raise Stage6CacheIdentityError("Stage 6 review requires exact materialized values.")
		matches = tuple(binding for binding in materialization.candidate_set_bindings if (
			binding.rung == attempt.rung and binding.batch_index == attempt.batch_index
		))
		if len(matches) != 1:
			raise Stage6CacheIdentityError("Stage 6 review requires its materialized candidate set.")
		return matches[0].candidate_identities

	#============================================
	@staticmethod
	def candidate_input_sha256(candidate_identities: tuple[str, ...]) -> str:
		"""Hash exact ordered artifact identities without retaining candidate bytes."""
		return daily_blog.io_utils.sha256_text(json.dumps(
			candidate_identities, ensure_ascii=True, separators=(",", ":"),
		))

	#============================================
	def identity_dict(self) -> dict[str, object]:
		"""Return the exact allowed Stage 6 semantic identity serialization."""
		return {name: getattr(self, name) for name in STAGE6_CACHE_IDENTITY_KEYS}


#============================================
def validate_route_request_witness(
	identity: Stage6CacheIdentity, *, request_id: str, step: str, role: str,
	route_name: str, prompt: str, route_contract_sha256: str,
) -> None:
	"""Bind a Stage 6 witness to its exact route-request values."""
	if type(identity) is not Stage6CacheIdentity:
		raise Stage6CacheIdentityError("Stage 6 request requires an exact typed witness.")
	if request_id != identity.slot_id or step != identity.stage:
		raise Stage6CacheIdentityError("Stage 6 witness requires its planned request slot.")
	if identity.role != role or identity.route_name != route_name:
		raise Stage6CacheIdentityError("Stage 6 witness requires its route request.")
	if identity.prompt_sha256 != daily_blog.io_utils.sha256_text(prompt):
		raise Stage6CacheIdentityError("Stage 6 witness requires its materialized prompt.")
	if identity.route_contract_sha256 != route_contract_sha256:
		raise Stage6CacheIdentityError("Stage 6 witness requires its route execution contract.")

"""Closed, response-free Stage 6 attempt-ledger contracts."""

# Standard Library
import collections
import dataclasses
import re


MAX_REJECTION_CODES = 64
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
ATTEMPT_EXECUTION_SOURCES = frozenset({"fresh_route", "cache_reuse", "skipped"})
ATTEMPT_TRANSPORT_OUTCOMES = frozenset({
	"not_started", "success", "start_failure", "timeout", "process_failure", "empty_response",
})
ATTEMPT_GATES = (
	"not_reached", "transport", "parsed", "mechanical", "publication_policy", "review", "selected",
)
ATTEMPT_DISPOSITIONS = frozenset({
	"route_failed", "parse_rejected", "mechanical_rejected", "policy_rejected",
	"review_completed", "review_rejected", "eligible_not_selected", "selected",
	"skipped_after_promotion",
})
ATTEMPT_REASON_CODES = frozenset({
	"", "route_start_failure", "route_timeout", "route_process_failure", "route_empty_response",
	"response_parse_failure", "mechanical_ineligible", "citation_density_mismatch",
	"presentation_policy_mismatch", "evidence_grounding_mismatch", "image_authority_mismatch",
	"review_rejected",
})
ROUTE_REASON_BY_TRANSPORT = {
	"start_failure": "route_start_failure", "timeout": "route_timeout",
	"process_failure": "route_process_failure", "empty_response": "route_empty_response",
}


@dataclasses.dataclass(frozen=True)
class AttemptFact:
	"""One terminal, response-free fact for a planned logical slot."""

	slot_id: str
	execution_source: str
	transport_attempts: int
	restored_agent_result_attempts: int
	transport_outcome: str
	highest_gate: str
	terminal_disposition: str
	reason_code: str
	candidate_sha256: str = ""
	feedback_input_sha256: str = ""

	def __post_init__(self) -> None:
		"""Validate exact closed values before aggregation or persistence."""
		if type(self.slot_id) is not str or SHA256_RE.fullmatch(self.slot_id) is None:
			raise RuntimeError("Attempt fact slot identity is invalid.")
		if type(self.execution_source) is not str or self.execution_source not in ATTEMPT_EXECUTION_SOURCES:
			raise RuntimeError("Attempt fact execution source is invalid.")
		if type(self.transport_outcome) is not str or self.transport_outcome not in ATTEMPT_TRANSPORT_OUTCOMES:
			raise RuntimeError("Attempt fact transport outcome is invalid.")
		if (type(self.highest_gate) is not str or type(self.terminal_disposition) is not str
			or self.highest_gate not in ATTEMPT_GATES or self.terminal_disposition not in ATTEMPT_DISPOSITIONS):
			raise RuntimeError("Attempt fact gate or disposition is invalid.")
		if type(self.reason_code) is not str or self.reason_code not in ATTEMPT_REASON_CODES:
			raise RuntimeError("Attempt fact reason is invalid.")
		if any(type(value) is not int or not 0 <= value <= 4 for value in (
			self.transport_attempts, self.restored_agent_result_attempts,
		)):
			raise RuntimeError("Attempt fact retry counts are invalid.")
		if any(type(value) is not str or (value and SHA256_RE.fullmatch(value) is None) for value in (
			self.candidate_sha256, self.feedback_input_sha256,
		)):
			raise RuntimeError("Attempt fact hashes are invalid.")
		if self.execution_source == "skipped":
			if (self.transport_attempts or self.restored_agent_result_attempts
				or self.transport_outcome != "not_started" or self.highest_gate != "not_reached"
				or self.terminal_disposition != "skipped_after_promotion" or self.reason_code
				or self.candidate_sha256 or self.feedback_input_sha256):
				raise RuntimeError("Skipped attempt facts must be empty terminal skips.")
			return
		if self.execution_source == "fresh_route":
			if not 1 <= self.transport_attempts <= 4 or self.restored_agent_result_attempts:
				raise RuntimeError("Fresh attempt provenance is invalid.")
		elif not 1 <= self.transport_attempts <= 4 or self.restored_agent_result_attempts != self.transport_attempts:
			raise RuntimeError("Cached attempt provenance is invalid.")
		if self.transport_outcome != "success":
			if (self.execution_source != "fresh_route" or self.terminal_disposition != "route_failed"
				or self.highest_gate != "transport"
				or self.reason_code != ROUTE_REASON_BY_TRANSPORT.get(self.transport_outcome, "")
				or self.candidate_sha256):
				raise RuntimeError("Failed transport attempt fact is invalid.")
			return
		if self.terminal_disposition == "route_failed" or self.highest_gate == "not_reached":
			raise RuntimeError("Successful transport cannot be a route failure.")
		candidate = bool(self.candidate_sha256)
		valid = {
			"parse_rejected": self.highest_gate == "transport" and self.reason_code == "response_parse_failure" and not candidate,
			"mechanical_rejected": self.highest_gate == "parsed" and self.reason_code == "mechanical_ineligible" and candidate,
			"policy_rejected": self.highest_gate == "publication_policy" and self.reason_code in ATTEMPT_REASON_CODES - {"", "mechanical_ineligible", "response_parse_failure", "review_rejected"} and candidate,
			"review_rejected": self.highest_gate == "review" and self.reason_code == "review_rejected" and candidate,
			"review_completed": self.highest_gate == "review" and not self.reason_code and candidate,
			"eligible_not_selected": self.highest_gate == "publication_policy" and not self.reason_code and candidate,
			"selected": self.highest_gate == "selected" and not self.reason_code and candidate,
		}.get(self.terminal_disposition, False)
		if not valid:
			raise RuntimeError("Attempt fact disposition conflicts with its terminal gate.")

	#============================================
	def to_dict(self) -> dict[str, object]:
		"""Serialize one validated terminal attempt fact."""
		self.__post_init__()
		return dataclasses.asdict(self)

	#============================================
	@classmethod
	def from_dict(cls, value: object) -> "AttemptFact":
		"""Restore one attempt fact with the current closed field set."""
		if type(value) is not dict or set(value) != {field.name for field in dataclasses.fields(cls)}:
			raise RuntimeError("Attempt fact uses unsupported fields.")
		return cls(**value)


@dataclasses.dataclass(frozen=True)
class AttemptReliabilitySummary:
	"""Reconciled bounded totals; reviewed counts completed or rejected review attempts."""

	planned: int
	fresh: int
	cache: int
	skipped: int
	current_physical_calls: int
	transport_success: int
	transport_failure: int
	parsed: int
	mechanical: int
	policy: int
	selected: int
	exhausted: int
	dispatched: int
	reviewed: int
	rejected: int
	reason_counts: tuple[tuple[str, int], ...]

	def __post_init__(self) -> None:
		"""Validate reconciled bounded attempt totals."""
		counts = dataclasses.astuple(self)[:-1]
		if any(type(value) is not int or value < 0 for value in counts):
			raise RuntimeError("Attempt reliability summary counts are invalid.")
		if self.planned != self.fresh + self.cache + self.skipped:
			raise RuntimeError("Attempt reliability sources do not reconcile.")
		if self.transport_success + self.transport_failure != self.fresh + self.cache:
			raise RuntimeError("Attempt reliability transport totals do not reconcile.")
		if not self.selected <= self.policy <= self.mechanical <= self.parsed <= self.transport_success:
			raise RuntimeError("Attempt reliability gates do not reconcile.")
		if self.selected > 1 or self.exhausted not in {0, 1}:
			raise RuntimeError("Attempt reliability terminal totals are invalid.")
		if self.selected and (self.exhausted or self.skipped != self.planned - self.fresh - self.cache):
			raise RuntimeError("Attempt reliability promotion totals are invalid.")
		if self.exhausted and (self.selected or self.skipped):
			raise RuntimeError("Attempt exhaustion cannot be a slot disposition.")
		if self.dispatched != self.fresh + self.cache or self.reviewed > self.dispatched or self.rejected > self.dispatched:
			raise RuntimeError("Attempt reliability execution totals do not reconcile.")
		if (type(self.reason_counts) is not tuple or len(self.reason_counts) > MAX_REJECTION_CODES
			or tuple(sorted(self.reason_counts)) != self.reason_counts
			or len({code for code, _count in self.reason_counts}) != len(self.reason_counts)
			or any(type(code) is not str or code not in ATTEMPT_REASON_CODES - {""}
				or type(count) is not int or not 1 <= count <= self.dispatched
				for code, count in self.reason_counts)):
			raise RuntimeError("Attempt reliability reason counts are invalid.")

	#============================================
	def to_dict(self) -> dict[str, object]:
		"""Serialize one validated reliability summary."""
		self.__post_init__()
		value = dataclasses.asdict(self)
		value["reason_counts"] = [{"code": code, "count": count} for code, count in self.reason_counts]
		return value

	#============================================
	@classmethod
	def from_dict(cls, value: object) -> "AttemptReliabilitySummary":
		"""Restore the current bounded reliability summary shape."""
		if (type(value) is not dict or set(value) != {field.name for field in dataclasses.fields(cls)}
			or type(value.get("reason_counts")) is not list
			or any(type(item) is not dict or set(item) != {"code", "count"} for item in value["reason_counts"])):
			raise RuntimeError("Attempt reliability summary uses unsupported fields.")
		return cls(**(value | {"reason_counts": tuple((item["code"], item["count"]) for item in value["reason_counts"])}))


@dataclasses.dataclass(frozen=True)
class AttemptLedger:
	"""Canonical planned-slot order and one terminal fact per applicable slot."""

	planned_slot_ids: tuple[str, ...]
	facts: tuple[AttemptFact, ...] = ()

	def __post_init__(self) -> None:
		"""Validate canonical order and exact closed facts."""
		if (type(self.planned_slot_ids) is not tuple or not self.planned_slot_ids or len(self.planned_slot_ids) > 10000
			or any(type(item) is not str or SHA256_RE.fullmatch(item) is None for item in self.planned_slot_ids)
			or len(set(self.planned_slot_ids)) != len(self.planned_slot_ids)):
			raise RuntimeError("Attempt ledger plan order is invalid.")
		if type(self.facts) is not tuple or len(self.facts) > len(self.planned_slot_ids) or any(type(item) is not AttemptFact for item in self.facts):
			raise RuntimeError("Attempt ledger facts are invalid.")
		if tuple(item.slot_id for item in self.facts) != self.planned_slot_ids[:len(self.facts)]:
			raise RuntimeError("Attempt ledger facts do not follow canonical plan order.")
		if self.complete:
			self.summary()

	@property
	def complete(self) -> bool:
		"""Return whether every planned slot has one terminal fact."""
		return len(self.facts) == len(self.planned_slot_ids)

	#============================================
	def close_slot(self, fact: AttemptFact) -> "AttemptLedger":
		"""Return a ledger extended by the next canonical terminal fact."""
		if type(fact) is not AttemptFact or self.complete or fact.slot_id != self.planned_slot_ids[len(self.facts)]:
			raise RuntimeError("Attempt ledger closure is outside canonical plan order.")
		return AttemptLedger(self.planned_slot_ids, self.facts + (fact,))

	#============================================
	def summary(self) -> AttemptReliabilitySummary:
		"""Derive bounded reliability totals from a complete canonical ledger."""
		if not self.complete:
			raise RuntimeError("Attempt ledger summary requires every terminal slot fact.")
		facts = self.facts
		fresh = sum(item.execution_source == "fresh_route" for item in facts)
		cache = sum(item.execution_source == "cache_reuse" for item in facts)
		skipped = sum(item.execution_source == "skipped" for item in facts)
		selected = sum(item.terminal_disposition == "selected" for item in facts)
		first_skip = next((index for index, item in enumerate(facts) if item.terminal_disposition == "skipped_after_promotion"), len(facts))
		if any(item.terminal_disposition != "skipped_after_promotion" for item in facts[first_skip:]):
			raise RuntimeError("Attempt ledger skips must form one terminal suffix.")
		if skipped and not selected:
			raise RuntimeError("Attempt ledger skips require an earlier promotion.")
		gate = {name: index for index, name in enumerate(ATTEMPT_GATES)}
		reasons = collections.Counter(item.reason_code for item in facts if item.reason_code)
		parsed = sum(gate[item.highest_gate] >= gate["parsed"] for item in facts)
		mechanical = sum(gate[item.highest_gate] >= gate["mechanical"] for item in facts)
		policy = sum(gate[item.highest_gate] >= gate["publication_policy"] for item in facts)
		return AttemptReliabilitySummary(
			len(facts), fresh, cache, skipped,
			sum(item.transport_attempts for item in facts if item.execution_source == "fresh_route"),
			sum(item.transport_outcome == "success" for item in facts),
			sum(item.execution_source != "skipped" and item.transport_outcome != "success" for item in facts),
			parsed, mechanical, policy,
			selected, int(not selected), fresh + cache,
			sum(item.terminal_disposition in {"review_completed", "review_rejected"} for item in facts),
			sum(item.terminal_disposition in {"parse_rejected", "mechanical_rejected", "policy_rejected", "review_rejected"} for item in facts),
			tuple(sorted(reasons.items())),
		)

	#============================================
	def to_dict(self) -> dict[str, object]:
		"""Serialize a complete ledger for durable run-state storage."""
		if not self.complete:
			raise RuntimeError("Attempt ledger persistence requires every terminal slot fact.")
		self.__post_init__()
		return {"planned_slot_ids": list(self.planned_slot_ids), "facts": [item.to_dict() for item in self.facts]}

	#============================================
	@classmethod
	def from_dict(cls, value: object) -> "AttemptLedger":
		"""Restore a complete or in-progress ledger from its closed schema."""
		if type(value) is not dict or set(value) != {"planned_slot_ids", "facts"} or type(value["planned_slot_ids"]) is not list or type(value["facts"]) is not list:
			raise RuntimeError("Attempt ledger JSON fields are invalid.")
		return cls(tuple(value["planned_slot_ids"]), tuple(AttemptFact.from_dict(item) for item in value["facts"]))

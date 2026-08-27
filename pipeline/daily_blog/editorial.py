"""Two-author generation, deterministic validation, and anonymous referee selection."""

# Standard Library
import os
import json
import re
import dataclasses

# local repo modules
import daily_blog.config
import daily_blog.schema
import daily_blog.routes
import daily_blog.candidates
import daily_blog.io_utils
import podlib.prompt_loader


AUTHOR_TEMPLATE_NAME = "daily_blog_author_v2.txt"
REFEREE_TEMPLATE_NAME = "daily_blog_referee_v2.txt"
REPAIR_TEMPLATE_NAME = "daily_blog_referee_repair_v2.txt"
RUBRIC_NAME = "daily_blog_rubric_v2.md"
MAX_FAILURE_CHARS = 1000
MAX_REFEREE_RESPONSE_CHARS = 4000
GENERATOR_RUN_RE = re.compile(r"^generator_run:\s*(\S+)\s*$", re.MULTILINE)


@dataclasses.dataclass(frozen=True)
class CandidateResult:
	"""One isolated author result plus deterministic validation."""

	private_route: str
	post: str
	post_hash: str
	valid: bool
	issues: tuple[str, ...]

	#============================================
	def public_summary(self, candidate_id: str) -> dict:
		"""Return a bundle-safe summary that preserves author anonymity."""
		value = {
			"candidate_id": candidate_id,
			"post_hash": self.post_hash,
			"valid": self.valid,
			"issues": list(self.issues),
		}
		return value

	#============================================
	def to_cache_dict(self) -> dict:
		"""Serialize the private validated candidate for hash-addressed reuse."""
		return {
			"private_route": self.private_route,
			"post": self.post,
			"post_hash": self.post_hash,
			"valid": self.valid,
			"issues": list(self.issues),
		}

	#============================================
	@classmethod
	def from_cache_dict(cls, value: dict) -> "CandidateResult":
		"""Restore and verify one private cached candidate."""
		candidate = cls(
			private_route=str(value["private_route"]),
			post=str(value["post"]),
			post_hash=str(value["post_hash"]),
			valid=value["valid"],
			issues=tuple(str(item) for item in value["issues"]),
		)
		if type(candidate.valid) is not bool:
			raise RuntimeError("Cached candidate validity must be Boolean.")
		if candidate.post_hash != daily_blog.io_utils.sha256_text(candidate.post):
			raise RuntimeError("Cached candidate hash does not match its post.")
		if candidate.valid == bool(candidate.issues):
			raise RuntimeError("Cached candidate validity and issues are inconsistent.")
		return candidate


@dataclasses.dataclass(frozen=True)
class EditorialDecision:
	"""Final referee result and exact publishable post."""

	winner: str
	reason: str
	evidence_quality: str
	confidence: float
	publication_quality: str
	post: str
	anonymous_mapping: dict[str, int]

	#============================================
	def to_cache_dict(self) -> dict:
		"""Serialize one complete private referee decision."""
		return {
			"winner": self.winner,
			"reason": self.reason,
			"evidence_quality": self.evidence_quality,
			"confidence": self.confidence,
			"publication_quality": self.publication_quality,
			"post": self.post,
			"anonymous_mapping": dict(self.anonymous_mapping),
		}

	#============================================
	@classmethod
	def from_cache_dict(cls, value: dict) -> "EditorialDecision":
		"""Restore one complete private referee decision."""
		mapping = {str(key): int(index) for key, index in value["anonymous_mapping"].items()}
		decision = cls(
			winner=str(value["winner"]),
			reason=str(value["reason"]),
			evidence_quality=str(value["evidence_quality"]),
			confidence=float(value["confidence"]),
			publication_quality=str(value["publication_quality"]),
			post=str(value["post"]),
			anonymous_mapping=mapping,
		)
		if decision.winner not in {"A", "B", "NONE"}:
			raise RuntimeError("Cached referee winner is unsupported.")
		if decision.publication_quality not in {"final", "provisional"}:
			raise RuntimeError("Cached publication quality is unsupported.")
		return decision


#============================================
def _rebind_post_run(post: str, source_run_id: str, target_run_id: str) -> str:
	"""Bind one cached article's required run metadata to the current run."""
	matches = list(GENERATOR_RUN_RE.finditer(post))
	if len(matches) != 1 or matches[0].group(1) != source_run_id:
		return post
	start, end = matches[0].span()
	bound = post[:start] + f"generator_run: {target_run_id}" + post[end:]
	return bound


#============================================
def validate_raw_candidates(value: object) -> list[dict]:
	"""Verify cached isolated-author outputs before reuse."""
	if not isinstance(value, list) or len(value) != 2:
		raise RuntimeError("Cached author generation requires exactly two candidates.")
	validated = []
	for item in value:
		if not isinstance(item, dict):
			raise RuntimeError("Cached author candidate must be an object.")
		for key in ("private_route", "post", "post_hash", "generation_error"):
			if not isinstance(item.get(key), str):
				raise RuntimeError(f"Cached author candidate field must be text: {key}")
		if item["post_hash"] != daily_blog.io_utils.sha256_text(item["post"]):
			raise RuntimeError("Cached author candidate hash does not match its post.")
		validated.append(dict(item))
	return validated


#============================================
def rebind_raw_candidates(
	value: object,
	source_run_id: str,
	target_run_id: str,
) -> list[dict]:
	"""Materialize cached author outputs for one immutable execution run."""
	bound = []
	for item in validate_raw_candidates(value):
		post = _rebind_post_run(item["post"], source_run_id, target_run_id)
		item["post"] = post
		item["post_hash"] = daily_blog.io_utils.sha256_text(post)
		bound.append(item)
	return bound


#============================================
def rebind_candidates(
	candidates: list[CandidateResult],
	source_run_id: str,
	target_run_id: str,
) -> list[CandidateResult]:
	"""Materialize validated candidates for one immutable execution run."""
	bound = []
	for candidate in candidates:
		post = _rebind_post_run(candidate.post, source_run_id, target_run_id)
		bound.append(
			CandidateResult(
				private_route=candidate.private_route,
				post=post,
				post_hash=daily_blog.io_utils.sha256_text(post),
				valid=candidate.valid,
				issues=candidate.issues,
			)
		)
	return bound


#============================================
def materialize_decision(
	decision: EditorialDecision,
	packet: daily_blog.schema.EvidencePacket,
	run_id: str,
	candidates: list[CandidateResult],
) -> EditorialDecision:
	"""Bind a reusable editorial verdict to current candidate artifacts."""
	if decision.winner == "NONE":
		post = daily_blog.candidates.provisional_post(packet, run_id)
	else:
		index = decision.anonymous_mapping.get(decision.winner)
		if index is None or index >= len(candidates):
			raise RuntimeError("Cached referee mapping does not identify a candidate.")
		post = candidates[index].post
	return dataclasses.replace(decision, post=post)


#============================================
def _prompt_path(name: str) -> str:
	"""Return one versioned prompt path adjacent to the pipeline package."""
	package_dir = os.path.dirname(os.path.abspath(__file__))
	path = os.path.join(os.path.dirname(package_dir), "prompts", name)
	return path


#============================================
def load_prompt(name: str) -> str:
	"""Read one complete versioned prompt or rubric."""
	path = _prompt_path(name)
	with open(path, "r", encoding="utf-8") as handle:
		text = handle.read().strip()
	if not text:
		raise RuntimeError(f"Prompt template is empty: {name}")
	text = podlib.prompt_loader.validate_positive_instructions(text, name)
	return text


#============================================
def validate_prompt_templates() -> dict[str, str]:
	"""Validate positive phrasing and explicit output contracts before any LLM call."""
	templates = {
		"author": load_prompt(AUTHOR_TEMPLATE_NAME),
		"referee": load_prompt(REFEREE_TEMPLATE_NAME),
		"repair": load_prompt(REPAIR_TEMPLATE_NAME),
		"rubric": load_prompt(RUBRIC_NAME),
	}
	for name, text in templates.items():
		podlib.prompt_loader.validate_positive_instructions(text, name)
	if "{evidence_json}" not in templates["author"]:
		raise RuntimeError("Author prompt must declare bounded evidence context.")
	if "## Output contract" not in templates["author"]:
		raise RuntimeError("Author prompt must declare its output contract.")
	if "{candidate_a}" not in templates["referee"] or "{candidate_b}" not in templates["referee"]:
		raise RuntimeError("Referee prompt must declare both anonymous candidates.")
	if "## Output contract" not in templates["referee"]:
		raise RuntimeError("Referee prompt must declare its output contract.")
	return templates


#============================================
def evidence_context(packet: daily_blog.schema.EvidencePacket, limit: int) -> str:
	"""Render bounded editorial evidence while preserving complete changelog items."""
	value = {
		"schema_version": packet.schema_version,
		"packet_id": packet.packet_id,
		"report_date": packet.report_date,
		"timezone": packet.timezone,
		"complete": packet.complete,
		"authority_order": list(daily_blog.schema.AUTHORITY_ORDER),
		"active_repositories": [activity.repository for activity in packet.activity],
		"items": [item.to_dict() for item in packet.items],
	}
	text = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True)
	if len(text) > limit:
		raise RuntimeError(
			f"Evidence context requires {len(text)} characters and exceeds its {limit} budget."
		)
	return text


#============================================
def render_author_prompt(
	packet: daily_blog.schema.EvidencePacket,
	run_id: str,
	limit: int,
) -> str:
	"""Render one identical author prompt for both isolated roles."""
	templates = validate_prompt_templates()
	prompt = templates["author"].format(
		report_date=packet.report_date,
		run_id=run_id,
		rubric=templates["rubric"],
		evidence_json=evidence_context(packet, limit),
	)
	if len(prompt) > limit:
		raise RuntimeError(
			f"Author prompt requires {len(prompt)} characters and exceeds its {limit} budget."
		)
	return prompt


#============================================
def generate_candidates(
	packet: daily_blog.schema.EvidencePacket,
	run_id: str,
	config: daily_blog.config.DailyBlogConfig,
	runner: object | None = None,
) -> list[dict]:
	"""Run two isolated author roles over the exact same evidence prompt."""
	if not packet.complete:
		raise RuntimeError("Author generation requires a complete evidence packet.")
	route_runner = runner if runner is not None else daily_blog.routes.CommandRouteRunner()
	prompt = ""
	prompt_error = ""
	try:
		prompt = render_author_prompt(
			packet,
			run_id,
			config.evidence_budgets["author_context_chars"],
		)
	except RuntimeError as error:
		prompt_error = str(error)
	results = []
	for route in config.author_routes:
		post = ""
		generation_error = prompt_error
		if not generation_error:
			try:
				post = route_runner.run(route, prompt, config.daily_blog_repository)
			except RuntimeError as error:
				generation_error = str(error)
		if len(post) > daily_blog.candidates.MAX_CANDIDATE_CHARS:
			post = ""
			generation_error = "The author response exceeded the candidate character budget."
		post = post.rstrip() + "\n" if post else ""
		results.append(
			{
				"private_route": route.name,
				"post": post,
				"post_hash": daily_blog.io_utils.sha256_text(post),
				"generation_error": generation_error,
			}
		)
	return results


#============================================
def validate_candidates(
	raw_candidates: list[dict],
	packet: daily_blog.schema.EvidencePacket,
	run_id: str,
) -> list[CandidateResult]:
	"""Apply deterministic structure and provenance validation to each author result."""
	results = []
	for candidate in raw_candidates:
		issues = daily_blog.candidates.validate_candidate(candidate["post"], packet, run_id)
		if candidate.get("generation_error"):
			issues.insert(0, str(candidate["generation_error"])[:MAX_FAILURE_CHARS])
		result = CandidateResult(
			private_route=candidate["private_route"],
			post=candidate["post"],
			post_hash=candidate["post_hash"],
			valid=not issues,
			issues=tuple(issues),
		)
		results.append(result)
	return results


#============================================
def _anonymous_mapping(packet_id: str, candidates: list[CandidateResult]) -> dict[str, int]:
	"""Map valid candidates to A/B deterministically and independently of route order."""
	valid_indexes = [index for index, candidate in enumerate(candidates) if candidate.valid]
	if len(valid_indexes) == 2:
		identity = packet_id + "".join(candidates[index].post_hash for index in valid_indexes)
		if int(daily_blog.io_utils.sha256_text(identity)[:2], 16) % 2:
			valid_indexes.reverse()
	mapping = {}
	for label, index in zip(("A", "B"), valid_indexes):
		mapping[label] = index
	return mapping


#============================================
def _parse_verdict(response: str, allowed_labels: set[str]) -> dict:
	"""Parse one exact structured referee verdict."""
	if len(response) > MAX_REFEREE_RESPONSE_CHARS:
		raise RuntimeError("Referee response exceeds the structured response budget.")
	value = json.loads(response.strip())
	if not isinstance(value, dict):
		raise RuntimeError("Referee verdict must be one JSON object.")
	winner = str(value.get("winner") or "")
	reason = str(value.get("reason") or "").strip()
	evidence_quality = str(value.get("evidence_quality") or "")
	confidence = value.get("confidence")
	if winner not in allowed_labels | {"NONE"}:
		raise RuntimeError("Referee winner is unavailable or unsupported.")
	if not reason or len(reason) > 500:
		raise RuntimeError("Referee reason must be concise and non-empty.")
	if evidence_quality not in {"high", "medium", "low"}:
		raise RuntimeError("Referee evidence_quality is unsupported.")
	if type(confidence) not in {int, float} or not 0 <= confidence <= 1:
		raise RuntimeError("Referee confidence must be a number from zero through one.")
	verdict = {
		"winner": winner,
		"reason": reason,
		"evidence_quality": evidence_quality,
		"confidence": float(confidence),
	}
	return verdict


#============================================
def _route_failure_reason(error: Exception) -> str:
	"""Return one publisher-compatible bounded referee route failure reason."""
	prefix = "The referee route remained pending: "
	available = 500 - len(prefix)
	reason = prefix + str(error)[:available]
	return reason


#============================================
def _referee_verdict(
	packet: daily_blog.schema.EvidencePacket,
	candidates: list[CandidateResult],
	mapping: dict[str, int],
	config: daily_blog.config.DailyBlogConfig,
	runner: object,
) -> dict:
	"""Run the separately configured referee, including one structured repair pass."""
	limit = config.evidence_budgets["referee_context_chars"]
	try:
		templates = validate_prompt_templates()
		context = evidence_context(packet, limit)
		candidate_a = (
			candidates[mapping["A"]].post if "A" in mapping else "Candidate A is unavailable."
		)
		candidate_b = (
			candidates[mapping["B"]].post if "B" in mapping else "Candidate B is unavailable."
		)
		prompt = templates["referee"].format(
			rubric=templates["rubric"],
			evidence_json=context,
			candidate_a=candidate_a,
			candidate_b=candidate_b,
		)
		if len(prompt) > limit:
			raise RuntimeError(
				f"Referee prompt requires {len(prompt)} characters and exceeds its {limit} budget."
			)
	except RuntimeError as error:
		return {
			"winner": "NONE",
			"reason": _route_failure_reason(error),
			"evidence_quality": "low",
			"confidence": 0.0,
		}
	try:
		response = runner.run(config.referee_route, prompt, config.daily_blog_repository)
	except RuntimeError as error:
		return {
			"winner": "NONE",
			"reason": _route_failure_reason(error),
			"evidence_quality": "low",
			"confidence": 0.0,
		}
	try:
		return _parse_verdict(response, set(mapping))
	except (json.JSONDecodeError, RuntimeError):
		repair_prompt = templates["repair"].format(
			response=response[:MAX_REFEREE_RESPONSE_CHARS]
		)
		try:
			repaired = runner.run(config.referee_route, repair_prompt, config.daily_blog_repository)
		except RuntimeError:
			return {
				"winner": "NONE",
				"reason": "The referee repair route remained pending.",
				"evidence_quality": "low",
				"confidence": 0.0,
			}
		try:
			return _parse_verdict(repaired, set(mapping))
		except (json.JSONDecodeError, RuntimeError):
			return {
				"winner": "NONE",
				"reason": "The referee result did not satisfy the structured decision contract.",
				"evidence_quality": "low",
				"confidence": 0.0,
			}


#============================================
def select_candidate(
	packet: daily_blog.schema.EvidencePacket,
	run_id: str,
	candidates: list[CandidateResult],
	config: daily_blog.config.DailyBlogConfig,
	runner: object | None = None,
) -> EditorialDecision:
	"""Anonymize valid candidates and publish exactly the referee-approved result."""
	mapping = _anonymous_mapping(packet.packet_id, candidates)
	if not mapping:
		post = daily_blog.candidates.provisional_post(packet, run_id)
		decision = EditorialDecision(
			winner="NONE",
			reason="Both author candidates failed deterministic validation.",
			evidence_quality="low",
			confidence=0.0,
			publication_quality="provisional",
			post=post,
			anonymous_mapping={},
		)
		return decision
	route_runner = runner if runner is not None else daily_blog.routes.CommandRouteRunner()
	verdict = _referee_verdict(packet, candidates, mapping, config, route_runner)
	winner = verdict["winner"]
	if winner == "NONE":
		post = daily_blog.candidates.provisional_post(packet, run_id)
		quality = "provisional"
	else:
		post = candidates[mapping[winner]].post
		quality = "final"
	decision = EditorialDecision(
		winner=winner,
		reason=verdict["reason"],
		evidence_quality=verdict["evidence_quality"],
		confidence=verdict["confidence"],
		publication_quality=quality,
		post=post,
		anonymous_mapping=mapping,
	)
	return decision

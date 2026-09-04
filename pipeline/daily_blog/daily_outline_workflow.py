"""Pure replicated Stage 5 ranking and whole daily-outline workflow."""

import collections.abc
import dataclasses
import datetime
import json
import os
import re

import daily_blog.agents
import daily_blog.artifacts
import daily_blog.candidate_set_prompts
import daily_blog.editorial_stage_config
import daily_blog.daily_outline_prompts
import daily_blog.daily_outline_context
import daily_blog.io_utils
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.loader
import daily_blog.projection
import daily_blog.replication
import daily_blog.routes
import daily_blog.schema


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
STORY_RANKING_ALIAS_MAP_VERSION = "story-ranking-alias-map.v1"


@dataclasses.dataclass(frozen=True)
class StoryRankingAliasMap:
	"""Map model-visible Stage 5 story aliases to durable canonical hashes."""

	version: str
	mappings: tuple[tuple[str, str], ...]
	identity_sha256: str

	def __post_init__(self) -> None:
		if (
			type(self.version) is not str
			or self.version != STORY_RANKING_ALIAS_MAP_VERSION
			or type(self.mappings) is not tuple
			or not self.mappings
			or any(
				type(item) is not tuple
				or len(item) != 2
				or type(item[0]) is not str
				or type(item[1]) is not str
				for item in self.mappings
			)
			or type(self.identity_sha256) is not str
		):
			raise RuntimeError("Story-ranking alias map fields are invalid.")
		width = max(2, len(str(len(self.mappings))))
		expected_aliases = tuple(
			"story-" + str(index).zfill(width)
			for index in range(1, len(self.mappings) + 1)
		)
		aliases = tuple(alias for alias, _content_hash in self.mappings)
		content_hashes = tuple(content_hash for _alias, content_hash in self.mappings)
		if (
			aliases != expected_aliases
			or len(set(content_hashes)) != len(content_hashes)
			or any(_SHA256.fullmatch(content_hash) is None for content_hash in content_hashes)
		):
			raise RuntimeError("Story-ranking alias map is not an exact bijection.")
		canonical = {
			"version": self.version,
			"mappings": [[alias, content_hash] for alias, content_hash in self.mappings],
		}
		if self.identity_sha256 != daily_blog.io_utils.hash_value(canonical):
			raise RuntimeError("Story-ranking alias map identity conflicts with its mappings.")

	@classmethod
	def from_stories(
		cls, stories: tuple[daily_blog.artifacts.RepoStory, ...],
	) -> "StoryRankingAliasMap":
		"""Create one repository-sorted, stable alias map from exact stories."""
		if (
			type(stories) is not tuple
			or not stories
			or any(type(story) is not daily_blog.artifacts.RepoStory for story in stories)
		):
			raise RuntimeError("Story-ranking aliases require exact repository stories.")
		ordered = tuple(sorted(stories, key=lambda story: (story.repositories[0], story.content_hash)))
		width = max(2, len(str(len(ordered))))
		mappings = tuple(
			("story-" + str(index).zfill(width), story.content_hash)
			for index, story in enumerate(ordered, start=1)
		)
		canonical = {
			"version": STORY_RANKING_ALIAS_MAP_VERSION,
			"mappings": [[alias, content_hash] for alias, content_hash in mappings],
		}
		return cls(
			STORY_RANKING_ALIAS_MAP_VERSION,
			mappings,
			daily_blog.io_utils.hash_value(canonical),
		)

	@property
	def aliases(self) -> tuple[str, ...]:
		"""Return exact model-visible aliases in stable repository order."""
		return tuple(alias for alias, _content_hash in self.mappings)

	@property
	def content_hashes(self) -> tuple[str, ...]:
		"""Return canonical story hashes in the corresponding alias order."""
		return tuple(content_hash for _alias, content_hash in self.mappings)

	def content_hash_for(self, alias: object) -> str:
		"""Resolve one exact model alias without prefix or heuristic matching."""
		if type(alias) is not str:
			raise daily_blog.daily_outline_prompts.DailyOutlineRankingParseError(
				"invalid_aliases"
			)
		for mapped_alias, content_hash in self.mappings:
			if alias == mapped_alias:
				return content_hash
		raise daily_blog.daily_outline_prompts.DailyOutlineRankingParseError(
			"invalid_aliases"
		)

	def alias_for(self, content_hash: object) -> str:
		"""Project one canonical story hash to its exact model alias."""
		if type(content_hash) is not str:
			raise RuntimeError("Story-ranking canonical identity is invalid.")
		for alias, mapped_hash in self.mappings:
			if content_hash == mapped_hash:
				return alias
		raise RuntimeError("Story-ranking canonical identity is absent from alias map.")

	def cache_identity(self) -> dict[str, object]:
		"""Return the sealed alias-map identity used by every Stage 5 route cache key."""
		return {
			"version": self.version,
			"identity_sha256": self.identity_sha256,
			"mappings": [[alias, content_hash] for alias, content_hash in self.mappings],
		}

	def to_dict(self) -> dict[str, object]:
		"""Return the complete versioned map for exact identity verification."""
		return self.cache_identity()

	@classmethod
	def from_dict(cls, value: object) -> "StoryRankingAliasMap":
		"""Load one exact persisted map without accepting alternate representations."""
		if type(value) is not dict or set(value) != {"version", "identity_sha256", "mappings"}:
			raise RuntimeError("Story-ranking alias map serialization is invalid.")
		mappings = value["mappings"]
		if type(mappings) is not list:
			raise RuntimeError("Story-ranking alias map serialization is invalid.")
		return cls(
			value["version"],
			tuple(tuple(item) if type(item) is list else item for item in mappings),
			value["identity_sha256"],
		)


@dataclasses.dataclass(frozen=True)
class DailyOutlineInput:
	repo_stories: tuple[daily_blog.artifacts.RepoStory, ...]
	repo_outlines: tuple[daily_blog.artifacts.RepoOutline, ...]
	packets: tuple[daily_blog.schema.EvidencePacket, ...]
	evidence_context: daily_blog.schema.BoundedEvidenceContext
	working_directory: str
	repository_context: daily_blog.daily_outline_context.BoundedRepositoryEditorialContext | None = None

	def __post_init__(self) -> None:
		if (
			type(self.repo_stories) is not tuple
			or type(self.repo_outlines) is not tuple
			or type(self.packets) is not tuple
			or type(self.evidence_context) is not daily_blog.schema.BoundedEvidenceContext
			or (
				self.repository_context is not None
				and type(self.repository_context)
				is not daily_blog.daily_outline_context.BoundedRepositoryEditorialContext
			)
		):
			raise RuntimeError("Daily-outline input requires tuples.")
		if not self.repo_stories or len(self.repo_stories) != len(self.repo_outlines) or not self.packets:
			raise RuntimeError("Daily-outline input requires complete repository artifacts and packets.")
		if any(type(item) is not daily_blog.artifacts.RepoStory for item in self.repo_stories) or any(type(item) is not daily_blog.artifacts.RepoOutline for item in self.repo_outlines) or any(type(item) is not daily_blog.schema.EvidencePacket for item in self.packets):
			raise RuntimeError("Daily-outline input requires exact artifact types.")
		if type(self.working_directory) is not str or not os.path.isabs(self.working_directory) or os.path.realpath(self.working_directory) != self.working_directory or not os.path.isdir(self.working_directory):
			raise RuntimeError("Daily-outline input requires an existing physical working directory.")
		packets = tuple(sorted(self.packets, key=lambda item: item.packet_id))
		stories = tuple(sorted(self.repo_stories, key=lambda item: item.artifact_id))
		outlines = tuple(sorted(self.repo_outlines, key=lambda item: item.artifact_id))
		if len({item.packet_id for item in packets}) != len(packets) or len({item.artifact_id for item in stories}) != len(stories) or len({item.artifact_id for item in outlines}) != len(outlines):
			raise RuntimeError("Daily-outline input identities cannot repeat.")
		object.__setattr__(self, "packets", packets)
		object.__setattr__(self, "repo_stories", stories)
		object.__setattr__(self, "repo_outlines", outlines)
		expected_context = daily_blog.daily_outline_context.BoundedRepositoryEditorialContext.create(
			stories, outlines, packets,
			daily_blog.daily_outline_prompts.MAX_STORIES_CONTEXT_CHARS,
			daily_blog.daily_outline_prompts.MAX_REPOSITORY_OUTLINES_CONTEXT_CHARS,
		)
		context = self.repository_context or expected_context
		if context.to_dict() != expected_context.to_dict():
			raise RuntimeError("Daily-outline repository context identity conflicts with its content.")
		object.__setattr__(self, "repository_context", context)
		date = stories[0].report_date
		try:
			datetime.date.fromisoformat(date)
		except (TypeError, ValueError) as error:
			raise RuntimeError("Daily-outline input report date is invalid.") from error
		packet_ids = frozenset(item.packet_id for item in packets)
		for packet in packets:
			daily_blog.schema.EvidencePacket.from_dict(packet.to_dict())
			if packet.report_date != date or packet.packet_id != daily_blog.io_utils.hash_value(packet.content_dict()):
				raise RuntimeError("Daily-outline packet identity or report date is invalid.")
		for artifact in stories + outlines:
			if (
				artifact.report_date != date
				or len(artifact.repositories) != 1
				or not daily_blog.artifacts.evaluate_eligibility(
					artifact, packets, allowed_repositories=artifact.repositories,
				).eligible
			):
				raise RuntimeError("Daily-outline artifact provenance or eligibility conflicts.")
		if tuple(sorted(item.repositories[0] for item in stories)) != tuple(sorted(item.repositories[0] for item in outlines)) or len({item.repositories[0] for item in stories}) != len(stories):
			raise RuntimeError("Daily-outline input repositories must align exactly.")
		local_packet_ids: set[str] = set()
		for story in stories:
			outline = next(item for item in outlines if item.repositories == story.repositories)
			if story.packet_ids != outline.packet_ids or not story.packet_ids:
				raise RuntimeError("Daily-outline paired artifacts must share local packet provenance.")
			for packet_id in story.packet_ids:
				matching = next((item for item in packets if item.packet_id == packet_id), None)
				if matching is None or {item.repository for item in matching.items} != set(story.repositories):
					raise RuntimeError("Daily-outline local packet scope conflicts with its repository.")
				local_packet_ids.add(packet_id)
		if local_packet_ids != packet_ids:
			raise RuntimeError("Daily-outline packet union contains an orphan local packet.")
		# The full packets stay authoritative for eligibility and publication.  The
		# separately sealed frame is the only evidence body exposed to Stage 5 routes.
		daily_blog.schema.BoundedEvidenceContext.from_dict(self.evidence_context.to_dict())
		daily_blog.projection.validate_bounded_evidence_context(packets, self.evidence_context)
		if self.evidence_context.context_chars > daily_blog.daily_outline_prompts.MAX_EVIDENCE_CONTEXT_CHARS:
			raise RuntimeError("Daily-outline evidence context exceeds its prompt limit.")
		self.evidence_context.render_context(self.evidence_context.context_chars)

	@property
	def report_date(self) -> str:
		return self.repo_stories[0].report_date

	@property
	def repositories(self) -> tuple[str, ...]:
		return tuple(sorted(item.repositories[0] for item in self.repo_stories))

	@property
	def story_ranking_aliases(self) -> StoryRankingAliasMap:
		"""Return the model-only alias boundary for this canonical story set."""
		return StoryRankingAliasMap.from_stories(self.repo_stories)

	def render_stories(self) -> str:
		return self.repository_context.story_context.render_context()

	def render_outlines(self) -> str:
		return self.repository_context.outline_context.render_context()

	def render_evidence(self) -> str:
		return self.evidence_context.render_context(self.evidence_context.context_chars)


@dataclasses.dataclass(frozen=True)
class RankingCandidate:
	candidate_id: str
	content_sha256: str
	request: daily_blog.agents.RouteRequest
	result: daily_blog.agents.AgentResult
	artifact_ids: tuple[str, ...]
	scores: tuple[tuple[str, int], ...]
	rationale: str

	def __post_init__(self) -> None:
		if (
			type(self.request) is not daily_blog.agents.RouteRequest
			or type(self.result) is not daily_blog.agents.AgentResult or not self.result.ok
			or type(self.artifact_ids) is not tuple or not self.artifact_ids
			or any(type(item) is not str or not item for item in self.artifact_ids)
			or len(set(self.artifact_ids)) != len(self.artifact_ids)
			or type(self.scores) is not tuple
			or any(type(pair) is not tuple or len(pair) != 2 for pair in self.scores)
			or tuple(key for key, _value in self.scores) != tuple(sorted(self.artifact_ids))
			or any(type(key) is not str or type(score) is not int or isinstance(score, bool) or not 0 <= score <= 100 for key, score in self.scores)
			or type(self.rationale) is not str or not self.rationale
			or len(self.rationale) > daily_blog.daily_outline_prompts.MAX_RATIONALE_CHARS
		):
			raise RuntimeError("Ranking candidate fields are invalid.")
		canonical = json.dumps({"request_identity_sha256": self.request.cache_input_hash, "artifact_ids": list(self.artifact_ids), "scores": dict(self.scores), "rationale": self.rationale}, sort_keys=True, separators=(",", ":"))
		content_hash = daily_blog.io_utils.sha256_text(canonical)
		if self.content_sha256 != content_hash or self.candidate_id != "ranking-" + content_hash[:24]:
			raise RuntimeError("Ranking candidate identity conflicts with canonical data.")

	def to_dict(self) -> dict[str, object]:
		return {"artifact_ids": list(self.artifact_ids), "scores": dict(self.scores), "rationale": self.rationale}

	def model_dict(self, aliases: StoryRankingAliasMap) -> dict[str, object]:
		"""Project durable ranking content into the model-only alias namespace."""
		return {
			"artifact_ids": [aliases.alias_for(item) for item in self.artifact_ids],
			"scores": {aliases.alias_for(item): score for item, score in self.scores},
			"rationale": self.rationale,
		}


@dataclasses.dataclass(frozen=True)
class RankingObservation:
	request: daily_blog.agents.RouteRequest
	result: daily_blog.agents.AgentResult
	candidate: RankingCandidate | None
	failure: str = ""


@dataclasses.dataclass(frozen=True)
class RankingReviewObservation:
	candidate_id: str
	request: daily_blog.agents.RouteRequest
	result: daily_blog.agents.AgentResult
	verdict: tuple[tuple[str, object], ...] | None
	failure: str = ""

	def __post_init__(self) -> None:
		if type(self.candidate_id) is not str or not self.candidate_id or type(self.request) is not daily_blog.agents.RouteRequest or type(self.result) is not daily_blog.agents.AgentResult:
			raise RuntimeError("Ranking-review observation provenance is invalid.")
		if self.verdict is None:
			if self.failure not in daily_blog.replication.REVIEW_FAILURES:
				raise RuntimeError("Failed ranking review requires a bounded reason.")
			return
		if (
			type(self.verdict) is not tuple or len(self.verdict) != 3
			or any(type(pair) is not tuple or len(pair) != 2 for pair in self.verdict)
			or tuple(key for key, _item in self.verdict) != ("decision", "reason", "score")
		):
			raise RuntimeError("Ranking-review verdict is invalid.")
		value = dict(self.verdict)
		if self.failure or type(value["decision"]) is not str or value["decision"] not in {"ACCEPT", "REJECT"} or type(value["score"]) is not int or isinstance(value["score"], bool) or not 0 <= value["score"] <= 100 or type(value["reason"]) is not str or not value["reason"] or len(value["reason"]) > 500:
			raise RuntimeError("Ranking-review verdict is invalid.")


@dataclasses.dataclass(frozen=True)
class PromotedRanking:
	candidate_id: str
	ranking_content_sha256: str
	artifact_ids: tuple[str, ...]
	scores: tuple[tuple[str, int], ...]
	rationale: str
	review_ids: tuple[str, ...]
	method: str = "available_ranking"
	promotion_id: str = dataclasses.field(init=False)

	def __post_init__(self) -> None:
		if (
			type(self.candidate_id) is not str or not self.candidate_id
			or type(self.ranking_content_sha256) is not str
			or re.fullmatch(r"[0-9a-f]{64}", self.ranking_content_sha256) is None
			or type(self.artifact_ids) is not tuple or not self.artifact_ids
			or any(type(item) is not str or not item for item in self.artifact_ids)
			or type(self.scores) is not tuple
			or any(type(pair) is not tuple or len(pair) != 2 for pair in self.scores)
			or type(self.rationale) is not str or not self.rationale
			or len(self.rationale) > daily_blog.daily_outline_prompts.MAX_RATIONALE_CHARS
			or type(self.review_ids) is not tuple
			or tuple(sorted(set(self.review_ids))) != self.review_ids
			or any(type(item) is not str or not item for item in self.review_ids)
			or tuple(key for key, _value in self.scores) != tuple(sorted(self.artifact_ids))
			or any(type(key) is not str or type(score) is not int or isinstance(score, bool) or not 0 <= score <= 100 for key, score in self.scores)
			or len(set(self.artifact_ids)) != len(self.artifact_ids)
			or self.method not in {
				"review_preferred_ranking", "available_ranking",
				"deterministic_story_order",
			}
		):
			raise RuntimeError("Promoted ranking fields are invalid.")
		canonical = json.dumps({
			"candidate_id": self.candidate_id,
			"method": self.method,
			"ranking_content_sha256": self.ranking_content_sha256,
			"review_ids": list(self.review_ids),
		}, sort_keys=True, separators=(",", ":"))
		object.__setattr__(
			self, "promotion_id",
			"ranking-promotion-" + daily_blog.io_utils.sha256_text(canonical)[:24],
		)

	def to_dict(self) -> dict[str, object]:
		return {"promotion_id": self.promotion_id, "candidate_id": self.candidate_id, "artifact_ids": list(self.artifact_ids), "scores": dict(self.scores), "rationale": self.rationale, "method": self.method}

	def model_dict(self, aliases: StoryRankingAliasMap) -> dict[str, object]:
		"""Project durable promotion content into the model-only alias namespace."""
		return {
			"artifact_ids": [aliases.alias_for(item) for item in self.artifact_ids],
			"scores": {aliases.alias_for(item): score for item, score in self.scores},
			"rationale": self.rationale,
		}


@dataclasses.dataclass(frozen=True)
class DailyOutlineResult:
	promotion: daily_blog.artifacts.SelectedPeer | daily_blog.artifacts.DegradedPromotion | daily_blog.artifacts.NoArtifact
	rankings: tuple[RankingObservation, ...]
	ranking_reviews: tuple[RankingReviewObservation, ...]
	promoted_ranking: PromotedRanking | None
	generation: daily_blog.replication.ReplicationResult
	review: daily_blog.replication.CandidateSetReviewResult
	reliability: tuple[daily_blog.replication.StepReliability, ...]
	source_stories: tuple[daily_blog.artifacts.RepoStory, ...]

	@property
	def artifact(self) -> daily_blog.artifacts.DailyOutline | None:
		return None if isinstance(self.promotion, daily_blog.artifacts.NoArtifact) else self.promotion.artifact

	@property
	def selected_stories(self) -> tuple[daily_blog.artifacts.RepoStory, ...]:
		return () if self.artifact is None else tuple(item for item in self.source_stories if item.repositories[0] in self.artifact.repositories)


def _request(
	value: DailyOutlineInput, step: str, role: str, ordinal: str,
	route: daily_blog.editorial_stage_config.RoleRoute, prompt: str,
	config: daily_blog.editorial_stage_config.DailyOutlineConfig,
	contract_identity: dict[str, object],
	input_ids: tuple[str, ...] = (),
	assignment: daily_blog.replication.CandidateSetReviewAssignment | None = None,
) -> daily_blog.agents.RouteRequest:
	assignment_value = {} if assignment is None else dataclasses.asdict(assignment)
	identity = {
		"report_date": value.report_date,
		"repositories": list(value.repositories),
		"packet_ids": sorted(
			daily_blog.schema.model_cache_packet_identity(item) for item in value.packets
		),
		"evidence_context_model_id": value.evidence_context.model_context_id,
		"repository_context_model_id": value.repository_context.model_context_id,
		"repository_context_projection_version": value.repository_context.story_context.projection_version,
		"story_ranking_alias_map": value.story_ranking_aliases.cache_identity(),
		"story_ids": sorted(item.content_hash for item in value.repo_stories),
		"outline_ids": sorted(item.content_hash for item in value.repo_outlines),
		"step": step,
		"role": role,
		"ordinal": ordinal,
		"input_ids": sorted(input_ids),
		"prompt_identity": contract_identity,
		"assignment": assignment_value,
	}
	input_hash = daily_blog.io_utils.hash_value(identity)
	contract_version = ":".join((
		daily_blog.prompt_registry.definitions.DAILY_OUTLINE_PROMPT_SET.version,
		STORY_RANKING_ALIAS_MAP_VERSION,
		value.story_ranking_aliases.identity_sha256,
		str(contract_identity["integrity_sha256"]),
	))
	return daily_blog.agents.RouteRequest(
		request_id=f"stage5_{step}_{role}_{ordinal}_{input_hash[:12]}",
		step=f"daily_outline_{step}", route=route, prompt=prompt,
		working_directory=value.working_directory, role=role,
		retry_attempts=config.route_retry_attempts,
		maximum_parallel_calls=config.maximum_parallel_calls,
		input_hash=input_hash, contract_version=contract_version, cache_input_hash=input_hash,
	)


def _parse_model_ranking(
	response: str, aliases: StoryRankingAliasMap,
) -> dict[str, object]:
	"""Parse exact model aliases, then restore canonical hashes before durability."""
	if type(response) is not str or len(response) > daily_blog.daily_outline_prompts.MAX_RESPONSE_CHARS:
		raise daily_blog.daily_outline_prompts.DailyOutlineRankingParseError(
			"response_limit"
		)
	try:
		value = json.loads(response.strip(), object_pairs_hook=_strict_json_object)
	except (json.JSONDecodeError, ValueError) as error:
		raise daily_blog.daily_outline_prompts.DailyOutlineRankingParseError(
			"invalid_json"
		) from error
	if type(value) is not dict or set(value) != {"artifact_ids", "scores", "rationale"}:
		raise daily_blog.daily_outline_prompts.DailyOutlineRankingParseError(
			"invalid_fields"
		)
	if type(value["artifact_ids"]) is not list or any(type(item) is not str for item in value["artifact_ids"]):
		raise daily_blog.daily_outline_prompts.DailyOutlineRankingParseError(
			"invalid_order"
		)
	if type(value["scores"]) is not dict or any(type(item) is not str for item in value["scores"]):
		raise daily_blog.daily_outline_prompts.DailyOutlineRankingParseError(
			"invalid_scores"
		)
	if set(value["artifact_ids"]) != set(aliases.aliases) or set(value["scores"]) != set(aliases.aliases):
		raise daily_blog.daily_outline_prompts.DailyOutlineRankingParseError(
			"invalid_aliases"
		)
	canonical_response = json.dumps({
		"artifact_ids": [aliases.content_hash_for(item) for item in value["artifact_ids"]],
		"scores": {
			aliases.content_hash_for(alias): score
			for alias, score in value["scores"].items()
		},
		"rationale": value["rationale"],
	}, sort_keys=True, separators=(",", ":"))
	return daily_blog.daily_outline_prompts.parse_story_ranking(
		canonical_response, aliases.content_hashes,
	)


def _strict_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
	"""Reject duplicate JSON members before a ranking identity is interpreted."""
	value: dict[str, object] = {}
	for key, item in pairs:
		if key in value:
			raise ValueError("Daily-story ranking contains duplicate JSON members.")
		value[key] = item
	return value


def _candidate(request: daily_blog.agents.RouteRequest, result: daily_blog.agents.AgentResult, ranking: dict[str, object]) -> RankingCandidate:
	ids, scores, rationale = tuple(ranking["artifact_ids"]), tuple(sorted(ranking["scores"].items())), ranking["rationale"]
	canonical = json.dumps({"request_identity_sha256": request.cache_input_hash, "artifact_ids": list(ids), "scores": dict(scores), "rationale": rationale}, sort_keys=True, separators=(",", ":"))
	hash_value = daily_blog.io_utils.sha256_text(canonical)
	return RankingCandidate("ranking-" + hash_value[:24], hash_value, request, result, ids, scores, rationale)


def _outline(value: DailyOutlineInput, result: daily_blog.agents.AgentResult) -> daily_blog.artifacts.DailyOutline:
	"""Derive outline scope from trusted evidence instead of model packaging syntax."""
	content = result.text.rstrip() + "\n"
	content, evidence_ids = daily_blog.artifacts.ensure_evidence_references(
		content,
		tuple(sorted({
			evidence_id for story in value.repo_stories for evidence_id in story.evidence_ids
		})),
	)
	try:
		repositories = daily_blog.artifacts.resolve_evidence_scope(
			evidence_ids, value.packets, value.repositories,
		)
	except daily_blog.artifacts.EvidenceScopeError as error:
		raise daily_blog.agents.RepairableStructuredOutput(
			"Daily outline evidence scope is invalid."
		) from error
	selected_packets = tuple(
		packet for packet in value.packets
		if {item.repository for item in packet.items}.issubset(repositories)
	)
	return daily_blog.artifacts.DailyOutline.create(
		value.report_date, selected_packets, repositories, content, evidence_ids,
		daily_blog.artifacts.referenced_image_paths(content),
	)


def _generation_reliability(step: str, generation: daily_blog.replication.ReplicationResult, reasons: tuple[str, ...] = ()) -> daily_blog.replication.StepReliability:
	reason_set = set(reasons) | {item.failure for item in generation.candidates if item.failure}
	if any(item.result.ok and (item.eligibility is None or not item.eligibility.eligible) for item in generation.candidates): reason_set.add("ineligible_generation")
	succeeded = sum(item.result.ok and item.eligibility is not None and item.eligibility.eligible for item in generation.candidates)
	return daily_blog.replication.StepReliability(step, "degraded" if reason_set else "succeeded", len(generation.candidates), succeeded, len(generation.candidates) - succeeded, sum(item.result.ok and item.result.resumed for item in generation.candidates), 0, 0, "", tuple(sorted(reason_set)), response_chars=daily_blog.replication.response_characters(generation))


def _ranking_reliability(
	rankings: tuple[RankingObservation, ...], fallback_used: bool,
) -> daily_blog.replication.StepReliability:
	reasons = {item.failure for item in rankings if item.failure}
	if fallback_used:
		reasons.add("ranking_fallback_used")
	return daily_blog.replication.StepReliability("5.1", "degraded" if reasons else "succeeded", len(rankings), sum(item.candidate is not None for item in rankings), sum(item.candidate is None for item in rankings), sum(item.result.ok and item.result.resumed for item in rankings), 0, 0, "", tuple(sorted(reasons)))


def _promotion_reliability(promotion: object) -> daily_blog.replication.StepReliability:
	reasons = (promotion.reason,) if isinstance(promotion, daily_blog.artifacts.NoArtifact) else (promotion.reasons if isinstance(promotion, daily_blog.artifacts.DegradedPromotion) else ())
	return daily_blog.replication.StepReliability("5.5", "degraded" if reasons else "succeeded", 1, 1, 0, 0, 0, 0, "" if isinstance(promotion, daily_blog.artifacts.NoArtifact) else promotion.artifact.artifact_id, tuple(sorted(reasons)))


def _ranking_promotion_reliability(reviews: tuple[RankingReviewObservation, ...], promoted: PromotedRanking | None, had_candidates: bool) -> daily_blog.replication.StepReliability:
	reasons = {item.failure for item in reviews if item.failure}
	if reviews and not any(item.verdict is not None for item in reviews): reasons.add("review_unavailable")
	if not had_candidates: reasons.add("ranking_fallback_used")
	succeeded = sum(item.verdict is not None for item in reviews)
	return daily_blog.replication.StepReliability("5.2", "degraded" if reasons else "succeeded", len(reviews), succeeded, len(reviews) - succeeded, sum(item.result.ok and item.result.resumed for item in reviews), 0, 0, "" if promoted is None else promoted.promotion_id, tuple(sorted(reasons)))


def _review_reliability(review: daily_blog.replication.CandidateSetReviewResult) -> daily_blog.replication.StepReliability:
	disagreements = daily_blog.replication.review_disagreements(review.votes)
	reasons = daily_blog.replication.review_reasons(review.votes, disagreements)
	return daily_blog.replication.StepReliability("5.4", "degraded" if reasons else "succeeded", len(review.votes), sum(item.status == "succeeded" for item in review.votes), sum(item.status == "failed" for item in review.votes), 0, 0, disagreements, "", reasons)


def _promote_ranking(candidates: tuple[RankingCandidate, ...], reviews: tuple[RankingReviewObservation, ...]) -> PromotedRanking | None:
	"""Prefer useful review signals without letting a reviewer veto available work."""
	available = []
	for candidate in candidates:
		observations = tuple(item for item in reviews if item.candidate_id == candidate.candidate_id and item.verdict is not None)
		verdicts = tuple(dict(item.verdict) for item in observations)
		review_ids = tuple(sorted(item.request.request_id for item in observations))
		accepted = any(item["decision"] == "ACCEPT" for item in verdicts)
		score = sum(int(item["score"]) for item in verdicts) / len(verdicts) if verdicts else -1
		available.append((candidate, verdicts, review_ids, accepted, score))
	if not available:
		return None
	best = sorted(available, key=lambda item: (
		not item[3], -item[4], item[0].content_sha256, item[0].candidate_id,
	))[0]
	candidate, verdicts, review_ids, _accepted, _score = best
	method = "review_preferred_ranking" if verdicts else "available_ranking"
	return PromotedRanking(candidate.candidate_id, candidate.content_sha256,
		candidate.artifact_ids, candidate.scores, candidate.rationale, review_ids, method)


def _deterministic_ranking(value: DailyOutlineInput) -> PromotedRanking:
	"""Use every available story when no ranker returns a parseable preference."""
	artifact_ids = value.story_ranking_aliases.content_hashes
	scores = tuple((artifact_id, 50) for artifact_id in artifact_ids)
	rationale = "Use every repository story in stable repository order."
	ranking_content = json.dumps({"artifact_ids": list(artifact_ids),
		"rationale": rationale, "scores": dict(scores)}, sort_keys=True, separators=(",", ":"))
	ranking_hash = daily_blog.io_utils.sha256_text(ranking_content)
	return PromotedRanking("ranking-fallback-" + ranking_hash[:24], ranking_hash,
		artifact_ids, scores, rationale, (), "deterministic_story_order")


@dataclasses.dataclass(frozen=True)
class _DailyOutlinePreparation:
	"""Validated shared inputs for all Stage 5 route roles."""

	prompts: daily_blog.prompt_registry.loader.LoadedPromptSet
	identity: dict[str, object]
	stories_json: str
	outlines_json: str
	evidence_json: str
	story_ids: tuple[str, ...]
	story_aliases: StoryRankingAliasMap
	route_runner: object


#============================================
def _repository_context_needs_reduction(value: DailyOutlineInput) -> bool:
	"""Return whether deterministic projection had to excerpt any editorial artifact."""
	contexts = value.repository_context.story_context.stories + value.repository_context.outline_context.stories
	return any(item.full_source_chars > len(item.content_excerpt) for item in contexts)


#============================================
def _reduce_repository_context(
	value: DailyOutlineInput,
	config: daily_blog.editorial_stage_config.DailyOutlineConfig,
	budget: daily_blog.agents.RouteBudget,
	route_runner: object,
	cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None,
	cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None,
) -> tuple[str, str]:
	"""Use one tolerant, linear summarizer per repository when the full set is too large."""
	prompts = daily_blog.prompt_registry.loader.load_prompt_set(
		daily_blog.prompt_registry.definitions.CONTEXT_REDUCTION_PROMPT_SET,
	)
	identity = prompts.identity_dict()
	identity["integrity_sha256"] = daily_blog.io_utils.hash_value(identity)
	outlines = {item.repositories[0]: item for item in value.repo_outlines}
	requests = []
	for index, story in enumerate(value.repo_stories):
		outline = outlines[story.repositories[0]]
		material = json.dumps({
			"repository_story": story.content[:45000],
			"repository_outline": outline.content[:15000],
		}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
		prompt = prompts.render(
			daily_blog.prompt_registry.definitions.CONTEXT_REDUCTION_RESOURCE,
			{"repository": story.repositories[0], "material": material},
		)
		requests.append(_request(
			value, "5_0", "context_summarizer", str(index), config.ranking_route,
			prompt, config, identity, (story.content_hash, outline.content_hash),
		))
	results = daily_blog.agents.execute_requests(
		requests, route_runner, config.maximum_parallel_calls, budget, cache_load,
	)
	summaries = []
	story_excerpts = {item.repository: item.content_excerpt for item in value.repository_context.story_context.stories}
	outline_excerpts = {item.repository: item.content_excerpt for item in value.repository_context.outline_context.stories}
	for story, request, result in zip(value.repo_stories, requests, results, strict=True):
		if result.ok:
			summary = result.text.strip()[:1200]
			if not result.resumed and cache_accept is not None:
				cache_accept(request, result)
		else:
			summary = (story_excerpts[story.repositories[0]] + "\n" + outline_excerpts[story.repositories[0]]).strip()[:1200]
		summaries.append({"repository": story.repositories[0], "summary": summary})
	story_context = json.dumps({
		"schema_version": "daily-story-context-summary.v1",
		"repositories": summaries,
	}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
	outline_context = json.dumps({
		"schema_version": "daily-story-context-summary.v1",
		"repositories": [
			{"repository": item["repository"], "summary_available": bool(item["summary"])}
			for item in summaries
		],
	}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
	return story_context, outline_context


#============================================
def _prepare_daily_outline(
	value: DailyOutlineInput,
	config: daily_blog.editorial_stage_config.DailyOutlineConfig,
	budget: daily_blog.agents.RouteBudget,
	runner: object | None,
	prompts: daily_blog.prompt_registry.loader.LoadedPromptSet | None,
	cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None,
	cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None,
) -> _DailyOutlinePreparation:
	"""Validate the coordinator boundary and build its immutable route context."""
	# ASVS 2.2.1/2.3.1: exact trusted inputs are validated before route work,
	# then the coordinator passes only the resulting ordered context downstream.
	if type(value) is not DailyOutlineInput or type(config) is not daily_blog.editorial_stage_config.DailyOutlineConfig or type(budget) is not daily_blog.agents.RouteBudget:
		raise RuntimeError("Daily-outline workflow requires exact input, configuration, and RouteBudget.")
	prompt_value = daily_blog.prompt_registry.loader.resolve_loaded_prompt_set(
		prompts, daily_blog.prompt_registry.definitions.DAILY_OUTLINE_PROMPT_SET,
	)
	identity = daily_blog.daily_outline_prompts.daily_outline_prompt_identity(prompt_value)
	route_runner = runner if runner is not None else daily_blog.routes.CommandRouteRunner()
	stories_json = value.render_stories()
	outlines_json = value.render_outlines()
	if _repository_context_needs_reduction(value):
		stories_json, outlines_json = _reduce_repository_context(
			value, config, budget, route_runner, cache_load, cache_accept,
		)
	return _DailyOutlinePreparation(
		prompt_value,
		identity,
		stories_json,
		outlines_json,
		value.render_evidence(),
		tuple(item.content_hash for item in value.repo_stories),
		value.story_ranking_aliases,
		route_runner,
	)


def _observe_rankings(
	value: DailyOutlineInput,
	config: daily_blog.editorial_stage_config.DailyOutlineConfig,
	budget: daily_blog.agents.RouteBudget,
	prepared: _DailyOutlinePreparation,
	cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None,
	cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None,
) -> tuple[tuple[RankingObservation, ...], tuple[RankingCandidate, ...], bool]:
	"""Observe one ranker wave; callers own the deterministic no-ranking fallback."""
	def observe_wave(step: str, role: str, replica_prefix: str) -> tuple[RankingObservation, ...]:
		requests = tuple(
			_request(
				value, step, role, str(index), config.ranking_route,
				daily_blog.daily_outline_prompts.render_story_ranking(
					prepared.stories_json, prepared.outlines_json, prepared.evidence_json,
					replica_prefix + str(index), prepared.prompts,
				),
				config, prepared.identity, prepared.story_ids,
			)
			for index in range(config.ranker_count)
		)
		results = daily_blog.agents.execute_requests(
			list(requests), prepared.route_runner, config.maximum_parallel_calls, budget, cache_load,
		)
		observations: list[RankingObservation] = []
		for request, result in zip(requests, results, strict=True):
			try:
				candidate = None
				if result.ok:
					candidate = _candidate(request, result, _parse_model_ranking(result.text, prepared.story_aliases))
				if candidate is not None and not result.resumed and cache_accept is not None:
					cache_accept(request, result)
				observations.append(RankingObservation(
					request, result, candidate,
					"" if candidate else (result.failure or "ineligible_generation"),
				))
			except daily_blog.daily_outline_prompts.DailyOutlineRankingParseError as error:
				observations.append(RankingObservation(request, result, None, error.category))
		return tuple(observations)

	primary = observe_wave("5_1", "ranker", "ranker-")
	candidates = tuple(item.candidate for item in primary if item.candidate is not None)
	return primary, candidates, not candidates


#============================================
def _replicate_outlines(
	value: DailyOutlineInput,
	config: daily_blog.editorial_stage_config.DailyOutlineConfig,
	budget: daily_blog.agents.RouteBudget,
	prepared: _DailyOutlinePreparation,
	promoted: PromotedRanking,
	cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None,
	cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None,
) -> daily_blog.replication.ReplicationResult:
	"""Generate independent whole-outline candidates from the promoted ranking."""
	ranking_json = json.dumps(
		promoted.model_dict(prepared.story_aliases), sort_keys=True, separators=(",", ":"),
	)
	requests = tuple(
		_request(
			value, "5_3", "outline_writer", str(index), config.outline_writer_route,
			daily_blog.daily_outline_prompts.render_daily_outline_writer(
				ranking_json, prepared.stories_json, prepared.outlines_json,
				prepared.evidence_json, "outline-writer-" + str(index), prepared.prompts,
			),
			config, prepared.identity, prepared.story_ids,
		)
		for index in range(config.outline_writer_count)
	)
	return daily_blog.replication.replicate(
		requests, prepared.route_runner, budget, daily_blog.artifacts.DailyOutline,
		lambda item: _outline(value, item),
		lambda item: daily_blog.artifacts.evaluate_eligibility(
			item, value.packets, allowed_repositories=value.repositories,
		),
		cache_load, cache_accept,
	)


def _review_outlines(
	value: DailyOutlineInput,
	config: daily_blog.editorial_stage_config.DailyOutlineConfig,
	budget: daily_blog.agents.RouteBudget,
	prepared: _DailyOutlinePreparation,
	peers: tuple[daily_blog.artifacts.DailyOutline, ...],
	cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None,
	cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None,
) -> daily_blog.replication.CandidateSetReviewResult:
	"""Review the complete eligible outline set once per independent reviewer."""
	review_prompts = daily_blog.candidate_set_prompts.load_prompt_set()
	review_identity = {**prepared.identity, "candidate_set_review": review_prompts.identity_dict()}
	review_identity["integrity_sha256"] = daily_blog.io_utils.hash_value(review_identity)
	context = json.dumps({
		"repository_stories": json.loads(prepared.stories_json),
		"repository_outlines": json.loads(prepared.outlines_json),
	}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

	def work(
		ordered: tuple[daily_blog.artifacts.EditorialArtifact, ...],
		assignment: daily_blog.replication.CandidateSetReviewAssignment,
	) -> daily_blog.replication.CandidateSetReviewWork:
		try:
			prompt, _labels = daily_blog.candidate_set_prompts.render_candidate_set_review(
				prepared.prompts.text(daily_blog.prompt_registry.definitions.DAILY_OUTLINE_RUBRIC_RESOURCE),
				context, ordered, review_prompts,
			)
		except RuntimeError as error:
			raise daily_blog.replication.ReviewUnavailable from error
		request = _request(
			value, "5_4", "outline_reviewer",
			str(assignment.reviewer_index),
			config.outline_reviewer_route,
			prompt, config, review_identity, tuple(item.content_hash for item in ordered), assignment,
		)
		return daily_blog.replication.CandidateSetReviewWork(request, assignment)

	def winner(text: str, item: daily_blog.replication.CandidateSetReviewWork) -> str:
		labels = dict(zip(
			daily_blog.candidate_set_prompts.candidate_labels(len(item.assignment.candidate_artifact_ids)),
			item.assignment.candidate_artifact_ids, strict=True,
		))
		try:
			return daily_blog.candidate_set_prompts.parse_candidate_set_verdict(text, labels)
		except daily_blog.candidate_set_prompts.CandidateSetVerdictParseError as error:
			raise daily_blog.agents.RepairableStructuredOutput(str(error)) from error

	return daily_blog.replication.review_candidate_set(
		peers, daily_blog.artifacts.DailyOutline, config.reviewer_count, work, winner,
		prepared.route_runner, budget, cache_load, cache_accept,
	)


def _daily_outline_result(
	promotion: daily_blog.artifacts.SelectedPeer | daily_blog.artifacts.DegradedPromotion | daily_blog.artifacts.NoArtifact,
	rankings: tuple[RankingObservation, ...],
	ranking_reviews: tuple[RankingReviewObservation, ...],
	promoted: PromotedRanking | None,
	generation: daily_blog.replication.ReplicationResult,
	review: daily_blog.replication.CandidateSetReviewResult,
	had_candidates: bool,
	ranking_fallback_used: bool,
	value: DailyOutlineInput,
) -> DailyOutlineResult:
	"""Build the typed terminal outcome and its stage-level reliability record."""
	return DailyOutlineResult(
		promotion, rankings, ranking_reviews, promoted, generation, review,
		(
			_ranking_reliability(rankings, ranking_fallback_used),
			_ranking_promotion_reliability(ranking_reviews, promoted, had_candidates),
			_generation_reliability(
				"5.3", generation,
				("upstream_unavailable",) if promoted is None else (),
			),
			_review_reliability(review),
			_promotion_reliability(promotion),
		),
		value.repo_stories,
	)


#============================================
def run_daily_outline(value: DailyOutlineInput, config: daily_blog.editorial_stage_config.DailyOutlineConfig, budget: daily_blog.agents.RouteBudget, runner: object | None = None, prompts: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None, cache_load: collections.abc.Callable[[daily_blog.agents.RouteRequest], daily_blog.agents.AgentResult | None] | None = None, cache_accept: collections.abc.Callable[[daily_blog.agents.RouteRequest, daily_blog.agents.AgentResult], None] | None = None) -> DailyOutlineResult:
	"""Coordinate ranking, replication, review, and promotion for Stage 5."""
	prepared = _prepare_daily_outline(
		value, config, budget, runner, prompts, cache_load, cache_accept,
	)
	rankings, candidates, ranking_fallback_used = _observe_rankings(
		value, config, budget, prepared, cache_load, cache_accept,
	)
	# Ranking candidates are already independent complete-day judgments. Select
	# one available ranking deterministically; another per-candidate judging wave
	# adds fan-out without improving the publication's recoverability.
	ranking_reviews: tuple[RankingReviewObservation, ...] = ()
	promoted = _promote_ranking(candidates, ranking_reviews)
	if promoted is None:
		promoted = _deterministic_ranking(value)
	generation = _replicate_outlines(
		value, config, budget, prepared, promoted, cache_load, cache_accept,
	)
	peers = tuple(sorted(
		{item.artifact_id: item for item in generation.eligible}.values(),
		key=lambda item: (item.content_hash, item.artifact_id),
	))
	if not peers:
		promotion = daily_blog.artifacts.NoArtifact(
			daily_blog.artifacts.DailyOutline, "no_eligible_generation",
		)
		return _daily_outline_result(
			promotion, rankings, ranking_reviews, promoted, generation,
			daily_blog.replication.CandidateSetReviewResult((), ()), True, ranking_fallback_used, value,
		)
	review = _review_outlines(
		value, config, budget, prepared, peers, cache_load, cache_accept,
	)
	promotion = daily_blog.replication.promote(
		peers, daily_blog.artifacts.DailyOutline,
		lambda item: daily_blog.artifacts.evaluate_eligibility(
			item, value.packets, allowed_repositories=value.repositories,
		),
		review.votes,
	)
	if len(peers) == 1 and isinstance(promotion, daily_blog.artifacts.SelectedPeer):
		promotion = daily_blog.artifacts.DegradedPromotion(
			promotion.artifact, daily_blog.artifacts.DailyOutline, ("review_unavailable",),
		)
	return _daily_outline_result(
		promotion, rankings, ranking_reviews, promoted, generation, review, True, ranking_fallback_used, value,
	)

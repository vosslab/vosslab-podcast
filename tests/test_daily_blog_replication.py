"""Offline behavioral tests for stage-neutral editorial replication."""

# Standard Library
import json

# PIP3 modules
import pytest

# local repo modules
import daily_blog.agents
import daily_blog.artifacts
import daily_blog.editorial_stage_config
import daily_blog.io_utils
import daily_blog.replication
import daily_blog.routes
import daily_blog.schema


#============================================
def packet() -> daily_blog.schema.EvidencePacket:
	"""Return one authoritative packet for exact-rung peer construction."""
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/project", "a" * 40, "docs/CHANGELOG.md", "b" * 40,
		"Grounded change.", "git show",
	)
	return daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item],
	)


#============================================
def outline(
	source: daily_blog.schema.EvidencePacket,
	body: str,
) -> daily_blog.artifacts.RepoOutline:
	"""Create a mechanically eligible same-rung editorial peer."""
	return daily_blog.artifacts.RepoOutline.create(
		source.report_date, (source,), "vosslab/project",
		f"{body} <!-- evidence: {source.items[0].evidence_id} -->",
		(source.items[0].evidence_id,),
	)


#============================================
def request(name: str) -> daily_blog.agents.RouteRequest:
	"""Build one isolated author request for the in-memory runner."""
	return daily_blog.agents.RouteRequest(
		name, "repo_outline", daily_blog.editorial_stage_config.RoleRoute("fake", ("fake",)), name,
		"/work", maximum_parallel_calls=2,
		cache_input_hash=daily_blog.io_utils.hash_value({"test": "replication", "request": name}),
	)


class Runner:
	"""Return deterministic route text while allowing one typed route failure."""

	#============================================
	def run(self, _route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, _directory: str) -> str:
		"""Return prompt text except for the declared failure request."""
		if prompt == "broken":
			raise daily_blog.routes.EditorialRouteTimeout("offline")
		return prompt


#============================================
def eligibility(
	artifact: daily_blog.artifacts.EditorialArtifact,
) -> daily_blog.artifacts.EligibilityResult:
	"""Apply the authoritative packet-specific mechanical predicate."""
	return daily_blog.artifacts.evaluate_eligibility(artifact, (packet(),))


#============================================
def test_replicate_retains_eligible_peer_after_one_generator_failure() -> None:
	"""Independent route loss leaves an eligible exact-rung result available."""
	source = packet()
	def parse(result: daily_blog.agents.AgentResult) -> daily_blog.artifacts.EditorialArtifact:
		return outline(source, result.text)
	result = daily_blog.replication.replicate(
		(request("strong"), request("broken")), Runner(), daily_blog.agents.RouteBudget(2, 2),
		daily_blog.artifacts.RepoOutline, parse,
		lambda value: daily_blog.artifacts.evaluate_eligibility(value, (source,)),
	)

	assert result.eligible == (outline(source, "strong"),)
	assert result.candidates[1].failure == "timeout"


#============================================
def test_review_repairs_malformed_json_to_a_known_eligible_candidate() -> None:
	"""A structured repair turns malformed review output into a valid candidate vote."""
	source = packet()
	first, second = outline(source, "First"), outline(source, "Second")
	def build(
		left: daily_blog.artifacts.EditorialArtifact,
		right: daily_blog.artifacts.EditorialArtifact,
		assignment: daily_blog.replication.ReviewAssignment,
	) -> daily_blog.replication.ReviewWork:
		return daily_blog.replication.ReviewWork(
			request(f"review-{assignment.reviewer_index}-{assignment.display_order}"),
			left.artifact_id,
			right.artifact_id,
			assignment,
		)
	def repair(
		work: daily_blog.replication.ReviewWork,
		_text: str,
	) -> daily_blog.replication.ReviewWork:
		repair_request = daily_blog.agents.RouteRequest(
			work.request.request_id + "_repair", "review", work.request.route,
			work.request.request_id + "_repair", "/work", maximum_parallel_calls=2,
			repair_of=work.request.cache_input_hash,
			cache_input_hash=daily_blog.io_utils.hash_value({
				"test": "replication-repair",
				"source_cache_input_hash": work.request.cache_input_hash,
				"malformed_response": _text,
			}),
		)
		return daily_blog.replication.ReviewWork(
			repair_request,
			work.first_artifact_id,
			work.second_artifact_id,
			work.assignment,
		)
	def parse(text: str, work: daily_blog.replication.ReviewWork) -> str:
		if not text.startswith("{"):
			raise daily_blog.agents.RepairableStructuredOutput("invalid JSON")
		return json.loads(text)["winner"]
	class ReviewRunner:
		def run(
			self,
			_route: daily_blog.editorial_stage_config.RoleRoute,
			prompt: str,
			_directory: str,
		) -> str:
			response = '{"winner":"' + first.artifact_id + '"}'
			return response if prompt.endswith("_repair") else "not-json"
	result = daily_blog.replication.review(
		(second, first), daily_blog.artifacts.RepoOutline, 2, build, parse, ReviewRunner(),
		daily_blog.agents.RouteBudget(8, 2), repair,
	)

	assert result.votes and all(
		vote.repaired and vote.winner_artifact_id == first.artifact_id
		for vote in result.votes
	)


#============================================
def test_review_salvages_only_unambiguous_candidate_identity() -> None:
	"""Free text can resolve only one known anonymous candidate identifier."""
	source = packet()
	first, second = outline(source, "First"), outline(source, "Second")
	def build(
		left: daily_blog.artifacts.EditorialArtifact,
		right: daily_blog.artifacts.EditorialArtifact,
		assignment: daily_blog.replication.ReviewAssignment,
	) -> daily_blog.replication.ReviewWork:
		return daily_blog.replication.ReviewWork(
			request(f"review-{assignment.reviewer_index}-{assignment.display_order}"),
			left.artifact_id,
			right.artifact_id,
			assignment,
		)
	def parse(_text: str, _work: daily_blog.replication.ReviewWork) -> str:
		raise daily_blog.agents.RepairableStructuredOutput("strict structure absent")
	def salvage(_text: str, work: daily_blog.replication.ReviewWork) -> str | None:
		return first.artifact_id
	class SalvageRunner:
		def run(
			self,
			_route: daily_blog.editorial_stage_config.RoleRoute,
			_prompt: str,
			_directory: str,
		) -> str:
			return "malformed verdict " + first.artifact_id
	def repair(
		work: daily_blog.replication.ReviewWork,
		_text: str,
	) -> daily_blog.replication.ReviewWork:
		repair_request = daily_blog.agents.RouteRequest(
			work.request.request_id + "_repair", "review", work.request.route,
			work.request.request_id + "_repair", "/work", maximum_parallel_calls=2,
			repair_of=work.request.cache_input_hash,
			cache_input_hash=daily_blog.io_utils.hash_value({
				"test": "replication-repair",
				"source_cache_input_hash": work.request.cache_input_hash,
				"malformed_response": _text,
			}),
		)
		return daily_blog.replication.ReviewWork(
			repair_request,
			work.first_artifact_id,
			work.second_artifact_id,
			work.assignment,
		)
	result = daily_blog.replication.review(
		(first, second), daily_blog.artifacts.RepoOutline, 1, build, parse,
		SalvageRunner(), daily_blog.agents.RouteBudget(4, 1), repair, salvage,
	)

	assert all(vote.winner_artifact_id == first.artifact_id for vote in result.votes)


#============================================
def test_review_propagates_non_repairable_parser_defect() -> None:
	"""A programming defect remains visible instead of becoming editorial repair."""
	source = packet()
	first, second = outline(source, "First"), outline(source, "Second")
	def build(
		left: daily_blog.artifacts.EditorialArtifact,
		right: daily_blog.artifacts.EditorialArtifact,
		assignment: daily_blog.replication.ReviewAssignment,
	) -> daily_blog.replication.ReviewWork:
		return daily_blog.replication.ReviewWork(
			request(f"defect-{assignment.reviewer_index}-{assignment.display_order}"),
			left.artifact_id,
			right.artifact_id,
			assignment,
		)
	def parse(_text: str, _work: daily_blog.replication.ReviewWork) -> str:
		raise RuntimeError("broken parser invariant")

	with pytest.raises(RuntimeError, match="broken parser invariant"):
		daily_blog.replication.review(
			(first, second), daily_blog.artifacts.RepoOutline, 1, build, parse, Runner(),
			daily_blog.agents.RouteBudget(2, 1),
		)


#============================================
def test_promote_preserves_incumbent_on_failed_review() -> None:
	"""An eligible incumbent survives a failed challenger review."""
	source = packet()
	first, second = outline(source, "First"), outline(source, "Second")
	def evaluate(
		value: daily_blog.artifacts.EditorialArtifact,
	) -> daily_blog.artifacts.EligibilityResult:
		return daily_blog.artifacts.evaluate_eligibility(value, (source,))
	failed = daily_blog.replication.ReviewVote(
		"r",
		first.artifact_id,
		second.artifact_id,
		"failed",
		"",
		"timeout",
	)
	preserved = daily_blog.replication.promote(
		(first, second), daily_blog.artifacts.RepoOutline, evaluate, (failed,), first,
	)

	assert isinstance(preserved, daily_blog.artifacts.PreservedArtifact)


#============================================
def test_promote_preserves_separate_incumbent_without_complete_direct_review() -> None:
	"""A missing challenger comparison cannot displace a separately held artifact."""
	source = packet()
	incumbent, challenger = outline(source, "Incumbent"), outline(source, "Challenger")
	def evaluate(
		value: daily_blog.artifacts.EditorialArtifact,
	) -> daily_blog.artifacts.EligibilityResult:
		return daily_blog.artifacts.evaluate_eligibility(value, (source,))
	failed = daily_blog.replication.ReviewVote(
		"review", incumbent.artifact_id, challenger.artifact_id,
		"failed", "", "invalid_verdict",
	)

	promotion = daily_blog.replication.promote(
		(challenger,), daily_blog.artifacts.RepoOutline, evaluate, (failed,), incumbent,
	)

	assert isinstance(promotion, daily_blog.artifacts.PreservedArtifact)


#============================================
def test_promote_replaces_incumbent_only_after_direct_challenger_improvement() -> None:
	"""A challenger wins only after a complete direct peer comparison favors it."""
	source = packet()
	incumbent, challenger = outline(source, "Incumbent"), outline(source, "Challenger")
	def evaluate(
		value: daily_blog.artifacts.EditorialArtifact,
	) -> daily_blog.artifacts.EligibilityResult:
		return daily_blog.artifacts.evaluate_eligibility(value, (source,))
	vote = daily_blog.replication.ReviewVote(
		"review", incumbent.artifact_id, challenger.artifact_id,
		"succeeded", challenger.artifact_id,
	)

	promotion = daily_blog.replication.promote(
		(challenger,), daily_blog.artifacts.RepoOutline, evaluate, (vote,), incumbent,
	)

	assert promotion.artifact == challenger


#============================================
def test_promote_uses_eligible_same_rung_recovery_when_reviews_are_unavailable() -> None:
	"""A review outage retains one eligible peer as explicitly degraded work."""
	source = packet()
	peer = outline(source, "Peer")
	def evaluate(
		value: daily_blog.artifacts.EditorialArtifact,
	) -> daily_blog.artifacts.EligibilityResult:
		return daily_blog.artifacts.evaluate_eligibility(value, (source,))

	promotion = daily_blog.replication.promote(
		(peer,), daily_blog.artifacts.RepoOutline, evaluate, (),
	)

	assert isinstance(promotion, daily_blog.artifacts.DegradedPromotion)


#============================================
def test_promote_rejects_wrong_rung_fallback() -> None:
	"""A recovery path cannot silently move to another editorial ladder rung."""
	source = packet()
	story = daily_blog.artifacts.RepoStory.create(
		source.report_date, (source,), "vosslab/project",
		f"Story <!-- evidence: {source.items[0].evidence_id} -->", (source.items[0].evidence_id,),
	)
	def evaluate(
		value: daily_blog.artifacts.EditorialArtifact,
	) -> daily_blog.artifacts.EligibilityResult:
		return daily_blog.artifacts.evaluate_eligibility(value, (source,))
	with pytest.raises(RuntimeError, match="wrong ladder rung"):
		daily_blog.replication.promote(
			(), daily_blog.artifacts.RepoOutline, evaluate, (), fallback=lambda: story,
		)

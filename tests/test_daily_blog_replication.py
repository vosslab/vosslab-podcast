"""Offline behavioral tests for stage-neutral editorial replication."""

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
		(request("strong"), request("broken")), Runner(), daily_blog.agents.RouteBudget(2),
		daily_blog.artifacts.RepoOutline, parse,
		lambda value: daily_blog.artifacts.evaluate_eligibility(value, (source,)),
	)

	assert result.eligible == (outline(source, "strong"),)
	assert result.candidates[1].failure == "timeout"


#============================================
def test_candidate_set_review_scales_with_reviewers_not_candidate_pairs() -> None:
	"""Five peers and three reviewers create three complete-set calls, never sixty."""
	source = packet()
	peers = tuple(outline(source, f"Candidate {index}") for index in range(5))
	seen_orders = []
	def build(
		ordered: tuple[daily_blog.artifacts.EditorialArtifact, ...],
		assignment: daily_blog.replication.CandidateSetReviewAssignment,
	) -> daily_blog.replication.CandidateSetReviewWork:
		seen_orders.append(tuple(item.artifact_id for item in ordered))
		return daily_blog.replication.CandidateSetReviewWork(
			request(f"set-review-{assignment.reviewer_index}"), assignment,
		)
	def parse(
		_text: str, work: daily_blog.replication.CandidateSetReviewWork,
	) -> str:
		return work.assignment.candidate_artifact_ids[0]
	result = daily_blog.replication.review_candidate_set(
		peers, daily_blog.artifacts.RepoOutline, 3, build, parse, Runner(),
		daily_blog.agents.RouteBudget(3),
	)

	assert len(result.work) == len(result.votes) == 3
	assert all(set(order) == {item.artifact_id for item in peers} for order in seen_orders)
	assert len(set(seen_orders)) == 3


#============================================
def test_candidate_set_votes_promote_one_plurality_winner() -> None:
	"""A bounded complete-set judgment can promote without pairwise reconstruction."""
	source = packet()
	peers = tuple(outline(source, f"Candidate {index}") for index in range(3))
	ids = tuple(item.artifact_id for item in peers)
	votes = tuple(
		daily_blog.replication.CandidateSetReviewVote(
			f"review-{index}", ids, "succeeded", peers[1].artifact_id,
		)
		for index in range(2)
	) + (
		daily_blog.replication.CandidateSetReviewVote(
			"review-2", ids, "succeeded", peers[0].artifact_id,
		),
	)

	result = daily_blog.replication.promote(
		peers, daily_blog.artifacts.RepoOutline,
		lambda item: daily_blog.artifacts.evaluate_eligibility(item, (source,)), votes,
	)

	assert isinstance(result, daily_blog.artifacts.DegradedPromotion)
	assert result.artifact is peers[1]
	assert result.reasons == ("review_disagreement",)


#============================================
def test_candidate_set_disagreement_preserves_incumbent() -> None:
	"""A tied optional complete-set review cannot remove the publishable incumbent."""
	source = packet()
	peers = tuple(outline(source, f"Candidate {index}") for index in range(3))
	ids = tuple(item.artifact_id for item in peers)
	votes = (
		daily_blog.replication.CandidateSetReviewVote(
			"review-0", ids, "succeeded", peers[1].artifact_id,
		),
		daily_blog.replication.CandidateSetReviewVote(
			"review-1", ids, "succeeded", peers[2].artifact_id,
		),
	)

	result = daily_blog.replication.promote(
		peers, daily_blog.artifacts.RepoOutline,
		lambda item: daily_blog.artifacts.evaluate_eligibility(item, (source,)), votes,
		peers[0],
	)

	assert isinstance(result, daily_blog.artifacts.PreservedArtifact)
	assert result.artifact is peers[0]


#============================================
def test_promote_preserves_incumbent_on_failed_review() -> None:
	"""An eligible incumbent survives a failed challenger review."""
	source = packet()
	first, second = outline(source, "First"), outline(source, "Second")
	def evaluate(
		value: daily_blog.artifacts.EditorialArtifact,
	) -> daily_blog.artifacts.EligibilityResult:
		return daily_blog.artifacts.evaluate_eligibility(value, (source,))
	failed = daily_blog.replication.CandidateSetReviewVote(
		"r", (first.artifact_id, second.artifact_id), "failed", "", "timeout",
	)
	preserved = daily_blog.replication.promote(
		(first, second), daily_blog.artifacts.RepoOutline, evaluate, (failed,), first,
	)

	assert isinstance(preserved, daily_blog.artifacts.PreservedArtifact)


#============================================
def test_promote_preserves_separate_incumbent_without_complete_direct_review() -> None:
	"""A failed complete-set judgment cannot displace a separate incumbent."""
	source = packet()
	incumbent, challenger = outline(source, "Incumbent"), outline(source, "Challenger")
	def evaluate(
		value: daily_blog.artifacts.EditorialArtifact,
	) -> daily_blog.artifacts.EligibilityResult:
		return daily_blog.artifacts.evaluate_eligibility(value, (source,))
	failed = daily_blog.replication.CandidateSetReviewVote(
		"review", (incumbent.artifact_id, challenger.artifact_id),
		"failed", "", "invalid_verdict",
	)

	promotion = daily_blog.replication.promote(
		(challenger,), daily_blog.artifacts.RepoOutline, evaluate, (failed,), incumbent,
	)

	assert isinstance(promotion, daily_blog.artifacts.PreservedArtifact)


#============================================
def test_promote_replaces_incumbent_only_after_complete_set_prefers_challenger() -> None:
	"""A challenger wins only after complete-set review favors it."""
	source = packet()
	incumbent, challenger = outline(source, "Incumbent"), outline(source, "Challenger")
	def evaluate(
		value: daily_blog.artifacts.EditorialArtifact,
	) -> daily_blog.artifacts.EligibilityResult:
		return daily_blog.artifacts.evaluate_eligibility(value, (source,))
	vote = daily_blog.replication.CandidateSetReviewVote(
		"review", (incumbent.artifact_id, challenger.artifact_id),
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

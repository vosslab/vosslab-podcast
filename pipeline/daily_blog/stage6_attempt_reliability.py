"""Advisory reliability summaries for Stage 6 editorial work."""

# Standard Library
import collections.abc

# local repo modules
import daily_blog.artifacts
import daily_blog.replication


#============================================
def _review_disagreements(
	votes: collections.abc.Iterable[daily_blog.replication.ReviewVote],
) -> int:
	"""Count candidate-pair conflicts without retaining reviewer prose."""
	pairs: dict[tuple[str, str], set[str]] = {}
	for vote in votes:
		if vote.status == "succeeded":
			pair = tuple(sorted((vote.first_artifact_id, vote.second_artifact_id)))
			pairs.setdefault(pair, set()).add(vote.winner_artifact_id)
	return sum(len(winners) > 1 for winners in pairs.values())


#============================================
def review_reliability(
	review: daily_blog.replication.ReviewResult,
	promotion: object,
	reasons: collections.abc.Iterable[str] = (),
) -> daily_blog.replication.StepReliability:
	"""Summarize actual review routes, repairs, and pair disagreements."""
	votes = review.votes
	disagreements = _review_disagreements(votes)
	all_reasons = set(reasons) | set(
		daily_blog.replication.review_reasons(votes, disagreements)
	)
	best = (
		"" if isinstance(promotion, daily_blog.artifacts.NoArtifact)
		else promotion.artifact.artifact_id
	)
	return daily_blog.replication.StepReliability(
		"6.3", "degraded" if all_reasons else "succeeded", len(votes),
		sum(item.status == "succeeded" for item in votes),
		sum(item.status == "failed" for item in votes), 0,
		sum(item.repaired and item.status == "succeeded" for item in votes),
		disagreements, best, tuple(sorted(all_reasons)),
	)


#============================================
def promotion_reliability(
	promotion: object,
	votes: collections.abc.Iterable[daily_blog.replication.ReviewVote],
) -> daily_blog.replication.StepReliability:
	"""Record deterministic selection separately from route observations."""
	if isinstance(promotion, daily_blog.artifacts.NoArtifact):
		reasons, best = (promotion.reason,), ""
	elif isinstance(promotion, daily_blog.artifacts.DegradedPromotion):
		reasons, best = promotion.reasons, promotion.artifact.artifact_id
	else:
		reasons, best = (), promotion.artifact.artifact_id
	return daily_blog.replication.StepReliability(
		"6.4", "degraded" if reasons else "succeeded", 1, 1, 0, 0, 0,
		_review_disagreements(votes), best, tuple(sorted(reasons)),
	)

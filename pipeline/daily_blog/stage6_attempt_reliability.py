"""Advisory reliability summaries for Stage 6 editorial work."""

# Standard Library
import collections.abc

# local repo modules
import daily_blog.artifacts
import daily_blog.replication


#============================================
def _review_disagreements(
	votes: collections.abc.Iterable[daily_blog.replication.CandidateSetReviewVote],
) -> int:
	"""Count complete-set conflicts without retaining reviewer prose."""
	return daily_blog.replication.review_disagreements(votes)


#============================================
def review_reliability(
	review: daily_blog.replication.CandidateSetReviewResult,
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
		0,
		disagreements, best, tuple(sorted(all_reasons)),
	)


#============================================
def promotion_reliability(
	promotion: object,
	votes: collections.abc.Iterable[daily_blog.replication.CandidateSetReviewVote],
) -> daily_blog.replication.StepReliability:
	"""Record deterministic selection separately from route observations."""
	if isinstance(promotion, daily_blog.artifacts.NoArtifact):
		reasons, best, succeeded = (promotion.reason,), "", 0
	elif isinstance(promotion, daily_blog.artifacts.DegradedPromotion):
		reasons, best, succeeded = promotion.reasons, promotion.artifact.artifact_id, 1
	else:
		reasons, best, succeeded = (), promotion.artifact.artifact_id, 1
	return daily_blog.replication.StepReliability(
		"6.4", "degraded" if reasons else "succeeded", 1, succeeded, 1 - succeeded, 0, 0,
		_review_disagreements(votes), best, tuple(sorted(reasons)),
	)

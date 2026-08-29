"""Deterministic acceptance rules for daily-blog prompt experiments."""

# local repo modules
import daily_blog.rubric_calibration


ACCEPTANCE_SCHEMA = "vosslab.daily-blog.prompt-experiment-acceptance.v3"


#============================================
def aggregate_comparisons(comparisons: list[dict[str, object]]) -> dict[str, object]:
	"""Summarize canonical referee results for one stable arm pair."""
	counts = {
		name: sum(item["verdict"] == name for item in comparisons)
		for name in ("A", "B", "NONE", "ERROR")
	}
	non_error = len(comparisons) - counts["ERROR"]
	stability = max(counts["A"], counts["B"], counts["NONE"]) / non_error if non_error else 0.0
	order_counts = {
		order: sum(item.get("order") == order for item in comparisons)
		for order in ("AB", "BA")
	}
	result = {
		"count": len(comparisons),
		"counts": counts,
		"order_counts": order_counts,
		"stability": stability,
	}
	return result


#============================================
def _scorecard_aggregate(
	records: list[dict[str, object]],
	fixture: str,
	arm: str,
	repetitions: int,
) -> dict[str, object]:
	"""Aggregate one arm's complete generated-post scorecards for one fixture."""
	matching = [
		record
		for record in records
		if record.get("fixture") == fixture and record.get("arm") == arm
	]
	scorecards = [record.get("scorecard") for record in matching]
	fields = tuple(
		value[0]
		for value in daily_blog.rubric_calibration.CALIBRATION_CONTRACT.expected_criteria
	)
	complete = len(matching) == repetitions and all(
		isinstance(scorecard, dict)
		and scorecard.get("status") == "scored"
		and isinstance(scorecard.get("scores"), dict)
		and set(scorecard["scores"]) == set(fields)
		and type(scorecard.get("weighted_score")) in {int, float}
		for scorecard in scorecards
	)
	if not complete:
		result = {"status": "incomplete", "scored_runs": 0}
		return result
	weighted_scores = [float(scorecard["weighted_score"]) for scorecard in scorecards]
	criterion_means = {
		field: sum(float(scorecard["scores"][field]) for scorecard in scorecards)
		/ repetitions
		for field in fields
	}
	result = {
		"status": "complete",
		"scored_runs": len(scorecards),
		"weighted_scores": weighted_scores,
		"minimum_weighted_score": min(weighted_scores),
		"mean_weighted_score": sum(weighted_scores) / repetitions,
		"criterion_means": criterion_means,
	}
	return result


#============================================
def _comparison_acceptance(
	comparisons: list[dict[str, object]],
	fixture: str,
	arm: str,
	repetitions: int,
) -> dict[str, object]:
	"""Require v4 to win every repeated comparison in both displayed positions."""
	pair = "v3:" + arm
	matching = [
		item
		for item in comparisons
		if item.get("fixture") == fixture and item.get("pair") == pair
	]
	aggregate = aggregate_comparisons(matching)
	expected_keys = {
		(repetition, order)
		for repetition in range(repetitions)
		for order in ("AB", "BA")
	}
	actual_keys = {
		(item.get("repetition"), item.get("order"))
		for item in matching
	}
	expected_count = repetitions * 2
	complete = (
		len(matching) == expected_count
		and actual_keys == expected_keys
		and all(item.get("parsed") is True for item in matching)
	)
	v4_wins = complete and aggregate["counts"]["B"] == expected_count
	stable = complete and aggregate["stability"] == 1.0
	position_invariant = complete and all(
		all(item.get("verdict") == "B" for item in matching if item.get("order") == order)
		for order in ("AB", "BA")
	)
	result = {
		"status": "complete" if complete else "incomplete",
		"pair": pair,
		"aggregate": aggregate,
		"counterbalanced": complete,
		"all_verdicts_choose_v4": v4_wins,
		"stable": stable,
		"position_invariant": position_invariant,
	}
	return result


#============================================
def _fixture_arm_acceptance(
	records: list[dict[str, object]],
	comparisons: list[dict[str, object]],
	fixture: str,
	arm: str,
	repetitions: int,
	reference_floor: float,
) -> dict[str, object]:
	"""Evaluate every generated-prose gate for one v4 arm on one fixture."""
	baseline = _scorecard_aggregate(records, fixture, "v3", repetitions)
	candidate = _scorecard_aggregate(records, fixture, arm, repetitions)
	comparison = _comparison_acceptance(comparisons, fixture, arm, repetitions)
	if (
		baseline["status"] != "complete"
		or candidate["status"] != "complete"
		or comparison["status"] != "complete"
	):
		result = {
			"status": "incomplete",
			"baseline": baseline,
			"candidate": candidate,
			"comparison": comparison,
		}
		return result
	baseline_means = baseline["criterion_means"]
	candidate_means = candidate["criterion_means"]
	criteria_not_regressed = all(
		candidate_means[field] >= baseline_means[field]
		for field in baseline_means
	)
	weighted_margin = candidate["mean_weighted_score"] - baseline["mean_weighted_score"]
	reference_margin = candidate["minimum_weighted_score"] - reference_floor
	checks = {
		"mean_weighted_score_strictly_beats_v3": weighted_margin > 0,
		"no_maker_criterion_regresses": criteria_not_regressed,
		"every_generated_sample_exceeds_reference_floor": reference_margin > 0,
		"all_repeated_pairwise_verdicts_choose_v4": comparison["all_verdicts_choose_v4"],
		"pairwise_verdict_is_stable": comparison["stable"],
		"pairwise_verdict_is_position_invariant": comparison["position_invariant"],
	}
	result = {
		"status": "pass" if all(checks.values()) else "fail",
		"baseline": baseline,
		"candidate": candidate,
		"comparison": comparison,
		"checks": checks,
		"weighted_margin_over_v3": weighted_margin,
		"minimum_margin_over_references": reference_margin,
	}
	return result


#============================================
def _arm_rank(
	arm: str,
	arm_results: dict[str, dict[str, object]],
	arms: tuple[str, ...],
) -> tuple[float, float, int]:
	"""Rank a passing arm by its weakest fixture before its declared order."""
	fixtures = arm_results[arm]["fixtures"]
	if not isinstance(fixtures, dict):
		raise RuntimeError("Prompt experiment acceptance fixtures are invalid.")
	fixture_results = list(fixtures.values())
	minimum_score = min(
		float(result["candidate"]["minimum_weighted_score"])
		for result in fixture_results
	)
	minimum_margin = min(
		float(result["weighted_margin_over_v3"])
		for result in fixture_results
	)
	rank = (minimum_score, minimum_margin, -arms.index(arm))
	return rank


#============================================
def build_acceptance_result(
	records: list[dict[str, object]],
	comparisons: list[dict[str, object]],
	repetitions: int,
	calibration: daily_blog.rubric_calibration.CalibrationEvidence,
	arms: tuple[str, ...],
) -> dict[str, object]:
	"""Select one review-ready v4 arm only after every deterministic prose gate passes."""
	v4_arms = tuple(arm for arm in arms if arm != "v3")
	arm_results = {
		arm: {
			"fixtures": {
				fixture: _fixture_arm_acceptance(
					records,
					comparisons,
					fixture,
					arm,
					repetitions,
					calibration.reference_floor,
				)
				for fixture in ("busy", "quiet")
			}
		}
		for arm in v4_arms
	}
	for result in arm_results.values():
		statuses = [value["status"] for value in result["fixtures"].values()]
		result["status"] = (
			"pass"
			if all(status == "pass" for status in statuses)
			else "incomplete"
			if any(status == "incomplete" for status in statuses)
			else "fail"
		)
	passing = [arm for arm in v4_arms if arm_results[arm]["status"] == "pass"]
	selected_arm = None
	if passing:
		# The least-successful fixture ranks first, so every fixture remains consequential.
		selected_arm = passing[0]
		for arm in passing[1:]:
			if _arm_rank(arm, arm_results, arms) > _arm_rank(selected_arm, arm_results, arms):
				selected_arm = arm
	all_complete = all(result["status"] != "incomplete" for result in arm_results.values())
	status = "pass" if selected_arm else "fail" if all_complete else "incomplete"
	result = {
		"schema_version": ACCEPTANCE_SCHEMA,
		"status": status,
		"review_ready": status == "pass",
		"selected_arm": selected_arm,
		"baseline_arm": "v3",
		"fixtures": ["busy", "quiet"],
		"repetitions": repetitions,
		"calibration": calibration.to_dict(),
		"requirements": {
			"reference_comparison": "strictly above both positive-passable references",
			"v3_comparison": "higher weighted score with no maker criterion regression",
			"stability": "every repeated pairwise verdict chooses v4",
			"activation": "the configured independent artifact reviews must accept both complete posts",
		},
		"arms": arm_results,
	}
	return result

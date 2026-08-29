"""Fail-closed historical calibration for the unactivated daily maker rubric."""

# Standard Library
import dataclasses
import datetime
import json
import re
import shutil
import subprocess
import uuid

# local repo modules
import daily_blog.config
import daily_blog.routes
import daily_blog.io_utils
import daily_blog.candidates
import daily_blog.evaluation
import daily_blog.prompt_resources
import daily_blog.private_artifacts


CALIBRATION_SCHEMA_VERSION = "vosslab.daily-blog.rubric-calibration.v3"
CALIBRATION_ROOT_NAME = "daily_blog_rubric_calibrations"
CALIBRATION_DATES = (
	"2026-08-22",
	"2026-08-23",
	"2026-08-24",
	"2026-08-25",
	"2026-08-26",
)
MAX_POST_BYTES = 250_000
MAX_ARTIFACT_BYTES = 2_000_000
MAX_RESPONSE_CHARS = 12_000
MAX_PASSAGE_CHARS = 400
MAX_CRITERION_REASON_CHARS = 600
MAX_OVERALL_REASON_CHARS = 1_000
DEFAULT_REPETITIONS = 3
MIN_REPETITIONS = 2
MAX_REPETITIONS = 5
DEFAULT_MAXIMUM_CRITERION_SCORE_SPAN = 1
DEFAULT_MINIMUM_AGGREGATE_BAND_SEPARATION = 0.25
CALIBRATION_ID_RE = re.compile(
	r"^rubric-calibration-(?:preparation-)?[a-z0-9][a-z0-9-]{0,95}$"
)
CALIBRATION_RESOURCE_NAMES = frozenset(
	{
		"daily_blog_rubric_v4.md",
		"daily_blog_rubric_calibrator_repair_v4.txt",
		"daily_blog_rubric_calibrator_v4.txt",
	}
)
RUBRIC_HEADING_RE = re.compile(r"^##\s+(.+?)\s+\((\d+)%\)\s*$", re.MULTILINE)


class CalibrationBlockedError(RuntimeError):
	"""A calibration boundary rejected the requested external evaluation."""


@dataclasses.dataclass(frozen=True)
class RubricCriterion:
	"""One exact rubric criterion and its deterministic weighting."""

	field: str
	title: str
	weight: int


@dataclasses.dataclass(frozen=True)
class HistoricalPost:
	"""One fixed historical post retained in memory for calibration only."""

	report_date: str
	text: str
	sha256: str
	byte_count: int
	profile: dict


@dataclasses.dataclass(frozen=True)
class RubricCalibrationContract:
	"""One immutable calibration-resource and score-schema declaration."""

	name: str
	version: str
	rubric_name: str
	rubric_sha256: str
	template_name: str
	template_sha256: str
	repair_template_name: str
	repair_template_sha256: str
	expected_criteria: tuple[tuple[str, str, int], ...]


@dataclasses.dataclass(frozen=True)
class CalibrationProcedure:
	"""One bounded, artifact-recorded diagnostic procedure for a live run."""

	repetitions: int
	maximum_criterion_score_span: int
	minimum_positive_negative_mean_separation: float

	#============================================
	def __post_init__(self) -> None:
		"""Reject procedure settings that could create invalid or unbounded route work."""
		if (
			type(self.repetitions) is not int
			or not MIN_REPETITIONS <= self.repetitions <= MAX_REPETITIONS
		):
			raise RuntimeError("Rubric calibration repetitions are outside the bounded range.")
		if (
			type(self.maximum_criterion_score_span) is not int
			or not 0 <= self.maximum_criterion_score_span <= 3
		):
			raise RuntimeError("Rubric calibration score-span tolerance is invalid.")
		if (
			type(self.minimum_positive_negative_mean_separation) is not float
			or not 0.0 <= self.minimum_positive_negative_mean_separation <= 3.0
		):
			raise RuntimeError("Rubric calibration separation threshold is invalid.")

	#============================================
	def to_dict(self) -> dict[str, int | float]:
		"""Return the procedure values embedded in preparation and live evidence."""
		return dataclasses.asdict(self)


CALIBRATION_CONTRACT = RubricCalibrationContract(
	name="daily-maker-rubric-historical-calibration",
	version="v2",
	rubric_name="daily_blog_rubric_v4.md",
	rubric_sha256="5a4562d9a995320f9b74c4dc69a58985bdc50dd37761c5c8563a0536c5ad3cad",
	template_name="daily_blog_rubric_calibrator_v4.txt",
	template_sha256="2679776c5b49711427ecaa54775c419874bc112c4103082be97699d7c951dafd",
	repair_template_name="daily_blog_rubric_calibrator_repair_v4.txt",
	repair_template_sha256="00fdd53dd7f17043daf42882c7133bbd5dead46a26c655f16b4b17b56494c3ba",
	expected_criteria=(
		("maker_substance", "Maker substance", 25),
		("author_presence_and_curiosity", "Author presence and curiosity", 20),
		("insight_and_selectivity", "Insight and selectivity", 20),
		("concrete_technical_grounding", "Concrete technical grounding", 15),
		("narrative_and_readability", "Narrative and readability", 10),
		(
			"intellectual_honesty_and_unfinished_edges",
			"Intellectual honesty and unfinished edges",
			10,
		),
	),
)


@dataclasses.dataclass(frozen=True)
class CalibrationEvidence:
	"""Verified passing historical score evidence consumed by the prompt experiment."""

	calibration_id: str
	preparation_id: str
	report_sha256: str
	rubric_sha256: str
	reference_scores: tuple[tuple[str, float], ...]
	reference_floor: float

	#============================================
	def __post_init__(self) -> None:
		"""Fail closed when an in-memory activation input is structurally inconsistent."""
		positive_dates = tuple(target_contract()["positive_passable"]["dates"])
		actual_dates = tuple(value[0] for value in self.reference_scores)
		digests = (self.preparation_id, self.report_sha256, self.rubric_sha256)
		if not CALIBRATION_ID_RE.fullmatch(self.calibration_id):
			raise RuntimeError("Calibration evidence ID is invalid.")
		if any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in digests):
			raise RuntimeError("Calibration evidence digest is invalid.")
		if actual_dates != positive_dates:
			raise RuntimeError("Calibration evidence reference dates are invalid.")
		if any(type(score) is not float or not 1.0 <= score <= 4.0 for _date, score in self.reference_scores):
			raise RuntimeError("Calibration evidence reference scores are invalid.")
		if type(self.reference_floor) is not float or self.reference_floor != max(
			score for _date, score in self.reference_scores
		):
			raise RuntimeError("Calibration evidence reference floor is inconsistent.")

	#============================================
	def to_dict(self) -> dict:
		"""Return the bounded activation evidence recorded in experiment artifacts."""
		return {
			"calibration_id": self.calibration_id,
			"preparation_id": self.preparation_id,
			"report_sha256": self.report_sha256,
			"rubric_sha256": self.rubric_sha256,
			"reference_scores": dict(self.reference_scores),
			"reference_floor_exclusive": self.reference_floor,
		}


import daily_blog.rubric_calibration_artifacts
from daily_blog.rubric_calibration_artifacts import (
	install_calibration_artifacts,
	load_historical_posts,
)

load_live_calibration_evidence = (
	daily_blog.rubric_calibration_artifacts.load_live_calibration_evidence
)
load_calibration_evidence = (
	daily_blog.rubric_calibration_artifacts.load_calibration_evidence
)
load_fixture_calibration_evidence = (
	daily_blog.rubric_calibration_artifacts.load_fixture_calibration_evidence
)
run_fixture_calibration = daily_blog.rubric_calibration_artifacts.run_fixture_calibration


#============================================
def parse_rubric_criteria(rubric: str) -> tuple[RubricCriterion, ...]:
	"""Derive the exact score fields and weights from the versioned maker rubric."""
	values = []
	for title, weight_text in RUBRIC_HEADING_RE.findall(rubric):
		field = re.sub(r"[^a-z0-9]+", "_", title.casefold()).strip("_")
		values.append((field, title, int(weight_text)))
	if (
		tuple(values) != CALIBRATION_CONTRACT.expected_criteria
		or sum(value[2] for value in values) != 100
	):
		raise RuntimeError("Maker rubric criteria or weights do not match calibration v2.")
	criteria = tuple(RubricCriterion(*value) for value in values)
	return criteria


#============================================
def calibration_resources() -> tuple[str, str, tuple[RubricCriterion, ...]]:
	"""Load the exact v4 rubric and calibrator prompt resources."""
	rubric = daily_blog.prompt_resources.load_allowlisted_instruction_prompt(
		CALIBRATION_CONTRACT.rubric_name,
		CALIBRATION_RESOURCE_NAMES,
		"rubric calibration",
	)
	criteria = parse_rubric_criteria(rubric)
	template = daily_blog.prompt_resources.load_allowlisted_instruction_prompt(
		CALIBRATION_CONTRACT.template_name,
		CALIBRATION_RESOURCE_NAMES,
		"rubric calibration",
	)
	repair = daily_blog.prompt_resources.load_allowlisted_instruction_prompt(
		CALIBRATION_CONTRACT.repair_template_name,
		CALIBRATION_RESOURCE_NAMES,
		"rubric calibration",
	)
	resource_hashes = (
		(daily_blog.io_utils.sha256_text(rubric), CALIBRATION_CONTRACT.rubric_sha256),
		(daily_blog.io_utils.sha256_text(template), CALIBRATION_CONTRACT.template_sha256),
		(daily_blog.io_utils.sha256_text(repair), CALIBRATION_CONTRACT.repair_template_sha256),
	)
	if any(actual != expected for actual, expected in resource_hashes):
		raise RuntimeError("Maker rubric calibration resource identity changed.")
	return rubric, template, criteria


#============================================
def _criterion_contract(criteria: tuple[RubricCriterion, ...]) -> str:
	"""Render the ordered JSON field allowlist supplied to calibrator prompts."""
	lines = [f"- `{criterion.field}` ({criterion.weight}%)" for criterion in criteria]
	return "\n".join(lines)


#============================================
def render_calibration_prompt(post: str, limit: int) -> tuple[str, tuple[RubricCriterion, ...]]:
	"""Render one bounded single-post scorecard prompt from registered resources."""
	rubric, template, criteria = calibration_resources()
	prompt = template.format(
		rubric=rubric,
		post=post,
		criterion_contract=_criterion_contract(criteria),
	)
	if len(prompt) > limit:
		raise RuntimeError("Rubric calibration prompt exceeds its configured referee budget.")
	return prompt, criteria


#============================================
def _bounded_text(value: object, label: str, limit: int) -> str:
	"""Require one concise structured-response string."""
	if not isinstance(value, str):
		raise RuntimeError(f"Rubric calibration {label} must be text.")
	text = value.strip()
	if not text or len(text) > limit:
		raise RuntimeError(f"Rubric calibration {label} is empty or too long.")
	return text


#============================================
def parse_calibration_result(
	response: str,
	criteria: tuple[RubricCriterion, ...],
	post: str,
) -> dict:
	"""Parse one passage-grounded scorecard and compute its weighted score.

	Args:
		response: Bounded JSON text returned by the referee route.
		criteria: Ordered contract-owned score fields and weights.
		post: Complete reviewed post used to verify every exact cited passage.

	Returns:
		Validated per-field scores, evidence, reason, and deterministic weighted score.

	Raises:
		RuntimeError: The response shape, score, or text bounds are invalid.
		json.JSONDecodeError: The response is not JSON.
	"""
	if not isinstance(response, str) or len(response) > MAX_RESPONSE_CHARS:
		raise RuntimeError("Rubric calibration response exceeds its structured budget.")
	value = daily_blog.rubric_calibration_artifacts.strict_json_loads(response.strip())
	if not isinstance(value, dict) or set(value) != {"scores", "overall_reason"}:
		raise RuntimeError("Rubric calibration result fields are invalid.")
	scores_value = value["scores"]
	if not isinstance(scores_value, dict) or set(scores_value) != {
		criterion.field for criterion in criteria
	}:
		raise RuntimeError("Rubric calibration score fields are invalid.")
	scores = {}
	passages = {}
	reasons = {}
	weighted = 0
	for criterion in criteria:
		entry = scores_value[criterion.field]
		if not isinstance(entry, dict) or set(entry) != {"score", "passage", "reason"}:
			raise RuntimeError("Rubric calibration criterion result fields are invalid.")
		score = entry["score"]
		if type(score) is not int or not 1 <= score <= 4:
			raise RuntimeError("Rubric calibration criterion score must be an integer from 1 through 4.")
		scores[criterion.field] = score
		passage = _bounded_text(
			entry["passage"],
			criterion.field + " passage",
			MAX_PASSAGE_CHARS,
		)
		# ASVS 2.2.1: a claimed grounding anchor must be an exact substring of the
		# fixed post rather than an unverified model-authored paraphrase.
		if passage not in post:
			raise RuntimeError("Rubric calibration passage is not present in the reviewed post.")
		passages[criterion.field] = passage
		reasons[criterion.field] = _bounded_text(
			entry["reason"],
			criterion.field + " reason",
			MAX_CRITERION_REASON_CHARS,
		)
		weighted += score * criterion.weight
	result = {
		"scores": scores,
		"passages": passages,
		"reasons": reasons,
		"weighted_score": weighted / 100,
		"overall_reason": _bounded_text(
			value["overall_reason"],
			"overall reason",
			MAX_OVERALL_REASON_CHARS,
		),
	}
	return result


#============================================
def scored_result_is_grounded(
	value: object,
	criteria: tuple[RubricCriterion, ...],
	post: str,
) -> bool:
	"""Return whether one scored result is complete and grounded in its reviewed post."""
	if not isinstance(value, dict) or value.get("status") != "scored":
		return False
	fields = {criterion.field for criterion in criteria}
	scores = value.get("scores")
	passages = value.get("passages")
	reasons = value.get("reasons")
	if (
		not isinstance(scores, dict) or set(scores) != fields
		or not isinstance(passages, dict) or set(passages) != fields
		or not isinstance(reasons, dict) or set(reasons) != fields
		or any(type(score) is not int or not 1 <= score <= 4 for score in scores.values())
		or any(
			not isinstance(passage, str)
			or not passage
			or len(passage) > MAX_PASSAGE_CHARS
			or passage not in post
			for passage in passages.values()
		)
		or any(
			not isinstance(reason, str)
			or not reason
			or len(reason) > MAX_CRITERION_REASON_CHARS
			for reason in reasons.values()
		)
		or not isinstance(value.get("overall_reason"), str)
		or not value["overall_reason"]
		or len(value["overall_reason"]) > MAX_OVERALL_REASON_CHARS
	):
		return False
	weighted = sum(scores[criterion.field] * criterion.weight for criterion in criteria) / 100
	return type(value.get("weighted_score")) in {int, float} and value["weighted_score"] == weighted


#============================================
def _safe_route_failure(stage: str, error: BaseException) -> dict:
	"""Return route diagnostics without retaining exception text, prompts, or paths."""
	# ASVS 13.4 and 16.5.1: persist a stable class code instead of external stderr.
	return {"stage": stage, "code": type(error).__name__}


#============================================
def _run_route(
	runner: object,
	route: daily_blog.config.RoleRoute,
	prompt: str,
	repository: str,
) -> str:
	"""Invoke one structurally validated route runner and require text output."""
	method = getattr(runner, "run", None)
	if not callable(method):
		raise RuntimeError("Rubric calibration runner does not implement its route contract.")
	response = method(route, prompt, repository)
	if not isinstance(response, str):
		raise RuntimeError("Rubric calibration route response must be text.")
	return response


#============================================
def score_maker_post(
	post: str,
	config: daily_blog.config.DailyBlogConfig,
	runner: object,
	diagnostic_scope: str,
) -> dict:
	"""Run one maker post through the exact rubric with one bounded repair.

	Args:
		post: Complete maker post retained in memory for the route call.
		config: Referee route, prompt limit, and repository context.
		runner: Structurally validated route implementation.
		diagnostic_scope: Allowlisted owner of stable persisted diagnostic stages.

	Returns:
		A scored record or one redacted error diagnostic.

	Raises:
		RuntimeError: The caller supplies an unowned diagnostic scope.
	"""
	# ASVS 2.2.1 and 15.3.5: only fixed internal owners may shape persisted stages.
	if diagnostic_scope not in {"historical_calibration", "prompt_experiment"}:
		raise RuntimeError("Maker rubric diagnostic scope is invalid.")
	prompt, criteria = render_calibration_prompt(
		post,
		config.prompt_limits["referee_chars"],
	)
	try:
		response = _run_route(
			runner,
			config.referee_route,
			prompt,
			config.daily_blog_repository,
		)
	except (OSError, RuntimeError, subprocess.SubprocessError) as error:
		return {
			"status": "error",
			"diagnostic": _safe_route_failure(diagnostic_scope + "_route", error),
		}
	try:
		result = parse_calibration_result(response, criteria, post)
	except (json.JSONDecodeError, RuntimeError, ValueError):
		_repair = daily_blog.prompt_resources.load_allowlisted_instruction_prompt(
			CALIBRATION_CONTRACT.repair_template_name,
			CALIBRATION_RESOURCE_NAMES,
			"rubric calibration",
		)
		repair_prompt = _repair.format(
			criterion_contract=_criterion_contract(criteria),
			post=post,
			response=response[:MAX_RESPONSE_CHARS],
		)
		if len(repair_prompt) > config.prompt_limits["referee_chars"]:
			return {
				"status": "error",
				"diagnostic": {
					"stage": diagnostic_scope + "_repair_prompt",
					"code": "prompt_limit",
				},
			}
		try:
			repaired = _run_route(
				runner,
				config.referee_route,
				repair_prompt,
				config.daily_blog_repository,
			)
		except (OSError, RuntimeError, subprocess.SubprocessError) as error:
			return {
				"status": "error",
				"diagnostic": _safe_route_failure(
					diagnostic_scope + "_repair_route",
					error,
				),
			}
		try:
			result = parse_calibration_result(repaired, criteria, post)
		except (json.JSONDecodeError, RuntimeError, ValueError) as error:
			return {
				"status": "error",
				"diagnostic": _safe_route_failure(
					diagnostic_scope + "_response_parse",
					error,
				),
			}
	return {"status": "scored", **result}


#============================================
def _date_target(report_date: str, weighted_score: float) -> bool | None:
	"""Apply the plan's operational interpretation of each historical target band."""
	if report_date in {"2026-08-22", "2026-08-23"}:
		return 2.5 <= weighted_score < 3.5
	if report_date in {"2026-08-24", "2026-08-25"}:
		return 1.0 <= weighted_score <= 2.25
	return None


#============================================
def calibration_procedure(
	*,
	repetitions: int = DEFAULT_REPETITIONS,
	maximum_criterion_score_span: int = DEFAULT_MAXIMUM_CRITERION_SCORE_SPAN,
	minimum_positive_negative_mean_separation: float = (
		DEFAULT_MINIMUM_AGGREGATE_BAND_SEPARATION
	),
) -> CalibrationProcedure:
	"""Build one validated experimental procedure from operator-configurable settings."""
	return CalibrationProcedure(
		repetitions,
		maximum_criterion_score_span,
		minimum_positive_negative_mean_separation,
	)


#============================================
def procedure_from_target_contract(value: object) -> CalibrationProcedure:
	"""Recover the procedure recorded by one sealed calibration target contract."""
	if not isinstance(value, dict):
		raise RuntimeError("Rubric calibration target contract is invalid.")
	try:
		procedure = CalibrationProcedure(
			value["diagnostic_repetitions"],
			value["maximum_criterion_score_span"],
			value["minimum_positive_negative_mean_separation"],
		)
	except KeyError as error:
		raise RuntimeError("Rubric calibration procedure is incomplete.") from error
	return procedure


#============================================
def target_contract(procedure: CalibrationProcedure | None = None) -> dict:
	"""Return historical bands plus this run's recorded diagnostic procedure."""
	procedure = procedure or calibration_procedure()
	return {
		"positive_passable": {
			"dates": ["2026-08-22", "2026-08-23"],
			"minimum_inclusive": 2.5,
			"maximum_exclusive": 3.5,
		},
		"negative": {
			"dates": ["2026-08-24", "2026-08-25"],
			"minimum_inclusive": 1.0,
			"maximum_inclusive": 2.25,
		},
		"baseline_only": {"dates": ["2026-08-26"]},
		"diagnostic_repetitions": procedure.repetitions,
		"passage_grounding": "exact_post_substring_per_criterion_per_run",
		"maximum_criterion_score_span": procedure.maximum_criterion_score_span,
		"minimum_positive_negative_mean_separation": (
			procedure.minimum_positive_negative_mean_separation
		),
		"band_four_begins_at": 3.5,
	}


#============================================
def aggregate_calibration(
	records: list[dict],
	criteria: tuple[RubricCriterion, ...],
	posts: tuple[HistoricalPost, ...],
	procedure: CalibrationProcedure,
) -> dict:
	"""Summarize grounded repeated-run consistency, separation, and target bands.

	Args:
		records: Every attempted scorecard with its fixed report date.
		criteria: Ordered contract-owned score fields.
		posts: Fixed posts that every reported passage must quote exactly.
		procedure: Bounded repetition count and diagnostic tolerances recorded by this run.

	Returns:
		Per-date observations and the deterministic pass, fail, or incomplete status.
	"""
	expected_count = len(CALIBRATION_DATES) * procedure.repetitions
	post_by_date = {post.report_date: post for post in posts}
	matrix_complete = (
		set(post_by_date) == set(CALIBRATION_DATES)
		and len(records) == expected_count
		and all(
			{
				record.get("repetition")
				for record in records
				if record.get("report_date") == report_date
			} == set(range(procedure.repetitions))
			for report_date in CALIBRATION_DATES
		)
	)
	complete = matrix_complete and all(record.get("status") == "scored" for record in records)
	dates: dict[str, dict[str, object]] = {}
	grounding_results = []
	consistency_results = []
	target_results = []
	band_four_results = []
	mean_by_date: dict[str, float] = {}
	for report_date in CALIBRATION_DATES:
		date_records = [
			record for record in records
			if record.get("report_date") == report_date and record.get("status") == "scored"
		]
		post = post_by_date.get(report_date)
		grounded_records = [
			record for record in date_records
			if post is not None
			and record.get("post_sha256") == post.sha256
			and scored_result_is_grounded(record, criteria, post.text)
		]
		criterion_values = {
			criterion.field: [record["scores"][criterion.field] for record in grounded_records]
			for criterion in criteria
		}
		weighted_values = [record["weighted_score"] for record in grounded_records]
		mean_weighted = (
			sum(weighted_values) / len(weighted_values) if weighted_values else None
		)
		if mean_weighted is not None:
			mean_by_date[report_date] = mean_weighted
		criterion_spans = {
			field: max(values) - min(values) if values else None
			for field, values in criterion_values.items()
		}
		passage_grounded = len(grounded_records) == procedure.repetitions
		qualitative_consistency = passage_grounded and all(
			span is not None and span <= procedure.maximum_criterion_score_span
			for span in criterion_spans.values()
		)
		target_met = (
			_date_target(report_date, mean_weighted)
			if mean_weighted is not None
			else None
		)
		grounding_results.append(passage_grounded)
		consistency_results.append(qualitative_consistency)
		target_results.append(target_met)
		band_four_results.append(
			mean_weighted is not None and mean_weighted < 3.5
		)
		dates[report_date] = {
			"scored_runs": len(date_records),
			"grounded_runs": len(grounded_records),
			"criterion_scores": criterion_values,
			"criterion_score_spans": criterion_spans,
			"weighted_scores": weighted_values,
			"weighted_score_span": (
				max(weighted_values) - min(weighted_values) if weighted_values else None
			),
			"mean_weighted_score": mean_weighted,
			"passage_grounded": passage_grounded,
			"qualitative_consistency": qualitative_consistency,
			"target_met": target_met,
		}
	passage_grounded = complete and all(grounding_results)
	qualitative_consistency = passage_grounded and all(consistency_results)
	targets_met = passage_grounded and all(value is not False for value in target_results)
	band_four_unclaimed = complete and all(band_four_results)
	positive_dates = target_contract(procedure)["positive_passable"]["dates"]
	negative_dates = target_contract(procedure)["negative"]["dates"]
	band_separation = None
	if all(report_date in mean_by_date for report_date in positive_dates + negative_dates):
		positive_mean = sum(mean_by_date[date] for date in positive_dates) / len(positive_dates)
		negative_mean = sum(mean_by_date[date] for date in negative_dates) / len(negative_dates)
		band_separation = positive_mean - negative_mean
	band_separation_met = (
		passage_grounded
		and band_separation is not None
		and band_separation >= procedure.minimum_positive_negative_mean_separation
	)
	status = "pass" if (
		qualitative_consistency
		and targets_met
		and band_separation_met
		and band_four_unclaimed
	) else "fail"
	if not matrix_complete or not complete:
		status = "incomplete"
	return {
		"status": status,
		"complete": complete,
		"passage_grounded": passage_grounded,
		"qualitative_consistency": qualitative_consistency,
		"targets_met": targets_met,
		"band_separation": band_separation,
		"band_separation_met": band_separation_met,
		"band_four_unclaimed": band_four_unclaimed,
		"dates": dates,
	}


#============================================
def _preparation_identity(
	posts: tuple[HistoricalPost, ...],
	rubric: str,
	procedure: CalibrationProcedure | None = None,
) -> dict:
	"""Build the immutable local-input identity shared by preparation and live runs.

	Args:
		posts: Fixed historical source records.
		rubric: Digest-validated maker rubric text.

	Returns:
		Stable contract, resource, target, and post identity value.
	"""
	return {
		"schema_version": CALIBRATION_SCHEMA_VERSION,
		"contract_name": CALIBRATION_CONTRACT.name,
		"contract_version": CALIBRATION_CONTRACT.version,
		"target_contract": target_contract(procedure),
		"rubric_sha256": daily_blog.io_utils.sha256_text(rubric),
		"template_sha256": daily_blog.io_utils.sha256_text(
			daily_blog.prompt_resources.load_allowlisted_instruction_prompt(
				CALIBRATION_CONTRACT.template_name,
				CALIBRATION_RESOURCE_NAMES,
				"rubric calibration",
			)
		),
		"repair_template_sha256": daily_blog.io_utils.sha256_text(
			daily_blog.prompt_resources.load_allowlisted_instruction_prompt(
				CALIBRATION_CONTRACT.repair_template_name,
				CALIBRATION_RESOURCE_NAMES,
				"rubric calibration",
			)
		),
		"posts": {
			post.report_date: {
				"bytes": post.byte_count,
				"sha256": post.sha256,
			}
			for post in posts
		},
	}


#============================================
def build_preparation(
	config: daily_blog.config.DailyBlogConfig,
	procedure: CalibrationProcedure | None = None,
) -> tuple[dict, tuple[HistoricalPost, ...]]:
	"""Build a route-free calibration report with deterministic historical profiles.

	Args:
		config: Historical source and prompt-resource configuration.

	Returns:
		Preparation report and its in-memory source posts.

	Raises:
		RuntimeError: Historical inputs or immutable resources fail validation.
	"""
	posts = load_historical_posts(config.daily_blog_repository)
	rubric, _template, criteria = calibration_resources()
	procedure = procedure or calibration_procedure()
	identity = _preparation_identity(posts, rubric, procedure)
	report = {
		"schema_version": CALIBRATION_SCHEMA_VERSION,
		"mode": "preparation",
		"non_publishing": True,
		"external_route_used": False,
		"preparation_id": daily_blog.io_utils.hash_value(identity),
		"criteria": [dataclasses.asdict(criterion) for criterion in criteria],
		"target_contract": target_contract(procedure),
		"posts": {
			post.report_date: {
				"bytes": post.byte_count,
				"sha256": post.sha256,
				"profile": post.profile,
			}
			for post in posts
		},
		"pending": [
			"explicit historical-post model-data-sharing approval",
			"repeated referee-route scorecards",
			"aggregate separation, grounded-reason, and consistency evaluation",
		],
	}
	return report, posts


#============================================
def prepare_calibration(
	config: daily_blog.config.DailyBlogConfig,
	procedure: CalibrationProcedure | None = None,
) -> tuple[str, dict]:
	"""Persist one route-free, content-addressed calibration preparation report.

	Args:
		config: Fixed historical repository and private output configuration.

	Returns:
		Installed artifact path and the route-free preparation report.

	Raises:
		RuntimeError: Historical inputs, resources, or private output fail their contracts.
	"""
	report, posts = build_preparation(config, procedure)
	calibration_id = "rubric-calibration-preparation-" + report["preparation_id"][:24]
	manifest = {
		"schema_version": CALIBRATION_SCHEMA_VERSION,
		"calibration_id": calibration_id,
		"mode": "preparation",
		"report_sha256": daily_blog.io_utils.sha256_text(
			daily_blog.io_utils.stable_json_text(report)
		),
		"post_hashes": {post.report_date: post.sha256 for post in posts},
	}
	path = install_calibration_artifacts(config, calibration_id, manifest, report)
	return path, report


#============================================
def _new_calibration_id() -> str:
	"""Create one sortable private live-calibration identity."""
	moment = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
	return f"rubric-calibration-{moment.lower()}-{uuid.uuid4().hex[:10]}"


#============================================
def _score_records(
	posts: tuple[HistoricalPost, ...],
	config: daily_blog.config.DailyBlogConfig,
	runner: object,
	repetitions: int,
) -> list[dict]:
	"""Return every repeated scorecard record for the fixed historical posts."""
	records = []
	for post in posts:
		for repetition in range(repetitions):
			result = score_maker_post(
				post.text,
				config,
				runner,
				"historical_calibration",
			)
			records.append(
				{
					"report_date": post.report_date,
					"post_sha256": post.sha256,
					"repetition": repetition,
					**result,
				}
			)
	return records


#============================================
def _calibration_report(
	config: daily_blog.config.DailyBlogConfig,
	calibration_id: str,
	procedure: CalibrationProcedure,
	preparation_identity: dict,
	criteria: tuple[RubricCriterion, ...],
	records: list[dict],
	aggregate: dict,
	*,
	mode: str,
	external_route_used: bool,
	fixture: dict | None = None,
) -> dict:
	"""Build one complete private score report with explicit route provenance."""
	report = {
		"schema_version": CALIBRATION_SCHEMA_VERSION,
		"calibration_id": calibration_id,
		"mode": mode,
		"non_publishing": True,
		"external_route_used": external_route_used,
		"route": {
			"name": config.referee_route.name,
			"command": list(config.referee_route.command),
		},
		"fixture": fixture,
		"repetitions": procedure.repetitions,
		"preparation_id": daily_blog.io_utils.hash_value(preparation_identity),
		"criteria": [dataclasses.asdict(criterion) for criterion in criteria],
		"target_contract": target_contract(procedure),
		"records": records,
		"aggregate": aggregate,
	}
	return report


#============================================
def _calibration_manifest(
	calibration_id: str,
	preparation_identity: dict,
	posts: tuple[HistoricalPost, ...],
	report: dict,
) -> dict:
	"""Build the immutable identity for one private provenance-labelled report."""
	manifest = {
		"schema_version": CALIBRATION_SCHEMA_VERSION,
		"calibration_id": calibration_id,
		"mode": report["mode"],
		"fixture": report["fixture"],
		"report_sha256": daily_blog.io_utils.sha256_text(
			daily_blog.io_utils.stable_json_text(report)
		),
		"rubric_sha256": preparation_identity["rubric_sha256"],
		"post_hashes": {post.report_date: post.sha256 for post in posts},
	}
	return manifest


#============================================
def run_live_calibration(
	config: daily_blog.config.DailyBlogConfig,
	*,
	operator_approved: bool,
	repetitions: int = DEFAULT_REPETITIONS,
	maximum_criterion_score_span: int = DEFAULT_MAXIMUM_CRITERION_SCORE_SPAN,
	minimum_positive_negative_mean_separation: float = (
		DEFAULT_MINIMUM_AGGREGATE_BAND_SEPARATION
	),
	runner: object | None = None,
	calibration_id: str | None = None,
) -> tuple[int, str, dict]:
	"""Score fixed public historical posts without any publication capability.

	Args:
		config: Historical source, referee route, limits, approval, and private output settings.
		operator_approved: Explicit approval for this invocation to share the fixed posts.
		repetitions: Scorecards requested for each fixed historical date.
		runner: Optional isolated route implementation used by offline checks.
		calibration_id: Optional validated immutable identity for an isolated run.

	Returns:
		Process status, installed private artifact path, and complete score report.

	Raises:
		CalibrationBlockedError: Either sharing approval or the configured route is unavailable.
		RuntimeError: Inputs, resources, repetitions, or private artifacts violate their contract.
	"""
	# ASVS 2.3.1 and 14.2.3: both durable configuration and this invocation approve sharing.
	if operator_approved is not True or not config.allow_shadow_model_data_sharing:
		raise CalibrationBlockedError(
			"Historical rubric calibration requires explicit model-data-sharing approval."
		)
	procedure = calibration_procedure(
		repetitions=repetitions,
		maximum_criterion_score_span=maximum_criterion_score_span,
		minimum_positive_negative_mean_separation=(
			minimum_positive_negative_mean_separation
		),
	)
	posts = load_historical_posts(config.daily_blog_repository)
	rubric, _template, criteria = calibration_resources()
	if runner is None and shutil.which(config.referee_route.command[0]) is None:
		raise CalibrationBlockedError("Configured rubric calibration route is unavailable.")
	runner = runner or daily_blog.routes.CommandRouteRunner()
	calibration_id = calibration_id or _new_calibration_id()
	records = _score_records(posts, config, runner, procedure.repetitions)
	aggregate = aggregate_calibration(records, criteria, posts, procedure)
	preparation_identity = _preparation_identity(posts, rubric, procedure)
	report = _calibration_report(
		config,
		calibration_id,
		procedure,
		preparation_identity,
		criteria,
		records,
		aggregate,
		mode="external_hermes",
		external_route_used=True,
	)
	manifest = _calibration_manifest(calibration_id, preparation_identity, posts, report)
	path = install_calibration_artifacts(config, calibration_id, manifest, report)
	code = 0 if aggregate["status"] == "pass" else 1
	return code, path, report

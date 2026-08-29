"""Route-free independent-review contract for sealed maker experiment artifacts."""

# Standard Library
import re

# local repo modules
import daily_blog.contracts
import daily_blog.io_utils


REVIEW_CONTRACT_SCHEMA = "vosslab.daily-blog.prompt-experiment-review-contract.v2"
REVIEW_SUBMISSION_SCHEMA = "vosslab.daily-blog.prompt-experiment-review-submission.v2"
REVIEWER_ID_RE = re.compile(r"^reviewer-[a-z0-9][a-z0-9-]{0,47}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_REVIEW_PASSAGE_CHARS = 500
MAX_REVIEW_ASSESSMENT_CHARS = 1_000
DEFAULT_REVIEWER_COUNT = 2
MIN_REVIEWER_COUNT = 1
MAX_REVIEWER_COUNT = 4
CENTRAL_MAKER_QUESTION = (
	"After reading this post, does it feel like Neil sat down after coding and wrote about what he "
	"made, what interested or surprised him, why he enjoyed working on it, what he learned, and what "
	"he wants to try next?"
)
REVIEW_DIMENSIONS = (
	("made", "What did Neil make or materially change?"),
	("attention_or_surprise", "What caught Neil's attention or surprised him?"),
	("enjoyment", "What shows why Neil enjoyed or cared about this work?"),
	("learning", "What did Neil learn through the work?"),
	("next_try", "What does Neil want to try next?"),
	("unfinished_edges", "What remains unresolved or uncertain?"),
	("technical_story_support", "How do technical details support the story?"),
	("routine_selectivity", "Does routine work stay brief enough for the interesting work to lead?"),
)
POST_SELECTION_POLICY = "first_authority_ordered_sample"


#============================================
def _selected_post_reference(
	fixture: str,
	selected_arm: str,
	capture_manifest: dict[str, object],
	capture_report: dict[str, object],
) -> dict[str, object]:
	"""Bind the predeclared first sample without using its experimental outcome."""
	repetitions = capture_manifest.get("repetitions")
	records = capture_report.get("records")
	if type(repetitions) is not int or repetitions < 1 or not isinstance(records, list):
		raise RuntimeError("Independent review capture matrix is invalid.")
	matching = [
		record
		for record in records
		if isinstance(record, dict)
		and record.get("fixture") == fixture
		and record.get("arm") == selected_arm
	]
	if (
		len(matching) != repetitions
		or {record.get("repetition") for record in matching} != set(range(repetitions))
	):
		raise RuntimeError("Independent review selected-post matrix is incomplete.")
	for record in matching:
		selected = record.get("selected")
		if (
			not isinstance(selected, dict)
			or selected.get("path") != "selected.md"
			or not isinstance(selected.get("post_hash"), str)
			or SHA256_RE.fullmatch(selected["post_hash"]) is None
		):
			raise RuntimeError("Independent review selected-post record is invalid.")
	chosen = min(matching, key=lambda record: record["repetition"])
	repetition = chosen["repetition"]
	selected = chosen["selected"]
	return {
		"artifact": f"{fixture}-{selected_arm}-{repetition}/selected.md",
		"post_sha256": selected["post_hash"],
		"repetition": repetition,
	}


#============================================
def validate_review_contract(value: object) -> dict[str, object]:
	"""Validate the complete artifact-only review brief and its exact prose targets."""
	fields = {
		"schema_version", "status", "central_question", "selected_arm", "fixtures",
		"reviewer_count", "review_basis", "independence", "required_dimensions",
		"post_selection", "submission_contract",
	}
	if not isinstance(value, dict) or set(value) != fields:
		raise RuntimeError("Independent review contract fields are invalid.")
	if (
		value["schema_version"] != REVIEW_CONTRACT_SCHEMA
		or value["central_question"] != CENTRAL_MAKER_QUESTION
		or value["review_basis"] != "sealed_artifacts_only"
		or value["post_selection"] != POST_SELECTION_POLICY
		or value["independence"] != {
			"manager_summary_visible": False,
			"other_reviewer_work_visible": False,
			"prompt_authorship_context_visible": False,
		}
		or value["required_dimensions"] != [
			{"field": field, "question": question}
			for field, question in REVIEW_DIMENSIONS
		]
		or value["submission_contract"] != {
			"fixture_conclusion_values": ["pass", "revise"],
			"passage_grounding": "exact_selected_post_substring_per_dimension",
			"complete_post_required": True,
			"overall_acceptance": "all_configured_reviewers_pass_both_fixtures",
		}
	):
		raise RuntimeError("Independent review contract policy is invalid.")
	reviewer_count = value["reviewer_count"]
	if (
		type(reviewer_count) is not int
		or not MIN_REVIEWER_COUNT <= reviewer_count <= MAX_REVIEWER_COUNT
	):
		raise RuntimeError("Independent review count is outside the bounded range.")
	fixtures = value["fixtures"]
	if not isinstance(fixtures, dict) or set(fixtures) != {"busy", "quiet"}:
		raise RuntimeError("Independent review fixture set is invalid.")
	ready = (
		value["status"] == "ready"
		and isinstance(value["selected_arm"], str)
		and value["selected_arm"] != "v3"
		and value["selected_arm"] in daily_blog.contracts.PROMPT_EXPERIMENT_ARMS
	)
	if not ready and not (value["status"] == "not_ready" and value["selected_arm"] is None):
		raise RuntimeError("Independent review readiness is invalid.")
	for fixture, reference in fixtures.items():
		if not isinstance(reference, dict) or set(reference) != {
			"fixture_id", "label", "packet_id", "projection_id", "selected_post",
		}:
			raise RuntimeError("Independent review fixture reference is invalid.")
		if any(
			not isinstance(reference[field], str) or not reference[field]
			for field in ("fixture_id", "label", "packet_id", "projection_id")
		):
			raise RuntimeError("Independent review fixture reference is incomplete.")
		selected_post = reference["selected_post"]
		if not ready:
			if selected_post is not None:
				raise RuntimeError("Non-ready review contract names a selected post.")
			continue
		if not isinstance(selected_post, dict) or set(selected_post) != {
			"artifact", "post_sha256", "repetition",
		}:
			raise RuntimeError("Independent review selected-post reference is invalid.")
		repetition = selected_post["repetition"]
		expected_artifact = f"{fixture}-{value['selected_arm']}-{repetition}/selected.md"
		if (
			type(repetition) is not int
			or repetition < 0
			or selected_post["artifact"] != expected_artifact
			or not isinstance(selected_post["post_sha256"], str)
			or SHA256_RE.fullmatch(selected_post["post_sha256"]) is None
		):
			raise RuntimeError("Independent review selected-post identity is invalid.")
	# ASVS 1.5.2 and 2.2.1: only the complete positive JSON contract enters review.
	return value.copy()


#============================================
def build_review_contract(
	acceptance: dict[str, object],
	capture_manifest: dict[str, object],
	capture_report: dict[str, object],
	reviewer_count: int = DEFAULT_REVIEWER_COUNT,
) -> dict[str, object]:
	"""Return one artifact-only brief for a bounded number of independent reviewers."""
	if (
		type(reviewer_count) is not int
		or not MIN_REVIEWER_COUNT <= reviewer_count <= MAX_REVIEWER_COUNT
	):
		raise RuntimeError("Independent review count is outside the bounded range.")
	fixtures = capture_manifest.get("fixtures")
	if not isinstance(fixtures, dict) or set(fixtures) != {"busy", "quiet"}:
		raise RuntimeError("Independent review requires the sealed busy and quiet fixtures.")
	fixture_references = {}
	for name, value in fixtures.items():
		if not isinstance(value, dict):
			raise RuntimeError("Independent review fixture reference is invalid.")
		required = {"label", "fixture_id", "packet_id", "projection_id"}
		if any(not isinstance(value.get(field), str) or not value[field] for field in required):
			raise RuntimeError("Independent review fixture reference is incomplete.")
		fixture_references[name] = {field: value[field] for field in sorted(required)}
	selected_arm = acceptance.get("selected_arm")
	review_ready = acceptance.get("review_ready") is True and isinstance(selected_arm, str)
	for name in fixture_references:
		fixture_references[name]["selected_post"] = (
			_selected_post_reference(name, selected_arm, capture_manifest, capture_report)
			if review_ready
			else None
		)
	contract = {
		"schema_version": REVIEW_CONTRACT_SCHEMA,
		"status": "ready" if review_ready else "not_ready",
		"central_question": CENTRAL_MAKER_QUESTION,
		"selected_arm": selected_arm if review_ready else None,
		"fixtures": fixture_references,
		"reviewer_count": reviewer_count,
		"review_basis": "sealed_artifacts_only",
		"post_selection": POST_SELECTION_POLICY,
		"independence": {
			"manager_summary_visible": False,
			"other_reviewer_work_visible": False,
			"prompt_authorship_context_visible": False,
		},
		"required_dimensions": [
			{"field": field, "question": question}
			for field, question in REVIEW_DIMENSIONS
		],
		"submission_contract": {
			"fixture_conclusion_values": ["pass", "revise"],
			"passage_grounding": "exact_selected_post_substring_per_dimension",
			"complete_post_required": True,
			"overall_acceptance": "all_configured_reviewers_pass_both_fixtures",
		},
	}
	return validate_review_contract(contract)


#============================================
def validate_review_submission(
	value: object,
	contract: dict[str, object],
	posts: dict[str, str],
) -> dict[str, object]:
	"""Validate one review written independently from complete sealed posts."""
	validated_contract = validate_review_contract(contract)
	if validated_contract["status"] != "ready" or set(posts) != {"busy", "quiet"}:
		raise RuntimeError("Independent review inputs are not ready.")
	required = {
		"schema_version", "reviewer_id", "review_contract_sha256", "fixtures",
	}
	if not isinstance(value, dict) or set(value) != required:
		raise RuntimeError("Independent review submission fields are invalid.")
	if value["schema_version"] != REVIEW_SUBMISSION_SCHEMA:
		raise RuntimeError("Independent review submission schema is invalid.")
	reviewer_id = value["reviewer_id"]
	if not isinstance(reviewer_id, str) or not REVIEWER_ID_RE.fullmatch(reviewer_id):
		raise RuntimeError("Independent reviewer identity is invalid.")
	if value["review_contract_sha256"] != daily_blog.io_utils.hash_value(validated_contract):
		raise RuntimeError("Independent review contract identity is invalid.")
	fixtures = value["fixtures"]
	if not isinstance(fixtures, dict) or set(fixtures) != set(posts):
		raise RuntimeError("Independent review fixture set is invalid.")
	dimension_fields = {field for field, _question in REVIEW_DIMENSIONS}
	for fixture, post in posts.items():
		reference = validated_contract["fixtures"][fixture]["selected_post"]
		post_sha256 = daily_blog.io_utils.sha256_text(post)
		if reference["post_sha256"] != post_sha256:
			raise RuntimeError("Independent review post is not the sealed review target.")
		review = fixtures[fixture]
		if not isinstance(review, dict) or set(review) != {
			"post_sha256", "complete_post_read", "conclusion", "dimensions", "overall_reason",
		}:
			raise RuntimeError("Independent review fixture fields are invalid.")
		if (
			review["post_sha256"] != post_sha256
			or review["complete_post_read"] is not True
			or review["conclusion"] not in {"pass", "revise"}
		):
			raise RuntimeError("Independent review fixture declaration is invalid.")
		dimensions = review["dimensions"]
		if not isinstance(dimensions, dict) or set(dimensions) != dimension_fields:
			raise RuntimeError("Independent review dimensions are invalid.")
		for assessment in dimensions.values():
			if not isinstance(assessment, dict) or set(assessment) != {"passage", "assessment"}:
				raise RuntimeError("Independent review dimension fields are invalid.")
			passage = assessment["passage"]
			reason = assessment["assessment"]
			if (
				not isinstance(passage, str)
				or not passage
				or len(passage) > MAX_REVIEW_PASSAGE_CHARS
				or passage not in post
				or not isinstance(reason, str)
				or not reason
				or len(reason) > MAX_REVIEW_ASSESSMENT_CHARS
			):
				raise RuntimeError("Independent review assessment is not passage-grounded.")
		overall_reason = review["overall_reason"]
		if (
			not isinstance(overall_reason, str)
			or not overall_reason
			or len(overall_reason) > MAX_REVIEW_ASSESSMENT_CHARS
		):
			raise RuntimeError("Independent review overall reason is invalid.")
	return value.copy()


#============================================
def aggregate_independent_reviews(
	submissions: list[dict[str, object]],
	contract: dict[str, object],
	posts: dict[str, str],
) -> dict[str, object]:
	"""Accept F4 only when every configured independent reviewer passes both posts."""
	reviewer_count = contract.get("reviewer_count")
	if type(reviewer_count) is not int or len(submissions) != reviewer_count:
		raise RuntimeError("Independent review submission count differs from its contract.")
	validated = [validate_review_submission(value, contract, posts) for value in submissions]
	reviewer_ids = [value["reviewer_id"] for value in validated]
	if len(set(reviewer_ids)) != reviewer_count:
		raise RuntimeError("Independent review requires distinct reviewers.")
	fixture_conclusions = {
		fixture: [value["fixtures"][fixture]["conclusion"] for value in validated]
		for fixture in ("busy", "quiet")
	}
	f4_accepted = all(
		all(conclusion == "pass" for conclusion in conclusions)
		for conclusions in fixture_conclusions.values()
	)
	return {
		"status": "pass" if f4_accepted else "revise",
		"f4_accepted": f4_accepted,
		"reviewer_ids": reviewer_ids,
		"fixture_conclusions": fixture_conclusions,
	}

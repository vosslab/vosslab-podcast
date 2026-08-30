"""Pinned final-synthesis prompt resource and bounded CompletePost parser."""

# Standard Library
import dataclasses
import datetime
import json
import re

# local repo modules
import daily_blog.artifacts
import daily_blog.io_utils
import daily_blog.prompt_resources
import daily_blog.schema


FINAL_SYNTHESIS_PROMPT_VERSION = "final-synthesis-v1"
FINAL_SYNTHESIS_TEMPLATE = "daily_blog_final_synthesis_v1.txt"
FINAL_SYNTHESIS_RESOURCE_NAMES = frozenset({FINAL_SYNTHESIS_TEMPLATE})
MAX_INCUMBENT_POST_CHARS = 120000
MAX_ALTERNATIVE_POSTS_CHARS = 180000
MAX_STAGE6_REVIEW_CHARS = 30000
MAX_RUBRIC_CHARS = 30000
MAX_EVIDENCE_CHARS = 90000
MAX_PROVENANCE_CHARS = 30000
MAX_COMPLETE_POST_RESPONSE_CHARS = 180000
MAX_RENDERED_PROMPT_CHARS = 470000
PINNED_RESOURCE_SHA256 = {
	FINAL_SYNTHESIS_TEMPLATE: "be1b952d3139e576122cdcd907474215403c5d4b6719a6654787a73ae3463cf6",
}
_UNTRUSTED_BLOCK_LABELS = frozenset({
	"INCUMBENT_COMPLETE_POST", "ALTERNATIVE_COMPLETE_POSTS", "STAGE6_REVIEW_FACTS",
	"EDITORIAL_RUBRIC", "EVIDENCE_PACKETS", "PROVENANCE_IDENTITIES",
})
_RESOURCE_NAME_RE = re.compile(r"[a-z0-9_]+_v[0-9]+\.txt\Z")
_PLACEHOLDER_RE = re.compile(r"\{([a-z0-9_]+)\}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


@dataclasses.dataclass(frozen=True)
class FinalSynthesisPromptContract:
	"""One immutable content-addressed final-synthesis prompt asset."""

	version: str
	template: str
	resource_sha256: str
	resource_bytes: bytes = dataclasses.field(repr=False)
	integrity_sha256: str

	#============================================
	def identity_dict(self) -> dict[str, object]:
		"""Return durable prompt provenance without copying its prompt text."""
		return {
			"version": self.version,
			"resources": {FINAL_SYNTHESIS_TEMPLATE: self.resource_sha256},
			"integrity_sha256": self.integrity_sha256,
		}


#============================================
def _validate_template(text: str) -> None:
	"""Require exactly the renderer-owned substitutions for this asset."""
	found = set(_PLACEHOLDER_RE.findall(text))
	required = {
		"report_date", "incumbent_post", "alternative_posts", "stage6_review", "rubric",
		"evidence", "provenance",
	}
	if found != required:
		raise RuntimeError("Final-synthesis prompt placeholders are invalid.")
	if "{" in _PLACEHOLDER_RE.sub("", text) or "}" in _PLACEHOLDER_RE.sub("", text):
		raise RuntimeError("Final-synthesis prompt braces are invalid.")


#============================================
def load_final_synthesis_prompt_contract() -> FinalSynthesisPromptContract:
	"""Load the owned final-synthesis asset with exact raw-byte identity."""
	if _RESOURCE_NAME_RE.fullmatch(FINAL_SYNTHESIS_TEMPLATE) is None:
		raise RuntimeError("Final-synthesis prompt resource name is invalid.")
	text, contents = daily_blog.prompt_resources.load_allowlisted_instruction_prompt_with_bytes(
		FINAL_SYNTHESIS_TEMPLATE, FINAL_SYNTHESIS_RESOURCE_NAMES, "final-synthesis prompt contract",
	)
	_validate_template(text)
	digest = daily_blog.io_utils.sha256_text(contents.decode("utf-8"))
	if digest != PINNED_RESOURCE_SHA256[FINAL_SYNTHESIS_TEMPLATE]:
		raise RuntimeError("Final-synthesis prompt bytes do not match the pinned asset.")
	identity = {
		"version": FINAL_SYNTHESIS_PROMPT_VERSION,
		"pinned_resources": PINNED_RESOURCE_SHA256,
		"resources": {FINAL_SYNTHESIS_TEMPLATE: digest},
	}
	return FinalSynthesisPromptContract(
		FINAL_SYNTHESIS_PROMPT_VERSION, text, digest, contents, daily_blog.io_utils.hash_value(identity),
	)


#============================================
def final_synthesis_prompt_identity(
	contract: FinalSynthesisPromptContract | None = None,
) -> dict[str, object]:
	"""Return exact content-addressed provenance for final-synthesis prompting."""
	value = contract if contract is not None else load_final_synthesis_prompt_contract()
	if type(value) is not FinalSynthesisPromptContract:
		raise RuntimeError("Final-synthesis prompt contract type is invalid.")
	if value.version != FINAL_SYNTHESIS_PROMPT_VERSION or type(value.template) is not str:
		raise RuntimeError("Final-synthesis prompt contract is invalid.")
	_validate_template(value.template)
	if _SHA256_RE.fullmatch(value.resource_sha256) is None:
		raise RuntimeError("Final-synthesis prompt resource identity is invalid.")
	if value.resource_sha256 != PINNED_RESOURCE_SHA256[FINAL_SYNTHESIS_TEMPLATE]:
		raise RuntimeError("Final-synthesis prompt identity does not match the pinned asset.")
	if type(value.resource_bytes) is not bytes:
		raise RuntimeError("Final-synthesis prompt bytes are invalid.")
	try:
		text = value.resource_bytes.decode("utf-8").strip()
	except UnicodeDecodeError as error:
		raise RuntimeError("Final-synthesis prompt bytes are invalid.") from error
	if text != value.template:
		raise RuntimeError("Final-synthesis prompt text and bytes conflict.")
	if daily_blog.io_utils.sha256_text(value.resource_bytes.decode("utf-8")) != value.resource_sha256:
		raise RuntimeError("Final-synthesis prompt bytes do not match the pinned asset.")
	expected = daily_blog.io_utils.hash_value({
		"version": value.version, "pinned_resources": PINNED_RESOURCE_SHA256,
		"resources": {FINAL_SYNTHESIS_TEMPLATE: value.resource_sha256},
	})
	if value.integrity_sha256 != expected:
		raise RuntimeError("Final-synthesis prompt contract integrity is invalid.")
	return value.identity_dict()


#============================================
def _bounded_text(value: object, label: str, maximum: int) -> str:
	"""Require one exact bounded text input before prompt construction."""
	if type(value) is not str or not value or len(value) > maximum:
		raise RuntimeError(f"Final-synthesis {label} is invalid or exceeds its limit.")
	return value


#============================================
def _report_date(value: object) -> str:
	"""Validate the sole publication identity through the artifact boundary."""
	if type(value) is not str or daily_blog.artifacts.DATE_RE.fullmatch(value) is None:
		raise RuntimeError("Final-synthesis report date is invalid.")
	try:
		datetime.date.fromisoformat(value)
	except ValueError as error:
		raise RuntimeError("Final-synthesis report date is invalid.") from error
	return value


#============================================
def _untrusted_data_block(label: str, value: object, context_label: str, maximum: int) -> str:
	"""Encode supplied text so it cannot close or add prompt-instruction blocks."""
	if label not in _UNTRUSTED_BLOCK_LABELS:
		raise RuntimeError("Final-synthesis untrusted data label is invalid.")
	literal = _bounded_text(value, context_label, maximum)
	payload = json.dumps(
		{"encoding": "utf-8-json-string", "literal_content": literal},
		ensure_ascii=True, separators=(",", ":"),
	).replace("<", "\\u003c").replace(">", "\\u003e")
	return f"<<BEGIN_UNTRUSTED_{label}_DATA>>\n{payload}\n<<END_UNTRUSTED_{label}_DATA>>"


#============================================
def render_final_synthesis_prompt(
	report_date: str, incumbent_post_json: str, alternative_posts_json: str, stage6_review_json: str,
	rubric_json: str, evidence_json: str, provenance_json: str,
	contract: FinalSynthesisPromptContract | None = None,
) -> str:
	"""Render a bounded final-synthesis assignment with all content encoded as data."""
	value = contract if contract is not None else load_final_synthesis_prompt_contract()
	final_synthesis_prompt_identity(value)
	rendered = value.template.format(
		report_date=_report_date(report_date),
		incumbent_post=_untrusted_data_block("INCUMBENT_COMPLETE_POST", incumbent_post_json,
			"incumbent CompletePost", MAX_INCUMBENT_POST_CHARS),
		alternative_posts=_untrusted_data_block("ALTERNATIVE_COMPLETE_POSTS", alternative_posts_json,
			"alternative CompletePosts", MAX_ALTERNATIVE_POSTS_CHARS),
		stage6_review=_untrusted_data_block("STAGE6_REVIEW_FACTS", stage6_review_json,
			"Stage 6 review facts", MAX_STAGE6_REVIEW_CHARS),
		rubric=_untrusted_data_block("EDITORIAL_RUBRIC", rubric_json, "editorial rubric", MAX_RUBRIC_CHARS),
		evidence=_untrusted_data_block("EVIDENCE_PACKETS", evidence_json, "evidence packets", MAX_EVIDENCE_CHARS),
		provenance=_untrusted_data_block("PROVENANCE_IDENTITIES", provenance_json,
			"provenance identities", MAX_PROVENANCE_CHARS),
	)
	if len(rendered) > MAX_RENDERED_PROMPT_CHARS:
		raise RuntimeError("Final-synthesis rendered prompt exceeds its configured limit.")
	return rendered


#============================================
def parse_final_synthesis_complete_post(
	response: object, report_date: object,
	packets: object, repositories: object, output_path: object,
	approved_output_root: object,
) -> daily_blog.artifacts.CompletePost:
	"""Build and mechanically admit one exact CompletePost without repairing prose."""
	content = _bounded_text(response, "complete-post response", MAX_COMPLETE_POST_RESPONSE_CHARS).rstrip() + "\n"
	date = _report_date(report_date)
	if type(packets) is not tuple or not packets or any(
		type(packet) is not daily_blog.schema.EvidencePacket for packet in packets
	):
		raise RuntimeError("Final-synthesis packets must be a nonempty exact EvidencePacket tuple.")
	if type(repositories) is not tuple or not repositories or any(
		type(repository) is not str or not repository for repository in repositories
	):
		raise RuntimeError("Final-synthesis repositories must be a nonempty exact text tuple.")
	if type(output_path) is not str or not output_path:
		raise RuntimeError("Final-synthesis output path is invalid.")
	if type(approved_output_root) is not str or not approved_output_root:
		raise RuntimeError("Final-synthesis approved output root is invalid.")
	evidence_ids = daily_blog.artifacts.evidence_references(content)
	if not evidence_ids:
		raise RuntimeError("Final-synthesis complete post has no evidence reference.")
	candidate = daily_blog.artifacts.CompletePost.create(
		date, packets, repositories, content, evidence_ids, date, output_path,
	)
	eligibility = daily_blog.artifacts.evaluate_eligibility(
		candidate, packets, (approved_output_root,),
	)
	if not eligibility.eligible:
		reasons = ", ".join(eligibility.reasons)
		raise RuntimeError(f"Final-synthesis complete post is ineligible: {reasons}.")
	return candidate

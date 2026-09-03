"""Pinned final-synthesis prompt resource and bounded CompletePost parser."""

# Standard Library
import datetime
import json

# local repo modules
import daily_blog.artifacts
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.loader
import daily_blog.schema


MAX_INCUMBENT_POST_CHARS = 120000
MAX_ALTERNATIVE_POSTS_CHARS = 180000
MAX_STAGE6_REVIEW_CHARS = 30000
MAX_RUBRIC_CHARS = 30000
MAX_EVIDENCE_CHARS = 90000
MAX_PROVENANCE_CHARS = 30000
MAX_COMPLETE_POST_RESPONSE_CHARS = 180000
MAX_RENDERED_PROMPT_CHARS = 470000
_UNTRUSTED_BLOCK_LABELS = frozenset({
	"INCUMBENT_COMPLETE_POST", "ALTERNATIVE_COMPLETE_POSTS", "STAGE6_REVIEW_FACTS",
	"EDITORIAL_RUBRIC", "EVIDENCE_PACKETS", "PROVENANCE_IDENTITIES",
})
def _loaded_prompt_set(
	value: daily_blog.prompt_registry.loader.LoadedPromptSet | None,
) -> daily_blog.prompt_registry.loader.LoadedPromptSet:
	"""Resolve the issued Stage 7 prompt set through the central registry."""
	return daily_blog.prompt_registry.loader.resolve_loaded_prompt_set(
		value, daily_blog.prompt_registry.definitions.FINAL_SYNTHESIS_PROMPT_SET,
	)


#============================================
def _synthesis_resource(
	value: daily_blog.prompt_registry.definitions.RegisteredPromptResource,
) -> daily_blog.prompt_registry.definitions.RegisteredPromptResource:
	"""Require the one canonical renderer resource for the Stage 7 prompt set."""
	if value is not daily_blog.prompt_registry.definitions.FINAL_SYNTHESIS_RESOURCE:
		raise RuntimeError("Final-synthesis prompt resource is not registry-issued.")
	return value


#============================================
def final_synthesis_prompt_identity(
	prompt_set: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None,
) -> dict[str, object]:
	"""Return the current cache identity issued by the central registry."""
	return _loaded_prompt_set(prompt_set).identity_dict()


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
	prompt_set: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None,
	resource: daily_blog.prompt_registry.definitions.RegisteredPromptResource = daily_blog.prompt_registry.definitions.FINAL_SYNTHESIS_RESOURCE,
) -> str:
	"""Render a bounded final-synthesis assignment with all content encoded as data."""
	loaded = _loaded_prompt_set(prompt_set)
	canonical_resource = _synthesis_resource(resource)
	rendered = loaded.render(canonical_resource, {
		"report_date": _report_date(report_date),
		"incumbent_post": _untrusted_data_block("INCUMBENT_COMPLETE_POST", incumbent_post_json,
			"incumbent CompletePost", MAX_INCUMBENT_POST_CHARS),
		"alternative_posts": _untrusted_data_block("ALTERNATIVE_COMPLETE_POSTS", alternative_posts_json,
			"alternative CompletePosts", MAX_ALTERNATIVE_POSTS_CHARS),
		"stage6_review": _untrusted_data_block("STAGE6_REVIEW_FACTS", stage6_review_json,
			"Stage 6 review facts", MAX_STAGE6_REVIEW_CHARS),
		"rubric": _untrusted_data_block("EDITORIAL_RUBRIC", rubric_json, "editorial rubric", MAX_RUBRIC_CHARS),
		"evidence": _untrusted_data_block("EVIDENCE_PACKETS", evidence_json, "evidence packets", MAX_EVIDENCE_CHARS),
		"provenance": _untrusted_data_block("PROVENANCE_IDENTITIES", provenance_json,
			"provenance identities", MAX_PROVENANCE_CHARS),
	})
	if len(rendered) > MAX_RENDERED_PROMPT_CHARS:
		raise RuntimeError("Final-synthesis rendered prompt exceeds its configured limit.")
	return rendered


#============================================
def parse_final_synthesis_complete_post(
	response: object, report_date: object,
	packets: object, repositories: object, output_path: object,
	approved_output_root: object,
) -> daily_blog.artifacts.CompletePost:
	"""Build one exact CompletePost with machine-owned front matter and intact prose."""
	content = _bounded_text(response, "complete-post response", MAX_COMPLETE_POST_RESPONSE_CHARS).rstrip() + "\n"
	date = _report_date(report_date)
	if not content.startswith("---"):
		content = f"---\ndate: {date}\n---\n" + content
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
	try:
		resolved_repositories = daily_blog.artifacts.resolve_evidence_scope(
			evidence_ids, packets, repositories,
		)
	except daily_blog.artifacts.EvidenceScopeError as error:
		raise RuntimeError("Final-synthesis complete post evidence scope is invalid.") from error
	candidate = daily_blog.artifacts.CompletePost.create(
		date, packets, resolved_repositories, content, evidence_ids, date, output_path,
	)
	eligibility = daily_blog.artifacts.evaluate_eligibility(
		candidate, packets, (approved_output_root,), repositories,
	)
	if not eligibility.eligible:
		reasons = ", ".join(eligibility.reasons)
		raise RuntimeError(f"Final-synthesis complete post is ineligible: {reasons}.")
	return candidate

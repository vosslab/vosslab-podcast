"""Pinned prompt resource and bounded renderer for Stage 6 whole-post editors."""

# Standard Library
import dataclasses
import re

# local repo modules
import daily_blog.io_utils
import daily_blog.prompt_resources


COMPLETE_POST_EDITOR_PROMPT_VERSION = "complete-post-editor-v1"
COMPLETE_POST_EDITOR_TEMPLATE = "daily_blog_complete_post_editor_v1.txt"
COMPLETE_POST_EDITOR_RESOURCE_NAMES = frozenset({COMPLETE_POST_EDITOR_TEMPLATE})
MAX_TYPED_CONTEXT_CHARS = 60000
MAX_CANDIDATE_POSTS_CHARS = 120000
MAX_RENDERED_PROMPT_CHARS = 185000
PINNED_RESOURCE_SHA256 = {
	COMPLETE_POST_EDITOR_TEMPLATE: "471a5b6063a435b1f1a0efc5fad70b894fe2d6a1b5269055c2572d054dbb33cc",
}
_RESOURCE_NAME_RE = re.compile(r"[a-z0-9_]+_v[0-9]+\.txt\Z")
_REPLICA_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


@dataclasses.dataclass(frozen=True)
class CompletePostEditorPromptContract:
	"""One immutable, content-addressed editor prompt asset."""

	version: str
	template: str
	resource_sha256: str
	resource_bytes: bytes = dataclasses.field(repr=False)
	integrity_sha256: str

	#============================================
	def identity_dict(self) -> dict[str, object]:
		"""Return durable prompt provenance without copying the prompt body."""
		value = {
			"version": self.version,
			"resources": {COMPLETE_POST_EDITOR_TEMPLATE: self.resource_sha256},
			"integrity_sha256": self.integrity_sha256,
		}
		return value


#============================================
def _validate_template(text: str) -> None:
	"""Require the exact bounded substitutions owned by this renderer."""
	found = set(_PLACEHOLDER_RE.findall(text))
	if found != {"typed_context_json", "candidate_posts_json", "replica_id"}:
		raise RuntimeError("Complete-post editor prompt placeholders are invalid.")
	if "{" in _PLACEHOLDER_RE.sub("", text) or "}" in _PLACEHOLDER_RE.sub("", text):
		raise RuntimeError("Complete-post editor prompt braces are invalid.")


#============================================
def load_complete_post_editor_prompt_contract() -> CompletePostEditorPromptContract:
	"""Load the owned editor prompt with its exact raw-byte identity."""
	if _RESOURCE_NAME_RE.fullmatch(COMPLETE_POST_EDITOR_TEMPLATE) is None:
		raise RuntimeError("Complete-post editor prompt resource name is invalid.")
	text, contents = daily_blog.prompt_resources.load_allowlisted_instruction_prompt_with_bytes(
		COMPLETE_POST_EDITOR_TEMPLATE, COMPLETE_POST_EDITOR_RESOURCE_NAMES,
		"complete-post editor prompt contract",
	)
	_validate_template(text)
	digest = daily_blog.io_utils.sha256_text(contents.decode("utf-8"))
	if digest != PINNED_RESOURCE_SHA256[COMPLETE_POST_EDITOR_TEMPLATE]:
		raise RuntimeError("Complete-post editor prompt bytes do not match the pinned asset.")
	identity = {
		"version": COMPLETE_POST_EDITOR_PROMPT_VERSION,
		"pinned_resources": PINNED_RESOURCE_SHA256,
		"resources": {COMPLETE_POST_EDITOR_TEMPLATE: digest},
	}
	contract = CompletePostEditorPromptContract(
		COMPLETE_POST_EDITOR_PROMPT_VERSION, text, digest, contents,
		daily_blog.io_utils.hash_value(identity),
	)
	return contract


#============================================
def complete_post_editor_prompt_identity(
	contract: CompletePostEditorPromptContract | None = None,
) -> dict[str, object]:
	"""Return exact content-addressed Stage 6 editor provenance."""
	value = contract if contract is not None else load_complete_post_editor_prompt_contract()
	if type(value) is not CompletePostEditorPromptContract:
		raise RuntimeError("Complete-post editor prompt contract type is invalid.")
	if value.version != COMPLETE_POST_EDITOR_PROMPT_VERSION:
		raise RuntimeError("Complete-post editor prompt version is invalid.")
	if type(value.template) is not str:
		raise RuntimeError("Complete-post editor prompt template is invalid.")
	_validate_template(value.template)
	if _SHA256_RE.fullmatch(value.resource_sha256) is None:
		raise RuntimeError("Complete-post editor prompt resource identity is invalid.")
	if value.resource_sha256 != PINNED_RESOURCE_SHA256[COMPLETE_POST_EDITOR_TEMPLATE]:
		raise RuntimeError("Complete-post editor prompt identity does not match the pinned asset.")
	if type(value.resource_bytes) is not bytes:
		raise RuntimeError("Complete-post editor prompt bytes are invalid.")
	try:
		text = value.resource_bytes.decode("utf-8").strip()
	except UnicodeDecodeError as error:
		raise RuntimeError("Complete-post editor prompt bytes are invalid.") from error
	if text != value.template:
		raise RuntimeError("Complete-post editor prompt text and bytes conflict.")
	if daily_blog.io_utils.sha256_text(value.resource_bytes.decode("utf-8")) != value.resource_sha256:
		raise RuntimeError("Complete-post editor prompt bytes do not match the pinned asset.")
	expected = daily_blog.io_utils.hash_value({
		"version": value.version,
		"pinned_resources": PINNED_RESOURCE_SHA256,
		"resources": {COMPLETE_POST_EDITOR_TEMPLATE: value.resource_sha256},
	})
	if value.integrity_sha256 != expected:
		raise RuntimeError("Complete-post editor prompt contract integrity is invalid.")
	identity = value.identity_dict()
	return identity


#============================================
def _bounded_text(value: object, label: str, maximum: int) -> str:
	"""Require one exact context component within its owned budget."""
	if type(value) is not str or not value or len(value) > maximum:
		raise RuntimeError(f"Complete-post editor {label} is invalid or exceeds its limit.")
	return value


#============================================
def _replica_id(value: object) -> str:
	"""Require an assignment identity without editorial ordering meaning."""
	if type(value) is not str or _REPLICA_ID_RE.fullmatch(value) is None:
		raise RuntimeError("Complete-post editor replica identity is invalid.")
	return value


#============================================
def render_complete_post_editor_prompt(
	typed_context_json: str,
	candidate_posts_json: str,
	replica_id: str,
	contract: CompletePostEditorPromptContract | None = None,
) -> str:
	"""Render one bounded anonymous whole-CompletePost editing assignment."""
	value = contract if contract is not None else load_complete_post_editor_prompt_contract()
	complete_post_editor_prompt_identity(value)
	context = _bounded_text(typed_context_json, "typed context", MAX_TYPED_CONTEXT_CHARS)
	candidates = _bounded_text(candidate_posts_json, "candidate posts", MAX_CANDIDATE_POSTS_CHARS)
	assignment = _replica_id(replica_id)
	rendered = value.template.format(
		typed_context_json=context, candidate_posts_json=candidates, replica_id=assignment,
	)
	if len(rendered) > MAX_RENDERED_PROMPT_CHARS:
		raise RuntimeError("Complete-post editor rendered prompt exceeds its configured limit.")
	return rendered

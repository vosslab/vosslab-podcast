"""Central declarations for allowlisted daily-blog prompt assets."""

# Standard Library
import dataclasses
import hashlib
import json
import pathlib
import re
import types

# local repo modules
import daily_blog.io_utils


_PROMPT_RESOURCE_NAME_RE = re.compile(r"[a-z0-9_]+_v[0-9]+\.(?:txt|md)\Z")
_PROMPT_RESOURCE_KEY_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
_PROMPT_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
PROMPT_PLACEHOLDER_RE = re.compile(r"\{([a-z0-9_]+)\}")


PROMPT_DIRECTORY = "pipeline/prompts"
MAX_EXAMPLE_BLOCKS = 3
MAX_EXAMPLE_CHARS = 36000
EXAMPLE_SELECTION_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
COVERAGE_REPOSITORY_SCOPES = (
	"all_packet_activity",
	"projected_repositories",
)


@dataclasses.dataclass(frozen=True)
class CandidateValidationPolicy:
	"""One immutable, allowlisted deterministic post-validation contract."""

	name: str
	version: str
	minimum_narrative_words: int
	maximum_narrative_words: int
	minimum_narrative_h2_sections: int
	maximum_narrative_h2_sections: int
	every_prose_block_cited: bool
	require_section_evidence: bool
	maximum_uncited_narrative_blocks: int
	coverage_maximum_blocks: int
	coverage_maximum_words: int
	require_final_project_coverage: bool
	coverage_reject_afterword: bool
	require_first_repository_link: bool
	coverage_repository_scope: str
	word_count_mode: str
	maximum_candidate_characters: int
	required_excerpt_marker_count: int
	required_opening_prose_blocks: int
	maximum_opening_h2_sections: int
	maximum_opening_words: int

	#============================================
	def __post_init__(self) -> None:
		"""Keep every behavior-affecting field declarative and bounded."""
		_validate_identifier("Candidate validation policy name", self.name)
		_validate_identifier("Candidate validation policy version", self.version)
		if (
			self.minimum_narrative_words < 0
			or self.maximum_narrative_words < self.minimum_narrative_words
			or self.minimum_narrative_h2_sections < 0
			or self.maximum_narrative_h2_sections < self.minimum_narrative_h2_sections
		):
			raise RuntimeError("Candidate validation policy limits are invalid.")
		for flag in (
			self.every_prose_block_cited,
			self.require_section_evidence,
			self.require_final_project_coverage,
			self.coverage_reject_afterword,
			self.require_first_repository_link,
		):
			if type(flag) is not bool:
				raise RuntimeError("Candidate validation policy flags must be Boolean.")
		for limit in (
			self.maximum_uncited_narrative_blocks,
			self.coverage_maximum_blocks,
			self.coverage_maximum_words,
			self.required_excerpt_marker_count,
			self.required_opening_prose_blocks,
			self.maximum_opening_h2_sections,
			self.maximum_opening_words,
		):
			if type(limit) is not int or limit < 0:
				raise RuntimeError(
					"Candidate validation policy unbounded limits must use nonnegative integers."
				)
		if (
			type(self.maximum_candidate_characters) is not int
			or self.maximum_candidate_characters <= 0
		):
			raise RuntimeError(
				"Candidate validation policy candidate character limit must use a positive integer."
			)
		if self.required_excerpt_marker_count != 1 and any(
			(
				self.required_opening_prose_blocks,
				self.maximum_opening_h2_sections,
				self.maximum_opening_words,
			)
		):
			raise RuntimeError(
				"Candidate validation policy opening limits require exactly one excerpt marker."
			)
		if (
			type(self.coverage_repository_scope) is not str
			or self.coverage_repository_scope not in COVERAGE_REPOSITORY_SCOPES
		):
			raise RuntimeError("Candidate validation policy coverage repository scope is unsupported.")
		if self.word_count_mode != "reader_visible_markdown":
			raise RuntimeError("Candidate validation policy word count mode is unsupported.")

	#============================================
	def canonical_value(self) -> dict[str, object]:
		"""Return the complete stable declaration used for compatibility identity."""
		return {
			"name": self.name,
			"version": self.version,
			"rules": {
				"coverage_max_blocks": self.coverage_maximum_blocks,
				"coverage_max_words": self.coverage_maximum_words,
				"coverage_reject_afterword": self.coverage_reject_afterword,
				"coverage_repository_scope": self.coverage_repository_scope,
				"max_candidate_chars": self.maximum_candidate_characters,
				"max_narrative_h2": self.maximum_narrative_h2_sections,
				"max_narrative_words": self.maximum_narrative_words,
				"max_opening_h2": self.maximum_opening_h2_sections,
				"max_opening_words": self.maximum_opening_words,
				"max_uncited_narrative_blocks": self.maximum_uncited_narrative_blocks,
				"min_narrative_h2": self.minimum_narrative_h2_sections,
				"min_narrative_words": self.minimum_narrative_words,
				"require_final_project_coverage": self.require_final_project_coverage,
				"require_first_narrative_repository_link": self.require_first_repository_link,
				"require_paragraph_evidence": self.every_prose_block_cited,
				"required_excerpt_marker_count": self.required_excerpt_marker_count,
				"required_opening_prose_blocks": self.required_opening_prose_blocks,
				"require_section_evidence": self.require_section_evidence,
				"word_count_mode": self.word_count_mode,
			},
		}

	#============================================
	def sha256(self) -> str:
		"""Return canonical JSON SHA-256 for this exact validation behavior."""
		payload = json.dumps(
			self.canonical_value(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
		).encode("ascii")
		return hashlib.sha256(payload).hexdigest()


@dataclasses.dataclass(frozen=True)
class ExampleResource:
	"""One trusted prompt resource with a fixed allowlist of block identifiers."""

	name: str
	filename: str
	block_ids: tuple[str, ...]
	external_block_ids: tuple[str, ...] = ()

	#============================================
	def __post_init__(self) -> None:
		"""Reject malformed internal example-resource declarations at import time."""
		_validate_identifier("Example resource name", self.name)
		_validate_prompt_name("example resource", self.filename)
		if not self.block_ids or len(set(self.block_ids)) != len(self.block_ids):
			raise RuntimeError("Example resource block IDs must be unique and non-empty.")
		for block_id in self.block_ids:
			_validate_identifier("Example block ID", block_id)
		if len(set(self.external_block_ids)) != len(self.external_block_ids):
			raise RuntimeError("External example block IDs must be unique.")
		if any(block_id not in self.block_ids for block_id in self.external_block_ids):
			raise RuntimeError("External example blocks must belong to their resource.")


@dataclasses.dataclass(frozen=True)
class ExampleSelection:
	"""One immutable, ordered, registered examples arm for a named contract."""

	name: str
	contract_name: str
	resource_name: str | None
	block_ids: tuple[str, ...]

	#============================================
	def __post_init__(self) -> None:
		"""Enforce documented selection types, counts, and order-bearing identifiers."""
		_validate_identifier("Example selection name", self.name)
		_validate_identifier("Example selection contract name", self.contract_name)
		if len(self.block_ids) > MAX_EXAMPLE_BLOCKS:
			raise RuntimeError("Editorial examples support zero through three ordered blocks.")
		if self.resource_name is None and self.block_ids:
			raise RuntimeError("Example blocks require a trusted example resource.")
		if self.resource_name is not None:
			_validate_identifier("Example selection resource name", self.resource_name)
		for block_id in self.block_ids:
			_validate_identifier("Example block ID", block_id)


@dataclasses.dataclass(frozen=True)
class EditorialContract:
	"""One complete, versioned set of trusted editorial prompt resources."""

	name: str
	author_template: str
	referee_template: str
	repair_template: str
	rubric: str
	example_resource_name: str | None
	example_selection_name: str | None
	prompt_version: str
	rubric_version: str
	author_uses_rubric: bool
	validation_policy_name: str

	#============================================
	def __post_init__(self) -> None:
		"""Reject malformed internal contract declarations at import time."""
		_validate_identifier("Editorial contract name", self.name)
		for field_name in (
			"author_template",
			"referee_template",
			"repair_template",
			"rubric",
		):
			_validate_prompt_name(field_name, getattr(self, field_name))
		if (self.example_resource_name is None) != (self.example_selection_name is None):
			raise RuntimeError("Editorial contracts pair example resources and selections.")
		if self.example_resource_name is not None:
			_validate_identifier("Editorial example resource name", self.example_resource_name)
			_validate_identifier("Editorial example selection name", self.example_selection_name)
		_validate_identifier("Editorial validation policy name", self.validation_policy_name)


#============================================
def _validate_identifier(label: str, value: object) -> None:
	"""Restrict registry labels to stable plain identifiers."""
	if not isinstance(value, str) or not EXAMPLE_SELECTION_RE.fullmatch(value):
		raise RuntimeError(f"{label} is invalid.")


#============================================
def _validate_prompt_name(field_name: str, value: object) -> None:
	"""Limit contract resources to one trusted prompt-directory filename."""
	if not isinstance(value, str) or not value:
		raise RuntimeError(f"Editorial contract {field_name} must be non-empty text.")
	pure = pathlib.PurePosixPath(value)
	if pure.is_absolute() or len(pure.parts) != 1 or pure.name != value:
		raise RuntimeError(f"Editorial contract {field_name} must be a bare filename.")


#============================================
def validate_example_resource_block_order(resource: ExampleResource, blocks: dict[str, str]) -> None:
	"""Require parsed resource blocks to preserve the registered order."""
	if tuple(blocks) != resource.block_ids:
		raise RuntimeError("Editorial example resource block order is unsupported.")


@dataclasses.dataclass(frozen=True)
class RegisteredPromptResource:
	"""One named, content-addressed prompt asset and its renderer contract."""

	key: str
	name: str
	sha256: str
	placeholders: tuple[str, ...]
	output_schema: str
	is_instruction: bool = True

	#============================================
	def __post_init__(self) -> None:
		"""Reject malformed registry declarations at import time."""
		if type(self.key) is not str or _PROMPT_RESOURCE_KEY_RE.fullmatch(self.key) is None:
			raise RuntimeError("Registered prompt resource key is invalid.")
		if type(self.name) is not str or _PROMPT_RESOURCE_NAME_RE.fullmatch(self.name) is None:
			raise RuntimeError("Registered prompt resource name is invalid.")
		if type(self.sha256) is not str or _PROMPT_SHA256_RE.fullmatch(self.sha256) is None:
			raise RuntimeError("Registered prompt resource digest is invalid.")
		if (
			type(self.placeholders) is not tuple
			or type(self.output_schema) is not str
			or not self.output_schema
			or type(self.is_instruction) is not bool
			or any(type(value) is not str or not value for value in self.placeholders)
			or len(set(self.placeholders)) != len(self.placeholders)
		):
			raise RuntimeError("Registered prompt resource metadata is invalid.")


@dataclasses.dataclass(frozen=True)
class RegisteredPromptSet:
	"""One immutable prompt-set declaration owned by the central registry."""

	stage_key: str
	version: str
	resources: tuple[RegisteredPromptResource, ...]

	#============================================
	def __post_init__(self) -> None:
		"""Require one complete ordered identity declaration."""
		if (
			type(self.stage_key) is not str
			or not self.stage_key
			or type(self.version) is not str
			or not self.version
			or type(self.resources) is not tuple
			or not self.resources
			or any(type(resource) is not RegisteredPromptResource for resource in self.resources)
			or len({resource.name for resource in self.resources}) != len(self.resources)
			or len({resource.key for resource in self.resources}) != len(self.resources)
		):
			raise RuntimeError("Registered prompt set is invalid.")

	#============================================
	@property
	def resource_names(self) -> tuple[str, ...]:
		"""Return the declaration's stable resource ordering."""
		return tuple(resource.name for resource in self.resources)

	#============================================
	def resource_by_key(self, key: str) -> RegisteredPromptResource:
		"""Return one declaration resource by its semantic registry key."""
		if type(key) is not str:
			raise RuntimeError("Registered prompt resource key is invalid.")
		for resource in self.resources:
			if resource.key == key:
				return resource
		raise RuntimeError("Registered prompt resource is unavailable.")

	#============================================
	def identity_dict(self) -> dict[str, object]:
		"""Return the complete provenance identity without prompt prose."""
		return {
			"stage_key": self.stage_key,
			"version": self.version,
			"resources": [
				{
					"key": resource.key,
					"name": resource.name,
					"sha256": resource.sha256,
					"placeholders": list(resource.placeholders),
					"output_schema": resource.output_schema,
					"is_instruction": resource.is_instruction,
				}
				for resource in self.resources
			],
		}

	#============================================
	def identity_sha256(self) -> str:
		"""Return the hash binding resource bytes to renderer-facing metadata."""
		return daily_blog.io_utils.hash_value(self.identity_dict())


def _resource(
	key: str, name: str, sha256: str, placeholders: tuple[str, ...], output_schema: str,
	*, is_instruction: bool = True,
) -> RegisteredPromptResource:
	"""Keep central declarations compact while preserving their exact identities."""
	return RegisteredPromptResource(key, name, sha256, placeholders, output_schema, is_instruction)


REPOSITORY_OUTLINE_PROMPT_SET = RegisteredPromptSet(
	"stage3.repository-outline", "repository-outline-v1", (
		_resource(
			"generator",
			"repository_outline_generator_v1.txt",
			"357014c83af0b08f9151c3d3d7326d6bfaac8cc51eb11b0ed64005af2a13bed1",
			("evidence_json", "replica_id"), "repository-outline-markdown.v1",
		),
		_resource(
			"merger",
			"repository_outline_merger_v1.txt",
			"ae206dcca3bec5428d74819405b2cfd57672b5e6b8db082293a7562db562f52c",
			("evidence_json", "candidate_outlines_json", "replica_id"),
			"repository-outline-markdown.v1",
		),
		_resource(
			"rubric",
			"repository_outline_rubric_v1.md",
			"3efa235111913cb67ab961d5bd75f1754d52887a914b7a19876b9974d3468633",
			(), "rubric-markdown.v1",
		),
		_resource(
			"comparison",
			"repository_outline_comparison_v1.txt",
			"084140fa6d3d103878db8e181d9623b345536c908bdce720d851f228cb5c16ad",
			("rubric", "evidence_json", "candidate_a", "candidate_b"),
			"repository-outline-verdict-json.v1",
		),
		_resource(
			"verdict_repair",
			"repository_outline_verdict_repair_v1.txt",
			"75fab060d5bb1a8bc25a219a896762a06d7284d30e893bfe9426f810c1b2e718",
			("response",), "repository-outline-verdict-json.v1",
		),
	),
)
REPOSITORY_STORY_PROMPT_SET = RegisteredPromptSet(
	"stage4.repository-story", "repository-story-v1", (
		_resource(
			"writer",
			"daily_blog_repository_story_writer_v1.txt",
			"cb851bca50652cf98e7505e259a7574318881a0ee828114214e1499645e5ba42",
			("repo_outline_json", "evidence_json", "replica_id"),
			"repository-story-markdown.v1",
		),
		_resource(
			"editor",
			"daily_blog_repository_story_editor_v1.txt",
			"8d87027b34671ff135bce9e668287637f17f4876f9fa46cad108ada728534edc",
			("repo_outline_json", "evidence_json", "candidate_stories_json", "replica_id"),
			"repository-story-markdown.v1",
		),
		_resource(
			"comparison",
			"daily_blog_repository_story_comparison_v1.txt",
			"1a164dd5dd29c3b34d803c5f77d962a6bfb62131b933ed4ee8c1ee10d722383c",
			(
				"rubric_identity", "rubric", "repo_outline_json", "evidence_json", "candidate_a",
				"candidate_b",
			),
			"repository-story-verdict-json.v1",
		),
		_resource(
			"verdict_repair",
			"daily_blog_repository_story_verdict_repair_v1.txt",
			"ccbc7c3f8c2c55f7a30d9bbbac1e297f99af2d1191373eb2145741071d3f24c7",
			("response",), "repository-story-verdict-json.v1",
		),
	),
)
STORY_RANKING_RESOURCES: tuple[RegisteredPromptResource, ...] = (
		_resource(
			"ranking",
			"daily_blog_story_ranking_v1.txt",
			"e20f4809d5f281b98aa6cc9d750603325edab86594a88e132f08c4e9e64f5e2a",
			("rubric", "stories_json", "repository_outlines_json", "evidence_json", "replica_id"),
			"story-ranking-json.v1",
		),
		_resource(
			"ranking_rubric",
			"daily_blog_story_ranking_rubric_v1.md",
			"d96186dcd4bf0d3382e92be577a7106eabbb9fc9038522502fbbf7ad25e0ab2b",
			(), "rubric-markdown.v1",
		),
		_resource(
			"review",
			"daily_blog_story_ranking_review_v1.txt",
			"cf7f28f2d6af7089ee4f22c118805ebc688365e3e1d9ca47def84f57b5275d99",
			(
				"rubric", "candidate_ranking_json", "stories_json", "repository_outlines_json",
				"evidence_json", "replica_id",
			),
			"story-ranking-review-verdict-json.v1",
		),
		_resource(
			"review_repair",
			"daily_blog_story_ranking_review_repair_v1.txt",
			"e82b58cdfb8ce558771cc8be994d26d741b04342877b2dc14b1a4ed0cfbdfc46",
			("response",), "story-ranking-review-verdict-json.v1",
		),
)
DAILY_OUTLINE_PROMPT_SET = RegisteredPromptSet(
	"stage5.daily-outline", "daily-outline-v1", STORY_RANKING_RESOURCES + (
		_resource(
			"writer",
			"daily_blog_daily_outline_writer_v1.txt",
			"f4a443825640875d74a55772fe5890b15c4a794eab6a1a0ecea8dde336730e4a",
			("ranking_json", "stories_json", "repository_outlines_json", "evidence_json", "replica_id"),
			"daily-outline-markdown.v1",
		),
		_resource(
			"outline_rubric",
			"daily_blog_daily_outline_rubric_v1.md",
			"dfca56e4309b3761ad6c9d55b9beecccdb66cedf954e2e14129687af52070c24",
			(), "rubric-markdown.v1",
		),
		_resource(
			"comparison",
			"daily_blog_daily_outline_comparison_v1.txt",
			"47eb85d8d3855501d1a4e9e3b14f624b841333893d332a4ac15435efb0a486ef",
			(
				"rubric", "stories_json", "repository_outlines_json", "evidence_json", "candidate_a",
				"candidate_b",
			),
			"daily-outline-verdict-json.v1",
		),
		_resource(
			"verdict_repair",
			"daily_blog_daily_outline_verdict_repair_v1.txt",
			"c23be6c118e1144980f4d7139311c943cf608233e7677fa602a3b5605b83b329",
			("response",), "daily-outline-verdict-json.v1",
		),
	),
)
COMPLETE_POST_EDITOR_PROMPT_SET = RegisteredPromptSet(
	"stage6.complete-post-editor", "complete-post-editor-v1", (
		_resource(
			"editor",
			"daily_blog_complete_post_editor_v1.txt",
			"471a5b6063a435b1f1a0efc5fad70b894fe2d6a1b5269055c2572d054dbb33cc",
			("typed_context_json", "candidate_posts_json", "replica_id"),
			"complete-post-markdown.v1",
		),
	),
)
V4_MAKER_PROMPT_SET = RegisteredPromptSet(
	"retained.v4-maker", "daily-blog-prompts-v4", (
		_resource(
			"author",
			"daily_blog_author_v4.txt",
			"258c5a8c6adf6af2eceeb65ff0e498d15c9d10f2ea1d137926e36175d4444e5a",
			("report_date", "run_id", "evidence_json", "examples"), "complete-post-markdown.v4",
		),
		_resource(
			"referee",
			"daily_blog_referee_v4.txt",
			"5702dcacaeb37db36e098394f513c79bf5345924f43f805b8d177d5c3a5d735c",
			("rubric", "evidence_json", "candidate_a", "candidate_b"),
			"complete-post-verdict-json.v4",
		),
		_resource(
			"referee_repair",
			"daily_blog_referee_repair_v4.txt",
			"032d020f13fb3f6c0763b2dbf4832be8c7edeb15bb4068f8906430dfa4b7f64f",
			("response",), "complete-post-verdict-json.v4",
		),
		_resource(
			"rubric",
			"daily_blog_rubric_v4.md",
			"13636a8b18a530f8f89570409c79b123b461ec033bc2013a29a58febc84875c1",
			(), "rubric-markdown.v4",
		),
		_resource(
			"voice_examples",
			"daily_blog_voice_examples_v4.md",
			"c99887758db3d3a93c0f4f07089e2cf9564518f91931a0bfb473cb9b90e52172",
			(), "example-corpus-markdown.v4", is_instruction=False,
		),
	),
)
FINAL_SYNTHESIS_PROMPT_SET = RegisteredPromptSet(
	"stage7.final-synthesis", "final-synthesis-v1", (
		_resource(
			"synthesis",
			"daily_blog_final_synthesis_v1.txt",
			"be1b952d3139e576122cdcd907474215403c5d4b6719a6654787a73ae3463cf6",
			(
				"report_date", "incumbent_post", "alternative_posts", "stage6_review", "rubric",
				"evidence", "provenance",
			),
			"complete-post-markdown.v1",
		),
	),
)
REGISTERED_PROMPT_SETS = types.MappingProxyType({
	prompt_set.stage_key: prompt_set
	for prompt_set in (
		REPOSITORY_OUTLINE_PROMPT_SET,
		REPOSITORY_STORY_PROMPT_SET,
		DAILY_OUTLINE_PROMPT_SET,
		COMPLETE_POST_EDITOR_PROMPT_SET,
		V4_MAKER_PROMPT_SET,
		FINAL_SYNTHESIS_PROMPT_SET,
	)
})

REPOSITORY_OUTLINE_GENERATOR_RESOURCE = REPOSITORY_OUTLINE_PROMPT_SET.resource_by_key("generator")
REPOSITORY_OUTLINE_MERGER_RESOURCE = REPOSITORY_OUTLINE_PROMPT_SET.resource_by_key("merger")
REPOSITORY_OUTLINE_RUBRIC_RESOURCE = REPOSITORY_OUTLINE_PROMPT_SET.resource_by_key("rubric")
REPOSITORY_OUTLINE_COMPARISON_RESOURCE = REPOSITORY_OUTLINE_PROMPT_SET.resource_by_key("comparison")
REPOSITORY_OUTLINE_VERDICT_REPAIR_RESOURCE = REPOSITORY_OUTLINE_PROMPT_SET.resource_by_key("verdict_repair")
REPOSITORY_STORY_WRITER_RESOURCE = REPOSITORY_STORY_PROMPT_SET.resource_by_key("writer")
REPOSITORY_STORY_EDITOR_RESOURCE = REPOSITORY_STORY_PROMPT_SET.resource_by_key("editor")
REPOSITORY_STORY_COMPARISON_RESOURCE = REPOSITORY_STORY_PROMPT_SET.resource_by_key("comparison")
REPOSITORY_STORY_VERDICT_REPAIR_RESOURCE = REPOSITORY_STORY_PROMPT_SET.resource_by_key("verdict_repair")
STORY_RANKING_RESOURCE = DAILY_OUTLINE_PROMPT_SET.resource_by_key("ranking")
STORY_RANKING_RUBRIC_RESOURCE = DAILY_OUTLINE_PROMPT_SET.resource_by_key("ranking_rubric")
STORY_RANKING_REVIEW_RESOURCE = DAILY_OUTLINE_PROMPT_SET.resource_by_key("review")
STORY_RANKING_REVIEW_REPAIR_RESOURCE = DAILY_OUTLINE_PROMPT_SET.resource_by_key("review_repair")
DAILY_OUTLINE_WRITER_RESOURCE = DAILY_OUTLINE_PROMPT_SET.resource_by_key("writer")
DAILY_OUTLINE_RUBRIC_RESOURCE = DAILY_OUTLINE_PROMPT_SET.resource_by_key("outline_rubric")
DAILY_OUTLINE_COMPARISON_RESOURCE = DAILY_OUTLINE_PROMPT_SET.resource_by_key("comparison")
DAILY_OUTLINE_VERDICT_REPAIR_RESOURCE = DAILY_OUTLINE_PROMPT_SET.resource_by_key("verdict_repair")
COMPLETE_POST_EDITOR_RESOURCE = COMPLETE_POST_EDITOR_PROMPT_SET.resource_by_key("editor")
V4_AUTHOR_RESOURCE = V4_MAKER_PROMPT_SET.resource_by_key("author")
V4_REFEREE_RESOURCE = V4_MAKER_PROMPT_SET.resource_by_key("referee")
V4_REFEREE_REPAIR_RESOURCE = V4_MAKER_PROMPT_SET.resource_by_key("referee_repair")
V4_RUBRIC_RESOURCE = V4_MAKER_PROMPT_SET.resource_by_key("rubric")
V4_VOICE_EXAMPLES_RESOURCE = V4_MAKER_PROMPT_SET.resource_by_key("voice_examples")
FINAL_SYNTHESIS_RESOURCE = FINAL_SYNTHESIS_PROMPT_SET.resource_by_key("synthesis")


#============================================
def prompt_set_for_editorial_contract(contract: EditorialContract) -> RegisteredPromptSet:
	"""Return the one registered set that owns a V4 editorial contract's bytes."""
	if type(contract) is not EditorialContract:
		raise RuntimeError("Editorial contract is invalid.")
	prompt_set = V4_MAKER_PROMPT_SET
	if (
		contract.author_template,
		contract.referee_template,
		contract.repair_template,
		contract.rubric,
	) != (
		V4_AUTHOR_RESOURCE.name,
		V4_REFEREE_RESOURCE.name,
		V4_REFEREE_REPAIR_RESOURCE.name,
		V4_RUBRIC_RESOURCE.name,
	):
		raise RuntimeError("Editorial contract resources do not match the registered prompt set.")
	return prompt_set


#============================================
def editorial_contract_resources(
	contract: EditorialContract,
) -> dict[str, RegisteredPromptResource]:
	"""Return canonical V4 resources after binding the contract to its prompt set."""
	prompt_set_for_editorial_contract(contract)
	return {
		"author": V4_AUTHOR_RESOURCE,
		"referee": V4_REFEREE_RESOURCE,
		"repair": V4_REFEREE_REPAIR_RESOURCE,
		"rubric": V4_RUBRIC_RESOURCE,
		"examples": V4_VOICE_EXAMPLES_RESOURCE,
	}

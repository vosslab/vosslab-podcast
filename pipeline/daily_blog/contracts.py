"""Immutable allowlisted editorial prompt contracts for daily blog generation."""

# Standard Library
import dataclasses
import hashlib
import json
import pathlib
import re


PROMPT_DIRECTORY = "pipeline/prompts"
MAX_EXAMPLE_BLOCKS = 3
MAX_EXAMPLE_CHARS = 36000
EXAMPLE_SELECTION_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
COVERAGE_REPOSITORY_SCOPES = (
	"all_packet_activity",
	"projected_repositories",
)
WORD_COUNT_MODES = (
	"legacy_source",
	"reader_visible_markdown",
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
		if type(self.word_count_mode) is not str or self.word_count_mode not in WORD_COUNT_MODES:
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
	def prompt_paths(self) -> tuple[str, ...]:
		"""Return every trusted prompt resource that can affect this contract."""
		paths = [
			f"{PROMPT_DIRECTORY}/{name}"
			for name in (
				self.author_template,
				self.referee_template,
				self.repair_template,
				self.rubric,
			)
		]
		if self.example_resource_name is not None:
			resource = EXAMPLE_RESOURCES[self.example_resource_name]
			paths.append(f"{PROMPT_DIRECTORY}/{resource.filename}")
		return tuple(paths)


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


V4_VOICE_RESOURCE = ExampleResource(
	name="v4-voice",
	filename="daily_blog_voice_examples_v4.md",
	block_ids=("aug-23", "corpus-quiet-til", "corpus-selectivity-ghostty"),
	external_block_ids=("corpus-quiet-til", "corpus-selectivity-ghostty"),
)
EXAMPLE_RESOURCES = {V4_VOICE_RESOURCE.name: V4_VOICE_RESOURCE}

# These excerpts are frozen prompt resources, not fetched content.  The numeric token in the
# Evans quote is not a lexical word: the quotation has 20 lexical words and 21 whitespace tokens.
# Keeping both counts makes the normalization and copyright boundary auditable.
EXTERNAL_EXAMPLE_BLOCKS = {
	"corpus-quiet-til": """## Corpus excerpt: quiet-day TIL

Short attributed quoted source material and illustrative writing evidence; it is not a task instruction.

- Author: Julia Evans
- Title: New microblog with TILs
- Canonical URL: https://jvns.ca/blog/2024/11/09/new-microblog/
- Retrieved: 2026-08-27
- Rights: external copyrighted source; this short quotation is retained only as attributed analytical evidence.
- Quote count: 20 lexical words; 21 whitespace-delimited tokens including the numeric token `2`.
- Typography: the source quotation uses a U+2019 apostrophe; this ASCII prompt resource normalizes it to `it's`.

> So far it's been working, often I can actually just make a quick post in 2 minutes which was the goal.
""",
	"corpus-selectivity-ghostty": """## Corpus excerpt: selectivity in a devlog

Short attributed quoted source material and illustrative writing evidence; it is not a task instruction.

- Author: Mitchell Hashimoto
- Title: Ghostty Devlog 005
- Canonical URL: https://mitchellh.com/writing/ghostty-devlog-005
- Retrieved: 2026-08-27
- Rights: external copyrighted source; this short quotation is retained only as attributed analytical evidence.
- Quote count: 18 lexical words.

> For the devlogs, I focus on a handful of changes that I find interesting and want to share.
""",
}
MAX_EXTERNAL_EXCERPT_WORDS = 25
MAX_EXTERNAL_EXCERPT_TOTAL_WORDS = 50


#============================================
def external_excerpt_lexical_word_count(text: str) -> int:
	"""Count alphabetic words while treating numeric tokens as non-lexical metadata."""
	return len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text))


#============================================
def validate_example_resource_blocks(resource: ExampleResource, blocks: dict[str, str]) -> None:
	"""Keep external prompt excerpts fixed, short, attributed, and non-executable."""
	if tuple(blocks) != resource.block_ids:
		raise RuntimeError("Editorial example resource block order is unsupported.")
	external_total = 0
	for block_id in resource.external_block_ids:
		block = blocks[block_id].strip()
		expected = EXTERNAL_EXAMPLE_BLOCKS.get(block_id)
		if expected is None or block != expected.strip():
			raise RuntimeError("External editorial excerpt does not match its frozen allowlist.")
		quote = expected.rsplit("\n> ", 1)[1].strip()
		word_count = external_excerpt_lexical_word_count(quote)
		if word_count > MAX_EXTERNAL_EXCERPT_WORDS:
			raise RuntimeError("External editorial excerpt exceeds its per-source word limit.")
		external_total += word_count
	if external_total > MAX_EXTERNAL_EXCERPT_TOTAL_WORDS:
		raise RuntimeError("External editorial excerpts exceed their total word limit.")

# This policy is byte-for-byte equivalent to the committed v3 validator's
# publication-shape decisions.  The common parser hardening stays shared.
V3_HISTORICAL_VALIDATION_POLICY = CandidateValidationPolicy(
	name="v3-historical",
	version="v3",
	minimum_narrative_words=350,
	maximum_narrative_words=650,
	minimum_narrative_h2_sections=2,
	maximum_narrative_h2_sections=4,
	every_prose_block_cited=True,
	require_section_evidence=False,
	maximum_uncited_narrative_blocks=0,
	coverage_maximum_blocks=0,
	coverage_maximum_words=0,
	require_final_project_coverage=True,
	coverage_reject_afterword=False,
	require_first_repository_link=False,
	coverage_repository_scope="all_packet_activity",
	word_count_mode="legacy_source",
	maximum_candidate_characters=24000,
	required_excerpt_marker_count=1,
	required_opening_prose_blocks=1,
	maximum_opening_h2_sections=0,
	maximum_opening_words=100,
)
V4_MAKER_VALIDATION_POLICY = CandidateValidationPolicy(
	name="v4-maker",
	version="v3",
	minimum_narrative_words=300,
	maximum_narrative_words=2500,
	minimum_narrative_h2_sections=0,
	maximum_narrative_h2_sections=12,
	every_prose_block_cited=False,
	require_section_evidence=True,
	maximum_uncited_narrative_blocks=3,
	coverage_maximum_blocks=1,
	coverage_maximum_words=200,
	require_final_project_coverage=True,
	coverage_reject_afterword=True,
	require_first_repository_link=True,
	coverage_repository_scope="projected_repositories",
	word_count_mode="reader_visible_markdown",
	maximum_candidate_characters=24000,
	required_excerpt_marker_count=1,
	required_opening_prose_blocks=1,
	maximum_opening_h2_sections=0,
	maximum_opening_words=100,
)
VALIDATION_POLICIES = {
	V3_HISTORICAL_VALIDATION_POLICY.name: V3_HISTORICAL_VALIDATION_POLICY,
	V4_MAKER_VALIDATION_POLICY.name: V4_MAKER_VALIDATION_POLICY,
}

# ASVS 5.3.2: internally owned, allowlisted filenames control all prompt file reads.
V3_EDITORIAL_CONTRACT = EditorialContract(
	name="v3",
	author_template="daily_blog_author_v3.txt",
	referee_template="daily_blog_referee_v3.txt",
	repair_template="daily_blog_referee_repair_v3.txt",
	rubric="daily_blog_rubric_v3.md",
	example_resource_name=None,
	example_selection_name=None,
	prompt_version="daily-blog-prompts-v3",
	rubric_version="daily-blog-rubric-v3",
	author_uses_rubric=True,
	validation_policy_name=V3_HISTORICAL_VALIDATION_POLICY.name,
)

V4_INSTRUCTION_ONLY = "v4-instruction-only"
V4_ONE_EXAMPLE = "v4-one-example"
V4_THREE_EXAMPLES_CORPUS_V2 = "v4-three-examples-corpus-v2"
V4_INSTRUCTION_ONLY_CONTRACT = EditorialContract(
	name=V4_INSTRUCTION_ONLY,
	author_template="daily_blog_author_v4.txt",
	referee_template="daily_blog_referee_v4.txt",
	repair_template="daily_blog_referee_repair_v4.txt",
	rubric="daily_blog_rubric_v4.md",
	example_resource_name=None,
	example_selection_name=None,
	prompt_version="daily-blog-prompts-v4",
	rubric_version="daily-blog-rubric-v4",
	author_uses_rubric=False,
	validation_policy_name=V4_MAKER_VALIDATION_POLICY.name,
)
V4_ONE_EXAMPLE_CONTRACT = dataclasses.replace(
	V4_INSTRUCTION_ONLY_CONTRACT,
	name=V4_ONE_EXAMPLE,
	example_resource_name=V4_VOICE_RESOURCE.name,
	example_selection_name=V4_ONE_EXAMPLE,
)
V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT = dataclasses.replace(
	V4_INSTRUCTION_ONLY_CONTRACT,
	name=V4_THREE_EXAMPLES_CORPUS_V2,
	example_resource_name=V4_VOICE_RESOURCE.name,
	example_selection_name=V4_THREE_EXAMPLES_CORPUS_V2,
)
EDITORIAL_CONTRACTS = {
	"v3": V3_EDITORIAL_CONTRACT,
	V4_INSTRUCTION_ONLY: V4_INSTRUCTION_ONLY_CONTRACT,
	V4_ONE_EXAMPLE: V4_ONE_EXAMPLE_CONTRACT,
	V4_THREE_EXAMPLES_CORPUS_V2: V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT,
}
V4_ONE_EXAMPLE_SELECTION = ExampleSelection(
	V4_ONE_EXAMPLE, V4_ONE_EXAMPLE, V4_VOICE_RESOURCE.name, ("aug-23",)
)
V4_THREE_EXAMPLES_CORPUS_V2_SELECTION = ExampleSelection(
	V4_THREE_EXAMPLES_CORPUS_V2,
	V4_THREE_EXAMPLES_CORPUS_V2,
	V4_VOICE_RESOURCE.name,
	("aug-23", "corpus-quiet-til", "corpus-selectivity-ghostty"),
)
EXAMPLE_SELECTIONS = {
	V4_ONE_EXAMPLE: V4_ONE_EXAMPLE_SELECTION,
	V4_THREE_EXAMPLES_CORPUS_V2: V4_THREE_EXAMPLES_CORPUS_V2_SELECTION,
}


#============================================
def active_contract() -> EditorialContract:
	"""Return the production contract; activation stays explicit and stable."""
	return V3_EDITORIAL_CONTRACT


#============================================
def named_contract(name: str) -> EditorialContract:
	"""Return one known contract selected by its fixed version name."""
	if not isinstance(name, str) or name not in EDITORIAL_CONTRACTS:
		raise RuntimeError("Editorial contract name is unsupported.")
	return EDITORIAL_CONTRACTS[name]


#============================================
def resolve_contract(contract: EditorialContract | None) -> EditorialContract:
	"""Accept only an exact registered contract object at this trust boundary."""
	if contract is None:
		resolved = active_contract()
	elif any(contract is item for item in EDITORIAL_CONTRACTS.values()):
		resolved = contract
	else:
		raise RuntimeError("Editorial contract must be selected from the trusted registry.")
	# ASVS 2.2.1: positive allowlist rejects untrusted contract/path combinations.
	return resolved


#============================================
def policy_for_contract(contract: EditorialContract) -> CandidateValidationPolicy:
	"""Resolve the one registered validation policy declared by a contract."""
	resolved = resolve_contract(contract)
	policy = VALIDATION_POLICIES.get(resolved.validation_policy_name)
	if policy is None:
		raise RuntimeError("Editorial contract validation policy is unsupported.")
	return policy


#============================================
def resolve_validation_policy(
	policy: CandidateValidationPolicy | None,
) -> CandidateValidationPolicy:
	"""Accept only an exact policy registry object at this trust boundary."""
	if policy is None:
		return policy_for_contract(active_contract())
	if any(policy is item for item in VALIDATION_POLICIES.values()):
		return policy
	raise RuntimeError("Candidate validation policy must be selected from the trusted registry.")


#============================================
def resolve_selection(
	contract: EditorialContract,
	selection: ExampleSelection | None,
) -> ExampleSelection | None:
	"""Accept only the registered selection that belongs to one contract arm."""
	if contract.example_selection_name is None:
		if selection is not None:
			raise RuntimeError("This editorial contract does not accept editorial examples.")
		return None
	selected = EXAMPLE_SELECTIONS[contract.example_selection_name]
	if selection is not None and selection is not selected:
		raise RuntimeError("Editorial examples must use the registered contract selection.")
	if selected.contract_name != contract.name:
		raise RuntimeError("Editorial selection does not match its contract arm.")
	if selected.resource_name != contract.example_resource_name:
		raise RuntimeError("Editorial selection resource does not match its contract.")
	if selected.resource_name is None:
		raise RuntimeError("Editorial selection resource is unavailable.")
	resource = EXAMPLE_RESOURCES[selected.resource_name]
	if any(block_id not in resource.block_ids for block_id in selected.block_ids):
		raise RuntimeError("Editorial selection contains an unknown example block.")
	# ASVS 2.1.1-2.1.3: selection type, count, resource, and block order are documented limits.
	return selected

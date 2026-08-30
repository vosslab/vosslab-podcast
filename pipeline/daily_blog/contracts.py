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


def validate_example_resource_blocks(resource: ExampleResource, blocks: dict[str, str]) -> None:
	"""Require parsed resource blocks to preserve the registered order."""
	if tuple(blocks) != resource.block_ids:
		raise RuntimeError("Editorial example resource block order is unsupported.")

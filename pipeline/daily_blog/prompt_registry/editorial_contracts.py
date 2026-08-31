"""V4 editorial contract declarations and contract-scoped resolution."""

# Standard Library
import re
import types

# local repo modules
import daily_blog.prompt_registry.definitions


V4_VOICE_RESOURCE = daily_blog.prompt_registry.definitions.ExampleResource(
	name="v4-voice",
	filename="daily_blog_voice_examples_v4.md",
	block_ids=("aug-23", "corpus-quiet-til", "corpus-selectivity-ghostty"),
	external_block_ids=("corpus-quiet-til", "corpus-selectivity-ghostty"),
)
EXAMPLE_RESOURCES = types.MappingProxyType({V4_VOICE_RESOURCE.name: V4_VOICE_RESOURCE})
_EXAMPLE_RESOURCES = EXAMPLE_RESOURCES

EXTERNAL_EXAMPLE_BLOCKS = types.MappingProxyType({
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
})
MAX_EXTERNAL_EXCERPT_WORDS = 25
MAX_EXTERNAL_EXCERPT_TOTAL_WORDS = 50
_EXTERNAL_EXAMPLE_BLOCKS = EXTERNAL_EXAMPLE_BLOCKS
_MAX_EXTERNAL_EXCERPT_WORDS = MAX_EXTERNAL_EXCERPT_WORDS
_MAX_EXTERNAL_EXCERPT_TOTAL_WORDS = MAX_EXTERNAL_EXCERPT_TOTAL_WORDS

V4_MAKER_VALIDATION_POLICY = daily_blog.prompt_registry.definitions.CandidateValidationPolicy(
	name="v4-maker", version="v3", minimum_narrative_words=300,
	maximum_narrative_words=2500, minimum_narrative_h2_sections=0,
	maximum_narrative_h2_sections=12, every_prose_block_cited=False,
	require_section_evidence=True, maximum_uncited_narrative_blocks=3,
	coverage_maximum_blocks=1, coverage_maximum_words=200,
	require_final_project_coverage=True, coverage_reject_afterword=True,
	require_first_repository_link=True, coverage_repository_scope="projected_repositories",
	word_count_mode="reader_visible_markdown", maximum_candidate_characters=24000,
	required_excerpt_marker_count=1, required_opening_prose_blocks=1,
	maximum_opening_h2_sections=0, maximum_opening_words=100,
)
VALIDATION_POLICIES = types.MappingProxyType({V4_MAKER_VALIDATION_POLICY.name: V4_MAKER_VALIDATION_POLICY})
_VALIDATION_POLICIES = VALIDATION_POLICIES

V4_THREE_EXAMPLES_CORPUS_V2 = "v4-three-examples-corpus-v2"
V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT = daily_blog.prompt_registry.definitions.EditorialContract(
	name=V4_THREE_EXAMPLES_CORPUS_V2, author_template="daily_blog_author_v4.txt",
	referee_template="daily_blog_referee_v4.txt", repair_template="daily_blog_referee_repair_v4.txt",
	rubric="daily_blog_rubric_v4.md", example_resource_name=V4_VOICE_RESOURCE.name,
	example_selection_name=V4_THREE_EXAMPLES_CORPUS_V2, prompt_version="daily-blog-prompts-v4",
	rubric_version="daily-blog-rubric-v4", author_uses_rubric=False,
	validation_policy_name=V4_MAKER_VALIDATION_POLICY.name,
)
EDITORIAL_CONTRACTS = types.MappingProxyType({
	V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT.name: V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT,
})
PRODUCTION_EDITORIAL_CONTRACT = V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT
_EDITORIAL_CONTRACTS = EDITORIAL_CONTRACTS
_PRODUCTION_EDITORIAL_CONTRACT = PRODUCTION_EDITORIAL_CONTRACT
V4_THREE_EXAMPLES_CORPUS_V2_SELECTION = daily_blog.prompt_registry.definitions.ExampleSelection(
	V4_THREE_EXAMPLES_CORPUS_V2, V4_THREE_EXAMPLES_CORPUS_V2,
	V4_VOICE_RESOURCE.name, ("aug-23", "corpus-quiet-til", "corpus-selectivity-ghostty"),
)
EXAMPLE_SELECTIONS = types.MappingProxyType({
	V4_THREE_EXAMPLES_CORPUS_V2: V4_THREE_EXAMPLES_CORPUS_V2_SELECTION,
})
_EXAMPLE_SELECTIONS = EXAMPLE_SELECTIONS


def prompt_paths(contract: daily_blog.prompt_registry.definitions.EditorialContract) -> tuple[str, ...]:
	"""Return every trusted prompt resource that can affect one registry contract."""
	contract = resolve_contract(contract)
	paths = [
		f"{daily_blog.prompt_registry.definitions.PROMPT_DIRECTORY}/{name}"
		for name in (contract.author_template, contract.referee_template, contract.repair_template, contract.rubric)
	]
	if contract.example_resource_name is not None:
		paths.append(f"{daily_blog.prompt_registry.definitions.PROMPT_DIRECTORY}/{EXAMPLE_RESOURCES[contract.example_resource_name].filename}")
	return tuple(paths)


def active_contract() -> daily_blog.prompt_registry.definitions.EditorialContract:
	"""Return the sole production contract owned by the publication pipeline."""
	return PRODUCTION_EDITORIAL_CONTRACT


def is_production_contract(contract: daily_blog.prompt_registry.definitions.EditorialContract) -> bool:
	"""Return whether a trusted contract is the current publication owner."""
	return resolve_contract(contract) is PRODUCTION_EDITORIAL_CONTRACT


def resolve_contract(
	contract: daily_blog.prompt_registry.definitions.EditorialContract | None,
) -> daily_blog.prompt_registry.definitions.EditorialContract:
	"""Accept only an exact registered contract object at this trust boundary."""
	if contract is None:
		return active_contract()
	if any(contract is item for item in EDITORIAL_CONTRACTS.values()):
		return contract
	raise RuntimeError("Editorial contract must be selected from the trusted registry.")


def contract_template_names() -> frozenset[str]:
	"""Return the instruction-template names owned by canonical contracts."""
	return frozenset(
		name for contract in EDITORIAL_CONTRACTS.values()
		for name in (contract.author_template, contract.referee_template, contract.repair_template, contract.rubric)
	)


def policy_for_contract(
	contract: daily_blog.prompt_registry.definitions.EditorialContract,
) -> daily_blog.prompt_registry.definitions.CandidateValidationPolicy:
	"""Resolve the one registered validation policy declared by a contract."""
	policy = VALIDATION_POLICIES.get(resolve_contract(contract).validation_policy_name)
	if policy is None:
		raise RuntimeError("Editorial contract validation policy is unsupported.")
	return policy


def resolve_validation_policy(
	policy: daily_blog.prompt_registry.definitions.CandidateValidationPolicy | None,
) -> daily_blog.prompt_registry.definitions.CandidateValidationPolicy:
	"""Accept only an exact policy registry object at this trust boundary."""
	if policy is None:
		return policy_for_contract(active_contract())
	if any(policy is item for item in VALIDATION_POLICIES.values()):
		return policy
	raise RuntimeError("Candidate validation policy must be selected from the trusted registry.")


def resolve_selection(
	contract: daily_blog.prompt_registry.definitions.EditorialContract,
	selection: daily_blog.prompt_registry.definitions.ExampleSelection | None,
) -> daily_blog.prompt_registry.definitions.ExampleSelection | None:
	"""Accept only the registered selection belonging to one contract arm."""
	contract = resolve_contract(contract)
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
	return selected


def example_resources() -> tuple[daily_blog.prompt_registry.definitions.ExampleResource, ...]:
	"""List the canonical example resources owned by this registry."""
	return tuple(EXAMPLE_RESOURCES.values())


def resolve_example_resource(
	resource: str | daily_blog.prompt_registry.definitions.ExampleResource,
) -> daily_blog.prompt_registry.definitions.ExampleResource:
	"""Resolve a name or accept only the exact canonical example resource."""
	if isinstance(resource, str):
		try:
			return EXAMPLE_RESOURCES[resource]
		except KeyError as error:
			raise RuntimeError("Editorial example resource is unsupported.") from error
	if not isinstance(resource, daily_blog.prompt_registry.definitions.ExampleResource):
		raise RuntimeError("Editorial example resource is unsupported.")
	try:
		canonical = EXAMPLE_RESOURCES[resource.name]
	except KeyError as error:
		raise RuntimeError("Editorial example resource is unsupported.") from error
	if resource is not canonical:
		raise RuntimeError("Editorial example resource must be the registered object.")
	return canonical


def external_excerpt_lexical_word_count(text: str) -> int:
	"""Count alphabetic words while treating numeric tokens as non-lexical metadata."""
	return len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text))


def validate_example_resource_blocks(
	resource: daily_blog.prompt_registry.definitions.ExampleResource, blocks: dict[str, str],
) -> None:
	"""Validate one registry resource's concrete external evidence blocks."""
	resource = resolve_example_resource(resource)
	daily_blog.prompt_registry.definitions.validate_example_resource_block_order(resource, blocks)
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

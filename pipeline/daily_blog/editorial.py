"""Current prompt snapshots, author rendering, and advisory referee parsing."""

# Standard Library
import re
import json
import weakref
import dataclasses

# local repo modules
import daily_blog.schema
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.editorial_contracts
import daily_blog.prompt_registry.loader
import daily_blog.io_utils
import podlib.prompt_loader


MAX_REFEREE_RESPONSE_CHARS = 4000
MAX_REFEREE_REASON_CHARS = 500
class EditorialBlockedError(RuntimeError):
	"""Trusted prompt material cannot fit the configured model boundary."""


class RefereeVerdictParseError(RuntimeError):
	"""A referee response does not satisfy the bounded verdict contract."""


EXAMPLE_MARKER_RE = re.compile(
	r"(?m)^<!-- editorial-example: ([a-z0-9][a-z0-9_-]{0,63}) -->\n"
	r"(.*?)^<!-- /editorial-example -->$",
	re.DOTALL,
)
UNSAFE_EXAMPLE_CONTENT_RE = re.compile(
	r"(?im)(?:^|\n)\s*(?:ignore|disregard|override)\b[^\n]*(?:instruction|prompt|message)\b"
	r"|(?:^|\n)\s*(?:system|developer|user)\s*:"
	r"|\{[a-z][a-z0-9_]{0,63}\}"
)


#============================================
def _example_resource_blocks(
	resource: daily_blog.prompt_registry.definitions.ExampleResource,
	text: str,
) -> dict[str, str]:
	"""Parse one fixed example resource without treating its content as instructions."""
	if "<!-- evidence:" in text or "## Project coverage" in text:
		raise RuntimeError("Editorial examples may not contain provenance or coverage controls.")
	if re.search(r"(?m)^---\s*$", text):
		raise RuntimeError("Editorial examples may not contain YAML fences or front matter.")
	if UNSAFE_EXAMPLE_CONTENT_RE.search(text):
		raise RuntimeError("Editorial examples contain unsafe instruction-like content.")
	matches = list(EXAMPLE_MARKER_RE.finditer(text))
	if len(matches) != len(resource.block_ids):
		raise RuntimeError("Editorial example resource markers are incomplete or nested.")
	blocks: dict[str, str] = {}
	for match in matches:
		block_id = match.group(1)
		body = match.group(2)
		if "<!-- editorial-example:" in body or "<!-- /editorial-example -->" in body:
			raise RuntimeError("Editorial example resource markers may not be nested.")
		if block_id in blocks:
			raise RuntimeError("Editorial example resource block IDs must be unique.")
		blocks[block_id] = body
	daily_blog.prompt_registry.editorial_contracts.validate_example_resource_blocks(resource, blocks)
	return blocks


_SNAPSHOT_TOKEN = object()


@dataclasses.dataclass(frozen=True)
class PromptContractSnapshot:
	"""One immutable read of all prompts and selected examples for an editorial run."""

	contract: daily_blog.prompt_registry.definitions.EditorialContract
	selection: daily_blog.prompt_registry.definitions.ExampleSelection | None
	template_names: tuple[tuple[str, str], ...]
	templates: tuple[tuple[str, str], ...]
	example_resource_bytes: bytes
	example_bytes: bytes
	validation_policy_name: str = ""
	validation_policy_version: str = ""
	validation_policy_sha256: str = ""
	integrity_sha256: str = ""
	_origin: object = dataclasses.field(repr=False, compare=False, default=None)
	prompt_set: daily_blog.prompt_registry.loader.LoadedPromptSet | None = dataclasses.field(
		repr=False, compare=False, default=None,
	)

	#============================================
	def template_dict(self) -> dict[str, str]:
		"""Return a detached lookup view of frozen template text."""
		values = dict(self.templates)
		return values


_SNAPSHOT_REGISTRY: weakref.WeakValueDictionary[
	int, PromptContractSnapshot
] = weakref.WeakValueDictionary()


#============================================
def _selected_examples(
	contract: daily_blog.prompt_registry.definitions.EditorialContract,
	selection: daily_blog.prompt_registry.definitions.ExampleSelection | None,
	loaded_prompt_set: daily_blog.prompt_registry.loader.LoadedPromptSet,
) -> tuple[str, bytes, bytes, daily_blog.prompt_registry.definitions.ExampleSelection | None]:
	"""Read and select exact trusted example blocks once in registered order."""
	resolved_selection = daily_blog.prompt_registry.editorial_contracts.resolve_selection(contract, selection)
	if resolved_selection is None:
		return "", b"", b"", resolved_selection
	if resolved_selection.resource_name is None:
		raise RuntimeError("Editorial selection resource is unavailable.")
	resource = daily_blog.prompt_registry.editorial_contracts.resolve_example_resource(
		resolved_selection.resource_name,
	)
	resource_ref = daily_blog.prompt_registry.definitions.editorial_contract_resources(contract)["examples"]
	if resource.filename != resource_ref.name:
		raise RuntimeError("Editorial example resource does not match the registered prompt set.")
	text = loaded_prompt_set.text(resource_ref)
	contents = loaded_prompt_set.contents(resource_ref)
	blocks = _example_resource_blocks(resource, text)
	selected_text = "\n\n".join(blocks[block_id] for block_id in resolved_selection.block_ids)
	selected_bytes = selected_text.encode("utf-8")
	if len(selected_text) > daily_blog.prompt_registry.definitions.MAX_EXAMPLE_CHARS:
		raise RuntimeError("Selected editorial examples exceed their character limit.")
	# ASVS 1.5.2: only allowlisted example blocks are parsed from trusted plain text.
	return selected_text, selected_bytes, contents, resolved_selection


#============================================
def load_prompt_contract_snapshot(
	contract: daily_blog.prompt_registry.definitions.EditorialContract | None = None,
	selection: daily_blog.prompt_registry.definitions.ExampleSelection | None = None,
	prompt_set: daily_blog.prompt_registry.loader.LoadedPromptSet | None = None,
) -> PromptContractSnapshot:
	"""Load one immutable contract snapshot for identity and all prompt renderings."""
	resolved = daily_blog.prompt_registry.editorial_contracts.resolve_contract(contract)
	registered_prompt_set = daily_blog.prompt_registry.definitions.prompt_set_for_editorial_contract(resolved)
	loaded_prompt_set = daily_blog.prompt_registry.loader.resolve_loaded_prompt_set(
		prompt_set, registered_prompt_set,
	)
	resources = daily_blog.prompt_registry.definitions.editorial_contract_resources(resolved)
	templates = {
		name: loaded_prompt_set.text(resource)
		for name, resource in resources.items()
		if name != "examples"
	}
	examples, example_bytes, resource_bytes, resolved_selection = _selected_examples(
		resolved,
		selection,
		loaded_prompt_set,
	)
	templates["examples"] = examples
	template_names = tuple(sorted({
		"author": resolved.author_template,
		"referee": resolved.referee_template,
		"repair": resolved.repair_template,
		"rubric": resolved.rubric,
	}.items()))
	frozen_templates = tuple(sorted(templates.items()))
	integrity = _snapshot_integrity(
		resolved,
		resolved_selection,
		template_names,
		frozen_templates,
		bytes(resource_bytes),
		bytes(example_bytes),
		daily_blog.prompt_registry.editorial_contracts.policy_for_contract(resolved),
	)
	snapshot = PromptContractSnapshot(
		resolved,
		resolved_selection,
		template_names,
		frozen_templates,
		bytes(resource_bytes),
		bytes(example_bytes),
		daily_blog.prompt_registry.editorial_contracts.policy_for_contract(resolved).name,
		daily_blog.prompt_registry.editorial_contracts.policy_for_contract(resolved).version,
		daily_blog.prompt_registry.editorial_contracts.policy_for_contract(resolved).sha256(),
		integrity,
		_SNAPSHOT_TOKEN,
		loaded_prompt_set,
	)
	_SNAPSHOT_REGISTRY[id(snapshot)] = snapshot
	validate_snapshot(snapshot)
	validate_prompt_templates(snapshot=snapshot)
	return snapshot


#============================================
def _snapshot_integrity(
	contract: daily_blog.prompt_registry.definitions.EditorialContract,
	selection: daily_blog.prompt_registry.definitions.ExampleSelection | None,
	template_names: tuple[tuple[str, str], ...],
	templates: tuple[tuple[str, str], ...],
	resource_bytes: bytes,
	example_bytes: bytes,
	policy: daily_blog.prompt_registry.definitions.CandidateValidationPolicy,
) -> str:
	"""Return a canonical tamper-evident binding for every snapshot payload field."""
	selection_value = None
	if selection is not None:
		selection_value = {
			"name": selection.name,
			"contract_name": selection.contract_name,
			"resource_name": selection.resource_name,
			"block_ids": list(selection.block_ids),
		}
	payload = {
		"contract_name": contract.name,
		"selection": selection_value,
		"template_names": list(template_names),
		"templates": list(templates),
		"resource_sha256": daily_blog.io_utils.sha256_bytes(resource_bytes),
		"examples_sha256": daily_blog.io_utils.sha256_bytes(example_bytes),
		"candidate_validation": {
			"name": policy.name,
			"version": policy.version,
			"sha256": policy.sha256(),
		},
	}
	digest = daily_blog.io_utils.hash_value(payload)
	return digest


#============================================
def validate_snapshot(snapshot: PromptContractSnapshot) -> PromptContractSnapshot:
	"""Verify that a snapshot came from one registered contract-resource read."""
	if not isinstance(snapshot, PromptContractSnapshot) or snapshot._origin is not _SNAPSHOT_TOKEN:
		raise RuntimeError("Editorial prompt snapshot is not trusted.")
	if _SNAPSHOT_REGISTRY.get(id(snapshot)) is not snapshot:
		raise RuntimeError("Editorial prompt snapshot was not issued by the trusted factory.")
	contract = daily_blog.prompt_registry.editorial_contracts.resolve_contract(snapshot.contract)
	if contract is not snapshot.contract:
		raise RuntimeError("Editorial prompt snapshot contract is not the registered object.")
	selection = daily_blog.prompt_registry.editorial_contracts.resolve_selection(contract, snapshot.selection)
	if selection is not snapshot.selection:
		raise RuntimeError("Editorial prompt snapshot selection is not the registered object.")
	policy = daily_blog.prompt_registry.editorial_contracts.policy_for_contract(contract)
	registered_prompt_set = daily_blog.prompt_registry.definitions.prompt_set_for_editorial_contract(contract)
	loaded_prompt_set = daily_blog.prompt_registry.loader.resolve_loaded_prompt_set(
		snapshot.prompt_set, registered_prompt_set,
	)
	resources = daily_blog.prompt_registry.definitions.editorial_contract_resources(contract)
	if (
		snapshot.validation_policy_name != policy.name
		or snapshot.validation_policy_version != policy.version
		or snapshot.validation_policy_sha256 != policy.sha256()
	):
		raise RuntimeError("Editorial prompt snapshot validation policy is incoherent.")
	expected_names = tuple(sorted({
		"author": contract.author_template,
		"referee": contract.referee_template,
		"repair": contract.repair_template,
		"rubric": contract.rubric,
	}.items()))
	if snapshot.template_names != expected_names:
		raise RuntimeError("Editorial prompt snapshot template resources are incoherent.")
	templates = snapshot.template_dict()
	if set(templates) != {"author", "referee", "repair", "rubric", "examples"}:
		raise RuntimeError("Editorial prompt snapshot template mapping is incoherent.")
	for name in ("author", "referee", "repair", "rubric"):
		if templates[name] != loaded_prompt_set.text(resources[name]):
			raise RuntimeError("Editorial prompt snapshot template bytes do not match the registry.")
	if selection is None:
		if snapshot.example_resource_bytes or snapshot.example_bytes or templates["examples"]:
			raise RuntimeError("The v3 prompt snapshot contains unexpected examples.")
	else:
		if selection.resource_name is None:
			raise RuntimeError("Editorial prompt snapshot example resource is unavailable.")
		resource = daily_blog.prompt_registry.editorial_contracts.resolve_example_resource(
			selection.resource_name,
		)
		if resource.filename != resources["examples"].name:
			raise RuntimeError("Editorial prompt snapshot example resource is incoherent.")
		if snapshot.example_resource_bytes != loaded_prompt_set.contents(resources["examples"]):
			raise RuntimeError("Editorial prompt snapshot example resource bytes do not match the registry.")
		try:
			resource_text = snapshot.example_resource_bytes.decode("utf-8")
		except UnicodeDecodeError as error:
			raise RuntimeError("Editorial prompt snapshot examples are not UTF-8.") from error
		blocks = _example_resource_blocks(resource, resource_text)
		expected_text = "\n\n".join(blocks[block_id] for block_id in selection.block_ids)
		if (
			templates["examples"] != expected_text
			or snapshot.example_bytes != expected_text.encode("utf-8")
		):
			raise RuntimeError("Editorial prompt snapshot example bytes do not match its selection.")
	expected_integrity = _snapshot_integrity(
		contract,
		selection,
		snapshot.template_names,
		snapshot.templates,
		snapshot.example_resource_bytes,
		snapshot.example_bytes,
		policy,
	)
	if snapshot.integrity_sha256 != expected_integrity:
		raise RuntimeError("Editorial prompt snapshot integrity binding is invalid.")
	# ASVS 2.2.1: every consumer verifies registered contract, resource, and selected bytes.
	return snapshot


#============================================
def resolve_snapshot(
	contract: daily_blog.prompt_registry.definitions.EditorialContract | None,
	selection: daily_blog.prompt_registry.definitions.ExampleSelection | None,
	snapshot: PromptContractSnapshot | None,
) -> PromptContractSnapshot:
	"""Load or bind one snapshot without accepting conflicting loose selectors."""
	if snapshot is None:
		resolved = load_prompt_contract_snapshot(contract, selection)
	else:
		resolved = validate_snapshot(snapshot)
		if contract is not None and contract is not resolved.contract:
			raise RuntimeError("Editorial contract conflicts with the supplied prompt snapshot.")
		if selection is not None and selection is not resolved.selection:
			raise RuntimeError("Editorial selection conflicts with the supplied prompt snapshot.")
	return resolved


#============================================
def resolve_run_snapshot(
	contract: daily_blog.prompt_registry.definitions.EditorialContract | None,
	snapshot: PromptContractSnapshot | None,
) -> PromptContractSnapshot:
	"""Resolve one run snapshot while preserving the named-run mismatch boundary."""
	if snapshot is None:
		resolved = resolve_snapshot(contract, None, None)
	else:
		resolved = validate_snapshot(snapshot)
		if contract is not None:
			selected_contract = daily_blog.prompt_registry.editorial_contracts.resolve_contract(contract)
			if resolved.contract is not selected_contract:
				raise RuntimeError("Editorial contract does not match the supplied prompt snapshot.")
	return resolved


#============================================
def validate_prompt_templates(
	contract: daily_blog.prompt_registry.definitions.EditorialContract | None = None,
	selection: daily_blog.prompt_registry.definitions.ExampleSelection | None = None,
	snapshot: PromptContractSnapshot | None = None,
) -> dict[str, str]:
	"""Validate positive phrasing and explicit output contracts before any LLM call."""
	snapshot = resolve_snapshot(contract, selection, snapshot)
	resolved = snapshot.contract
	templates = snapshot.template_dict()
	for name, text in templates.items():
		if name == "examples":
			continue
		podlib.prompt_loader.validate_positive_instructions(text, name)
	if "{evidence_json}" not in templates["author"]:
		raise RuntimeError("Author prompt must declare bounded evidence context.")
	if "## Output contract" not in templates["author"]:
		raise RuntimeError("Author prompt must declare its output contract.")
	if resolved.author_uses_rubric:
		if "{rubric}" not in templates["author"]:
			raise RuntimeError("Rubric-author prompt must declare its rubric slot.")
	elif "{rubric}" in templates["author"] or "{examples}" not in templates["author"]:
		raise RuntimeError("Exemplar-author prompt must declare only its examples slot.")
	if "{candidate_a}" not in templates["referee"] or "{candidate_b}" not in templates["referee"]:
		raise RuntimeError("Referee prompt must declare both anonymous candidates.")
	if "## Output contract" not in templates["referee"]:
		raise RuntimeError("Referee prompt must declare its output contract.")
	return templates


#============================================
def prompt_contract_identity(
	contract: daily_blog.prompt_registry.definitions.EditorialContract | None = None,
	selection: daily_blog.prompt_registry.definitions.ExampleSelection | None = None,
	snapshot: PromptContractSnapshot | None = None,
) -> dict[str, object]:
	"""Return the exact content identity that owns editorial cache reuse."""
	snapshot = resolve_snapshot(contract, selection, snapshot)
	resolved = snapshot.contract
	templates = validate_prompt_templates(snapshot=snapshot)
	identity: dict[str, object] = {
		"contract_name": resolved.name,
		"prompt_version": resolved.prompt_version,
		"rubric_version": resolved.rubric_version,
		"candidate_validation": {
			"name": snapshot.validation_policy_name,
			"version": snapshot.validation_policy_version,
			"sha256": snapshot.validation_policy_sha256,
		},
		"templates": {
			name: daily_blog.io_utils.sha256_text(text)
			for name, text in sorted(templates.items())
			if name != "examples"
		},
	}
	if snapshot.selection is not None:
		# ASVS 1.5.2: retain exact ordered example bytes in the cache identity.
		identity["examples"] = {
			"name": snapshot.selection.name,
			"blocks": list(snapshot.selection.block_ids),
			"sha256": daily_blog.io_utils.sha256_bytes(snapshot.example_bytes),
		}
	return identity


#============================================
def render_author_prompt(
	projection: daily_blog.schema.EditorialProjection,
	run_id: str,
	limit: int,
	contract: daily_blog.prompt_registry.definitions.EditorialContract | None = None,
	selection: daily_blog.prompt_registry.definitions.ExampleSelection | None = None,
	snapshot: PromptContractSnapshot | None = None,
) -> str:
	"""Render one identical author prompt for both isolated roles."""
	snapshot = resolve_snapshot(contract, selection, snapshot)
	templates = validate_prompt_templates(snapshot=snapshot)
	prompt = templates["author"].format(
		report_date=projection.report_date,
		run_id=run_id,
		rubric=templates["rubric"],
		examples=templates.get("examples", ""),
		evidence_json=projection.render_context(),
	)
	if len(prompt) > limit:
		raise EditorialBlockedError(
			f"The complete author prompt requires {len(prompt)} characters "
			+ f"and exceeds its {limit} limit."
		)
	return prompt


#============================================
def _bounded_referee_reason(reason: str) -> str:
	"""Bound explanatory metadata without changing the referee's control fields."""
	normalized = reason.strip()
	if not normalized:
		raise RuntimeError("Referee reason must be non-empty.")
	if len(normalized) <= MAX_REFEREE_REASON_CHARS:
		return normalized
	return normalized[: MAX_REFEREE_REASON_CHARS - 3].rstrip() + "..."


#============================================
def parse_referee_verdict(response: str, allowed_labels: set[str]) -> dict:
	"""Parse one exact structured referee verdict."""
	if len(response) > MAX_REFEREE_RESPONSE_CHARS:
		raise RefereeVerdictParseError(
			"Referee response exceeds the structured response budget."
		)
	try:
		value = json.loads(response.strip())
	except json.JSONDecodeError as error:
		raise RefereeVerdictParseError("Referee verdict is not valid JSON.") from error
	if not isinstance(value, dict):
		raise RefereeVerdictParseError("Referee verdict must be one JSON object.")
	for key in ("winner", "reason", "evidence_quality", "confidence"):
		if key not in value:
			raise RefereeVerdictParseError(f"Referee verdict is missing {key}.")
	if not isinstance(value["winner"], str):
		raise RefereeVerdictParseError("Referee winner must be text.")
	if not isinstance(value["reason"], str):
		raise RefereeVerdictParseError("Referee reason must be text.")
	if not isinstance(value["evidence_quality"], str):
		raise RefereeVerdictParseError("Referee evidence_quality must be text.")
	winner = value["winner"]
	try:
		reason = _bounded_referee_reason(value["reason"])
	except RuntimeError as error:
		raise RefereeVerdictParseError(str(error)) from error
	evidence_quality = value["evidence_quality"]
	confidence = value["confidence"]
	if winner not in allowed_labels | {"NONE"}:
		raise RefereeVerdictParseError("Referee winner is unavailable or unsupported.")
	if evidence_quality not in {"high", "medium", "low"}:
		raise RefereeVerdictParseError("Referee evidence_quality is unsupported.")
	if type(confidence) not in {int, float} or not 0 <= confidence <= 1:
		raise RefereeVerdictParseError(
			"Referee confidence must be a number from zero through one."
		)
	verdict = {
		"winner": winner,
		"reason": reason,
		"evidence_quality": evidence_quality,
		"confidence": float(confidence),
	}
	return verdict


#============================================

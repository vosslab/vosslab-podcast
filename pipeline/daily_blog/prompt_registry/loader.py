"""Validated loading and issuance for registered prompt assets."""

# Standard Library
import dataclasses

# local repo modules
import daily_blog.io_utils
import daily_blog.prompt_resources
import daily_blog.prompt_registry.definitions


@dataclasses.dataclass(frozen=True, init=False)
class LoadedPromptResource:
	"""One byte-validated resource issued only by this module's loader."""

	_declaration: daily_blog.prompt_registry.definitions.RegisteredPromptResource = dataclasses.field(repr=False)
	_text_value: str = dataclasses.field(repr=False)
	_contents_value: bytes = dataclasses.field(repr=False)

	#============================================
	def __init__(self) -> None:
		"""Prevent callers from constructing a usable loaded resource."""
		raise RuntimeError("Loaded prompt resources are issued only by the registry loader.")

	#============================================
	def _require_issued(self) -> None:
		"""Reject a copied or forged object before exposing loaded data."""
		if _ISSUED_LOADED_PROMPT_RESOURCES.get(id(self)) is not self:
			raise RuntimeError("Loaded prompt resource was not issued by the registry loader.")

	#============================================
	@property
	def declaration(self) -> daily_blog.prompt_registry.definitions.RegisteredPromptResource:
		"""Return the canonical declaration for this issued resource."""
		self._require_issued()
		return self._declaration


@dataclasses.dataclass(frozen=True, init=False)
class LoadedPromptSet:
	"""A trusted loaded view of one canonical prompt declaration."""

	_declaration: daily_blog.prompt_registry.definitions.RegisteredPromptSet = dataclasses.field(repr=False)
	_loaded_resources: tuple[LoadedPromptResource, ...] = dataclasses.field(repr=False)

	#============================================
	def __init__(self) -> None:
		"""Prevent callers from constructing a usable loaded prompt set."""
		raise RuntimeError("Loaded prompt sets are issued only by the registry loader.")

	#============================================
	def _require_issued(self) -> None:
		"""Reject a copied or forged view before every public operation."""
		if _ISSUED_LOADED_PROMPT_SETS.get(id(self)) is not self:
			raise RuntimeError("Loaded prompt set was not issued by the registry loader.")

	#============================================
	@property
	def declaration(self) -> daily_blog.prompt_registry.definitions.RegisteredPromptSet:
		"""Return the canonical declaration for this issued loaded view."""
		self._require_issued()
		return self._declaration

	#============================================
	def resource(
		self, ref: daily_blog.prompt_registry.definitions.RegisteredPromptResource,
	) -> LoadedPromptResource:
		"""Return one resource only when its canonical declaration belongs here."""
		self._require_issued()
		if type(ref) is not daily_blog.prompt_registry.definitions.RegisteredPromptResource:
			raise RuntimeError("Loaded prompt resource reference is invalid.")
		for loaded in self._loaded_resources:
			if ref is loaded.declaration:
				return loaded
		raise RuntimeError("Loaded prompt resource does not belong to this prompt set.")

	#============================================
	def text(self, ref: daily_blog.prompt_registry.definitions.RegisteredPromptResource) -> str:
		"""Return validated renderer text for one canonical resource reference."""
		self._require_issued()
		return self.resource(ref)._text_value

	#============================================
	def contents(self, ref: daily_blog.prompt_registry.definitions.RegisteredPromptResource) -> bytes:
		"""Return the exact validated bytes for one canonical resource reference."""
		self._require_issued()
		return self.resource(ref)._contents_value

	#============================================
	def render(
		self, ref: daily_blog.prompt_registry.definitions.RegisteredPromptResource, values: dict[str, str],
	) -> str:
		"""Render one resource after exact placeholder-key validation."""
		self._require_issued()
		resource = self.resource(ref)
		if (
			type(values) is not dict
			or set(values) != set(resource.declaration.placeholders)
			or any(type(key) is not str or type(value) is not str for key, value in values.items())
		):
			raise RuntimeError("Loaded prompt render values do not match the declared placeholders.")
		return resource._text_value.format(**values)

	#============================================
	def legacy_identity_dict(self) -> dict[str, object]:
		"""Return a current stage payload when its identity is resource-only."""
		self._require_issued()
		if self._declaration is daily_blog.prompt_registry.definitions.V4_MAKER_PROMPT_SET:
			raise RuntimeError("V4 editorial identity is owned by the editorial contract boundary.")
		resources = {
			resource.declaration.name: daily_blog.io_utils.sha256_bytes(resource._contents_value)
			for resource in sorted(self._loaded_resources, key=lambda item: item.declaration.name)
		}
		pinned_resources = {
			resource.name: resource.sha256
			for resource in sorted(self._declaration.resources, key=lambda item: item.name)
		}
		integrity_sha256 = daily_blog.io_utils.hash_value({
			"version": self._declaration.version,
			"pinned_resources": pinned_resources,
			"resources": resources,
		})
		return {"version": self._declaration.version, "resources": resources, "integrity_sha256": integrity_sha256}

_ISSUED_LOADED_PROMPT_RESOURCES: dict[int, LoadedPromptResource] = {}
_ISSUED_LOADED_PROMPT_SETS: dict[int, LoadedPromptSet] = {}


#============================================
def registered_prompt_sets() -> tuple[daily_blog.prompt_registry.definitions.RegisteredPromptSet, ...]:
	"""Return every canonical set in stable declaration order."""
	return tuple(daily_blog.prompt_registry.definitions.REGISTERED_PROMPT_SETS.values())


#============================================
def lookup_prompt_set(stage_key: str) -> daily_blog.prompt_registry.definitions.RegisteredPromptSet:
	"""Resolve one known stage key without accepting caller-owned declarations."""
	if type(stage_key) is not str:
		raise RuntimeError("Registered prompt-set key is invalid.")
	try:
		return daily_blog.prompt_registry.definitions.REGISTERED_PROMPT_SETS[stage_key]
	except KeyError as error:
		raise RuntimeError("Registered prompt set is unavailable.") from error


#============================================
def resolve_prompt_set(
	value: str | daily_blog.prompt_registry.definitions.RegisteredPromptSet,
) -> daily_blog.prompt_registry.definitions.RegisteredPromptSet:
	"""Accept a key or only the exact canonical prompt-set object."""
	if type(value) is str:
		return lookup_prompt_set(value)
	if type(value) is daily_blog.prompt_registry.definitions.RegisteredPromptSet and any(
		value is item for item in daily_blog.prompt_registry.definitions.REGISTERED_PROMPT_SETS.values()
	):
		return value
	raise RuntimeError("Prompt set must be selected from the trusted registry.")


#============================================
def _issue_loaded_resource(
	declaration: daily_blog.prompt_registry.definitions.RegisteredPromptResource, text: str, contents: bytes,
) -> LoadedPromptResource:
	"""Create and retain one resource instance that public callers cannot forge."""
	value = object.__new__(LoadedPromptResource)
	object.__setattr__(value, "_declaration", declaration)
	object.__setattr__(value, "_text_value", text)
	object.__setattr__(value, "_contents_value", contents)
	_ISSUED_LOADED_PROMPT_RESOURCES[id(value)] = value
	return value


#============================================
def _issue_loaded_prompt_set(
	declaration: daily_blog.prompt_registry.definitions.RegisteredPromptSet,
	resources: tuple[LoadedPromptResource, ...],
) -> LoadedPromptSet:
	"""Create and retain one exact issued view for its canonical declaration."""
	value = object.__new__(LoadedPromptSet)
	object.__setattr__(value, "_declaration", declaration)
	object.__setattr__(value, "_loaded_resources", resources)
	_ISSUED_LOADED_PROMPT_SETS[id(value)] = value
	return value


#============================================
def load_prompt_set(
	value: str | daily_blog.prompt_registry.definitions.RegisteredPromptSet,
) -> LoadedPromptSet:
	"""Issue one trusted loaded view through the safe prompt-resource loader."""
	prompt_set = resolve_prompt_set(value)
	for issued in _ISSUED_LOADED_PROMPT_SETS.values():
		if issued._declaration is prompt_set:
			return issued
	allowlist = frozenset(prompt_set.resource_names)
	loaded: list[LoadedPromptResource] = []
	for resource in prompt_set.resources:
		if resource.is_instruction:
			text, contents = daily_blog.prompt_resources.load_allowlisted_instruction_prompt_with_bytes(
				resource.name, allowlist, f"registered prompt set {prompt_set.stage_key}",
			)
		else:
			with open(daily_blog.prompt_resources.prompt_resource_path(resource.name), "rb") as handle:
				contents = handle.read()
			try:
				text = contents.decode("utf-8")
			except UnicodeDecodeError as error:
				raise RuntimeError(f"Registered plain prompt resource is not UTF-8: {resource.name}") from error
			if not contents.strip():
				raise RuntimeError(f"Registered plain prompt resource is empty: {resource.name}")
		found = tuple(daily_blog.prompt_registry.definitions.PROMPT_PLACEHOLDER_RE.findall(text))
		if set(found) != set(resource.placeholders) or len(found) != len(set(found)):
			raise RuntimeError(f"Registered prompt placeholders do not match: {resource.name}")
		if "{" in daily_blog.prompt_registry.definitions.PROMPT_PLACEHOLDER_RE.sub("", text) or "}" in daily_blog.prompt_registry.definitions.PROMPT_PLACEHOLDER_RE.sub("", text):
			raise RuntimeError(f"Registered prompt braces are invalid: {resource.name}")
		if daily_blog.io_utils.sha256_bytes(contents) != resource.sha256:
			raise RuntimeError(f"Registered prompt bytes do not match the pinned asset: {resource.name}")
		loaded.append(_issue_loaded_resource(resource, text, contents))
	return _issue_loaded_prompt_set(prompt_set, tuple(loaded))


#============================================
def resolve_loaded_prompt_set(
	value: LoadedPromptSet | None,
	declaration: str | daily_blog.prompt_registry.definitions.RegisteredPromptSet,
) -> LoadedPromptSet:
	"""Resolve a trusted issued view for one exact canonical declaration."""
	prompt_set = resolve_prompt_set(declaration)
	if value is None:
		return load_prompt_set(prompt_set)
	if type(value) is not LoadedPromptSet:
		raise RuntimeError("Loaded prompt set must be issued by the trusted registry loader.")
	if value.declaration is not prompt_set:
		raise RuntimeError("Loaded prompt set does not match the trusted registry declaration.")
	return value

"""Deeply immutable JSON-compatible contract values."""

# Standard Library
import dataclasses
import collections.abc


@dataclasses.dataclass(frozen=True)
class FrozenMapping(collections.abc.Mapping[str, object]):
	"""Deeply immutable JSON-object storage with deterministic key order."""

	_entries: tuple[tuple[str, object], ...]

	#============================================
	@classmethod
	def create(cls, value: collections.abc.Mapping[str, object]) -> "FrozenMapping":
		"""Copy and recursively freeze one JSON object."""
		entries = []
		for key in sorted(value):
			if not isinstance(key, str):
				raise RuntimeError("Frozen mapping keys must be text.")
			entries.append((key, _freeze_json_value(value[key])))
		return cls(tuple(entries))

	#============================================
	def __getitem__(self, key: str) -> object:
		"""Return one immutable value by key."""
		for candidate, value in self._entries:
			if candidate == key:
				return value
		raise KeyError(key)

	#============================================
	def __iter__(self) -> collections.abc.Iterator[str]:
		"""Iterate keys in deterministic order."""
		return (key for key, _value in self._entries)

	#============================================
	def __len__(self) -> int:
		"""Return the number of keys."""
		return len(self._entries)

	#============================================
	def to_dict(self) -> dict:
		"""Return a detached mutable JSON-object serialization."""
		return {key: _thaw_json_value(value) for key, value in self._entries}


#============================================
def _freeze_json_value(value: object) -> object:
	"""Recursively freeze one JSON-compatible value."""
	if isinstance(value, collections.abc.Mapping):
		return FrozenMapping.create(value)
	if isinstance(value, (list, tuple)):
		return tuple(_freeze_json_value(item) for item in value)
	return value


#============================================
def _thaw_json_value(value: object) -> object:
	"""Return a detached JSON-compatible value from immutable storage."""
	if isinstance(value, FrozenMapping):
		return value.to_dict()
	if isinstance(value, tuple):
		return [_thaw_json_value(item) for item in value]
	return value

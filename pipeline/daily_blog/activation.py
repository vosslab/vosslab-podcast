"""Sealed producer activation for the accepted maker editorial contract."""

# Standard Library
import dataclasses
import json
import pathlib
import re

# local repo modules
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.editorial_contracts
import daily_blog.editorial
import daily_blog.io_utils


ACTIVATION_SCHEMA_VERSION = "vosslab.daily-blog.maker-activation.v1"
ACTIVATION_FILENAME = "daily_blog_maker_activation.json"
ACTIVATION_ID_RE = re.compile(r"^daily-blog-maker-activation-[0-9a-f]{64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ACCEPTED_F4_EVIDENCE = {
	"review_evidence_id": "prompt-experiment-review-evidence-fa097dd766ef0a9e89b87a91bb1b64758a41a1367ba5db0e2234f028a4f49265",
	"review_evidence_report_sha256": "e0bba9af5700bdcb362fc010f95ae0837b8101b2a8bfae733e97e58e35c52aff",
	"attestation_id": "prompt-experiment-attestation-6cfc303e23e8af22e53c50d5c01741600938e3d14ff14e880635cf9197d0aac3",
	"attestation_report_sha256": "c10de02fd488473cf561687d65f1ae4bdbec2ab46066ec6bb52c454bd478f19b",
	"review_contract_sha256": "cf3a55fadc7247344904a1d44cffd4a0d1c461eba6e756c1b6d9e109cacd845c",
	"f4_accepted": True,
}


@dataclasses.dataclass(frozen=True)
class MakerActivation:
	"""One checked-in, content-addressed receipt authorizing production v4."""

	path: pathlib.Path
	receipt: dict[str, object]

	@property
	def activation_id(self) -> str:
		"""Return the validated immutable activation identity."""
		value = self.receipt["activation_id"]
		if not isinstance(value, str):
			raise RuntimeError("Daily-blog maker activation is invalid.")
		return value

	@property
	def contract(self) -> daily_blog.prompt_registry.definitions.EditorialContract:
		"""Return the exact selected production contract."""
		return daily_blog.prompt_registry.editorial_contracts.V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT


#============================================
def _strict_json(path: pathlib.Path) -> dict[str, object]:
	"""Read one checked-in receipt without accepting ambiguous JSON objects."""
	try:
		contents = path.read_bytes()
		value = json.loads(
			contents.decode("utf-8"),
			object_pairs_hook=_unique_object,
			parse_constant=_reject_constant,
		)
	except (OSError, UnicodeDecodeError, ValueError) as error:
		raise RuntimeError("Daily-blog maker activation is unavailable or malformed.") from error
	if not isinstance(value, dict):
		raise RuntimeError("Daily-blog maker activation is unavailable or malformed.")
	return value


#============================================
def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
	"""Reject duplicate receipt keys before semantic validation."""
	value = {}
	for key, item in pairs:
		if key in value:
			raise ValueError("Duplicate JSON key.")
		value[key] = item
	return value


#============================================
def _reject_constant(value: str) -> None:
	"""Reject non-standard JSON numbers in the signed receipt."""
	raise ValueError("Unsupported JSON constant: " + value)


#============================================
def _receipt_payload(receipt: dict[str, object]) -> dict[str, object]:
	"""Return the content-addressed receipt body without its derived ID."""
	return {key: value for key, value in receipt.items() if key != "activation_id"}


#============================================
def _activation_id(receipt: dict[str, object]) -> str:
	"""Derive the stable activation ID from canonical receipt content."""
	return "daily-blog-maker-activation-" + daily_blog.io_utils.hash_value(
		_receipt_payload(receipt)
	)


#============================================
def _require_sha256(value: object) -> str:
	"""Return one fixed lowercase digest or fail closed."""
	if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
		raise RuntimeError("Daily-blog maker activation is invalid.")
	return value


#============================================
def _expected_prompt_identity() -> dict[str, object]:
	"""Load the current exact v4-three prompt snapshot identity."""
	snapshot = daily_blog.editorial.load_prompt_contract_snapshot(
		daily_blog.prompt_registry.editorial_contracts.V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT
	)
	return daily_blog.editorial.prompt_contract_identity(snapshot=snapshot)


#============================================
def _validate_receipt(receipt: dict[str, object]) -> None:
	"""Verify receipt integrity and exact immutable production selection."""
	required = {
		"schema_version",
		"activation_id",
		"selected_contract",
		"editorial_prompt_contract",
		"editorial_prompt_contract_sha256",
		"candidate_validation",
		"f4_evidence",
	}
	if set(receipt) != required or receipt.get("schema_version") != ACTIVATION_SCHEMA_VERSION:
		raise RuntimeError("Daily-blog maker activation is invalid.")
	activation_id = receipt.get("activation_id")
	if not isinstance(activation_id, str) or not ACTIVATION_ID_RE.fullmatch(activation_id):
		raise RuntimeError("Daily-blog maker activation is invalid.")
	if activation_id != _activation_id(receipt):
		raise RuntimeError("Daily-blog maker activation integrity is invalid.")
	contract = daily_blog.prompt_registry.editorial_contracts.V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT
	if receipt.get("selected_contract") != contract.name:
		raise RuntimeError("Daily-blog maker activation does not select the production contract.")
	prompt_identity = receipt.get("editorial_prompt_contract")
	if not isinstance(prompt_identity, dict) or prompt_identity != _expected_prompt_identity():
		raise RuntimeError("Daily-blog maker activation prompt snapshot is invalid.")
	if receipt.get("editorial_prompt_contract_sha256") != daily_blog.io_utils.hash_value(prompt_identity):
		raise RuntimeError("Daily-blog maker activation prompt identity is invalid.")
	policy = daily_blog.prompt_registry.editorial_contracts.policy_for_contract(contract)
	if receipt.get("candidate_validation") != {
		"name": policy.name,
		"version": policy.version,
		"sha256": policy.sha256(),
	}:
		raise RuntimeError("Daily-blog maker activation validation policy is invalid.")
	f4 = receipt.get("f4_evidence")
	if not isinstance(f4, dict) or set(f4) != {
		"review_evidence_id",
		"review_evidence_report_sha256",
		"attestation_id",
		"attestation_report_sha256",
		"review_contract_sha256",
		"f4_accepted",
	}:
		raise RuntimeError("Daily-blog maker activation F4 evidence is invalid.")
	if f4 != ACCEPTED_F4_EVIDENCE:
		raise RuntimeError("Daily-blog maker activation F4 evidence is invalid.")


#============================================
def _receipt_path(repository_root: str | None = None) -> pathlib.Path:
	"""Locate the sole tracked activation receipt beneath the producer root."""
	root = repository_root or daily_blog.io_utils.repository_root(__file__)
	return pathlib.Path(root) / ACTIVATION_FILENAME


#============================================
def load_maker_activation(repository_root: str | None = None) -> MakerActivation:
	"""Load the tracked receipt; production never reopens private F4 evidence."""
	path = _receipt_path(repository_root)
	receipt = _strict_json(path)
	_validate_receipt(receipt)
	return MakerActivation(path, receipt)

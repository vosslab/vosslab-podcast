"""Validated publication bundle creation at one stable path per report date."""

# Standard Library
import dataclasses
import datetime
import os
import re

# local repo modules
import daily_blog.schema
import daily_blog.repository_contracts
import daily_blog.io_utils
import daily_blog.artifacts
import daily_blog.json_contracts
import daily_blog.publication_storage
import daily_blog.publication_source_safety
import daily_blog.publication_admission
import daily_blog.publication_surface_contract


GENERATOR_CONTRACT_VERSION = "vosslab.daily-blog.generator-source.v1"
GENERATOR_SUPPORT_PATHS = (
	"pipeline/podlib/pipeline_settings.py",
	"pipeline/podlib/prompt_loader.py",
	"daily_blog_maker_activation.json",
)
_IDENTITY_TOKEN = object()
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ACTIVATION_ID_RE = re.compile(r"^daily-blog-maker-activation-[0-9a-f]{64}$")
SEALED_BUNDLE_TRANSFER_SCHEMA_VERSION = "vosslab.daily-blog.bundle-transfer.v1"
SEALED_BUNDLE_TRANSFER_MAGIC = (SEALED_BUNDLE_TRANSFER_SCHEMA_VERSION + "\n").encode("ascii")
MAX_TRANSFER_BYTES = daily_blog.publication_storage.MAX_EVIDENCE_BYTES
_CORE_TRANSFER_PATHS = frozenset({
	"bundle.json", "evidence.json", "repository_roster.json", "editorial_projection.json",
	"publication_surface.json", "post.md",
})


@dataclasses.dataclass(frozen=True)
class SealedBundleTransferEntry:
	"""One bounded, hash-bound byte member of the publisher handoff."""

	path: str
	contents: bytes
	sha256: str

	#============================================
	def __post_init__(self) -> None:
		"""Reject non-canonical names, bounds, and digests at the handoff boundary."""
		maximum = _transfer_path_limit(self.path)
		if type(self.contents) is not bytes or len(self.contents) > maximum:
			raise RuntimeError("Sealed bundle transfer entry exceeds its schema envelope.")
		if type(self.sha256) is not str or self.sha256 != daily_blog.io_utils.sha256_bytes(self.contents):
			raise RuntimeError("Sealed bundle transfer entry checksum is invalid.")


@dataclasses.dataclass(frozen=True)
class SealedBundleTransfer:
	"""The sole byte snapshot that a producer may hand to a publisher."""

	report_date: str
	bundle_sha256: str
	entries: tuple[SealedBundleTransferEntry, ...]

	#============================================
	def __post_init__(self) -> None:
		"""Require one exact, sorted, bounded transfer envelope."""
		try:
			if datetime.date.fromisoformat(self.report_date).isoformat() != self.report_date:
				raise ValueError
		except (TypeError, ValueError) as error:
			raise RuntimeError("Sealed bundle transfer report date is invalid.") from error
		if type(self.bundle_sha256) is not str or SHA256_RE.fullmatch(self.bundle_sha256) is None:
			raise RuntimeError("Sealed bundle transfer bundle checksum is invalid.")
		if type(self.entries) is not tuple or not self.entries:
			raise RuntimeError("Sealed bundle transfer entries are invalid.")
		if any(type(entry) is not SealedBundleTransferEntry for entry in self.entries):
			raise RuntimeError("Sealed bundle transfer entries are invalid.")
		paths = tuple(entry.path for entry in self.entries)
		if paths != tuple(sorted(paths)) or len(set(paths)) != len(paths) or not _CORE_TRANSFER_PATHS <= set(paths):
			raise RuntimeError("Sealed bundle transfer entries are incomplete or unordered.")
		if self._encoded_size() > MAX_TRANSFER_BYTES:
			raise RuntimeError("Sealed bundle transfer exceeds its aggregate schema envelope.")

	#============================================
	def _header_bytes(self) -> bytes:
		"""Build the exact canonical header whose size participates in the cap."""
		header = {
			"schema_version": SEALED_BUNDLE_TRANSFER_SCHEMA_VERSION,
			"report_date": self.report_date,
			"bundle_sha256": self.bundle_sha256,
			"entries": [
				{"path": entry.path, "size": len(entry.contents), "sha256": entry.sha256}
				for entry in self.entries
			],
		}
		header_bytes = daily_blog.io_utils.canonical_json_bytes(header)
		if len(header_bytes) > daily_blog.publication_storage.MAX_JSON_BYTES:
			raise RuntimeError("Sealed bundle transfer header exceeds its schema envelope.")
		return header_bytes

	#============================================
	def _encoded_size(self) -> int:
		"""Measure the exact pre-read stdin envelope before allocating its body."""
		return len(SEALED_BUNDLE_TRANSFER_MAGIC) + 8 + len(self._header_bytes()) + sum(
			len(entry.contents) for entry in self.entries
		)

	#============================================
	def to_bytes(self) -> bytes:
		"""Encode the canonical binary stdin envelope without reopening a path."""
		header_bytes = self._header_bytes()
		if self._encoded_size() > MAX_TRANSFER_BYTES:
			raise RuntimeError("Sealed bundle transfer exceeds its aggregate schema envelope.")
		return SEALED_BUNDLE_TRANSFER_MAGIC + len(header_bytes).to_bytes(8, "big") + header_bytes + b"".join(
			entry.contents for entry in self.entries
		)


#============================================
def _transfer_path_limit(path: object) -> int:
	"""Return the single supported storage envelope for one transfer path."""
	if type(path) is not str:
		raise RuntimeError("Sealed bundle transfer path is invalid.")
	if path == "evidence.json":
		return daily_blog.publication_storage.MAX_EVIDENCE_BYTES
	if path in {
		"bundle.json", "repository_roster.json", "editorial_projection.json", "publication_surface.json",
	}:
		return daily_blog.publication_storage.MAX_JSON_BYTES
	if path == "post.md":
		return daily_blog.publication_storage.MAX_POST_BYTES
	daily_blog.schema.validate_bundle_asset_path(path)
	return daily_blog.publication_storage.MAX_ASSET_BYTES


@dataclasses.dataclass(frozen=True, init=False)
class PublicationIdentity:
	"""A deeply frozen producer identity that is valid only through the factory."""

	revision: str
	_contracts: daily_blog.json_contracts.FrozenMapping
	_editorial_prompt_contract: daily_blog.json_contracts.FrozenMapping
	_activation_receipt: daily_blog.json_contracts.FrozenMapping

	#============================================
	def __init__(
		self, token: object, revision: str, contracts: daily_blog.json_contracts.FrozenMapping,
		prompt_contract: daily_blog.json_contracts.FrozenMapping,
		activation_receipt: daily_blog.json_contracts.FrozenMapping,
	) -> None:
		"""Reject direct construction so all public instances are cross-bound."""
		if token is not _IDENTITY_TOKEN:
			raise RuntimeError("Publication identities must be created by publication_identity().")
		object.__setattr__(self, "revision", revision)
		object.__setattr__(self, "_contracts", contracts)
		object.__setattr__(self, "_editorial_prompt_contract", prompt_contract)
		object.__setattr__(self, "_activation_receipt", activation_receipt)

	#============================================
	def contracts_dict(self) -> dict[str, object]:
		"""Return a detached contracts value for serialization or comparison."""
		return self._contracts.to_dict()

	#============================================
	def prompt_contract_dict(self) -> dict[str, object]:
		"""Return a detached prompt-contract value for serialization or comparison."""
		return self._editorial_prompt_contract.to_dict()

	#============================================
	def activation_receipt_dict(self) -> dict[str, object]:
		"""Return a detached activation receipt for serialization or comparison."""
		return self._activation_receipt.to_dict()


#============================================
def publication_identity(
	repository_root: str,
	settings_path: str | None,
	*,
	prompt_paths: tuple[str, ...],
	contracts: dict[str, object],
	editorial_prompt_contract: dict[str, object] | None,
	activation_receipt: dict[str, object] | None,
) -> PublicationIdentity:
	"""Seal caller-validated publication identity without importing editorial owners."""
	validated_contracts = _validate_contract_identity(contracts)
	revision = generator_revision(
		repository_root,
		settings_path,
		prompt_paths=prompt_paths,
		contracts=validated_contracts,
	)
	prompt_contract = _validate_prompt_contract_identity(editorial_prompt_contract)
	activation = _validate_activation_receipt_binding(
		activation_receipt, prompt_contract, validated_contracts,
	)
	return PublicationIdentity(
		_IDENTITY_TOKEN, revision, daily_blog.json_contracts.FrozenMapping.create(validated_contracts),
		daily_blog.json_contracts.FrozenMapping.create(prompt_contract),
		daily_blog.json_contracts.FrozenMapping.create(activation),
	)


#============================================
def _validate_contract_identity(value: object) -> dict[str, object]:
	"""Copy the primitive contract fields required by the bundle-v9 manifest."""
	base_fields = {
		"evidence_schema", "editorial_projection_schema", "prompt_version",
		"rubric_version", "candidate_validation",
	}
	if not isinstance(value, dict) or set(value) not in (
		base_fields, base_fields | {"publication_source_safety"},
	):
		raise RuntimeError("Publication contract identity is invalid.")
	candidate_validation = value["candidate_validation"]
	if not isinstance(candidate_validation, dict) or set(candidate_validation) != {
		"name", "version", "sha256"
	}:
		raise RuntimeError("Publication validation-policy identity is invalid.")
	if not all(isinstance(value[key], str) and value[key] for key in (
		"evidence_schema", "editorial_projection_schema", "prompt_version", "rubric_version"
	)) or not all(isinstance(candidate_validation[key], str) and candidate_validation[key] for key in candidate_validation) or not SHA256_RE.fullmatch(candidate_validation["sha256"]):
		raise RuntimeError("Publication contract identity is invalid.")
	result = {
		"evidence_schema": value["evidence_schema"],
		"editorial_projection_schema": value["editorial_projection_schema"],
		"prompt_version": value["prompt_version"],
		"rubric_version": value["rubric_version"],
		"candidate_validation": dict(candidate_validation),
	}
	if "publication_source_safety" in value and value["publication_source_safety"] != daily_blog.publication_source_safety.policy_identity():
		raise RuntimeError("Publication source-safety policy identity is invalid.")
	result["publication_source_safety"] = daily_blog.publication_source_safety.policy_identity()
	return result


#============================================
def _validate_prompt_contract_identity(value: object) -> dict[str, object]:
	"""Copy the primitive prompt identity required by every production bundle."""
	if not isinstance(value, dict):
		raise RuntimeError("Publication prompt contract identity is invalid.")
	candidate = value.get("candidate_validation")
	if not isinstance(candidate, dict) or set(candidate) != {"name", "version", "sha256"}:
		raise RuntimeError("Publication prompt contract validation policy is invalid.")
	if not all(isinstance(candidate[key], str) and candidate[key] for key in candidate):
		raise RuntimeError("Publication prompt contract validation policy is invalid.")
	if not SHA256_RE.fullmatch(candidate["sha256"]):
		raise RuntimeError("Publication prompt contract validation policy is invalid.")
	try:
		frozen = daily_blog.json_contracts.FrozenMapping.create(value)
		exported = frozen.to_dict()
		exported_candidate = exported["candidate_validation"]
		if not isinstance(exported_candidate, dict):
			raise RuntimeError("Publication prompt contract identity is invalid.")
	except (TypeError, RuntimeError) as error:
		raise RuntimeError("Publication prompt contract identity is invalid.") from error
	return exported


#============================================
def _validate_activation_receipt_binding(
	value: object, prompt_contract: dict[str, object], contracts: dict[str, object],
) -> dict[str, object]:
	"""Require the activation receipt to bind the prompt and validation policy."""
	if not isinstance(value, dict) or set(value) != {
		"activation_id", "editorial_prompt_contract_sha256",
	}:
		raise RuntimeError("Publication activation receipt binding is invalid.")
	activation_id = value["activation_id"]
	prompt_sha = value["editorial_prompt_contract_sha256"]
	if not isinstance(activation_id, str) or ACTIVATION_ID_RE.fullmatch(activation_id) is None:
		raise RuntimeError("Publication activation receipt binding is invalid.")
	if not isinstance(prompt_sha, str) or SHA256_RE.fullmatch(prompt_sha) is None:
		raise RuntimeError("Publication activation receipt binding is invalid.")
	if prompt_sha != daily_blog.io_utils.hash_value(prompt_contract):
		raise RuntimeError("Publication activation receipt does not bind the prompt contract.")
	if prompt_contract["candidate_validation"] != contracts["candidate_validation"]:
		raise RuntimeError("Publication prompt contract does not bind the validation policy.")
	return {"activation_id": activation_id, "editorial_prompt_contract_sha256": prompt_sha}


#============================================
def _require_identity(value: object) -> PublicationIdentity:
	"""Return a valid-by-construction identity before any bundle I/O."""
	if type(value) is not PublicationIdentity:
		raise RuntimeError("Publication bundles require a sealed publication identity.")
	if not SHA256_RE.fullmatch(value.revision):
		raise RuntimeError("Generator source identity must be lowercase SHA-256 text.")
	_validate_activation_receipt_binding(
		value.activation_receipt_dict(), value.prompt_contract_dict(), value.contracts_dict(),
	)
	return value


#============================================
def validate_bundle_identity_fields(value: object) -> None:
	"""Validate sealed bundle identity fields without importing editorial owners."""
	if not isinstance(value, dict):
		raise RuntimeError("Publication bundle identity is invalid.")
	contracts = _validate_contract_identity(value.get("contracts"))
	prompt_contract = _validate_prompt_contract_identity(value.get("editorial_prompt_contract"))
	_validate_activation_receipt_binding(value.get("maker_activation"), prompt_contract, contracts)


#============================================
def _generator_contract_paths(
	repository_root: str,
	settings_path: str | None,
	prompt_paths: tuple[str, ...],
) -> list[tuple[str, str]]:
	"""Return stable logical names and physical files for the output-affecting contract."""
	root = os.path.abspath(repository_root)
	daily_blog_root = os.path.join(root, "pipeline", "daily_blog")
	if not os.path.isdir(daily_blog_root):
		raise RuntimeError("Generator daily-blog source directory is unavailable.")
	paths = []
	for current_root, _directories, files in os.walk(daily_blog_root):
		for name in sorted(files):
			if not name.endswith(".py"):
				continue
			physical_path = os.path.join(current_root, name)
			logical_path = os.path.relpath(physical_path, root).replace(os.sep, "/")
			paths.append((logical_path, physical_path))
	for logical_path in GENERATOR_SUPPORT_PATHS + prompt_paths:
		paths.append((logical_path, os.path.join(root, *logical_path.split("/"))))
	configured_settings = settings_path if settings_path is not None else "settings.yaml"
	if not os.path.isabs(configured_settings):
		configured_settings = os.path.join(root, configured_settings)
	paths.append(("runtime/settings.yaml", os.path.abspath(configured_settings)))
	paths.sort(key=lambda item: item[0])
	return paths


#============================================
def generator_revision(
	repository_root: str,
	settings_path: str | None = None,
	*,
	prompt_paths: tuple[str, ...],
	contracts: dict[str, object],
) -> str:
	"""Hash the exact running source, active prompts, and settings contract."""
	validated_contracts = _validate_contract_identity(contracts)
	files = []
	for logical_path, physical_path in _generator_contract_paths(
		repository_root,
		settings_path,
		prompt_paths,
	):
		if not os.path.isfile(physical_path):
			raise RuntimeError(f"Generator contract file is unavailable: {logical_path}")
		with open(physical_path, "rb") as handle:
			contents = handle.read()
		files.append(
			{
				"path": logical_path,
				"sha256": daily_blog.io_utils.sha256_bytes(contents),
			}
		)
	generator_contract: dict[str, object] = {
		"schema_version": GENERATOR_CONTRACT_VERSION,
		"files": files,
		"contracts": validated_contracts,
	}
	revision = daily_blog.io_utils.hash_value(generator_contract)
	return revision


#============================================
def bundle_sha256(bundle: dict) -> str:
	"""Hash every manifest field except the checksum itself."""
	content = dict(bundle)
	content.pop("bundle_sha256", None)
	digest = daily_blog.io_utils.hash_value(content)
	return digest


#============================================
def validate_bundle_manifest_coherence(
	bundle: dict,
	packet: daily_blog.schema.EvidencePacket,
	evidence_value: object,
) -> None:
	"""Bind the v9 manifest-wide publication identity to active evidence."""
	if (
		bundle.get("report_date") != packet.report_date
		or bundle.get("timezone") != packet.timezone
	):
		raise RuntimeError("Cached publication bundle date or timezone is invalid.")
	active_evidence = packet.to_dict()
	if evidence_value != active_evidence:
		raise RuntimeError("Cached publication bundle evidence does not match the packet.")
	expected_manifest = {
		"path": "evidence.json",
		"packet_id": packet.packet_id,
		"sha256": daily_blog.io_utils.hash_value(active_evidence),
	}
	if bundle.get("evidence") != expected_manifest:
		raise RuntimeError("Cached publication bundle evidence manifest is invalid.")


#============================================
def _surface_allowed_image_paths(surface_value: dict[str, object]) -> tuple[str, ...]:
	"""Return the exact portable-surface image paths allowed in post source."""
	images = surface_value["allowed_images"]
	if not isinstance(images, list):
		raise RuntimeError("Publication surface images are invalid.")
	return tuple(image["publish_path"] for image in images if isinstance(image, dict))


#============================================
def _surface_assets(surface_value: dict[str, object]) -> dict[str, dict[str, object]]:
	"""Index already-validated portable image authority by confined asset path."""
	images = surface_value["allowed_images"]
	if not isinstance(images, list):
		raise RuntimeError("Publication surface images are invalid.")
	return {image["asset_path"]: image for image in images if isinstance(image, dict)}


#============================================
def sealed_bundle_transfer(bundle: object, artifacts: object) -> SealedBundleTransfer:
	"""Validate one v9 byte snapshot and freeze it for one publisher invocation."""
	if type(bundle) is not dict or type(artifacts) is not dict:
		raise RuntimeError("Sealed bundle transfer requires exact bundle artifacts.")
	if not _CORE_TRANSFER_PATHS <= set(artifacts) or any(
		type(path) is not str or type(contents) is not bytes for path, contents in artifacts.items()
	):
		raise RuntimeError("Sealed bundle transfer artifacts are incomplete.")
	for path in artifacts:
		if path not in _CORE_TRANSFER_PATHS:
			_transfer_path_limit(path)
	bundle_value = daily_blog.publication_storage.json_artifact(artifacts["bundle.json"])
	if not isinstance(bundle_value, dict) or bundle_value != bundle:
		raise RuntimeError("Sealed bundle transfer manifest does not match its bytes.")
	if bundle.get("schema_version") != daily_blog.schema.BUNDLE_SCHEMA_VERSION:
		raise RuntimeError("Sealed bundle transfer schema is invalid.")
	if bundle.get("bundle_sha256") != bundle_sha256(bundle):
		raise RuntimeError("Sealed bundle transfer manifest checksum is invalid.")
	validate_bundle_identity_fields(bundle)
	evidence_value = daily_blog.publication_storage.json_artifact(artifacts["evidence.json"])
	if not isinstance(evidence_value, dict):
		raise RuntimeError("Sealed bundle transfer evidence is invalid.")
	packet = daily_blog.schema.EvidencePacket.from_dict(evidence_value)
	validate_bundle_manifest_coherence(bundle, packet, evidence_value)
	roster_value = daily_blog.publication_storage.json_artifact(artifacts["repository_roster.json"])
	if not isinstance(roster_value, dict):
		raise RuntimeError("Sealed bundle transfer roster is invalid.")
	roster = daily_blog.repository_contracts.RepositoryRoster.from_dict(roster_value)
	roster_manifest = bundle.get("repository_roster")
	if roster_manifest != {
		"path": "repository_roster.json", "roster_id": roster.roster_id,
		"sha256": daily_blog.io_utils.hash_value(roster.to_dict()),
	}:
		raise RuntimeError("Sealed bundle transfer roster manifest is invalid.")
	if not {activity.repository for activity in packet.activity} <= {item.repository for item in roster.repositories}:
		raise RuntimeError("Sealed bundle transfer activity exceeds its roster.")
	projection_value = daily_blog.publication_storage.json_artifact(artifacts["editorial_projection.json"])
	if not isinstance(projection_value, dict):
		raise RuntimeError("Sealed bundle transfer projection is invalid.")
	projection = daily_blog.schema.EditorialProjection.from_dict(projection_value)
	if projection.packet_id != packet.packet_id or bundle.get("editorial_projection") != {
		"path": "editorial_projection.json", "projection_id": projection.projection_id,
		"sha256": daily_blog.io_utils.hash_value(projection.to_dict()),
	}:
		raise RuntimeError("Sealed bundle transfer projection manifest is invalid.")
	surface_value = daily_blog.publication_storage.json_artifact(artifacts["publication_surface.json"])
	surface = daily_blog.publication_surface_contract.validate_publication_surface_value(
		surface_value, packet, projection,
	)
	if bundle.get("publication_surface") != {
		"path": "publication_surface.json", "surface_id": surface["surface_id"],
		"sha256": daily_blog.io_utils.hash_value(surface),
	}:
		raise RuntimeError("Sealed bundle transfer surface manifest is invalid.")
	try:
		post_source = artifacts["post.md"].decode("utf-8")
	except UnicodeDecodeError as error:
		raise RuntimeError("Sealed bundle transfer post is invalid.") from error
	# ASVS 2.3.1: post admission consumes the exact authority transferred to the publisher.
	if daily_blog.publication_source_safety.validate_post_source(
		post_source, _surface_allowed_image_paths(surface),
	):
		raise RuntimeError("Sealed bundle transfer post source is unsafe.")
	post_manifest = bundle.get("post")
	post_bytes = artifacts["post.md"]
	try:
		post_bytes.decode("utf-8")
	except UnicodeDecodeError as error:
		raise RuntimeError("Sealed bundle transfer post is invalid.") from error
	if not isinstance(post_manifest, dict) or set(post_manifest) != {"path", "sha256", "artifact_id"} or (
		post_manifest.get("path") != "post.md" or post_manifest.get("sha256") != daily_blog.io_utils.sha256_bytes(post_bytes)
		or post_manifest.get("artifact_id") != bundle.get("best_artifact_id")
	):
		raise RuntimeError("Sealed bundle transfer selected post binding is invalid.")
	manifest_assets: dict[str, str] = {}
	surface_assets = _surface_assets(surface)
	packet_items = {item.evidence_id: item for item in packet.items}
	if not isinstance(bundle.get("assets"), list):
		raise RuntimeError("Sealed bundle transfer asset manifest is invalid.")
	for item in bundle["assets"]:
		if not isinstance(item, dict) or set(item) != {"path", "sha256", "evidence_id", "git_blob_hash", "publish_path"}:
			raise RuntimeError("Sealed bundle transfer asset manifest is invalid.")
		path = daily_blog.schema.validate_bundle_asset_path(item["path"])
		image = surface_assets.get(path)
		if (
			path in manifest_assets or type(item["sha256"]) is not str or image is None
			or item["evidence_id"] != image["evidence_id"]
			or item["publish_path"] != image["publish_path"]
			or item["git_blob_hash"] != packet_items[item["evidence_id"]].blob_hash
		):
			raise RuntimeError("Sealed bundle transfer asset manifest is invalid.")
		manifest_assets[path] = item["sha256"]
	if set(manifest_assets) != set(surface_assets):
		raise RuntimeError("Sealed bundle transfer assets do not match the publication surface.")
	if set(artifacts) != _CORE_TRANSFER_PATHS | set(manifest_assets):
		raise RuntimeError("Sealed bundle transfer artifacts do not match their manifest.")
	for path, sha256 in manifest_assets.items():
		if sha256 != daily_blog.io_utils.sha256_bytes(artifacts[path]):
			raise RuntimeError("Sealed bundle transfer asset checksum is invalid.")
	entries = tuple(
		SealedBundleTransferEntry(path, artifacts[path], daily_blog.io_utils.sha256_bytes(artifacts[path]))
		for path in sorted(artifacts)
	)
	return SealedBundleTransfer(packet.report_date, bundle["bundle_sha256"], entries)


#============================================
def load_reusable_bundle(
	record: dict,
	date_root: str,
	surface: daily_blog.publication_admission.PublicationSurface,
	assets: dict[str, bytes],
	identity: PublicationIdentity,
	repository_roster: daily_blog.repository_contracts.RepositoryRoster | None = None,
) -> tuple[str, dict, SealedBundleTransfer]:
	"""Verify and return the completed bundle at the stable date path."""
	if type(surface) is not daily_blog.publication_admission.PublicationSurface:
		raise RuntimeError("Reusable publication bundles require one exact publication surface.")
	packet = surface.packet
	projection = surface.projection
	surface_value = daily_blog.publication_surface_contract.publication_surface_value(surface)
	identity = _require_identity(identity)
	resolved_revision = identity.revision
	storage = daily_blog.publication_storage.storage_for_date_root(date_root)
	bundle_path = os.path.join(storage.output_root, storage.owner, "daily_blog", storage.report_date, "publication")
	if record.get("bundle_path") != bundle_path:
		raise RuntimeError("Cached publication bundle path is unavailable or unconfined.")
	artifacts = storage.read()
	bundle_value = daily_blog.publication_storage.json_artifact(artifacts["bundle.json"])
	if not isinstance(bundle_value, dict) or bundle_value != record.get("bundle"):
		raise RuntimeError("Cached publication bundle manifest does not match its record.")
	bundle = dict(bundle_value)
	if bundle.get("schema_version") != daily_blog.schema.BUNDLE_SCHEMA_VERSION:
		raise RuntimeError("Cached publication bundle schema has changed.")
	if bundle.get("bundle_sha256") != bundle_sha256(bundle):
		raise RuntimeError("Cached publication bundle checksum does not match its manifest.")
	roster_manifest = bundle.get("repository_roster")
	if not isinstance(roster_manifest, dict) or set(roster_manifest) != {
		"path", "roster_id", "sha256"
	}:
		raise RuntimeError("Cached publication bundle repository roster manifest is invalid.")
	if roster_manifest["path"] != "repository_roster.json":
		raise RuntimeError("Cached publication bundle repository roster path is invalid.")
	roster_value = daily_blog.publication_storage.json_artifact(artifacts["repository_roster.json"])
	if not isinstance(roster_value, dict):
		raise RuntimeError("Cached publication bundle repository roster is invalid.")
	roster = daily_blog.repository_contracts.RepositoryRoster.from_dict(roster_value)
	if repository_roster is None:
		raise RuntimeError("Reusable publication bundles require the current repository roster.")
	current_roster = daily_blog.repository_contracts.RepositoryRoster.from_dict(
		repository_roster.to_dict()
	)
	if (
		roster.roster_id != roster_manifest["roster_id"]
		or daily_blog.io_utils.hash_value(roster.to_dict()) != roster_manifest["sha256"]
		or roster != current_roster
	):
		raise RuntimeError("Cached publication bundle repository roster integrity is invalid.")
	contracts = bundle.get("contracts", {})
	expected_contracts = identity.contracts_dict()
	if (
		contracts != expected_contracts
		or bundle.get("generator", {}).get("revision") != resolved_revision
		or bundle.get("generator", {}).get("version") != daily_blog.schema.GENERATOR_VERSION
		or bundle.get("maker_activation") != identity.activation_receipt_dict()
	):
		raise RuntimeError("Cached publication bundle generator contracts have changed.")
	if bundle.get("editorial_prompt_contract") != identity.prompt_contract_dict():
		raise RuntimeError("Cached publication bundle prompt contract has changed.")
	evidence = daily_blog.publication_storage.json_artifact(artifacts["evidence.json"])
	validate_bundle_manifest_coherence(bundle, packet, evidence)
	projection_value = daily_blog.publication_storage.json_artifact(artifacts["editorial_projection.json"])
	if projection_value != projection.to_dict():
		raise RuntimeError("Cached publication bundle projection does not match the active projection.")
	projection_manifest = bundle.get("editorial_projection", {})
	if (
		projection_manifest.get("path") != "editorial_projection.json"
		or projection_manifest.get("projection_id") != projection.projection_id
		or projection_manifest.get("sha256")
		!= daily_blog.io_utils.hash_value(projection.to_dict())
	):
		raise RuntimeError("Cached publication bundle projection manifest is invalid.")
	stored_surface = daily_blog.publication_storage.json_artifact(artifacts["publication_surface.json"])
	if stored_surface != surface_value or bundle.get("publication_surface") != {
		"path": "publication_surface.json", "surface_id": surface_value["surface_id"],
		"sha256": daily_blog.io_utils.hash_value(surface_value),
	}:
		raise RuntimeError("Cached publication bundle surface does not match current authority.")
	try:
		post = artifacts["post.md"].decode("utf-8")
	except UnicodeDecodeError as error:
		raise RuntimeError("Cached publication bundle post is invalid.") from error
	post_manifest = bundle.get("post")
	best_artifact_id = bundle.get("best_artifact_id")
	if (
		type(post_manifest) is not dict
		or set(post_manifest) != {"path", "sha256", "artifact_id"}
		or post_manifest["path"] != "post.md"
		or type(best_artifact_id) is not str
		or daily_blog.artifacts.ARTIFACT_ID_RE.fullmatch(best_artifact_id) is None
		or post_manifest["artifact_id"] != best_artifact_id
	):
		raise RuntimeError("Cached publication bundle selected artifact binding is invalid.")
	if daily_blog.io_utils.sha256_text(post) != post_manifest["sha256"]:
		raise RuntimeError("Cached publication bundle post hash does not match its content.")
	if daily_blog.publication_source_safety.validate_post_source(post, _surface_allowed_image_paths(surface_value)):
		raise RuntimeError("Cached publication bundle post source is unsafe.")
	expected_assets = {
		path: daily_blog.io_utils.sha256_bytes(contents) for path, contents in assets.items()
	}
	if not isinstance(bundle.get("assets"), list):
		raise RuntimeError("Cached publication bundle assets are invalid.")
	manifest_assets = {}
	for item in bundle["assets"]:
		if not isinstance(item, dict) or set(item) != {
			"path", "sha256", "evidence_id", "git_blob_hash", "publish_path"
		}:
			raise RuntimeError("Cached publication bundle assets are invalid.")
		asset_path = daily_blog.schema.validate_bundle_asset_path(item["path"])
		if asset_path in manifest_assets:
			raise RuntimeError("Cached publication bundle assets are invalid.")
		manifest_assets[asset_path] = item["sha256"]
	if manifest_assets != expected_assets or set(expected_assets) != set(_surface_assets(surface_value)):
		raise RuntimeError("Cached publication bundle assets do not match current evidence.")
	for asset_path, expected_hash in expected_assets.items():
		daily_blog.schema.validate_bundle_asset_path(asset_path)
		contents = artifacts.get(asset_path)
		if contents is None:
			raise RuntimeError("Cached publication bundle asset is unavailable.")
		if daily_blog.io_utils.sha256_bytes(contents) != expected_hash:
			raise RuntimeError("Cached publication bundle asset hash does not match its content.")
	transfer = sealed_bundle_transfer(bundle, artifacts)
	return bundle_path, bundle, transfer


class BundleWriter:
	"""Write one complete bundle by staging and atomic directory promotion."""

	#============================================
	def __init__(
		self,
		output_root: str,
		owner: str,
		identity: PublicationIdentity,
	) -> None:
		"""Configure output ownership and the frozen running-source identity."""
		identity = _require_identity(identity)
		revision = identity.revision
		self.output_root = os.path.abspath(output_root)
		self.owner = owner
		self.generator_revision = revision
		self.identity = identity

	#============================================
	def _asset_manifest(
		self,
		surface_value: dict[str, object],
		packet: daily_blog.schema.EvidencePacket,
		assets: dict[str, bytes],
	) -> list[dict]:
		"""Build asset hash and provenance entries from selected screenshot evidence."""
		items_by_evidence_id = {item.evidence_id: item for item in packet.items}
		surface_assets = _surface_assets(surface_value)
		if set(surface_assets) != set(assets):
			raise RuntimeError("Bundle assets must exactly match publication surface authority.")
		manifest = []
		for path in sorted(assets):
			daily_blog.schema.validate_bundle_asset_path(path)
			if type(assets[path]) is not bytes:
				raise RuntimeError("Bundle asset bytes are invalid.")
			image = surface_assets[path]
			item = items_by_evidence_id[image["evidence_id"]]
			manifest.append(
				{
					"path": path,
					"sha256": daily_blog.io_utils.sha256_bytes(assets[path]),
					"evidence_id": image["evidence_id"],
					"git_blob_hash": item.blob_hash,
					"publish_path": image["publish_path"],
				}
			)
		return manifest

	#============================================
	def write(
		self,
		run_id: str,
		surface: daily_blog.publication_admission.PublicationSurface,
		assets: dict[str, bytes],
		repository_roster: daily_blog.repository_contracts.RepositoryRoster,
		selected_post: daily_blog.artifacts.CompletePost,
	) -> tuple[str, dict, SealedBundleTransfer]:
		"""Write and atomically promote the current date-owned publication bundle."""
		_require_identity(self.identity)
		if type(surface) is not daily_blog.publication_admission.PublicationSurface:
			raise RuntimeError("Publication bundles require one exact publication surface.")
		packet = surface.packet
		projection = surface.projection
		surface_value = daily_blog.publication_surface_contract.publication_surface_value(surface)
		if not packet.complete:
			raise RuntimeError("Publication bundles require complete evidence packets.")
		if projection.packet_id != packet.packet_id:
			raise RuntimeError("Publication bundle projection does not match its evidence packet.")
		# ASVS 1.5.2 and 2.2.1: validate the typed roster before binding it to a bundle.
		roster = daily_blog.repository_contracts.RepositoryRoster.from_dict(repository_roster.to_dict())
		active_repositories = {activity.repository for activity in packet.activity}
		rostered_repositories = {item.repository for item in roster.repositories}
		if not active_repositories <= rostered_repositories:
			raise RuntimeError("Publication bundle activity exceeds its authoritative roster.")
		if type(selected_post) is not daily_blog.artifacts.CompletePost:
			raise RuntimeError("Publication bundle requires an exact selected CompletePost.")
		if selected_post.report_date != packet.report_date:
			raise RuntimeError("Publication bundle selected post has a different report date.")
		post = selected_post.content
		if daily_blog.publication_source_safety.validate_post_source(post, _surface_allowed_image_paths(surface_value)):
			raise RuntimeError("Publication bundle selected post source is unsafe.")
		best_artifact_id = selected_post.artifact_id
		post_hash = daily_blog.io_utils.sha256_text(post)
		evidence_value = packet.to_dict()
		evidence_hash = daily_blog.io_utils.hash_value(evidence_value)
		projection_value = projection.to_dict()
		projection_hash = daily_blog.io_utils.hash_value(projection_value)
		roster_value = roster.to_dict()
		roster_hash = daily_blog.io_utils.hash_value(roster_value)
		asset_manifest = self._asset_manifest(surface_value, packet, assets)
		bundle = {
			"schema_version": daily_blog.schema.BUNDLE_SCHEMA_VERSION,
			"bundle_sha256": "",
			"report_date": packet.report_date,
			"best_artifact_id": best_artifact_id,
			"timezone": packet.timezone,
			"created_at": daily_blog.io_utils.utc_now(),
			"generator": {
				"run_id": run_id,
				"revision": self.generator_revision,
				"version": daily_blog.schema.GENERATOR_VERSION,
			},
			"contracts": self.identity.contracts_dict(),
			"evidence": {
				"path": "evidence.json",
				"packet_id": packet.packet_id,
				"sha256": evidence_hash,
			},
			"repository_roster": {
				"path": "repository_roster.json",
				"roster_id": roster.roster_id,
				"sha256": roster_hash,
			},
			"editorial_projection": {
				"path": "editorial_projection.json",
				"projection_id": projection.projection_id,
				"sha256": projection_hash,
			},
			"publication_surface": {
				"path": "publication_surface.json", "surface_id": surface_value["surface_id"],
				"sha256": daily_blog.io_utils.hash_value(surface_value),
			},
			"post": {
				"path": "post.md",
				"sha256": post_hash,
				"artifact_id": best_artifact_id,
			},
			"assets": asset_manifest,
		}
		bundle["maker_activation"] = self.identity.activation_receipt_dict()
		bundle["editorial_prompt_contract"] = self.identity.prompt_contract_dict()
		bundle["bundle_sha256"] = bundle_sha256(bundle)
		storage = daily_blog.publication_storage.PublicationStorage(
			self.output_root, self.owner, packet.report_date, run_id,
		)
		artifacts = {
			"bundle.json": daily_blog.io_utils.stable_json_text(bundle).encode("utf-8"),
			"evidence.json": daily_blog.io_utils.stable_json_text(evidence_value).encode("utf-8"),
			"repository_roster.json": daily_blog.io_utils.stable_json_text(roster_value).encode("utf-8"),
			"editorial_projection.json": daily_blog.io_utils.stable_json_text(projection_value).encode("utf-8"),
			"publication_surface.json": daily_blog.io_utils.stable_json_text(surface_value).encode("utf-8"),
			"post.md": post.encode("utf-8"),
			**assets,
		}
		transfer = sealed_bundle_transfer(bundle, artifacts)
		bundle_path = storage.write(artifacts)
		return bundle_path, bundle, transfer

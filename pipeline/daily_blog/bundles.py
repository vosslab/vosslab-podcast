"""Validated publication bundle creation at one stable path per report date."""

# Standard Library
import os
import shutil
import uuid
import pathlib
import dataclasses
import weakref

# local repo modules
import daily_blog.schema
import daily_blog.repository_contracts
import daily_blog.editorial
import daily_blog.contracts
import daily_blog.io_utils
import daily_blog.atomic_paths
import daily_blog.activation


GENERATOR_CONTRACT_VERSION = "vosslab.daily-blog.generator-source.v1"
GENERATOR_SUPPORT_PATHS = (
	"pipeline/podlib/pipeline_settings.py",
	"pipeline/podlib/prompt_loader.py",
	"daily_blog_maker_activation.json",
)
_GENERATOR_IDENTITY_TOKEN = object()
_GENERATOR_IDENTITIES: weakref.WeakValueDictionary[int, "GeneratorContractIdentity"] = weakref.WeakValueDictionary()


@dataclasses.dataclass(frozen=True)
class GeneratorContractIdentity:
	"""Opaque factory-issued generator revision bound to one prompt snapshot."""

	revision: str
	contract: daily_blog.contracts.EditorialContract
	snapshot: daily_blog.editorial.PromptContractSnapshot
	_origin: object = dataclasses.field(repr=False, compare=False, default=None)


#============================================
def generator_contract_identity(
	repository_root: str,
	settings_path: str | None,
	contract: daily_blog.contracts.EditorialContract,
	snapshot: daily_blog.editorial.PromptContractSnapshot,
) -> GeneratorContractIdentity:
	"""Issue the only v4 revision record accepted by bundle writing and reuse."""
	daily_blog.editorial.validate_snapshot(snapshot)
	if snapshot.contract is not contract:
		raise RuntimeError("Generator identity snapshot does not match its editorial contract.")
	revision = generator_revision(repository_root, settings_path, contract, snapshot)
	identity = GeneratorContractIdentity(revision, contract, snapshot, _GENERATOR_IDENTITY_TOKEN)
	_GENERATOR_IDENTITIES[id(identity)] = identity
	return identity


#============================================
def _validate_generator_identity(identity: GeneratorContractIdentity) -> GeneratorContractIdentity:
	"""Accept only an exact factory-issued generator identity object."""
	if (
		not isinstance(identity, GeneratorContractIdentity)
		or identity._origin is not _GENERATOR_IDENTITY_TOKEN
		or _GENERATOR_IDENTITIES.get(id(identity)) is not identity
	):
		raise RuntimeError("Generator identity was not issued by the trusted factory.")
	daily_blog.editorial.validate_snapshot(identity.snapshot)
	return identity


#============================================
def _requires_generator_identity(contract: daily_blog.contracts.EditorialContract) -> bool:
	"""Keep raw revisions confined to the historical v3 artifact shape."""
	return contract is not daily_blog.contracts.V3_EDITORIAL_CONTRACT


#============================================
def _activation_manifest(
	contract: daily_blog.contracts.EditorialContract,
	snapshot: daily_blog.editorial.PromptContractSnapshot | None,
) -> dict[str, object] | None:
	"""Bind production bundles to the checked-in F4-derived activation receipt."""
	if contract is not daily_blog.contracts.active_contract():
		return None
	if snapshot is None:
		raise RuntimeError("Publication bundles require the activated maker prompt snapshot.")
	activation = daily_blog.activation.load_maker_activation()
	prompt_identity = daily_blog.editorial.prompt_contract_identity(snapshot=snapshot)
	if activation.contract is not contract or (
		activation.receipt["editorial_prompt_contract"] != prompt_identity
	):
		raise RuntimeError("Publication bundle prompt snapshot does not match maker activation.")
	return {
		"activation_id": activation.activation_id,
		"editorial_prompt_contract_sha256": activation.receipt[
			"editorial_prompt_contract_sha256"
		],
	}


#============================================
def _generator_contract_paths(
	repository_root: str,
	settings_path: str | None,
	contract: daily_blog.contracts.EditorialContract | None = None,
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
	resolved = daily_blog.contracts.resolve_contract(contract)
	for logical_path in GENERATOR_SUPPORT_PATHS + resolved.prompt_paths():
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
	contract: daily_blog.contracts.EditorialContract | None = None,
	snapshot: daily_blog.editorial.PromptContractSnapshot | None = None,
) -> str:
	"""Hash the exact running source, active prompts, and settings contract."""
	resolved = daily_blog.contracts.resolve_contract(contract)
	if snapshot is not None:
		daily_blog.editorial.validate_snapshot(snapshot)
	if _requires_generator_identity(resolved) and snapshot is None:
		raise RuntimeError("V4 generator revisions require their validated prompt snapshot.")
	if snapshot is not None and snapshot.contract is not resolved:
		raise RuntimeError("Generator revision snapshot does not match its editorial contract.")
	files = []
	for logical_path, physical_path in _generator_contract_paths(
		repository_root,
		settings_path,
		contract,
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
		"editorial_contract": {
			"name": resolved.name,
			"candidate_validation": {
				"name": daily_blog.contracts.policy_for_contract(resolved).name,
				"version": daily_blog.contracts.policy_for_contract(resolved).version,
				"sha256": daily_blog.contracts.policy_for_contract(resolved).sha256(),
			},
		},
	}
	if snapshot is not None and snapshot.selection is not None:
		editorial_contract = generator_contract["editorial_contract"]
		if not isinstance(editorial_contract, dict):
			raise RuntimeError("Generator editorial contract is invalid.")
		editorial_contract["selection"] = {
			"name": snapshot.selection.name,
			"blocks": list(snapshot.selection.block_ids),
			"examples_sha256": daily_blog.io_utils.sha256_bytes(snapshot.example_bytes),
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
def load_reusable_bundle(
	record: dict,
	date_root: str,
	packet: daily_blog.schema.EvidencePacket,
	projection: daily_blog.schema.EditorialProjection,
	assets: dict[str, bytes],
	revision: str | GeneratorContractIdentity,
	contract: daily_blog.contracts.EditorialContract | None = None,
	snapshot: daily_blog.editorial.PromptContractSnapshot | None = None,
	repository_roster: daily_blog.repository_contracts.RepositoryRoster | None = None,
) -> tuple[str, dict]:
	"""Verify and return the completed bundle at the stable date path."""
	resolved = daily_blog.contracts.resolve_contract(contract)
	activation_manifest = _activation_manifest(resolved, snapshot)
	if _requires_generator_identity(resolved):
		if not isinstance(revision, GeneratorContractIdentity):
			raise RuntimeError("Reusable v4 bundles require their factory-issued generator identity.")
		identity = _validate_generator_identity(revision)
		if snapshot is None:
			raise RuntimeError("Reusable v4 bundles require their validated prompt snapshot.")
		daily_blog.editorial.validate_snapshot(snapshot)
		if identity.contract is not resolved or identity.snapshot is not snapshot:
			raise RuntimeError("Reusable v4 generator identity does not match its prompt snapshot.")
		resolved_revision = identity.revision
	else:
		if not isinstance(revision, str):
			raise RuntimeError("Reusable historical bundles require a SHA-256 generator revision.")
		resolved_revision = revision
	bundle_path = os.path.abspath(str(record.get("bundle_path") or ""))
	physical_root = os.path.realpath(os.path.abspath(date_root))
	if (
		not os.path.isdir(bundle_path)
		or os.path.islink(bundle_path)
		or os.path.commonpath((physical_root, os.path.realpath(bundle_path))) != physical_root
	):
		raise RuntimeError("Cached publication bundle path is unavailable or unconfined.")
	bundle_value = daily_blog.io_utils.read_json(os.path.join(bundle_path, "bundle.json"))
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
	roster_value = daily_blog.io_utils.read_json(
		os.path.join(bundle_path, roster_manifest["path"])
	)
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
	if snapshot is not None:
		daily_blog.editorial.validate_snapshot(snapshot)
	if snapshot is not None and snapshot.contract is not resolved:
		raise RuntimeError("Reusable bundle prompt snapshot does not match its editorial contract.")
	expected_contracts = {
		"evidence_schema": daily_blog.schema.EVIDENCE_SCHEMA_VERSION,
		"editorial_projection_schema": daily_blog.schema.PROJECTION_SCHEMA_VERSION,
		"prompt_version": resolved.prompt_version,
		"rubric_version": resolved.rubric_version,
		"candidate_validation": {
			"name": daily_blog.contracts.policy_for_contract(resolved).name,
			"version": daily_blog.contracts.policy_for_contract(resolved).version,
			"sha256": daily_blog.contracts.policy_for_contract(resolved).sha256(),
		},
	}
	if (
		contracts != expected_contracts
		or bundle.get("generator", {}).get("revision") != resolved_revision
		or bundle.get("generator", {}).get("version") != daily_blog.schema.GENERATOR_VERSION
		or (
			activation_manifest is not None
			and bundle.get("maker_activation") != activation_manifest
		)
	):
		raise RuntimeError("Cached publication bundle generator contracts have changed.")
	if snapshot is not None:
		expected_prompt_contract = daily_blog.editorial.prompt_contract_identity(snapshot=snapshot)
		if bundle.get("editorial_prompt_contract") != expected_prompt_contract:
			raise RuntimeError("Cached publication bundle prompt contract has changed.")
	evidence = daily_blog.io_utils.read_json(os.path.join(bundle_path, "evidence.json"))
	if evidence != packet.to_dict():
		raise RuntimeError("Cached publication bundle evidence does not match the packet.")
	projection_value = daily_blog.io_utils.read_json(
		os.path.join(bundle_path, "editorial_projection.json")
	)
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
	post_path = os.path.join(bundle_path, "post.md")
	with open(post_path, "r", encoding="utf-8") as handle:
		post = handle.read()
	if daily_blog.io_utils.sha256_text(post) != bundle.get("post", {}).get("sha256"):
		raise RuntimeError("Cached publication bundle post hash does not match its content.")
	expected_assets = {
		path: daily_blog.io_utils.sha256_bytes(contents) for path, contents in assets.items()
	}
	manifest_assets = {item["path"]: item["sha256"] for item in bundle.get("assets", [])}
	if manifest_assets != expected_assets:
		raise RuntimeError("Cached publication bundle assets do not match current evidence.")
	for asset_path, expected_hash in expected_assets.items():
		pure = pathlib.PurePosixPath(asset_path)
		if pure.is_absolute() or ".." in pure.parts:
			raise RuntimeError("Cached publication bundle asset path is unconfined.")
		path = os.path.join(bundle_path, *pure.parts)
		with open(path, "rb") as handle:
			contents = handle.read()
		if daily_blog.io_utils.sha256_bytes(contents) != expected_hash:
			raise RuntimeError("Cached publication bundle asset hash does not match its content.")
	return bundle_path, bundle


class BundleWriter:
	"""Write one complete bundle by staging and atomic directory promotion."""

	#============================================
	def __init__(
		self,
		output_root: str,
		owner: str,
		generator_revision: str | GeneratorContractIdentity,
		contract: daily_blog.contracts.EditorialContract | None = None,
		snapshot: daily_blog.editorial.PromptContractSnapshot | None = None,
	) -> None:
		"""Configure output ownership and the frozen running-source identity."""
		identity: GeneratorContractIdentity | None = (
			generator_revision if isinstance(generator_revision, GeneratorContractIdentity) else None
		)
		if identity is not None:
			identity = _validate_generator_identity(identity)
			revision: str = identity.revision
		else:
			if not isinstance(generator_revision, str):
				raise RuntimeError("Generator source identity must be lowercase SHA-256 text.")
			revision = generator_revision
		if not isinstance(revision, str) or len(revision) != 64 or any(
			character not in "0123456789abcdef" for character in revision
		):
			raise RuntimeError("Generator source identity must be lowercase SHA-256 text.")
		self.output_root = os.path.abspath(output_root)
		self.owner = owner
		self.generator_revision = revision
		self.contract = daily_blog.contracts.resolve_contract(contract)
		if snapshot is not None:
			daily_blog.editorial.validate_snapshot(snapshot)
			if snapshot.contract is not self.contract:
				raise RuntimeError("Bundle prompt snapshot does not match its editorial contract.")
			self.prompt_contract_identity: dict[str, object] | None = daily_blog.editorial.prompt_contract_identity(
				snapshot=snapshot
			)
		else:
			self.prompt_contract_identity = None
		if _requires_generator_identity(self.contract) and snapshot is None:
			raise RuntimeError("V4 bundle writing requires its validated prompt snapshot.")
		if _requires_generator_identity(self.contract):
			if identity is None or identity.contract is not self.contract or identity.snapshot is not snapshot:
				raise RuntimeError("V4 bundle writing requires its factory-issued generator identity.")
		self.prompt_snapshot = snapshot
		self.activation_manifest = _activation_manifest(self.contract, snapshot)

	#============================================
	def _asset_manifest(
		self,
		packet: daily_blog.schema.EvidencePacket,
		assets: dict[str, bytes],
	) -> list[dict]:
		"""Build asset hash and provenance entries from selected screenshot evidence."""
		items_by_path = {item.asset_path: item for item in packet.items if item.asset_path}
		manifest = []
		for path in sorted(assets):
			if path not in items_by_path:
				raise RuntimeError(f"Bundle asset lacks evidence provenance: {path}")
			item = items_by_path[path]
			manifest.append(
				{
					"path": path,
					"sha256": daily_blog.io_utils.sha256_bytes(assets[path]),
					"evidence_id": item.evidence_id,
					"git_blob_hash": item.blob_hash,
					"publish_path": item.publish_path,
				}
			)
		return manifest

	#============================================
	def write(
		self,
		run_id: str,
		packet: daily_blog.schema.EvidencePacket,
		projection: daily_blog.schema.EditorialProjection,
		assets: dict[str, bytes],
		candidates: list[daily_blog.editorial.CandidateResult],
		decision: daily_blog.editorial.EditorialDecision,
		repository_roster: daily_blog.repository_contracts.RepositoryRoster,
	) -> tuple[str, dict]:
		"""Write and atomically promote the current date-owned publication bundle."""
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
		if decision.winner not in {"A", "B"}:
			raise RuntimeError("Publication bundles require an approved referee winner.")
		if decision.projection_id != projection.projection_id:
			raise RuntimeError("Publication bundle referee decision has a different projection.")
		if any(candidate.projection_id != projection.projection_id for candidate in candidates):
			raise RuntimeError("Publication bundle candidates have a different projection.")
		winner_index = decision.anonymous_mapping.get(decision.winner)
		if winner_index is None or winner_index >= len(candidates):
			raise RuntimeError("Publication bundle winner mapping is unavailable.")
		winner = candidates[winner_index]
		if not winner.valid or winner.post != decision.post:
			raise RuntimeError("Publication bundle post is not the approved valid candidate.")
		post = decision.post
		post_hash = daily_blog.io_utils.sha256_text(post)
		evidence_value = packet.to_dict()
		evidence_hash = daily_blog.io_utils.hash_value(evidence_value)
		projection_value = projection.to_dict()
		projection_hash = daily_blog.io_utils.hash_value(projection_value)
		roster_value = roster.to_dict()
		roster_hash = daily_blog.io_utils.hash_value(roster_value)
		asset_manifest = self._asset_manifest(packet, assets)
		candidate_summaries = [
			candidate.public_summary(f"candidate_{index + 1}")
			for index, candidate in enumerate(candidates)
		]
		bundle = {
			"schema_version": daily_blog.schema.BUNDLE_SCHEMA_VERSION,
			"bundle_sha256": "",
			"report_date": packet.report_date,
			"timezone": packet.timezone,
			"created_at": daily_blog.io_utils.utc_now(),
			"generator": {
				"run_id": run_id,
				"revision": self.generator_revision,
				"version": daily_blog.schema.GENERATOR_VERSION,
			},
			"contracts": {
				"evidence_schema": daily_blog.schema.EVIDENCE_SCHEMA_VERSION,
				"editorial_projection_schema": daily_blog.schema.PROJECTION_SCHEMA_VERSION,
				"prompt_version": self.contract.prompt_version,
				"rubric_version": self.contract.rubric_version,
				"candidate_validation": {
					"name": daily_blog.contracts.policy_for_contract(self.contract).name,
					"version": daily_blog.contracts.policy_for_contract(self.contract).version,
					"sha256": daily_blog.contracts.policy_for_contract(self.contract).sha256(),
				},
			},
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
			"post": {"path": "post.md", "sha256": post_hash},
			"assets": asset_manifest,
			"candidates": candidate_summaries,
			"referee": {
				"projection_id": decision.projection_id,
				"winner": decision.winner,
				"reason": decision.reason,
				"evidence_quality": decision.evidence_quality,
				"confidence": decision.confidence,
				"anonymous_mapping": {
					label: f"candidate_{index + 1}"
					for label, index in decision.anonymous_mapping.items()
				},
			},
		}
		if self.activation_manifest is not None:
			bundle["maker_activation"] = self.activation_manifest
		if self.prompt_contract_identity is not None:
			bundle["editorial_prompt_contract"] = self.prompt_contract_identity
		bundle["bundle_sha256"] = bundle_sha256(bundle)
		date_root = os.path.join(
			self.output_root,
			self.owner,
			"daily_blog",
			packet.report_date,
		)
		bundle_path = os.path.join(date_root, "publication")
		os.makedirs(date_root, exist_ok=True)
		stage = os.path.join(date_root, f".{run_id}.staging-{uuid.uuid4().hex}")
		if os.path.islink(bundle_path):
			raise RuntimeError("Publication bundle path must be one physical directory.")
		os.makedirs(os.path.join(stage, "assets"))
		try:
			daily_blog.io_utils.atomic_write_json(
				os.path.join(stage, "bundle.json"),
				bundle,
			)
			daily_blog.io_utils.atomic_write_json(
				os.path.join(stage, "evidence.json"),
				evidence_value,
			)
			daily_blog.io_utils.atomic_write_json(
				os.path.join(stage, "repository_roster.json"),
				roster_value,
			)
			daily_blog.io_utils.atomic_write_json(
				os.path.join(stage, "editorial_projection.json"),
				projection_value,
			)
			daily_blog.io_utils.atomic_write_text(os.path.join(stage, "post.md"), post)
			for asset_path, contents in assets.items():
				destination = os.path.join(stage, asset_path)
				daily_blog.io_utils.atomic_write_bytes(destination, contents)
			if os.path.lexists(bundle_path):
				daily_blog.atomic_paths.exchange_directories(bundle_path, stage)
			else:
				os.replace(stage, bundle_path)
		except Exception:
			if os.path.exists(stage):
				shutil.rmtree(stage)
			raise
		# A successful exchange leaves the old revision at the staging name.  Its
		# removal is post-commit cleanup; the stable publication path already names
		# the complete new directory throughout this cleanup.
		if os.path.lexists(stage):
			shutil.rmtree(stage)
		return bundle_path, bundle

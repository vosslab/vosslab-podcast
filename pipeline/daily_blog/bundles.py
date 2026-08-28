"""Immutable publication bundle creation and stable per-date latest pointers."""

# Standard Library
import os
import shutil
import uuid
import pathlib

# local repo modules
import daily_blog.schema
import daily_blog.editorial
import daily_blog.io_utils


GENERATOR_CONTRACT_VERSION = "vosslab.daily-blog.generator-source.v1"
GENERATOR_SUPPORT_PATHS = (
	"pipeline/podlib/pipeline_settings.py",
	"pipeline/podlib/prompt_loader.py",
)
GENERATOR_PROMPT_PATHS = (
	"pipeline/prompts/daily_blog_author_v3.txt",
	"pipeline/prompts/daily_blog_referee_repair_v3.txt",
	"pipeline/prompts/daily_blog_referee_v3.txt",
	"pipeline/prompts/daily_blog_rubric_v3.md",
)


#============================================
def _generator_contract_paths(repository_root: str, settings_path: str | None) -> list[tuple[str, str]]:
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
	for logical_path in GENERATOR_SUPPORT_PATHS + GENERATOR_PROMPT_PATHS:
		paths.append((logical_path, os.path.join(root, *logical_path.split("/"))))
	configured_settings = settings_path if settings_path is not None else "settings.yaml"
	if not os.path.isabs(configured_settings):
		configured_settings = os.path.join(root, configured_settings)
	paths.append(("runtime/settings.yaml", os.path.abspath(configured_settings)))
	paths.sort(key=lambda item: item[0])
	return paths


#============================================
def generator_revision(repository_root: str, settings_path: str | None = None) -> str:
	"""Hash the exact running source, active prompts, and settings contract."""
	files = []
	for logical_path, physical_path in _generator_contract_paths(repository_root, settings_path):
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
	contract = {
		"schema_version": GENERATOR_CONTRACT_VERSION,
		"files": files,
	}
	revision = daily_blog.io_utils.hash_value(contract)
	return revision


#============================================
def bundle_identity(bundle: dict) -> str:
	"""Compute bundle identity from every manifest field except the identity itself."""
	content = dict(bundle)
	content.pop("bundle_id", None)
	digest = daily_blog.io_utils.hash_value(content)
	return digest


#============================================
def load_reusable_bundle(
	record: dict,
	date_root: str,
	packet: daily_blog.schema.EvidencePacket,
	projection: daily_blog.schema.EditorialProjection,
	assets: dict[str, bytes],
	revision: str,
) -> tuple[str, dict]:
	"""Verify and return one previously completed immutable bundle artifact."""
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
	if bundle.get("bundle_id") != bundle_identity(bundle):
		raise RuntimeError("Cached publication bundle identity does not match its manifest.")
	contracts = bundle.get("contracts", {})
	expected_contracts = {
		"evidence_schema": daily_blog.schema.EVIDENCE_SCHEMA_VERSION,
		"editorial_projection_schema": daily_blog.schema.PROJECTION_SCHEMA_VERSION,
		"prompt_version": daily_blog.schema.PROMPT_VERSION,
		"rubric_version": daily_blog.schema.RUBRIC_VERSION,
	}
	if (
		contracts != expected_contracts
		or bundle.get("generator", {}).get("revision") != revision
		or bundle.get("generator", {}).get("version") != daily_blog.schema.GENERATOR_VERSION
	):
		raise RuntimeError("Cached publication bundle generator contracts have changed.")
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
	def __init__(self, output_root: str, owner: str, generator_revision: str) -> None:
		"""Configure output ownership and the frozen running-source identity."""
		if (
			len(generator_revision) != 64
			or any(character not in "0123456789abcdef" for character in generator_revision)
		):
			raise RuntimeError("Generator source identity must be lowercase SHA-256 text.")
		self.output_root = os.path.abspath(output_root)
		self.owner = owner
		self.generator_revision = generator_revision

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
	) -> tuple[str, dict]:
		"""Write and atomically promote one immutable publication bundle."""
		if not packet.complete:
			raise RuntimeError("Publication bundles require complete evidence packets.")
		if projection.packet_id != packet.packet_id:
			raise RuntimeError("Publication bundle projection does not match its evidence packet.")
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
		asset_manifest = self._asset_manifest(packet, assets)
		candidate_summaries = [
			candidate.public_summary(f"candidate_{index + 1}")
			for index, candidate in enumerate(candidates)
		]
		bundle = {
			"schema_version": daily_blog.schema.BUNDLE_SCHEMA_VERSION,
			"bundle_id": "",
			"report_date": packet.report_date,
			"timezone": packet.timezone,
			"created_at": daily_blog.schema.utc_now(),
			"generator": {
				"run_id": run_id,
				"revision": self.generator_revision,
				"version": daily_blog.schema.GENERATOR_VERSION,
			},
			"contracts": {
				"evidence_schema": daily_blog.schema.EVIDENCE_SCHEMA_VERSION,
				"editorial_projection_schema": daily_blog.schema.PROJECTION_SCHEMA_VERSION,
				"prompt_version": daily_blog.schema.PROMPT_VERSION,
				"rubric_version": daily_blog.schema.RUBRIC_VERSION,
			},
			"evidence": {
				"path": "evidence.json",
				"packet_id": packet.packet_id,
				"sha256": evidence_hash,
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
		bundle["bundle_id"] = bundle_identity(bundle)
		date_root = os.path.join(
			self.output_root,
			self.owner,
			"daily_blog",
			packet.report_date,
		)
		bundle_path = os.path.join(date_root, run_id)
		if os.path.exists(bundle_path):
			raise RuntimeError(f"Immutable publication run already exists: {bundle_path}")
		os.makedirs(date_root, exist_ok=True)
		stage = os.path.join(date_root, f".{run_id}.staging-{uuid.uuid4().hex}")
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
				os.path.join(stage, "editorial_projection.json"),
				projection_value,
			)
			daily_blog.io_utils.atomic_write_text(os.path.join(stage, "post.md"), post)
			for asset_path, contents in assets.items():
				destination = os.path.join(stage, asset_path)
				daily_blog.io_utils.atomic_write_bytes(destination, contents)
			os.replace(stage, bundle_path)
		except Exception:
			if os.path.exists(stage):
				shutil.rmtree(stage)
			raise
		latest = {
			"schema_version": daily_blog.schema.BUNDLE_SCHEMA_VERSION,
			"report_date": packet.report_date,
			"run_id": run_id,
			"bundle_id": bundle["bundle_id"],
			"bundle_path": run_id,
			"updated_at": daily_blog.schema.utc_now(),
		}
		daily_blog.io_utils.atomic_write_json(os.path.join(date_root, "latest.json"), latest)
		return bundle_path, bundle

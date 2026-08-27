"""Immutable publication bundle creation and stable per-date latest pointers."""

# Standard Library
import os
import shutil
import subprocess
import uuid
import pathlib

# local repo modules
import daily_blog.schema
import daily_blog.editorial
import daily_blog.io_utils


#============================================
def generator_revision(repository_root: str) -> str:
	"""Return the exact generator Git revision."""
	result = subprocess.run(
		["git", "-C", repository_root, "rev-parse", "HEAD"],
		check=False,
		text=True,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		timeout=60,
	)
	if result.returncode:
		message = result.stderr.strip() or result.stdout.strip()
		raise RuntimeError(f"Generator revision is unavailable: {message}")
	revision = result.stdout.strip()
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
	if bundle.get("bundle_id") != bundle_identity(bundle):
		raise RuntimeError("Cached publication bundle identity does not match its manifest.")
	contracts = bundle.get("contracts", {})
	expected_contracts = {
		"evidence_schema": daily_blog.schema.EVIDENCE_SCHEMA_VERSION,
		"prompt_version": daily_blog.schema.PROMPT_VERSION,
		"rubric_version": daily_blog.schema.RUBRIC_VERSION,
	}
	if contracts != expected_contracts or bundle.get("generator", {}).get("revision") != revision:
		raise RuntimeError("Cached publication bundle generator contracts have changed.")
	evidence = daily_blog.io_utils.read_json(os.path.join(bundle_path, "evidence.json"))
	if evidence != packet.to_dict():
		raise RuntimeError("Cached publication bundle evidence does not match the packet.")
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
	def __init__(self, output_root: str, owner: str, generator_root: str) -> None:
		"""Configure output ownership and generator revision source."""
		self.output_root = os.path.abspath(output_root)
		self.owner = owner
		self.generator_root = os.path.abspath(generator_root)

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
		assets: dict[str, bytes],
		candidates: list[daily_blog.editorial.CandidateResult],
		decision: daily_blog.editorial.EditorialDecision,
	) -> tuple[str, dict]:
		"""Write and atomically promote one immutable publication bundle."""
		if not packet.complete:
			raise RuntimeError("Publication bundles require complete evidence packets.")
		post = decision.post
		post_hash = daily_blog.io_utils.sha256_text(post)
		evidence_value = packet.to_dict()
		evidence_hash = daily_blog.io_utils.hash_value(evidence_value)
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
			"publication_quality": decision.publication_quality,
			"created_at": daily_blog.schema.utc_now(),
			"generator": {
				"run_id": run_id,
				"revision": generator_revision(self.generator_root),
				"version": daily_blog.schema.GENERATOR_VERSION,
			},
			"contracts": {
				"evidence_schema": daily_blog.schema.EVIDENCE_SCHEMA_VERSION,
				"prompt_version": daily_blog.schema.PROMPT_VERSION,
				"rubric_version": daily_blog.schema.RUBRIC_VERSION,
			},
			"evidence": {
				"path": "evidence.json",
				"packet_id": packet.packet_id,
				"sha256": evidence_hash,
			},
			"post": {"path": "post.md", "sha256": post_hash},
			"assets": asset_manifest,
			"candidates": candidate_summaries,
			"referee": {
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

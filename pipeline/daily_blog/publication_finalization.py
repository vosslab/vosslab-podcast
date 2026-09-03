"""Seal, import, and verify one already-written selected publication post."""

# Standard Library
import collections.abc
import dataclasses
import datetime
import os

# local repo modules
import daily_blog.artifacts
import daily_blog.activity
import daily_blog.io_utils
import daily_blog.locks
import daily_blog.publication_contract
import daily_blog.publication_admission
import daily_blog.publication_surface_contract
import daily_blog.publisher
import daily_blog.publisher_contract
import daily_blog.repository_contracts
import daily_blog.run_contracts
import daily_blog.run_state
import daily_blog.schema


#============================================
@dataclasses.dataclass(frozen=True)
class SealedPublicationInput:
	"""Exact Stage-8 inputs that may enter the sealed publication boundary."""

	report_date: str
	run_id: str
	output_root: str
	output_owner: str
	publisher_repository: str
	generator_identity: daily_blog.publication_contract.PublicationIdentity
	force_regeneration: bool
	roster: daily_blog.repository_contracts.RepositoryRoster
	publication_surface: daily_blog.publication_admission.PublicationSurface
	assets: dict[str, bytes]
	selected_post: daily_blog.artifacts.CompletePost
	active_roster: dict[str, object]

	#============================================
	def __post_init__(self) -> None:
		"""Reject malformed or cross-date values before durable publication I/O.

		ASVS 2.2.1, 2.2.3, and 15.3.5: strict types and coherent identities keep
		untrusted cache or publisher data from changing publication authority.
		"""
		if (
			type(self.report_date) is not str
			or datetime.date.fromisoformat(self.report_date).isoformat() != self.report_date
			or type(self.run_id) is not str
			or not self.run_id
			or type(self.output_root) is not str
			or not os.path.isabs(self.output_root)
			or type(self.output_owner) is not str
			or not self.output_owner
			or type(self.publisher_repository) is not str
			or not os.path.isabs(self.publisher_repository)
			or type(self.force_regeneration) is not bool
			or type(self.generator_identity) is not daily_blog.publication_contract.PublicationIdentity
			or type(self.roster) is not daily_blog.repository_contracts.RepositoryRoster
			or type(self.publication_surface) is not daily_blog.publication_admission.PublicationSurface
			or type(self.assets) is not dict
			or type(self.selected_post) is not daily_blog.artifacts.CompletePost
		):
			raise RuntimeError("Publication finalization input is invalid.")
		if (
			self.publication_surface.packet.report_date != self.report_date
			or self.selected_post.report_date != self.report_date
		):
			raise RuntimeError("Publication finalization input report date is inconsistent.")
		if any(type(path) is not str or type(contents) is not bytes for path, contents in self.assets.items()):
			raise RuntimeError("Publication finalization assets are invalid.")
		daily_blog.activity.validate_daily_active_roster(self.active_roster)


#============================================
@dataclasses.dataclass(frozen=True)
class PublicationFinalizationResult:
	"""The three verified durable outcomes of publication finalization."""

	bundle_path: str
	bundle: dict[str, object]
	transfer: daily_blog.publication_contract.SealedBundleTransfer
	site_import: dict[str, object]
	page_verification: dict[str, object]
	bundle_reused: bool


#============================================
def _validate_verified_page_receipt(value: object, bundle: dict, report_date: str) -> dict:
	"""Require a page verifier to preserve the sealed importer receipt.

	ASVS 1.5.2 and 11.4.3: accept only the exact bounded receipt schema and
	its SHA-256 identities before recording a reader-visible publication.
	"""
	if not isinstance(bundle, dict):
		raise RuntimeError("Page verification requires one sealed publication bundle.")
	if not isinstance(value, dict) or set(value) != (
		daily_blog.publisher.IMPORT_RECEIPT_FIELDS | {"rendered_page_sha256"}
	):
		raise RuntimeError("Page verification receipt has unsupported fields.")
	import_receipt = dict(value)
	page_sha256 = import_receipt.pop("rendered_page_sha256")
	validated = daily_blog.publisher.validate_import_receipt(
		import_receipt, bundle["bundle_sha256"], report_date,
	)
	if validated["best_artifact_id"] != bundle["best_artifact_id"]:
		raise RuntimeError("Page verification does not bind the selected artifact.")
	if (
		type(page_sha256) is not str
		or len(page_sha256) != 64
		or set(page_sha256) - set("0123456789abcdef")
	):
		raise RuntimeError("Page verification receipt has no valid rendered page identity.")
	validated["rendered_page_sha256"] = page_sha256
	return validated


#============================================
class PublicationFinalizationCoordinator:
	"""Own only durable bundle creation, publisher import, and page verification."""

	#============================================
	def __init__(
		self,
		value: SealedPublicationInput,
		cache: daily_blog.locks.PhaseCache,
		store: daily_blog.run_state.RunStore,
		record: daily_blog.run_contracts.RunRecord,
		start_phase: collections.abc.Callable[[str, object], str],
		complete_phase: collections.abc.Callable[[str, object, bool], str],
		publish: collections.abc.Callable,
		publisher_function: collections.abc.Callable,
		page_verifier: collections.abc.Callable,
	) -> None:
		"""Bind narrow lifecycle dependencies without importing orchestration.

		ASVS 2.3.1 and 15.4.2: the caller supplies its current store and record;
		this owner cannot manufacture a detached lifecycle or reopen a path that
		the publication contract has already validated.
		"""
		if (
			type(value) is not SealedPublicationInput
			or type(cache) is not daily_blog.locks.PhaseCache
			or type(store) is not daily_blog.run_state.RunStore
			or type(record) is not daily_blog.run_contracts.RunRecord
			or record.run_id != value.run_id
			or record.report_date != value.report_date
			or not all(callable(item) for item in (
				start_phase, complete_phase, publish, publisher_function, page_verifier,
			))
		):
			raise RuntimeError("Publication finalization dependencies are invalid.")
		self.value = value
		self.cache = cache
		self.store = store
		self.record = record
		self.start_phase = start_phase
		self.complete_phase = complete_phase
		self.publish = publish
		self.publisher_function = publisher_function
		self.page_verifier = page_verifier

	#============================================
	def create_or_reuse_bundle(self) -> tuple[str, dict, daily_blog.publication_contract.SealedBundleTransfer, bool]:
		"""Create or verify one descriptor-pinned reusable bundle."""
		value = self.value
		surface = value.publication_surface
		packet = surface.packet
		projection = surface.projection
		surface_value = daily_blog.publication_surface_contract.publication_surface_value(surface)
		phase_input = {
			"active_roster": value.active_roster,
			"repository_roster": value.roster.to_dict(),
			"packet_id": packet.packet_id,
			"projection_id": projection.projection_id,
			"publication_surface_id": surface_value["surface_id"],
			"best_artifact_id": value.selected_post.artifact_id,
			"post_content_hash": value.selected_post.content_hash,
			"asset_hashes": {
				path: daily_blog.io_utils.sha256_bytes(contents)
				for path, contents in value.assets.items()
			},
			"generator_revision": value.generator_identity.revision,
			"prompt_contract": value.generator_identity.prompt_contract_dict(),
			"bundle_schema": daily_blog.schema.BUNDLE_SCHEMA_VERSION,
		}
		input_hash = self.start_phase("bundle_creation", phase_input)
		cached = self.cache.load_json("bundle_creation", input_hash, "bundle.json")
		reused = cached is not None
		if cached is None:
			writer = daily_blog.publication_contract.BundleWriter(
				value.output_root, value.output_owner, value.generator_identity,
			)
			bundle_path, bundle, transfer = writer.write(
				value.run_id, surface, value.assets, value.roster,
				value.selected_post, value.active_roster,
			)
			self.cache.store_json("bundle_creation", input_hash, "bundle.json", {
				"bundle_path": bundle_path, "bundle": bundle,
			})
		else:
			date_root = os.path.join(
				value.output_root, value.output_owner, "daily_blog", value.report_date,
			)
			bundle_path, bundle, transfer = daily_blog.publication_contract.load_reusable_bundle(
				dict(cached), date_root, surface, value.assets,
				value.generator_identity, value.roster, value.active_roster,
			)
		if bundle.get("best_artifact_id") != value.selected_post.artifact_id:
			raise RuntimeError("Publication bundle does not bind the selected artifact.")
		self.store.write_artifact("publication_bundle.json", bundle)
		self.record.publication_bundle = {
			"bundle_sha256": bundle["bundle_sha256"],
			"path": self.store.derive_output_logical_path(bundle_path),
			"origin_run_id": bundle["generator"]["run_id"],
			"reused": reused,
			"best_artifact_id": bundle["best_artifact_id"],
		}
		self.complete_phase("bundle_creation", bundle, reused)
		return bundle_path, bundle, transfer, reused

	#============================================
	def import_bundle(
		self, transfer: daily_blog.publication_contract.SealedBundleTransfer, bundle: dict,
	) -> dict:
		"""Import the exact sealed byte snapshot with replacement intent."""
		if type(transfer) is not daily_blog.publication_contract.SealedBundleTransfer or type(bundle) is not dict:
			raise RuntimeError("Publication import requires one sealed bundle transfer.")
		if transfer.report_date != self.value.report_date or transfer.bundle_sha256 != bundle.get("bundle_sha256"):
			raise RuntimeError("Publication import transfer does not bind the sealed bundle.")
		phase_input = {
			"bundle_sha256": bundle["bundle_sha256"],
			"publisher_repository": self.value.publisher_repository,
			"replace_existing": self.value.force_regeneration,
		}
		self.start_phase("site_import", phase_input)
		publisher_result = self.publish(
			self.publisher_function, self.value.publisher_repository, transfer,
			replace_existing=self.value.force_regeneration,
		)
		result = daily_blog.publisher.validate_import_receipt(
			publisher_result, bundle["bundle_sha256"], self.value.report_date,
		)
		if result["best_artifact_id"] != bundle["best_artifact_id"]:
			raise RuntimeError("Site import receipt does not bind the selected artifact.")
		reused = result["status"] == "idempotent"
		self.store.write_artifact("site_import.json", result)
		self.complete_phase("site_import", result, reused)
		return result

	#============================================
	def verify_page(self, site_import: dict, bundle: dict) -> dict:
		"""Verify the reader page against the exact durable importer receipt."""
		if type(site_import) is not dict or type(bundle) is not dict:
			raise RuntimeError("Page verification requires sealed import data.")
		phase_input = {
			"bundle_sha256": bundle["bundle_sha256"],
			"best_artifact_id": bundle["best_artifact_id"],
			"site_import_status": site_import["status"],
		}
		self.start_phase("page_verification", phase_input)
		result = self.page_verifier(self.value.publisher_repository, site_import)
		validated = _validate_verified_page_receipt(result, bundle, self.value.report_date)
		site_import = daily_blog.publisher.validate_import_receipt(
			site_import, bundle["bundle_sha256"], self.value.report_date,
		)
		if any(validated[field] != site_import[field] for field in site_import):
			raise RuntimeError("Page verification receipt does not preserve the site-import receipt.")
		self.store.write_artifact("page_verification.json", validated)
		self.record.publication_bundle["site_import"] = site_import
		self.record.publication_bundle["page_verification"] = validated
		self.store.save(self.record)
		self.complete_phase("page_verification", validated, False)
		return validated

	#============================================
	def finalize(self, post_writer: collections.abc.Callable[[], None]) -> PublicationFinalizationResult:
		"""Materialize, deliver, render, and verify one producer-approved post."""
		if not callable(post_writer):
			raise RuntimeError("Publication finalization requires one post writer.")
		bundle_path, bundle, transfer, reused = self.create_or_reuse_bundle()
		post_writer()
		site_import = self.import_bundle(transfer, bundle)
		page_verification = self.verify_page(site_import, bundle)
		return PublicationFinalizationResult(
			bundle_path, bundle, transfer, site_import, page_verification, reused,
		)

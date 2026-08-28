"""Date-driven orchestration for evidence, editorial, bundling, and site import."""

# Standard Library
import os
import uuid
import datetime
import dataclasses

# local repo modules
import daily_blog.config
import daily_blog.schema
import daily_blog.locks
import daily_blog.mirrors
import daily_blog.activity
import daily_blog.evidence
import daily_blog.projection
import daily_blog.bundles
import daily_blog.editorial
import daily_blog.publisher
import daily_blog.run_state
import daily_blog.io_utils


#============================================
def new_run_id() -> str:
	"""Create a sortable unique run identity."""
	moment = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
	run_id = f"{moment}-{uuid.uuid4().hex[:10]}"
	return run_id


#============================================
def _stable_mirror_input(entries: list[dict]) -> list[dict]:
	"""Remove refresh timestamps while retaining every object-location input."""
	values = []
	for entry in entries:
		values.append(
			{
				"repository": entry["repository"],
				"repository_url": entry["repository_url"],
				"cache_path": entry["cache_path"],
				"default_revision": entry["default_revision"],
				"object_available": entry["object_available"],
				"ref_fingerprint": entry["ref_fingerprint"],
			}
		)
	return values


#============================================
def _cache_assets(
	cache: daily_blog.locks.PhaseCache,
	phase: str,
	input_hash: str,
	assets: dict[str, bytes],
) -> None:
	"""Persist selected evidence assets with a hash-verified manifest."""
	asset_dir = cache.asset_dir(phase, input_hash)
	manifest = {}
	for asset_path, contents in assets.items():
		destination = os.path.join(asset_dir, os.path.basename(asset_path))
		daily_blog.io_utils.atomic_write_bytes(destination, contents)
		manifest[asset_path] = daily_blog.io_utils.sha256_bytes(contents)
	cache.store_json(phase, input_hash, "assets.json", manifest)


#============================================
def _load_cached_assets(
	cache: daily_blog.locks.PhaseCache,
	phase: str,
	input_hash: str,
	packet: daily_blog.schema.EvidencePacket,
) -> dict[str, bytes]:
	"""Load and verify all asset bytes required by one cached evidence packet."""
	assets = {}
	asset_dir = cache.asset_dir(phase, input_hash)
	manifest = cache.load_json(phase, input_hash, "assets.json")
	if not isinstance(manifest, dict):
		raise RuntimeError("Cached evidence asset manifest is missing.")
	for item in packet.items:
		if not item.asset_path:
			continue
		path = os.path.join(asset_dir, os.path.basename(item.asset_path))
		if not os.path.isfile(path):
			raise RuntimeError(f"Cached evidence asset is missing: {item.asset_path}")
		with open(path, "rb") as handle:
			contents = handle.read()
		if manifest.get(item.asset_path) != daily_blog.io_utils.sha256_bytes(contents):
			raise RuntimeError(f"Cached evidence asset hash mismatch: {item.asset_path}")
		assets[item.asset_path] = contents
	if set(manifest) != set(assets):
		raise RuntimeError("Cached evidence assets do not match their manifest.")
	return assets


#============================================
def _decision_value(decision: daily_blog.editorial.EditorialDecision) -> dict:
	"""Return one run-safe referee summary without private candidate content."""
	return {
		"winner": decision.winner,
		"reason": decision.reason,
		"evidence_quality": decision.evidence_quality,
		"confidence": decision.confidence,
		"projection_id": decision.projection_id,
		"post_hash": daily_blog.io_utils.sha256_text(decision.post),
		"anonymous_mapping": decision.anonymous_mapping,
	}


class DailyPublicationOrchestrator:
	"""Execute the nine legal phases for one immutable daily run."""

	#============================================
	def __init__(
		self,
		config: daily_blog.config.DailyBlogConfig,
		report_date: str,
		route_runner: object | None = None,
		publisher_function: object | None = None,
		refresh_mirrors: bool = True,
	) -> None:
		"""Bind dependencies while preserving replaceable test boundaries."""
		daily_blog.activity.build_date_window(report_date, config.report_timezone)
		self.config = config
		self.report_date = report_date
		self.route_runner = route_runner
		self.publisher_function = publisher_function or daily_blog.publisher.import_bundle
		self.refresh_mirrors = refresh_mirrors
		self.generator_root = daily_blog.io_utils.repository_root(__file__)
		self.generator_revision = daily_blog.bundles.generator_revision(
			self.generator_root,
			config.settings_path,
		)
		self.run_id = new_run_id()
		self.store = daily_blog.run_state.RunStore(
			config.output_root,
			config.output_owner,
			report_date,
			self.run_id,
		)
		self.record = daily_blog.schema.RunRecord.create(self.run_id, report_date)
		cache_root = os.path.join(
			config.output_root,
			config.output_owner,
			"daily_blog_cache",
		)
		self.cache = daily_blog.locks.PhaseCache(cache_root)
		self.store.save(self.record)
		self.store.append_event(
			"daily_publication.run_started", {"state": self.record.state}
		)

	#============================================
	def _start(self, phase: str, input_value: object) -> str:
		"""Start one phase and persist its canonical input hash."""
		source_bound_input = {
			"generator_revision": self.generator_revision,
			"phase_input": input_value,
		}
		input_hash = daily_blog.io_utils.hash_value(source_bound_input)
		self.record.start_phase(phase, input_hash)
		self.store.save(self.record)
		self.store.append_event("daily_publication.phase_started", {"phase": phase})
		return input_hash

	#============================================
	def _complete(self, phase: str, output_value: object, reused: bool = False) -> str:
		"""Complete one phase and persist its canonical output hash."""
		output_hash = daily_blog.io_utils.hash_value(output_value)
		self.record.complete_phase(phase, output_hash, reused=reused)
		self.store.save(self.record)
		self.store.append_event(
			"daily_publication.phase_completed", {"phase": phase, "reused": reused}
		)
		return output_hash

	#============================================
	def _fail_current(self, error: Exception) -> None:
		"""Keep raw failure text in run state and emit only its class to lifecycle logs."""
		phase = self.record.current_phase
		if not phase:
			return
		self.record.fail_phase(phase, error.__class__.__name__, str(error))
		self.store.save(self.record)
		self.store.append_event(
			"daily_publication.phase_failed",
			{"error_class": error.__class__.__name__, "phase": phase},
		)

	#============================================
	def _mirror_phase(self) -> list[dict]:
		"""Refresh durable mirrors and persist their complete manifest."""
		phase_input = {
			"cache_root": self.config.mirror_cache_root,
			"repository_urls": list(self.config.repository_urls),
			"refresh": self.refresh_mirrors,
		}
		self._start("mirror_refresh", phase_input)
		manager = daily_blog.mirrors.MirrorManager(
			self.config.mirror_cache_root,
			self.config.repository_urls,
		)
		entries = manager.refresh_all(refresh=self.refresh_mirrors)
		self.store.write_artifact("mirror_manifest.json", entries)
		failed = [entry for entry in entries if entry["refresh_result"] == "failed"]
		if failed:
			names = ", ".join(entry["repository"] for entry in failed)
			raise RuntimeError(f"Mirror refresh failed for: {names}")
		self._complete("mirror_refresh", entries)
		return entries

	#============================================
	def _activity_phase(
		self,
		mirror_entries: list[dict],
	) -> list[daily_blog.schema.RepositoryActivity]:
		"""Locate activity or restore the exact matching typed artifact."""
		phase_input = {
			"report_date": self.report_date,
			"timezone": self.config.report_timezone,
			"identity_names": list(self.config.identity_names),
			"identity_emails": list(self.config.identity_emails),
			"mirrors": _stable_mirror_input(mirror_entries),
		}
		input_hash = self._start("activity_location", phase_input)
		cached = self.cache.load_json("activity_location", input_hash, "activity.json")
		reused = cached is not None
		if cached is None:
			activities = daily_blog.activity.locate_activity(
				self.report_date,
				self.config.report_timezone,
				mirror_entries,
				self.config.identity_names,
				self.config.identity_emails,
			)
			value = [activity.to_dict() for activity in activities]
			self.cache.store_json("activity_location", input_hash, "activity.json", value)
		else:
			value = list(cached)
			activities = [
				daily_blog.schema.RepositoryActivity.from_dict(item) for item in value
			]
		self.store.write_artifact("activity.json", value)
		self._complete("activity_location", value, reused=reused)
		return activities

	#============================================
	def _evidence_phase(
		self,
		mirror_entries: list[dict],
		activities: list[daily_blog.schema.RepositoryActivity],
	) -> tuple[daily_blog.schema.EvidencePacket, dict[str, bytes]]:
		"""Assemble evidence or restore one hash-verified packet and assets."""
		activity_value = [activity.to_dict() for activity in activities]
		phase_input = {
			"activity": activity_value,
			"collection_limits": self.config.collection_limits,
			"schema": daily_blog.schema.EVIDENCE_SCHEMA_VERSION,
			"mirrors": _stable_mirror_input(mirror_entries),
		}
		input_hash = self._start("evidence_assembly", phase_input)
		cached = self.cache.load_json("evidence_assembly", input_hash, "evidence.json")
		reused = cached is not None
		if cached is None:
			assembler = daily_blog.evidence.EvidenceAssembler(
				self.report_date,
				self.config.report_timezone,
				self.config.collection_limits,
			)
			packet, assets = assembler.assemble(mirror_entries, activities)
			self.cache.store_json(
				"evidence_assembly", input_hash, "evidence.json", packet.to_dict()
			)
			_cache_assets(self.cache, "evidence_assembly", input_hash, assets)
		else:
			packet = daily_blog.schema.EvidencePacket.from_dict(dict(cached))
			assets = _load_cached_assets(
				self.cache, "evidence_assembly", input_hash, packet
			)
		if not packet.complete:
			raise RuntimeError("Evidence assembly is incomplete.")
		self.store.write_artifact("evidence.json", packet.to_dict())
		self.record.evidence_packet = {
			"packet_id": packet.packet_id,
			"artifact": "evidence.json",
		}
		self._complete("evidence_assembly", packet.to_dict(), reused=reused)
		return packet, assets

	#============================================
	def _projection_phase(
		self,
		packet: daily_blog.schema.EvidencePacket,
	) -> daily_blog.schema.EditorialProjection:
		"""Build or restore the exact bounded editorial projection."""
		phase_input = {
			"packet_id": packet.packet_id,
			"projection_policy": daily_blog.projection.PROJECTION_POLICY_VERSION,
			"projection_limits": self.config.projection_limits,
			"schema": daily_blog.schema.PROJECTION_SCHEMA_VERSION,
		}
		input_hash = self._start("editorial_projection", phase_input)
		cached = self.cache.load_json(
			"editorial_projection",
			input_hash,
			"editorial_projection.json",
		)
		reused = cached is not None
		if cached is None:
			projection = daily_blog.projection.build_projection(
				packet,
				self.config.projection_limits,
			)
			self.cache.store_json(
				"editorial_projection",
				input_hash,
				"editorial_projection.json",
				projection.to_dict(),
			)
		else:
			projection = daily_blog.schema.EditorialProjection.from_dict(dict(cached))
		if projection.packet_id != packet.packet_id:
			raise RuntimeError("Editorial projection does not match the evidence packet.")
		self.store.write_artifact("editorial_projection.json", projection.to_dict())
		self.record.editorial_projection = {
			"projection_id": projection.projection_id,
			"artifact": "editorial_projection.json",
		}
		self._complete("editorial_projection", projection.to_dict(), reused=reused)
		return projection

	#============================================
	def _author_phase(
		self,
		packet: daily_blog.schema.EvidencePacket,
		projection: daily_blog.schema.EditorialProjection,
	) -> tuple[str, str, list[dict], list[dict], bool]:
		"""Generate or reuse complete isolated-author artifacts."""
		phase_input = {
			"packet_id": packet.packet_id,
			"projection_id": projection.projection_id,
			"prompt_contract": daily_blog.editorial.prompt_contract_identity(),
			"prompt_limit": self.config.prompt_limits["author_chars"],
			"generator_revision": self.generator_revision,
			"routes": [dataclasses.asdict(route) for route in self.config.author_routes],
		}
		input_hash = self._start("author_generation", phase_input)
		artifact_run_id = "artifact-" + input_hash[:24]
		cached = self.cache.load_json("author_generation", input_hash, "candidates.json")
		reused = cached is not None
		if cached is None:
			canonical = daily_blog.editorial.generate_candidates(
				packet,
				projection,
				artifact_run_id,
				self.config,
				runner=self.route_runner,
			)
			canonical = daily_blog.editorial.validate_raw_candidates(canonical)
		else:
			canonical = daily_blog.editorial.validate_raw_candidates(cached)
		current = daily_blog.editorial.rebind_raw_candidates(
			canonical, artifact_run_id, self.run_id
		)
		self.store.write_artifact("candidates.json", current)
		self._complete("author_generation", current, reused=reused)
		return input_hash, artifact_run_id, canonical, current, reused

	#============================================
	def _validation_phase(
		self,
		packet: daily_blog.schema.EvidencePacket,
		projection: daily_blog.schema.EditorialProjection,
		author_hash: str,
		artifact_run_id: str,
		canonical_raw: list[dict],
		author_reused: bool,
	) -> tuple[list[daily_blog.editorial.CandidateResult], list[daily_blog.editorial.CandidateResult]]:
		"""Validate canonical candidates and bind their metadata to this run."""
		phase_input = {
			"packet_id": packet.packet_id,
			"projection_id": projection.projection_id,
			"candidate_hashes": [item["post_hash"] for item in canonical_raw],
			"generator_revision": self.generator_revision,
		}
		input_hash = self._start("candidate_validation", phase_input)
		cached = self.cache.load_json(
			"candidate_validation", input_hash, "validation.json"
		)
		reused = cached is not None
		if cached is None:
			canonical = daily_blog.editorial.validate_candidates(
				canonical_raw,
				packet,
				projection,
				artifact_run_id,
			)
		else:
			canonical = [
				daily_blog.editorial.CandidateResult.from_cache_dict(item)
				for item in list(cached)
			]
		current = daily_blog.editorial.rebind_candidates(
			canonical, artifact_run_id, self.run_id
		)
		if all(candidate.valid for candidate in canonical):
			if not author_reused:
				self.cache.store_json(
					"author_generation", author_hash, "candidates.json", canonical_raw
				)
			if not reused:
				self.cache.store_json(
					"candidate_validation",
					input_hash,
					"validation.json",
					[candidate.to_cache_dict() for candidate in canonical],
				)
		value = [
			candidate.public_summary(f"candidate_{index + 1}")
			for index, candidate in enumerate(current)
		]
		self.store.write_artifact("candidate_validation.json", value)
		self._complete("candidate_validation", value, reused=reused)
		return canonical, current

	#============================================
	def _referee_phase(
		self,
		packet: daily_blog.schema.EvidencePacket,
		projection: daily_blog.schema.EditorialProjection,
		artifact_run_id: str,
		canonical_candidates: list[daily_blog.editorial.CandidateResult],
		current_candidates: list[daily_blog.editorial.CandidateResult],
	) -> tuple[daily_blog.editorial.EditorialDecision, daily_blog.editorial.EditorialDecision]:
		"""Select canonical editorial content and bind it to this run."""
		phase_input = {
			"packet_id": packet.packet_id,
			"projection_id": projection.projection_id,
			"candidates": [candidate.to_cache_dict() for candidate in canonical_candidates],
			"route": dataclasses.asdict(self.config.referee_route),
			"prompt_contract": daily_blog.editorial.prompt_contract_identity(),
			"prompt_limit": self.config.prompt_limits["referee_chars"],
			"generator_revision": self.generator_revision,
		}
		input_hash = self._start("referee_selection", phase_input)
		cached = self.cache.load_json("referee_selection", input_hash, "decision.json")
		reused = cached is not None
		if cached is None:
			canonical = daily_blog.editorial.select_candidate(
				packet,
				projection,
				artifact_run_id,
				canonical_candidates,
				self.config,
				runner=self.route_runner,
			)
			self.cache.store_json(
				"referee_selection",
				input_hash,
				"decision.json",
				canonical.to_cache_dict(),
			)
		else:
			canonical = daily_blog.editorial.EditorialDecision.from_cache_dict(dict(cached))
		current = daily_blog.editorial.materialize_decision(
			canonical,
			projection,
			self.run_id,
			current_candidates,
		)
		value = _decision_value(current)
		self.store.write_artifact("referee.json", value)
		self._complete("referee_selection", value, reused=reused)
		return canonical, current

	#============================================
	def _bundle_phase(
		self,
		packet: daily_blog.schema.EvidencePacket,
		projection: daily_blog.schema.EditorialProjection,
		assets: dict[str, bytes],
		canonical_candidates: list[daily_blog.editorial.CandidateResult],
		current_candidates: list[daily_blog.editorial.CandidateResult],
		canonical_decision: daily_blog.editorial.EditorialDecision,
		current_decision: daily_blog.editorial.EditorialDecision,
	) -> tuple[str, dict]:
		"""Create or reuse one verified immutable publication bundle."""
		phase_input = {
			"packet_id": packet.packet_id,
			"projection_id": projection.projection_id,
			"candidates": [candidate.to_cache_dict() for candidate in canonical_candidates],
			"decision": canonical_decision.to_cache_dict(),
			"asset_hashes": {
				path: daily_blog.io_utils.sha256_bytes(contents)
				for path, contents in assets.items()
			},
			"generator_revision": self.generator_revision,
			"bundle_schema": daily_blog.schema.BUNDLE_SCHEMA_VERSION,
		}
		input_hash = self._start("bundle_creation", phase_input)
		cached = self.cache.load_json("bundle_creation", input_hash, "bundle.json")
		reused = cached is not None
		if cached is None:
			writer = daily_blog.bundles.BundleWriter(
				self.config.output_root,
				self.config.output_owner,
				self.generator_revision,
			)
			bundle_path, bundle = writer.write(
				self.run_id,
				packet,
				projection,
				assets,
				current_candidates,
				current_decision,
			)
			self.cache.store_json(
				"bundle_creation",
				input_hash,
				"bundle.json",
				{"bundle_path": bundle_path, "bundle": bundle},
			)
		else:
			date_root = os.path.join(
				self.config.output_root,
				self.config.output_owner,
				"daily_blog",
				self.report_date,
			)
			bundle_path, bundle = daily_blog.bundles.load_reusable_bundle(
				dict(cached),
				date_root,
				packet,
				projection,
				assets,
				self.generator_revision,
			)
		self.store.write_artifact("publication_bundle.json", bundle)
		self.record.publication_bundle = {
			"bundle_id": bundle["bundle_id"],
			"path": bundle_path,
			"origin_run_id": bundle["generator"]["run_id"],
			"reused": reused,
		}
		self._complete("bundle_creation", bundle, reused=reused)
		return bundle_path, bundle

	#============================================
	def _site_import_phase(self, bundle_path: str, bundle: dict) -> dict:
		"""Invoke the idempotent publisher and record whether it reused the release."""
		phase_input = {
			"bundle_id": bundle["bundle_id"],
			"publisher_repository": self.config.daily_blog_repository,
		}
		self._start("site_import", phase_input)
		publisher_result = self.publisher_function(self.config.daily_blog_repository, bundle_path)
		result = daily_blog.schema.validate_site_import_result(
			publisher_result,
			bundle["bundle_id"],
			self.report_date,
		)
		reused = result["status"] == "idempotent"
		self.store.write_artifact("site_import.json", result)
		self._complete("site_import", result, reused=reused)
		return result

	#============================================
	def run(self) -> tuple[str, dict]:
		"""Sequence the nine typed phases and persist any terminal failure."""
		try:
			mirrors = self._mirror_phase()
			activities = self._activity_phase(mirrors)
			packet, assets = self._evidence_phase(mirrors, activities)
			projection = self._projection_phase(packet)
			author_hash, artifact_id, canonical_raw, _current_raw, author_reused = (
				self._author_phase(packet, projection)
			)
			canonical_candidates, current_candidates = self._validation_phase(
				packet,
				projection,
				author_hash,
				artifact_id,
				canonical_raw,
				author_reused,
			)
			canonical_decision, current_decision = self._referee_phase(
				packet,
				projection,
				artifact_id,
				canonical_candidates,
				current_candidates,
			)
			bundle_path, bundle = self._bundle_phase(
				packet,
				projection,
				assets,
				canonical_candidates,
				current_candidates,
				canonical_decision,
				current_decision,
			)
			site_import = self._site_import_phase(bundle_path, bundle)
			self.record.complete()
			self.store.save(self.record)
			self.store.append_event(
				"daily_publication.run_completed",
				{
					"bundle_id": bundle["bundle_id"],
					"site_import_status": site_import["status"],
					"state": self.record.state,
				},
			)
			return bundle_path, bundle
		except Exception as error:
			self._fail_current(error)
			raise


#============================================
def run_daily_publication(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
	route_runner: object | None = None,
	publisher_function: object | None = None,
	refresh_mirrors: bool = True,
) -> tuple[str, dict]:
	"""Acquire the per-date lock and execute one complete immutable run."""
	lock_path = os.path.join(
		config.output_root,
		config.output_owner,
		"daily_blog_locks",
		f"{report_date}.lock",
	)
	with daily_blog.locks.FileLock(lock_path):
		orchestrator = DailyPublicationOrchestrator(
			config,
			report_date,
			route_runner=route_runner,
			publisher_function=publisher_function,
			refresh_mirrors=refresh_mirrors,
		)
		result = orchestrator.run()
	return result

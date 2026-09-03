"""Acquire the sealed evidence inputs consumed by daily editorial publication."""

# Standard Library
import os
import dataclasses
import collections.abc

# local repo modules
import daily_blog.activity
import daily_blog.config
import daily_blog.io_utils
import daily_blog.locks
import daily_blog.publication_workflow
import daily_blog.repository_contracts
import daily_blog.repositories
import daily_blog.roster_snapshots
import daily_blog.run_contracts
import daily_blog.run_state
import daily_blog.schema


@dataclasses.dataclass(frozen=True)
class AcquisitionDependencies:
	"""Bind only the durable inputs and lifecycle seams needed for acquisition."""

	config: daily_blog.config.DailyBlogConfig
	runtime: daily_blog.publication_workflow.PublicationRuntime
	report_date: str
	prompt_contract: dict[str, object]
	generator_revision: str
	repository_loader: collections.abc.Callable[[str, str], daily_blog.repository_contracts.RepositoryRoster]
	refresh_mirrors: bool
	store: daily_blog.run_state.RunStore
	record: daily_blog.run_contracts.RunRecord
	cache: daily_blog.locks.PhaseCache
	start: collections.abc.Callable[[str, object], str]
	complete: collections.abc.Callable[[str, object, bool], str]


@dataclasses.dataclass(frozen=True)
class AcquisitionResult:
	"""Return the sealed evidence handoff consumed by repository editorial."""

	roster: daily_blog.repository_contracts.RepositoryRoster
	mirrors: tuple[dict[str, object], ...]
	activities: tuple[daily_blog.schema.RepositoryActivity, ...]
	packet: daily_blog.schema.EvidencePacket
	assets: dict[str, bytes]


class AcquisitionCoordinator:
	"""Persist repository, mirror, activity, and complete evidence in order."""

	#============================================
	def __init__(self, dependencies: AcquisitionDependencies) -> None:
		"""Retain one exact dependency object for the complete acquisition sequence."""
		if type(dependencies) is not AcquisitionDependencies:
			raise RuntimeError("Acquisition dependencies must be exact.")
		self.dependencies = dependencies

	#============================================
	def acquire(self) -> AcquisitionResult:
		"""Build and return the immutable acquisition handoff in durable phase order."""
		commit_references = self._commit_inventory()
		roster = self._repository_phase()
		active_repositories = set(daily_blog.activity.commit_repositories(
			self.dependencies.config.output_owner, commit_references,
		))
		active_records = [
			record for record in roster.repositories
			if record.repository in active_repositories
		]
		if active_records:
			active_roster = daily_blog.repository_contracts.RepositoryRoster.create(
				roster.owner, active_records,
			)
			mirrors = self._mirror_phase(active_roster)
		else:
			mirrors = self._empty_mirror_phase(roster)
		activities = self._activity_phase(mirrors, commit_references)
		packet, assets = self._evidence_phase(mirrors, activities)
		result = AcquisitionResult(
			roster=roster,
			mirrors=tuple(mirrors),
			activities=tuple(activities),
			packet=packet,
			assets=assets,
		)
		return result

	#============================================
	def _commit_inventory(self) -> list[dict]:
		"""Write Step 0's local account/date commit inventory before LLM work."""
		config = self.dependencies.config
		commits = daily_blog.publication_workflow.discover_daily_commits(
			self.dependencies.runtime, config.output_owner,
			self.dependencies.report_date, config.output_root,
		)
		if type(commits) is not list:
			raise RuntimeError("Daily commit discovery must return a list.")
		document = daily_blog.activity.render_daily_commits(
			config.output_owner, self.dependencies.report_date, commits,
		)
		self.dependencies.store.write_document("daily_commits.md", document)
		return commits

	#============================================
	def _repository_phase(self) -> daily_blog.repository_contracts.RepositoryRoster:
		"""Acquire, reparse, snapshot, and persist the authoritative owner roster."""
		config = self.dependencies.config
		phase_input = {
			"owner": config.output_owner,
			"policy": daily_blog.repositories.REPOSITORY_POLICY_VERSION,
			"schema": daily_blog.repository_contracts.REPOSITORY_ROSTER_SCHEMA_VERSION,
		}
		self.dependencies.start("repository_discovery", phase_input)
		roster = self.dependencies.repository_loader(config.output_owner, config.output_root)
		roster = daily_blog.repository_contracts.RepositoryRoster.from_dict(roster.to_dict())
		if roster.owner.casefold() != config.output_owner.casefold():
			raise RuntimeError("Repository roster owner does not match publication owner.")
		snapshot_path, snapshot_identity = daily_blog.roster_snapshots.write_repository_roster_snapshot(
			config.output_root, config.output_owner, roster,
		)
		verified_roster, verified_identity = daily_blog.roster_snapshots.load_repository_roster_snapshot(
			config.output_root, config.output_owner, snapshot_path,
		)
		if verified_roster != roster or verified_identity != snapshot_identity:
			raise RuntimeError("Repository roster snapshot verification does not match discovery.")
		value = roster.to_dict()
		self.dependencies.store.write_artifact("repository_roster.json", value)
		self.dependencies.store.write_artifact("prompt_contract.json", self.dependencies.prompt_contract)
		self.dependencies.record.repository_roster = {
			"roster_id": roster.roster_id,
			"artifact": "repository_roster.json",
			"snapshot_path": self.dependencies.store.derive_output_logical_path(snapshot_path),
			"snapshot_identity": snapshot_identity,
		}
		self.dependencies.complete("repository_discovery", value, False)
		return roster

	#============================================
	def _mirror_phase(
		self, roster: daily_blog.repository_contracts.RepositoryRoster,
	) -> list[dict[str, object]]:
		"""Refresh mirrors and reject failed refreshes before any downstream reader."""
		config = self.dependencies.config
		phase_input = {
			"cache_root": config.mirror_cache_root,
			"roster_id": roster.roster_id,
			"refresh": self.dependencies.refresh_mirrors,
		}
		self.dependencies.start("mirror_refresh", phase_input)
		entries = daily_blog.publication_workflow.refresh_mirrors(
			self.dependencies.runtime, config, roster, self.dependencies.refresh_mirrors,
		)
		self.dependencies.store.write_artifact("mirror_manifest.json", entries)
		failed = [entry for entry in entries if entry["refresh_result"] == "failed"]
		if failed:
			names = ", ".join(entry["repository"] for entry in failed)
			raise RuntimeError(f"Mirror refresh failed for: {names}")
		self.dependencies.complete("mirror_refresh", entries, False)
		return entries

	#============================================
	def _empty_mirror_phase(
		self, roster: daily_blog.repository_contracts.RepositoryRoster,
	) -> list[dict[str, object]]:
		"""Record a complete no-op mirror phase when Step 0 found no active repositories."""
		phase_input = {
			"cache_root": self.dependencies.config.mirror_cache_root,
			"roster_id": roster.roster_id,
			"repositories": [],
			"refresh": False,
		}
		self.dependencies.start("mirror_refresh", phase_input)
		entries: list[dict[str, object]] = []
		self.dependencies.store.write_artifact("mirror_manifest.json", entries)
		self.dependencies.complete("mirror_refresh", entries, False)
		return entries

	#============================================
	def _activity_phase(
		self, mirror_entries: list[dict[str, object]], commit_references: list[dict],
	) -> list[daily_blog.schema.RepositoryActivity]:
		"""Locate typed activity or restore it only through its schema parser."""
		config = self.dependencies.config
		phase_input = {
			"report_date": self.dependencies.report_date,
			"timezone": config.report_timezone,
			"github_commits": [
				{"repository": item.get("repository"), "sha": item.get("sha")}
				for item in commit_references
			],
			"mirrors": _stable_mirror_input(mirror_entries),
		}
		input_hash = self.dependencies.start("activity_location", phase_input)
		cached = self.dependencies.cache.load_json("activity_location", input_hash, "activity.json")
		reused = cached is not None
		if cached is None:
			activities = daily_blog.publication_workflow.locate_activity(
				self.dependencies.runtime, self.dependencies.report_date, config.report_timezone,
				mirror_entries, commit_references, config.output_owner,
			)
			value = [activity.to_dict() for activity in activities]
			self.dependencies.cache.store_json("activity_location", input_hash, "activity.json", value)
		else:
			value = list(cached)
			activities = [daily_blog.schema.RepositoryActivity.from_dict(item) for item in value]
		self.dependencies.store.write_artifact("activity.json", value)
		self.dependencies.complete("activity_location", value, reused)
		return activities

	#============================================
	def _evidence_phase(
		self,
		mirror_entries: list[dict[str, object]],
		activities: list[daily_blog.schema.RepositoryActivity],
	) -> tuple[daily_blog.schema.EvidencePacket, dict[str, bytes]]:
		"""Assemble complete evidence or restore packet and declared verified assets."""
		config = self.dependencies.config
		activity_value = [activity.to_dict() for activity in activities]
		phase_input = {
			"report_date": self.dependencies.report_date,
			"timezone": config.report_timezone,
			"activity": activity_value,
			"collection_limits": config.collection_limits,
			"schema": daily_blog.schema.EVIDENCE_SCHEMA_VERSION,
			"mirrors": _stable_mirror_input(mirror_entries),
		}
		input_hash = self.dependencies.start("evidence_assembly", phase_input)
		cached = self.dependencies.cache.load_json("evidence_assembly", input_hash, "evidence.json")
		reused = cached is not None
		if cached is None:
			packet, assets = daily_blog.publication_workflow.assemble_evidence(
				self.dependencies.runtime, self.dependencies.report_date, config.report_timezone,
				config.collection_limits, mirror_entries, activities,
			)
			# The companion assets are complete before the packet makes this cache entry reusable.
			_cache_assets(self.dependencies.cache, "evidence_assembly", input_hash, packet, assets)
			self.dependencies.cache.store_json(
				"evidence_assembly", input_hash, "evidence.json", packet.to_dict(),
			)
		else:
			packet = daily_blog.schema.EvidencePacket.from_dict(dict(cached))
			if (
				packet.report_date != self.dependencies.report_date
				or packet.timezone != config.report_timezone
			):
				raise RuntimeError("Cached evidence packet date or timezone does not match the request.")
			try:
				assets = _load_cached_assets(
					self.dependencies.cache, "evidence_assembly", input_hash, packet,
				)
			except RuntimeError:
				# A packet is not reusable without its verified companion assets. Rebuild the
				# whole entry instead of treating a partial cache write as authoritative.
				packet, assets = daily_blog.publication_workflow.assemble_evidence(
					self.dependencies.runtime, self.dependencies.report_date, config.report_timezone,
					config.collection_limits, mirror_entries, activities,
				)
				_cache_assets(self.dependencies.cache, "evidence_assembly", input_hash, packet, assets)
				self.dependencies.cache.store_json(
					"evidence_assembly", input_hash, "evidence.json", packet.to_dict(),
				)
				reused = False
		if not packet.complete:
			raise RuntimeError("Evidence assembly is incomplete.")
		self.dependencies.store.write_artifact("evidence.json", packet.to_dict())
		self.dependencies.record.evidence_packet = {
			"packet_id": packet.packet_id,
			"artifact": "evidence.json",
		}
		self.dependencies.complete("evidence_assembly", packet.to_dict(), reused)
		return packet, assets

#============================================
def _stable_mirror_input(entries: list[dict[str, object]]) -> list[dict[str, object]]:
	"""Remove refresh timestamps while retaining every object-location input."""
	values = []
	for entry in entries:
		values.append({
			"repository": entry["repository"],
			"repository_url": entry["repository_url"],
			"clone_url": entry["clone_url"],
			"created_at": entry["created_at"],
			"is_fork": entry["is_fork"],
			"roster_id": entry["roster_id"],
			"cache_path": entry["cache_path"],
			"default_revision": entry["default_revision"],
			"object_available": entry["object_available"],
			"ref_fingerprint": entry["ref_fingerprint"],
		})
	return values


#============================================
def _cache_assets(
	cache: daily_blog.locks.PhaseCache,
	phase: str,
	input_hash: str,
	packet: daily_blog.schema.EvidencePacket,
	assets: dict[str, bytes],
) -> None:
	"""Persist selected evidence assets with a hash-verified manifest."""
	asset_dir = cache.asset_dir(phase, input_hash)
	manifest = {}
	for asset_path, contents in assets.items():
		destination = os.path.join(asset_dir, os.path.basename(asset_path))
		daily_blog.io_utils.atomic_write_bytes(destination, contents)
		manifest[asset_path] = daily_blog.io_utils.sha256_bytes(contents)
	cache.store_json(phase, input_hash, "assets.json", {
		"packet_id": packet.packet_id,
		"assets": manifest,
	})


#============================================
def _load_cached_assets(
	cache: daily_blog.locks.PhaseCache,
	phase: str,
	input_hash: str,
	packet: daily_blog.schema.EvidencePacket,
) -> dict[str, bytes]:
	"""Load and verify all and only the declared evidence assets for one packet."""
	assets = {}
	asset_dir = cache.asset_dir(phase, input_hash)
	manifest_value = cache.load_json(phase, input_hash, "assets.json")
	if type(manifest_value) is not dict:
		raise RuntimeError("Cached evidence asset manifest is missing.")
	if manifest_value.get("packet_id") != packet.packet_id:
		raise RuntimeError("Cached evidence asset manifest does not match its packet.")
	manifest = manifest_value.get("assets")
	if type(manifest) is not dict:
		raise RuntimeError("Cached evidence asset manifest is invalid.")
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

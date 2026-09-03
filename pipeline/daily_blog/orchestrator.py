"""Date-driven lifecycle coordination for one daily blog publication."""

# Standard Library
import collections.abc
import datetime
import os
import uuid

# local repo modules
import daily_blog.acquisition_workflow
import daily_blog.activation
import daily_blog.activity
import daily_blog.config
import daily_blog.editorial
import daily_blog.io_utils
import daily_blog.locks
import daily_blog.observability
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.editorial_contracts
import daily_blog.publication_contract
import daily_blog.publication_finalization
import daily_blog.publication_images
import daily_blog.publication_workflow
import daily_blog.publisher
import daily_blog.repositories
import daily_blog.repository_contracts
import daily_blog.repository_editorial_workflow
import daily_blog.recovery
import daily_blog.route_cache
import daily_blog.run_contracts
import daily_blog.run_state
import daily_blog.schema


#============================================
def new_run_id() -> str:
	"""Create a sortable unique run identity."""
	moment = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
	run_id = f"{moment}-{uuid.uuid4().hex[:10]}"
	return run_id


#============================================
def invoke_publisher(
	publisher_function: collections.abc.Callable,
	daily_blog_repository: str,
	transfer: daily_blog.publication_contract.SealedBundleTransfer,
	*,
	replace_existing: bool,
) -> dict:
	"""Invoke the publisher through the explicit replacement-intent boundary."""
	if type(replace_existing) is not bool:
		raise RuntimeError("Replace-existing state must be Boolean.")
	if type(transfer) is not daily_blog.publication_contract.SealedBundleTransfer:
		raise RuntimeError("Daily-blog publisher requires one sealed bundle transfer.")
	result = publisher_function(
		daily_blog_repository,
		transfer,
		replace_existing=replace_existing,
	)
	if not isinstance(result, collections.abc.Mapping):
		raise RuntimeError("Daily-blog publisher must return a mapping.")
	result_copy = dict(result)
	return result_copy


#============================================
def _resolve_active_publication_snapshot(
	contract: daily_blog.prompt_registry.definitions.EditorialContract | None,
	snapshot: daily_blog.editorial.PromptContractSnapshot | None,
) -> daily_blog.editorial.PromptContractSnapshot:
	"""Accept the one active, factory-issued prompt snapshot for publication."""
	resolved_contract = None
	if contract is not None:
		resolved_contract = daily_blog.prompt_registry.editorial_contracts.resolve_contract(contract)
	if snapshot is not None:
		resolved_snapshot = daily_blog.editorial.validate_snapshot(snapshot)
	else:
		resolved_snapshot = None
	if (
		resolved_contract is not None
		and not daily_blog.prompt_registry.editorial_contracts.is_production_contract(resolved_contract)
	) or (
		resolved_snapshot is not None
		and not daily_blog.prompt_registry.editorial_contracts.is_production_contract(resolved_snapshot.contract)
	):
		raise RuntimeError("Production publication requires the active editorial contract.")
	activation = daily_blog.activation.load_maker_activation()
	resolved = daily_blog.editorial.resolve_run_snapshot(contract, snapshot)
	if not daily_blog.prompt_registry.editorial_contracts.is_production_contract(resolved.contract):
		raise RuntimeError("Production publication requires the active editorial contract.")
	if (
		activation.contract is not resolved.contract
		or activation.receipt["editorial_prompt_contract"]
		!= daily_blog.editorial.prompt_contract_identity(snapshot=resolved)
	):
		raise RuntimeError("Production prompt snapshot does not match maker activation.")
	return resolved


#============================================
def _publication_identity(
	repository_root: str,
	settings_path: str | None,
	contract: daily_blog.prompt_registry.definitions.EditorialContract,
	snapshot: daily_blog.editorial.PromptContractSnapshot,
) -> daily_blog.publication_contract.PublicationIdentity:
	"""Resolve validated prompt and activation state before publication sealing."""
	policy = daily_blog.prompt_registry.editorial_contracts.policy_for_contract(contract)
	activation = daily_blog.activation.load_maker_activation()
	prompt_contract = daily_blog.editorial.prompt_contract_identity(snapshot=snapshot)
	if activation.contract is not contract or activation.receipt["editorial_prompt_contract"] != prompt_contract:
		raise RuntimeError("Production prompt snapshot does not match maker activation.")
	identity = daily_blog.publication_contract.publication_identity(
		repository_root,
		settings_path,
		prompt_paths=daily_blog.prompt_registry.editorial_contracts.prompt_paths(contract),
		contracts={
			"evidence_schema": daily_blog.schema.EVIDENCE_SCHEMA_VERSION,
			"editorial_projection_schema": daily_blog.schema.PROJECTION_SCHEMA_VERSION,
			"prompt_version": contract.prompt_version,
			"rubric_version": contract.rubric_version,
			"candidate_validation": {
				"name": policy.name,
				"version": policy.version,
				"sha256": policy.sha256(),
			},
		},
		editorial_prompt_contract=prompt_contract,
		activation_receipt={
			"activation_id": activation.activation_id,
			"editorial_prompt_contract_sha256": activation.receipt[
				"editorial_prompt_contract_sha256"
			],
		},
	)
	return identity


#============================================
def record_phase_failure(
	record: daily_blog.run_contracts.RunRecord,
	store: daily_blog.run_state.RunStore,
	error: BaseException,
) -> None:
	"""Atomically record the current phase's redacted failure transition."""
	phase = record.current_phase
	if not phase:
		return
	failure_kind = daily_blog.run_contracts.classify_exception(error)
	terminal_fault = (
		error.fault.terminal_fault
		if isinstance(error, daily_blog.recovery.PipelineFaultError)
		else None
	)
	record.fail_phase(phase, failure_kind, terminal_fault)
	store.save(record)
	store.append_event(
		"daily_publication.phase_failed",
		{"failure_kind": failure_kind, "phase": phase},
	)


#============================================
class DailyPublicationOrchestrator:
	"""Execute admission, typed editorial stages, and terminal publication."""

	#============================================
	def __init__(
		self,
		config: daily_blog.config.DailyBlogConfig,
		report_date: str,
		route_runner: object | None = None,
		publisher_function: collections.abc.Callable | None = None,
		page_verifier: collections.abc.Callable | None = None,
		runtime: daily_blog.publication_workflow.PublicationRuntime | None = None,
		repository_loader: collections.abc.Callable[
			[str, str], daily_blog.repository_contracts.RepositoryRoster
		] | None = None,
		refresh_mirrors: bool = True,
		contract: daily_blog.prompt_registry.definitions.EditorialContract | None = None,
		snapshot: daily_blog.editorial.PromptContractSnapshot | None = None,
		force_regeneration: bool = False,
		command_started_at: str | None = None,
	) -> None:
		"""Bind explicit lifecycle dependencies for one report-date-owned run."""
		daily_blog.activity.build_date_window(report_date, config.report_timezone)
		if type(force_regeneration) is not bool:
			raise RuntimeError("Force-regeneration state must be Boolean.")
		self.config = config
		self.report_date = report_date
		self.force_regeneration = force_regeneration
		self.runtime = daily_blog.publication_workflow.require_runtime(runtime)
		self.route_runner = self.runtime.route_runner or route_runner
		self.publisher_function = (
			self.runtime.publisher_function or publisher_function or daily_blog.publisher.import_bundle
		)
		self.page_verifier = (
			self.runtime.page_verifier or page_verifier or daily_blog.publisher.verify_published_page
		)
		self.repository_loader = (
			self.runtime.repository_loader or repository_loader
			or daily_blog.repositories.discover_owner_repositories
		)
		self.refresh_mirrors = refresh_mirrors
		self.prompt_snapshot = _resolve_active_publication_snapshot(contract, snapshot)
		self.editorial_contract = self.prompt_snapshot.contract
		self.prompt_contract = daily_blog.editorial.prompt_contract_identity(snapshot=self.prompt_snapshot)
		self.generator_root = daily_blog.io_utils.repository_root(__file__)
		self.generator_identity = _publication_identity(
			self.generator_root,
			config.settings_path,
			self.editorial_contract,
			self.prompt_snapshot,
		)
		self.generator_revision = self.generator_identity.revision
		self.run_id = new_run_id()
		run_dir = os.path.join(
			config.output_root, config.output_owner, "daily_blog", report_date,
		)
		progress = daily_blog.observability.HumanProgress(
			report_date, os.path.join(run_dir, f"runlog-{report_date}.jsonl"),
		)
		self.store = daily_blog.run_state.RunStore(
			config.output_root,
			config.output_owner,
			report_date,
			self.run_id,
			max_events_per_run=config.logging.max_events_per_run,
			progress=progress,
		)
		progress.announce()
		self.record = daily_blog.run_contracts.RunRecord.create(
			self.run_id,
			report_date,
			created_at=command_started_at,
		)
		cache_root = os.path.join(config.output_root, config.output_owner, "daily_blog_cache")
		self.cache = daily_blog.locks.PhaseCache(cache_root)
		self.route_capacity = daily_blog.route_cache.RunCapacityPlan.for_run(config, 0)
		self.route_budget = self.route_capacity.new_budget()
		self.route_cache = daily_blog.route_cache.RouteResultCache(self.cache)
		self.store.save(self.record)
		self.store.append_event("daily_publication.run_started", {"state": self.record.state})

	#============================================
	def _start(self, phase: str, input_value: object) -> str:
		"""Start one phase and persist its canonical source-bound input hash."""
		input_hash = daily_blog.io_utils.hash_value({
			"generator_revision": self.generator_revision,
			"phase_input": input_value,
		})
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
		if self.store.progress is not None:
			self.store.progress.phase_result(phase, output_value, reused)
		return output_hash

	#============================================
	def _fail_current(self, error: Exception) -> None:
		"""Delegate the current run's failure transition to its public boundary."""
		record_phase_failure(self.record, self.store, error)

	#============================================
	def run(self) -> tuple[str, dict]:
		"""Run each durable boundary in its required publication order."""
		try:
			acquisition = daily_blog.acquisition_workflow.AcquisitionCoordinator(
				daily_blog.acquisition_workflow.AcquisitionDependencies(
					self.config, self.runtime, self.report_date, self.prompt_contract,
					self.generator_revision, self.repository_loader, self.refresh_mirrors,
					self.store, self.record, self.cache, self._start, self._complete,
				)
			).acquire()
			repository_editorial = daily_blog.repository_editorial_workflow.RepositoryEditorialCoordinator(
				daily_blog.repository_editorial_workflow.RepositoryEditorialDependencies(
					self.config, self.report_date, self.prompt_snapshot, self.route_runner,
					self.route_cache, self.generator_root, self._start, self._complete,
					lambda summary, transition: self.store.record_editorial_step(
						self.record, summary, transition,
					),
					self.store.write_artifact,
				)
			).run(acquisition.packet)
			self.route_capacity = repository_editorial.route_capacity
			self.route_budget = repository_editorial.route_budget
			stage6_input = daily_blog.publication_workflow.run_typed_stage5(
				self, repository_editorial.stage5_input,
			)
			stage6_result = daily_blog.publication_workflow.run_typed_stage6(self, stage6_input)
			stage7_result = daily_blog.publication_workflow.run_typed_stage7(
				self, stage6_input, stage6_result,
			)
			surface = stage6_input.publication_surface
			validated = daily_blog.publication_workflow.validate_selected_post(
				self, stage7_result.artifact, surface,
				recovery=stage6_result.recovery_generation is not None,
			)
			if validated.source_post is not stage7_result.artifact:
				raise RuntimeError("Publication validation must retain the exact Stage 7 selected source post.")
			image_selection = daily_blog.publication_images.resolve_final_post_images(
				surface, validated.post, acquisition.assets,
			)
			self.store.write_artifact(
				"publication_image_selection.json", image_selection.to_dict(),
			)
			def write_post() -> None:
				"""Materialize the producer-approved post before transport."""
				daily_blog.publication_workflow.write_selected_post(self, validated.post)

			finalized = daily_blog.publication_finalization.PublicationFinalizationCoordinator(
				daily_blog.publication_finalization.SealedPublicationInput(
					self.report_date, self.run_id, self.config.output_root, self.config.output_owner,
					self.config.daily_blog_repository, self.generator_identity,
					self.force_regeneration, acquisition.roster, surface,
					image_selection.assets, validated.post, acquisition.active_roster,
				),
				self.cache, self.store, self.record, self._start, self._complete,
				invoke_publisher, self.publisher_function, self.page_verifier,
			).finalize(write_post)
			self.record.complete()
			self.store.save(self.record)
			self.store.append_event(
				"daily_publication.run_completed",
				{
					"best_artifact_id": finalized.bundle["best_artifact_id"],
					"bundle_sha256": finalized.bundle["bundle_sha256"],
					"outcome": self.record.outcome,
					"site_import_status": finalized.site_import["status"],
					"verified_page_sha256": finalized.page_verification["rendered_page_sha256"],
					"state": self.record.state,
				},
			)
		except Exception as error:
			self._fail_current(error)
			if self.record.state == "failed":
				try:
					self.store.finalize_summary(self.record)
				except (OSError, RuntimeError):
					pass
			raise
		self.store.finalize_summary(self.record)
		published_post = os.path.join(
			self.config.daily_blog_repository,
			"docs", "blog", "posts", f"{self.report_date}.md",
		)
		self.store.discard_completed_working_artifacts()
		return published_post, finalized.bundle


#============================================
def publication_date_lock(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
) -> daily_blog.locks.FileLock:
	"""Return the single-owner lock for one report date."""
	daily_blog.activity.build_date_window(report_date, config.report_timezone)
	lock_path = os.path.join(
		config.output_root, config.output_owner, "daily_blog_locks", f"{report_date}.lock",
	)
	lock = daily_blog.locks.FileLock(lock_path)
	return lock


#============================================
def run_daily_publication_locked(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
	route_runner: object | None = None,
	publisher_function: collections.abc.Callable | None = None,
	repository_loader: collections.abc.Callable[
		[str, str], daily_blog.repository_contracts.RepositoryRoster
	] | None = None,
	refresh_mirrors: bool = True,
	contract: daily_blog.prompt_registry.definitions.EditorialContract | None = None,
	snapshot: daily_blog.editorial.PromptContractSnapshot | None = None,
	force_regeneration: bool = False,
	runtime: daily_blog.publication_workflow.PublicationRuntime | None = None,
	*,
	command_started_at: str,
) -> tuple[str, dict]:
	"""Execute one complete run while holding the matching per-date lock."""
	prompt_snapshot = _resolve_active_publication_snapshot(contract, snapshot)
	orchestrator = DailyPublicationOrchestrator(
		config, report_date, route_runner=route_runner, publisher_function=publisher_function,
		repository_loader=repository_loader, refresh_mirrors=refresh_mirrors,
		contract=daily_blog.prompt_registry.editorial_contracts.active_contract(), snapshot=prompt_snapshot,
		force_regeneration=force_regeneration, runtime=runtime,
		command_started_at=command_started_at,
	)
	result = orchestrator.run()
	return result


#============================================
def run_daily_publication(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
	route_runner: object | None = None,
	publisher_function: collections.abc.Callable | None = None,
	repository_loader: collections.abc.Callable[
		[str, str], daily_blog.repository_contracts.RepositoryRoster
	] | None = None,
	refresh_mirrors: bool = True,
	contract: daily_blog.prompt_registry.definitions.EditorialContract | None = None,
	snapshot: daily_blog.editorial.PromptContractSnapshot | None = None,
	force_regeneration: bool = False,
	runtime: daily_blog.publication_workflow.PublicationRuntime | None = None,
) -> tuple[str, dict]:
	"""Validate, lock, and execute one report-date-owned publication run."""
	command_started_at = daily_blog.io_utils.utc_now()
	prompt_snapshot = _resolve_active_publication_snapshot(contract, snapshot)
	with publication_date_lock(config, report_date):
		result = run_daily_publication_locked(
			config, report_date, route_runner=route_runner, publisher_function=publisher_function,
			repository_loader=repository_loader, refresh_mirrors=refresh_mirrors,
			snapshot=prompt_snapshot, force_regeneration=force_regeneration,
			runtime=runtime, command_started_at=command_started_at,
		)
	return result

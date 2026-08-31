"""Fast boundary tests for non-publishing editorial contracts."""

# Standard Library
import dataclasses
import json
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.config
import daily_blog.editorial_stage_config
import daily_blog.acquisition_workflow
import daily_blog.activation
import daily_blog.editorial
import daily_blog.io_utils
import daily_blog.prompt_registry.editorial_contracts
import daily_blog.mirrors
import daily_blog.orchestrator
import daily_blog.publication_workflow
import daily_blog.repository_contracts


#============================================
def make_config(tmp_path: pathlib.Path) -> daily_blog.config.DailyBlogConfig:
	"""Build the smallest isolated configuration that can open a run."""
	return daily_blog.config.DailyBlogConfig(
		settings_path="settings.yaml", output_root=str(tmp_path), output_owner="vosslab",
		report_timezone="America/Chicago", daily_blog_repository=str(tmp_path),
		mirror_cache_root=str(tmp_path / "mirrors"), identity_names=("Neil",), identity_emails=(),
		author_routes=(daily_blog.editorial_stage_config.RoleRoute("one", ("fake",)), daily_blog.editorial_stage_config.RoleRoute("two", ("fake",))),
		referee_route=daily_blog.editorial_stage_config.RoleRoute("judge", ("fake",)), collection_limits={}, projection_limits={
			"context_chars": 8000, "excerpt_chars": 1000, "commit_subject_chars": 120,
		},
		prompt_limits={"author_chars": 60000, "referee_chars": 60000},
	)


#============================================
def acquire_evidence(
	config: daily_blog.config.DailyBlogConfig,
	report_date: str,
	roster: daily_blog.repository_contracts.RepositoryRoster,
	runtime: daily_blog.publication_workflow.PublicationRuntime,
) -> tuple[daily_blog.orchestrator.DailyPublicationOrchestrator, daily_blog.acquisition_workflow.AcquisitionResult]:
	"""Run the public acquisition handoff with its durable phase lifecycle."""
	orchestrator = daily_blog.orchestrator.DailyPublicationOrchestrator(
		config, report_date, repository_loader=lambda *_args: roster, runtime=runtime,
	)
	coordinator = daily_blog.acquisition_workflow.AcquisitionCoordinator(
		daily_blog.acquisition_workflow.AcquisitionDependencies(
			orchestrator.config, orchestrator.runtime, orchestrator.report_date,
			orchestrator.prompt_contract, orchestrator.generator_revision,
			orchestrator.repository_loader, orchestrator.refresh_mirrors,
			orchestrator.store, orchestrator.record, orchestrator.cache,
			orchestrator._start, orchestrator._complete,
		)
	)
	result = coordinator.acquire()
	return orchestrator, result


#============================================
def test_acquisition_persists_the_authoritative_roster_and_prompt_contract(
	tmp_path: pathlib.Path,
) -> None:
	"""Public acquisition makes its authoritative roster and prompt contract inspectable."""
	record = daily_blog.repository_contracts.RepositoryRecord.from_dict({
		"repository": "vosslab/example", "repository_url": "https://github.com/vosslab/example",
		"clone_url": "https://github.com/vosslab/example.git", "created_at": "2026-08-23T00:00:00Z", "is_fork": False,
	})
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [record])
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/example", "a" * 40, "", "", "A grounded change.", "fixture",
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item],
	)
	runtime = daily_blog.publication_workflow.PublicationRuntime(
		mirror_refresh=lambda *_args: [],
		activity_locator=lambda *_args: [],
		evidence_assembler=lambda *_args: (packet, {}),
	)
	orchestrator = daily_blog.orchestrator.DailyPublicationOrchestrator(
		make_config(tmp_path), "2026-08-23", repository_loader=lambda *_args: roster,
		runtime=runtime,
	)
	def start(_phase: str, value: object) -> str:
		return daily_blog.io_utils.hash_value(value)

	def complete(_phase: str, value: object, _reused: bool) -> str:
		orchestrator.store.save(orchestrator.record)
		return daily_blog.io_utils.hash_value(value)

	coordinator = daily_blog.acquisition_workflow.AcquisitionCoordinator(
		daily_blog.acquisition_workflow.AcquisitionDependencies(
			orchestrator.config, orchestrator.runtime, orchestrator.report_date,
			orchestrator.prompt_contract, orchestrator.generator_revision,
			orchestrator.repository_loader, orchestrator.refresh_mirrors,
			orchestrator.store, orchestrator.record, orchestrator.cache,
			start, complete,
		)
	)

	result = coordinator.acquire()
	roster_artifact = pathlib.Path(orchestrator.store.run_dir) / "repository_roster.json"
	prompt_artifact = pathlib.Path(orchestrator.store.run_dir) / "prompt_contract.json"

	assert result.roster == roster
	assert (
		json.loads(roster_artifact.read_text(encoding="utf-8"))["roster_id"]
		== orchestrator.record.repository_roster["roster_id"]
		and json.loads(prompt_artifact.read_text(encoding="utf-8")) == orchestrator.prompt_contract
	)


#============================================
def test_evidence_acquisition_does_not_reuse_another_report_dates_empty_activity(
	tmp_path: pathlib.Path,
) -> None:
	"""A shared cache keeps otherwise identical no-activity days separate."""
	record = daily_blog.repository_contracts.RepositoryRecord.from_dict({
		"repository": "vosslab/example", "repository_url": "https://github.com/vosslab/example",
		"clone_url": "https://github.com/vosslab/example.git", "created_at": "2026-08-23T00:00:00Z", "is_fork": False,
	})
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [record])
	assembled_dates: list[str] = []

	def assemble(report_date: str, timezone: str, *_args: object) -> tuple[daily_blog.schema.EvidencePacket, dict[str, bytes]]:
		assembled_dates.append(report_date)
		item = daily_blog.schema.EvidenceItem.create(
			"commit_metadata", "vosslab/example", "a" * 40, "", "", "A grounded change.", "fixture",
		)
		packet = daily_blog.schema.EvidencePacket.create(
			report_date, timezone, True, {}, [], [], [item],
		)
		return packet, {}

	runtime = daily_blog.publication_workflow.PublicationRuntime(
		mirror_refresh=lambda *_args: [], activity_locator=lambda *_args: [], evidence_assembler=assemble,
	)
	config = make_config(tmp_path)
	acquire_evidence(config, "2026-08-22", roster, runtime)
	_, second = acquire_evidence(config, "2026-08-23", roster, runtime)

	assert second.packet.report_date == "2026-08-23"
	assert assembled_dates[-1] == "2026-08-23"


#============================================
def test_evidence_acquisition_reassembles_when_cached_packet_lacks_its_asset(
	tmp_path: pathlib.Path,
) -> None:
	"""A partial multi-file cache entry cannot become authoritative evidence."""
	record = daily_blog.repository_contracts.RepositoryRecord.from_dict({
		"repository": "vosslab/example", "repository_url": "https://github.com/vosslab/example",
		"clone_url": "https://github.com/vosslab/example.git", "created_at": "2026-08-23T00:00:00Z", "is_fork": False,
	})
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [record])
	assembled_dates: list[str] = []

	def assemble(report_date: str, timezone: str, *_args: object) -> tuple[daily_blog.schema.EvidencePacket, dict[str, bytes]]:
		assembled_dates.append(report_date)
		item = daily_blog.schema.EvidenceItem.create(
			"screenshot", "vosslab/example", "a" * 40, "", "", "Screenshot", "fixture",
			asset_path="assets/image.png",
		)
		packet = daily_blog.schema.EvidencePacket.create(
			report_date, timezone, True, {}, [], [], [item],
		)
		return packet, {"assets/image.png": b"image"}

	runtime = daily_blog.publication_workflow.PublicationRuntime(
		mirror_refresh=lambda *_args: [], activity_locator=lambda *_args: [], evidence_assembler=assemble,
	)
	config = make_config(tmp_path)
	first, _result = acquire_evidence(config, "2026-08-23", roster, runtime)
	phase = first.record.phases["evidence_assembly"]
	asset = pathlib.Path(first.cache.asset_dir("evidence_assembly", phase.input_hash)) / "image.png"
	asset.unlink()
	_second, recovered = acquire_evidence(config, "2026-08-23", roster, runtime)

	assert recovered.assets == {"assets/image.png": b"image"}
	assert assembled_dates == ["2026-08-23", "2026-08-23"]


#============================================
def test_evidence_acquisition_reassembles_when_manifest_binds_another_packet(
	tmp_path: pathlib.Path,
) -> None:
	"""An otherwise valid asset manifest must belong to the restored packet."""
	record = daily_blog.repository_contracts.RepositoryRecord.from_dict({
		"repository": "vosslab/example", "repository_url": "https://github.com/vosslab/example",
		"clone_url": "https://github.com/vosslab/example.git", "created_at": "2026-08-23T00:00:00Z", "is_fork": False,
	})
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [record])
	assembled_dates: list[str] = []

	def assemble(report_date: str, timezone: str, *_args: object) -> tuple[daily_blog.schema.EvidencePacket, dict[str, bytes]]:
		assembled_dates.append(report_date)
		item = daily_blog.schema.EvidenceItem.create(
			"screenshot", "vosslab/example", "a" * 40, "", "", "Screenshot", "fixture",
			asset_path="assets/image.png",
		)
		packet = daily_blog.schema.EvidencePacket.create(
			report_date, timezone, True, {}, [], [], [item],
		)
		return packet, {"assets/image.png": b"image"}

	runtime = daily_blog.publication_workflow.PublicationRuntime(
		mirror_refresh=lambda *_args: [], activity_locator=lambda *_args: [], evidence_assembler=assemble,
	)
	config = make_config(tmp_path)
	first, _result = acquire_evidence(config, "2026-08-23", roster, runtime)
	phase = first.record.phases["evidence_assembly"]
	manifest = first.cache.load_json("evidence_assembly", phase.input_hash, "assets.json")
	if type(manifest) is not dict:
		raise RuntimeError("Test evidence cache manifest was not created.")
	forged = dict(manifest)
	forged["packet_id"] = "0" * 64
	first.cache.store_json("evidence_assembly", phase.input_hash, "assets.json", forged)
	_second, recovered = acquire_evidence(config, "2026-08-23", roster, runtime)

	assert recovered.assets == {"assets/image.png": b"image"}
	assert assembled_dates == ["2026-08-23", "2026-08-23"]


#============================================
def test_publication_resolves_through_one_explicit_contract_owner(
	tmp_path: pathlib.Path,
) -> None:
	"""The default publication snapshot belongs to the registry's sole production owner."""
	orchestrator = daily_blog.orchestrator.DailyPublicationOrchestrator(
		make_config(tmp_path), "2026-08-23"
	)

	assert orchestrator.editorial_contract is daily_blog.prompt_registry.editorial_contracts.PRODUCTION_EDITORIAL_CONTRACT
	assert daily_blog.prompt_registry.editorial_contracts.is_production_contract(orchestrator.editorial_contract)


#============================================
def test_maker_activation_rejects_missing_or_malformed_tracked_receipts(
	tmp_path: pathlib.Path,
) -> None:
	"""Production cannot select a contract without one valid tracked activation."""
	with pytest.raises(RuntimeError, match="unavailable or malformed"):
		daily_blog.activation.load_maker_activation(str(tmp_path))
	(tmp_path / daily_blog.activation.ACTIVATION_FILENAME).write_text("[]", encoding="utf-8")
	with pytest.raises(RuntimeError, match="unavailable or malformed"):
		daily_blog.activation.load_maker_activation(str(tmp_path))


#============================================
def test_maker_activation_rejects_tampered_f4_receipt(
	tmp_path: pathlib.Path,
) -> None:
	"""Production rejects a resealed receipt with altered historical F4 evidence."""
	receipt = dict(daily_blog.activation.load_maker_activation().receipt)
	f4_evidence = dict(receipt["f4_evidence"])
	f4_evidence["review_evidence_id"] = "prompt-experiment-review-evidence-" + "0" * 64
	receipt["f4_evidence"] = f4_evidence
	payload = {key: value for key, value in receipt.items() if key != "activation_id"}
	receipt["activation_id"] = "daily-blog-maker-activation-" + daily_blog.io_utils.hash_value(payload)
	(tmp_path / daily_blog.activation.ACTIVATION_FILENAME).write_text(
		json.dumps(receipt), encoding="utf-8"
	)

	with pytest.raises(RuntimeError, match="F4 evidence"):
		daily_blog.activation.load_maker_activation(str(tmp_path))


#============================================
def test_example_resource_validation_requires_the_canonical_resource() -> None:
	"""Example blocks are accepted only for the registry's exact resource object."""
	registry = daily_blog.prompt_registry.editorial_contracts
	blocks = {"aug-23": "Local maker example."}
	for block_id in registry.V4_VOICE_RESOURCE.external_block_ids:
		blocks[block_id] = registry.EXTERNAL_EXAMPLE_BLOCKS[block_id]

	registry.validate_example_resource_blocks(registry.V4_VOICE_RESOURCE, blocks)
	with pytest.raises(RuntimeError, match="registered object"):
		registry.validate_example_resource_blocks(
			dataclasses.replace(registry.V4_VOICE_RESOURCE), blocks,
		)

#============================================
def test_registry_helpers_reject_a_replaced_registered_contract() -> None:
	"""Public registry helpers only accept the exact registered contract object."""
	contract = daily_blog.prompt_registry.editorial_contracts.V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT
	forged = dataclasses.replace(
		contract,
		author_template="untrusted.txt",
	)
	with pytest.raises(RuntimeError, match="trusted registry"):
		daily_blog.prompt_registry.editorial_contracts.prompt_paths(forged)
	with pytest.raises(RuntimeError, match="trusted registry"):
		daily_blog.prompt_registry.editorial_contracts.policy_for_contract(forged)
	with pytest.raises(RuntimeError, match="trusted registry"):
		daily_blog.prompt_registry.editorial_contracts.resolve_selection(
			forged,
			daily_blog.prompt_registry.editorial_contracts.V4_THREE_EXAMPLES_CORPUS_V2_SELECTION,
		)


#============================================
def test_registry_mappings_and_registered_values_are_immutable() -> None:
	"""Registry mappings cannot be changed to redirect a trusted contract binding."""
	registry = daily_blog.prompt_registry.editorial_contracts
	for mapping, key, value in (
		(registry.EXAMPLE_RESOURCES, "v4-voice", registry.V4_VOICE_RESOURCE),
		(registry.VALIDATION_POLICIES, "v4-maker", registry.V4_MAKER_VALIDATION_POLICY),
		(
			registry.EXAMPLE_SELECTIONS,
			registry.V4_THREE_EXAMPLES_CORPUS_V2,
			registry.V4_THREE_EXAMPLES_CORPUS_V2_SELECTION,
		),
		(
			registry.EDITORIAL_CONTRACTS,
			registry.V4_THREE_EXAMPLES_CORPUS_V2,
			registry.V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT,
		),
	):
		with pytest.raises(TypeError):
			mapping[key] = value  # type: ignore[index]
	with pytest.raises(dataclasses.FrozenInstanceError):
		registry.V4_VOICE_RESOURCE.filename = "another.md"  # type: ignore[misc]
	assert (
		registry.policy_for_contract(registry.V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT)
		is registry.V4_MAKER_VALIDATION_POLICY
	)
	assert (
		registry.resolve_selection(registry.V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT, None)
		is registry.V4_THREE_EXAMPLES_CORPUS_V2_SELECTION
	)

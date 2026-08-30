"""Date-owned publication state and replacement tests."""

# Standard Library
import contextlib
import json
import pathlib
import shutil
import types

# PIP3 modules
import pytest

# local repo modules
import automation.publish_daily_blog
import daily_blog.artifacts
import daily_blog.acquisition_workflow
import daily_blog.activation
import daily_blog.contracts
import daily_blog.prompt_registry
import daily_blog.editorial
import daily_blog.publication_contract
import daily_blog.publication_finalization
import daily_blog.config
import daily_blog.editorial_stage_config
import daily_blog.editorial
import daily_blog.io_utils
import daily_blog.orchestrator
import daily_blog.projection
import daily_blog.publisher
import daily_blog.publication_state
import daily_blog.repository_contracts
import daily_blog.roster_snapshots
import daily_blog.schema


#============================================
def _bundle_identity() -> daily_blog.publication_contract.PublicationIdentity:
	"""Return the current maker-bound identity required by publication."""
	contract = daily_blog.prompt_registry.active_contract()
	policy = daily_blog.prompt_registry.policy_for_contract(contract)
	snapshot = daily_blog.editorial.resolve_snapshot(contract, None, None)
	activation = daily_blog.activation.load_maker_activation().receipt
	return daily_blog.publication_contract.publication_identity(
		str(pathlib.Path(__file__).resolve().parents[1]), None,
		prompt_paths=daily_blog.prompt_registry.prompt_paths(contract), contracts={
			"evidence_schema": daily_blog.schema.EVIDENCE_SCHEMA_VERSION,
			"editorial_projection_schema": daily_blog.schema.PROJECTION_SCHEMA_VERSION,
			"prompt_version": contract.prompt_version,
			"rubric_version": contract.rubric_version,
			"candidate_validation": {
				"name": policy.name, "version": policy.version, "sha256": policy.sha256(),
			},
		}, editorial_prompt_contract=daily_blog.editorial.prompt_contract_identity(snapshot=snapshot),
		activation_receipt={
			"activation_id": activation["activation_id"],
			"editorial_prompt_contract_sha256": activation["editorial_prompt_contract_sha256"],
		},
	)


#============================================
def _current_publication_config(tmp_path: pathlib.Path) -> types.SimpleNamespace:
	"""Create one complete publisher-owned date publication for integrity tests."""
	report_date = "2026-08-26"
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/project", "a" * 40, "", "", "work", "git show"
	)
	packet = daily_blog.schema.EvidencePacket.create(
		report_date, "America/Chicago", True, {}, [], [], [item]
	)
	projection = daily_blog.projection.build_projection(packet, {
		"context_chars": 8000,
		"excerpt_chars": 1000,
		"commit_subject_chars": 120,
	})
	record = daily_blog.repository_contracts.RepositoryRecord.from_dict({
		"repository": "vosslab/project",
		"repository_url": "https://github.com/vosslab/project",
		"clone_url": "https://github.com/vosslab/project.git",
		"created_at": "2020-01-01T00:00:00Z",
		"is_fork": False,
	})
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [record])
	post = f"A small maker note.\n\n<!-- evidence: {item.evidence_id} -->\n"
	selected = daily_blog.artifacts.CompletePost.create(
		report_date, (packet,), ("vosslab/project",), post, (item.evidence_id,), report_date,
		str(tmp_path / "producer" / "vosslab" / "daily_blog" / report_date / "post.md"),
	)
	producer_root = tmp_path / "producer"
	producer_root.mkdir()
	bundle_path, bundle = daily_blog.publication_contract.BundleWriter(
		str(producer_root), "vosslab", _bundle_identity()
	).write("run-one", packet, projection, {}, roster, selected)
	publisher_root = tmp_path / "publisher"
	archive = publisher_root / "data" / "publication_bundles" / report_date
	archive.parent.mkdir(parents=True)
	shutil.copytree(bundle_path, archive)
	installed_post = publisher_root / "docs" / "blog" / "posts" / f"{report_date}.md"
	installed_post.parent.mkdir(parents=True)
	installed_post.write_text(post, encoding="utf-8")
	(publisher_root / "generated" / "releases" / report_date).mkdir(parents=True)
	(publisher_root / "generated" / "releases" / report_date / "index.html").write_text("ok", encoding="utf-8")
	publication_record = {
		"schema_version": daily_blog.publication_state.PUBLICATION_SCHEMA_VERSION,
		"report_date": report_date,
		"timezone": "America/Chicago",
		"generator_run": "run-one",
		"generator_revision": "f" * 64,
		"bundle_sha256": bundle["bundle_sha256"],
		"best_artifact_id": bundle["best_artifact_id"],
		"evidence_manifest": f"data/publication_bundles/{report_date}/evidence.json",
		"editorial_projection_manifest": f"data/publication_bundles/{report_date}/editorial_projection.json",
		"post_path": f"docs/blog/posts/{report_date}.md",
		"imported_at": "2026-08-27T00:00:00Z",
	}
	path = publisher_root / "data" / "publications" / f"{report_date}.json"
	path.parent.mkdir(parents=True)
	path.write_text(json.dumps(publication_record), encoding="utf-8")
	return types.SimpleNamespace(
		daily_blog_repository=str(publisher_root), report_timezone="America/Chicago"
	)


#============================================
def _path_record_config(tmp_path: pathlib.Path) -> daily_blog.config.DailyBlogConfig:
	"""Build an offline configuration whose output root is intentionally unique."""
	return daily_blog.config.DailyBlogConfig(
		settings_path="settings.yaml", output_root=str(tmp_path), output_owner="vosslab",
		report_timezone="America/Chicago", daily_blog_repository=str(tmp_path / "publisher"),
		mirror_cache_root=str(tmp_path / "mirrors"), identity_names=("Maker",), identity_emails=(),
		author_routes=(daily_blog.editorial_stage_config.RoleRoute("author-a", ("fixture",)),
			daily_blog.editorial_stage_config.RoleRoute("author-b", ("fixture",))),
		referee_route=daily_blog.editorial_stage_config.RoleRoute("referee", ("fixture",)),
		collection_limits={}, projection_limits={"context_chars": 8000, "excerpt_chars": 1000,
			"commit_subject_chars": 120}, prompt_limits={"author_chars": 72000, "referee_chars": 88000},
	)


#============================================
def _path_record_roster() -> daily_blog.repository_contracts.RepositoryRoster:
	"""Return one typed roster for output-path persistence tests."""
	return daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [
		daily_blog.repository_contracts.RepositoryRecord.from_dict({
			"repository": "vosslab/example", "repository_url": "https://github.com/vosslab/example",
			"clone_url": "https://github.com/vosslab/example.git", "created_at": "2026-08-26T00:00:00Z",
			"is_fork": False,
		}),
	])


#============================================
@pytest.mark.parametrize(
	("state", "force_regeneration"),
	(("missing", False), ("current", True), ("invalid", True)),
)
def test_publication_inspection_controls_replacement_intent(
	monkeypatch: pytest.MonkeyPatch, state: str, force_regeneration: bool,
) -> None:
	"""Only a missing date imports without asking the publisher to replace it."""
	config = types.SimpleNamespace(daily_blog_repository="/publisher")
	observed: list[bool] = []
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.publication_state, "inspect_publication",
		lambda _config, _date: daily_blog.publication_state.PublicationInspection(state),
	)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator, "publication_date_lock",
		lambda _config, _date: contextlib.nullcontext(),
	)

	def run_locked(_config: object, _date: str, **kwargs: object) -> tuple[str, dict]:
		observed.append(kwargs["force_regeneration"])
		return "/bundle", {"bundle_sha256": "a" * 64}

	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator,
		"run_daily_publication_locked", run_locked,
	)
	automation.publish_daily_blog.publish_report_date(config, "2026-08-26")

	assert observed == [force_regeneration]


#============================================
@pytest.mark.parametrize("replace_existing", [False, True])
def test_invoke_publisher_passes_intent_and_copies_mapping_receipt(
	replace_existing: bool,
) -> None:
	"""The publisher boundary passes its Boolean intent and isolates a mapping receipt."""
	receipt = types.MappingProxyType({"status": "imported"})
	observed = []

	def publisher(_repository: str, _bundle: str, *, replace_existing: bool) -> object:
		observed.append(replace_existing)
		return receipt

	result = daily_blog.orchestrator.invoke_publisher(
		publisher, "/publisher", "/bundle", replace_existing=replace_existing
	)

	assert observed == [replace_existing]
	assert result == dict(receipt)


#============================================
def test_invoke_publisher_rejects_nonmapping_receipt() -> None:
	"""The publisher boundary rejects receipts without mapping semantics."""

	def publisher(_repository: str, _bundle: str, *, replace_existing: bool) -> object:
		return [("status", "imported")]

	with pytest.raises(RuntimeError, match="must return a mapping"):
		daily_blog.orchestrator.invoke_publisher(
			publisher, "/publisher", "/bundle", replace_existing=False
		)


#============================================
def test_invoke_publisher_rejects_integer_replacement_intent() -> None:
	"""Replacement intent accepts only the Boolean protocol value."""

	def publisher(_repository: str, _bundle: str, *, replace_existing: bool) -> object:
		return {}

	with pytest.raises(RuntimeError, match="must be Boolean"):
		daily_blog.orchestrator.invoke_publisher(
			publisher, "/publisher", "/bundle", replace_existing=1
		)


#============================================
#============================================
def test_publication_exists_rejects_a_tampered_declared_evidence_artifact(
	tmp_path: pathlib.Path,
) -> None:
	"""An archive cannot become current merely because its manifest still exists."""
	config = _current_publication_config(tmp_path)
	evidence = pathlib.Path(config.daily_blog_repository) / "data" / "publication_bundles" / "2026-08-26" / "evidence.json"
	evidence.write_text("{}", encoding="utf-8")

	inspection = daily_blog.publication_state.inspect_publication(config, "2026-08-26")
	assert inspection.state == "invalid"
	with pytest.raises(RuntimeError, match="publication state is invalid"):
		daily_blog.publication_state.publication_exists(config, "2026-08-26")


#============================================
def test_publication_exists_rejects_missing_repository_roster(
	tmp_path: pathlib.Path,
) -> None:
	"""The roster is a required typed artifact, not optional supporting metadata."""
	config = _current_publication_config(tmp_path)
	roster = pathlib.Path(config.daily_blog_repository) / "data" / "publication_bundles" / "2026-08-26" / "repository_roster.json"
	roster.unlink()

	inspection = daily_blog.publication_state.inspect_publication(config, "2026-08-26")
	assert inspection.state == "invalid"
	assert "repository roster" in inspection.reason


#============================================
def test_publication_inspection_rejects_a_symlinked_archive_intermediate(
	tmp_path: pathlib.Path,
) -> None:
	"""An occupied date is invalid when its publisher archive crosses a symlink."""
	config = _current_publication_config(tmp_path)
	root = pathlib.Path(config.daily_blog_repository)
	data = root / "data"
	replacement = root / "replacement-data"
	data.rename(replacement)
	data.symlink_to(replacement, target_is_directory=True)

	inspection = daily_blog.publication_state.inspect_publication(config, "2026-08-26")

	assert inspection.state == "invalid"


#============================================
def test_run_state_keeps_roster_snapshot_logical_while_loader_receives_absolute_path(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The verified snapshot stays physical only at the roster-loader boundary."""
	config = _path_record_config(tmp_path)
	roster = _path_record_roster()
	snapshot_path = tmp_path / "vosslab" / "daily_blog_repository_rosters" / roster.roster_id
	identity = {"roster_id": roster.roster_id}
	received: list[str] = []
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/example", "a" * 40, "", "", "A grounded change.", "fixture",
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-26", "America/Chicago", True, {}, [], [], [item],
	)
	runtime = daily_blog.publication_workflow.PublicationRuntime(
		mirror_refresh=lambda *_args: [],
		activity_locator=lambda *_args: [],
		evidence_assembler=lambda *_args: (packet, {}),
	)
	orchestrator = daily_blog.orchestrator.DailyPublicationOrchestrator(
		config, "2026-08-26", repository_loader=lambda *_args: roster, runtime=runtime,
	)
	monkeypatch.setattr(
		daily_blog.roster_snapshots, "write_repository_roster_snapshot",
		lambda *_args: (str(snapshot_path), identity),
	)

	def load_snapshot(
		_root: str, _owner: str, path: str,
	) -> tuple[daily_blog.repository_contracts.RepositoryRoster, dict]:
		received.append(path)
		return roster, identity

	monkeypatch.setattr(daily_blog.roster_snapshots, "load_repository_roster_snapshot", load_snapshot)

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
	coordinator.acquire()
	saved = json.loads(pathlib.Path(orchestrator.store.record_path).read_text(encoding="utf-8"))

	assert pathlib.Path(received[0]).is_absolute()
	assert not pathlib.PurePosixPath(saved["repository_roster"]["snapshot_path"]).is_absolute()


#============================================
def test_finalization_keeps_bundle_logical_while_importer_receives_absolute_path(
	tmp_path: pathlib.Path,
) -> None:
	"""Finalization imports a sealed physical bundle while state retains a logical path."""
	config = _path_record_config(tmp_path)
	roster = _path_record_roster()
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-26", "America/Chicago", True, {}, [], [], [
			daily_blog.schema.EvidenceItem.create(
				"commit_metadata", "vosslab/example", "a" * 40, "", "", "work", "git show",
			),
		],
	)
	projection = daily_blog.projection.build_projection(packet, {
		"context_chars": 8000, "excerpt_chars": 1000, "commit_subject_chars": 120,
	})
	content = (
		"# Published\n\nA grounded maker note. <!-- evidence: "
		f"{packet.items[0].evidence_id} -->\n"
	)
	post = daily_blog.artifacts.CompletePost.create(
		packet.report_date, (packet,), ("vosslab/example",), content,
		(packet.items[0].evidence_id,), packet.report_date,
		str(tmp_path / "vosslab" / "daily_blog" / packet.report_date / "post.md"),
	)
	imported: list[str] = []

	def publisher(_root: str, bundle_path: str, *, replace_existing: bool) -> dict:
		imported.append(bundle_path)
		bundle = daily_blog.io_utils.read_json(str(pathlib.Path(bundle_path) / "bundle.json"))
		return {
			"schema_version": "vosslab.daily-blog.import-receipt.v1",
			"status": "imported",
			"bundle_sha256": bundle["bundle_sha256"],
			"report_date": packet.report_date,
			"publication_record_path": f"data/publications/{packet.report_date}.json",
			"publication_record_sha256": "a" * 64,
			"post_path": f"docs/blog/posts/{packet.report_date}.md",
			"post_sha256": bundle["post"]["sha256"],
			"rendered_page_path": (
				f"generated/releases/{packet.report_date}/blog/2026/08/26/published/index.html"
			),
			"best_artifact_id": bundle["best_artifact_id"],
		}

	coordinator = daily_blog.orchestrator.DailyPublicationOrchestrator(
		config, packet.report_date,
		publisher_function=publisher,
	)
	for phase in daily_blog.run_contracts.LEGAL_PHASES:
		if phase == "bundle_creation":
			break
		coordinator._start(phase, {"fixture": phase})
		coordinator._complete(phase, {"fixture": phase})

	value = daily_blog.publication_finalization.SealedPublicationInput(
		packet.report_date, coordinator.run_id, config.output_root, config.output_owner,
		config.daily_blog_repository, coordinator.generator_identity,
		coordinator.force_regeneration, roster, packet, projection, {}, post,
	)
	finalizer = daily_blog.publication_finalization.PublicationFinalizationCoordinator(
		value, coordinator.cache, coordinator.store, coordinator.record,
		coordinator._start, coordinator._complete, daily_blog.orchestrator.invoke_publisher,
		coordinator.publisher_function, coordinator.page_verifier,
	)
	bundle_path, bundle, _reused = finalizer.create_or_reuse_bundle()
	finalizer.import_bundle(bundle_path, bundle)
	saved = json.loads(pathlib.Path(coordinator.store.record_path).read_text(encoding="utf-8"))

	assert pathlib.Path(imported[0]).is_absolute()
	assert not pathlib.PurePosixPath(saved["publication_bundle"]["path"]).is_absolute()

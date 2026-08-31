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
import daily_blog.prompt_registry.editorial_contracts
import daily_blog.editorial
import daily_blog.publication_contract
import daily_blog.publication_finalization
import daily_blog.config
import daily_blog.editorial_stage_config
import daily_blog.editorial
import daily_blog.io_utils
import daily_blog.orchestrator
import daily_blog.observability
import daily_blog.projection
import daily_blog.publication_admission
import daily_blog.publisher
import daily_blog.publisher_contract
import daily_blog.publication_article_projection
import daily_blog.publication_state
import daily_blog.publication_workflow
import daily_blog.repository_editorial_workflow
import daily_blog.repository_contracts
import daily_blog.roster_snapshots
import daily_blog.schema


#============================================
def _bundle_identity() -> daily_blog.publication_contract.PublicationIdentity:
	"""Return the current maker-bound identity required by publication."""
	contract = daily_blog.prompt_registry.editorial_contracts.active_contract()
	policy = daily_blog.prompt_registry.editorial_contracts.policy_for_contract(contract)
	snapshot = daily_blog.editorial.resolve_snapshot(contract, None, None)
	activation = daily_blog.activation.load_maker_activation().receipt
	return daily_blog.publication_contract.publication_identity(
		str(pathlib.Path(__file__).resolve().parents[1]), None,
		prompt_paths=daily_blog.prompt_registry.editorial_contracts.prompt_paths(contract), contracts={
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
def _transfer() -> daily_blog.publication_contract.SealedBundleTransfer:
	"""Return a minimal typed transfer for publisher-boundary unit tests."""
	entries = tuple(
		daily_blog.publication_contract.SealedBundleTransferEntry(
			path, b"{}" if path.endswith(".json") else b"post\n",
			daily_blog.io_utils.sha256_bytes(b"{}" if path.endswith(".json") else b"post\n"),
		)
		for path in sorted((
			"bundle.json", "evidence.json", "repository_roster.json", "editorial_projection.json",
			"publication_surface.json", "post.md",
		))
	)
	return daily_blog.publication_contract.SealedBundleTransfer("2026-08-26", "a" * 64, entries)


#============================================
def _surface(
	packet: daily_blog.schema.EvidencePacket,
) -> daily_blog.publication_admission.PublicationSurface:
	"""Build one valid survivor-scoped authority for finalization exercises."""
	repository = packet.items[0].repository
	commit = packet.items[0].commit
	activity = daily_blog.schema.RepositoryActivity(
		repository, f"https://github.com/{repository}", f"/fixture/{repository}", commit,
		(daily_blog.schema.CommitActivity(
			commit, (), "Fixture", "fixture@example.com", "2026-08-26T12:00:00-05:00",
			"2026-08-26T12:00:00-05:00", "Fixture work",
		),), (daily_blog.schema.RevisionRange("", commit),), (commit,), False,
		(daily_blog.repository_contracts.RepositoryLifecycleEvent(
			"repository_created", "2020-01-01T00:00:00Z", False, "github_owner_roster",
		),),
	)
	survivor = daily_blog.schema.EvidencePacket.create(
		packet.report_date, packet.timezone, packet.complete, packet.collection_limits.to_dict(),
		[mirror.to_dict() for mirror in packet.mirrors], [activity], list(packet.items),
	)
	evidence_ids = tuple(item.evidence_id for item in survivor.items)
	story = daily_blog.artifacts.RepoStory.create(
		survivor.report_date, (survivor,), repository,
		"Story <!-- evidence: " + ", ".join(evidence_ids) + " -->", evidence_ids,
	)
	outline = daily_blog.artifacts.DailyOutline.create(
		survivor.report_date, (survivor,), (repository,),
		"Outline <!-- evidence: " + ", ".join(evidence_ids) + " -->", evidence_ids,
	)
	limits = {"context_chars": 8000, "excerpt_chars": 1000, "commit_subject_chars": 120}
	return daily_blog.publication_admission.build_surface(
		(survivor,), (repository,), limits, (outline, story),
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
	surface = _surface(packet)
	record = daily_blog.repository_contracts.RepositoryRecord.from_dict({
		"repository": "vosslab/project",
		"repository_url": "https://github.com/vosslab/project",
		"clone_url": "https://github.com/vosslab/project.git",
		"created_at": "2020-01-01T00:00:00Z",
		"is_fork": False,
	})
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [record])
	post = (
		"---\ndate: 2026-08-26\nslug: current-publication\ngenerator_run: run-one\n"
		"evidence_manifest: evidence.json\neditorial_projection: editorial_projection.json\n---\n\n"
		f"# Current publication\n\nA small maker note.\n\n<!-- evidence: {item.evidence_id} -->\n"
	)
	selected = daily_blog.artifacts.CompletePost.create(
		report_date, (packet,), ("vosslab/project",), post, (item.evidence_id,), report_date,
		str(tmp_path / "producer" / "vosslab" / "daily_blog" / report_date / "post.md"),
	)
	producer_root = tmp_path / "producer"
	producer_root.mkdir()
	bundle_path, bundle, _transfer_value = daily_blog.publication_contract.BundleWriter(
		str(producer_root), "vosslab", _bundle_identity()
	).write("run-one", surface, {}, roster, selected)
	publisher_root = tmp_path / "publisher"
	publisher_root.mkdir()
	(publisher_root / "mkdocs.yml").write_text(
		"markdown_extensions:\n  - toc:\n      permalink: true\n", encoding="utf-8",
	)
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
		"generator_run": bundle["generator"]["run_id"],
		"generator_revision": bundle["generator"]["revision"],
		"bundle_sha256": bundle["bundle_sha256"],
		"article_body_sha256": daily_blog.publication_article_projection.article_body_sha256(
			daily_blog.publication_article_projection.source_article_projection(
				post, (publisher_root / "mkdocs.yml").read_text(encoding="utf-8"),
			)
		),
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
def _historical_v5_publication_config(tmp_path: pathlib.Path) -> types.SimpleNamespace:
	"""Convert one fixture-built v9 bundle into the retained v5/v8 read-only shape."""
	config = _current_publication_config(tmp_path)
	root = pathlib.Path(config.daily_blog_repository)
	report_date = "2026-08-26"
	archive = root / "data" / "publication_bundles" / report_date
	bundle_path = archive / "bundle.json"
	bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
	bundle.pop("publication_surface")
	bundle["schema_version"] = "vosslab.daily-blog.bundle.v8"
	bundle["bundle_sha256"] = daily_blog.publication_contract.bundle_sha256(bundle)
	bundle_path.write_text(daily_blog.io_utils.stable_json_text(bundle), encoding="utf-8")
	(archive / "publication_surface.json").unlink()
	archived_post = (archive / "post.md").read_text(encoding="utf-8")
	installed_post = root / "docs" / "blog" / "posts" / f"{report_date}.md"
	installed_post.write_text(archived_post, encoding="utf-8")
	article_digest = daily_blog.publication_article_projection.article_body_sha256(
		daily_blog.publication_article_projection.source_article_projection(
			archived_post, (root / "mkdocs.yml").read_text(encoding="utf-8"),
		)
	)
	record = {
		"schema_version": "vosslab.daily-blog.publication.v5",
		"report_date": report_date,
		"timezone": "America/Chicago",
		"generator_run": bundle["generator"]["run_id"],
		"generator_revision": bundle["generator"]["revision"],
		"bundle_sha256": bundle["bundle_sha256"],
		"article_body_sha256": article_digest,
		"best_artifact_id": bundle["best_artifact_id"],
		"evidence_manifest": f"data/publication_bundles/{report_date}/evidence.json",
		"editorial_projection_manifest": (
			f"data/publication_bundles/{report_date}/editorial_projection.json"
		),
		"post_path": f"docs/blog/posts/{report_date}.md",
		"imported_at": "2026-08-27T00:00:00Z",
	}
	record_path = root / "data" / "publications" / f"{report_date}.json"
	record_path.write_text(daily_blog.io_utils.stable_json_text(record), encoding="utf-8")
	return config


#============================================
def _historical_publication_config(
	tmp_path: pathlib.Path, evidence_padding: int = 0,
) -> types.SimpleNamespace:
	"""Create the bounded v3 archive retained for occupied-date inspection only."""
	report_date = "2026-08-26"
	publisher_root = tmp_path / "publisher"
	archive = publisher_root / "data" / "publication_bundles" / report_date
	archive.mkdir(parents=True)
	evidence = {
		"report_date": report_date, "timezone": "America/Chicago", "packet_id": "packet-one",
		"padding": "x" * evidence_padding,
	}
	projection = {"report_date": report_date, "timezone": "America/Chicago", "projection_id": "projection-one"}
	post = "---\ndate: 2026-08-26\nslug: historical-publication\n---\n\n# Historical publication\n"
	(archive / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
	(archive / "editorial_projection.json").write_text(json.dumps(projection), encoding="utf-8")
	(archive / "post.md").write_text(post, encoding="utf-8")
	bundle = {
		"schema_version": "vosslab.daily-blog.bundle.v2", "bundle_sha256": "",
		"report_date": report_date, "timezone": "America/Chicago", "assets": [],
		"generator": {"revision": "a" * 64, "run_id": "historical-run", "version": "v2"},
		"evidence": {"path": "evidence.json", "sha256": daily_blog.io_utils.hash_value(evidence)},
		"editorial_projection": {
			"path": "editorial_projection.json", "sha256": daily_blog.io_utils.hash_value(projection),
		},
		"post": {"path": "post.md", "sha256": daily_blog.io_utils.sha256_bytes(post.encode("utf-8"))},
	}
	bundle["bundle_sha256"] = daily_blog.publication_contract.bundle_sha256(bundle)
	(archive / "bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
	installed_post = publisher_root / "docs" / "blog" / "posts" / f"{report_date}.md"
	installed_post.parent.mkdir(parents=True)
	installed_post.write_text(post, encoding="utf-8")
	record = {
		"schema_version": "vosslab.daily-blog.publication.v3", "report_date": report_date,
		"timezone": "America/Chicago", "generator_run": "historical-run",
		"generator_revision": "a" * 64, "bundle_sha256": bundle["bundle_sha256"],
		"evidence_manifest": f"data/publication_bundles/{report_date}/evidence.json",
		"editorial_projection_manifest": f"data/publication_bundles/{report_date}/editorial_projection.json",
		"post_path": f"docs/blog/posts/{report_date}.md", "imported_at": "2026-08-27T00:00:00Z",
	}
	record_path = publisher_root / "data" / "publications" / f"{report_date}.json"
	record_path.parent.mkdir(parents=True)
	record_path.write_text(json.dumps(record), encoding="utf-8")
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

	def publisher(_repository: str, _bundle: daily_blog.publication_contract.SealedBundleTransfer, *, replace_existing: bool) -> object:
		observed.append(replace_existing)
		return receipt

	result = daily_blog.orchestrator.invoke_publisher(
		publisher, "/publisher", _transfer(), replace_existing=replace_existing
	)

	assert observed == [replace_existing]
	assert result == dict(receipt)


#============================================
def test_invoke_publisher_rejects_nonmapping_receipt() -> None:
	"""The publisher boundary rejects receipts without mapping semantics."""

	def publisher(_repository: str, _bundle: daily_blog.publication_contract.SealedBundleTransfer, *, replace_existing: bool) -> object:
		return [("status", "imported")]

	with pytest.raises(RuntimeError, match="must return a mapping"):
		daily_blog.orchestrator.invoke_publisher(
			publisher, "/publisher", _transfer(), replace_existing=False
		)


#============================================
def test_invoke_publisher_rejects_integer_replacement_intent() -> None:
	"""Replacement intent accepts only the Boolean protocol value."""

	def publisher(_repository: str, _bundle: daily_blog.publication_contract.SealedBundleTransfer, *, replace_existing: bool) -> object:
		return {}

	with pytest.raises(RuntimeError, match="must be Boolean"):
		daily_blog.orchestrator.invoke_publisher(
			publisher, "/publisher", _transfer(), replace_existing=1
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


#============================================
def test_publication_exists_accepts_the_exact_historical_v3_archive(
	tmp_path: pathlib.Path,
) -> None:
	"""The one retained v3 archive keeps its date occupied without a fabricated v5 receipt."""
	config = _historical_publication_config(tmp_path)

	inspection = daily_blog.publication_state.inspect_publication(config, "2026-08-26")

	assert inspection.state == "current"
	assert daily_blog.publication_state.publication_exists(config, "2026-08-26")


#============================================
def test_historical_v3_inspection_allows_its_larger_evidence_packet(
	tmp_path: pathlib.Path,
) -> None:
	"""The legacy-only reader admits old evidence that exceeds the v5/v8 receipt cap."""
	config = _historical_publication_config(
		tmp_path, daily_blog.publisher.MAX_RECORD_BYTES + 1,
	)

	inspection = daily_blog.publication_state.inspect_publication(config, "2026-08-26")

	assert inspection.state == "current"


#============================================
def test_historical_v3_archive_rejects_a_tampered_installed_post(
	tmp_path: pathlib.Path,
) -> None:
	"""A v3 record alone cannot make changed installed prose look current."""
	config = _historical_publication_config(tmp_path)
	path = pathlib.Path(config.daily_blog_repository) / "docs" / "blog" / "posts" / "2026-08-26.md"
	path.write_text("changed", encoding="utf-8")

	inspection = daily_blog.publication_state.inspect_publication(config, "2026-08-26")

	assert inspection.state == "invalid"


#============================================
def test_historical_v3_record_rejects_new_receipt_fields(
	tmp_path: pathlib.Path,
) -> None:
	"""New v5-only integrity fields cannot be claimed by a retained v3 record."""
	config = _historical_publication_config(tmp_path)
	path = pathlib.Path(config.daily_blog_repository) / "data" / "publications" / "2026-08-26.json"
	record = json.loads(path.read_text(encoding="utf-8"))
	record["article_body_sha256"] = "a" * 64
	path.write_text(json.dumps(record), encoding="utf-8")

	inspection = daily_blog.publication_state.inspect_publication(config, "2026-08-26")

	assert inspection.state == "invalid"


#============================================
@pytest.mark.parametrize("tamper", (False, True))
def test_historical_v5_bundle_v8_keeps_the_date_occupied_only_when_its_archive_is_intact(
	tmp_path: pathlib.Path, tamper: bool,
) -> None:
	"""The retained v5 reader verifies its archive rather than trusting an old receipt."""
	config = _historical_v5_publication_config(tmp_path)
	if tamper:
		path = pathlib.Path(config.daily_blog_repository) / "data" / "publication_bundles" / "2026-08-26" / "post.md"
		path.write_text("changed", encoding="utf-8")

	inspection = daily_blog.publication_state.inspect_publication(config, "2026-08-26")

	assert inspection.state == ("invalid" if tamper else "current"), inspection.reason


#============================================
def test_publication_inspection_does_not_reclassify_an_internal_fault(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Expected corrupt state is invalid, but an internal fault remains a pipeline fault."""
	config = _historical_publication_config(tmp_path)

	def fail_read(_path: str) -> object:
		raise AssertionError("internal fault")

	monkeypatch.setattr(daily_blog.io_utils, "read_json", fail_read)

	with pytest.raises(AssertionError, match="internal fault"):
		daily_blog.publication_state.inspect_publication(config, "2026-08-26")


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
	content = (
		f"---\ndate: {packet.report_date}\n---\n# Published\n\nA grounded maker note. <!-- evidence: "
		f"{packet.items[0].evidence_id} -->\n"
	)
	post = daily_blog.artifacts.CompletePost.create(
		packet.report_date, (packet,), ("vosslab/example",), content,
		(packet.items[0].evidence_id,), packet.report_date,
		str(tmp_path / "vosslab" / "daily_blog" / packet.report_date / "post.md"),
	)
	imported: list[daily_blog.publication_contract.SealedBundleTransfer] = []
	preflighted: list[daily_blog.publication_contract.SealedBundleTransfer] = []
	lifecycle: list[str] = []

	def publisher(_root: str, transfer: daily_blog.publication_contract.SealedBundleTransfer, *, replace_existing: bool) -> dict:
		imported.append(transfer)
		lifecycle.append("site_import")
		bundle = json.loads(next(entry.contents for entry in transfer.entries if entry.path == "bundle.json"))
		return {
			"schema_version": "vosslab.daily-blog.import-receipt.v2",
			"status": "imported",
			"bundle_sha256": bundle["bundle_sha256"],
			"report_date": packet.report_date,
			"publication_record_path": f"data/publications/{packet.report_date}.json",
			"publication_record_sha256": "a" * 64,
			"post_path": f"docs/blog/posts/{packet.report_date}.md",
			"post_sha256": bundle["post"]["sha256"],
			"article_body_sha256": "a" * 64,
			"rendered_page_path": (
				f"generated/releases/{packet.report_date}/blog/2026/08/26/published/index.html"
			),
			"best_artifact_id": bundle["best_artifact_id"],
		}

	def publisher_validator(_root: str, transfer: daily_blog.publication_contract.SealedBundleTransfer) -> dict:
		"""Return the publisher's strict no-write attestation for this fixture."""
		preflighted.append(transfer)
		lifecycle.append("publisher_preflight")
		bundle = json.loads(next(entry.contents for entry in transfer.entries if entry.path == "bundle.json"))
		return {
			"schema_version": "vosslab.daily-blog.import-validation.v1",
			"status": "valid",
			"bundle_sha256": bundle["bundle_sha256"],
			"report_date": packet.report_date,
			"best_artifact_id": bundle["best_artifact_id"],
		}

	def page_verifier(_root: str, receipt: dict) -> dict:
		"""Return one bound page verification without publisher filesystem access."""
		lifecycle.append("page_verification")
		return dict(receipt, rendered_page_sha256="b" * 64)

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
		coordinator.force_regeneration, roster, _surface(packet), {}, post,
	)
	def finalizer_start(phase: str, value: object) -> str:
		"""Record the bundle handoff while retaining the run's real phase transition."""
		if phase == "bundle_creation":
			lifecycle.append(phase)
		return coordinator._start(phase, value)

	finalizer = daily_blog.publication_finalization.PublicationFinalizationCoordinator(
		value, coordinator.cache, coordinator.store, coordinator.record,
		finalizer_start, coordinator._complete, daily_blog.orchestrator.invoke_publisher,
		coordinator.publisher_function, publisher_validator, page_verifier,
	)

	def write_post() -> None:
		"""Record the lifecycle's producer-owned materialization point."""
		lifecycle.append("post_write")
		coordinator._start("post_write", {"fixture": "post_write"})
		coordinator._complete("post_write", {"fixture": "post_write"})

	finalized = finalizer.finalize(write_post)
	bundle = finalized.bundle
	transfer = finalized.transfer
	saved = json.loads(pathlib.Path(coordinator.store.record_path).read_text(encoding="utf-8"))

	assert imported[0].bundle_sha256 == bundle["bundle_sha256"]
	assert all(item is transfer for item in preflighted + imported)
	assert (
		lifecycle.index("bundle_creation") < lifecycle.index("publisher_preflight")
		< lifecycle.index("post_write") < lifecycle.index("site_import")
		< lifecycle.index("page_verification")
	)
	assert not pathlib.PurePosixPath(saved["publication_bundle"]["path"]).is_absolute()


#============================================
def test_finalization_stops_before_post_write_when_publisher_preflight_rejects(
	tmp_path: pathlib.Path,
) -> None:
	"""A publisher-policy fault cannot materialize a post before its attestation."""
	config = _path_record_config(tmp_path)
	roster = _path_record_roster()
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-26", "America/Chicago", True, {}, [], [], [
			daily_blog.schema.EvidenceItem.create(
				"commit_metadata", "vosslab/example", "a" * 40, "", "", "work", "git show",
			),
		],
	)
	post = daily_blog.artifacts.CompletePost.create(
		packet.report_date, (packet,), ("vosslab/example",),
		f"---\ndate: {packet.report_date}\n---\n# Published\n\nGrounded. <!-- evidence: {packet.items[0].evidence_id} -->\n",
		(packet.items[0].evidence_id,), packet.report_date,
		str(tmp_path / "vosslab" / "daily_blog" / packet.report_date / "post.md"),
	)
	coordinator = daily_blog.orchestrator.DailyPublicationOrchestrator(config, packet.report_date)
	for phase in daily_blog.run_contracts.LEGAL_PHASES:
		if phase == "bundle_creation":
			break
		coordinator._start(phase, {"fixture": phase})
		coordinator._complete(phase, {"fixture": phase})
	value = daily_blog.publication_finalization.SealedPublicationInput(
		packet.report_date, coordinator.run_id, config.output_root, config.output_owner,
		config.daily_blog_repository, coordinator.generator_identity,
		coordinator.force_regeneration, roster, _surface(packet), {}, post,
	)
	def reject_preflight(*_args: object) -> dict:
		"""Model the publisher's safe typed validation rejection."""
		raise daily_blog.publisher_contract.PublisherCommandError("snapshot_rejected", "validate")

	finalizer = daily_blog.publication_finalization.PublicationFinalizationCoordinator(
		value, coordinator.cache, coordinator.store, coordinator.record,
		coordinator._start, coordinator._complete, daily_blog.orchestrator.invoke_publisher,
		lambda *_args, **_kwargs: {},
		reject_preflight,
		lambda *_args: {},
	)
	written: list[bool] = []

	with pytest.raises(daily_blog.publisher_contract.PublisherCommandError):
		finalizer.finalize(lambda: written.append(True))

	assert written == []
	assert coordinator.record.phases["post_write"].status == "pending"


#============================================
def test_orchestrator_records_publisher_preflight_as_an_operational_fault(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A typed publisher rejection fails the actual run before post materialization."""
	config = _path_record_config(tmp_path)
	record = daily_blog.repository_contracts.RepositoryRecord.from_dict({
		"repository": "vosslab/example", "repository_url": "https://github.com/vosslab/example",
		"clone_url": "https://github.com/vosslab/example.git", "created_at": "2026-08-23T00:00:00Z",
		"is_fork": False,
	})
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [record])
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog", "vosslab/example", "a" * 40, "docs/CHANGELOG.md", "b" * 40,
		"Fixture work.", "fixture",
	)
	activity = daily_blog.schema.RepositoryActivity(
		"vosslab/example", "https://github.com/vosslab/example", "/fixture/example",
		"a" * 40,
		(daily_blog.schema.CommitActivity(
			"a" * 40, (), "Fixture", "fixture@example.com",
			"2026-08-26T12:00:00-05:00", "2026-08-26T12:00:00-05:00", "Fixture work",
		),),
		(daily_blog.schema.RevisionRange("", "a" * 40),), ("a" * 40,), False,
		(daily_blog.repository_contracts.RepositoryLifecycleEvent(
			"repository_created", "2020-01-01T00:00:00Z", False, "github_owner_roster",
		),),
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-26", "America/Chicago", True, {}, [], [activity], [item],
	)
	story = daily_blog.artifacts.RepoStory.create(
		packet.report_date, (packet,), "vosslab/example",
		"Grounded story. <!-- evidence: " + item.evidence_id + " -->", (item.evidence_id,),
	)
	outline = daily_blog.artifacts.DailyOutline.create(
		packet.report_date, (packet,), ("vosslab/example",),
		"Grounded outline. <!-- evidence: " + item.evidence_id + " -->", (item.evidence_id,),
	)
	limits = {"context_chars": 8000, "excerpt_chars": 1000, "commit_subject_chars": 120}
	surface = daily_blog.publication_admission.build_surface(
		(packet,), ("vosslab/example",), limits, (outline, story),
	)
	post = daily_blog.artifacts.CompletePost.create(
		packet.report_date, (packet,), ("vosslab/example",),
		f"---\ndate: {packet.report_date}\n---\n# Fixture\n\nGrounded. <!-- evidence: {item.evidence_id} -->\n",
		(item.evidence_id,), packet.report_date,
		str(tmp_path / "vosslab" / "daily_blog" / packet.report_date / "post.md"),
	)
	publisher_calls: list[str] = []

	def complete(orchestrator: daily_blog.orchestrator.DailyPublicationOrchestrator, phase: str) -> None:
		"""Advance one mocked upstream boundary through the real run record."""
		orchestrator._start(phase, {"fixture": phase})
		orchestrator._complete(phase, {"fixture": phase})

	def reject_preflight(*_args: object) -> dict:
		"""Return one valid typed publisher operational failure."""
		raise daily_blog.publisher_contract.PublisherCommandError("snapshot_rejected", "validate")

	runtime = daily_blog.publication_workflow.PublicationRuntime(
		publisher_function=lambda *_args, **_kwargs: publisher_calls.append("site_import") or {},
		publisher_validator=reject_preflight,
	)
	orchestrator = daily_blog.orchestrator.DailyPublicationOrchestrator(config, packet.report_date, runtime=runtime)

	def acquire() -> object:
		"""Return a sealed fixture after advancing actual acquisition phases."""
		for phase in (
			"repository_discovery", "mirror_refresh", "activity_location", "evidence_assembly",
		):
			complete(orchestrator, phase)
		return types.SimpleNamespace(roster=roster, packet=packet, assets={})

	def repository_editorial() -> object:
		"""Return the narrow Stage 5 handoff after the repository editorial phase."""
		complete(orchestrator, "repository_editorial")
		return types.SimpleNamespace(stage5_input=object(), route_capacity=object(), route_budget=object())

	def stage5(*_args: object) -> object:
		complete(orchestrator, "stage5_daily_outline")
		return types.SimpleNamespace(publication_surface=surface)

	def stage6(*_args: object) -> object:
		complete(orchestrator, "stage6_complete_post")
		return types.SimpleNamespace(artifact=post)

	def stage7(*_args: object) -> object:
		complete(orchestrator, "stage7_final_synthesis")
		return types.SimpleNamespace(artifact=post)

	def validate(*_args: object) -> object:
		complete(orchestrator, "publication_validation")
		return types.SimpleNamespace(source_post=post, post=post)

	monkeypatch.setattr(
		daily_blog.acquisition_workflow, "AcquisitionCoordinator",
		lambda _dependencies: types.SimpleNamespace(acquire=acquire),
	)
	monkeypatch.setattr(
		daily_blog.repository_editorial_workflow, "RepositoryEditorialCoordinator",
		lambda _dependencies: types.SimpleNamespace(run=lambda _packet: repository_editorial()),
	)
	monkeypatch.setattr(daily_blog.publication_workflow, "run_typed_stage5", stage5)
	monkeypatch.setattr(daily_blog.publication_workflow, "run_typed_stage6", stage6)
	monkeypatch.setattr(daily_blog.publication_workflow, "run_typed_stage7", stage7)
	monkeypatch.setattr(daily_blog.publication_workflow, "validate_selected_post", validate)
	with pytest.raises(daily_blog.publisher_contract.PublisherCommandError):
		orchestrator.run()

	stored = json.loads(pathlib.Path(orchestrator.store.record_path).read_text(encoding="utf-8"))
	terminal_lines = pathlib.Path(orchestrator.store.summary_path).read_text(encoding="utf-8").splitlines()
	terminal = next(
		(
			daily_blog.observability.parse_terminal_summary_line(line)
			for line in terminal_lines
			if line
		),
		None,
	)
	assert stored["failure"] == {"phase": "publisher_preflight", "kind": "snapshot_rejected"}
	assert (
		terminal is not None and not publisher_calls
		and stored["phases"]["post_write"]["status"] == "pending"
		and (
			terminal["failure_phase"], terminal["terminal_fault_category"],
			terminal["operational_failure_kind"],
		) == ("publisher_preflight", "", "snapshot_rejected")
	)

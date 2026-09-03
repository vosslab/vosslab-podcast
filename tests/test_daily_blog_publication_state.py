"""Date-owned publication state and replacement tests."""

# Standard Library
import contextlib
import json
import pathlib
import types

# PIP3 modules
import pytest

# local repo modules
import automation.publish_daily_blog
import daily_blog.artifacts
import daily_blog.activity
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
import daily_blog.publication_state
import daily_blog.publication_workflow
import daily_blog.repository_editorial_workflow
import daily_blog.repository_contracts
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
			"bundle.json", "evidence.json", "repository_roster.json", "daily_active_roster.json",
			"editorial_projection.json",
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
def _active_roster(
	packet: daily_blog.schema.EvidencePacket,
	roster: daily_blog.repository_contracts.RepositoryRoster,
) -> dict:
	"""Return the machine-observed roster provenance for one synthetic packet."""
	repository = packet.items[0].repository
	return daily_blog.activity.build_daily_active_roster("vosslab", packet.report_date, roster.roster_id, [{
		"repository": repository, "sha": packet.items[0].commit,
		"author_timestamp": packet.report_date + "T12:00:00Z",
		"author_name": "Fixture", "message": "Fixture work",
	}])


#============================================
def _path_record_config(tmp_path: pathlib.Path) -> daily_blog.config.DailyBlogConfig:
	"""Build an offline configuration whose output root is intentionally unique."""
	return daily_blog.config.DailyBlogConfig(
		settings_path="settings.yaml", output_root=str(tmp_path), output_owner="vosslab",
		report_timezone="America/Chicago", daily_blog_repository=str(tmp_path / "publisher"),
		mirror_cache_root=str(tmp_path / "mirrors"),
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
def test_publication_inspection_uses_the_installed_post_and_release(tmp_path: pathlib.Path) -> None:
	"""The renderer's two durable outputs make one report date occupied."""
	root = tmp_path / "publisher"
	post = root / "docs" / "blog" / "posts" / "2026-08-26.md"
	post.parent.mkdir(parents=True)
	post.write_text("# Published\n", encoding="utf-8")
	(root / "generated" / "releases" / "2026-08-26").mkdir(parents=True)
	config = types.SimpleNamespace(daily_blog_repository=str(root))

	inspection = daily_blog.publication_state.inspect_publication(config, "2026-08-26")

	assert inspection.state == "current"


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
	lifecycle: list[str] = []

	def publisher(_root: str, transfer: daily_blog.publication_contract.SealedBundleTransfer, *, replace_existing: bool) -> dict:
		imported.append(transfer)
		lifecycle.append("site_import")
		bundle = json.loads(next(entry.contents for entry in transfer.entries if entry.path == "bundle.json"))
		return {
			"schema_version": "vosslab.daily-blog.import-receipt.v3",
			"status": "imported",
			"bundle_sha256": bundle["bundle_sha256"],
			"report_date": packet.report_date,
			"post_path": f"docs/blog/posts/{packet.report_date}.md",
			"post_sha256": bundle["post"]["sha256"],
			"assets": [],
			"article_body_sha256": "a" * 64,
			"rendered_page_path": (
				f"generated/releases/{packet.report_date}/blog/2026/08/26/published/index.html"
			),
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
		coordinator.force_regeneration, roster, _surface(packet), {}, post, _active_roster(packet, roster),
	)
	def finalizer_start(phase: str, value: object) -> str:
		"""Record the bundle handoff while retaining the run's real phase transition."""
		if phase == "bundle_creation":
			lifecycle.append(phase)
		return coordinator._start(phase, value)

	finalizer = daily_blog.publication_finalization.PublicationFinalizationCoordinator(
		value, coordinator.cache, coordinator.store, coordinator.record,
		finalizer_start, coordinator._complete, daily_blog.orchestrator.invoke_publisher,
		coordinator.publisher_function, page_verifier,
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
	assert imported == [transfer]
	assert (
		lifecycle.index("bundle_creation") < lifecycle.index("post_write") < lifecycle.index("site_import")
		< lifecycle.index("page_verification")
	)
	assert not pathlib.PurePosixPath(saved["publication_bundle"]["path"]).is_absolute()

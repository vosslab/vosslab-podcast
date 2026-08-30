"""Date-owned publication bundle and checksum contract tests."""

# Standard Library
import json
import os
import pathlib
import copy

# PIP3 modules
import pytest

# local repo modules
import daily_blog.schema
import daily_blog.artifacts
import daily_blog.repository_contracts
import daily_blog.publication_contract
import daily_blog.editorial
import daily_blog.contracts
import daily_blog.prompt_registry
import daily_blog.activation
import daily_blog.io_utils
import daily_blog.projection
import daily_blog.publication_storage


#============================================
def storage_artifacts() -> dict[str, bytes]:
	"""Return the smallest complete storage payload for boundary exercises."""
	return {
		"bundle.json": b"{}\n",
		"evidence.json": b"{}\n",
		"repository_roster.json": b"{}\n",
		"editorial_projection.json": b"{}\n",
		"post.md": b"A complete post.\n",
		"assets/screenshot.png": b"image-bytes",
	}


#============================================
def test_descriptor_storage_round_trips_only_confined_bundle_artifacts(
	tmp_path: pathlib.Path,
) -> None:
	"""A complete bundle round-trips through the public descriptor storage boundary."""
	storage = daily_blog.publication_storage.PublicationStorage(
		str(tmp_path), "vosslab", "2026-08-23", "storage-round-trip",
	)
	path = storage.write(storage_artifacts())

	assert pathlib.Path(path).is_dir()
	assert storage.read() == storage_artifacts()


#============================================
def test_descriptor_storage_rejects_asset_traversal_and_nonregular_artifacts(
	tmp_path: pathlib.Path,
) -> None:
	"""Unconfined names and a symlinked stored asset never become reusable input."""
	storage = daily_blog.publication_storage.PublicationStorage(
		str(tmp_path), "vosslab", "2026-08-23", "storage-rejections",
	)
	with pytest.raises(RuntimeError, match="asset name"):
		storage.write({**storage_artifacts(), "assets/../outside": b"bad"})
	storage.write(storage_artifacts())
	asset = tmp_path / "vosslab" / "daily_blog" / "2026-08-23" / "publication" / "assets" / "screenshot.png"
	asset.unlink()
	os.symlink("/dev/null", asset)
	with pytest.raises(RuntimeError, match="unavailable|regular"):
		storage.read()


#============================================
def make_projection(
	packet: daily_blog.schema.EvidencePacket,
) -> daily_blog.schema.EditorialProjection:
	"""Return one compact validated projection for bundle tests."""
	limits = {
		"context_chars": 8000,
		"excerpt_chars": 1000,
		"commit_subject_chars": 120,
	}
	return daily_blog.projection.build_projection(packet, limits)


#============================================
def bundle_roster(
	packet: daily_blog.schema.EvidencePacket,
) -> daily_blog.repository_contracts.RepositoryRoster:
	"""Return a complete test roster that covers every active packet repository."""
	repositories = {activity.repository for activity in packet.activity} or {"vosslab/project"}
	records = [
		daily_blog.repository_contracts.RepositoryRecord.from_dict({
			"repository": repository,
			"repository_url": f"https://github.com/{repository}",
			"clone_url": f"https://github.com/{repository}.git",
			"created_at": "2020-01-01T00:00:00Z",
			"is_fork": False,
		})
		for repository in sorted(repositories)
	]
	return daily_blog.repository_contracts.RepositoryRoster.create("vosslab", records)


#============================================
def selected_post(
	tmp_path: pathlib.Path, packet: daily_blog.schema.EvidencePacket, content: str,
) -> daily_blog.artifacts.CompletePost:
	"""Return the exact typed post which publication is allowed to seal."""
	evidence_ids = tuple(sorted(item.evidence_id for item in packet.items))
	if not daily_blog.artifacts.evidence_references(content):
		content += "\n<!-- evidence: " + ", ".join(evidence_ids) + " -->\n"
	return daily_blog.artifacts.CompletePost.create(
		packet.report_date,
		(packet,),
		tuple(sorted({item.repository for item in packet.items})),
		content,
		evidence_ids,
		packet.report_date,
		str(tmp_path / "vosslab" / "daily_blog" / packet.report_date / "post.md"),
	)


#============================================
def bundle_identity(
	contract: daily_blog.contracts.EditorialContract | None = None,
	snapshot: daily_blog.editorial.PromptContractSnapshot | None = None,
) -> daily_blog.publication_contract.PublicationIdentity:
	"""Build the primitive identity that the orchestration boundary supplies."""
	# Publication identity is production-shaped even when the surrounding bundle
	# exercise uses compact synthetic evidence.
	contract = daily_blog.prompt_registry.active_contract()
	snapshot = daily_blog.editorial.resolve_snapshot(contract, None, snapshot)
	policy = daily_blog.prompt_registry.policy_for_contract(contract)
	activation_receipt = daily_blog.activation.load_maker_activation().receipt
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
			"activation_id": activation_receipt["activation_id"],
			"editorial_prompt_contract_sha256": activation_receipt[
				"editorial_prompt_contract_sha256"
			],
		},
	)


#============================================
def test_bundle_writer_hashes_and_promotes_one_date_owned_publication(
	tmp_path: pathlib.Path,
) -> None:
	"""A complete staged run becomes the current bundle at one stable date path."""
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/project", "a" * 40, "", "", "located work", "git show"
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item]
	)
	projection = make_projection(packet)
	post = "approved selected post\n"
	complete_post = selected_post(tmp_path, packet, post)
	writer = daily_blog.publication_contract.BundleWriter(
		str(tmp_path), "vosslab", bundle_identity()
	)

	bundle_path, bundle = writer.write(
		"run-one", packet, projection, {}, bundle_roster(packet), complete_post
	)

	with open(f"{bundle_path}/bundle.json", "r", encoding="utf-8") as handle:
		written = json.load(handle)
	assert written["bundle_sha256"] == daily_blog.publication_contract.bundle_sha256(written)
	assert pathlib.Path(bundle_path).is_relative_to(tmp_path / "vosslab" / "daily_blog" / packet.report_date)
	assert bundle["editorial_projection"]["projection_id"] == projection.projection_id
	replacement_path, replacement = writer.write(
		"run-two", packet, projection, {}, bundle_roster(packet), complete_post
	)

	assert replacement_path == bundle_path
	assert replacement["generator"]["run_id"] == "run-two"


#============================================
#============================================
def write_generator_contract(
	root: pathlib.Path, contract: daily_blog.contracts.EditorialContract
) -> None:
	"""Write one minimal producer source, prompt, support, and settings contract."""
	(root / "pipeline" / "daily_blog").mkdir(parents=True)
	(root / "pipeline" / "podlib").mkdir(parents=True)
	(root / "pipeline" / "prompts").mkdir(parents=True)
	(root / "pipeline" / "daily_blog" / "module.py").write_text(
		"VALUE = 'source-one'\n",
		encoding="utf-8",
	)
	for relative_path in daily_blog.publication_contract.GENERATOR_SUPPORT_PATHS:
		(root / relative_path).write_text("VALUE = 'support'\n", encoding="utf-8")
	for relative_path in daily_blog.prompt_registry.prompt_paths(contract):
		(root / relative_path).write_text("Prompt contract one.\n", encoding="utf-8")
	(root / "settings.yaml").write_text("daily_blog: {}\n", encoding="utf-8")


#============================================
def test_generator_revision_fingerprints_dirty_source(
	tmp_path: pathlib.Path,
) -> None:
	"""An uncommitted source change produces a new generator identity."""
	contract = daily_blog.prompt_registry.active_contract()
	write_generator_contract(tmp_path, contract)
	identity = bundle_identity(contract)
	first = daily_blog.publication_contract.generator_revision(
		str(tmp_path), prompt_paths=daily_blog.prompt_registry.prompt_paths(contract), contracts=identity.contracts_dict(),
	)
	(tmp_path / "pipeline" / "daily_blog" / "module.py").write_text(
		"VALUE = 'source-two'\n",
		encoding="utf-8",
	)
	second = daily_blog.publication_contract.generator_revision(
		str(tmp_path), prompt_paths=daily_blog.prompt_registry.prompt_paths(contract), contracts=identity.contracts_dict(),
	)
	assert first != second


#============================================
def test_reusable_bundle_requires_a_structured_publication_identity() -> None:
	"""Bundle reuse accepts the sealed value contract, never a raw revision string."""
	with pytest.raises(RuntimeError, match="publication identity"):
		daily_blog.publication_contract.load_reusable_bundle(
			{},
			"/nonexistent/vosslab-test/bundles",
			None,
			None,
			{},
			"f" * 64,  # type: ignore[arg-type]
		)


#============================================
def make_v4_bundle(
	tmp_path: pathlib.Path,
	contract: daily_blog.contracts.EditorialContract,
	run_id: str,
) -> tuple[
	daily_blog.publication_contract.PublicationIdentity,
	daily_blog.editorial.PromptContractSnapshot,
	daily_blog.schema.EvidencePacket,
	daily_blog.schema.EditorialProjection,
	dict,
	str,
]:
	"""Write one small valid v4 bundle and return its exact reuse inputs."""
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/project", "a" * 40, "", "", "located work", "git show"
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item]
	)
	projection = make_projection(packet)
	post = "approved selected post\n"
	snapshot = daily_blog.editorial.load_prompt_contract_snapshot(contract)
	identity = bundle_identity(contract, snapshot)
	writer = daily_blog.publication_contract.BundleWriter(
		str(tmp_path),
		"vosslab",
		identity,
	)
	bundle_path, bundle = writer.write(
		run_id,
		packet,
		projection,
		{},
		bundle_roster(packet),
		selected_post(tmp_path, packet, post),
	)
	record = {"bundle_path": bundle_path, "bundle": bundle}
	date_root = str(tmp_path / "vosslab" / "daily_blog" / packet.report_date)
	return identity, snapshot, packet, projection, record, date_root


#============================================
def test_active_factory_identity_writes_and_reuses_issued_contract(
	tmp_path: pathlib.Path,
) -> None:
	"""The active factory-issued identity and snapshot permit bundle reuse."""
	contract = daily_blog.prompt_registry.active_contract()
	identity, snapshot, packet, projection, record, date_root = make_v4_bundle(
		tmp_path,
		contract,
		"exact-v4",
	)
	bundle_path, bundle = daily_blog.publication_contract.load_reusable_bundle(
		record,
		date_root,
		packet,
		projection,
		{},
		identity,
		bundle_roster(packet),
	)

	assert bundle_path == record["bundle_path"]
	assert bundle["editorial_prompt_contract"] == daily_blog.editorial.prompt_contract_identity(
		snapshot=snapshot
	)


#============================================
def test_publication_identity_seals_caller_owned_nested_inputs(
	tmp_path: pathlib.Path,
) -> None:
	"""Writing and reuse retain the factory-sealed nested identity values."""
	issued_identity = bundle_identity(daily_blog.prompt_registry.active_contract())
	contracts = issued_identity.contracts_dict()
	prompt_contract = issued_identity.prompt_contract_dict()
	activation_receipt = issued_identity.activation_receipt_dict()
	expected_contracts = copy.deepcopy(contracts)
	expected_prompt_contract = copy.deepcopy(prompt_contract)
	expected_activation_receipt = copy.deepcopy(activation_receipt)
	identity = daily_blog.publication_contract.publication_identity(
		str(pathlib.Path(__file__).resolve().parents[1]),
		None,
		prompt_paths=daily_blog.prompt_registry.prompt_paths(daily_blog.prompt_registry.active_contract()),
		contracts=contracts,
		editorial_prompt_contract=prompt_contract,
		activation_receipt=activation_receipt,
	)
	contracts["candidate_validation"]["version"] = "caller-mutated"
	prompt_contract["candidate_validation"]["version"] = "caller-mutated"
	activation_receipt["activation_id"] = "daily-blog-maker-activation-" + "0" * 64
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/project", "a" * 40, "", "", "located work", "git show"
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item]
	)
	projection = make_projection(packet)
	writer = daily_blog.publication_contract.BundleWriter(str(tmp_path), "vosslab", identity)
	bundle_path, bundle = writer.write(
		"sealed-caller-inputs", packet, projection, {}, bundle_roster(packet),
		selected_post(tmp_path, packet, "sealed selected post\n"),
	)
	_, reused = daily_blog.publication_contract.load_reusable_bundle(
		{"bundle_path": bundle_path, "bundle": bundle},
		str(tmp_path / "vosslab" / "daily_blog" / packet.report_date),
		packet, projection, {}, identity, bundle_roster(packet),
	)

	assert reused["contracts"] == expected_contracts
	assert reused["editorial_prompt_contract"] == expected_prompt_contract
	assert reused["maker_activation"] == expected_activation_receipt
	assert reused["maker_activation"]["editorial_prompt_contract_sha256"] == (
		daily_blog.io_utils.hash_value(reused["editorial_prompt_contract"])
	)


#============================================
def test_active_bundle_reuse_rejects_an_altered_activation_receipt(
	tmp_path: pathlib.Path,
) -> None:
	"""A cache hit remains bound to the receipt that selected the maker contract."""
	contract = daily_blog.prompt_registry.active_contract()
	identity, snapshot, packet, projection, record, date_root = make_v4_bundle(
		tmp_path, contract, "active-activation"
	)
	tampered = copy.deepcopy(record["bundle"])
	tampered["maker_activation"]["activation_id"] = "daily-blog-maker-activation-" + "0" * 64
	tampered["bundle_sha256"] = daily_blog.publication_contract.bundle_sha256(tampered)
	bundle_path = pathlib.Path(record["bundle_path"])
	(bundle_path / "bundle.json").write_text(json.dumps(tampered), encoding="utf-8")
	record["bundle"] = tampered

	with pytest.raises(RuntimeError, match="generator contracts have changed"):
		daily_blog.publication_contract.load_reusable_bundle(
		record, date_root, packet, projection, {}, identity, bundle_roster(packet)
		)


#============================================
def test_v4_reuse_rejects_tampered_persisted_prompt_contract(
	tmp_path: pathlib.Path,
) -> None:
	"""Reuse compares the persisted v4 contract, selection, and example digest exactly."""
	contract = daily_blog.prompt_registry.active_contract()
	identity, snapshot, packet, projection, record, date_root = make_v4_bundle(
		tmp_path,
		contract,
		"persisted-attacks",
	)
	tampered = copy.deepcopy(record["bundle"])
	prompt_contract = tampered["editorial_prompt_contract"]
	prompt_contract.update({"contract_name": "tampered"})
	tampered["bundle_sha256"] = daily_blog.publication_contract.bundle_sha256(tampered)
	bundle_path = pathlib.Path(record["bundle_path"])
	(bundle_path / "bundle.json").write_text(json.dumps(tampered), encoding="utf-8")
	record["bundle"] = tampered

	with pytest.raises(RuntimeError, match="prompt contract"):
		daily_blog.publication_contract.load_reusable_bundle(
		record, date_root, packet, projection, {}, identity, bundle_roster(packet)
		)


#============================================
def test_reusable_bundle_rejects_a_changed_authoritative_roster(
	tmp_path: pathlib.Path,
) -> None:
	"""A cache hit cannot reuse a bundle after repository scope changes."""
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/project", "a" * 40, "", "", "located work", "git show"
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item]
	)
	projection = make_projection(packet)
	post = "selected post\n"
	writer = daily_blog.publication_contract.BundleWriter(
		str(tmp_path), "vosslab", bundle_identity()
	)
	bundle_path, bundle = writer.write(
		"roster-scope", packet, projection, {}, bundle_roster(packet), selected_post(tmp_path, packet, post)
	)
	quiet = daily_blog.repository_contracts.RepositoryRecord.from_dict({
		"repository": "vosslab/quiet-repository",
		"repository_url": "https://github.com/vosslab/quiet-repository",
		"clone_url": "https://github.com/vosslab/quiet-repository.git",
		"created_at": "2020-01-01T00:00:00Z",
		"is_fork": False,
	})
	changed_roster = daily_blog.repository_contracts.RepositoryRoster.create(
		"vosslab", [*bundle_roster(packet).repositories, quiet]
	)
	with pytest.raises(RuntimeError, match="roster integrity"):
		daily_blog.publication_contract.load_reusable_bundle(
			{"bundle_path": bundle_path, "bundle": bundle},
			str(tmp_path / "vosslab" / "daily_blog" / packet.report_date),
			packet,
			projection,
			{},
			bundle_identity(), changed_roster,
		)


#============================================
def test_reuse_rejects_a_tampered_candidate_validation_artifact(
	tmp_path: pathlib.Path,
) -> None:
	"""A persisted policy artifact cannot silently select a changed policy contract."""
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/project", "a" * 40, "", "", "located work", "git show"
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item]
	)
	projection = make_projection(packet)
	post = "selected post\n"
	writer = daily_blog.publication_contract.BundleWriter(
		str(tmp_path), "vosslab", bundle_identity()
	)
	bundle_path, bundle = writer.write(
		"tampered-policy", packet, projection, {}, bundle_roster(packet), selected_post(tmp_path, packet, post)
	)
	tampered = copy.deepcopy(bundle)
	tampered["contracts"]["candidate_validation"]["version"] = "retired"
	tampered["bundle_sha256"] = daily_blog.publication_contract.bundle_sha256(tampered)
	(pathlib.Path(bundle_path) / "bundle.json").write_text(json.dumps(tampered), encoding="utf-8")
	record = {"bundle_path": bundle_path, "bundle": tampered}
	date_root = str(tmp_path / "vosslab" / "daily_blog" / packet.report_date)

	with pytest.raises(RuntimeError, match="generator contracts have changed"):
		daily_blog.publication_contract.load_reusable_bundle(
			record, date_root, packet, projection, {},
		bundle_identity(), bundle_roster(packet)
		)

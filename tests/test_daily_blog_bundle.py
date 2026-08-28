"""Date-owned publication bundle and checksum contract tests."""

# Standard Library
import json
import re
import pathlib
import dataclasses
import copy

# PIP3 modules
import pytest

# local repo modules
import daily_blog.schema
import daily_blog.repository_contracts
import daily_blog.bundles
import daily_blog.editorial
import daily_blog.contracts
import daily_blog.io_utils
import daily_blog.projection


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
	decision = daily_blog.editorial.EditorialDecision(
		winner="A",
		reason="Candidate A is approved for final publication.",
		evidence_quality="medium",
		confidence=0.8,
		projection_id=projection.projection_id,
		post=post,
		anonymous_mapping={"A": 0},
	)
	candidate = daily_blog.editorial.CandidateResult(
		private_route="author",
		projection_id=projection.projection_id,
		post=post,
		post_hash=daily_blog.io_utils.sha256_text(post),
		valid=True,
		issues=(),
	)
	writer = daily_blog.bundles.BundleWriter(str(tmp_path), "vosslab", "f" * 64)

	bundle_path, bundle = writer.write(
		"run-one", packet, projection, {}, [candidate, candidate], decision, bundle_roster(packet)
	)

	with open(f"{bundle_path}/bundle.json", "r", encoding="utf-8") as handle:
		written = json.load(handle)
	assert written["bundle_sha256"] == daily_blog.bundles.bundle_sha256(written)
	assert bundle_path.endswith(f"/{packet.report_date}/publication")
	assert bundle["editorial_projection"]["projection_id"] == projection.projection_id
	replacement_path, replacement = writer.write(
		"run-two", packet, projection, {}, [candidate, candidate], decision, bundle_roster(packet)
	)

	assert replacement_path == bundle_path
	assert replacement["generator"]["run_id"] == "run-two"
	assert not tuple(pathlib.Path(bundle_path).parent.glob(".*.staging-*"))


#============================================
def test_bundle_records_anonymous_winner_mapping_and_exact_post_hash(
	tmp_path: pathlib.Path,
) -> None:
	"""The publisher can prove which anonymous valid candidate became the final post."""
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/project", "a" * 40, "", "", "located work", "git show"
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item]
	)
	projection = make_projection(packet)
	post = "final selected post\n"
	candidates = [
		daily_blog.editorial.CandidateResult(
			"one",
			projection.projection_id,
			"other\n",
			"1" * 64,
			False,
			("invalid",),
		),
		daily_blog.editorial.CandidateResult(
			"two",
			projection.projection_id,
			post,
			daily_blog.io_utils.sha256_text(post),
			True,
			(),
		),
	]
	decision = daily_blog.editorial.EditorialDecision(
		winner="A",
		reason="Candidate A matches the exact evidence.",
		evidence_quality="high",
		confidence=0.9,
		projection_id=projection.projection_id,
		post=post,
		anonymous_mapping={"A": 1},
	)
	writer = daily_blog.bundles.BundleWriter(str(tmp_path), "vosslab", "f" * 64)

	_bundle_path, bundle = writer.write(
		"run-final", packet, projection, {}, candidates, decision, bundle_roster(packet)
	)

	assert bundle["referee"]["anonymous_mapping"] == {"A": "candidate_2"}
	assert bundle["post"]["sha256"] == candidates[1].post_hash


#============================================
def write_generator_contract(root: pathlib.Path) -> None:
	"""Write one minimal producer source, prompt, support, and settings contract."""
	(root / "pipeline" / "daily_blog").mkdir(parents=True)
	(root / "pipeline" / "podlib").mkdir(parents=True)
	(root / "pipeline" / "prompts").mkdir(parents=True)
	(root / "pipeline" / "daily_blog" / "module.py").write_text(
		"VALUE = 'source-one'\n",
		encoding="utf-8",
	)
	for relative_path in daily_blog.bundles.GENERATOR_SUPPORT_PATHS:
		(root / relative_path).write_text("VALUE = 'support'\n", encoding="utf-8")
	for relative_path in daily_blog.contracts.active_contract().prompt_paths():
		(root / relative_path).write_text("Prompt contract one.\n", encoding="utf-8")
	(root / "settings.yaml").write_text("daily_blog: {}\n", encoding="utf-8")


#============================================
def test_generator_revision_fingerprints_dirty_source_and_exact_prompt_bytes(
	tmp_path: pathlib.Path,
) -> None:
	"""Uncommitted source or prompt changes produce a new lowercase SHA-256 generator identity."""
	write_generator_contract(tmp_path)
	first = daily_blog.bundles.generator_revision(str(tmp_path))
	(tmp_path / "pipeline" / "daily_blog" / "module.py").write_text(
		"VALUE = 'source-two'\n",
		encoding="utf-8",
	)
	second = daily_blog.bundles.generator_revision(str(tmp_path))
	prompt_path = daily_blog.contracts.active_contract().prompt_paths()[0]
	(tmp_path / prompt_path).write_text(
		"Prompt contract two.\n",
		encoding="utf-8",
	)
	third = daily_blog.bundles.generator_revision(str(tmp_path))

	assert re.fullmatch(r"[0-9a-f]{64}", first) is not None
	assert first != second and second != third and first != third


#============================================
def test_generator_revision_uses_the_explicit_contract_prompt_paths(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A future experiment hashes its own prompt resources instead of v3 globals."""
	write_generator_contract(tmp_path)
	contract = daily_blog.contracts.V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT
	assert "pipeline/prompts/daily_blog_voice_examples_v4.md" in contract.prompt_paths()
	for relative_path in contract.prompt_paths():
		path = tmp_path / relative_path
		path.write_text("Future contract prompt.\n", encoding="utf-8")
	resource_text = (
		"<!-- editorial-example: aug-23 -->\nB\n<!-- /editorial-example -->\n"
		"<!-- editorial-example: corpus-quiet-til -->\n"
		+ daily_blog.contracts.EXTERNAL_EXAMPLE_BLOCKS["corpus-quiet-til"]
		+ "<!-- /editorial-example -->\n"
		+ "<!-- editorial-example: corpus-selectivity-ghostty -->\n"
		+ daily_blog.contracts.EXTERNAL_EXAMPLE_BLOCKS["corpus-selectivity-ghostty"]
		+ "<!-- /editorial-example -->\n"
	)
	templates = {
		"author": "{examples}{evidence_json}\n## Output contract",
		"referee": "{candidate_a}{candidate_b}\n## Output contract",
		"repair": "Return JSON.",
		"rubric": "Grounded detail.",
	}
	monkeypatch.setattr(daily_blog.editorial, "load_prompt", lambda name: templates[
		"author" if "author" in name else "referee" if "referee" in name else "repair" if "repair" in name else "rubric"
	])
	monkeypatch.setattr(daily_blog.editorial, "load_plain_prompt_resource", lambda _name: (
		resource_text, resource_text.encode("utf-8")
	))
	first_snapshot = daily_blog.editorial.load_prompt_contract_snapshot(contract)
	resource_text = resource_text.replace("B", "Changed B")
	second_snapshot = daily_blog.editorial.load_prompt_contract_snapshot(contract)
	first = daily_blog.bundles.generator_revision(
		str(tmp_path), contract=contract, snapshot=first_snapshot
	)
	second = daily_blog.bundles.generator_revision(
		str(tmp_path), contract=contract, snapshot=second_snapshot
	)
	resource_path = tmp_path / "pipeline/prompts/daily_blog_voice_examples_v4.md"
	resource_path.write_text("Future contract resource edit.\n", encoding="utf-8")
	third = daily_blog.bundles.generator_revision(
		str(tmp_path), contract=contract, snapshot=first_snapshot
	)
	identity = daily_blog.bundles.generator_contract_identity(
		str(tmp_path), None, contract, first_snapshot
	)
	for copied in (dataclasses.replace(identity), copy.copy(identity), copy.deepcopy(identity)):
		with pytest.raises(RuntimeError, match="trusted factory"):
			daily_blog.bundles._validate_generator_identity(copied)
	with pytest.raises(RuntimeError, match="trusted factory|example bytes|integrity binding"):
		daily_blog.bundles.generator_revision(
			str(tmp_path),
			contract=contract,
			snapshot=dataclasses.replace(first_snapshot, example_bytes=b"altered"),
		)

	assert first != second and first != third


#============================================
def test_reusable_v4_bundle_rejects_a_raw_revision_before_path_access() -> None:
	"""A raw SHA-256 string cannot spoof an opaque v4 generator identity."""
	with pytest.raises(RuntimeError, match="factory-issued generator identity"):
		daily_blog.bundles.load_reusable_bundle(
			{},
			"/nonexistent/vosslab-test/bundles",
			None,
			None,
			{},
			"f" * 64,
			contract=daily_blog.contracts.V4_ONE_EXAMPLE_CONTRACT,
		)
	with pytest.raises(RuntimeError, match="factory-issued generator identity"):
		daily_blog.bundles.load_reusable_bundle(
			{},
			"/nonexistent/vosslab-test/bundles",
			None,
			None,
			{},
			"f" * 64,
			contract=daily_blog.contracts.V4_INSTRUCTION_ONLY_CONTRACT,
		)


#============================================
def make_v4_bundle(
	tmp_path: pathlib.Path,
	contract: daily_blog.contracts.EditorialContract,
	run_id: str,
) -> tuple[
	daily_blog.bundles.GeneratorContractIdentity,
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
	candidate = daily_blog.editorial.CandidateResult(
		"author",
		projection.projection_id,
		post,
		daily_blog.io_utils.sha256_text(post),
		True,
		(),
	)
	decision = daily_blog.editorial.EditorialDecision(
		winner="A",
		reason="Candidate A is approved for final publication.",
		evidence_quality="medium",
		confidence=0.8,
		projection_id=projection.projection_id,
		post=post,
		anonymous_mapping={"A": 0},
	)
	snapshot = daily_blog.editorial.load_prompt_contract_snapshot(contract)
	repository_root = str(pathlib.Path(__file__).resolve().parents[1])
	identity = daily_blog.bundles.generator_contract_identity(
		repository_root,
		None,
		contract,
		snapshot,
	)
	writer = daily_blog.bundles.BundleWriter(
		str(tmp_path),
		"vosslab",
		identity,
		contract,
		snapshot,
	)
	bundle_path, bundle = writer.write(
		run_id,
		packet,
		projection,
		{},
		[candidate],
		decision,
		bundle_roster(packet),
	)
	record = {"bundle_path": bundle_path, "bundle": bundle}
	date_root = str(tmp_path / "vosslab" / "daily_blog" / packet.report_date)
	return identity, snapshot, packet, projection, record, date_root


#============================================
@pytest.mark.parametrize(
	"contract",
	(
		daily_blog.contracts.V4_INSTRUCTION_ONLY_CONTRACT,
		daily_blog.contracts.V4_ONE_EXAMPLE_CONTRACT,
		daily_blog.contracts.V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT,
	),
)
def test_v4_factory_identity_writes_and_reuses_exact_contract(
	tmp_path: pathlib.Path,
	contract: daily_blog.contracts.EditorialContract,
) -> None:
	"""Each v4 arm accepts only its exact factory identity and snapshot on reuse."""
	identity, snapshot, packet, projection, record, date_root = make_v4_bundle(
		tmp_path,
		contract,
		"exact-v4",
	)
	bundle_path, bundle = daily_blog.bundles.load_reusable_bundle(
		record,
		date_root,
		packet,
		projection,
		{},
		identity,
		contract,
		snapshot,
		bundle_roster(packet),
	)

	assert bundle_path == record["bundle_path"]
	assert bundle["editorial_prompt_contract"] == daily_blog.editorial.prompt_contract_identity(
		snapshot=snapshot
	)


#============================================
def test_v4_bundle_sha256_rejects_copies_omissions_and_cross_arm_inputs(
	tmp_path: pathlib.Path,
) -> None:
	"""Opaque v4 identity objects cannot be copied, omitted, or mixed across arms."""
	contract = daily_blog.contracts.V4_ONE_EXAMPLE_CONTRACT
	identity, snapshot, packet, projection, record, date_root = make_v4_bundle(
		tmp_path,
		contract,
		"identity-attacks",
	)
	other_contract = daily_blog.contracts.V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT
	other_snapshot = daily_blog.editorial.load_prompt_contract_snapshot(other_contract)
	other_identity = daily_blog.bundles.generator_contract_identity(
		str(pathlib.Path(__file__).resolve().parents[1]),
		None,
		other_contract,
		other_snapshot,
	)
	for copied in (dataclasses.replace(identity), copy.copy(identity), copy.deepcopy(identity)):
		with pytest.raises(RuntimeError, match="trusted factory"):
			daily_blog.bundles.BundleWriter(
				str(tmp_path), "vosslab", copied, contract, snapshot
			)
	with pytest.raises(RuntimeError, match="validated prompt snapshot"):
		daily_blog.bundles.BundleWriter(str(tmp_path), "vosslab", identity, contract)
	with pytest.raises(RuntimeError, match="prompt snapshot|generator identity"):
		daily_blog.bundles.BundleWriter(
			str(tmp_path), "vosslab", identity, contract, other_snapshot
		)
	with pytest.raises(RuntimeError, match="factory-issued generator identity"):
		daily_blog.bundles.BundleWriter(
			str(tmp_path), "vosslab", identity.revision, contract, snapshot
		)
	with pytest.raises(RuntimeError, match="prompt snapshot|generator identity"):
		daily_blog.bundles.load_reusable_bundle(
			record,
			date_root,
			packet,
			projection,
			{},
		other_identity,
		contract,
		snapshot,
		bundle_roster(packet),
		)
	with pytest.raises(RuntimeError, match="validated prompt snapshot"):
		daily_blog.bundles.load_reusable_bundle(
			record, date_root, packet, projection, {}, identity, contract, repository_roster=bundle_roster(packet)
		)
	with pytest.raises(RuntimeError, match="factory-issued generator identity"):
		daily_blog.bundles.load_reusable_bundle(
			record,
			date_root,
			packet,
			projection,
			{},
			identity.revision,
			contract,
			snapshot,
		)
	for copied in (dataclasses.replace(snapshot), copy.copy(snapshot), copy.deepcopy(snapshot)):
		with pytest.raises(RuntimeError, match="snapshot"):
			daily_blog.bundles.load_reusable_bundle(
				record, date_root, packet, projection, {}, identity, contract, copied
			)


#============================================
@pytest.mark.parametrize(
	"change",
	(
		lambda prompt_contract: prompt_contract.update({"contract_name": "v4-tampered"}),
		lambda prompt_contract: prompt_contract["examples"].update({"name": "v4-three-examples-corpus-v2"}),
		lambda prompt_contract: prompt_contract["examples"].update({"sha256": "0" * 64}),
	),
)
def test_v4_reuse_rejects_tampered_persisted_prompt_contract(
	tmp_path: pathlib.Path,
	change: object,
) -> None:
	"""Reuse compares the persisted v4 contract, selection, and example digest exactly."""
	contract = daily_blog.contracts.V4_ONE_EXAMPLE_CONTRACT
	identity, snapshot, packet, projection, record, date_root = make_v4_bundle(
		tmp_path,
		contract,
		"persisted-attacks",
	)
	tampered = copy.deepcopy(record["bundle"])
	prompt_contract = tampered["editorial_prompt_contract"]
	change(prompt_contract)
	tampered["bundle_sha256"] = daily_blog.bundles.bundle_sha256(tampered)
	bundle_path = pathlib.Path(record["bundle_path"])
	(bundle_path / "bundle.json").write_text(json.dumps(tampered), encoding="utf-8")
	record["bundle"] = tampered

	with pytest.raises(RuntimeError, match="prompt contract"):
		daily_blog.bundles.load_reusable_bundle(
			record, date_root, packet, projection, {}, identity, contract, snapshot, bundle_roster(packet)
		)


#============================================
def test_v3_raw_revision_remains_an_explicit_compatibility_branch(
	tmp_path: pathlib.Path,
) -> None:
	"""The raw SHA-256 path remains available only to the isolated v3 contract."""
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/project", "a" * 40, "", "", "located work", "git show"
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item]
	)
	projection = make_projection(packet)
	post = "v3 selected post\n"
	candidate = daily_blog.editorial.CandidateResult(
		"author", projection.projection_id, post, daily_blog.io_utils.sha256_text(post), True, ()
	)
	decision = daily_blog.editorial.EditorialDecision(
		"A", "Candidate A is approved.", "medium", 0.8, projection.projection_id, post, {"A": 0}
	)
	writer = daily_blog.bundles.BundleWriter(str(tmp_path), "vosslab", "f" * 64)
	bundle_path, bundle = writer.write(
		"v3-raw", packet, projection, {}, [candidate], decision, bundle_roster(packet)
	)
	record = {"bundle_path": bundle_path, "bundle": bundle}
	date_root = str(tmp_path / "vosslab" / "daily_blog" / packet.report_date)
	reused_path, _reused = daily_blog.bundles.load_reusable_bundle(
		record, date_root, packet, projection, {}, "f" * 64, repository_roster=bundle_roster(packet)
	)

	assert reused_path == bundle_path


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
	post = "v3 selected post\n"
	candidate = daily_blog.editorial.CandidateResult(
		"author", projection.projection_id, post, daily_blog.io_utils.sha256_text(post), True, ()
	)
	decision = daily_blog.editorial.EditorialDecision(
		"A", "Candidate A is approved.", "medium", 0.8, projection.projection_id, post, {"A": 0}
	)
	writer = daily_blog.bundles.BundleWriter(str(tmp_path), "vosslab", "f" * 64)
	bundle_path, bundle = writer.write(
		"roster-scope", packet, projection, {}, [candidate], decision, bundle_roster(packet)
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
		daily_blog.bundles.load_reusable_bundle(
			{"bundle_path": bundle_path, "bundle": bundle},
			str(tmp_path / "vosslab" / "daily_blog" / packet.report_date),
			packet,
			projection,
			{},
			"f" * 64,
			repository_roster=changed_roster,
		)


#============================================
@pytest.mark.parametrize("retired_version", ("v1", "v2"))
def test_reuse_rejects_a_retired_candidate_validation_artifact(
	tmp_path: pathlib.Path,
	retired_version: str,
) -> None:
	"""A persisted policy artifact cannot silently select a retired policy contract."""
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/project", "a" * 40, "", "", "located work", "git show"
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item]
	)
	projection = make_projection(packet)
	post = "v3 selected post\n"
	candidate = daily_blog.editorial.CandidateResult(
		"author", projection.projection_id, post, daily_blog.io_utils.sha256_text(post), True, ()
	)
	decision = daily_blog.editorial.EditorialDecision(
		"A", "Candidate A is approved.", "medium", 0.8, projection.projection_id, post, {"A": 0}
	)
	writer = daily_blog.bundles.BundleWriter(str(tmp_path), "vosslab", "f" * 64)
	bundle_path, bundle = writer.write(
		"v3-retired-policy", packet, projection, {}, [candidate], decision, bundle_roster(packet)
	)
	tampered = copy.deepcopy(bundle)
	tampered["contracts"]["candidate_validation"]["version"] = retired_version
	tampered["bundle_sha256"] = daily_blog.bundles.bundle_sha256(tampered)
	(pathlib.Path(bundle_path) / "bundle.json").write_text(json.dumps(tampered), encoding="utf-8")
	record = {"bundle_path": bundle_path, "bundle": tampered}
	date_root = str(tmp_path / "vosslab" / "daily_blog" / packet.report_date)

	with pytest.raises(RuntimeError, match="generator contracts have changed"):
		daily_blog.bundles.load_reusable_bundle(
			record, date_root, packet, projection, {}, "f" * 64, repository_roster=bundle_roster(packet)
		)

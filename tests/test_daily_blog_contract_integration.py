"""Fast boundary tests for non-publishing editorial contracts."""

# Standard Library
import dataclasses
import json
import pathlib
import types

# PIP3 modules
import pytest

# local repo modules
import daily_blog.config
import daily_blog.activation
import daily_blog.contracts
import daily_blog.experiment_capture_artifacts
import daily_blog.mirrors
import daily_blog.orchestrator
import daily_blog.repository_contracts


#============================================
def make_config(tmp_path: pathlib.Path) -> daily_blog.config.DailyBlogConfig:
	"""Build the smallest isolated configuration that can open a run."""
	return daily_blog.config.DailyBlogConfig(
		settings_path="settings.yaml", output_root=str(tmp_path), output_owner="vosslab",
		report_timezone="America/Chicago", daily_blog_repository=str(tmp_path),
		mirror_cache_root=str(tmp_path / "mirrors"), identity_names=("Neil",), identity_emails=(),
		author_routes=(daily_blog.config.RoleRoute("one", ("fake",)), daily_blog.config.RoleRoute("two", ("fake",))),
		referee_route=daily_blog.config.RoleRoute("judge", ("fake",)), collection_limits={}, projection_limits={},
		prompt_limits={"author_chars": 60000, "referee_chars": 60000}, allow_shadow_model_data_sharing=False,
	)


#============================================
def test_repository_roster_is_written_before_prompt_contract(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A run records its authoritative repository set before editorial work begins."""
	record = daily_blog.repository_contracts.RepositoryRecord.from_dict({
		"repository": "vosslab/example", "repository_url": "https://github.com/vosslab/example",
		"clone_url": "https://github.com/vosslab/example.git", "created_at": "2026-08-23T00:00:00Z", "is_fork": False,
	})
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [record])
	orchestrator = daily_blog.orchestrator.DailyPublicationOrchestrator(make_config(tmp_path), "2026-08-23", repository_loader=lambda *_args: roster)
	written: list[str] = []
	monkeypatch.setattr(orchestrator.store, "write_artifact", lambda name, _value: written.append(name))

	assert orchestrator._repository_phase() == roster
	assert written == ["repository_roster.json", "prompt_contract.json"]


#============================================
@pytest.mark.parametrize(
	"contract",
	(
		daily_blog.contracts.V3_EDITORIAL_CONTRACT,
		daily_blog.contracts.V4_ONE_EXAMPLE_CONTRACT,
	),
)
def test_nonproduction_contract_stops_before_mirror_side_effects(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
	contract: daily_blog.contracts.EditorialContract,
) -> None:
	"""A trusted comparison contract cannot start production collection."""
	def forbidden(*_args: object, **_kwargs: object) -> object:
		raise AssertionError("Non-production contract reached mirror collection.")

	monkeypatch.setattr(daily_blog.mirrors, "MirrorManager", forbidden)
	with pytest.raises(RuntimeError, match="Non-production editorial contracts require"):
		daily_blog.orchestrator.DailyPublicationOrchestrator(
			make_config(tmp_path), "2026-08-23", contract=contract,
		)


#============================================
def test_publication_resolves_through_one_explicit_contract_owner(
	tmp_path: pathlib.Path,
) -> None:
	"""The default publication snapshot belongs to the registry's sole production owner."""
	orchestrator = daily_blog.orchestrator.DailyPublicationOrchestrator(
		make_config(tmp_path), "2026-08-23"
	)

	assert orchestrator.editorial_contract is daily_blog.contracts.PRODUCTION_EDITORIAL_CONTRACT
	assert daily_blog.contracts.is_production_contract(orchestrator.editorial_contract)
	assert all(
		not daily_blog.contracts.is_production_contract(contract)
		for contract in daily_blog.contracts.MAKER_EXPERIMENT_EDITORIAL_CONTRACTS.values()
		if contract is not daily_blog.contracts.PRODUCTION_EDITORIAL_CONTRACT
	)


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
def test_activation_creation_rejects_nonpassing_f4_evidence(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A review artifact that did not accept F4 cannot create a producer receipt."""
	monkeypatch.setattr(
		daily_blog.experiment_review_artifacts,
		"load_review_evidence",
		lambda *_args: types.SimpleNamespace(manifest={"aggregate": {"f4_accepted": False}}),
	)
	with pytest.raises(RuntimeError, match="requires accepted F4 evidence"):
		daily_blog.activation.create_activation_receipt(
			make_config(tmp_path),
			str(tmp_path / "review.json"),
			str(tmp_path / daily_blog.activation.ACTIVATION_FILENAME),
		)


#============================================
def test_activation_creation_rejects_passing_evidence_for_a_different_arm(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A passing review cannot mint production activation for a different selection."""
	monkeypatch.setattr(
		daily_blog.experiment_review_artifacts,
		"load_review_evidence",
		lambda *_args: types.SimpleNamespace(manifest={
			"aggregate": {"f4_accepted": True},
			"attestation": {"attestation_id": "attestation-other"},
		}),
	)
	monkeypatch.setattr(
		daily_blog.experiment_attestation,
		"load_attestation",
		lambda *_args: types.SimpleNamespace(report={
			"acceptance": {"selected_arm": "v4-one-example"},
			"review_contract": {"selected_arm": "v4-one-example"},
		}),
	)
	with pytest.raises(RuntimeError, match="selected a different contract"):
		daily_blog.activation.create_activation_receipt(
			make_config(tmp_path),
			str(tmp_path / "review.json"),
			str(tmp_path / daily_blog.activation.ACTIVATION_FILENAME),
		)


#============================================
def test_maker_activation_rejects_a_resealed_different_f4_identity(
	tmp_path: pathlib.Path,
) -> None:
	"""Receipt integrity cannot authorize a different passing review artifact."""
	receipt = dict(daily_blog.activation.load_maker_activation().receipt)
	f4 = dict(receipt["f4_evidence"])
	f4["review_evidence_id"] = "prompt-experiment-review-evidence-" + "0" * 64
	receipt["f4_evidence"] = f4
	receipt["activation_id"] = daily_blog.activation._activation_id(receipt)
	(tmp_path / daily_blog.activation.ACTIVATION_FILENAME).write_text(
		json.dumps(receipt), encoding="utf-8"
	)
	with pytest.raises(RuntimeError, match="F4 evidence"):
		daily_blog.activation.load_maker_activation(str(tmp_path))


#============================================
def test_maker_experiment_membership_ignores_production_and_trusted_registry_changes(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A broad same-name registry rebind cannot alter the reviewed experiment."""
	contracts = daily_blog.contracts
	replacement = dataclasses.replace(
		contracts.V4_ONE_EXAMPLE_CONTRACT,
		author_template="daily_blog_author_v3.txt",
	)
	monkeypatch.setattr(
		contracts,
		"PRODUCTION_EDITORIAL_CONTRACT",
		contracts.V4_ONE_EXAMPLE_CONTRACT,
	)
	monkeypatch.setattr(
		contracts,
		"EDITORIAL_CONTRACTS",
		types.MappingProxyType({
			**contracts.EDITORIAL_CONTRACTS,
			replacement.name: replacement,
		}),
	)

	assert contracts.active_contract() is contracts.V4_ONE_EXAMPLE_CONTRACT
	assert contracts.named_contract(replacement.name) is replacement
	assert (
		contracts.resolve_maker_experiment_contract(replacement.name)
		is contracts.V4_ONE_EXAMPLE_CONTRACT
	)


#============================================
def test_maker_experiment_contract_resolver_rejects_unreviewed_arm() -> None:
	"""Experiment selection fails closed instead of falling back to broad registration."""
	with pytest.raises(RuntimeError, match="Maker experiment contract name is unsupported"):
		daily_blog.contracts.resolve_maker_experiment_contract("v5-unreviewed")

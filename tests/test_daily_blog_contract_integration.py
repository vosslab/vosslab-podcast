"""Fast boundary tests for non-publishing editorial contracts."""

# Standard Library
import dataclasses
import pathlib
import types

# PIP3 modules
import pytest

# local repo modules
import daily_blog.config
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
def test_nonproduction_contract_stops_before_mirror_side_effects(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A trusted comparison contract cannot start production collection."""
	def forbidden(*_args: object, **_kwargs: object) -> object:
		raise AssertionError("Non-production contract reached mirror collection.")

	monkeypatch.setattr(daily_blog.mirrors, "MirrorManager", forbidden)
	with pytest.raises(RuntimeError, match="Non-production editorial contracts require"):
		daily_blog.orchestrator.DailyPublicationOrchestrator(
			make_config(tmp_path), "2026-08-23", contract=daily_blog.contracts.V4_ONE_EXAMPLE_CONTRACT,
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
def test_prompt_experiment_uses_the_fixed_maker_control_and_candidate_matrix() -> None:
	"""Capture validation consumes the exact reviewed maker arm and pair order."""
	contracts = daily_blog.contracts.MAKER_EXPERIMENT_EDITORIAL_CONTRACTS
	assert tuple(contracts.items()) == (
		("v3", daily_blog.contracts.V3_EDITORIAL_CONTRACT),
		("v4-instruction-only", daily_blog.contracts.V4_INSTRUCTION_ONLY_CONTRACT),
		("v4-one-example", daily_blog.contracts.V4_ONE_EXAMPLE_CONTRACT),
		("v4-three-examples-corpus-v2", daily_blog.contracts.V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT),
	)
	assert daily_blog.contracts.PROMPT_EXPERIMENT_ARMS == (
		"v3",
		"v4-instruction-only",
		"v4-one-example",
		"v4-three-examples-corpus-v2",
	)
	assert daily_blog.contracts.PROMPT_EXPERIMENT_COMPARISON_PAIRS == (
		"v3:v4-instruction-only",
		"v3:v4-one-example",
		"v3:v4-three-examples-corpus-v2",
		"v4-instruction-only:v4-one-example",
		"v4-instruction-only:v4-three-examples-corpus-v2",
		"v4-one-example:v4-three-examples-corpus-v2",
	)
	assert (
		daily_blog.experiment_capture_artifacts.DEFAULT_ARMS
		is daily_blog.contracts.PROMPT_EXPERIMENT_ARMS
	)
	assert (
		daily_blog.experiment_capture_artifacts.COMPARISON_PAIRS
		is daily_blog.contracts.PROMPT_EXPERIMENT_COMPARISON_PAIRS
	)


#============================================
def test_maker_experiment_membership_ignores_production_and_trusted_registry_changes(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A broad same-name registry rebind cannot alter the reviewed experiment."""
	contracts = daily_blog.contracts
	expected_arms = contracts.PROMPT_EXPERIMENT_ARMS
	expected_pairs = contracts.PROMPT_EXPERIMENT_COMPARISON_PAIRS
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
	assert contracts.PROMPT_EXPERIMENT_ARMS is expected_arms
	assert contracts.PROMPT_EXPERIMENT_COMPARISON_PAIRS is expected_pairs


#============================================
def test_maker_experiment_contract_resolver_rejects_unreviewed_arm() -> None:
	"""Experiment selection fails closed instead of falling back to broad registration."""
	with pytest.raises(RuntimeError, match="Maker experiment contract name is unsupported"):
		daily_blog.contracts.resolve_maker_experiment_contract("v5-unreviewed")

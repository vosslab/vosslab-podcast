"""Fast boundary tests for non-publishing editorial contracts."""

# Standard Library
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.config
import daily_blog.contracts
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
def test_experimental_contract_stops_before_mirror_side_effects(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""An experimental contract cannot start production collection."""
	def forbidden(*_args: object, **_kwargs: object) -> object:
		raise AssertionError("Experimental contract reached mirror collection.")

	monkeypatch.setattr(daily_blog.mirrors, "MirrorManager", forbidden)
	with pytest.raises(RuntimeError, match="Experimental editorial contracts require"):
		daily_blog.orchestrator.DailyPublicationOrchestrator(
			make_config(tmp_path), "2026-08-23", contract=daily_blog.contracts.V4_ONE_EXAMPLE_CONTRACT,
		)

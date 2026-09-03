"""Editorial isolation, prompt, validation, and final referee behavior tests."""

# Standard Library
import dataclasses
import pathlib
import subprocess

# PIP3 modules
import pytest

# local repo modules
import daily_blog.config
import daily_blog.editorial_stage_config
import daily_blog.schema
import daily_blog.repository_contracts
import daily_blog.routes
import daily_blog.editorial
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.editorial_contracts
import daily_blog.projection
import daily_blog.io_utils


#============================================
def make_packet(with_activity: bool = False) -> daily_blog.schema.EvidencePacket:
	"""Return one complete inline primary-evidence packet."""
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog",
		"vosslab/project",
		"a" * 40,
		"docs/CHANGELOG.md",
		"b" * 40,
		"## 2026-08-23\n\n- Added exact bundle validation.\n",
		"git show",
	)
	activity = []
	if with_activity:
		commit = daily_blog.schema.CommitActivity(
			sha="a" * 40,
			parents=("c" * 40,),
			author_name="Author",
			author_email="author@example.com",
			author_timestamp="2026-08-23T12:00:00-05:00",
			committer_timestamp="2026-08-23T12:00:00-05:00",
			message="Add exact bundle validation",
		)
		activity.append(
			daily_blog.schema.RepositoryActivity(
				repository="vosslab/project",
				repository_url="https://github.com/vosslab/project",
				cache_path="/nonexistent/vosslab-test/project",
				default_revision="a" * 40,
				commits=(commit,),
				revision_ranges=(
					daily_blog.schema.RevisionRange("c" * 40, "a" * 40),
				),
				snapshot_commits=("a" * 40,),
				is_fork=False,
				lifecycle_events=(daily_blog.repository_contracts.RepositoryLifecycleEvent(
					"repository_created", "2020-01-01T00:00:00Z", False, "github_owner_roster",
				),),
			)
		)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23",
		"America/Chicago",
		True,
		{},
		[],
		activity,
		[item],
	)
	return packet


#============================================
def make_projection(
	packet: daily_blog.schema.EvidencePacket,
) -> daily_blog.schema.EditorialProjection:
	"""Return one deterministic editorial projection for inline evidence."""
	limits = {
		"context_chars": 12000,
		"excerpt_chars": 2000,
		"commit_subject_chars": 160,
	}
	return daily_blog.projection.build_projection(packet, limits)


#============================================
def test_route_configuration_rejects_hidden_instruction_sources(tmp_path: pathlib.Path) -> None:
	"""Execution routes cannot inject profile skills beside versioned prompts."""
	settings_path = tmp_path / "settings.yaml"
	settings_path.write_text(
		"github:\n"
		"  username: vosslab\n"
		"  identity_login: vosslab\n"
		"daily_blog:\n"
		"  routes:\n"
		"    authors:\n"
		"      - name: one\n"
		"        command: [hermes, chat, --provider, openai-codex, --skills, daily-github-blogger, --query-file, -, --ignore-rules, --quiet]\n"
		"      - name: two\n"
		"        command: [hermes, chat, --provider, openai-codex, --query-file, -, --ignore-rules, --quiet]\n"
		"    referee:\n"
		"      name: judge\n"
		"      command: [hermes, chat, --provider, openai-codex, --query-file, -, --ignore-rules, --quiet]\n",
		encoding="utf-8",
	)

	with pytest.raises(RuntimeError, match="sealed Hermes editorial route"):
		daily_blog.config.load_config(str(settings_path))


#============================================
def test_hermes_route_requires_profile_instruction_isolation(tmp_path: pathlib.Path) -> None:
	"""A Hermes executor must disable profile rules even when its query uses stdin."""
	settings_path = tmp_path / "settings.yaml"
	settings_path.write_text(
		"github:\n"
		"  username: vosslab\n"
		"  identity_login: vosslab\n"
		"daily_blog:\n"
		"  routes:\n"
		"    authors:\n"
		"      - name: one\n"
		"        command: [hermes, chat, --provider, openai-codex, --query-file, -, --quiet]\n"
		"      - name: two\n"
		"        command: [hermes, chat, --provider, openai-codex, --query-file, -, --ignore-rules, --quiet]\n"
		"    referee:\n"
		"      name: judge\n"
		"      command: [hermes, chat, --provider, openai-codex, --query-file, -, --ignore-rules, --quiet]\n",
		encoding="utf-8",
	)

	with pytest.raises(RuntimeError, match="sealed Hermes editorial route"):
		daily_blog.config.load_config(str(settings_path))


def test_command_route_sends_prompt_through_stdin(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: pathlib.Path,
) -> None:
	"""Hermes-compatible routes receive full prompts through subprocess stdin."""
	captured = {}

	def fake_run(command: tuple[str, ...], **kwargs: object) -> object:
		captured["command"] = command
		captured["input"] = kwargs["input"]
		captured["shell"] = kwargs["shell"]
		return dataclasses.make_dataclass(
			"Result", [("returncode", int), ("stdout", str), ("stderr", str)]
		)(0, "response", "")

	monkeypatch.setattr(daily_blog.routes.subprocess, "run", fake_run)
	route = daily_blog.editorial_stage_config.RoleRoute(
		"author", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE
	)

	response = daily_blog.routes.CommandRouteRunner().run(
		route,
		"full prompt",
		str(tmp_path),
	)

	assert captured["input"] == "full prompt"
	assert response == "response"
	assert captured["shell"] is False


#============================================
def test_command_route_rejects_unsealed_command_before_execution(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: pathlib.Path,
) -> None:
	"""The process sink accepts only the sealed Hermes route."""
	called = False

	def fake_run(*_args: object, **_kwargs: object) -> object:
		nonlocal called
		called = True
		raise AssertionError("Invalid route must not execute.")

	monkeypatch.setattr(daily_blog.routes.subprocess, "run", fake_run)
	route = daily_blog.editorial_stage_config.RoleRoute("author", ("not-hermes",))

	with pytest.raises(RuntimeError, match="must invoke hermes chat"):
		daily_blog.routes.CommandRouteRunner().run(route, "prompt", str(tmp_path))

	assert not called


#============================================
def test_command_route_redacts_failed_process_output(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: pathlib.Path,
) -> None:
	"""External stdout and stderr never enter the route failure surfaced to callers."""
	secret = "account-label api-key private-prompt"

	def fake_run(_command: tuple[str, ...], **_kwargs: object) -> object:
		return dataclasses.make_dataclass(
			"Result", [("returncode", int), ("stdout", str), ("stderr", str)]
		)(2, secret, secret)

	monkeypatch.setattr(daily_blog.routes.subprocess, "run", fake_run)
	route = daily_blog.editorial_stage_config.RoleRoute(
		"secret-route-name", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE
	)

	with pytest.raises(RuntimeError) as caught:
		daily_blog.routes.CommandRouteRunner().run(route, secret, str(tmp_path))

	assert secret not in str(caught.value)
	assert route.name not in str(caught.value)


@pytest.mark.parametrize(
	("route_error", "expected_type"),
	(
		(
			subprocess.TimeoutExpired(("hermes", "chat", "private-prompt"), 1200),
			TimeoutError,
		),
		(
			OSError("credential path /private/account"),
			OSError,
		),
	),
)
def test_command_route_redacts_process_exceptions(
	monkeypatch: pytest.MonkeyPatch,
	route_error: BaseException,
	expected_type: type[BaseException],
	tmp_path: pathlib.Path,
) -> None:
	"""Process-start and timeout failures expose stable operational categories only."""
	def fake_run(_command: tuple[str, ...], **_kwargs: object) -> object:
		raise route_error

	monkeypatch.setattr(daily_blog.routes.subprocess, "run", fake_run)
	route = daily_blog.editorial_stage_config.RoleRoute(
		"author", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE
	)

	with pytest.raises(expected_type) as caught:
		daily_blog.routes.CommandRouteRunner().run(
			route,
			"private-prompt",
			str(tmp_path),
		)

	assert str(route_error) not in str(caught.value)
	assert caught.value.__cause__ is None


#============================================
def test_contract_registry_rejects_freeform_contracts_and_selections() -> None:
	"""Only registered values reach the prompt boundary."""
	with pytest.raises(RuntimeError, match="trusted registry"):
		daily_blog.prompt_registry.editorial_contracts.resolve_contract(
		dataclasses.replace(daily_blog.prompt_registry.editorial_contracts.active_contract(), name="unregistered")
	)
	with pytest.raises(RuntimeError, match="trusted registry"):
		daily_blog.prompt_registry.editorial_contracts.resolve_selection(
		daily_blog.prompt_registry.editorial_contracts.V4_THREE_EXAMPLES_CORPUS_V2_SELECTION,
		daily_blog.prompt_registry.definitions.ExampleSelection(
			"unregistered",
			daily_blog.prompt_registry.editorial_contracts.V4_THREE_EXAMPLES_CORPUS_V2,
			"v4-voice",
			("aug-23",),
		),
	)
	with pytest.raises(RuntimeError, match="bare filename"):
		daily_blog.prompt_registry.definitions.ExampleResource("unsafe", "../outside.md", ("aug-22",))
	with pytest.raises(RuntimeError, match="not trusted"):
		daily_blog.editorial.validate_snapshot(
			daily_blog.editorial.PromptContractSnapshot(
				daily_blog.prompt_registry.editorial_contracts.active_contract(),
				None,
				(),
				(),
				b"",
				b"",
				"",
			)
		)


#============================================
def test_v4_snapshot_rejects_unissued_or_cross_set_prompt_views() -> None:
	"""The cache-owning V4 snapshot accepts only its issued registry view."""
	for prompt_set in (
		object.__new__(daily_blog.prompt_registry.loader.LoadedPromptSet),
		daily_blog.prompt_registry.loader.load_prompt_set(
			daily_blog.prompt_registry.definitions.REPOSITORY_OUTLINE_PROMPT_SET,
		),
	):
		with pytest.raises(RuntimeError, match="issued|does not match"):
			daily_blog.editorial.load_prompt_contract_snapshot(prompt_set=prompt_set)

"""Focused offline tests for the private deterministic Hermes fixture boundary."""

# Standard Library
import io
import os
import pathlib
import subprocess
import sys

# Third Party
import pytest

# local repo modules
import daily_blog.config
import daily_blog.fixture_hermes
import daily_blog.routes


#============================================
def test_fixture_hermes_matches_complete_stdin_by_sha256(tmp_path: pathlib.Path) -> None:
	"""A complete registered prompt receives exactly its registered response."""
	prompt = "Tell the interesting story in this implementation."
	installation = daily_blog.fixture_hermes.install_fixture_hermes(
		str(tmp_path), {prompt: "I found the seam worth keeping."}
	)
	code, stdout, stderr = daily_blog.fixture_hermes.fixture_response(
		daily_blog.config.HERMES_EDITORIAL_ROUTE,
		prompt.encode("utf-8"),
		installation.mapping_path,
	)

	assert (code, stdout, stderr) == (0, b"I found the seam worth keeping.", "")



#============================================
def test_installed_fixture_hermes_restores_executable_argv_zero(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The disposable executable accepts the unchanged route command after argv parsing."""
	prompt = "A complete prompt from the author route."
	installation = daily_blog.fixture_hermes.install_fixture_hermes(
		str(tmp_path), {prompt: "A complete response."}
	)
	stdin = io.TextIOWrapper(io.BytesIO(prompt.encode("utf-8")), encoding="utf-8")
	stdout_bytes = io.BytesIO()
	stdout = io.TextIOWrapper(stdout_bytes, encoding="utf-8")
	stderr = io.StringIO()
	monkeypatch.setattr(sys, "stdin", stdin)
	monkeypatch.setattr(sys, "stdout", stdout)
	monkeypatch.setattr(sys, "stderr", stderr)
	monkeypatch.setattr(
		sys,
		"argv",
		[installation.executable, *daily_blog.config.HERMES_EDITORIAL_ROUTE[1:]],
	)

	code = daily_blog.fixture_hermes.run_installed_shim(installation.mapping_path)
	stdout.flush()

	assert code == 0 and stderr.getvalue() == ""
	assert stdout_bytes.getvalue() == b"A complete response."


#============================================
def test_fixture_installation_attests_stable_non_secret_runner_provenance(
	tmp_path: pathlib.Path,
) -> None:
	"""Installation validation derives one stable route identity without response contents."""
	installation = daily_blog.fixture_hermes.install_fixture_hermes(
		str(tmp_path), {"prompt": "private response"}
	)
	first = daily_blog.fixture_hermes.validate_fixture_installation(installation)
	second = daily_blog.fixture_hermes.validate_fixture_installation(installation)

	assert first == second and first.external_route_used is False
	assert "private response" not in repr(first)


#============================================
def test_fixture_hermes_rejects_unregistered_inputs_without_prompt_disclosure(
	tmp_path: pathlib.Path,
) -> None:
	"""Wrong argv and an unknown complete prompt fail with stable redacted categories."""
	prompt = "private prompt that must not be disclosed"
	installation = daily_blog.fixture_hermes.install_fixture_hermes(
		str(tmp_path), {prompt: "response"}
	)
	command_result = daily_blog.fixture_hermes.fixture_response(
		("hermes", "chat", "--quiet"), prompt.encode("utf-8"), installation.mapping_path
	)
	unknown_result = daily_blog.fixture_hermes.fixture_response(
		daily_blog.config.HERMES_EDITORIAL_ROUTE,
		b"a different private prompt",
		installation.mapping_path,
	)

	assert command_result == (2, b"", "fixture-hermes: command rejected\n")
	assert unknown_result == (2, b"", "fixture-hermes: unknown prompt\n")


#============================================
def test_fixture_hermes_keeps_private_files_and_path_in_one_disposable_directory(
	tmp_path: pathlib.Path,
) -> None:
	"""The installed command and hidden mapping are mode-private direct children."""
	installation = daily_blog.fixture_hermes.install_fixture_hermes(
		str(tmp_path), {"prompt": "response"}
	)
	root = pathlib.Path(installation.root)
	mapping = pathlib.Path(installation.mapping_path)

	assert root.parent == tmp_path and mapping.parent == root and os.path.isfile(installation.executable)
	assert (
		os.stat(root).st_mode & 0o077 == 0
		and os.stat(mapping).st_mode & 0o077 == 0
		and os.stat(installation.executable).st_mode & 0o077 == 0
	)


#============================================
def test_command_runner_scopes_verified_fixture_path_to_its_child_process(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""One fixture runner supplies PATH to its child without changing global process state."""
	captured = {}

	def fake_run(_command: tuple[str, ...], **kwargs: object) -> object:
		captured["environment"] = kwargs["env"]
		return subprocess.CompletedProcess(_command, 0, "response", "")

	monkeypatch.setattr(daily_blog.routes.subprocess, "run", fake_run)
	original_path = os.environ.get("PATH")
	installation = daily_blog.fixture_hermes.install_fixture_hermes(
		str(tmp_path), {"complete prompt": "response"}
	)
	runner = installation.create_route_runner()
	runner.run(
		daily_blog.config.RoleRoute("author", daily_blog.config.HERMES_EDITORIAL_ROUTE),
		"complete prompt",
		"/private/repository",
	)

	assert captured["environment"]["PATH"] == installation.path
	assert os.environ.get("PATH") == original_path


#============================================
def test_command_runner_rejects_an_unprovenanced_path_override() -> None:
	"""An arbitrary path cannot claim no-egress fixture route provenance."""
	with pytest.raises(RuntimeError, match="Editorial route child PATH"):
		daily_blog.routes.CommandRouteRunner(path_override="/private/fixture-hermes")


#============================================
def test_fixture_runner_rechecks_an_executable_before_starting_a_child(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A changed executable after runner creation blocks the child process before launch."""
	installation = daily_blog.fixture_hermes.install_fixture_hermes(
		str(tmp_path), {"prompt": "response"}
	)
	runner = installation.create_route_runner()
	pathlib.Path(installation.executable).write_text("changed", encoding="utf-8")
	called = False

	def fake_run(_command: tuple[str, ...], **_kwargs: object) -> object:
		nonlocal called
		called = True
		return subprocess.CompletedProcess(_command, 0, "response", "")

	monkeypatch.setattr(daily_blog.routes.subprocess, "run", fake_run)

	with pytest.raises(RuntimeError, match="Fixture Hermes installation identity is invalid."):
		runner.run(
			daily_blog.config.RoleRoute("author", daily_blog.config.HERMES_EDITORIAL_ROUTE),
			"prompt",
			str(tmp_path),
		)

	assert called is False


#============================================
def test_fixture_runner_rejects_private_response_map_tampering(
	tmp_path: pathlib.Path,
) -> None:
	"""A changed private response map cannot create a fixture-attested runner."""
	installation = daily_blog.fixture_hermes.install_fixture_hermes(
		str(tmp_path), {"prompt": "response"}
	)
	pathlib.Path(installation.mapping_path).write_text("changed", encoding="utf-8")

	with pytest.raises(RuntimeError, match="Fixture Hermes installation identity is invalid."):
		installation.create_route_runner()

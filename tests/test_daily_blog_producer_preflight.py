"""Fast offline coverage for the daily-blog producer credential preflight."""

# Standard Library
import importlib
import importlib.util
import pathlib
from datetime import datetime
from datetime import timezone

# PIP3 modules
import pytest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "automation" / "preflight_daily_blog_producer.py"
SPEC = importlib.util.spec_from_file_location("daily_blog_producer_preflight", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
producer_preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(producer_preflight)


#============================================
def test_preflight_config_ignores_unrelated_editorial_route_validation(tmp_path: pathlib.Path) -> None:
	"""Credential readiness depends only on the GitHub owner, not prompt-route state."""
	settings_path = tmp_path / "settings.yaml"
	settings_path.write_text(
		"github:\n  username: vosslab\ndaily_blog:\n  routes: invalid-for-editorial-config\n",
		encoding="utf-8",
	)

	config = producer_preflight.load_preflight_config(str(settings_path), str(tmp_path / "out"))

	assert config == producer_preflight.ProducerPreflightConfig(
		output_root=str(tmp_path / "out"),
		output_owner="vosslab",
	)


#============================================
def test_authenticated_quota_metadata_is_redacted_and_uses_runtime_token(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: pathlib.Path,
) -> None:
	"""The preflight exposes quota facts but never the token supplied to its client."""
	config = type("Config", (), {"output_root": str(tmp_path), "output_owner": "vosslab"})()
	seen: dict[str, object] = {}

	class FakeClient:
		"""Offline authenticated-client stand-in."""

		def __init__(self, token: str, *, cache_dir: str) -> None:
			seen["token"] = token
			seen["cache_dir"] = cache_dir

		def get_core_rate_limit_snapshot(self) -> tuple[int, datetime]:
			return 5000, datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)

	monkeypatch.setattr(producer_preflight.podlib.runtime_credentials, "get_github_token", lambda: "token-sentinel")
	monkeypatch.setattr(producer_preflight.podlib.github_client, "GitHubClient", FakeClient)

	metadata = producer_preflight.authenticated_quota_metadata(config)

	assert metadata == {
		"github_token_available": True,
		"github_core_remaining": 5000,
		"github_core_reset_utc": "2026-08-28T12:00:00Z",
	}
	assert seen["token"] == "token-sentinel"
	assert "token-sentinel" not in repr(metadata)
	assert seen["cache_dir"] == str(tmp_path / "vosslab" / "daily_blog_cache" / "github_preflight")


#============================================
def test_preflight_failure_is_generic_and_does_not_echo_token(
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
) -> None:
	"""Credential lookup failures are safe for systemd's captured stderr."""
	monkeypatch.setattr(
		producer_preflight,
		"parse_args",
		lambda _arguments: type("Arguments", (), {"settings_path": "unused.yaml", "output_root": "out"})(),
	)
	monkeypatch.setattr(producer_preflight, "load_preflight_config", lambda _path, _root: object())
	monkeypatch.setattr(
		producer_preflight,
		"authenticated_quota_metadata",
		lambda _config: (_ for _ in ()).throw(RuntimeError("token-sentinel invalid")),
	)

	assert producer_preflight.main([]) == 2

	captured = capsys.readouterr()
	assert captured.out == ""
	assert "authenticated GitHub quota is unavailable" in captured.err
	assert "token-sentinel" not in captured.err


#============================================
def test_preflight_hides_pygithub_exception_details(
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
) -> None:
	"""A provider exception cannot leak response text or a traceback into systemd logs."""
	monkeypatch.setattr(
		producer_preflight,
		"parse_args",
		lambda _arguments: type("Arguments", (), {"settings_path": "unused.yaml", "output_root": "out"})(),
	)
	monkeypatch.setattr(producer_preflight, "load_preflight_config", lambda _path, _root: object())
	github_exception = importlib.import_module("github.GithubException").GithubException
	provider_error = github_exception(401, {"message": "token-sentinel provider response"}, None)
	monkeypatch.setattr(
		producer_preflight,
		"authenticated_quota_metadata",
		lambda _config: (_ for _ in ()).throw(provider_error),
	)

	assert producer_preflight.main([]) == 2

	captured = capsys.readouterr()
	assert captured.out == ""
	assert captured.err == "Daily-blog producer preflight failed; authenticated GitHub quota is unavailable.\n"
	assert "token-sentinel" not in captured.err
	assert "Traceback" not in captured.err


#============================================
def test_preflight_prints_only_fixed_redacted_metadata(
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
) -> None:
	"""Successful systemd output has no channel for the credential value."""
	monkeypatch.setattr(
		producer_preflight,
		"parse_args",
		lambda _arguments: type("Arguments", (), {"settings_path": "unused.yaml", "output_root": "out"})(),
	)
	monkeypatch.setattr(producer_preflight, "load_preflight_config", lambda _path, _root: object())
	monkeypatch.setattr(
		producer_preflight,
		"authenticated_quota_metadata",
		lambda _config: {
			"github_token_available": True,
			"github_core_remaining": 5000,
			"github_core_reset_utc": "2026-08-28T12:00:00Z",
		},
	)

	assert producer_preflight.main([]) == 0

	assert capsys.readouterr().out.splitlines() == [
		"github_token_available=True",
		"github_core_remaining=5000",
		"github_core_reset_utc=2026-08-28T12:00:00Z",
	]


#============================================
@pytest.mark.parametrize("raw_remaining", (True, "5000", 5000.0, -1))
def test_preflight_rejects_invalid_quota_metadata(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: pathlib.Path,
	raw_remaining: object,
) -> None:
	"""Malformed remote quota values cannot be mistaken for authenticated access."""
	config = type("Config", (), {"output_root": str(tmp_path), "output_owner": "vosslab"})()

	class FakeClient:
		"""Offline client with malformed quota data."""

		def __init__(self, _token: str, *, cache_dir: str) -> None:
			pass

		def get_core_rate_limit_snapshot(self) -> tuple[object, datetime]:
			return raw_remaining, datetime(2026, 8, 28, tzinfo=timezone.utc)

	monkeypatch.setattr(producer_preflight.podlib.runtime_credentials, "get_github_token", lambda: "test-token")
	monkeypatch.setattr(producer_preflight.podlib.github_client, "GitHubClient", FakeClient)

	with pytest.raises(RuntimeError, match="metadata is invalid"):
		producer_preflight.authenticated_quota_metadata(config)

"""Root daily-blog command contract tests."""

# Standard Library
import argparse
import builtins
import contextlib
import types

# PIP3 modules
import pytest

# local repo modules
import make_blog
import automation.publish_daily_blog
import daily_blog.publication_state


#============================================
@pytest.mark.parametrize(
	("value", "expected"),
	(
		("2026-08-21", "2026-08-21"),
		("2026-21-08", "2026-08-21"),
		("2026-08-09", "2026-08-09"),
	),
)
def test_normalize_report_date_accepts_canonical_and_requested_forms(
	value: str,
	expected: str,
) -> None:
	"""The public date boundary preserves ISO and normalizes the requested day-month form."""
	assert make_blog.normalize_report_date(value) == expected


#============================================
@pytest.mark.parametrize(
	"value",
	(
		"2026-21-99",
		"2026-02-29",
		"2026/08/21",
		"21-08-2026",
		"2026-8-21",
	),
)
def test_normalize_report_date_rejects_invalid_inputs(value: str) -> None:
	"""Malformed and impossible dates stop before configuration or publication work."""
	with pytest.raises(argparse.ArgumentTypeError):
		make_blog.normalize_report_date(value)


#============================================
def test_parse_args_requires_exactly_one_date_selector() -> None:
	"""The CLI prevents missing or conflicting date-selection workflows."""
	with pytest.raises(SystemExit):
		make_blog.parse_args([])
	with pytest.raises(SystemExit):
		make_blog.parse_args(["--yesterday", "--date", "2026-21-08"])


#============================================
def test_parse_args_accepts_yesterday_without_replacement_authorization() -> None:
	"""Yesterday remains the only short date-selection flag for a scheduled run."""
	args = make_blog.parse_args(["-Y"])

	assert args.yesterday is True


#============================================
def test_parse_args_normalizes_an_explicit_date_with_overwrite_authorization() -> None:
	"""The lower-case replacement flag is distinct from the upper-case date selector."""
	args = make_blog.parse_args(["-d", "2026-27-08", "-y"])

	assert args.report_date == "2026-08-27"
	assert args.yes is True


#============================================
def test_parse_args_rejects_date_selector_collisions() -> None:
	"""The command still rejects conflicting date selectors."""
	with pytest.raises(SystemExit):
		make_blog.parse_args(["-Y", "-d", "2026-08-27"])
	with pytest.raises(SystemExit):
		make_blog.parse_args(["-Y", "--yes"])


#============================================
def test_repo_python_boundary_rejects_wrong_interpreter(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The direct command fails closed inside a repository environment using the wrong Python."""
	monkeypatch.setattr(make_blog.sys, "prefix", str(make_blog.REPO_VENV))
	monkeypatch.setattr(make_blog.sys, "version_info", (3, 13, 0))

	with pytest.raises(RuntimeError, match="Python 3.1x"):
		make_blog._restart_with_repo_python()


#============================================
def test_selected_report_date_uses_configured_timezone_for_yesterday(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Yesterday is owned by the configured report timezone, not the host shell timezone."""
	args = argparse.Namespace(yesterday=True, report_date=None)
	def yesterday(timezone_name: str) -> str:
		if timezone_name != "America/Chicago":
			raise AssertionError("configured report timezone was not used")
		return "2026-08-27"

	monkeypatch.setattr(make_blog, "yesterday_for_timezone", yesterday)

	assert make_blog.selected_report_date(args, "America/Chicago") == "2026-08-27"
def test_yesterday_uses_automatic_replacement_without_terminal_input(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The unattended selector owns replacement without needing a terminal callback."""
	config = types.SimpleNamespace(report_timezone="America/Chicago")
	observed: list[dict[str, object]] = []
	monkeypatch.setattr(make_blog.daily_blog.config, "load_config", lambda *_args, **_kwargs: config)
	monkeypatch.setattr(builtins, "input", lambda _prompt: (_ for _ in ()).throw(AssertionError()))
	monkeypatch.setattr(
		make_blog.automation.publish_daily_blog,
		"publish_report_date",
		lambda _config, _date, **kwargs: observed.append(kwargs) or True,
	)

	make_blog.main(["--yesterday"])

	assert observed == [{"replace_existing": True, "confirm_replace": None}]


#============================================
def test_explicit_date_passes_the_narrow_confirmation_callback(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""An explicit date delegates its occupied-date decision to the lock-owning service."""
	config = types.SimpleNamespace(report_timezone="America/Chicago")
	observed: list[dict[str, object]] = []
	confirmation = lambda _prompt: "y"
	monkeypatch.setattr(make_blog.daily_blog.config, "load_config", lambda *_args, **_kwargs: config)
	monkeypatch.setattr(
		make_blog.automation.publish_daily_blog,
		"publish_report_date",
		lambda _config, _date, **kwargs: observed.append(kwargs) or True,
	)

	make_blog.main(["--date", "2026-08-27"], confirmation=confirmation)

	assert observed == [{"replace_existing": False, "confirm_replace": confirmation}]


#============================================
def test_yes_authorizes_an_explicit_date_without_confirmation(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The explicit noninteractive replacement flag reaches the lock-owning service."""
	config = types.SimpleNamespace(report_timezone="America/Chicago")
	observed: list[dict[str, object]] = []
	monkeypatch.setattr(make_blog.daily_blog.config, "load_config", lambda *_args, **_kwargs: config)
	monkeypatch.setattr(
		make_blog.automation.publish_daily_blog,
		"publish_report_date",
		lambda _config, _date, **kwargs: observed.append(kwargs) or True,
	)

	make_blog.main(["--date", "2026-08-27", "--yes"])

	assert observed == [{"replace_existing": True, "confirm_replace": None}]


#============================================
def test_occupied_explicit_date_requires_exact_y_without_running_generation(
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
) -> None:
	"""Default denial preserves the occupied date after inspection under its same lock."""
	config = types.SimpleNamespace(output_root="/out", output_owner="owner")
	generated: list[str] = []
	prompts: list[str] = []
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator,
		"publication_date_lock",
		lambda _config, _date: contextlib.nullcontext(),
	)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.publication_state,
		"inspect_publication",
		lambda _config, _date: daily_blog.publication_state.PublicationInspection("current"),
	)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator,
		"run_daily_publication_locked",
		lambda *_args, **_kwargs: generated.append("ran"),
	)

	result = automation.publish_daily_blog.publish_report_date(
		config, "2026-08-27", replace_existing=False,
		confirm_replace=lambda prompt: prompts.append(prompt) or "Y",
	)

	assert result is False
	assert generated == []
	assert prompts == ["Overwrite 2026-08-27? [N/y]: "]
	assert capsys.readouterr().out == "Publication cancelled: 2026-08-27 remains unchanged.\n"


#============================================
def test_occupied_explicit_date_accepts_only_exact_y(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The exact documented reply permits an occupied date to regenerate."""
	config = types.SimpleNamespace(output_root="/out", output_owner="owner")
	observed: list[bool] = []
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator,
		"publication_date_lock",
		lambda _config, _date: contextlib.nullcontext(),
	)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.publication_state,
		"inspect_publication",
		lambda _config, _date: daily_blog.publication_state.PublicationInspection("current"),
	)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator,
		"run_daily_publication_locked",
		lambda *_args, **kwargs: observed.append(kwargs["force_regeneration"]) or ("/bundle", {}),
	)

	result = automation.publish_daily_blog.publish_report_date(
		config, "2026-08-27", replace_existing=False,
		confirm_replace=lambda prompt: "y" if prompt == "Overwrite 2026-08-27? [N/y]: " else "",
	)

	assert result is True
	assert observed == [True]


#============================================
def test_missing_date_publishes_without_a_confirmation_callback(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A missing date enters generation directly and never asks an overwrite question."""
	config = types.SimpleNamespace(output_root="/out", output_owner="owner")
	observed: list[bool] = []
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator,
		"publication_date_lock",
		lambda _config, _date: contextlib.nullcontext(),
	)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.publication_state,
		"inspect_publication",
		lambda _config, _date: daily_blog.publication_state.PublicationInspection("missing"),
	)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator,
		"run_daily_publication_locked",
		lambda *_args, **kwargs: observed.append(kwargs["force_regeneration"]) or ("/bundle", {}),
	)

	result = automation.publish_daily_blog.publish_report_date(
		config, "2026-08-27", replace_existing=False,
		confirm_replace=lambda _prompt: (_ for _ in ()).throw(AssertionError()),
	)

	assert result is True
	assert observed == [False]

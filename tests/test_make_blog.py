"""Root daily-blog command contract tests."""

# Standard Library
import argparse
import builtins
import types

# PIP3 modules
import pytest

# local repo modules
import make_blog


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
def test_parse_args_keeps_yesterday_and_replacement_authorization_distinct() -> None:
	"""The short flags select a date and authorize replacement without ambiguity."""
	args = make_blog.parse_args(["-Y", "-y"])

	assert args.yesterday is True
	assert args.yes is True


#============================================
def test_parse_args_keeps_explicit_date_and_replacement_authorization_distinct() -> None:
	"""The explicit-date selector and the replacement override retain separate short flags."""
	args = make_blog.parse_args(["-d", "2026-27-08", "-y"])

	assert args.report_date == "2026-08-27"
	assert args.yes is True


#============================================
def test_parse_args_rejects_date_selector_collisions_with_yes() -> None:
	"""Replacement authorization cannot make two date selectors valid together."""
	with pytest.raises(SystemExit):
		make_blog.parse_args(["-Y", "-d", "2026-08-27", "-y"])


#============================================
def test_repo_python_boundary_rejects_wrong_interpreter(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The direct command fails closed inside a repository environment using the wrong Python."""
	monkeypatch.setattr(make_blog.sys, "prefix", str(make_blog.REPO_VENV))
	monkeypatch.setattr(make_blog.sys, "version_info", (3, 13, 0))

	with pytest.raises(RuntimeError, match="Python 3.12"):
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
#============================================
def test_noninteractive_confirmation_preserves_without_reading_input(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A systemd run preserves an existing date without waiting for terminal input."""
	monkeypatch.setattr(make_blog.sys, "stdin", types.SimpleNamespace(isatty=lambda: False))
	monkeypatch.setattr(
		builtins,
		"input",
		lambda _prompt: (_ for _ in ()).throw(AssertionError("input must stay unused")),
	)

	assert make_blog.confirm_replacement("2026-08-27") is False


#============================================
@pytest.mark.parametrize("response", ("Y", " y", "y ", "yes", ""))
def test_confirmation_requires_literal_lowercase_y(
	monkeypatch: pytest.MonkeyPatch,
	response: str,
) -> None:
	"""Only the documented literal terminal response authorizes replacement."""
	monkeypatch.setattr(make_blog.sys, "stdin", types.SimpleNamespace(isatty=lambda: True))
	monkeypatch.setattr(builtins, "input", lambda _prompt: response)

	assert make_blog.confirm_replacement("2026-08-27") is False


#============================================
def test_confirmation_accepts_literal_lowercase_y(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The interactive confirmation accepts the one documented affirmative response."""
	monkeypatch.setattr(make_blog.sys, "stdin", types.SimpleNamespace(isatty=lambda: True))
	monkeypatch.setattr(builtins, "input", lambda _prompt: "y")

	assert make_blog.confirm_replacement("2026-08-27") is True


#============================================
def test_yes_preauthorizes_replacement_without_terminal_input(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The unattended override reaches the date-owned workflow as an affirmative decider."""
	config = types.SimpleNamespace(report_timezone="America/Chicago")
	observed = []
	monkeypatch.setattr(make_blog.daily_blog.config, "load_config", lambda *_args, **_kwargs: config)
	monkeypatch.setattr(
		make_blog.automation.publish_daily_blog,
		"publish_report_date",
		lambda _config, date, replacement_decider: observed.append((date, replacement_decider(date))),
	)

	make_blog.main(["--date", "2026-08-27", "--yes"])

	assert observed == [("2026-08-27", True)]

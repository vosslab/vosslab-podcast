"""Root command rendering tests for diagnosed daily-blog terminal faults."""

# Standard Library
import json
import types

# PIP3 modules
import pytest

# local repo modules
import daily_blog.recovery
import make_blog


#============================================
def _fault_error(category: daily_blog.recovery.TerminalFaultCategory) -> daily_blog.recovery.PipelineFaultError:
	"""Build one validated terminal fault without unbounded diagnostics."""
	successful = 1 if category is daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION else 0
	observation = daily_blog.recovery.GenerationObservation("stage6", 1, successful, (), category)
	fault = daily_blog.recovery.PipelineFault(category, 1, "", "", (observation,))
	return daily_blog.recovery.PipelineFaultError(fault, "a" * 64)


#============================================
@pytest.mark.parametrize("category", tuple(daily_blog.recovery.TerminalFaultCategory))
def test_command_serializes_each_terminal_fault_without_unsafe_diagnostics(
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
	category: daily_blog.recovery.TerminalFaultCategory,
) -> None:
	"""Every closed fault category has one canonical stderr result and command status."""
	config = types.SimpleNamespace(report_timezone="America/Chicago")
	monkeypatch.setattr(make_blog.daily_blog.config, "load_config", lambda *_args, **_kwargs: config)

	def raise_fault(_config: object, _date: str, **_kwargs: object) -> None:
		raise _fault_error(category)

	monkeypatch.setattr(make_blog.automation.publish_daily_blog, "publish_report_date", raise_fault)

	assert make_blog.command(["--date", "2026-08-27"]) == 2
	assert json.loads(capsys.readouterr().err) == {
		"artifact_name": "recovery_fault.json",
		"category": category.value,
		"digest_sha256": "a" * 64,
		"report_date": "2026-08-27",
		"status": "pipeline_fault",
	}


#============================================
def test_command_keeps_the_selected_date_on_stdout_and_fault_only_on_stderr(
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
) -> None:
	"""The command preserves its normal selection notice while isolating terminal JSON."""
	config = types.SimpleNamespace(report_timezone="America/Chicago")
	monkeypatch.setattr(make_blog.daily_blog.config, "load_config", lambda *_args, **_kwargs: config)
	def raise_fault(_config: object, _date: str, **_kwargs: object) -> None:
		raise _fault_error(daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE)

	monkeypatch.setattr(
		make_blog.automation.publish_daily_blog,
		"publish_report_date",
		raise_fault,
	)

	make_blog.command(["--date", "2026-08-27"])
	captured = capsys.readouterr()

	assert captured.out == "Selected report date: 2026-08-27\n"
	assert captured.err.count("\n") == 1


#============================================
def test_command_re_raises_an_untyped_defect(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Unexpected defects remain visible to the process supervisor and developer."""
	config = types.SimpleNamespace(report_timezone="America/Chicago")
	monkeypatch.setattr(make_blog.daily_blog.config, "load_config", lambda *_args, **_kwargs: config)

	def raise_defect(_config: object, _date: str, **_kwargs: object) -> None:
		raise RuntimeError("test implementation defect")

	monkeypatch.setattr(make_blog.automation.publish_daily_blog, "publish_report_date", raise_defect)

	with pytest.raises(RuntimeError, match="test implementation defect"):
		make_blog.command(["--date", "2026-08-27"])


#============================================
def test_command_returns_success_without_stderr(
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
) -> None:
	"""A successful command remains zero-status and emits no terminal JSON."""
	config = types.SimpleNamespace(report_timezone="America/Chicago")
	monkeypatch.setattr(make_blog.daily_blog.config, "load_config", lambda *_args, **_kwargs: config)
	monkeypatch.setattr(
		make_blog.automation.publish_daily_blog,
		"publish_report_date",
		lambda *_args, **_kwargs: None,
	)

	assert make_blog.command(["--date", "2026-08-27"]) == 0
	assert capsys.readouterr().err == ""


#============================================
def test_command_preserves_argparse_status_two() -> None:
	"""Invalid CLI selection remains an argparse validation failure, not a pipeline fault."""
	with pytest.raises(SystemExit) as raised:
		make_blog.command([])

	assert raised.value.code == 2

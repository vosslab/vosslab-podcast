"""Typed terminal recovery faults retain only their fixed public category."""

# Standard Library
import json
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.recovery
import daily_blog.run_contracts
import daily_blog.run_state

CREATED_AT = "2026-08-29T00:00:00Z"

#============================================
def _fault_error(
	category: daily_blog.recovery.TerminalFaultCategory,
) -> daily_blog.recovery.PipelineFaultError:
	"""Return one typed terminal fault with no authored or route diagnostics."""
	successful = 1 if category is daily_blog.recovery.TerminalFaultCategory.NO_ELIGIBLE_GENERATION else 0
	observation = daily_blog.recovery.GenerationObservation(
		"stage6", 1, successful, (), category,
	)
	fault = daily_blog.recovery.PipelineFault(category, 1, "", "", (observation,))
	return daily_blog.recovery.PipelineFaultError(fault, "a" * 64)


#============================================
@pytest.mark.parametrize("category", tuple(daily_blog.recovery.TerminalFaultCategory))
def test_pipeline_fault_error_maps_each_closed_category_exactly(
	category: daily_blog.recovery.TerminalFaultCategory,
) -> None:
	"""Every recovery terminal category survives exception classification unchanged."""
	error = _fault_error(category)

	assert daily_blog.run_contracts.classify_exception(error) == category.value
	assert category.value in daily_blog.run_contracts.FAILURE_KINDS


#============================================
def test_pipeline_fault_failure_persists_only_bounded_logical_diagnosis(
	tmp_path: pathlib.Path,
	capsys: pytest.CaptureFixture,
) -> None:
	"""The failed Stage 6 record and event omit digest, paths, and route details."""
	category = daily_blog.recovery.TerminalFaultCategory.ROUTE_UNAVAILABLE
	error = _fault_error(category)
	record = daily_blog.run_contracts.RunRecord.create("run-pipeline-fault", "2026-08-29", CREATED_AT)
	record.start_phase("repository_discovery", "b" * 64)
	store = daily_blog.run_state.RunStore(
		str(tmp_path), "vosslab", "2026-08-29", "run-pipeline-fault",
	)
	failure_kind = daily_blog.run_contracts.classify_exception(error)
	record.fail_phase("repository_discovery", failure_kind)
	store.save(record)
	store.append_event(
		"daily_publication.phase_failed",
		{"failure_kind": failure_kind, "phase": "repository_discovery"},
	)

	with open(store.record_path, encoding="utf-8") as handle:
		persisted = json.load(handle)
	with open(store.event_path, encoding="utf-8") as handle:
		event = json.loads(handle.read())
	stdout = capsys.readouterr().out
	serialized = json.dumps({"record": persisted, "event": event, "stdout": stdout})

	assert persisted["failure"] == {
		"phase": "repository_discovery", "kind": category.value,
	}
	assert event["failure_kind"] == category.value
	assert event["run_state_artifact"] == "run_state.json"
	assert "run_state_path" not in event
	assert "a" * 64 not in serialized
	assert str(tmp_path) not in serialized
	assert "recovery_fault.json" not in serialized

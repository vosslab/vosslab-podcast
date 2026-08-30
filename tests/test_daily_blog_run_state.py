"""Coordinator-owned editorial reliability persistence tests."""

# Standard Library
import json
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.observability
import daily_blog.replication
import daily_blog.run_contracts
import daily_blog.run_state

CREATED_AT = "2026-08-23T00:00:00Z"

#============================================
def editorial_summary(
	step: str,
	artifact_id: str = "",
) -> daily_blog.replication.StepReliability:
	"""Return one small valid editorial reliability summary."""
	return daily_blog.replication.StepReliability(
		step, "succeeded", 1, 1, 0, 0, 0, 0, artifact_id, (),
	)


#============================================
def test_v11_run_record_replays_typed_incumbent_transitions() -> None:
	"""Typed transition replay preserves the selected publication artifact."""
	record = daily_blog.run_contracts.RunRecord.create("run-transitions", "2026-08-23", CREATED_AT)
	first = "artifact-0123456789abcdef01234567"
	second = "artifact-fedcba987654321001234567"
	third = "artifact-abcdef0123456789abcdef01"
	record.add_editorial_step(editorial_summary("repository-observation"), daily_blog.run_contracts.ObserveIncumbent())
	record.add_editorial_step(
		editorial_summary("whole-post-selection", first),
		daily_blog.run_contracts.EstablishIncumbent(first),
	)
	record.add_editorial_step(
		editorial_summary("final-synthesis", second),
		daily_blog.run_contracts.ReplaceIncumbent(first, second),
	)
	record.add_editorial_step(
		editorial_summary("publication-repair", third),
		daily_blog.run_contracts.RepairPublicationIncumbent(second, third),
	)
	restored = daily_blog.run_contracts.RunRecord.from_dict(record.to_dict())
	assert restored.best_artifact_id == third


#============================================
@pytest.mark.parametrize(
	("transition", "summary_artifact_id"),
	(
		(
			daily_blog.run_contracts.ReplaceIncumbent(
				"artifact-fedcba987654321001234567",
				"artifact-abcdef0123456789abcdef01",
			),
			"artifact-abcdef0123456789abcdef01",
		),
		(
			daily_blog.run_contracts.ReplaceIncumbent(
				"artifact-0123456789abcdef01234567",
				"artifact-0123456789abcdef01234567",
			),
			"artifact-0123456789abcdef01234567",
		),
		(
			daily_blog.run_contracts.ReplaceIncumbent(
				"artifact-0123456789abcdef01234567",
				"ranking-promotion-0123456789abcdef01234567",
			),
			"ranking-promotion-0123456789abcdef01234567",
		),
		(
			daily_blog.run_contracts.ReplaceIncumbent(
				"artifact-0123456789abcdef01234567",
				"artifact-fedcba987654321001234567",
			),
			"artifact-abcdef0123456789abcdef01",
		),
	),
)
def test_v11_rejects_forged_successor_relations(
	transition: daily_blog.run_contracts.IncumbentTransition,
	summary_artifact_id: str,
) -> None:
	"""A successor must name the live eligible incumbent and matching summary."""
	record = daily_blog.run_contracts.RunRecord.create("run-forged", "2026-08-23", CREATED_AT)
	incumbent = "artifact-0123456789abcdef01234567"
	record.add_editorial_step(
		editorial_summary("selected-post", incumbent),
		daily_blog.run_contracts.EstablishIncumbent(incumbent),
	)
	with pytest.raises(RuntimeError):
		record.add_editorial_step(editorial_summary("forged-successor", summary_artifact_id), transition)
	assert record.best_artifact_id == incumbent


#============================================
def test_v11_rejects_transition_stream_with_wrong_replayed_final_identity() -> None:
	"""Durable state cannot retain a final identity absent from its transition chain."""
	record = daily_blog.run_contracts.RunRecord.create("run-replay", "2026-08-23", CREATED_AT)
	artifact_id = "artifact-0123456789abcdef01234567"
	record.add_editorial_step(
		editorial_summary("selected-post", artifact_id),
		daily_blog.run_contracts.EstablishIncumbent(artifact_id),
	)
	value = record.to_dict()
	value["best_artifact_id"] = "artifact-fedcba987654321001234567"
	with pytest.raises(RuntimeError):
		daily_blog.run_contracts.RunRecord.from_dict(value)


#============================================
def test_v11_rejects_public_reopen_of_v10_record() -> None:
	"""A legacy public record requires an explicit offline migration."""
	value = daily_blog.run_contracts.RunRecord.create("run-v10", "2026-08-23", CREATED_AT).to_dict()
	value["schema_version"] = "vosslab.daily-blog.run.v10"
	with pytest.raises(RuntimeError, match="requires an offline migration"):
		daily_blog.run_contracts.RunRecord.from_dict(value)


#============================================
def test_run_store_rejects_unsafe_event_labels_before_record_mutation(
	tmp_path: pathlib.Path,
) -> None:
	"""Untrusted diagnostic-like labels cannot enter a durable event or record."""
	store = daily_blog.run_state.RunStore(str(tmp_path), "vosslab", "2026-08-23", "run-redaction")
	record = daily_blog.run_contracts.RunRecord.create("run-redaction", "2026-08-23", CREATED_AT)
	before = record.to_dict()
	with pytest.raises(RuntimeError):
		store.record_editorial_step(
			record,
			editorial_summary("editorial/secret-token"),
			daily_blog.run_contracts.ObserveIncumbent(),
		)
	assert record.to_dict() == before
	assert not pathlib.Path(store.record_path).exists()
	assert not pathlib.Path(store.event_path).exists()


#============================================
def test_run_store_rejects_forged_replacement_before_durable_mutation(
	tmp_path: pathlib.Path,
) -> None:
	"""A successor cannot be committed without its exact durable predecessor."""
	store = daily_blog.run_state.RunStore(str(tmp_path), "vosslab", "2026-08-23", "run-forged-store")
	record = daily_blog.run_contracts.RunRecord.create("run-forged-store", "2026-08-23", CREATED_AT)
	before = record.to_dict()
	with pytest.raises(RuntimeError):
		store.record_editorial_step(
			record,
			editorial_summary("selected-post", "artifact-fedcba987654321001234567"),
			daily_blog.run_contracts.ReplaceIncumbent(
				"artifact-0123456789abcdef01234567",
				"artifact-fedcba987654321001234567",
			),
		)
	assert record.to_dict() == before
	assert not pathlib.Path(store.record_path).exists()
	assert not pathlib.Path(store.pending_editorial_step_path).exists()


#============================================
def test_run_store_persists_one_typed_editorial_replacement(
	tmp_path: pathlib.Path,
) -> None:
	"""A valid typed successor becomes the selected durable artifact."""
	store = daily_blog.run_state.RunStore(str(tmp_path), "vosslab", "2026-08-23", "run-replacement")
	record = daily_blog.run_contracts.RunRecord.create("run-replacement", "2026-08-23", CREATED_AT)
	incumbent = "artifact-0123456789abcdef01234567"
	replacement = "artifact-fedcba987654321001234567"
	store.record_editorial_step(
		record,
		editorial_summary("selected-post", incumbent),
		daily_blog.run_contracts.EstablishIncumbent(incumbent),
	)
	store.record_editorial_step(
		record,
		editorial_summary("editorial-decision", replacement),
		daily_blog.run_contracts.ReplaceIncumbent(incumbent, replacement),
	)
	persisted = daily_blog.run_contracts.RunRecord.from_dict(
		json.loads(pathlib.Path(store.record_path).read_text(encoding="utf-8")),
	)
	assert persisted.best_artifact_id == replacement
	events = [json.loads(line) for line in pathlib.Path(store.event_path).read_text(encoding="utf-8").splitlines()]
	assert any(event.get("transition_kind") == "replace" for event in events)


#============================================
def test_run_store_replays_a_pending_replacement_without_duplicate_event(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Retrying a pending typed replacement converges on one durable event."""
	store = daily_blog.run_state.RunStore(str(tmp_path), "vosslab", "2026-08-23", "run-replay")
	record = daily_blog.run_contracts.RunRecord.create("run-replay", "2026-08-23", CREATED_AT)
	incumbent = "artifact-0123456789abcdef01234567"
	replacement = "artifact-fedcba987654321001234567"
	store.record_editorial_step(
		record,
		editorial_summary("selected-post", incumbent),
		daily_blog.run_contracts.EstablishIncumbent(incumbent),
	)
	summary = editorial_summary("editorial-decision", replacement)
	transition = daily_blog.run_contracts.ReplaceIncumbent(incumbent, replacement)

	def interrupted_replay(run_fd: int, line: str) -> bool:
		raise daily_blog.observability.EventJournalError("interrupted")

	monkeypatch.setattr(store.event_sink, "replay_editorial_at", interrupted_replay)
	with pytest.raises(RuntimeError, match="event could not be persisted"):
		store.record_editorial_step(record, summary, transition)
	assert record.best_artifact_id == incumbent

	monkeypatch.undo()
	store.record_editorial_step(record, summary, transition)
	assert record.best_artifact_id == replacement
	events = [json.loads(line) for line in pathlib.Path(store.event_path).read_text(encoding="utf-8").splitlines()]
	matches = [event for event in events if event.get("step") == summary.step]
	assert len(matches) == 1
	assert matches[0]["transition_kind"] == "replace"
	assert not pathlib.Path(store.pending_editorial_step_path).exists()


#============================================
def _record_with_persisted_path(field: str, path: str) -> daily_blog.run_contracts.RunRecord:
	"""Return a small record carrying one durable producer path."""
	record = daily_blog.run_contracts.RunRecord.create("run-logical-path", "2026-08-23", CREATED_AT)
	if field == "repository_roster.snapshot_path":
		record.repository_roster = {"roster_id": "a" * 64, "snapshot_path": path}
	else:
		record.publication_bundle = {"path": path}
	return record


#============================================
def test_run_record_rejects_an_absolute_persisted_producer_path() -> None:
	"""Durable producer references are logical paths, never host paths."""
	record = _record_with_persisted_path("repository_roster.snapshot_path", "/private/output/path")
	with pytest.raises(RuntimeError):
		record.to_dict()
	value = daily_blog.run_contracts.RunRecord.create("run-logical-path", "2026-08-23", CREATED_AT).to_dict()
	value["repository_roster"] = {"roster_id": "a" * 64, "snapshot_path": "/private/output/path"}
	with pytest.raises(RuntimeError):
		daily_blog.run_contracts.RunRecord.from_dict(value)


#============================================
@pytest.mark.parametrize(
	("field", "path"),
	(
		("repository_roster.snapshot_path", "vosslab/daily_blog_repository_rosters/" + "a" * 64),
		("publication_bundle.path", "vosslab/daily_blog/2026-08-23/publication"),
	),
)
def test_run_record_round_trips_valid_logical_producer_paths(field: str, path: str) -> None:
	"""Canonical producer references survive durable serialization."""
	record = _record_with_persisted_path(field, path)
	assert daily_blog.run_contracts.RunRecord.from_dict(record.to_dict()).to_dict() == record.to_dict()


#============================================
def test_run_store_derives_resolves_and_binds_contained_logical_paths(
	tmp_path: pathlib.Path,
) -> None:
	"""A store persists only paths contained by, and bound to, its identity."""
	store = daily_blog.run_state.RunStore(str(tmp_path / "output"), "vosslab", "2026-08-23", "run-paths")
	contained = str(tmp_path / "output" / "vosslab" / "daily_blog" / "2026-08-23" / "publication")
	logical = "vosslab/daily_blog/2026-08-23/publication"
	assert store.derive_output_logical_path(contained) == logical
	assert store.resolve_output_logical_path(logical) == contained
	with pytest.raises(RuntimeError):
		store.derive_output_logical_path(str(tmp_path / "outside"))
	record = _record_with_persisted_path("publication_bundle.path", "vosslab/daily_blog/2026-08-24/publication")
	with pytest.raises(RuntimeError):
		store.save(record)
	assert not pathlib.Path(store.record_path).exists()


#============================================
#============================================
def test_run_store_rejects_oversized_authoritative_state_before_parsing(
	tmp_path: pathlib.Path,
) -> None:
	"""Reopening refuses a regular state file beyond its documented schema envelope."""
	store = daily_blog.run_state.RunStore(str(tmp_path), "vosslab", "2026-08-23", "run-large-state")
	pathlib.Path(store.record_path).write_bytes(b"x" * (store.MAX_RUN_STATE_BYTES + 1))
	with pytest.raises(RuntimeError):
		store.finalize_summary()

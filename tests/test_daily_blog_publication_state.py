"""Date-owned publication state and replacement tests."""

# Standard Library
import contextlib
import json
import pathlib
import shutil
import types

# PIP3 modules
import pytest

# local repo modules
import automation.publish_daily_blog
import daily_blog.bundles
import daily_blog.editorial
import daily_blog.io_utils
import daily_blog.orchestrator
import daily_blog.projection
import daily_blog.publication_state
import daily_blog.repository_contracts
import daily_blog.schema


#============================================
def _current_publication_config(tmp_path: pathlib.Path) -> types.SimpleNamespace:
	"""Create one complete publisher-owned date publication for integrity tests."""
	report_date = "2026-08-26"
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/project", "a" * 40, "", "", "work", "git show"
	)
	packet = daily_blog.schema.EvidencePacket.create(
		report_date, "America/Chicago", True, {}, [], [], [item]
	)
	projection = daily_blog.projection.build_projection(packet, {
		"context_chars": 8000,
		"excerpt_chars": 1000,
		"commit_subject_chars": 120,
	})
	record = daily_blog.repository_contracts.RepositoryRecord.from_dict({
		"repository": "vosslab/project",
		"repository_url": "https://github.com/vosslab/project",
		"clone_url": "https://github.com/vosslab/project.git",
		"created_at": "2020-01-01T00:00:00Z",
		"is_fork": False,
	})
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [record])
	post = "A small maker note.\n"
	decision = daily_blog.editorial.EditorialDecision(
		winner="A",
		reason="Candidate A is approved.",
		evidence_quality="high",
		confidence=0.9,
		projection_id=projection.projection_id,
		post=post,
		anonymous_mapping={"A": 0},
	)
	candidate = daily_blog.editorial.CandidateResult(
		"author", projection.projection_id, post, daily_blog.io_utils.sha256_text(post), True, ()
	)
	producer_root = tmp_path / "producer"
	bundle_path, bundle = daily_blog.bundles.BundleWriter(
		str(producer_root), "vosslab", "f" * 64, daily_blog.contracts.V3_EDITORIAL_CONTRACT
	).write("run-one", packet, projection, {}, [candidate], decision, roster)
	publisher_root = tmp_path / "publisher"
	archive = publisher_root / "data" / "publication_bundles" / report_date
	archive.parent.mkdir(parents=True)
	shutil.copytree(bundle_path, archive)
	installed_post = publisher_root / "docs" / "blog" / "posts" / f"{report_date}.md"
	installed_post.parent.mkdir(parents=True)
	installed_post.write_text(post, encoding="utf-8")
	(publisher_root / "generated" / "releases" / report_date).mkdir(parents=True)
	(publisher_root / "generated" / "releases" / report_date / "index.html").write_text("ok", encoding="utf-8")
	publication_record = {
		"schema_version": daily_blog.publication_state.PUBLICATION_SCHEMA_VERSION,
		"report_date": report_date,
		"timezone": "America/Chicago",
		"generator_run": "run-one",
		"generator_revision": "f" * 64,
		"bundle_sha256": bundle["bundle_sha256"],
		"evidence_manifest": f"data/publication_bundles/{report_date}/evidence.json",
		"editorial_projection_manifest": f"data/publication_bundles/{report_date}/editorial_projection.json",
		"post_path": f"docs/blog/posts/{report_date}.md",
		"imported_at": "2026-08-27T00:00:00Z",
	}
	path = publisher_root / "data" / "publications" / f"{report_date}.json"
	path.parent.mkdir(parents=True)
	path.write_text(json.dumps(publication_record), encoding="utf-8")
	return types.SimpleNamespace(
		daily_blog_repository=str(publisher_root), report_timezone="America/Chicago"
	)


#============================================
def test_missing_date_passes_nonreplacement_intent_to_public_pipeline(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A missing date gives the public pipeline explicit nonreplacement intent."""
	config = types.SimpleNamespace(daily_blog_repository="/publisher")
	observed = []

	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.publication_state,
		"inspect_publication",
		lambda _config, _date: daily_blog.publication_state.PublicationInspection("missing"),
	)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator,
		"publication_date_lock",
		lambda _config, _date: contextlib.nullcontext(),
	)

	def import_bundle(_repository: str, _path: str, *, replace_existing: bool) -> dict:
		observed.append(("publisher", replace_existing))
		return {}

	def run_locked(_config: object, report_date: str, **kwargs: object) -> tuple[str, dict]:
		observed.append((
			report_date,
			kwargs["publisher_function"] is import_bundle,
			kwargs["force_regeneration"],
		))
		publisher = kwargs["publisher_function"]
		publisher("/publisher", "/bundle", replace_existing=False)
		return "/bundle", {"bundle_sha256": "a" * 64}

	monkeypatch.setattr(automation.publish_daily_blog.daily_blog.publisher, "import_bundle", import_bundle)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator,
		"run_daily_publication_locked",
		run_locked,
	)

	automation.publish_daily_blog.publish_report_date(
		config,
		"2026-08-26",
	)

	assert observed == [("2026-08-26", True, False), ("publisher", False)]


#============================================
def test_current_date_reports_already_published_before_generation(
	monkeypatch: pytest.MonkeyPatch,
	capsys: pytest.CaptureFixture[str],
) -> None:
	"""A coherent occupied date is a successful no-work publication result."""
	config = types.SimpleNamespace(daily_blog_repository="/publisher")
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.publication_state,
		"inspect_publication",
		lambda _config, _date: daily_blog.publication_state.PublicationInspection("current"),
	)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator,
		"publication_date_lock",
		lambda _config, _date: contextlib.nullcontext(),
	)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator,
		"run_daily_publication_locked",
		lambda *_args, **_kwargs: pytest.fail("Current dates must not regenerate."),
	)

	automation.publish_daily_blog.publish_report_date(config, "2026-08-26")

	assert "Publication status: already published" in capsys.readouterr().out


#============================================
def test_confirmed_date_replacement_passes_replacement_intent_to_public_pipeline(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""An affirmative decision gives the public pipeline explicit replacement intent."""
	config = types.SimpleNamespace(daily_blog_repository="/publisher")
	observed = []

	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.publication_state,
		"inspect_publication",
		lambda _config, _date: daily_blog.publication_state.PublicationInspection("current"),
	)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator,
		"publication_date_lock",
		lambda _config, _date: contextlib.nullcontext(),
	)

	def import_bundle(_repository: str, _path: str, *, replace_existing: bool) -> dict:
		observed.append(("publisher", replace_existing))
		return {}

	def run_locked(_config: object, report_date: str, **kwargs: object) -> tuple[str, dict]:
		observed.append((
			report_date,
			kwargs["publisher_function"] is import_bundle,
			kwargs["force_regeneration"],
		))
		kwargs["publisher_function"]("/publisher", "/bundle", replace_existing=True)
		return "/bundle", {"bundle_sha256": "a" * 64}

	monkeypatch.setattr(automation.publish_daily_blog.daily_blog.publisher, "import_bundle", import_bundle)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator,
		"run_daily_publication_locked",
		run_locked,
	)

	automation.publish_daily_blog.publish_report_date(
		config,
		"2026-08-26",
		replacement_decider=lambda report_date: report_date == "2026-08-26",
	)

	assert observed == [("2026-08-26", True, True), ("publisher", True)]


#============================================
@pytest.mark.parametrize("replace_existing", [False, True])
def test_invoke_publisher_passes_intent_and_copies_mapping_receipt(
	replace_existing: bool,
) -> None:
	"""The publisher boundary passes its Boolean intent and isolates a mapping receipt."""
	receipt = types.MappingProxyType({"status": "imported"})
	observed = []

	def publisher(_repository: str, _bundle: str, *, replace_existing: bool) -> object:
		observed.append(replace_existing)
		return receipt

	result = daily_blog.orchestrator.invoke_publisher(
		publisher, "/publisher", "/bundle", replace_existing=replace_existing
	)

	assert (observed, result, result is receipt) == ([replace_existing], dict(receipt), False)


#============================================
def test_invoke_publisher_rejects_nonmapping_receipt() -> None:
	"""The publisher boundary rejects receipts without mapping semantics."""

	def publisher(_repository: str, _bundle: str, *, replace_existing: bool) -> object:
		return [("status", "imported")]

	with pytest.raises(RuntimeError, match="must return a mapping"):
		daily_blog.orchestrator.invoke_publisher(
			publisher, "/publisher", "/bundle", replace_existing=False
		)


#============================================
def test_invoke_publisher_rejects_integer_replacement_intent() -> None:
	"""Replacement intent accepts only the Boolean protocol value."""

	def publisher(_repository: str, _bundle: str, *, replace_existing: bool) -> object:
		return {}

	with pytest.raises(RuntimeError, match="must be Boolean"):
		daily_blog.orchestrator.invoke_publisher(
			publisher, "/publisher", "/bundle", replace_existing=1
		)


#============================================
def test_unconfirmed_invalid_date_fails_before_generation(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Noninteractive scheduling preserves an invalid occupied date fail-closed."""
	config = types.SimpleNamespace(daily_blog_repository="/publisher")
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.publication_state,
		"inspect_publication",
		lambda _config, _date: daily_blog.publication_state.PublicationInspection(
			"invalid", "missing roster"
		),
	)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator,
		"publication_date_lock",
		lambda _config, _date: contextlib.nullcontext(),
	)
	monkeypatch.setattr(
		automation.publish_daily_blog.daily_blog.orchestrator, "run_daily_publication_locked", lambda *_args, **_kwargs: pytest.fail("Generation must not run."))

	with pytest.raises(RuntimeError, match="requires confirmed replacement: missing roster"):
		automation.publish_daily_blog.publish_report_date(config, "2026-08-26")


#============================================
def test_publication_exists_rejects_a_tampered_declared_evidence_artifact(
	tmp_path: pathlib.Path,
) -> None:
	"""An archive cannot become current merely because its manifest still exists."""
	config = _current_publication_config(tmp_path)
	evidence = pathlib.Path(config.daily_blog_repository) / "data" / "publication_bundles" / "2026-08-26" / "evidence.json"
	evidence.write_text("{}", encoding="utf-8")

	inspection = daily_blog.publication_state.inspect_publication(config, "2026-08-26")
	assert inspection.state == "invalid"
	with pytest.raises(RuntimeError, match="publication state is invalid"):
		daily_blog.publication_state.publication_exists(config, "2026-08-26")


#============================================
def test_publication_exists_rejects_missing_repository_roster(
	tmp_path: pathlib.Path,
) -> None:
	"""The roster is a required typed artifact, not optional supporting metadata."""
	config = _current_publication_config(tmp_path)
	roster = pathlib.Path(config.daily_blog_repository) / "data" / "publication_bundles" / "2026-08-26" / "repository_roster.json"
	roster.unlink()

	inspection = daily_blog.publication_state.inspect_publication(config, "2026-08-26")
	assert inspection.state == "invalid"
	assert "repository roster" in inspection.reason


#============================================

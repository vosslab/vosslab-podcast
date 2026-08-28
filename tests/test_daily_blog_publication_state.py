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
		str(producer_root), "vosslab", "f" * 64
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
def test_confirmed_date_replacement_forces_fresh_generation_under_one_lock(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""One affirmative date decision selects fresh generation and publisher replacement."""
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
		observed.append((report_date, kwargs["force_regeneration"]))
		publisher = kwargs["publisher_function"]
		publisher("/publisher", "/bundle")
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

	assert observed == [("2026-08-26", True), ("publisher", True)]


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

"""Producer-side post-import publication verification tests."""

# Standard Library
import json
import pathlib
import shutil
import subprocess

# PIP3 modules
import pytest

# local repo modules
import daily_blog.publication_contract
import daily_blog.io_utils
import daily_blog.publisher
import daily_blog.publisher_contract
import daily_blog.activation
import daily_blog.prompt_registry.editorial_contracts
import daily_blog.editorial
import daily_blog.schema
import daily_blog.projection
import daily_blog.repository_contracts


REPORT_DATE = "2026-08-26"
POST = (
	"---\n"
	"date: 2026-08-26\n"
	"slug: durable-boundaries\n"
	"generator_run: run-one\n"
	"evidence_manifest: evidence.json\n"
	"editorial_projection: editorial_projection.json\n"
	"---\n\n"
	"# Durable Boundaries\n\nA grounded maker note.\n"
)


#============================================
def _write_json(path: pathlib.Path, value: dict) -> None:
	"""Write one small deterministic JSON object beneath a disposable root."""
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(daily_blog.io_utils.stable_json_text(value), encoding="utf-8")


#============================================
def _publisher_tree(tmp_path: pathlib.Path, *, include_page: bool = True) -> pathlib.Path:
	"""Create one coherent committed publisher tree without invoking its importer."""
	root = tmp_path / "publisher"
	(root / "scripts").mkdir(parents=True)
	(root / "scripts" / "import_publication_bundle.py").write_text("# importer\n", encoding="utf-8")
	(root / "mkdocs.yml").write_text(
		"markdown_extensions:\n  - toc:\n      permalink: true\n", encoding="utf-8",
	)
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/project", "a" * 40, "", "", "work", "git show",
	)
	packet = daily_blog.schema.EvidencePacket.create(
		REPORT_DATE, "America/Chicago", True, {}, [], [], [item],
	)
	projection = daily_blog.projection.build_projection(packet, {
		"context_chars": 8000, "excerpt_chars": 1000, "commit_subject_chars": 120,
	})
	roster = daily_blog.repository_contracts.RepositoryRoster.create("vosslab", [
		daily_blog.repository_contracts.RepositoryRecord.from_dict({
			"repository": "vosslab/project", "repository_url": "https://github.com/vosslab/project",
			"clone_url": "https://github.com/vosslab/project.git", "created_at": "2020-01-01T00:00:00Z",
			"is_fork": False,
		}),
	])
	post = POST + f"\n<!-- evidence: {item.evidence_id} -->\n"
	body = post.split("---\n", 2)[2]
	selected = daily_blog.artifacts.CompletePost.create_publication_derivative(
		REPORT_DATE, (packet,), ("vosslab/project",), body, (item.evidence_id,), REPORT_DATE,
		str(tmp_path / "producer" / "vosslab" / "daily_blog" / REPORT_DATE / "post.md"),
		{
			"date": REPORT_DATE, "slug": "durable-boundaries", "generator_run": "run-one",
			"evidence_manifest": "evidence.json", "editorial_projection": "editorial_projection.json",
		},
	)
	post_path = root / "docs" / "blog" / "posts" / f"{REPORT_DATE}.md"
	post_path.parent.mkdir(parents=True)
	post_path.write_text(post, encoding="utf-8")
	archive = root / "data" / "publication_bundles" / REPORT_DATE
	contract = daily_blog.prompt_registry.editorial_contracts.active_contract()
	policy = daily_blog.prompt_registry.editorial_contracts.policy_for_contract(contract)
	prompt_contract = daily_blog.editorial.prompt_contract_identity(contract=contract)
	activation = daily_blog.activation.load_maker_activation().receipt
	identity = daily_blog.publication_contract.publication_identity(
		str(pathlib.Path(__file__).resolve().parents[1]), None,
		prompt_paths=daily_blog.prompt_registry.editorial_contracts.prompt_paths(contract), contracts={
			"evidence_schema": daily_blog.schema.EVIDENCE_SCHEMA_VERSION,
			"editorial_projection_schema": daily_blog.schema.PROJECTION_SCHEMA_VERSION,
			"prompt_version": contract.prompt_version,
			"rubric_version": contract.rubric_version,
			"candidate_validation": {
				"name": policy.name, "version": policy.version, "sha256": policy.sha256(),
			},
		}, editorial_prompt_contract=prompt_contract, activation_receipt={
			"activation_id": activation["activation_id"],
			"editorial_prompt_contract_sha256": activation["editorial_prompt_contract_sha256"],
		},
	)
	producer_root = tmp_path / "producer"
	producer_root.mkdir(exist_ok=True)
	bundle_path, bundle, _transfer_value = daily_blog.publication_contract.BundleWriter(
		str(producer_root), "vosslab", identity,
	).write("run-one", packet, projection, {}, roster, selected)
	archive.parent.mkdir(parents=True)
	shutil.copytree(bundle_path, archive)
	article_projection = daily_blog.publication_article_projection.source_article_projection(
		post, (root / "mkdocs.yml").read_text(encoding="utf-8"),
	)
	_write_json(root / "data" / "publications" / f"{REPORT_DATE}.json", {
		"schema_version": "vosslab.daily-blog.publication.v5",
		"report_date": REPORT_DATE,
		"bundle_sha256": bundle["bundle_sha256"],
		"article_body_sha256": daily_blog.publication_article_projection.article_body_sha256(article_projection),
		"best_artifact_id": bundle["best_artifact_id"],
		"editorial_projection_manifest": (
			f"data/publication_bundles/{REPORT_DATE}/editorial_projection.json"
		),
		"evidence_manifest": f"data/publication_bundles/{REPORT_DATE}/evidence.json",
		"generator_revision": "b" * 64,
		"generator_run": "run-one",
		"imported_at": "2026-08-26T00:00:00Z",
		"post_path": f"docs/blog/posts/{REPORT_DATE}.md",
		"timezone": "America/Chicago",
	})
	if include_page:
		page = root / "generated" / "releases" / REPORT_DATE / "blog" / "2026" / "08" / "26" / "durable-boundaries" / "index.html"
		page.parent.mkdir(parents=True)
		page.write_text(
			"<html><main><time datetime='2026-08-26 00:00:00+00:00'>August 26, 2026</time>"
			"<article class='md-content__inner md-typeset'>"
			"<h1>Durable Boundaries<a class='headerlink'>&para;</a></h1>"
			"<p>A grounded maker note.</p></article></main></html>",
			encoding="utf-8",
		)
	(root / "site").symlink_to(f"generated/releases/{REPORT_DATE}")
	return root


#============================================
def _bundle_sha256(root: pathlib.Path) -> str:
	"""Read the exact bundle identity committed by the disposable publisher."""
	value = json.loads(
		(root / "data" / "publication_bundles" / REPORT_DATE / "bundle.json").read_text(
			encoding="utf-8"
		)
	)
	return value["bundle_sha256"]


#============================================
def _transfer(root: pathlib.Path) -> daily_blog.publication_contract.SealedBundleTransfer:
	"""Return a bounded typed transfer for importer subprocess boundary tests."""
	archive = root / "data" / "publication_bundles" / REPORT_DATE
	bundle = json.loads((archive / "bundle.json").read_text(encoding="utf-8"))
	artifacts = {
		"bundle.json": (archive / "bundle.json").read_bytes(),
		"evidence.json": (archive / "evidence.json").read_bytes(),
		"repository_roster.json": (archive / "repository_roster.json").read_bytes(),
		"editorial_projection.json": (archive / "editorial_projection.json").read_bytes(),
		"post.md": (archive / "post.md").read_bytes(),
	}
	transfer = daily_blog.publication_contract.sealed_bundle_transfer(bundle, artifacts)
	return transfer


#============================================
def _receipt(root: pathlib.Path) -> dict:
	"""Return the exact producer-side receipt derived from one committed tree."""
	receipt = daily_blog.publisher._committed_receipt(str(root), {
		"status": "imported", "bundle_sha256": _bundle_sha256(root), "report_date": REPORT_DATE,
	})
	return receipt


#============================================
def test_import_bundle_returns_a_complete_committed_receipt(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A successful importer result becomes an independently verifiable receipt."""
	root = _publisher_tree(tmp_path)
	observed: dict[str, object] = {}

	def fake_run(*arguments: object, **kwargs: object) -> subprocess.CompletedProcess:
		observed["command"] = arguments[0]
		observed["input"] = kwargs["input"]
		return subprocess.CompletedProcess([], 0, daily_blog.io_utils.stable_json_text({
			"status": "imported", "bundle_sha256": _bundle_sha256(root), "report_date": REPORT_DATE,
		}).encode("utf-8"), b"")

	monkeypatch.setattr(daily_blog.publisher.subprocess, "run", fake_run)
	result = daily_blog.publisher.import_bundle(str(root), _transfer(root))

	assert result["best_artifact_id"].startswith("artifact-")
	assert result["rendered_page_path"].endswith("durable-boundaries/index.html")
	assert any("--bundle-stdin" in part for part in observed["command"])
	assert observed["input"] == _transfer(root).to_bytes()


#============================================
def test_import_rejects_a_partial_importer_receipt(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The producer does not accept a subprocess result missing the identity fields."""
	root = _publisher_tree(tmp_path)

	def fake_run(*_arguments: object, **_kwargs: object) -> subprocess.CompletedProcess:
		return subprocess.CompletedProcess([], 0, b'{"status":"imported"}', b"")

	monkeypatch.setattr(daily_blog.publisher.subprocess, "run", fake_run)
	with pytest.raises(daily_blog.publisher_contract.PublisherCommandError, match="publisher_protocol_failure"):
		daily_blog.publisher.import_bundle(str(root), _transfer(root))


#============================================
def test_import_exposes_only_an_allowlisted_publisher_failure(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A publisher failure keeps its safe category and never returns foreign stderr text."""
	root = _publisher_tree(tmp_path)
	envelope = daily_blog.io_utils.stable_json_text({
		"schema_version": "vosslab.daily-blog.import-failure.v1",
		"category": "snapshot_rejected", "phase": "validate",
	}).encode("utf-8")

	def fake_run(*_arguments: object, **_kwargs: object) -> subprocess.CompletedProcess:
		return subprocess.CompletedProcess([], 1, b"", envelope)

	monkeypatch.setattr(daily_blog.publisher.subprocess, "run", fake_run)
	with pytest.raises(daily_blog.publisher_contract.PublisherCommandError) as raised:
		daily_blog.publisher.import_bundle(str(root), _transfer(root))

	assert (raised.value.category, raised.value.phase) == ("snapshot_rejected", "validate")
	assert "stderr" not in str(raised.value)


#============================================
def test_import_rejects_noncanonical_failure_protocol(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Untrusted stderr cannot become a classification or diagnostic surface."""
	root = _publisher_tree(tmp_path)

	def fake_run(*_arguments: object, **_kwargs: object) -> subprocess.CompletedProcess:
		return subprocess.CompletedProcess([], 1, b"", b"untrusted publisher detail")

	monkeypatch.setattr(daily_blog.publisher.subprocess, "run", fake_run)
	with pytest.raises(daily_blog.publisher_contract.PublisherCommandError) as raised:
		daily_blog.publisher.import_bundle(str(root), _transfer(root))

	assert raised.value.category == "publisher_protocol_failure"


#============================================
@pytest.mark.parametrize("envelope", [
	b"{" + b"x" * (daily_blog.publisher_contract.MAX_PROTOCOL_BYTES + 1) + b"}",
	daily_blog.io_utils.stable_json_text({
		"schema_version": "vosslab.daily-blog.import-failure.v1", "category": "snapshot_rejected",
		"phase": "validate", "detail": "not allowed",
	}).encode("utf-8"),
	b'{"category":"snapshot_rejected","phase":"validate","schema_version":"vosslab.daily-blog.import-failure.v1"}\n',
	daily_blog.io_utils.stable_json_text({
		"schema_version": "vosslab.daily-blog.import-failure.v1", "category": "unknown",
		"phase": "validate",
	}).encode("utf-8"),
])
def test_import_failure_protocol_rejects_nonallowlisted_envelopes(envelope: bytes) -> None:
	"""Failure envelopes stay bounded, canonical, and limited to documented classifications."""
	with pytest.raises(daily_blog.publisher_contract.PublisherCommandError) as raised:
		daily_blog.publisher_contract.parse_import_failure(envelope)

	assert raised.value.category == "publisher_protocol_failure"


#============================================
def test_publisher_command_error_canonicalizes_forged_details() -> None:
	"""Direct exception construction cannot retain caller-controlled diagnostics."""
	error = daily_blog.publisher_contract.PublisherCommandError("forged-secret", "untrusted-phase")

	assert (error.category, error.phase) == ("publisher_protocol_failure", "receive")
	assert "forged-secret" not in str(error)


#============================================
def test_import_classifies_timeout_without_subprocess_details(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A timed-out publisher process has one stable actionable classification."""
	root = _publisher_tree(tmp_path)

	def fake_run(*_arguments: object, **_kwargs: object) -> subprocess.CompletedProcess:
		raise subprocess.TimeoutExpired("publisher", 1)

	monkeypatch.setattr(daily_blog.publisher.subprocess, "run", fake_run)
	with pytest.raises(daily_blog.publisher_contract.PublisherCommandError) as raised:
		daily_blog.publisher.import_bundle(str(root), _transfer(root))

	assert raised.value.category == "publisher_timeout"


#============================================
def test_import_classifies_subprocess_start_failure(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A process-start failure remains distinguishable without exposing its detail."""
	root = _publisher_tree(tmp_path)

	def fake_run(*_arguments: object, **_kwargs: object) -> subprocess.CompletedProcess:
		raise OSError("unavailable")

	monkeypatch.setattr(daily_blog.publisher.subprocess, "run", fake_run)
	with pytest.raises(daily_blog.publisher_contract.PublisherCommandError) as raised:
		daily_blog.publisher.import_bundle(str(root), _transfer(root))

	assert raised.value.category == "publisher_start_failure"


#============================================
def test_validate_bundle_transfer_binds_the_exact_sealed_identity(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The read-only publisher preflight receives and attests the one transfer snapshot."""
	root = _publisher_tree(tmp_path)
	transfer = _transfer(root)
	report_date, bundle_sha256, best_artifact_id = daily_blog.publisher._transfer_identity(transfer)
	observed: dict[str, object] = {}

	def fake_run(*arguments: object, **kwargs: object) -> subprocess.CompletedProcess:
		observed["command"] = arguments[0]
		observed["input"] = kwargs["input"]
		receipt = daily_blog.io_utils.stable_json_text({
			"schema_version": "vosslab.daily-blog.import-validation.v1", "status": "valid",
			"bundle_sha256": bundle_sha256, "report_date": report_date,
			"best_artifact_id": best_artifact_id,
		}).encode("utf-8")
		return subprocess.CompletedProcess([], 0, receipt, b"")

	monkeypatch.setattr(daily_blog.publisher.subprocess, "run", fake_run)
	receipt = daily_blog.publisher.validate_bundle_transfer(str(root), transfer)

	assert receipt["bundle_sha256"] == transfer.bundle_sha256
	assert any("--validate-bundle-stdin" in part for part in observed["command"])
	assert observed["input"] == transfer.to_bytes()


#============================================
def test_validate_bundle_transfer_rejects_a_mismatched_identity(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The publisher validation receipt cannot attest a different sealed transfer."""
	root = _publisher_tree(tmp_path)
	transfer = _transfer(root)
	_report_date, bundle_sha256, best_artifact_id = daily_blog.publisher._transfer_identity(transfer)

	def fake_run(*_arguments: object, **_kwargs: object) -> subprocess.CompletedProcess:
		receipt = daily_blog.io_utils.stable_json_text({
			"schema_version": "vosslab.daily-blog.import-validation.v1", "status": "valid",
			"bundle_sha256": bundle_sha256, "report_date": "2026-08-27",
			"best_artifact_id": best_artifact_id,
		}).encode("utf-8")
		return subprocess.CompletedProcess([], 0, receipt, b"")

	monkeypatch.setattr(daily_blog.publisher.subprocess, "run", fake_run)
	with pytest.raises(daily_blog.publisher_contract.PublisherCommandError) as raised:
		daily_blog.publisher.validate_bundle_transfer(str(root), transfer)

	assert raised.value.category == "publisher_protocol_failure"


#============================================
@pytest.mark.parametrize("field, replacement", [
	("report_date", "2026-08-27"),
	("bundle_sha256", "0" * 64),
])
def test_import_rejects_success_receipts_for_a_different_transfer(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, field: str, replacement: str,
) -> None:
	"""A zero-exit publisher may not redirect the producer to another publication identity."""
	root = _publisher_tree(tmp_path)
	transfer = _transfer(root)

	def fake_run(*_arguments: object, **_kwargs: object) -> subprocess.CompletedProcess:
		result = {
			"status": "imported", "bundle_sha256": transfer.bundle_sha256,
			"report_date": transfer.report_date,
		}
		result[field] = replacement
		return subprocess.CompletedProcess([], 0, daily_blog.io_utils.stable_json_text(result).encode("utf-8"), b"")

	monkeypatch.setattr(daily_blog.publisher.subprocess, "run", fake_run)
	with pytest.raises(daily_blog.publisher_contract.PublisherCommandError) as raised:
		daily_blog.publisher.import_bundle(str(root), transfer)

	assert raised.value.category == "publisher_protocol_failure"


#============================================
def test_verify_published_page_binds_committed_content_and_page(
	tmp_path: pathlib.Path,
) -> None:
	"""Verification reads the expected physical page and returns its content identity."""
	root = _publisher_tree(tmp_path)
	result = daily_blog.publisher.verify_published_page(str(root), _receipt(root))

	assert len(result["rendered_page_sha256"]) == 64


#============================================
def test_publication_archive_reader_reads_fixed_direct_artifacts(
	tmp_path: pathlib.Path,
) -> None:
	"""The publisher exposes only the fixed sealed archive artifact surface."""
	root = _publisher_tree(tmp_path)
	with daily_blog.publisher.open_publication_archive(str(root), REPORT_DATE) as archive:
		bundle = archive.read_json_artifact("bundle.json", "bundle")
		post = archive.read_post()

	assert json.loads(bundle)["report_date"] == REPORT_DATE
	assert post.startswith(POST.encode("utf-8"))


#============================================
def test_publication_archive_reader_rejects_a_symlinked_archive_intermediate(
	tmp_path: pathlib.Path,
) -> None:
	"""Archive inspection cannot traverse a substituted publisher directory."""
	root = _publisher_tree(tmp_path)
	data = root / "data"
	replacement = root / "replacement-data"
	data.rename(replacement)
	data.symlink_to(replacement, target_is_directory=True)

	with pytest.raises(RuntimeError, match="archive"):
		with daily_blog.publisher.open_publication_archive(str(root), REPORT_DATE):
			pass


#============================================
def test_publication_archive_reader_rejects_a_nonregular_bundle(
	tmp_path: pathlib.Path,
) -> None:
	"""A sealed archive artifact must remain a direct regular file."""
	root = _publisher_tree(tmp_path)
	bundle = root / "data" / "publication_bundles" / REPORT_DATE / "bundle.json"
	bundle.unlink()
	bundle.mkdir()

	with daily_blog.publisher.open_publication_archive(str(root), REPORT_DATE) as archive:
		with pytest.raises(RuntimeError, match="not regular"):
			archive.read_json_artifact("bundle.json", "bundle")


#============================================
@pytest.mark.parametrize("path", ["notes.txt", "assets/undeclared.bin"])
def test_committed_publication_rejects_undeclared_archive_provenance(
	tmp_path: pathlib.Path, path: str,
) -> None:
	"""A v8 archive contains exactly its sealed manifests and declared assets."""
	root = _publisher_tree(tmp_path)
	archive = root / "data" / "publication_bundles" / REPORT_DATE
	target = archive / path
	target.parent.mkdir(exist_ok=True)
	target.write_bytes(b"unsealed")

	with pytest.raises(RuntimeError, match="archive"):
		daily_blog.publisher._committed_receipt(str(root), {
			"status": "imported", "bundle_sha256": _bundle_sha256(root), "report_date": REPORT_DATE,
		})


#============================================
def test_verify_published_page_rejects_same_date_wrong_article_body(tmp_path: pathlib.Path) -> None:
	"""A dated page with the selected title still needs the full committed article body."""
	root = _publisher_tree(tmp_path)
	page = root / "generated" / "releases" / REPORT_DATE / "blog" / "2026" / "08" / "26" / "durable-boundaries" / "index.html"
	page.write_text(
		"<html><main><time datetime='2026-08-26T00:00:00+00:00'>August 26, 2026</time>"
		"<article class='md-content__inner md-typeset'>"
		"<h1>Durable Boundaries</h1><p>An unrelated article body.</p></article></main></html>",
		encoding="utf-8",
	)

	with pytest.raises(RuntimeError, match="installed article body"):
		daily_blog.publisher.verify_published_page(str(root), _receipt(root))


#============================================
@pytest.mark.parametrize("mutation", ["date", "record", "post", "page_path"])
def test_verify_published_page_fails_closed_on_a_tampered_receipt(
	tmp_path: pathlib.Path, mutation: str,
) -> None:
	"""Receipt identity and date/path substitutions never select another page."""
	root = _publisher_tree(tmp_path)
	receipt = _receipt(root)
	if mutation == "date":
		receipt["report_date"] = "2026-08-25"
	elif mutation == "record":
		receipt["publication_record_sha256"] = "b" * 64
	elif mutation == "post":
		receipt["post_sha256"] = "b" * 64
	else:
		receipt["rendered_page_path"] = "generated/releases/2026-08-26/blog/2026/08/26/other/index.html"

	with pytest.raises(RuntimeError, match="page_verification"):
		daily_blog.publisher.verify_published_page(str(root), receipt)


#============================================
def test_verify_published_page_rejects_a_symlinked_page(
	tmp_path: pathlib.Path,
) -> None:
	"""A published page cannot resolve through a symlink, even inside the release."""
	root = _publisher_tree(tmp_path)
	page = root / "generated" / "releases" / REPORT_DATE / "blog" / "2026" / "08" / "26" / "durable-boundaries" / "index.html"
	target = root / "elsewhere.html"
	target.write_text(REPORT_DATE, encoding="utf-8")
	page.unlink()
	page.symlink_to(target)

	with pytest.raises(RuntimeError, match="symlinks"):
		daily_blog.publisher.verify_published_page(str(root), _receipt(root))


#============================================
def test_verify_published_page_rejects_a_generic_date_page(tmp_path: pathlib.Path) -> None:
	"""A date marker alone cannot stand in for the reader-visible selected article."""
	root = _publisher_tree(tmp_path)
	page = root / "generated" / "releases" / REPORT_DATE / "blog" / "2026" / "08" / "26" / "durable-boundaries" / "index.html"
	page.write_text(f"<html><main>{REPORT_DATE}</main></html>", encoding="utf-8")

	with pytest.raises(RuntimeError, match="article surface"):
		daily_blog.publisher.verify_published_page(str(root), _receipt(root))


#============================================
@pytest.mark.parametrize("datetime_value", ["2026-08-25T00:00:00+00:00", "not-a-date"])
def test_verify_published_page_rejects_a_wrong_semantic_date(
	tmp_path: pathlib.Path, datetime_value: str,
) -> None:
	"""The stable machine-readable page date must bind to the requested report date."""
	root = _publisher_tree(tmp_path)
	page = root / "generated" / "releases" / REPORT_DATE / "blog" / "2026" / "08" / "26" / "durable-boundaries" / "index.html"
	page.write_text(
		f"<html><main><time datetime='{datetime_value}'>August 26, 2026</time>"
		"<article class='md-content__inner md-typeset'><h1>Durable Boundaries</h1>"
		"<p>A grounded maker note.</p></article></main></html>",
		encoding="utf-8",
	)

	with pytest.raises(RuntimeError, match="semantic date"):
		daily_blog.publisher.verify_published_page(str(root), _receipt(root))


#============================================
@pytest.mark.parametrize("rendered", [
	f"<html><mainland><h1>Durable Boundaries</h1>{REPORT_DATE}</mainland></html>",
	f"<html><main><h1>Other</h1>{REPORT_DATE}</main><h1>Durable Boundaries</h1></html>",
	f"<html><main><h1>Durable Boundaries</h1>{REPORT_DATE}</main><main></main></html>",
	f"<html><main><h1>Durable Boundaries</h1><h1>Other</h1>{REPORT_DATE}</main></html>",
	f"<html><main data-title='Durable Boundaries'>{REPORT_DATE}<!-- <h1>Durable Boundaries</h1> --></main></html>",
	f"<html><main><script>Durable Boundaries {REPORT_DATE}</script></main></html>",
])
def test_verify_published_page_rejects_nonvisible_or_ambiguous_article_surfaces(
	tmp_path: pathlib.Path, rendered: str,
) -> None:
	"""Tag-like text, attributes, scripts, and duplicate surfaces cannot satisfy verification."""
	root = _publisher_tree(tmp_path)
	page = root / "generated" / "releases" / REPORT_DATE / "blog" / "2026" / "08" / "26" / "durable-boundaries" / "index.html"
	page.write_text(rendered, encoding="utf-8")

	with pytest.raises(RuntimeError, match="page_verification"):
		daily_blog.publisher.verify_published_page(str(root), _receipt(root))


#============================================
def test_verify_published_page_rejects_a_split_article_token(
	tmp_path: pathlib.Path,
) -> None:
	"""A structurally different article token cannot impersonate committed source text."""
	root = _publisher_tree(tmp_path)
	page = root / "generated" / "releases" / REPORT_DATE / "blog" / "2026" / "08" / "26" / "durable-boundaries" / "index.html"
	page.write_text(
		"<html><main><time datetime='2026-08-26'>August 26, 2026</time>"
		"<article class='md-content__inner md-typeset'>"
		"<h1> Durable <em>Boundaries</em> </h1><p>A grounded maker note.</p>"
		"</article></main></html>",
		encoding="utf-8",
	)

	with pytest.raises(RuntimeError, match="installed article body"):
		daily_blog.publisher.verify_published_page(str(root), _receipt(root))


#============================================
def test_verify_published_page_ignores_mkdocs_headerlink_chrome(
	tmp_path: pathlib.Path,
) -> None:
	"""MkDocs' visible permanent-link glyph is navigation chrome, not post-title text."""
	root = _publisher_tree(tmp_path)
	page = root / "generated" / "releases" / REPORT_DATE / "blog" / "2026" / "08" / "26" / "durable-boundaries" / "index.html"
	page.write_text(
		"<html><main><time datetime='2026-08-26T00:00:00Z'>August 26, 2026</time>"
		"<article class='md-content__inner md-typeset'>"
		"<h1 id='durable-boundaries'>Durable Boundaries"
		"<a class='headerlink' href='#durable-boundaries' title='Permanent link'>&para;</a>"
		"</h1><p>A grounded maker note.</p></article></main></html>",
		encoding="utf-8",
	)

	result = daily_blog.publisher.verify_published_page(str(root), _receipt(root))

	assert result["report_date"] == REPORT_DATE


#============================================
def test_verify_published_page_requires_the_served_pointer_for_its_date(
	tmp_path: pathlib.Path,
) -> None:
	"""A complete dated build is insufficient unless the publisher serves that release."""
	root = _publisher_tree(tmp_path)
	(root / "site").unlink()
	(root / "site").symlink_to("generated/releases/not-the-requested-date")

	with pytest.raises(RuntimeError, match="site pointer"):
		daily_blog.publisher.verify_published_page(str(root), _receipt(root))


#============================================
def test_committed_receipt_rejects_a_self_reported_bundle_digest(
	tmp_path: pathlib.Path,
) -> None:
	"""An archive manifest cannot substitute a false checksum for its own content."""
	root = _publisher_tree(tmp_path)
	bundle_path = root / "data" / "publication_bundles" / REPORT_DATE / "bundle.json"
	bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
	bundle["post"]["artifact_id"] = "artifact-ffffffffffffffffffffffff"
	bundle_path.write_text(json.dumps(bundle, sort_keys=True), encoding="utf-8")

	with pytest.raises(RuntimeError, match="archive bundle"):
		daily_blog.publisher._committed_receipt(str(root), {
			"status": "imported", "bundle_sha256": _bundle_sha256(root), "report_date": REPORT_DATE,
		})


#============================================
@pytest.mark.parametrize("mutation", ["missing", "mismatch"])
def test_committed_receipt_requires_the_v5_record_artifact_binding(
	tmp_path: pathlib.Path, mutation: str,
) -> None:
	"""The publisher record and sealed bundle must name the same selected artifact."""
	root = _publisher_tree(tmp_path)
	record_path = root / "data" / "publications" / f"{REPORT_DATE}.json"
	record = json.loads(record_path.read_text(encoding="utf-8"))
	if mutation == "missing":
		del record["best_artifact_id"]
	else:
		record["best_artifact_id"] = "artifact-ffffffffffffffffffffffff"
	record_path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")

	with pytest.raises(RuntimeError, match="publication record"):
		daily_blog.publisher._committed_receipt(str(root), {
			"status": "imported", "bundle_sha256": _bundle_sha256(root), "report_date": REPORT_DATE,
		})


#============================================
def test_verify_published_page_rejects_a_symlinked_intermediate_directory(
	tmp_path: pathlib.Path,
) -> None:
	"""Descriptor-relative traversal rejects a substituted release-page directory."""
	root = _publisher_tree(tmp_path)
	receipt = _receipt(root)
	page_parent = root / "generated" / "releases" / REPORT_DATE / "blog" / "2026" / "08" / "26" / "durable-boundaries"
	page = page_parent / "index.html"
	replacement = root / "replacement"
	replacement.mkdir()
	(replacement / "index.html").write_text(
		f"<main>Durable Boundaries {REPORT_DATE}</main>", encoding="utf-8"
	)
	page.unlink()
	page_parent.rmdir()
	page_parent.symlink_to(replacement)

	with pytest.raises(RuntimeError, match="rendered page"):
		daily_blog.publisher.verify_published_page(str(root), receipt)


#============================================
def test_publish_and_verify_preserves_imported_artifacts_on_page_failure(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A page failure occurs after import and does not remove its committed artifacts."""
	root = _publisher_tree(tmp_path, include_page=False)
	receipt = _receipt(root)

	def imported(*_arguments: object, **_kwargs: object) -> dict:
		return receipt

	monkeypatch.setattr(daily_blog.publisher, "import_bundle", imported)
	with pytest.raises(RuntimeError, match="page_verification"):
		daily_blog.publisher.publish_and_verify(str(root), str(tmp_path / "bundle"))

	assert (root / "data" / "publication_bundles" / REPORT_DATE / "post.md").read_text(encoding="utf-8").startswith(POST)
	assert (root / "data" / "publications" / f"{REPORT_DATE}.json").is_file()

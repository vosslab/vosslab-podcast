"""Producer-side post-import publication verification tests."""

# Standard Library
import json
import pathlib
import subprocess

# PIP3 modules
import pytest

# local repo modules
import daily_blog.publication_contract
import daily_blog.io_utils
import daily_blog.publisher
import daily_blog.activation
import daily_blog.contracts
import daily_blog.prompt_registry
import daily_blog.editorial
import daily_blog.schema


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
	path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


#============================================
def _publisher_tree(tmp_path: pathlib.Path, *, include_page: bool = True) -> pathlib.Path:
	"""Create one coherent committed publisher tree without invoking its importer."""
	root = tmp_path / "publisher"
	(root / "scripts").mkdir(parents=True)
	(root / "scripts" / "import_publication_bundle.py").write_text("# importer\n", encoding="utf-8")
	post_path = root / "docs" / "blog" / "posts" / f"{REPORT_DATE}.md"
	post_path.parent.mkdir(parents=True)
	post_path.write_text(POST, encoding="utf-8")
	archive = root / "data" / "publication_bundles" / REPORT_DATE
	archive.mkdir(parents=True)
	(archive / "post.md").write_text(POST, encoding="utf-8")
	post_sha256 = daily_blog.io_utils.sha256_text(POST)
	contract = daily_blog.prompt_registry.active_contract()
	policy = daily_blog.prompt_registry.policy_for_contract(contract)
	prompt_contract = daily_blog.editorial.prompt_contract_identity(contract=contract)
	activation = daily_blog.activation.load_maker_activation().receipt
	bundle = {
		"bundle_sha256": "",
		"report_date": REPORT_DATE,
		"best_artifact_id": "artifact-0123456789abcdef01234567",
		"post": {
			"sha256": post_sha256,
			"artifact_id": "artifact-0123456789abcdef01234567",
		},
		"contracts": {
			"evidence_schema": daily_blog.schema.EVIDENCE_SCHEMA_VERSION,
			"editorial_projection_schema": daily_blog.schema.PROJECTION_SCHEMA_VERSION,
			"prompt_version": contract.prompt_version,
			"rubric_version": contract.rubric_version,
			"candidate_validation": {
				"name": policy.name, "version": policy.version, "sha256": policy.sha256(),
			},
		},
		"editorial_prompt_contract": prompt_contract,
		"maker_activation": {
			"activation_id": activation["activation_id"],
			"editorial_prompt_contract_sha256": activation["editorial_prompt_contract_sha256"],
		},
	}
	bundle["bundle_sha256"] = daily_blog.publication_contract.bundle_sha256(bundle)
	_write_json(archive / "bundle.json", bundle)
	_write_json(root / "data" / "publications" / f"{REPORT_DATE}.json", {
		"schema_version": "vosslab.daily-blog.publication.v4",
		"report_date": REPORT_DATE,
		"bundle_sha256": bundle["bundle_sha256"],
		"best_artifact_id": "artifact-0123456789abcdef01234567",
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
			f"<html><main><h1>Durable Boundaries</h1>{REPORT_DATE}</main></html>",
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

	def fake_run(*_arguments: object, **_kwargs: object) -> subprocess.CompletedProcess:
		return subprocess.CompletedProcess([], 0, json.dumps({
			"status": "imported", "bundle_sha256": _bundle_sha256(root), "report_date": REPORT_DATE,
		}), "")

	monkeypatch.setattr(daily_blog.publisher.subprocess, "run", fake_run)
	result = daily_blog.publisher.import_bundle(str(root), str(tmp_path / "bundle"))

	assert result["best_artifact_id"] == "artifact-0123456789abcdef01234567"
	assert result["rendered_page_path"].endswith("durable-boundaries/index.html")


#============================================
def test_import_rejects_a_partial_importer_receipt(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The producer does not accept a subprocess result missing the identity fields."""
	root = _publisher_tree(tmp_path)

	def fake_run(*_arguments: object, **_kwargs: object) -> subprocess.CompletedProcess:
		return subprocess.CompletedProcess([], 0, '{"status":"imported"}', "")

	monkeypatch.setattr(daily_blog.publisher.subprocess, "run", fake_run)
	with pytest.raises(RuntimeError, match="unsupported receipt"):
		daily_blog.publisher.import_bundle(str(root), str(tmp_path / "bundle"))


#============================================
def test_verify_published_page_binds_committed_content_and_page(
	tmp_path: pathlib.Path,
) -> None:
	"""Verification reads the expected physical page and returns its content identity."""
	root = _publisher_tree(tmp_path)
	result = daily_blog.publisher.verify_published_page(str(root), _receipt(root))

	assert result["rendered_page_sha256"] == daily_blog.io_utils.sha256_text(
		f"<html><main><h1>Durable Boundaries</h1>{REPORT_DATE}</main></html>"
	)


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
	assert post == POST.encode("utf-8")


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
def test_verify_published_page_normalizes_visible_nested_title_text(
	tmp_path: pathlib.Path,
) -> None:
	"""Visible nested inline markup retains the selected H1's normalized text identity."""
	root = _publisher_tree(tmp_path)
	page = root / "generated" / "releases" / REPORT_DATE / "blog" / "2026" / "08" / "26" / "durable-boundaries" / "index.html"
	page.write_text(
		f"<html><main><h1> Durable <em>Boundaries</em> </h1><p>{REPORT_DATE}</p></main></html>",
		encoding="utf-8",
	)

	result = daily_blog.publisher.verify_published_page(str(root), _receipt(root))

	assert result["report_date"] == REPORT_DATE


#============================================
def test_verify_published_page_ignores_mkdocs_headerlink_chrome(
	tmp_path: pathlib.Path,
) -> None:
	"""MkDocs' visible permanent-link glyph is navigation chrome, not post-title text."""
	root = _publisher_tree(tmp_path)
	page = root / "generated" / "releases" / REPORT_DATE / "blog" / "2026" / "08" / "26" / "durable-boundaries" / "index.html"
	page.write_text(
		"<html><main><article>"
		"<h1 id='durable-boundaries'>Durable Boundaries"
		"<a class='headerlink' href='#durable-boundaries' title='Permanent link'>&para;</a>"
		f"</h1><p>{REPORT_DATE}</p></article></main></html>",
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
def test_committed_receipt_requires_the_v4_record_artifact_binding(
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

	assert (root / "data" / "publication_bundles" / REPORT_DATE / "post.md").read_text(encoding="utf-8") == POST
	assert (root / "data" / "publications" / f"{REPORT_DATE}.json").is_file()

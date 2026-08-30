"""Invoke and independently verify a publisher-owned daily-blog import."""

# Standard Library
import contextlib
import datetime
import errno
import html.parser
import json
import os
import pathlib
import re
import stat
import subprocess
from collections.abc import Iterator

# local repo modules
import daily_blog.publication_contract
import daily_blog.io_utils


IMPORT_RECEIPT_SCHEMA_VERSION = "vosslab.daily-blog.import-receipt.v1"
PUBLISHER_PUBLICATION_RECORD_SCHEMA_VERSION = "vosslab.daily-blog.publication.v4"
PUBLISHER_PUBLICATION_RECORD_FIELDS = frozenset({
	"best_artifact_id", "bundle_sha256", "editorial_projection_manifest",
	"evidence_manifest", "generator_revision", "generator_run", "imported_at",
	"post_path", "report_date", "schema_version", "timezone",
})
IMPORT_STATUSES = frozenset({"idempotent", "imported", "replaced"})
IMPORT_RECEIPT_FIELDS = frozenset({
	"best_artifact_id", "bundle_sha256", "post_path", "post_sha256",
	"publication_record_path", "publication_record_sha256", "rendered_page_path",
	"report_date", "schema_version", "status",
})
MAX_RECORD_BYTES = 128 * 1024
MAX_POST_BYTES = 2 * 1024 * 1024
MAX_PAGE_BYTES = 8 * 1024 * 1024
MAX_ASSET_BYTES = 8 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class _RenderedPageParser(html.parser.HTMLParser):
	"""Collect only visible article text from one bounded rendered HTML page."""

	#============================================
	def __init__(self) -> None:
		"""Initialize structural counters and visible-text capture state."""
		super().__init__(convert_charrefs=True)
		self.main_count = 0
		self.main_depth = 0
		self.hidden_depth = 0
		self.visible_h1_count = 0
		self.main_h1_titles: list[list[str]] = []
		self.active_h1: int | None = None
		self.headerlink_depth = 0
		self.main_text: list[str] = []
		self.structure_invalid = False

	#============================================
	def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
		"""Track only real HTML elements, never attribute strings or comments."""
		if tag in {"script", "style"}:
			self.hidden_depth += 1
			return
		if self.hidden_depth:
			return
		if tag == "main":
			self.main_count += 1
			self.main_depth += 1
			return
		if tag == "h1":
			self.visible_h1_count += 1
			if self.main_depth:
				self.main_h1_titles.append([])
				self.active_h1 = len(self.main_h1_titles) - 1
			return
		if tag == "a" and self.active_h1 is not None:
			classes = next((value for name, value in attrs if name == "class"), "")
			if isinstance(classes, str) and "headerlink" in classes.split():
				self.headerlink_depth += 1

	#============================================
	def handle_endtag(self, tag: str) -> None:
		"""Require balanced main and title surfaces before accepting their text."""
		if tag in {"script", "style"}:
			if not self.hidden_depth:
				self.structure_invalid = True
			else:
				self.hidden_depth -= 1
			return
		if self.hidden_depth:
			return
		if tag == "h1":
			self.active_h1 = None
			return
		if tag == "a" and self.headerlink_depth:
			self.headerlink_depth -= 1
			return
		if tag == "main":
			if not self.main_depth:
				self.structure_invalid = True
			else:
				self.main_depth -= 1

	#============================================
	def handle_data(self, data: str) -> None:
		"""Capture text only while inside a visible main element."""
		if self.hidden_depth or not self.main_depth:
			return
		self.main_text.append(data)
		if self.active_h1 is not None and not self.headerlink_depth:
			self.main_h1_titles[self.active_h1].append(data)


#============================================
def _normalized_visible_text(value: str) -> str:
	"""Normalize HTML text-node whitespace before comparing reader-visible text."""
	normalized = " ".join(value.split())
	return normalized


#============================================
def _validate_report_date(value: object) -> str:
	"""Return one canonical ISO report date without accepting path-shaped text."""
	if not isinstance(value, str):
		raise RuntimeError("Publisher receipt report date is invalid.")
	try:
		parsed = datetime.date.fromisoformat(value)
	except ValueError as error:
		raise RuntimeError("Publisher receipt report date is invalid.") from error
	if parsed.isoformat() != value:
		raise RuntimeError("Publisher receipt report date is invalid.")
	return value


#============================================
def _validate_relative_path(value: object, label: str) -> str:
	"""Return one normalized publisher-root-relative POSIX path."""
	if not isinstance(value, str) or not value:
		raise RuntimeError(f"Publisher receipt {label} path is invalid.")
	pure = pathlib.PurePosixPath(value)
	if pure.is_absolute() or not pure.parts or "." in pure.parts or ".." in pure.parts:
		raise RuntimeError(f"Publisher receipt {label} path is invalid.")
	path = pure.as_posix()
	if path != value:
		raise RuntimeError(f"Publisher receipt {label} path is invalid.")
	return path


#============================================
def _trusted_root(repository: str) -> str:
	"""Return one physical publisher root; a symlink cannot become a trust anchor."""
	root = os.path.abspath(repository)
	if not os.path.isdir(root) or os.path.islink(root) or os.path.realpath(root) != root:
		raise RuntimeError("Daily-blog publisher repository is unavailable.")
	return root


#============================================
def _directory_flags() -> int:
	"""Return no-follow flags for one directory descriptor."""
	return (
		os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
		| getattr(os, "O_DIRECTORY", 0)
	)


#============================================
def _file_flags() -> int:
	"""Return no-follow flags for one regular file descriptor."""
	return os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)


#============================================
def _open_directory_at(parent_fd: int | None, name: str, label: str) -> int:
	"""Open one direct physical directory without following a substitution."""
	kwargs = {} if parent_fd is None else {"dir_fd": parent_fd}
	try:
		descriptor = os.open(name, _directory_flags(), **kwargs)
	except OSError as error:
		raise RuntimeError(f"Publisher {label} path may not contain symlinks.") from error
	if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
		os.close(descriptor)
		raise RuntimeError(f"Publisher {label} parent is not a directory.")
	return descriptor


#============================================
def _read_regular_at(directory_fd: int, name: str, maximum_bytes: int, label: str) -> bytes:
	"""Read one bounded non-symlink regular direct child."""
	try:
		descriptor = os.open(name, _file_flags(), dir_fd=directory_fd)
	except OSError as error:
		if error.errno == errno.ELOOP:
			raise RuntimeError(f"Publisher {label} path may not contain symlinks.") from error
		raise RuntimeError(f"Publisher {label} file is unavailable.") from error
	try:
		metadata = os.fstat(descriptor)
		if not stat.S_ISREG(metadata.st_mode):
			raise RuntimeError(f"Publisher {label} file is not regular.")
		if metadata.st_size > maximum_bytes:
			raise RuntimeError(f"Publisher {label} file exceeds its bounded size.")
		chunks = []
		remaining = metadata.st_size
		while remaining:
			chunk = os.read(descriptor, remaining)
			if not chunk:
				raise RuntimeError(f"Publisher {label} file changed while it was read.")
			chunks.append(chunk)
			remaining -= len(chunk)
		return b"".join(chunks)
	finally:
		os.close(descriptor)


#============================================
class PublicationArchiveReader:
	"""Read one held publisher archive through its fixed public artifact surface."""

	_JSON_ARTIFACTS = frozenset({
		"bundle.json", "evidence.json", "repository_roster.json", "editorial_projection.json",
	})

	#============================================
	def __init__(self, archive_fd: int) -> None:
		self._archive_fd = archive_fd

	#============================================
	def read_json_artifact(self, name: str, label: str) -> bytes:
		"""Return one fixed bounded JSON archive artifact."""
		if name not in self._JSON_ARTIFACTS:
			raise RuntimeError("Publisher archive JSON artifact is unsupported.")
		return _read_regular_at(self._archive_fd, name, MAX_RECORD_BYTES, label)

	#============================================
	def read_post(self) -> bytes:
		"""Return the fixed bounded archived post."""
		return _read_regular_at(self._archive_fd, "post.md", MAX_POST_BYTES, "archived post")

	#============================================
	def read_asset(self, asset_path: str) -> bytes:
		"""Return one direct bounded asset from the archive-owned assets directory."""
		if not isinstance(asset_path, str) or not asset_path.startswith("assets/"):
			raise RuntimeError("Publisher archive asset path is invalid.")
		leaf = asset_path.removeprefix("assets/")
		if leaf in {"", ".", ".."} or os.path.basename(leaf) != leaf:
			raise RuntimeError("Publisher archive asset path is invalid.")
		assets_fd = _open_directory_at(self._archive_fd, "assets", "archive asset")
		try:
			return _read_regular_at(assets_fd, leaf, MAX_ASSET_BYTES, "archive asset")
		finally:
			os.close(assets_fd)


#============================================
@contextlib.contextmanager
def open_publication_archive(repository: str, report_date: str) -> Iterator[PublicationArchiveReader]:
	"""Hold one canonical publisher archive while reading its sealed artifacts."""
	root = _trusted_root(repository)
	date = _validate_report_date(report_date)
	root_fd = _open_directory_at(None, root, "repository")
	data_fd: int | None = None
	bundles_fd: int | None = None
	archive_fd: int | None = None
	try:
		data_fd = _open_directory_at(root_fd, "data", "archive")
		bundles_fd = _open_directory_at(data_fd, "publication_bundles", "archive")
		archive_fd = _open_directory_at(bundles_fd, date, "archive")
		yield PublicationArchiveReader(archive_fd)
	finally:
		if archive_fd is not None:
			os.close(archive_fd)
		if bundles_fd is not None:
			os.close(bundles_fd)
		if data_fd is not None:
			os.close(data_fd)
		os.close(root_fd)


#============================================
def _confined_file(root: str, relative_path: str, maximum_bytes: int, label: str) -> bytes:
	"""Read one bounded regular file below a physical root without symlink traversal."""
	relative = _validate_relative_path(relative_path, label)
	parts = pathlib.PurePosixPath(relative).parts
	try:
		directory = _open_directory_at(None, root, label)
	except RuntimeError as error:
		raise RuntimeError("Daily-blog publisher repository is unavailable.") from error
	try:
		for part in parts[:-1]:
			next_directory = _open_directory_at(directory, part, label)
			os.close(directory)
			directory = next_directory
		return _read_regular_at(directory, parts[-1], maximum_bytes, label)
	finally:
		os.close(directory)


#============================================
def _json_object(contents: bytes, label: str) -> dict:
	"""Decode one object-shaped UTF-8 receipt artifact."""
	try:
		value = json.loads(contents.decode("utf-8"))
	except (UnicodeDecodeError, json.JSONDecodeError) as error:
		raise RuntimeError(f"Publisher {label} is not valid JSON.") from error
	if not isinstance(value, dict):
		raise RuntimeError(f"Publisher {label} must be an object.")
	return value


#============================================
def _front_matter_value(post: bytes, key: str) -> str:
	"""Read one simple importer-validated scalar from post front matter."""
	try:
		text = post.decode("utf-8")
	except UnicodeDecodeError as error:
		raise RuntimeError("Publisher post is not UTF-8 text.") from error
	match = re.match(r"\A---\n(?P<front>.*?)\n---\n", text, flags=re.DOTALL)
	if match is None:
		raise RuntimeError("Publisher post front matter is unavailable.")
	values = {}
	for line in match.group("front").splitlines():
		if ": " in line:
			name, value = line.split(": ", 1)
			values[name] = value
	value = values.get(key)
	if not isinstance(value, str) or not value:
		raise RuntimeError(f"Publisher post front matter {key} is unavailable.")
	return value


#============================================
def _post_title(post: bytes) -> str:
	"""Return the sole reader-visible H1 required to appear on the rendered page."""
	try:
		text = post.decode("utf-8")
	except UnicodeDecodeError as error:
		raise RuntimeError("Publisher post is not UTF-8 text.") from error
	matches = re.findall(r"^# (?P<title>[^\n]+)$", text, flags=re.MULTILINE)
	if len(matches) != 1:
		raise RuntimeError("Publisher post title is unavailable.")
	title = _normalized_visible_text(matches[0])
	if not title:
		raise RuntimeError("Publisher post title is unavailable.")
	return title


#============================================
def _verify_rendered_article(page_text: str, title: str, report_date: str) -> None:
	"""Require one visible main/H1 surface bound to the selected post and date."""
	parser = _RenderedPageParser()
	parser.feed(page_text)
	parser.close()
	if (
		parser.structure_invalid
		or parser.hidden_depth
		or parser.main_depth
		or parser.main_count != 1
		or parser.visible_h1_count != 1
		or len(parser.main_h1_titles) != 1
	):
		raise RuntimeError("rendered page does not contain one unambiguous article surface")
	rendered_title = _normalized_visible_text("".join(parser.main_h1_titles[0]))
	if rendered_title != title:
		raise RuntimeError("rendered page title does not match the installed post")
	visible_main_text = _normalized_visible_text("".join(parser.main_text))
	if report_date not in visible_main_text:
		raise RuntimeError("rendered page does not contain its report date")


#============================================
def _verify_served_release(root: str, report_date: str) -> None:
	"""Require the publisher's served pointer to select this exact physical release."""
	release = os.path.join(root, "generated", "releases", report_date)
	site = os.path.join(root, "site")
	if not os.path.isdir(release) or os.path.islink(release):
		raise RuntimeError("publisher dated release is unavailable")
	if not os.path.islink(site):
		raise RuntimeError("publisher site pointer is unavailable")
	if os.path.realpath(site) != os.path.realpath(release):
		raise RuntimeError("publisher site pointer does not select the dated release")


#============================================
def _receipt_best_artifact(bundle: dict, post_sha256: str) -> str:
	"""Bind the sealed editorial artifact identity directly to installed post bytes."""
	artifact_id = bundle.get("best_artifact_id")
	post = bundle.get("post")
	if (
		not isinstance(artifact_id, str)
		or re.fullmatch(r"artifact-[0-9a-f]{24}", artifact_id) is None
		or not isinstance(post, dict)
		or post.get("artifact_id") != artifact_id
		or post.get("sha256") != post_sha256
	):
		raise RuntimeError("Publisher bundle selected artifact does not bind the installed post.")
	return artifact_id


#============================================
def validate_import_receipt(value: object, bundle_sha256: str, report_date: str) -> dict:
	"""Fail closed unless one complete structured importer receipt is coherent."""
	if not isinstance(value, dict) or set(value) != IMPORT_RECEIPT_FIELDS:
		raise RuntimeError("Daily-blog importer receipt has unsupported fields.")
	if value["schema_version"] != IMPORT_RECEIPT_SCHEMA_VERSION:
		raise RuntimeError("Daily-blog importer receipt schema is unsupported.")
	if value["status"] not in IMPORT_STATUSES:
		raise RuntimeError("Daily-blog importer receipt status is unsupported.")
	if value["bundle_sha256"] != bundle_sha256 or SHA256_RE.fullmatch(bundle_sha256) is None:
		raise RuntimeError("Daily-blog importer receipt bundle identity is inconsistent.")
	if _validate_report_date(value["report_date"]) != report_date:
		raise RuntimeError("Daily-blog importer receipt report date is inconsistent.")
	for key in ("publication_record_sha256", "post_sha256"):
		if not isinstance(value[key], str) or SHA256_RE.fullmatch(value[key]) is None:
			raise RuntimeError(f"Daily-blog importer receipt {key} is invalid.")
	if not isinstance(value["best_artifact_id"], str) or not value["best_artifact_id"]:
		raise RuntimeError("Daily-blog importer receipt selected artifact is invalid.")
	record_path = _validate_relative_path(value["publication_record_path"], "record")
	post_path = _validate_relative_path(value["post_path"], "post")
	page_path = _validate_relative_path(value["rendered_page_path"], "rendered page")
	if record_path != f"data/publications/{report_date}.json" or post_path != f"docs/blog/posts/{report_date}.md":
		raise RuntimeError("Daily-blog importer receipt publication paths are inconsistent.")
	if not page_path.startswith(f"generated/releases/{report_date}/blog/") or not page_path.endswith("/index.html"):
		raise RuntimeError("Daily-blog importer receipt rendered page path is inconsistent.")
	receipt = dict(value)
	return receipt


#============================================
def _committed_receipt(repository: str, importer_result: dict) -> dict:
	"""Construct a full receipt only from the committed publisher-owned tree."""
	root = _trusted_root(repository)
	report_date = _validate_report_date(importer_result["report_date"])
	bundle_sha256 = importer_result["bundle_sha256"]
	if not isinstance(bundle_sha256, str) or SHA256_RE.fullmatch(bundle_sha256) is None:
		raise RuntimeError("Daily-blog bundle importer returned an invalid bundle identity.")
	record_path = f"data/publications/{report_date}.json"
	post_path = f"docs/blog/posts/{report_date}.md"
	record_bytes = _confined_file(root, record_path, MAX_RECORD_BYTES, "publication record")
	post_bytes = _confined_file(root, post_path, MAX_POST_BYTES, "post")
	record = _json_object(record_bytes, "publication record")
	if (
		record.get("schema_version") != PUBLISHER_PUBLICATION_RECORD_SCHEMA_VERSION
		or set(record) != PUBLISHER_PUBLICATION_RECORD_FIELDS
	):
		raise RuntimeError("Publisher publication record schema is unsupported.")
	if record.get("report_date") != report_date or record.get("bundle_sha256") != bundle_sha256:
		raise RuntimeError("Publisher publication record does not bind the imported bundle.")
	if record.get("post_path") != post_path:
		raise RuntimeError("Publisher publication record post path is inconsistent.")
	archive_post = _confined_file(root, f"data/publication_bundles/{report_date}/post.md", MAX_POST_BYTES, "archived post")
	if archive_post != post_bytes:
		raise RuntimeError("Publisher archived post does not match the installed post.")
	bundle = _json_object(_confined_file(root, f"data/publication_bundles/{report_date}/bundle.json", MAX_RECORD_BYTES, "bundle"), "bundle")
	if (
		bundle.get("bundle_sha256") != bundle_sha256
		or daily_blog.publication_contract.bundle_sha256(bundle) != bundle_sha256
		or bundle.get("report_date") != report_date
	):
		raise RuntimeError("Publisher archive bundle does not bind the importer receipt.")
	# The importer is deliberately independent of editorial owners, but it must
	# still reject a bundle whose sealed primitive policy/prompt/activation links
	# have been omitted or cross-bound incorrectly.
	daily_blog.publication_contract.validate_bundle_identity_fields(bundle)
	post_sha256 = daily_blog.io_utils.sha256_bytes(post_bytes)
	post_manifest = bundle.get("post")
	if not isinstance(post_manifest, dict) or post_manifest.get("sha256") != post_sha256:
		raise RuntimeError("Publisher bundle post checksum does not bind the installed post.")
	best_artifact_id = _receipt_best_artifact(bundle, post_sha256)
	if record.get("best_artifact_id") != best_artifact_id:
		raise RuntimeError("Publisher publication record selected artifact is inconsistent.")
	slug = _front_matter_value(post_bytes, "slug")
	if SLUG_RE.fullmatch(slug) is None or _front_matter_value(post_bytes, "date") != report_date:
		raise RuntimeError("Publisher post does not describe the requested dated page.")
	year, month, day = report_date.split("-")
	rendered_page_path = f"generated/releases/{report_date}/blog/{year}/{month}/{day}/{slug}/index.html"
	receipt = {
		"schema_version": IMPORT_RECEIPT_SCHEMA_VERSION,
		"status": importer_result["status"], "bundle_sha256": bundle_sha256,
		"report_date": report_date, "publication_record_path": record_path,
		"publication_record_sha256": daily_blog.io_utils.sha256_bytes(record_bytes),
		"post_path": post_path, "post_sha256": post_sha256,
		"rendered_page_path": rendered_page_path,
		"best_artifact_id": best_artifact_id,
	}
	validated = validate_import_receipt(receipt, bundle_sha256, report_date)
	return validated


#============================================
def import_bundle(daily_blog_repository: str, bundle_path: str, *, replace_existing: bool = False) -> dict:
	"""Run the publisher transaction and return a receipt of committed artifacts."""
	repository = _trusted_root(daily_blog_repository)
	if not os.path.isfile(os.path.join(repository, "scripts", "import_publication_bundle.py")):
		raise RuntimeError("Daily-blog bundle importer is unavailable.")
	if type(replace_existing) is not bool:
		raise RuntimeError("Replace-existing state must be Boolean.")
	script = 'source source_me.sh && python3 scripts/import_publication_bundle.py --bundle "$1"'
	arguments = ["daily-blog-import", os.path.abspath(bundle_path)]
	if replace_existing:
		script += " --replace-existing"
	result = subprocess.run(["/bin/bash", "-lc", script, *arguments], cwd=repository, check=False,
		text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1200)
	if result.returncode:
		raise RuntimeError("Daily-blog bundle import failed.")
	try:
		importer_result = json.loads(result.stdout)
	except json.JSONDecodeError as error:
		raise RuntimeError("Daily-blog bundle importer returned invalid JSON.") from error
	if not isinstance(importer_result, dict) or set(importer_result) != {"status", "bundle_sha256", "report_date"}:
		raise RuntimeError("Daily-blog bundle importer returned an unsupported receipt.")
	if importer_result["status"] not in IMPORT_STATUSES:
		raise RuntimeError("Daily-blog bundle importer returned an unsupported status.")
	if importer_result["status"] == "replaced" and not replace_existing:
		raise RuntimeError("Daily-blog bundle importer replaced an unapproved report date.")
	receipt = _committed_receipt(repository, importer_result)
	return receipt


#============================================
def verify_published_page(daily_blog_repository: str, receipt: object) -> dict:
	"""Verify the committed dated page separately from the importer transaction."""
	if not isinstance(receipt, dict):
		raise RuntimeError("page_verification: importer receipt must be an object.")
	try:
		validated = validate_import_receipt(receipt, receipt["bundle_sha256"], receipt["report_date"])
		root = _trusted_root(daily_blog_repository)
		record = _confined_file(root, validated["publication_record_path"], MAX_RECORD_BYTES, "publication record")
		if daily_blog.io_utils.sha256_bytes(record) != validated["publication_record_sha256"]:
			raise RuntimeError("publication record changed after import")
		post = _confined_file(root, validated["post_path"], MAX_POST_BYTES, "post")
		if daily_blog.io_utils.sha256_bytes(post) != validated["post_sha256"]:
			raise RuntimeError("installed post changed after import")
		_verify_served_release(root, validated["report_date"])
		page = _confined_file(root, validated["rendered_page_path"], MAX_PAGE_BYTES, "rendered page")
		try:
			page_text = page.decode("utf-8")
		except UnicodeDecodeError as error:
			raise RuntimeError("rendered page is not UTF-8 text") from error
		_verify_rendered_article(page_text, _post_title(post), validated["report_date"])
	except RuntimeError as error:
		raise RuntimeError(f"page_verification: {error}") from error
	result = dict(validated)
	result["rendered_page_sha256"] = daily_blog.io_utils.sha256_bytes(page)
	return result


#============================================
def publish_and_verify(daily_blog_repository: str, bundle_path: str, *, replace_existing: bool = False) -> dict:
	"""Import first, then verify the reader-visible page in a separate phase."""
	receipt = import_bundle(daily_blog_repository, bundle_path, replace_existing=replace_existing)
	verified = verify_published_page(daily_blog_repository, receipt)
	return verified

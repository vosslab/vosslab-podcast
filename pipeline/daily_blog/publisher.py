"""Invoke and independently verify a publisher-owned daily-blog import."""

# Standard Library
import datetime
import errno
import html.parser
import json
import os
import pathlib
import posixpath
import re
import stat
import subprocess
import urllib.parse

# local repo modules
import daily_blog.publication_contract
import daily_blog.publication_storage
import daily_blog.publisher_contract
import daily_blog.io_utils
import daily_blog.publication_article_projection
import daily_blog.repository_contracts
import daily_blog.schema
import daily_blog.publication_surface_contract


IMPORT_RECEIPT_SCHEMA_VERSION = "vosslab.daily-blog.import-receipt.v3"
IMPORT_STATUSES = frozenset({"idempotent", "imported", "replaced"})
IMPORT_RECEIPT_FIELDS = frozenset({
	"article_body_sha256", "assets", "best_artifact_id", "bundle_sha256", "post_path", "post_sha256",
	"rendered_page_path",
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
		self.main_datetimes: list[str] = []
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
		if tag == "time" and self.main_depth:
			value = next((value for name, value in attrs if name == "datetime"), None)
			if isinstance(value, str) and value:
				self.main_datetimes.append(value)
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
class _RenderedArticleImageParser(html.parser.HTMLParser):
	"""Collect image sources from exactly the Material reader article surface."""

	#============================================
	def __init__(self) -> None:
		"""Initialize article-scoped image collection with structural tracking."""
		super().__init__(convert_charrefs=True)
		self._candidates: list[list[str]] = []
		self._active: list[tuple[int, list[str]]] = []
		self._depth = 0

	#============================================
	def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
		"""Record image sources only beneath a recognized reader article."""
		attributes = {name.lower(): value for name, value in attrs if value is not None}
		if tag == "img":
			source = attributes.get("src")
			if isinstance(source, str) and source:
				for _start_depth, images in self._active:
					images.append(source)
		if tag in daily_blog.publication_article_projection.VOID_TAGS:
			return
		self._depth += 1
		if tag == "article" and (
			daily_blog.publication_article_projection.ARTICLE_CLASS_TOKENS
			<= set(attributes.get("class", "").split())
		):
			images: list[str] = []
			self._candidates.append(images)
			self._active.append((self._depth, images))

	#============================================
	def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
		"""Apply normal source collection to XML-style HTML elements."""
		self.handle_starttag(tag, attrs)
		if tag not in daily_blog.publication_article_projection.VOID_TAGS:
			self.handle_endtag(tag)

	#============================================
	def handle_endtag(self, _tag: str) -> None:
		"""Retire article collectors without allowing sibling images to leak in."""
		if self._depth <= 0:
			raise RuntimeError("Rendered article HTML is structurally invalid.")
		self._active = [(depth, images) for depth, images in self._active if depth != self._depth]
		self._depth -= 1

	#============================================
	def article_images(self) -> tuple[str, ...]:
		"""Return sources from one complete, unambiguous reader article."""
		if self._active or self._depth:
			raise RuntimeError("Rendered article HTML is structurally incomplete.")
		if len(self._candidates) != 1:
			raise RuntimeError("rendered page does not contain one unambiguous article surface")
		return tuple(self._candidates[0])


#============================================
def _normalized_visible_text(value: str) -> str:
	"""Normalize HTML text-node whitespace before comparing reader-visible text."""
	normalized = " ".join(value.split())
	return normalized


#============================================
def _datetime_matches_report_date(value: str, report_date: str) -> bool:
	"""Return whether one semantic HTML datetime names the report calendar date."""
	try:
		parsed = datetime.datetime.fromisoformat(value)
	except ValueError:
		try:
			return datetime.date.fromisoformat(value).isoformat() == report_date
		except ValueError:
			return False
	return parsed.date().isoformat() == report_date


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
	if not any(
		_datetime_matches_report_date(value, report_date) for value in parser.main_datetimes
	):
		raise RuntimeError("rendered page semantic date does not match its report date")


#============================================
def _normalized_rendered_image_path(value: str, page_path: str) -> str:
	"""Resolve one rendered image source against its dated reader page."""
	if type(value) is not str or not value:
		raise RuntimeError("rendered article image source is invalid")
	parsed = urllib.parse.urlsplit(value)
	if parsed.scheme or parsed.netloc:
		raise RuntimeError("rendered article image source is not a local publication asset")
	path = urllib.parse.unquote(parsed.path)
	if not path or "\x00" in path or "\\" in path:
		raise RuntimeError("rendered article image source is invalid")
	# ASVS 5.3.2: MkDocs may emit a deep relative URL for a source asset that is
	# stored beside the dated Markdown. Resolve it before comparing authorities.
	page_url = "/" + page_path.removeprefix("generated/releases/").split("/", 1)[1]
	normalized = posixpath.normpath(urllib.parse.urljoin(page_url, path))
	return normalized


#============================================
def _verify_rendered_article_images(
	page_text: str, allowed_image_paths: tuple[str, ...], page_path: str,
) -> None:
	"""Require every reader-visible article image to remain surface-authorized."""
	if type(allowed_image_paths) is not tuple or any(type(path) is not str for path in allowed_image_paths):
		raise RuntimeError("publication surface image authority is invalid")
	allowed = {posixpath.normpath("/" + path) for path in allowed_image_paths}
	parser = _RenderedArticleImageParser()
	parser.feed(page_text)
	parser.close()
	for source in parser.article_images():
		if _normalized_rendered_image_path(source, page_path) not in allowed:
			raise RuntimeError("rendered article image is outside the publication surface")


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
	for key in ("article_body_sha256", "post_sha256"):
		if not isinstance(value[key], str) or SHA256_RE.fullmatch(value[key]) is None:
			raise RuntimeError(f"Daily-blog importer receipt {key} is invalid.")
	if not isinstance(value["best_artifact_id"], str) or not value["best_artifact_id"]:
		raise RuntimeError("Daily-blog importer receipt selected artifact is invalid.")
	post_path = _validate_relative_path(value["post_path"], "post")
	page_path = _validate_relative_path(value["rendered_page_path"], "rendered page")
	if post_path != f"docs/blog/posts/{report_date}.md":
		raise RuntimeError("Daily-blog importer receipt publication paths are inconsistent.")
	if not page_path.startswith(f"generated/releases/{report_date}/blog/") or not page_path.endswith("/index.html"):
		raise RuntimeError("Daily-blog importer receipt rendered page path is inconsistent.")
	assets = value["assets"]
	if not isinstance(assets, list):
		raise RuntimeError("Daily-blog importer receipt assets are invalid.")
	validated_assets = []
	for asset in assets:
		if not isinstance(asset, dict) or set(asset) != {"path", "publish_path", "sha256"}:
			raise RuntimeError("Daily-blog importer receipt assets are invalid.")
		path = _validate_relative_path(asset["path"], "asset")
		publish_path = asset["publish_path"]
		if (
			path != f"docs/blog/posts/{report_date}/{pathlib.PurePosixPath(path).name}"
			or type(publish_path) is not str
			or not publish_path.startswith(f"{report_date}/")
			or pathlib.PurePosixPath(publish_path).name != pathlib.PurePosixPath(path).name
			or not isinstance(asset["sha256"], str)
			or SHA256_RE.fullmatch(asset["sha256"]) is None
		):
			raise RuntimeError("Daily-blog importer receipt assets are invalid.")
		validated_assets.append(dict(asset))
	if validated_assets != sorted(validated_assets, key=lambda item: item["path"]):
		raise RuntimeError("Daily-blog importer receipt assets are invalid.")
	receipt = dict(value)
	receipt["assets"] = validated_assets
	return receipt


#============================================
#============================================
def _transfer_entry(transfer: daily_blog.publication_contract.SealedBundleTransfer, path: str) -> bytes:
	"""Return one already-sealed transfer member without reopening producer storage."""
	for entry in transfer.entries:
		if entry.path == path:
			return entry.contents
	raise RuntimeError(f"Sealed publication transfer is missing {path}.")


#============================================
def _delivered_receipt(
	repository: str, importer_result: dict,
	transfer: daily_blog.publication_contract.SealedBundleTransfer,
) -> dict:
	"""Bind the importer result to exact installed bytes from the sealed transfer."""
	root = _trusted_root(repository)
	report_date = transfer.report_date
	bundle = _json_object(_transfer_entry(transfer, "bundle.json"), "bundle manifest")
	if (
		importer_result["report_date"] != report_date
		or importer_result["bundle_sha256"] != transfer.bundle_sha256
		or bundle.get("report_date") != report_date
		or bundle.get("bundle_sha256") != transfer.bundle_sha256
	):
		raise RuntimeError("Publisher result does not bind the sealed publication transfer.")
	post_path = f"docs/blog/posts/{report_date}.md"
	# ASVS 5.3.2: code-owned date and asset identities select confined renderer
	# destinations; exact byte comparison proves delivery without trusting paths.
	post_bytes = _confined_file(root, post_path, MAX_POST_BYTES, "post")
	expected_post = _transfer_entry(transfer, "post.md")
	if post_bytes != expected_post:
		raise RuntimeError("Publisher installed post does not match the sealed transfer.")
	post_sha256 = daily_blog.io_utils.sha256_bytes(post_bytes)
	best_artifact_id = _receipt_best_artifact(bundle, post_sha256)
	assets_value = bundle.get("assets")
	if not isinstance(assets_value, list):
		raise RuntimeError("Publisher bundle assets manifest is invalid.")
	assets = []
	for item in assets_value:
		if not isinstance(item, dict):
			raise RuntimeError("Publisher bundle assets manifest is invalid.")
		bundle_path = daily_blog.schema.validate_bundle_asset_path(item.get("path"))
		name = pathlib.PurePosixPath(bundle_path).name
		installed_path = f"docs/blog/posts/{report_date}/{name}"
		contents = _confined_file(root, installed_path, MAX_ASSET_BYTES, "publication asset")
		expected = _transfer_entry(transfer, bundle_path)
		if contents != expected or item.get("sha256") != daily_blog.io_utils.sha256_bytes(contents):
			raise RuntimeError("Publisher installed asset does not match the sealed transfer.")
		assets.append({
			"path": installed_path, "publish_path": item.get("publish_path"),
			"sha256": daily_blog.io_utils.sha256_bytes(contents),
		})
	try:
		mkdocs_config = _confined_file(
			root, "mkdocs.yml", MAX_RECORD_BYTES, "MkDocs configuration",
		).decode("utf-8")
		post_text = post_bytes.decode("utf-8")
	except UnicodeDecodeError as error:
		raise RuntimeError("Publisher publication source is not UTF-8 text.") from error
	article_projection = daily_blog.publication_article_projection.source_article_projection(
		post_text, mkdocs_config,
	)
	slug = _front_matter_value(post_bytes, "slug")
	if SLUG_RE.fullmatch(slug) is None or _front_matter_value(post_bytes, "date") != report_date:
		raise RuntimeError("Publisher post does not describe the requested dated page.")
	year, month, day = report_date.split("-")
	receipt = {
		"schema_version": IMPORT_RECEIPT_SCHEMA_VERSION,
		"status": importer_result["status"], "bundle_sha256": transfer.bundle_sha256,
		"report_date": report_date, "post_path": post_path, "post_sha256": post_sha256,
		"assets": sorted(assets, key=lambda item: item["path"]),
		"rendered_page_path": (
			f"generated/releases/{report_date}/blog/{year}/{month}/{day}/{slug}/index.html"
		),
		"best_artifact_id": best_artifact_id,
		"article_body_sha256": daily_blog.publication_article_projection.article_body_sha256(
			article_projection,
		),
	}
	return validate_import_receipt(receipt, transfer.bundle_sha256, report_date)


#============================================
def _publisher_stdout(
	repository: str,
	script: str,
	transfer: daily_blog.publication_contract.SealedBundleTransfer,
) -> bytes:
	"""Run one stdin-only publisher command and retain only typed safe failures."""
	# ASVS 2.3.1: trusted argv selects one operation; the sealed bytes travel
	# only over stdin, and arbitrary child diagnostics never cross this boundary.
	command = ["/bin/bash", "-lc", script, "daily-blog-import"]
	payload = transfer.to_bytes()
	try:
		result = subprocess.run(
			command, cwd=repository, check=False, input=payload,
			stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1200,
		)
	except subprocess.TimeoutExpired as error:
		raise daily_blog.publisher_contract.PublisherCommandError("publisher_timeout", "receive") from error
	except OSError as error:
		raise daily_blog.publisher_contract.PublisherCommandError("publisher_start_failure", "receive") from error
	if result.returncode:
		raise daily_blog.publisher_contract.parse_import_failure(result.stderr)
	stdout = result.stdout
	return stdout


#============================================
def import_bundle(
	daily_blog_repository: str,
	transfer: daily_blog.publication_contract.SealedBundleTransfer,
	*,
	replace_existing: bool = False,
) -> dict:
	"""Run the publisher transaction from one immutable producer byte snapshot."""
	repository = _trusted_root(daily_blog_repository)
	if not os.path.isfile(os.path.join(repository, "scripts", "import_publication_bundle.py")):
		raise RuntimeError("Daily-blog bundle importer is unavailable.")
	if type(replace_existing) is not bool:
		raise RuntimeError("Replace-existing state must be Boolean.")
	if type(transfer) is not daily_blog.publication_contract.SealedBundleTransfer:
		raise RuntimeError("Daily-blog bundle import requires one sealed bundle transfer.")
	script = "source source_me.sh && python3 scripts/import_publication_bundle.py --bundle-stdin"
	if replace_existing:
		script += " --replace-existing"
	stdout = _publisher_stdout(repository, script, transfer)
	importer_result = daily_blog.publisher_contract.parse_import_result(
		stdout, report_date=transfer.report_date, bundle_sha256=transfer.bundle_sha256,
	)
	if importer_result["status"] == "replaced" and not replace_existing:
		raise RuntimeError("Daily-blog bundle importer replaced an unapproved report date.")
	receipt = _delivered_receipt(repository, importer_result, transfer)
	return receipt


#============================================
def verify_published_page(daily_blog_repository: str, receipt: object) -> dict:
	"""Verify the committed dated page separately from the importer transaction."""
	if not isinstance(receipt, dict):
		raise RuntimeError("page_verification: importer receipt must be an object.")
	try:
		validated = validate_import_receipt(receipt, receipt["bundle_sha256"], receipt["report_date"])
		root = _trusted_root(daily_blog_repository)
		post = _confined_file(root, validated["post_path"], MAX_POST_BYTES, "post")
		if daily_blog.io_utils.sha256_bytes(post) != validated["post_sha256"]:
			raise RuntimeError("installed post changed after import")
		for asset in validated["assets"]:
			contents = _confined_file(root, asset["path"], MAX_ASSET_BYTES, "publication asset")
			if daily_blog.io_utils.sha256_bytes(contents) != asset["sha256"]:
				raise RuntimeError("installed publication asset changed after import")
		mkdocs_config = _confined_file(root, "mkdocs.yml", MAX_RECORD_BYTES, "MkDocs configuration")
		try:
			expected_projection = daily_blog.publication_article_projection.source_article_projection(
				post.decode("utf-8"), mkdocs_config.decode("utf-8"),
			)
		except UnicodeDecodeError as error:
			raise RuntimeError("installed publication source is not UTF-8 text") from error
		if daily_blog.publication_article_projection.article_body_sha256(expected_projection) != validated["article_body_sha256"]:
			raise RuntimeError("installed post body does not match the committed article digest")
		_verify_served_release(root, validated["report_date"])
		page = _confined_file(root, validated["rendered_page_path"], MAX_PAGE_BYTES, "rendered page")
		try:
			page_text = page.decode("utf-8")
		except UnicodeDecodeError as error:
			raise RuntimeError("rendered page is not UTF-8 text") from error
		_verify_rendered_article(page_text, _post_title(post), validated["report_date"])
		daily_blog.publication_article_projection.verify_rendered_article(
			page_text, expected_projection,
		)
		_verify_rendered_article_images(
			page_text, tuple(asset["publish_path"] for asset in validated["assets"]),
			validated["rendered_page_path"],
		)
	except RuntimeError as error:
		raise RuntimeError(f"page_verification: {error}") from error
	result = dict(validated)
	result["rendered_page_sha256"] = daily_blog.io_utils.sha256_bytes(page)
	return result


#============================================
def publish_and_verify(
	daily_blog_repository: str,
	transfer: daily_blog.publication_contract.SealedBundleTransfer,
	*,
	replace_existing: bool = False,
) -> dict:
	"""Import first, then verify the reader-visible page in a separate phase."""
	receipt = import_bundle(daily_blog_repository, transfer, replace_existing=replace_existing)
	verified = verify_published_page(daily_blog_repository, receipt)
	return verified

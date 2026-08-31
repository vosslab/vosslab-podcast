"""Canonical reader-body projections shared with the publisher contract."""

# Standard Library
import hashlib
import html
from html.parser import HTMLParser
import re

# PIP3 modules
import markdown
import yaml


ARTICLE_CLASS_TOKENS = frozenset({"md-content__inner", "md-typeset"})
HIDDEN_STYLE_RE = re.compile(r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", re.I)
PERMALINK_CLASS = "headerlink"
VOID_TAGS = frozenset({
	"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
	"param", "source", "track", "wbr",
})


#============================================
def _normalized_text(value: str) -> str:
	"""Return one whitespace-stable reader-visible text value."""
	return " ".join(html.unescape(value).split())


#============================================
def _attributes(pairs: list[tuple[str, str | None]]) -> dict[str, str]:
	"""Return lower-case HTML attributes without absent values."""
	return {name.lower(): value for name, value in pairs if value is not None}


#============================================
def _is_hidden(attributes: dict[str, str]) -> bool:
	"""Return whether an element and its descendants are reader-hidden."""
	if "hidden" in attributes or attributes.get("aria-hidden", "").lower() == "true":
		return True
	if {"hidden", "visually-hidden"} & set(attributes.get("class", "").split()):
		return True
	return HIDDEN_STYLE_RE.search(attributes.get("style", "")) is not None


#============================================
class _ProjectionParser(HTMLParser):
	"""Collect canonical visible reader tokens from an HTML fragment."""

	def __init__(self) -> None:
		super().__init__(convert_charrefs=True)
		self.tokens: list[str] = []
		# Depth counters make suppression inherit through every nested element.
		self._hidden_depth = 0
		self._suppressed_depth = 0
		self._code_depth = 0
		# Each non-void opening tag records exactly the counters it incremented.
		self._stack: list[tuple[bool, bool, bool]] = []

	def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
		attributes = _attributes(attrs)
		classes = set(attributes.get("class", "").split())
		hidden = self._hidden_depth > 0 or _is_hidden(attributes)
		suppressed = self._suppressed_depth > 0 or tag in {"script", "style"}
		permalink = tag == "a" and PERMALINK_CLASS in classes
		if tag not in VOID_TAGS:
			self._stack.append((hidden, suppressed or permalink, tag in {"code", "pre"}))
		if hidden:
			self._hidden_depth += 1
		if suppressed or permalink:
			self._suppressed_depth += 1
		if tag in {"code", "pre"}:
			self._code_depth += 1
		if tag == "img" and not hidden and not suppressed:
			# Alt text is the reader-visible representation of an otherwise void image.
			self.tokens.append(f"image:{_normalized_text(attributes.get('alt', ''))}")

	def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
		self.handle_starttag(tag, attrs)
		if tag not in VOID_TAGS:
			self.handle_endtag(tag)

	def handle_endtag(self, _tag: str) -> None:
		if not self._stack:
			raise RuntimeError("Rendered article HTML is structurally invalid.")
		# Restore exactly the state captured for this element instead of inferring it
		# from the closing tag, which keeps nested suppression state balanced.
		hidden, suppressed, code = self._stack.pop()
		if hidden:
			self._hidden_depth -= 1
		if suppressed:
			self._suppressed_depth -= 1
		if code:
			self._code_depth -= 1

	def handle_data(self, data: str) -> None:
		if self._hidden_depth or self._suppressed_depth:
			return
		text = _normalized_text(data)
		if text:
			self.tokens.append(f"{'code' if self._code_depth else 'text'}:{text}")

	def projection(self) -> str:
		"""Return ordered reader tokens after structural validation."""
		if self._stack:
			raise RuntimeError("Rendered article HTML is structurally incomplete.")
		return "\n".join(self.tokens)


#============================================
def _post_body(markdown_post: str) -> str:
	"""Return one Markdown post body after its required front matter."""
	if not markdown_post.startswith("---\n"):
		raise RuntimeError("Publication post must begin with front matter.")
	closing = markdown_post.find("\n---\n", len("---\n"))
	if closing < 0:
		raise RuntimeError("Publication post front matter is incomplete.")
	body = markdown_post[closing + len("\n---\n"):]
	if not body.strip():
		raise RuntimeError("Publication post body is empty.")
	return body


#============================================
def _markdown_extensions(config_text: str) -> tuple[list[str], dict[str, object]]:
	"""Load the publisher's MkDocs Markdown extension declarations exactly."""
	try:
		config = yaml.safe_load(config_text)
	except yaml.YAMLError as error:
		raise RuntimeError("Publisher MkDocs configuration is invalid.") from error
	if not isinstance(config, dict) or not isinstance(config.get("markdown_extensions", []), list):
		raise RuntimeError("Publisher MkDocs configuration is invalid.")
	extensions: list[str] = []
	extension_configs: dict[str, object] = {}
	for item in config["markdown_extensions"]:
		if isinstance(item, str):
			extensions.append(item)
			continue
		if not isinstance(item, dict) or len(item) != 1:
			raise RuntimeError("Publisher MkDocs Markdown extension declaration is invalid.")
		name, options = next(iter(item.items()))
		if not isinstance(name, str) or not isinstance(options, dict):
			raise RuntimeError("Publisher MkDocs Markdown extension declaration is invalid.")
		extensions.append(name)
		extension_configs[name] = options
	return extensions, extension_configs


#============================================
def source_article_projection(markdown_post: str, mkdocs_config: str) -> str:
	"""Render one staged post body with the publisher's actual extension set."""
	extensions, extension_configs = _markdown_extensions(mkdocs_config)
	rendered = markdown.Markdown(extensions=extensions, extension_configs=extension_configs).convert(
		_post_body(markdown_post)
	)
	parser = _ProjectionParser()
	parser.feed(rendered)
	parser.close()
	projection = parser.projection()
	if not projection:
		raise RuntimeError("Publication post has no reader-visible body projection.")
	return projection


#============================================
def article_body_sha256(projection: str) -> str:
	"""Return the receipt digest for one canonical reader projection."""
	if not projection:
		raise RuntimeError("Publication article projection is empty.")
	return hashlib.sha256(projection.encode("utf-8")).hexdigest()


#============================================
class _ArticleParser(HTMLParser):
	"""Extract projections from exactly the Material reader article surfaces."""

	def __init__(self) -> None:
		super().__init__(convert_charrefs=True)
		self._candidates: list[_ProjectionParser] = []
		# Active parsers receive only descendants of their matching article surface.
		self._active: list[tuple[int, _ProjectionParser]] = []
		self._depth = 0

	def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
		# Forward first so a newly recognized article does not include its own shell.
		for _start_depth, parser in self._active:
			parser.handle_starttag(tag, attrs)
		if tag in VOID_TAGS:
			return
		self._depth += 1
		if tag == "article" and ARTICLE_CLASS_TOKENS <= set(_attributes(attrs).get("class", "").split()):
			# The depth marker excludes the article wrapper while retaining all descendants.
			parser = _ProjectionParser()
			self._candidates.append(parser)
			self._active.append((self._depth, parser))

	def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
		self.handle_starttag(tag, attrs)
		if tag not in VOID_TAGS:
			self.handle_endtag(tag)

	def handle_endtag(self, tag: str) -> None:
		# Only nested closes belong to an active article; its own close retires it below.
		for start_depth, parser in self._active:
			if start_depth < self._depth:
				parser.handle_endtag(tag)
		# Retire at the opening depth before decrementing to avoid forwarding siblings.
		self._active = [(depth, parser) for depth, parser in self._active if depth != self._depth]
		self._depth -= 1

	def handle_data(self, data: str) -> None:
		for _start_depth, parser in self._active:
			parser.handle_data(data)

	def projections(self) -> list[str]:
		"""Return projections only after complete, balanced document parsing."""
		if self._active or self._depth:
			raise RuntimeError("Built page HTML is structurally incomplete.")
		return [candidate.projection() for candidate in self._candidates]


#============================================
def _contains_projection(actual: str, expected: str) -> bool:
	"""Return whether every source token appears in reader order."""
	position = 0
	actual_tokens = actual.splitlines()
	for expected_token in expected.splitlines():
		while position < len(actual_tokens) and actual_tokens[position] != expected_token:
			position += 1
		if position == len(actual_tokens):
			return False
		position += 1
	return True


#============================================
def verify_rendered_article(page_text: str, expected_projection: str) -> None:
	"""Require one Material article surface retaining the full source projection."""
	parser = _ArticleParser()
	parser.feed(page_text)
	parser.close()
	projections = parser.projections()
	if len(projections) != 1:
		raise RuntimeError("rendered page does not contain one unambiguous article surface")
	if not _contains_projection(projections[0], expected_projection):
		raise RuntimeError("rendered page does not retain the installed article body")

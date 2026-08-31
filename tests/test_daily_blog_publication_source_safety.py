"""Durable source-safety checks at the producer publication boundary."""

# PIP3 modules
import pytest

# local repo modules
import daily_blog.publication_source_safety


#============================================
@pytest.mark.parametrize("case", daily_blog.publication_source_safety.CANONICAL_VECTOR["cases"])
def test_canonical_policy_cases_execute_at_the_producer_boundary(case: dict) -> None:
	"""Every behavior named in the sealed cross-repository corpus remains executable."""
	assert bool(daily_blog.publication_source_safety.validate_post_source(
		case["post"], daily_blog.publication_source_safety.CANONICAL_VECTOR["approved_paths"],
	)) is not case["valid"]

#============================================
def test_source_safety_rejects_active_markup_and_disguised_targets() -> None:
	"""Only approved reader-visible publication constructs cross the trust boundary."""
	post = "---\ndate: 2026-08-30\n---\n# Note\n\n[bad](https&#58;//evil.example) <script>x</script>\n"

	issues = daily_blog.publication_source_safety.validate_post_source(post, ())

	assert "unsafe_link" in issues
	assert "raw_html" in issues


#============================================
def test_source_safety_keeps_code_and_exact_screenshot_paths_inert_or_allowed() -> None:
	"""Attack-looking code cannot affect a post that otherwise uses one sealed asset."""
	post = "---\ndate: 2026-08-30\n---\n# Note\n\n![proof](../../assets/publications/2026-08-30/proof.png) `https://evil.example <script>`\n"

	assert daily_blog.publication_source_safety.validate_post_source(
		post, ("../../assets/publications/2026-08-30/proof.png",),
	) == ()


#============================================
@pytest.mark.parametrize("body", (
	'# Title { onclick="alert(1)" }',
	'Paragraph.\n{ data-state="active" }',
	'![proof](assets/proof.png){ .proof }',
	'[GitHub](https://github.com/vosslab/project){ #source }',
))
def test_source_safety_rejects_spaced_attribute_lists(body: str) -> None:
	"""Each active attr_list form is rejected at the producer boundary."""
	issues = daily_blog.publication_source_safety.validate_post_source(
		f"---\ndate: 2026-08-30\n---\n{body}\n", ("assets/proof.png",),
	)
	assert "markdown_attribute_list" in issues


#============================================
def test_source_safety_keeps_brace_prose_and_code_inert() -> None:
	"""Ordinary braces and code examples do not become active attributes."""
	assert daily_blog.publication_source_safety.validate_post_source(
		"---\ndate: 2026-08-30\n---\n{a small set} ` { onclick=\"x\" } `\n", (),
	) == ()

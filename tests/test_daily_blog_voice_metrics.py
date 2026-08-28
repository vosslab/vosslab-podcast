"""Deterministic diagnostics describe narrative voice without judging it."""

# local repo modules
import daily_blog.evaluation


#============================================
def test_article_profile_ignores_nonvisible_markdown_and_i_o() -> None:
	"""Code, images, comments, and link targets cannot change visible voice diagnostics."""
	baseline = """---
date: 2026-08-23
---

# Visible parser work

I changed the parser. Did it help?
"""
	decorated = baseline.replace(
		"I changed the parser. Did it help?",
		"""I changed the [parser](https://example.test/a_(nested)_target \"why) hidden?\"). Did it help?

![diagram](https://example.test/image?ignored)

`I/O is not a maker action?`

<!-- I/O has a question? -->

```
I/O changed the parser? [hidden](https://example.test/hidden)
```
""",
	)
	baseline_profile = daily_blog.evaluation.article_profile(baseline)
	decorated_profile = daily_blog.evaluation.article_profile(decorated)

	assert (
		baseline_profile["narrative_words"] == decorated_profile["narrative_words"]
		and baseline_profile["question_count"] == decorated_profile["question_count"]
		and baseline_profile["narrative_prose_block_count"]
		== decorated_profile["narrative_prose_block_count"]
	)


#============================================
def test_article_profile_is_invariant_to_source_line_wrapping() -> None:
	"""A reader-visible short paragraph stays the same when its Markdown source wraps."""
	base = """---
date: 2026-08-23
---

# A tiny discovery

That was surprisingly satisfying.
"""
	wrapped = base.replace("That was surprisingly satisfying.", "That was surprisingly\nsatisfying.")

	base_profile = daily_blog.evaluation.article_profile(base)
	wrapped_profile = daily_blog.evaluation.article_profile(wrapped)

	assert base_profile["narrative_words"] == wrapped_profile["narrative_words"]


#============================================
def test_article_profile_distinguishes_first_person_possessives_from_i_o() -> None:
	"""Legacy first-person presence keeps possessives while excluding technical I/O."""
	io_post = """---
date: 2026-08-23
---

# I/O work

I/O monitoring changed after the build.
"""
	maker_post = io_post.replace("I/O monitoring changed after the build.", "My parser surprised me.")

	io_profile = daily_blog.evaluation.article_profile(io_post)
	maker_profile = daily_blog.evaluation.article_profile(maker_post)

	assert not io_profile["first_person"] and io_profile["first_person_sentence_count"] == 0
	assert maker_profile["first_person"] and maker_profile["first_person_sentence_count"] == 1


#============================================
def test_article_profile_handles_a_fully_empty_narrative() -> None:
	"""An empty narrative reports no reader-visible prose."""
	post = """---
date: 2026-08-23
---

# Empty day

<!-- more -->

<!-- nothing to measure -->

## Project coverage

Footer only.
"""

	profile = daily_blog.evaluation.article_profile(post)

	assert profile["narrative_words"] == 0

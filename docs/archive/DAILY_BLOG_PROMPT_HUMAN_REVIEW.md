# Daily-blog prompt human review

## Status

The active author, referee, repair, and rubric prompt prose remains unchanged during this review. This report separates the recent mechanical contract migration from future human-owned editorial changes.

## What changed from v2 to v3

The author prompt retained its editorial direction. Its changes were mechanical:

- `active_repositories` became `repositories`.
- The output contract gained `editorial_projection: editorial_projection.json`.
- Evidence references changed from the full packet to the bounded editorial projection.
- The obsolete `publication_quality: final` field disappeared.

The referee prompt retained the same comparison job. It now permits `NONE` only when neither candidate should publish and validates citations against the projection. The repair prompt changed its accepted winner values from `A` or `B` to `A`, `B`, or `NONE`. The rubric changed "evidence IDs" to "projected evidence IDs."

The v3 label therefore describes a software-envelope migration more than a new editorial voice. Combining those concepts under one version name made the change look like a broad prompt rewrite and made editorial provenance harder to reason about.

## Output diagnosis

The August 22 and August 23 posts are the positive references. They each organize the day around a single realization, use personal perspective and varied sentence rhythm, explain a meaningful trade-off, and end with a real unresolved question or current state.

The August 26 post has a thematic title, but its body is denser and more mechanical. It repeatedly bridges several repositories through abstract formulations, compresses many facts into each paragraph, and finishes with a mandatory repository-by-repository coverage section. The reader receives a technically coherent inventory rather than a lived account of the day.

The strongest causes are structural rather than the small v2-to-v3 wording changes:

1. The projection and validation contracts require every active repository to appear.
2. The author must simultaneously write a personal narrative and an exhaustive evidence ledger.
3. "First-person news-style" and "dated changelog entries as the primary account" bias the model toward formal reporting.
4. The rubric rewards completeness, factual fidelity, and cross-project synthesis more explicitly than personal voice, selectivity, surprise, uncertainty, or opinion.
5. The prompt contains no human-approved positive example, even though the August 22 and 23 posts already provide the desired voice.

Increasing the context limit would not fix this. It would provide more material for the model to catalogue. Deterministic bounded projection is still the correct context architecture; the editorial question is which facts belong in the narrative and which belong in a deterministic appendix.

## Recommended ownership boundary

Keep four concerns independent:

1. **Immutable evidence** - complete, lossless, and never rewritten for style.
2. **Editorial projection** - deterministic, bounded, provenance-preserving source material.
3. **Human-owned prompt edition** - exact author/referee/rubric prose reviewed as text by the human.
4. **Software envelope contract** - placeholders, schema fields, hashes, model routing, and output parsing owned by code.

A schema or envelope migration must not silently create a new editorial edition. Exact template hashes should continue to own cache identity.

## Human decisions before any prompt edit

The human should decide the exact text for these editorial questions:

- Whether the desired form is a personal engineering diary, a news-style account, or another named form.
- Whether selected excerpts from the August 22 and 23 posts should be included as positive examples.
- Whether the main narrative may deliberately omit minor repositories while a deterministic appendix preserves complete coverage.
- Whether the article should explicitly include a personal reaction, surprise, frustration, decision, trade-off, uncertainty, or open question when the evidence supports one.
- Whether the referee should reject an article whose paragraphs could be reordered into a repository changelog without changing its meaning.

## Safe evaluation protocol

1. Preserve the current prompt bytes as the baseline.
2. Have the human make one editorial change at a time.
3. Run the non-publishing shadow evaluator on fixed historical evidence for August 22 and August 23.
4. Save generated and reference posts side by side with exact prompt hashes.
5. Review title specificity, narrative selectivity, personal voice, sentence rhythm, reader interest, and factual fidelity.
6. Activate a prompt edition only after direct human approval of both the exact prompt text and representative outputs.

This protocol keeps agents useful for diagnosis, deterministic assembly, and experiment execution while leaving editorial wording and final taste with the human.

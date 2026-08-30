# Stage 4 rubric decision

## Status and outcome

Decision: reuse the frozen
[daily_blog_rubric_v4.md](../../../pipeline/prompts/daily_blog_rubric_v4.md) unchanged for Stage 4
repository-story comparison. The provisional narrower rubric does not become a production asset.

This applies M8's rule in the
[LAYERED_PODCAST_IMPROVE_PLAN.md](../../archive/LAYERED_PODCAST_IMPROVE_PLAN.md): select the rubric that
separates expected-strong and expected-weak stories more consistently; on a consistency tie, use
normalized 1--4 score separation. Both rubrics tied on consistency, while V4 had greater normalized
separation. The final frozen-V4 preference was not needed.

## Independent method

1. An independent reviewer received only the anonymous review input and two rubrics. It scored each
   complete pair in A/B and B/A order and wrote the blind score record without expected labels.
2. This decision read the completed blind score record and then the separate sealed expected-order
   mapping. It compared selected aliases with expected labels and did not rescore candidate prose.

This preserves the anonymous, position-independent review boundary in the
[daily_blog_prompt_authoring_guide.md](daily_blog_prompt_authoring_guide.md).

## Durable capture chain

All generated inputs below live under the ignored `output_blog_capture/` root; `.gitignore` entry
`/output*/` excludes this evidence from version control while the decision records its reproducible
identity. The main capture binds the blinded input and expected-order mapping. The blind score
record binds that input and both rubric bytes. This decision binds the capture-chain paths and exact
digests to the adoption outcome.

| Artifact | Relative path | Schema or identity | SHA-256 |
| --- | --- | --- | --- |
| Main candidate capture | `output_blog_capture/m8_stage4_rubric_decision/repository_story_candidates.json` | `vosslab.daily-blog.repository-story-candidates.v1` | `9d26ec2315acc8de11416e863ff979d343ef6bd38f3470ee1d10f058322d2d5a` |
| Blinded review input | `output_blog_capture/m8_stage4_rubric_decision/rubric_review_input.json` | `vosslab.daily-blog.repository-story-rubric-review-input.v1` | `03a806313697ad1ea62616e4a9eabf22ae7afc814d6e324055574fa0b83c35ff` |
| Expected-order mapping | `output_blog_capture/m8_stage4_rubric_decision/expected_order.json` | `vosslab.daily-blog.repository-story-expected-order.v1` | `e4f51f2ba8c45356a805a95ff9a94724ddb42169e94e52bdfaa70b66c5257eff` |
| Provisional narrow rubric | `output_blog_capture/m8_stage4_rubric_decision/provisional_narrow_story_rubric.md` | Markdown comparison input; 1--4 scale | `7dc01c285039f15db2a27d1db3751bd143b3d29d04ec2f3cd9cc170b04ad266f` |
| Blind score record | `output_blog_capture/m8_stage4_rubric_decision/blind_rubric_scores.json` | `vosslab.daily-blog.blind-rubric-scores.v1` | `d8f016055c3e55c1b24bdcace3df92e46ea660bc1fb480739c33c5974727d3a4` |
| Frozen V4 rubric | `pipeline/prompts/daily_blog_rubric_v4.md` | Markdown resource; 1--4 scale | `13636a8b18a530f8f89570409c79b123b461ec033bc2013a29a58febc84875c1` |

## Comparison result

| Rubric | Expected-order accuracy | Order consistency | Raw separation | Normalized separation |
| --- | --- | --- | --- | --- |
| Frozen V4 | 4/4 presentations; 2/2 pairs | 2/2 pairs | 1.9 | 0.63 |
| Provisional narrow | 4/4 presentations; 2/2 pairs | 2/2 pairs | 1.8 | 0.60 |

For both fixture repositories and both display orders, each rubric selected the alias labeled
`expected_strong`: `story-ad7f237ebd4e` for `vosslab/story-fixture-alpha` and
`story-fbda62df8c3e` for `vosslab/story-fixture-beta`.

The durable score record gives V4 raw scores of 4.0 and 2.1 for each strong/weak pair, producing a
1.9 raw separation. It gives the provisional narrow rubric 4.0 and 2.2, producing 1.8. On the
common 1--4 scale, raw separation divided by 3 is 0.633 (reported as 0.63) for V4 and 0.600
(reported as 0.60) for the provisional rubric.

## Operational consequence

Stage 4 uses the existing V4 rubric bytes and identity. No story-rubric resource is promoted,
registered, or added to the production prompt inventory. A later narrower rubric requires a new
versioned asset, a content identity, focused fixture evaluation, and reviewable approval as the
prompt authoring guide requires.

## Regeneration and validation

Regenerate the capture with:

```bash
source source_me.sh && python3 automation/run_repository_story_fixture.py \
  --output-root output_blog_capture/m8_stage4_rubric_decision \
  --copy-review-candidate-set
```

After regeneration, a new independent reviewer must rescore the blinded input without receiving
the expected-order mapping. Recompute all capture hashes, then repeat this decision comparison;
do not reuse the earlier score record as a score for changed candidate or rubric bytes.

The offline validator is `tests/e2e/e2e_stage4_rubric_decision.py`; it checks the sealed capture
chain, expected-order and order-balanced selections, decision bindings, and absence of a production
narrow rubric.

## Limits of this decision

The two deliberately contrasting pairs test only an export-handoff story and an HTML-renderer
verification story. They show separation on those fixed examples without display-order bias. They
do not establish general rubric superiority, production quality across repositories or dates, a
universal score threshold, or a fixed future replication count.

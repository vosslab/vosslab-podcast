# Stage 6 failure: root-cause fix guidance

## Scope

Apply this guidance to the Stage 6 failure in run `20260831T054505Z-efb371c559` for report date `2026-08-29`.

Preserve the approved prompt package unchanged. Keep the work inside the daily-blog pipeline and its existing Hermes route boundary. The goal is a durable integration fix: the evidence shown to complete-post agents and the evidence accepted by complete-post admission must be the same evidence authority.

## What the failed run proves

The run completed repository discovery, evidence acquisition, repository editorial, and Stage 5. Stage 6 then ended with `no_eligible_generation` and produced no Markdown post.

This was not a model-route outage:

- Stage 6 produced fifteen substantial writer, editor, and recovery candidates.
- Fourteen candidates omitted `vosslab/peptidyle-learning-engine`, matching the three-repository survivor set produced after that repository's editorial job ended with `implementation_defect`.
- Fourteen candidates used evidence IDs and screenshot paths supplied through the Stage 5/Stage 6 editorial context but absent from the separate admission projection.
- The admission layer therefore rejected material that the pipeline itself had supplied to the models.
- Most remaining issues were repairable body-policy findings such as citation density or compact project coverage.

Additional route attempts cannot resolve contradictory inputs. The same context/admission mismatch will continue rejecting otherwise useful generations.

## Current ownership seam

The current source already moves in the correct direction:

- `Stage6Input.context_packets` derives the packet set from `daily_outline.repositories`.
- `PublicationSurface` describes itself as the exact survivor-scoped evidence surface.
- `publication_workflow.py` builds a Stage 6 bounded evidence context from Stage 5 survivors.

One important divergence can still remain: agents read `BoundedEvidenceContext`, while admission checks `PublicationSurface.projection`. Both are independently derived and can select different excerpts or screenshots under their bounds. A candidate can therefore cite material visible in `Stage6Input.render_context()` and still fail as unknown or unsafe during `complete_post_eligibility()`.

## Required design correction

### 1. Use one Stage 6 evidence authority

Make one typed survivor-scoped value own all of the following:

- survivor repositories;
- survivor source packets;
- bounded model-visible excerpts;
- allowed evidence IDs;
- allowed screenshot publication paths;
- repository coverage expected from a complete post;
- mechanical admission and authored-body validation.

Derive the model context and validation view from this same value. Prefer a single projection with a bounded rendering method over two independently selected projections.

A useful invariant is:

> Every evidence ID and screenshot path exposed in the Stage 6 model context is accepted by Stage 6 admission, and every repository required by admission is present in the Stage 6 editorial scope.

### 2. Keep survivor scope consistent

When repository editorial produces three surviving repository stories, carry those same three repositories through Stage 5, Stage 6 context, body-policy coverage, recovery, and publication provenance. Record the omitted repository and its terminal category as degradation evidence.

When the contract requires recovery of the failed repository, complete that model-produced recovery before constructing Stage 5. Then include the recovered repository in both context and admission. Use one of these coherent states rather than prompting from three repositories while validating against four.

### 3. Separate hard provenance from repairable editorial policy

Keep these as hard eligibility boundaries:

- report-date and output ownership;
- packet and artifact provenance;
- evidence references belonging to the exact Stage 6 authority;
- screenshot paths belonging to that authority;
- structurally parseable complete-post output.

Feed explicit authored-body findings to the model editor and recovery rungs, including:

- first-person voice;
- thematic title and expected structure;
- excerpt marker;
- compact project coverage;
- paragraph or section citation density.

Retain mechanically grounded candidates as recovery inputs while those editorial paths run. Promote only an eligible result. If bounded model-produced recovery is exhausted, emit the diagnosed nonzero pipeline fault required by the plan.

### 4. Preserve concrete diagnostics

Replace the aggregate-only `ineligible_generation` observation with bounded categorical counts derived from actual admission findings, for example:

- `unknown_evidence_reference`;
- `unapproved_screenshot_path`;
- `repository_scope_mismatch`;
- `citation_density_mismatch`;
- `project_coverage_mismatch`.

Persist categories and counts in Stage 6 reliability output without retaining additional prompt or candidate prose. Keep the terminal fault category, but make its causes visible enough to guide the next repair.

## Verification

### One-time diagnostic replay

Replay the cached August 29 Stage 6 candidates offline against the corrected unified authority.

Verify:

- material exposed to the model is accepted as known evidence and approved imagery;
- survivor repository coverage agrees across context and admission;
- remaining authored-body issues are reported individually and supplied to editorial repair;
- the replay does not invoke live model routes.

Treat this as implementation evidence rather than a permanent regression suite.

### Permanent test

Retain one small offline behavior test if existing coverage does not prove the invariant:

- build a Stage 6 input containing survivor evidence and a screenshot;
- create a complete post using the exact ID and image path visible in its rendered context;
- verify mechanical admission accepts that material and body-policy coverage requires exactly the survivor repositories.

Assert behavior rather than exact prompt text, exact projection bytes, internal call counts, reviewer order, or timing.

### End-to-end acceptance

After the offline replay passes, run the repository's documented environment and test commands, then rerun:

```bash
./make_blog.py -y -d 2026-08-29
```

Require evidence of the complete terminal path:

- nonempty generated `post.md`;
- publication bundle;
- successful import and MkDocs build;
- verified rendered page for `2026-08-29`;
- bounded degradation/fault summary that reflects the actual route and admission outcomes.

The exact report-date rerun is the decisive acceptance check for this defect.

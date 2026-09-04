# Daily-blog editorial spotlight and screenshot plan

## Objective

Make the existing daily-blog pipeline use its strongest evidence selectively.

For a day with many active repositories, the article should give the most significant development enough room to remain concrete and interesting. A small number of genuinely connected developments may share the narrative when that produces a stronger story. Routine work should remain available for grounding and appear compactly in `Project coverage` instead of forcing the article into an exhaustive cross-repository theme.

When a selected narrative has relevant screenshot evidence, make the screenshot's exact publication path available to the complete-post writers, editors, recovery path, bundle builder, and publisher under one authority. Let the editorial stages decide whether it strengthens the story.

Preserve the current reliability contract: `make_blog.py` produces and verifies the best eligible grounded post that survives the replicated editorial pipeline. Preserve approved prompts and rubrics byte-for-byte.

## User-visible outcome

A successful run should produce a cohesive maker post that:

- centers a specific artifact, decision, experiment, investigation, or result;
- develops the most interesting work with concrete technical detail;
- gives additional work substantial treatment only when it supports the story;
- summarizes the remaining active repositories in the compact `Project coverage` section;
- can use selected screenshot evidence through its published `publish_path`;
- retains exact evidence, repository, asset, bundle, and page-verification integrity;
- remains resilient to partial model failure through the existing replicated editorial and recovery paths.

The August 22 and August 23 posts remain the positive voice references. The August 25 post, `One Authoritative Thing`, is acceptance evidence for the current failure mode: broad thematic grouping preserved coverage but diluted the specific progress, and available screenshot evidence never reached the published article.

## Governing contracts

Implement this plan within the existing contracts:

- `docs/BLOG_CONTRACT.md`: one cohesive article; ranking controls emphasis; the daily outline chooses substantial, brief, and omitted treatment; all usable repository stories remain available; publication remains evidence-grounded and mechanically verified.
- `docs/HUMAN_GUIDANCE.md`: approved prompt prose is human-owned; software-contract work and prompt revision remain separate; August 22-23 are the positive references.
- `docs/REPO_STYLE.md`, `docs/PYTEST_STYLE.md`, `tests/TESTS_README.md`, and `devel/DEVEL_README.md`: use existing module owners, keep permanent tests fast/offline/deterministic/behavior-focused, and treat live checks as one-time evidence.
- `layered_podcast_improve_plan.md`: retain replicated editorial stages, promotion, survivor preservation, model-produced recovery, resumable caching, and explicit degradation/fault reporting.

The external model boundary remains the configured Hermes route. Hermes owns provider-account selection internally.

## Current evidence and root causes

### Narrative specificity

The existing prompts and rubrics already express the desired editorial behavior:

- `pipeline/prompts/daily_blog_author_v4.txt` tells the writer to choose the story inside the work, give important details room, and treat routine work briefly.
- `pipeline/prompts/daily_blog_daily_outline_writer_v1.txt` says the complete story set is source material while ranking determines emphasis and permits a nonempty repository subset.
- `pipeline/prompts/daily_blog_daily_outline_rubric_v1.md` prefers selective, coherent movement.
- `pipeline/prompts/daily_blog_story_ranking_rubric_v1.md` favors concrete technical problems, decisions, experiments, and results.
- `pipeline/prompts/daily_blog_rubric_v4.md` rewards maker substance and developing a meaningful thread.

The missing behavior is therefore an orchestration and authority problem, not missing prompt prose.

`pipeline/daily_blog/publication_workflow.py` currently builds the Stage 6 publication surface from `DailyOutlineResult.selected_stories`. `pipeline/daily_blog/daily_outline_workflow.py` derives that set from the promoted outline's repository scope. The same scope is then asked to serve two different purposes:

1. the repositories that receive full narrative material; and
2. the repositories that must remain visible for complete daily coverage.

That conflation encourages broad outlines and broad complete posts. The implementation needs distinct narrative and coverage concepts while retaining one authoritative Stage 6 handoff.

### Screenshot availability

The completed August 25 run is concrete evidence:

- run: `out/vosslab/daily_blog/2026-08-25/runs/20260831T211539Z-c60846358a/`;
- `evidence.json` contains usable Peptidyle screenshots with `asset_path` and `publish_path`;
- the promoted Stage 5 outline cites screenshot evidence IDs;
- `stage5_daily_outline.json` records no image paths;
- `stage6_prompt_context.json` and `stage6_evidence_context.json` omit the screenshot `publish_path`;
- `publication_bundle.json` has no assets;
- the published post has no images.

`pipeline/daily_blog/publication_admission.py` derives allowed image paths from Markdown image destinations already embedded in promoted artifacts. A promoted outline can cite a screenshot evidence ID without embedding Markdown image syntax, so the screenshot is visible as evidence but its publication path is withheld from Stage 6. The complete-post writer cannot select an image that upstream prose did not already embed.

## Design

### One Stage 5 handoff with two explicit scopes

Represent the Stage 5 result with two semantically different views:

- **Narrative scope:** the promoted daily outline's selected repository stories. These receive full outline/story context for complete-post writing.
- **Coverage scope:** every usable Stage 4 repository survivor for the report date. These remain available for grounding, recovery, and the compact `Project coverage` section.

Use one typed handoff at the Stage 5-to-Stage 6 boundary. Keep the authoritative source stories in the existing Stage 5 result or its direct replacement; expose derived narrative and coverage views rather than duplicating independently supplied collections.

The narrative scope is qualitative. Preserve the promoted outline's repository selection and ranking. Use no hard top-N rule, score threshold, required repository count, or code-level prose-quality predicate. One development may dominate a day; several may share the narrative when the promoted outline connects them meaningfully.

The coverage scope must not force routine repository stories into the article body. It supplies the canonical repository roster and compact coverage facts needed by publication validation.

### One screenshot authority derived from selected evidence

Build the Stage 6 image authority from the same survivor-scoped evidence used for prose admission:

1. Collect screenshot evidence IDs cited by the promoted daily outline and selected narrative stories.
2. Resolve those IDs against the survivor packets.
3. Create the existing publication-image representation from each exact `(evidence_id, asset_path, publish_path)` mapping.
4. Union explicitly embedded, valid image destinations only when they resolve to the same survivor-scoped mapping.
5. Store the resulting image map once on the Stage 6 publication surface.
6. Render selected screenshot evidence with its `publish_path` in the Stage 6 context.
7. Reuse that exact image map for complete-post admission, recovery, Stage 7, publication repair, bundle assets, producer validation, and sibling publisher validation.

A screenshot from an unavailable repository or an uncited screenshot outside the selected narrative evidence remains outside the model-visible and publishable image set. This keeps image selection useful without widening the trust boundary to every screenshot in the aggregate packet.

### Preserve availability without forcing inclusion

Keep all usable Stage 4 stories available to:

- ranking and daily-outline generation;
- recovery when the selected narrative path cannot produce an eligible complete post;
- deterministic repository coverage validation;
- provenance and diagnostics.

Give Stage 6 full prose context only for the narrative scope plus a compact, mechanically derived coverage summary for the remaining repositories. This lets the writer spotlight significant progress without losing daily completeness.

### Cache identity

Keep physical mirror paths, refresh observations, and branch-inventory metadata outside semantic model-cache identity.

Include semantic changes that alter model-visible work:

- report date and output owner;
- workflow stage and role;
- approved prompt/rubric digest;
- selected commit/evidence content;
- narrative repository scope;
- coverage repository scope when rendered to the model;
- selected screenshot evidence IDs and publication-path mapping.

A changed narrative or image selection must invalidate the relevant Stage 5-7 cache entries. A mirror refresh that leaves the historical evidence unchanged must reuse them.

## Implementation milestones

### S1 - Capture the current behavior at the existing seams

Use Graphify first, then verify the current source and tests around:

- `pipeline/daily_blog/daily_outline_workflow.py`;
- `pipeline/daily_blog/publication_workflow.py`;
- `pipeline/daily_blog/publication_admission.py`;
- `pipeline/daily_blog/stage6_context.py`;
- `pipeline/daily_blog/stage6.py`;
- `pipeline/daily_blog/candidates.py`;
- `pipeline/daily_blog/publication_contract.py`;
- the sibling publisher's import and validation scripts.

Record the exact current owners for narrative selection, Project coverage, screenshot resolution, bundle assets, and publisher validation. Use the August 25 run artifacts as one-time diagnostic evidence. Preserve prompt and rubric assets unchanged.

### S2 - Separate narrative emphasis from complete coverage

Refine the existing Stage 5 result and Stage 6 publication-surface construction so that:

- the promoted outline's selected repositories define narrative scope;
- all usable repository survivors define coverage scope;
- Stage 6 receives full story material for narrative scope;
- Stage 6 receives compact coverage data for the complete survivor roster;
- recovery can still reach all usable survivor stories;
- `Project coverage` validation uses coverage scope;
- article-body grounding uses narrative scope plus any specifically admitted corroborating evidence.

Keep one owner for the source artifacts and derive both scopes from it. Remove compatibility aliases or duplicate fields made obsolete by the change.

### S3 - Resolve cited screenshots into the Stage 6 publication surface

Extend the existing publication-surface builder to resolve cited screenshot evidence IDs to exact survivor-scoped image records.

Render the admitted image records in Stage 6 context with enough information for the approved author prompt to use them: evidence ID, short description, and exact `publish_path`. Keep local source paths and unrelated screenshots out of model-visible context.

Use the same admitted image records through normal generation and recovery. Keep Stage 7 and publication repair from losing an incumbent image reference.

### S4 - Align bundle and publisher validation

Verify that producer bundle creation and the sibling `vosslab-daily-blog` publisher consume the same selected image authority.

Prefer the existing bundle schema and `allowed_images`/asset representation if it can express the corrected behavior. If a schema change is necessary, update producer and publisher together and retain one canonical meaning for:

- evidence metadata;
- selected bundle assets;
- permitted Markdown image destinations;
- copied asset bytes;
- rendered-page validation.

A valid selected screenshot should survive import and page verification. An unselected screenshot should remain absent from the bundle and unacceptable in the article.

### S5 - Preserve cache and recovery semantics

Update semantic cache inputs only where model-visible narrative or selected-image context changes. Verify that:

- a changed narrative scope misses the affected cache entry;
- a changed cited screenshot selection misses the affected cache entry;
- physical mirror relocation or refresh-only changes still reuse prior editorial work;
- portable cache aliases resolve to current-run artifacts and provenance;
- complete-post recovery uses the same narrative, coverage, evidence, and image authority as the normal path.

### S6 - Simplify after the boundary is correct

Remove duplicate authority fields, trivial aliases, and validation checks that merely compare two copies of the same data. Keep modules under the repository line limit and move stage-owned types/helpers to their owning modules if the edited files approach the limit.

Use `PublicationSurface` or its direct replacement as the sole Stage 6 publication authority. Keep `Stage6Input` focused on execution inputs rather than restating publication ownership.

### S7 - Verify and document

Run the permanent behavior tests, existing E2E, full suite, and one live historical publication. Update current operational documentation and the changelog with the implemented ownership model and verified evidence. Archive this plan after all acceptance criteria pass.

## Verification strategy

### Permanent tests

Retain only durable behavior coverage. Prefer replacing or extending current tests over creating new modules or fixtures.

#### Stage 5 narrative/coverage behavior

Update `tests/test_daily_blog_stage5_availability.py` to prove:

- a promoted daily outline may select a narrow narrative repository subset;
- the Stage 6 handoff gives that subset full narrative story context;
- the full usable survivor roster remains available to `Project coverage` and recovery;
- a routine repository is not forced into the article-body source set merely to satisfy coverage.

Assert public behavior and typed outputs. Avoid assertions on exact reviewer counts, call order, private helper topology, prompt rendering bytes, or tunable defaults.

#### Screenshot admission behavior

Replace the existing incomplete seam test in `tests/test_daily_blog_publication_admission.py` with a behavior test that:

1. builds a survivor packet containing a screenshot with an evidence ID, asset path, and publish path;
2. builds promoted outline/story artifacts that cite the screenshot evidence ID without pre-writing Markdown image syntax;
3. constructs the real Stage 6 input/publication surface;
4. confirms the rendered Stage 6 context exposes the exact admitted `publish_path`;
5. admits a complete post that uses that path;
6. confirms the bundle contains the selected asset;
7. confirms an uncited screenshot remains unavailable and absent.

Keep the test offline, deterministic, inline, and focused on the exact production seam. Use existing local helpers where they clarify the test; create no external fixture corpus.

#### Cache behavior

Extend the existing route-cache behavior test only if the new semantic fields are not already covered. Assert semantic reuse/miss behavior, not hashes, serialized bytes, implementation-specific field order, or exact model-call counts.

### One-time implementation checks

Use temporary probes or scripts during implementation for:

- replaying the August 25 artifacts through the corrected Stage 5-to-Stage 6 seam;
- inspecting rendered Stage 6 context for narrative and screenshot availability;
- confirming producer and sibling publisher agree on selected assets;
- examining generated prose and image use;
- checking cache reuse across a historical mirror refresh.

Keep these outside permanent pytest. Remove temporary scripts, generated fixture copies, and debug assertions before closure.

### Commands

Run the focused permanent tests:

```bash
source source_me.sh && pytest \
  tests/test_daily_blog_stage5_availability.py \
  tests/test_daily_blog_publication_admission.py \
  tests/test_daily_blog_route_cache.py
```

Run the existing E2E boundary:

```bash
source source_me.sh && python3 tests/e2e/e2e_daily_publication.py
```

Run the complete permanent suite on the final unchanged tree:

```bash
source source_me.sh && pytest tests/
```

Run one live historical publication as one-time acceptance evidence:

```bash
source source_me.sh && ./make_blog.py -y -d 2026-08-25
```

Inspect the resulting run artifacts, source Markdown, imported bundle, and verified page. Record the run ID and decisive observations without turning prose wording, exact repository counts, exact image counts, elapsed time, or model-call topology into permanent test gates.

## Acceptance criteria

The plan is complete when all of the following are verified:

- A narrow Stage 5 narrative selection reaches Stage 6 without removing the full survivor roster from Project coverage or recovery.
- Stage 6 receives selected narrative details instead of full prose for every active repository.
- A screenshot cited by selected survivor evidence reaches Stage 6 with its exact `publish_path`, can be used by the complete post, survives bundle creation/import, and verifies on the rendered page.
- An unrelated or uncited screenshot remains outside the admitted image set.
- Normal generation, complete-post recovery, Stage 7, publication repair, bundle creation, and publisher validation use the same publication authority.
- Existing partial-agent-failure behavior still produces a grounded post when an eligible editorial path survives.
- Semantic cache changes invalidate the right entries; refresh-only mirror changes reuse historical work.
- Permanent tests satisfy repository rules and pass; temporary verification artifacts have been removed.
- The existing E2E and full permanent suite pass.
- A live August 25 run completes publication and page verification. Its article gives substantial space to significant progress and treats routine work compactly. The run artifacts prove whether selected screenshot paths were made available; actual model image choice is reported separately from backend availability.
- Approved prompts, rubrics, `docs/BLOG_CONTRACT.md`, and Hermes account-selection infrastructure remain unchanged.

## Manager execution model

Use fresh, self-contained subagents for independent implementation units and separate fresh reviewers for verification. Keep milestones dependency-scoped:

1. one worker traces and corrects the Stage 5 narrative/coverage handoff;
2. one worker corrects screenshot resolution and publication-surface ownership after S2 is stable;
3. one worker aligns producer/publisher asset validation if the shared boundary changes;
4. one worker audits cache/recovery semantics after the data model is stable;
5. one reviewer audits repository-rule and permanent-test compliance;
6. one reviewer audits publication integrity from Stage 5 through the rendered page.

The manager integrates and verifies each artifact before starting dependent work. Replace drifting workers with fresh tasks. Use captured run artifacts, inline test data, and existing E2E harnesses so implementation and verification can finish autonomously.

## Documentation updates after implementation

Update only current, behavior-owning documentation:

- `docs/DAILY_BLOG_OPERATIONS.md`: narrative scope, coverage scope, selected-image authority, diagnostics, and live verification.
- `docs/CHANGELOG.md`: concrete behavioral change and verification evidence.
- `docs/FILE_STRUCTURE.md`: only if module ownership or placement changes.

Preserve approved prompt assets, rubrics, and `docs/BLOG_CONTRACT.md` byte-for-byte. Move this plan to `docs/archive/` after every acceptance criterion is satisfied.

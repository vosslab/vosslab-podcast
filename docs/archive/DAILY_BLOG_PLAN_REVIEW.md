# Review of `foamy-fluttering-nebula.md`

## Overall assessment

The edited plan has the right governing direction but is not ready for implementation as written.

The strongest idea is faithful to `docs/BLOG_CONTRACT.md`: every subjective stage should create alternatives, review them, promote the strongest usable artifact, and preserve the incumbent when later work fails. The command should finish with an evidence-grounded post whenever sufficient repository evidence exists. Editorial weakness should lead to a weaker but usable post, not to no post.

The plan now distinguishes three outcomes clearly:

- **Degraded:** a usable artifact exists and continues through the pipeline.
- **Incomplete:** an artifact exists, but import, build, or page verification did not finish; the command reports the failed stage with a nonzero exit.
- **Aborted:** sufficient verified evidence or a safe writable destination does not exist, so no trustworthy post can be constructed.

That distinction should remain.

The plan also correctly preserves these contract decisions:

- `make_blog.py --yesterday` is the complete user-facing command.
- Repositories remain independent through the repository-story stages.
- Subjective stages follow replicate, review, and promote.
- The final result is one cohesive daily story rather than concatenated repository reports.
- Ranking changes emphasis rather than silently deleting available repository material.
- A later synthesis must demonstrate improvement before replacing the incumbent.
- `report_date` is the sole published-post identity, and rerunning a date overwrites that post.
- Hermes remains responsible for model and account selection behind the existing command-route boundary.
- Deterministic structure is constructed by software rather than requested from an LLM and then rejected when malformed.

The implementation plan still contains several scope, correctness, ownership, and test-design problems. Address the following before execution.

## Required revisions

### 1. Preserve the approved package and author the genuinely missing stage assets

The earlier blanket conclusion that all prompt work is outside scope was too broad. The new architecture introduces editorial roles that the approved complete-post package never had, so some prompt and rubric authoring is required. The correct boundary is:

> Preserve the approved production package unchanged. Reuse suitable existing assets. Author new versioned assets only for genuinely new roles that lack a suitable prompt or rubric.

The plan is directionally correct when it treats prompt *tuning* as a later measurement-loop concern while supplying working first versions for the new stages. It should make the reuse boundary explicit before implementation and before any removal sweep.

#### Existing assets to reuse unchanged

- `pipeline/prompts/daily_blog_author_v4.txt` - strong complete-post author prompt. It already asks the writer to write as Neil, find the interesting story, show attention, surprise, enjoyment, learning, uncertainty, and unresolved work, use a thematic title, and apply the central maker question. Reuse it for Stage 6 complete-post generation by compiling the daily outline, repository stories, and evidence into its existing bounded input contract.
- `pipeline/prompts/daily_blog_rubric_v4.md` - strong final-post rubric covering maker substance, author presence and curiosity, insight and selectivity, concrete grounding, narrative/readability, and intellectual honesty. Reuse it for complete-post and final-synthesis comparison. It may also be reused for repository-story review if its whole-article criteria are not applied mechanically to repository intermediates.
- `pipeline/prompts/daily_blog_referee_v4.txt` - suitable for anonymous comparison of two complete posts using an injected rubric and authoritative evidence.
- `pipeline/prompts/daily_blog_referee_repair_v4.txt` - suitable for repairing malformed complete-post referee JSON.
- `pipeline/prompts/daily_blog_voice_examples_v4.md` - retain as part of the approved package and preserve its current runtime/calibration ownership.
- `pipeline/prompts/daily_blog_rubric_v3.md` - retain as a historical reference for factual fidelity, thematic focus, editorial arc, synthesis, specificity, reader interest, provenance, and publication shape. V4 remains the stronger maker-voice rubric.

These approved V4 assets are already registered as frozen production resources in `pipeline/daily_blog/contracts.py`. The migration should preserve their bytes and identities rather than silently replacing them with similarly named files.

#### Existing legacy prompts that are references, not suitable replacements

- `outline_repo.txt` and `outline_repo_targeted.txt` favor exhaustive sections, commit subjects, changelog inventory, and empty-activity placeholders. They can inform evidence variables, but they do not perform the editorial reduction required by Stage 3.
- `outline_global.txt` ranks repositories by activity and count, conflicting with the contract rule that commit count, repository size, and generated word count are not proxies for importance.
- `depth_referee_outline.txt` rewards commit counts, separate repository summaries, and target-length proximity rather than narrative potential and downstream usefulness.
- `blog_repo_markdown.txt` and `blog_markdown.txt` emphasize counts, per-repository enumeration, commit/file anchors, and uniform coverage. Used unchanged, they would reproduce the mechanical Aug. 24-25 failure mode.
- `depth_polish_outline.txt` and `depth_polish_blog.txt` lack authoritative evidence, stage-specific rubrics, the maker criterion, and incumbent-preservation semantics.
- `blog_expand.txt`, `blog_trim.txt`, `blog_regenerate.txt`, and `blog_word_band_retry.txt` may supply narrow transformation ideas, but their behavior must remain subordinate to the new preservation and evidence contracts.

Reuse reviewed helper behavior and template mechanics from these files. Do not treat their prose as the approved editorial contract for the new stages.

#### Genuinely missing assets that should be authored

The repository has no adequate historical prompt/rubric set for these new roles:

1. **Stage 3 repository outlines**
   - repository-outline generator;
   - independent outline merger;
   - repository-outline rubric covering factual grounding, specificity, interestingness, technical substance, completeness, narrative potential, and usefulness to the writing stage.
2. **Stage 4 repository stories**
   - repository-story writer;
   - repository-story editor;
   - optionally a narrower repository-story rubric, or an explicit decision to reuse V4 unchanged where its criteria fit.
3. **Stage 5 ranking and daily outline**
   - editorial story-ranking prompt and ranking rubric;
   - daily-outline generator and daily-outline rubric.
   These assets are genuinely absent; the legacy activity-ranking prompt is incompatible with the contract.
4. **Stage 6 complete post**
   - complete-post editor prompt.
   Reuse the V4 author, rubric, referee, and referee-repair assets for generation and selection.
5. **Stage 7 synthesis**
   - synthesis prompt that receives the incumbent, alternatives, reviewer feedback, rubric, and evidence, and treats the incumbent as an active candidate without recency preference.

A small architecture is preferable to separate reviewer and repair prose for every stage:

- use stage-specific creation/editing prompts where the editorial task genuinely differs;
- use one generic, versioned artifact-comparison prompt for newly introduced intermediate artifact types, parameterized by artifact type, candidates, evidence, rubric, and incumbent identity;
- use one generic, versioned structured-verdict repair prompt for those new comparisons;
- keep the approved V4 complete-post referee and repair prompts unchanged for their existing contract.

#### Prompt-authoring acceptance

New assets should:

- derive their task and rubric criteria directly from `docs/BLOG_CONTRACT.md`;
- state desired behavior positively and concretely;
- use examples where they clarify the target;
- carry only operationally necessary boundaries;
- preserve evidence grounding as eligibility rather than an editorial score;
- avoid commit-count, repository-size, word-count, or repository-order proxies for importance;
- remain versioned and identity-recorded with generated artifacts;
- be exercised against fixed evidence packets as implementation evidence without turning prose quality into brittle permanent assertions.

Prompt authoring is therefore in scope for missing stage roles. Prompt editing of the approved V4 production package is not required for this integration.

### 2. Keep evidence grounding as an eligibility boundary

The plan says every current check becomes a score. That is appropriate for editorial preferences, but not for provenance and publication integrity.

Use scoring or reviewer judgment for qualities such as:

- thematic strength;
- maker voice;
- narrative coherence;
- preferred article length;
- treatment depth;
- heading style.

Keep the following as mechanical artifact-eligibility conditions:

- every factual evidence reference resolves to the correct evidence packet;
- cited material belongs to the correct repository and report date;
- image paths come from approved evidence;
- `report_date` and publication identity are correct;
- output paths remain inside approved roots;
- required machine-owned metadata is valid;
- the article contains enough verified evidence to be trustworthy.

An ineligible candidate should not abort the run. Preserve the strongest grounded incumbent and continue through the fallback hierarchy.

### 3. Define typed fallback results for every stage

WP-B1 still says that when no candidate survives, promotion returns the stage input marked degraded. The stages transform different artifact types:

- evidence packet to repository outline;
- repository outline to repository story;
- repository stories to daily outline;
- daily outline to complete article.

Returning the input as the output can place an evidence packet where an outline is expected or an outline where an article is expected.

Give each stage an explicit typed result such as:

- `Promoted[T]`;
- `NoPromotedArtifact` with a categorical reason;
- `PreservedIncumbent[T]`;
- a deterministic same-type fallback where the contract defines one.

Repository-stage failure should preserve successful repositories independently. The complete-article fallback hierarchy should receive only complete-article artifacts or deterministic complete-article constructions.

### 4. Preserve the incumbent when review cannot demonstrate improvement

The plan allows a sole surviving candidate or deterministic selection after reviewer failure. That behavior is useful when a stage has no incumbent. It must not replace an existing promoted artifact without evidence of improvement.

Use these rules:

1. Rank mechanically eligible candidates only.
2. When an incumbent exists, retain it after reviewer, referee, or parsing failure.
3. Use deterministic selection only among eligible peer candidates when no incumbent can be displaced.
4. Use deterministic repair for mechanical structure without treating the repaired artifact as a new editorial candidate.

This is especially important for Stage 7 synthesis.

### 5. Replace positional referee fallback

WP-B2 explicitly preserves the historical behavior where malformed referee output selects positional candidate B. That creates systematic order bias and turns a parsing failure into an editorial decision.

Use this resolution order:

1. parse the reviewer response strictly;
2. make one bounded repair attempt;
3. salvage an unambiguous candidate identifier when present;
4. preserve the incumbent when one exists;
5. otherwise use a stable deterministic choice among eligible candidates.

Historical `podlib` code is useful reference material, not an orchestration component to restore wholesale.

### 6. Use the historical pipeline selectively

The old pipeline contains useful pure helpers, including text normalization, prompt rendering, wrapper stripping, and word counting. Its orchestration also contains behavior that conflicts with the new contract:

- generator, reviewer, and polish exceptions can escape;
- malformed referee output selects candidate B;
- "best" can mean draft zero or the first bracket winner;
- old cache identities omit important content;
- old cache writes are not atomic;
- its main score is distance from a target word count;
- its whole-outline fallback is another model call that can fail;
- some historical paths own model-client construction instead of using Hermes.

Revise the plan from "recover the pre-lockdown machinery" to "reuse reviewed pure helpers and behavioral ideas." Implement current ownership and failure semantics around the existing Hermes command route, `PhaseCache`, and run-state infrastructure.

### 7. Resolve the Stage 9 publisher ownership contradiction

The plan excludes changes to the separately owned publisher repository while requiring the imported source to survive a later MkDocs build failure.

The current publisher transaction builds before committing the import. A failed build removes its staging tree. Therefore, producer-side orchestration cannot produce the state "source import succeeded; later build failed; imported source remains."

Choose and document one durable publisher contract:

1. commit imported source and return an `imported_source` receipt;
2. build that committed source and return a separate `built` receipt;
3. verify the served page and return a separate `verified` receipt;
4. preserve every completed receipt when a later step fails.

This requires a narrow coordinated change in `vosslab-daily-blog`, or an explicitly defined durable staging/archive boundary owned by that repository. Update the non-goals and dependencies accordingly. This is a publication-ownership repair, not a model-routing project.

### 8. Retain bundle dependencies until migration is complete

The removal plan deletes `contracts.py`, `activation.py`, and `editorial.py` while retaining `bundles.py`. The retained bundle module imports those modules and embeds their types and identities in its API.

Add a module-by-module disposition table with these categories:

- retain unchanged;
- adapt in place;
- replace behind an existing interface;
- migrate consumers, then remove;
- remove after verified disconnection.

Keep bundle dependencies until a minimal publication-contract owner replaces them and all consumers have migrated. Run import and E2E verification before and after each removal group.

### 9. Use one durable state owner

The plan adds a ledger, a journal, detailed run directories, summary records, retention, and reliability aggregation while the repository already has `RunStore` and `PhaseCache`.

Prefer this ownership model:

- `RunStore` owns the authoritative run record, artifact identities, parent relationships, promotion decisions, eligibility, degradation reasons, and `best_artifact_id`.
- `PhaseCache` owns resumable hash-addressed stage outputs.
- One event stream records facts needed for operator diagnostics.
- A read-only reporter derives optional aggregates from those records.

Avoid creating standalone ledger and journal authorities that can disagree with `RunStore` or `PhaseCache`. Add retention only after the actual retained artifacts and their size justify it.

### 10. Use an explicit incumbent instead of ambiguous ledger levels

The plan defines level 1 as final synthesis and level 5 as the minimal floor, then says `best()` returns the "highest occupied level." That phrase is ambiguous and can select the weakest fallback numerically.

Represent priority explicitly, for example:

```text
FINAL_SYNTHESIS
EDITED_COMPLETE_POST
COMPLETE_WRITER_DRAFT
DETERMINISTIC_STORY_ASSEMBLY
EVIDENCE_FLOOR
```

Better still, retain immutable artifacts and store one explicit `best_artifact_id`. Update that pointer only through a valid promotion or deterministic fallback transition.

### 11. Keep shared durable writes under one coordinator

The plan places repository processing inside concurrent futures while also writing caches, artifacts, and events. `PhaseCache` and `RunStore` are shared durable state and should have one coordinator.

Use this concurrency boundary:

1. discover repositories and gather deterministic evidence;
2. freeze immutable repository packets;
3. run independent Hermes route calls concurrently under one global budget;
4. serialize cache writes, promotion decisions, incumbent updates, and run events through the orchestrator.

This preserves repository independence without multiplying executors or introducing concurrent authoritative writes.

### 12. Keep route failure handling narrow and typed

The route layer should absorb ordinary model-call failures, but it should not convert every `RuntimeError` or unexpected programming defect into an editorial degradation.

Distinguish:

- recoverable route failures: timeout, start failure, nonzero model exit, empty response;
- repairable structured-output failures;
- repository-specific evidence unavailability;
- terminal configuration, path-safety, identity, or cache-corruption failures;
- unexpected implementation defects.

Preserve completed artifacts before returning a precise nonzero result for terminal and unexpected failures.

### 13. Remove arbitrary measurement thresholds

The open decisions propose thresholds of one-third disagreement, one-quarter synthesis wins, and one-in-five fallback frequency. These numbers are not grounded in current operational evidence.

Ship raw observations first:

- counts and denominators;
- fallback frequency by step;
- reviewer disagreement frequency;
- synthesis wins against the incumbent;
- repair and retry categories;
- final fallback level.

Use those observations to support a later design decision. Keep the reporter advisory and outside command success criteria.

### 14. Simplify the first implementation milestone into a vertical slice

The edited plan correctly admits that M1 alone does not satisfy the command contract. The most useful first integrated milestone should nevertheless reach the user-visible result as soon as possible.

After the minimum route-result and floor types exist, wire this vertical path:

1. resolve a fixed report date;
2. obtain verified repository evidence;
3. build the deterministic complete-post floor;
4. construct machine-owned metadata;
5. overwrite the date's post;
6. import, build, and verify through disposable publication roots;
7. return the Stage 9 result from `make_blog.py`.

Once this path works, add replicated editorial stages incrementally. Every subsequent milestone then improves a command that already produces a page.

## Test and verification revisions

### Permanent tests

Keep a small offline, deterministic behavior suite protecting these contracts:

1. Total route outage with sufficient verified evidence produces a complete evidence-grounded floor artifact.
2. A later-stage failure leaves the incumbent unchanged.
3. An unsupported candidate cannot replace a grounded incumbent.
4. Failure of one repository leaves successful repositories available downstream.
5. Ranking changes emphasis without making available repository stories inaccessible.
6. A stylistic or word-band miss remains usable and is recorded diagnostically.
7. A same-date run overwrites the published post.
8. A publication-stage failure preserves every previously completed artifact and returns a structured nonzero result naming the failed step.
9. Cache reuse requires a complete immutable fingerprint and invalidates when evidence or prompt identity changes.
10. Deterministic mechanical repair changes only the machine-owned region it repairs.

Use inline inputs, `tmp_path`, injected boundaries, retries disabled, and no real sleeps or network access.

### One controlled permanent E2E

Retain one fixed-date, synthetic, disposable-root path covering:

```text
command -> evidence -> complete article -> import -> build -> verify
```

Run it outside pytest according to the repository E2E rules.

### One-time implementation evidence

Use temporary harnesses for:

- exact reviewer and referee topology;
- retry counts and delay behavior;
- exact route-call counts;
- forced process failures;
- live installed-service behavior;
- representative historical-date comparisons;
- real `make_blog.py --yesterday` execution.

Capture the outcomes in a report and remove temporary harnesses that lack enduring E2E value.

### Full repository verification

Because the plan removes modules imported by multiple E2Es, inventory and migrate every consumer and run:

```bash
source source_me.sh && pytest tests/ -k daily_blog
source source_me.sh && python3 tests/e2e/e2e_daily_publication.py
source source_me.sh && bash tests/e2e/run_all.sh
source source_me.sh && pytest tests/
```

## Recommended minimum architecture

Start with three small new concerns rather than twelve new stage-owned modules:

### `agents.py`

- typed route results;
- bounded, classified retry;
- one repair attempt for structured responses;
- a global route-call budget;
- no model or account selection outside Hermes.

### `replication.py`

- pure replication of eligible alternatives;
- reviewer voting;
- promotion while preserving an incumbent;
- deterministic fallback only among mechanically eligible peers.

### `floor.py`

- a complete evidence-grounded post when model stages do not produce one;
- no model calls;
- machine-owned front matter and publication identity.

Then revise the existing orchestrator as the single coordinator, extend the existing run state, and make the narrow publisher transaction change needed for Stage 9. Split additional modules only after an independent ownership boundary appears in working code.

## Suggested execution order

1. Freeze the approved prompts, rubrics, evidence interfaces, and Hermes route boundary.
2. Define typed artifacts, eligibility, route outcomes, and the incumbent contract.
3. Implement and wire the deterministic floor through the complete publication path.
4. Repair the publisher transaction boundary so imported source survives later build failure.
5. Add replicated repository outline and story stages around the working fallback path.
6. Add daily ranking, complete-article generation, editing, and synthesis.
7. Extend run-state observability with factual step outcomes.
8. Run the focused permanent tests and controlled E2E.
9. Collect one-time historical and live evidence.
10. Migrate dependencies and remove only components proven obsolete.
11. Run the full E2E aggregate and full pytest suite.
12. Update the changelog, transcript, operations documentation, and active-plan status.

## Final assessment

The revised plan has the correct contract-level direction: quality work should improve the strongest available post rather than become a sequence of vetoes. Its user-facing outcome model is substantially improved.

Implementation should begin after the plan:

- freezes the approved prompt package;
- preserves hard evidence and publication eligibility boundaries;
- replaces generic fallback values with typed stage outcomes;
- removes positional referee bias;
- narrows historical-code reuse;
- coordinates the required publisher transaction change;
- consolidates durable state ownership;
- removes unsupported thresholds and fragile mechanism tests;
- converts the first integrated milestone into a command-to-page vertical slice.

With those changes, the plan will stay centered on the requested result: running `make_blog.py --yesterday` produces the strongest evidence-grounded blog page the available stages can create, and later failures preserve rather than erase completed work.

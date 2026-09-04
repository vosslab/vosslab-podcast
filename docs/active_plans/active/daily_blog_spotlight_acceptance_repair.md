# Daily-blog spotlight acceptance repair

## Status

Active implementation plan.

## Objective

Make the daily-blog pipeline use its editorial ranking to spotlight the most significant, interesting work while retaining compact coverage of the rest of the day. Preserve the pipeline's current reliability: when eligible editorial work survives, the command continues through publication, and later quality stages improve or preserve the strongest grounded artifact.

This is a narrow acceptance repair for the completed daily-blog rebuild. It implements the already approved editorial intent rather than redesigning the pipeline:

- Give the strongest development enough space for concrete technical detail, a maker's perspective, and a coherent story.
- Use related work when it strengthens that story.
- Carry every surviving repository separately as coverage and recovery material.
- Let screenshots support the selected story when an editorial artifact cites them.
- Treat stochastic disagreement and partial model failure as ordinary degradation while preserving the strongest eligible result.

The central editorial question remains:

> After reading this post, does it feel like Neil sat down after coding and wrote about what he made, what interested or surprised him, why he enjoyed working on it, what he learned, and what he wants to try next?

## Acceptance evidence that motivates this repair

The live August 24 run completed publication successfully:

- Run: `20260901T032524Z-28fe5e871f`
- Run state: `output-pipeline/vosslab/daily_blog/2026-08-24/runs/20260901T032524Z-28fe5e871f/run_state.json`
- Published source: `/home/vosslab/nsh/vosslab-daily-blog/docs/blog/posts/2026-08-24.md`
- Published page: `http://aella.local:8016/blog/2026/08/24/make-the-real-path-carry-the-proof/`
- Final result: completed, imported, built, and verified with `outcome=degraded`

The run proves that the rebuilt reliability path works. It also exposes a narrower editorial defect:

1. Five of six repository jobs survived, but all five surviving stories were promoted into the narrative scope. The resulting article summarizes several projects at similar depth instead of clearly spotlighting the strongest development.
2. Stage 5 had three outline candidates, but eight of twelve review/repair attempts failed. One eligible outline survived, so publication correctly continued, yet the surviving outline did not demonstrate the intended selectivity.
3. Stage 6 produced one eligible complete post from three writers; both editor attempts failed. Stage 7 produced no eligible synthesis. Preserving the incumbent was correct, but it makes the quality of Stage 5's promoted outline especially important.
4. Evidence acquisition found screenshots, including six from the surviving Ferrum repository. Stage 5's bounded evidence context exposed their evidence IDs and publishable paths, but the promoted narrative artifacts cited none. The final bundle therefore contained no image assets.
5. The `vosslab/attack-on-cancer` repository job ended with the categorical reason `implementation_defect`. That concrete defect must be diagnosed at its owning boundary rather than accepted as stochastic degradation.

The archived plan at `docs/archive/daily_blog_editorial_spotlight_and_screenshot_plan.md` established the correct architecture: narrative scope is selective, coverage scope is complete, and cited images flow through one `PublicationSurface`. This plan closes the remaining acceptance gap without reopening that architecture.

## Protected boundaries

Preserve these authorities and behaviors throughout implementation:

- Keep `docs/BLOG_CONTRACT.md` byte-identical.
- Keep the approved prompt and rubric assets byte-identical.
- Use the existing Hermes-owned provider, model, and account-routing boundary.
- Keep each author, reviewer, referee, and repair attempt isolated in a fresh one-shot process with a complete self-contained prompt.
- Preserve evidence grounding, provenance binding, publication validation, path safety, and the sole `PublicationSurface` authority.
- Preserve semantic route-cache identity and resumable recovery.
- Preserve the distinction between editorial degradation and a genuine pipeline fault.
- Preserve model-produced recovery paths; exhausted editorial recovery remains a diagnosed nonzero fault.
- Keep screenshot choice editorial and optional. Record availability and use clearly rather than making image use a publication gate.
- Keep ranking qualitative and adaptable. Ranking expresses editorial importance; it is not a fixed top-N rule, repository-count threshold, commit-count proxy, or word-allocation formula.
- Keep full survivor coverage available even when the narrative spotlights one development.

## Repository-rule execution model

The manager owns integration and final verification. Use a fresh, self-contained subagent for every implementation or review task. Give each worker one dependency-scoped objective, the exact files and evidence it needs, the protected boundaries above, and a required verification result. Use separate workers for implementation and review.

Before broad exploration, use the repository Graphify map and verify every conclusion in current source and tests:

```bash
graphify query "<task-specific question>" --budget 1500
graphify explain "<symbol-or-path>"
graphify affected "<symbol-or-path>" --depth 2
```

Follow `docs/REPO_STYLE.md`, `docs/PYTEST_STYLE.md`, `tests/TESTS_README.md`, `devel/DEVEL_README.md`, `docs/HUMAN_GUIDANCE.md`, and the repository's remaining applicable style documents.

## Milestone A - Reconstruct the two concrete failure paths

### A1. Capture the Stage 5 editorial decision path

Use the durable August 24 run artifacts and route cache to reconstruct Stage 5 without making new live calls. Produce a private, bounded diagnostic report that records:

- the promoted repository ranking and its rationale;
- each generated daily-outline candidate's narrative repositories and coverage repositories;
- the evidence and screenshot descriptors visible to each candidate;
- each reviewer response, parse result, repair result, vote, and stated reason;
- the promotion decision and fallback path;
- the exact point where the promoted narrative scope expanded to all five survivors.

Classify the root cause as one or more of:

- ranking information was absent or too weak in candidate context;
- candidate generation produced materially equivalent scopes;
- candidate parsing erased scope distinctions;
- review or repair rejected otherwise usable candidates;
- promotion selected a broader candidate despite stronger ranked alternatives;
- fallback broadened narrative scope while preserving coverage.

Keep this diagnostic harness ephemeral unless it proves a stable operational need. Store the resulting one-time evidence in the active plan's report or closeout record rather than in pytest fixtures.

### A2. Recover the `attack-on-cancer` implementation defect

Replay the captured August 24 repository packet through the repository editorial worker under a private diagnostic boundary that retains the original exception type and safe traceback. Keep production logs categorical and redacted.

Identify the owning invariant that failed, fix it at that owner, and verify the same captured packet reaches an eligible repository result or a correctly classified evidence/route outcome. Record the root cause and correction.

Retain a permanent regression test only when the defect reduces to a stable, pure behavior using inline data and `tmp_path`. Use the replay as one-time evidence when reproducing it requires run artifacts, external repositories, subprocesses, or exact historical payloads.

### A3. Decision checkpoint

Before editing Stage 5, write a concise design note identifying the smallest causal fix supported by A1 and A2. The manager verifies that the proposed change:

- improves candidate diversity or promotion at its actual owner;
- preserves full coverage and recovery inputs;
- reuses the current prompt and rubric package;
- introduces no new quality threshold or publication gate.

## Milestone B - Make ranking produce genuinely selective narrative candidates

### B1. Give candidate generation a ranking-shaped choice

Use the promoted ranking and its rationale to construct candidate-specific narrative treatments while using the existing approved daily-outline prompt unchanged.

Each replicated candidate receives:

- the same complete survivor coverage inventory;
- the same grounded evidence authority;
- an explicit candidate treatment derived from the promoted ranking;
- enough detail about the leading development to tell a concrete story;
- compact context for routine or weakly connected work.

Generate materially different editorial treatments from the ranking, such as:

- a focused treatment centered on the highest-ranked substantive thread;
- a connected treatment that includes supporting work when the ranking rationale identifies a meaningful relationship;
- a broader treatment when the day's evidence genuinely supports one coherent multi-repository story.

These are qualitative candidate perspectives, not fixed repository counts. Reviewers continue to choose the strongest eligible artifact with the approved rubric.

### B2. Preserve separate narrative and coverage authorities

Keep `DailyOutlineResult` and `PublicationSurface` explicit about two scopes:

- **Narrative scope:** repositories and story artifacts selected for the article's main arc.
- **Coverage scope:** every eligible survivor available for factual completeness, compact mentions, recovery, validation, and provenance.

Stage 6 prompting uses the promoted narrative scope as the primary writing material and carries coverage separately. Recovery may use additional surviving editorial artifacts while preserving the same scope distinction. Publication eligibility remains grounded against the full authorized surface.

### B3. Make fallback preserve the strongest ranked editorial intent

When reviews disagree, repairs fail, or only one outline remains eligible, preserve the strongest eligible candidate and its narrative scope. Use deterministic fallback only to choose among already eligible editorial artifacts. Record that promotion as degraded.

A fallback should retain the ranking-shaped spotlight represented by the surviving artifact while coverage remains available separately. It should not convert coverage scope into narrative scope merely because later reviewers failed.

## Milestone C - Carry screenshot opportunity with the selected story

### C1. Bind screenshot descriptors to candidate narrative material

For each Stage 5 candidate, make the screenshot evidence associated with its proposed narrative repositories visible in the bounded candidate context:

- evidence ID;
- repository identity;
- safe publishable path;
- available caption or evidence description;
- provenance needed by existing admission checks.

Use the existing bounded evidence projection and path-safety owners. Keep aggregate screenshots outside the selected narrative context unless they are needed for coverage or recovery.

### C2. Reuse cited-image admission

Continue using the current cited-image flow:

1. A promoted outline or selected narrative story cites a screenshot evidence ID or approved path.
2. `PublicationSurface` resolves that citation against its authorized evidence and path set.
3. Stage 6 and recovery receive the same resolved image authority.
4. Bundle creation includes cited assets.
5. The sibling publisher validates and imports those exact assets.

Record these counts separately in bounded summaries:

- screenshots available to the selected narrative;
- screenshots cited by promoted editorial artifacts;
- screenshots included in the bundle;
- screenshots used by the published article.

A value of zero remains valid when the selected story has no useful image or the strongest post does not use one.

### C3. Verify one authority through recovery

Trace normal Stage 6, each complete-post recovery rung, Stage 7 incumbent preservation, publication repair, bundle serialization, and sibling publisher validation. Every path must use the same `PublicationSurface` image and evidence authority.

## Milestone D - Repair quality-stage survivability at the causal boundary

Use the captured August 24 reviewer and editor results to explain the high failure rates before changing code.

For every failed response, classify:

- route start, timeout, or nonzero-exit failure;
- empty response;
- parser mismatch;
- repair mismatch;
- eligibility or evidence-grounding failure;
- valid disagreement;
- actual implementation defect.

Fix a parser, repair, context, or admission boundary only when captured evidence shows that it rejected a response that satisfied the approved contract. Keep malformed or ungrounded responses ineligible. Preserve bounded retries and the strongest eligible incumbent.

The target is graceful stochastic operation, not identical prose and not unanimous review.

## Milestone E - Observability and resumability

Extend existing bounded run summaries only where needed to answer:

- Which repositories were ranked highest, and why?
- Which repositories entered narrative scope?
- Which eligible repositories remained coverage-only?
- Which candidate treatment was promoted?
- Did promotion fall back because reviewers or repairs failed?
- How many relevant screenshots were available, cited, bundled, and used?
- Which repository jobs ended in a genuine implementation defect?

Keep editorial payloads, prompt contents, credentials, account labels, filesystem internals, and sensitive route diagnostics out of ordinary logs.

Verify that changes to candidate treatment and scope are represented in semantic cache identity. Preserve reuse across mirror refresh timestamps, mirror paths, branch-inventory observations, run IDs, and output relocation. Preserve invalidation for changed selected evidence, report date, user, prompt identity, stage, route contract, or candidate treatment.

## Milestone F - Repository-compliant verification

### Permanent tests

Retain only offline, deterministic, durable behavior tests that satisfy `docs/PYTEST_STYLE.md`. Prefer replacing or extending an existing test over adding a new module.

Use the existing Stage 5 and publication-admission tests to cover these durable behaviors:

1. A promoted ranking can yield a narrative scope narrower than the full coverage scope.
2. Every eligible survivor remains available to coverage and recovery.
3. Partial reviewer failure preserves an eligible ranked narrative candidate rather than destroying it or broadening it mechanically.
4. A screenshot cited by a selected narrative artifact reaches the authorized Stage 6 context and bundle; an uncited screenshot remains absent.
5. Normal and recovery paths use the same publication evidence and image authority.
6. A changed candidate treatment invalidates the relevant model-cache entry while nonsemantic mirror observations continue to reuse it.

Assert observable behavior. Keep replication counts, reviewer order, exact candidate wording, exact logs, exact scores, word counts, timing, and internal call topology outside permanent assertions.

For the `attack-on-cancer` defect and any reviewer/parser defect, add permanent coverage only when a compact pure regression protects a stable user-visible or integrity contract.

### One-time implementation evidence

Keep these checks separate from permanent pytest:

- captured August 24 Stage 5 replay and decision report;
- private replay that exposes the `attack-on-cancer` exception safely;
- inspection of candidate scope diversity and reviewer reasons;
- controlled producer-to-publisher E2E;
- live August 24 publication and rendered-page inspection;
- independent editorial, publication-integrity, cache/recovery, security, and repository-rule reviews.

Temporary scripts and captured payloads live in a disposable run/debug location and are removed after their evidence is recorded.

### Verification commands

Run the repository's native environment and commands:

```bash
source source_me.sh && pytest tests/ -k 'daily_blog and (stage5 or publication_admission or recovery or route_cache)'
source source_me.sh && python3 tests/e2e/e2e_daily_publication.py
source source_me.sh && pytest tests/
```

Run the sibling publisher's documented offline compatibility checks when producer or bundle semantics change. Then perform the one-time live acceptance run:

```bash
source source_me.sh && ./make_blog.py -d 2026-08-24 -y
```

## Live acceptance criteria

The manager and fresh independent reviewers can close this plan without human interaction when all of the following evidence exists:

- The command completes publication for August 24 whenever at least one eligible complete-post path survives.
- The ranking and promoted candidate artifacts show a meaningful narrative choice rather than automatic inclusion of every survivor in the main arc.
- The published article gives the selected significant development room for specific technical detail, maker perspective, and unresolved next steps while treating routine coverage compactly.
- Full survivor coverage, grounding, provenance, recovery, and publication integrity remain intact.
- A relevant screenshot associated with the selected narrative is available to the editorial stages and can reach the bundle and page when cited. Image use remains an editorial choice rather than a success condition.
- The `attack-on-cancer` `implementation_defect` has an identified root cause and verified correction, or a precise remaining infrastructure fault is recorded with its owner.
- Reviewer, editor, or synthesis failures produce transparent degradation while preserving the strongest eligible incumbent.
- Approved prompts, rubrics, `docs/BLOG_CONTRACT.md`, and Hermes route ownership remain byte-identical.
- Focused tests, the controlled E2E, the full permanent suite, sibling publisher compatibility checks, and `git diff --check` pass on the final tree.
- Independent reviewers approve editorial-scope behavior, publication-surface integrity, cache/recovery semantics, security boundaries, repository-rule compliance, and test hygiene.

The live article is one-time acceptance evidence, not a permanent exact-prose fixture. Record reviewer findings and artifact identities without converting stochastic prose into a brittle test oracle.

## Documentation and closeout

After verification:

1. Add a dated `docs/CHANGELOG.md` entry that states the causal defect, the implemented ownership change, permanent-test disposition, one-time evidence, live run identity, bundle hash, and rendered-page hash.
3. Update current operational or architecture documentation only when the implemented behavior changes an operator-visible command or durable ownership boundary.
4. Record protected-file hashes or byte-comparison evidence for prompts, rubrics, and `docs/BLOG_CONTRACT.md`.
5. Move this completed plan to `docs/archive/daily_blog_spotlight_acceptance_repair.md`.
6. Verify the active-plan index contains no stale reference to this plan.

## Explicit non-goals

These boundaries are stated because they protect human-owned or already accepted contracts:

- Prompt and rubric editing belongs to a separate small, reviewable, human-approved change with output evidence.
- This plan does not introduce a minimum quality score, fixed spotlight count, mandatory screenshot, exact word allocation, or perfection gate.
- This plan does not replace model-produced recovery with deterministic mechanical prose assembly.
- This plan does not change provider, model, account, or credential ownership.
- This plan does not turn historical live artifacts or sibling repositories into permanent pytest fixtures.

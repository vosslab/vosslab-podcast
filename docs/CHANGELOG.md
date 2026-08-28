## 2026-08-27

### Additions and New Features
- Added `docs/HUMAN_GUIDANCE.md` as the durable local record for affirmative
  model-instruction design, context omission, concrete ownership, and explicit output contracts.
- Preserved every attributed commit-parent edge and explicit branch-tip snapshot in the
  authoritative evidence contract, including non-linear same-day histories.
- Added immutable editorial projection v1 and `pipeline/daily_blog/projection.py`. The projection
  keeps one compact card and reserves one highest-authority citable excerpt per active repository,
  then fills remaining capacity through stable authority-ranked repository round robin.
- Added v3 author, referee, repair, and rubric files and moved the byte-preserved v2 contracts out
  of the active prompt directory into `docs/archive/prompt-contracts/v2/`.

### Behavior or Interface Changes
- Cut the producer to bundle v2, evidence v3, run v2, generator v2, prompt/rubric v3, and editorial
  projection v1 without compatibility aliases.
- Split daily-blog limits into `collection_limits`, `projection_limits`, and `prompt_limits`.
  Complete author and referee prompts now own their full envelopes after templates, rubric,
  candidates, and filtered projection context are rendered.
- Inserted `editorial_projection` between evidence assembly and author generation. The phase is
  hash-cached, persisted as `editorial_projection.json`, and bound to author artifacts, referee
  decisions, front matter, and bundle metadata.
- Removed the technical fallback publication path. Missing valid candidates, `NONE`, route failure,
  or prompt failure raises `EditorialBlockedError`; no bundle or publisher import follows.
- Removed the publication-quality field from active candidate front matter, decisions, bundles,
  lifecycle events, tests, and producer documentation. Every created bundle is an approved final
  publication by construction.
- Classified daily-publication verification by lifetime. Stable schema, evidence, editorial,
  bundle, lock, and importer properties remain permanent tests; host-state and historical cutover
  proofs remain explicit operator checks.
- Removed the fixed August schedule gate and its derived pass/fail threshold from production. The
  historical evaluator now emits measurements for human review. The operator later superseded the
  temporary activation gate to restore publication, and the timer is active while quality review
  remains pending.
- Replaced one-date persistent-timer catch-up with a durable cursor that drains up to seven missed
  report dates oldest-first and advances only after the publisher success record is present. A
  missing cursor now bootstraps only from the explicit `daily_blog.schedule_start_date`; without
  that operator-owned boundary, reconciliation fails closed instead of silently skipping history.
- Added a durable schedule-level JSONL event stream for activation, cursor reconciliation, per-date
  work, advancement, completion, and bounded failure classes. Independent logging sinks cannot
  change the publication result.
- Deep-froze evidence collection limits, mirror snapshots, and editorial projection limits before
  computing their content identities, so caller mutation cannot invalidate an allegedly immutable
  artifact.
- Shared prompt loading now validates direct desired-outcome language before model routing. Daily
  author, referee, repair, rubric, and shadow templates use the same policy.
- Rephrased active blog, Bluesky, podcast, outline, depth-polish, referee, and speaker-style prompts
  around the content, factual source, structure, and exact output each model should produce.
- Moved blog and Bluesky repair instructions from Python string assembly into versioned prompt
  templates so retries receive the same validation and editing workflow as first-pass prompts.

### Fixes and Maintenance
- Split GitHub fetch support and deterministic outline parsing/rendering into dedicated `podlib`
  modules. The executable stages now own orchestration while reusable behavior, types, and artifact
  contracts live with their direct tests.
- Limited referee evidence to projection excerpts cited by candidate paragraphs while retaining all
  active repository cards, and rejected generic date-derived Work log titles.
- Made a projected screenshot's confined, hash-bound publication path its authoritative citation,
  removing a redundant model-authored evidence comment that could reject otherwise valid posts.
- Added structured lifecycle events for every producer run. Independent best-effort `events.jsonl`
  and stdout sinks report run creation, phase progress, cache reuse, safe failure classes, and
  terminal bundle/import state without letting a logging failure overturn authoritative run state.
  Structured events omit raw exception text; ordinary stderr traceback lines can retain it.
- Made the referee's bounded explanatory reason non-controlling: a valid winner, evidence-quality,
  and confidence decision now persists a deterministic 500-character summary instead of blocking
  publication when the model supplies an overlong explanation. Tuned prompt bytes remain unchanged.
- Validated publisher receipt status, report date, and bundle identity before completing the external
  import phase.
- Added an explicit-date publication preflight that validates the complete publisher-owned receipt,
  archive, installed post, and served release before any mirror or model work. An already published
  immutable date now returns its exact bundle instead of generating a competing candidate.
- Advanced the schedule cursor to v2, bound each completed date to its exact publication v2 bundle,
  and revalidated that publisher receipt before each backlog scan. Unsupported, missing, or divergent
  publisher state cannot silently advance or outrank the final-only cursor.
- Rotated older changelog day blocks into `CHANGELOG-2026-08a.md` after the active file crossed the
  800-line repository threshold.
- Refactored the daily orchestrator into explicit phase methods and added hash-verified reuse for
  activity, evidence, fully valid author output, validation, final referee decisions, and completely
  revalidated immutable bundles. Editorial cache identities bind the exact validated author,
  referee, repair, and rubric bytes rather than trusting version labels alone. Blocked and failed
  editorial outcomes remain retryable, and the importer still executes to confirm external
  idempotency.
- Replaced Git-HEAD provenance with an exact 64-character SHA-256 fingerprint over producer source,
  configuration, projection policy, and prompt/rubric bytes, so dirty source and contract changes
  invalidate cached publication artifacts.
- Made evidence providers traverse every exact revision range and relevant branch-tip snapshot, so
  changelogs, documentation, diffs, README context, and screenshots retain independent branch work.
- Resolved producer and publisher repository roots through Git instead of fixed parent traversal.
- Coordinated bundle v2/evidence v3/projection v1 validation with the publisher importer, including
  exact range, snapshot, excerpt, asset, and provenance checks.
- Strengthened the permanent bundle contract test to verify that `latest.json` identifies the
  newly completed immutable run and bundle.
- Moved temporary-repository Git process checks from the pytest fast lane into durable direct E2E
  programs for exact evidence and mirror refresh behavior.
- Renamed the complete cross-repository runner as a permanent publication E2E and removed its
  one-time assertion about retired filenames.
- Removed brittle tests of checked-in route defaults, fixed editorial threshold text, collection
  lengths, and cutover dates. Retained stable error detection, round trips, behavioral ordering,
  provenance, idempotency, and atomic-failure guarantees.
- Synchronized shared style guides, tests, and repository support files from the starter template.
- Synchronized shared style guides, tests, and repository support files from the starter template.

### Developer Tests and Notes
- The fetch/changelog/outline behavior selection passed 23 tests, the focused structural and hygiene
  selection passed 1276 tests, and `source source_me.sh && pytest tests/` passed all 1716 tests.
- Python 3.12 compiled every changed Python file. Its direct pytest run was unavailable in this
  environment because the Python 3.12 installation does not contain the `pytest` module; the required
  repository command resolves to the installed Python 3.13 pytest executable here.
- Confirmed the supplied projection contract started red because `daily_blog.projection` was absent;
  its five deterministic projection and envelope tests now pass.
- Focused daily-blog, settings, and prompt-policy tests passed: 57 tests. Focused typing, import,
  pyflakes, whitespace, ASCII, source-size, and shebang checks passed: 209 tests.
- All 13 direct E2E runners passed, including exact-Git evidence, bundle v2 import into a strict
  temporary MkDocs publisher, nine-phase projection reuse, and idempotent reimport.
- Added fault-injection coverage for independent event-file and stdout failures, real failure-message
  redaction, strict importer receipts, ordered schedule recovery, crash reconciliation, and bounded
  activation slices.
- The focused daily-publication and schedule suite passed 35 tests; changed-file typing, pyflakes,
  and ASCII hygiene passed 83 checks; the direct producer-to-publisher E2E passed.
- The installed schedule service reconciled the existing August 26 publisher record without
  regenerating it, exited 0, and persisted the cursor through August 26.
- Added permanent direct E2E coverage for non-linear exact-Git evidence and for a second immutable
  run reusing approved phase artifacts, its validated bundle, and an idempotent site import.
- The focused positive-prompt and content-pipeline suite passed 66 permanent tests, and all 13
  direct E2E runners passed under Python 3.12.
- The full producer test command reported 1914 passing tests. Its 32 failures remain confined to
  established typing, vendored-document link, and oversized legacy source gates outside the daily
  publication rebuild. The producer-owned `pytest_sessionstart` hook now carries its native
  `pytest.Session` annotation and passes the repository typing gate. `tests/conftest.py` derives the
  checkout root from its own path and inserts that package parent on `sys.path`, so
  `automation.publish_daily_blog` imports correctly even when pytest starts outside the checkout.
- A live August 26 rerun `20260828T003950Z-bdee87fdc1` completed all editorial and bundle phases. The
  clean pre-production cutover imported final bundle
  `d6d06817bec1b057411b10d135400e0db8024a7f750f603bd45c630d783c5799` with the thematic title
  `Making the Interface Tell the Truth`. The exact publication-v2 record, four byte-identical archived
  artifacts, all ten assets, strict site build, served release pointer, live thematic HTTP route,
  durable schedule cursor, active static service, and enabled timer were verified.
- A one-time complete-library audit loaded and validated all 40 active prompt templates through the
  shared runtime policy. The scratch audit program was removed after use.
- A one-time local profile confirmed that the preserved August 22 and 23 posts both satisfy the v2
  structural contract: first-person voice, four narrative H2s, compact openings, Project coverage,
  and 613/636 narrative words. The scratch profiler was removed after use.

## 2026-08-26

> Historical implementation record. The 2026-08-27 bundle-v2, projection, final-only, and durable
> scheduler contracts supersede the fallback and fixed-date behavior described in this section.

### Additions and New Features
- Added `automation/publish_daily_blog.py` as the single explicit-date command for mirror refresh,
  activity location, evidence assembly, two-author generation, deterministic candidate validation,
  anonymous referee selection, immutable bundling, and local site import.
- Added the typed `pipeline/daily_blog/` package with independent mirror, activity, evidence,
  editorial, bundle, publisher, run-state, locking, hashing, configuration, and schema boundaries.
- Added exact-object changelog, changed-documentation, diff, README, screenshot, and commit-metadata
  providers with authority-ranked `EvidenceItem` records and explicit context budgets.
- Added versioned affirmative author, referee, repair, and rubric templates under
  `pipeline/prompts/`, with prompt validation and standard-input role routing.
- Added `vosslab-daily-publication.service` and `.timer` as the one scheduled producer/import job for
  the previous completed Central-calendar date.
- Added focused temporary-Git provider, mirror lock, editorial isolation, schema, bundle, and
  cross-repository synthetic publication tests.
- Added `automation/evaluate_daily_blog_shadow.py` and `daily_blog.evaluation` for immutable,
  non-publishing historical comparisons with generated/reference posts, exact evidence, candidate
  validation, and typed reader-interest and house-style scorecards.
- Added a hash-bound two-date schedule gate. The systemd service now skips before model execution
  until current August 22 and 23 scorecards pass every deterministic and semantic threshold.
- Restored `tests/e2e/run_all.sh` as the required direct end-to-end aggregate runner.
- Added [CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md), [FILE_STRUCTURE.md](FILE_STRUCTURE.md), and
  [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md) for the producer ownership contract.
- Added [DAILY_BLOG_OWNERSHIP_CUTOVER.md](DAILY_BLOG_OWNERSHIP_CUTOVER.md) and archived the obsolete
  revival plan and its branch scorecard as historical decision records.

### Behavior or Interface Changes
- Daily publication bundles now live under `out/<user>/daily_blog/YYYY-MM-DD/RUN_ID/`, while typed
  run records and hash-addressed reusable artifacts use separate `daily_blog_runs` and
  `daily_blog_cache` namespaces.
- `settings.yaml` now configures the publisher repository, mirror cache, report timezone,
  attribution identities, exactly two author routes, one distinct referee route, and evidence
  budgets by role.
- Matching `docs/CHANGELOG.md` date sections now remain complete and outrank supporting evidence
  before any prompt rendering.
- Bundle referee records now preserve the anonymous label-to-candidate mapping so the publisher can
  prove that a final post is the exact valid candidate selected during judging.
- Complete evidence now produces a deterministic provisional post when candidate validation or
  referee approval remains pending.
- Advanced the editorial prompt and rubric contracts to v2 with the August house style: a compact
  opening realization, strongest-thread emphasis, evidence-supported cross-project synthesis,
  350-650 narrative words, two to four thematic sections, a closing current state, and complete
  active-repository coverage.
- Made role routes transport-only. Hermes routes now use standard input with `--ignore-rules`, and
  configuration rejects profile skills, inline queries, and resumed sessions as additional
  instruction sources.
- Made historical model data sharing an explicit default-deny contract. Shadow semantic evaluation
  now stops before route execution until the configured destination is approved in settings.

### Fixes and Maintenance
- Removed the superseded M2/M3/M4 `daily_github_*` commands and library modules, the private static
  site operations guide, and v1 daily editorial templates at the no-compatibility cutover.
- Bounded role failures and typed failed-phase serialization so external command output cannot
  corrupt or mask the authoritative run record.
- Added deterministic final-candidate gates for opening shape, narrative length, section count, and
  complete Project coverage while preserving the concise provisional contract.
- Brought every new daily-blog source and test under the repository typing, Bandit, import, pyflakes,
  shebang, whitespace, and source-size gates, including the cross-repository importer loader.
- Completed the repository hygiene-helper migration in broad-pipeline and direct E2E tests by
  replacing imports of the removed `git_file_utils` module with the current `file_utils` helper.
- Updated [README.md](../README.md) and
  [OUT_DIRECTORY_ORGANIZATION_SPEC.md](OUT_DIRECTORY_ORGANIZATION_SPEC.md) to document the current
  producer-to-publisher bundle interface and generated paths.

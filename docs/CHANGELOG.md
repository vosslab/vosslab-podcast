## 2026-08-31

### Fixes and Maintenance

- Advanced transfers to bundle v9; its portable `PublicationSurface` owns survivor evidence,
  images, coverage, assets, admission, and page verification. Bundle v8 is historical evidence.
- Covered Stage6Input-to-bundle and actual publisher import/page seams with offline checks,
  including an unselected aggregate screenshot that remains outside survivor assets.
- Kept semantic cache identity on selected commits, evidence, and prompts; advanced run
  state to v12; removed the pre-survivor projection gate; bounded Stage-5 comparisons and
  the complete Stage-6 context; aligned archived evidence reads at 128 MiB; and retained
  the one historical phase required for valid terminal-receipt replay.

### Developer Tests and Notes

- The latest-release harness re-reviewed two README images; protected
  `docs/BLOG_CONTRACT.md` and approved prompt assets remain unchanged.
- Permanent verification passed: 3,728 producer tests, 1,462 publisher tests, and the
  controlled publisher E2E. One-time acceptance included the strict Python-3.13 build and live
  Aug. 27 run `20260831T183847Z-be18800c63`; it published 10,474 bytes with degradation. SHA-256:
  bundle `323a04478108a4a9fd068ea06e7f99716e24295de196d16436ae30494e74cff6`;
  page `1fe83125aed76a1ff77460d0e4d9982a6bbb4e8776a4e9cd58db0b9f876a7b0d`.

## 2026-08-30

### Behavior or Interface Changes

- Advanced the active producer-to-publisher contract to
  `vosslab.daily-blog.bundle.v8`. New bundles seal the portable
  `publication_source_safety.v1` version, executable 35-case corpus, and SHA-256
  `d50166736d79be7f7715cc0f7585fac71dfb2aecc1c631b10e01aeca2fb63c6b` alongside the selected
  artifact and grounded inputs. The producer marks unsafe reader-visible Markdown ineligible, the
  publisher independently rechecks it, and cache/reuse rejects stale schema or policy identity.
  Bundle-v7 and exact publication-v3 handling remain historical compatibility paths only; new
  imports continue to write publication v5 records.

- Historically advanced the producer-to-publisher publication contract to
  `vosslab.daily-blog.bundle.v7`. That sealed handoff contained only the
  validated Stage-8 selected post and its artifact identity; candidate and
  referee topology remains in producer-owned run artifacts.
- The acquisition, repository editorial, and publication-finalization modules
  own their respective phases, with typed incumbent establishment, replacement,
  and repair transitions.
- Recovery now promotes ordinary writer/editor peers before two sequential,
  whole-post V4-author paths: daily-outline expansion and repository-story
  merge. The strongest in-scope repository story is terminal provenance only
  and is never publishable or mechanically assembled.
- Repository scope is derived from authoritative cited evidence through Stage 8.
  Model-declared scope is an assertion checked against that provenance, not the
  authority. Recovery digests v5 bind scope, full packet, artifact type, and
  recovery rung.
- The prompt registry is a package with a documentation-only root and distinct
  definitions, loader, and editorial-contract leaves. It centrally declares all
  Stage 3--7 and V4 assets while each stage keeps its own editorial rendering.
- The producer's historical bundle-v7 deployment handed the validated snapshot to the sibling importer
  through a bounded hash-bound standard-input envelope. The publisher record is
  `vosslab.daily-blog.publication.v5`; the producer's `import-receipt.v2` binds
  the committed archive, installed post, and canonical reader-body digest.

### Fixes and Maintenance

- Stabilized the real daily-blog publication boundary after live-route design
  discoveries: recovery now distinguishes policy-only ineligibility from forged
  lineage, Stage 6 retains mechanically grounded drafts for editorial repair,
  and rendered-page verification binds `report_date` through semantic
  `<time datetime>` data rather than requiring an ISO spelling in visible prose.
- Completed the unattended real `2026-08-28` publication run
  `20260831T023101Z-00f0b92468` with degraded editorial outcome, authorized
  same-date replacement, and verified rendered page. It promoted
  `artifact-55ac6377bb909fb95ebbcfa1`; the sealed bundle SHA-256 is
  `38a796c05c4b12f91860dc5322f0b7c051e6b7ba43b7540f2bf2fb6384b68798` and the
  rendered-page SHA-256 is
  `c443aa25614504ca7ff508b7a397769404933869c420e41a8efebbcd1e4457a0`.

- Removed retired experiment, calibration, attestation, shadow, and fixture-runner
  paths after their replacement boundaries were verified.
- Archived nine superseded plan and procedure records and reconciled the active
  documentation with the current publication and CLI contracts.
- Applied the six-pass pre-merge audit fixes: reconciled the stale index/worktree
  mismatch so retired one-time harnesses and modules cannot be resurrected,
  removed `test_checkout_disk_budget.py` and milestone
  `test_daily_blog_m5_integration.py` under `PYTEST_STYLE.md`, corrected current
  run-evidence documentation, archived the root-plan review and repaired its
  tracker link, and removed the permanent M5 comment tag while adding the
  required Stage-6 and Stage-7 function separators.
- Removed the duplicate Stage-6 implementation plus retired atomic-path and
  fixture-route compatibility surfaces. Runtime configuration now has explicit
  stage owners, and the Stage-5 coordinator is split into readable phase helpers.
- Stage 6 now requires its current result shape, promotion is internal to its
  current editorial decision boundary, and the concrete editorial route runner
  revalidates sealed command, prompt, and working-directory inputs at the
  subprocess sink.
- Pruned prompt-byte, replica-topology, raw-schema, and default-storage tests
  that did not meet [PYTEST_STYLE.md](PYTEST_STYLE.md)'s durable-behavior rule.
- Preserved original reviewer-response salvage when a repair attempt fails, and
  added Stage-6 editor partial-failure coverage that retains grounded peer work.
- Parsed-but-ineligible primary candidates now proceed through recovery, while
  forged lineage and eligibility faults remain terminal. Stage 5/6 typed terminal
  faults commit validated cache effects for resumption, and route capacity
  accounts for the two sequential recovery envelopes.
- Unified local publication inspection with the same committed-publication
  archive validator used for importer receipts. Reader-page verification now
  checks the full ordered source-body projection inside the dated Material
  article, rather than accepting matching title and date chrome alone.
- Synchronized shared style guides, tests, and repository support files from the starter template.

### Decisions and Failures

- Retained stage-specific comparison and repair prose because the current assets
  are materially different. Shared mechanics are centralized, but no prompt
  prose or prompt bytes changed without human approval.
- Explicit-date replacement semantics remain governed by
  [HUMAN_GUIDANCE.md](HUMAN_GUIDANCE.md): interactive occupied dates require an
  exact `y`; scheduled `--yesterday` remains unattended.

### Developer Tests and Notes

- Permanent offline verification passed: 3,676 producer tests, 1,453 sibling
  publisher tests, and the retained controlled publication E2E. The real run
  above is one-time operational evidence, not a pytest case or a claim that
  stochastic model output is deterministic. No prompt prose changed, and
  `docs/BLOG_CONTRACT.md` remained SHA-256
  `306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`.

- Final focused integration coverage passed 346 tests. Focused hygiene, source
  size, typing, lint, security, and Markdown-link checks passed 1,550 tests.
- The controlled no-egress publication E2E passed through the public
  `--yesterday` entrypoint. It verifies sealed, date-owned publication integrity
  and same-date replacement; it does not claim live prose quality.
- Independent final source, security, and permanent-test-policy reviews accepted
  the current ownership, validation, and offline durable-behavior boundaries.
- `docs/BLOG_CONTRACT.md` remained byte-identical at SHA-256
  `306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`.
- The audit-fix record above reflects the final focused verification results.
- At this point in the migration, the manager-verified full fast suite passed
  3,356 tests after the then-current fixes. Subsequent focused fixes retain their
  own listed verification; this entry does not claim a later full-suite rerun.
- Daily-blog pytest coverage passed 494 tests. The permanent-test-policy audit
  accepted 494 behavior tests and 1,027 hygiene checks.
- The controlled `e2e_daily_publication.py` passed initial import, replacement,
  and forced page-fault preservation. Prompt-registry package split/source gates
  passed 139 focused checks; Markdown links (65), diff check, Bandit, pyflakes,
  and compilation passed.

## 2026-08-29 (M13 observability/retention and M14 validation acceptance)

### Decisions and Failures

- Corrected the remaining M14--M16 plan gates so completion is unattended: the required validation
  evidence is a self-generated no-egress five-case matrix, optional local historical observations
  have a structured unavailable disposition, and live model/network work is optional enrichment.
  The M14 reviewer rule is now publication/page verification plus recorded evidence-tuple and
  explanation parity, not a subjective prose-quality gate.
- Sequenced M15 verification by test tier: record and remove temporary E2Es before the aggregate
  runner, use focused checks and the controlled E2E per coherent group, then run aggregate E2E and
  full pytest once after the coordinated migration. Retained prompt identities are mechanically
  checked without editing or approving prompt prose; M16 will document automatic same-date
  replacement using controlled E2E evidence.
- Added M16's final reader-visible Aug. 28 demonstration: the public `make_blog.py --yesterday`
  semantics must yield recorded terminal-summary, sealed-bundle, and published-page evidence.
  Controlled self-generated no-egress evidence injection is the completion path; any live external
  run is optional and provenance-labelled rather than a claim about synthetic prose quality.
- Accepted M14's mechanically reviewed durable validation record: five self-generated fixed-date,
  no-egress fixture cases reached verified pages with sealed provenance-to-publication evidence.
  The accepted record distinguishes editorial degradation from typed pipeline faults, keeps local
  historical and live external work non-gating, and leaves the Aug. 28 public-entrypoint proof to
  M16.

### Additions and New Features

- Accepted direct date-owned run records with bounded redacted step events, terminal date summaries,
  and an advisory reliability reporter that preserves raw counts and absent-population `n/a` values.

### Behavior or Interface Changes

- Run retention is now an explicit, command-start-age policy under the date lock. It retains the
  date-level publication and summary while expiring only validated terminal receipted run children.
  Descriptor-relative no-follow traversal prevents redirected deletion targets.

### Developer Tests and Notes

- Final security and permanent-test-policy re-reviews accepted the descriptor-pinned retention and
  offline durable-behavior test boundary. Independent focused verification reported 71 checks; the
  manager's M13 selection reported 127 focused tests and the sole controlled publication E2E
  passing. No broad suite was run.
- `docs/BLOG_CONTRACT.md` remained byte-identical at SHA-256
  `306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`.
- `pipeline/daily_blog/orchestrator.py` exceeds the repository source-size limit. M15 must split or
  remove superseded paths before its full-suite removal gate; this acceptance grants no exception.
- Matrix and RunStore source, security, and test-policy reviews accepted the bounded
  descriptor/observability boundary. The durable record retains `detailed_retention_days: null`
  because no grounded positive-day value exists and names every temporary M14 harness for deletion
  before M15 aggregate E2E.

## 2026-08-29 (M12 multi-repository acceptance)

### Behavior or Interface Changes

- Accepted the multi-repository editorial boundary: one frozen repository projection set drives
  capacity, concurrent repository-isolated Stage 3/4 jobs share one run budget, and only validated
  eligible work enters the serialized durable cache and canonical survivor join.
- Cache fingerprints now use portable semantic input rather than transient run or filesystem
  identity. Partial route failure preserves eligible grounded work; no surviving publishable pair
  produces a typed evidence-grounded pipeline fault rather than assembled prose.

### Fixes and Maintenance

- Removed stale provider and executor-topology tests per `PYTEST_STYLE.md`; they encoded obsolete
  implementation seams rather than durable user-visible behavior.

### Developer Tests and Notes

- Independent cache/capacity, source-ownership, adversarial-concurrency, and final acceptance
  reviews accepted M12. The affected focused suite passed 174 tests in 3.54 seconds and the
  controlled `tests/e2e/e2e_daily_publication.py` passed. No broad suite was run.
- `docs/BLOG_CONTRACT.md` remained byte-identical at SHA-256
  `306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`.

## 2026-08-29 (M11 Stage 7 acceptance)

### Behavior or Interface Changes

- Accepted Stage 7 synthesis as an incumbent-preserving editorial decision. An eligible challenger
  advances only on demonstrated direct improvement; synthesis loss or no demonstrated improvement
  preserves the exact grounded Stage-6 post through Stage 8 and publication.
- Recorded exact recovery-generation lineage, a truthful two-summary legacy importer projection,
  and logical root-contained operational run-state paths. Existing evidence-v4 absolute cache
  paths remain an explicit versioned producer/publisher migration boundary.

### Developer Tests and Notes

- Final behavior review accepted 133 lean focused tests and the controlled
  `tests/e2e/e2e_daily_publication.py` path. `docs/BLOG_CONTRACT.md` remained byte-identical at
  SHA-256 `306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`.
- The Stage-7 and recovery E2Es remain one-time implementation evidence. M14 will record their
  commands and results, then remove them; they are not permanent gates.

## 2026-08-29 (M10 Stage 5 acceptance)

### Additions and New Features

- Accepted the Stage 5 daily-outline path: independent ranking and outline candidates, strict
  reviewed promotion with bounded structured-verdict repair, scope-marked Stage 6 handoff, retained
  low-ranked context, and typed terminal recovery without mechanical prose assembly.

### Behavior or Interface Changes

- Production now runs Stage 5 before Stage 6 with the same route-budget and cache objects. Its
  sequential call capacity reserves Stage 5 plus Stage 6; Stage-5 summaries are non-incumbent and
  Stage 6 alone may advance the publishable artifact.

### Developer Tests and Notes

- Final architect acceptance recorded 41 focused integration/recovery tests, 33 focused Stage-5
  tests, the no-egress daily-outline E2E, and the controlled publication E2E. Compilation,
  Pyflakes, and diff checks passed; no broad or static suite was run. `docs/BLOG_CONTRACT.md`
  remained byte-identical at SHA-256
  `306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`.

## 2026-08-29

### Additions and New Features

- Added independently resumable complete-post route calls, bounded parallel execution, replicated
  pairwise review, strict structured-verdict repair, and pure incumbent-preserving promotion. The
  coordinator retains eligible author work across retries and writes all shared cache and run state
  serially.
- Added run-state v5 editorial reliability summaries with raw attempt, success, failure, reuse,
  repair, and disagreement counts plus one explicit `best_artifact_id`. Bounded lifecycle events
  expose those facts without prompts, model output, or raw external diagnostics.

### Behavior or Interface Changes

- Production complete-post generation now requests three independent candidates and three reviews
  per eligible pair, with at most six simultaneous calls and a 24-call run budget. Counts and limits
  remain settings-owned and cache identities retain compatible ordinal work when they change.
- Expected route and verdict failures now degrade the matching editorial step while eligible whole
  posts continue. No eligible post records `editorial_blocked`; corrupted caches, unsafe identity or
  path state, invalid configuration, and unexpected defects remain pipeline failures.
- Replaced positional and all-or-nothing referee behavior with stable eligible-peer promotion.
  Candidate order varies deterministically, duplicate alternatives are observable, one malformed
  verdict receives a bounded repair attempt, and no fallback mechanically assembles final prose.

### Fixes and Maintenance

- Closed the maker-voice fixup with the descriptor-snapshot TOCTOU repair and removal of arbitrary
  test gates. The final acceptance path remains fixture-backed; live model work is optional
  corroboration and no completion step depends on human approval.

### Developer Tests and Notes

- Replicated-editorial focused coverage passed 106 tests, including a coordinator-level degraded
  author path through validation and promotion. The daily-blog pytest selection passed 1,158 tests;
  its only two failures were established shebang/executable-bit findings outside this change.
- The full suite passed 2,584 tests. Seven hygiene checks failed: six established findings in
  unrelated automation/E2E files and one new-file Markdown-link visibility issue that was corrected
  and then passed with the 64-test Markdown/reliability selection. The controlled publication E2E
  could not start because its sealed `out/` fixture is absent from this checkout.
- F7 accepted: Python 3.12.13 producer suite 2,450 passed with 0 failures; Python 3.13.5 publisher
  suite 1,362 passed with 0 failures; publisher hygiene 310 passed; strict disposable MkDocs build;
  publication, 12-case crash, and schedule E2Es; and four independent requirements, security,
  test-policy, and maintainability audits. Approved prompt hashes match.

## 2026-08-28

### Additions and New Features

- Added the pre-production maker experiment's three-stage evidence boundary. Fresh capture writes a
  sealed `vosslab.daily-blog.prompt-experiment-capture.v3` artifact, attestation v4 joins a completed
  capture with passing live calibration, and its immutable contract records a bounded configurable
  count of independent, passage-grounded artifact reviews before F4 can be accepted.
- Added executable repository-root `make_blog.py` as the single manual daily-blog
  command. `--yesterday` uses the configured report timezone; `--date` accepts
  canonical `YYYY-MM-DD` and the requested unambiguous `YYYY-DD-MM` form before
  delegating one canonical date to the date-owned publication workflow.
- Refreshed the complete repository documentation set across the README, architecture and file
  structure, install and usage, release and news, related projects, operational guides, file formats,
  roadmap, and remaining work.
- Added reproducible offline documentation capture with
  `automation/capture_work_log_screenshots.mjs` and two managed README images:
  `docs/screenshots/work_log_landing_page.png` and
  `docs/screenshots/making_the_interface_tell_the_truth.png`.
- Added authoritative fresh GitHub owner-roster discovery, immutable roster artifacts,
  owner-qualified repository caches and locks, typed repository-creation lifecycle evidence, and
  an Aug. 26 regression proving `vosslab/cancer-clicker` becomes a first-day story candidate.
- Added first-class immutable owner-roster snapshots and content-addressed experiment fixture v2.
  Fresh Aug. 23 and Aug. 26 fixtures now bind the same verified 111-repository snapshot without a
  publisher-bundle bootstrap dependency.
- Added a fail-closed historical maker-rubric calibration command, immutable resource contract,
  fixed Aug. 22-26 loader, structured repeated scorecards, private artifacts, and a route-free
  calibration report. Preparation identity
  `0df85dd7fdd48428353d0e6bde893acfaa21d4b23f66ffd267565a36c2ce6169` used no model route.
- Added a manager-ready daily-blog integration plan centered on the approved maker-voice contract,
  producer orchestration, publisher integrity, and the direct 04:00 systemd path. The plan treats
  `hermes chat --provider openai-codex --query-file - --ignore-rules --quiet` as the complete
  external model boundary;
  Hermes continues to own model credentials and account selection internally.

### Behavior or Interface Changes

- Activated `v4-three-examples-corpus-v2` through maker activation
  `daily-blog-maker-activation-6b104be9c6907eeeffcf330f6b10173857b39c6b05baa46d4cf009a67daa7547`.
  The producer now emits bundle v5 for the publisher's active v4-maker policy v3 boundary.
- Recorded the repository's durable plan-and-test guidance: gates require a real behavioral, policy,
  evidence, or failure-mode basis; one-time proof stays distinct from permanent offline pytest; and a
  test that forces unrequested production behavior is presumed defective before code is distorted.
- Advanced historical calibration to schema v2. Each run now retains exact cited passages and
  reasons; the sealed artifact records the bounded repetition count, score-span tolerance, and
  positive/negative separation threshold instead of requiring exact repeated-score identity or
  making one-time settings permanent pipeline behavior.
- Changed deterministic experiment acceptance from `activation_ready` to `review_ready`.
  Attestation v4 embeds the unchanged central maker question, sealed fixture identities, and an
  artifact-only contract with a bounded configurable reviewer count. It binds the exact complete
  busy and quiet first-sample paths and SHA-256 identities without consulting experimental outcomes;
  later repetitions remain diagnostic, and F5 remains unavailable until every required independent
  review accepts both posts.
- Made route failures redact external stdout, stderr, command details, paths, account labels, and
  prompt material while preserving stable timeout, startup, nonzero-exit, and empty-response
  categories at the strict Hermes parser boundary.
- Made the podcast's current publication contract an explicit single registry owner and separated
  every trusted comparison arm into a non-production registry. Publication now asks that owner
  directly before any collection side effect, so a later evidence-backed maker activation has one
  cutover point instead of duplicated identity checks; approved prompt bytes remain unchanged.
- Made publisher replacement intent explicit for every direct and CLI orchestration call. Run state
  v4 now persists only the failed phase and a fixed diagnostic category, keeping exception text and
  secret-like values out of both lifecycle state and events.
- Advanced the immutable producer candidate-validation records to policy v3 without compatibility
  aliases. Active `v3-historical` is
  `aada487814ca0080d4a49648440ee6614e5f3a3628be6197ffafcef242969324`; experimental `v4-maker`
  is `3a4b7148579e509b6c32fa19b31d107dc4278eb5f721b2a01353a1a9a51264ee`. Both declare a
  24,000-character candidate cap, one excerpt marker, one opening prose block, no pre-marker H2,
  and a 100-word opening cap. Policy versions 1 and 2 reject without compatibility behavior.
- Kept active v3 production and v4 experimentation separate: the publication orchestrator rejects
  v4 before lock acquisition, mirror refresh, model routing, bundle writing, or publisher import.
  The publisher independently enforces the same policy shape and imports only active v3 policy v3.
- Cut the pre-production evidence boundary to evidence v4, editorial projection v2, and run v4.
  Projection exposes `new_source_repository` and puts same-day new source repositories before
  routine cards while leaving the author and referee responsible for the final editorial choice.
- Advanced the producer/publisher boundary to bundle v4. `report_date` is the sole publication
  identity, `bundle_sha256` is integrity-only, and one stable `publication/` directory holds the
  current validated bundle for that date.
- Made existing-date behavior explicit at the root command. Interactive runs ask
  `Overwrite YYYY-MM-DD? [N/y]:`; exact `y` replaces through one per-date lock, while unattended
  runs preserve the coherent installed date and exit successfully without model work.
- Made systemd the sole schedule owner. The 04:00 America/Chicago service directly calls
  `./make_blog.py --yesterday`; Hermes remains the configured model/provider runner inside prose
  generation, and the retired cursor/backlog wrapper is removed.
- Made `source_me.sh` select and positively verify a physical repository-local Python 3.12
  environment instead of inheriting an ambiguous shell interpreter.
- Made the repository-root blog command enforce that same Python 3.12 boundary after relaunch and
  added a direct executable E2E that exercises help and fail-closed date parsing without reaching a
  model route or publisher.
- Reserved one highest-authority budgeted evidence item for every active repository before routine
  supporting material. Projection can now enforce citable coverage without global-budget
  starvation dropping a newly discovered repository.

### Fixes and Maintenance

- Repaired the sealed prompt-fixture handoff at its schema owner. The capture writer and experiment
  consumer now share one strict v2 manifest contract instead of emitting the documented rich
  identity while loading a stale reduced shape. The consumer also cross-checks the sealed packet,
  projection, roster, mirror summaries, byte counts, and file hashes. Both approved busy and quiet
  fixtures now pass route-free production loading and prompt rendering without recapture or model
  egress.
- Added Hermes quiet mode to the sealed author and referee route so programmatic stdout contains the
  final model response while session diagnostics remain on stderr. The strict JSON and Markdown
  parsers stay fail-closed instead of learning to strip CLI decoration. Process failures now expose
  only stable error categories rather than raw external stdout, stderr, commands, paths, or prompts.
- Corrected the maker-fixup autonomy boundary: deterministic local work remains autonomous, while
  historical-post calibration and sealed project-evidence capture each require direct operator
  authorization for their named payload and configured model route.
- Replaced alternating single-order maker-post comparisons with a complete paired order matrix.
  Every generated candidate pair now reaches the anonymous referee once as A/B and once as B/A;
  capture v2 verifies both positional records and their canonical-arm mapping, while acceptance v2
  requires v4 to win every repetition in both displayed positions before activation can be attested.
  Direct and CLI execution also share the calibration contract's bounded two-to-five repetition
  range, preventing accidental unbounded route work.
- Replaced anonymous/settings-backed GitHub discovery with one runtime credential boundary. The
  collector accepts an explicitly injected `GITHUB_TOKEN` or reads only that named value from the
  active `$HERMES_HOME/.env`; it never sources neighboring Hermes credentials or places the token in
  generated artifacts and logs. Manual and systemd publication now share authenticated discovery.
- Made `repository_contracts.py` the sole owner of repository identities, roster records,
  lifecycle events, and canonical repository timestamps. Production, capture automation, and tests
  now use that module directly; `schema.py` no longer re-exports a compatibility surface.
- Corrected current documentation to the physical repository-local Python 3.12.13 bootstrap,
  distinguished its contract-test evidence from the remaining real-route activation gate, clarified
  the current bundle v4 and publication-date identity, and renumbered the active
  maker-voice plan through milestones 15 and 16.
- Corrected the daily-blog fixup scope after review showed that it had expanded into a separate Hermes
  capacity-routing project. The replacement dependency chain is podcast-owned: prepare the approved
  maker candidate, simplify producer orchestration, retain grounded deterministic tests, complete and
  review the existing empirical evidence, activate the attested winner through one producer/publisher
  cutover, and verify the tracked schedule. Existing
  Hermes account selection remains an accepted external service behind the normal `hermes chat`
  command. Scratch Hermes work and its former M2-M8 gates are superseded and do not participate in
  implementation, deployment, or closure.
- Classified permanent and one-time verification directly from the repository rules. Fast pytest
  retains offline deterministic behavior contracts; real model calls, process crashes, PTY and
  multiprocess checks, filesystem atomicity, strict publication, and systemd observations remain
  one-time evidence unless a durable E2E earns its maintenance cost. Editorial acceptance uses the
  complete-post maker question and August 22-23 as qualitative examples rather than output
  equivalence or arbitrary prose-shape gates.
- Expanded the historical daily-blog bring-up report with an account-selection investigation and
  implementation concerns in Hermes. Those notes remain background for the external service owner;
  they are not active fixup dependencies or podcast deliverables.
- Recorded the investigation's refresh-policy distinction for historical completeness. The podcast
  integration relies on the supported `hermes chat` boundary and does not implement or validate that
  internal policy.
- Applied the repository's fresh-subagent principle to blog creation. Each author, referee, and repair
  attempt receives a new isolated Hermes process and self-contained prompt. Deterministic project
  evidence may cross task boundaries; Hermes account and capacity state remains entirely behind the
  external CLI boundary.
- Consolidated durable human guidance around the intended operating model: Hermes owns model and
  account selection, systemd invokes `./make_blog.py --yesterday` non-interactively at 04:00, all
  non-content phases remain deterministic, one date has one replaceable result, interactive
  replacement requires exact `y`, and downstream prompt edits receive careful review.
- Reconciled release, roadmap, usage, architecture, ownership-cutover, and output-layout documents
  with the completed roster, lifecycle, and story-first salience contracts. The remaining v4 gates
  are live real-model comparisons, rubric calibration, and an evidence-based activation decision.
- Clarified the operating layers across the README, FAQ, usage, development, and troubleshooting
  guides: systemd owns the daily schedule and service boundary, while Hermes is the configured
  author and referee command runner inside the Python publication job.
- Aligned final Project coverage heading handling between producer and publisher, including raw
  heading behavior, while retaining the v4 compact-coverage boundary.
- Applied the final independent audit's mechanical Python cleanup: normalized validation-policy
  indentation, removed a duplicate function separator, and wrapped long changed lines.
- Removed one-time, mock-only, duplicate, and hygiene checks from the permanent E2E policy. The
  remaining direct runners each exercise a durable real boundary.
- Closed the final multi-reviewer audit findings: mirror paths reject symbolic-link escapes and
  nonexact origins, bundle reuse revalidates the current sealed roster, the experiment fixture
  retains quiet eligible repositories, and real Git work now runs only in the E2E tier.
- Corrected the reusable screenshot harness so Material's retained sticky-header state cannot crop
  the article capture. Both 1280x800 PNGs now assert a fully visible header and reproduce
  byte-for-byte on repeat capture.
- Sealed the prompt-experiment consumer boundary to the approved quiet Aug. 23 and busy Aug. 26
  fixture identities plus their shared authoritative roster. Wrong dates, fixture identities, and
  roster identities now fail before generation or private output creation; synthetic tests replace
  the allowlist only within their local scope.
- Pinned roster snapshot roots, snapshot directories, and artifacts with descriptor-relative,
  no-follow I/O so a concurrent pathname replacement cannot redirect verification. The experiment
  CLI now distinguishes a reviewed-rotation mismatch with a stable redacted diagnostic.
- Extracted neutral, consumer-allowlisted prompt loading and descriptor-pinned private-artifact
  primitives. Editorial, shadow evaluation, roster snapshots, and rubric calibration retain
  separate semantic ownership while sharing the hardened filesystem and instruction boundaries.
- Bounded the rubric repair prompt, pinned the rubric and both calibrator templates by digest, and
  kept live scoring behind both durable configuration and explicit per-invocation approval.
- Removed the prompt experiment's caller-selected output root. Configuration now owns the sole
  private `out/<user>/daily_blog_experiments/` namespace, matching the documented retention and
  non-publishing boundary.
- Separated fresh capture from calibration: capture contains only sealed experiment evidence, and
  calibration remains a distinct, explicitly approved historical-scorecard artifact. A valid
  deterministic attestation is the exact evidence boundary before a separately reviewed activation
  decision; it does not itself activate v4, publish, import, or alter the schedule.
- Corrected the external-data-sharing documentation to match its shadow/calibration scope,
  documented idempotent manual publication without a new run, and recorded the exact approval-gated
  command for the sealed non-publishing prompt comparison.
- Restored the complete direct E2E aggregate after its hygiene runners drifted from the shared Git
  enumeration API. The shared boundary now owns full-versus-changed selection, including untracked
  paths, without restoring the removed generic compatibility helper.
- Applied the follow-up six-pass audit's low-risk cleanup: removed unreachable experimental
  identity plumbing from the active-v3 orchestrator, dropped two tests that froze tunable prompt
  text and fixture identities, updated the remaining snapshot fixture after the Aug. 22 resource
  cut, corrected private-artifact import order, and reconciled the central maker question,
  idempotent-run wording, and audited Python-version wording in current docs.
- Removed remaining brittle prompt-text assertions from the experiment path. Tests now retain
  contract, acceptance, and isolation behavior without treating adjustable prompt prose as a
  stable interface.
- Split experiment result handling, private output transactions, and rubric-calibration artifact I/O
  into owning modules below the repository line limit. Private directory installation now uses
  atomic no-replace primitives on Linux and macOS and cleans partial stages on setup failure.
- Closed the final audit's publication-integrity and replacement findings. Existing-date inspection
  now verifies the complete v4 bundle, evidence, roster, projection, post, assets, release, and receipt;
  the pre-v4 Aug. 26 install is quarantined as occupied-invalid until confirmed replacement.
- Replaced remove-then-install directory moves with Linux/macOS kernel exchange operations. Stable
  producer and publisher directory names remain visible, transaction recovery fingerprints staged
  trees, and the publisher record is installed last as the authoritative commit marker.

### Developer Tests and Notes

- Accepted F4 fixture-backed capture, calibration, route-free attestation, and independent
  passage-grounded reviews; accepted F5 producer/publisher import and 12-case crash recovery; and
  accepted F6 disposable-root schedule evidence. F7 full suites and independent audits later accepted
  on August 29.
- Focused route, editorial, capture, calibration, and attestation behavior passed 92 offline tests;
  the post-repair fixture/capture/attestation selection passed 36 tests. Pyflakes, source-size,
  pytest hygiene, ASCII, prompt-resource, and Markdown-link checks passed 858 tests. The complete
  Python 3.12.13 suite passed all 2,418 tests, and all eight retained E2Es passed. Route-free
  calibration preparation reproduced identity
  `0df85dd7fdd48428353d0e6bde893acfaa21d4b23f66ffd267565a36c2ce6169`.
- A sandboxed live-calibration attempt wrote an incomplete private diagnostic after Hermes could not
  initialize its restricted state and log paths. The route contract is repaired, configuration
  remains opt-in, and no passing calibration, capture, attestation, winner, activation, or
  publication is claimed.
- The August 26 intake defect is closed in the local producer and publisher contracts. Fresh
  discovery bypasses the GitHub client's 24-hour list cache, fails closed on malformed roster data,
  and persists no token or raw remote payload.
- A live fresh owner query captured 111 repositories and proved `vosslab/cancer-clicker` is in
  scope. Mirror reconciliation added the four missing owner-qualified caches and verified all 111
  exact origins. The real Aug. 26 projection retains nine active repositories and places
  `vosslab/cancer-clicker` first with `new_source_repository` and citable excerpts.
- Producer verification passed 2,012 tests with 48 deselected under `-k not markdown_links`, the
  focused roster regression, and the complete producer-to-publisher E2E. An earlier full suite
  reached 2,059 passed with one README/Git-aware Markdown-link failure before the new documentation
  and PNG assets entered the index. The current full publisher suite passes 1,278 tests.
- The focused calibration, prompt-resource, editorial, and roster-snapshot set passed 55 tests;
  direct Pyflakes, Python compilation, MyPy, six daily-blog E2Es, route-free preparation reuse, and
  the fail-closed unapproved live command also passed.
- The non-link producer suite and the roster, prompt-contract, experiment-lifecycle, and publication
  E2Es now pass under the required Python 3.12.13 environment.
- The live Hermes route remains unresolved. No live rubric scores, generated-prose comparison, arm
  winner, or v4 activation is recorded by this change.
- Focused sealed-capture, calibration, prompt-experiment, and deterministic-attestation tests pass
  (29 passed). The direct attestation E2E passes with local route doubles and proves no route use,
  publication, importer, or activation.
- An authorized Hermes no-content smoke returned OK without a content payload. The attempted full
  project-evidence capture stopped at the external-action gate before payload egress; therefore no
  live capture, calibration, arm winner, activation, or publication is recorded.
- The requested six-pass audit reran against the complete staged, unstaged, and untracked change.
  Its low-risk root-command, E2E, import-heading, and documentation findings were remediated; the
  remaining findings and the uncompleted maker-voice activation gate are recorded in the audit
  handoff.
- Final editorial-cap and duplicate-test pruning removed six tunable or redundant checks. The
  permanent Python 3.12 suite passes all 2,238 pytest tests, and the eight real E2E runners pass.
  Compilation, Pyflakes, MyPy, Bandit, Markdown, ASCII, mode, and diff checks pass for the audit
  remediations.

## 2026-08-27

### Additions and New Features
- Added the unactivated v4 maker-voice experiment foundation: registered immutable 0/1/3-example
  contracts, a project-owned voice resource, snapshot-bound opaque generator identities, author and
  referee prompt packages, non-gating voice diagnostics, sealed fixtures, a non-publishing prompt
  harness, and an offline producer-side contract E2E.
- Added immutable per-contract candidate-validation policies v2. Active v3-historical retains its
  exact 350-650-word, two-to-four-section, paragraph-evidence control with
  `all_packet_activity`, `legacy_source`, and digest
  `28e50e99651096b2cc94c2f2023fda1fe492a205358dccd7b6eb381b3c020cb5`. Experimental v4-maker
  owns `projected_repositories`, `reader_visible_markdown`, section-level citation, maker bounds,
  and digest `8722d6dce7f789796784f63914fe240c1f1bdcd472e5be176f7e720f8b557947`. Version 1 policy
  records are rejected as ambiguous. The producer binds snapshot, generator, bundle, and reuse
  identities; the publisher independently enforces validation policy and exact active v3 import.
  The importer remains v3-only.
- Added maker-corpus and prompt-experiment status reports. They retain August 23 as the primary
  project-owned house-voice example, the `v4-three-examples-corpus-v2` arm with short attributed
  Julia Evans and Mitchell Hashimoto excerpts, the literature rationale, sealed fixture identities,
  and the blocked first live experiment result. The old quiet-day/August 22 three-shot arm is removed.
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
- Focused v4 prompt, candidate, citation, fixture, experiment, and voice-metric gates exercise the
  unactivated contract. The offline v4 contract E2E exercises producer-side rendering through the
  publisher validator boundary with the v4 policy passed explicitly; the publisher importer remains
  intentionally v3-only.
- The first private live prompt experiment scheduled 24 author generations across two fixtures,
  four arms, and three repetitions. All stopped at `author_generation` because the external Hermes
  route failed for tiny prompts; no comparison, quality conclusion, arm winner, or activation follows.
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

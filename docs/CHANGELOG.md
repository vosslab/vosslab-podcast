## 2026-08-28

### Additions and New Features

- Added the pre-production maker experiment's two-stage evidence boundary. Fresh capture writes a
  sealed `vosslab.daily-blog.prompt-experiment-capture.v2` artifact, while the new
  `vosslab.daily-blog.prompt-experiment-attestation.v2` schema, loader, and CLI join a completed
  capture with a passing live calibration and recompute the deterministic acceptance result.
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
  `aa1ceeb9d14db2c5d68b7be9c1369cf9231709f2cc0acc7a30f50570b74a2e87` used no model route.
- Added a manager-ready daily-blog integration plan centered on the approved maker-voice contract,
  producer orchestration, publisher integrity, and the direct 04:00 systemd path. The plan treats
  `hermes chat --provider openai-codex --query-file -` as the complete external model boundary;
  Hermes continues to own model credentials and account selection internally.

### Behavior or Interface Changes

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

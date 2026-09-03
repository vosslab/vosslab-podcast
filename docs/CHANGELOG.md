## 2026-09-03

### Behavior or Interface Changes

- Added monotonic elapsed-time reporting to every human-visible daily-publication step. Existing
  result lines now end with compact durations such as `completed in 54 sec` or `completed in 2m54s`;
  phases without separate result text receive a completion line, and the final line shows total run
  time. Timing remains presentation-only and cannot affect workflow state or publication decisions.
- Replaced the retired publisher-record/archive receipt dependency with
  `vosslab.daily-blog.import-receipt.v3`. The producer now verifies the installed Markdown and every
  selected image directly against its sealed transfer, then binds the rendered page separately.
- Kept selected images beside the date-owned Markdown under `docs/blog/posts/<report_date>/` with
  short `<report_date>/<filename>` Markdown links. New deterministic filenames include the source
  repository, a content-hash prefix, and the original image basename; multiple images remain supported.
- Defined `vosslab-podcast` as the owner of publication correctness, bundle meaning, validation,
  export, and delivery verification. Defined `vosslab-daily-blog` as a mechanical receiver,
  MkDocs renderer, deployer, and rendered-page verifier with no editorial admission authority.
- Made MkDocs the authority on Markdown renderability. The display repository does not pre-judge
  readability, structure, evidence grounding, citations, roster coverage, or whether supplied prose
  makes sense.
- Replaced the timestamped canonical run tree in the publication flow with one report-date-owned
  run log and artifact set.
- Removed the separate publisher-preflight phase and its validation-receipt protocol. The producer
  now verifies the renderer's import receipt against the sealed report date and bundle digest after
  delivery.
- Prevented publication-surface construction from re-expanding every evidence ID carried by an
  already-compressed editorial artifact into raw prompt excerpts. Complete evidence and artifact
  lineage remain durable while the LLM projection stays bounded.
- Changed image publication from screenshot discovery to final-post selection. The producer now
  transports only images referenced by the selected Markdown, using date-relative paths for assets
  stored beside the post; unreferenced screenshot evidence never reaches the display repository.
- Added a typed publication-image resolution layer that records stable evidence IDs, producer asset
  paths, final Markdown paths, and display destinations before bundle creation. This keeps editorial
  choice, deterministic routing, byte resolution, and transport filtering as separate responsibilities.
- Made publication bundles, candidates, reviews, projections, and other stage outputs working
  artifacts. They remain available to diagnose an incomplete run, then are discarded after verified
  delivery while the canonical run log and terminal summary remain.
- Reduced the renderer handoff to a transient routing manifest, final Markdown, and referenced image
  bytes. Evidence, rosters, projections, and publication-surface JSON remain producer-side.
- Added the stage-neutral complete-candidate-set review contract. It constructs exactly one request
  per independent reviewer, gives each request the entire canonical peer set in one deterministic
  ordering, and records one winner from that set. Five candidates and three reviewers now schedule
  three calls through this contract, not 60 pair/order calls.
- Extended promotion to consume complete-candidate-set votes directly. One strict plurality winner
  may be promoted without reconstructing candidate pairs; tied, failed, or otherwise inconclusive
  optional review preserves an existing publishable incumbent.
- Migrated repository-outline, repository-story, daily-outline, complete-post, recovery, and final-
  synthesis review to that complete-set contract. Ranking candidates are selected mechanically
  without a second judging wave, and the pair/order coordinates were removed from Stage 6 planning
  and cache identity.
- Removed the global route-call cap and all configured `max_route_calls` values. The shared executor
  now limits concurrency and records actual calls for diagnostics; it cannot abort publication
  because a separately maintained call counter was exhausted.
- Added a machine-authored repository-context summarizer prompt. When the cross-repository story and
  outline corpus would otherwise be excerpted, Stage D runs one summarizer per repository and feeds
  compact results forward. Missing or unusable summaries fall back to existing bounded excerpts and
  cannot remove repository identity or stop publication.
- Added the bounded image-decoration response contract and deterministic inserter. An editorial
  decorator may select up to three machine-catalog image IDs and prose-block positions; unknown IDs,
  malformed output, empty selection, or decorator failure preserve the publishable incumbent. The
  producer alone assigns date-owned paths and resolves the selected bytes.
- Wired a machine-authored image decorator prompt after final prose selection. It runs once when
  the machine catalog has images, targets one to three useful placements, and degrades to the exact
  undecorated post on transport failure, malformed advice, or an empty selection.

- Classified every `PUBLICATION_FLOW.md` artifact as machine-owned, LLM-derived and machine-wrapped,
  or the LLM-authored publication. Renamed editorial observation files away from `reliability`:
  `daily_outline_editorial.json`, `complete_post_attempts.json`,
  `complete_post_editorial.json`, and `final_synthesis_editorial.json`.
- Abbreviated the flow-table ownership labels to MOA, LDMW, and LAP while retaining their full
  authority definitions immediately above the tables.
- Replaced the Step-0 Markdown commit inventory with machine-owned `daily_active_roster.json`. It
  records the dynamic report-date repository set, exact commit references, truncated message
  previews, and a content-derived identity before any LLM work. The same artifact and identity are
  carried into the sealed producer-publisher bundle as provenance, not prose-coverage admission.
- Kept clone and fetch outcomes in `mirror_manifest.json`; recovery state does not create a parallel
  repository roster or redefine the authoritative daily roster.

- Replaced the public command's JSON event stream with a concise Rich progress display. Each run
  begins by naming its absolute machine-log path, then reports the selected date, active repository,
  commit and evidence counts, editorial received/reviewed/promoted totals, publication phases, and
  final outcome. Redirected output remains plain text.
- Renamed the per-run machine journal to `runlog-YYYY-MM-DD.jsonl`. Canonical JSON events remain
  durable there; human presentation has no authority over workflow state or publication admission.
- Added `PUBLICATION_FLOW.md` as the canonical A1-through-G6 map from human progress steps to durable
  filenames. The map explicitly permits zero-count and degraded model steps and defers all
  availability authority to `LLM_GATE_STYLE.md`; it is not a mandatory route topology.
- Documented the filename ownership rule: validated code-owned identities and fixed artifact names
  determine every path; model output never chooses or influences a filename.
- Clarified that deterministic repository derivation does not mean fixed membership. Every run
  fetches a fresh complete account roster and derives a fresh report-day active set; permanent tests
  verify the behavior with inline synthetic sets rather than freezing real repository names or
  counts.

### Fixes and Maintenance

- Moved Stage 6 phase start before its model work. Complete-post generation now reports its real
  elapsed time, and an exception during that work is attributed to Stage 6 instead of the previously
  completed daily-outline phase.
- Made image-decoration parsing salvage valid, unique catalog placements from a noisy response.
  Invalid or duplicate siblings and extra explanatory fields no longer discard usable image choices;
  unknown identities still cannot influence paths or transferred bytes.
- Removed the outline/story image-selection gate from the Stage 6 publication surface. Every
  provenance-validated survivor screenshot is now available to the final author and optional image
  decorator; deterministic final-Markdown resolution still copies only images the selected post
  actually references.
- Corrected publication-surface evidence validation to recognize its two typed channels: bounded
  prose excerpts and the available screenshot catalog. A screenshot no longer has to consume prose
  projection space merely to remain available for later editorial selection.
- Made primary Stage 6 observation tolerate an unavailable optional reviewer wave. When a complete
  peer set exists but its review prompt exceeds the configured bound, only observed generation slots
  are materialized and a usable peer continues instead of raising a missing-result `KeyError`.
- Fixed the August 17 `site_import` failure caused by the producer checking the renderer's removed
  `data/publications/` tree after a successful import. Removed the obsolete archive/record validation
  code and its tests rather than recreating renderer persistence that the current ownership boundary
  intentionally removed.

- Removed gate-like flow vocabulary including editorial `eligible`, `stable`, `admit`, and recovery
  topology wording. Daily-outline comparison context overflow now makes optional review unavailable
  instead of failing the usable outline incumbent.
- Removed the obsolete ranking-review wave, pair-specific daily-outline context builder, pairwise
  prompt resources, pairwise replication API, and the permanent route-budget exhaustion expectation.
- Audited the gate cleanup with six independent review passes. Removed the evidence-budget and
  projection vetoes that required one citable item for every active repository, and deleted the two
  permanent tests that enforced that obsolete all-repository gate.
- Bound `daily_active_roster.json` to its exact A1 `repository_roster.json` identity, owner, report
  date, and repository universe at bundle creation and sealed-transfer validation. This is a
  provenance boundary and does not compare the roster with model prose.
- Corrected A1/A2 documentation order, documented the active roster in the sealed directory, removed
  stale review-repair topology, and removed unused route-failure classification code.
- Removed the whole-day mirror-refresh gate. One repository's ordinary clone or fetch unavailability
  is now recorded and skipped while other usable repositories continue; path, origin, identity, and
  artifact-integrity defects remain hard failures.

- Fixed the Step-0 active-repository mirror selection to retain the authoritative full owner-roster
  identity. The former subset roster made valid evidence fail publisher preflight with
  `snapshot_rejected` even though the active repository belonged to the sealed roster.
- Kept the publisher provenance boundary intact: mirror work is limited to repositories with
  report-day commits, while every emitted mirror record now identifies the same full roster sealed
  into the publication bundle.
- Established `LLM_GATE_STYLE.md` as the primary policy for continued gate cleanup and added the
  cross-component diagnosis rule: recover the exact downstream rejection, remove editorial gates,
  and fix contradictory producer identity without weakening genuine integrity checks.

### Developer Tests and Notes

- The second gate audit classified remaining publication failures by concrete harm and retained only
  evidence authority, date and repository scope, source safety, path confinement, selected-byte
  availability, artifact integrity, and transactional publisher boundaries as hard failures.
- Focused image, observability, Stage 6, recovery, and fault-semantics checks passed 49 tests. The
  complete Python 3.12 permanent suite passed all 3,989 tests in 30.34 seconds. The controlled
  publication E2E passed separately; no live-model, historical-artifact, count, prompt-byte, or
  call-topology check was added to permanent pytest.
- Focused Stage 6, recovery, publication-surface, bundle, publisher, Stage 7, and publication-
  validation checks passed 96 tests. A live August 27 rerun degraded across unavailable outline,
  writer, editor, reviewer, and synthesis work, then replaced the post, copied its one selected
  image, and verified the rendered page in 11m31s.
- The complete Python 3.12 permanent suite passed all 3,989 tests in 30.11 seconds. The controlled
  publication E2E passed initial import, same-date replacement, selected-image transfer, rendered-
  page verification, and preservation of the imported state after an expected page-check failure.
- Focused publisher, publication-state, and evidence tests passed 62 cases. The controlled
  producer-to-renderer publication E2E passed initial import, same-date replacement, selected-image
  transfer, rendered-page verification, and the expected post-import page failure. The Git evidence
  E2E passed with repository-qualified image naming. The complete Python 3.12 suite passed all 3,983
  tests.

- Publication-flow ownership and editorial-filename changes passed 108 focused documentation,
  outline-review, Stage-7, and observability tests. The complete permanent suite passed all 3,947
  tests in 31.08 seconds.
- Post-audit focused evidence, projection, roster, bundle, storage, publisher, and finalization tests
  passed all 115 cases. The permanent suite passed all 3,947 remaining tests in 31.31 seconds after
  deleting the two obsolete gate tests.
- Focused roster, mirror, bundle, storage, publisher, finalization, and controlled publication E2E
  checks passed. The complete permanent suite passed all 3,949 tests in 30.98 seconds. No live-network
  or model-output test was added; synthetic roster inputs remain inline and deterministic.

- Replayed the failed August 17 bundle through the publisher's validation core and recovered the
  exact hidden cause: `Evidence mirror is outside the sealed repository roster.` A one-time
  no-refresh check then selected only `vosslab/vosslab-skills` and confirmed its mirror record kept
  the full roster ID `fdaba8dcdfa86324296d479bcb1ad4afd5a6bf2f8a830ec59c9a34c55d3aff54`.
- Focused mirror, multi-repository, integration, and bundle tests passed all 39 cases. The controlled
  producer-to-publisher E2E passed import, same-date replacement, and expected page-failure paths.
  The complete permanent suite passed all 3,944 tests in 30.86 seconds. No permanent test or fixture
  was added for this one historical specimen.
- Human-progress verification passed 857 focused observability, CLI, fault, integration, typing,
  lint, source-size, and documentation cases. The controlled publication E2E displayed the complete
  plain-language flow and passed all three scenarios; the complete permanent suite passed all 3,944
  tests in 31.11 seconds after the final deterministic-filename documentation update.
- The explicitly requested complete permanent suite passed all 3,944 tests in 31.15 seconds. No
  failing gate was found, and no new test, fixture, or production workaround was added.

## 2026-09-02

### Availability and Gate Removal

- Diagnosed the August 17 failure as a discovery and gating defect rather than a prompt defect. Step
  0 now searches the configured GitHub owner's repositories by report date, writes the run-local
  `daily_commits.md` inventory before mirror work, truncates long commit-message previews, and makes
  a genuinely quiet day a successful no-op. The one-time live August 17 check found commit
  `92672c25d91d825eef0038d84480db71eddc4b25` in `vosslab/vosslab-skills`.
- Defined robustness as producing a grounded blog entry despite stochastic model noncompliance.
  Added `LLM_GATE_STYLE.md` as the companion to the vendored pytest policy and documented the
  pre-production clean-break rule in `DESIGN_DECISIONS.md`: editorial preferences cannot acquire
  publication authority, and obsolete schemas or compatibility paths are replaced in place.
- Narrowed complete-post eligibility to mechanical trust facts. Missing evidence comments are
  reconstructed from trusted stage inputs, missing or repeated H1 headings are normalized during
  publication packaging, malformed or negative rankings and reviews fall back to a stable usable
  candidate, and style findings remain advisory.
- Removed model-driven reviewer repair end to end: no second repair calls, repair admission budget,
  repair attempt slots, repair cache identities, repair prompt renderers, or repair prompt assets
  remain in Stages 3 through 6. Reviewer failures are degradation facts and cannot veto every
  mechanically eligible artifact.
- Removed the retired prose-policy rejection codes from the active artifact contract. Optional
  outline mergers, story and complete-post editors, reviewers, and final synthesis now degrade or
  preserve their usable input when their larger comparison prompt exceeds its resource bound;
  prompt growth in an optional improvement step no longer converts an eligible incumbent into a
  failed run.
- Removed the unused Stage-6 attempt ledger, repair-feedback state, historical publication-record
  readers, retired candidate-selection subsystem, and their migration and model-obedience tests.
  Current internal run, terminal-summary, reliability, route-cache, and attempt-plan contracts use
  clean unversioned identities; current producer-to-publisher and approved prompt-asset interfaces
  retain their independently owned external contract identifiers.

### Availability Verification

- The complete permanent suite passed all 3,944 tests in 30.78 seconds after the gate and test
  deletion. Focused transport, replication, Stage-6, route-cache, Stage-7, prompt-registry, style,
  source-size, and Markdown checks also passed; Python compilation and Pyflakes were clean.
- The exact-Git evidence E2E, new-repository E2E, and complete controlled producer-to-publisher E2E
  passed. The publication E2E demonstrated the intended availability contract directly: both Stage
  7 synthesis calls failed, the eligible Stage-6 incumbent continued, Stage 8 normalized its
  machine-owned packaging, and the dated article was imported and then replaced successfully.
- No live production publication was run. The GitHub query and controlled E2Es are one-time
  implementation evidence, not new permanent pytest cases or stochastic acceptance thresholds.

### Fixes and Maintenance

- Completed six independent plan, test, style, documentation, legacy, and comment review passes
  over the integrated stochastic-resilience implementation. Consolidated primary and recovery
  Stage-6 reliability summaries under one owner so recovery promotion retains reviewer disagreement
  counts, and made the split Stage-6 modules declare their direct imports.
- Applied the clean pre-production schema policy to terminal-summary v2: production readers now
  accept only the current phase set. Removed the retired-phase pytest fixture and retained a smaller
  two-assertion idempotency check for the current receipt contract.
- Documented `fresh_batch_count: 1` as provisional until the bounded stochastic comparison writes
  its one-time result receipt. Removed milestone labels from permanent attempt-plan docstrings.
- Split primary and recovery Stage-6 orchestration into named writer, editor, feedback, observation,
  review, and finalization helpers. The route order, immutable materialization, cache witnesses, and
  reliability ledger remain unchanged; recovery repair prompts again enforce their configured bound.
- Corrected the one-time M16 runner before live execution: H2 now measures eligible generation
  survivors instead of the binary final-selection flag, every materialized attempt retains its safe
  response-free fact and identity digest, and H3 records an explicit retain/remove decision only when
  feedback was exercised. The sealed-ceiling and archived-input preflight passes offline.
- Synchronized shared style guides, tests, and repository support files from the starter template.

### Decisions and Failures

- Kept the existing active-plan copy in its current `docs/active_plans/` location because the
  repository filing policy requires an explicit one-time sweep before relocating legacy root-level
  plan files.
- Kept the plan open: the authorized live M16 comparison, evidence-selected production default,
  explicit-date publication receipt, final review disposition, and closeout records remain pending.

### Developer Tests and Notes

- Focused Stage-6, recovery, observability, admission, replication, route-cache, and attempt-plan
  verification passed 99 tests; the slowest completed in 0.23 seconds. The style, typing,
  source-limit, import, ASCII, and documentation-link checks passed.
- The controlled producer-to-publisher E2E passed after the orchestration split. The complete
  permanent suite passed all 3,817 tests in 35.72 seconds. No permanent pytest was added; controlled
  publication remains E2E evidence and the stochastic comparison remains one-time evidence.
- The M1-M15 receipt digest chain was re-read from disk and reconciled through the M16 manifest. A
  temporary offline M16 preflight script and its empty output directory were removed after use.

## 2026-08-31

### Behavior or Interface Changes

- Separated the promoted daily outline's narrative scope from the complete usable-survivor coverage
  scope. Normal Stage 6 receives full prose context only for selected narrative stories plus a compact
  `Project coverage` roster; recovery retains the full survivor catalog and its admission scope through
  Stage 7 and publication validation.
- Made screenshot citations on the promoted outline or selected narrative stories authorize the exact
  evidence ID, bundle asset path, and published path on one `PublicationSurface`. Normal, recovery,
  and Stage 7 model frames expose the same optional image records without local asset paths; uncited
  screenshots remain outside the bundle and publisher.
- Extended semantic route identity with narrative, rendered coverage, recovery, and selected-image
  context while preserving reuse across mirror-location and refresh-only changes. Portable
  publication-surface v1 and bundle v9 schemas remain unchanged.

### Fixes and Maintenance

- Rotated the 2026-08-26 through 2026-08-29 day blocks into
  `docs/CHANGELOG-2026-08b.md` after the active changelog crossed its 800-line
  threshold; the active file retains the two newest date blocks.
- Corrected the outer recovery coordinator, Stage 7, and Stage 8 to preserve full-survivor recovery
  evidence instead of reapplying the normal narrative-only scope. Publication-validation replay now
  records that explicit recovery fact.
- Advanced transfers to bundle v9; its portable `PublicationSurface` owns survivor evidence,
  images, coverage, assets, admission, and page verification. Bundle v8 is historical evidence.
- Covered Stage6Input-to-bundle and actual publisher import/page seams with offline checks,
  including an unselected aggregate screenshot that remains outside survivor assets.
- Kept semantic cache identity on selected commits, evidence, and prompts; advanced run
  state to v12; removed the pre-survivor projection gate; bounded Stage-5 comparisons and
  the complete Stage-6 context; aligned archived evidence reads at 128 MiB; and retained
  the one historical phase required for valid terminal-receipt replay.

### Decisions and Failures

- Kept editorial selection qualitative: no top-N rule, score threshold, required narrative repository
  count, mandatory image use, prose wording assertion, model-call topology assertion, or code-level
  prose-quality predicate was added.
- Live acceptance run `20260901T000547Z-81288cc26f` stopped at `mirror_refresh` because the sandbox
  could not write `/home/vosslab/repo-mirrors`. The external-write escalation was rejected pending
  explicit user approval; the publisher was not invoked or changed by that attempt.
- After approval, live run `20260901T005316Z-b8907d6ec5` completed through the existing degraded and
  recovery paths, replaced the August 25 sibling publication, rebuilt the site, and verified the
  rendered page. Its outline retained all 10 surviving repositories, Stage 6 received four cited
  screenshot paths, and the article chose one image. These are observations from this run, not new
  selection, prose, model-count, or image-use gates.

### Developer Tests and Notes

- Permanent producer verification passed all 3,750 tests; 27 focused producer bundle/admission tests
  and 44 focused sibling publisher tests also passed. An independent repository-rule and
  permanent-test review accepted the changed tests without finding a stochastic-output gate. The
  controlled producer-to-publisher E2E was initially recorded as passed, but a later exact rerun
  disproved that claim and prompted the correction below.
- A temporary in-memory replay of archived August 25 run `20260831T211539Z-c60846358a` resolved four
  cited screenshots despite the promoted outline's empty `image_paths`, exposed their publish paths
  without local asset paths, and excluded three uncited screenshots. The probe was removed afterward;
  these observed counts are one-time evidence, not permanent acceptance thresholds.
- Live run `20260901T005316Z-b8907d6ec5` sealed bundle
  `05412ec6ee562ad6fbc20b4e81ca4f170c23edae43dc87413b458c757daecc19` and verified rendered page
  `0a6bfeffa1dfbd1ff258010c5c2faf46c363c56ede967bcfe5591be52f7288b2`. Producer and sibling post
  hashes match at `69b22a7d0a647a9d264f876fb6709ab16f97a8152c596a6281eff1cbe8d07463`; all four selected asset
  hashes also match their installed copies. The article gives its principal space to curriculum
  adoption, maintained syllabus authority, and durable chemical-object identity, then covers the
  remaining projects compactly before listing the complete roster.
- Final verification on the documented tree passed all 3,760 permanent producer tests in 34.49
  seconds. A fresh post-live publication-integrity review confirmed all six sealed producer artifacts
  match the sibling archive, the four selected assets match producer, archive, and install bytes, and
  the three unselected screenshots are absent from the bundle, publisher, and rendered page.
- Corrected the controlled-publication evidence after reproducing its same-date replacement failure.
  The retained local diagnostic was `ENOSPC` while the disposable publisher copied the sibling's
  growing `docs/` screenshot corpus into a second staged tree; production replacement logic and the
  live publication were not implicated. The E2E now copies the real publisher runtime with a fixed
  minimal MkDocs reader source, preserving strict first-import, same-date replacement, page
  verification, and post-import-failure checks without multiplying unrelated historical assets. The
  exact documented E2E command now passes, as do 1,972 focused source-policy checks. No production
  code, editorial gate, or model-output assertion changed.
- `docs/BLOG_CONTRACT.md` and the five approved prompt/rubric assets remain byte-identical. No sibling
  publisher code or schema change was required.
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

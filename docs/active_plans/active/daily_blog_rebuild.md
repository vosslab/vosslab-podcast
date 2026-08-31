# Daily blog rebuild progress

## Purpose and authority

This tracker records execution of
[`LAYERED_PODCAST_IMPROVE_PLAN.md`](../../archive/LAYERED_PODCAST_IMPROVE_PLAN.md).
The plan remains authoritative for scope, wording, dependencies, and acceptance evidence. The
human-owned [docs/BLOG_CONTRACT.md](../../BLOG_CONTRACT.md) remains unchanged.

The target is a readable, evidence-grounded post for each requested `report_date` with obtainable
evidence. Reliability belongs inside every editorial stage: independent candidates, partial-failure
survival, review and promotion of eligible artifacts, and an editorial recovery ladder. Mechanical
checks retain evidence grounding and publication integrity; they do not assemble replacement prose.

## Current decision state

Status: M1 through M16 remain accepted historical rebuild evidence. A forward
hardening track, H1 through H3, is open after the real 2026-08-28 run sealed a
bundle but did not complete site import. This is a stabilization track, not a
revision of the accepted milestones.
M14's accepted durable record is
[`daily_blog_rebuild_validation.md`](../reports/daily_blog_rebuild_validation.md).

The accepted route foundation now provides strict `AgentResult` invariants, five typed route failure
classes, bounded retry, a shared process-wide `RouteBudget`, one repair admission per logical
source, coordinator-owned durable writes, and integrity-checked resumable cache records. This is
M1 evidence only. M2 separately establishes five distinct artifact types, four typed stage
outcomes, explicit eligibility predicates, packet-subset provenance, and deterministic same-rung
promotion behavior. M3 now separately establishes balanced independent reviewer replicas,
generic review and promotion in Stage 6, strict repair and unambiguous salvage, a separate eligible
incumbent, and typed degradation. Its acceptance does not establish M4 through M5 by implication.

M4 now establishes the permanent Stage 6 input boundary: a `DailyOutline`, promoted `RepoStory`
artifacts, and their `EvidencePacket` sources. It uses unchanged V4 assets and a no-egress,
two-writer balanced-referee fixture that promotes a grounded `CompletePost`. This acceptance does
not establish the prompt-authoring work in M6 by implication.

M5 now establishes the publication boundary and date-owned replacement behavior: Stage 8 repairs
only machine-owned metadata, Stage 9 imports a sealed v6 bundle and verifies the rendered page,
and the coordinator records `publication_validation`, `post_write`, `site_import`, and
`page_verification` as distinct phases. A controlled direct E2E proves success, replacement, and
preservation after a forced `page_verification` failure. Scheduled `--yesterday` automatically
replaces an occupied date; an occupied interactive `--date` asks `Overwrite YYYY-MM-DD? [N/y]:`
and requires exact `y`; `--yes` is the unattended explicit-date replacement path. This later
[HUMAN_GUIDANCE.md](../../HUMAN_GUIDANCE.md) decision supersedes the older unconditional-interactive
wording while retaining `report_date` as the sole publication identity with no versioning. The
producer's final reviewer reported 205 focused tests passing; the sibling publisher's v6/v4 review
accepted its matching contract. This acceptance does not establish new prompt wording or M6's
prompt-authoring guide.

The human explicitly directs prompt writing to use
`~/BOOKS_to_CONVERT/SORTED_SUBJECTS_MD/prompt_engineering/`. M6 must derive and cite its guide from
that corpus before new role prompts are written. The approved V4 complete-post assets remain frozen.

M6 now records the cited prompt-authoring guide at
`docs/active_plans/decisions/daily_blog_prompt_authoring_guide.md`. Its corrected local citations
cover four prompt-engineering books, distinguish immutable behavioral requirements from tunables,
and leave the approved V4 assets unchanged. An independent review accepted the guide. This
acceptance authorizes M7's prompt-contract and configuration work; it does not approve a change to
the human-owned V4 prompt wording.

M7 now establishes the Stage 3 repository-outline path: pinned, reviewable prompt contracts and
settings-owned replication/rubric configuration produce fixture-promoted `RepoOutline` artifacts
through events `3.1` through `3.4`. Its final reviewer accepted the direct executable no-egress E2E,
the pinned prompt/budget/workflow/event boundary, and 143 focused tests while confirming that the
contract and frozen V4 assets remain unchanged. This acceptance does not decide the Stage 4 rubric;
M8 must record a captured-candidate comparison before promoting that decision.

M8 now establishes the Stage 4 repository-story path. Its final reviewer accepted both direct,
mode-`0755` E2Es and 91 focused tests, with the durable ignored capture chain at
`output_blog_capture/m8_stage4_rubric_decision`. The captured comparison retained V4 unchanged:
expected-order and order-consistency tied, while normalized separation was `0.633` versus `0.600`.
The exact publication contract remains unchanged. This acceptance starts M9's robustness work; it
does not by itself prove the recovery ladder or fault digest.

M9 now establishes per-stage partial-failure survival, the typed recovery ladder, and its bounded
v3 fault digest in the production Stage 6 command path. The final architect re-gate accepted 337
focused offline tests, both direct mode-`0755` recovery E2Es, shared run-owned budget/cache hooks,
replay-divergence detection, and the typed command fault projection. The protected contract remains
byte-identical at SHA-256 `306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`.
M10 now establishes independently replicated ranking and daily-outline editorial work, strict
reviewed promotion, retained low-ranked context, typed terminal recovery, and the exact Stage 5 to
Stage 6 production handoff. The final architect accepted 41 focused integration/recovery tests,
33 focused Stage-5 tests, the no-egress daily-outline E2E, and the controlled publication E2E.
It also confirmed clean compilation, Pyflakes, and diff checks; `orchestrator.py` is 980 lines and
the protected contract remains byte-identical at SHA-256
`306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`.

M11 now establishes Stage 7 as an incumbent-preserving editorial decision: an eligible synthesis
challenger advances only after direct demonstrated improvement, while synthesis loss or no
demonstrated improvement preserves the exact grounded Stage-6 incumbent. Recovery-generation
lineage is exact rather than reconstructed, the legacy importer receives its required truthful
two-summary projection, and operational run-state paths are logical and root-contained. The final
behavior review accepted 133 lean focused tests and the controlled publication E2E; the protected
contract remains byte-identical at SHA-256
`306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`. The additional Stage-7 and
recovery E2Es are recorded one-time evidence and remain scheduled for M14 evidence capture and
removal, not permanent gates.

M12 now establishes the multi-repository editorial boundary. One frozen repository projection set
drives capacity planning and concurrent repository-isolated Stage 3/4 jobs under one run-owned
budget. Cache identity derives from portable semantic input rather than transient run or filesystem
identity; only validated eligible work is accepted into the serialized cache. The coordinator joins
eligible repository pairs canonically, records bounded aggregate reliability, preserves valid work
through partial route failure, and emits a typed evidence-grounded fault when no publishable pair
survives. The durable state owner serializes cache effects and run records. The final acceptance
reviewed cache/capacity, source ownership, adversarial concurrency, and end-to-end behavior;
174 affected focused tests and the controlled publication E2E passed. Stale provider/topology tests
were removed under `PYTEST_STYLE.md` rather than retained as compatibility requirements.

M13 now establishes bounded factual observability without a publication health gate. The direct
date-owned layout retains a date-level summary beside expirable run directories. A bounded,
redacted step-event stream and one terminal receipt distinguish completed editorial degradation,
classified pipeline faults, and incomplete operational failures. The advisory reporter exposes raw
step numerators and denominators rather than inferred targets. Retention is disabled unless
configured and, when enabled, uses command-start creation age under the date lock; it preserves
the publication and date summary while descriptor-relative no-follow traversal removes only
validated, terminal, receipted direct run children. Independent final acceptance recorded 71
focused checks; the manager's full M13 selection recorded 127 focused tests and the retained durable
controlled publication E2E passing. The security re-review accepted the parent-swap and bounded-journal
repairs, and the permanent-test-policy re-review accepted the non-topological, offline coverage.
`docs/BLOG_CONTRACT.md` remains byte-identical at SHA-256
`306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`.
M15 completed the coordinated ownership migration and removal sweep: the superseded orchestration
paths were split into owned workflow modules, temporary harnesses were removed, and the current
documentation and publication contracts were reconciled. This is completed rebuild work, not a
hidden exception to the repository limit.

## 2026-08-30 hardening track

The real 2026-08-28 route completed editorial work and sealed a bundle, but site
import rejected that bundle. The observed failure is a pipeline fault, not an
editorial degradation: the producer admitted a final post whose repository
coverage and narrative citation policy did not satisfy the sibling publisher's
publication policy. The track below stabilizes that boundary before another
live route. It preserves all historical M1--M16 acceptance records and leaves
prompt prose and the human-owned contract unchanged.

The scope rule is fixed before candidate generation: `PublicationSurface` is
the exact union of Stage-6 eligible survivor `EvidencePacket` sources, with a
matching projection and only their required assets. Citations demonstrate
grounding within that frozen surface; they cannot reduce required repository
coverage. The full roster remains provenance context rather than a source of
post-publication scope expansion.

| Track | Scope and completion evidence | Status |
| --- | --- | --- |
| H1 | Build one frozen survivor `PublicationSurface`; apply final-policy admission to Stage 6 and Stage 7 candidates, with Stage 8 as an invariant check. Verify that policy-invalid peers degrade while an eligible peer can survive, and that the sealed publication uses the same surface. | In progress; implementation awaits focused offline tests and review. |
| H2 | Add sibling validate-only preflight for the exact sealed transfer; use bounded, text-free, typed publisher failures; and treat replacement as authorization rather than a claim that an installed record exists. Verify all four prior-state transitions and that validation writes nothing. | In progress; implementation awaits focused offline tests and review. |
| H3 | Retain focused offline permanent tests and the fixed, offline retained durable controlled E2E. Then run one unattended real 2026-08-28 public rerun and verify its terminal summary, import receipt, sealed bundle, installed post, and rendered page. | Pending H1 and H2. |

`--yes` and `--yesterday` remain unattended paths; H1--H3 contain no human
approval or interactive milestone. The real rerun is one-time corroboration,
never a pytest case or permanent acceptance gate. It confirms integration and
publication behavior only; it does not convert live model output into a
repeatable prose-quality test.

## Gate rejections and blockers

| Gate | Verdict | Evidence and blocker | Next dependency |
| --- | --- | --- | --- |
| M1-M3 architect | Rejected | `AgentResult` lacks required fields; route calls have no bounded retry; the counter is not a shared semaphore and stages create budgets; result construction lacks status validation; five typed artifacts and eligibility predicates are absent; `replicate` and `review` are not separate APIs; reviewer order balance is not guaranteed; the workflow has no incumbent input; unambiguous candidate identifiers are not salvaged; and required tests are absent. | M1 repair is in progress. Bind a generic `AgentResult` and shared run semaphore, typed artifacts, separately callable `replicate`-`review`-`promote`, balanced order, threaded incumbents, then repair -> salvage -> incumbent/stable resolution. |
| M1 independent review | Rejected after 74 focused passes | The route slice still lacks the explicit complete five-class failure taxonomy and a stub-runner test for each class; the route/budget layer does not enforce at most one repair attempt per logical source; a `time.sleep` test violates `PYTEST_STYLE`; and tests are missing direct `AgentResult` invariant coverage plus identity-mismatch-before-work proof. Passing focused tests do not substitute for these contract tests. | Keep M1 in progress. Complete the taxonomy and test matrix, enforce the repair limit at the route boundary, replace timing-based synchronization with deterministic coordination, and add the missing invariant and pre-work identity tests before re-review. |
| M1 independent final gate | Accepted | The final independent gate accepted the strict `AgentResult`, five failure classes, bounded retry, shared `RouteBudget`, repair admission, cache-integrity, and coordinator-write contract. It reported 82 focused M1/editorial tests and 120 manager-relevant tests passing. | M2 may proceed: create five distinct artifacts, four typed stage outcomes, and explicit eligibility predicates with tests. |
| M2 initial independent gate | Rejected | The initial typed-artifact slice did not yet prove all five rungs, complete per-predicate eligibility outcomes, packet-subset provenance, or each of the four unspoofable same-rung outcomes. It therefore could not establish that ineligible work stays out of promotion while the stage continues. | Keep M2 in progress until the complete typed ladder and its deterministic evidence matrix exist. |
| M2 independent final gate | Accepted | The final gate accepted all five artifact rungs, explicit eligibility predicates, packet-subset provenance, and the four unspoofable same-rung outcomes. It reported 51 focused artifact tests passing; the manager's relevant focused suite reported 120 passing. | M3 may proceed with independently callable replication, review, and promotion over these typed artifacts. |
| M1-M3 fresh architect gate | Accepted | The fresh architect gate accepted M3's balanced both-order reviewer replicas, generic `review` and `promote` use by Stage 6, strict repair then unambiguous salvage, separate incumbent handling, and typed degradation. It reported 171 focused M1-M3/artifact/editorial tests passing, clean `py_compile`, `pyflakes`, and diff checks, with `docs/BLOG_CONTRACT.md` unchanged. | M4 may proceed with the captured-fixture Stage 6 input and complete-post path. |
| M4-M5 reviewer | Rejected | Stage 6 accepts `EvidencePacket` plus `EditorialProjection`, not `DailyOutline` plus `RepoStory` plus evidence; it has no Stage 6 editor path; `make_blog.py` retains `--yes`, interactive confirmation, and occupied-date early return; no distinct post-import page-verification phase preserves failure evidence; and the controlled E2E bypasses command/workflow and lacks fixture and `best_artifact_id` proof. | Keep M2-M5 unaccepted. After the M1-M3 gate accepts, build the eventual Stage 6 input contract and editor path, then repair command, publication verification, and controlled E2E behavior. |
| M4 initial test-audit/style gate | Rejected | The first M4 submission did not yet demonstrate the permanent typed Stage 6 input, the no-egress balanced referee path, or the required style and focused-test evidence. | Keep M4 in progress until the fixture path is typed, deterministic, and independently verified. |
| M4 final acceptance gate | Accepted | The final gate accepted the permanent `DailyOutline` + `RepoStory` + `EvidencePacket` Stage 6 input, unchanged V4 assets, and the no-egress two-writer balanced-referee/repair fixture. It reported 18 Stage 6 tests and 131 focused M1-M4 tests passing, with clean `py_compile`, `pyflakes`, and diff checks. `docs/BLOG_CONTRACT.md` remains byte-identical at SHA-256 `306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`. | M5 may proceed with the command and publication path. |
| M5 final acceptance gate | Accepted | The final producer reviewer accepted the Stage 8 metadata repair, sealed bundle v6, durable `post.md`, distinct `publication_validation`, `post_write`, `site_import`, and `page_verification` phases, and controlled non-interactive same-date replacement; 205 focused tests passed. The sibling publisher v6/v4 review also accepted the matching `best_artifact_id`, receipt, descriptor-pinned import, and semantic page-verification contract. The direct executable controlled E2E proved initial success, replacement, and a forced `page_verification` failure that preserved the imported site and receipt. The later Human Guidance decision supersedes the earlier unconditional-interactive wording: scheduled `--yesterday` auto-replaces, an occupied interactive `--date` requires exact `y`, and `--yes` is the unattended explicit-date path. `orchestrator.py` is 984 lines, and `docs/BLOG_CONTRACT.md` remains byte-identical at SHA-256 `306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`. | M6 may proceed with the human-directed prompt-engineering corpus. |
| M6 final acceptance gate | Accepted | The corrected prompt-authoring guide cites four books from the human-directed local corpus, separates immutable editorial guarantees from tunable prompt details, and retains the frozen V4 assets unchanged. The independent reviewer accepted the corrected citations and guide. `docs/BLOG_CONTRACT.md` remains byte-identical at SHA-256 `306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`. | M7 may begin the prompt-contract and configuration tracks. |
| M7 final acceptance gate | Accepted | The final reviewer accepted pinned Stage 3 prompt contracts, settings-owned budget and replication configuration, workflow event IDs `3.1` through `3.4`, and fixture promotion of `RepoOutline`. It reported 143 focused tests and a direct executable no-egress E2E; the contract and frozen V4 assets remain unchanged. | M8 may begin parallel story prompt-contract and stage-configuration tracks, retaining a captured candidate comparison for the V4-versus-narrower-rubric decision. |
| M8 final acceptance gate | Accepted | The final reviewer accepted Stage 4 after 91 focused tests and both direct mode-`0755` E2Es passed. The durable ignored capture chain at `output_blog_capture/m8_stage4_rubric_decision` preserved the rubric decision: V4 remains unchanged after an expected-order/order-consistency tie and normalized separation of `0.633` versus `0.600`; the exact contract remains unchanged. | M9 may begin robustness, recovery, fault-digest, and Stage 6 foundation work. |
| M9 architect re-gate | Accepted | The architect accepted production-path Stage 6 recovery and command fault projection: 337 focused offline tests passed; direct mode-`0755` recovery and production-recovery E2Es passed; the coordinator reused one canonical v3 digest, shared run-owned budget/cache hooks, and detected replay divergence. `docs/BLOG_CONTRACT.md` remained byte-identical at SHA-256 `306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`. | M10 may begin only after C0 extracts the stage-local configuration/loading boundary; independent prompt research may proceed separately. |
| M10 final architect gate | Accepted | The architect accepted Stage 5's independent rankers, reviewed ranking promotion, scope-marked daily outlines, balanced outline review, retained low-ranked context, v7 non-incumbent run state, v4 typed terminal recovery, and real orchestrator handoff to Stage 6. It reported 41 focused integration/recovery tests, 33 focused Stage-5 tests, no-egress daily-outline and controlled-publication E2Es, clean compilation/Pyflakes/diff checks, and a byte-identical protected contract at the expected SHA-256. | M11 may begin P/C in parallel, then W/J/G for synthesis, incumbent comparison, production join, and final gate. |
| M11 final behavior gate | Accepted | The review accepted direct demonstrated-improvement promotion, exact incumbent preservation on synthesis loss or no improvement, exact recovery-generation lineage, the truthful two-summary legacy projection, logical operational paths, and the boundary that leaves existing evidence-v4 cache paths versioned rather than partially redacted. It reported 133 lean focused tests and the controlled `e2e_daily_publication.py` passing, with `docs/BLOG_CONTRACT.md` byte-identical at SHA-256 `306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`. The additional Stage-7 and recovery E2Es are one-time evidence to record and remove in M14. | M12 may begin the single multi-repository budget, cache-fingerprint, isolation, and serialized durable-write boundary. |
| M12 final acceptance gate | Accepted | Independent cache/capacity, source-ownership, adversarial-concurrency, and final acceptance reviews accepted one frozen projection set, a shared run budget, repository isolation, portable semantic cache fingerprints, validated cache admission, canonical survivor joining, serialized durable effects, and typed zero-survivor faults. The affected focused suite passed 174 tests in 3.54 seconds and the controlled `e2e_daily_publication.py` passed; `docs/BLOG_CONTRACT.md` remained byte-identical at SHA-256 `306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`. Stale provider/topology tests were removed per `PYTEST_STYLE.md`, not compatibility-preserved. | M13 may establish bounded factual observability and retention. |
| M13 final acceptance gate | Accepted | Final review accepted the direct date-owned layout, bounded redacted event stream, terminal receipts, advisory raw-count reporter, closed degradation-versus-fault taxonomy, and creation-time retention. Final security review accepted descriptor-relative no-follow retention after the parent-swap repair; test-policy review accepted the offline durable-behavior coverage. Independent focused verification reported 71 checks; the manager's M13 selection reported 127 focused tests and the retained durable controlled E2E passing. `docs/BLOG_CONTRACT.md` remained byte-identical at SHA-256 `306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`. | M14 may record fixture-to-publication coverage, historical-date evidence, and one-time harness dispositions. M15 must resolve the tracked `orchestrator.py` source-size issue before its full-suite gate. |
| M14 final mechanical-record gate | Accepted | The durable report records five self-generated fixed-date no-egress cases (quiet, busy, single-repository, screenshot-bearing, and degraded-dependency), each with sealed provenance-to-page evidence and ladder depth. Matrix and RunStore source, security, and test-policy reviews accepted the bounded descriptor/observability boundary and the degradation-versus-typed-fault distinction. Retention remains `null` because no supported positive-day capacity value exists. The report records temporary harness deletion obligations; local historical material and live external `--yesterday` are excluded/non-gating. | M15 may begin its coordinated consumer migration and removal sweep. It must delete the recorded temporary harnesses before aggregate E2E, preserve prompt text and the protected contract, and resolve the source-size follow-on. M16 retains the Aug. 28 public-entrypoint demonstration. |

These rejections are corrective gates, not completed milestones. The archived pre-implementation
review, [`DAILY_BLOG_PLAN_REVIEW.md`](../../archive/DAILY_BLOG_PLAN_REVIEW.md), explains the same architectural
gaps: preserve the incumbent, use typed stage outcomes, avoid positional review fallback, retain one
durable state owner, and resolve the publisher ownership boundary.

## Milestone register

| M | Plan wording | Depends on | Status and next acceptance evidence |
| --- | --- | --- | --- |
| M1 | Route layer: `agents.py`, failure taxonomy, route budget. | None | Accepted. Independent final gate accepted strict `AgentResult`, five classes, bounded retry, shared `RouteBudget`, repair admission, cache integrity, and coordinator writes; 82 focused M1/editorial tests and 120 manager-relevant tests passed. |
| M2 | Typed artifacts and eligibility: five artifact types, eligibility predicates. | M1 | Accepted. Final independent gate accepted the five-rung artifact ladder, eligibility predicates, packet-subset provenance, and four unspoofable same-rung outcomes; 51 focused artifact tests and 120 manager-relevant focused tests passed. |
| M3 | Replication and promotion: `replication.py`, incumbent contract. | M2 | Accepted. Architect gate accepted independently callable replication, balanced both-order reviewer replicas, generic Stage 6 review/promotion, strict repair then unambiguous salvage, a separate eligible incumbent, and typed degradation; 171 focused M1-M3/artifact/editorial tests passed with clean `py_compile`, `pyflakes`, and diff checks. |
| M4 | Stage 6 on fixtures: complete post from a captured packet, reused V4 assets. | M3 | Accepted. Final gate accepted the permanent `DailyOutline` + `RepoStory` + `EvidencePacket` Stage 6 input, unchanged V4 assets, and the no-egress two-writer balanced-referee/repair fixture; 18 Stage 6 tests and 131 focused M1-M4 tests passed with clean `py_compile`, `pyflakes`, and diff checks. `docs/BLOG_CONTRACT.md` retained its expected SHA-256. |
| M5 | Publication path and command: Stages 8-9, coordinator, `make_blog.py`. | M4 | Accepted. Final producer review reported 205 focused tests passing; sibling publisher v6/v4 review accepted. Direct executable E2E proved success, replacement, and forced `page_verification` failure preservation with sealed editorial `best_artifact_id` evidence. |
| M6 | Prompt authoring guide: guide derived from prompt-engineering references. | M5 | Accepted. The corrected guide cites four local prompt-engineering books, preserves the frozen V4 assets, and was independently accepted. |
| M7 | Stage 3 repository outlines: generators, mergers, rubric, promotion. | M6 | Accepted. Final review accepted pinned prompt contracts, settings-owned configurable replication and rubric, fixture-promoted `RepoOutline`, event IDs `3.1` through `3.4`, 143 focused tests, and a direct executable no-egress E2E; the contract and frozen V4 assets remain unchanged. |
| M8 | Stage 4 repository stories: writers, editors, rubric decision, promotion. | M7 | Accepted. Final review accepted 91 focused tests, both direct mode-`0755` E2Es, and the durable ignored rubric-decision capture chain. V4 remains unchanged after the expected-order/order-consistency tie and normalized separation `0.633` versus `0.600`; the exact contract remains unchanged. |
| M9 | Per-stage robustness and ladder: partial-failure survival, ladder transitions, digest. | M8 | Accepted. Architect re-gate accepted production-path Stage 6 recovery, a closed typed ladder and v3 digest, shared run-owned budget/cache hooks, replay-divergence detection, bounded command fault projection, 337 focused tests, and both recovery E2Es. `docs/BLOG_CONTRACT.md` retained its expected SHA-256. |
| M10 | Stage 5 ranking and daily outline: rankers, outline agents, rubrics. | M9 | Accepted. Final architect gate accepted independent rankers and writers, strict reviewed promotion with bounded repair, retained low-ranked context, scope-marked Stage-6 handoff, typed v4 exhaustion recovery, non-incumbent v7 Stage-5 state, shared budget/cache production join, 41 + 33 focused tests, and both required E2Es. `docs/BLOG_CONTRACT.md` retained its expected SHA-256. |
| M11 | Stage 7 synthesis: synthesizers, incumbent comparison. | M10 | Accepted. The selected Stage-7 artifact replaces Stage 6 only on demonstrated improvement; synthesis failure or no improvement preserves the exact incumbent. The final behavior gate accepted 133 lean focused tests and the controlled publication E2E; temporary Stage-7/recovery E2Es move to M14 evidence capture and removal. |
| M12 | Multi-repository scale: parallelism, budget, resumable caching. | M11 | Accepted. Independent reviews accepted one frozen projection set, repository-isolated concurrent Stage 3/4 jobs under one run budget, portable semantic cache fingerprints, validated cache admission, canonical joining, serialized durable writes, partial-failure survival, and typed zero-survivor faults. The affected focused suite passed 174 tests in 3.54 seconds; the controlled publication E2E passed; `docs/BLOG_CONTRACT.md` retained its expected SHA-256. Stale provider/topology tests were removed per `PYTEST_STYLE.md` rather than compatibility-preserved. |
| M13 | Observability and retention: event stream, reporter, retention. | M12 | Accepted. Direct date-owned run layout, bounded redacted events, terminal summaries, advisory raw-count reporting, closed outcome taxonomy, and descriptor-relative no-follow creation-time retention are accepted. Independent verification reported 71 focused checks; the manager selection reported 127 focused tests and the retained durable controlled E2E. M15 must split or remove superseded `orchestrator.py` paths to restore the source-size limit. |
| M14 | Automated validation: fixture suite, historical dates, harnesses. | M13 | Accepted. The mechanically reviewed durable report records five self-generated no-egress cases (busy, quiet, single-repository, screenshot-bearing, and degraded-dependency) through verified pages with provenance/coverage parity and ladder depth. It distinguishes editorial degradation from typed pipeline faults, accepts descriptor-owned RunStore and bounded observability, retains `detailed_retention_days: null`, and records M15 deletion dispositions. Local historical capture and live `--yesterday` remain optional/non-gating. |
| M15 | Redesign and removal: publication contract, registry, module removal. | M14 | Accepted. Consumers were migrated before removal; retired experiment, calibration, shadow, and minting paths plus temporary harnesses were removed; retained prompt identities were verified without editing prompt prose; and workflow ownership was split across acquisition, repository editorial, and publication finalization. The single aggregate daily-publication E2E passed 7/7. The one full `pytest tests/` run reported 3,513 passed and one stale transition failure; its narrow repaired closure reported 206 passing. Current operator, architecture, and sibling-publication documentation was reconciled. |
| M16 | Documentation close-out: changelog, transcript, operations docs. | M15 | Accepted. The current documentation records the shipped nine-stage pipeline, four outcomes, ladder, advisory reporter, and no-egress acceptance path. A fixture-backed, no-egress disposable August 28 proof ran public `make_blog.py --yesterday` twice with zero returns; the second import was automatically `replaced`, and terminal summary, historical sealed bundle-v7, artifact identity, digests, and reader page were verified. Nine historical records were archived and the independent pre-final review passed 64 Markdown-link tests with a clean diff check. The live route remains optional `not_run` corroboration and this proof makes no live-model or prose-quality claim. |
| H1 | Survivor publication surface and final-policy admission. | M1--M16 historical record | In progress. Freeze the Stage-6 eligible survivor packet union before candidate generation; use it for Stage 6/7 admission and Stage 8 invariant validation. Awaiting focused offline tests and independent review. |
| H2 | Exact-transfer preflight and publisher fault boundary. | H1 surface contract | In progress. Add validate-only sibling preflight, bounded text-free typed failures, and replacement-as-authorization state handling. Awaiting focused offline tests and independent review. |
| H3 | Stabilization proof and public rerun. | H1, H2 | Pending. Retain the durable fixed offline E2E, run focused permanent tests, then perform the one-time unattended 2026-08-28 public rerun. |

## Cross-cutting acceptance rules

- A stage treats mechanical eligibility as a boundary and editorial quality as review preference.
- A later stage preserves an eligible incumbent unless a review demonstrates improvement.
- A reviewer failure resolves through bounded repair, unambiguous identifier salvage, incumbent
  preservation, or stable selection only among eligible peers.
- Ordinary route failures become typed editorial observations. Configuration, path safety, identity,
  cache corruption, and implementation defects remain precise pipeline faults.
- The coordinator serializes cache writes, promotion decisions, incumbent updates, and run events.
- Publication preserves `report_date` as the sole post identity and overwrites that date's post.
- M13 reports raw counts and denominators; it does not make ungrounded thresholds command gates.

## Required evidence before acceptance

| Requirement | Authoritative evidence |
| --- | --- |
| Editorial reliability | Offline failure-injection tests proving each implemented stage promotes an eligible same-type artifact after partial failure. |
| Grounding and integrity | Fixture tests resolving every cited evidence reference and publication identity, plus SHA-verified cache and bundle records. |
| Resumability and scale | Multi-repository fixture with a single budget, atomic cache records, serialized durable writes, and a rerun with fewer calls. |
| Publication | Disposable-root controlled E2E proving import, build, verification, overwrite, and preservation of prior completed receipts. |
| Prompt additions | M6 guide with citations to the human-directed corpus and recorded identity for every new versioned asset. |
| Historical closure | Accepted. M14's mechanically reviewed five-case report, M15's coherent removal and ownership verification, its single aggregate/full-suite evidence with narrow stale-test closure, and M16's current operational documentation plus August 28 fixture-backed public-command proof. |
| Forward hardening | H1/H2 focused offline acceptance and H3's retained durable controlled E2E, followed by the separate one-time public rerun evidence. |

## Remaining work

H1 and H2 are in progress and await their focused offline tests and reviews;
H3 follows. The 2026-08-28 public route is pending one-time corroboration after
those checks. It is separate from the accepted fixture-backed August 28 proof
and must not be converted into a permanent model or prose-quality test.

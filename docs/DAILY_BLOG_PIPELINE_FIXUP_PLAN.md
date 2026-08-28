# Plan: Complete the daily-blog Hermes route and capacity selection

Status date: August 28, 2026
Status: ready for unattended autonomous execution
Execution gates: manager-verifiable evidence only
Plan owner: daily-blog fixup manager
Bring-up report: read-only context; closure records a self-contained local evidence reference

## Context

The producer has a proven stdin route to Hermes, but fresh one-shot processes select before their
process-local capacity refresh can affect ranking. The tracked daily schedule is direct and at
04:00, while an M0 captured scheduler observation records retired-wrapper drift. This plan repairs those two
reliability boundaries and proves the whole date-owned path without relying on a person being
present at any milestone.

## Objectives

- Complete every routing, capacity, publication, deployment, and closure milestone through manager- and
  subagent-verifiable artifacts.
- Preserve Hermes credential/model ownership, frozen prompt assets, and deterministic producer behavior.
- Exercise interactive and occupied-date behavior only in disposable roots; use a deterministic
  fixture-backed unpublished date for publication proof.

## Design philosophy

This is an incremental reliability repair because the observed defect is a localized lifecycle error,
not an invalid account-ranking algorithm. In keeping with **Fix the design, not the symptom** and
**Use the scientific method**, each gate uses a deterministic fixture, a disposable harness, or a
redacted operational artifact rather than operator presence, a calendar wait, or an unrepeatable judgment.

## Scope

- Repair the Hermes shared-capacity lifecycle and prove fresh-process selection.
- Verify the producer, publisher, and tracked/staged systemd boundaries with unattended evidence.
- Record optional commit boundaries and documentation findings without making either a completion gate.

## Non-goals

- Edit frozen editorial prompt assets or activate the maker-voice experiment.
- Replace an occupied publication date outside a disposable root.
- Create Git history, submit upstream changes, or require downstream action for closure.

## Source basis

This plan is grounded in:

- [DAILY_BLOG_PIPELINE_BRINGUP_REPORT.md](DAILY_BLOG_PIPELINE_BRINGUP_REPORT.md), read-only to this
  plan owner;
- `/home/vosslab/wiki/concepts/aella-openai-codex-provider-accounts.md`;
- `/home/vosslab/wiki/concepts/aella-codex-credential-pool-selection.md`;
- the current `vosslab-podcast` working tree and its repository rules;
- the locally available Hermes source revision, recorded by M0 without a network fetch;
- checked-in unit files and the M0 sealed fixture pack.

The report proves that the project is already connected to Hermes through stdin:

```text
Python pipeline
    -> hermes chat --provider openai-codex --query-file -
    -> active Hermes model selection
    -> Hermes OpenAI Codex credential-pool selection
    -> stdout
    -> deterministic project validation
```

The route uses Hermes's existing provider authentication. `GITHUB_TOKEN` is a separate, narrowly
loaded credential used only for authenticated GitHub discovery.

The remaining routing defect is in Hermes core. A fresh `hermes chat` process ranks an empty
process-local capacity cache, then starts a daemon refresh after selection. The refresh cannot help
that selection and can disappear when the one-shot process exits. The durable repair keeps scoring,
quota access, and provider credentials inside Hermes core while the project supplies only its provider
choice and prompt.

## Decisions made

These decisions are final for this plan; no milestone waits for another design choice.

1. The project explicitly selects only `openai-codex`; Hermes selects the model and credential.
   Every author, referee, and referee-repair attempt receives one complete self-contained stdin prompt
   in a new one-shot Hermes process. Each role's editorial context consists solely of its current task
   prompt.
2. Hermes owns model configuration, account factors, eligibility, capacity probes, cooldowns,
   ranking, rotation, and provider execution. Shared capacity state is limited to sanitized
   operational quota and eligibility observations.
3. Hermes will persist one versioned, sanitized, profile-scoped capacity snapshot under the active
   `HERMES_HOME` and coordinate refresh ownership across processes.
4. A snapshot younger than ten minutes is used without a probe.
5. When a snapshot is due but no more than three hours old, selection uses that snapshot before refresh
   completion. One leased refresh owner then starts a bounded managed refresh and owns it through atomic
   persistence or explicit retention of the previous snapshot before the process exits. Concurrent
   callers use the same usable snapshot rather than joining the refresh operation.
6. Missing, corrupt, or more-than-three-hour-old state triggers one bounded synchronous owner refresh
   before selection. Callers without usable state wait only within the bound.
7. If a due refresh fails, the previous non-stale snapshot may be used with a redacted reason. If a
   cold or stale refresh fails, Hermes uses deterministic eligible-order fallback with a redacted
   reason.
8. Hermes owns every refresh task through atomic persistence or explicit retention of the prior
   snapshot before a one-shot CLI process exits.
9. Systemd is the sole schedule owner. It runs `./make_blog.py --yesterday` at 04:00
   America/Chicago.
10. `report_date` is the sole publication identity. One process owns a date at a time.
11. `-Y` is the short form of `--yesterday`; `-y` is the short form of `--yes`. Existing-date
    replacement requires the literal response `y` unless the operator supplied `-y` or `--yes`.
    Plan verification uses an automated PTY and disposable fixtures.
12. Editorial prompt assets are outside this reliability change. A one-time baseline and scoped diff
    detect accidental edits; generated prose and model responses are never required to be byte-
    equivalent.
13. Maker-voice activation remains a separate quality project and does not block reliable publication.
14. The capacity diagnostic will be an explicit, opt-in operator harness or command that emits only
    the redacted operational fields required for selection proof.
15. Agents prepare an upstream-quality, reviewed Hermes diff, an exact owned-file boundary, and a
    proposed optional commit message, then package that reviewed source into the exact CLI and gateway
    runtime. Technical verification proceeds through locally staged packages; target deployment is
    optional corroboration and history publication is not a plan dependency.

## Gate grounding and test retention

Every acceptance requirement must trace to user-visible behavior, a security or data-integrity
boundary, an external protocol, an explicit operating policy, or a repository rule. Do not invent
latency targets, item counts, output equivalence, or implementation-shape assertions merely to make a
gate measurable.

- The ten-minute reuse window and three-hour stale boundary come from the capacity policy and remain
  configuration-owned. Permanent tests use fake time and assert behavior on each side of the configured
  boundaries rather than duplicating wall-clock delays.
- The 04:00 America/Chicago schedule, literal overwrite parser behavior, and owner-only state
  permissions are explicit product or security contracts.
- Exact content identity is required only where it proves artifact integrity or that the staged
  runtime contains the reviewed source. It is not a proxy for editorial quality or rendered-output
  equivalence.
- Each milestone labels evidence as a permanent test, one-time implementation check, fixture-backed
  deployment check, or scoped review. Calling a check automated does not make it suitable for the
  permanent suite.
- A new permanent test is retained only when it passes the full checklist in `docs/PYTEST_STYLE.md`:
  meaningful behavior, stable offline inputs, deterministic time, no real subprocess or network, writes
  only under `tmp_path`, simple assertions, and no hardcoded tunables or collection counts.
- Real-process, network, PTY, filesystem-permission, staged-package, and transient-systemd checks
  produce one-time evidence. Keep a reusable `tests/e2e/` check only when it protects durable
  user-visible behavior and earns its maintenance cost; otherwise remove the scratch harness after
  evidence capture.
- If a proposed test pressures production code toward behavior the user did not request, review or
  delete the test before changing the product.

## Autonomous execution contract

After dispatch, the manager and subagents complete every milestone independently. This plan has no
interactive, external-response, downstream-action, or calendar-wait dependency.

- The manager dispatches a fresh subagent for every independent task with a self-contained prompt
  containing the objective, scope, repository paths, dependencies, acceptance gates, and required
  evidence. Each subagent handles exactly one task or milestone.
- Implementation and review use different fresh subagents; the reviewer begins from an independent
  brief and verified artifacts.
- If a subagent stalls, drifts, or performs suboptimally, the manager stops it and dispatches a fresh
  replacement immediately with the verified artifact and failure evidence.
- The manager verifies every claimed artifact from disk or the staged target.
- The manager and fresh subagents own ordinary implementation, testing, review, package staging, and
  diagnosis.
- Independent reviewer subagents replace interactive code-review gates.
- Captured fixtures, fake clocks, fake quota responses, process barriers, PTY input, and disposable
  publisher roots replace interactive behavior gates.
- A deterministic fixture-backed unpublished date is used for publication proof. Automated PTY input
  and all replacement transitions are restricted to disposable roots; no milestone replaces an occupied
  non-fixture date.
- The normal scheduled path remains fully noninteractive and resolves an occupied coherent date at the
  idempotent preflight.
- Operational completion uses contract-valid output and the existing anonymous referee result.
  Independent editorial-review subagents record qualitative findings for the separate maker-voice
  project.
- Any failed milestone emits the exact command, exit status, owning phase, artifact path, and next
  bounded repair.

### Former dependency replacements

| Former dependency | Autonomous replacement |
| --- | --- |
| Accept the route patch | Independent reviewer subagent plus focused tests and diff inspection |
| Prompt-text decision | Prompt assets are out of scope; M0 baseline and scoped diff review detect accidental edits |
| Type `[N/y]` | Automated PTY against disposable publication fixtures |
| Replace an occupied date | Never attempt it outside fixtures; prove replacement only in disposable roots |
| Start two commands concurrently | Multiprocess harness with barriers and bounded timeouts |
| Inspect current capacity interactively | Redacted JSON diagnostic compared programmatically with the selected label |
| Check target systemd state | Static tracked-unit comparison, captured inventory, staged user-unit, and transient harness |
| Decide whether a failed run is GitHub, Hermes, or publisher | Typed phase state and automated artifact inspection |
| Review final code | Independent audit subagents; manager verifies and resolves grounded findings |
| Update the bring-up report | Local closure evidence records read-only findings and artifact paths without a downstream action |
| Commit or submit changes upstream | Optional commit boundaries and messages are recorded; neither Git history nor upstream submission gates completion |

## Goals

- Bind all author and referee routes to `openai-codex` while leaving model and account selection in
  Hermes.
- Repair and prove capacity-aware selection for fresh one-shot Hermes processes.
- Preserve credential isolation and profile isolation.
- Complete one ordinary publication through the sibling publisher using `report_date` as its sole
  identity.
- Prove date locking, replacement, idempotence, failure isolation, and unattended scheduling.
- Verify the tracked 04:00 systemd contract through local staged evidence.
- Finish with current tests, direct E2Es, publisher checks, strict MkDocs build, independent audit,
  durable documentation, and a self-contained closure index.

## Scope boundaries

- Use the Hermes CLI stdin route for every editorial invocation.
- Keep provider credentials and provider authentication inside Hermes. Load `GITHUB_TOKEN` through the
  project's narrow runtime GitHub boundary only.
- Let the sealed M0 fixture pack model the active Hermes profile and credential pool for mandatory
  selection proof.
- Keep capacity scoring, quota probes, and account ordering in Hermes core.
- Leave current and experimental prompt-contract assets outside the owned reliability diff.
- Keep maker-voice activation as a separate quality project.
- Use systemd as the sole scheduler and the per-date lock as the sole same-date execution owner.
- Treat `HERMES_ROUTE_OK` as transport evidence and the complete author/referee run as workload
  evidence.
- Gate staged service behavior on the daily-publication contract; target observations are optional
  context.

## Current evidence

| Boundary | Evidence | Status |
| --- | --- | --- |
| Hermes stdin transport | Exact smoke returned `HERMES_ROUTE_OK` | Proven |
| Project provider key | CLI route uses active Hermes profile | No key required |
| Project provider contract | Working tree adds exactly one `--provider openai-codex` per role | Candidate; focused tests pass |
| Active pool strategy | M0 sealed fixture pack records `openai-codex: codex_capacity` | Fixture preflight sufficient |
| Active pool | Sealed fixture pack records transient eligibility state | Fixture preflight sufficient |
| Fresh-process ranking | Rank occurs before daemon refresh against process-local state | Defective |
| Hermes CLI runtime | `/home/vosslab/.local/bin/hermes` resolves to the source checkout venv | Proven |
| Gateway runtime | M0 records an optional target observation | Staged gateway package is mandatory proof |
| GitHub credential | Sealed fixture pack records redacted authenticated discovery | Fixture preflight sufficient; no recheck |
| Roster lock | Existing capture lock is `0664`; contract requires `0600` | One-time migration required |
| Checked-in timer | 04:00 America/Chicago, direct `make_blog.py --yesterday` | Proven in tree |
| Target timer | M0 captures the prior 02:00-wrapper observation | Staged contract proof is mandatory; target reconciliation is optional |
| Target service | M0 captures the retired anonymous-GitHub failure | Staged direct-path proof is mandatory; target reconciliation is optional |
| User lingering | Optional M0 target observation | Not a completion input |
| Full editorial workload | No current two-author-plus-referee completion through final route | Unproved |
| Candidate publication date | M0 integrity-pinned fixture provides an unpublished `report_date` for M11 | Fixture-backed proof |

The dated wiki score table is historical evidence rather than a current ranking. The M0 captured
fixture supplies the mandatory rank; optional provider observations use one same-time sanitized rank.

## Ownership boundaries

- `vosslab-podcast` owns provider selection, complete task-prompt construction, fresh-process role
  isolation, prompt stdin transport, deterministic evidence, validation, run phases, date locking,
  bundle creation, and schedule unit files.
- Hermes owns provider credentials, model configuration, sanitized operational capacity state,
  account ranking, cooldowns, rotation, and execution. It does not persist or convey editorial state
  between role invocations.
- `vosslab-daily-blog` owns independent bundle validation, MkDocs build, receipt, and atomic release.
- The fixup manager owns dispatch, local staging, verification, and plan closure.
- `DAILY_BLOG_PIPELINE_BRINGUP_REPORT.md` remains read-only; the fixup manager writes this plan and the
  self-contained closure index.

## Dependency graph

```text
M0 baseline
 |-- M1 project route ---------------------------+
 |-- M2 snapshot -> M3 refresh -> M4 integrate  |
 |                         -> M5 unit matrix      |
 |                         -> M6 process harness  |
 |                         -> M7 stage packages   |
 |                         -> M8 fixture proof ---+
 |-- M9 producer preflight ----------------------+-> M11 full run
 |-- M10 date harness ---------------------------+       |
                                                        M12 publisher proof
                                                          |
                                                        M13 systemd repair
                                                          |
                                                        M14 final audit
                                                          |
                                                        M15 documentation
                                                          |
                                                        M16 closure index
```

M1, M2, M9, and M10 may run in parallel after M0. Hermes storage, coordination, integration, tests,
process proof, package staging, and fixture proof remain serial because each establishes the next contract.
Publication and installation remain serial and date-owned.

## Milestones

### M0 - Freeze the evidence baseline

- Owner: fixup manager.
- Depends on: none.
- Touch points: plan evidence directory, current diffs, prompt assets, unit files; no source changes.
- Deliverables:
  - Scope manifest identifying the current author/referee prompt-contract paths and baseline content
    identities solely to detect out-of-scope edits.
  - Exact paths and revisions for producer, publisher, Hermes source, Hermes CLI runtime, and gateway
    release.
  - The manager resolves and records the latest locally available Hermes revision immediately before creating a named
    dedicated capacity-routing worktree. The ledger records its path, parent revision, clean baseline
    digest, and owned-path allowlist.
  - One sealed integrity-pinned M0 fixture pack containing redacted capacity-wiki extracts, provider
    diagnostic shape, authenticated GitHub/mirror discovery, scheduler inventory, and the necessary
    pool/timer/lingering observations. Later milestones consume this pack as their only mandatory input.
  - Optional target observations are segregated from the sealed fixture pack and never required by a
    milestone.
  - A machine-readable milestone ledger with status, commands, outputs, artifacts, and dependencies.
- Acceptance evidence (one-time baseline):
  - Every required path resolves.
  - The dedicated worktree is either created from the recorded revision or regenerated from that
    revision. A conflict or dirty baseline stops that worktree only, records the diff, and regenerates
    a fresh disposable worktree without modifying another checkout.
  - M2-M8 edits, tests, commands, package staging, and diagnostics execute exclusively from the named
    worktree. The primary Hermes checkout is read-only provenance after its revision is recorded.
  - Prompt paths and baseline identities are captured as one-time scope evidence without copying prompt
    prose into logs.
- Evidence: baseline manifest and redacted host-state artifact.

### M1 - Seal the project provider boundary

- Owner: producer-route subagent.
- Depends on: M0.
- Touch points: `settings.yaml`, `pipeline/daily_blog/config.py`, `pipeline/daily_blog/routes.py`,
  stable route tests.
- Deliverables:
  - Exactly one `--provider openai-codex` in both author routes, referee route, and default route.
  - Validation rejects missing, empty, duplicate, or different provider arguments.
  - Every author, referee, and referee-repair call invokes a new process with its complete role prompt
    on stdin; no runner instance carries model conversation state.
  - `--query-file -`, `--ignore-rules`, stdout capture, and no `--model` remain intact. Validation
    rejects saved-session, resume, inline-query, profile-skill, and other external instruction sources.
- Acceptance evidence (permanent tests and scoped review):
  - Focused route tests pass with `source source_me.sh && pytest <focused route test paths>`.
  - Process-spy tests prove separate invocations for both authors, the referee, and a referee-repair
    attempt. Each runner input matches its caller-supplied complete prompt; tests assert the transport
    contract rather than copying editorial prose into test expectations.
  - Scoped diff review shows no prompt-contract asset changes because editorial prompt work is outside
    this reliability scope.
  - Project diff contains no credential reader or account-selection logic.
- Review: independent reviewer subagent reports findings; manager verifies the files and test output.

### M2 - Define and implement the shared snapshot contract

- Owner: Hermes-state subagent.
- Depends on: M0.
- Touch points: Hermes `agent/codex_capacity.py` and focused tests.
- Deliverables:
  - Versioned, profile-scoped snapshot path below the active `HERMES_HOME`.
  - Cache identity includes active Hermes home/profile, provider, stable pseudonymous credential
    identity, and credential-version fingerprint.
  - Minimal fields: remaining weekly capacity, reset time, provider eligibility state, fetch time,
    schema version, and integrity metadata.
  - The Codex usage parser retains the provider's non-secret `allowed` and `limit_reached` state so a
    currently disallowed account is excluded before model execution.
  - Owner-only directory/file permissions, symlink-safe access, atomic replacement, bounded reads,
    corrupt-state rejection, and credential-rotation invalidation.
  - Reuse existing Hermes locking and safe-state primitives where they satisfy the snapshot contract;
    add or adapt a primitive only when a reviewed gap is demonstrated. Verify atomicity, ownership,
    symlink safety, and crash behavior rather than helper identity.
  - The persisted schema is limited to sanitized quota, eligibility, freshness, identity fingerprint,
    version, and integrity fields.
- Acceptance evidence (permanent tests plus one-time filesystem checks):
  - Fast offline tests cover snapshot round trip, malformed-state rejection, and profile plus
    credential-version identity using inline `tmp_path` inputs.
  - Symlink, permission, and atomic-replacement checks run once against a disposable filesystem root;
    retain them only if the owning repository already has a durable platform-safe test seam.
  - Sentinel scans return zero matches in the snapshot and test artifacts.

### M3 - Implement cross-process refresh ownership

- Owner: Hermes-coordination subagent.
- Depends on: M2.
- Touch points: Hermes capacity module and focused tests.
- Deliverables:
  - Cross-process refresh lease with atomic acquisition, bounded wait, crash expiry, and one owner per
    refresh window.
  - Selection from due-but-usable state occurs before refresh completion, followed by one leased managed
    refresh that persists atomically or retains the prior snapshot before the owner exits.
  - Bounded synchronous owner refresh before selection only for missing, corrupt, cold, or stale state.
  - Per-credential probe isolation: one account's timeout or invalid response cannot discard healthy
    peer snapshots or turn the whole refresh into an error snapshot; all account probes share one
    bounded overall refresh deadline.
  - Non-stale concurrent-reader path and deterministic cold/stale fallback.
  - Network I/O remains outside the credential-pool lock.
- Acceptance evidence (permanent tests; M6 owns process evidence):
  - Fast fake-clock tests prove refresh-state decisions and per-account failure isolation with
    in-process fake probes and deterministic time.
  - M6 supplies the one-time real-process lease, bounded-wait, crash-recovery, and persistence proof.
  - Due-state tests block refresh completion at a process barrier and prove selection occurs before the
    barrier is released; lifecycle tests then release it and prove the managed refresh has a defined
    completion owner.

### M4 - Integrate prepared capacity into all pool selection paths

- Owner: Hermes-pool subagent.
- Depends on: M3.
- Touch points: Hermes `agent/credential_pool.py`, capacity module, focused tests.
- Deliverables:
  - One prepare-and-rank boundary used before the first credential decision.
  - `select()` and `acquire_lease()` preserve their existing semantics while consuming the same
    prepared capacity view.
  - Active lease counts remain process-local scheduling state and are not written into the shared
    capacity snapshot; the shared snapshot supplies capacity rank, not a distributed lease ledger.
  - Cooldown, 401 rotation, lease caps, canonical eligible-order fallback, and provider errors remain
    intact.
  - Capacity ranking includes only eligible credentials from usable, matching state.
- Acceptance evidence (permanent tests):
  - Sibling-path tests prove both direct selection and delegated lease selection use the prepared
    state.
  - Existing pool regression suite remains green.

### M5 - Complete the focused deterministic Hermes regressions

- Owner: Hermes-test subagent.
- Depends on: M4.
- Touch points: Hermes tests only unless a failing behavior exposes a source defect.
- Deliverables:
  - Offline behavior tests for the meaningful state classes: usable fresh, usable due, unusable
    cold/stale/corrupt, ineligible or cooling credentials, credential-version change, and one failed
    account probe alongside a healthy peer.
  - Assertions on selection, refresh action, and fallback behavior rather than internal key lists,
    function names, live labels, scores, or quota values.
- Acceptance evidence (permanent tests):
  - Focused tests pass with fake time and in-process provider responses.
  - Repository-required Hermes checks for touched files pass.
  - Permanent tests use fake time and in-process provider responses.

### M6 - Run the fresh-process proof harness

- Owner: Hermes-process-test subagent.
- Depends on: M5.
- Touch points: an opt-in redacted process harness outside the fast pytest lane; retain it as a
  permanent E2E only when the Hermes repository rules justify its continuing maintenance.
- Deliverables:
  - Isolated `HERMES_HOME`, fake usage endpoint, child-process barriers, and inline temporary inputs.
  - Redacted JSON fields: strategy, pseudonymous label, snapshot generation/digest, snapshot age,
    refresh action, selection reason, fallback class, and exit status.
  - Process scenarios:
    - cold child refreshes and selects the highest eligible fixture score;
    - second child inside ten minutes performs no probe;
    - due child selects from the usable snapshot while refresh completion is held at a process barrier,
      then persists refreshed state after the barrier is released and before exit;
    - one concurrent child uses permitted non-stale state while one refresh owner persists the update;
    - one owner-exit case proves the lease recovers within its configured bound.
- Acceptance evidence (one-time process harness):
  - Harness executes each scenario as a real fresh process and compares actual selection with fixture
    rank programmatically.
  - The selection record references the exact snapshot generation/digest used for that decision.
  - Output is limited to the declared redacted diagnostic fields.

### M7 - Stage and verify the Hermes repair package

- Owner: Hermes-release subagent.
- Depends on: M6.
- Touch points: dedicated Hermes worktree, disposable release/package root, disposable gateway package
  root, and local health harness.
- Deliverables:
  - Upstream-quality independently reviewed source diff, exact owned-file list, and optional proposed
    commit message.
  - Local release provenance notes kept separate from technical deployment and Git history.
  - A locally staged disposable CLI release and gateway package built from the repaired named-worktree
    source, each with an isolated import path and local health harness.
- Acceptance evidence (mandatory local package checks):
  - The staged CLI resolves and imports only its disposable package root; the staged gateway harness
    imports only its disposable gateway root.
  - Both health harnesses load the repaired strategy and complete a redacted fixture request without a
    network call, daemon restart, or managed release mutation.
  - Record the worktree parent revision and owned-path diff digest for provenance. Hash the same repaired
    module files in the dedicated worktree, staged CLI package, and staged gateway package; source,
    import-target, and package-content hashes agree.
  - An optional managed release deployment or gateway restart is corroboration only and records the
    same hash comparison when available.

### M8 - Prove staged best-account selection

- Owner: Hermes-staged-verifier subagent.
- Depends on: M1 and M7.
- Touch points: staged Hermes CLI/gateway packages, M0 captured-provider fixture, redacted diagnostics,
  and the exact staged CLI command shape.
- Deliverables:
  - An offline staged-runtime harness loads the packaged CLI and gateway modules against the M0
    redacted captured-provider fixture, fake clock, and disposable `HERMES_HOME`.
  - Exact sanitized snapshot generation/digest consumed by each selection and a programmatic fixture
    rank comparison.
  - Two fresh one-shot `hermes chat --provider openai-codex` selections under the fixture: the second
    reuses the snapshot within the configured window without another probe.
  - Optional provider observation recorded only as corroboration when available.
- Acceptance evidence (mandatory offline staged-package checks):
  - The selected pseudonymous label equals the highest-ranked eligible fixture account in the exact
    snapshot generation/digest named in the selection record.
  - The second process inside ten minutes reuses the snapshot without another fixture probe.
  - Every selected fixture account is eligible in that exact snapshot, and diagnostics remain redacted
    with no project prompt payload.

### M9 - Clear producer preflight blockers

- Owner: producer-preflight subagent.
- Depends on: M0.
- Touch points: runtime credential boundary, exact roster lock, Python bootstrap; no model prompts.
- Deliverables:
  - Narrow `GITHUB_TOKEN` preflight that prints only availability and authenticated quota metadata.
  - Proof that anonymous GitHub fallback is impossible in the production path.
  - Exact one-file migration of
    `out/vosslab/daily_blog_repository_rosters/.capture.lock` to owner-controlled mode `0600`.
  - Physical Python 3.12 relaunch proof for `make_blog.py`.
  - A captured authenticated GitHub/mirror fixture with integrity metadata, injected only through the
    existing narrow credential boundary in a disposable root.
- Acceptance evidence (one-time operational checks):
  - Fixture-backed preflight runs without network access; token-sentinel scans return zero matches
    across environment diagnostics, logs, settings, and artifacts.
  - `stat` proves the exact lock is a regular file with the expected owner and `0600` mode.
  - Fixture-backed owner roster discovery succeeds without the stale repository-list cache. A live
    authenticated observation is optional corroboration.

### M10 - Prove date ownership and overwrite behavior in disposable roots

- Owner: producer-behavior subagent.
- Depends on: M0.
- Touch points: tests, direct E2E harness, disposable producer/publisher roots.
- Deliverables:
  - Fast parser cases prove `-Y`/`--yesterday`, `-y`/`--yes`, and `-d`/`--date` resolve without
    collision.
  - Fast decision cases prove literal `y` accepts replacement and representative other input,
    including uppercase or whitespace-padded forms, declines.
  - A one-time PTY E2E proves the prompt wiring with disposable producer and publisher roots.
  - Noninteractive occupied-coherent case that exits successfully before model work.
  - Occupied-invalid case that fails closed noninteractively.
  - Two-process same-date contention case proving one lock owner and no concurrent model work.
  - Replacement case that validates and stages the new publication before atomically changing the
    date-owned paths.
- Acceptance evidence (permanent parser tests plus one-time disposable E2E):
  - Only literal interactive `y` or an explicit `-y`/`--yes` accepts replacement.
  - Every case runs against disposable roots and leaves coherent state. Generous harness timeouts are
    hang guards, not elapsed-time acceptance assertions.

### M11 - Complete one full publication

- Owner: publication-run subagent.
- Depends on: M8, M9, and M10.
- Touch points: one date-owned disposable run, M0 captured GitHub/mirror fixture, deterministic Hermes
  role fixture, publisher CLI.
- Deliverables:
  - One serialized fixture-backed `./make_blog.py --date <resolved-unpublished-date>` execution in
    disposable producer and publisher roots. A bounded resolver scans a recorded candidate sequence,
    selects the first verified-unpublished date, and emits a deterministic exhaustion diagnostic instead
    of touching an occupied non-fixture date.
  - Fresh fixture-backed authenticated roster discovery, fixture-backed authenticated GitHub discovery,
    immutable snapshot, owner-qualified mirrors, exact report-day
    evidence, bounded projection, two author outputs, deterministic candidate validation, anonymous
    referee result, bundle, and site import.
  - Separate fresh deterministic Hermes role-fixture process evidence for each author, the referee, and any referee-repair
    attempt; shared state is limited to the exact sanitized operational-capacity snapshot used for
    selection.
  - Phase-owned failure evidence for any retry; failed attempts stop before publication.
- Acceptance evidence (mandatory fixture-backed publication):
  - Provider is `openai-codex`; M8 proves account selection against the staged runtime.
  - Both authors and referee return nonempty contract-valid output.
  - Every editorial role starts a fresh process whose context is its current self-contained prompt.
  - The selected post has a specific thematic H1; the existing deterministic candidate validator
    rejects generic dated `Work log` titles.
  - Scoped diff review shows no prompt-contract asset changes because editorial prompt work is outside
    this reliability scope.
  - Bundle creation and site change begin only after every prior phase passes.
  - If report-day evidence contains a repository created that day, record that it remains available to
    editorial projection; otherwise mark this observation not applicable.
    `tests/e2e/e2e_daily_blog_new_repository.py` owns regression evidence for this behavior.
  - `run_state.json` and `events.jsonl` retain the exact owning phase for any bounded retry.
  - An optional external publication may use a separately resolved unpublished date as corroboration
    only.

### M12 - Verify publisher installation and idempotence

- Owner: publisher-verification subagent.
- Depends on: M11.
- Touch points: fixture-backed producer artifacts, disposable sibling publisher receipt/release, served
  fixture site.
- Deliverables:
  - Cross-checked `report_date`, bundle hash, receipt, release path, MkDocs source, strict build, and
    served page.
  - Second noninteractive same-date invocation.
  - Failure-injection proof against a disposable publisher root.
  - Captured GitHub/mirror inputs and deterministic Hermes-role outputs remain integrity-pinned through
    the producer, publisher, and served fixture route.
- Acceptance evidence (mandatory disposable publication and failure-injection checks):
  - The receipt identifies the bundle that was produced, and `report_date` agrees across the bundle,
    receipt, release, and served route.
  - Second invocation exits at the idempotent preflight before GitHub, mirror, model, bundle, and
    import phases.
  - Failure injection leaves the prior served release unchanged.
  - Runtime tokens and redacted provider metadata are absent from public output.
  - A live publisher observation is optional corroboration.

### M13 - Reconcile and prove the 04:00 systemd contract

- Owner: host-systemd subagent.
- Depends on: M12.
- Touch points: checked-in unit files, M0 integrity-pinned scheduler inventory, staged user-unit root,
  fake scheduler CLI, and transient user-systemd test unit.
- Deliverables:
  - Static unit inspection proves the tracked service directly executes
    `/home/vosslab/nsh/vosslab-podcast/make_blog.py --yesterday` and the tracked timer uses
    `OnCalendar=*-*-* 04:00:00 America/Chicago`.
  - M0's integrity-pinned scheduler inventory drives a fake scheduler CLI/removal-semantics harness,
    proving only the exact retired daily-blog entry would be removed and all other entries preserved.
  - A staged disposable user-unit root proves install, enable, active-state, and failed-state-clear
    behavior without mutating the target user manager.
  - A manager-independent local unit-command emulator parses the byte-identical tracked/staged unit,
    injects a fake clock and disposable configuration, invokes `ExecStart`, and captures exit and
    journal semantics without a target user manager.
- Acceptance evidence (mandatory local scheduler checks):
  - `systemd-analyze calendar` resolves the configured schedule to 04:00 America/Chicago.
  - Static comparison proves the staged user unit and tracked unit are byte-identical except for the
    allowed disposable configuration/test-clock environment entries.
  - The local unit-command emulator captures `ExecStart` exit status, journal, date lock, and
    no-replacement result. Its disposable roots are removed on completion. Static comparison verifies
    that the tracked/staged unit retains the
    same byte-identical direct command and scheduling contract; no calendar wait or non-fixture date
    mutation is needed.
  - The staged user-unit harness proves healthy staged-unit state; the captured scheduler inventory
    confirms systemd as the sole daily-blog schedule owner.
  - Optional `systemd-run --user` and target-manager inventory, install, enablement, and health
    observations are corroboration only.

### M14 - Run final suites and independent audits

- Owner: audit manager with independent test, security, architecture, and requirements subagents.
- Depends on: M13.
- Touch points: final producer tree, named Hermes worktree and staged packages, sibling publisher
  fixtures, staged user-unit root, and optional target observations.
- Deliverables:
  - Current focused tests, full producer suite, direct E2Es, sibling publisher suite, strict MkDocs
    build, and repository-required structural checks from the required interpreters.
  - Independent reviews for requirements conformance, credential boundaries, concurrency/state,
    test durability, prompt-scope preservation, staged-runtime parity, and staged-systemd parity.
  - Grounded findings repaired and rerun before sign-off.
- Acceptance evidence (existing suites and one-time independent reviews):
  - All required commands exit zero.
  - Every grounded finding that violates a stated acceptance contract or repository rule is resolved
    and its affected check rerun; discretionary improvements are recorded separately and do not block
    completion.
  - Every subagent claim is verified against recorded files, commands, artifacts, or staged state by the
    manager. Target observations are supplementary.

### M15 - Reconcile durable documentation

- Owner: fixup manager with documentation subagent.
- Depends on: M14.
- Touch points: this plan and its relevant `docs/CHANGELOG.md` entry. Verify the transcript, operations
  docs, Aella capacity wiki, evidence index, and bring-up report read-only; record findings in a local
  versioned evidence bundle without requiring a downstream edit or later external read.
- Deliverables:
  - Versioned local evidence bundle contains the milestone ledger, commands, exit codes, artifact paths,
    staged revisions, checksum manifest, and index.
  - Read-only findings state whether operations docs match the direct systemd and Hermes boundaries.
  - Read-only findings identify any stale Aella capacity terminology while preserving dated historical
    snapshots in the read-only documentation context.
  - Current prompt-contract status and separate maker-voice experiment status are recorded in the local
    versioned evidence bundle.
- Acceptance evidence (existing documentation checks and scoped review):
  - Documentation links and formatting tests pass.
  - This plan and its relevant changelog entry satisfy repository rules; other documents remain
    unmodified and their findings are self-contained in the closure evidence.
  - The owned-change manifest contains no `DAILY_BLOG_PIPELINE_BRINGUP_REPORT.md` changes; any current
    diff there is recorded as read-only external context rather than absorbed into this plan's work.

### M16 - Publish autonomous closure evidence

- Owner: fixup manager with integration subagent.
- Depends on: M15.
- Touch points: owned plan change sets in producer, Hermes, and publisher; plan-owned closure evidence
  below `out/vosslab/daily_blog_bringup/`; not the bring-up report.
- Deliverables:
  - Independently reviewed owned-path manifest and pre-change content identities for each repository,
    with optional proposed commit boundaries and messages.
  - Baseline and final status manifests proving every unrelated staged, unstaged, and untracked user
    change remains untouched.
  - Final content-identity manifest linking the tested producer diff, Hermes source/runtime package,
    publisher diff, staged user-unit artifacts, and prompt-scope baseline.
  - Self-contained versioned closure bundle with checksum manifest and index containing the managed
    due-refresh correction and all M8-M15 evidence.
- Acceptance evidence (one-time closure checks):
  - File comparison confirms content outside the owned change sets is preserved. Concurrent unrelated
    edits are classified and rebaselined rather than forced to match fragile Git hunk boundaries.
  - Focused smoke, documentation links, and diff checks pass from the recorded tested working trees and
    staged content identities.
  - The closure bundle checksum manifest verifies, and its index cross-references the final
    content-identity manifest.
  - Closure is complete without downstream action, Git action, or upstream submission.

## Parallel dispatch waves

| Wave | Milestones | Dispatch rule |
| --- | --- | --- |
| 0 | M0 | Manager captures one immutable baseline |
| 1 | M1, M2, M9, M10 | Independent files and artifacts; run in parallel |
| 2 | M3 | Start after M2 storage contract passes |
| 3 | M4 | Integrate only after refresh ownership is proven |
| 4 | M5 | Dedicated deterministic test pass |
| 5 | M6 | Real-process harness after unit behavior is stable |
| 6 | M7 | Stage and verify packages from the independently reviewed Hermes revision |
| 7 | M8 | Fixture selection proof through staged runtime packages |
| 8 | M11 | Full publication after M8, M9, and M10 |
| 9 | M12 | Publisher and idempotence proof |
| 10 | M13 | Prove the tracked schedule with staged and transient systemd fixtures |
| 11 | M14 | Full suites and parallel independent audits |
| 12 | M15 | Durable documentation reconciliation |
| 13 | M16 | Autonomous closure evidence |

The manager keeps only one milestone `in_progress` per serialized chain. Every table entry launches a
fresh task-scoped subagent; parallel entries launch separate fresh subagents. A stopped or failed task
is redispatched to another fresh subagent carrying only its self-contained brief plus verified
artifact and failure evidence.

## Stable test policy

Permanent tests must be offline, deterministic, behavior-focused, and compliant with
`docs/PYTEST_STYLE.md`. Every proposed test first passes that document's permanent-test checklist.
Use inline inputs and `tmp_path`; add a shared fixture only when it is redacted, integrity-pinned,
deterministic, independently reviewed, and clearer than inline data.
The repository's existing test and style rules are the authority; this plan does not add a competing
runtime budget, test count, fixture convention, or coverage target.

Keep as permanent tests:

- route parser and provider-boundary tests;
- route-runner isolation behavior with the subprocess boundary replaced by an in-process fake;
- snapshot round-trip, malformed-state, profile-isolation, and credential-version behavior using
  inline temporary inputs;
- pure refresh-state decisions with fake time and in-process probe results;
- overwrite-decision parsing and deterministic publisher contracts.

Classify as one-time implementation or operational evidence:

- real subprocess, multiprocess, crash-recovery, and PTY integration checks against disposable roots;
- filesystem permission, symlink, and atomic-replacement checks when platform behavior is the subject;
- optional current account rank and selected label;
- optional authenticated GitHub quota;
- optional current full-prompt output;
- optional target timer next-fire time;
- optional target systemd journal and served-page capture.

Place a reusable whole-system check under `tests/e2e/` only when it protects durable user-visible
behavior, remains self-contained, and earns its maintenance cost. Otherwise capture its result in the
milestone evidence and remove the scratch harness. Build fast pytest with in-process fakes,
deterministic time, inline inputs, and `tmp_path`.

Delete or omit tests that freeze prompt prose, current account labels, transient scores, quota values,
model names, repository counts, wall-clock sleeps, or current systemd timestamps.

Milestone acceptance evidence is classified as follows:

- M1-M5 parser, state, ranking, and decision behavior: permanent fast tests when they satisfy the
  checklist.
- M0 and M7-M16 artifact, process, publication, staged-package, fixture-backed provider, and host checks:
  one-time implementation evidence unless an existing repository-required suite already owns the
  behavior.
- M6 and the PTY/concurrency portions of M10: scratch process harnesses by default; retain under
  `tests/e2e/` only after a concrete durable regression justifies ongoing maintenance.
- M14 runs existing repository-required suites and reviews the proposed new tests; it does not create
  tests solely to increase counts or convert one-time evidence into pytest.

## Required verification commands

Representative command families are listed here; milestone artifacts record the exact final commands.

```bash
# Producer
source source_me.sh && python3 -m pytest -q <focused tests>
source source_me.sh && pytest tests/

# Hermes
cd <M0-named-Hermes-capacity-worktree>
<repo-required focused tests and process harness>
<staged CLI and gateway package fixture harness with redacted captured provider>

# Publication
<fixture-backed make_blog invocation in disposable producer and publisher roots>
<bounded unpublished-date resolver against the disposable root>
source source_me.sh && python3 -m pytest -q tests/test_make_blog.py
source source_me.sh && python3 tests/e2e/e2e_make_blog.py
python3 -m json.tool <evidence-root>/m10_date_ownership_evidence.json

# Systemd contract
systemd-analyze calendar '*-*-* 04:00:00 America/Chicago'
<integrity-pinned scheduler-inventory and fake-removal-semantics harness>
<staged user-unit install-enable-health harness>
<manager-independent byte-identical-ExecStart local unit-command emulator>
# Optional corroboration: systemd-run --user --wait --collect
```

Commands that inspect environment or credential state emit only redacted booleans, pseudonymous
labels, and quota metadata.

## Risk register

| Risk | Impact | Automated mitigation |
| --- | --- | --- |
| Explicit provider is mistaken for best-account proof | Every fresh process uses canonical order | M2-M8 shared-state and fixture-selection gates |
| Managed due refresh loses its lifecycle owner | One-shot processes lose refreshed observations | M3 lifecycle ownership and M6 process-exit evidence |
| Capacity logic enters the project | Credential boundary drifts | M1 diff gate and M14 architecture audit |
| Snapshot leaks identity or secrets | Credential exposure | Minimal schema, fingerprinting, `0600`, sentinel scans, redacted diagnostics |
| Cross-process owner dies | Refresh stalls | Expiring lease, bounded wait, crash-recovery process test |
| Cold-state synchronous refresh increases latency | Scheduled run waits for quota observations | One bounded refresh only when state is unusable, then deterministic fallback |
| Source fix is absent from a package | Tests pass but staged artifacts stay defective | M7 exact worktree/import/package parity proof |
| History publication is unavailable | Verified runtime state lacks a repository-history record | M7/M16 retain optional commit boundaries, messages, and content identities; closure remains complete |
| Broad dotenv enters systemd | Unrelated credentials leak | Exact-key token loader and service-environment audit |
| Occupied non-fixture date is replaced unintentionally | Unwanted content replacement | Automation never targets an occupied non-fixture date; replacement transitions run only in disposable roots |
| Full prompt fails after smoke passes | Wrong subsystem blamed | Typed phase artifacts and no-fallback publication |
| Scheduler contract retains a 02:00 wrapper | Old scheduler semantics persist | M13 sealed inventory, staged-unit, and local unit-command emulator proof |
| Target user manager is unavailable | Target observation cannot run | Local emulator remains the mandatory proof; target observation is optional |
| Prompt drift hides in broad tree | Editorial behavior changes | M0 scope baseline and scoped diff review at M1, M11, and M14 |
| Oversized milestone hides failures | Recovery becomes ambiguous | Narrow dependency-scoped milestones and explicit dispatch waves |

## Rollout checklist

- [ ] M0 baseline and prompt-scope manifest captured.
- [ ] M1 project provider boundary passes focused tests and independent review.
- [ ] M2 shared snapshot contract passes privacy and integrity tests.
- [ ] M3 refresh ownership passes crash, concurrency, and bounded-time tests.
- [ ] M4 all pool selection paths consume prepared capacity state.
- [ ] M5 focused deterministic Hermes behavior regressions pass.
- [ ] M6 one-time fresh-process harness proves cold persistence, warm reuse, managed due refresh, and
  refresh-owner recovery.
- [ ] M7 independently reviewed Hermes diff is staged, loaded, content-identified, and health-checked.
- [ ] M8 staged-package fixture fresh-process selections match the exact consumed eligible rank and
  prove warm reuse.
- [ ] M9 GitHub token, Python runtime, owner roster, and exact lock migration pass.
- [ ] M10 disposable PTY replacement and two-process date ownership evidence passes.
- [ ] M11 full publication reaches site import with the current prompt-contract assets preserved.
- [ ] M12 publisher hashes, receipt, strict build, served page, and idempotence pass.
- [ ] M13 tracked direct 04:00 systemd contract, staged user unit, and fake scheduler removal semantics
  pass.
- [ ] M14 all final suites and independent audits pass with findings resolved.
- [ ] M15 this plan and its relevant changelog entry pass; read-only documentation findings are recorded
  in self-contained closure evidence.
- [ ] M16 owned change sets, optional commit-boundary record, content-identity manifest, and
  self-contained closure index close.

## Evidence format

Every milestone report uses this schema:

```text
Milestone:
Owner subagent:
Inputs/revisions:
Files changed:
Behavior changed:
Prompt-contract files changed: no (verified by scoped diff)
Credential ownership changed: no
Commands run:
Exit statuses:
Observed result:
Artifacts:
Independent review:
Autonomous next action:
```

A milestone is complete only when the manager reads the artifact or staged state and verifies the
claim. A subagent's summary alone is not evidence.

## Definition of done

The technical plan is complete when all of the following are machine- or manager-verifiable:

- The project sends full prompts over stdin to `hermes chat --provider openai-codex`; Hermes retains
  model-provider credential ownership.
- Fresh Hermes CLI processes share sanitized capacity state and select the highest-ranked eligible
  account under the M0 captured Aella-policy fixture, subject to bounded documented fallback.
- Due-but-usable selection occurs from the existing snapshot before refresh completion, and the managed
  refresh either persists its result or explicitly retains the previous snapshot before owner-process
  exit.
- Focused deterministic tests prove cold, due, stale, corrupt, eligibility, cooldown, rotation, and
  per-account probe behavior; one-time process evidence proves cross-process persistence and recovery.
- The repaired named-worktree source is the source actually loaded by staged CLI and gateway packages.
- Fixture-backed authenticated GitHub discovery, fresh fixture-backed authenticated roster discovery,
  exact roster locking, Python 3.12 bootstrap, and fresh repository coverage pass.
- One fixture-backed unpublished report date completes two authors, deterministic validation, anonymous
  referee,
  any required referee repair, bundle creation,
  publisher validation, strict build, atomic release, and served-page verification.
- A repeated noninteractive same-date run exits at the idempotent preflight before model or
  publication work.
- Disposable automation proves exact-`y` replacement and same-date contention; no plan action replaces
  an occupied non-fixture date.
- The tracked systemd timer directly runs `./make_blog.py --yesterday` at 04:00 America/Chicago, and
  the staged/transient user-unit harness proves the matching direct-command behavior.
- Current producer, Hermes, publisher, documentation, and audit gates pass from the recorded tested
  working trees and staged content identities.
- Prompt-contract files remain outside the owned reliability diff, and the maker-voice experiment
  remains separate.
- Owned change sets, optional commit boundaries, and baseline/final status manifests preserve
  unrelated user work without freezing fragile Git hunk boundaries.
- Closure evidence is written and self-contained; the separately owned bring-up report remains
  unmodified.

## Non-blocking follow-ups

These are optional work outside technical closure:

- Git commits, upstream submission, maintainer review, and merge.
- Separate maker-voice live calibration, capture, attestation, winner selection, and activation.
- Broader cleanup of unrelated failed user services.

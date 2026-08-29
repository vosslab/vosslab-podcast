# Plan: Finish the daily-blog maker-voice integration

Status date: August 28, 2026
Status: ready for autonomous execution
Plan owner: daily-blog fixup manager
Primary repository: `/home/vosslab/nsh/vosslab-podcast`
Guiding plan: [better_prompt_plan.md](active_plans/better_prompt_plan.md)

## Context

The daily-blog producer already calls Hermes through the supported command boundary:

```text
hermes chat --provider openai-codex --query-file -
```

That command is the complete project-facing model boundary. Hermes chooses the model credential and
account internally. The podcast project supplies a self-contained prompt, consumes stdout, validates
the result, and records a redacted failure when the command does not complete.

The remaining work is an integration and editorial-quality fix inside the daily-blog producer, plus
the narrow publisher and schedule contracts required to prove delivery. It is not a Hermes account
selection project.

The intended result is a blog that sounds like a human maker who enjoys building software. August 22
and 23 are positive evidence that the system was once closer to that voice. The approved maker prompt
work and experiment machinery already live in
[better_prompt_plan.md](active_plans/better_prompt_plan.md); this plan consumes those results instead
of designing another prompt experiment.

## Ultimate goal

The production path writes a specific, technically grounded first-person story from the point of view
of the person who made the software. It gives the interesting part of the day room to breathe, treats
routine work briefly, and shows curiosity, satisfaction, uncertainty, surprise, learning, and what
comes next.

The central editorial test is:

> After reading this post, does it feel like Neil sat down after coding and wrote about what he made,
> what interested or surprised him, why he enjoyed working on it, what he learned, and what he wants
> to try next?

August 22 and 23 are qualitative references for voice, emphasis, thematic titles, and maker
perspective. They are examples, not byte-equivalence templates.

## Objectives

- Complete the existing maker evidence sequence, then make its attested winner the single production
  owner of editorial behavior.
- Preserve fresh, isolated, one-shot model calls with complete self-contained prompts.
- Keep model and account selection behind the existing Hermes command boundary.
- Prove the complete producer-to-publisher path for one date with coherent, replaceable artifacts.
- Prove the tracked 04:00 America/Chicago systemd command through repository-owned configuration and
  one-time operational evidence.
- Retain only offline, deterministic, behavior-focused permanent tests justified by repository rules.
- Close the work with current documentation, verified artifacts, and independent review.

## Design philosophy

This codebase is pre-production and has no compatibility obligation to deployed users. Prefer one
clear production contract, one owner for each state transition, and direct schemas over adapters for
retired behavior. Remove obsolete compatibility paths when the replacement is proven.

Use positive editorial instructions and concrete examples. Describe the desired story directly. Use
prohibitions only for real safety, privacy, integrity, and publication boundaries.

Focus review effort on editorial quality, correct ownership, deterministic validation, failure
isolation, publication integrity, and delivery. Treat infrastructure already owned by an external
abstraction as an accepted dependency.

## Scope

### Podcast-owned work

The implementation may change these producer-owned areas when needed:

- `pipeline/daily_blog/`
- `automation/publish_daily_blog.py`
- repository-root `make_blog.py`
- daily-blog prompt-contract resources already owned by the producer
- focused producer tests and justified `tests/e2e/` checks
- tracked daily-publication units under `deploy/`
- daily-blog operations, design, plan, and changelog documentation

### Narrow sibling-publisher integration

`/home/vosslab/nsh/vosslab-daily-blog` remains the publisher owner. Work there is limited to the
public bundle/import/release contract needed to accept the producer's active maker contract and to
preserve atomic publication. Publisher changes use that repository's rules, tests, and independent
review. Broader publisher redesign belongs in its own plan.

### Existing external model boundary

The producer invokes `hermes chat --provider openai-codex --query-file -`. Hermes owns provider
authentication, model resolution, credential eligibility, account choice, quota handling, retry, and
fallback behavior. The producer records only route-level success or a redacted route-level failure.

Existing Hermes checkouts, worktrees, dashboards, usage services, account stores, and gateway
packages are external to this plan. Any scratch changes in those locations are unrelated evidence and
are not part of this plan's implementation, verification, deployment, or closure.

## Non-goals

- Building, changing, or validating Hermes model-account selection infrastructure.
- Adding caller-facing account labels, capacity fields, usage probes, routing scores, or credential
  controls to the podcast project.
- Repeating the maker prompt research, historical calibration, or experiment design already owned by
  `better_prompt_plan.md`.
- Preserving retired pre-production schemas or prompt contracts through compatibility aliases.
- Expanding the sibling publisher beyond the bundle/import/release boundary used by this pipeline.
- Turning live model, process, filesystem, or systemd observations into permanent pytest tests.

## Source of truth and precedence

Implementation follows these sources in order:

1. [HUMAN_GUIDANCE.md](HUMAN_GUIDANCE.md) for the desired maker voice and ownership boundaries.
2. [better_prompt_plan.md](active_plans/better_prompt_plan.md) for approved maker resources,
   experiments, attestation, and activation evidence.
3. [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) for durable architectural decisions.
4. [REPO_STYLE.md](REPO_STYLE.md), [PYTEST_STYLE.md](PYTEST_STYLE.md),
   [TESTS_README.md](../tests/TESTS_README.md), and [DEVEL_README.md](../devel/DEVEL_README.md) for
   repository and verification rules.
5. This plan for the remaining dependency order and closure gates.

When an older ledger or report describes Hermes account-routing work as a prerequisite, this plan
supersedes that dependency. Historical evidence remains historical; it does not define current scope.

## Fixed architecture

1. Systemd owns the daily schedule and directly invokes `./make_blog.py --yesterday` at 04:00
   America/Chicago.
2. `report_date` is the publication identity, and one process owns a date at a time.
3. The producer owns evidence collection, editorial projection, prompt construction, role isolation,
   deterministic validation, selection, and bundle creation.
4. Every author, referee, and referee-repair call starts a fresh one-shot Hermes process with one
   complete task prompt on stdin.
5. The project chooses the `openai-codex` provider route. Hermes performs the remaining model and
   account decisions internally.
6. The existing maker candidate becomes the sole production editorial contract only after its fresh
   capture, live calibration, route-free attestation, and separately reviewed producer/publisher
   cutover pass. Retired pre-production contracts are then removed from production dispatch and
   validation.
7. The publisher independently validates the bundle, builds the site, and changes the served release
   atomically.
8. Model prose is replaceable. Evidence, prompt identity, validation policy, bundle digest, receipt,
   and publication state are deterministic and auditable. `report_date` remains the sole publication
   identity; the bundle digest proves integrity only.
9. An occupied coherent date exits at idempotent preflight in unattended mode. Explicit replacement
   stages and validates the complete new publication before changing date-owned paths.
10. Operational failures identify the owning phase and preserve the last coherent publication.

## Grounded acceptance policy

Acceptance gates protect user-visible behavior, data integrity, privacy, repository rules, or an
explicit operating contract.

- Editorial quality is judged from complete posts using the central test and the approved maker
  rubric. Exact wording, sentence counts, paragraph counts, and resemblance scores are not gates.
- August 22 and 23 demonstrate desired qualities; generated posts may tell different stories in a
  different shape.
- Exact content identity is appropriate for an approved prompt asset, schema, bundle, receipt, or
  staged release. It is not a proxy for prose quality.
- Timeouts in one-time process harnesses are generous hang guards, not performance requirements.
- Current account labels, quota values, model names selected inside Hermes, repository counts, and
  live scheduler timestamps are not acceptance inputs.
- A test that forces unrequested production behavior is reviewed as a test defect before production
  code changes.
- Independent review findings block closure only when they identify a violated requirement,
  repository rule, integrity boundary, or reproducible defect.

## Verification classification

### Permanent tests

Retain a test only when it satisfies `docs/PYTEST_STYLE.md`: it is meaningful, offline,
deterministic, behavior-focused, independent of real time and network state, writes only to temporary
paths, and uses simple durable assertions.

Appropriate permanent coverage includes:

- active maker-contract selection and fail-closed contract validation;
- complete self-contained role-prompt construction using in-process fakes;
- deterministic candidate and bundle validation;
- date ownership, idempotence, and replacement decisions with fake boundaries;
- publisher adapter arguments, including explicit replacement intent;
- schema and receipt consistency using temporary roots.

### One-time implementation evidence

Use disposable roots and captured artifacts for:

- real `hermes chat` smoke and full-role calls;
- qualitative maker-voice review of generated posts;
- fresh-process isolation and process-failure checks;
- PTY, multiprocess, crash-recovery, filesystem-atomicity, and permission checks;
- strict publisher build and served-page inspection;
- systemd calendar, unit installation, journal, and live schedule observations.

Keep a reusable E2E only when it protects durable user-visible behavior and remains reliable enough
to justify maintenance. Remove temporary harnesses after their evidence is recorded.

## Autonomous execution contract

The manager completes the plan through dependency-scoped implementation and independent review tasks.
Each task receives a fresh self-contained brief with its owned files, dependencies, acceptance gates,
and required artifacts. Implementation and review use separate subagents.

Captured evidence fixtures, deterministic role fakes, disposable roots, synthetic state transitions,
and debug harnesses provide the complete unattended path. Real route and host checks run as one-time
integration evidence through the project's existing configured interfaces. A failed external check
records its phase, redacted result, preserved state, and the next bounded retry.

The user has authorized the manager and fresh subagents to complete every technical F0-F7 action,
including the already-defined configured-route payloads, deterministic attestation, publication,
scheduler verification, diagnosis, repair, and review. No further confirmation is required inside
the dependency chain. Git-history changes and replacement of a real occupied publication date remain
outside that authorization.

The manager verifies every claimed artifact from disk. A subagent summary is not completion evidence.

## Dependency graph

```text
F0 scope baseline
 |
 +--> F1 prepare the maker candidate set
 |      |
 |      +--> F2 simplify producer orchestration
 |              |
 +--------------+--> F3 deterministic producer acceptance
                         |
                         +--> F4 real maker-output evidence
                         |       |
                         +-------+--> F5 publisher integration
                                         |
                                         +--> F6 schedule and operations proof
                                                 |
                                                 +--> F7 final audit and closure
```

The manager may inspect independent F1 and F2 touch points in parallel. Candidate preparation and
orchestration land before F3 deterministic acceptance; F4 empirical evidence and attestation pass
before F5 activation. Publication, schedule proof, and closure remain serial because each consumes the
prior verified artifact.

## Milestones

### F0 - Rebaseline the fixup around the owned integration

**Owner:** fixup manager

**Deliverables:**

- Record the producer and publisher revisions, current working-tree state, active and candidate
  prompt-contract identities, and tracked schedule-unit identity.
- Record the external-data-sharing authorization, durable configuration, and per-invocation approval
  that apply to the already-defined live calibration and fresh-capture payloads. F4 consumes those
  exact approvals and payloads; a missing approval is reported as a security precondition rather than
  replaced by a code or fixture workaround.
- Mark prior Hermes-infrastructure milestones as superseded and outside this plan.
- Record unrelated working-tree changes without modifying or absorbing them.
- Create a compact evidence index for F0-F7 with commands, exit statuses, artifact paths, and reviews.

**Acceptance:**

- The owned-path manifest contains podcast paths and only the narrow publisher contract paths needed
  later.
- No Hermes checkout, worktree, account state, dashboard, gateway package, or service is an owned
  input or deliverable.
- Prompt resources match the approved maker evidence recorded by `better_prompt_plan.md` before
  activation begins.

**Evidence class:** one-time baseline.

### F1 - Prepare the maker candidate set for the empirical decision

**Owner:** producer-contract implementation subagent

**Depends on:** F0

**Deliverables:**

- Resolve the exact user-approved v4 maker brief, examples, rubric, validation policy, and immutable
  candidate identity from the existing prompt-plan artifacts.
- Establish one explicit candidate-contract registry used consistently by prompt construction,
  candidate validation, experiment artifacts, and the eventual producer/publisher cutover.
- Keep the approved instruction-only, one-example, and three-example arms as immutable candidate
  identities inside that registry; F4, not registry order, selects the eventual production arm.
- Consolidate candidate-contract ownership while leaving the currently active contract unchanged
  until F4 produces a passing attestation.
- Preserve the approved maker prompt wording and examples exactly unless a defect is demonstrated by
  generated-output evidence and handled through the prompt plan's review process.

**Acceptance:**

- One candidate registry owns the exact approved author, referee, validation, example-selection, and
  experiment expectations for every maker arm.
- Experimental or malformed contracts fail before model or publication side effects.
- A focused diff confirms that F1 makes no exact prompt-text change.
- The active producer and publisher contract remain unchanged in this milestone.

**Evidence class:** permanent deterministic contract tests plus scoped review.

### F2 - Simplify the podcast-owned orchestration boundary

**Owner:** producer-orchestration implementation subagent

**Depends on:** F0

**Deliverables:**

- Keep each editorial role in a fresh one-shot process with a complete self-contained stdin prompt.
- Use the existing `openai-codex` Hermes command route as the only model invocation surface.
- Pass replacement intent explicitly from root command through orchestration to the publisher call.
- Give prompt resolution, repository discovery, validation, bundle creation, and publication one clear
  owner and a truthful execution order.
- Emit phase-owned, redacted failures and preserve the last coherent date-owned state.

**Acceptance:**

- Producer code contains no account-selection inputs, outputs, probes, ranking, cache, or lease state.
- In-process route fakes prove command construction, stdin transport, stdout handling, one invocation
  request per role, and redacted failure mapping. One-time process evidence proves fresh OS-process
  isolation.
- Direct and CLI callers produce the same replacement behavior.
- Comments and documentation match the actual execution order.

**Evidence class:** permanent deterministic tests and independent architecture review.

### F3 - Prove deterministic producer behavior

**Owner:** producer-verification subagent

**Depends on:** F1 and F2

**Deliverables:**

- Focused tests for maker-contract selection, role-prompt completeness, candidate validation, date
  ownership, replacement, idempotence, and bundle-digest integrity.
- A test-retention audit against `PYTEST_STYLE.md`, `TESTS_README.md`, and existing coverage.
- Removal or reclassification of fragile tests that use arbitrary timing, real network access, real
  subprocesses, helper identity, exact incidental counts, or final-state checks that do not prove the
  claimed transition.

**Acceptance:**

- Focused tests pass under Python 3.12 with network-independent inputs and deterministic time.
- New permanent tests protect requested behavior that was not already covered.
- Process, crash, kernel-atomicity, and host checks are classified as one-time evidence unless a
  durable E2E clearly earns retention.

**Evidence class:** permanent suite plus one-time test audit.

### F4 - Complete and review the existing maker experiment

**Owner:** editorial-evidence subagent, followed by independent editorial reviewers

**Depends on:** F3

**Deliverables:**

- Use the existing calibration, fresh-capture, and attestation commands from
  `better_prompt_plan.md`; build no replacement experiment framework.
- Run the approved live calibration payload and the sealed representative quiet/busy project payloads
  through fresh role processes using the recorded F0 egress boundary.
- Preserve the exact evidence inputs, prompt-contract identity, candidate outputs, paired anonymous
  referee records, calibration artifact, route-free attestation, and redacted route results.
- Compare complete output qualitatively with the positive qualities demonstrated on August 22 and 23.
- Record what the post says Neil made, what caught his attention, what surprised or pleased him, what
  he learned, what remains unresolved, and what he wants to try next.

**Acceptance:**

- The selected post is technically grounded in the day's evidence and has a specific thematic title.
- The fresh capture, passing live calibration, and route-free attestation satisfy the existing prompt
  plan's integrity and acceptance contracts.
- Independent reviewers answer the central editorial test from the complete post and cite concrete
  passages supporting their conclusion.
- Technical details support the story; routine work does not crowd out the interesting work.
- Route diagnostics contain no credentials, account labels, editorial context from another role, or
  unrelated environment data.
- A failed qualitative attempt records passage-level evidence and returns to the existing maker prompt
  workflow. Any later exact prompt-text revision follows `HUMAN_GUIDANCE.md`; deterministic prose-shape
  hacks are not used as a substitute.

**Evidence class:** one-time real-route and qualitative evidence.

### F5 - Activate the attested maker contract and prove atomic publication

**Owner:** integration implementation subagent; publisher review follows under publisher rules

**Depends on:** F4

**Deliverables:**

- Cite and verify the exact passing F4 attestation in one separately reviewed producer/publisher
  cutover.
- Make the attested maker contract the sole active producer and publisher contract, then remove the
  retired pre-production production paths.
- Produce one complete date-owned bundle and import it through the publisher's public interface in a
  disposable root.
- Verify bundle, receipt, release, source page, and served route agree on the sole publication identity,
  `report_date`, while the bundle digest is checked only as an integrity value.
- Repair reproducible publication-transition defects within the narrow import/release boundary,
  including interrupted pre-commit recovery and first-publication rollback when still present.
- Prove a repeated coherent date exits at idempotent preflight before model and publication work.

**Acceptance:**

- Bundle validation and strict site build finish before the served release changes.
- Producer and publisher name and verify the same passing attestation and active maker-contract
  identity.
- Failure injection and abrupt-process evidence leave the prior coherent release available or leave a
  clean first-publication state that can retry automatically.
- Recovery handles every persisted transaction state written by the importer.
- Public output contains no runtime credentials or private route diagnostics.
- Publisher changes stay within the declared bundle/import/release boundary and pass that repository's
  required checks.

**Evidence class:** permanent deterministic contract tests plus one-time process and strict-build
checks.

### F6 - Prove the tracked schedule and operating path

**Owner:** operations-verification subagent

**Depends on:** F5

**Deliverables:**

- Reconcile tracked service and timer files with the documented direct command and 04:00
  America/Chicago schedule.
- Stage the tracked units in a disposable root and exercise the exact `ExecStart` command with fixture
  configuration.
- Capture the current installed-unit inventory and identify any drift separately from repository
  correctness.
- Verify the scheduled path is noninteractive, date-owned, idempotent, and phase-diagnostic.

**Acceptance:**

- Tracked units parse successfully and express the documented schedule and direct command.
- The staged command completes against disposable producer and publisher roots.
- Installed-unit drift is either reconciled and verified live or recorded as an explicit deployment
  action with exact evidence; it does not cause redesign of the producer.
- No calendar wait or occupied real date is required for proof.

**Evidence class:** one-time staged and operational evidence.

### F7 - Run final audit and close the plan

**Owner:** fixup manager with fresh requirements, test, security, and maintainability reviewers

**Depends on:** F6

**Deliverables:**

- Run focused and full producer checks, required publisher checks, strict site build, documentation
  checks, and diff checks from the recorded working trees.
- Audit conformance to `HUMAN_GUIDANCE.md`, `better_prompt_plan.md`, repository rules, and this scope.
- Resolve grounded correctness, integrity, privacy, maintainability, validation, and delivery findings.
- Update durable operations/design documentation, changelog, and the evidence index.
- Record any remaining external deployment observation as a follow-up with an exact owner and command.

**Acceptance:**

- Required suites and documentation checks pass.
- The final diff contains no Hermes implementation, configuration, account-routing, dashboard, usage,
  gateway, or auth-store changes.
- Permanent tests satisfy repository rules; one-time evidence remains outside the regular pytest lane.
- A complete generated post passes the central editorial test with passage-level independent review.
- Producer, bundle, receipt, built page, and served route agree on the active maker contract and
  `report_date`.
- The closure index links every acceptance claim to a command, artifact, or review.

**Evidence class:** existing suites, one-time independent audits, and closure manifest.

## Dispatch waves

| Wave | Milestones | Rule |
| --- | --- | --- |
| 0 | F0 | Capture one scope-correct baseline |
| 1 | F1 and F2 | Use separate implementation tasks; reconcile before tests |
| 2 | F3 | Audit and stabilize deterministic producer behavior |
| 3 | F4 | Generate and independently review real maker output |
| 4 | F5 | Verify the narrow producer-publisher transition |
| 5 | F6 | Verify repository-owned schedule and operating path |
| 6 | F7 | Run independent audits, resolve findings, and close |

A failed task is replaced with a fresh task carrying the verified artifact and failure evidence. The
manager keeps only dependency-ready work active and verifies results before opening the next wave.

## Required verification families

Exact commands are recorded in milestone evidence and follow the current repository instructions.
Representative families are:

```bash
# Producer deterministic checks
source source_me.sh
python3 -m pytest -q <focused producer tests>
python3 -m pytest -q tests/

# Real editorial evidence: one-time, outside pytest
./make_blog.py --date <fixture-backed unpublished date>

# Publisher contract and strict build
cd /home/vosslab/nsh/vosslab-daily-blog
python3 -m pytest -q <focused publisher tests>
mkdocs build --strict

# Schedule and documentation
systemd-analyze verify deploy/vosslab-daily-publication.service \
  deploy/vosslab-daily-publication.timer
systemd-analyze calendar '*-*-* 04:00:00 America/Chicago'
python3 -m pytest -q tests/test_markdown_links.py
git diff --check
```

The manager chooses the repository-documented interpreter and environment for each repository. Live
route and host commands are one-time integration checks and produce redacted evidence.

## Risk register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Account-routing work re-enters the project | Scope expands while editorial delivery stalls | Fixed external Hermes command boundary and F7 owned-path audit |
| Maker contract remains experimental only | Reliable pipeline still publishes the wrong voice | F4 passing attestation and F5 atomic producer/publisher cutover |
| Prompt improvement becomes formatting enforcement | Prose passes tests but sounds artificial | Qualitative central test; deterministic checks limited to integrity and safety |
| Retired contracts remain coupled to production | Pre-production complexity and ambiguous ownership persist | F5 removes compatibility paths after attested replacement proof |
| Replacement intent diverges between callers | Regeneration succeeds but publication does not replace | F2 explicit end-to-end replacement argument |
| Fragile tests dictate design | Maintenance grows without protecting users | F3 retention audit and one-time classification |
| Interrupted import blocks future publication | Daily pipeline requires manual cleanup | F5 explicit persisted-state recovery proof |
| Publisher rollback damages first publication | Served path becomes incoherent | F5 first-publication and prior-release failure injection |
| Tracked and installed units drift | Documentation and actual schedule disagree | F6 separates repository proof from installed-state reconciliation |
| Broad review delays closure | Important defects are buried in bikeshedding | F7 blocks only grounded requirement and repository-rule findings |

## Definition of done

The fixup is complete when all of the following are verified:

- The active production editorial contract is the passing attested maker contract from the guiding
  prompt plan, adopted by one reviewed producer/publisher cutover.
- A complete generated post passes the central maker-voice test with concrete independent review.
- August 22 and 23 inform the desired qualities without imposing output equivalence.
- Every editorial role uses a fresh self-contained invocation through the existing Hermes provider
  command boundary.
- The podcast code contains no model-account selection infrastructure or caller-facing account
  controls.
- Deterministic validation protects evidence grounding, prompt identity, schema integrity, date
  ownership, replacement intent, bundle-digest integrity, and publication safety.
- One date completes producer generation, publisher validation, strict build, atomic release, receipt,
  and served-page verification.
- Repeated coherent dates are idempotent, and failed attempts preserve coherent publication state.
- Tracked units express and exercise the direct 04:00 America/Chicago path.
- Permanent tests are offline, deterministic, behavior-focused, and repository-compliant.
- Real model, process, filesystem, publisher, and systemd observations are recorded as one-time
  evidence.
- Final documentation and the closure index link every material claim to verified evidence.

## Evidence record

Each milestone report records:

```text
Milestone:
Owner task:
Dependencies verified:
Owned files:
Behavior changed:
Commands and exit statuses:
Artifacts:
One-time checks:
Permanent tests retained or removed:
Independent review:
Grounded findings and resolution:
Next dependency-ready action:
```

The manager marks a milestone complete only after reading the artifact or target state and verifying
the claim directly.

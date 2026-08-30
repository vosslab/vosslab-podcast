# Daily blog test hygiene disposition

Date: 2026-08-29

## Decision

This is a forward-looking cleanup disposition for the rebuild test suite. It applies the permanent
test checklist in [PYTEST_STYLE.md](../../PYTEST_STYLE.md) and the E2E boundary in
[E2E_TESTS.md](../../E2E_TESTS.md) to the six 2026-08-29 audits. It does not claim that the listed
test changes are complete.

Keep permanent tests only when they prove a stable, offline behavior that could plausibly regress:

- whole eligible artifact promotion and incumbent preservation;
- partial editorial failure without mechanical prose assembly;
- separation of editorial degradation from typed pipeline faults;
- provenance, trusted-root, prompt-tamper, and pre-egress input limits;
- safe handoff, resumable replay behavior, and digest-backed publication integrity; and
- a reader-visible published page, same-date overwrite, and preservation after one representative
  publication verification failure.

Rewrite an existing test when it currently proves one of those behaviors through route counts,
field layouts, step identifiers, private helpers, fixed prompt prose, or default configuration.
Remove it when no stable behavior remains. No production behavior should be changed merely to make
a test in the removal category pass.

## Permanent E2E

Retain exactly one E2E: `tests/e2e/e2e_daily_publication.py`. It is rewritten, not duplicated, to
run a fixed synthetic date through the public command, evidence collection, editorial stages,
selected complete post, sibling import/build, and reader-page verification in disposable roots.
It uses an offline deterministic model substitute and asserts an eligible editorial winner,
digest-backed producer-to-publisher identity, same-date overwrite, and preservation after one
controlled post-import verification failure.

The following runners are one-time implementation evidence and are removed after their M14 record:

- `e2e_daily_blog_stage7_synthesis.py` after its current Stage 7 fixture capability is folded into
  the retained E2E;
- `e2e_daily_blog_production_recovery.py` and `e2e_daily_blog_stage_recovery.py`;
- `e2e_daily_outline_fixture.py`, `e2e_repository_outline_fixture.py`, and
  `e2e_repository_story_fixture.py`; and
- `e2e_stage4_rubric_decision.py` after its linked decision record and capture identities are in
  the M14 fixture matrix.

## Fast-suite disposition

The six audits cover Stages 3 through 7, recovery and run state, publication, and E2E runners.
Their common disposition is:

- Configuration: keep fail-closed unsafe, duplicate-route, incomplete, and under-budget behavior.
  Remove default values and capacity formulas.
- Prompts and parsers: keep identity/tamper, bounded untrusted-data, and malformed-output behavior.
  Remove headings, copy, resource inventories, and historical prompt-byte snapshots.
- Editorial stages: keep eligibility, whole-artifact promotion, partial-loss survival, safe repair,
  and incumbent preservation. Remove replica totals, pair schedules, reviewer order, and route
  calls, plus reliability-step layouts.
- Recovery and state: keep typed fault/degradation distinction, selected-artifact lineage, trusted
  roots, and replay divergence rejection. Remove exact dataclass fields, callback order,
  ladder-depth calibration, and raw state schemas.
- Publication and bundles: keep selected-post binding, no fabrication under partial loss, canonical
  logical paths, and sealed digest validation. Retain only the importer-required exact two-summary
  bundle compatibility; remove slot/order and duplicate-byte witness probes.

M14 preserves the value of every removed harness as a concise evidence row: source command, commit,
fixture date when applicable, no-egress result, outcome, and SHA-256 of a generated capture or
fault artifact when one exists. The harness then leaves the repository. This separates a one-time
rebuild proof from a durable regression obligation.

## Explicit exclusions

The permanent suite does not gate on exact model-call counts, reviewer/referee topology, retry
counts or delays, step names, defaults, prompt copy, fixed response text, or byte equivalence.
Those properties are implementation details or editorial inputs that can improve over time.

Two narrow integration checks remain exact where the protocol requires them: content and evidence
digests that bind sealed publication artifacts, and the external importer's two-summary bundle
shape. Neither is a golden-prose or frozen-prompt test.

## Next actions

1. Rewrite or remove the audited tests using this disposition, preserving unrelated test coverage.
2. Fold the current Stage 7 synthetic fixture into `e2e_daily_publication.py`, then delete the
   duplicate E2E and other recorded one-time runners.
3. Run focused offline tests and the one retained controlled E2E.
4. Have an independent reviewer confirm that the resulting tests satisfy
   [PYTEST_STYLE.md](../../PYTEST_STYLE.md) and that the M14 evidence fields are recorded before
   accepting the cleanup.

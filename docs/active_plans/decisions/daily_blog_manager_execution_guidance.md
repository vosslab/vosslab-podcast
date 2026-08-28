# Daily blog manager execution guidance

## Purpose

Use this guidance with [docs/DAILY_BLOG_PIPELINE_FIXUP_PLAN.md](../../DAILY_BLOG_PIPELINE_FIXUP_PLAN.md)
and [docs/active_plans/better_prompt_plan.md](../better_prompt_plan.md). Build a working,
autonomous daily-blog pipeline that remains maintainable after pre-production.

## Maker voice outcome

Build toward a blog that reads as if Neil sat down after coding and wrote about:

- What he made.
- What interested or surprised him.
- Why he enjoyed working on it.
- What he learned.
- What he wants to try next.

Use the Aug. 22 and Aug. 23 posts as positive evidence for the intended first-person maker register.
Use the prompt-engineering literature and the better-prompt plan to improve the system deliberately.

Write prompt instructions as direct desired behavior:

- Write as the person who made this software.
- Tell the interesting story inside today's work.
- Show what drew attention, what surprised the maker, what they enjoyed, what they learned, and what
  remains unresolved.
- Give important details room to breathe and treat routine work briefly.
- Let technical details support the story.
- Use examples to demonstrate the intended voice.
- Write with curiosity, satisfaction, uncertainty, and the personality of someone describing work
  they care about.

Keep maker-voice evidence, prompt approval, external-context use, activation, publication, and import
within the separately declared boundaries in [docs/HUMAN_GUIDANCE.md](../../HUMAN_GUIDANCE.md) and
[docs/active_plans/better_prompt_plan.md](../better_prompt_plan.md).

## Grounded implementation gates

Use the repository rules as the test and artifact authority:

- [docs/REPO_STYLE.md](../../REPO_STYLE.md)
- [docs/PYTEST_STYLE.md](../../PYTEST_STYLE.md)
- [tests/TESTS_README.md](../../../tests/TESTS_README.md)
- [devel/DEVEL_README.md](../../../devel/DEVEL_README.md)
- Other relevant repository style documents for the touched language, test tier, and artifact type.

Ground every acceptance gate in at least one concrete source:

- User-visible behavior.
- Security or data-integrity boundary.
- External protocol.
- Explicit operating policy.
- Repository rule.

Use content identity checks for artifact integrity, prompt-scope preservation, and staged-runtime parity.
Use behavioral contracts for product improvement. Record the rationale for every gate in its milestone
evidence.

## Test and fixture discipline

Keep permanent tests small, offline, deterministic, behavior-focused, and compliant with the
[docs/PYTEST_STYLE.md](../../PYTEST_STYLE.md) checklist.

- Use inline inputs, fake clocks, in-process fakes, and `tmp_path` for fast pytest coverage.
- Place durable fast behavior tests in `tests/`.
- Place browser, network, real-process, multiprocess, PTY, filesystem-permission, package, systemd,
  and full pipeline checks in the appropriate direct E2E tier or one-time evidence record.
- Keep fixtures compact, redacted, integrity-pinned, and owned by the repository component that uses
  them.
- Retain a permanent test when it protects meaningful durable behavior. Replace a test that drives an
  unrequested product hack with a grounded behavioral check or remove it.
- Treat realistic process and host observations as useful implementation evidence without converting
  them into fragile fast-pytest requirements.

## Autonomous completion

Keep every milestone runnable if the user is offline.

- Use captured fixtures, synthetic transitions, disposable roots, staged packages, process barriers,
  temporary service units, and automated behavior harnesses to establish the needed evidence.
- Use manager and fresh subagent verification to replace interactive review and calendar-wait gates.
- Record target-host observations precisely as corroborating context when fixture-backed technical
  verification supplies the required contract evidence.
- Preserve unresolved target drift as a clearly named operational follow-up rather than silently
  changing its meaning.

## Pre-production design

Use the pre-production state to strengthen foundational schemas, contracts, abstractions, and ownership
boundaries when that produces the more durable long-term design. Keep responsibilities explicit,
components replaceable, and product behavior grounded in the stated purpose.

## Milestone handoff

Each handoff records:

- Milestone and dependency status.
- Owned files and behavior changed.
- Grounded acceptance rationale.
- Test tier and permanent-versus-one-time classification.
- Commands and exit status.
- Verified artifact paths.
- Independent review result.
- Residual risk and next autonomous dependency.

## Scope envelope

Approach this as an integration and reliability repair. Keep the validated producer and publisher
pipeline intact while connecting it to the repaired Hermes capacity path and exercising the existing
end-to-end contracts through appropriately scoped fixtures.

- Preserve the established producer/provider route, publication identity, bundle/import boundary, and
  maker-voice workstream unless a verified contract gap requires a focused change.
- Focus source work on the explicit provider boundary, the Hermes shared-capacity lifecycle, the narrow
  staged-runtime integration, and the direct scheduler-command contract.
- Reuse existing abstractions, validation paths, and direct E2E runners when they cover the required
  behavior.
- Add a component, schema, fixture, or test only when it closes a demonstrated gap in a stated
  contract.
- Keep the maker-voice experiment separate from the capacity integration and preserve its approval
  boundaries.
- Record any broader foundational redesign with the user-visible or integrity contract that requires
  it, the focused owned paths, and the verification that establishes its value.

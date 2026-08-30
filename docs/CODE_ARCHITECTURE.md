# Code architecture

## Overview

This repository has two content paths. The established path turns GitHub activity into blog,
social, podcast, and optional audio outputs. The daily-publication path turns one report day's
exact Git evidence into a date-owned post that a separate local publisher imports.

The daily path treats `report_date` as its sole publication identity. It uses independent
editorial candidates, review, and promotion to preserve the strongest eligible grounded work. A
partial editorial failure is recorded as degradation when an eligible artifact survives; absence
of an eligible artifact or an unsafe deterministic boundary is a typed pipeline fault.

## Major components

| Component | Owner | Result |
| --- | --- | --- |
| [`make_blog.py`](../make_blog.py) | Public command | Date selection, replacement intent, and terminal result |
| [`automation/publish_daily_blog.py`](../automation/publish_daily_blog.py) | Command implementation | Configured producer invocation |
| [`pipeline/daily_blog/orchestrator.py`](../pipeline/daily_blog/orchestrator.py) | Lifecycle composition | Ordered admission and phase collaboration |
| [`pipeline/daily_blog/acquisition_workflow.py`](../pipeline/daily_blog/acquisition_workflow.py) | Acquisition coordinator | Roster, mirrors, activity, evidence, and projection |
| [`pipeline/daily_blog/repository_editorial_workflow.py`](../pipeline/daily_blog/repository_editorial_workflow.py) | Repository editorial coordinator | Stage 3/4 repository material and shared route-budget results |
| [`pipeline/daily_blog/publication_workflow.py`](../pipeline/daily_blog/publication_workflow.py) | Stages 5-8 | Daily outline, complete post, synthesis, and validation transitions |
| [`pipeline/daily_blog/publication_finalization.py`](../pipeline/daily_blog/publication_finalization.py) | Finalization coordinator | Selected-post write, sealed bundle, import, and page verification |
| [`pipeline/daily_blog/run_contracts.py`](../pipeline/daily_blog/run_contracts.py) and [`pipeline/daily_blog/run_state.py`](../pipeline/daily_blog/run_state.py) | Durable run record | Resumable bounded state, events, and terminal summaries |
| [`pipeline/daily_blog/prompt_registry.py`](../pipeline/daily_blog/prompt_registry.py) | Prompt identity registry | Sole immutable production contract, policy, and resource selection |
| [`pipeline/daily_blog/publication_contract.py`](../pipeline/daily_blog/publication_contract.py) and [`pipeline/daily_blog/publication_storage.py`](../pipeline/daily_blog/publication_storage.py) | Producer publication boundary | Sealed bundle-v7 and descriptor-owned date storage |
| [`pipeline/daily_blog/publisher.py`](../pipeline/daily_blog/publisher.py) | Publisher process boundary | Import and receipt validation without importing publisher code |

The orchestrator is deliberately a small composition owner. Acquisition, repository editorial, and
publication finalization do not import it; each receives the typed values and narrow lifecycle
dependencies it needs.

## Daily publication flow

```text
1. repository discovery and roster snapshot
2. mirror refresh and report-day activity
3. exact evidence packet and editorial projection
4. independent repository outlines and stories
5. independent daily-outline ranking, writing, review, and promotion
6. independent complete posts, validation, review, repair, and promotion
7. optional final synthesis that preserves an incumbent unless it directly improves it
8. publication validation and selected-post repair when required
9. selected-post write, bundle creation, importer transaction, and page verification
```

Stages 3 through 6 generate multiple independent candidates and promote only eligible whole
artifacts. Review and bounded repair can improve a candidate but never mechanically assemble prose.
Stage 7 begins with the Stage-6 incumbent and retains it if synthesis is unavailable or does not
demonstrate improvement. Recovery takes additional editorial paths when a stage has no promoted
artifact; exhausting those paths records a categorized pipeline fault and a bounded evidence digest.

Expected route and malformed-verdict failures remain stage-local observations. Cache corruption,
invalid identity or path state, configuration errors, and unexpected defects fail the deterministic
boundary. The run outcome is `succeeded`, `degraded`, or `failed`; reader-visible publication
failure after `post.md` is preserved as incomplete operational work rather than discarded prose.

## Durable state and caching

[`pipeline/daily_blog/run_contracts.py`](../pipeline/daily_blog/run_contracts.py) defines the
`vosslab.daily-blog.run.v11` record. `RunStore` persists legal phases, bounded redacted events,
phase identities, editorial summaries, and one `best_artifact_id`. The v11 transition log replays
the incumbent through four exact operations: observation, establishment, editorial replacement,
and publication repair. Stage 7 can request replacement only from its validated direct result;
Stage 8 has its separately typed repair operation.

[`pipeline/daily_blog/locks.py`](../pipeline/daily_blog/locks.py) supplies date ownership and
phase caching. Independent model calls use cache identities that allow compatible completed work to
be reused when later peers fail. The coordinator serializes durable state and shared cache effects,
while route execution stays bounded and parallel inside the configured limits.

## Prompt and evidence trust boundaries

[`pipeline/daily_blog/repositories.py`](../pipeline/daily_blog/repositories.py),
[`pipeline/daily_blog/mirrors.py`](../pipeline/daily_blog/mirrors.py),
[`pipeline/daily_blog/activity.py`](../pipeline/daily_blog/activity.py), and
[`pipeline/daily_blog/evidence.py`](../pipeline/daily_blog/evidence.py) establish the source side.
[`pipeline/daily_blog/projection.py`](../pipeline/daily_blog/projection.py) builds the bounded
editorial input; candidates must resolve their cited evidence against that packet.

`prompt_registry.py` is the only concrete registry owner. It exposes the active approved contract,
its validation policy, template names, and selected example resources through immutable captured
registry state. [`pipeline/daily_blog/activation.py`](../pipeline/daily_blog/activation.py) loads
the tracked activation receipt, which binds the active prompt-contract identity before publication.
Prompt prose remains in [`pipeline/prompts/`](../pipeline/prompts/) and is not changed by this
architecture.

## Producer-publisher boundary

The producer writes `vosslab.daily-blog.bundle.v7`. Its manifest binds the report date, selected
`best_artifact_id`, generator identity, contracts, immutable maker receipt, prompt contract,
evidence packet, roster, editorial projection, post, declared assets, and bundle digest. Candidate
and referee deliberation remain producer-owned run history and are not handoff fields.

`publication_storage.py` reads and writes bundle artifacts through held no-follow descriptors,
enforces bounded regular-file envelopes, and atomically promotes one date-local bundle. The sibling
publisher independently snapshots the declared files, validates the selected post and artifact
identity, and records a `publication-v4` result. Finalization verifies that the importer receipt and
the served-page receipt both bind the same selected artifact.

## Testing and verification

Permanent unit coverage is offline, deterministic, and behavior-focused under
[`tests/`](../tests/). The controlled publication E2E is
[`tests/e2e/e2e_daily_publication.py`](../tests/e2e/e2e_daily_publication.py); it uses disposable
local roots and no model or network route. It covers initial publication, automatic same-date
replacement, and preservation after an injected page-verification failure.

The other retained direct E2Es are intentionally separate infrastructure proofs:

- [`tests/e2e/e2e_daily_blog_evidence_git.py`](../tests/e2e/e2e_daily_blog_evidence_git.py)
- [`tests/e2e/e2e_daily_blog_mirror_refresh.py`](../tests/e2e/e2e_daily_blog_mirror_refresh.py)
- [`tests/e2e/e2e_daily_blog_new_repository.py`](../tests/e2e/e2e_daily_blog_new_repository.py)
- [`tests/e2e/e2e_make_blog.py`](../tests/e2e/e2e_make_blog.py)

[`tests/e2e/run_all.sh`](../tests/e2e/run_all.sh) runs the retained direct E2E programs. Repository
style, permanent-test criteria, and focused test commands are in
[`PYTEST_STYLE.md`](PYTEST_STYLE.md).

## Extension points

- Add an evidence provider through the evidence schema and preserve its provenance through the
  projection and bundle boundary.
- Add or change editorial stage behavior in its phase-owning module, retaining independent
  candidate generation and typed promotion semantics.
- Change settings-owned concurrency, replication, rubric, or cache inputs without treating those
  values as durable artifact identity by themselves.
- Advance a prompt contract by updating the registry, immutable receipt, and producer/publisher
  contract together. Prompt wording remains a separately human-owned editorial change.

## Known gaps

- Verify a new live external-model route only as optional corroboration. Controlled fixture-backed
  evidence remains the unattended acceptance path.

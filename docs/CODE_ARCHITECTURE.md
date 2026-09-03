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
| [`pipeline/daily_blog/acquisition_workflow.py`](../pipeline/daily_blog/acquisition_workflow.py) | Acquisition coordinator | Step-0 commit inventory, active mirrors, activity, and exact evidence |
| [`pipeline/daily_blog/repository_editorial_workflow.py`](../pipeline/daily_blog/repository_editorial_workflow.py) | Repository editorial coordinator | Stage 3/4 repository material and shared route-budget results |
| [`pipeline/daily_blog/publication_workflow.py`](../pipeline/daily_blog/publication_workflow.py) | Stages 5-8 | Daily outline, complete post, synthesis, and validation transitions |
| [`pipeline/daily_blog/stage6.py`](../pipeline/daily_blog/stage6.py), `stage6_primary.py`, [`pipeline/daily_blog/stage6_recovery.py`](../pipeline/daily_blog/stage6_recovery.py), and [`pipeline/daily_blog/stage_recovery_coordinator.py`](../pipeline/daily_blog/stage_recovery_coordinator.py) | Complete-post editorial boundary | Replicated primary work, typed lower-rung recovery, and promotion |
| `stage6_attempt_plan.py` and `stage6_execution.py` | Stage-6 attempt topology | Finite capacity admission, dependency-closed materialization, and plan-bound requests |
| `stage6_cache_identity.py` and `stage6_attempt_reliability.py` | Stage-6 execution evidence | Digest-only cache witnesses and advisory summaries |
| [`pipeline/daily_blog/publication_finalization.py`](../pipeline/daily_blog/publication_finalization.py) | Finalization coordinator | Selected-post write, sealed bundle, import, and page verification |
| [`pipeline/daily_blog/run_contracts.py`](../pipeline/daily_blog/run_contracts.py) and [`pipeline/daily_blog/run_state.py`](../pipeline/daily_blog/run_state.py) | Durable run record | Resumable bounded state, events, and terminal summaries |
| `pipeline/daily_blog/prompt_registry/` | Prompt identity registry | Central immutable declarations and issued resource loads |
| [`pipeline/daily_blog/publication_admission.py`](../pipeline/daily_blog/publication_admission.py) | Final-post admission | Frozen survivor evidence surface, matching projection, and confined publication assets |
| [`pipeline/daily_blog/publication_contract.py`](../pipeline/daily_blog/publication_contract.py), `pipeline/daily_blog/publication_surface_contract.py`, and [`pipeline/daily_blog/publication_storage.py`](../pipeline/daily_blog/publication_storage.py) | Producer publication boundary | Sealed bundle-v9, portable survivor authority, source-safety identity, and descriptor-owned date storage |
| [`pipeline/daily_blog/publisher.py`](../pipeline/daily_blog/publisher.py) and [`pipeline/daily_blog/publisher_contract.py`](../pipeline/daily_blog/publisher_contract.py) | Publisher process boundary | Exact stdin preflight/import, bounded typed subprocess protocol, committed-publication, and reader-body validation |

The orchestrator is deliberately a small composition owner. Acquisition, repository editorial, and
publication finalization do not import it; each receives the typed values and narrow lifecycle
dependencies it needs.

## Daily publication flow

```text
0. repository discovery and authoritative `repository_roster.json` snapshot
1. account-wide GitHub commit search and canonical `daily_active_roster.json`
2. active-repository mirror refresh and exact report-day activity
3. exact evidence packet
4. independent repository outlines and stories
5. independent daily-outline ranking, writing, review, and promotion
6. independent complete posts, validation, optional review, and promotion
7. optional final synthesis that preserves an incumbent unless it directly improves it
8. publication validation and selected-post repair when required
9. selected-post write, bundle creation, importer transaction, and page verification
```

Stages 3 through 6 generate multiple independent candidates and promote only eligible whole
artifacts. Review can improve selection but never mechanically assemble prose or veto every usable
candidate.
Stage 5 gives every retained repository a fair bounded story and outline slice. Each direct outline
comparison receives its own pair-specific projection, so high-volume evidence cannot crowd a
survivor out of the model frame. Stage 6 derives one survivor-scoped prompt context from the
promoted outline, repository stories, and citable evidence. Its primary and recovery frames each
fit a complete 60,000-character envelope while retaining exact source and model-context identities.
Stage 6 runs replicated authors, retains each grounded eligible peer through ordinary route failure,
gives editors candidate-local positive repair objectives, and promotes only a resulting eligible
complete post. Before dispatch, one immutable maximum attempt plan admits primary work, two recovery
rungs, as many as three fresh batches, and bounded same-request transport retries. Each batch then
materializes only generation slots and candidate-dependent reviews whose inputs exist. Reviews bind
the two ordered candidate hashes they receive. Malformed or unavailable reviewer output is recorded
as degradation; it does not trigger another model call. Materialization can only select a
dependency-closed subsequence of the maximum plan and preserves its canonical order.

Complete-post admission is a deterministic mechanical boundary, not a house-style grader. It enforces
typed provenance, evidence and repository authority, output ownership, and approved image paths.
Citation density and presentation findings remain optional positive repair input for later editorial
work and cannot exhaust an otherwise grounded candidate set.

If the primary path is exhausted, the two bounded editorial recovery rungs ask the existing V4 author
for one whole Markdown post from the daily outline and then from the retained repository-story set.
The strongest `RepoStory` is retained only as terminal provenance if both whole-post paths fail; it is
never publishable by itself. Stage 7 begins with the exact Stage-6 incumbent and retains it if
synthesis is unavailable or its eligible challenger does not demonstrate direct improvement.
Recovery exhaustion records a categorized pipeline fault and a bounded evidence digest.

Expected route and malformed-verdict failures remain stage-local observations. Cache corruption,
invalid identity or path state, configuration errors, and unexpected defects fail the deterministic
boundary. The run outcome is `succeeded`, `degraded`, or `failed`; reader-visible publication
failure after `post.md` is preserved as incomplete operational work rather than discarded prose.

## Durable state and caching

[`pipeline/daily_blog/run_contracts.py`](../pipeline/daily_blog/run_contracts.py) defines the
`vosslab.daily-blog.run` record. `RunStore` persists legal phases, bounded redacted events,
phase identities, editorial summaries, and one
`best_artifact_id`. The transition log replays
the incumbent through four exact operations: observation, establishment, editorial replacement,
and publication repair. Stage 7 can request replacement only from its validated direct result;
Stage 8 has its separately typed repair operation.

The run record is a clean pre-production boundary with no historical reader. Survivor selection owns the projection boundary, so a
pre-survivor global `editorial_projection` phase cannot reject a large repository universe before
Stage 5.

[`pipeline/daily_blog/locks.py`](../pipeline/daily_blog/locks.py) supplies date ownership and
phase caching. Independent model calls use cache identities that allow compatible completed work to
be reused when later peers fail. The coordinator serializes durable state and shared cache effects,
while route execution stays bounded and parallel inside the configured limits. Validated route results
buffered during terminal Stage-6 recovery are committed before its typed fault leaves that boundary.
`pipeline/daily_blog/model_cache_contract.py` defines the shared cache identity as a semantic editorial
request: report date, collection limits, selected
activity, and evidence items. It omits mutable mirror inventory, including mirror locations,
default revisions, ref fingerprints, refresh timestamps, and refresh outcomes. A selected commit,
range, or evidence change therefore misses the cache, while an equivalent mirror observation reuses
the completed editorial result. Stage 6 additionally uses the closed
`vosslab.daily-blog.route-cache` witness. It binds the planned slot, materialized prompt, actual
ordered candidate hashes, route name,
and route execution contract without retaining candidate, response, or prompt bytes.

`stage6_attempt_reliability.py` summarizes route and review outcomes for diagnostics. Those summaries
do not approve a model response and cannot prevent publication of an available mechanically valid
post.

## Prompt and evidence trust boundaries

[`pipeline/daily_blog/repositories.py`](../pipeline/daily_blog/repositories.py),
[`pipeline/daily_blog/mirrors.py`](../pipeline/daily_blog/mirrors.py),
[`pipeline/daily_blog/activity.py`](../pipeline/daily_blog/activity.py), and
[`pipeline/daily_blog/evidence.py`](../pipeline/daily_blog/evidence.py) establish the source side.
`activity.py` begins with one account/date GitHub commit search, renders the local Step-0 inventory,
and then resolves those exact repository/SHA references against active local mirrors.
[`pipeline/daily_blog/projection.py`](../pipeline/daily_blog/projection.py) builds bounded editorial
input after the relevant survivor scope is known. Stage-local artifacts resolve their cited evidence
against their authoritative packet under a stage-owned ceiling. Final-post admission is stricter:
[`pipeline/daily_blog/publication_admission.py`](../pipeline/daily_blog/publication_admission.py)
freezes one `PublicationSurface` from the exact Stage-6 survivor packets, bounded model context, and
promoted Stage-5 outline and repository stories before complete-post selection. It derives the
aggregate packet, allowed evidence and image paths, required repository coverage, sealed projection,
and required assets from that one authority. Evidence identities already visible through a promoted
source artifact remain in the sealed projection even when the bounded raw context omitted their
excerpt. The full acquired roster remains provenance context, but it cannot expand final-post scope.
Citations demonstrate grounding inside the frozen surface and cannot shrink its required repository
coverage. A model scope marker remains an equality-checked assertion, never authority.

Final-post policy findings are projected into a closed candidate-local repair envelope. Its
affirmative objective codes ask the editor to add authorized citations, ground claims in authorized
evidence, use authorized images, or meet presentation requirements. The envelope carries only the
candidate hash and allowlisted evidence and source-artifact identities. The editor prompt leads with
the desired synthesis action and authoritative inputs; deterministic admission remains responsible
for enforcing the publication boundary on every returned post.

The `prompt_registry/` package is the central registry owner. Its declarations issue only pinned,
allowlisted loads for the Stage 3-7 resources; stage
modules retain domain rendering and parsing while importing the direct registry leaf they require.
[`pipeline/daily_blog/activation.py`](../pipeline/daily_blog/activation.py) loads
the tracked activation receipt, which binds the active prompt-contract identity before publication.
Prompt prose remains in [`pipeline/prompts/`](../pipeline/prompts/) and is not changed by this
architecture.

## Producer-publisher boundary

The producer writes `vosslab.daily-blog.bundle.v9`. Before Stage 6, one immutable
`PublicationSurface` binds the survivor packets, promoted daily outline and repository stories,
bounded evidence context, repository scope, aggregate packet, editorial projection, allowed evidence
IDs, and allowed screenshots. Stage 6 prompt rendering, whole-post admission, Stage 7 synthesis, and
Stage 8 validation all use that same surface. `Stage6Input` carries execution paths and recovery
catalogue alongside the surface; it does not own a competing copy of editorial authority.

`pipeline/daily_blog/publication_surface_contract.py` serializes that authority as canonical
`publication_surface.json`. Its surface ID binds the report
date and timezone, aggregate and source packet identities, survivor repositories and source
artifacts, projection, allowed evidence IDs, and one-to-one screenshot evidence, asset, and publish
paths. Bundle v9 binds that portable surface alongside the report date, selected `best_artifact_id`,
generator identity, contracts, immutable maker receipt, prompt contract, evidence packet, roster,
editorial projection, post, declared assets, source-safety policy identity, and bundle digest.
Candidate and referee deliberation remain producer-owned run history and are not handoff fields.

`publication_storage.py` reads and writes bundle artifacts through held no-follow descriptors,
enforces bounded regular-file envelopes, and atomically promotes one date-local bundle. The producer
first sends that exact sealed byte snapshot to the sibling's no-write validation endpoint. A valid
`vosslab.daily-blog.import-validation.v1` receipt binds the report date, bundle digest, and selected
artifact before the producer invokes the importing standard-input endpoint; neither endpoint can
reopen a producer path. The sibling validates the portable surface before it admits post evidence or
images, requires the asset manifest and staged assets to equal that surface's allowed screenshot set,
and validates the declared archive and date-keyed `publication-v6` record as one committed
publication. Its `import-receipt.v2` includes the canonical reader-body digest. Finalization then
verifies the whole ordered body and the article-local image sources against the installed portable
surface, rather than relying on title/date chrome or aggregate evidence screenshots.

The subprocess boundary accepts only bounded canonical JSON results. Publisher failures use the
text-free `vosslab.daily-blog.import-failure.v1` envelope with one allowlisted category
(`snapshot_rejected`, `publication_conflict`, `staged_build_failed`, `commit_failed`, or
`publisher_implementation_defect`) and phase (`receive`, `validate`, `preflight`, `stage`, or
`commit`). Malformed publisher output, start failure, and timeout are producer-side typed boundary
faults; foreign stderr and diagnostics do not enter run state or operator output.

The producer treats unapproved links, active raw HTML, and related unsafe Markdown constructs as
editorial ineligibility before promotion. Its portable `publication_source_safety.v1` identity and
digest travel in the sealed contracts: the executable corpus has 35 cases and SHA-256
`d50166736d79be7f7715cc0f7585fac71dfb2aecc1c631b10e01aeca2fb63c6b`. The publisher rechecks the
source independently. Reuse is fail-closed: a bundle made under a different schema or safety
identity is rebuilt rather than silently upgraded. Obsolete pre-production publication records have
no runtime reader.

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

- Add an evidence provider through [`pipeline/daily_blog/evidence.py`](../pipeline/daily_blog/evidence.py)
  and preserve its provenance through the projection and bundle boundary.
- Add or change editorial stage behavior in its phase-owning module, retaining independent
  candidate generation and typed promotion semantics.
- Change settings-owned concurrency, replication, rubric, or cache inputs without treating those
  values as durable artifact identity by themselves.
- Advance a prompt contract by updating central registry declarations, the immutable receipt, and producer/publisher
  contract together. Prompt wording remains a separately human-owned editorial change.

## Known gaps

- Verify a new live external-model route only as optional corroboration. Controlled fixture-backed
  evidence remains the unattended acceptance path.

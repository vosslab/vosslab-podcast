# Daily blog operations

## Ownership

`vosslab-podcast` owns the date-owned producer workflow: it collects exact Git evidence, runs
the editorial stages, seals a bundle, and invokes the local publisher.

`vosslab-daily-blog` owns the MkDocs source tree, per-date publication archive and receipt,
verified built release, served-site pointer, and static service.

`report_date` is the only publication identity. `bundle_sha256` proves the integrity of the
currently published manifest; it does not create a second version of the date.

## Run a publication

Use the root command with one required date selector:

```bash
cd /home/vosslab/nsh/vosslab-podcast
./make_blog.py --yesterday
./make_blog.py --date 2026-08-21
```

`--yesterday` (also `-Y`) resolves the completed previous calendar day in the configured report
timezone. `--date` (also `-d`) accepts canonical `YYYY-MM-DD` and an unambiguous `YYYY-DD-MM`,
then reports the canonical date before work starts. The command restarts under the repository's
physical Python 3.12 environment.

An occupied `--yesterday` (also `-Y`) date is automatically replaced for scheduled unattended
operation. It validates the existing publication state, builds a complete replacement, then
atomically installs that replacement for the same `report_date`. This is automatic same-date
replacement, not versioning.

An occupied explicit `--date` (also `-d`) asks exactly `Overwrite YYYY-MM-DD? [N/y]:`; only an
exact lowercase `y` authorizes replacement. `--yes` (also `-y`) preauthorizes that explicit-date
replacement without prompting. A date with no current publication never prompts. A declined
overwrite is a successful no-fault cancellation: it starts no generation and leaves the existing
publication unchanged. The per-date lock encloses inspection, the replacement decision, and every
publication mutation; the publisher transaction preserves the old coherent publication until a
replacement is verified.

## Pipeline and outcomes

The current pipeline has nine operator-visible stages:

1. Discover the repository roster and refresh exact local mirrors.
2. Locate date-bounded Git activity and assemble evidence packets.
3. Produce and promote repository outlines.
4. Produce and promote repository stories.
5. Rank the material and promote a daily outline.
6. Generate, validate, review, and promote complete-post candidates.
7. Synthesize only when it demonstrably improves the Stage-6 incumbent.
8. Validate publication metadata and write the selected post and sealed bundle.
9. Import, build, and verify the reader-visible page through the publisher.

Every subjective stage produces independent candidates, keeps eligible survivors after ordinary route
failures, uses bounded review and verdict repair, and promotes an eligible whole artifact. It never
mechanically joins prose. Stage 7 preserves the already-grounded Stage-6 incumbent unless an
eligible synthesis wins its direct comparison.

Stage 6 is a bounded editorial subflow: it freezes one survivor-scoped `PublicationSurface`, then
uses that same authority for writer and editor context, evidence citations, repository coverage,
screenshots, recovery, and final admission. The promoted daily outline defines the narrative scope;
only those selected repository stories receive full primary prose context. The surface separately
retains every usable repository survivor as coverage scope and renders its canonical repository roster
in `project_coverage`. Routine work therefore remains visible and recoverable without being forced
into the article body.

Screenshot evidence cited by the promoted outline or its selected narrative stories is resolved to
one exact evidence ID, bundle asset path, and publication path on the surface. Primary, recovery, and
Stage 7 model frames expose only the evidence ID, a short filename-derived description, and the exact
`publish_path`; local asset paths remain private to bundle transfer. A model may use an available
image when it strengthens the post, but image use is not required. Uncited screenshots remain outside
the admitted image set and bundle.

Replicated authors create whole-post candidates; eligible grounded work survives partial route loss;
editors return bounded feedback for those candidates; and promotion selects only an eligible whole
post. If its normal narrative-scoped author/editor path exhausts, its two recovery rungs request a
whole post from the retained daily outline and then from the full retained repository-story catalog.
The retained strongest story remains provenance only and is never assembled into a post. Stage 7 and
publication validation retain the recovery scope when recovery produced the incumbent.

Stage 5 first projects every retained repository story and outline into fair bounded frames. Direct
outline reviews use pair-specific story, outline, and evidence projections. Stage 6 then derives its
narrative and coverage views from the same retained source catalog and seals both on one prompt
context. Its full primary and recovery frames each fit within 60,000 characters. Inspect
`stage5_repository_context.json` and `stage6_prompt_context.json` for the narrative, coverage, image,
source, and semantic cache identities used by those requests.

The user-facing terminal meanings are:

| Outcome | Meaning | Command result |
| --- | --- | --- |
| Success | An editorially generated selected post was imported and its page verified. | Zero |
| Degraded | Partial editorial failure occurred, but an eligible grounded post was preserved and verified. | Zero |
| Incomplete | A sealed post or bundle exists, but import or page verification did not finish. | Nonzero |
| Pipeline fault | No publishable result can be produced, or a trusted boundary is unsafe. A typed category and evidence digest identify the fault. | Nonzero |

Editorial degradation is an expected, bounded route-level condition: timeout, malformed response,
or a failed candidate/review leaves remaining eligible work available. Pipeline faults instead cover
route exhaustion, no eligible generation, unavailable evidence, invalid configuration, unsafe
integrity/path state, and unexpected implementation defects. The public CLI emits a structured
`pipeline_fault` record and exits 2 for a diagnosed pipeline fault.

An exact-transfer preflight rejection is a typed producer/publisher integration fault before publisher
state changes. A publisher staged-build or commit failure leaves the sealed post or bundle available as
incomplete operational work and preserves the prior verified publication. Publisher protocol, start,
and timeout failures are typed boundary faults; terminal state records only an allowlisted category and
phase, never raw publisher stderr or diagnostics.

If a stage cannot produce its own artifact type, the recovery ladder takes another editorial path.
Stage 7 first preserves its exact Stage-6 incumbent when no challenger wins. For an exhausted Stage
6, the existing V4 author writes one whole Markdown post from the promoted daily outline, then one
whole Markdown post from the retained repository-story set. These lower rungs never mechanically
assemble prose. The strongest `RepoStory` is retained only as terminal provenance when both paths
fail; it is not a publishable fallback. Exhausting the ladder is a pipeline fault, not degradation.

## Durable state and recovery

Each run is stored under:

```text
out/<owner>/daily_blog/YYYY-MM-DD/runs/RUN_ID/
```

The date directory also owns `summary.jsonl`, a bounded terminal receipt for each completed or
failed run. Inspect `run_state.json` for phase status and selected artifact, `events.jsonl` for
bounded lifecycle and bundle facts, and `summary.jsonl` for the terminal outcome, publication status,
terminal run-record digest, and verified-page digest. These records intentionally omit prompts, model
responses, credentials, and raw external diagnostics.

Run state uses `vosslab.daily-blog.run.v12`. Each editorial summary carries an exact typed incumbent
transition: observe, establish, editorial replacement, or publication repair. Replay validates the
transition chain and `best_artifact_id`; stage names are observability labels, never authority to
replace a post. Each production retry creates a new auditable run and reuses only compatible
phase and route-cache work. `RunStore.reopen()` is reconciliation-only: it can resolve a pending
transition in an existing run once, but it does not make that run the retry target.

Run v12 proceeds from evidence assembly to repository editorial; the survivor-scoped surface now
owns editorial projection. The reader narrowly migrates compatible retained v11 records with the
retired `editorial_projection` phase, and terminal-summary replay preserves failure receipts that
name that historical phase. New records and receipts use the current phase set.

Hash-verified phase-cache entries reuse matching activity, evidence, projections, and successful
route results. Failed route calls remain retryable, and compatible ordinal calls can be reused when
the configured replication count changes. Model-cache identity describes the semantic editorial
request: selected commits, activity, evidence, prompts, narrative scope, rendered coverage scope,
and selected screenshot evidence-to-publication mappings. Mirror locations, refresh observations,
default-branch observations, and ref fingerprints do not invalidate matching work by themselves.
Changed selected evidence, narrative scope, image mapping, or commits does invalidate the affected
editorial work. Cache reuse saves work; it cannot relax evidence, eligibility, identity, or
publication validation.

Complete-post candidates reused from cache are admitted again against the current frozen
`PublicationSurface` and final-post policy. A cached candidate that no longer meets that admission is
an ineligible editorial peer, not a reason to bypass survivor scope or manufacture a fallback.

For a failed or incomplete run, inspect the terminal summary first, then the bounded events and run
state. Correct the external condition and run the same date again. The new attempt can reuse valid
matching work while the prior attempt remains an auditable receipt.

## Bundle and publication integrity

The producer writes one selected-post handoff at:

```text
out/<owner>/daily_blog/YYYY-MM-DD/publication/
```

Its manifest is `vosslab.daily-blog.bundle.v9`. It binds the report date, selected
`best_artifact_id`, evidence packet, repository roster, editorial projection, immutable
`publication_surface.json`, declared assets, activation and prompt-contract identities, generator
revision, source-safety policy identity, and hashes. The surface records the exact survivor set:
aggregate and source packet identities, repositories, source-artifact attestations, projected
evidence IDs, and the one-to-one evidence ID, asset path, and published image-path entries. Bundle
assets exactly equal those selected image entries; screenshots that remain in aggregate evidence but
were not cited or otherwise selected by the narrative artifacts are not transferred or published.
Candidate and referee topology remains producer-side diagnostic state; it is not publisher input.

The producer sends that validated snapshot through one bounded hash-bound standard-input envelope;
the publisher never reopens a producer bundle path. It first invokes the publisher's no-write
`--validate-bundle-stdin` endpoint and accepts its identity-bound
`vosslab.daily-blog.import-validation.v1` receipt only when it matches the exact sealed transfer.
That preflight validates the same semantic contract but creates no publisher record, archive, post,
release, or `site` change. The importing endpoint then revalidates and accepts only the bounded,
manifest-declared snapshot through held descriptors. It rejects symlinks, nonregular or undeclared
artifacts, missing artifacts, identity mismatch, digest mismatch, and any asset or image reference
outside `publication_surface.json`. Its per-date `vosslab.daily-blog.publication.v6` record binds
the bundle, selected artifact, installed post, archive, release, canonical `article_body_sha256`, and
the surface manifest, hash, and identity to the same report date. The producer returns
`vosslab.daily-blog.import-receipt.v2` only after shared committed-publication validation confirms
the archive, v6 record, surface, and installed post together. Separate page verification requires the
complete ordered reader body in the dated article surface and checks that each article image is one
of the surface's published image paths, while allowing normal site chrome.

The source-safety identity records the version and digest of the policy applied to the selected
Markdown. The active `publication_source_safety.v1` policy has an executable 35-case corpus and
SHA-256 `d50166736d79be7f7715cc0f7585fac71dfb2aecc1c631b10e01aeca2fb63c6b`. It admits only the sealed
surface screenshot paths and GitHub HTTPS links as reader-visible targets; raw HTML and ambiguous,
disguised, or otherwise unapproved active markup make a candidate editorially ineligible. The
publisher independently rechecks the same policy and surface scope at import. A cached bundle is
reused only when its current v9 schema, surface identity, safety identity, and sealed artifacts
validate; otherwise the producer rebuilds it. Earlier publication receipts are retained only for
read-only historical inspection; new imports use v9 bundles and v6 records.

The importer reports actual prior-state results under its date lock:

| Prior date state and authorization | Result |
| --- | --- |
| No record, with or without replacement authorization | `imported` |
| Matching installed bundle | `idempotent` |
| Different installed bundle without authorization | `publication_conflict`, no mutation |
| Different installed bundle with authorization | `replaced` atomically |

`--yes` and the scheduled `--yesterday` path supply replacement authorization. Authorization permits
replacement when a different installed publication exists; it does not require one to exist.

Automated failures use only the bounded text-free
`vosslab.daily-blog.import-failure.v1` envelope. Its categories are `snapshot_rejected`,
`publication_conflict`, `staged_build_failed`, `commit_failed`, and
`publisher_implementation_defect`; phases are `receive`, `validate`, `preflight`, `stage`, and
`commit`. A malformed envelope, publisher start failure, or timeout is a producer-side typed boundary
fault. Operators use the terminal category and phase to correct the owning boundary, without relying
on raw publisher output.

## Configuration and model routes

The `daily_blog` section of `settings.yaml` owns repository and mirror locations, report timezone,
attribution identity, isolated author/referee routes, collection and projection limits, prompt
envelope limits, and editorial reliability settings. Replication counts, review counts, concurrency,
and route budget are configuration-owned so they can evolve without changing durable semantics.

Hermes owns configured model and account selection. Each author, reviewer, and repair is a fresh,
isolated route request with a complete prompt supplied on standard input. The project sends no
provider key or account label, and routes do not inherit saved conversations or sessions.

The active production prompt and maker identities are validated mechanically at the producer and
publisher boundaries. Prompt prose is human-owned editorial material and is not changed by routine
pipeline operation.

## Observability and reliability

The terminal summary and event stream expose bounded counts for attempts, successes, failures,
reuse, repairs, disagreements, and the selected artifact. `run_state.json` and the stage reliability
artifacts additionally retain bounded categorical rejection counts, without candidate, prompt, or
provider prose, so operators can diagnose why eligible editorial work degraded.

The read-only reliability reporter aggregates those receipts across runs. Its rates preserve raw
numerators and denominators and report an absent population as `n/a`; it is advisory only. It does
not decide publication success, enforce an arbitrary threshold, or change retry behavior.

## Controlled verification

The required unattended verification path is the controlled no-egress daily-publication E2E. It
uses disposable roots, deterministic evidence and route boundaries, a sealed bundle, and a verified
local reader page. It requires no credentials, network access, model call, or human approval:

```bash
source source_me.sh && python3 tests/e2e/e2e_daily_publication.py
```

This proves producer-to-publisher integrity and recovery behavior, not that fixture prose establishes
live editorial quality. A live route or network run is optional corroboration and must record its
provenance and an unavailable or `not_run` disposition when it is not performed.

Permanent offline tests protect stable contracts. Exact-Git and mirror E2Es separately protect their
own infrastructure boundaries. Temporary implementation harnesses, historical shadow evaluation,
calibration, experiment capture, and attestation are retired and are not operational commands.

## Scheduling

The producer supplies these user units:

- `deploy/vosslab-daily-publication.service`
- `deploy/vosslab-daily-publication.timer`

Install the checked-in units, reload user systemd, and enable the timer:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/vosslab-daily-publication.service ~/.config/systemd/user/
cp deploy/vosslab-daily-publication.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now vosslab-daily-publication.timer
```

The timer invokes `./make_blog.py --yesterday` at 04:00 America/Chicago. Systemd owns schedule and
service lifecycle; Hermes owns only configured route execution inside one run. The per-date lock and
automatic replacement make a repeated scheduled invocation safe for the same completed date.

`automation/preflight_daily_blog_producer.py` is an optional operator diagnostic for producer
configuration. The scheduled service does not invoke it as a separate gate.

The service supplies the Hermes home while keeping provider/account selection outside project
configuration. The publisher static service remains independently owned by the sibling repository.

Useful local checks are:

```bash
systemctl --user status vosslab-daily-publication.timer
systemctl --user status vosslab-daily-publication.service
systemctl --user status vosslab-daily-blog.service
journalctl --user -u vosslab-daily-publication.service -n 100
systemctl --user list-timers --all
```

## Operator response

- For `degraded`, read the terminal summary and advisory roll-up, then allow the verified selected
  post to stand unless there is a substantive editorial reason to rerun the date.
- For `incomplete`, preserve and inspect the sealed post or bundle, correct the failed publication
  boundary, and rerun the same date; do not manually assemble or copy a post into the publisher.
- For `pipeline_fault`, use its diagnosed category and evidence digest to correct the root cause.
  Do not recast an integrity, evidence, configuration, or implementation defect as a route failure.
- For an occupied date, invoke the normal date command. The complete replacement transaction keeps
  the last verified publication in place until the new one is ready.

# Frequently asked questions

This FAQ covers the current daily-blog operating contract. For the complete workflow, see
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).

## What does this repository generate?

It turns GitHub activity into outlines, blog posts, Bluesky copy, podcast scripts, and optional
audio. Its daily-publication subsystem also creates one evidence-bound blog bundle and imports it
into the local site. See [README.md](../README.md) and
[CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md).

## Which editorial contract publishes?

The producer validates the active maker, activation, and prompt-contract identities before it
publishes. Those identities travel in the sealed bundle, while prompt prose remains human-owned
editorial material. Retired experiment, calibration, capture, attestation, and shadow-evaluation
workflows are not operational commands. See [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).

## How do I make one daily post?

Run `./make_blog.py --yesterday` from the repository root, or select an explicit date with
`./make_blog.py --date 2026-21-08`. The latter means August 21, 2026 and is normalized to
`2026-08-21`. The command reports the canonical date before it starts and delegates one
date-owned publication workflow. See [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).

## Does a repeat replace the post?

Yes. The scheduler runs `./make_blog.py --yesterday` at 04:00 America/Chicago. A scheduled
occupied date is regenerated and atomically replaced after verification under its per-date lock.
An occupied explicit `--date` asks `Overwrite YYYY-MM-DD? [N/y]:`; only exact `y` replaces it.
Use `-y` or `--yes` to authorize that explicit replacement noninteractively. This is replacement,
not versioning. See [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).

## Why can a new repository be missing?

The August 26 `cancer-clicker` post was generated before authoritative roster discovery existed, so
the uncached repository never reached activity, evidence, or headline selection. Current runs fetch
a fresh validated GitHub owner roster and carry creation-day evidence into projection. If a new
repository is missing now, inspect `repository_roster.json` first. See
[CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md).

## What is an active repository today?

For the current daily-blog contract, an active repository is an eligible public owner repository
with attributed activity in the report window. Archived, disabled, and private repositories remain
outside publication scope. See [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).

## Why systemd instead of Hermes?

Scheduling is an operating-system lifecycle responsibility: systemd is the sole 04:00
America/Chicago scheduler and directly runs `./make_blog.py --yesterday`. This gives manual and
unattended runs the same date lock, idempotency, and recovery path. See
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).

## What does Hermes own?

Hermes owns only configured author and referee model/provider execution inside editorial phases.
Repository-owned prompts arrive on standard input; collection, validation, bundling, importing, and
scheduling remain deterministic pipeline responsibilities. Offline checks need neither Hermes nor
network access. See [CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md).

## Why is report_date identity?

One calendar date has one stable publication slot, protected by a per-date lock through inspection,
generation, replacement, and import. Runs are attempts and `bundle_sha256` verifies bytes; neither
identifies the publication. This makes idempotency and intentional replacement unambiguous. See
[USAGE.md](USAGE.md) and [CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md).

## Why allow a clean schema cutover?

This repository is pre-production, so it can advance producer and publisher contracts together
without preserving obsolete aliases or accepting ambiguous legacy versions. The cutover remains
explicit, reviewed, and fail-closed. The active interface is validated independently at import.
See [CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md).

## Where do generated outputs live?

Generated artifacts are user-scoped below `out/<github_username>/`. Each current daily publication
lives at `out/<user>/daily_blog/YYYY-MM-DD/publication/`; that date directory also retains bounded
run receipts and diagnostics. The date is the publication identity and its `bundle_sha256` verifies
the manifest. See
[OUT_DIRECTORY_ORGANIZATION_SPEC.md](OUT_DIRECTORY_ORGANIZATION_SPEC.md).

## What proves publication provenance?

The `vosslab.daily-blog.bundle.v8` manifest binds the report date, selected
`best_artifact_id`, evidence packet, repository roster, editorial projection, declared assets,
activation and prompt-contract identities, generator revision, and hashes. The producer sends its
validated immutable byte snapshot to the publisher on standard input; the publisher never reopens a
producer path. It writes a `vosslab.daily-blog.publication.v5` record and an
`import-receipt.v2` that bind the installed post, canonical reader-body digest, and verified page to
the same date. See
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).

## Why can a grounded post still be rejected before publication?

Grounding proves provenance, but it does not authorize every Markdown construct. The current
source-safety policy accepts reader-visible GitHub HTTPS links and exact sealed screenshot paths,
while treating active raw HTML, ambiguous comments or attributes, and disguised or unapproved
links as editorial ineligibility. Code examples are inert. The policy version and vector digest are
sealed in bundle v8: `publication_source_safety.v1` has an executable 35-case corpus with SHA-256
`d50166736d79be7f7715cc0f7585fac71dfb2aecc1c631b10e01aeca2fb63c6b`. The publisher checks the
post independently. A cache entry with another schema or policy identity is rebuilt rather than
reused.

Legacy `publication.v3` is only an exact historical record reader for an existing occupied date;
new imports create publication v5 records.

## What is editorial degradation?

A route-level failure such as a timeout, malformed result, or failed candidate or review is an
editorial degradation when an eligible grounded post survives and the page verifies. The pipeline
keeps eligible whole artifacts, uses bounded editorial repair, and never mechanically assembles
prose from fragments. A degraded publication is still a verified publication. See
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).

## What is a pipeline fault?

A pipeline fault means no publishable result exists or a trusted boundary is unsafe: for example,
route exhaustion, no eligible generation, unavailable evidence, invalid configuration, or an
integrity, path, or implementation defect. It publishes nothing. The CLI writes a structured
`pipeline_fault` record with the report date and evidence digest, then exits with status 2. See
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).

## How is the pipeline verified unattended?

The permanent controlled daily-publication E2E uses deterministic evidence and routes, disposable
roots, a sealed bundle, and a verified local reader page. It needs no credentials, network access,
model call, or human approval:

```bash
source source_me.sh && python3 tests/e2e/e2e_daily_publication.py
```

It verifies publication and recovery behavior, not live prose quality. A live route or network run
is optional corroboration and records its provenance or `not_run` disposition. See
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).

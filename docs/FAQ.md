# Frequently asked questions

This FAQ answers the recurring operational questions about the GitHub-content pipeline and its
daily blog. For commands, contracts, and failure handling, follow the linked source documents.

## What does this repository generate?

It turns GitHub activity into outlines, blog posts, Bluesky copy, podcast scripts, and optional
audio. Its daily-publication subsystem also creates one evidence-bound blog bundle and imports it
into the local site. See [README.md](../README.md) and
[CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md).

## Is v4 active?

Schema v4 is active for the publication bundle and evidence packet, but the editorial
`v4-maker` contract is not. Production still selects and imports `v3-historical` policy v3;
`v4-maker` is a private, non-publishing experiment. See
[CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md) and
[prompt_experiment_status.md](active_plans/reports/prompt_experiment_status.md).

## Can v4-maker publish?

No. The production orchestrator rejects it before lock acquisition, mirror refresh, model routing,
bundle creation, or importer invocation. The experiment writes only private reports under `out/`.
See [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).

## Does the timer activate v4-maker?

No. The timer runs the active v3 editorial contract. Activation requires a completed reviewed
non-publishing experiment and one explicit producer-publisher contract change. See
[ROADMAP.md](ROADMAP.md) and [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).

## How do I make one daily post?

Run `./make_blog.py --yesterday` from the repository root, or select an explicit
day with `./make_blog.py --date 2026-21-08`. The latter means August 21, 2026;
the command normalizes it to `2026-08-21`. When that date exists, an interactive
terminal asks `Overwrite 2026-08-21? [N/y]:`; `y` replaces the generated post and
the default preserves it. A noninteractive run preserves the existing post and
exits successfully. Otherwise the command runs the active v3 producer through
local site import.
See [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).

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

## Why separate capture, calibration, and attestation?

They prove different facts. Capture seals the busy and quiet experiment inputs from read-only local
evidence. Calibration separately produces approved historical score evidence. Attestation then
recomputes whether an immutable experiment capture and passing calibration meet acceptance criteria,
without a model route or publication side effect. See [ROADMAP.md](ROADMAP.md) and
[prompt_experiment_status.md](active_plans/reports/prompt_experiment_status.md).

## Why is report_date identity?

One calendar date has one stable publication slot, protected by a per-date lock through inspection,
generation, replacement, and import. Runs are attempts and `bundle_sha256` verifies bytes; neither
identifies the publication. This makes idempotency and intentional replacement unambiguous. See
[USAGE.md](USAGE.md) and [CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md).

## What approvals remain?

Before a v4-maker activation decision, approve historical-post sharing, record a passing live
calibration, approve the Hermes author/referee route and project-context access, run and review the
sealed comparison, record its winner, and review the explicit joint producer-publisher cutover.
These approvals do not authorize publication by the experiment. See
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md) and [ROADMAP.md](ROADMAP.md).

## Why allow a clean schema cutover?

This repository is pre-production, so it can advance producer and publisher contracts together
without preserving obsolete aliases or accepting ambiguous legacy versions. The cutover remains
explicit, reviewed, and fail-closed: policy versions 1 and 2 reject, while the active interface is
validated independently at import. See [CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md).

## Where do generated outputs live?

Generated artifacts are user-scoped below `out/<github_username>/`. Each current daily publication
lives at `out/<user>/daily_blog/YYYY-MM-DD/publication/`; run diagnostics live under
`out/<user>/daily_blog_runs/`, and v4 experiment reports under
`out/<user>/daily_blog_experiments/`. The date is the publication identity and its
`bundle_sha256` verifies the manifest. See
[OUT_DIRECTORY_ORGANIZATION_SPEC.md](OUT_DIRECTORY_ORGANIZATION_SPEC.md).

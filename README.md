# Vosslab GitHub content pipeline

An evidence-grounded local pipeline for a maker who wants GitHub work to become a daily blog post,
social copy, podcast script, and optional audio, with every published claim traceable to exact Git
sources.

It turns a day's real work into a story rather than a changelog dump. The ordinary content path
collects repository activity and produces outlines, posts, Bluesky copy, podcast scripts, and audio.
The daily-publication path adds exact-Git evidence, two independent authors, an anonymous referee,
and a validated bundle before a private local MkDocs site can import a post.

## Status before onboarding

The daily blog's v3 historical contract is the production-active contract. The v4 maker-voice
contract is a private, non-publishing experiment: it must not be used to publish or import a post.
The codebase and local site remain pre-production and private; no external users depend on either
contract today.

V4 keeps this central test: "After reading this post, does it feel like Neil sat down after coding
and wrote about what he made, what interested or surprised him, why he enjoyed working on it, what
he learned, and what he wants to try next?"

The August 22 and 23 posts both inform calibration. August 23 is the project-owned runtime voice
example; August 22 remains corpus and calibration evidence rather than prompt material.

`source_me.sh` requires a physical repository-local Python 3.12 environment; the audited host
currently selects Python 3.12.13. The remaining v4 activation evidence is a completed real-route
comparison, a passing live rubric calibration, and a recorded evidence-based activation decision.

One attempted external capture was blocked before any payload egress. It produced no candidate,
referee comparison, quality result, or winner. That is a transport diagnostic, not evidence for an
editorial arm; v3 remains the active contract.

Repository intake now starts from a fresh, validated GitHub owner roster. Public, live owner
repositories receive owner-qualified mirrors, and repository creation becomes typed lifecycle
evidence. This fixes the August 26 `cancer-clicker` failure: a new source repository created during
the report day reaches both authors and the referee as a first-class story signal. See
[docs/CODE_ARCHITECTURE.md](docs/CODE_ARCHITECTURE.md) for the boundary.

## Why this is different

The signature promise is a daily build story with an audit trail. Instead of asking a model to
continue a giant evidence dump, the experimental maker contract gives it a bounded editorial
projection, an affirmative maker brief, and selected writing examples. The final post remains bound
to the evidence that supports it, while technical detail stays in service of the story.

For an approved daily post, the pipeline creates a date-owned producer-to-publisher interface:

```text
Git caches -> activity -> evidence packet -> editorial projection
    -> author A + author B -> validation -> anonymous referee
    -> validated bundle -> private local MkDocs import
```

The publisher independently verifies the bundle, its integrity checksum, evidence provenance, and
active contract. `report_date` is the publication identity; `bundle_sha256` verifies the manifest
that currently serves that date.
A blocked author, invalid candidate, overflow, or `NONE` referee result creates no bundle and calls
no importer.

## A traceable day of building

Every real daily run leaves an inspectable record instead of only a rendered post:

```text
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/
  run_state.json                 authoritative phase state
  events.jsonl                   append-only operational timeline
  repository_roster.json         authoritative eligible repository snapshot
  mirror_manifest.json           owner-qualified mirror provenance

out/vosslab/daily_blog/YYYY-MM-DD/publication/
  bundle.json                    immutable producer/publisher manifest
  evidence.json                  exact source evidence
  editorial_projection.json      bounded context shown to editorial roles
  post.md                         approved final post
```

Each date has one current publication directory. A confirmed replacement builds a fresh post and
atomically installs it at that same path. These artifacts make a useful question answerable: which
Git evidence led to this sentence, and which candidate did the referee select? The full output layout is in
[docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md](docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md).

## Visual proof: from work to publishable story

These captures show the current private work-log landing page and its August 26 post. The rendered
story is the reader-facing end of the traceable run record and validated bundle shown above.

<!-- screenshots:begin (managed by screenshot-docs) -->
![Vosslab Work Log landing page with the visible editorial header and field-notes lead story](docs/screenshots/work_log_landing_page.png)
![August 26 Work Log post titled Making the Interface Tell the Truth with the visible editorial header](docs/screenshots/making_the_interface_tell_the_truth.png)
<!-- screenshots:end -->

Refresh both images from the sibling publisher's verified local build with:

```bash
node automation/capture_work_log_screenshots.mjs
```

## Safe first success

Use Bash and install the project and developer dependencies described in
[docs/INSTALL.md](docs/INSTALL.md). The following focused tests are permanent, offline contract
checks. They use local synthetic inputs and do not call Hermes, refresh mirrors, or import a post.

```bash
source source_me.sh && pytest \
  tests/test_daily_blog_prompt_resources.py \
  tests/test_daily_blog_prompt_experiment.py \
  tests/test_daily_blog_rubric_calibration.py \
  tests/test_daily_blog_experiment_attestation.py
```

Expected result: the private v4 experiment's resource, capture, calibration, and attestation
contracts pass. These regression checks are not v4 activation evidence because no real experiment
result has been reviewed.

## Choose a first route

- Want a daily content draft from GitHub activity? Run the general pipeline below.
- Need an evidence-bound post for the private work log? Use the daily-publication command only when
  its roster, identity, and local publisher are ready.
- Evaluating the v4 maker voice? Capture the sealed comparison, then attest it against a passing
  live calibration. Both stages are private and non-publishing; keep v3 active until a separately
  reviewed activation decision changes the producer and publisher together.

## Use the two pipelines

### General GitHub content

For the established GitHub-to-content path, the local runner collects activity, builds an outline,
then creates a blog post, Bluesky copy, a podcast script, and narration:

```bash
source source_me.sh && python3 automation/run_local_pipeline.py --last-day
```

The runner supports `--last-week`, `--last-month`, `--no-api-calls`, `--no-continue`, and local
model depth selection. It writes user-scoped artifacts under `out/<github_username>/`; the exact
stage sequence and command options belong in [docs/USAGE.md](docs/USAGE.md).

### Daily publication

The repository-root command owns mirror refresh through local site import. Make yesterday's post in
the configured report timezone, or select one explicit day:

```bash
./make_blog.py --yesterday
./make_blog.py --date 2026-21-08
```

The explicit example means August 21, 2026 and is normalized to `2026-08-21`; canonical
`YYYY-MM-DD` input is also accepted. The command selects the repository's physical Python 3.12
environment itself, so no separate activation command is required.

This command can invoke configured model routes and import into the private local site. Run it only
when the repository roster, date, identities, and publisher configuration are ready. The operational
contract, scheduling, recovery behavior, and failure handling are in
[docs/DAILY_BLOG_OPERATIONS.md](docs/DAILY_BLOG_OPERATIONS.md).

The systemd user timer runs `./make_blog.py --yesterday` at 04:00 America/Chicago. It keeps an
existing date unchanged and exits successfully, which makes unattended runs predictable. An
interactive command asks `Overwrite YYYY-MM-DD? [N/y]:` only when that date is already published.
Hermes supplies the configured model/provider execution during prose generation; the rest of the
publication path is deterministic.

### V4 maker experiment: capture, then attest

The maker experiment deliberately separates model execution from the acceptance decision. The
following commands are one-time, approval-gated evidence steps, not permanent E2E suite commands.
First, after explicit approval to send the sealed project evidence through the configured Hermes
author and referee routes, capture the busy and quiet fixture comparison. Capture accepts both
fixture leaves and no calibration argument; it writes a private, non-publishing capture only.

```bash
source source_me.sh && python3 automation/experiment_daily_blog_prompts.py \
  --busy-fixture /absolute/path/to/busy-fixture \
  --quiet-fixture /absolute/path/to/quiet-fixture
```

Separately, live historical calibration requires its documented durable-sharing setting and
per-invocation approval. After that calibration passes, join it to the capture with the
deterministic attestation command:

```bash
source source_me.sh && python3 automation/attest_daily_blog_prompt_experiment.py \
  --capture /absolute/path/to/sealed-capture \
  --calibration /absolute/path/to/passing-live-calibration
```

Neither command activates v4, imports a post, publishes the site, or changes the systemd schedule.
An attestation records whether its inputs satisfy the acceptance contract; activation remains a
separate reviewed decision. The sealed fixtures, artifact contracts, and activation evidence are in
[docs/active_plans/reports/prompt_experiment_status.md](docs/active_plans/reports/prompt_experiment_status.md).

## Documentation routes

- [docs/INSTALL.md](docs/INSTALL.md): prerequisites, dependencies, and local setup.
- [docs/USAGE.md](docs/USAGE.md): canonical content-pipeline and daily-blog workflows.
- [docs/CODE_ARCHITECTURE.md](docs/CODE_ARCHITECTURE.md): component ownership, trust boundaries,
  contracts, and repository intake.
- [docs/FILE_STRUCTURE.md](docs/FILE_STRUCTURE.md): where commands, pipeline stages, prompts,
  tests, and generated artifacts live.
- [docs/DAILY_BLOG_OPERATIONS.md](docs/DAILY_BLOG_OPERATIONS.md): publish, schedule, recover,
  and investigate a daily run.
- [docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md](docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md): generated
  output locations and retention boundaries.
- [docs/FAQ.md](docs/FAQ.md): direct answers about contracts, repositories, routes, and outputs.
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md): setup failures, recovery steps, and
  operational diagnostics.
- [docs/active_plans/better_prompt_plan.md](docs/active_plans/better_prompt_plan.md): the
  maker-voice design, evidence, and activation requirements.
- [docs/active_plans/reports/prompt_experiment_status.md](docs/active_plans/reports/prompt_experiment_status.md):
  current v4 experiment status and what remains before activation.

## Current next steps

Repository discovery, lifecycle evidence, first-day salience, and the August 26 regression are now
production contracts. The remaining v4 work is to obtain a successful approved-route capture,
attest it with passing live calibration, review the private evidence against the central maker
question, and record a separate activation decision.

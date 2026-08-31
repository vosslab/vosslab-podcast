# Pipeline troubleshooting

Use this page to diagnose the local GitHub-to-content runner or the date-owned
daily publication without changing a generated artifact, cache, run record, or
published release. The routes have different recovery boundaries: local drafts
are stage outputs, while the daily route has one durable attempt per run and
one publication identity per `report_date`.

## General runner stops

Symptom: `automation/run_local_pipeline.py` reports a failed named stage or
exits after its configured retry count.

Read the first failing stage name and correct that stage's declared input,
runtime dependency, or configuration before rerunning the established command:

```bash
source source_me.sh && python3 automation/run_local_pipeline.py --last-day
source source_me.sh && python3 automation/run_local_pipeline.py --last-week
```

The runner invokes fetch, changelog summary, outline, outline compilation,
blog, Bluesky, podcast-script, and narrator-audio stages in that order. It
passes the same `settings.yaml` path to each stage. Use `--no-api-calls` only
when a current user-scoped `github_data_*.jsonl` artifact already exists; it
skips fetch and cannot create that input. Inspect the resolved output paths and
the named stage's input before deleting or regenerating cached files. See
[USAGE.md](USAGE.md) for the supported runner options and output locations.

## Daily run records

Symptom: a date-owned daily publication needs diagnosis or recovery.

Start with `out/<owner>/daily_blog/YYYY-MM-DD/summary.jsonl`, then inspect the
selected `runs/RUN_ID/run_state.json` and `runs/RUN_ID/events.jsonl`. The
summary is the bounded terminal receipt; the run files contain bounded phase
and lifecycle facts for that one attempt. They intentionally omit prompts,
model responses, credentials, and raw external diagnostics. Use
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md) for the current layout and
ownership contract.

## Wrong Python environment

Symptom: the bootstrap reports a missing, symbolic-link, or non-3.12 `.venv`.

The repository requires a physical repository-local Python 3.12 environment.
`source_me.sh` fails closed until that environment is present. The audited host
currently selects Python 3.12.13 and its dependencies.

Check the selected interpreter before running a repository command:

```bash
source source_me.sh && python3 --version
source source_me.sh && python3 -c 'import sys, yaml; assert sys.version_info[:2] == (3, 12); print(sys.version)'
```

Recreate the physical environment with the steps in [INSTALL.md](INSTALL.md),
then install the declared dependencies. If the local runner reports a missing
`rich` dependency, install the declared runtime dependencies into that same
environment.

## Missing scheduled run

Symptom: the expected date has no run directory, so there is no
`run_state.json` to inspect. The failure occurred before the orchestrator took
ownership of that date.

Inspect the systemd timer and the most recent service log first:

```bash
systemctl --user status vosslab-daily-publication.timer
systemctl --user list-timers vosslab-daily-publication.timer
journalctl --user -u vosslab-daily-publication.service -n 100
systemctl --user cat vosslab-daily-publication.service
```

The timer invokes `./make_blog.py --yesterday` at 04:00 America/Chicago. It
uses the same date-owned generator and importer path as the manual command and
automatically replaces an occupied date after validation. Compare the installed
unit with the deployment files and confirm that it invokes the repository's
`make_blog.py --yesterday` command.

## GitHub repository discovery is unauthenticated or blocked

Symptom: `repository_discovery` reports a missing `GITHUB_TOKEN`, bad credentials, or a GitHub API
rate-limit failure.

The publication pipeline requires authenticated GitHub discovery. It accepts an explicit process
`GITHUB_TOKEN`; otherwise it reads only that named entry from `$HERMES_HOME/.env`, defaulting to
`~/.hermes/.env`. The checked-in systemd service sets `HERMES_HOME=/home/vosslab/.hermes`.

Verify the source and loader without printing the credential:

```bash
stat -c '%a %U %n' /home/vosslab/.hermes/.env
source source_me.sh && python3 -c \
  'from podlib import runtime_credentials; runtime_credentials.get_github_token(); print("GITHUB_TOKEN available")'
```

Keep the token out of `settings.yaml`. Importing the complete Hermes dotenv with systemd
`EnvironmentFile=` is also the wrong boundary because it would expose every neighboring credential
to the publication process.

## Editorial route degradation or pipeline fault

Symptom: author, editor, reviewer, or repair work records a route failure,
empty response, malformed structured response, or no eligible result.

Read the terminal summary before treating a route problem as a pipeline defect.
A completed `degraded` run promoted an eligible grounded artifact despite
partial editorial failure and verified its page. A completed `succeeded` run
also verified its page. A failed receipt identifies either a typed terminal
pipeline-fault category or an operational failure kind; a process interruption
before a terminal receipt is an incomplete operational failure. The public CLI
emits a bounded `pipeline_fault` JSON record and exits with status 2 only for a
diagnosed terminal pipeline fault.

Route unavailability, malformed output, and failed candidate or review work are
editorial degradation only while an eligible whole artifact survives. Exhausted
routes, no eligible generation, unavailable evidence, invalid configuration,
or an unsafe integrity or path boundary are pipeline faults. A surface,
evidence, or image-admission mismatch is an integrity-boundary fault: it means
the post, bundle, or publisher was presented with authority that does not agree
with the immutable survivor-scoped publication surface. Neither condition
justifies changing prompt prose during recovery.

The recovery coordinator uses additional editorial paths and promotes only an
eligible artifact. It does not mechanically assemble partial prose. Preserve the
bounded phase and category in a ticket; keep route output, prompts, credentials,
and private paths out of logs and tickets.

## Run state or replay rejected

Symptom: loading, resuming, or recording a run rejects an editorial transition,
an incumbent identity, duplicate reliability facts, or a terminal record.

Do not hand-edit `run_state.json`, replay events, or append a replacement step.
The durable record accepts typed `observe`, `establish`, editorial `replace`,
and publication-repair incumbent transitions; it validates the prior and next
artifact identities with the associated reliability observation. A rejected
transition is a state-integrity or implementation fault. Preserve the bounded
error and terminal summary, correct the underlying configuration or code, then
rerun the public command for the same report date.

## Terminal summary or advisory report unavailable

Symptom: `events.jsonl` has no valid terminal-summary line, or the advisory
report exits with `Reliability report input is unavailable or invalid.`

The terminal summary is a bounded, redacted receipt rather than a raw log. It
binds the report date, run identity, terminal record digest, outcome, failure
classification, page-verification digest, and per-step reliability counts.
Inspect the date-owned run first. To aggregate retained summaries without
changing them, run:

```bash
source source_me.sh && python3 automation/report_blog_reliability.py \
  --owner OUTPUT_OWNER --report-date YYYY-MM-DD --output-root out
```

The report is advisory: its denominators show observed runs and attempts, and
it distinguishes completed success, completed editorial degradation, classified
pipeline faults, and incomplete operational failures. It is not a publication
gate or a source of recovery state.

## Missing new repository

Symptom: work from a newly created repository is absent from `activity.json`,
`evidence.json`, `editorial_projection.json`, and the post headline. The
August 26 audit found this exact failure for `vosslab/cancer-clicker`.

Current runs persist `repository_roster.json` before mirror work. Check that
artifact first. A missing record means GitHub did not return an eligible public,
live owner repository or the roster boundary failed. A present record with no
mirror entry means owner-qualified clone or origin validation failed. A present
activity record with no first-day story signal means the GitHub creation time
falls outside the selected local report day or the repository is a fork.

## Mirror refresh failure

Symptom: `mirror_manifest.json` records `"refresh_result": "failed"`, a
nonempty `refresh_error`, a missing default revision, or an unavailable exact
object.

Read the manifest entry for the affected repository and preserve its reported
error. A valid activity phase requires an available exact default object, so a
failed refresh is an evidence-boundary failure rather than a reason to generate
from stale or guessed Git data. Verify the cache origin and local Git state,
correct the source condition, then rerun the date-owned command.

## Publication bundle rejection

Symptom: reuse or import reports a changed schema, policy, prompt contract,
generator contract, evidence packet, projection, selected-post identity, post
hash, or asset hash.

This is a protective rejection. The checksum binds the bundle contents and
contract metadata. Inspect `bundle.json`, `publication_surface.json`,
`evidence.json`, `editorial_projection.json`, and `post.md` together.

The active production interface is `vosslab.daily-blog.bundle.v9`.
`publication_surface.json` is the immutable authority shared by Stage 6,
bundle construction, import, and rendered-page verification. Its aggregate
packet, projection, survivor packet IDs, repository coverage, allowed evidence
IDs, and allowed image entries must agree with the bundled evidence and
projection. The asset manifest and reader-visible Markdown may use only the
surface's allowed images. It hands the publisher the validated selected post
and its artifact identity; candidate and referee deliberation remains
producer-owned run history.

Use the exact bounded rejection code in the terminal receipt to identify the failed relationship.
Surface-related eligibility codes include `unknown_evidence_reference`, `unapproved_image_path`,
`unapproved_screenshot_path`, `project_coverage_mismatch`, and `publication_policy_mismatch`.
An importer contract failure instead uses the bounded `snapshot_rejected` failure category. These
are trust-boundary faults, not an editorial-quality signal. Preserve the receipt and sealed bundle,
correct the contract or source artifact, then rerun the ordinary date-owned workflow. An editor may
improve a grounded post for presentation issues without discarding it, but it cannot expand
evidence or image authority beyond the surface.

Bundle v9 also binds the source-safety policy version and digest:
`publication_source_safety.v1` has an executable 35-case corpus and SHA-256
`d50166736d79be7f7715cc0f7585fac71dfb2aecc1c631b10e01aeca2fb63c6b`. An unsafe reader-visible
Markdown source is an editorial-ineligibility result, not a publication fallback: resolve the
candidate or source condition, then use the ordinary date-owned workflow to generate and validate
a current bundle. Do not reconstruct a candidate from a rejected manifest.
Publication-v3 handling is historical occupied-date inspection/replacement
only, never an import downgrade path.

## Unexpected cache miss or reuse

Symptom: a resumed editorial route either repeats model work after a mirror
refresh or reuses work after an apparently equivalent repository checkout.

Model-cache identity represents the semantic editorial request: the report
date and collection settings, selected historical commits and ranges, and the
evidence made available to the route. Mirror locations, current default branch
tips, and refresh fingerprints are operational inventory, not editorial input.
A move or refresh that leaves the selected commits and evidence unchanged may
reuse the cached route result. A changed selected commit, source content,
evidence item, prompt contract, or stage configuration must produce a new
request identity.

Compare the selected activity and evidence artifacts before treating a cache
result as suspect. A cache-identity mismatch is an operational diagnosis; it
does not change the publication surface, post eligibility, or the date-owned
publication identity. Preserve the bounded run facts and rerun the normal
workflow when semantic input changed.

## Publisher import failure

Symptom: `site_import` fails, or the importer reports an unsupported status or
invalid JSON. The producer accepts `imported`, `idempotent`, and `replaced` receipts.

Inspect the failed run state, event timeline, validated bundle, importer receipt,
and page-verification receipt. A failed import preserves the previous MkDocs
source, publication record, content release, and served site pointer. Correct
the importer-side condition before rerunning the same date.

## Unexpected same-date replacement

Symptom: a run for an already occupied report date reports `replaced` rather
than `imported`.

This is the normal public-command policy. `report_date` is the sole publication
identity; the bundle digest is integrity evidence, not a version. The scheduler
uses `make_blog.py --yesterday`, and the date-owned publication service inspects
the existing date and passes explicit replacement intent whenever it is occupied.
An import receipt may therefore be `imported`, `idempotent`, or `replaced`.

Verify that the bundle digest, selected artifact identity, importer receipt, and
rendered-page digest agree for the report date. If they do not, preserve the
receipts and treat the failure as provenance or publication-integrity failure;
do not repair the published page by editing it directly.

# Daily blog troubleshooting

Use this page to identify a known daily-blog failure without changing a run, a
cache, or a published release. Start with the date-owned run directory: its
`run_state.json`, `events.jsonl`, and bounded terminal summary describe the
same durable attempt.

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
journalctl --user -u vosslab-daily-publication.service -n 100
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

Read the terminal summary before treating the run as a pipeline defect. A
completed `succeeded` run has no recorded editorial degradation; a completed
`degraded` run promoted an eligible artifact despite partial editorial failure.
A `pipeline_fault` CLI result carries a typed category and digest, while an
incomplete operational failure has no completed publication. Route unavailability
and no eligible generation are diagnosed facts, not evidence that any prompt
or model candidate was better.

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
contract metadata. Inspect `bundle.json`, `evidence.json`,
`editorial_projection.json`, and `post.md` together.

The active production interface is `vosslab.daily-blog.bundle.v8`. It hands the
publisher the validated selected post and its artifact identity; candidate and
referee deliberation remains producer-owned run history. Bundle v8 also binds the
source-safety policy version and digest: `publication_source_safety.v1` has an
executable 35-case corpus and SHA-256
`d50166736d79be7f7715cc0f7585fac71dfb2aecc1c631b10e01aeca2fb63c6b`. An unsafe reader-visible
Markdown source is an editorial-ineligibility result, not a publication fallback: resolve the
candidate or source condition, then use the ordinary date-owned workflow to generate and validate
a current bundle. Do not downgrade a bundle, reuse a stale-schema or stale-policy cache entry, or
reconstruct a candidate from a rejected manifest. Publication-v3 handling is historical
occupied-date inspection/replacement only, never an import downgrade path.

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

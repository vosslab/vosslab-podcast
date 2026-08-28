# Daily blog troubleshooting

Use this page to identify a known daily-blog failure without changing a run, a
cache, or a published release. The complete workflow and artifact layout are in
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).

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

The timer invokes `./make_blog.py --yesterday` at 04:00 America/Chicago. A
coherent publication for that date produces a successful preserve result;
otherwise the service enters the same date-owned generator and importer path
as the manual command. Compare the installed unit with the deployment files
and follow the ownership checks in
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md#operator-checks).

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

## Blocked author generation

Symptom: a run stops in `author_generation` or `referee_selection` with
`EditorialBlockedError`, and later phases remain pending. The failure can mean
an unavailable configured route, a prompt overflow, no valid candidates, or a
`NONE` referee verdict.

Inspect the run's `run_state.json` and `events.jsonl` listed in
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md#inspecting-a-run). The
structured events name the failed phase but intentionally omit raw exception
text. Service logs can retain the original exception. Treat a route failure as
an external dependency failure, not as evidence that a prompt arm won or lost.
Keep credentials, command arguments, and private artifact paths out of tickets
and logs.

## Hermes has no project content

Symptom: a sandboxed Hermes smoke reports that `~/.hermes` is read-only, or an
otherwise healthy unsandboxed smoke returns no content. These are different
boundaries, so keep their diagnoses separate.

Use the sandbox result to verify that Hermes cannot mutate its profile state.
Use the unsandboxed smoke to verify the configured executable, active profile,
and stdin transport with a harmless prompt that contains no project payload.
An empty response is a route failure: the runner requires nonempty stdout and
will stop the experiment before it writes a successful capture.

Before sending a sealed fixture, projection, historical post, or other project
payload through an unsandboxed `hermes chat` route, obtain the external-action
approval for that route and project-context access. This approval is distinct
from approval of prompt text. Then run the reviewed sealed command from
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md#prompt-experiment-and-calibration).
Do not treat a sandbox permission error or an empty smoke response as evidence
about the prompt contract or a candidate arm.

## Model sharing is blocked

Symptom: live rubric calibration exits with `Rubric calibration blocked:
explicit historical-post sharing approval and configuration are required.` The
gate stops before the referee route receives the five historical posts.

Enable the durable setting
`daily_blog.shadow_evaluation.external_model_data_sharing: true` in the
reviewed `settings.yaml`, obtain approval for this invocation, then create live
calibration evidence:

```bash
source source_me.sh && python3 automation/calibrate_daily_blog_rubric.py \
  --approve-historical-post-sharing \
  --repetitions 3
```

Use `--prepare-only` to inspect the local input profile without a route. A
passing live result creates the required private calibration artifact; a
prepared-only report does not satisfy the live-calibration requirement.

## Fixture capture rejected

Symptom: the fixture-capture command rejects `--calibration`, an old bundle
input, a non-approved date, or an unverified roster reference.

Fixture capture owns only offline evidence and projection collection. It no
longer accepts `--calibration`; calibration belongs to the later attestation
join. Provide the report date, private fixture root, and a verified immutable
owner-roster snapshot:

```bash
source source_me.sh && python3 automation/capture_daily_blog_experiment_fixture.py \
  --date YYYY-MM-DD \
  --fixture-root /absolute/private/fixture-root \
  --repository-roster-snapshot /absolute/private/roster-snapshot
```

Use the command's `--validate-only` mode to collect and validate the same
offline material without installing a fixture. Keep fixture capture separate
from calibration and model routes.

## Attestation cannot activate

Symptom: attestation fails, or it completes with a non-activation result.

Attestation is route-free and requires two independently verified direct-child
private artifacts: a completed sealed experiment capture and a passing live
calibration. Supply their absolute physical directories to the attestation
command:

```bash
source source_me.sh && python3 automation/attest_daily_blog_prompt_experiment.py \
  --capture /absolute/private/prompt-experiment-ID \
  --calibration /absolute/private/rubric-calibration-ID
```

The command revalidates both artifacts and recomputes acceptance. It can record
a valid losing comparison without activation. Run an experiment only after the
external-action gate permits the configured author and referee routes; run live
calibration only after its configuration and per-invocation sharing approval
are present.

## Private artifact rejected

Symptom: an experiment, calibration, fixture, or attestation command reports a
generic private-artifact or configuration failure.

Use the exact absolute directory produced under the configured private root.
The validators accept a direct child with the expected identity, physical
directory ownership and mode, regular declared files, bounded JSON, matching
hashes, and coherent manifest/report identities. They reject symbolic links,
relative paths, `..` traversal, copies outside the configured root, incomplete
stages, tampered files, and stale identities.

Inspect `manifest.json` and `report.json` locally through the owning command's
documented artifact layout. Preserve the generic diagnostic in shared tickets;
keep private paths, route output, prompts, credentials, and historical text in
the private operator record.

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
from stale or guessed Git data. Verify the cache origin and local Git state
before any operator-approved network retry. The cache layout and lock ownership
are documented in [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md#cache-checks).

## Publication bundle rejection

Symptom: reuse or import reports a changed schema, policy, prompt contract,
generator contract, evidence packet, projection, post hash, or asset hash.

This is a protective rejection. The checksum binds the bundle contents and
contract metadata. Inspect `bundle.json`,
`evidence.json`, `editorial_projection.json`, and `post.md` together, as
described in [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md#inspecting-a-bundle).

The active production importer accepts only the active v3 contract and policy
v3. Policy versions 1 and 2 are rejected, and v4-maker is restricted to its
explicit offline validator path while the experiment remains non-publishing.
Resolve the source contract mismatch, then use the ordinary date-owned workflow
to generate and validate the current artifact. Keep v4 experimentation in its
explicit offline validator path until the activation gate selects it.

## Publisher import failure

Symptom: `site_import` fails, or the importer reports an unsupported status or
invalid JSON. The producer accepts `imported`, `idempotent`, and `replaced` receipts.

Inspect the failed run state, event timeline, and validated bundle. A failed
import preserves the previous MkDocs source, publication record, content
release, and served site pointer. Correct the importer-side condition before retrying the same date, as
described in [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md#failure-and-recovery).

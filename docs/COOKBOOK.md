# Cookbook

Use these small operator recipes to check the local daily-blog workflow without duplicating the
complete procedures in [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md). Commands run from the
repository root and use the repository environment.

## Check local readiness

Confirm that the settings loader and the permanent offline prompt-contract tests agree with the
checked-in configuration before changing a route or starting an experiment.

```bash
source source_me.sh && python3 -m pytest \
  tests/test_pipeline_settings.py \
  tests/test_daily_blog_prompt_resources.py \
  tests/test_daily_blog_prompt_experiment.py \
  tests/test_daily_blog_rubric_calibration.py \
  tests/test_daily_blog_experiment_attestation.py \
  tests/test_daily_blog_voice_metrics.py
```

`source_me.sh` selects the required physical Python 3.12 environment; the audited host currently
uses Python 3.12.13. These offline results are regression evidence, not an activation gate; a
real-route comparison and evidence-based decision remain required. See
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md) for the activation boundary.

## Make one daily post

Use the repository-root command for the active v3 publication workflow. It selects exactly one
report date, relaunches through the repository-local Python 3.12 environment, and owns the
date-level publication boundary.

```bash
./make_blog.py --yesterday
./make_blog.py --date 2026-21-08
```

`--date` prefers `YYYY-MM-DD` and also accepts unambiguous `YYYY-DD-MM`; the example becomes
`2026-08-21`. A coherent existing publication is preserved in noninteractive use; an interactive
terminal asks before replacement. This command may refresh mirrors, invoke configured model routes,
and import the selected v3 post. It is separate from the private v4 experiment, calibration, and
attestation workflow.

## Capture a sealed fixture

First, capture a fresh immutable repository roster snapshot. This is the only networked step.
Record the absolute snapshot path printed by the command.

```bash
source source_me.sh && python3 automation/capture_daily_blog_repository_roster.py
```

Then capture one approved v2 fixture. Use either `2026-08-23` or `2026-08-26`, replace
`ROSTER_SNAPSHOT_PATH` with the recorded absolute path, and create the required fixture root.

```bash
mkdir -p out/vosslab/daily_blog_experiment_fixtures_v2
source source_me.sh && python3 automation/capture_daily_blog_experiment_fixture.py \
  --date 2026-08-23 \
  --fixture-root "$(pwd)/out/vosslab/daily_blog_experiment_fixtures_v2" \
  --repository-roster-snapshot ROSTER_SNAPSHOT_PATH
```

The roster snapshot defines the repository universe. Caches remain evidence storage and never
define scope; every repository in the snapshot must have its owner-qualified local cache before
fixture capture starts. Fixture capture uses only those existing caches: it makes no network calls,
does not clone or refresh repositories, and does not run author or referee routes. It writes a
private packet, projection, and manifest, and fails if a required cache is absent or the fixture
destination already exists. Use `--validate-only` to check local inputs without creating the dated
fixture.

Those are the only allowed capture dates; they do not make every captured leaf runnable. The
consumer currently accepts only this reviewed sealed rotation:

- Quiet: `2026-08-23--4adcb80db0cdde222fbc6a7a53ec008d1198d0cc03f9cecc16c12ddbca24522e`
- Busy: `2026-08-26--04fd7a045538662e5c6b48ad79e08dd608de1b5a10c1c8857c7b12042bad41da`
- Shared roster: `0f79bcfea4d3fb783258df4a37effef5996b6fdb9736ff6944fd17051570b8a1`

A capture produces a new content-addressed leaf. Review and rotate the consumer allowlist before
using any replacement leaf for a real-route experiment.

## Prepare rubric inputs

Profile and hash the fixed historical rubric inputs before any route use. This route-free
preparation stays private and does not invoke a model route, publish a bundle, or call the
publisher importer.

```bash
source source_me.sh && python3 automation/calibrate_daily_blog_rubric.py --prepare-only
```

Preparation produces only a private input-identity report. It neither authorizes historical-post
sharing nor decides whether v4 may be activated. Read
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md) and
[rubric_calibration.md](active_plans/reports/rubric_calibration.md) before requesting a live route.

## Capture a sealed comparison

This is a one-time, approval-gated evidence run rather than a permanent E2E. After explicitly
approving the configured Hermes author and referee route use for the sealed project evidence,
capture the reviewed busy and quiet comparison. This command deliberately has no `--calibration`
option: it writes a sealed, private experiment capture for later deterministic evaluation.

```bash
source source_me.sh && python3 automation/experiment_daily_blog_prompts.py \
  --busy-fixture /home/vosslab/nsh/vosslab-podcast/out/vosslab/daily_blog_experiment_fixtures_v2/2026-08-26--04fd7a045538662e5c6b48ad79e08dd608de1b5a10c1c8857c7b12042bad41da \
  --quiet-fixture /home/vosslab/nsh/vosslab-podcast/out/vosslab/daily_blog_experiment_fixtures_v2/2026-08-23--4adcb80db0cdde222fbc6a7a53ec008d1198d0cc03f9cecc16c12ddbca24522e
```

The runner uses the configured author and referee routes and writes only a private capture below
`out/vosslab/daily_blog_experiments/`. It writes no bundle, calls no publisher importer, and does
not activate or publish v4. Record the absolute new `prompt-experiment-*` directory as
`CAPTURE_PATH` for attestation.

## Calibrate historical scores

This is a separate one-time, approval-gated evidence run. Live calibration requires both
`daily_blog.shadow_evaluation.external_model_data_sharing: true` in `settings.yaml` and the
`--approve-historical-post-sharing` flag for this invocation. It shares the five fixed public
historical posts with the configured referee route and creates private score evidence.

```bash
source source_me.sh && python3 automation/calibrate_daily_blog_rubric.py \
  --approve-historical-post-sharing \
  --repetitions 3
```

When the command reports `pass`, record the absolute `rubric-calibration-*` directory below
`out/vosslab/daily_blog_rubric_calibrations/` as `CALIBRATION_PATH`. A non-passing score still
produces evidence; it is not usable for attestation or activation.

## Attest the evidence

After those approved one-time runs, join one sealed experiment capture to one passing
live-calibration artifact without invoking a model route. Both arguments must be absolute paths
under their configured private roots. This deterministic attestation records this particular
evidence set; it is not a permanent E2E suite command.

```bash
source source_me.sh && python3 automation/attest_daily_blog_prompt_experiment.py \
  --capture CAPTURE_PATH \
  --calibration CALIBRATION_PATH
```

The command writes a content-addressed private attestation below
`out/vosslab/daily_blog_experiment_attestations/` and independently verifies both source
artifacts. It is deterministic, route-free, non-publishing, and does not activate v4. An exit of
`0` only records that the evidence meets the deterministic acceptance policy; a separate reviewed
producer-publisher activation change and human decision remain required.

## Interpret evidence exits

For live calibration and deterministic attestation, interpret process exits as follows:

| Exit | Meaning | Operator action |
| --- | --- | --- |
| `0` | Calibration passed, or attestation recorded an acceptance-ready result. | Preserve the private evidence; do not infer publication or activation. |
| `1` | Calibration completed but did not pass, or attestation recorded a complete non-acceptance result. | Preserve the evidence; do not activate v4. |
| `2` | A required approval, route, input, or private-artifact contract was blocked or failed. | Correct the reported boundary before any new approved run. |

The sealed comparison returns `2` when its fixture or private-artifact contract is blocked. Its
successful capture is still not an activation or publication action.

## Inspect experiment artifacts

Private prompt experiments are stored below `out/vosslab/daily_blog_experiments/`. Inspect their
manifest and report locally; do not copy route output, credentials, or private artifact paths into
public logs.

```bash
source source_me.sh && python3 -m json.tool \
  out/vosslab/daily_blog_experiments/EXPERIMENT_ID/manifest.json
source source_me.sh && python3 -m json.tool \
  out/vosslab/daily_blog_experiments/EXPERIMENT_ID/report.json
```

The real `automation/experiment_daily_blog_prompts.py` runner is non-publishing and invokes the
configured author and referee routes. It writes no publication artifact. Read
[prompt_experiment_status.md](active_plans/reports/prompt_experiment_status.md) before an approved
rerun.

## Inspect a daily run

For a known date and `RUN_ID`, inspect state before reading individual large evidence artifacts.
The event log gives phase progression without raw exception text.

```bash
source source_me.sh && python3 -m json.tool \
  out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/run_state.json
sed -n '1,160p' out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/events.jsonl
source source_me.sh && python3 -m json.tool \
  out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/editorial_projection.json
```

The run has ten ordered phases, from `repository_discovery` through `site_import`. Their ownership,
reuse rules, and failure behavior are documented in
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).

## Inspect an approved bundle

Each approved bundle is the date-owned publication record. Inspect its manifest, projection, and
final post at the stable publication path. Production uses the selected report date directly.

```bash
source source_me.sh && python3 -m json.tool \
  out/OWNER/daily_blog/YYYY-MM-DD/publication/bundle.json
source source_me.sh && python3 -m json.tool \
  out/OWNER/daily_blog/YYYY-MM-DD/publication/editorial_projection.json
source source_me.sh && python3 -m json.tool \
  out/OWNER/daily_blog/YYYY-MM-DD/publication/evidence.json
sed -n '1,220p' out/OWNER/daily_blog/YYYY-MM-DD/publication/post.md
```

Replace `OWNER` with the configured `github.username`. `report_date` is the sole publication
identity. The manifest's `bundle_sha256` is an integrity checksum for the complete bundle, not a
second identity or a run selector.

Do not edit bundle files or remove run records during investigation. Their layout and retention
boundaries are defined in [OUT_DIRECTORY_ORGANIZATION_SPEC.md](OUT_DIRECTORY_ORGANIZATION_SPEC.md).
For publication or mirror actions, follow the explicit boundaries in
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md); those actions can refresh repositories,
invoke models, or import a post.

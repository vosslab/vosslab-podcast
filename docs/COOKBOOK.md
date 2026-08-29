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

Use the repository-root command for the active v4 publication workflow. It selects exactly one
report date, relaunches through the repository-local Python 3.12 environment, and owns the
date-level publication boundary.

```bash
./make_blog.py --yesterday
./make_blog.py --date 2026-21-08
```

`--date` prefers `YYYY-MM-DD` and also accepts unambiguous `YYYY-DD-MM`; the example becomes
`2026-08-21`. A coherent existing publication is preserved in noninteractive use; an interactive
terminal asks before replacement. This command may refresh mirrors, invoke configured model routes,
and import the selected v4 post. Accepted maker evidence remains separate from ordinary daily
publication.

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

Run the mandatory autonomous capture through the fixture Hermes boundary. It uses the exact Hermes
command `hermes chat --provider openai-codex --query-file - --ignore-rules --quiet` with deterministic
captured responses, so no model egress occurs. Hermes retains model and account ownership behind that
boundary. The command writes a private sealed capture; it does not publish.

```bash
source source_me.sh && python3 automation/run_daily_blog_fixture_capture.py
```

Record the absolute `prompt-experiment-*` directory printed by the command as `CAPTURE_PATH`.
Repetitions are bounded configurable procedure inputs recorded in the artifact, not permanent test
requirements.

## Calibrate historical scores

Run the mandatory autonomous calibration over the sealed historical corpus. It writes private,
passage-grounded score evidence without model egress.

```bash
source source_me.sh && python3 automation/run_daily_blog_fixture_calibration.py
```

When it reports `pass`, record the absolute `rubric-calibration-*` directory as `CALIBRATION_PATH`.
Repetitions, score-span tolerance, and separation threshold are bounded configurable procedure inputs
recorded in the artifact, not permanent behavior requirements.

## Attest the evidence

After the autonomous capture and calibration runs, join their absolute private paths without invoking
a model route. This deterministic attestation precedes independent artifact review and sealed
acceptance; it is not a permanent E2E suite command.

```bash
source source_me.sh && python3 automation/attest_daily_blog_prompt_experiment.py \
  --capture CAPTURE_PATH \
  --calibration CALIBRATION_PATH
```

The command writes a content-addressed private attestation below
`out/vosslab/daily_blog_experiment_attestations/` and independently verifies both source
artifacts. It is deterministic and route-free. Independent artifact reviewers then assess the sealed
complete posts against the unchanged central question. The recorded activation is already complete;
later runs are evidence procedures rather than a human dependency.

## Interpret evidence exits

For fixture-backed calibration and deterministic attestation, interpret process exits as follows:

| Exit | Meaning | Operator action |
| --- | --- | --- |
| `0` | Calibration passed, or attestation recorded a review-ready result. | Preserve the private evidence for independent review. |
| `1` | Calibration completed but did not pass, or attestation recorded a complete non-acceptance result. | Preserve the evidence and diagnose the fixture contract. |
| `2` | A fixture, input, or private-artifact contract was blocked or failed. | Correct the reported boundary before a new run. |

The sealed comparison returns `2` when its fixture or private-artifact contract is blocked. Its
successful capture is still not an activation or publication action.

The ordinary `automation/experiment_daily_blog_prompts.py` and
`automation/calibrate_daily_blog_rubric.py` commands remain optional one-time live corroboration.
They require explicit egress consent and never gate activation or closure.

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

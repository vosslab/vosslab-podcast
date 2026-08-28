# Usage

This repository turns GitHub activity into content and optional audio; its
daily-blog workflow imports an evidence-bound post into the private local site.

Load the repository environment before each command:

```bash
source source_me.sh
```

## General content pipeline

Run the primary local workflow for the last completed logical day:

```bash
source source_me.sh && python3 automation/run_local_pipeline.py --last-day
```

Common [`automation/run_local_pipeline.py`](../automation/run_local_pipeline.py)
options are:

- `--last-day`, `--last-week`, and `--last-month` select the activity window.
- `--no-api-calls` reuses fetched JSONL; `--no-continue` regenerates cached
  local-model outputs.
- `--depth`, `--max-retries`, and `--retry-wait-seconds` control generation and
  retry behavior.

`--no-api-calls` does not make later local-model and audio stages offline, and
it fails when no cached fetch JSONL is available.

The pipeline writes artifacts below `out/<github_username>/`; see
[OUT_DIRECTORY_ORGANIZATION_SPEC.md](OUT_DIRECTORY_ORGANIZATION_SPEC.md).

## Daily blog publication

The active production daily-blog interface is v3-historical policy v3. It
gathers exact Git evidence, validates editorial candidates, and imports the
date-owned publication into the configured private site:

```bash
./make_blog.py --yesterday
./make_blog.py --date 2026-21-08
```

Exactly one selector is required. `--date` prefers `YYYY-MM-DD` but also accepts
unambiguous `YYYY-DD-MM`; the executable relaunches through repository Python
3.12. `report_date` is the sole publication identity. Existing coherent posts
are preserved by default, including in a noninteractive timer run.

`make_blog.py` owns report-date selection and one run. Systemd owns the 04:00
America/Chicago schedule and calls it directly. Hermes supplies model execution
inside that run; it owns neither scheduling nor a publication loop. Read
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md) for configuration,
recovery, scheduling, and ownership boundaries.

## Maker experiment

The v4-maker policy v3 is a private, non-publishing experiment. The production
importer remains v3-only. No live maker capture has succeeded, so there is no
winner, acceptance attestation, or v4 activation decision.

The experiment has three independently owned stages. Capture invokes configured
author and referee routes using two sealed fixture directories. Historical
calibration is a separately approval-gated live route operation. Attestation
loads completed artifacts and recomputes the acceptance result without invoking
a model route, importer, publisher, or scheduler.

### Capture

The capture CLI requires direct physical absolute paths for both sealed fixtures
and accepts no calibration input. It writes one private capture artifact only:

```bash
source source_me.sh && python3 automation/experiment_daily_blog_prompts.py \
  --busy-fixture /absolute/path/to/busy-fixture \
  --quiet-fixture /absolute/path/to/quiet-fixture
```

Fixture identities and supported arms are recorded in
[active_plans/reports/prompt_experiment_status.md](active_plans/reports/prompt_experiment_status.md).

### Historical calibration

Prepare the fixed historical rubric inputs without a model route or site import:

```bash
source source_me.sh && python3 automation/calibrate_daily_blog_rubric.py --prepare-only
```

Live historical calibration is separately approval-gated. Before running it,
an operator must enable the durable historical-post-sharing setting in
[`settings.yaml`](../settings.yaml) and approve the invocation explicitly:

```bash
source source_me.sh && python3 automation/calibrate_daily_blog_rubric.py \
  --approve-historical-post-sharing \
  --repetitions 3
```

Only a passing live calibration artifact may be used for attestation.

### Deterministic attestation

After a capture completes and live calibration passes, create the private
attestation with direct physical absolute paths. This command requires both
inputs and does not call Hermes:

```bash
source source_me.sh && python3 automation/attest_daily_blog_prompt_experiment.py \
  --capture /absolute/path/to/prompt-experiment-capture \
  --calibration /absolute/path/to/passing-live-calibration
```

The attestation is review evidence, not an activation; v4 needs a separately
reviewed producer/publisher contract change.

## Known gaps

- TODO: complete and review a real-route v4 experiment before activation.

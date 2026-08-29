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

The active production daily-blog interface is `v4-three-examples-corpus-v2`. It
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

## Maker evidence

The fixture-backed maker evidence accepted v4-maker policy v3 and the
`v4-three-examples-corpus-v2` contract. The producer/publisher cutover imports bundle v5 through
activation `daily-blog-maker-activation-6b104be9c6907eeeffcf330f6b10173857b39c6b05baa46d4cf009a67daa7547`.

The experiment has three independently owned stages. Capture uses the existing
author and referee interfaces with deterministic role fakes and two sealed
fixture directories. Historical calibration uses deterministic referee evidence
for the fixed corpus. Attestation loads completed artifacts and recomputes the
acceptance result without invoking a model route, importer, publisher, or
scheduler. A live Hermes run is optional one-time corroboration.

### Capture

The capture CLI requires direct physical absolute paths for both sealed fixtures
and accepts no calibration input. Its current ordinary invocation uses the configured external route;
do not use it as fixture-backed F4 evidence until the narrow deterministic role-harness configuration
lands. The manager invokes that harness rather than an undocumented command-line flag.

Fixture identities and supported arms are recorded in
[active_plans/reports/prompt_experiment_status.md](active_plans/reports/prompt_experiment_status.md).

### Historical calibration

Prepare the fixed historical rubric inputs without a model route or site import:

```bash
source source_me.sh && python3 automation/calibrate_daily_blog_rubric.py --prepare-only
```

The F4 fixture harness supplies deterministic referee responses through the same strict parsing and
sealed-artifact interfaces used by live calibration. Only its passing fixture-backed calibration
artifact may be used for attestation. Repetitions, score-span tolerance, and separation threshold
are recorded one-time procedure settings; they remain configurable. Live historical calibration may
be run later as redacted corroboration, but it is not an activation prerequisite.

### Deterministic attestation

After the fixture harness writes capture and calibration artifacts, create the private attestation
with their direct physical absolute paths. This command requires both inputs and does not call Hermes:

```bash
source source_me.sh && python3 automation/attest_daily_blog_prompt_experiment.py \
  --capture /absolute/path/to/prompt-experiment-capture \
  --calibration /absolute/path/to/passing-fixture-calibration \
  --reviewer-count 2
```

The attestation is review evidence, not activation readiness. The configured independent reviewers
work only from the sealed artifacts and must pass both complete selected posts with exact
passage-grounded assessments. Each post is the first authority-ordered sample for its fixture;
selection does not consult score or comparison outcomes, and later samples remain diagnostic. Load
the exact descriptor-verified post bytes with `daily_blog.experiment_attestation.load_review_posts`.
The shown count is the current one-time review procedure. V4 then needs a separately reviewed
producer/publisher contract change.

## Next autonomous step

Run F7 full suites and fresh independent audits. The accepted F4-F6 artifacts are retained as
one-time evidence; installed host state remains telemetry.

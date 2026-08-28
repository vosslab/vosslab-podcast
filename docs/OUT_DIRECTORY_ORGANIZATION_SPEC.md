# Out directory organization spec

## Purpose

Define the generated-artifact layout under `out/` so users, pipeline stages, and cleanup tools can
find a run without overwriting another user's files.

## Scope

This contract applies to default input, output, cache, and operational-log paths used by project
scripts. An explicit CLI path remains an intentional override and is used as provided.

## Core rule

Default pipeline artifacts and caches are user-scoped:

- `out/<github_username>/...`

`<github_username>` comes from `settings.yaml` `github.username`. The fetch stage also accepts
`--user`, which determines its scoped paths.

## Allowed top-level namespaces

- `out/<github_username>/`: real pipeline runs.
- `out/logs/`: operational logs grouped by program.
- `out/smoke/`: smoke-test artifacts.
- `out/samples/`: intentionally shared small examples.
- `out/archive/`: manually archived historical outputs.
- `out/tmp/`: disposable scratch data.

A new top-level `out/` namespace requires a documented update to this specification.

## Default user layout

### Daily publication

- `out/<user>/daily_blog/YYYY-MM-DD/publication/bundle.json`
- `out/<user>/daily_blog/YYYY-MM-DD/publication/evidence.json`
- `out/<user>/daily_blog/YYYY-MM-DD/publication/editorial_projection.json`
- `out/<user>/daily_blog/YYYY-MM-DD/publication/post.md`
- `out/<user>/daily_blog/YYYY-MM-DD/publication/assets/`
- `out/<user>/daily_blog_runs/YYYY-MM-DD/RUN_ID/run_state.json`
- `out/<user>/daily_blog_runs/YYYY-MM-DD/RUN_ID/events.jsonl`
- `out/<user>/daily_blog_runs/YYYY-MM-DD/RUN_ID/repository_roster.json`
- `out/<user>/daily_blog_repository_rosters/ROSTER_ID/repository_roster.json`
- `out/<user>/daily_blog_repository_rosters/ROSTER_ID/manifest.json`
- `out/<user>/daily_blog_runs/YYYY-MM-DD/RUN_ID/mirror_manifest.json`
- `out/<user>/daily_blog_runs/YYYY-MM-DD/RUN_ID/activity.json`
- `out/<user>/daily_blog_runs/YYYY-MM-DD/RUN_ID/editorial_projection.json`
- `out/<user>/daily_blog_runs/YYYY-MM-DD/RUN_ID/*.json`
- `out/<user>/daily_blog_locks/YYYY-MM-DD.lock`
- `out/<user>/daily_blog_cache/activity_location/INPUT_HASH/`
- `out/<user>/daily_blog_cache/evidence_assembly/INPUT_HASH/`
- `out/<user>/daily_blog_cache/editorial_projection/INPUT_HASH/`
- `out/<user>/daily_blog_shadow/YYYY-MM-DD/SHADOW_ID/scorecard.json`
- `out/<user>/daily_blog_shadow/YYYY-MM-DD/SHADOW_ID/generated_post.md`
- `out/<user>/daily_blog_shadow/YYYY-MM-DD/SHADOW_ID/reference_post.md`
- `out/<user>/daily_blog_shadow/YYYY-MM-DD/SHADOW_ID/evidence.json`
- `out/<user>/daily_blog_shadow/YYYY-MM-DD/latest.json`
- `out/<user>/daily_blog_shadow_locks/YYYY-MM-DD.lock`
- `out/<user>/daily_blog_rubric_calibrations/CALIBRATION_ID/manifest.json`
- `out/<user>/daily_blog_rubric_calibrations/CALIBRATION_ID/report.json`
- `out/<user>/daily_blog_experiment_fixtures_v2/YYYY-MM-DD--FIXTURE_ID/evidence.json`
- `out/<user>/daily_blog_experiment_fixtures_v2/YYYY-MM-DD--FIXTURE_ID/editorial_projection.json`
- `out/<user>/daily_blog_experiment_fixtures_v2/YYYY-MM-DD--FIXTURE_ID/manifest.json`
- `out/<user>/daily_blog_experiments/prompt-experiment-EXPERIMENT_ID/manifest.json`
- `out/<user>/daily_blog_experiments/prompt-experiment-EXPERIMENT_ID/report.json`
- `out/<user>/daily_blog_experiments/prompt-experiment-EXPERIMENT_ID/FIXTURE-ARM-REPETITION/`
- `out/<user>/daily_blog_experiments/prompt-experiment-EXPERIMENT_ID/FIXTURE-ARM-REPETITION/candidate-0.md`
  when the author route returns a candidate
- `out/<user>/daily_blog_experiments/prompt-experiment-EXPERIMENT_ID/FIXTURE-ARM-REPETITION/candidate-1.md`
  when the second author route returns a candidate
- `out/<user>/daily_blog_experiments/prompt-experiment-EXPERIMENT_ID/FIXTURE-ARM-REPETITION/selected.md`
  when a valid candidate is selected
- `out/<user>/daily_blog_experiment_attestations/prompt-experiment-attestation-ATTESTATION_ID/manifest.json`
- `out/<user>/daily_blog_experiment_attestations/prompt-experiment-attestation-ATTESTATION_ID/report.json`

Experiment fixtures, capture v1 artifacts, calibration artifacts, and attestation v1 artifacts are
private, immutable, and non-publishing. Configuration owns all four roots; the CLIs accept no
alternate output namespace. A capture v1 directory records the sealed fixture rotation, registered
arms, route metadata, candidate material, comparisons, and its content-addressed `capture_id`.

An attestation v1 directory is a deterministic, route-free join of exactly one completed capture
and one passing live calibration from `daily_blog_rubric_calibrations/CALIBRATION_ID/`. Its report
retains those source artifact names and identities, the recomputed acceptance result, and its
content-addressed `attestation_id`. An attestation is evidence for a later reviewed activation
decision only; it does not activate an experiment, create a bundle, publish, import, or change the
schedule.

`report_date` remains the sole publication identity and names only the date-owned publication and
run paths. Capture IDs, calibration IDs, and attestation IDs identify private evidence artifacts;
they are not publication IDs, report-date aliases, bundle IDs, or publication pointers.

`report_date` is the sole publication identity. For an unpublished date,
`make_blog.py --date YYYY-MM-DD` creates a run record and writes
the validated authoritative roster snapshot at `daily_blog_repository_rosters/ROSTER_ID/`, reloads
and verifies it, and binds its path and identity in `run_state.json` before mirror work. It then
writes the per-run sealed `repository_roster.json` and `mirror_manifest.json` for the exact
owner-qualified mirror set. The typed run-v3 `run_state.json` records all ten legal phases, their
status, input and output hashes, reuse state, timestamps, roster/evidence packet references, bundle
reference, and bounded failure details. Phase-specific JSON artifacts and the append-only
`events.jsonl` operational timeline remain beside it for inspection. If the publisher already has a
coherent record for the date, the command reports that publication and creates no run. An interactive
command can confirm replacement; a non-interactive command preserves the existing publication. One
per-date lock covers receipt inspection, generation, and import.

Every complete bundle is an approved final publication. It lives at the stable
`daily_blog/YYYY-MM-DD/publication/` path and contains the current schema version, report date,
`bundle_sha256` integrity checksum, generator revision, prompt and rubric versions,
authority-ranked evidence, bounded editorial projection, exact selected post, asset bytes, candidate
validation summaries, and structured referee result. A confirmed replacement atomically replaces
that date-owned directory.

Phase caches use canonical input hashes and store hash-verified envelopes. Matching repository refs,
date, identity, collection limits, projection limits, prompt limits, and contract versions can reuse
activity, evidence, editorial projection, valid author, candidate-validation, and approved-referee
artifacts while a new run record owns the current execution. Evidence assets are stored beside their
cached packet and verified against their asset manifest. Blocked editorial results remain retryable.

`automation/calibrate_daily_blog_rubric.py` writes only private, non-publishing calibration
artifacts. Preparation leaves retain hashes and deterministic profiles for the five fixed
historical posts without invoking a route. Explicitly approved live leaves retain redacted repeated
scorecards and target/stability aggregates. Neither form creates a bundle or changes a publication
pointer.

`automation/evaluate_daily_blog_shadow.py` writes an immutable non-publishing comparison under the
shadow namespace. Each completed evaluation retains the generated and reference posts, evidence,
candidate outputs and validation, assets, deterministic measurements, and typed semantic scorecard.
Its `latest.json` pointer is independent of production bundle pointers, and the command has no site
import path.

### Fetch and changelog processing

- `out/<user>/github_data_YYYY-MM-DD.jsonl`
- `out/<user>/daily_cache/github_data_YYYY-MM-DD.jsonl`
- `out/<user>/cache/list_repos.json`
- `out/<user>/cache/github_api/`

`pipeline/fetch_github_data.py` writes the dated main JSONL and daily cache files. The date label
uses the fetch stage's logical completed-day window. `pipeline/summarize_changelog_data.py` reads
the latest default fetch JSONL and atomically replaces that same user-scoped JSONL after it
summarizes oversized `repo_changelog` entries. It does not create a separate published content
artifact.

### Outline processing

- `out/<user>/outline.json`
- `out/<user>/outline.md`
- `out/<user>/daily_outlines/github_outline-YYYY-MM-DD.json`
- `out/<user>/daily_outlines/github_outline-YYYY-MM-DD.md`
- `out/<user>/outline_repos/index.json`
- `out/<user>/outline_repos/*.json`
- `out/<user>/outline_repos/*.txt`
- `out/<user>/compilation_outline-<window>-YYYY-MM-DD.md`

`pipeline/github_data_to_outline.py` writes the current outline, daily snapshots, and per-repository
shards. `pipeline/outline_compilation.py` reads daily snapshots and writes the compiled
`outline.json` plus a date-stamped compilation Markdown file.

### Content processing

- `out/<user>/blog_post_YYYY-MM-DD.md`
- `out/<user>/blog_repo_drafts/*.json`
- `out/<user>/bluesky_post-YYYY-MM-DD.txt`
- `out/<user>/podcast_script-YYYY-MM-DD.txt`
- `out/<user>/podcast_narration-YYYY-MM-DD.txt`

`pipeline/outline_to_blog_post.py` adds its date stamp with an underscore. The Bluesky and podcast
stages, `pipeline/blog_to_bluesky_post.py` and `pipeline/blog_to_podcast_script.py`, add their
date stamps with hyphens. The podcast stage writes both script artifacts unless `--skip-narration`
is requested.

### Audio processing

- `out/<user>/podcast_audio-YYYY-MM-DD.mp3`
- `out/<user>/narrator_audio-YYYY-MM-DD.mp3`

`pipeline/script_to_audio.py` creates the Qwen multi-speaker `podcast_audio` MP3 from the
multi-speaker script. `pipeline/script_to_audio_say.py` creates the macOS `say` `narrator_audio` MP3
from the single-speaker narration; temporary WAV or AIFF conversion files are removed after a
successful MP3 conversion.

## Naming rules

- Use lowercase ASCII, numbers, underscores, and hyphens in generated filenames.
- Use `YYYY-MM-DD` date stamps.
- Preserve stable names where a downstream default expects a current artifact, including
  `outline.json` and `outline.md`.
- Use the date-stamped names above for artifacts that represent one content run.

## Behavior rules

- Default paths resolve below `out/<user>/`.
- Explicit custom CLI paths are honored as-is.
- Scripts log resolved paths before writing where practical.
- Scripts do not write default artifacts to bare `out/`.
- Downstream default inputs resolve to the matching user scope. The fetch, changelog, and outline
  stages discover the newest matching fetch JSONL when their default input file is absent.

## Logs

Operational logs that are stored in `out/` use:

- `out/logs/<program>/...`

The macOS launchd installer is an explicit exception. It writes its standard output and error logs
to:

- `~/Library/Logs/vosslab_podcast/launchd/launchd_pipeline.log`
- `~/Library/Logs/vosslab_podcast/launchd/launchd_pipeline.error.log`

## Cleanup

Safe cleanup targets include `out/tmp/`, stale `out/smoke/` artifacts, and old cache files below
`out/<user>/daily_cache/` or `out/<user>/cache/github_api/`. Daily publication bundles and run
records are immutable audit artifacts; remove them only under an explicit retention policy.

Do not delete the newest dated fetch, blog, Bluesky, podcast script, narration, or audio artifact,
or the current `outline.json`, without a deliberate retention decision.

## Non-goals

This specification does not set retention periods, require generated files to be committed, or
change explicit CLI override behavior.

Legacy files directly under bare `out/` are historical and non-canonical.

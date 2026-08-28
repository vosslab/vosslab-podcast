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

- `out/<user>/daily_blog/YYYY-MM-DD/RUN_ID/bundle.json`
- `out/<user>/daily_blog/YYYY-MM-DD/RUN_ID/evidence.json`
- `out/<user>/daily_blog/YYYY-MM-DD/RUN_ID/editorial_projection.json`
- `out/<user>/daily_blog/YYYY-MM-DD/RUN_ID/post.md`
- `out/<user>/daily_blog/YYYY-MM-DD/RUN_ID/assets/`
- `out/<user>/daily_blog/YYYY-MM-DD/latest.json`
- `out/<user>/daily_blog_runs/YYYY-MM-DD/RUN_ID/run_state.json`
- `out/<user>/daily_blog_runs/YYYY-MM-DD/RUN_ID/events.jsonl`
- `out/<user>/daily_blog_runs/YYYY-MM-DD/RUN_ID/editorial_projection.json`
- `out/<user>/daily_blog_runs/YYYY-MM-DD/RUN_ID/*.json`
- `out/<user>/daily_blog_schedule.json`
- `out/<user>/daily_blog_schedule.lock`
- `out/<user>/daily_blog_cache/activity_location/INPUT_HASH/`
- `out/<user>/daily_blog_cache/evidence_assembly/INPUT_HASH/`
- `out/<user>/daily_blog_cache/editorial_projection/INPUT_HASH/`
- `out/<user>/daily_blog_shadow/YYYY-MM-DD/SHADOW_ID/scorecard.json`
- `out/<user>/daily_blog_shadow/YYYY-MM-DD/SHADOW_ID/generated_post.md`
- `out/<user>/daily_blog_shadow/YYYY-MM-DD/SHADOW_ID/reference_post.md`
- `out/<user>/daily_blog_shadow/YYYY-MM-DD/SHADOW_ID/evidence.json`
- `out/<user>/daily_blog_shadow/YYYY-MM-DD/latest.json`
- `out/<user>/daily_blog_shadow_locks/YYYY-MM-DD.lock`

`automation/publish_daily_blog.py --date YYYY-MM-DD` creates one immutable run ID. The typed
`run_state.json` records all nine legal phases, their status, input and output hashes, reuse state,
timestamps, evidence packet reference, bundle reference, and bounded failure details. Phase-specific
JSON artifacts and the append-only `events.jsonl` operational timeline remain beside it for
inspection. The schedule cursor advances atomically only after a matching publication v2 publisher
record exists, stores that record's bundle ID, and revalidates the exact receipt before each backlog
scan.

Every complete bundle is an approved final publication. It contains the current schema version,
report identity, generator revision, prompt and rubric versions, authority-ranked evidence, bounded
editorial projection, exact selected post, asset bytes, candidate validation summaries, and
structured referee result. `latest.json` points to the newest complete bundle for one date without
changing prior run directories.

Phase caches use canonical input hashes and store hash-verified envelopes. Matching repository refs,
date, identity, collection limits, projection limits, prompt limits, and contract versions can reuse
activity, evidence, editorial projection, valid author, candidate-validation, and approved-referee
artifacts while a new run record still owns the current execution. Evidence assets are stored beside
their cached packet and verified against their asset manifest. Blocked editorial results remain
retryable. Complete bundles retain the producing run directory and can be referenced by later runs
only after full artifact revalidation.

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

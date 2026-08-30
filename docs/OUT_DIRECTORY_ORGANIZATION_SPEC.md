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

`report_date` is the sole publication identity. The configured output root defaults to `out`, and
the configured GitHub owner supplies `<user>`. A date has one producer-owned hierarchy:

- `out/<user>/daily_blog/YYYY-MM-DD/post.md`: the trusted date-owned producer destination used
  while the selected complete post is finalized.
- `out/<user>/daily_blog/YYYY-MM-DD/publication/`: the atomically promoted sealed bundle.
- `out/<user>/daily_blog/YYYY-MM-DD/summary.jsonl`: one bounded terminal receipt per completed or
  failed run for the date.
- `out/<user>/daily_blog/YYYY-MM-DD/runs/RUN_ID/`: one detailed run record and its inspectable
  artifacts.
- `out/<user>/daily_blog_locks/YYYY-MM-DD.lock`: the advisory date lock that covers admission,
  generation, import, and replacement.

The sealed `publication/` directory contains exactly the manifest and evidence needed by the
publisher boundary:

- `bundle.json`
- `evidence.json`
- `repository_roster.json`
- `editorial_projection.json`
- `post.md`
- `assets/` containing only manifest-declared evidence assets

The bundle binds the report date, selected artifact identity, generator revision, evidence,
roster, projection, post hash, assets, active prompt contract, and activation identity. The
producer stages those fixed files under descriptor ownership and atomically names the directory
`publication`. A confirmed same-date replacement replaces that one directory; it never creates a
publication version or changes the date identity.

Each `runs/RUN_ID/` directory retains `run_state.json`, `events.jsonl`, and direct JSON artifacts
for the run. Current workflow artifacts include the captured roster and prompt contract, mirror and
activity records, evidence and editorial projection, editorial reliability summaries, selected-post
write record, publication validation, bundle, import, page-verification, and typed recovery fault
when applicable. The pending editorial and terminal-summary JSON journals are transaction-recovery
records and are removed after successful reconciliation. Artifact names are deliberately
stage-owned rather than a fixed editorial-topology contract.

The immutable authoritative roster snapshot is shared outside a single run:

- `out/<user>/daily_blog_repository_rosters/ROSTER_ID/repository_roster.json`
- `out/<user>/daily_blog_repository_rosters/ROSTER_ID/manifest.json`

`run_state.json` records the logical path and identity of the roster snapshot and the sealed
publication path. Its event journal and terminal summary intentionally contain bounded status,
identity, count, and redacted fault facts rather than route prompts, model output, or provider
diagnostics. `summary.jsonl` is the date-level receipt journal used by the advisory reliability
report and retention check; it is not a publication pointer.

Phase caches are producer-owned and hash-addressed:

- `out/<user>/daily_blog_cache/PHASE/INPUT_HASH/ARTIFACT.json`
- `out/<user>/daily_blog_cache/PHASE/INPUT_HASH/assets/` when a cached phase owns assets
- `out/<user>/daily_blog_cache/.locks/PHASE/INPUT_HASH.lock`

Cache phase names and artifact filenames evolve with the workflow. Every reusable JSON envelope
binds its input hash and content hash, and a new `RUN_ID` still owns the current execution record.
The separately configured mirror cache is operational source storage, not a publication artifact
under this output contract.

The sibling daily-blog publisher receives the sealed producer bundle from the date-owned
`publication/` directory. It validates the fixed manifest and declared assets through held
descriptors before importing one byte snapshot and verifying the rendered page. The sibling site
output is publisher-owned and is not part of the producer's `out/<user>/` layout.

Detailed-run retention is an explicit configuration policy, not a cleanup default. With
`detailed_retention_days` unset, run directories remain. With a positive value, the locked command
can remove only a safely contained run directory that is terminal, has no pending terminal journal,
and has exactly one matching terminal receipt. Age is calculated from command start. The
date-level publication and `summary.jsonl` remain; unsafe, incomplete, or unreceipted children are
skipped and reported rather than removed.

The active maker activation is a tracked production input whose identity is bound into the bundle.
It is not an output directory. Retired calibration, experiment, fixture-capture, attestation, and
shadow-evaluation output namespaces have no daily-publication ownership.

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

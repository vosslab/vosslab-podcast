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

### Daily GitHub evidence

- `out/<user>/daily/YYYY-MM-DD/raw_commits.json`
- `out/<user>/daily/YYYY-MM-DD/claims.json`
- `out/<user>/daily/YYYY-MM-DD/run_manifest.json`
- `out/<user>/daily/YYYY-MM-DD/post_draft.md`
- `out/<user>/daily/YYYY-MM-DD/agent_generation_manifest.json`
- `out/<user>/daily/YYYY-MM-DD/author_prompt.txt` (normal Hermes authoring only)
- `out/<user>/daily/YYYY-MM-DD/agent_authoring_result.json` (normal Hermes authoring only)
- `out/<user>/daily/YYYY-MM-DD/post-YYYY-MM-DD.md`
- `out/<user>/daily/YYYY-MM-DD/validation_failures/validation_report.json` (invalid drafts only)
- `out/<user>/daily_site/index.html`
- `out/<user>/daily_site/status.html`
- `out/<user>/daily_site/date/YYYY-MM-DD/index.html`
- `out/<user>/daily_site/posts/post-YYYY-MM-DD.md`
- `out/<user>/daily_site/site_manifest.json`

`pipeline/daily_github_evidence.py` is the independent M2 evidence path. It requires an explicit
`--date YYYY-MM-DD`, applies the configured IANA timezone's local-midnight interval, and stores the
unmodified input commit records in `raw_commits.json`. `claims.json` contains only confirmed claims
with SHA, GitHub API URL, HTML permalink, complete message, timestamps, and identity evidence.
`run_manifest.json` records expected and received collection pages, rate-limit state, identity
outcomes, errors, completeness, and publication prerequisites. A later publication stage must reject
any manifest whose `publication.eligible` is false; a complete empty day remains eligible for an
explicit no-activity post.

`pipeline/daily_github_blog.py` is the independent M3 Hermes authoring and deterministic validation
path. The normal authoring path requires the `hermes` CLI and a current active Hermes profile that
exposes the `daily-github-blogger` skill. It uses that profile's configured route without a
project-local model or provider setting, records the prompt and Hermes subprocess result in the same
run directory, then writes the draft and generation manifest there. The generation manifest maps every
prose paragraph to confirmed claim IDs and matching SHAs. Promotion creates `post-YYYY-MM-DD.md` only
after M2 metadata, claim/SHA declarations, paragraph coverage, and exact Markdown commit permalinks
validate. Failed drafts remain inspectable alongside a separate validation report and never overwrite a
promoted post.

`pipeline/daily_github_site.py` reads only these generated daily artifacts and rebuilds the static
archive deterministically. It sorts dates newest-first, copies only the promoted post filename,
renders one page per date, and leaves incomplete, validation-failed, and complete-unpublished runs
visible in the archive and status page. M4 does not independently rerun M3 validation: the operation
requires a prior successful M3 validation and promotion to `post-YYYY-MM-DD.md`; a draft or generation
manifest cannot satisfy that promotion requirement.
It makes no GitHub, Hermes, model, or provider call. `pipeline/daily_github_site_server.py` serves an
already-built archive only after it validates a configured, locally assigned RFC1918 IPv4 address and
a non-privileged port. The server refuses wildcard, loopback, public, unassigned, and privileged bind
choices before listening.

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
- `out/logs/daily_github_site/access.log` for the private static-site server's query-free requests.

The macOS launchd installer is an explicit exception. It writes its standard output and error logs
to:

- `~/Library/Logs/vosslab_podcast/launchd/launchd_pipeline.log`
- `~/Library/Logs/vosslab_podcast/launchd/launchd_pipeline.error.log`

## Cleanup

Safe cleanup targets include `out/tmp/`, stale `out/smoke/` artifacts, and old cache files below
`out/<user>/daily_cache/` or `out/<user>/cache/github_api/`.

Do not delete the newest dated fetch, blog, Bluesky, podcast script, narration, or audio artifact,
or the current `outline.json`, without a deliberate retention decision.

## Non-goals

This specification does not set retention periods, require generated files to be committed, or
change explicit CLI override behavior.

Legacy files directly under bare `out/` are historical and non-canonical.

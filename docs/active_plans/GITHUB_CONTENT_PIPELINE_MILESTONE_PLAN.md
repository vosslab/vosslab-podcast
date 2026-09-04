# GitHub content pipeline milestone status

## Status

This milestone plan is a completed historical record of the broad GitHub-content pipeline. It is not
an active operating plan. The former daily GitHub blog follow-on is preserved in
[the archived revival plan](../archive/DAILY_GITHUB_BLOG_REVIVAL_PLAN.md), but its M2/M3/M4 design was
superseded by the current bundle-based daily publication subsystem documented in
[CODE_ARCHITECTURE.md](../CODE_ARCHITECTURE.md) and
[DAILY_BLOG_OPERATIONS.md](../DAILY_BLOG_OPERATIONS.md).

## Implemented pipeline

The executable pipeline is script-per-stage and user-scoped by default:

1. `pipeline/fetch_github_data.py` collects GitHub records into dated JSONL and daily caches.
2. `pipeline/summarize_changelog_data.py` processes long changelog records in the fetched JSONL.
3. `pipeline/github_data_to_outline.py` creates current outlines, daily snapshots, and repository
   shards.
4. `pipeline/outline_compilation.py` combines daily snapshots for a day, week, or month window.
5. `pipeline/outline_to_blog_post.py` generates the date-stamped Markdown blog.
6. `pipeline/blog_to_bluesky_post.py` renders the date-stamped Bluesky text from that blog.
7. `pipeline/blog_to_podcast_script.py` renders a multi-speaker script and a single-speaker
   narration script from that blog.
8. Optional audio renderers:
   - `pipeline/script_to_audio.py` renders Qwen multi-speaker audio.
   - `pipeline/script_to_audio_say.py` renders macOS `say` narration audio.

The local orchestration entry point is `automation/run_local_pipeline.py`. It runs fetch, changelog
summarization, outline, outline compilation, blog, Bluesky, podcast-script, and macOS `say` audio
stages. It accepts `--last-day`, `--last-week`, `--last-month`, `--no-api-calls`, `--no-continue`,
and `--depth`.

## Current output contract

Default artifacts are below `output-pipeline/<github_username>/`; the full contract is
[docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md](../OUT_DIRECTORY_ORGANIZATION_SPEC.md).

- Fetch: `github_data_YYYY-MM-DD.jsonl` and `daily_cache/github_data_YYYY-MM-DD.jsonl`.
- Outline: `outline.json`, `outline.md`, `daily_outlines/github_outline-YYYY-MM-DD.json|md`, and
  `outline_repos/` shards.
- Compilation: `compilation_outline-<window>-YYYY-MM-DD.md` plus the current `outline.json`.
- Content: `blog_post_YYYY-MM-DD.md`, `bluesky_post-YYYY-MM-DD.txt`,
  `podcast_script-YYYY-MM-DD.txt`, and `podcast_narration-YYYY-MM-DD.txt`.
- Audio: `podcast_audio-YYYY-MM-DD.mp3` for Qwen and `narrator_audio-YYYY-MM-DD.mp3` for macOS
  `say`.

## Scheduling and workflow status

- No `.github/workflows/` directory is present in this checkout. There is no configured GitHub
  Actions workflow or GitHub Actions schedule.
- `automation/install_launchd_pipeline.sh` can install a per-user macOS launchd job that runs the
  Python runner every Monday at 09:00 local time.
- `automation/uninstall_launchd_pipeline.sh` removes that job.
- The launchd job is not installed merely because the scripts exist; installation is a user action.

## Superseded assumptions

The initial milestone design named retired paths and contracts, including
`outline_github_data.py`, `outline_to_bluesky_post.py`, `outline_to_podcast_script.py`, a shell
runner, bare `output-pipeline/` paths, and WAV/AIFF episode outputs. Those descriptions are superseded by the
current executable paths and output contract above.

The broad pipeline still uses local LLM stages. Its retired daily-blog revival assumptions do not
describe the current daily publication subsystem, whose versioned repository prompts, isolated role
routes, projection contract, and publisher boundary are documented in the current architecture.

## Superseded revival gates

The following rules governed the retired branch-based revival and are retained only as historical
decision context:

- Preserve `dr_voss` and `origin/main`; do not merge, rebase, delete, or force-push either branch.
- Compare both branches in isolated worktrees against the same date fixture.
- Obtain a human-approved baseline before any branch-changing operation.
- Run normal M3 authoring only when `hermes` is available and the current active profile exposes
  `daily-github-blogger`; review the validated, promoted post before treating that route as proven.
- Build and serve M4 only from validated, promoted `post-YYYY-MM-DD.md` artifacts. A draft or
  generation manifest is not a publication input.
- Scheduling remained disabled until the original manual generation, validation, and private-LAN
  review gates passed. That gate is complete and must not be interpreted as a current instruction.

Current scheduling and recovery instructions live only in
[DAILY_BLOG_OPERATIONS.md](../DAILY_BLOG_OPERATIONS.md).

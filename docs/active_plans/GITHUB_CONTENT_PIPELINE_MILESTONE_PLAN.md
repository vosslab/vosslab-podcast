# GitHub content pipeline milestone status

## Status

This milestone plan records the implemented broad GitHub-content pipeline. It is no longer the plan
for new product work. The active follow-on is
[docs/active_plans/DAILY_GITHUB_BLOG_REVIVAL_PLAN.md](DAILY_GITHUB_BLOG_REVIVAL_PLAN.md). Its M2
evidence, M3 author/validation/promotion, and M4 static archive/server code are implemented, but its
human baseline decision, normal active-profile Hermes review, and macOS LAN-promotion gates remain
future work.

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

Default artifacts are below `out/<github_username>/`; the full contract is
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
runner, bare `out/` paths, and WAV/AIFF episode outputs. Those descriptions are superseded by the
current executable paths and output contract above.

The broad pipeline still uses local LLM stages. The daily-blog revival deliberately does not carry
that local-model execution path forward: its M3 prose author uses the current active Hermes profile
and `daily-github-blogger` skill, with mechanical claim and provenance validation. It does not hardcode
a project model or provider.

## Remaining active-revival gates

Before any daily-blog branch-changing operation:

- Preserve `dr_voss` and `origin/main`; do not merge, rebase, delete, or force-push either branch.
- Compare both branches in isolated worktrees against the same date fixture.
- Obtain a human-approved baseline before any branch-changing operation.
- Run normal M3 authoring only when `hermes` is available and the current active profile exposes
  `daily-github-blogger`; review the validated, promoted post before treating that route as proven.
- Build and serve M4 only from validated, promoted `post-YYYY-MM-DD.md` artifacts. A draft or
  generation manifest is not a publication input.
- Keep scheduling disabled until manual generation, validation, and private-LAN review gates pass.

The authoritative requirements, milestones, and open work for that follow-on are in
[docs/active_plans/DAILY_GITHUB_BLOG_REVIVAL_PLAN.md](DAILY_GITHUB_BLOG_REVIVAL_PLAN.md).

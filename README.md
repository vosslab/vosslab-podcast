# Vosslab GitHub content pipeline

Generates evidence-grounded GitHub content for Vosslab, including one durable daily publication
workflow that ends at the private local MkDocs site.

Output contract: [docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md](docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md)

## Current pipeline

1. `pipeline/fetch_github_data.py` collects GitHub records into a dated JSONL file and daily cache.
2. `pipeline/summarize_changelog_data.py` summarizes long `repo_changelog` records in that JSONL
   in place before outline generation.
3. `pipeline/github_data_to_outline.py` creates the current outline, per-repository shards, and
   dated daily outline snapshots.
4. `pipeline/outline_compilation.py` combines daily snapshots for the requested period.
5. `pipeline/outline_to_blog_post.py` writes a date-stamped Markdown blog post from the compiled
   outline.
6. `pipeline/blog_to_bluesky_post.py` writes a date-stamped Bluesky post from the blog Markdown.
7. `pipeline/blog_to_podcast_script.py` writes both a multi-speaker podcast script and, unless
   `--skip-narration` is set, a single-speaker narration script.
8. Optional audio renderers create MP3 files from those script artifacts.

The supplied local runner, `automation/run_local_pipeline.py`, executes stages 1 through 7 and
uses `pipeline/script_to_audio_say.py` for its final `podcast_audio` stage. It does not invoke
`pipeline/script_to_audio.py`; run that Qwen multi-speaker renderer separately when needed.

## Output files

All default pipeline artifacts are user-scoped under `out/<github_username>/`. The username comes
from `settings.yaml` `github.username` unless `--user` overrides the fetch stage.

- `out/<user>/github_data_YYYY-MM-DD.jsonl`: fetched JSONL for the logical completed day.
- `out/<user>/daily_cache/github_data_YYYY-MM-DD.jsonl`: one JSONL cache file per day in the
  active window.
- `out/<user>/daily_outlines/github_outline-YYYY-MM-DD.json` and `.md`: daily outline snapshots.
- `out/<user>/outline.json` and `out/<user>/outline.md`: current outline outputs.
- `out/<user>/outline_repos/index.json` plus per-repository `.json` and `.txt` shards.
- `out/<user>/compilation_outline-<window>-YYYY-MM-DD.md`: compiled outline Markdown.
- `out/<user>/blog_post_YYYY-MM-DD.md`: date-stamped blog Markdown.
- `out/<user>/bluesky_post-YYYY-MM-DD.txt`: date-stamped Bluesky post.
- `out/<user>/podcast_script-YYYY-MM-DD.txt`: multi-speaker podcast script.
- `out/<user>/podcast_narration-YYYY-MM-DD.txt`: single-speaker narration script.
- `out/<user>/podcast_audio-YYYY-MM-DD.mp3`: Qwen multi-speaker audio.
- `out/<user>/narrator_audio-YYYY-MM-DD.mp3`: macOS `say` narration audio.
- `out/<user>/daily_blog/YYYY-MM-DD/RUN_ID/`: immutable daily publication bundles.
- `out/<user>/daily_blog_runs/YYYY-MM-DD/RUN_ID/`: typed run state and phase artifacts.
- `out/<user>/daily_blog_cache/`: hash-verified reusable phase artifacts and evidence assets.

The runner reports the latest files it finds for these output classes when it completes.

## Local use

Install the project dependencies, then run the local runner from the repository root:

```bash
source source_me.sh && python3 automation/run_local_pipeline.py --last-day
```

Available runner windows are `--last-day` (default), `--last-week`, and `--last-month`. The runner
also supports `--no-api-calls` to reuse the latest user-scoped fetch JSONL, `--no-continue` to
regenerate cached LLM outputs, and `--depth 1` through `--depth 4` for the local-model stages.

To run the stages directly, use the same order as the runner:

```bash
source source_me.sh && python3 pipeline/fetch_github_data.py --settings settings.yaml --last-day
source source_me.sh && python3 pipeline/summarize_changelog_data.py --settings settings.yaml
source source_me.sh && python3 pipeline/github_data_to_outline.py --settings settings.yaml
source source_me.sh && python3 pipeline/outline_compilation.py --settings settings.yaml --last-day
source source_me.sh && python3 pipeline/outline_to_blog_post.py --settings settings.yaml
source source_me.sh && python3 pipeline/blog_to_bluesky_post.py --settings settings.yaml
source source_me.sh && python3 pipeline/blog_to_podcast_script.py --settings settings.yaml
source source_me.sh && python3 pipeline/script_to_audio_say.py --settings settings.yaml
```

The fetch stage defaults to the last completed logical day and supports `--last-week` and
`--last-month`. It includes forks by default; use `--no-include-forks` to exclude them. It also
collects repository changelog records by default; use `--skip-changelog` to omit that input.

## Settings

`settings.yaml` supplies the default GitHub username, optional GitHub token, local LLM selection,
and macOS narration settings. CLI flags override applicable values.

```yaml
github:
  username: vosslab
  identity_login: vosslab
  allowed_emails: []
  timezone: America/Chicago
  token: ""

llm:
  max_tokens: 1200
  repo_limit: 0
  depth: 1
  providers:
    apple:
      enabled: true
    ollama:
      enabled: false

tts:
  say:
    voice: "Siri"
    rate_wpm: 185
```

The currently implemented outline, changelog, and text-generation stages use the configured local
LLM provider. Keep exactly one provider enabled in `llm.providers`.

## Optional audio rendering

`pipeline/script_to_audio.py` renders the multi-speaker `podcast_script` with Qwen TTS. It writes
a dated `podcast_audio-YYYY-MM-DD.mp3` under the user-scoped output directory by default.

```bash
source source_me.sh && python3 pipeline/script_to_audio.py --settings settings.yaml
```

`pipeline/script_to_audio_say.py` renders the single-speaker `podcast_narration` with macOS `say`,
then converts it to `narrator_audio-YYYY-MM-DD.mp3`. It resolves the latest dated narration script
when the undated default path is absent.

```bash
source source_me.sh && python3 pipeline/script_to_audio_say.py --settings settings.yaml
```

List installed macOS voices with:

```bash
source source_me.sh && python3 pipeline/script_to_audio_say.py --list-voices
```

## Scheduling and workflows

There is currently no `.github/workflows/` directory, so this checkout provides no GitHub Actions
workflow or GitHub Actions schedule.

macOS launchd support is available but is not installed until a user runs the installer:

- `automation/install_launchd_pipeline.sh` writes a per-user `com.vosslab.podcast.pipeline` job.
- That job runs `automation/run_local_pipeline.py` every Monday at 09:00 local time.
- `automation/uninstall_launchd_pipeline.sh` removes the job.
- Launchd logs go to `~/Library/Logs/vosslab_podcast/launchd/`.

```bash
chmod +x automation/run_local_pipeline.py automation/install_launchd_pipeline.sh
./automation/install_launchd_pipeline.sh
```

## Daily publication

One date-driven command owns mirror refresh, activity location, evidence assembly, two isolated
author sessions, deterministic validation, anonymous referee selection, immutable bundling, and
local site import:

```bash
source source_me.sh && python3 automation/publish_daily_blog.py --date 2026-08-23
```

The command reads durable repositories below `/home/vosslab/repo-mirrors/vosslab`, resolves exact
Git objects, and treats matching `docs/CHANGELOG.md` date sections as the primary narrative
authority. Supporting documentation, diffs, README context, screenshots, and commit metadata follow
the authority order encoded in `pipeline/daily_blog/schema.py`.

Both authors receive the same bounded evidence packet through separate configured command routes.
Each result must satisfy structure, front matter, and paragraph-level evidence references before the
referee sees it anonymously. The referee can select `A`, `B`, or `NONE`. `NONE`, route failure, or
candidate rejection produces a deterministic provisional work log, so complete evidence remains
publishable without trusting unvalidated model output.

The v2 editorial contract also validates the visible house style: one compact opening realization,
350-650 narrative words, two to four thematic sections, and final evidence-cited coverage for every
active repository. Role commands are transport-only. The checked-in Hermes routes read the
repository-owned prompt from standard input with profile rules disabled, so profile skills, memory,
and saved sessions cannot silently add a second instruction source.

The immutable producer/publisher interface contains `bundle.json`, `evidence.json`, `post.md`, and
`assets/`. The publisher repository validates every hash and provenance reference, performs a strict
staged MkDocs build, and switches the served release only after the complete proposal succeeds.

Add explicit clone sources under `daily_blog.repository_urls` when a repository has no cache yet.
Configure attribution identities, role routes, context budgets, report timezone, mirror root, and
publisher repository under `daily_blog` in `settings.yaml`.

Compare the current editorial contract with a preserved historical post without importing into the
site. First set `daily_blog.shadow_evaluation.external_model_data_sharing: true` only when the
configured author and referee destinations are approved to receive exact-Git evidence and the
referee destination is approved to receive the historical post:

```bash
source source_me.sh && python3 automation/evaluate_daily_blog_shadow.py \
  --date 2026-08-23 \
  --reference ../vosslab-daily-blog/docs/blog/posts/2026-08-23.md
```

The shadow command writes generated and reference posts, exact evidence, candidate validation, and
a typed semantic scorecard below `out/<user>/daily_blog_shadow/`. It has no publisher call. The
data-sharing setting defaults to `false`, and the evaluator reaches no model route until the setting
is explicitly enabled.

The August 22 and 23 comparisons are one-time cutover evidence, not a permanent schedule condition
or pytest contract. Keep the timer disabled while they await review. After an operator approves the
generated posts and scorecards and records their shadow IDs in the ownership record, enable the
ordinary date-driven timer. The service contains no historical-date special case.

Operations: [docs/DAILY_BLOG_OPERATIONS.md](docs/DAILY_BLOG_OPERATIONS.md)

Architecture: [docs/CODE_ARCHITECTURE.md](docs/CODE_ARCHITECTURE.md)

Generated paths: [docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md](docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md)

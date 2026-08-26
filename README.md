# Vosslab GitHub content pipeline

Generates a local, user-scoped content package from GitHub activity. The current executable
pipeline remains the broad GitHub-content pipeline.

The proposed factual daily-blog replacement is tracked in:
[docs/active_plans/DAILY_GITHUB_BLOG_REVIVAL_PLAN.md](docs/active_plans/DAILY_GITHUB_BLOG_REVIVAL_PLAN.md)

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
- `out/<user>/daily_site/`: deterministic private static archive built only from M2/M3 daily artifacts.

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

## Daily-blog revival

The M2 evidence acquisition command and independent M3 Hermes authoring path are separate from the
broad local-LLM pipeline. M2 accepts one explicit local calendar date, retains raw GitHub commit
provenance, classifies each record as `confirmed`, `ambiguous`, or `excluded`, and writes a
date-scoped evidence contract. M3 accepts only a complete, publication-eligible M2 run and invokes
the current active Hermes profile through its installed `daily-github-blogger` skill, without a
project model or provider override. M4 builds and manually serves only promoted M3 posts on one
configured private LAN address; scheduling remains disabled.

Use `github.identity_login` for the GitHub login to confirm and optionally add exact
`github.allowed_emails`. `github.timezone` must be an IANA timezone. A direct login or allowed-email
match is confirmed unless a co-author trailer makes the record ambiguous; only confirmed records
enter `claims.json`.

Live collection requires one or more explicit repositories:

```bash
source source_me.sh && python3 pipeline/daily_github_evidence.py \
  --date 2026-08-19 --repo vosslab/example --settings settings.yaml
```

Offline synthetic-input runs use the same durable contract and can set `--collected-at`
for byte-stable evidence. An input file is either a JSON record list or an object containing `records`
and optional `collection` metadata; every record supplies `repo_full_name`, `sha`, and GitHub's commit
payload fields. The E2E runners create their minimal input inside their own temporary run directory;
the repository carries no checked-in daily-blog fixture corpus.

```bash
source source_me.sh && python3 pipeline/daily_github_evidence.py \
  --date 2026-08-19 --input /path/to/owned-records.json \
  --collected-at 2026-08-20T00:00:00Z --output-root out/smoke
```

The command writes `raw_commits.json`, `claims.json`, and `run_manifest.json` below
`out/<user>/daily/YYYY-MM-DD/`; see
[docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md](docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md). A later
publication stage must require `run_manifest.json` `publication.eligible: true`. Complete empty
collections are eligible for a no-activity post, while partial or rate-limited manifests are not.

Author and promote a complete M2 run with Hermes:

```bash
source source_me.sh && python3 pipeline/daily_github_blog.py --date 2026-08-19
```

The normal M3 path requires the `hermes` CLI on `PATH`, the active Hermes profile to expose the
`daily-github-blogger` skill, and Linux `bwrap` for the required write-confined author sandbox. It
runs through the active profile's configured route with no project model or provider override. Hosts
without `bwrap` fail closed; use the deterministic synthetic author mode until an equivalent
capability sandbox is available. The normal path writes `author_prompt.txt`,
`agent_authoring_result.json`, `post_draft.md`, and `agent_generation_manifest.json` in the daily run
directory. The manifest must map each prose paragraph to confirmed claim IDs and matching SHAs. The
deterministic validator verifies M2 date/timezone consistency, every declared claim/SHA pair, and each
declared GitHub commit permalink before it promotes `post-YYYY-MM-DD.md`. Invalid drafts remain in
place and their report is retained at `validation_failures/validation_report.json`; they never replace
a promoted post.

Use the deterministic offline author mode for synthetic-input and CLI round trips. It makes no Hermes, model,
or network call:

```bash
source source_me.sh && python3 pipeline/daily_github_blog.py \
  --date 2026-08-19 --run-dir out/smoke/vosslab/daily/2026-08-19 --dry-run
```

The normal author invocation uses the installed `daily-github-blogger` Hermes skill and an equivalent
active-profile command of the form `hermes chat --in <repo> --skills daily-github-blogger --query-file
<prompt> --quiet`. It deliberately does not pass `--model` or `--provider`.

### Private static archive

Build the M4 archive only after M3 has validated and promoted one or more posts. `post_draft.md` and
an unvalidated generation manifest are never M4 publication inputs:

```bash
source source_me.sh && python3 pipeline/daily_github_site.py --settings settings.yaml
```

The generated `out/<user>/daily_site/` archive is newest-first and includes direct date navigation,
`status.html`, source-date/collection/commit/repository visibility, and clear markers for published,
incomplete, validation-failed, and complete-but-unpublished runs. It reads local artifacts only.

Start the local server only after selecting a configured `daily_site.bind_address` that belongs to the
host's private LAN interface:

```bash
source source_me.sh && python3 pipeline/daily_github_site_server.py --settings settings.yaml
```

The server refuses wildcard, loopback, public, unassigned, and privileged bind configurations before
listening. It writes query-free access records to `out/logs/daily_github_site/access.log`. See
[docs/DAILY_GITHUB_SITE_OPERATIONS.md](docs/DAILY_GITHUB_SITE_OPERATIONS.md) for address inspection,
HTTP smoke, recovery, and rollback steps. M4 does not install a service or schedule.

Plan: [docs/active_plans/DAILY_GITHUB_BLOG_REVIVAL_PLAN.md](docs/active_plans/DAILY_GITHUB_BLOG_REVIVAL_PLAN.md)

# Usage

This repository has two command routes: a general GitHub-to-content runner for local
drafts, and a date-owned daily-publication command that imports one evidence-bound
post into the local daily-blog site.

Load the repository environment before Python commands:

```bash
source source_me.sh
```

## General content pipeline

Use the established runner when you want local drafts rather than a sealed,
reader-visible daily publication:

```bash
source source_me.sh && python3 automation/run_local_pipeline.py --last-day
source source_me.sh && python3 automation/run_local_pipeline.py --last-week
```

- `--last-day`, `--last-week`, and `--last-month` select a one-, seven-, or
  30-day GitHub activity window; the first is the default.
- `--no-api-calls` skips fetching and requires a cached `github_data_*.jsonl` input.
- `--no-continue` regenerates cached outlines and drafts; `--depth 1` through
  `--depth 4` selects the LLM generation depth.
- `--settings PATH`, `--max-retries COUNT`, and `--retry-wait-seconds SECONDS`
  override the documented runner defaults.

The runner writes user-scoped artifacts under `output-pipeline/<github_username>/`, including
the fetched JSONL, `blog_post_*.md`, `bluesky_post-*.txt`, podcast text, and any
generated MP3 files. It stops after fetch when the selected window has no commits.

## Daily publication

The root command is the public daily-blog interface:

```bash
./make_blog.py --yesterday
./make_blog.py --date 2026-08-21
```

`report_date` is the sole publication identity. A bundle digest proves the integrity
of the selected artifact; it does not create a second version of that date.

## Date and replacement

- `-Y` and `--yesterday` select the prior completed date in the configured report timezone.
  They are for the systemd run and automatically replace an occupied date without prompting.
- `-d DATE` and `--date DATE` select one explicit date. The command accepts canonical
  `YYYY-MM-DD` and unambiguous `YYYY-DD-MM`, then uses canonical ISO form.
- An occupied interactive explicit date asks `Overwrite YYYY-MM-DD? [N/y]:`. Only exact
  lowercase `y` replaces it; every other response leaves the existing publication unchanged.
- `-y` and `--yes` authorize replacement for an occupied explicit `--date` without prompting.
  They cannot accompany `--yesterday`, because that path already replaces automatically.

The scheduled service runs `./make_blog.py --yesterday` at 04:00 America/Chicago.
Systemd owns scheduling; Hermes executes configured editorial model routes inside a
publication run. The systemd assets and operational setup are in
[`DAILY_BLOG_OPERATIONS.md`](DAILY_BLOG_OPERATIONS.md).

## Controlled verification

Run the retained daily-publication E2E when verifying the whole public path without
external dependencies:

```bash
source source_me.sh && python3 tests/e2e/e2e_daily_publication.py
```

The controlled path injects deterministic evidence and route responses into disposable
producer and publisher roots. It verifies initial publication, same-date replacement,
and preservation of imported work after an injected page-verification fault. It is the
required unattended no-egress verification path; a live Hermes publication is optional
corroboration, not a test prerequisite or a claim about synthetic prose quality.

## Inputs and outputs

- Live input comes from the configured repository roster, exact Git activity, and bounded
  source projections. The model sees the deterministic evidence packet through an isolated route.
- The producer writes date-owned artifacts below
	`output-pipeline/<owner>/daily_blog/<report_date>/`. Working state and the sealed bundle remain while a run is
	incomplete; verified success retains `runlog-<report_date>.jsonl` and `summary.jsonl`.
- The sealed bundle contains the validated selected post, its artifact identity, evidence,
  repository roster, editorial projection, prompt-contract binding, activation receipt, and source-
  safety policy identity. Its `publication_surface.json` is the survivor-scoped authority for the
  accepted evidence IDs, repository coverage, and image paths. Candidate and referee deliberation
  remains producer-owned run history.
- After producer validation, the producer sends the immutable bundle snapshot to the sibling
  renderer on standard input and verifies delivery; the renderer does not consume a producer
  filesystem path or independently admit editorial content.
- The renderer keeps the installed Markdown at `docs/blog/posts/<report_date>.md`, selected images
  in the adjacent `docs/blog/posts/<report_date>/` directory, and the built dated release. The
  producer's `import-receipt.v3` binds those installed bytes and the verified dated page directly.

The current handoff is `vosslab.daily-blog.bundle.v9`. Publication admission and source policy are
producer responsibilities. The sibling repository places the supplied Markdown and assets at
confined destinations and lets MkDocs determine renderability. See
[`DAILY_BLOG_OPERATIONS.md`](DAILY_BLOG_OPERATIONS.md) for the complete producer-to-publisher
contract.

## Terminal results

Ordinary partial editorial failures may produce a completed but `degraded` run when an
eligible whole post remains. A run with no eligible post, unavailable evidence, invalid
configuration, or an implementation defect records a typed pipeline fault; the command
returns a nonzero status and emits its bounded JSON diagnosis on standard error.

For operation and recovery details, read
[`DAILY_BLOG_OPERATIONS.md`](DAILY_BLOG_OPERATIONS.md).

## Known gaps

- TODO: record optional live-route corroboration separately from controlled E2E evidence.

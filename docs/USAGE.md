# Usage

This repository collects evidence, runs the daily editorial stages, and imports one
evidence-bound post for a date into the local daily-blog site.

Load the repository environment before Python commands:

```bash
source source_me.sh
```

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
publication run.

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
  `out/<owner>/daily_blog/<report_date>/`, including `runs/<run_id>/run_state.json`,
  `summary.jsonl`, `post.md`, and `publication/bundle.json`.
- The sealed bundle contains the validated selected post, its artifact identity, evidence,
  repository roster, editorial projection, prompt-contract binding, activation receipt, and the
  versioned source-safety policy identity.
  Candidate and referee deliberation remains producer-owned run history. After descriptor
  validation, the producer sends the immutable bundle snapshot to the sibling importer on standard
  input; the importer does not consume a producer filesystem path.
- The local publisher records the imported date in
  `data/publications/<report_date>.json` as `vosslab.daily-blog.publication.v5`, retains its sealed
  bundle archive, and records the canonical reader-body digest. The producer's
  `import-receipt.v2` binds that record, installed post, and verified dated page.

The current handoff is `vosslab.daily-blog.bundle.v8`. A candidate with unsafe reader-visible
Markdown is ineligible before publication: links are limited to GitHub HTTPS targets or declared
screenshots, while active raw HTML and ambiguous or disguised active constructs are rejected. The
sealed identity is `publication_source_safety.v1` with an executable 35-case corpus and SHA-256
`d50166736d79be7f7715cc0f7585fac71dfb2aecc1c631b10e01aeca2fb63c6b`. The publisher repeats this
policy check using that identity. A cached bundle from a prior schema or policy is rebuilt; it is
not upgraded in place. A historical publication-v3 record can only be inspected or replaced as an
occupied date, not created by this command.

## Terminal results

Ordinary partial editorial failures may produce a completed but `degraded` run when an
eligible whole post remains. A run with no eligible post, unavailable evidence, invalid
configuration, or an implementation defect records a typed pipeline fault; the command
returns a nonzero status and emits its bounded JSON diagnosis on standard error.

For operation and recovery details, read
[`DAILY_BLOG_OPERATIONS.md`](DAILY_BLOG_OPERATIONS.md).

## Known gaps

- TODO: record optional live-route corroboration separately from controlled E2E evidence.

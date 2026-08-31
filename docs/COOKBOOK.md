# Cookbook

Use these small operator recipes to inspect and exercise the current daily-blog workflow without
duplicating the complete procedures in [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).
Commands run from the repository root and use the repository environment.

## Check local contracts

Run the permanent, offline checks that protect the configuration-to-publication and advisory-report
boundaries. These tests do not contact a model, refresh a mirror, or publish a post.

```bash
source source_me.sh && python3 -m pytest \
  tests/test_pipeline_settings.py \
  tests/test_daily_blog_contract_integration.py \
  tests/test_daily_blog_publication_validation.py \
  tests/test_daily_blog_reliability_report.py
```

The test result is regression evidence, not a prerequisite for a normal publication. Prompt prose
remains a separately governed editorial artifact.

## Exercise publication safely

The controlled E2E creates a disposable producer, mirrors, and publisher. It runs the public
publication boundary, verifies a same-date replacement, and makes no model or network request.

```bash
source source_me.sh && python3 tests/e2e/e2e_daily_publication.py
```

This is the permanent no-egress publication check. It proves publication integrity and recovery
behavior with deterministic fixture content; it does not claim that fixture prose has live editorial
quality.

## Make one daily post

Use the repository-root command for the active date-owned publication workflow.

```bash
source source_me.sh && python3 make_blog.py --yesterday
source source_me.sh && python3 make_blog.py --date 2026-08-21
source source_me.sh && python3 make_blog.py --date 2026-08-21 --yes
```

`--yesterday` selects the preceding date in the configured report timezone. `--date` uses canonical
`YYYY-MM-DD` and also accepts an unambiguous `YYYY-DD-MM` input. The command selects exactly one
report date and runs through the repository-local Python 3.12 environment. `report_date` is the sole
publication identity. `--yesterday` and explicit `--yes` authorize same-date replacement; an
explicit date without `--yes` asks before replacing it.

This normal route may refresh mirrors, invoke the configured model routes, and import the selected
post. It is optional corroboration of the controlled no-egress path, not a completion dependency.

## Inspect run evidence

Replace `OWNER`, `YYYY-MM-DD`, and `RUN_ID` with values from the completed run. Read the bounded
run record and event log before opening larger artifacts.

```bash
source source_me.sh && python3 -m json.tool \
  out/OWNER/daily_blog/YYYY-MM-DD/runs/RUN_ID/run_state.json
sed -n '1,160p' out/OWNER/daily_blog/YYYY-MM-DD/runs/RUN_ID/events.jsonl
source source_me.sh && python3 -m json.tool \
  out/OWNER/daily_blog/YYYY-MM-DD/runs/RUN_ID/publication_bundle.json
```

Completed runs distinguish editorial degradation, typed pipeline faults, and incomplete operational
failures. Do not edit run artifacts while diagnosing a result.

## Read the reliability report

The advisory reporter aggregates only the date-level terminal-summary journal. It keeps raw counts
and shows `n/a` when a rate has no observed population.

```bash
source source_me.sh && python3 automation/report_blog_reliability.py \
  --owner OWNER \
  --report-date YYYY-MM-DD
```

Add `--json` for a stable machine-readable representation. A missing, malformed, or unsafe summary
returns a bounded input error and does not inspect detailed run artifacts.

## Verify the published bundle

Inspect the stable date-owned publication after a successful import. The manifest digest proves the
complete bundle's integrity; it is not a version or an alternate publication identity.

```bash
source source_me.sh && python3 -m json.tool \
  out/OWNER/daily_blog/YYYY-MM-DD/publication/bundle.json
source source_me.sh && python3 -m json.tool \
  out/OWNER/daily_blog/YYYY-MM-DD/publication/evidence.json
source source_me.sh && python3 -m json.tool \
  out/OWNER/daily_blog/YYYY-MM-DD/publication/editorial_projection.json
source source_me.sh && python3 -m json.tool \
  out/OWNER/daily_blog/YYYY-MM-DD/publication/publication_surface.json
sed -n '1,220p' out/OWNER/daily_blog/YYYY-MM-DD/publication/post.md
```

The producer bundle binds the selected whole post, evidence, roster, survivor surface, and editorial
projection. The surface owns admitted evidence IDs, repository coverage, images, and assets. The
publisher's reader-visible page verification is recorded with the date's publication receipt; see
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md) for that producer-to-publisher boundary.

## Diagnose cache and resume

Rerun the same date through `make_blog.py` only after reading its terminal summary and run state.
Matching validated inputs can reuse activity, evidence, bounded editorial contexts, and successful
route work; a changed input misses cache rather than reusing unrelated work. Failed route results remain
retryable, and an unsafe or mismatched cache entry is a pipeline fault.

Cache and run records are audit artifacts. Preserve them during diagnosis; the retention boundary is
defined in [OUT_DIRECTORY_ORGANIZATION_SPEC.md](OUT_DIRECTORY_ORGANIZATION_SPEC.md).

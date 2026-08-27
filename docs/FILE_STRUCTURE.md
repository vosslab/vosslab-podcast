# File structure

## Daily publication files

```text
automation/
  evaluate_daily_blog_shadow.py      non-publishing historical comparison
  publish_daily_blog.py              one public date-driven command
deploy/
  vosslab-daily-publication.service  complete producer/import job
  vosslab-daily-publication.timer    single daily schedule
pipeline/
  daily_blog/
    activity.py                      calendar-day Git activity location
    bundles.py                       immutable publication bundle writer
    candidates.py                    post validation and provisional renderer
    config.py                        settings and role-route contract
    editorial.py                     two authors and anonymous referee
    evaluation.py                    historical shadow scorecards
    evidence.py                      exact-object evidence providers and assembler
    io_utils.py                      canonical hashes and atomic file writes
    locks.py                         file locks and hash-verified phase cache
    mirrors.py                       durable repository cache manager
    orchestrator.py                  eight explicit phase boundaries and workflow owner
    publisher.py                     cross-repository importer invocation
    routes.py                        isolated stdin subprocess routes
    run_state.py                     run record and artifacts
    schema.py                        typed versioned contracts
  prompts/
    daily_blog_author_v2.txt
    daily_blog_referee_v2.txt
    daily_blog_referee_repair_v2.txt
    daily_blog_rubric_v2.md
    daily_blog_shadow_evaluator_v1.txt
    daily_blog_shadow_evaluator_repair_v1.txt
tests/
  test_daily_blog_bundle.py
  test_daily_blog_editorial.py
  test_daily_blog_evaluation.py
  test_daily_blog_evidence.py
  test_daily_blog_mirrors.py
  e2e/
    e2e_daily_blog_evidence_git.py    exact-object evidence with temporary Git
    e2e_daily_blog_mirror_refresh.py  durable cache identity with temporary Git
    e2e_daily_publication.py          producer-to-publisher strict-build flow
    run_all.sh
```

## Runtime layout

```text
/home/vosslab/repo-mirrors/vosslab/
  REPOSITORY/                       physical Git cache
  .locks/                           per-cache refresh locks
out/vosslab/
  daily_blog/YYYY-MM-DD/RUN_ID/     immutable bundle
  daily_blog/YYYY-MM-DD/latest.json stable newest-complete pointer
  daily_blog_runs/YYYY-MM-DD/RUN_ID typed run state and artifacts
  daily_blog_cache/                 hash-verified reusable phase outputs
  daily_blog_shadow/YYYY-MM-DD/     immutable non-publishing comparisons
  daily_blog_shadow_locks/          per-date evaluation locks
```

The mirror cache is shared by manual and scheduled runs. Default generated paths remain below the
configured GitHub username namespace.

Evidence v2 stores exact commit-to-parent ranges and attributed branch-tip snapshots. Reusable phase
artifacts carry their input and output hashes; later runs record reuse without changing the original
bundle or prior run directory.

## Cross-repository interface

One bundle directory contains:

```text
bundle.json
evidence.json
post.md
assets/
```

`bundle.json` identifies every other artifact by schema, path, and hash. No producer module imports
publisher Python code or edits publisher content directly. `pipeline/daily_blog/publisher.py` calls
the publisher's command-line importer with the bundle directory.

## Other repository areas

- `automation/run_local_pipeline.py`: established multi-output GitHub content runner.
- `pipeline/*.py`: executable established pipeline stages.
- `pipeline/podlib/`: shared established pipeline library modules.
- `settings.yaml`: GitHub, LLM, text-to-speech, and daily publication configuration.
- `docs/HUMAN_GUIDANCE.md`: durable local preferences for model-facing instructions.
- `docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md`: authoritative generated-path contract.
- `docs/DAILY_BLOG_OPERATIONS.md`: scheduling, inspection, and recovery runbook.
- `docs/DAILY_BLOG_OWNERSHIP_CUTOVER.md`: final producer/publisher ownership and retirement record.
- `docs/archive/`: pre-cutover revival plan and branch scorecard retained for history.
- `tests/`: unit, hygiene, and end-to-end verification.

## Change placement

- Put daily producer behavior under `pipeline/daily_blog/`.
- Put versioned daily editorial text under `pipeline/prompts/`.
- Put only the public command wrapper under `automation/`.
- Put user-service definitions under `deploy/`.
- Update `schema.py` and the publisher importer together for contract changes.
- Add focused unit coverage beside the existing daily-blog tests and cross-repository behavior to
  `tests/e2e/e2e_daily_publication.py`.

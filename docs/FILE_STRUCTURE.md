# File structure

## Top-level layout

```text
AGENTS.md                  repository workflow and runtime rules
README.md                  product overview and onboarding routes
make_blog.py               public daily-publication command
automation/                command implementations and operational helpers
deploy/                    systemd service and timer definitions
docs/                      durable documentation, plans, and reports
pipeline/                  reusable content and daily-blog modules
tests/                     offline unit, hygiene, and direct E2E checks
settings.yaml              local GitHub, model-route, and daily-blog settings
source_me.sh               Bash Python 3.12 environment setup
```

## Daily-blog modules

```text
pipeline/daily_blog/
  acquisition_workflow.py           roster, mirror, activity, evidence, projection ownership
  activity.py                       report-day Git activity location
  agents.py                         bounded parallel editorial route execution
  artifacts.py                      typed editorial artifact identities
  candidates.py                     complete-post eligibility validation
  config.py                         settings and role-route configuration
  contracts.py                      generic prompt contract dataclasses and validators
  daily_outline_workflow.py         Stage-5 ranking, outline, review, and promotion
  editorial.py                      prompt rendering and editorial packet preparation
  evidence.py                       exact-object evidence collection
  final_synthesis_config.py         Stage-7 settings contract
  final_synthesis_prompts.py        Stage-7 prompt resource loader
  locks.py                          date lock and resumable phase cache
  mirrors.py                        owner-qualified Git mirror refresh and inspection
  observability.py                  bounded lifecycle events and terminal summaries
  orchestrator.py                   lifecycle composition only
  prompt_registry.py                sole active contract, policy, and resource registry
  publication_contract.py           bundle-v7 identity and manifest writer
  publication_finalization.py       selected-post bundle/import/page owner
  publication_state.py              local publication-state validation
  publication_storage.py            descriptor-owned no-follow bundle storage
  publication_validation.py         Stage-8 publication validation
  publisher.py                      publisher CLI and receipt validation boundary
  recovery.py                       typed editorial recovery and fault digest
  replication.py                    independent review and promotion primitives
  repositories.py                   authoritative owner-roster acquisition
  repository_editorial_workflow.py  Stage-3/4 repository editorial coordination
  repository_outline_workflow.py    Stage-3 outline candidates and review
  repository_story_workflow.py      Stage-4 story candidates and review
  roster_snapshots.py               immutable verified roster storage
  route_cache.py                    route-result cache serialization
  run_contracts.py                  v11 run record and incumbent transitions
  run_state.py                      RunStore persistence and recovery
  stage6.py                         Stage-6 complete-post generation
  stage7.py                         Stage-7 incumbent-preserving synthesis
  stage_recovery_coordinator.py     serial typed recovery-state coordination
```

[`pipeline/prompts/`](../pipeline/prompts/) stores versioned prompt resources. The active contract
and its immutable activation receipt select resources through
[`pipeline/daily_blog/prompt_registry.py`](../pipeline/daily_blog/prompt_registry.py), rather than
through experiment or calibration executables.

[`pipeline/podlib/`](../pipeline/podlib/) contains shared support for the established content path.
Its runtime credential helper is the GitHub credential boundary; credentials do not enter evidence,
run state, or publication bundles.

## Command and deployment files

```text
automation/
  capture_daily_blog_repository_roster.py  roster snapshot helper
  preflight_daily_blog_producer.py         producer configuration preflight
  publish_daily_blog.py                    daily-publication command implementation
  report_blog_reliability.py               bounded reliability summary report
  run_local_pipeline.py                    established GitHub-to-content runner
deploy/
  ...                                      systemd service and timer assets
```

`make_blog.py --yesterday` is the scheduled public entry point. It selects yesterday in the
configured timezone and automatically replaces an existing result for that date in unattended use.
An interactive request retains its explicit overwrite confirmation behavior.

## Generated daily-blog data

The configured `output_root` and output owner place generated data below `out/<owner>/` by default.
The exact paths are configuration-dependent; durable records use logical paths where appropriate.

```text
out/<owner>/
+- daily_blog/YYYY-MM-DD/
|  +- summary.jsonl                       bounded terminal receipts for this date
|  +- post.md                             trusted selected-post handoff during finalization
|  +- runs/RUN_ID/
|  |  +- run_state.json                   authoritative typed run record
|  |  +- events.jsonl                     bounded lifecycle diagnostics
|  |  `- stage-owned JSON artifacts       including recovery journals while unresolved
|  `- publication/                        atomically promoted sealed bundle
|     +- bundle.json
|     +- evidence.json
|     +- repository_roster.json
|     +- editorial_projection.json
|     +- post.md
|     `- assets/                          manifest-declared evidence assets only
+- daily_blog_cache/
+- daily_blog_locks/
`- daily_blog_repository_rosters/ROSTER_ID/
   +- repository_roster.json
   `- manifest.json
```

The current handoff manifest is `vosslab.daily-blog.bundle.v7`. It contains the validated
Stage-8 selected post and `best_artifact_id`, with evidence, roster, projection, assets, prompt and
activation bindings, and integrity digest. Candidate and referee records remain run-owned editorial
history, not publisher inputs. The publisher records `publication-v4` state after import.

## Tests

```text
tests/
  test_daily_blog_*.py                    offline behavior and contract coverage
  e2e/
    e2e_daily_publication.py              controlled producer-to-publisher publication behavior
    e2e_daily_blog_evidence_git.py        Git evidence infrastructure boundary
    e2e_daily_blog_mirror_refresh.py      mirror-refresh infrastructure boundary
    e2e_daily_blog_new_repository.py      new-repository evidence boundary
    e2e_make_blog.py                      public command boundary
    run_all.sh                            aggregate direct-E2E runner
```

The controlled publication E2E uses disposable local roots and deterministic local responses. It
does not call a model provider or the network. Other E2Es retain their distinct source and command
scope; they are not alternate editorial-promotion suites.

## Documentation map

- [`README.md`](../README.md): reader-oriented overview and first routes.
- [`INSTALL.md`](INSTALL.md): prerequisites and local setup.
- [`USAGE.md`](USAGE.md): supported commands.
- [`DAILY_BLOG_OPERATIONS.md`](DAILY_BLOG_OPERATIONS.md): publishing, schedule, recovery, and
  investigation.
- [`CODE_ARCHITECTURE.md`](CODE_ARCHITECTURE.md): component ownership and trust boundaries.
- [`FILE_FORMATS.md`](FILE_FORMATS.md): durable formats and publication schemas.
- [`OUT_DIRECTORY_ORGANIZATION_SPEC.md`](OUT_DIRECTORY_ORGANIZATION_SPEC.md): output ownership.
- [`PYTEST_STYLE.md`](PYTEST_STYLE.md): permanent-test policy and commands.
- [`active_plans/`](active_plans/): in-flight plans, reports, decisions, and workstreams.

## Where to add work

- Add an evidence source beside [`pipeline/daily_blog/evidence.py`](../pipeline/daily_blog/evidence.py)
  and extend the typed schema/provenance boundary.
- Add a stage mechanism beside its phase owner, preserving independent candidates and typed
  promotion rather than extending the orchestrator.
- Add prompt resources in [`pipeline/prompts/`](../pipeline/prompts/) and register identity changes
  in `prompt_registry.py`; prompt prose requires separate editorial approval.
- Add permanent behavior tests under [`tests/`](../tests/) only when they meet
  [`PYTEST_STYLE.md`](PYTEST_STYLE.md); keep one-time demonstration evidence out of the suite.
- Add operational documentation under [`docs/`](.) with relative links and ASCII Markdown.

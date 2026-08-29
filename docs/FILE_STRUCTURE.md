# File structure

## Top-level layout

```text
AGENTS.md                 repository workflow and Python runtime rules
README.md                 product overview and first commands
make_blog.py              root daily-publication command
automation/               executable workflow entry points
deploy/                   systemd service and timer definitions
docs/                     durable documentation and active plans
pipeline/                 reusable content and daily-blog modules
tests/                    unit, hygiene, and direct E2E checks
settings.yaml             local GitHub, model, and daily-blog configuration
source_me.sh              Bash environment activation
```

## Daily-blog modules

```text
automation/
  attest_daily_blog_prompt_experiment.py  stage-2 capture/calibration attestation CLI
  calibrate_daily_blog_rubric.py          historical rubric calibration CLI
  capture_daily_blog_experiment_fixture.py sealed fixture-capture CLI
  capture_daily_blog_repository_roster.py immutable roster-snapshot CLI
  experiment_daily_blog_prompts.py        stage-1 non-publishing experiment CLI
  publish_daily_blog.py                   shared active daily-publication implementation
pipeline/daily_blog/
  activity.py                             report-day Git activity location
  bundles.py                              date-owned producer bundle writer
  candidates.py                           final-post and evidence validation
  config.py                               settings, output owner, and role routes
  contracts.py                            registered editorial and validation contracts
  editorial.py                            two authors and anonymous referee
  evidence.py                             exact-object evidence collection
  experiment_acceptance.py                deterministic experiment acceptance policy
  experiment_attestation.py               stage-2 immutable attestation owner
  experiment_capture_artifacts.py         sealed fixture and capture verifier
  experiment_output.py                    stage-1 private output transaction
  io_utils.py                             UTC timestamps, canonical JSON, and hash helpers
  private_artifacts.py                    descriptor-pinned private artifact I/O
  projection.py                           bounded editorial projection
  publisher.py                            publisher CLI boundary
  repositories.py                         authoritative public owner-roster acquisition
  repository_contracts.py                 typed repository and lifecycle contracts
  roster_snapshots.py                     immutable verified roster storage
  rubric_calibration.py                   calibration contract and execution
  rubric_calibration_artifacts.py         historical-post and calibration-artifact I/O
  mirrors.py                              owner-qualified Git mirror refresh and inspection
  orchestrator.py                         date-owned publication phase coordinator
  run_state.py                            durable per-run state and event records
  run_contracts.py                        typed run-state schema and legal phase contracts
  locks.py                                per-date ownership and phase-value cache
  schema.py                               typed evidence, projection, and bundle records
```

`pipeline/prompts/` contains versioned author, referee, rubric, calibration, and voice-example
resources. [`pipeline/podlib/`](../pipeline/podlib/) holds shared modules for the established
GitHub-to-content path, including `runtime_credentials.py`, which supplies the single runtime-only
GitHub credential boundary.

## Experiment artifact layout

The configured `output_root` and GitHub `output_owner` create private leaves below
`out/<owner>/` by default:

```text
out/<owner>/
+- daily_blog_experiment_fixtures_v2/
|  `- YYYY-MM-DD--FIXTURE_ID/
|     +- evidence.json
|     +- editorial_projection.json
|     `- manifest.json
+- daily_blog_experiments/
|  `- prompt-experiment-.../
|     +- <fixture>-<arm>-<repetition>/
|     |  +- candidate-0.md
|     |  +- candidate-1.md
|     |  `- selected.md
|     +- manifest.json
|     `- report.json
+- daily_blog_rubric_calibrations/
|  `- rubric-calibration-.../
|     +- manifest.json
|     `- report.json
`- daily_blog_experiment_attestations/
   `- prompt-experiment-attestation-<sha256>/
      +- manifest.json
      `- report.json
```

[`automation/experiment_daily_blog_prompts.py`](../automation/experiment_daily_blog_prompts.py)
owns the second root. It receives two approved fixture directories and writes one immutable capture
with `activation_status: pending_calibration_attestation` and `non_publishing: true`.
[`pipeline/daily_blog/experiment_capture_artifacts.py`](../pipeline/daily_blog/experiment_capture_artifacts.py)
is the consuming verifier for both fixture and capture records.

[`automation/attest_daily_blog_prompt_experiment.py`](../automation/attest_daily_blog_prompt_experiment.py)
owns the user-facing stage-2 command. It receives absolute direct-child paths to the capture and a
passing live calibration. [`pipeline/daily_blog/experiment_attestation.py`](../pipeline/daily_blog/experiment_attestation.py)
writes the final root only after it revalidates both sources and recomputes the acceptance result.
The attestation remains `non_publishing: true` regardless of whether its result is ready for human
review.

## Publication and supporting output

```text
/home/vosslab/repo-mirrors/
+- OWNER/REPOSITORY/                 physical Git mirror
`- .locks/                           per-mirror refresh locks
out/<owner>/
+- daily_blog/YYYY-MM-DD/publication/ date-owned producer bundle
+- daily_blog_runs/YYYY-MM-DD/RUN_ID/ run state, events, and phase artifacts
+- daily_blog_cache/                 hash-verified reusable phase values
+- daily_blog_locks/YYYY-MM-DD.lock  complete workflow ownership for one date
+- daily_blog_repository_rosters/ROSTER_ID/
|  +- manifest.json
|  `- repository_roster.json
`- daily_blog_shadow/YYYY-MM-DD/     non-publishing historical comparison
```

The root daily-blog command is [`make_blog.py`](../make_blog.py). The active publication path uses
[`pipeline/daily_blog/publisher.py`](../pipeline/daily_blog/publisher.py) to call the publisher's
CLI importer. It does not share Python imports with the publisher checkout. The experiment roots
are separate from `daily_blog/` and cannot become publication input.

## Tests and documentation

```text
tests/
+- test_daily_blog_prompt_experiment.py       stage-1 capture behavior
+- test_daily_blog_experiment_attestation.py  stage-2 attestation behavior
+- test_daily_blog_rubric_calibration.py      live-calibration contract
`- e2e/
   +- e2e_daily_blog_evidence_git.py          exact-object evidence with temporary Git
   +- e2e_daily_blog_mirror_refresh.py        durable mirror identity with temporary Git
   +- e2e_daily_blog_new_repository.py        first-day repository-story regression
   +- e2e_daily_publication.py                producer-to-publisher publication flow
   `- e2e_make_blog.py                        root-command executable boundary
docs/
+- CODE_ARCHITECTURE.md               ownership and data flows
+- FILE_STRUCTURE.md                  repository and artifact map
+- DAILY_BLOG_OPERATIONS.md           operator procedure and recovery
+- OUT_DIRECTORY_ORGANIZATION_SPEC.md generated-output contract
`- active_plans/reports/              experimental status reports
```

The three fast prompt-experiment modules verify deterministic contracts with local data. The direct
E2E tier retains only whole-system local Git, publication, and executable-boundary checks. The
approved capture, historical calibration, and route-free attestation commands are one-time
operational evidence procedures; they are documented in
[`CODE_ARCHITECTURE.md`](CODE_ARCHITECTURE.md) and
[`DAILY_BLOG_OPERATIONS.md`](DAILY_BLOG_OPERATIONS.md), not represented by mock-driven permanent
E2E runners.

## Where to add work

- Add executable wrappers under [`automation/`](../automation/).
- Add reusable daily-blog behavior under [`pipeline/daily_blog/`](../pipeline/daily_blog/).
- Add versioned model-facing resources under [`pipeline/prompts/`](../pipeline/prompts/).
- Add fast deterministic coverage under [`tests/`](../tests/) and direct workflow checks under
  [`tests/e2e/`](../tests/e2e/).
- Add durable architecture or runbook material under [`docs/`](./).
- Keep generated data under the configured `out/<owner>/` namespace; `out/` and `graphify-out/`
  are ignored.

# Code architecture

## Overview

This repository has two independent content paths. The established pipeline turns GitHub activity
into a blog post, social copy, podcast script, and optional audio. The daily-blog producer turns
exact Git evidence into one date-owned bundle that the separate private MkDocs publisher imports.

The active daily editorial contract is v3-historical. The v4 maker-voice work is a private,
non-publishing experiment. It supplies evidence for a later activation decision but cannot change
the active contract, create a publication bundle, invoke the importer, or publish a post.

## Major components

| Component | Ownership | Primary result |
| --- | --- | --- |
| [`automation/run_local_pipeline.py`](../automation/run_local_pipeline.py) and [`pipeline/`](../pipeline/) | Established GitHub-to-content path | User-scoped text and audio outputs |
| [`make_blog.py`](../make_blog.py) and [`automation/publish_daily_blog.py`](../automation/publish_daily_blog.py) | Active v3 date-owned daily publication command | One validated publication or an inspected existing date |
| [`pipeline/daily_blog/orchestrator.py`](../pipeline/daily_blog/orchestrator.py) | Deterministic producer workflow | Activity, evidence, projection, editorial result, and bundle |
| [`pipeline/daily_blog/repository_contracts.py`](../pipeline/daily_blog/repository_contracts.py) and [`pipeline/daily_blog/roster_snapshots.py`](../pipeline/daily_blog/roster_snapshots.py) | Repository identities, lifecycle records, and immutable owner roster | Verified repository universe |
| [`pipeline/daily_blog/evidence.py`](../pipeline/daily_blog/evidence.py) and [`pipeline/daily_blog/projection.py`](../pipeline/daily_blog/projection.py) | Exact Git evidence and bounded editorial context | Evidence packet and editorial projection |
| [`pipeline/daily_blog/editorial.py`](../pipeline/daily_blog/editorial.py) and [`pipeline/daily_blog/candidates.py`](../pipeline/daily_blog/candidates.py) | Two authors, anonymous referee, and contract validation | Validated final candidate or a blocked result |
| [`pipeline/daily_blog/bundles.py`](../pipeline/daily_blog/bundles.py) and [`pipeline/daily_blog/publisher.py`](../pipeline/daily_blog/publisher.py) | Date-owned producer/publisher interface | Sealed bundle and importer result |
| [`automation/experiment_daily_blog_prompts.py`](../automation/experiment_daily_blog_prompts.py) | Stage 1 maker-voice experiment | Immutable non-publishing capture |
| [`pipeline/daily_blog/experiment_capture_artifacts.py`](../pipeline/daily_blog/experiment_capture_artifacts.py) | Descriptor-pinned capture and fixture verification | Trusted capture inputs |
| [`automation/attest_daily_blog_prompt_experiment.py`](../automation/attest_daily_blog_prompt_experiment.py) and [`pipeline/daily_blog/experiment_attestation.py`](../pipeline/daily_blog/experiment_attestation.py) | Stage 2 deterministic acceptance join | Immutable non-publishing attestation |
| [`pipeline/daily_blog/rubric_calibration.py`](../pipeline/daily_blog/rubric_calibration.py) | Historical rubric calibration | Passing live calibration evidence |

`schema.py` owns typed evidence, projection, and bundle serialization contracts.
`run_contracts.py` owns the versioned durable run-state schema, legal phase sequence, and redacted
failure categories. `io_utils.py` owns shared UTC timestamps, canonical JSON, hashing, and atomic
file writes. `contracts.py` owns registered editorial contracts and validation policies.
`config.py` owns settings, output roots, and isolated role-route configuration.
`private_artifacts.py` owns descriptor-pinned reads and private atomic directory operations shared
by captures, calibrations, and attestations.

## Active publication flow

```text
fresh owner roster -> local mirrors -> activity -> exact Git evidence -> projection
    -> two authors -> candidate validation -> anonymous referee -> date-owned bundle
    -> publisher CLI importer -> private MkDocs release
```

`make_blog.py` selects yesterday in the configured report timezone or one explicit date. The
producer holds a per-date lock, verifies reuse by content identity, and uses
[`pipeline/daily_blog/publisher.py`](../pipeline/daily_blog/publisher.py) as its only
cross-repository interface. The producer does not import the publisher's Python code or write the
publisher's source tree directly.

The checked-in systemd service calls `./make_blog.py --yesterday`; systemd owns the schedule.
Hermes is a model-transport boundary inside the editorial phases. The active publisher accepts the
active v3 contract; v4 cannot enter this flow.

Fresh repository discovery resolves one runtime `GITHUB_TOKEN` through
[`pipeline/podlib/runtime_credentials.py`](../pipeline/podlib/runtime_credentials.py). An explicit
process value wins; otherwise the loader reads only that entry from the active Hermes dotenv. It
does not place the credential or neighboring dotenv values in the process environment, run state,
evidence packet, or publication bundle.

## Maker experiment flow

```text
approved sealed busy and quiet fixtures
    -> stage 1: author and referee experiment routes
    -> immutable capture: manifest.json + report.json, pending calibration attestation
    -> independently verified passing live historical calibration
    -> stage 2: deterministic acceptance recomputation
    -> immutable attestation: manifest.json + report.json, non_publishing: true
    -> human review and a separate activation decision
```

Stage 1 is [`automation/experiment_daily_blog_prompts.py`](../automation/experiment_daily_blog_prompts.py).
It accepts the exact reviewed busy and quiet fixture rotation, all registered arms, and at least two
repetitions. It runs the configured author and referee routes, records candidates and pairwise
comparisons, then atomically installs a capture beneath the configured private root. A complete
capture still has `activation_status: pending_calibration_attestation`; it contains no full prompts
and creates no bundle, importer request, mirror refresh, shadow evaluation, or publication.

[`pipeline/daily_blog/experiment_capture_artifacts.py`](../pipeline/daily_blog/experiment_capture_artifacts.py)
loads stage-1 artifacts only through direct, absolute, descriptor-pinned paths. It validates the
capture schema, content-addressed identity, report digest, approved fixture identities, expected
arm/repetition matrix, stored candidate bytes and hashes, and redacted non-publishing state before
an attestation can consume the capture.

Stage 2 is [`automation/attest_daily_blog_prompt_experiment.py`](../automation/attest_daily_blog_prompt_experiment.py).
It accepts a capture and a calibration artifact, with no route, model, publisher, or activation
options. [`pipeline/daily_blog/experiment_attestation.py`](../pipeline/daily_blog/experiment_attestation.py)
requires both artifacts to be direct children of their configured private roots, reloads them,
recomputes the acceptance result, and atomically installs a content-addressed attestation. It exits
0 when the result is `activation_ready`, 1 for a valid non-ready result, and 2 for invalid inputs or
artifact failure. That exit status is evidence for review, not a mechanism that activates v4.

The calibration input is separately owned by
[`pipeline/daily_blog/rubric_calibration.py`](../pipeline/daily_blog/rubric_calibration.py). A live
artifact must pass the fixed historical calibration targets and match the current historical posts,
registered rubric, and calibration resources before attestation accepts it.

## Private artifact roots

The configured output root and GitHub owner produce these private namespaces:

```text
out/<owner>/
+- daily_blog_experiment_fixtures_v2/YYYY-MM-DD--FIXTURE_ID/
|  +- evidence.json
|  +- editorial_projection.json
|  `- manifest.json
+- daily_blog_experiments/prompt-experiment-.../
|  +- candidate artifacts
|  +- manifest.json
|  `- report.json
+- daily_blog_rubric_calibrations/rubric-calibration-.../
|  +- manifest.json
|  `- report.json
`- daily_blog_experiment_attestations/prompt-experiment-attestation-<sha256>/
   +- manifest.json
   `- report.json
```

Fixtures bind evidence and projections to a verified roster. Capture, calibration, and attestation
directories are private immutable leaves. Their manifests identify content and their reports contain
the corresponding bounded evidence. Repeated creation is idempotent only when the existing
descriptor-read artifact equals the recomputed result.

## One-time approval-gated evidence

Use the repository Bash environment for all Python commands:

```bash
source source_me.sh && python3 automation/experiment_daily_blog_prompts.py \
  --busy-fixture /absolute/path/to/busy-fixture \
  --quiet-fixture /absolute/path/to/quiet-fixture \
  --repetitions 3

source source_me.sh && python3 automation/attest_daily_blog_prompt_experiment.py \
  --capture /absolute/path/to/prompt-experiment-capture \
  --calibration /absolute/path/to/passing-live-calibration
```

The stage-1 command intentionally has no `--calibration` option. It sends sealed project evidence
through the configured author and referee routes only after explicit approval. The stage-2 command
has no model-route or publication option; it joins an already completed capture to an independently
approved live calibration. Both commands produce one-time non-publishing evidence for a human
activation decision. They are operational procedures, not permanent test runners and not proof that
a local double represents live maker quality.

## Permanent test topology

Fast deterministic coverage lives in
[`tests/test_daily_blog_prompt_experiment.py`](../tests/test_daily_blog_prompt_experiment.py),
[`tests/test_daily_blog_experiment_attestation.py`](../tests/test_daily_blog_experiment_attestation.py),
and [`tests/test_daily_blog_rubric_calibration.py`](../tests/test_daily_blog_rubric_calibration.py).
The permanent direct E2E tier exercises real local Git, mirror, publication, and executable
boundaries. It deliberately excludes mock-driven prompt-capture, calibration, and attestation
lifecycle runners; their former implementations did not execute approved model routes and therefore
could not establish live prose quality.

## Extension points

- Add a daily evidence provider in `evidence.py` and define its provenance in the schema and
  publisher contract together.
- Add an experiment arm in `contracts.py`, then update the sealed arm order, capture validation,
  acceptance policy, and fixtures as one versioned experiment contract.
- Change private artifact format in its owning module and retain independent descriptor-read
  validation at every consumer boundary.
- Advance the active publication contract only after an attestation is reviewed and a separate,
  recorded decision changes the active contract. Do not treat a capture or attestation as activation.

## Known gaps

- Run the approved live routes, review the resulting non-publishing attestation, and record an
  evidence-based decision before considering any change to the active v3 contract.

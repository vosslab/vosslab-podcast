# Development guide

This guide is the practical starting point for contributors. It describes the
repository's development commands and links to the documents that own detailed
contracts.

## Start a session

Read [AGENTS.md](../AGENTS.md) and
[CODEX_CHAT_TRANSCRIPT.txt](../CODEX_CHAT_TRANSCRIPT.txt) before changing the
repository. Read the applicable canonical guidance before editing code, tests,
or documentation:

- [REPO_STYLE.md](REPO_STYLE.md) for repository-wide conventions.
- [PYTHON_STYLE.md](PYTHON_STYLE.md) for Python code and configuration rules.
- [PYTEST_STYLE.md](PYTEST_STYLE.md) and [E2E_TESTS.md](E2E_TESTS.md) for test placement.
- [MARKDOWN_STYLE.md](MARKDOWN_STYLE.md) for documentation changes.
- [HUMAN_GUIDANCE.md](HUMAN_GUIDANCE.md) before changing human-approved workflow or prompt text.

For broad codebase orientation, query the checked-in Graphify map, then verify
each conclusion in current source and tests:

```bash
graphify query "How does the daily blog assemble and publish a bundle?" --budget 1500
```

`graphify-out/` is generated and ignored. It is an orientation aid, not proof of
the current runtime behavior.

## Bootstrap Python

Run Python commands from Bash after sourcing the repository bootstrap:

```bash
source source_me.sh && python3 <script>.py
source source_me.sh && pytest tests/
```

`source_me.sh` requires a physical, repository-local `.venv` and rejects a
symbolic link or an interpreter other than Python 3.12. It places that environment
first on `PATH`, clears inherited `PYTHONPATH`, and sets the pipeline import path.
Create the required environment, then install the declared dependencies, when the
bootstrap reports that it is missing:

```bash
python3.12 -m venv .venv
source source_me.sh && pip install -r pip_requirements.txt -r pip_requirements-dev.txt
```

Dependencies are declared in [pip_requirements.txt](../pip_requirements.txt) and
[pip_requirements-dev.txt](../pip_requirements-dev.txt). Keep private settings in
the established configuration and command-line interfaces described in
[PYTHON_STYLE.md](PYTHON_STYLE.md), rather than adding them to environment variables.

## Test a change

Start with the smallest relevant fast test, then widen coverage when a change
crosses a contract or ownership boundary:

```bash
source source_me.sh && pytest tests/test_daily_blog_publication_validation.py
source source_me.sh && python3 tests/e2e/e2e_daily_publication.py
```

Fast pytest is deterministic and offline. Use inline inputs and `tmp_path` for
test-owned files; do not add network, model, real-process, or publisher calls
to permanent pytest. [PYTEST_STYLE.md](PYTEST_STYLE.md) owns the test-design
checklist and failure triage.

Direct E2Es live in `tests/e2e/` and are excluded from pytest collection. The
controlled daily-publication E2E is the durable reader-visible publication
path; it uses fixed-date, synthetic evidence and a disposable publisher root:

```bash
source source_me.sh && python3 tests/e2e/e2e_daily_publication.py
```

Run focused tests and that controlled E2E for each coherent change group. Run
the aggregate direct-E2E runner and the full fast suite once after a coordinated
migration has removed its temporary harnesses:

```bash
source source_me.sh && bash tests/e2e/run_all.sh
source source_me.sh && pytest tests/
```

The aggregate runner also covers separately-owned infrastructure E2Es. See
[E2E_TESTS.md](E2E_TESTS.md) for the separation between the fast lane, direct
E2Es, and browser E2Es.

`docs/BLOG_CONTRACT.md` is human-owned and byte-protected. The repository's
Layer-2 hygiene configuration excludes it only from the ASCII and whitespace
auto-fixers; do not edit it as part of ordinary pipeline work. Verify its
recorded SHA-256 before and after a broad hygiene-bearing run.

## Daily publication work

Read [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md) before changing the
daily-blog workflow. It owns the producer-to-publisher operational contract;
use [CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md) and
[FILE_STRUCTURE.md](FILE_STRUCTURE.md) to locate the responsible module and its
tests.

The public entry point selects exactly one report date and delegates the
date-owned workflow:

```bash
source source_me.sh && python3 make_blog.py --yesterday
source source_me.sh && python3 make_blog.py --date YYYY-MM-DD
```

`report_date` remains the sole publication identity. The workflow records
terminal date summaries, seals the selected eligible post, imports it, and
verifies the rendered page. An editorial route failure may produce a degraded
run while preserving eligible grounded work; typed pipeline faults stay visible
and publish nothing.

The production extension boundaries are deliberately narrow:

- `PublicationRuntime` supplies controlled provider overrides for repository
  loading, mirror refresh, activity location, evidence assembly, route calls,
  publisher import, and page verification.
- `DailyPublicationOrchestrator` owns the date lock and lifecycle order.
- `publication_workflow.py` owns the typed editorial-stage handoffs.
- `PublicationFinalizationCoordinator` owns bundle sealing, site import, and
  rendered-page verification.

Keep additions behind these owner boundaries rather than restoring retired
experiment, calibration, attestation, fixture-runner, or shadow-evaluation
commands. Prompt text and human approval remain outside routine implementation:
mechanically verify retained prompt identities and resources, but do not edit,
display, or approve prompt prose without the boundary in
[HUMAN_GUIDANCE.md](HUMAN_GUIDANCE.md).

For controlled no-egress publication evidence, use the permanent E2E rather
than a private runner:

```bash
source source_me.sh && python3 tests/e2e/e2e_daily_publication.py
```

It proves same-date replacement, selected-artifact preservation, structured
terminal faults, sealed-bundle integrity, and the reader-visible page without
external route egress.

## Refresh screenshots

The README screenshots come from the sibling publisher's verified local
`generated/check` site. Capture them only when that output and the sibling
repository's local Playwright installation are available:

```bash
node automation/capture_work_log_screenshots.mjs
```

The harness serves only the local static output, blocks non-local browser
requests, verifies each page heading, and updates the two managed PNGs in
`docs/screenshots/`. Inspect both images after capture. Keep the managed
`screenshots:begin` and `screenshots:end` sentinels in [README.md](../README.md)
so later captures remain idempotent.

## Maintain releases

`devel/` contains maintainer tools for changelog work, version preparation,
documentation repair, and cleanup. Start with [DEVEL_README.md](../devel/DEVEL_README.md)
and inspect a tool's help before relying on its options:

```bash
source source_me.sh && python3 devel/make_release.py --help
source source_me.sh && python3 devel/make_release.py --dry-run
```

`make_release.py` defaults to a dry run. `--write` builds release archives and
can update release documents, so use it only after reviewing the dry-run output
and release notes. The tool prints the final tag and GitHub-release commands for
a human to run.

## Record durable changes

Every code or behavior change needs a dated entry in [CHANGELOG.md](CHANGELOG.md).
After a major change, append a dated section to
[CODEX_CHAT_TRANSCRIPT.txt](../CODEX_CHAT_TRANSCRIPT.txt) with what changed,
what was tested, and the next action.

For documentation-only work, validate local links, ASCII content, and the
working-tree diff. Do not treat an older test result as current evidence.

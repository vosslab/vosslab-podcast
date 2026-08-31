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

For broad orientation, query the checked-in Graphify map and then verify every
conclusion in current source and tests. The map is generated, ignored, and can
be stale; it is an index, not runtime evidence:

```bash
graphify query "How does the daily blog assemble and publish a bundle?" --budget 1500
```

Use [CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md) and
[FILE_STRUCTURE.md](FILE_STRUCTURE.md) to find the current owner before making
a cross-module change.

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

Permanent pytest tests live directly in `tests/`. They are deterministic and
offline, use inline inputs and `tmp_path` for test-owned files, and do not make
network, model, real-process, or publisher calls. [PYTEST_STYLE.md](PYTEST_STYLE.md)
owns the complete test-design and failure-triage rules.

Direct E2Es live in `tests/e2e/` and browser E2Es in `tests/playwright/`; both
are excluded from `pytest tests/`. The controlled daily-publication E2E uses
fixed-date synthetic evidence and a disposable publisher root:

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

## Acceptance checks

One-time acceptance checks corroborate a particular migration, deployment, or
live operational run. Record their date, inputs, and result in the changelog or
transcript, but do not turn them into permanent pytest tests or recurring gates.
Examples include a real external `--yesterday` publication, a historical
capture, or a manual rendering inspection after a release.

Permanent tests instead protect durable behavior: focused offline pytest tests,
the fixed no-egress controlled publication E2E, and the aggregate direct-E2E
runner when a coordinated migration has removed its temporary harnesses. Do not
use an old passing result as evidence for a new change.

## Daily publication work

Read [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md) before changing the
producer-to-publisher workflow. Its operational contract and
[CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md) identify the responsible boundary.

The public entry point selects exactly one report date and delegates the
date-owned workflow:

```bash
source source_me.sh && python3 make_blog.py --yesterday
source source_me.sh && python3 make_blog.py --date YYYY-MM-DD
```

`make_blog.py` restarts through the physical repository Python 3.12 runtime.
`report_date` is the sole publication identity. `--yesterday` selects the
preceding date in the configured report timezone and replaces an occupied date
for unattended scheduled operation. An occupied explicit `--date` asks for
confirmation unless `--yes` authorizes replacement.

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

It covers same-date replacement, selected-artifact preservation, structured
terminal faults, sealed-bundle integrity, and rendered-page verification without
external route egress.

## Generated outputs

Generated material is ignored unless it is a deliberately tracked project
artifact. Keep generated directories at the repository root and do not use
their contents as authority for source behavior. In particular:

- `out/` holds user-scoped run state, sealed bundles, and publication receipts.
- `generated/` belongs to generated site output; the producer does not own it.
- `graphify-out/` is an orientation index, not proof of the current runtime.
- `output_screenshot_capture/` is temporary capture output and is removed by its harness.

`docs/BLOG_CONTRACT.md` is human-owned and byte-protected. Ordinary pipeline
work does not edit it; broad hygiene-bearing work verifies its SHA-256 before
and after the run.

## Refresh screenshots

The README screenshots come from the sibling publisher's newest canonical
publication record. The harness resolves its `report_date`, serves that
verified local `generated/releases/<report_date>` site, and uses the sibling
repository's local Playwright installation:

```bash
node automation/capture_work_log_screenshots.mjs
```

The harness serves only local static output, blocks non-local browser requests,
checks each page heading, and updates the managed landing-page and newest-post
PNGs in `docs/screenshots/`. It does not build, publish, import, refresh a
mirror, or call a model route, and it removes its temporary capture directory.
Inspect both images after capture. Keep the `screenshots:begin` and
`screenshots:end` sentinels in [README.md](../README.md) so later captures
remain idempotent.

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

For documentation-only work, validate local links, ASCII content, whitespace,
and the working-tree diff. Do not treat an older test result as current evidence.

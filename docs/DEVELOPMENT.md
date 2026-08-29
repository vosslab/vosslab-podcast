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
source source_me.sh && pytest tests/test_daily_blog_candidates.py
source source_me.sh && pytest tests/ -k daily_blog
source source_me.sh && pytest tests/
```

The `pytest tests/` lane is deterministic, offline, and quick. Use `tmp_path`
for test-owned files. Its test-design rules and failure triage are in
[PYTEST_STYLE.md](PYTEST_STYLE.md).

Direct E2Es live in `tests/e2e/` and are excluded from pytest collection. Run
the smallest durable E2E that covers the changed boundary:

```bash
source source_me.sh && python3 tests/e2e/e2e_daily_blog_evidence_git.py
```

See [E2E_TESTS.md](E2E_TESTS.md) for the separation between the fast lane,
direct E2Es, and browser E2Es.

## Verify private experiments

Read [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md) before changing the
daily-blog workflow. It owns the producer-to-publisher operational contract;
use [CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md) and
[FILE_STRUCTURE.md](FILE_STRUCTURE.md) to locate the responsible module and its
tests.

The maker-voice experiment is a private verification workflow, not a
publication workflow. Capture owns sealed fixture evidence and writes it below
`out/<owner>/daily_blog_experiment_fixtures_v2/`. The experiment runner owns its
private capture report below `out/<owner>/daily_blog_experiments/`. Neither
artifact is a publication bundle or publisher input.

Use Python 3.12 through `source_me.sh` for every check. Start with the focused
permanent offline tests that cover prompt resources, capture validation,
route-free calibration preparation, and attestation:

```bash
source source_me.sh && python3 -m pytest \
  tests/test_daily_blog_prompt_resources.py \
  tests/test_daily_blog_rubric_calibration.py \
  tests/test_daily_blog_prompt_experiment.py \
  tests/test_daily_blog_experiment_attestation.py
```

The mandatory one-time evidence path is autonomous and uses the fixture Hermes
shim through the exact configured command boundary without model egress:

```bash
source source_me.sh && python3 automation/run_daily_blog_fixture_capture.py
source source_me.sh && python3 automation/run_daily_blog_fixture_calibration.py
```

Record their absolute artifact paths, then join them without invoking a route:

```bash
source source_me.sh && python3 automation/attest_daily_blog_prompt_experiment.py \
  --capture /absolute/path/to/prompt-experiment-CAPTURE_ID \
  --calibration /absolute/path/to/rubric-calibration-CALIBRATION_ID
```

Attestation re-reads descriptor-pinned source artifacts, recomputes the
acceptance decision, and writes a content-addressed non-publishing record below
`out/<owner>/daily_blog_experiment_attestations/`. It invokes no model route and
does not create a bundle, import a site, or alter a publisher schedule. Fresh
artifact-only reviewers judge the complete sealed posts, and
`record_daily_blog_experiment_reviews.py` records their passage-grounded
submissions before activation. Repetition counts, score tolerances, and reviewer
counts are configurable one-time evidence settings rather than permanent pytest
assertions. Live capture or calibration may be run separately with explicit
data-sharing consent as optional corroboration; it never gates fixture-backed
acceptance. Keep activation, publisher import, and timer ownership in
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md).

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

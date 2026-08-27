# Archived plan: Daily GitHub blog revival

This pre-cutover plan is retained as a decision record. The authoritative producer/publisher
ownership contract is `docs/DAILY_BLOG_OWNERSHIP_CUTOVER.md`; current operations are defined by
`docs/DAILY_BLOG_OPERATIONS.md` and `docs/CODE_ARCHITECTURE.md`.

## Context

Dr. Voss wants to revive this project around one narrow, useful product: choose a day and see a
local-LAN blog post describing what `vosslab` actually did on GitHub that day.

The repository currently has two independently evolved implementations from the same commit
`5ff9d83`:

- `dr_voss` / `origin/dr_voss`: 24 commits ahead of the common base, with the richer `pipeline/`
  implementation, cached JSONL, daily outlines, and embedded local-LLM content stages.
- `origin/main`: Pierre's deliberate attempt to improve the `dr_voss` work, 3 different commits
  ahead of the common base, with the `pipelines/` implementation and explicit `--date` runner.

They are not alternate versions of one linear history. Do not merge or overwrite either branch
until an isolated comparison evaluates Pierre's intended improvements, selects a baseline, and
records which components are retained.
The initial branch assessment recorded a clean `dr_voss` worktree with seven untracked documentation,
test, and development files. Re-check the actual worktree immediately before any comparison and
preserve the resulting inventory.

The existing `dr_voss` fetch stage collects every commit in a recently updated repository. It
records a commit's author timestamp but does not establish that the commit belongs to `vosslab`.
The existing sample blog is generic, contains nested Markdown fences, and gives no commit links.
Its LLM outline artifacts also contain raw XML. Those are unsuitable evidence for a personal daily
work log.

## Implementation status

The M2 evidence command, M3 author/validator/promotion command, and M4 static archive/server code
now exist in this checkout and have synthetic-input tests. That implementation evidence does not close
the remaining human and operational gates in this plan:

- M1 still requires the recorded branch scorecard and a human baseline decision before any
  branch-changing operation.
- M3 still requires one normal authoring run with the current active Hermes profile and its
  `daily-github-blogger` skill, followed by human factual review of the promoted output.
- M4 still requires a fresh macOS private-interface inspection, a manual LAN smoke through the
  selected address, and the promotion prerequisite for every served post.
- Scheduling and public deployment remain out of scope and disabled.

The future-oriented gates below apply to advancing from synthetic-input evidence to normal operation; they do
not mean that the existing M2/M3/M4 code or offline contract tests are absent.

## Objectives

- Generate a source-traceable Markdown post for one explicit local calendar date.
- Include only commits attributable to `vosslab`, with recorded attribution evidence.
- Publish the generated posts and run status only on a selected private LAN address.
- Preserve both current branch histories while selecting and rebuilding from a verified baseline.
- Make failures, partial GitHub data, empty days, and source provenance visible in the site.

## Design philosophy

- Use raw GitHub commits as the authority and build a deterministic evidence layer before agent prose.
- Make Hermes, through the current active profile and `daily-github-blogger` skill, the only generative
  writer; remove the vendored local-LLM execution
  path from the revived daily-blog workflow.
- Give the agent a narrow, self-contained writing contract, structured claims, and a validator rather
  than asking a local model to infer style or facts from a large intermediate outline.
- Keep the first release local-first, inspectable, and reversible; defer podcast, TTS, social, and
  public hosting until the daily blog has real usage.
- Treat branch consolidation as evidence-led component selection, not an automatic merge.

## Scope

- Compare `dr_voss` and `origin/main` in isolated worktrees and select a documented rebuild base.
- Define a date, identity, completeness, and provenance contract for one daily GitHub report.
- Implement a commit-only fetch, an agent-ready claim packet, and a Hermes-authored daily Markdown
  post with mechanical provenance validation.
- Build a static local site with date navigation, visible run state, and links to source commits.
- Serve the static site on an explicitly selected LAN address and non-privileged port.
- Add deterministic unit tests, synthetic-input end-to-end tests, and a live read-only smoke check.
- Update active-plan, output-layout, usage, and changelog documentation as implementation lands.

## Non-goals

- Do not publish to the public internet, GitHub Pages, Bluesky, or a podcast feed.
- Do not retain the vendored `local-llm-wrapper`, Apple Foundation Models, Ollama, depth/referee,
  or local model configuration in the revived daily-blog execution path.
- Do not require TTS, changelog scraping, issues, pull requests, or audio generation.
- Do not merge, rebase, delete, or force-push either existing branch during the revival work.
- Do not claim unverified co-authored, bot-authored, or email-only commits as Dr. Voss's work.
- Do not schedule unattended runs until a manual single-day run and LAN review pass.

## Current state summary

- [README.md](../../README.md) describes a broad multi-channel pipeline rather than a daily blog.
- `pipeline/fetch_github_data.py` already provides PyGithub access, cache handling, JSONL output,
  and logical daily buckets, but it gates on recently updated repositories and emits all commits in
  those repositories.
- `pipeline/github_data_to_outline.py` aggregates commit messages but truncates the evidence passed
  downstream and requires local-LLM outline synthesis before writing its final artifacts.
- `out/vosslab/blog_post_2026-02-22.md` demonstrated the
  current output-quality failure: no source provenance, generic prose, and a Markdown code fence
  around the post itself.
- Pierre's `origin/main` experiment supplies useful explicit-date and validation concepts, but uses
  a separate `pipelines/` tree and `data/YYYY-MM-DD/` artifact contract. It is a candidate source of
  improvements, not an automatically preferred replacement for `dr_voss`.
- There is no `mkdocs.yml`, local site, server configuration, or end-to-end browser test tree.

## Resolved decisions

- The reporting unit is one named date in a configured IANA timezone, not a rolling window.
  The initial default is the last completed calendar day; `--date YYYY-MM-DD` is always explicit.
- The initial content source is GitHub commit history only. Repository update time, issue activity,
  and changelog text are not evidence that Dr. Voss worked on that day.
- Hermes authors the post from a compact, structured claim packet. The code validates the agent's
  evidence manifest and source links before the post is eligible for publication.
- Every published factual bullet carries a commit permalink. The post contains no unsupported
  explanation of intent or impact.
- Local-LAN-only means binding the service to one discovered private LAN address, never `0.0.0.0`.

## Agent writing contract

- The agent runs through Hermes, not a Python import of a local model or a project-local
  API key. The active Hermes profile selects its own configured route; the project stores no model or
  provider configuration for M3. Normal authoring uses a Linux `bwrap` capability sandbox and fails
  closed on hosts without that prerequisite until an equivalent sandbox is configured.
- The agent receives only the complete run manifest, normalized claim JSON, source-permalink map,
  output paths, and the `daily-github-blogger` skill. A cron run must be self-contained because it
  starts in a fresh Hermes session and does not rely on chat memory.
- The agent writes `post_draft.md` and `agent_generation_manifest.json`. The manifest lists each
  paragraph's claim IDs and commit SHAs. It must not use claims outside the supplied packet.
- A deterministic validator rejects malformed Markdown, missing source links, unknown claim IDs,
  unknown SHAs, incomplete data, and paragraphs with no supporting claim IDs. A rejected draft is
  quarantined with the validation report; it never replaces the last verified post.
- Manual generation uses `hermes chat --in <repo> --skills daily-github-blogger --query-file <prompt>
  --quiet`.
  Scheduled generation uses a Hermes cron job with `workdir=<repo>`, the same skill, and a
  pre-run script that prepares claims. Both paths must produce the same artifact contract.

## Architecture boundaries and ownership

### Mapping (milestones / workstreams -> components / patches)

| Milestone / Workstream | Component | Review boundary |
| --- | --- | --- |
| M1 / branch assessment | isolated worktrees and branch scorecard | baseline decision before code moves |
| M2 / evidence acquisition | GitHub client, daily claim JSON, raw snapshot | identity and date contract |
| M3 / agent blog writing | Hermes skill, agent artifacts, validator, and promotion | claim-to-post traceability |
| M4 / LAN operation | static-site builder, static server, run manifest, and status page | LAN exposure and recovery behavior |

## Milestone plan

| M | Title | Summary | Goal |
| --- | --- | --- | --- |
| M1 | Select the recovery baseline | Compare both branch implementations without modifying them. | One documented, protected source base. |
| M2 | Establish daily commit evidence | Fetch and validate confirmed `vosslab` commits for one date. | A complete, inspectable claim set. |
| M3 | Author and validate the daily blog | Aella writes from claims; code validates and publishes it. | A readable post with commit-level provenance. |
| M4 | Operate the LAN monitor | Bind the site safely and expose run health. | Manual local review and diagnosable operation. |

### Milestone: M1 - Select the recovery baseline

- Depends on: none.
- Deliverables: branch scorecard, retained-component inventory, protected untracked-file inventory,
  and human-approved branch/rebuild decision.
- Workstreams: WS1 branch comparison.
- Entry criteria: both branch tips and the current worktree status are recorded.
- Exit criteria: one base is selected; the other branch remains untouched; no branch merge has run.
- Parallel-plan ready: no. The scorecard decision must precede all implementation work.

### Milestone: M2 - Establish daily commit evidence

- Implementation status: command, artifact contract, unit tests, and an offline fixture E2E exist.
- Operational dependency: M1 still governs any branch-changing or baseline-selection follow-on.
- Deliverables: daily input schema, identity configuration, raw response snapshot, normalized claim
  JSON, and no-activity/partial-data manifests.
- Workstreams: WS2 acquisition and WS3 contract verification.
- Entry criteria for normal operation: selected base and an approved fixture shape.
- Exit criteria: fixture and live read-only runs distinguish confirmed, ambiguous, excluded, empty,
  and partial outcomes.
- Parallel-plan ready: yes. Contract tests can proceed after the schema is fixed.

### Milestone: M3 - Author and validate the daily blog

- Implementation status: Hermes command construction, dry-run author artifacts, deterministic
  validation, promotion, and offline fixture E2E exist.
- Depends on: M2, because every visible statement must be derived from normalized claims.
- Deliverables: Hermes writing skill, agent draft/manifest, validated daily post, source links, and
  empty-day post.
- Workstreams: WS4 agent authoring and validation.
- Entry criteria for normal authoring: M2 evidence contract and representative fixtures pass; `hermes`
  is available and the current active profile exposes `daily-github-blogger`.
- Exit criteria: every displayed statement can be traced to a stored claim, a normal active-profile
  run promotes only after validation, and a human reviews that promoted post.
- Parallel-plan ready: yes. Presentation can begin after the JSON contract is frozen.

### Milestone: M4 - Operate the LAN monitor

- Implementation status: static build/server code, fixture M2-to-M4 E2E, and operations guidance
  exist; no long-running service or schedule is installed.
- Depends on: M3 promotion, because the server and archive accept only validated
  `post-YYYY-MM-DD.md` artifacts.
- Deliverables: static archive, bind configuration, manual server command, status manifest, access log
  location, recovery checklist, and LAN smoke evidence.
- Workstreams: WS5 static-site presentation and WS6 local operation.
- Entry criteria for LAN operation: a static site is built from a promoted M3 post and the target
  macOS host has a freshly inspected private interface.
- Exit criteria: the service is reachable through the intended LAN address and not bound to all
  interfaces; fixture-only evidence does not satisfy this gate.
- Parallel-plan ready: no. Binding and exposure verification are inherently serial.

## Workstream breakdown

### Workstream: WS1 branch comparison

- Goal: Select components by observed behavior rather than commit volume or branch name.
- Owner: implementation lead.
- Work packages: WP1 and WP2.
- Needs: clean scratch worktrees for `dr_voss` and `origin/main`.
- Provides: branch scorecard and a human-approved rebuild base.
- Review boundary: no source modifications; a reviewer checks the recorded matrix.

### Workstream: WS2 acquisition

- Goal: Produce a complete date-scoped set of commits demonstrably attributable to `vosslab`.
- Owner: implementation lead.
- Work packages: WP3 and WP4.
- Needs: selected branch base and GitHub identity contract.
- Provides: raw snapshot, claim JSON, and a run manifest.
- Review boundary: data schema and attribution logic receive independent review.

### Workstream: WS3 contract verification

- Goal: Make identity, time-window, completeness, and failure semantics testable.
- Owner: test reviewer.
- Work packages: WP5.
- Needs: WP3 schema.
- Provides: fixtures and deterministic tests.
- Review boundary: tests must not make network calls.

### Workstream: WS4 agent authoring and validation

- Goal: Have Hermes write concise, factual Markdown from claims, then validate the result before
  publication.
- Owner: implementation lead.
- Work packages: WP6.
- Needs: WP4 claim JSON.
- Provides: Hermes writing skill, author prompt/result records, post draft, generation manifest, and
  validated post.
- Review boundary: source links, declared claim IDs, and output text are checked against a fixture
  oracle before a post is promoted.

### Workstream: WS5 static-site presentation

- Goal: Make the daily posts browsable and monitorable on the LAN.
- Owner: presentation reviewer.
- Work packages: WP7.
- Needs: promoted WP6 artifacts.
- Provides: index, date pages, status page, and static build.
- Review boundary: the site reads generated artifacts only and makes no GitHub calls.

### Workstream: WS6 local operation

- Goal: Expose the static site safely on the intended LAN only.
- Owner: operations reviewer.
- Work packages: WP8.
- Needs: WS5 static build and the actual host network inventory.
- Provides: service configuration and operational evidence.
- Review boundary: bind address and port require a fresh host inspection before activation.

## Work packages

### Work package: WP1 - Inventory both branch implementations

- Owner: implementation lead.
- Touch points: scratch worktrees only; `dr_voss`, `origin/main`, and untracked-file inventory.
- Depends on: none.
- Acceptance criteria:
  - Run each branch against the same recorded GitHub fixture, without changing either branch.
  - Score Pierre's intended improvements and the `dr_voss` implementation against explicit-date
    handling, attribution filtering, source permalinks, claim-packet readiness, test health,
    artifact layout, and LAN-site readiness.
  - Record retained, replace, and discard decisions for both `pipeline/` and `pipelines/` trees.
- Evidence or review: a side-by-side command/output table and independent review of the scorecard.
- Obvious follow-ons: WP2.

### Work package: WP2 - Establish the protected rebuild branch

- Owner: human repository owner.
- Touch points: Git branch topology after WP1 approval.
- Depends on: WP1.
- Acceptance criteria:
  - Preserve `dr_voss` and `origin/main` unchanged.
  - Create a clearly named revival branch from the approved base only after a human reviews the
    scorecard.
  - Carry untracked current-worktree files forward deliberately rather than silently deleting them.
- Evidence or review: `git log --graph --all`, `git status --short`, and a human-reviewed diff.
- Obvious follow-ons: WP3.

### Work package: WP3 - Define the daily GitHub evidence contract

- Owner: implementation lead.
- Touch points: settings schema, GitHub fetch adapter, generated `out/vosslab/daily/YYYY-MM-DD/`.
- Depends on: WP2.
- Acceptance criteria:
  - Accept `--date YYYY-MM-DD` and use the configured IANA timezone's 00:00:00 through 23:59:59
    calendar boundaries.
  - Configure a GitHub login allowlist and optional explicit email allowlist.
  - Mark each retrieved commit `confirmed`, `ambiguous`, or `excluded`, with the exact login/email
    evidence and author/committer timestamps retained.
  - Store SHA, full message, API URL, HTML permalink, repository, and retrieval timestamp without
    destructive truncation.
  - Write a run manifest with expected/received pages, rate-limit status, exclusion counts, and a
    `complete` boolean.
- Evidence or review: fixed JSON fixtures for login match, allowlisted email match, no match,
  co-authorship ambiguity, timezone boundary, pagination, and rate-limit partial data.
- Obvious follow-ons: WP4 and WP5.

### Work package: WP4 - Build the normalized daily claim set

- Owner: implementation lead.
- Touch points: deterministic aggregation module and daily artifact writer.
- Depends on: WP3.
- Acceptance criteria:
  - Group confirmed commits by repository and preserve chronological order within each group.
  - Emit only directly supported claims such as repository name, count, subject, timestamp, and
    permalink.
  - Generate an explicit zero-activity result instead of an invented narrative.
  - Refuse publication when the run manifest is incomplete, while retaining the partial raw data
    for diagnosis.
- Evidence or review: byte-stable result for a fixed fixture and a checked claim-to-SHA map.
- Obvious follow-ons: WP6.

### Work package: WP5 - Test provenance and failure semantics

- Owner: test reviewer.
- Touch points: `tests/` unit tests and `tests/e2e/` fixture-backed runner.
- Depends on: WP3.
- Acceptance criteria:
  - Fast tests cover all identity states, day boundaries, duplicate commits, ordering, and empty
    days with no network access.
  - Separate E2E runners verify raw snapshot -> claims -> promoted Markdown and promoted Markdown ->
    static site; both synthesize their inputs inside owned temporary harnesses.
  - A partial/rate-limited manifest blocks publication and presents a visible failure state.
- Evidence or review: focused pytest results plus an explicit end-to-end command result.
- Obvious follow-ons: M3 integration gate.

### Work package: WP6 - Author and validate factual Markdown posts

- Owner: implementation lead.
- Touch points: `daily-github-blogger` Hermes skill, agent prompt template, agent generation
  manifest, deterministic validator, post metadata, and manual/cron invocation wrappers.
- Depends on: WP4.
- Acceptance criteria:
  - Create a compact, reusable Hermes skill with explicit voice, output paths, evidence rules,
    self-review checklist, no-activity behavior, and an instruction to stop on incomplete input.
  - Invoke Hermes manually through `hermes chat` using the repository as its working directory and
    the current active profile's `daily-github-blogger` skill; do not invoke `local_llm_wrapper` or
    an LLM HTTP client.
  - Have the agent write one H1 with date/timezone coverage, concise first-person prose, repository
    sections, commit permalinks, local claim JSON link, and `agent_generation_manifest.json`.
  - Validate every listed claim ID and SHA against the source packet before promoting the draft to
    the publishable post path. Preserve rejected drafts and their validation report for inspection.
  - Use the same agent contract in a later Hermes cron job with `workdir` and pre-run claim script;
    no scheduled job is created until the manual path passes.
  - Render a plain no-activity post for complete empty days and never publish nested Markdown fences,
    raw XML, a local-model error payload, or an unvalidated agent draft.
- Evidence or review: fixture-driven agent runs, validator tests, and a human review of one live
  historical post against its claim packet.
- Obvious follow-ons: WP7.

### Work package: WP7 - Build the private static site

- Owner: presentation reviewer.
- Touch points: static-site configuration, generated archive index, status page, and `out/` layout
  specification.
- Depends on: WP6.
- Acceptance criteria:
  - Build static pages from validated, promoted post artifacts only; presentation performs no GitHub
    calls and never treats a draft or generation manifest as publishable content.
  - Provide newest-first archive navigation and a direct date selector/list.
  - Show last run timestamp, source date, commit/repository counts, completeness, and failure text
    prominently on the home page.
  - Keep generated site output under the user-scoped `out/vosslab/` namespace and update the output
    contract before adding that path.
- Evidence or review: static build succeeds from fixtures and links resolve locally.
- Obvious follow-ons: WP8.

### Work package: WP8 - Serve and monitor the LAN site

- Owner: operations reviewer.
- Touch points: local server command or user-level service, bind configuration, logs, and
  troubleshooting documentation.
- Depends on: WP7.
- Acceptance criteria:
  - On macOS, inspect interfaces with `networksetup -listallhardwareports`, `ifconfig`, and
    `ipconfig getifaddr <interface>` immediately before configuration, then bind to one selected
    private LAN address and a non-privileged port.
  - Reject wildcard bind addresses in configuration validation.
  - Keep server logs under `out/logs/` and expose status through the generated static page rather
    than a hidden terminal-only state.
  - Verify the page over the selected LAN address and use
    `lsof -nP -iTCP:<port> -sTCP:LISTEN` to confirm that the configured service does not listen on
    public or wildcard interfaces.
  - Document start, stop, rebuild, failure inspection, and rollback commands; do not add a schedule
    in this milestone.
- Evidence or review: socket inspection, LAN HTTP smoke result, and a documented recovery drill.
- Obvious follow-ons: optional scheduling only after Dr. Voss has monitored manual runs.

## Acceptance criteria and gates

- Baseline gate: WP1 scorecard is reviewed before any branch-changing operation.
- Evidence gate: a post has one complete manifest, one claim set, and valid source links for every
  displayed commit.
- Attribution gate: no `ambiguous` or `excluded` commit appears in the agent generation manifest or
  published post.
- Agent gate: the agent generation manifest references only approved claim IDs and SHAs; the
  deterministic validator promotes the post only on success.
- Content gate: complete empty day produces a clear empty post; incomplete day produces no post.
- Site gate: static build has no broken local links and exposes current run state.
- LAN gate: listener is bound to the configured private address only; a wildcard listener fails.
- Independent review gate: another agent/reviewer compares the published fixture post to claims and
  source fixtures before live use.

## Test and verification strategy

- Unit tests: identity evaluation, timezone interval construction, event filtering, ordering, claim
  packet creation, agent-manifest validation, HTML/Markdown escaping, and listener configuration.
- Fixture integration: recorded GitHub API payloads cover multi-repo activity, outside-window
  commits, ambiguous identity, a zero-commit day, duplicate pages, and a rate-limit failure.
- End-to-end: run the complete fixture pipeline into an owned temporary output tree, use deterministic
  dry-run authoring, then verify the promoted post, index, manifests, and source links. This does not
  invoke Hermes or a model.
- Live read-only smoke: fetch one explicit historical date from GitHub, invoke Hermes through the
  current active profile and `daily-github-blogger` skill, inspect its declared evidence and commit
  links manually, then build the local page.
- LAN smoke: request the home page and a dated post through the chosen private address; inspect the
  listener with the host's socket tool. Failure of any completeness, provenance, or bind check blocks
  the next gate.

## Risk register

| Risk | Impact | Trigger | Owner | Mitigation |
| --- | --- | --- | --- | --- |
| Incorrect personal attribution | High | collaborator or bot commit appears in post | WS2 | explicit evidence states; default-exclude ambiguity; fixture coverage |
| Incomplete GitHub data | High | rate limit, API failure, or truncated pagination | WS2 | manifest completeness; retain raw partial data; block publication |
| Branch loss or accidental merge | High | branch-changing command before WP1 review | WP2 | isolated worktrees, human-owned branch action, no auto-merge |
| Agent hallucination or format drift | High | text or manifest cannot map to a claim SHA | WS4 | constrained skill, self-review, deterministic manifest validator, human live-sample review |
| Hermes job configuration failure | High | missing CLI, active-profile skill, or project working directory | WS4 | manual run first; self-contained cron prompt; scheduler preflight; visible failed status |
| LAN overexposure | High | wildcard or public-interface listener | WS6 | explicit private-IP bind and socket verification |
| Scope return to podcast complexity | Medium | TTS or local-LLM work blocks daily blog | implementation lead | non-goals enforced; separate later plan |
| Output-layout drift | Medium | artifacts appear outside user-scoped `out/` | WS5 | update and test output contract before implementation |

## Rollout and release checklist

- [ ] Preserve and compare both branch tips in isolated worktrees.
- [ ] Record human approval of the revival base and retained components.
- [x] Implement and pass identity/completeness fixture coverage and the offline M2/M3 E2E.
- [ ] Produce and inspect a complete historical daily post through the current active Hermes profile.
- [x] Implement deterministic generation-manifest validation and promotion checks.
- [x] Implement and fixture-test archive and status-page generation from promoted artifacts.
- [ ] Verify private-address-only LAN serving and recovery documentation.
- [ ] Run independent provenance review of fixture and live-sample posts.
- [ ] Keep scheduling disabled until manual monitoring demonstrates stable operation.

## Documentation close-out requirements

- Active plan / progress tracker: keep this plan current and add a concise progress tracker when M1
  begins; archive the older broad pipeline plan only after its retained work is mapped here.
- docs/CHANGELOG.md entry: record each implemented behavior change under its actual date.
- Archive / closure notes: record baseline decision, discarded components, verification evidence,
  server bind address class (not secrets), and follow-on work.

## Patch plan and reporting format

- Patch 1: branch scorecard and human-selected revival base; no merge.
- Patch 2: explicit-date, identity-aware raw fetch and manifest.
- Patch 3: normalized claims with provenance, source-permalink map, and deterministic test fixtures.
- Patch 4: Hermes writing skill, agent generation manifest, deterministic validator, and static
  archive/status site.
- Patch 5: private LAN server configuration, verification, and operations documentation.
- Patch N: regression tests, output-contract updates, and changelog/progress evidence.

## Open questions and decisions needed

- Manager/subagent decision procedure:
  - Decision owner or dedicated class: Dr. Voss approves the branch baseline; an implementation
    lead supplies the scorecard.
  - Evidence and decision rule: select the branch/component mix that passes the same date fixture
    with the fewest changes while preserving explicit-date behavior, complete provenance, and a
    clean test path. Do not select by recency or line count alone.
- Non-blocking follow-up: after manual active-profile Hermes posts are reliable, add a dedicated
  Hermes cron job with the same active-profile route and a pre-run claim-collection script; retain the
  manual path as the recovery mode.

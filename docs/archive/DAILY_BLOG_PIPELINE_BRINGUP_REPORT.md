# Daily Blog Pipeline Bring-Up Report

Status date: August 28, 2026

> Historical bring-up record. F4-F6 later accepted the fixture-backed maker activation, bundle v5
> publisher integration, disposable schedule proof, and F7 audits. The August 29 closure accepted F7.

This report records the work required to turn the Vosslab daily work blog from a collection of
partly overlapping scripts, agents, caches, and schedulers into one inspectable daily publication
pipeline. It includes the approaches tried, what failed, why the design changed, what now works,
and what still prevents a clean August 27 publication.

The short version is that the hard part was never just writing a blog post. The pipeline crosses
GitHub, local Git mirrors, deterministic evidence extraction, LLM authoring, LLM judging, a
producer repository, a publisher repository, MkDocs, systemd, and Hermes. Several early designs
allowed those layers to share responsibilities. Each time one layer failed, it was difficult to
tell whether the cause was collection, scheduling, prompt transport, model access, validation,
publication, or stale state.

The durable direction is now much clearer:

```text
systemd user timer at 04:00 America/Chicago
    -> ./make_blog.py --yesterday
    -> one report-date lock and one publication identity
    -> authenticated fresh GitHub owner roster
    -> immutable roster snapshot
    -> owner-qualified local Git mirrors
    -> exact report-day activity and evidence
    -> bounded editorial projection
    -> two isolated Hermes author calls
    -> deterministic candidate validation
    -> one isolated anonymous Hermes referee call
    -> one date-owned publication bundle
    -> publisher CLI validation, strict MkDocs build, and atomic local release
```

The project explicitly selects the `openai-codex` provider for content stages. The active Hermes
profile owns model selection, and the Hermes credential pool owns eligible-account selection.
Hermes does not own the daily schedule, report-date identity, evidence rules, publication state,
retry policy, or MkDocs release.

## Current state

| Area | Current state |
| --- | --- |
| Scheduler design | Checked-in systemd user timer calls `./make_blog.py --yesterday` at 04:00 Central |
| Manual entry point | `./make_blog.py --yesterday` or `./make_blog.py --date DATE` |
| Publication identity | `report_date`; `bundle_sha256` is integrity only |
| GitHub repository intake | Fresh owner roster, bypassing the stale repository-list cache |
| GitHub authentication | Required before client construction; a narrow runtime `GITHUB_TOKEN` loader proved a 5,000-request authenticated quota |
| Hermes editorial transport | Verified through the configured `hermes chat` stdin route; no project API or provider credential is required |
| Project provider contract | Every author/referee route uses exactly one `--provider openai-codex`; focused configuration tests pass |
| Hermes account selection | Confirmed defect: fresh CLI processes rank an empty process-local capacity cache before asynchronous refresh |
| Evidence | Exact Git objects, repository lifecycle data, dated changelog and documentation context, diffs, screenshots, and commit metadata |
| Editorial production | The current contract uses two authors, deterministic validation, and an anonymous referee |
| Maker-voice work | V4 is implemented as a non-publishing experiment and remains unactivated |
| Publisher | Separate `vosslab-daily-blog` checkout validates and atomically installs a date-owned release |
| August 26 | A post exists, but later contract changes caused the current producer to treat the installed date as occupied-invalid pending confirmed replacement |
| August 27 | No post exists; two runs failed in `repository_discovery` before mirror or model work |
| Immediate producer blocker | `out/vosslab/daily_blog_repository_rosters/.capture.lock` is mode `0664`; the roster writer requires an owner-controlled `0600` lock |
| Next cross-repository step | Repair and verify Hermes cold-start capacity selection, then repair the lock and run August 27 |

The working tree contains extensive pre-production changes. The Graphify map was generated from
commit `50db1601c637`, but the current source and tests include substantial work after that commit.
The report therefore treats Graphify as an orientation map and the current files and run artifacts
as the authority.

## The desired product

The requested output is not a machine-readable digest disguised as prose. The central test is:

> After reading this post, does it feel like Neil sat down after coding and wrote about what he
> made, what interested or surprised him, why he enjoyed working on it, what he learned, and what
> he wants to try next?

The evidence system must be broad enough to notice the important work, especially a newly created
repository. The editorial system must then be selective enough to tell the interesting story rather
than enumerate every commit. Technical details support that story; they are not the story by
themselves.

August 22 and August 23 were identified as closer to the desired voice. August 24 and August 25
showed the failure mode: generic headings, repository-by-repository enumeration, quoted commit
subjects, and little sense of a maker reflecting on the work. August 26 exposed a different
problem: even improved prose cannot headline a new project if repository discovery omitted that
project before the model ever saw the evidence.

## Architectural challenge 1: identifying which repository owns what

The first investigation began in `vosslab-podcast`, but the live MkDocs site, dated post source,
build output, static service, and publication state were in the sibling
`/home/vosslab/nsh/vosslab-daily-blog` checkout. Historical generation code and revival plans lived
in the podcast repository. Runtime responsibility was split among both repositories, Hermes-owned
wrappers, cron jobs, and multiple systemd units.

This ambiguity caused two kinds of mistakes:

1. It was possible to diagnose or plan changes in the generator repository without first proving
   which code owned the visible site.
2. A simple-looking wrapper such as `process_day.sh` concealed several external schedulers and
   handoffs, so an operational failure looked like a content failure.

The adopted ownership boundary is:

- `vosslab-podcast` is the producer. It owns repository discovery, mirrors, report-day activity,
  exact evidence, editorial projection, model calls, candidate validation, referee selection,
  bundle construction, run state, and the one schedule.
- `vosslab-daily-blog` is the publisher. It owns independent bundle validation, MkDocs source,
  date-owned releases, publication receipts, the atomic served-site pointer, and the port-8016
  static service.
- The repositories communicate through a versioned bundle and a publisher CLI. They do not import
  each other's Python modules.

This was the first major design correction. It made later failures attributable to a specific
owner.

## Architectural challenge 2: replacing the inherited daily-blog paths

The first revived design, implemented around August 20, was a staged M2/M3/M4 path:

- M2 collected explicit-date GitHub evidence into claims and a run manifest.
- M3 asked a `daily-github-blogger` Hermes skill to write a post and validated paragraph-to-claim
  provenance.
- M4 built a private static archive and LAN server from promoted posts.

That work proved several useful ideas: explicit report dates, identity-aware commit evidence,
deterministic validation, private LAN serving, and a Hermes-selected model rather than a project
model setting. It also remained a parallel system beside the live MkDocs workflow.

Keeping it would have meant maintaining two publication architectures. The later producer/publisher
cutover therefore replaced the M2/M3/M4 publication path instead of adding more adapters. The useful
contracts were retained conceptually; their runtime ownership was moved into `pipeline/daily_blog/`
and the sibling importer.

## Architectural challenge 3: exact evidence across many repositories

The blog is reconstructed from bounded public development evidence, not a complete private diary.
That creates several correctness problems:

- GitHub Events is a snapshot and is not complete history.
- A recently updated repository list can be cached while a new repository is created later.
- Multiple same-day branches can diverge.
- A commit SHA alone does not say which parent range to inspect.
- Commit messages locate activity but often do not explain why the work matters.
- A global evidence budget can accidentally spend all of its space on large repositories and leave
  another active repository with nothing citable.

The pipeline went through several evidence versions before reaching the current design:

1. Initial evidence was commit-centric and dependent on recently updated repository lists.
2. Exact Git evidence added every attributed commit-to-parent revision range and branch-tip
   snapshots.
3. Dated changelog entries became the preferred narrative anchor, with changed docs, diffs, README
   context, screenshots, and commit metadata as corroboration.
4. Editorial projection separated the complete evidence packet from the bounded material actually
   sent to authors and referees.
5. A fresh owner roster became the authoritative repository universe.
6. Repository creation time and fork state became typed lifecycle evidence.
7. Evidence budgeting reserved at least one high-authority citable item for every active repository
   before allocating routine support.

This work made the evidence larger and more reliable while giving the prompt a smaller, more useful
view.

## The August 26 missing-repository failure

The August 26 post did not cover `vosslab/cancer-clicker`, even though it was a newly created game
repository and therefore an obvious story candidate. The omission was not primarily a prompt
failure. The repository never reached the model.

The old intake began from configured or cached repository names. A repository created during the
report day could be absent from that list, which meant it was absent from mirror refresh, activity
location, evidence, projection, and headline selection. No amount of prompt emphasis could recover
data that was missing upstream.

The fix changed the foundation:

- Fetch a fresh complete public owner roster from `GET /users/vosslab/repos` before mirror work.
- Bypass the 24-hour repository-list cache for that request.
- Validate owner identity, repository URLs, creation time, fork state, and eligibility.
- Persist and reload an immutable roster snapshot before any mirror consumes it.
- Scope mirror directories and locks by both owner and repository.
- Carry `created_in_report_window` and `new_source_repository` into projection.
- Put a same-day new repository first in story-oriented context without forcing the final headline.

A fresh snapshot found 111 repositories. The repaired August 26 projection retained nine active
repositories and placed `vosslab/cancer-clicker` first with citable excerpts and the new-repository
signal. That proves discovery and salience. It does not prove the final prose, because the current
v4 experiment has not completed a live model run.

## Architectural challenge 4: getting large prompts to the model

One earlier layered-editorial path passed a large prompt as a command-line argument and failed with:

```text
OSError: [Errno 7] Argument list too long
```

That failure was operationally dangerous because a later fallback path could leave a generic post
visible. The solution was not to make the prompt smaller merely to satisfy the operating system.
Large evidence must travel through standard input or a file.

The current Hermes role contract uses:

```text
hermes chat --provider openai-codex --in {generator_repository} --query-file - --ignore-rules --quiet
```

Each author and referee starts in a fresh process. The complete prompt is written to stdin. The
repository templates own the task instructions, the project names the provider, the active Hermes
profile owns model selection, and the Hermes pool owns eligible-account selection. Resumed sessions,
profile skills, inline queries, and inherited repository instructions are rejected for these routes.

This fresh-process boundary is part of editorial correctness, not just subprocess convenience. Each
author, the referee, and any referee-repair attempt receives one new isolated Hermes process and one
self-contained task prompt. No role inherits another role's conversation, saved session, memory, or
instruction context. The two authors therefore remain independent, and the anonymous referee sees
only the deterministic evidence and candidate material intentionally assembled for judging.

The planned shared capacity snapshot does not weaken this isolation. It carries only sanitized
operational account state used before model execution. It carries no prompts, responses, transcripts,
conversation identifiers, model memory, or editorial decisions. Editorial context remains fresh per
task while account-capacity observations remain safely reusable across one-shot processes.

The project is already connected to Hermes correctly. The stdin transport was verified before the
explicit provider binding with:

```bash
printf '%s\n' 'Reply with exactly: HERMES_ROUTE_OK' |
  hermes chat \
    --in /home/vosslab/nsh/vosslab-podcast \
    --query-file - \
    --ignore-rules \
    --quiet \
    --source tool
```

Hermes returned:

```text
HERMES_ROUTE_OK
```

The production relationship is therefore:

```text
Python pipeline
    -> subprocess stdin
    -> hermes chat --query-file -
    -> active Hermes model/provider
    -> stdout
    -> deterministic project validation
```

The project neither receives nor forwards OpenAI, Nous, or other model-provider credentials.
Hermes obtains those from its active profile. No project API key or GUI key is needed for the
current author/referee workflow.

The technical fallback publication path was removed. Invalid or missing model output now stops the
run before bundle creation and site import, preserving the last good site.

## Account-selection challenge: fresh Hermes processes start cold

The explicit provider route enters the correct OpenAI Codex credential pool, but it does not by
itself guarantee that the pool chooses the best eligible account. Current Hermes source confirms a
cold-process lifecycle defect:

1. `rank_cached_available()` reads capacity snapshots held only in process memory.
2. A fresh `hermes chat` process has no snapshots, so ranking preserves canonical eligible order.
3. `schedule_refresh()` starts a daemon refresh only after that first ranking and selection.
4. The refreshed state cannot help the selection already made and is not shared with the next fresh
   author or referee process.

The three daily-blog model roles are sequential fresh CLI processes. Without shared state, each role
can repeat the same cold fallback even though Hermes has a capacity-scoring policy. A later 429 can
still trigger normal cooldown and rotation, but reactive failover is not the same as choosing the
highest-ranked eligible account before the request.

The durable repair belongs in Hermes core. Hermes should load one shared sanitized capacity snapshot
before selection. Data younger than ten minutes should be reused without probing. Data between ten
minutes and three hours can drive immediate selection while one cross-process owner refreshes them in
the background. Missing, corrupt, or older data should trigger one bounded synchronous refresh before
first selection. A failed cold probe should produce an explicit non-secret reason and deterministic
eligible-order fallback. Atomic replacement, owner-only permissions, rate-limit eligibility, and
credential-version matching keep the cache safe and ensure token rotation invalidates only the
affected snapshot.

The due-but-usable case is intentionally different from the cold or expired case. A ten-minute-old
snapshot is due for refresh but remains valid for ranking until the three-hour stale boundary. The
current selection should not wait for another quota round trip when it already has usable evidence.
The refresh owner should select from that snapshot immediately, then run one bounded managed refresh
and guarantee that the task finishes or preserves the prior snapshot before the CLI process exits.
This can use a joined non-daemon task or another existing Hermes-managed lifecycle; it must not use an
untracked daemon thread. The confirmed defect is selecting with no usable snapshot and losing the
result between processes, not background refresh after a valid selection.

This repair requires neither a Hermes HTTP API nor project access to provider credentials. It is a
generic account-pool correction for the CLI, TUI, gateway, and scheduled workloads.

Several implementation details deserve explicit review during that repair:

- The current refresh worker probes accounts sequentially inside one outer `try` block. One raised
  request can stop later healthy accounts from receiving snapshots. Each account probe needs an
  isolated result while the overall refresh retains one bounded deadline.
- The current Codex usage parser retains rate-limit windows but drops the provider's non-secret
  eligibility state. Capacity ranking must exclude a currently disallowed account rather than merely
  give it a low score and wait for a model request to return 429.
- A daemon refresh thread is not durable state. For due-but-usable data, selection proceeds from the
  existing snapshot while a bounded managed refresh runs. Hermes must join or otherwise own that task
  through atomic commit or explicit retention of the prior snapshot before process exit.
- Hermes already has cross-platform file-lock and atomic JSON-writing primitives. The cache should
  reuse those mechanisms with a dedicated capacity lock and should not hold the authentication-store
  lock during quota network calls.
- Cache identity must include the active Hermes home/profile, provider, stable credential identity,
  and credential version so profiles cannot reuse each other's observations and token rotation
  invalidates only the changed account.
- Active credential leases are currently process-local. The daily-blog roles run sequentially, so
  the publication path needs shared capacity observations, not a new distributed lease system. Any
  broader claim about balancing simultaneous independent CLI processes requires separate evidence or
  an explicit shared-lease design.
- Fresh-process verification should compare the selected account with the exact sanitized snapshot
  used for that decision. A separately fetched dashboard ranking can change between requests and is
  supporting evidence rather than the authoritative selection record.
- The installed `hermes` executable used by systemd must resolve to the reviewed core implementation
  after the repair. A correct editable source file is not deployment evidence by itself.

## Editorial challenge: rules produced compliant but lifeless prose

The early prompts accumulated many style instructions because every observed bad output suggested
another rule. This made the prompt look precise while still encouraging an average, mechanical
internet response.

The prompt-engineering literature supported a different approach:

- Examples communicate qualities that are hard to describe precisely.
- Zero-shot generation tends toward broad average patterns.
- A prompt should resemble the genre the model is expected to produce.
- Irrelevant or excessive instruction can make prose less natural.
- Target writing samples establish voice and tone more directly than a long style checklist.

The resulting v4 maker experiment uses a short positive maker brief and registered example arms:

| Arm | Examples |
| --- | --- |
| `v4-instruction-only` | None |
| `v4-one-example` | Project-owned August 23 post |
| `v4-three-examples-corpus-v2` | August 23 plus short attributed Julia Evans and Mitchell Hashimoto excerpts |

The author receives evidence, examples, the maker brief, and the output contract. The author does
not receive the scoring rubric. The referee receives anonymous candidates, the central question,
and the weighted rubric. Deterministic code still owns factual provenance, structure needed by the
publisher, prompt and output budgets, repository links, and evidence comments.

This separation follows the user's positive-prompting direction: describe the desired behavior
directly, demonstrate it with examples, and reserve prohibitions for actual safety or correctness
boundaries.

## Editorial attempts and why there is still no v4 winner

A private experiment attempted two fixtures, four arms, and three repetitions, for 24 planned
author generations. All 24 stopped in `author_generation` with `EditorialBlockedError`. The
artifact contains no selected candidates, referee comparisons, aggregates, or winner.

That artifact is intentionally redacted. It records the stable failure stage and class but does not
retain provider diagnostics or complete prompts. A reported `RateLimitError` raised understandable
concern, but the durable artifact cannot distinguish provider quota from another Hermes route
failure. It should therefore be treated as route-diagnostic evidence, not as proof that a model or
prompt arm failed semantically.

A later Hermes transport smoke returned `HERMES_ROUTE_OK`. That proves the CLI, stdin transport,
active profile, and basic model route are connected. The current checked-in route additionally pins
`--provider openai-codex` and validates that command shape offline. Neither result proves that a full
project payload will finish two author calls plus referee work, that a fresh process selects the
best eligible account, or that the separate 24-call experiment will complete under its larger
workload.

The current experiment was then split into two stages:

1. A fresh non-publishing capture runs the busy and quiet fixtures through the author and referee
   routes. Its result remains pending calibration attestation.
2. A route-free attestation joins that capture to a separately passing live historical rubric
   calibration and recomputes the deterministic acceptance result.

V4 remains unactivated because there is no current live capture, passing live calibration,
attestation, stable winner, or reviewed activation change. Active production remains v3.

## Approval challenge: assisted-run approval was mistaken for a runtime requirement

The word "approval" referred to two relevant but different boundaries during bring-up:

1. The repository has an application-level opt-in for sending historical posts and exact-Git
   evidence through live shadow evaluation and rubric calibration. This is
   `daily_blog.shadow_evaluation.external_model_data_sharing` plus an explicit calibration flag.
2. The coding-agent environment required human approval before I could send project content to an
   external model during an assisted run. That restricted what I could execute on the user's behalf.

Neither boundary means that the ordinary CLI route needs a project API key or an interactive prompt.
The systemd service should be completely noninteractive. Its model calls should either succeed or
fail with a recorded phase; they should never stop to ask an operator to approve routine scheduled
execution. Historical calibration remains separately opt-in because it is evaluation work, not
ordinary daily publication.

The coding-agent approval restriction explains why some live experiments were not run from this
session. It is not a requirement that should be built into the production scheduler.

## Credential boundaries: GitHub, provider, and HTTP API keys are different

Three credential names appeared during the investigation, but they serve unrelated systems:

| Credential | Owner and purpose | Daily publication use |
| --- | --- | --- |
| `GITHUB_TOKEN` | Project runtime credential for authenticated GitHub repository discovery | Required |
| Model provider credentials or OAuth | Active Hermes profile selects and authenticates the model/provider | Used internally by Hermes; never passed through the project |
| `API_SERVER_KEY` | Bearer authentication for clients of the optional Hermes HTTP API | Not used by the CLI author/referee route |

The current Hermes gateway is running. `API_SERVER_KEY` exists in the Hermes dotenv, but the HTTP
API server is not enabled and `127.0.0.1:8642/health` is unreachable. None of that blocks the blog:
the project launches `hermes chat` directly and reads stdout.

If a future GUI or persistent application uses the Hermes HTTP API, its intended boundary is:

```text
Browser
    -> project backend
    -> loopback Hermes API at 127.0.0.1:8642
```

The backend would own the bearer key. It should not appear in browser JavaScript, project settings,
prompt text, Git, or frontend build variables. That optional HTTP design should not replace the
current CLI editorial route unless it preserves the same `--ignore-rules` instruction-isolation
contract.

## Scheduling challenge: Hermes cron versus systemd

Scheduling changed several times because the old ownership model kept reappearing in operations.

### Attempt 1: Hermes cron

The revived design initially planned a Hermes cron job that ran a preflight script and invoked the
author skill. This coupled scheduling to the model runtime and depended on external wrapper paths.
A missed publication was eventually traced to a retired Hermes cron entry that still called a
deleted publisher script before the new producer orchestrator could create a run.

### Attempt 2: systemd plus cursor and backlog reconciliation

The first systemd repair used a persistent schedule cursor, reconciled publisher receipts, and
drained missing dates oldest-first. This was more inspectable than the Hermes cron and proved that a
systemd-owned job could drive the producer and publisher.

It was also more state than the product needed. A date is already the natural identity. There is no
requirement for concurrent same-date runs or an independent backlog cursor.

### Current design: one direct date-owned systemd command

The checked-in timer now runs at 04:00 America/Chicago and invokes:

```text
/home/vosslab/nsh/vosslab-podcast/make_blog.py --yesterday
```

The command owns date selection, publication inspection, the per-date lock, generation, and import.
An operator can run any missed date explicitly. This eliminates a second scheduling state machine.

The current Codex environment could inspect and verify the unit files but could not reliably connect
to the user's systemd user bus. Therefore the checked-in design is verified; the exact currently
installed user-unit state still needs a host-side `systemctl --user cat` and timer status check.

## Command challenge: one obvious manual front door

Before `make_blog.py`, operators had to know which automation module, settings path, environment,
date format, and publisher handoff to use. The requested root interface is now:

```bash
./make_blog.py --yesterday
./make_blog.py --date 2026-21-08
```

The command also accepts canonical ISO `YYYY-MM-DD`. It resolves the repository root, relaunches
through the physical repository-local Python 3.12 environment, fixes settings and output ownership
to repository paths, and delegates one canonical report date to the shared publisher command.

Existing-date behavior was another source of confusion. The current contract is:

- Interactive terminal: ask `Overwrite YYYY-MM-DD? [N/y]:`.
- Exact `y`: build and validate a replacement before changing stable publication paths.
- Default answer: preserve the existing coherent publication.
- Noninteractive systemd run: preserve a coherent existing date and exit successfully.
- Occupied legacy or invalid date: fail closed until an interactive operator confirms replacement.

This behavior matches the content's actual value. Generated prose is replaceable. The system should
preserve consistency and rollback ability, not invent a permanent identity for every attempted
draft.

## Identity challenge: removing `bundle_id`

Earlier bundles used both a report date and a generated bundle or run identity. That made ordinary
replacement sound like a conflict between equally permanent publications.

The current contract uses `report_date` as the sole publication identity. There is one stable
producer publication path and one stable publisher release for that date. `bundle_sha256` proves
integrity but does not create another business identity. Run IDs remain diagnostic records of
attempts; they are not publication identities.

The publisher builds a complete proposed source tree and strict MkDocs release before swapping the
date-owned paths. The publication receipt is written last as the authoritative commit marker.
Rollback copies exist only to recover from an interrupted replacement.

## GitHub rate-limit challenge

The scheduled August 27 run at 07:00 UTC failed immediately in `repository_discovery`:

```text
GitHub API rate limit exceeded while GET /users/vosslab/repos;
remaining=0; reset_local=02:15:37
```

The old collector made anonymous public GitHub requests. That unsupported path caused the failed
run and has now been removed. A read-only fine-grained
`GITHUB_TOKEN` already existed in `/home/vosslab/.hermes/.env`, but the collector still read the old
blank `settings.yaml` token field.

The production rule is categorical: GitHub authentication is required. A missing token fails
locally before `GitHubClient` creates a cache or makes a network request. There is no anonymous
fallback.

Research and local source inspection found:

- GitHub expects personal access tokens in the HTTP `Authorization` header and grants authenticated
  requests a higher rate limit.
- Hermes loads its own `.env` at process startup.
- Hermes deliberately strips `GITHUB_TOKEN` from child command environments.
- `~/.hermes/.env` contains many unrelated credentials, so systemd `EnvironmentFile=` would inject
  far more authority than the blog process needs.

The working-tree solution is a narrow runtime credential owner in
`pipeline/podlib/runtime_credentials.py`:

1. Use an explicitly injected process `GITHUB_TOKEN` when present.
2. Otherwise resolve `$HERMES_HOME/.env`, defaulting to `~/.hermes/.env`.
3. Parse only the exact `GITHUB_TOKEN` entry.
4. Validate a nonempty, single-line ASCII value.
5. Return it directly to `GitHubClient` without sourcing the file or adding neighboring values to
   `os.environ`.

Both fresh repository discovery and the older general GitHub fetch command now use this runtime
boundary in the working tree. `GitHubClient` also rejects an empty token, so a future caller cannot
accidentally restore anonymous access. The obsolete rate-limit message was changed to point at the
runtime credential rather than `settings.yaml`.

Focused credential, repository-discovery, integration, and rate-limit tests passed. Structural
hygiene checks also passed. A live read-only quota request returned:

```text
Authenticated GitHub core quota: limit=5000 remaining=5000
```

The credential value was not printed. This proves that the exact-key loader and PyGithub
authentication work. It does not prove a complete daily publication, because the next manual run
encountered a different local-state failure.

The obsolete blank `github.token` key has been removed from `settings.yaml`.

## Roster lock challenge

The manual August 27 run at 16:06 UTC got past the GitHub request and then failed while installing
the immutable roster snapshot:

```text
RuntimeError: Repository roster snapshot capture lock is unsafe.
```

The lock currently has:

```text
mode=0664 owner=vosslab group=vosslab
path=out/vosslab/daily_blog_repository_rosters/.capture.lock
```

The hardened roster code requires the lock to be a regular, owner-controlled `0600` file. The file
predates that stricter contract, so opening it again does not change its existing mode. The failure
is therefore a local migration problem, not a GitHub or Hermes failure.

The immediate repair is to change that exact file to mode `0600`, then rerun the report date. A
longer-term cleanup should ensure any pre-hardening lock files are explicitly migrated or rejected
with an operator message that includes the exact safe repair. That repair has not yet been applied
in this report's status snapshot.

## Python environment challenge

The repository requires Python 3.12 for producer commands, while the sibling publisher currently
uses Python 3.13. Several earlier test reports accidentally used whatever `python3` appeared first
and therefore did not constitute activation evidence for the producer.

The repository now uses a physical local `.venv`, and agents run commands through:

```bash
source source_me.sh && python3 ...
source source_me.sh && pytest tests/
```

`make_blog.py` independently verifies the same physical Python 3.12 boundary after relaunch. This
removed ambiguity between a successful compilation under one interpreter and a runnable pytest
environment under another.

## Publication safety challenge

The pipeline has repeatedly favored stopping over publishing a plausible but invalid fallback.
That choice created more visible failures during bring-up, but it also prevented new errors from
silently replacing the last good site.

Current safeguards include:

- One lock for the complete report-date operation.
- Typed, versioned run state with explicit phase transitions.
- Hash-bound phase reuse only for identity-checked successful artifacts.
- Failed, invalid, provisional, or `NONE` editorial outcomes remain eligible for fresh attempts.
- Independent publisher validation of schemas, hashes, paths, provenance, post structure, and
  active contract.
- Complete staged MkDocs build before installation.
- Atomic date-owned source and release replacement.
- Publication receipt written last.
- No bundle or import after model failure or deterministic candidate rejection.

The downside is that a stale local file mode, schema mismatch, or old receipt can block a run. The
upside is that those problems are visible and cannot quietly mutate the served site.

## Tests, audits, and documentation work

This change set went through several rounds of implementation review because many early tests and
fixtures were more fragile than the behaviors they claimed to protect.

The repository's permanent-test policy was applied explicitly:

- Fast pytest covers parser logic, immutable contract behavior, deterministic validation, and
  boundary enforcement.
- Real Git, subprocess orchestration, publisher round trips, MkDocs builds, and whole-pipeline flows
  live in direct E2E runners.
- One-time capture, calibration, live route, screenshot, and migration checks remain operational
  evidence rather than permanent tests.
- Tests that froze prompt prose, tunable limits, current fixture identities, mock-only end-to-end
  paths, duplicate hygiene, or filesystem orchestration in the fast lane were removed or moved.

The implementation was reviewed in repeated independent passes for plan fidelity, test lifetime,
Python and repository style, documentation, legacy-path removal, comments, ownership, and security.
Findings led to changes such as:

- Moving real Git work to E2E.
- Removing unsafe hardcoded temporary paths.
- Pinning roster and private-artifact reads against path replacement.
- Revalidating reused rosters and bundles.
- Retaining quiet eligible repositories in experiment fixtures.
- Removing unreachable generator-identity branches.
- Splitting large experiment, attestation, calibration, and private-output responsibilities into
  owning modules.
- Removing obsolete schedules, wrappers, tests, aliases, and bundle identity concepts.

Test totals changed as the design and suite changed. Important checkpoints included:

| Checkpoint | Evidence |
| --- | --- |
| Initial exact-Git producer/publisher cutover | Focused producer and importer tests plus strict MkDocs E2E passed; broader suites still had established unrelated failures |
| Clean v2 live August 26 import | Producer daily-blog tests, publisher importer tests, strict MkDocs build, and idempotent schedule reconciliation passed |
| Authoritative roster and new-repository repair | Fresh 111-repository snapshot, 111 verified mirror origins, focused tests, and August 26 real-Git E2E passed |
| Final maker-work audits | Multiple full producer runs exceeded 2,000 passing tests; direct E2E aggregates ranged from 6 to 17 as obsolete runners were removed and contracts changed |
| Date-owned publication rebuild | Producer 2,345 tests, 17 direct E2Es, publisher 1,278 tests, and strict MkDocs build were recorded as passing at that checkpoint |
| Current runtime-token change | 12 focused credential/discovery/integration tests, 633 structural checks, and 247 ASCII checks passed; authenticated quota was 5,000 |

Counts are historical evidence for specific working-tree states, not cumulative guarantees. Any
final activation should rerun the current focused suite, full producer suite, direct E2Es, publisher
suite, and strict build from the final recorded tree.

The repository documentation and screenshots were also refreshed. Two 1280x800 work-log images are
captured through a local Playwright harness that checks HTTP status, page identity, full header
visibility, file size, and byte-identical repeat capture.

## Approaches tried and their disposition

| Approach | Result | Disposition |
| --- | --- | --- |
| Extend the old broad local LLM pipeline | Wrong model ownership for the revived blog | Retired from the daily-blog path |
| M2 claims, M3 Hermes skill, M4 standalone site | Proved explicit-date evidence and validation but duplicated the live system | Superseded by the producer/publisher pipeline |
| Keep generation in the MkDocs repository | Blurred content generation and publication ownership | Replaced by producer bundles and publisher import |
| Pass complete prompt on the command line | Failed with OS argument-size limit | Replaced by stdin transport |
| Layered editorial plus fallback publishing | Could leave generic content visible after failure | Removed; editorial failures stop publication |
| One author | No independent choice or quality comparison | Replaced by two isolated authors and anonymous referee |
| Long style-rule prompt | Produced compliant but mechanical prose | V4 uses a short maker brief plus examples |
| Give author and referee the same document | Encouraged authors to optimize for scorecard wording | Split author brief/examples from referee rubric |
| Repository list from config or stale cache | Missed newly created `cancer-clicker` | Replaced by fresh authoritative owner roster |
| Anonymous GitHub requests | Exhausted the small public quota before repository discovery | Removed; runtime authentication is mandatory |
| Global evidence budget only | Could starve a small or new active repository | Reserve one citable item per active repository first |
| Hermes cron owns daily publication | Hidden wrapper drift called deleted paths | Removed as schedule owner |
| systemd plus backlog cursor | Worked but duplicated date identity with scheduling state | Replaced by direct `--yesterday` and explicit-date runs |
| `bundle_id` as publication identity | Made replacement and concurrency unnecessarily confusing | Removed; date is the identity |
| Store GitHub token in `settings.yaml` | Mixed durable configuration and runtime secret material | Replaced in working tree by runtime credential loader |
| Source the entire Hermes `.env` in systemd | Would expose unrelated credentials | Rejected |
| Wrap `make_blog.py` in Hermes to inherit the GitHub token | Hermes intentionally strips GitHub tokens from children; also confuses scheduling and model roles | Rejected |
| Add a Hermes `API_SERVER_KEY` to the editorial project | Solves an HTTP API problem the CLI route does not have | Rejected for current author/referee workflow |
| Rely on process-local asynchronous capacity refresh | Fresh CLI selects before capacity data can affect ranking | Confirmed defect; repair with Hermes-owned shared state and bounded cold refresh |
| Preserve every test and fixture | Kept fragile snapshots and mock orchestration alive | Pruned using permanent-test criteria |

## What is working now

The following design pieces have concrete evidence behind them:

- One producer and one publisher have explicit ownership.
- `make_blog.py` is the single root manual and scheduled entry point.
- Systemd, not Hermes, is the intended schedule owner.
- Report date is the sole publication identity.
- GitHub owner discovery bypasses stale list cache.
- The read-only token can authenticate PyGithub with a 5,000-request core quota.
- Repository roster snapshots are immutable and independently verified.
- Owner-qualified mirrors have exact-origin validation.
- Exact Git revision ranges handle divergent same-day branches.
- Dated changelogs and changed documentation can anchor the story.
- A newly created repository has a typed lifecycle and salience path.
- Every active repository can retain at least one citable source.
- Authors and referee receive bounded, role-specific stdin prompts.
- Every author/referee route explicitly enters the `openai-codex` provider through Hermes.
- The Hermes stdin transport is proven; capacity-aware first selection remains an open core repair.
- Invalid model output cannot create a bundle or replace the site.
- The sibling publisher validates, strict-builds, and atomically installs a release.
- The experimental maker-voice prompt, examples, rubric, calibration contract, capture contract, and
  attestation contract exist without changing the current publication contract.

## What remains unresolved

### 1. Hermes cold-process account selection needs its core repair

The provider route is correct, but a fresh CLI process cannot use capacity-aware ranking before its
first request because the current cache is process-local and refreshed too late. Hermes needs the
shared sanitized snapshot, bounded cold refresh, atomic persistence, and fresh-process verification
described above. This is account-selection correctness, not a transport or project-credential issue.

### 2. The roster lock needs an explicit one-time repair

The exact existing lock must be changed from `0664` to `0600`. The current hardened code is doing
what it was designed to do by rejecting it.

### 3. August 27 is still unpublished

The 07:00 UTC run exposed the old unsupported unauthenticated path by exhausting GitHub's public
quota. That path is removed. The 16:06 UTC manual run failed on the unsafe roster capture lock. Both
failures occurred in `repository_discovery`. No mirrors, evidence, authors, referee, bundle, or
publisher import ran for August 27.

### 4. The verified Hermes route has not completed a full current workload

The `HERMES_ROUTE_OK` transport smoke is healthy, but the old 24-call attempt produced no candidates.
After the Hermes pool repair and roster-lock migration, the next real publication run will show
whether current authoring completes two full author prompts and the referee. The exact-key GitHub
loader, mandatory client boundary, and authenticated quota check already pass. The separate v4
experiment still needs live capture and calibration.

### 5. The experimental maker voice is not active

The current editorial contract remains active. The experimental maker-voice contract needs a passing
live calibration, a current busy-and-quiet capture, route-free attestation, a stable winner, review
against the central maker question, and a separate producer/publisher activation change. Publication
identity remains the date; activating a new editorial contract changes how the next replacement is
generated rather than creating a second version of that date.

### 6. Installed systemd state should be reconciled on the host

The checked-in service and timer reflect the intended 04:00 direct command. The user systemd bus was
not accessible from every assisted environment, so installed unit contents, enablement, next fire
time, and lingering user-service behavior should be checked directly on Aella.

### 7. The working tree needs a coherent final review and commit

The repository contains a large set of staged, unstaged, added, modified, and deleted files from the
pre-production rebuild. The final tree should be reviewed as one design, not committed as unrelated
partial patches.

## Recommended final bring-up sequence

The remaining operational sequence should be short and deterministic.

1. Complete the upstream-quality Hermes core repair: shared sanitized capacity state, one bounded
   cold refresh when no usable state exists, background refresh only with a usable snapshot, atomic
   cross-process persistence, deterministic fallback, cooldown exclusion, and credential-rotation
   invalidation.

2. Verify the repaired pool through real fresh processes:

   - A cold process selects the highest-ranked eligible account.
   - A second process inside ten minutes reuses the snapshot without probing.
   - A rate-limited account is excluded.
   - Data older than three hours do not drive ranking.
   - Rotating one credential invalidates only its corresponding snapshot.

3. Repair only the known lock file:

   ```bash
   chmod 600 out/vosslab/daily_blog_repository_rosters/.capture.lock
   ```

4. Confirm the token loader without printing the token:

   ```bash
   source source_me.sh && python3 -c \
     'from podlib import runtime_credentials; runtime_credentials.get_github_token(); print("GITHUB_TOKEN available")'
   ```

5. Run August 27 interactively:

   ```bash
   ./make_blog.py --date 2026-08-27
   ```

6. Inspect the new run's `run_state.json` and `events.jsonl`. If it fails, use the phase to keep the
   diagnosis narrow:

   - `repository_discovery`: token, GitHub response, roster validation, or roster snapshot.
   - `mirror_refresh`: local mirror ownership, origin, or exact Git object availability.
   - `activity_location` or `evidence_assembly`: report-day identity or source extraction.
   - `editorial_projection`: evidence budgeting or projection contract.
   - `author_generation`: Hermes command, provider quota, timeout, or empty output.
   - `candidate_validation`: deterministic post contract.
   - `referee_selection`: Hermes referee command or structured result.
   - `bundle_creation`: date-owned artifact transaction.
   - `site_import`: sibling validation, MkDocs build, or atomic installation.

7. Confirm the publisher contains a `2026-08-27` post, publication receipt, date-owned release, and
   strict built site before treating the run as complete.

8. Reconcile and enable the checked-in systemd unit only after the manual path completes:

   ```bash
   systemctl --user daemon-reload
   systemctl --user cat vosslab-daily-publication.service
   systemctl --user cat vosslab-daily-publication.timer
   systemctl --user enable --now vosslab-daily-publication.timer
   systemctl --user list-timers --all
   ```

9. Treat the maker-voice experiment as a separate quality project. Complete its live calibration,
   fresh capture, attestation, and review without coupling that work to basic publication reliability.

## Definition of done

The pipeline is operationally up when all of these statements are true:

- A cold fresh Hermes process selects the highest-ranked eligible account, and a second fresh
  process inside the refresh interval reuses the shared sanitized snapshot without probing.
- A manual explicit-date run completes from GitHub discovery through strict publisher import.
- The published post includes a same-day new repository when its evidence makes it the interesting
  story candidate.
- A failed model or validation phase leaves the prior served site unchanged.
- A second noninteractive run for the same coherent date exits successfully without regeneration.
- An interactive replacement requires exact `y` and atomically replaces the date.
- The installed timer calls only `./make_blog.py --yesterday` at 04:00 America/Chicago.
- The timer requires no interactive approval and no Hermes scheduler.
- GitHub authentication is runtime-only and no token appears in settings, logs, artifacts, URLs, or
  generated prose.
- Current producer tests, direct E2Es, publisher tests, strict MkDocs build, and unit verification
  pass from the final tree.
- Current versus experimental editorial status is explicit; basic publication reliability does not
  imply maker-voice activation.

The pipeline is editorially successful when the resulting post also passes the central human test:
it reads like a maker describing work they care about, not a system reciting a development ledger.

## Source record

The primary local sources for this report are:

- `CODEX_CHAT_TRANSCRIPT.txt`
- `docs/CHANGELOG.md`
- `docs/archive/DAILY_BLOG_PIPELINE_FIXUP_PLAN.md`
- `docs/archive/BETTER_PROMPT_PLAN.md`
- `docs/archive/PROMPT_EXPERIMENT_STATUS.md`
- `docs/DAILY_BLOG_OPERATIONS.md`
- `docs/DESIGN_DECISIONS.md`
- `pipeline/daily_blog/`
- `pipeline/podlib/github_client.py`
- `pipeline/podlib/runtime_credentials.py`
- `deploy/vosslab-daily-publication.service`
- `deploy/vosslab-daily-publication.timer`
- `out/vosslab/daily_blog_runs/2026-08-27/`
- `/home/vosslab/nsh/vosslab-daily-blog/data/publications/`

External implementation references consulted during the credential investigation:

- [Hermes secrets documentation](https://hermes-agent.nousresearch.com/docs/user-guide/secrets/)
- [Hermes command helper secret source](https://hermes-agent.nousresearch.com/docs/user-guide/secrets/command)
- [Hermes API server](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server)
- [GitHub REST API authentication](https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api)
- [GitHub credential guidance](https://docs.github.com/en/rest/authentication/keeping-your-api-credentials-secure)

No credential values are included in this report.

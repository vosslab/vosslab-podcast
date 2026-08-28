# Code architecture

## Purpose

This repository contains two content systems. The established GitHub-to-podcast pipeline creates
outlines, posts, social copy, scripts, and audio. The daily publication subsystem is a separate,
date-driven producer that owns evidence through local site import.

## Daily publication boundary

```text
durable Git caches
        |
        v
mirror refresh -> activity -> authoritative evidence packet
                                      |
                                      v
                         bounded editorial projection
                              |                 |
                              v                 v
                           author A          author B
                              |                 |
                              +-------> validation
                                           |
                                           v
                         candidate-cited excerpts -> referee
                                                   |
                                                   v
                                          immutable bundle
                                                   |
                                                   v
                                    daily-blog bundle importer
                                                   |
                                                   v
                                        local MkDocs release
```

The publication bundle is the complete cross-repository interface. Producer code has no direct
write path into the publisher's `docs/`, `data/`, `generated/releases/`, or `site` locations.

## Entry point and orchestration

`automation/publish_daily_blog.py` parses one required report date, loads `settings.yaml`, and calls
`daily_blog.orchestrator.run_daily_publication`. The scheduled
`automation/publish_scheduled_daily_blog.py` command computes yesterday in the configured timezone,
then asks `daily_blog.schedule` to reconcile a bounded oldest-first backlog through the same
orchestrator. The orchestrator creates one unique run record and executes the nine legal phases in
order. It persists state before and after each phase so a failure has an inspectable owner and input
identity.

The systemd service uses the schedule reconciler; manual repair uses the explicit-date command. A
schedule lock owns cursor advancement, and a per-date lock surrounds each complete workflow,
including the publisher import. The cursor advances only after the publisher record proves success.
An existing publisher record resolves a crash after import but before cursor persistence without
generating the date again.

## Run observability

Every producer invocation that enters the orchestrator creates one durable run directory under
`out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/`. Its `run_state.json` is the authoritative phase
state and its `events.jsonl` is an append-only operational timeline when that secondary sink is
available. The same JSON event lines go to standard output, so the user service retains them in
`journalctl`. File and stdout event failures are independent and cannot overturn authoritative phase
or publication state; a bounded sink warning goes to standard error when available.

The structured event stream records run creation, each phase start, completion or cache reuse, a
safe phase failure class, and terminal bundle/import status. Structured `daily_publication.*` events
contain the run ID and run-state path but omit raw exception messages. Use the run-state record for
the bounded detailed failure. The process still re-raises failures, so ordinary traceback lines on
service standard error can contain exception text even though the structured event objects do not.

The schedule owner has a separate durable `daily_blog_schedule_events.jsonl` stream. It records
activation start, cursor reconciliation, each skipped or attempted date, successful publisher
receipt discovery, cursor advancement, terminal backlog state, and bounded failure classes. Its file
and stdout sinks are also best-effort, so schedule logging cannot change publication or cursor state.

## Component boundaries

| Component | Responsibility | Main output |
| --- | --- | --- |
| `config.py` | Validate repositories, identities, routes, timezone, and three limit maps | `DailyBlogConfig` |
| `mirrors.py` | Lock, clone when configured, refresh, and fingerprint physical Git caches | Refresh manifest |
| `activity.py` | Locate exact attributed commits in one local calendar day | `RepositoryActivity` records |
| `evidence.py` | Read changelogs, docs, diffs, screenshots, and metadata from Git objects | `EvidencePacket` and asset bytes |
| `projection.py` | Split, rank, and fairly select exact source slices | `EditorialProjection` |
| `editorial.py` | Run two authors, validate candidates, anonymize, and invoke the referee | `EditorialDecision` |
| `candidates.py` | Enforce final post structure and projected evidence references | Validation issues |
| `evaluation.py` | Run historical non-publishing comparisons against current contracts | Immutable shadow scorecard |
| `bundles.py` | Hash and atomically promote the cross-repository contract | Immutable bundle directory |
| `publisher.py` | Invoke the publisher-owned importer through its environment | Import result |
| `schema.py` | Define evidence, activity, phase, and run contracts | Typed serialization |
| `run_state.py` | Persist the authoritative run and phase artifacts | Run directory |
| `locks.py` | Coordinate per-cache/per-date ownership and phase reuse | Locks and hash cache |
| `schedule.py` | Reconcile missed dates and advance the success cursor | Schedule state |

## Evidence authority

Authority is data, not prompt convention. Each `EvidenceItem` carries a kind, authority level,
numeric rank, repository, commit, path, blob hash, content hash, content, and acquisition source.
The fixed descending order is:

1. `dated_changelog`
2. `changed_documentation`
3. `diff`
4. `readme_context`
5. `screenshot`
6. `commit_metadata`

Matching `docs/CHANGELOG.md` date sections remain complete. Supporting sources receive explicit
per-kind, per-item, total, and screenshot collection limits before the packet is hashed. The complete
evidence v3 packet remains authoritative and is never reduced for storage.

Evidence schema v3 represents every attributed commit-to-parent edge as an exact revision range.
Root commits use an empty base, and every attributed branch tip is an explicit snapshot revision.
Providers read those ranges and snapshots independently, then deduplicate identical blobs. This
preserves work from non-linear same-day histories without treating one repository-wide base/final
range as a complete history.

## Editorial trust boundary

Prompt templates and the rubric live in `pipeline/prompts/`, separate from Python code. Template
validation requires affirmative phrasing, an explicit output contract, evidence hierarchy, and
bounded evidence placeholders.

The shared `podlib.prompt_loader` validates direct desired-outcome language for the broad content
pipeline. The daily editorial loader applies the same policy to author, referee, repair, rubric, and
shadow templates. Model-facing instructions name the action, source, structure, and output that
contribute to the requested result.

Projection v1 deterministically splits oversized evidence into exact source slices. Every excerpt
records source offsets, source and excerpt hashes, authority, repository, commit, and path. The
coverage-first policy reserves one highest-authority citable excerpt for every active repository and
fails when the context envelope cannot retain all of them; remaining capacity is filled by descending
authority with stable repository round robin. Compact repository cards remain present for every
active repository even when the rendered referee context filters excerpts to the IDs cited by
candidates. The complete projection context stays within `projection_limits.context_chars`.

Each configured role runs in a fresh subprocess with its prompt on standard input. Route
configuration owns transport only. Hermes routes require `--ignore-rules` and reject profile skills,
saved sessions, and inline query arguments, making the repository templates the sole editorial
instruction source.

Complete author and referee prompts are checked against their own envelope limits after templates,
rubric, projection context, and candidates are rendered. Deterministic final-candidate validation
checks projection-bound front matter, date/run consistency, a specific thematic H1, a compact index
opening, 350-650 narrative words, two to four thematic sections, complete active-repository
coverage, MkDocs structure, and projected evidence IDs on prose paragraphs. Only valid candidates
enter the anonymous A/B mapping, and the selected candidate is published byte-for-byte. The referee's
winner, evidence-quality label, and confidence are publication controls; its explanatory reason is
non-controlling metadata and is deterministically bounded before persistence.

The tuned author prompt uses `thematic-lowercase-slug` as a literal output sentinel. A deterministic
producer adapter replaces only that exact sentinel with the lowercase ASCII slug derived from the
candidate's single H1 before hashing, validation, cache storage, judging, and publication. Any
unresolved sentinel remains invalid, and the publisher independently rejects it. This keeps prompt
bytes stable while making the stored candidate and published post agree on one canonical route.

A screenshot's confined `publish_path` is itself a typed provenance binding to one projected evidence
item and one hashed bundle asset. The validator rejects every image path outside that mapping; it does
not require the model to repeat the same evidence identity in a nearby HTML comment.

Editorial approval is a hard publication boundary. `EditorialBlockedError` ends the current phase
when prompts overflow, a route fails, no candidate validates, the referee returns `NONE`, or the
referee does not choose an available A/B label. Those runs retain state and events but never create
or import a bundle.

`evaluation.py` owns historical shadow runs. It reuses exact-Git evidence and the production
editorial roles, compares the selected post with a preserved reference through a versioned
evaluator prompt, and atomically writes a typed scorecard under `daily_blog_shadow`. This path never
calls the publisher. Exact-Git evidence crosses the author routes, and the historical post plus
evidence cross the referee route, only when `shadow_evaluation.external_model_data_sharing` is
explicitly enabled; the default-deny setting stops before any model subprocess call.

The scorecard retains deterministic structure and provenance measurements plus the bounded semantic
assessment. Historical comparisons support human editorial review without becoming a permanent
schedule dependency. The production service remains date-driven and contains no fixed historical
dates or editorial score threshold.

## Durable contracts

`schema.py` versions the generator v2, prompts and rubric v3, evidence packet v3, editorial
projection v1, bundle v2, and run record v2. Packet, projection, and bundle identities are canonical
JSON SHA-256 hashes. The generator revision is a 64-character lowercase SHA-256 fingerprint of the
exact producer source, configuration, projection policy, and prompt/rubric bytes that define the
publication contract; uncommitted source changes therefore invalidate reuse. Exact Git object,
excerpt, and asset identities stay in the bundle so the publisher can verify them independently. The
referee record maps anonymous labels to candidate summaries, allowing the importer to prove the final
post hash is the exact valid candidate selected during judging.

Run records distinguish mutable execution state from immutable outcomes. A new invocation gets a new
run ID. Hash-verified cache envelopes bind each reusable value to its canonical input and output
hashes. Activity, evidence, and editorial projections reuse exact inputs; fully valid author and
validation artifacts reuse their stable projection identity; approved referee decisions reuse their
exact candidate mapping. Blocked editorial attempts remain eligible for a fresh run. A complete prior
bundle is reused only after its manifest, evidence, projection, post, assets, schema, and generator
revision are independently revalidated. The site importer always runs and reports an idempotent
result when the same bundle is already installed.

## Failure containment

Mirror, evidence, editorial, bundle, and import failures are phase-local and retained in the run
record. Bundle staging prevents partial producer output. The publisher performs its own independent
schema and hash validation, serializes imports with a publisher-owned lock, stages a complete MkDocs
tree, and builds strictly before atomically changing source or the served release. It records an
install transaction for crash recovery and installs the success record last, so a partial commit
cannot advance the producer schedule cursor.

## Extension points

- Add an evidence source as a provider that emits `EvidenceItem`; assign its authority in the schema
  and publisher contract together.
- Add a model route through transport-only `RoleRoute` configuration while preserving standard-input
  prompt delivery, instruction isolation, exactly two authors, and one independent referee.
- Revise editorial behavior by adding versioned prompt and rubric files and advancing the declared
  contract versions.
- Advance bundle, evidence, or projection schemas in producer and importer together; the current
  producer emits bundle v2 with evidence v3 and projection v1.

## Established content pipeline

The non-daily pipeline remains orchestrated by `automation/run_local_pipeline.py`. Its stages under
`pipeline/` fetch GitHub data, summarize changelogs, create daily outlines, compile a reporting
window, generate text outputs, and optionally render audio. It shares `settings.yaml` and the
user-scoped `out/<user>/` convention, but it does not participate in the daily publication bundle.

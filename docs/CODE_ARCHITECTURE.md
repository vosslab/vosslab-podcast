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
mirror refresh -> activity -> evidence packet -> author A -----+
                                      |                         |
                                      +-------> author B -----+ |
                                                             v v
                                                validation -> referee
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
`daily_blog.orchestrator.run_daily_publication`. The orchestrator creates one unique run record and
executes the eight legal phases in order. It persists state before and after each phase so a failure
has an inspectable owner and input identity.

The public command and the systemd service use the same entry point. A per-date file lock surrounds
the complete workflow, including the publisher import.

## Component boundaries

| Component | Responsibility | Main output |
| --- | --- | --- |
| `config.py` | Validate repository paths, identities, routes, timezone, and budgets | `DailyBlogConfig` |
| `mirrors.py` | Lock, clone when configured, refresh, and fingerprint physical Git caches | Refresh manifest |
| `activity.py` | Locate exact attributed commits in one local calendar day | `RepositoryActivity` records |
| `evidence.py` | Read changelogs, docs, diffs, screenshots, and metadata from Git objects | `EvidencePacket` and asset bytes |
| `editorial.py` | Run two authors, validate candidates, anonymize, and invoke the referee | `EditorialDecision` |
| `candidates.py` | Enforce post structure and evidence references; render provisional posts | Validation issues or fallback post |
| `evaluation.py` | Run historical non-publishing comparisons against current contracts | Immutable shadow scorecard |
| `bundles.py` | Hash and atomically promote the cross-repository contract | Immutable bundle directory |
| `publisher.py` | Invoke the publisher-owned importer through its environment | Import result |
| `schema.py` | Define evidence, activity, phase, and run contracts | Typed serialization |
| `run_state.py` | Persist the authoritative run and phase artifacts | Run directory |
| `locks.py` | Coordinate per-cache/per-date ownership and phase reuse | Locks and hash cache |

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
per-kind, per-item, total, and screenshot budgets before the packet is hashed. Both authors and the
referee receive the same immutable packet identity.

Evidence schema v2 represents every attributed commit-to-parent edge as an exact revision range.
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

Each configured role runs in a fresh subprocess with its prompt on standard input. Route
configuration owns transport only. Hermes routes require `--ignore-rules` and reject profile skills,
saved sessions, and inline query arguments, making the repository templates the sole editorial
instruction source.

Deterministic final-candidate validation checks front matter, date/run consistency, a compact index
opening, 350-650 narrative words, two to four thematic sections, complete active-repository
coverage, MkDocs structure, and evidence IDs on prose paragraphs. These editorial shape gates apply
to final candidates; the provisional work log retains its intentionally compact evidence-first
contract. Only valid candidates enter the anonymous A/B mapping. The selected candidate is
published byte-for-byte. `NONE` produces the deterministic provisional work log.

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

`schema.py` versions the generator, prompts, rubric, evidence packet, bundle, and run record. Packet
and bundle identities are canonical JSON SHA-256 hashes. Exact Git object and asset identities stay
in the bundle so the publisher can verify them independently. The referee record maps anonymous
labels to candidate summaries, allowing the importer to prove the final post hash is the exact valid
candidate selected during judging.

Run records distinguish mutable execution state from immutable outcomes. A new invocation gets a new
run ID. Hash-verified cache envelopes bind each reusable value to its canonical input and output
hashes. Activity and evidence reuse exact inputs; fully valid author and validation artifacts reuse
their stable editorial identity; final referee decisions reuse their exact candidate mapping.
Invalid candidates, route failures, and `NONE` decisions remain eligible for a fresh editorial
attempt. A complete prior bundle is reused only after its manifest, evidence, post, assets, schema,
and generator revision are independently revalidated. The site importer always runs and reports an
idempotent result when the same bundle is already installed.

## Failure containment

Mirror, evidence, editorial, bundle, and import failures are phase-local and retained in the run
record. Bundle staging prevents partial producer output. The publisher performs its own independent
schema and hash validation, stages a complete MkDocs tree, and builds strictly before atomically
changing source or the served release.

## Extension points

- Add an evidence source as a provider that emits `EvidenceItem`; assign its authority in the schema
  and publisher contract together.
- Add a model route through transport-only `RoleRoute` configuration while preserving standard-input
  prompt delivery, instruction isolation, exactly two authors, and one independent referee.
- Revise editorial behavior by adding versioned prompt and rubric files and advancing the declared
  contract versions.
- Advance bundle or evidence schemas in producer and importer together; the current importer accepts
  bundle v1 with evidence v2.

## Established content pipeline

The non-daily pipeline remains orchestrated by `automation/run_local_pipeline.py`. Its stages under
`pipeline/` fetch GitHub data, summarize changelogs, create daily outlines, compile a reporting
window, generate text outputs, and optionally render audio. It shares `settings.yaml` and the
user-scoped `out/<user>/` convention, but it does not participate in the daily publication bundle.

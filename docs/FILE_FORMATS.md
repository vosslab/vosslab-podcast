# Daily blog file formats

## Purpose

This guide describes the durable daily-blog artifacts that cross an operator, recovery, or
producer-publisher boundary. Validators in the owning code are authoritative. Private working files
and cache entries are implementation details, not interchange formats.

For operating a run, see [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md). For output locations,
see [OUT_DIRECTORY_ORGANIZATION_SPEC.md](OUT_DIRECTORY_ORGANIZATION_SPEC.md).

## Configuration input

`settings.yaml` supplies the operator-owned `daily_blog` configuration. It selects the report
timezone, repository and mirror roots, account owner, bounded collection and projection limits,
and the bounded reliability and route settings for editorial stages. The configuration loader rejects
unknown or malformed values. Credentials, raw provider responses, and routing capacity state are not
publication artifacts.

`report_date` is the only publication identity. A digest binds bytes to that date; it never creates a
second publication namespace.

## Evidence and projection

### Daily active roster

`daily_active_roster.json` is the machine-owned Step 0 authority for repositories with commits on the
report date. It records the owner, report date, ordered active repositories, and each exact commit SHA
returned by `user:<owner> author-date:<report_date>`. Commit-message previews contain only the first
line and are capped at 160 characters. Its content-derived `active_roster_id` makes accidental drift
observable without making imperfect LLM coverage a publication-stopping gate. Downstream evidence
uses these repository/SHA pairs directly; Markdown and model output never define roster membership.

`mirror_manifest.json` records each active repository's concrete refresh outcome. An individual
clone or fetch failure is recorded there, where it occurs; recovery state does not become a parallel
repository roster or redefine the machine-observed report-day membership.

The sealed producer-publisher bundle includes `daily_active_roster.json` and binds its
`active_roster_id` and content hash in `bundle.json`. This is provenance only: the publisher does not
require model prose or downstream editorial artifacts to reproduce the active repository set.

### Repository roster

`repository_roster.json` records the authoritative repository universe for a run. Its schema is
`vosslab.daily-blog.repository-roster.v1`. A roster has a content-derived `roster_id`; its records
carry the canonical repository identity and collection-relevant Git metadata.

The producer retains a verified roster snapshot and binds the sealed roster copy into a publication
bundle. Readers validate the roster before accepting activity, evidence, or projection data that
depends on it.

### Evidence packet

`evidence.json` is an immutable `EvidencePacket` with schema
`vosslab.daily-blog.evidence.v4`. Its `packet_id` is the canonical hash of the packet content. It
binds the report date and timezone to complete collection state, collection limits, mirror metadata,
attributed activity, and authority-ordered evidence items.

Each evidence item carries source repository and Git provenance, a source path and blob identity,
content identity, acquisition and authority metadata, and any approved asset or publish path. Content
may be bounded or truncated under the packet limits. A consumer recomputes the packet identity rather
than trusting a filename or caller-provided identifier.

### Editorial projection

`editorial_projection.json` is the bounded editorial view of one packet. Its schema is
`vosslab.daily-blog.editorial-projection.v2`; `projection_id` is its canonical content hash. It binds
the packet identity, report identity, projection limits, repository cards, and exact evidence excerpts.

An excerpt preserves its source evidence identity and Git provenance together with source and excerpt
hashes, offsets, and text. The projection is grounded editorial input, not an instruction that a
particular repository or signal must appear in the post.

### Editorial artifact

An eligible whole-post artifact has schema `vosslab.daily-blog.editorial-artifact.v1`. It binds an
artifact type, report date, packet identities, repositories, evidence references, content, and a
canonical `artifact_id`. Stage-local eligibility derives scope from cited evidence that resolves
against authoritative packets under the stage-owned repository ceiling; a model-provided scope marker
must equal that derived scope and cannot grant authority. Final `CompletePost` admission is separate:
it uses the frozen `PublicationSurface` made from the exact Stage-6 survivor packets, its
`vosslab.daily-blog.bounded-evidence-context.v2` context, and promoted Stage-5 source artifacts. The
surface derives one aggregate packet, required
repository coverage, allowed evidence and image paths, and a sealed projection that includes every
evidence identity already visible through a promoted source artifact. Final citations demonstrate
grounding inside that surface; they cannot reduce its required coverage. The full repository roster
remains sealed provenance context, not extra final-post scope. Validation also verifies report identity
and embedded-asset provenance before an artifact can become the selected post.

Author, referee, and repair work may produce several private artifacts. Only the selected eligible
`CompletePost` crosses the publication boundary; candidates, reviewer comparisons, and route labels do
not.

Authored-body policy findings remain available as candidate-local repair guidance. They do not make a
mechanically valid, evidence-grounded `CompletePost` ineligible. Provenance, authority, repository
scope, path confinement, approved image paths, metadata, and source-safety checks remain enforced at
their deterministic boundaries.

### Bounded editorial contexts

The run directory retains `stage5_evidence_context.json`, `stage5_repository_context.json`, and
`stage6_prompt_context.json` as inspectable prompt-projection evidence. They are run-owned audit and
resumption artifacts, not producer-publisher handoff formats. The Stage-5 repository context keeps a
fair exact-prefix projection for every retained story and outline; each direct comparison derives a
pair-specific story, outline, and evidence context from the same sources.

`stage6_prompt_context.json` binds the promoted daily outline, retained repository stories, and
survivor evidence projection through separate provenance and model-context identities. The shared
scale maximizes usable source text while keeping each complete primary and recovery frame within
60,000 characters. Its source identities are validated against the same `PublicationSurface` that
later governs citations, screenshots, repository coverage, and admission.

### Stage-6 attempt topology

`vosslab.daily-blog.stage6-attempt-plan` is the in-memory capacity and ordering contract for
complete-post work. One immutable maximum plan expands the configured writer, editor, reviewer,
same-request retry, fresh-batch, and recovery-rung policy before route dispatch. The policy accepts
one through three fresh batches and reserves at most 10,000 semantic attempts and 40,000 physical
route calls. Transport retries keep the same semantic slot identity.

Candidate-dependent work is admitted through a `MaterializedStage6AttemptPlan`. It retains canonical
maximum-plan order and includes only generation slots whose inputs exist and optional review slots
bound to an ordered pair of distinct candidate SHA-256 witnesses. A materialization cannot add or
reorder work.

Stage-6 route-cache entries use `vosslab.daily-blog.route-cache`. Their identity binds the attempt
plan, materialized slot, prompt digest, ordered actual candidate digest, route name, and route
execution contract.
The witness retains hashes rather than prompt, candidate, reviewer-response, or provider text.

## Run state and observability

### Run record

Every attempt owns `run_state.json` under its date-owned run directory. It uses schema
`vosslab.daily-blog.run` and is the authoritative resumable lifecycle record. It records the run
and report identities, ordered phase states, evidence and bundle references, editorial reliability
summaries, the current `best_artifact_id`, an outcome, and a safe failure classification when needed.
The pre-production reader accepts only this current shape.

Each editorial summary uses `vosslab.daily-blog.editorial-reliability`. Its `rejection_counts`
contains at most 64 sorted, unique canonical `{code, count}` entries. Each code is a bounded
machine-readable category, and each positive count is no greater than the step's attempted count;
the field carries no candidate or provider prose.

The record's `editorial_transitions` are replayable typed incumbent operations paired one-for-one with
editorial summaries:

- `observe` records a reliability observation without changing the incumbent.
- `establish` records the first eligible selected artifact.
- `replace` records an editorially adjudicated successor with its prior artifact identity.
- `repair_publication` records a publication-validation repair separately from editorial promotion.

The validator replays every transition from an empty incumbent and requires the result to equal
`best_artifact_id`. It rejects missing, duplicated, mismatched, or type-confused transitions. Current
mutable records contain only the current phase set.

### Event journal and terminal summary

`runlog-YYYY-MM-DD.jsonl` is a bounded, append-only, canonical-JSON operational journal. It contains scalar,
redacted lifecycle observations tied to one run. It intentionally excludes raw exception text,
paths, URLs, credentials, prompt text, and provider responses. Capacity produces one explicit
truncation record instead of an unbounded log.

The date-level `summary.jsonl` journal contains one bounded terminal-summary receipt for each retained
terminal run. A receipt uses schema `vosslab.daily-blog.terminal-summary`, binds `summary_id` to the
terminal run-record digest, distinguishes completed and failed outcomes, reports verified publication
facts without diagnostic payloads. Detailed run state is retained or expired only through the validated
summary and descriptor-owned retention path.

The terminal-summary reader accepts only the current shape.

Phase cache data is resumability support, not a durable exchange protocol. The producer revalidates
cached response bytes and identities before reuse. Model/cache identity retains selected commits,
revision ranges, snapshot commits, lifecycle facts, and evidence items. It excludes mirror paths,
default revisions, ref fingerprints, object-availability inventory, and refresh observations that
do not change the editorial request.

### Recovery fault digest

An exhausted editorial recovery writes a bounded `recovery_fault.json` with schema
`vosslab.daily-blog.recovery.v6`. Its canonical digest identifies the report date, stage, safe route
observations, eligible recovery provenance, prompt and rubric identities, the typed fault category,
and the reconciled Stage-6 plan-exhaustion digest when applicable. It is a run-owned diagnostic
receipt, not a publication format or a substitute post.

## Publication handoff

The producer writes one date-owned publication directory containing:

```text
bundle.json
evidence.json
repository_roster.json
editorial_projection.json
publication_surface.json
post.md
assets/...
```

All declared files are sealed before handoff. The importer reads the manifest and declared children
through held no-follow descriptors, applies size limits, rejects missing, extra, symbolic, or
non-regular files, and validates content hashes before staging an import.

Sealed JSON artifacts use a 128-KiB envelope except `evidence.json`, whose complete immutable packet
uses a 128-MiB envelope. Producer storage, publisher transfer validation, and archived-publication
inspection apply that same evidence-specific limit, so a valid bundle remains readable at every
boundary.

Before import, the producer sends the same exact sealed transfer to the sibling's no-write validation
operation. A successful `vosslab.daily-blog.import-validation.v1` receipt contains exactly
`schema_version`, `status: valid`, `report_date`, `bundle_sha256`, and `best_artifact_id`; each value
must bind the transfer. Validation checks the complete bundle admission contract but creates no archive,
post, release, record, or `site` mutation. The importing operation revalidates those same bytes before
staging, so preflight is an integration check rather than a publication shortcut.

### Bundle v9 manifest and publication surface v1

`bundle.json` uses `vosslab.daily-blog.bundle.v9`. It is the producer-to-publisher integrity
boundary. `publication_surface.json` uses
`vosslab.daily-blog.publication-surface.v1` and is the immutable, survivor-scoped authority for
the complete post, its evidence, its repository coverage, and its images. The same surface is used
to construct the writer and editor context, admit the selected post, choose transfer assets, import
the bundle, and verify the rendered page.

The bundle's exact top-level fields are part of the protocol:

```text
schema_version
bundle_sha256
best_artifact_id
report_date
timezone
created_at
generator
contracts
evidence
repository_roster
editorial_projection
publication_surface
post
assets
maker_activation
editorial_prompt_contract
```

`bundle_sha256` is the canonical digest of this manifest with that field omitted. The `post` entry
names only `post.md`, binds its SHA-256 and `artifact_id`, and must agree with `best_artifact_id`.
The evidence, roster, projection, and surface entries bind their sealed filenames, identities, and
hashes. The `publication_surface` entry is exactly:

```text
path: publication_surface.json
surface_id: SHA-256 identity of the canonical surface value
sha256: SHA-256 identity of the canonical surface JSON value
```

The surface has exactly these fields:

```text
schema_version
surface_id
report_date
timezone
aggregate_packet_id
source_packet_ids
repositories
source_artifacts
editorial_projection_id
allowed_evidence_ids
allowed_images
```

`surface_id` is the canonical SHA-256 hash of the surface object with only `surface_id` omitted.
It therefore binds the complete survivor authority, rather than a mutable run or mirror location.
`source_packet_ids` and `repositories` are sorted, unique lists. `source_artifacts` is a sorted
list of exact attestations with `kind`, `artifact_id`, and `content_hash`; it contains one
`DailyOutline` and the promoted `RepoStory` artifacts that formed the survivor set.
`aggregate_packet_id` and `editorial_projection_id` identify the sealed packet and projection used
by the surface. `allowed_evidence_ids` is the sorted, exact set of evidence IDs in that projection's
excerpts: neither side may add, omit, or substitute an evidence identity.

Each `allowed_images` entry is a structured, canonical tuple of:

```text
evidence_id
asset_path
publish_path
```

Every entry must resolve to one screenshot in the aggregate packet whose evidence ID is allowed;
the evidence ID, transfer asset path, and public post path must all match that screenshot. The list
is sorted by this three-part tuple, and no evidence ID, `asset_path`, or `publish_path` may appear
twice. Only image paths declared by the promoted outline or repository stories enter this list.
Other screenshots may remain citable aggregate evidence without becoming required publication
assets. This avoids treating an aggregate packet's unrelated screenshots as publication authority.

`assets` is the exact allowlist of the surface's `allowed_images`: each asset manifest entry binds
its path, SHA-256, evidence ID, Git blob hash, and public path to one such image. A bundle cannot
include a packet-wide extra asset, and an allowed surface asset cannot be omitted. `generator`,
`contracts`, maker activation, and editorial prompt-contract values preserve validated producer
provenance. The
`contracts.publication_source_safety` value identifies the deterministic source-safety policy by
version and executable-vector SHA-256; the active identity is
`publication_source_safety.v1` with a 35-case executable corpus and SHA-256
`d50166736d79be7f7715cc0f7585fac71dfb2aecc1c631b10e01aeca2fb63c6b`. It makes the exact policy
applied to the post verifiable without treating the prose as a prompt contract.

The sealed transfer contains every core artifact above plus exactly the manifest-declared surface
assets. The producer's no-write validation and the publisher's import both revalidate that held,
no-follow byte snapshot. The archive, installed post, and rendered-page validator retain this same
surface authority; article-local image sources must be among its `publish_path` values.

The bundle carries one validated selected post and its grounded inputs. It never carries candidate
posts, referee results, anonymous rankings, or route-to-candidate mappings.

Before a whole-post artifact is eligible, the producer applies that source-safety policy. Reader
links may target only GitHub HTTPS URLs or exact declared screenshot paths; active raw HTML,
unapproved comments, Markdown attribute lists, and ambiguous or disguised links are ineligible.
Code examples remain inert source text. The publisher independently applies the same identified
policy while importing, so an unsafe candidate cannot become publishable through bundle reuse or a
cross-repository handoff.

### Publisher record v6 and import receipt v2

The sibling `vosslab-daily-blog` repository owns the current date-keyed record at:

```text
data/publications/YYYY-MM-DD.json
```

It uses `vosslab.daily-blog.publication.v6`. The record is exact and date-keyed; it binds the
report date, timezone, bundle digest, selected artifact identity, generator run and revision,
verified evidence and projection archive paths, the public post path, import timestamp, and
`article_body_sha256`. It also binds `publication_surface_id`,
`publication_surface_sha256`, and the exact date-owned
`publication_surface_manifest` archive path. The body digest is calculated from the canonical visible
reader-body projection of the installed Markdown post using the publisher's configured MkDocs
Markdown extensions.

The producer returns `vosslab.daily-blog.import-receipt.v2` only after its one
`CommittedPublication` validation reads the held archive snapshot, date-keyed record, and installed
post together. The receipt repeats the bundle, post, selected-artifact, and reader-body digests and
names the verified rendered page. Page verification requires the complete ordered source body to
appear in the one Material article surface; matching title and date alone are insufficient.

The publisher owns the sealed date archive at
`data/publication_bundles/YYYY-MM-DD/` and the public post at
`docs/blog/posts/YYYY-MM-DD.md`. Reimporting a matching bundle is idempotent; a confirmed replacement
updates the same date-owned publication rather than creating a versioned variant.

Automated publisher failures are one bounded, text-free canonical JSON envelope with schema
`vosslab.daily-blog.import-failure.v1`, exactly `category` and `phase` alongside its schema version.
The allowed categories are `snapshot_rejected`, `publication_conflict`, `staged_build_failed`,
`commit_failed`, and `publisher_implementation_defect`; allowed phases are `receive`, `validate`,
`preflight`, `stage`, and `commit`. The protocol carries no exception text, paths, prompts, post bytes,
or raw stderr. A malformed protocol response, timeout, or failed publisher start is classified by the
producer as its own typed boundary fault rather than being treated as a publisher diagnostic.

`--replace-existing` is authorization, not an assertion that a record exists. A missing date imports
whether or not authorization is present; matching bytes are idempotent; different bytes on an occupied
date fail without authorization and replace atomically with authorization. These outcomes retain the
same date-owned identity and do not create versions.

## Identity relationships

```text
repository_roster.json -- roster_id --> daily_active_roster.json -- repository/SHA --> evidence.json
                                      |                                         |
                                      |                                         packet_id
                                      v                                         v
                                bundle.json <-------------------------- editorial_projection.json
                                                         |                     |
                                                         |                     projection_id
                                                         v                     v
selected CompletePost -- artifact_id --> publication_surface.json --> bundle.json -- bundle_sha256
                                      |              |                    |              |
                                      |              v                    |              v
                                      |      surface_id / allowed scope    |   publication v6 record
                                      |                                   |              |
                                      v                                   v              v
                             surface-scoped images ----------------> sealed transfer  import-receipt v2
                                                                                       / article_body_sha256
```

The manifest ties all sealed input hashes and the selected post to the one `report_date`; the surface
ties all downstream editorial and image authority to the same survivor set. The publisher repeats
the bundle digest, selected artifact identity, and surface identity in its date-keyed record and
binds the reader-visible body digest in its receipt, making provenance and publication integrity
independently verifiable on both sides of the handoff.

### Current reuse

The active writer and importer use the current bundle; the producer refuses to reuse a cached bundle
when its schema, source-safety policy
identity, publication surface, or sealed contents do not match the current run. Publisher
records likewise accept only the current shape. There is no runtime compatibility reader for
obsolete pre-production records.

## Maintenance rules

- Treat producer and publisher validators as the source of truth for version and field rules.
- Add a new durable format only with a named owner, a validator, identity behavior, and focused
  offline coverage.
- Keep editorial prompt prose in its human-owned contract; this format guide records machine
  identities and boundaries only.
- Update this guide when an operator-facing durable format or producer-publisher protocol changes.

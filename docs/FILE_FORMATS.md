# Daily blog file formats

## Purpose

This guide describes the durable daily-blog artifacts that cross an operator, recovery, or
producer-publisher boundary. Validators in the owning code are authoritative. Private working files
and cache entries are implementation details, not interchange formats.

For operating a run, see [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md). For output locations,
see [OUT_DIRECTORY_ORGANIZATION_SPEC.md](OUT_DIRECTORY_ORGANIZATION_SPEC.md).

## Configuration input

`settings.yaml` supplies the operator-owned `daily_blog` configuration. It selects the report
timezone, repository and mirror roots, source identities, bounded collection and projection limits,
and the bounded reliability and route settings for editorial stages. The configuration loader rejects
unknown or malformed values. Credentials, raw provider responses, and routing capacity state are not
publication artifacts.

`report_date` is the only publication identity. A digest binds bytes to that date; it never creates a
second publication namespace.

## Evidence and projection

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
canonical `artifact_id`. Eligibility validation verifies the evidence references, report identity,
and any embedded asset provenance before an artifact can become the selected post.

Author, referee, and repair work may produce several private artifacts. Only the selected eligible
`CompletePost` crosses the publication boundary; candidates, reviewer comparisons, and route labels do
not.

## Run state and observability

### Run record

Every attempt owns `run_state.json` under its date-owned run directory. It uses schema
`vosslab.daily-blog.run.v11` and is the authoritative resumable lifecycle record. It records the run
and report identities, ordered phase states, evidence and bundle references, editorial reliability
summaries, the current `best_artifact_id`, an outcome, and a safe failure classification when needed.

The record's `editorial_transitions` are replayable typed incumbent operations paired one-for-one with
editorial summaries:

- `observe` records a reliability observation without changing the incumbent.
- `establish` records the first eligible selected artifact.
- `replace` records an editorially adjudicated successor with its prior artifact identity.
- `repair_publication` records a publication-validation repair separately from editorial promotion.

The validator replays every transition from an empty incumbent and requires the result to equal
`best_artifact_id`. It rejects missing, duplicated, mismatched, or type-confused transitions. Run v10
records require an offline migration before they can be reopened.

### Event journal and terminal summary

`events.jsonl` is a bounded, append-only, canonical-JSON operational journal. It contains scalar,
redacted lifecycle observations tied to one run. It intentionally excludes raw exception text,
paths, URLs, credentials, prompt text, and provider responses. Capacity produces one explicit
truncation record instead of an unbounded log.

The date-level `summary.jsonl` journal contains one bounded terminal-summary receipt for each retained
terminal run. A receipt uses schema `vosslab.daily-blog.terminal-summary.v1`, binds `summary_id` to the
terminal run-record digest, distinguishes completed and failed outcomes, reports verified publication
facts, and projects reliability counts without diagnostic payloads. Detailed run state is retained or
expired only through the validated summary and descriptor-owned retention path.

Phase cache data is resumability support, not a durable exchange protocol. The producer revalidates
cached response bytes and identities before reuse.

## Publication handoff

The producer writes one date-owned publication directory containing:

```text
bundle.json
evidence.json
repository_roster.json
editorial_projection.json
post.md
assets/...
```

All declared files are sealed before handoff. The importer reads the manifest and declared children
through held no-follow descriptors, applies size limits, rejects missing, extra, symbolic, or
non-regular files, and validates content hashes before staging an import.

### Bundle v7 manifest

`bundle.json` uses `vosslab.daily-blog.bundle.v7`. It is the producer-to-publisher integrity
boundary, so its exact top-level fields are part of the protocol:

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
post
assets
maker_activation
editorial_prompt_contract
```

`bundle_sha256` is the canonical digest of this manifest with that field omitted. The `post` entry
names only `post.md`, binds its SHA-256 and `artifact_id`, and must agree with `best_artifact_id`.
The evidence, roster, and projection entries bind their sealed filenames, identities, and hashes.
`assets` is the complete allowlist of declared asset paths and identities. `generator`, `contracts`,
maker activation, and editorial prompt-contract values preserve validated producer provenance.

The bundle carries one validated selected post and its grounded inputs. It never carries candidate
posts, referee results, anonymous rankings, or route-to-candidate mappings.

### Publisher receipt v4

The sibling `vosslab-daily-blog` repository owns the current receipt at:

```text
data/publications/YYYY-MM-DD.json
```

It uses `vosslab.daily-blog.publication.v4`. The receipt is exact and date-keyed; it binds the
report date, timezone, bundle digest, selected artifact identity, generator run and revision,
verified evidence and projection archive paths, the public post path, and import timestamp.

The publisher owns the sealed date archive at
`data/publication_bundles/YYYY-MM-DD/` and the public post at
`docs/blog/posts/YYYY-MM-DD.md`. Reimporting a matching bundle is idempotent; a confirmed replacement
updates the same date-owned publication rather than creating a versioned variant.

## Identity relationships

```text
repository_roster.json -- roster_id --> evidence.json -- packet_id --> editorial_projection.json
                                                         |                     |
                                                         |                     projection_id
                                                         v                     v
selected CompletePost -- artifact_id --> bundle.json -- bundle_sha256 --> publication v4 receipt
```

The manifest ties all sealed input hashes and the selected post to the one `report_date`. The
publisher repeats the bundle digest and selected artifact identity in its date-keyed receipt, making
provenance and publication integrity independently verifiable on both sides of the handoff.

## Maintenance rules

- Treat producer and publisher validators as the source of truth for version and field rules.
- Add a new durable format only with a named owner, a validator, identity behavior, and focused
  offline coverage.
- Keep editorial prompt prose in its human-owned contract; this format guide records machine
  identities and boundaries only.
- Update this guide when an operator-facing durable format or producer-publisher protocol changes.

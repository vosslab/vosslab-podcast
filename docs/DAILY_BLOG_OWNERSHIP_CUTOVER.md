# Daily blog ownership cutover

## Current ownership

`vosslab-podcast` is the daily-blog producer. It owns the date lock, repository
roster and mirrors, exact-object activity collection, evidence packet, editorial
projection, independent editorial work, eligibility and promotion, selected
complete post, durable run state, and sealed publication bundle. Hermes runs
only the configured author and referee routes inside that producer-owned run.
It does not own schedule, publication identity, durable run state, or site
installation.

`vosslab-daily-blog` is the local publisher. It receives a sealed producer
bundle, validates it from held no-follow descriptors, stages the site, builds
MkDocs strictly, installs the result atomically, and records the date-owned
publication receipt and reader-visible page. The static publisher service owns
the served release. The scheduled producer entrypoint is `./make_blog.py
--yesterday`; `report_date` is the sole publication identity.

The producer retains all candidate and referee artifacts. They are useful for
editorial recovery and reliability reporting, but they are not publisher input.
The publisher neither recreates deliberation nor selects a post. It accepts one
eligible Stage-8 complete post whose artifact identity is bound to its bytes.

## Accepted maker activation

Production uses the checked-in immutable maker-activation receipt. The receipt
content-addresses the accepted F4 evidence, selects
`v4-three-examples-corpus-v2`, and binds the exact editorial prompt-contract
identity and `v4-maker` validation-policy identity. Loading it validates the
receipt and those bindings; production does not reopen private calibration or
experiment artifacts.

The historic fixture-backed calibration and attestation work is accepted
evidence for this receipt, not a live production subsystem. It has no current
command, model-route, publisher-import, or schedule role. Prompt prose remains
the separately governed editorial material described in
[HUMAN_GUIDANCE.md](HUMAN_GUIDANCE.md).

## Sealed handoff

The producer-to-publisher interface is `vosslab.daily-blog.bundle.v9`. Its
manifest binds the report date, timezone, generator identity, evidence packet,
editorial projection, repository roster, activation receipt, prompt-contract
identity, selected `best_artifact_id`, post bytes, assets, source-safety policy
identity, immutable `publication_surface.json`, and bundle digest. The surface
is the single survivor-scoped publication authority. Its canonical content and
`surface_id` bind the aggregate packet and projection identities, selected
source packets and repositories, source-artifact attestations, allowed evidence
IDs, and the one-to-one allowed screenshot evidence, asset, and publish paths.
Writer/editor context, producer admission, bundle assets, publisher staging,
and rendered-page image admission all derive from that same surface.
After producer-side descriptor validation, the producer serializes exactly that
snapshot into one bounded, hash-bound standard-input transfer. It does not give
the publisher a producer filesystem path.

The publisher validates the manifest, `publication_surface.json`, and every
declared file before staging. A new import writes the date-owned
`vosslab.daily-blog.publication.v6` record, which binds the bundle digest,
surface manifest, surface identity and hash, selected artifact identity,
generator run and revision, evidence and projection archives, installed post,
timezone, import time, and canonical `article_body_sha256`. The producer issues
`import-receipt.v2` only after one shared committed-publication validator
confirms the archive, v6 record, and installed post as one coherent snapshot.
Page verification requires the full ordered reader body and validates each
article-local rendered image against the sealed surface, not merely the expected
title and date. A rejected bundle leaves the prior published release intact.

The producer rejects a whole-post candidate with unsafe reader-visible Markdown
as editorially ineligible. The portable policy permits only GitHub HTTPS links
and declared screenshot paths, keeping code inert while rejecting active raw
HTML and disguised or ambiguous link forms. Its version and digest are sealed in
the bundle: the active `publication_source_safety.v1` identity has an executable
35-case corpus and SHA-256
`d50166736d79be7f7715cc0f7585fac71dfb2aecc1c631b10e01aeca2fb63c6b`. The publisher performs
its own check before it stages a site. Cache reuse fails closed across this v9
policy and survivor-surface boundary while remaining keyed to semantic
editorial inputs rather than mutable mirror inventory.

New imports use bundle v9 and publication-v6. Historical records remain
read-only inspection inputs: they can identify an occupied legacy date for
inspection or replacement, but cannot originate a new import. A confirmed
same-date replacement creates one current v9/v6 snapshot for that report date.

## Operational boundary

One run owns a report date at a time. A confirmed same-date run replaces the
generated result for that date rather than creating a versioned publication.
Expected author, referee, and repair failures are recorded as editorial
degradation while eligible grounded work continues. Invalid provenance,
identity, configuration, cache, or storage state is a pipeline fault and does
not produce a mechanical prose fallback.

The systemd timer invokes the producer at 04:00 America/Chicago. Scheduling,
model routing, editorial decision-making, and publication installation remain
separate owners so each boundary can be verified independently.

## References

- [README.md](../README.md)
- [CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md)
- [DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md)
- [FILE_STRUCTURE.md](FILE_STRUCTURE.md)
- [OUT_DIRECTORY_ORGANIZATION_SPEC.md](OUT_DIRECTORY_ORGANIZATION_SPEC.md)

# Daily blog file formats

## Purpose

This guide identifies the persisted daily-blog inputs and artifacts that operators and maintainers
inspect or exchange. It describes the current contracts, not a general compatibility promise for
private caches or implementation-only files. For commands and recovery, see
[DAILY_BLOG_OPERATIONS.md](DAILY_BLOG_OPERATIONS.md). For the complete output layout, see
[OUT_DIRECTORY_ORGANIZATION_SPEC.md](OUT_DIRECTORY_ORGANIZATION_SPEC.md).

## Configuration input

`settings.yaml` is the operator-owned input. The `daily_blog` mapping accepts only the following
keys:

| Key | Meaning |
| --- | --- |
| `repository_path` | Local checkout that owns the site importer. |
| `mirror_cache_root` | Physical Git-cache root used by collection. |
| `report_timezone` | IANA timezone used to assign commits to a report date. |
| `identity_names`, `identity_emails` | Exact Git author identities included in activity. |
| `routes` | Exactly two named author routes and one distinct referee route. |
| `collection_limits`, `projection_limits`, `prompt_limits` | Positive bounded-input limits. |
| `shadow_evaluation.external_model_data_sharing` | Explicit opt-in for external model access during shadow evaluation and historical rubric scoring. |

The configured GitHub username defines repository ownership. Each run fetches a fresh public owner
listing and admits non-archived, non-disabled entries after exact boundary validation. The token and
raw response remain outside persisted publication artifacts.

## Collection artifacts

### Repository roster snapshot and mirror manifest

`automation/capture_daily_blog_repository_roster.py` captures one fresh, first-class immutable
repository roster snapshot before offline experiment collection. The snapshot manifest uses schema
`vosslab.daily-blog.repository-roster-snapshot.v1`; its embedded roster uses
`vosslab.daily-blog.repository-roster.v1`. Snapshots live at:

```
out/<user>/daily_blog_repository_rosters/<roster_id>/
```

Each snapshot directory contains `repository_roster.json` and `manifest.json`. The roster contains
the owner, sorted eligible repository records, and a content-derived `roster_id`. Each record
carries canonical page and clone URLs, exact UTC creation time, and fork state.

The snapshot manifest binds `captured_utc`, `owner`, `roster_id`, the schema version, and the exact
fresh GitHub owner-repository acquisition policy. Its `files.repository_roster.json` declaration
records the roster byte count and SHA-256. A reader accepts a snapshot only when the absolute path
is a direct, non-symbolic child of the configured snapshot root; the manifest, roster hash, owner,
directory name, and `roster_id` must agree.

Production orchestration writes this same immutable snapshot under
`out/<user>/daily_blog_repository_rosters/<roster_id>/`, reloads and verifies it before mirror
work, and records its absolute path and complete identity in the run state's repository-roster
reference. The per-run `repository_roster.json` remains the sealed run artifact; it does not replace
the first-class snapshot.

Each run records `mirror_manifest.json` beside its run state. It is a JSON list, ordered by canonical
`owner/repository`, with one entry per refreshed cache. An entry contains `repository`,
`repository_url`, `clone_url`, `created_at`, `is_fork`, `roster_id`, owner-qualified `cache_path`,
refresh state, default revision, exact-object availability, ref fingerprint, and refresh time.

### Activity

`activity.json` contains the attributed daily activity records. A `RepositoryActivity` records the
repository identity and URL, cache path, default revision, attributed commits, exact parent-to-commit
revision ranges, snapshot commits, fork state, and one typed `repository_created` lifecycle event.
A `CommitActivity` contains SHA, parents, author and committer
timestamps, author identity, and message. Activity contains only commits matching configured identity
rules inside the report window.

### Evidence packet

`evidence.json` is an immutable `EvidencePacket` with schema version
`vosslab.daily-blog.evidence.v4`. It contains the report date and timezone, completeness state,
collection limits, mirror entries, activity, and authority-ranked evidence items. The canonical
content hash is `packet_id`; readers must validate it after loading rather than trusting its filename.

Each `EvidenceItem` has immutable provenance: an `evidence_id`, source repository and commit, path,
Git blob hash, content hash, acquisition source, authority kind/rank, and optional asset and publish
paths. Its `content` may be truncated according to the packet limits. Current authority kinds are
`dated_changelog`, `changed_documentation`, `diff`, `readme_context`, `screenshot`, and
`commit_metadata`.

## Editorial artifacts

### Editorial projection

`editorial_projection.json` is an immutable bounded view of a packet, with schema version
`vosslab.daily-blog.editorial-projection.v2`. It retains the packet identity, report date, timezone,
projection limits, one `RepositoryCard` for every active repository, and exact evidence excerpts.
`projection_id` is the canonical hash of those fields.

A repository card contains the repository URL, attributed commit count, selected commit SHAs,
creation time, report-day creation state, fork state, and story signals. Newly created source
repositories use `new_source_repository` and precede routine cards. An excerpt carries its source
evidence identity, repository and Git provenance, offsets,
source and excerpt content hashes, and the exact excerpt text. Projection is an editorial input, not a
statement that the signal must win the editorial decision.

### Candidates and referee result

Author outputs are private run artifacts. A `CandidateResult` carries its private route label,
`projection_id`, complete post text and SHA-256, validity, and validation issues. The bundle exposes
only anonymous candidate summaries; it does not expose a route-to-candidate mapping.

The private referee result is an `EditorialDecision`: winner (`A` or `B`), bounded reason,
evidence-quality label, confidence, projection identity, selected post, and anonymous mapping. A
publication bundle is written only when the selected candidate is valid and its projection identity
matches the decision and packet-derived projection.

The active production prompt contract is `v4-three-examples-corpus-v2`, with prompt version
`daily-blog-prompts-v4` and validation policy `v4-maker-policy-v3`
(`3a4b7148579e509b6c32fa19b31d107dc4278eb5f721b2a01353a1a9a51264ee`). Activation
`daily-blog-maker-activation-6b104be9c6907eeeffcf330f6b10173857b39c6b05baa46d4cf009a67daa7547`
binds both producer and publisher.

## Run state and events

Each attempt receives a new directory under
`out/<user>/daily_blog_runs/YYYY-MM-DD/RUN_ID/`. `run_state.json` uses schema version
`vosslab.daily-blog.run.v4` and is the authoritative typed lifecycle record. It holds the run and
report identities, state, current phase, all phase records, roster/evidence/projection/bundle references,
one fixed failure category without raw exception text, and timestamps.

The ordered phase names are `repository_discovery`, `mirror_refresh`, `activity_location`, `evidence_assembly`,
`editorial_projection`, `author_generation`, `candidate_validation`, `referee_selection`,
`bundle_creation`, and `site_import`. Each phase record carries its state, start/completion times,
input and output hashes, reuse state, and failure label. `events.jsonl` is an append-only, bounded
operational timeline; it omits raw exception text.

Phase caches under `out/<user>/daily_blog_cache/` are implementation-owned, hash-addressed reuse
artifacts. They are revalidated by the producer and should not be hand-authored, copied between runs,
or treated as an interchange format.

### Publication receipt

The publisher-owned completion receipt for a report date lives at
`<daily_blog_repository>/data/publications/YYYY-MM-DD.json` and uses schema
`vosslab.daily-blog.publication.v3`. `report_date` is the sole publication identity. The receipt
binds that date to `bundle_sha256`, an integrity checksum, plus the imported timestamp, source post,
date-owned archive, and date-owned rendered release. The producer validates this receipt before it
treats a date as published.

## Publication bundle boundary

The producer writes the date-owned publication directory at
`out/<user>/daily_blog/YYYY-MM-DD/publication/`. Its `bundle.json` has schema version
`vosslab.daily-blog.bundle.v5` and contains:

- `report_date`, the sole publication identity.
- `bundle_sha256`, the canonical hash of the manifest with that field omitted, used only as an
  integrity checksum.
- Timezone, creation time, and generator identity.
- Evidence and projection paths, identities, and hashes.
- A sealed `repository_roster.json` path, roster identity, and SHA-256. The roster is the exact
  authoritative repository universe used for mirror, activity, evidence, and projection work.
- Prompt, rubric, evidence-schema, projection-schema, and candidate-policy identities.
- The selected post path and SHA-256, provenanced assets, anonymous candidate summaries, and referee
  result.
- The registered editorial prompt-contract snapshot identity when the generic bundle writer is
  exercised directly in explicit v4 tests. The producer and publisher validate the active editorial
  contract independently.

The sibling `vosslab-daily-blog` repository is the importer owner. It independently validates the
producer bundle and active editorial contract. A successful receipt has `status` (`imported`,
`idempotent`, or `replaced`), matching `bundle_sha256`, and matching `report_date`. The producer
stores that receipt in its run state. The publisher owns the date-keyed archive at
`data/publication_bundles/YYYY-MM-DD/`, rendered release at
`generated/releases/YYYY-MM-DD/`, and public post at `docs/blog/posts/YYYY-MM-DD.md`.

## Prompt-experiment fixture, capture, and attestation

The prompt experiment uses only a sealed offline capture fixture with schema version
`vosslab.daily-blog.experiment-fixture.v2`. Its root is exactly:

```
out/<user>/daily_blog_experiment_fixtures_v2/
```

Each content-addressed fixture leaf is named `<date>--<fixture_id>` and contains only
`evidence.json`, `editorial_projection.json`, and `manifest.json`. Capture requires an explicit,
verified repository roster snapshot. It loads that snapshot before inspecting existing local
mirrors; it does not discover repositories, clone, fetch, lock, publish, or call an importer.

The fixture manifest is its identity with `fixture_id` omitted; `fixture_id` is the canonical hash
of all remaining manifest fields. It binds the report date plus evidence packet and projection
identities,
repository count, mirror summary, source repository, bounded configuration identity, and the
`repository_roster_snapshot` identity. That roster identity includes `captured_utc`,
`repository_count`, `roster_id`, schema version, and acquisition source. The manifest also declares
the byte count and SHA-256 for `evidence.json` and `editorial_projection.json`.
The capture writer and experiment consumer use the same positive manifest contract; the consumer
does not carry a reduced or compatibility-shaped interpretation of these fields.

The capture command allows only the `2026-08-23` quiet and `2026-08-26` busy dates. That is a
capture-date boundary, not permission for every leaf from those dates to run. The experiment
consumer accepts only the current sealed rotation: quiet
`2026-08-23--4adcb80db0cdde222fbc6a7a53ec008d1198d0cc03f9cecc16c12ddbca24522e` and busy
`2026-08-26--04fd7a045538662e5c6b48ad79e08dd608de1b5a10c1c8857c7b12042bad41da`. Both require
roster `0f79bcfea4d3fb783258df4a37effef5996b6fdb9736ff6944fd17051570b8a1`. A new capture changes
the leaf identity and requires an explicit reviewed allowlist rotation before the consumer can run it.

The experiment runner accepts only this v2 capture schema and sealed rotation. It verifies the
fixture ID, `<date>--<fixture_id>` leaf name, packet/projection coherence, declared file hashes and
byte counts, and the 60,000-character projection context limit. It does not accept a publisher or
publication bundle as a fixture source.

### Prompt-experiment capture v3

The experiment runner writes a private capture with schema
`vosslab.daily-blog.prompt-experiment-capture.v3` only below:

```
out/<user>/daily_blog_experiments/<experiment_id>/
```

`<experiment_id>` is the direct-child leaf name and matches the strict
`prompt-experiment-...` identifier. It is not content addressed. Each completed capture contains
mode-0600 `manifest.json` and `report.json`, plus mode-0700 arm directories named
`<fixture>-<arm>-<repetition>`. Those arm directories own any full candidate Markdown; the two JSON
documents retain only redacted candidate metadata and hashes.

`manifest.json` owns the immutable experiment declaration. Its exact fields are
`schema_version`, `experiment_id`, `fixtures`, `arms`, `repetitions`, `report_sha256`,
`activation_status`, `non_publishing`, and `capture_id`. It binds each approved fixture label to its
fixture, roster, packet, projection, and declared-file identities. `report_sha256` is the SHA-256 of
the exact `report.json` bytes. `capture_id` is the canonical hash of every manifest field except
`capture_id`, so it binds the matrix and report digest without changing the directory identity.

`report.json` owns observed execution data. Its exact fields are `schema_version`, `experiment_id`,
`routes`, `records`, `comparisons`, `errors`, `capture_status`, `activation_status`,
`non_publishing`, and `contains_full_prompts`. Records bind each fixture/arm/repetition to its prompt
snapshot, candidate metadata, selected candidate, scorecard, diagnostic, and elapsed time.
Comparisons bind counterbalanced pairwise referee results to those selected candidates. The loader
requires a complete unique record matrix, a complete unique comparison matrix, and that every
selected candidate derives from a valid recorded candidate with a matching post hash. Every scored
candidate carries one exact selected-post passage and one reason per maker-rubric criterion; the
loader reopens `selected.md` and rejects a scorecard whose passage is not an exact substring.

The capture report deliberately has no aggregate or acceptance fields. It is the source evidence for
later deterministic acceptance, not a decision artifact. Both capture documents must declare
`activation_status: pending_calibration_attestation`; this status means the capture cannot activate a
prompt contract. Both must also declare `non_publishing: true`, while the report additionally fixes
`contains_full_prompts: false`.

Current registered arms are `v3`, `v4-instruction-only`, `v4-one-example`, and
`v4-three-examples-corpus-v2`. Capture artifacts are private evaluation evidence. Do not publish
them, copy them into site content, or log full prompts, route arguments, credentials, or private
artifact paths.

### Prompt-experiment attestation v4

An attestation is the route-free, immutable join of one verified capture and one verified passing
live calibration. It uses schema `vosslab.daily-blog.prompt-experiment-attestation.v4` only below:

```
out/<user>/daily_blog_experiment_attestations/<attestation_id>/
```

`<attestation_id>` is `prompt-experiment-attestation-` plus the canonical hash of every attestation
manifest field except `attestation_id`. Each leaf has only private mode-0600 `manifest.json` and
`report.json`; it has no candidate or arm directories.

The attestation report owns the source references and recomputed acceptance result. Its exact fields
are `schema_version`, `experiment_id`, `capture`, `calibration`, `acceptance_schema`, `acceptance`,
`review_contract`, and `non_publishing`. `capture` binds the direct-child capture artifact name, its
`capture_id`, and its `report_sha256`. `calibration` binds the direct-child calibration artifact name
and the complete bounded `CalibrationEvidence` value: `calibration_id`, `preparation_id`,
`report_sha256`, `rubric_sha256`, positive-reference scores, and the exclusive reference floor. The
attestation loader reopens both source artifacts, revalidates their private descriptors and
identities, and recomputes the report; a changed capture or calibration invalidates the attestation.

`acceptance` is computed from capture records and comparisons plus the bound calibration evidence.
It records `review_ready` and any selected arm; it never claims activation readiness. The capture
report must not precompute or duplicate those aggregates. `review_contract` fixes the unchanged
central question, selected arm, busy and quiet artifact identities, passage-grounded review
dimensions, the configured bounded reviewer count, and artifact-only independence rules. For each
fixture it also binds one exact `selected.md` path, repetition, and SHA-256 from the selected arm.
The deterministic selection takes the first authority-ordered sample without consulting any score
or comparison outcome. Later repetitions remain diagnostic evidence rather than a way to steer the
qualitative review toward a favorable or unfavorable result. The attestation does not duplicate
candidate Markdown: those bytes remain owned by the capture and are read through descriptor-pinned
paths whose hashes must match the review contract.

The attestation manifest repeats every report field, adds `report_sha256`, and adds
`attestation_id`. `report_sha256` is the SHA-256 of the exact report bytes. The report and its
manifest copy must be byte-consistent at the structured-field level, and `non_publishing` is always
`true`. A successful attestation is ready for its configured independent artifact-only reviews. F4
is accepted only when every passage-grounded reviewer submission required by the contract passes
both exact complete fixture posts. A submission binds the review-contract hash and both selected-post
hashes; supplying different prose fails even when the caller makes its own submission hashes
internally consistent. Activation remains a later explicit producer/publisher boundary decision.

## Rubric-calibration preparation and report

Historical calibration artifacts use schema `vosslab.daily-blog.rubric-calibration.v2` below:

```
out/<user>/daily_blog_rubric_calibrations/<calibration_id>/
```

Every leaf contains private mode-0600 `manifest.json` and `report.json` files. Preparation leaves
use `rubric-calibration-preparation-<identity-prefix>` and contain fixed post hashes, deterministic
profiles, rubric criteria, target bands, and prompt identities without copying historical post text.
Live leaves use `rubric-calibration-<timestamp>-<suffix>` and add redacted route identity, the
recorded bounded diagnostic procedure, per-post scorecards, exact cited passages and reasons,
criterion spans, aggregate historical target status, and positive/negative mean separation.

The loader accepts only the five fixed `2026-08-22` through `2026-08-26` post slots from the
configured daily-blog repository. Live mode additionally requires durable model-data-sharing
configuration and explicit invocation approval. Both modes are non-publishing; neither artifact
kind is a publication bundle, prompt-experiment fixture, or activation decision. Only a passing live
calibration can supply `CalibrationEvidence` to an attestation: its loader verifies the calibration
report digest, preparation identity, rubric digest, fixed historical-post hashes, every cited
passage, the recomputed procedure-bound aggregate, configured consistency and separation settings,
and positive-reference means before exposing the bounded evidence value. Preparation artifacts
cannot satisfy this binding.

## Maintenance rules

- Treat schema-version and identity validation in the producer and publisher as authoritative over
  this descriptive guide.
- Add a new persisted interchange artifact only with an owning validator, explicit version and
  identity behavior, and matching tests.
- Update this guide when an operator-facing input, publication bundle field, importer receipt, or
  experiment artifact contract changes.

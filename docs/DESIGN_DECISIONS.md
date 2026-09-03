# Design decisions

<!-- VENDORED HEADER: START -->
Record each durable decision about how this code and repository are shaped, once it is settled, with
the reasoning a later reader needs. Guidance Neil Voss states belongs in
[HUMAN_GUIDANCE.md](HUMAN_GUIDANCE.md), dated history in `docs/CHANGELOG.md`, open discussion in
`docs/active_plans/decisions/`. [PROPAGATED HEADER - ENTRIES BELOW ARE YOURS]
<!-- VENDORED HEADER: END -->

Write each decision as a level-three heading with these four fields. `Owner` names the
authoritative code or contract document, rather than a person.

```markdown
### <decision title>

**Decision.** <the durable direction>

**Why.** <the reason it was chosen>

**Consequence.** <the constraint a future change preserves>

**Owner.** <the authoritative code or contract doc>
```

## Software design

### Report date owns a publication

**Decision.** `report_date` is the sole identity for a daily publication. The producer writes one
stable bundle at `out/<owner>/daily_blog/YYYY-MM-DD/publication/`; the publisher owns the matching
archive, rendered release, post, and receipt under the same date. `bundle_sha256` verifies bundle
integrity without defining a second publication identity.

**Why.** A daily report has one natural identity. Keeping its artifacts date-owned makes inspection,
replacement, and recovery direct while preserving a clear checksum for independent validation.

**Consequence.** One per-date lock covers receipt inspection, generation, and import. The unattended
`--yesterday` selector automatically replaces an occupied date. An occupied explicit `--date`
selector asks for confirmation unless `--yes` preauthorizes replacement; a declined confirmation
leaves the existing publication unchanged. Each replacement exchanges stable directories without a
visibility gap and writes the publication record last as the authoritative transaction commit.

**Owner.** `make_blog.py`, `daily_blog.orchestrator`,
`daily_blog.publication_contract`, `daily_blog.publication_storage`,
`daily_blog.publication_state`, and the publisher import contract.

### systemd schedules and Hermes executes models

**Decision.** The checked-in systemd timer invokes `make_blog.py --yesterday` directly at 04:00 in
the report timezone. Hermes selects and executes editorial model routes; the surrounding pipeline is
deterministic.

**Why.** A systemd timer provides an inspectable, reliable execution schedule, while the established
Hermes integration remains the model-selection boundary.

**Consequence.** Scheduling state is not part of the publication contract. Publication state is
derived from the date-owned publisher receipt and validated artifacts.

**Owner.** `deploy/vosslab-daily-publication.timer`,
`deploy/vosslab-daily-publication.service`, and `make_blog.py`.

### Robustness preserves usable LLM work

**Decision.** Robust means a blog entry is created despite many LLMs barely listening. Robust does
not mean making publication more likely to fail by adding gates. Editorial preferences such as
citation density, word count, section shape, heading style, and coverage presentation may guide
generation, editing, and review; they do not make a mechanically valid complete post ineligible.

**Why.** LLM output is variable even when prompts are clear. Treating every requested prose detail as
an abort condition multiplies failure probabilities and discards usable work. The August 14 run
demonstrated this directly: model routes returned candidates, while presentation and citation-policy
checks eliminated all of them. The system becomes robust by preserving grounded output, not by
demanding more exact compliance from a stochastic component.

**Consequence.** The publication control path enforces only stable mechanical boundaries: exact
report identity, evidence and repository provenance, output confinement, approved image paths,
machine-owned metadata, publication source safety, and sealed publisher integrity. Authored-body
findings remain advisory repair input. Permanent tests do not require a live or simulated LLM to
follow exact prose or formatting directions; one-time checks may assess editorial quality without
becoming suite gates.

**Owner.** `pipeline/daily_blog/publication_admission.py`,
`pipeline/daily_blog/publication_validation.py`, and [PYTEST_STYLE.md](PYTEST_STYLE.md).

### Runtime code owns GitHub credential consumption

**Decision.** GitHub clients receive one runtime-only `GITHUB_TOKEN`. An explicitly injected process
value takes precedence; otherwise the credential owner reads only that named entry from the active
`$HERMES_HOME/.env`. GitHub credentials do not belong in `settings.yaml`.

**Why.** Hermes loads its profile credentials for its own operation and deliberately strips GitHub
authentication from child commands. Importing the whole Hermes dotenv into the publication service
would expose unrelated credentials, while a narrow reader gives manual and systemd runs the same
authenticated GitHub path.

**Consequence.** The systemd unit declares `HERMES_HOME` and calls `make_blog.py` directly. The
collector passes the resolved value only to the GitHub HTTPS client; it does not export neighboring
dotenv values or persist credential material.

**Owner.** `podlib.runtime_credentials`, `daily_blog.repositories`, and
`deploy/vosslab-daily-publication.service`.

### Empirical review owns the v4 prompt decision

**Decision.** The approved v4 maker package remains unchanged. Fixture-backed evidence accepted the
sealed busy and quiet posts, attestation, and independent reviews before the recorded activation.

**Why.** Small wording changes materially affect long-form voice, and coupling editorial revisions
to schema migrations obscures whether an output changed because of content guidance or plumbing.
For this rebuild, generated prose and independent comparison are stronger approval evidence than
another round of abstract wording review.

**Consequence.** The producer and publisher changed together in the recorded activation. Later prompt
text changes require a separate plan; live routes remain optional corroboration.

**Owner.** `docs/HUMAN_GUIDANCE.md`, `pipeline/prompts/`, and
`daily_blog.editorial.prompt_contract_identity()`.

### Historical prompt-quality acceptance had two immutable stages

**Decision.** Before the v4 maker activation, prompt-quality acceptance used two independently
immutable stages. A fixture-backed experiment capture established a candidate result without
historical-context sharing. A deterministic, non-publishing attestation then verified that capture
against a passing historical rubric calibration and recorded their exact identities. Activation was
a separate producer-and-publisher change that named the passing attestation it adopted.

**Why.** Fresh candidate evaluation and historical rubric calibration answer different questions
and carry different sharing authority. Binding them only through deterministic attestation makes
the approval evidence inspectable, reproducible, and unable to turn a historical-sharing approval
into permission for capture or publication.

**Consequence.** This process remains historical acceptance provenance, not a current production
path. Its capture, calibration, and attestation runners are retired and are not operational
commands or ownership boundaries. Production validates the active immutable prompt registry and
sealed maker activation without reopening the historical procedure.

**Owner.** `daily_blog_maker_activation.json`,
`pipeline/daily_blog/prompt_registry/editorial_contracts.py`, and
`pipeline/daily_blog/prompt_registry/loader.py`; historical evidence remains recorded in
`docs/active_plans/reports/`.

### Experimental examples bind identity

**Decision.** V4 maker-voice examples live in a separate, plain, project-owned resource. Registered
zero-, one-, and three-example selections bind their ordered block IDs and bytes to the immutable
prompt snapshot and opaque generator identity. The author receives examples and the maker brief;
the referee receives the rubric before candidates.

**Why.** Examples communicate voice choices that surface rules describe poorly, while a separate
resource makes each experimental arm auditable. Keeping the rubric out of the author prompt avoids
turning a scorecard into prose instructions.

**Consequence.** The completed fixture-backed experiment selected
`v4-three-examples-corpus-v2`. Active v4-maker policy v3 uses immutable validation-policy digest
`3a4b7148579e509b6c32fa19b31d107dc4278eb5f721b2a01353a1a9a51264ee` with
`projected_repositories` and `reader_visible_markdown`. Policy versions 1 and 2 fail closed. The
producer seals the snapshot, generator identity, selected artifact, and source-safety policy identity
in the active bundle-v9 boundary. The active `publication_source_safety.v1` identity has an
executable 35-case corpus and SHA-256
`d50166736d79be7f7715cc0f7585fac71dfb2aecc1c631b10e01aeca2fb63c6b`; the historical bundle-v7
boundary remains recorded evidence. The sibling publisher independently validates the active boundary and records a
`vosslab.daily-blog.publication.v6` receipt, including the canonical reader-body and surface digests.

**Owner.** `pipeline/daily_blog/prompt_registry/definitions.py`,
`pipeline/daily_blog/prompt_registry/editorial_contracts.py`, `pipeline/daily_blog/editorial.py`,
`daily_blog_maker_activation.json`, `pipeline/daily_blog/publication_contract.py`, and
`pipeline/daily_blog/publication_storage.py`.

### A survivor-scoped publication surface owns publication admission

**Decision.** A single immutable `PublicationSurface` owns the survivor-scoped evidence authority
for a publication. Stage 6 derives its writer and editor context, allowed evidence IDs, image
paths, repository coverage, and final admission from that same runtime object. Bundle-v9 carries a
canonical `publication_surface.json` handoff with the surface identity, packet and projection
identities, source-artifact attestations, and the exact evidence and image allowlists. The publisher
revalidates that handoff before staging, archive admission, and rendered-page image verification.

**Why.** A stage can produce a grounded post only when its editorial context and its admission
rules describe the same selected survivors. Reconstructing image or evidence authority from an
aggregate packet at a producer or publisher boundary can silently restore unselected sources or
reject the selected ones. A portable, hash-bound surface makes that authority inspectable across the
two repositories without asking either side to infer it again.

**Consequence.** `Stage6Input` carries execution configuration and forwards typed outline and story
views from its surface instead of retaining a parallel authority. The bundle asset manifest, imported
assets, post evidence references, and article-local rendered image sources must exactly match the
surface allowlists. Bundle-v8 remains historical, read-only evidence; new imports require the v9
surface contract. The semantic model-cache identity captures selected report inputs and evidence,
not mutable mirror inventory such as a default branch revision or ref fingerprint.

**Owner.** `pipeline/daily_blog/publication_admission.py`,
`pipeline/daily_blog/stage6.py`, `pipeline/daily_blog/publication_contract.py`,
`pipeline/daily_blog/publication_finalization.py`, and the publisher bundle importer and validators.

### Propagation records consumer maintenance

**Decision.** A successful, non-dry-run single-repository propagation that changes files adds one
canonical maintenance entry to the consumer's active changelog through `devel/changelog_lib.py`.

**Why.** Propagated maintenance belongs in the repository history, while no-op runs and failed runs
must not manufacture history. Using the shared parser and serializer keeps the entry compatible with
the changelog query, rotation, and commit tools.

**Consequence.** Propagation change accounting and `.gitignore` normalization remain idempotent, and
future changelog writes use the shared changelog library rather than assembling Markdown separately.

**Owner.** `devel/changelog_lib.py` and the single-repository propagation contract.

## Dependencies

## Generated artifacts

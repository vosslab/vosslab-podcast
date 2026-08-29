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

**Consequence.** One per-date lock covers receipt inspection, generation, and import. An interactive
root command confirms replacement for an existing date; non-interactive runs preserve a coherent
existing publication. Confirmed replacement exchanges each stable directory without a visibility
gap and writes the publication record last as the authoritative transaction commit.

**Owner.** `make_blog.py`, `daily_blog.orchestrator`, `daily_blog.bundles`,
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

### Empirical prose gates own the v4 prompt decision

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

### Prompt-quality evidence has two immutable stages

**Decision.** Prompt-quality evidence is owned as two independently immutable stages. A fresh
experiment capture establishes the candidate result without historical-context sharing. A
deterministic, non-publishing attestation then verifies that capture against a passing historical
rubric calibration and records their exact identities. Activation is a separate producer-and-
publisher change that names the exact passing attestation it adopts.

**Why.** Fresh candidate evaluation and historical rubric calibration answer different questions
and carry different sharing authority. Binding them only through deterministic attestation makes
the approval evidence inspectable, reproducible, and unable to turn a historical-sharing approval
into permission for capture or publication.

**Consequence.** The pre-production cutover adopts the two-stage contract cleanly: no legacy
evidence format, inferred calibration, compatibility alias, or implicit activation remains.
Producer and publisher activation changes cite and verify one immutable passing attestation before
they make the selected prompt contract active.

**Owner.** `pipeline/daily_blog/experiment_capture_artifacts.py`,
`pipeline/daily_blog/rubric_calibration.py`, and
`pipeline/daily_blog/experiment_attestation.py`.

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
producer binds snapshot, generator identity, bundle, and reuse identity; the publisher independently
recomputes and enforces the active bundle v5 import contract.

**Owner.** `pipeline/daily_blog/contracts.py`, `pipeline/daily_blog/editorial.py`, and
`pipeline/prompts/daily_blog_voice_examples_v4.md`.

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

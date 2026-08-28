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

### Humans own editorial prompt wording

**Decision.** Daily-blog editorial prose and rubric wording change only through explicit human review
of the exact text. Software-owned envelope, evidence, and output-schema contracts evolve separately
and identify their versions independently.

**Why.** Small wording changes materially affect long-form voice, and coupling editorial revisions
to schema migrations obscures whether an output changed because of content guidance or plumbing.

**Consequence.** Agents can diagnose output, prepare candidate diffs, and change deterministic
prompt assembly, but they preserve active prompt prose until the human approves an exact editorial
change. Prompt experiments compare outputs against human-selected reference posts before activation.

**Owner.** `docs/HUMAN_GUIDANCE.md`, `pipeline/prompts/`, and
`daily_blog.editorial.prompt_contract_identity()`.

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

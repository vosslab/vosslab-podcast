# Prompt asset sharing decision

## Decision

The central prompt registry owns immutable declarations, resource loading, and identity for all
Stage 3 through Stage 7 prompt assets. Each editorial stage retains its own prompt bytes when its
comparison or repair task has a distinct placeholder context or output schema.

Shared mechanics are the reusable boundary: balanced comparison, one repair attempt,
original-response salvage, typed verdicts, and registry-backed immutable identities. The archived
plan's implementation detail requiring one generic comparison prompt and one generic repair prompt
is superseded.

## Why

The current repository-outline, repository-story, Stage-5 ranking, and daily-outline comparison and
repair assets use materially different inputs and typed outputs. Combining their prose would require
conditional instructions that obscure the stage contract, or would erase a stage's editorial
semantics.

This follows [REPO_STYLE.md](../../REPO_STYLE.md)'s "fix the design, not the symptom" and "design
for adaptability" principles. It also follows [HUMAN_GUIDANCE.md](../../HUMAN_GUIDANCE.md): prompt
prose is human-owned, and an arbitrary consolidation gate is not a reason to rewrite it.

## Consequence

- The registry centrally declares and resolves each stage-specific asset without changing its text.
- Reusable comparison and repair behavior stays in code, where the shared typed contract is
  mechanically verifiable.
- The rebuild has no human approval milestone for a generic prose asset; this decision does not
  approve current prompt prose or make a live editorial-quality claim.
- Future prose consolidation requires evidence that the affected placeholder and output schemas are
  genuinely identical, followed by explicit human approval of the exact revised text.

## Owner

The prompt registry and the stage-local prompt contracts own this boundary. The immutable prompt
assets and their recorded identities remain the authoritative editorial provenance.

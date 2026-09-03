# LLM gate audit

Use this checklist when an LLM-assisted workflow returns usable material but the surrounding
pipeline reports failure. It complements [PYTEST_STYLE.md](PYTEST_STYLE.md): that document decides
whether a test deserves permanent residence, while this document decides whether the behavior being
tested should be a publication gate at all.

This is the primary policy for continued daily-blog gate cleanup. Apply it across generation,
promotion, bundle construction, publisher preflight, import, and rendered-page verification whenever
a usable grounded article fails to reach publication.

> **When in doubt, remove the gate and its test.**

The burden of proof is on keeping a publication gate. Model disobedience, malformed presentation,
or editorial weakness is not sufficient reason to prevent publication.

## The boundary

A hard gate protects a mechanical fact the system must know before it can publish a mechanically
valid artifact. Keep gates for wrong publication identity, unknown or out-of-scope evidence, unsafe
source or asset paths, unconfined output, corrupt durable state, and failed publisher-integrity
checks.

An editorial preference describes how good or polished an LLM response is. Word bands, heading
shape, section order, excerpt placement, citation density, first-person voice, exact JSON from a
reviewer, reviewer approval, reviewer agreement, and exact prompt compliance are not availability
conditions. They may guide a model or appear in diagnostics, but they must not discard a usable
grounded artifact or prevent publication.

An imperfect grounded artifact is preferable to no publication unless publishing it would violate a
named hard boundary.

## Audit checklist

For every `eligible`, `reject`, `blocked`, `mismatch`, `validate`, `repair`, `winner`, and
`no_eligible_generation` branch on the model-output path:

- [ ] State the concrete harm prevented by the branch.
- [ ] Confirm that the harm concerns evidence authority, publication identity, filesystem or source
  safety, durable-state integrity, or publisher integrity.
- [ ] Ask whether grounded prose could reach the branch only because the model ignored a requested
  presentation or response-format detail. If yes, remove the gate.
- [ ] Assume the surviving imperfect grounded artifact is preferable to no publication unless it
  violates a named hard boundary. Preserve the artifact and record quality issues only as advisory
  information.
- [ ] Look for chains of individually reasonable checks whose probabilities multiply. If several
  checks can independently discard an otherwise usable model artifact, collapse them into advisory
  diagnostics or a single genuine mechanical boundary.
- [ ] Treat model rankings and reviews as preferences. Missing, malformed, negative, or disagreeing
  reviews must fall back to a stable usable candidate instead of producing no artifact.
- [ ] When structured model output cannot be parsed as requested, recover usable content first. A
  schema or parser failure is not an editorial failure when the intended information can be
  recovered deterministically.
- [ ] Normalize machine-owned packaging, such as front matter and a required publication heading,
  outside the model. Do not retry merely to obtain packaging syntax.
- [ ] Treat retries and additional model calls as recovery tools, not stages an artifact must
  successfully traverse. If the current artifact is usable, continue rather than requiring another
  model call to approve or improve it.
- [ ] Keep repairs local. Change only what prevents continued use, preserve unaffected prose, and
  retain the strongest existing artifact rather than regenerating it to satisfy a local defect.
- [ ] Do not replace a removed gate with more retries, another model judge, a stricter prompt, a new
  response schema, or a larger rejection vocabulary.
- [ ] In pre-production code, replace the wrong contract in place. Do not retain version branches,
  compatibility adapters, migration fixtures, or legacy tests for an unused design.
- [ ] Keep unknown evidence references, cross-repository scope, unsafe links or images, wrong dates,
  unconfined paths, and corrupt artifacts as hard failures.
- [ ] Keep deterministic rosters authoritative throughout the run. Model prose may omit an active
  repository, but that omission must become coverage metadata, never a new roster or a publication
  veto. Carry identity forward mechanically instead of asking finalization to rediscover it.
- [ ] Treat a single repository's remote unavailability as local evidence loss. Record it and
  continue with usable repositories; do not promote a network or clone failure into a whole-day
  editorial failure. Keep local path, origin, and content-integrity violations hard.
- [ ] At a cross-component rejection, recover the exact downstream reason before removing a check.
  If the producer emitted contradictory identity or provenance metadata, repair that ownership bug
  while keeping the genuine integrity boundary. Selection may reduce work without inventing a new
  authority identity.
- [ ] Delete permanent tests whose success requires a fake or live LLM to obey exact prose,
  formatting, ranking, reviewer, or procedural instructions.
- [ ] Test robustness by injecting realistic model failures and asserting the resulting artifact or
  pipeline outcome rather than the model response. Useful cases include partial output, extra prose,
  missing optional fields, malformed but recoverable structure, candidate failure, and reviewer
  disagreement.
- [ ] Apply the permanent-test checklist in [PYTEST_STYLE.md](PYTEST_STYLE.md) to every remaining
  test. Keep live-model and whole-publication demonstrations as one-time or controlled E2E evidence.

## Useful search

Start with the control path and its tests together:

```bash
rg -n "eligible|reject|blocked|mismatch|validate|repair|winner|no_eligible_generation" pipeline tests
rg -n "word|heading|section|excerpt|citation|coverage|first-person|JSON|review" pipeline tests
```

Search results are leads, not proof that a gate is wrong. A parser used to protect a mechanical trust
boundary may deserve a permanent test. A parser whose only purpose is making an LLM emit a preferred
envelope does not deserve authority over whether the blog exists.

Also inspect combinations of checks rather than reviewing each gate only in isolation. Several
defensible-looking editorial checks can collectively make successful publication unlikely even when
each check usually passes.

## Review outcome

For each gate, record one of three dispositions:

- **Keep hard:** failure would violate a named mechanical trust boundary.
- **Make advisory:** the result helps editorial judgment but cannot stop publication.
- **Delete:** the check, repair loop, or test exists only to demand model obedience or freeze an
  implementation topology.

**When in doubt, remove the gate and its test.** The burden of proof is on keeping a publication
gate. A gate without a named mechanical trust boundary is an editorial preference with control-flow
authority, which is precisely the design this document exists to remove.

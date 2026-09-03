# Daily publication flow

This document owns the human step names and durable filename flow for one daily-blog run. Console
output uses the short IDs below. The canonical JSON run log retains the internal phase and editorial
step identifiers so presentation remains separate from workflow authority.

## Run directory

Every run writes beneath one date-and-run-owned directory:

```text
out/<owner>/daily_blog/YYYY-MM-DD/runs/RUN_ID/
```

The console names the absolute machine log first:

```text
runlog-YYYY-MM-DD.jsonl
```

Every name in this flow is deterministic and code-owned. Names derive only from validated
`report_date`, `run_id`, fixed artifact names, and manifest-confined asset paths. Model responses,
titles, headings, summaries, rankings, and selected prose never choose or influence filenames.

Artifact ownership has three abbreviated labels in this document:

- **MOA - Machine-owned authority:** deterministic code owns the complete artifact and its authority.
- **LDMW - LLM-derived, machine-wrapped:** deterministic code constructs a JSON envelope for provenance,
  attempts, relationships, and opaque or minimally interpreted stochastic model content. The model
  is never required to emit that envelope correctly.
- **LAP - LLM-authored publication:** model prose is the human-readable artifact; deterministic code owns
  its filename, metadata, provenance, and publication packaging.

JSON therefore does not imply deterministic content or model schema compliance. LLM output never
becomes authority over machine-owned facts.

MOA describes authority, not merely deterministic implementation. In an LDMW artifact, the machine
owns the JSON envelope while the enclosed editorial material remains stochastic and non-authoritative.

Repository membership is dynamic even though its derivation is deterministic. A run fetches a fresh
complete account-roster snapshot because repositories may be created at any time. It separately
derives the active repository set from commits on that run's `report_date`. Neither set is a fixed
configuration, fixture, or expected count. Each becomes immutable only inside its run so repository
agents and publication consume the same observed inputs.

The stages are not equally necessary editorial gates:

```text
A  Acquire deterministic evidence
   -> B  Build repository outlines
   -> C  Build repository summaries
   -> D  Build the daily story outline
   -> E  Produce a publishable post     <- editorial availability is achieved here
   -> F  Optionally improve the post
   -> G  Mechanically publish and verify
```

## A: Evidence acquisition

| Step | Work | Ownership | Durable output |
| --- | --- | --- | --- |
| A1 | Capture a fresh authoritative account-roster snapshot | MOA | `repository_roster.json` |
| A2 | Search GitHub and establish report-day activity within that universe | MOA | `daily_active_roster.json` |
| A3 | Fetch active repositories and record their revisions | MOA | `mirror_manifest.json` |
| A4 | Resolve exact commits and revision ranges | MOA | `activity.json` |
| A5 | Assemble bounded commit, changelog, diff, and supporting-file evidence | MOA | `evidence.json` |

## B: Repository outlines

| Step | Work | Ownership | Durable output |
| --- | --- | --- | --- |
| B1 | Generate repository outline candidates | LDMW | `repository_editorial.json` |
| B2 | Optionally improve or review usable outlines | LDMW | `repository_editorial.json` |
| B3 | Preserve usable promoted outlines | LDMW | `repository_editorial.json` |

## C: Repository summaries

| Step | Work | Ownership | Durable output |
| --- | --- | --- | --- |
| C1 | Generate repository summary candidates | LDMW | `repository_editorial.json` |
| C2 | Optionally improve or review usable summaries | LDMW | `repository_editorial.json` |
| C3 | Preserve usable promoted summaries | LDMW | `repository_editorial.json` |

## D: Daily outline

| Step | Work | Ownership | Durable output |
| --- | --- | --- | --- |
| D1 | Receive story rankings when available | LDMW | `daily_outline_editorial.json` |
| D2 | Review rankings when review is available | LDMW | `daily_outline_editorial.json` |
| D3 | Receive daily outline candidates | LDMW | `daily_outline.json` |
| D4 | Review usable daily outlines when review is available | LDMW | `daily_outline_editorial.json` |
| D5 | Preserve a usable daily outline | LDMW | `daily_outline.json` |

## E: Complete post

| Step | Work | Ownership | Durable output |
| --- | --- | --- | --- |
| E1 | Receive complete-post candidates | LDMW | `complete_post_attempts.json` |
| E2 | Receive edited complete-post candidates | LDMW | `complete_post_attempts.json` |
| E3 | Review usable posts when review is available | LDMW | `complete_post_attempts.json` |
| E4 | Select a usable complete-post candidate when available | LDMW | `complete_post_editorial.json` |
| E5 | Retain one publishable incumbent | LDMW | `complete_post_editorial.json` |

E4 records candidate selection; E5 records the stage-level incumbent that remains available after
selection or degradation. Here, **publishable** means that enough recoverable prose exists to proceed
to deterministic publication packaging. It does not mean that an LLM obeyed a format, passed an
editorial review, reproduced every repository, or followed a prescribed route. By the end of E, the
pipeline owns a publishable incumbent. Later editorial work cannot take that availability away.

## F: Optional synthesis

| Step | Work | Ownership | Durable output |
| --- | --- | --- | --- |
| F1 | Attempt optional final syntheses | LDMW | `final_synthesis_editorial.json` |
| F2 | Compare usable syntheses with the incumbent when available | LDMW | `final_synthesis_editorial.json` |
| F3 | Promote a preferred challenger or preserve the incumbent | LDMW | `final_synthesis_editorial.json` |

## G: Publication

| Step | Work | Ownership | Durable output |
| --- | --- | --- | --- |
| G1 | Normalize machine metadata for the selected post | MOA | `publication_validation.json` |
| G2 | Seal the post, evidence, rosters, surface, and assets | MOA | `publication_bundle.json`, `publication/` |
| G3 | Mechanically validate the exact sealed bytes with the publisher | MOA | `publisher_preflight.json` |
| G4 | Write the selected producer handoff | LAP | date-owned `post.md` |
| G5 | Import or replace the date-owned reader publication | MOA | publisher receipt in `run_state.json` |
| G6 | Verify the rendered reader page | MOA | terminal receipt in `summary.jsonl` |

`publication_validation.json` records only mechanical metadata normalization and trust-boundary,
provenance, source, and artifact-integrity checks. Editorial quality and reviewer approval are outside
G1 validation.

## Availability rule

Steps describe observations, not gates or mandatory model-call topology. Counts may be zero, and a
model response may be sloppy, incomplete, malformed, or contrary to its instructions. The pipeline
continues whenever deterministic code can recover enough content for the next stage. Missing
sections, unexpected structure, extra prose, malformed reviewer output, weak rankings, and incomplete
editorial responses remain recoverable conditions rather than publication failures. Optional
reviews, edits, mergers, and synthesis may improve a
usable artifact, but their absence does not stop publication. Tests must not freeze display counts,
route topology, or instruction-perfect model behavior. [LLM_GATE_STYLE.md](LLM_GATE_STYLE.md) owns
this availability policy and overrules this presentation map if the two ever conflict.

The A1 and A2 rosters are never rewritten to disguise an operational loss. A3 records a concrete
clone or fetch failure in `mirror_manifest.json`, where it occurs. Usable repository evidence may
continue, but a recovery mechanism does not become a separate repository-domain concept.

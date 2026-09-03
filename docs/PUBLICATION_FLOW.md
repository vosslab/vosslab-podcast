# Daily publication flow

This document owns the human step names and durable filename flow for one daily-blog run. Console
output uses the short IDs below. The canonical JSON run log retains the internal phase and editorial
step identifiers so presentation remains separate from workflow authority.

## Run directory

Every run writes beneath one report-date-owned directory:

```text
out/<owner>/daily_blog/YYYY-MM-DD/
```

The `report_date` is the sole durable publication identity. A rerun for the same date updates or
replaces that date's canonical run state and artifacts; it does not create a timestamp- or
execution-ID-owned sibling tree. An execution identifier may appear inside logs and diagnostic
records, but never owns the canonical artifact path. Historical attempt artifacts, if retained for
diagnosis, live outside the canonical publication structure.

The console names the absolute machine log first:

```text
runlog-YYYY-MM-DD.jsonl
```

Each human-visible step reports its elapsed monotonic time when it completes. Existing result lines
end with `completed in 54 sec` or `completed in 2m54s`; phases without a separate result line print a
short completion line. Editorial substeps report time from their enclosing phase start, and the final
publication line reports total run time. These timings are operator feedback only and never influence
workflow state, reuse, admission, or publication output.

Every name in this flow is deterministic and code-owned. Names derive only from validated
`report_date`, fixed artifact names, and manifest-confined asset paths. Model responses,
titles, headings, summaries, rankings, and selected prose never choose or influence filenames.

## Producer and renderer boundary

`vosslab-podcast` owns publication correctness. It defines the publication artifact, decides which
Markdown and assets are authoritative, mechanically validates and seals them, exports their exact
bytes, and verifies delivery of those bytes.

`vosslab-daily-blog` owns rendering and deployment mechanics only. It places the producer-supplied
Markdown and assets at confined destination paths, invokes MkDocs, deploys the built site, and
verifies the rendered page. It does not interpret or reject the publication for prose quality,
meaning, readability, Markdown structure, editorial completeness, evidence grounding, citations,
repository coverage, roster equality, or producer workflow decisions. MkDocs is the authority on
whether the supplied Markdown can be rendered. If MkDocs can render producer-supplied nonsense,
`vosslab-daily-blog` publishes that nonsense.

The renderer may fail only for its own mechanical responsibilities: unsafe destination paths, file
placement failure, MkDocs build failure, deployment failure, or rendered-page verification failure.
It does not run an independent publication-admission or Markdown-readability preflight.

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

| Step | Work | Ownership | Working output |
| --- | --- | --- | --- |
| A1 | Capture a fresh authoritative account-roster snapshot | MOA | `repository_roster.json` |
| A2 | Search GitHub and establish report-day activity within that universe | MOA | `daily_active_roster.json` |
| A3 | Fetch active repositories and record their revisions | MOA | `mirror_manifest.json` |
| A4 | Resolve exact commits and revision ranges | MOA | `activity.json` |
| A5 | Assemble bounded commit, changelog, diff, and supporting-file evidence | MOA | `evidence.json` |
| A6 | Catalog candidate images with stable evidence identities and no embedded bytes | MOA | `image_catalog.json` |

## B: Repository outlines

| Step | Work | Ownership | Working output |
| --- | --- | --- | --- |
| B1 | Generate repository outline candidates | LDMW | `repository_editorial.json` |
| B2 | Optionally improve or review usable outlines | LDMW | `repository_editorial.json` |
| B3 | Preserve usable promoted outlines | LDMW | `repository_editorial.json` |

## C: Repository summaries

| Step | Work | Ownership | Working output |
| --- | --- | --- | --- |
| C1 | Generate repository summary candidates | LDMW | `repository_editorial.json` |
| C2 | Optionally improve or review usable summaries | LDMW | `repository_editorial.json` |
| C3 | Preserve usable promoted summaries | LDMW | `repository_editorial.json` |

## D: Daily outline

| Step | Work | Ownership | Working output |
| --- | --- | --- | --- |
| D0 | Compact oversized repository-story context with one summarizer per repository | LDMW | `daily_outline_editorial.json` |
| D1 | Receive story rankings when available | LDMW | `daily_outline_editorial.json` |
| D2 | Select among available independent rankings deterministically | LDMW | `daily_outline_editorial.json` |
| D3 | Receive daily outline candidates | LDMW | `daily_outline.json` |
| D4 | Review usable daily outlines when review is available | LDMW | `daily_outline_editorial.json` |
| D5 | Preserve a usable daily outline | LDMW | `daily_outline.json` |

D0 runs only when the complete repository editorial corpus would otherwise be excerpted for the daily stage. Its work
scales linearly with repositories. Summarizer output is advisory: any non-empty response can be normalized into the
bounded daily context, while an unavailable response falls back to the existing repository artifact excerpt. Context
size and summarizer compliance never become publication gates.

## E: Complete post

| Step | Work | Ownership | Working output |
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

| Step | Work | Ownership | Working output |
| --- | --- | --- | --- |
| F1 | Attempt optional final syntheses | LDMW | `final_synthesis_editorial.json` |
| F2 | Compare usable syntheses with the incumbent when available | LDMW | `final_synthesis_editorial.json` |
| F3 | Promote a preferred challenger or preserve the incumbent | LDMW | `final_synthesis_editorial.json` |
| F4 | Select useful images from the bounded machine catalog when available | LDMW | `image_decoration_editorial.json` |
| F5 | Place selected image identities and captions into the incumbent prose | LDMW | `image_decoration_editorial.json` |

F4-F5 target at least one useful image whenever the catalog contains suitable imagery. They are
editorial improvement steps, never publication gates: no catalog, no suitable selection, malformed
decorator output, or decorator failure preserves the existing publishable incumbent. The decorator
may name only stable image identities supplied by A6. It cannot choose filenames or destination paths.
Its bounded response contains at most three `{image_id, after_block, alt_text}` placements. The machine
salvages valid, unique identities and positions against the exact post and catalog, ignoring malformed
siblings and explanatory fields before changing Markdown.

## G: Publication

| Step | Work | Ownership | Working output |
| --- | --- | --- | --- |
| G1 | Normalize machine metadata for the selected post | MOA | `publication_validation.json` |
| G2 | Resolve decorator image identities into date-owned Markdown paths and seal only those selected asset bytes | MOA | `publication_image_selection.json`, transient `publication_bundle.json`, `publication/` |
| G3 | Export the exact sealed bytes and verify their delivery | MOA | producer transport receipt in `run_state.json` |
| G4 | Place the authoritative Markdown and assets, then invoke MkDocs and deployment | MOA | renderer receipt in `run_state.json` |
| G5 | Verify the rendered reader page | MOA | terminal receipt in `summary.jsonl` |

`publication_validation.json` records only mechanical metadata normalization and trust-boundary,
provenance, source, and artifact-integrity checks. Editorial quality and reviewer approval are outside
G1 validation.

All listed JSON, candidate, review, projection, and bundle artifacts are date-owned working material.
They remain available while a run is incomplete so failures can be traced. After the final Markdown
and selected assets have been delivered and the reader page has been verified, the producer retains
only the canonical run log and terminal summary for diagnostics and discards the working artifacts.
A fresh run for the same `report_date` replaces that date's working state.

G3 is producer-owned transport verification, not a request for the display repository to admit or
approve the publication. G4 treats the received publication bytes as authoritative input. A failure
to understand, score, or approve their content is not a G4 failure category.

The transport contains only its transient routing manifest, final `post.md`, and assets referenced by
that final Markdown. Repository image discovery remains producer-side working evidence and is never a
bulk-copy instruction for the display repository.

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

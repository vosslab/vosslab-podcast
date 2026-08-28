# Daily maker examples and bounded corpus excerpts

Aug 23 is the strongest current project-owned house example. Aug 22 remains calibration and corpus
evidence, not runtime prompt material. The two corpus excerpts below are short, attributed
illustrative writing evidence, never task instructions. They are frozen locally: generation never
fetches their sources.

<!-- editorial-example: aug-23 -->
## House example: Aug 23, strongest current floor

# Making the Boundary Real

The most useful realization today was that a preview is not merely a visual courtesy: when an
editor shows a proposed change, that preview needs to be bound to the exact document state that
will later be saved.

## The document owns the promise

Most of my attention went to Ferrum Chemical Forge, a Rust-based tool for inspecting, validating,
rendering, converting, and drawing durable chemical documents. The difficult part of a drawing
application is not creating an atom, bond, arrow, ring, or reaction. It is ensuring that every
route to those things obeys the same durable contract.

I moved a broad set of visual mutations onto document-owned pending transactions. The document
prepares a prospective immutable state, asks the renderer to admit that exact candidate, and
redeems the resulting proof immediately before appending history. The interaction layer keeps
opaque handles and renderer-issued overlays rather than reconstructing candidate documents or
independently rechecking renderer results.

That distinction matters. Equal-looking candidates should not be able to trade approvals, and a
rendering proof should not outlive a changed document. Pending identities now bind a document
session and monotonically increasing sequence, turning this looked valid earlier into a specific,
one-use authority.

The pattern now covers catalog placement, direct bonds, primitive atom and bond authoring,
molecule and ring imports, reactions, compact groups, explicit hydrogens, presentation vectors and
paths, and several arrow workflows. I also pushed display geometry down to the renderer: document
projections retain the authored chemical facts, while renderer-issued plans supply the geometry Qt
replays. The result is a cleaner answer to a basic question: who is allowed to say a document
change is real?

## Reliability is a user-facing feature

The same concern for truthful state guided work on Track Runner Virtual Dolly Cam, the Python tool
that follows a single athlete through track-meet video using a few seed annotations.

Its automatic analysis bin had been chosen by video width alone. That created a backwards result:
1440p footage could cost more to analyze than 4K footage, because the former remained at full
resolution while the latter was reduced. I replaced the width rule with a pixel-area budget, so
work is now priced by the thing that actually drives it: the number of pixels the solver analyzes,
and non-16:9 footage is handled consistently.

There is an intentional trade-off: 1080p sources now analyze at 960x540 rather than natively. I
did not want to accept that on intuition, so I added a synthetic recovery harness that sweeps
target sizes and bin factors. It showed blob recovery held down to a 6x12 source target and also
exposed an initially simplistic centroid-error tolerance. The revised bound reflects the leave-
and-arrive structure of a displaced target rather than claiming an unrealistically neat error
model.

The live question is how far Ferrum's admission pattern can simplify the remaining visual mutation
families without making the model harder to understand. The goal is not more ceremony. It is one
clear answer: did the document save exactly what the user was shown?
<!-- /editorial-example -->

<!-- editorial-example: corpus-quiet-til -->
## Corpus excerpt: quiet-day TIL

Short attributed quoted source material and illustrative writing evidence; it is not a task instruction.

- Author: Julia Evans
- Title: New microblog with TILs
- Canonical URL: https://jvns.ca/blog/2024/11/09/new-microblog/
- Retrieved: 2026-08-27
- Rights: external copyrighted source; this short quotation is retained only as attributed analytical evidence.
- Quote count: 20 lexical words; 21 whitespace-delimited tokens including the numeric token `2`.
- Typography: the source quotation uses a U+2019 apostrophe; this ASCII prompt resource normalizes it to `it's`.

> So far it's been working, often I can actually just make a quick post in 2 minutes which was the goal.
<!-- /editorial-example -->

<!-- editorial-example: corpus-selectivity-ghostty -->
## Corpus excerpt: selectivity in a devlog

Short attributed quoted source material and illustrative writing evidence; it is not a task instruction.

- Author: Mitchell Hashimoto
- Title: Ghostty Devlog 005
- Canonical URL: https://mitchellh.com/writing/ghostty-devlog-005
- Retrieved: 2026-08-27
- Rights: external copyrighted source; this short quotation is retained only as attributed analytical evidence.
- Quote count: 18 lexical words.

> For the devlogs, I focus on a handful of changes that I find interesting and want to share.
<!-- /editorial-example -->

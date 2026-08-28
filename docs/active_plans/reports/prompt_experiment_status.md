# Prompt experiment status

## Current result

The maker-voice implementation is complete as experimental v4-maker policy v3 and remains
unactivated. Production selects v3-historical policy v3 by default. The current publisher importer accepts the active
v3 interface; it does not accept v4 bundles. This report records the current working-tree status,
not an activation decision.

The immutable v3-historical policy v3 validation digest is
`aada487814ca0080d4a49648440ee6614e5f3a3628be6197ffafcef242969324`: it uses
`all_packet_activity` coverage and `legacy_source` word counting as the exact historical control.
V4-maker policy v3 is `3a4b7148579e509b6c32fa19b31d107dc4278eb5f721b2a01353a1a9a51264ee`: it uses
`projected_repositories` and `reader_visible_markdown`. Both policies declare a 24,000-character
candidate cap, one marker, one opening prose block, no pre-marker H2, and a 100-word opening limit.
Policy versions 1 and 2 fail closed. The producer binds the policy to its snapshot, opaque generator identity, bundle, and
reuse identity. The publisher independently recomputes and enforces its validation policy and the
exact active v3 contract at import; it does not recompute producer snapshot, generator, or reuse
identities. The importer remains v3-only until a separately reviewed activation change advances
both contracts.

The central review question is:

> After reading this post, does it feel like Neil sat down after coding and wrote about what he
> made, what interested or surprised him, why he enjoyed working on it, what he learned, and what
> he wants to try next?

The approved maker brief is:

> Write as the person who made this software. Tell the interesting story inside today's work. Show
> what drew your attention, what surprised you, what you enjoyed, what you learned, and what remains
> unresolved. Give important details room to breathe and treat routine work briefly. Let technical
> details support the story. Write with the curiosity, satisfaction, uncertainty, and personality of
> someone describing work they actually care about.

## Evidence and design

[maker_blog_corpus.md](maker_blog_corpus.md) treats the project-owned August 23 post as the primary
house-voice example. The corpus finds that its useful moves
are a specific artifact, attention or surprise, personal reasoning, technical detail in service of a
story, and an honest next question. They are positive, passable references rather than a ceiling.

The v4 experiment varies an example-led design across three registered arms:

| Arm | Selected examples |
| --- | --- |
| `v4-instruction-only` | None |
| `v4-one-example` | August 23 |
| `v4-three-examples-corpus-v2` | August 23, attributed Julia Evans excerpt, attributed Mitchell Hashimoto excerpt |

The old synthetic quiet-day and August 22 three-shot selection has been removed. The implementation
keeps examples as a separate plain prompt resource. A registered selection
binds ordered block IDs, bytes, and SHA-256 to an immutable prompt snapshot. The producer derives
the generator identity from that validated snapshot through an opaque factory record. This makes a
result attributable to an exact arm without letting callers construct an arbitrary identity.

The frozen external excerpts are below 25 words per source, carry source URL, author, retrieval,
rights, and ASCII-normalization metadata, and are illustrative writing evidence rather than task
instructions. The Evans quotation has 20 lexical words (21 whitespace tokens because of numeric
`2`); the Hashimoto quotation has 18 lexical words, for 38 lexical words total. The largest rendered
prompt is 67,572 characters, below the 72,000-character limit. The author receives evidence, examples,
the maker brief, and the output contract. The author does
not receive the scoring rubric. The referee receives the central question and weighted rubric before
anonymous candidates. Deterministic rules preserve factual and publication boundaries: prose-bearing
narrative sections carry projected evidence comments; up to three narrative prose blocks may be
uncited; the narrative is 300-2500 words with zero to 12 narrative H2 sections; final Project
coverage stays compact; and the first narrative use of a canonical repository identity is a direct
link to its exact repository URL. Voice metrics are review diagnostics and do not block publication.

The literature supports this division of labor without claiming that any single prompt arrangement
is universally best. Phoenix and Taylor, *Prompt Engineering for Generative AI: Future-Proof
Inputs* (2024), lines 97-100 and 225-227, describe generic zero-shot output tending toward broad
internet patterns and examples communicating qualities that are difficult to state as rules. Their
lines 12616-12638 caution that excessive untested instruction can make output less natural. Mizrahi,
*Unlocking the Secrets of Prompt Engineering* (2023), lines 921-925 and 2081-2112, recommends
target writing samples for voice and tone. Berryman and Ziegler, *Prompt Engineering for LLMs: The
Art and Science of Building Large Language Models* (2023), lines 332-346, 1429-1457, and 1942-1988,
describe prompts as imitated text patterns, representative examples as a way to teach subtle style,
and ending a prompt with a focused task. The local converted books are the source corpus for these
line references.

## Permanent tests and one-time evidence

Permanent pytest coverage stays route-free and narrow. It protects prompt-resource identity,
rendering, candidate-validation boundaries, sealed artifact integrity, and deterministic
attestation. These checks use compact offline inputs and are regression protection for contracts,
not a substitute for generated prose.

One-time implementation checks may prove a migration or private-artifact rebuild while work is in
progress, but they do not belong in the permanent suite merely because they exercise a large path.
The approval-gated capture, live calibration, and attestation are operational evidence. They use
the real sealed inputs and, where applicable, configured model routes; only their immutable output
artifacts establish an activation decision. Prompt prose is reviewed through its resources and
captured outputs, not frozen by pytest snapshots or stubbed full-pipeline E2Es.

The non-publishing experiment requires two sealed content-addressed v2 inputs. Capture uses
`vosslab.daily-blog.experiment-fixture.v2` and a first-class immutable repository-roster snapshot
schema. It accepts only the approved `2026-08-23` quiet and `2026-08-26` busy report dates, and
constructs evidence and projection directly from read-only owner-qualified mirrors. Publisher
bundles are no longer accepted as fixture sources.

The capture-date allowlist is narrower than the consumer contract. Capture may create only a
quiet `2026-08-23` or busy `2026-08-26` leaf, while the current consumer may run only quiet
`4adcb80db0cdde222fbc6a7a53ec008d1198d0cc03f9cecc16c12ddbca24522e` and busy
`04fd7a045538662e5c6b48ad79e08dd608de1b5a10c1c8857c7b12042bad41da`, both bound to roster
`0f79bcfea4d3fb783258df4a37effef5996b6fdb9736ff6944fd17051570b8a1`. A replacement capture needs
a reviewed consumer-allowlist rotation before live generation.

`rubric_calibration.md` records the fixed five-post calibration input, content hashes, route-free
profiles, operational score bands, and exact stability rule. Its preparation identity is
`63fcad727dcca58c10410986abe4d6da4803e9bf557c1d8cee43fabc7dd76bb1`; it used no model route.
Preparation validates the fixed local inputs. A sealed experiment accepts a separate passing live
calibration artifact produced by the approved historical-calibration command.

Fresh current v2 capture is complete for both inputs:

| Fixture | Date | Fixture ID | Roster snapshot | Roster repositories |
| --- | --- | --- | --- | ---: |
| quiet | 2026-08-23 | `4adcb80db0cdde222fbc6a7a53ec008d1198d0cc03f9cecc16c12ddbca24522e` | `0f79bcfea4d3fb783258df4a37effef5996b6fdb9736ff6944fd17051570b8a1` | 111 |
| busy | 2026-08-26 | `04fd7a045538662e5c6b48ad79e08dd608de1b5a10c1c8857c7b12042bad41da` | `0f79bcfea4d3fb783258df4a37effef5996b6fdb9736ff6944fd17051570b8a1` | 111 |

## Current operational sequence

The experiment has two intentionally separate private artifacts. A capture records what the
configured author and referee routes did with the sealed busy and quiet fixtures. It is not an
activation decision: its v1 capture schema always records
`activation_status: pending_calibration_attestation`, including when all generations, comparisons,
and scorecards complete. The capture command accepts no `--calibration` option.

An attestation is the later deterministic join of a verified capture with a passing live
calibration. It recomputes the acceptance result, invokes no route, and writes only under
`/home/vosslab/nsh/vosslab-podcast/out/vosslab/daily_blog_experiment_attestations/`. Its exit
status reports whether the joined evidence is activation-ready; it neither activates v4 nor changes
the active production contract.

After the operator enables historical-post sharing in `settings.yaml`, explicitly approves the
live calibration invocation, and separately approves configured-route use with project context,
run these commands from the repository root in order.

First, create a passing live calibration under the configured private calibration root:

```bash
source source_me.sh && python3 automation/calibrate_daily_blog_rubric.py \
  --approve-historical-post-sharing \
  --repetitions 3
```

The live calibration must print a passing status and creates a direct-child artifact below
`/home/vosslab/nsh/vosslab-podcast/out/vosslab/daily_blog_rubric_calibrations/`.

Second, capture the sealed non-publishing comparison. The current CLI requires absolute busy and
quiet fixture paths and uses the registered arms with three repetitions by default:

```bash
source source_me.sh && python3 automation/experiment_daily_blog_prompts.py \
  --busy-fixture /home/vosslab/nsh/vosslab-podcast/out/vosslab/daily_blog_experiment_fixtures_v2/2026-08-26--04fd7a045538662e5c6b48ad79e08dd608de1b5a10c1c8857c7b12042bad41da \
  --quiet-fixture /home/vosslab/nsh/vosslab-podcast/out/vosslab/daily_blog_experiment_fixtures_v2/2026-08-23--4adcb80db0cdde222fbc6a7a53ec008d1198d0cc03f9cecc16c12ddbca24522e \
  --repetitions 3
```

This command writes a sealed capture only below
`/home/vosslab/nsh/vosslab-podcast/out/vosslab/daily_blog_experiments/`. Record the resulting
`prompt-experiment-...` directory name. It does not activate v4, import a post, publish a site, or
alter the systemd schedule.

Third, attest the verified capture with the passing live calibration. Both arguments must be
absolute, configured-root, direct-child artifacts:

```bash
source source_me.sh && python3 automation/attest_daily_blog_prompt_experiment.py \
  --capture /home/vosslab/nsh/vosslab-podcast/out/vosslab/daily_blog_experiments/PROMPT_EXPERIMENT_ID \
  --calibration /home/vosslab/nsh/vosslab-podcast/out/vosslab/daily_blog_rubric_calibrations/RUBRIC_CALIBRATION_ID
```

Replace the placeholders with the actual immutable directory names printed by the preceding
successful commands. The attestation is route-free and non-publishing. A successful attestation
only establishes evidence for the separately reviewed activation decision.

The busy manifest has 34 evidence items, nine active repositories, and a 59,881-character rendered
projection. Its actual projection places `vosslab/cancer-clicker` at position zero with
`created_in_report_window` true, the `new_source_repository` story signal, and citable excerpts.

The following prior capture values are obsolete diagnostics from the superseded fixture path; they
are not current v2 fixture identities and must not be used for live generation:

| Fixture | Date | Packet ID | Projection ID | Evidence bytes/SHA-256 | Projection bytes/SHA-256 |
| --- | --- | --- | --- | --- | --- |
| busy | 2026-08-26 | `96eb36e58425dc7c8b1a60dfa23428b83fc329ea8fdbd7aace43d5ad01a00907` | `e93ee777fdb95521bf89a2844e7d7b97cb399ddcae536256499144d795da5965` | `304383` / `5330147d63bee9b6271e7a8bcc0eca325952083c54a8039e78294780935829f9` | `62077` / `1776a58cc0e1d8486c90b5d5353af3058fd8745d9804a100f722455869b9d77b` |
| quiet | 2026-08-23 | `7b513ff376f38220b73c419c3e98d101a2cd7f6a3dd97ed1e41af870e85c0923` | `52eca1b0e1cc53c65ebabdd53e3ad26aea1b62909b04b4686deec30369fd8294` | `98352` / `422d0e96b1af9b68812a92c45d58c9222f9d510470cb81c8c7b92d860bcbfcb0` | `61898` / `2fa92b10c4c67e37d457baa2743dcd405c6f4ef2e35c7861dd80d296347c3101` |

The former busy fixture hashes and the former captured publisher source-bundle digest
`d6d06817bec1b057411b10d135400e0db8024a7f750f603bd45c630d783c5799` remain only as obsolete
route-diagnostic provenance. They are superseded by the current sealed v2 captures above.

## Hermes route evidence

Private artifact `prompt-experiment-cdfa63f1acbf48a58b41e50a3327a6e9` is superseded and retained
only as a redacted route diagnostic. It recorded two fixtures, four arms, and three repetitions:
24 planned author generations. All 24 stopped at `author_generation` with
`EditorialBlockedError`; it has zero selected candidates, zero referee comparisons, and no
aggregates. It used a superseded arm definition, so it is not evidence about the current prose
package, a comparison between current arms, or an activation candidate.

An authorized Hermes no-content smoke returned OK. That proves only the no-content route smoke;
it did not send a project payload or create a capture. The attempted full project-evidence capture
was blocked at the external-action gate before payload egress. Therefore there is no current live
capture, passing live calibration, attestation, generated-prose comparison, arm winner, activation,
publication, or change to active v3.

All private route diagnostics remain redacted and contain no complete prompts. Before an operator
runs an unsandboxed `hermes chat` route with `--ignore-rules` and project context, the operator must
explicitly approve that route use. That approval is separate from prompt-text approval and has not
been inferred here.

## Activation condition

Activation remains empirical. Route-free rubric calibration preparation is complete, but a passing
live calibration, a verified busy-and-quiet capture, the route-free attestation, repeated live
historical scorecards, and a winner remain missing. First obtain the two explicit approvals,
produce the calibration and capture, attest their deterministic acceptance result, inspect generated
posts and referee comparisons against the central question, and record the evidence-based decision.
Only then may a separately reviewed change advance the active contract and the producer/publisher
interface together. Until that change, v3 remains active and the production orchestrator rejects v4
before it takes a lock, refreshes mirrors, invokes any model route, writes a bundle, or calls the
importer.

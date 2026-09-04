# Plan: rebuild the daily blog pipeline around replicate, review, and promote

## Context

The pipeline produces a blog post for **any requested `report_date` that has obtainable evidence**.
`--yesterday` selects that date; historical dates are equally first-class.

The current pipeline was built to a misread requirement. "Robust" was implemented as "strict", so
quality checks became abort conditions:

- 794 `raise` statements across 13,990 lines in `pipeline/daily_blog/`, one per ~18 lines.
- `orchestrator.py:764` runs ten phases under `except Exception: self._fail_current(error); raise`.
- `candidates.py` defines 32 rejection reasons; `editorial.py:772` sets `valid = not issues`.
- Two candidates, zero retries (`editorial.py:671`).
- `editorial.py:926` and `:940` raise when candidates or the referee fall short.

At 98% per-check success a candidate clears 32 checks 52% of the time and both fail ~23% of runs.
Gate probabilities multiply; that is a design property, not a tuning problem.

`docs/BLOG_CONTRACT.md` is the specification and stays under human ownership. This plan implements
it.

The codebase is **pre-production**. Nothing depends on current interfaces, so this plan improves
foundational schemas, contracts, abstractions, and ownership boundaries directly rather than
layering compatibility work over designs that are already known to be wrong.

Reviews found five defects verified against the code, each corrected here: `bundles.py:14-18`
imports modules an earlier draft removed while keeping `bundles.py`; `contracts.py:394-411` is the
prompt asset registry as well as gate machinery; `RunStore` and `PhaseCache` already own run state;
`import_publication_bundle.py:925-940` makes import and build atomic; and
`depth_orchestrator.py:99-118` resolves malformed referee output to positional candidate B.

Two corrections came from the human and set the plan's center:

1. Robustness belongs **inside** the editorial stages. An earlier draft made a deterministic floor
   the guarantee, which would let the pipeline report health while skipping the editorial system.
2. When every replicated writer, retry, repair, editor, reviewer, and fallback path fails, the cause
   is infrastructure or a fundamental pipeline defect. That is an operational alarm, and the command
   reports it as one.

## Objectives

- Produce an editorially generated, evidence-grounded post for any requested `report_date` whenever
  repository evidence and a working model route exist.
- Design each subjective stage to survive partial agent failure and still promote the strongest
  usable artifact of its own type.
- Keep the fallback ladder inside the editorial pipeline, degrading to another model-produced
  artifact of the same or next useful type.
- Preserve the strongest grounded artifact at every point in the run.
- Keep evidence grounding and publication identity as mechanical eligibility conditions.
- Report total model-route failure as an infrastructure fault with a precise diagnostic.
- Reach a published, verified page early, then deepen editorial quality milestone by milestone.

## Design philosophy

The trade-off: **more model calls and more retained intermediates in exchange for a pipeline that
ends with a post someone would want to read.**

The governing principle:

> **Robustness means each editorial stage survives partial agent failure and still promotes the
> strongest usable artifact available from that stage.**

This makes the route, retry, repair, and promotion machinery load-bearing rather than polish. It is
the mechanism by which each stage reliably emits something useful.

Total failure of every route is treated as what it is: an infrastructure or pipeline defect. The
command writes an evidence digest for diagnosis, names the failing route category, and exits
nonzero. Keeping mechanical assembly out of the success path removes the incentive to appear healthy
while skipping editorial work.

This applies `docs/REPO_STYLE.md`'s **fix the design, not the symptom** and **long-term over
short-term**: quality signals move off the control path, and the pre-production state is used to
correct schemas and ownership boundaries now. It also respects **perfect is the enemy of good** --
M4 and M5 reach a published page with reused assets before later milestones deepen quality.

**Focus on important issues.** Review and implementation attention belongs on decisions that affect
correctness, maintainability, validation, and delivery: reliable stage output, replicated promotion,
evidence grounding, publication semantics, and observability. Exact call volumes, asset counts, class
names, and default constants are context rather than subjects for extended debate, and this plan
marks them revisable so they do not absorb review time.

**Gates stay grounded.** Every gate in this plan asserts something the change actually causes: a
stage still promotes under injected failure, a rerun makes fewer calls, prose outside a repaired
region is unchanged, a published page verifies. Where a bar could tempt false precision -- evidence
comparison across pipelines, retention defaults, replication counts -- the plan asks for coverage
plus explanation, or defers the number to measurement.

- Evidence strategy for uncertain methods: the reporter ships raw observations -- counts,
  denominators, degradation frequency by step, disagreement frequency, synthesis wins against the
  incumbent, retry and repair categories, ladder depth -- and stays advisory, outside command success
  criteria. Thresholds follow accumulated observation.

## Scope

- Build `agents.py` (typed route results, bounded classified retry, one repair attempt, one global
  route budget), `replication.py` (replication, voting, promotion under an incumbent contract), and
  `recovery.py` (ladder transitions and the diagnostic evidence digest).
- Define typed artifacts, an eligibility boundary, typed stage outcomes, and the incumbent contract.
- Reach a published verified page from the real editorial path early, then add stages.
- Harden every subjective stage against partial agent failure.
- Implement the nine-stage contract, reusing the approved V4 prompt package and authoring the
  genuinely missing stage assets from a guide derived from the prompt-engineering references.
- Extend `RunStore` with step outcomes and `best_artifact_id`; add a read-only reporter.
- Redesign the publication-contract ownership boundary and remove superseded modules.

## Non-goals

- `docs/BLOG_CONTRACT.md` stays under human ownership; this plan implements it as written.
- The publisher repository keeps its current import-and-build transaction; this plan integrates with
  it as-is.
- Evidence-collection algorithms keep their current behavior; this plan adds fallback paths and
  recording around them.
- Hermes keeps ownership of model and account selection behind the existing route boundary.
- `report_date` remains the sole published-post identity; reruns overwrite.
- The pre-lockdown pipeline contributes pure helpers; the new coordinator owns control flow.
- Prompt tuning belongs to the later measurement loop; this plan supplies working first versions.

## Current state summary

**Evidence layer: keep.** `repositories.py`, `roster_snapshots.py`, `mirrors.py`, `activity.py`,
`evidence.py` produce an `EvidencePacket`. `io_utils.py`, `atomic_paths.py`, `locks.py`
(`PhaseCache`), `run_state.py` (`RunStore`), and `routes.py` are infrastructure.
`CommandRouteRunner.run` (`routes.py:73`) is stateless per call.

**Editorial and gate layer: superseded.** `editorial.py`, `candidates.py`, `projection.py`,
`evaluation.py`, `activation.py`, `run_contracts.py`, `private_artifacts.py`, `fixture_hermes.py`,
`experiment_fixture_contract.py`, six `experiment_*` modules, two `rubric_calibration*` modules,
eight `automation/` drivers, eleven test modules.

**Two modules carry a second responsibility**, so both are redesigned rather than dropped:

- `bundles.py:14-18` imports `editorial`, `contracts`, and `activation` and embeds their types in
  its API (`bundles.py:36-37, 45-46, 72-87`). Pre-production status allows a direct redesign: a
  minimal publication-contract owner replaces those types outright.
- `contracts.py:394-411` binds the approved V4 prompt assets to their identities. That registry
  moves to `prompt_registry.py` as its own component.

**Pre-lockdown pipeline: pure helpers only.** `prompt_loader`, `pipeline_text_utils`,
`outline_llm.strip_xml_wrapper`, and `normalize_markdown_blog` (`outline_to_blog_post.py:395`)
transfer. Its control flow stays behind: exceptions escape from generators, reviewers, and polish
(`outline_to_blog_post.py:922-925, 965-968`); malformed referee output selects positional candidate
B (`depth_orchestrator.py:99-118`); "best" can mean draft zero or the first bracket winner
(`:249, :267`); cache identities omit content that should invalidate them; cache writes lack
atomicity; the primary score is distance from a target word count (`outline_to_blog_post.py:704`);
and the zero-candidate fallback is another model call that can fail (`:708-755`).

## User-facing contract

Four outcomes, each with one meaning.

| Outcome | Meaning | Artifact | Exit status |
| --- | --- | --- | --- |
| Success | An editorially generated article was generated, imported, built, and verified | published | 0 |
| Degraded | A stage produced a lesser but still editorially generated artifact | preserved, weaker | 0 |
| Incomplete | An artifact exists; publication did not finish | preserved as produced | nonzero, naming stage and step |
| Pipeline fault | The editorial pipeline could not produce an article | evidence digest written for diagnosis | nonzero, naming the diagnosed category |

**Pipeline fault carries a diagnosed category**, because the causes are genuinely different and an
operator needs to know which one they are looking at:

| Category | Meaning |
| --- | --- |
| `route_unavailable` | model routes failed to respond |
| `no_eligible_generation` | routes responded, and every candidate failed mechanical eligibility |
| `evidence_unavailable` | no repository evidence was obtainable for the date |
| `configuration` | settings unparseable, output root unwritable, mirror root unsafe |
| `implementation_defect` | an unexpected defect surfaced |

`no_eligible_generation` is the category an earlier draft missed. Every route can respond perfectly
while a systematic prompt, provenance, eligibility-contract, or implementation problem makes every
candidate ineligible. That is a pipeline fault, not a route outage, and diagnosing it as one would
send an operator looking in the wrong place.

From Step 9.1 onward the outcome is Incomplete at worst, because Step 9.1 has already written
`post.md`.

### Publication sequence under the atomic publisher

```
9.1  write post.md                      -> preserved from here on
9.2  import and build (one transaction) -> atomic; failure imports nothing, post.md survives
9.4  verify served page                 -> failure preserves the imported and built site
9.5  exit status
```

## Robustness model

**Reliability comes from the stages, not from recovery.** A stage replicates, survives ordinary
agent failures, reviews the survivors, and promotes the strongest. That is the architecture. The
recovery ladder below is a narrow preservation mechanism for the exceptional case where a stage
genuinely cannot produce its own artifact type at all -- with two writers, retries, repair, editors,
and reviewers, every Stage 6 path failing is rare and highly diagnostic. Movement down the ladder is
an event worth investigating, not a normal operating mode.

### Per-stage robustness contract

This table is the load-bearing part of the design.

| Stage | Continues to produce | While surviving |
| --- | --- | --- |
| 3 repository outline | a usable repository outline | failure of one generator, one merger, one reviewer, or the referee |
| 4 repository story | a usable repository story | failure of one writer, one editor, or one reviewer |
| 5 daily outline | a daily outline | failure of one ranker or one outline agent |
| 6 complete post | a complete post | failure of one writer, one editor, or one reviewer |
| 7 synthesis | the Stage 6 incumbent, untouched | any failure |

Partial failure degrades quality within the stage. A stage moves down the ladder only when every
generator fails or no candidate is eligible.

### Recovery ladder, kept narrow

When a stage cannot produce its type, the run falls back to the strongest artifact already promoted,
in this order: final synthesis, edited complete post, complete writer draft, a writer's expansion of
the daily outline, a writer's merge of the promoted repository stories, then the strongest usable
repository material. The two expansion levels are one more model call apiece, so the article stays
inside the editorial system rather than becoming a mechanical join.

Exhausting every recovery path is a **pipeline fault**, not editorial degradation. It means route
infrastructure failed, generation was systematically ineligible, the eligibility contract mismatches
what generators produce, or an implementation defect is present. `recovery.py` writes an evidence
digest for diagnosis and the command reports the diagnosed category and exits nonzero.

## Artifact and eligibility model

### Typed artifacts

```
EvidencePacket -> RepoOutline -> RepoStory -> DailyOutline -> CompletePost
```

### Typed stage outcomes

**The behavioral contract is what binds; the class names are a starting shape.** A stage caller can
always distinguish four situations, and an implementation that expresses them more simply is
welcome:

1. a candidate was selected over its peers;
2. an incumbent existed and remains strongest;
3. fewer agents survived than intended, a same-type artifact was still promoted, and the degradation
   is recorded;
4. no artifact of this type is available, with a categorical reason, so the caller moves one ladder
   level.

The starting implementation names these `Promoted[T]`, `PreservedIncumbent[T]`,
`DegradedPromotion[T]`, and `NoPromotedArtifact(reason)`. If implementation evidence shows a simpler
abstraction carrying the same four distinctions, adopt it and record the change; the tests assert
the behavior rather than the class names.

At a repository stage, case 4 removes that repository from downstream editorial input while every
other repository continues.

### Eligibility, distinct from preference

**Mechanical eligibility**: ranked candidates satisfy all of these:

- every evidence reference resolves within the run's evidence packets;
- cited material belongs to the correct repository and `report_date`;
- image paths come from approved evidence;
- `report_date` and publication identity are correct;
- output paths stay inside approved roots;
- machine-owned metadata is valid;
- evidence density holds: the article cites at least one resolvable evidence item for each
  repository it discusses, and every cited identifier resolves. Stated mechanically so trustworthiness
  stays measurable.

**Preference, scored or reviewed**: thematic strength, maker voice, narrative coherence, length,
treatment depth, heading style.

Ineligibility removes one candidate from contention; the run continues.

### Incumbent contract

1. Rank mechanically eligible candidates.
2. When an incumbent exists, retain it after reviewer, referee, or parsing failure.
3. Use deterministic selection among eligible peers when no incumbent can be displaced.
4. Apply deterministic repair to mechanical structure, keeping the repaired artifact outside
   editorial candidacy.

Rule 2 governs Stage 7: a synthesis replaces the promoted post on demonstrated improvement.

### Reviewer resolution order

1. parse strictly;
2. one bounded repair attempt;
3. salvage an unambiguous candidate identifier when present;
4. preserve the incumbent when one exists;
5. otherwise a stable deterministic choice among eligible candidates.

This replaces positional resolution, which turned parse failures into biased editorial decisions.

## Prompt and rubric asset plan

> Preserve provenance and identities. Reuse suitable existing assets. Author new versioned assets
> for the roles that lack one, and supersede an existing asset with a new version when the
> architecture requires it.

Preservation protects **provenance**, so a later reader can trace which text produced which post. It
does not freeze editorial decisions: the codebase is pre-production, and an asset whose assumptions
no longer fit is superseded by a `v5` version with its own recorded identity while the `v4` bytes
stay intact as history. `prompt_registry.py` records both. A superseding version carries a note in
the decisions directory saying what stopped fitting.

### Reuse as-is

Registered at `contracts.py:394-411`, keeping bytes and identities:

| Asset | Role |
| --- | --- |
| `daily_blog_author_v4.txt` | Stage 6 complete-post author, and the writer for ladder levels 4 and 5 |
| `daily_blog_rubric_v4.md` | complete-post and final-synthesis comparison; reusable for repository-story review |
| `daily_blog_referee_v4.txt` | anonymous comparison of two complete posts |
| `daily_blog_referee_repair_v4.txt` | repair of malformed complete-post referee JSON |
| `daily_blog_voice_examples_v4.md` | retained with current runtime and calibration ownership |
| `daily_blog_rubric_v3.md` | historical reference |

### Legacy prompts serve as references

`outline_repo.txt` and `outline_repo_targeted.txt` favor exhaustive inventory over editorial
reduction. `outline_global.txt` ranks by activity and count, where the contract holds that counts
are separate from editorial importance. `depth_referee_outline.txt` rewards commit counts and
target-length proximity. `blog_repo_markdown.txt` and `blog_markdown.txt` emphasize enumeration and
uniform coverage, the mechanical Aug. 24-25 failure mode. The `depth_polish_*` and
`blog_expand`/`trim`/`regenerate`/`word_band_retry` prompts contribute transformation ideas that sit
under the preservation and evidence contracts.

### Author these

| Stage | New assets |
| --- | --- |
| 3 | outline generator; outline merger; repository-outline rubric |
| 4 | story writer; story editor; story rubric, or an automated decision to reuse V4 (see M8) |
| 5 | ranking prompt and rubric; daily-outline generator and rubric |
| 6 | complete-post editor |
| 7 | synthesis prompt receiving incumbent, alternatives, reviewer feedback, rubric, and evidence |

Plus one generic versioned artifact-comparison prompt for the new intermediate types and one generic
structured-verdict repair prompt, so comparison and repair prose stays shared rather than duplicated
per stage.

New assets derive criteria from `docs/BLOG_CONTRACT.md`, keep evidence grounding as eligibility,
stay versioned and identity-recorded, and are exercised against captured evidence fixtures.

**Authored prompts lead with the desired action.** Small models handle positive instruction more
reliably than prohibition, and a negated instruction can invert into the behavior it meant to
prevent. Each prompt opens with what to do, and omits the unwanted alternative rather than naming
it:

| Write | In place of |
| --- | --- |
| "Rank stories by narrative importance and technical interest." | "Do not rank by commit count or repository size." |
| "Cite the evidence identifier supporting each factual claim." | "Never make claims without citations." |
| "Return one JSON object with `winner` and `reason`." | "Do not add prose around the JSON." |
| "Write in first-person work-log voice." | "Avoid sounding like an automated summary." |

State a boundary explicitly where correctness depends on it, such as producing only content the
evidence supports. Elsewhere, omission plus a clear positive instruction carries more weight than a
prohibition.

## Data inventory

| Owner | Responsibility |
| --- | --- |
| `RunStore` (`run_state.py:15`) | artifact identities, parent relationships, promotion decisions, eligibility outcomes, degradation reasons, `best_artifact_id` |
| `PhaseCache` (`locks.py:50`) | resumable hash-addressed stage outputs |
| Run event stream | operator diagnostics keyed by contract step ID |
| Read-only reporter | advisory aggregates |

Artifacts are immutable and named `FINAL_SYNTHESIS`, `EDITED_COMPLETE_POST`,
`COMPLETE_WRITER_DRAFT`, `OUTLINE_EXPANSION`, `STORY_MERGE`, `REPO_MATERIAL`. `best_artifact_id`
moves through valid promotion or ladder transitions.

### Logging organization and retention

```
out/<owner>/daily_blog/<report_date>/
	post.md                       published artifact, overwritten per Core 1
	summary.jsonl                 long-lived, append-only, one record per run
	runs/<run_id>/
		events.jsonl              detailed events for this run only
		<intermediates>           cached stage outputs, candidate artifacts
```

Logs are keyed by `report_date`, historical dates included; each run gets a `run_id`. Detailed
events live inside the run directory, so expiry is a directory delete. `report_date` decides where a
run belongs; run creation time decides when its detailed diagnostics expire, so regenerating a 2025
post today starts today's clock. `daily_blog.logging.detailed_retention_days` governs whole run
directories. Summaries carry per-step roll-ups so reporting survives expiry. Published posts and
summaries persist.

## Architecture boundaries and ownership

- **`agents.py`**: the single site of model calls. Typed results, bounded classified retry, one
  structured-output repair attempt, one global route budget.
- **`replication.py`**: replication of eligible alternatives, reviewer voting, promotion under the
  incumbent contract, deterministic selection among eligible peers.
- **`recovery.py`**: ladder transitions and the diagnostic evidence digest.
- **`prompt_registry.py`**: prompt and rubric asset identities.
- **`publication_contract.py`**: the minimal publication-identity owner that `bundles.py` uses.
- **`orchestrator.py`**: the single coordinator: sequences stages, owns durable writes, and keeps
  editorial policy inside stage functions.

### Route failure taxonomy

Error handling stays narrow and typed so implementation defects surface as defects.

| Class | Handling |
| --- | --- |
| Recoverable route failure: timeout, start failure, nonzero exit, empty response | bounded retry, then typed failure result |
| Repairable structured output | one repair attempt, then salvage, then incumbent or deterministic choice |
| Repository evidence unavailable | that repository degrades; others continue |
| Terminal: configuration, path safety, identity, cache corruption | preserve completed artifacts, return a precise nonzero result |
| Unexpected implementation defect | preserve completed artifacts, propagate as a defect |

### Concurrency boundary

1. discover repositories and gather deterministic evidence;
2. freeze immutable repository packets;
3. run independent route calls concurrently under one global budget;
4. serialize cache writes, promotion decisions, incumbent updates, and run events through the
   coordinator.

A busy multi-repository day runs on the order of a hundred model calls, since every subjective step
is replicated across every repository. The route budget, per-repository concurrency, and resumable
caching exist to make that volume practical and repeatable. The exact count follows from the
configured replication counts and the day's repository set.

### Mapping (milestones / workstreams -> components / patches)

| Milestone | Component | Review boundary |
| --- | --- | --- |
| M1-M3 | `agents.py`, artifact types, `replication.py` | `architect` review of promotion and eligibility |
| M4-M5 | Stage 6 on fixtures, Stages 8-9, coordinator, command | `reviewer` review of the published path |
| M6-M8 | prompt guide, Stages 3-4, new assets | per-stage `reviewer` review |
| M9 | per-stage robustness, ladder transitions | `architect` review of the degradation model |
| M10-M11 | Stages 5 and 7 | per-stage `reviewer` review |
| M12-M13 | parallelism, caching, observability | `reviewer` review of the concurrency boundary |
| M14-M16 | validation, redesign removal, documentation | `reviewer` review of validation evidence |

## Milestone plan

Every milestone completes through manager and subagent work alone. Gates are captured fixtures,
synthetic transitions, debug harnesses, and automated behavior tests, so the sequence runs to
completion unattended.

**Review gates are manager-dispatched subagents.** Where a milestone names an `architect` or
`reviewer` gate, the manager spawns that subagent, supplies the artifact and the decision rule
below, and continues on its returned verdict. The sequence proceeds without waiting on the human.

| Gate | Decision rule the manager supplies |
| --- | --- |
| `architect` after M3 | Accept when `replicate`, `review`, and `promote` are separately callable, stage-specific policy lives in stage functions, and resolution is independent of candidate position. |
| `reviewer` after M5 | Accept when the controlled E2E reaches a verified page and `best_artifact_id` names an editorially generated artifact. |
| `architect` after M9 | Accept when the Stages 3, 4, and 6 robustness rows each have a passing failure-injection test, ladder movement requires no eligible candidate of that type, and pipeline faults report a diagnosed category. |
| `reviewer` on the M14 report | Accept when every fixture date reaches a published verified page from the editorial path and evidence-packet parity holds. |

A returned rejection carries its reason, and the manager dispatches the fix as the next work package
in that milestone.

**The pipeline is usable from M12.** M13 through M15 add observability, recorded validation, and
cleanup. Daily runs can begin as soon as M12 completes; historical validation supports removal rather
than gating ordinary use.

| M | Title | Summary | Goal |
| --- | --- | --- | --- |
| M1 | Route layer | `agents.py`, failure taxonomy, route budget | Model calls return typed results |
| M2 | Typed artifacts and eligibility | Five artifact types, eligibility predicates | Grounding is mechanical and testable |
| M3 | Replication and promotion | `replication.py`, incumbent contract | Stages promote without owning failure policy |
| M4 | Stage 6 on fixtures | Complete post from a captured packet, reused V4 assets | The first editorially generated article |
| M5 | Publication path and command | Stages 8-9, coordinator, `make_blog.py` | A published, verified page |
| M6 | Prompt authoring guide | Guide derived from the prompt-engineering references | New assets have a documented basis |
| M7 | Stage 3 repository outlines | Generators, mergers, rubric, promotion | Promoted repository outlines |
| M8 | Stage 4 repository stories | Writers, editors, rubric decision, promotion | Promoted repository stories |
| M9 | Per-stage robustness and ladder | Partial-failure survival, ladder transitions, digest | Stages emit their own type under partial failure |
| M10 | Stage 5 ranking and daily outline | Rankers, outline agents, rubrics | A promoted daily outline |
| M11 | Stage 7 synthesis | Synthesizers, incumbent comparison | Synthesis improves or the incumbent stands |
| M12 | Multi-repository scale | Parallelism, budget, resumable caching | A ~120-call day runs practically |
| M13 | Observability and retention | Event stream, reporter, retention | Step behavior measurable by step ID |
| M14 | Automated validation | Fixture suite, historical dates, harnesses | Recorded evidence the path works |
| M15 | Redesign and removal | Publication contract, registry, module removal | One pipeline remains |
| M16 | Documentation close-out | Changelog, transcript, operations docs | Documentation matches the system |

Per-milestone detail below records dependencies, deliverables, and done checks. Entry criteria are
the predecessor's exit criteria unless stated.

### Milestone: M1 route layer

- Depends on: none. Deliverables: `agents.py` with `AgentResult`, the five-class failure taxonomy,
  bounded retry, one repair attempt, and `RouteBudget`.
- Exit criteria: `AgentResult` owns transport and execution metadata -- `role`, `text`, `ok`,
  `failure`, `attempts`, `duration_s`, `repaired`, `resumed`, `route_name`; recoverable categories
  retry a bounded number of times; terminal failures and implementation defects propagate as
  themselves; `RouteBudget` is one process-wide semaphore.
- Done checks: a stub runner drives one test per taxonomy class.
- Parallel-plan ready: no -- one small module.

### Milestone: M2 typed artifacts and eligibility

- Depends on: M1. Deliverables: the five artifact types; eligibility predicates including the
  evidence-density rule; the four typed stage outcomes.
- Exit criteria: an ineligible candidate stays out of ranking while the run continues; each artifact
  type is distinct so ladder transitions carry same-type artifacts.
- Done checks: a test per eligibility predicate using inline candidates.
- Parallel-plan ready: yes -- predicates are independent.

### Milestone: M3 replication and promotion

- Depends on: M2. Deliverables: `replication.py` with `replicate`, `review`, `promote`; the
  incumbent contract; the reviewer resolution order.
- Exit criteria: `review` varies candidate order between reviewers per contract §77; an incumbent
  survives reviewer, referee, and parse failure; each stage supplies its own typed fallback;
  resolution stays independent of candidate position.
- Done checks: a malformed reviewer response resolves through repair, salvage, or incumbent.
- Parallel-plan ready: no -- one small API surface.

### Milestone: M4 Stage 6 on fixtures

- Depends on: M3. Deliverables: Stage 6 writing, editing, and promotion using the reused V4 author,
  rubric, referee, and repair assets; a fixture route runner replaying recorded responses.
- **The fixture matches Stage 6's eventual input contract exactly**: a `DailyOutline`, a set of
  promoted `RepoStory` artifacts, and the evidence packets -- the same objects M10 will supply for
  real. The upstream artifacts are captured, and the Stage 6 input pathway is the permanent one, so
  M4's code survives unchanged when the earlier stages come online. This keeps M4 a contract-first
  milestone rather than scaffolding that later needs removing.
- Exit criteria: from that fixture, replicated writers and editors produce candidates and a
  rubric-based promotion selects one `CompletePost`; the same path runs against a live route when
  one is available, as non-gating corroboration.
- Done checks: the fixture path runs offline and produces a promoted `CompletePost`; Stage 6 reads
  only artifacts of the types M10 and M8 will produce.
- Parallel-plan ready: no.

### Milestone: M5 publication path and command

- Depends on: M4. Deliverables: Stage 8 validation and repair with machine-owned metadata
  construction; Stage 9 publication and verification; the coordinator; `make_blog.py`.
- Exit criteria: a fixed report date runs from command to verified page through disposable
  publication roots; a forced verification failure preserves the imported site and exits nonzero
  naming the step; `--yes` and the replacement prompt give way to unconditional overwrite.
- Done checks: the controlled E2E passes; `best_artifact_id` names an editorially generated artifact.
- Parallel-plan ready: yes -- Stage 8 and Stage 9 are separable.

### Milestone: M6 prompt authoring guide

- Depends on: M5. Deliverables:
  `docs/active_plans/decisions/daily_blog_prompt_authoring_guide.md`, owned by a `reviewer` subagent.
- Exit criteria: the guide covers role and persona framing, rubric-based comparative evaluation,
  structured output contracts that survive repair, few-shot example selection for voice, and
  comparison designs that resist order and position bias, each recommendation citing its source; it
  carries `docs/REPO_STYLE.md`'s prompt-positively principle; it reads the reused V4 assets first so
  new prompts sit consistently beside them.
- Sources: `~/BOOKS_to_CONVERT/SORTED_SUBJECTS_MD/prompt_engineering/`, roughly 51,500 lines across
  eleven titles, summarized rather than read in full. Primary titles:
  `LLM_Prompt_Engineering_for_Developers_the_Art_and_Science-2024.md`,
  `Prompt_Engineering_for_LLMs_the_Art_and_Science_of_Building_Large_Language-2023.md`,
  `Prompt_Engineering_for_Generative_AI_Future-Proof_Inputs-2024.md`,
  `Optimizing_Prompt_Engineering_for_Generative_AI-2025.md`.
- Parallel-plan ready: no -- one document, one owner.

### Milestone: M7 Stage 3 repository outlines

- Depends on: M6. Deliverables: outline generator and merger prompts; repository-outline rubric;
  Stage 3 promotion wired to `replication.py`; the generic comparison and repair prompts.
- Exit criteria: from captured evidence, replicated generators and mergers produce candidates and a
  rubric-based promotion selects one `RepoOutline`; the rubric judges editorial merit. Replication
  counts start at the contract's floor of two and are configuration, not a fixed milestone contract.
- Done checks: fixture path green; events carry step IDs `3.1` through `3.4`.
- Parallel-plan ready: yes -- prompt authoring and stage wiring are separable.

### Milestone: M8 Stage 4 repository stories

- Depends on: M7. Deliverables: story writer and editor prompts; the story-rubric decision; Stage 4
  promotion.
- Exit criteria: a promoted `RepoStory` per repository from fixtures. The story-rubric decision is
  automated: a `reviewer` subagent scores a captured candidate set with `daily_blog_rubric_v4.md`
  and with a drafted narrower rubric, and the plan adopts whichever separates strong from weak
  candidates more consistently, recording the comparison.
- Done checks: fixture path green; the rubric comparison is recorded in the decisions directory.
- Parallel-plan ready: yes.

### Milestone: M9 robustness for Stages 3, 4, and 6

Scoped to the stages that exist at this point. Stage 5 is hardened inside M10 and Stage 7 inside
M11, as part of building them, so no milestone gate depends on a stage that has yet to be written.

- Depends on: M8. Deliverables: the per-stage robustness contract for Stages 3, 4, and 6; the
  recovery ladder in `recovery.py` across the levels those stages produce; the diagnostic evidence
  digest and pipeline-fault reporting with its diagnosed categories.
- Exit criteria: Stages 3, 4, and 6 each promote their own artifact type when one generator, one
  editor, one reviewer, or the referee fails; a stage moves down the ladder only when every
  generator fails or no candidate is eligible; exhausting recovery reports a pipeline fault with its
  diagnosed category and writes the evidence digest.
- Done checks: one failure-injection test per robustness-table row for Stages 3, 4, and 6; a test
  distinguishing `route_unavailable` from `no_eligible_generation`.
- Parallel-plan ready: yes -- per-stage hardening packages are independent.

### Milestone: M10 Stage 5 ranking and daily outline

- Depends on: M9. Deliverables: ranking prompt and rubric; daily-outline generator and rubric;
  Stage 5 promotion.
- Exit criteria: a promoted `DailyOutline`; ranking sets emphasis while every usable repository story
  stays available; the outline structures the article on editorial grounds; Stage 5 satisfies its
  robustness row, continuing to produce a daily outline when one ranker or one outline agent fails.
- Done checks: a test asserting a low-ranked repository's material stays available to outline agents;
  the Stage 5 failure-injection test.
- Parallel-plan ready: yes.

### Milestone: M11 Stage 7 synthesis

- Depends on: M10. Deliverables: synthesis prompt; Stage 7 promotion with the incumbent as an active
  candidate.
- Exit criteria: a synthesis replaces the Stage 6 artifact on demonstrated improvement; with every
  synthesis failing or judged no better, the incumbent stands unchanged, which is Stage 7's
  robustness row.
- Done checks: incumbent-retention test green; the Stage 7 failure-injection test completes the
  robustness table.
- Parallel-plan ready: no.

### Milestone: M12 multi-repository scale

- Depends on: M11. Deliverables: repository parallelism under one `RouteBudget`; `PhaseCache` keyed
  per repository and step with complete immutable fingerprints and atomic writes; the coordinator's
  serialized durable-write boundary.
- Exit criteria: a multi-repository fixture date completes within the configured budget; one
  repository failing every route leaves the others promoted; a rerun resumes and makes strictly
  fewer calls.
- Done checks: repository isolation test green; route calls stay within the single budget.
- Parallel-plan ready: no -- one concurrency boundary.

**M12 completes the working system.** Daily runs can begin here. M13 through M15 add measurement,
recorded validation, and cleanup around a pipeline that already produces the blog.

### Milestone: M13 observability and retention

- Depends on: M12. Deliverables: run event stream keyed by step ID; per-run `events.jsonl`;
  date-level `summary.jsonl` with per-step roll-ups; `automation/report_blog_reliability.py`;
  configurable retention with expiry at command start.
- Exit criteria: the reporter answers contract §11's questions with raw observations and
  denominators, stays advisory, and counts infrastructure faults separately from editorial
  degradation; expiry removes run directories by creation time while posts and summaries persist.
- Done checks: reporting works for a date whose detailed tier has expired.
- Parallel-plan ready: yes.

### Milestone: M14 automated validation

- Depends on: M13. Deliverables: a self-generated, no-egress five-case suite covering fixed-date
  busy, quiet, single-repository, screenshot-bearing, and degraded-dependency publication paths;
  synthetic transition harnesses for ladder levels and publication failures; and a report under
  `docs/active_plans/reports/`. Each case is built and run in a manager-created disposable root.
  The report records the command, commit, date, `external_route_used: false`, coverage inventory
  and explanation, terminal outcome, ladder depth, page/bundle/summary digests, disk observation,
  and generated capture or fault-artifact SHA-256 where available, for every temporary harness
  retained long enough to run. It records a removal disposition for each such harness before M15.
  Local historical-date capture is optional no-egress corroboration: it records either a sealed
  limited local observation or `historical_local_evidence_unavailable`; neither requires an
  artifact transfer nor changes acceptance. A live `make_blog.py --yesterday`/model/network run is
  optional enrichment only and is recorded as `not_run` when no configured external route exists.
- Exit criteria: all five generated cases produce a published, verified page through the editorial
  path. Their evidence tuples and coverage explanations have recorded parity with the separately
  sealed case baselines; packet byte equality is not required because deliberate fallbacks can
  change packets. The fresh `reviewer` subagent accepts only this mechanical record integrity,
  publication/page verification, and tuple/explanation parity, not subjective prose quality.
  Per-run disk use is measured so any retention default follows evidence.
- Done checks: the report records every case's ladder depth and investigates any infrastructure
  fault; optional historical and live-external entries remain explicitly non-gating.
- Parallel-plan ready: yes -- dates are independent runs.

### Milestone: M15 redesign and removal

- Depends on: M14. Deliverables: `publication_contract.py` replacing `bundles.py`'s dependence on
  `editorial`, `contracts`, and `activation`; `prompt_registry.py` extracted from
  `contracts.py:394-411`; removal of the superseded modules, drivers, tests, and experiment prompts.
- Exit criteria: imports resolve across the repository; retained prompt assets continue to be
  identified by the prompt registry at use time; pre-production status keeps the redesign direct,
  with the new interfaces standing alone. Prompt copy and historical byte snapshots are not a test
  gate: an approved prompt revision receives a new recorded identity.
- Done checks: record and remove temporary M14 E2Es before the aggregate runner. After each
  coherent migration/removal group, run focused daily-blog checks and the sole controlled E2E.
  After the coordinated migration is complete, run the aggregate E2E runner once and the full
  pytest suite once. This sequence avoids arbitrary repeated broad-suite gates while retaining
  final repository-wide evidence.
- Parallel-plan ready: no -- one coordinated sweep.

### Milestone: M16 documentation close-out

  refreshed `docs/DAILY_BLOG_OPERATIONS.md` and `docs/CODE_ARCHITECTURE.md`, superseded plans moved
  to `docs/archive/` with `git mv`, updated approved-prompt bookkeeping.
- Final validation: complete and show one reader-visible publication for `report_date=2026-08-28`
  using the public `make_blog.py --yesterday` entrypoint semantics. Verify its terminal summary,
  sealed bundle integrity, and published page. The required unattended path uses a separately
  captured or self-generated no-egress evidence injection (or the existing controlled runner) when
  an external route is unavailable; a live model/network run is optional corroboration only and
  records `not_run` or its unavailable reason without credentials or human action. The displayed
  result identifies whether its provenance is fixture-backed or live and does not claim that
  synthetic prose establishes editorial prose quality.
- Exit criteria: documentation describes the shipped nine-stage pipeline, the four outcomes, the
  ladder, and the advisory reporter. Operations documentation describes verified automatic
  same-date replacement for the scheduled/noninteractive command; obsolete interactive overwrite
  language is historical context only. Prompt bookkeeping mechanically records retained registry
  identities before and after migration without editing, approving, or displaying prompt prose.
- Done checks: `pytest tests/test_markdown_links.py` green.
- Parallel-plan ready: no.

## Acceptance criteria and gates

- Per coherent production change or removal group: run focused pytest coverage and the controlled
  publication E2E. Keep a temporary harness only while it captures its recorded implementation
  evidence. After the coordinated M15 migration removes those temporary E2Es, run the aggregate
  E2E runner and the full pytest suite once; use M16's applicable documentation and link checks
  after that final code-validation pass. This preserves final repository-wide coverage without
  turning every patch into an arbitrary broad-suite gate.
- Repository-rule conformance, checked as each milestone lands:
  - Permanent tests keep inputs inline and write only into `tmp_path`; captured data lives in the
    generated `output_blog_capture/` directory.
  - Permanent tests run offline against stub runners; real routes and the publisher appear only in
    `tests/e2e/`.
  - `automation/report_blog_reliability.py` is runnable, so it carries `#!/usr/bin/env python3` and
    the executable bit, per `tests/test_shebangs.py`.
  - New modules stay under the 1000-line limit; a module approaching it splits along an ownership
    boundary rather than growing.
  - Plan artifacts land in `docs/active_plans/active/`, `reports/`, and `decisions/` with snake_case
    names; durable docs keep SCREAMING_SNAKE_CASE.
  - Moves and removals use `git mv` and `git rm`.
  - `docs/CHANGELOG.md` is 512 lines today; M16 checks it against the 800-line rotation threshold and
    runs `devel/rotate_changelog.py` when the new entries cross it.
  - A test that would force an unrequested production behavior is treated as the defect, per the
    repository's plan-and-test guidance.
- Robustness gate: from M9 onward, every row of the per-stage robustness table has a passing
  failure-injection test.
- Editorial-success gate: from M5 onward, the controlled E2E asserts `best_artifact_id` names an
  editorially generated artifact.
- Removal gate: M15 begins after the M14 report records the five generated fixture cases and the
  mechanically defined reviewer acceptance. Historical local capture is corroboration or a
  structured unavailable record, never a completion dependency.
- Final public-entrypoint demonstration: M16 records and displays the `2026-08-28` publication
  through `--yesterday` semantics, with terminal-summary, sealed-bundle, and reader-page evidence.
  A controlled no-egress injected-evidence run is the required completion path; live external
  corroboration remains optional and explicitly provenance-labelled.
- Independent review gate: `architect` after M3 and M9, `reviewer` after M5 and on the M14 report.

## Test and verification strategy

Tests are classified against the `docs/PYTEST_STYLE.md` checklist. A check earns permanence when it
tests logic that could plausibly be wrong, stays stable without code changes, asserts behavior rather
than topology or tunables, runs offline in well under a second, and writes only inside `tmp_path`.
Checks that fail the checklist run as temporary harnesses during implementation and are removed
after their evidence is recorded.

### Permanent behavior tests

1. Each stage promotes its own artifact type when one generator, one editor, or one reviewer fails --
   one test per robustness-table row.
2. A later-stage failure leaves the incumbent unchanged.
3. An ineligible candidate stays out of ranking while the run continues.
4. Failure of one repository leaves the other repositories' artifacts available downstream.
5. Ranking sets emphasis while every usable repository story stays available.
6. A stylistic or word-band miss remains usable and is recorded.
7. A rerun with changed evidence or a changed prompt produces a fresh result rather than a stale
   reused one. Stated as observable behavior; the fingerprint construction that achieves it stays an
   implementation choice verified by harness.
8. Total route failure reports an infrastructure fault and writes the evidence digest.

Candidate-ordering behavior and exact fingerprint composition are verified as M3 and M12 exit
criteria and by temporary harness, since asserting them permanently would pin topology that
contract §8 marks free to evolve.

### Temporary implementation harnesses

Temporary harnesses may exist while a milestone is being implemented. M14 records the command,
commit, date where applicable, no-egress result, outcome, and available artifact digest for each,
then they are removed. This includes exact reviewer/referee topology, retries and delay behavior,
route-call counts, forced process failures, publication-failure sequences, live-service behavior,
historical comparisons, prompt copy, defaults, cache-fingerprint recipes, and the live
`make_blog.py --yesterday` run. These assert implementation topology or tunables that contract
§8 marks free to evolve, so they stay outside the permanent suite.

Do not use byte equivalence, literal prompt copy, step names, field lists, role counts, or internal
call topology as permanent gates. The narrow exceptions are protocol integrity digests and the
exact two-summary shape required by the external bundle importer; both prove an integration
boundary rather than editorial output equivalence.

### Controlled permanent E2E

One fixed-date, synthetic, disposable-root path, outside pytest per `docs/E2E_TESTS.md`:

```text
command -> evidence -> replicated editorial stages -> complete article -> import and build -> verify
```

Publication-path behavior -- same-date overwrite, artifact preservation on publication failure,
structured nonzero exit -- lives here, where real filesystem and publisher interaction belong.

### Where captured data lives

`docs/PYTEST_STYLE.md` keeps test inputs inline and treats a committed `tests/fixtures/` directory as
shared infrastructure requiring explicit human sign-off. The repository has no such directory today,
and this plan keeps it that way:

- **Permanent pytest tests** build their inputs inline -- a short literal `EvidencePacket`, a couple
  of candidate strings, a stub route runner defined in the test file -- and write file-shaped inputs
  into `tmp_path` at runtime.
- **Captured real-world data** (recorded route responses, evidence packets from historical dates)
  is generated by a capture harness into a root-level `output_blog_capture/` directory covered by
  the existing root-scoped ignore rule. It feeds `tests/e2e/` runs and temporary harnesses, and
  stays out of the fast pytest lane.
- The M4, M7, M8, and M14 milestones use captured data in that generated directory, so a milestone
  can regenerate what it needs rather than depending on committed sample files that can drift out of
  existence.

### Full repository verification

```bash
source source_me.sh && pytest tests/ -k daily_blog
source source_me.sh && python3 tests/e2e/e2e_daily_publication.py
source source_me.sh && bash tests/e2e/run_all.sh
source source_me.sh && pytest tests/
```

## Risk register

Ordered by impact on correctness, validation, and delivery.

| Risk | Impact | Trigger | Owner | Mitigation |
| --- | --- | --- | --- | --- |
| Stage-level fragility pushed onto the ladder | Stages skip instead of degrading; quality drops a level at a time while runs still succeed | A stage moves a level on partial rather than total failure | `expert_coder` | Per-stage robustness contract with one failure-injection test per row; a level move requires no eligible candidate of that type |
| Route layer absorbing implementation defects | Real bugs appear as editorial degradation and stay hidden | Broad exception handling in the route layer | `expert_coder` | Five-class taxonomy; a test asserting an injected defect propagates as a defect |
| A second state authority beside `RunStore` | Two answers to "what is the best artifact" | A ledger is built as a parallel authority | `expert_coder` | `best_artifact_id` lives in `RunStore`; M2 exit criterion keeps ownership single |
| Eligibility rules becoming abort conditions | The gate design returns under a new name | An ineligible candidate ends a run | `architect` | Ineligibility removes one candidate; test 3 guards it |
| Concurrent workers writing durable state | Corrupted cache or run record | A stage writes directly from a worker | `expert_coder` | Coordinator serializes durable writes; route calls run concurrently |
| Publication redesign breaking imports | The publication path stops resolving | `publication_contract.py` lands before consumers move | `integrator` | Pre-production redesign lands with its consumers in one group; four verification commands per group |
| Prompt assets losing recorded identity | The reused V4 assets drift from their registry | The registry moves without identity checks | `integrator` | `prompt_registry.py` extracted first; retained assets resolve to recorded identities before and after migration |
| New prompts judging importance by counts | Ranking drifts toward mechanical enumeration, the Aug. 24-25 failure mode | A legacy prompt is copied rather than referenced | `coder` | Legacy prompts classified as references; authoring acceptance judges editorial merit |
| Retained intermediates filling the disk | Unattended runs degrade the machine | Every run keeps candidates and packets | `coder` | Retention deletes whole run directories by creation time, tuned from M14 measurements |
| Plan-implementation drift across sixteen milestones | Later work builds on assumed interfaces | Packages start before dependency exit criteria | `integrator` | Explicit `Depends on`; exit criteria checked before entry |

## Documentation close-out requirements

- Closed plan / progress record: `docs/archive/daily_blog_rebuild.md`;
  `docs/active_plans/reports/daily_blog_rebuild_validation.md` holds M14 evidence; superseded plans
  move to `docs/archive/` with `git mv`.
- `docs/CHANGELOG.md` entry: dated sections for additions, behavior changes, and removals, plus a
  `### Decisions and Failures` entry recording that fail-closed gating inverted the robustness goal,
  and that a deterministic floor was set aside as a success path because it would let the pipeline
  appear robust while skipping the editorial stages.
  section per `AGENTS.md`; `docs/DAILY_BLOG_OPERATIONS.md` and `docs/CODE_ARCHITECTURE.md` describe
  the nine stages, the four outcomes, the ladder, and the advisory reporter.

## Resolved decisions

- **Robustness lives inside the stages.** Each subjective stage survives partial agent failure and
  promotes its own artifact type. The ladder degrades to another model-produced artifact of the same
  or next useful type.
- **Exhausted recovery is a pipeline fault with a diagnosed category.** When every replicated
  writer, retry, repair, editor, reviewer, and recovery path fails, the cause is a fundamental
  problem rather than editorial weakness. An earlier draft called this an infrastructure fault and
  equated it with total route failure, which was wrong: routes can respond perfectly while a
  systematic prompt, provenance, eligibility-contract, or implementation problem makes every
  candidate ineligible. The command reports `route_unavailable`, `no_eligible_generation`,
  `evidence_unavailable`, `configuration`, or `implementation_defect`, writes an evidence digest,
  and exits nonzero. Mechanical assembly stays out of the success path.
- **Recovery stays narrow.** Reliability comes from stages that survive partial agent failure, not
  from a sophisticated fallback system. Ladder movement is exceptional and diagnostic, and the
  robustness table is the load-bearing part of the design.
- **Milestone scope matches what exists.** M9 hardens Stages 3, 4, and 6; Stage 5 and Stage 7 are
  hardened inside the milestones that build them, so no gate depends on a stage yet to be written.
- **M4 is contract-first.** Its captured fixture matches Stage 6's eventual input shape -- a
  `DailyOutline`, promoted `RepoStory` artifacts, and evidence packets -- so the Stage 6 pathway built
  there is the permanent one rather than scaffolding to remove later.
- **Milestones complete through manager and subagent work.** Gates are captured fixtures, synthetic
  transitions, debug harnesses, and automated behavior tests. Live model runs serve as non-gating
  corroboration, so the sequence runs to completion unattended.
- **Pre-production status allows direct redesign.** `publication_contract.py` and
  `prompt_registry.py` replace the coupled responsibilities in `bundles.py` and `contracts.py`
  outright, and the new interfaces stand alone.
- **Publisher atomicity accepted.** `import_publication_bundle.py:925-940` builds inside staging and
  removes the staging tree on failure, so Steps 9.2 and 9.3 collapse into one atomic transaction.
  A site that fails to build stays off the server, and Step 9.1 has already written `post.md`.
- **Provenance preserved; assets improvable.** The V4 and v3 assets keep their bytes and identities
  so past posts stay traceable, and new assets cover the roles that lack one. Because the codebase
  is pre-production, an asset whose assumptions no longer fit the new architecture is superseded by a
  recorded `v5` version rather than being worked around.
- **Behavioral contracts bind; class names and file layout stay revisable.** The stage-outcome
  taxonomy and module boundaries are a starting shape, and tests assert behavior so a simpler
  abstraction can replace them on evidence.
- **Evidence grounding is eligibility**, with trustworthiness stated as the mechanical
  evidence-density rule.
- **`best_artifact_id` replaces numbered ladder levels in code.**
- **Reviewer resolution is position-independent**, replacing the positional default that turned
  parse failures into editorial decisions.
- **The pre-lockdown pipeline contributes pure helpers**, and the coordinator owns control flow.

## Open questions and decisions needed

None block execution. Each resolves through recorded observation.

- **`score_post` weighting.**
  - Decision owner: `expert_coder`, with `tester` producing observations.
  - Evidence and decision rule: record both the reviewer's choice and the deterministic choice on
    every promotion. Once promotions accumulate, a persistent disagreement rate means the weights
    need re-fitting for their role of standing in when reviewers are unavailable. The threshold comes
    from the observed distribution.
- **Whether Stage 7 synthesis earns its cost.**
  - Decision owner: `architect`, on `tester` evidence.
  - Evidence and decision rule: run synthesis and record wins against the incumbent, since contract
    §11 asks whether synthesis usually improves the promoted input. A persistently low win rate
    invokes §464's "when synthesis is expected to improve the result".
- **Which steps need redesign.**
  - Decision owner: `coder`, on reporter evidence.
  - Evidence and decision rule: the reporter emits degradation frequency by step with denominators.
    Once a distribution exists, steps outside the healthy band are candidates for the §12 response --
    revise their inputs, decomposition, instructions, prompts, rubric, validation, or reviewer
    arrangement.
- Non-blocking follow-up: per-step replication counts start at the contract's floor of two. Raising
  them where disagreement is frequent is a natural tuning pass under contract §8.

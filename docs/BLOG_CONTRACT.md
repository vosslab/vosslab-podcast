Disclaimer: This is the first draft of the blog contract, authored by a human on Aug 29, 2026; agents do not edit this 
with out prior approval from the human. This contract defines the required behavior and quality goals of the blog 
pipeline. It does not freeze the current implementation.

# BLOG_CONTRACT.md

# Daily Blog Creation Contract

## Purpose

The daily blog pipeline turns one day of repository activity into one complete, evidence-grounded blog post.

The pipeline is designed around three principles:

1. **Generate alternatives.** Subjective LLM work is replicated so important decisions do not depend on one generation.
2. **Review and promote.** Candidate artifacts are compared using explicit rubrics, and stronger work is promoted through the pipeline.
3. **Preserve successful work.** Later stages may improve an artifact, replace it with something demonstrably better, or fail. They must not destroy the strongest usable artifact already produced.

The recurring editorial pattern is:

**replicate → review → promote → replicate → review → promote**

The pipeline deliberately trades additional computation for editorial quality.

---

# Contract Guarantees

## 1. Command behavior

When:

`make_blog.py --yesterday`

is run, the pipeline attempts to create and publish one complete blog post for yesterday.

The requested date is the `report_date` and is the identity of the generated blog post.

Running the pipeline again for the same `report_date` creates the post again and overwrites the previous generated post. The blog pipeline does not maintain generated revisions or versions.

## 2. Complete daily article

The final artifact is one cohesive daily blog post.

Repository-level stories are intermediate artifacts used to construct the complete article. They are not required to remain separate sections in the final post.

Repository stories may be combined, reorganized, shortened, referenced briefly, or omitted when constructing the daily article.

Repository boundaries do not dictate final article structure.

The final article should read as one blog post written about the day's work, not as repository summaries concatenated together.

## 3. Replicated generation

Subjective LLM creation stages use multiple independent candidate generations when practical.

Independent candidates should receive equivalent evidence, instructions, and rubrics. One candidate should not become canonical merely because it was generated first.

Replication is used throughout both repository-level processing and complete-blog processing.

Replication creates competing alternatives, not revisions of a single canonical draft.

## 4. Review and promotion

Important subjective decisions are made through explicit promotion steps.

Reviewers receive:

- multiple candidate artifacts;
- the evidence needed to evaluate them when appropriate;
- an explicit rubric describing what constitutes the stronger artifact.

Reviewers compare candidates rather than merely approving the output of the preceding agent.

Review should itself be replicated where practical.

Candidate ordering should be reversed or randomized between reviewers when practical to reduce ordering bias.

Meaningful reviewer disagreement should be resolved by an additional referee or another explicit promotion mechanism.

## 5. Parallelism

Independent work should run in parallel wherever practical.

Repositories are processed independently and in parallel through the repository stages.

Within a repository, independent candidate generation should also run in parallel when possible.

Cross-repository editorial processing begins after usable repository stories have been produced.

## 6. Evidence grounding

All factual content originates from repository evidence.

Agents may summarize, reorganize, explain, and make editorial judgments about supported material.

Agents may not invent technical facts, motivations, results, reactions, lessons, or future plans unsupported by the available evidence.

Later agents may consult underlying repository evidence rather than being restricted to summaries produced by earlier stages.

---

# Contract Evolution

## 7. Stages and steps

The pipeline is organized into **stages** and **steps**.

Stages describe relatively durable responsibilities.

Steps describe the current mechanism used to satisfy those responsibilities.

Stage boundaries should remain stable enough to support testing, logging, discussion, and historical comparison.

Individual steps may evolve.

A step may be revised, split, combined, reordered within a stage, or replaced when evidence shows that another method better satisfies the purpose of the stage.

## 8. Implementation flexibility

Unless explicitly identified as a contract requirement, the following are implementation choices:

- exact number of agents;
- models;
- prompts;
- rubric wording;
- reviewer topology;
- merge algorithms;
- retry policies;
- concurrency mechanisms;
- intermediate file formats;
- synthesis methods.

The replicated-generation and explicit-promotion principles are contract requirements.

The exact implementation used to satisfy those principles may evolve.

## 9. Failure as feedback

Repeated failure of a step is evidence that the step should be reconsidered.

The pipeline should not normalize chronic failure by indefinitely adding retries, exceptions, or fallbacks around an unreliable design.

If Step X.Y frequently fails, investigate the cause and consider changing its:

- evidence or inputs;
- decomposition;
- instructions;
- models;
- prompts;
- rubric;
- validation;
- reviewer arrangement;
- relationship to surrounding steps.

Fallbacks protect the pipeline from occasional failure. They are not substitutes for repairing chronically weak stages.

The governing rule is:

**preserve the guarantees and responsibilities; improve the mechanisms when evidence shows they can be better.**

---

# Stage 1: Identify the Day's Work

## Step 1.1: Resolve the report date

Resolve the requested `report_date`.

For `make_blog.py --yesterday`, the `report_date` is yesterday.

## Step 1.2: Identify active repositories

Identify repositories containing qualifying development activity for the `report_date`.

## Step 1.3: Establish the repository work set

Create the canonical set of repositories entering the pipeline.

Repositories remain independent through the repository-processing stages.

---

# Stage 2: Gather Repository Evidence

Stage 2 establishes what happened.

Later stages decide what is interesting and how to tell the story.

## Step 2.1: Gather evidence

For each repository, gather relevant evidence.

Evidence should generally be prioritized approximately as follows:

1. `docs/CHANGELOG.md`
2. commit messages
3. new or changed screenshots
4. changed files and diffs
5. relevant repository documentation
6. other repository material directly related to the day's work

Priority indicates expected evidentiary value, not an absolute restriction.

## Step 2.2: Build the repository evidence package

Create an evidence package containing enough context for downstream agents to understand the day's work.

Evidence should preserve useful technical detail rather than reducing changes to commit counts or truncated commit titles.

## Step 2.3: Validate the evidence package

Deterministically verify that the evidence package corresponds to the correct repository and `report_date`.

Repository access remains available to later stages for factual verification and recovery of context lost during reduction.

---

# Stage 3: Create and Promote Repository Outlines

Stage 3 transforms repository evidence into editorially useful outlines.

## Step 3.1: Generate independent repository outlines

Assign multiple independent outline agents to each repository.

Each receives equivalent evidence, guidance, and evaluation criteria.

Each independently identifies useful story material, including where supported:

- what was made, changed, fixed, or explored;
- interesting technical details;
- problems encountered and solutions found;
- meaningful design or implementation decisions;
- unexpected results or discoveries;
- things learned;
- what made the work interesting or enjoyable;
- possible next steps.

The goal is editorial reduction, not comprehensive changelog reproduction.

## Step 3.2: Generate independent merged outlines

Assign multiple independent merger agents to the candidate outlines.

Each independently produces a stronger combined outline using the best supported material from the candidates.

Merger agents may reorganize, combine, emphasize, or remove material.

They may not introduce unsupported facts.

## Step 3.3: Review the merged outlines

Assign reviewers to compare the merged outline candidates using an explicit repository-outline rubric.

The rubric should consider:

- factual grounding;
- specificity;
- interestingness;
- useful technical substance;
- completeness;
- narrative potential;
- usefulness to the next writing stage.

## Step 3.4: Promote the repository outline

Promote the strongest candidate as the official repository outline.

Resolve meaningful reviewer disagreement through an explicit referee or equivalent promotion mechanism.

---

# Stage 4: Create and Promote Repository Stories

Stage 4 turns each repository outline into readable maker-oriented prose before repositories are combined.

## Step 4.1: Generate independent repository stories

Assign multiple independent writers.

Each writer receives the promoted repository outline and access to underlying evidence.

Each independently writes a repository-level blog story.

The central editorial criterion is:

> After reading this, does it feel like Neil sat down after coding and wrote about what he made, what interested or surprised him, why he enjoyed working on it, what he learned, and what he wants to try next?

The story should sound like a maker describing the work, not an automated system describing GitHub activity.

## Step 4.2: Generate independent edited repository stories

Assign multiple independent editors.

Editors receive the repository-story candidates and independently produce improved candidates.

Editors may improve:

- organization;
- clarity;
- pacing;
- specificity;
- transitions;
- voice.

Editors preserve factual grounding.

## Step 4.3: Review the repository stories

Assign reviewers to compare the edited candidates using an explicit repository-story rubric.

## Step 4.4: Promote the repository story

Promote the strongest candidate as the official repository story.

Resolve meaningful reviewer disagreement through an explicit referee or equivalent mechanism.

At the completion of Stage 4, each usable repository has one promoted repository story.

---

# Stage 5: Rank and Organize the Day's Stories

Stage 5 transitions from independent repository processing to construction of the complete daily article.

## Step 5.1: Independently rank repository stories

Assign multiple independent reviewers to read all promoted repository stories.

Each ranks the stories according to their editorial value to the complete daily blog.

The rubric should consider:

- interestingness;
- significance of the work;
- strength of the story;
- useful technical or creative insight;
- discoveries or lessons;
- distinctiveness;
- contribution to the larger story of the day.

Commit count, repository size, and generated word count are not proxies for editorial importance.

## Step 5.2: Promote the editorial ranking

Compare the independent rankings and establish an official editorial ranking.

Resolve meaningful disagreements explicitly.

Ranking determines emphasis, not automatic inclusion or exclusion.

Every usable repository story remains available to downstream agents.

## Step 5.3: Generate independent daily outlines

Assign multiple independent daily-outline agents.

Each receives the promoted repository stories, editorial ranking, repository outlines, and supporting evidence as appropriate.

Each independently creates an outline for one cohesive daily article.

The outline determines:

- the day's strongest story;
- the opening focus;
- relationships among projects;
- which work deserves substantial treatment;
- which work deserves brief treatment;
- which routine material can be omitted;
- narrative order;
- the appropriate ending.

The ranked repository stories are source material for the larger post.

Repository boundaries do not dictate article structure.

## Step 5.4: Review the daily outlines

Assign reviewers to compare the daily-outline candidates using an explicit overall-outline rubric.

## Step 5.5: Promote the daily outline

Promote the strongest candidate as the official daily outline.

Resolve meaningful reviewer disagreement through an explicit referee or equivalent promotion mechanism.

---

# Stage 6: Create and Promote the Complete Blog

Stage 6 independently solves the complete writing problem multiple times.

## Step 6.1: Generate independent complete blog posts

Assign multiple independent writers.

Each receives the promoted daily outline and may consult:

- promoted repository stories;
- repository outlines;
- underlying repository evidence.

Each independently writes one complete daily blog post.

The final article should read as one story about the day's work.

Repository-level stories are ingredients. They do not need to survive as separate sections.

The maker-story criterion remains the primary editorial test:

> After reading this post, does it feel like Neil sat down after coding and wrote about what he made, what interested or surprised him, why he enjoyed working on it, what he learned, and what he wants to try next?

## Step 6.2: Generate independent edited complete posts

Assign multiple independent editors.

Editors receive the complete-blog candidates and independently produce polished complete-post candidates.

Editors may draw upon strong material from the available drafts while improving narrative structure, pacing, clarity, transitions, specificity, and voice.

Editors preserve factual grounding.

## Step 6.3: Independently review complete posts

Assign multiple independent reviewers.

Each compares the complete-post candidates using the final-blog rubric.

Candidate order should be varied when practical.

The rubric should evaluate:

- factual accuracy;
- maker voice;
- specificity;
- interestingness;
- narrative coherence;
- technical substance;
- editorial emphasis;
- absence of generic LLM filler;
- quality of the opening;
- quality of the ending;
- whether the article feels written rather than assembled.

## Step 6.4: Promote the strongest complete post

Promote the strongest complete-post candidate.

Resolve meaningful reviewer disagreement through an additional referee or equivalent promotion mechanism.

The promoted post becomes the strongest complete usable artifact produced so far.

---

# Stage 7: Final Synthesis and Quality Improvement

Stage 7 provides another opportunity to improve the complete article.

Stage 7 is an improvement stage. It must not turn a good existing article into a pipeline failure.

## Step 7.1: Generate independent final syntheses

Assign multiple independent synthesizers when synthesis is expected to improve the result.

Each may receive:

- the promoted complete post;
- other strong complete-post candidates;
- reviewer feedback;
- the final-blog rubric;
- supporting evidence.

Synthesizers may combine stronger elements, reorganize material, tighten prose, and improve narrative flow.

They may not introduce unsupported facts.

## Step 7.2: Review synthesis candidates

Compare the synthesis candidates against one another and against the previously promoted complete post.

The previously promoted post remains an active candidate.

A synthesis does not become preferred merely because it was generated later.

## Step 7.3: Promote the final prose artifact

Promote whichever candidate best satisfies the final-blog rubric.

If synthesis does not improve upon the previously promoted post, retain the existing post unchanged.

---

# Stage 8: Validate and Repair the Publication Artifact

Stage 8 concerns mechanical publication correctness rather than editorial rewriting.

## Step 8.1: Run deterministic validation

Validate machine-verifiable requirements, including:

- Markdown structure;
- required metadata;
- correct `report_date`;
- publication identity;
- links;
- filename;
- expected output location;
- other required publication structure.

## Step 8.2: Repair mechanical problems

Apply deterministic repairs where practical.

Repairs should make the minimum necessary changes and preserve the promoted prose.

## Step 8.3: Preserve the strongest usable artifact

Failure in a later quality-improvement step must not discard an earlier usable artifact.

The approximate fallback hierarchy is:

**promoted final synthesis**  
↓  
**promoted edited complete blog**  
↓  
**strongest complete writer draft**  
↓  
**deterministic assembly from promoted repository stories**  
↓  
**minimal complete post constructed from verified evidence**

The exact fallback mechanism may evolve.

The governing requirement is that the strongest complete evidence-grounded artifact produced so far remains available.

The pipeline should fail to create a blog artifact only when no evidence-grounded complete article can reasonably be constructed.

---

# Stage 9: Publish and Verify

## Step 9.1: Write the blog artifact

Write the final selected artifact using `report_date` as its publication identity.

If a generated post already exists for the same `report_date`, overwrite it.

Once successfully written, the generated artifact is preserved if a later publication step fails.

## Step 9.2: Import into MkDocs

Place or import the generated post into the expected MkDocs source location.

Once successfully imported, the source artifact is preserved if a later build or verification step fails.

## Step 9.3: Build the site

Build the MkDocs site.

A build failure does not roll back the successfully generated or imported blog artifact.

Record a precise diagnostic identifying the build failure.

## Step 9.4: Verify the published page

Verify that the expected page for `report_date` exists in the built site and contains the newly generated blog post.

A verification failure does not roll back successful earlier work.

Record a precise diagnostic identifying the verification failure.

## Step 9.5: Report command status

A zero exit status means the complete end-to-end contract succeeded:

**generated → imported → built → verified**

If blog generation succeeds but MkDocs build or page verification fails:

- preserve the generated blog artifact;
- preserve the imported source artifact;
- preserve useful diagnostic information;
- return a nonzero exit status identifying the failed stage and step.

A nonzero exit status therefore does not necessarily mean that no blog artifact was created.

It means that the complete end-to-end publication contract was not satisfied.

---

# Pipeline Observability and Improvement

## 10. Record stage outcomes

The pipeline should make the behavior of individual stages and steps observable.

Where practical, record information such as:

- step success or failure;
- execution time;
- candidate generation failures;
- reviewer decisions;
- reviewer disagreement;
- promoted candidate;
- fallback use;
- validation failures;
- publication failures.

Intermediate artifacts may be retained for debugging, evaluation, and pipeline improvement.

They are pipeline artifacts, not published blog versions.

## 11. Measure repeated weakness

Repeated problems should be identifiable at the stage and step level.

Useful questions include:

- Which steps fail frequently?
- Which steps frequently require fallback?
- Where do reviewers disagree most often?
- Which stages regularly produce candidates that are rejected?
- Does a synthesis stage usually improve the promoted input?
- Are particular evidence sources producing weak or misleading outlines?
- Are later stages repeatedly repairing problems that should be solved earlier?

These observations should guide refinement.

## 12. Improve the responsible step

When a recurring problem can be localized to Step X.Y, improve Step X.Y or its relationship to surrounding steps rather than treating the current mechanism as permanent.

For example, if Step 3.2 consistently produces weak merged outlines, Step 3.2 may be redesigned, replaced, or decomposed while Stage 3 continues to fulfill its responsibility:

**create and promote a strong repository outline.**

The numbered stages and steps provide stable names for discussing and measuring the pipeline. They are not intended to prevent architectural improvement.

---

# Governing Principles

## Quality through alternatives

LLMs are treated as generators of competing possibilities, not authoritative producers of canonical text.

Important subjective work should not depend on a single generation when meaningful independent alternatives can reasonably be produced.

## Selection over blind refinement

Reviewers compare alternatives using explicit rubrics.

Later does not automatically mean better.

A promoted earlier artifact remains preferable to a weaker later artifact.

## Evidence before prose

Repository evidence establishes what happened.

Outlines determine what is interesting.

Writers determine how to tell the story.

Editors improve the telling.

Reviewers determine which telling is strongest.

## Cohesion over repository structure

Repository-level processing exists to understand the work well.

The final product is about the day, not about preserving repository boundaries.

## Preservation over rollback

Successful earlier work survives later failure.

Fallbacks provide resilience without redefining failure as success.

## Failure should produce learning

Occasional failures are handled gracefully.

Repeated failures are investigated.

Fallbacks should not conceal chronically weak stages.

## Evolution over rigidity

Stages provide stable responsibilities.

Steps provide modifiable mechanisms.

Rubrics, models, prompts, agent arrangements, and algorithms should evolve as evidence accumulates about what produces better writing.

## Final governing pattern

The editorial architecture is:

**replicate → review → promote → replicate → review → promote**

The reliability rule is:

**preserve the strongest usable artifact produced so far.**

The improvement rule is:

**preserve the guarantees and responsibilities; improve the mechanisms when evidence shows they can be better.**

The publication rule is:

**exit 0 means the requested blog was generated, imported, built, and verified. Earlier successful artifacts remain preserved when a later publication step fails.**

# Give the daily blog a human maker's voice

## Context

Make the blog sound like a human maker who enjoys building software. The daily posts currently
read like a technical changelog; they should carry the joy of coding, the love of the creative
process, and the spirit of a maker. The Aug 22 and Aug 23 posts are the evidence that the system
was once closer to the intended voice, and the prompt-engineering literature is the source for
how to get it back and further.

Three findings reframe the problem:

1. **The v2 to v3 prompt switch was not an editorial rewrite.** Comparing
   `pipeline/prompts/daily_blog_author_v3.txt` against
   `docs/archive/prompt-contracts/v2/daily_blog_author_v2.txt`, every prose craft instruction
   is byte-identical. The only changes were plumbing: the coverage key renamed
   `active_repositories` to `repositories`, `publication_quality: final` dropped,
   `editorial_projection` added to front matter, and the referee's `NONE` verdict changed from
   "fall back to the mechanical post" to a hard publication block. No agent rewrote the prose.

2. **The bad Aug 24 and Aug 25 posts came from a system that no longer exists.** They are
   output from `pipeline/podlib/daily_github_blog.py`, deleted in commit `498423b`. Its author
   prompt (`build_author_prompt`) contained an output contract and an untrusted-data boundary
   and nothing else; it gave the model no voice guidance at all. Those post files have only
   been touched cosmetically since (image alt text). The single post the current system has
   produced is `2026-08-26.md`.

3. **The current validators would reject even the passable reference posts.** Neither
   `2026-08-22.md` nor `2026-08-23.md` carries a single `<!-- evidence: -->` comment, while
   `pipeline/daily_blog/candidates.py:228-231` requires one on every prose paragraph. Both
   posts would be rejected outright. Their narrative length (measured: 584 and 609 words) does
   sit inside the 350 to 650 band, but at 90 to 94 percent of the ceiling, so there is no
   headroom for the larger voice Neil is asking for.

## Reference terminology

This distinction governs the whole plan, so it is fixed here before anything else. The four
historical posts are **not** a good-and-bad pair.

- `2026-08-22.md` and `2026-08-23.md` are **positive-passable references**. They are the
  minimum examples that demonstrate the intended genre, worth roughly a 3 on the scale below.
  They are the floor, not the ceiling.
- `2026-08-24.md` and `2026-08-25.md` are **negative examples**, worth a 1 or a low 2.
- `2026-08-26.md` is the **current-system baseline**: what the live v3 contract actually
  produces, measured rather than judged in advance.
- What a 4 looks like is deliberately left open, to be established by a future post that earns
  it.

Calibrating the rubric to Aug 22 and 23 as "excellent" would freeze the target at merely
passable and teach the system that the least-bad historical posts are the ceiling. Every
threshold and every success criterion below is written against this scale.

So the target is not to undo a bad prompt edit. It is to write the voice guidance that has
never existed, and to remove the structural forces that flatten prose.

The five flatteners, in order of force:

- **Per-paragraph citation.** `candidates.py:228-231` requires an evidence comment on every
  prose block. A reflective sentence, an aside, a moment of delight, or a closing question has
  nowhere legal to live.
- **Mandatory dense `## Project coverage`.** Every post ends with one evidence-cited paragraph
  per active repository. That section is a changelog, stapled to every post by contract.
- **A shape that no real blog uses.** 350 to 650 words across two to four H2 sections sits below
  both shapes working bloggers write, and the two-heading minimum makes the commonest one, the
  short unsectioned story, illegal outright. The passable references already spend 584 and 609 of those
  words on merely being thoughtful.
- **The prompt is itself a changelog.** Sixty thousand characters of JSON evidence cards,
  truncated commit subjects, and authority ranks are the last thing the model reads before it
  writes. Genre is contagious; this one is being set by the input, not the instructions.
- **A rubric with no word for joy.** All nine bullets of `daily_blog_rubric_v3.md` score
  fidelity, coverage, and shape. The persona itself is "Daily work-log author".

## Constraints discovered

- `podlib/prompt_loader.py:9-29 validate_positive_instructions` rejects any prompt template
  containing `not`, `never`, `avoid`, `without`, `do not`, `cannot`, a sentence-initial
  "no x", or deferred-ownership phrasing. Every new instruction must be an affirmative
  imperative. This also means verbatim exemplar posts cannot be pasted into a template file:
  both passable references contain "not". Validation runs on the template at
  `editorial.py:245`, before `str.format`, so exemplars must arrive through a render slot.
- Exactly two author routes produce candidates A and B; one referee picks the winner
  (`config.py:156-181`). The referee's rubric therefore decides what "better" means, and it
  currently means better-covered.
- Tests already drive the whole editorial path offline with a stub whose protocol is
  `run(route, prompt, repository) -> str` (`tests/test_daily_blog_editorial.py:156`). The full
  pipeline is testable with no network and no model.
- **The validators exist twice, in two repositories.**
  `~/nsh/vosslab-daily-blog/scripts/validate_daily_post.py` is an independent reimplementation
  that the bundle importer runs at publish time. It carries its own `prose_blocks`
  (lines 59-71) and its own per-paragraph citation rule (lines 152-155). Relaxing the citation
  rule in the producer alone would make every post fail at import. It does *not* duplicate the
  word band, the H2 count, or the Project coverage rule, so those three are producer-only
  edits.
- `daily_blog/evaluation.py` already implements a non-publishing shadow harness that
  regenerates a historical date and compares it to a preserved reference post, plus
  `article_profile` (`evaluation.py:59`), which measures narrative shape deterministically.
  This is the experiment rig; it needs voice metrics added, not a replacement.

## Autonomy

Automation owns deterministic validation, sealed private artifacts, and the route-free
attestation. External data egress remains an explicit operator boundary. Two approvals remain
required: approval to send the fixed public historical-post payload to the referee route for live
calibration, and separate approval to use the configured author/referee route with the Aug. 23
and Aug. 26 project-context payloads for fresh capture. Neither approval activates v4, publishes
content, imports a bundle, or changes the schedule.

The permanent offline tests protect deterministic contracts: prompt-resource identity, rendering,
candidate-validation boundaries, artifact integrity, and route-free attestation. They keep prose
reviewable and attributable, but they do not freeze a maker voice into assertions. Voice quality is
reviewed from generated posts and scorecards captured over sealed evidence. The later attestation
joins that capture to passing live calibration evidence. Only that deterministic join can become
activation-ready; a separately reviewed activation change remains responsible for advancing the
active producer/publisher contract.

## What the prompt-engineering literature says about this exact failure

Surveyed `~/BOOKS_to_CONVERT/SORTED_SUBJECTS_MD/prompt_engineering/`. Two titles carry the
citable guidance: Berryman and Ziegler, *Prompt Engineering for LLMs* (2023), and Phoenix and
Taylor, *Prompt Engineering for Generative AI* (2024). The second book's chapter 10 builds
almost exactly this system, an evidence-fed blog generator that has to sound like its author.

Five findings drive the design:

1. **The Little Red Riding Hood principle** (Berryman and Ziegler, ch. 4): "the prompt must
   closely resemble documents from the training set... don't stray far from the path upon which
   the model was trained." A prompt and its completion form one document. Our prompt *is* a
   changelog: 60,000 characters of JSON evidence cards, truncated commit subjects, authority
   ranks. We hand the model a changelog and ask it to continue. The genre of the output is
   being set by the shape of the input, not by the instructions.

2. **The Valley of Meh** (ch. 6): "The closer a piece of information is to the end of the
   prompt, the more impact it has" and "the model can easily recall the beginning and end of
   the prompt, it struggles with the information stuffed in the middle." Our author prompt puts
   every craft instruction in lines 1 to 28 and the 60,000-character JSON payload last. Every
   word about voice is as far from the point of generation as it can be. The book's remedy is
   the *sandwich*: "start and end the prompt by clearly stating what they want the model to
   do," with a short *refocus* at the end.

3. **Instruction-only style direction does not work, and more instructions make it worse.**
   Phoenix and Taylor audit a heavily specified blog prompt (tone, transition words, active
   voice, word counts, section counts) and conclude: "the content is still likely to sound like
   AI, and not like the user," and separately, "It's likely some of these instructions make no
   difference to quality (unnecessarily costing tokens) or might even degrade quality." They
   name this **blind prompting**: adding instructions without testing them. They also note
   models are "often unable to follow instructions dictating a number of sections or words."

4. **Voice is an "I know it when I see it" property, so show it.** Berryman and Ziegler,
   ch. 5: writing the rules explicitly means "you'd also have to be careful not to accidentally
   omit a rule. And this presumes you are even able to state your rules in the first place." The
   hard numbers: Phoenix and Taylor, ch. 1, "go past three to five examples and your results
   will become more reliable, while sacrificing creativity." Selection matters more than count:
   anchor on *representative* days, not best-of, or quiet days get inflated; and shuffle,
   because "your prompt examples are not randomly ordered unless you consciously shuffle them,"
   and a chronological run invites the model to extrapolate the arc between them.

5. **An LLM referee is a convergence pump toward the median.** Berryman and Ziegler, ch. 10,
   describe a judge that systematically ends up "accepting generally OK answers... while
   rejecting almost perfect answers," and warn that a model asked to grade its own work is
   "subject to a host of conflicting biases," with RLHF models "falling over themselves to
   correct" on any hint of doubt. Their remedy is **SOMA**: specific questions, ordinal scales
   with described levels, multi-aspect coverage, and the framework stated *before* the model
   reads the candidate. Our referee currently gets a nine-bullet rubric with no scale anchors
   and one open question, which is the shape they predict will punish an ambitious post.

The one method in the survey that evaluates voice without a judge is embedding distance to a
reference post (Phoenix and Taylor, ch. 10), which they used to pick between an instruction-only
control and three exemplar strategies. That A/B design is reused directly in milestone 5.

## What real maker blogs actually do

Neither directory Neil supplied turned out to contain the target genre: detailed.com's 50
entries are all trade publications, and Feedspot ranks by domain authority and surfaces the
same. Evidence came instead from eight measured posts by solo authors writing about software
they themselves built: Julia Evans (two), Simon Willison (two), antirez, Jim Nielsen (two), and
a Little Polygon devlog, with a Massimo Gauthier engine retrospective as context.

The findings that bear directly on our contract:

**Posts come in two shapes, and we currently permit neither.**

- *The story*: 700 to 1,300 words, **zero subheadings**, 14 to 25 paragraphs of about 50 words,
  straight-through narrative. Used for one build, one fix, one decision.
- *The findings list*: 1,200 to 2,500 words, a heading every 150 to 200 words, three to four
  paragraphs per section. Used for "N things I learned".

Our contract demands 350 to 650 words across two to four H2 sections. That is below both shapes
and, by requiring at least two H2 headings, it makes the story shape structurally illegal.

**Paragraphs are short and sentence length swings hard.** Roughly 50 words and two to three
sentences per paragraph across the corpus. The recurring rhythm is a long multi-clause sentence
followed by a very short one, and the emotional beats live in standalone one-line paragraphs:
"That seemed wrong to me: computers are fast!", "I have no idea if it works."

**Every post admits something unresolved, at roughly one admission per 250 words.** Evans's
SQLite post carries at least five, including "I don't think I've actually tested restoring from
my backups." Simon grades his own artifact down: "As a finished game project, it's mediocre. As
a starting point from a single prompt I think it's very impressive."

**Provenance is woven into prose; no post has a references section.** Evans runs 37 inline
links in 1,232 words, about one per 33 words, attached to ordinary nouns mid-sentence, so
citing and explaining are the same act. Our posts do the opposite: links are sparse and
provenance is quarantined into trailing HTML comments and a coverage section.

**Endings never summarize.** Four observed shapes: a future admission, a split verdict, a named
open question, or a small stated joy. Our current rubric asks for "the current state of
attention", which produces the first three and forbids the fourth.

**The single move a changelog structurally cannot make** is picking a favorite. Simon: "Then my
favorite change: it added the dog." A changelog treats every diff as equal; a blog post loves
one of them more than the rest.

The survey produced twelve positive-imperative writing instructions, which become the body of
the v4 voice brief in milestone 1.

This eight-post read was broad enough to establish shape, rhythm, and provenance habits, but too
small and too loosely filtered to derive rubric descriptors from. Milestone 0 widens it.

## Plan

Everything ships as a v4 editorial contract alongside the untouched v3 files, so the two can be
compared before v4 becomes active. `editorial.py:342` already folds
`prompt_contract_identity()` into the author phase's cache key, so changing prompt bytes
invalidates cached candidates automatically; no manual cache bust is needed.

### Foundational milestone 0: make the repository universe authoritative

The Aug. 26 post could not tell the story of `vosslab/cancer-clicker`, much less make it the
headline. GitHub records the repository as created during the Aug. 26 Central report day, with
the game work committed that evening, but the producer's mirror phase only considered configured
clone URLs and cache directories that already existed. `daily_blog.repository_urls` was empty and
the repository had no cache, so every later phase received a complete-looking but incomplete
universe. The prompt never saw the game. This is an acquisition and ownership failure rather
than a prose failure.

Before judging v4, replace that cache-as-roster design with these contracts:

- The GitHub owner-repository listing is the authoritative publication roster. The eligible
  publication scope is every public repository owned by the configured account that is neither
  archived nor disabled. The API response is positively validated at the network boundary;
  incomplete or malformed roster data fails the run before Git, model, bundle, or publisher work.
- One immutable typed roster snapshot records canonical owner/repository identity, HTTPS GitHub
  page and clone URLs, creation time, fork state, and a content-derived roster identity. The run
  persists that snapshot as its first artifact. Tokens and raw remote payloads stay outside
  artifacts and lifecycle logs.
- Durable cache identity is `<mirror_cache_root>/<owner>/<repository>`. Cache paths are derived
  only from validated identifiers, and a mirror's origin must equal its roster record. Caches
  store evidence; they no longer decide which repositories exist. This removes the current
  cross-owner name collision and keeps deleted or ineligible stale caches outside the run.
- Repository creation becomes typed lifecycle evidence. Activity and projection carry the exact
  UTC creation timestamp, whether it falls in the selected local report day, and whether the
  repository is a fork. The evidence packet and projection schema versions change with that
  contract rather than silently reinterpreting old artifacts.
- Projection policy becomes story-first. A source repository created during the report day is a
  first-class headline candidate and appears before routine repository cards, while its technical
  excerpts remain exact and authority-ranked. This is a salience signal, not a forced verdict:
  the author and referee can still prefer another story when its evidence is stronger.

Verification is an offline Aug. 26 regression named for the missed repository. A validated fake
GitHub roster contains a newly created `vosslab/cancer-clicker` with same-day attributed commits
and an unrelated existing cache. The test proves roster discovery creates the owner-qualified
mirror, activity types the creation event, projection puts the new source repository first and
marks it headline-eligible, and the rendered author/referee context contains those facts. Boundary
tests reject owner mismatch, non-HTTPS clone URLs, traversal-shaped identifiers, malformed
timestamps, private/archived/disabled entries, origin mismatch, duplicate identities, and the
old bare-name cache layout. The focused tests run before the prompt-quality experiment, because a
voice experiment over an incomplete repository universe cannot establish a winner.

Sixteen numbered milestones follow foundational milestone 0, each scoped to one owner, one outcome,
and one verification. They
are small on purpose: an oversized milestone hides unresolved design decisions inside itself,
and several of the decisions here (the shape rule, the exemplar count, the citation trade) are
exactly the kind that disappear when bundled into a larger unit of work.

### Milestone 1: assemble the maker corpus

Files: new `docs/active_plans/reports/maker_blog_corpus.md`.

The rubric must be derived from what maker posts actually do, rather than from generic
good-blogging advice. Feedspot and detailed.com are useful for rubric *methodology* and useless
as a style corpus: both rank broad technology publications by authority, relevance, and
freshness, so their top entries are WIRED, The Verge, TechCrunch, Gizmodo, ZDNet, 9to5Mac,
Engadget, CNET, and VentureBeat. That is news and reviews, a different genre entirely.

Assemble 20 to 30 first-person posts by solo developers about software they themselves built,
changed, debugged, tested, redesigned, or learned from. Mitchell Hashimoto's Ghostty devlogs are
the closest match available: they cover features, bugs, discoveries, uncertainty, and his own
ignorance, and he describes the intended register as casual and conversational. Julia Evans is
the second anchor, including her short TIL posts, which run the compact pattern "I hit X, found
Y, changed Z, and here is why I like the result". Simon Willison, antirez, and a few comparable
solo developers fill it out. Include a spread of post sizes, since a daily blog will have quiet
days and the corpus needs to show what a good short post looks like.

Excluded: news reporting, industry commentary, product marketing, pure release notes, and
tutorials written independently of the author's current work.

This milestone produces the post list and the per-post record only: URL, subject, word count,
section count, and a representative sample of openings and closings. Analysis is milestones 2
and 3.

Verification: the report exists, holds 20 to 30 posts, every post passes the inclusion filter,
and the size spread includes several posts under 800 words.

### Milestone 2: extract selectivity and maker presence from the corpus

Files: `docs/active_plans/reports/maker_blog_corpus.md` (analysis sections).

Two properties get read out of the corpus first, because they are the ones our system fails
hardest and the ones the evidence packet actively fights.

**Selectivity.** The exact sentence-level moves that elevate one piece of work above the rest of
the day, and that demote minor work to a clause. A changelog reports six changes as six changes;
a maker post says five things happened, this one was the interesting part, here is why. Collect
as many verbatim examples of both moves as the corpus yields.

**Maker presence.** How the author's reasoning, enjoyment, and uncertainty show up at sentence
level.

Report what strong posts repeatedly do and what weaker posts do instead, without grading either
against a scale. The scale comes later, in milestone 11, and deriving it from pre-graded
examples would be circular.

Verification: both properties have quoted examples on both sides, or an explicit finding that
the corpus shows no clean split, which is a useful result rather than a failure.

### Milestone 3: settle post shape, quiet days, and endings from the corpus

Files: `docs/active_plans/reports/maker_blog_corpus.md` (analysis sections).

This milestone exists to decide one thing the plan currently only hypothesizes. An eight-post
sample suggested two shapes, a 700-to-1,300-word story with no subheadings and a
1,200-to-2,500-word findings list with frequent headings. Twenty to thirty posts either confirm
that or replace it. The report gives the observed distribution of lengths and section counts and
states plainly whether the hypothesis survives.

The quiet-day question is the one that matters most for a *daily* blog: whether excellent short
posts exist, and what a strong 300-to-800-word post does. Julia Evans's TIL posts and short
Hashimoto devlog entries are the places to look.

Also covered: how posts close, and how code, commands, links, and measurements are used.

The report additionally tallies every post against the five parts of the holistic question: what
was made, what interested or surprised the author, why they enjoyed it, what they learned, and
what they want to try next. The last two matter most, because "why I enjoyed working on it" and
"what I want to try next" are the two the current system never produces at all.

Verification: the report states a shape decision with the distribution behind it, answers the
quiet-day question with named examples, and gives at least two verbatim sentences for each of
the five holistic parts.

### Milestone 4: restructure the author prompt as a document, not a spec sheet

Files: new `pipeline/prompts/daily_blog_author_v4.txt`.

The current file orders itself: craft instructions (lines 1-28), output contract (30-46),
rubric (48-50), then 60,000 characters of JSON (52-56). That puts every word about voice in the
Valley of Meh and ends the document on a machine-readable evidence dump, which is the genre the
model then continues.

The v4 architecture is deliberately small:

1. Identity and purpose, in a sentence or two.
2. The evidence, introduced by a line that frames it as working notes rather than a data
   payload. Berryman and Ziegler, ch. 6: "if there are some pieces of context where the model
   needs to focus on a certain aspect, it helps if you set up that aspect in the beginning."
3. Two or three human examples (milestone 2).
4. A short positive voice brief.
5. The output requirements.
6. A short closing reminder of the desired voice, immediately before generation.

The mechanical contract (front matter shape, H1, excerpt marker, evidence-comment syntax,
`publish_path` rule) carries over byte-for-byte from v3. Only ordering and the brief change.

**The brief is short on purpose.** An earlier draft of this plan carried twelve specific
instructions distilled from the blog survey: three admissions, a colon-hinge reaction, sentence
length choreography, link density, a favorite beat, paired verdict sentences. That was
self-contradicting. The plan's own argument is that instruction-heavy style prompts produce
generic prose, and those twelve rules are an attempt to reverse-engineer the surface statistics
of human writing. Phoenix and Taylor are direct about the alternative: examples communicate
qualities that are difficult to describe explicitly, and without them a model tends toward
something like the average of its training data. So the survey's twelve observations stay
diagnostics in milestone 5 and evidence in milestone 0; they do not become rules.

The brief itself is roughly this, refined once milestones 2 and 3 land:

> Write as the person who made this software. Tell the interesting story inside today's work.
> Show what drew your attention, what surprised you, what you enjoyed, what you learned, and
> what remains unresolved. Give important details room to breathe and treat routine work
> briefly. Let technical details support the story. Write with the curiosity, satisfaction,
> uncertainty, and personality of someone describing work they actually care about.

That is six sentences carrying role, task, tone, and desired outcome in concrete positive terms,
which is what the DeepSeek book and Tavakoli both recommend, and it leaves the examples to carry
everything about style that prose cannot state.

**On positive phrasing.** `podlib/prompt_loader.py:33` mechanically rejects `not`, `never`,
`avoid`, `without`, `cannot`, and sentence-initial "no x", so every line must be affirmative
regardless. The defensible principle behind that rule, and the one this plan claims, is:
describe the desired behavior directly and concretely, demonstrate it with examples, and reserve
prohibitions for real boundaries. The books are genuinely not uniform on whether negative
prompting underperforms, and several teach it as a legitimate technique, so this plan stops
short of claiming they prove it. Omission is the companion move: leaving an unwanted action
unnamed works better than naming it in order to forbid it, since naming an action puts it in
front of the model at all.

Verification: focused permanent tests confirm that the template loads, passes
`validate_positive_instructions`, and places its closing reminder after the `{evidence_json}` slot.
They verify prompt structure, not a fixed literary result.

### Milestone 5: add the exemplar slot to the prompt machinery

Files: `editorial.py` gains an `{examples}` render slot and a plain-read loader;
`bundles.py:20-25` gains the new path; `prompt_contract_identity()` includes it so exemplar
edits invalidate the author cache.

This is plumbing only, and it is separated from choosing the exemplars because the two fail for
different reasons and are verified differently.

The exemplars cannot live inside the template. Both passable references contain the word "not",
and `load_prompt` validates the template *before* `str.format` runs (`editorial.py:245`), so a
template containing them fails to load. They arrive through a slot instead, and the examples file
is read plainly rather than through `load_prompt`.

Verification: permanent offline tests use compact inline inputs to confirm that rendering remains
within the author limit and that an example-resource edit changes `prompt_contract_identity()`.
They do not treat a fixture post as a proxy for generated prose quality.

### Milestone 6: choose and prepare the exemplars

Files: new `pipeline/prompts/daily_blog_voice_examples_v4.md`.

Contents: a project-owned full August 23 example plus two frozen, attributed external excerpts:
Julia Evans's quiet-day TIL and Mitchell Hashimoto's selectivity sentence. Each external quotation
is below 25 lexical words, names its author and canonical URL, records retrieval and rights, and is
ASCII-normalized with the source typography noted. The resource labels them as illustrative writing
evidence, not task instructions. The former synthetic quiet-day and August 22 three-shot selection
is removed; August 22 remains corpus evidence, not a current prompt example.

**Exemplars come from the maker corpus, not only from our own archive.** Using `2026-08-22.md`
and `2026-08-23.md` as the sole exemplars would teach the model that passable is the target,
which is exactly the ceiling this plan exists to lift. The set pairs one of our own posts, so the
model sees the house constraints satisfied, with two corpus posts that are stronger on the
properties milestone 2 identified. Where a corpus post cannot be reproduced at length, an excerpt
of the passage carrying the property is used instead.

Selection follows the anchoring warning rather than instinct: the set deliberately includes one
quiet-activity day, because exemplars drawn only from big days teach the model to inflate small
ones. Order is fixed but non-chronological, since "your prompt examples are not randomly ordered
unless you consciously shuffle them." The *count* is left open here and decided by the experiment
in milestone 15.

Verification: the resource is pure ASCII and remains separate from evidence comments and coverage
headings. Its wording stays subject to human review and fresh capture; pytest records the resource
contract rather than freezing its prose.

### Milestone 7: redesign the citation rule in the producer

Files: `pipeline/daily_blog/candidates.py`.

- **Per-paragraph citation.** Today `candidates.py:228-231` requires an evidence comment on
  every prose block, so a reflective sentence has nowhere legal to live. An earlier draft
  proposed exempting blocks lacking a repository name, link, backtick, or digit. That heuristic
  is unsound: "the parser finally handles malformed input correctly" is a concrete, checkable
  factual claim carrying none of those markers, and a lexical proxy cannot tell a claim from a
  reflection. The design instead works from the actual invariant, which is that a reader can
  trace the post's factual assertions back to evidence, and that a post cannot smuggle in large
  uncited stretches. Two structural rules deliver that without pretending to classify sentences:
  every narrative section carries at least one evidence comment, and a post may carry at most a
  small fixed number of uncited prose blocks overall. Reflection gets room; nothing substantial
  goes unattributed. This is a real weakening of the paragraph-level guarantee, stated plainly
  rather than papered over.

Verification: focused permanent tests cover the deterministic boundary: one reflective uncited
paragraph is permitted, a section with no citation fails, and the uncited-block cap is enforced.

### Milestone 8: mirror the citation rule into the publisher

Files: `~/nsh/vosslab-daily-blog/scripts/validate_daily_post.py`.

The publisher repository carries an independent reimplementation of the same rules, with its own
`prose_blocks` (lines 59-71) and its own per-paragraph citation check (lines 152-155). Relaxing
the producer alone makes every post fail at bundle import. This milestone is separate from
milestone 7 only so the second repository is never forgotten; the two land together.

Verification: the publisher repository's own test suite, plus importing a bundle whose post
carries a reflective uncited paragraph.

### Milestone 9: relax Project coverage and move provenance into the prose

Files: `pipeline/daily_blog/candidates.py`, and the publisher copy.

- **Project coverage.** Keep the guarantee that every active repository is named and the post
  stays honest about the day's full scope, and drop the requirement that this be a dense
  evidence-cited paragraph per repository. The passable references satisfy the intent with a
  compact footer.
- **Provenance moves into the prose.** In the measured corpus, no post has a references section,
  and Evans runs about one inline link per 33 words attached to ordinary nouns, so citing and
  explaining are one act. The passable references do this too, linking each repository inline on
  first mention; `2026-08-26.md` links no repository at all in its narrative. The HTML evidence
  comment stays as the machine-checkable provenance channel, and v4 additionally asks for an
  inline Markdown link to a repository on first mention in the narrative. The projection already
  carries `repository_url` on every card (`schema.py:494-509`), so this needs an instruction and
  a check rather than new evidence.

Verification: cases proving a compact coverage footer passes, that a post omitting an active
repository still fails, and that a narrative mentioning a repository without linking it fails.

### Milestone 10: replace the word band and section count with the corpus shape rule

Files: `pipeline/daily_blog/candidates.py`.

Depends on milestone 3. Today's 350 to 650 words across two to four H2 sections is narrower than
anything observed, and `MIN_NARRATIVE_H2_SECTIONS = 2` forbids the unsectioned short story
outright. The replacement rule is whatever milestone 3's distribution supports, including the
possibility that the two-shape hypothesis is wrong and a single wider band with a floor is
better. The literature is explicit that models follow word and section counts poorly, so whatever
lands stays a guardrail against runaway or stub output rather than a target.

Verification: focused permanent tests cover registered selection, provenance, ASCII, excerpt
limits, and the distinction between voice resources and candidate inputs. Raw August 22 and August
23 posts remain corpus evidence rather than valid candidates because they are not bound to current
evidence or projection identities. Generated prose is assessed in the approval-gated capture, not
made to satisfy adapted test inputs.

### Milestone 11: write the v4 rubric

Files: new `pipeline/prompts/daily_blog_rubric_v4.md`.

The current rubric spends eight of nine bullets on fidelity, coverage, and shape, names its
criteria without describing any level, and hands the referee one open question. That is the
configuration Berryman and Ziegler predict will accept a competent generic post and reject an
ambitious one.

A survey of real blog scoring rubrics (an academic social-work rubric recovered from PDF, a
twelve-point content-marketing rubric, a classroom rubric, and TeamBench's design guidance)
supplies the shape:

- **Four to six criteria.** TeamBench recommends roughly four to six and warns against
  overlapping dimensions; the twelve-point rubric concedes that sixteen causes reviewer
  fatigue. Six is the working number.
- **A descriptor in every cell, and each descriptor pairs a countable clause with a judged
  one.** The academic rubric's strongest content level combines preparation and reflection,
  substantial information, focus, reader engagement, research or introspection, and clear
  concise writing - observable descriptions rather than adjectives. That pairing is what makes
  a criterion survive the **two-reviewers test**: "if two different reviewers independently
  score the same piece, would they give similar scores?" The classroom grading machinery around
  it is discarded.
- **Calibrate against real examples rather than inventing thresholds.** TeamBench recommends
  exactly this, and it is why the reference terminology above is fixed before the rubric is
  written.
- **Deterministic and mechanical properties stay outside the rubric entirely.** Factual
  accuracy, repository coverage, citation validity, front matter, well-formed Markdown, and
  maximum length remain hard validators in `candidates.py`. A technically false post must never
  win on the strength of its voice, and a scored link count teaches the author to stuff links.

**The whole rubric in one question.** This is the one piece both the author brief and the
referee rubric carry, because it states the target as a felt experience rather than a scoring
dimension. The referee reads it before the six criteria it decomposes into:

> After reading this post, does it feel like Neil sat down after coding and wrote about what he
> made, what interested or surprised him, why he enjoyed working on it, what he learned, and
> what he wants to try next?

Its five parts are the shape of the post itself, and each maps onto a criterion below, so the
decomposition stays honest: what he made is maker substance, what interested or surprised him is
author presence, why he enjoyed it and which part mattered most is insight and selectivity, what
he learned is technical grounding, and what he wants to try next is unfinished edges. A post
that scores well on all six while failing this question means the criteria have drifted and get
rewritten.

**The six criteria and their weights.** Generic dimensions like "substance", "voice", and
"originality" would describe an essay, a research blog, or a newsletter equally well. These are
specific to writing about making software:

| Criterion | Weight | What excellent writing does |
| --- | --- | --- |
| Maker substance | 25% | Centers on something actually built, changed, debugged, tested, redesigned, or learned while making software. Explains enough of the technical problem and solution that the reader learns something. |
| Author presence and curiosity | 20% | Makes the author's reasoning visible. Shows what seemed interesting, surprising, frustrating, satisfying, uncertain, or worth pursuing. Sounds like the person who did the work rather than a reporter summarizing commits. |
| Insight and selectivity | 20% | Finds the interesting story inside the day's work. Gives some developments more importance than others, explains why they matter, and develops at least one observation beyond "this changed". |
| Concrete technical grounding | 15% | Uses real details, examples, links, commands, screenshots, code, measurements, or implementation specifics where they improve understanding. Claims remain faithful to the evidence. |
| Narrative and readability | 10% | Has a natural progression from problem or motivation through exploration to current state. Paragraphs and sections serve the story instead of mechanically partitioning it. Reads cleanly and economically. |
| Intellectual honesty and unfinished edges | 10% | Distinguishes what worked from what remains uncertain, incomplete, provisional, ugly, or unexplored. Ends where the actual thinking currently stands rather than manufacturing a conclusion. |

Two naming choices carry weight. **Maker substance** rather than substance, because the subject
matter is the point. **Author presence and curiosity** rather than voice, because an LLM referee
reads "voice" as surface style; what actually matters is whether a recognizable person is
visibly thinking while making something. And **insight and selectivity** rather than
originality, because originality is close to unjudgeable while selectivity is observable: a
changelog reports six changes as six changes, while a good maker post says five things happened,
this one was the interesting part, and here is why.

**Four anchored levels, not a hundred.** A 0-to-100 scale invites imaginary precision from an
LLM judge. The academic rubric's coarse High / Adequate / Low structure is the right instinct,
extended to four so the passable band is separable from the strong one:

- **4, strong**: clearly demonstrates the property and could serve as a future positive exemplar.
- **3, passable**: genuinely demonstrates the property with obvious room to become more
  interesting or effective.
- **2, weak**: some evidence of the property, with generic changelog behavior dominant.
- **1, failure**: essentially absent.

Every level descriptor is written affirmatively, describing what a post at that level *contains*
rather than what it lacks, both because `validate_positive_instructions` forbids the negations
and because a positive description is easier for two readers to agree on.

Two warnings shape the wording. First, the aspirational-versus-evaluable line: "'Content should
be engaging' is aspirational. 'Content should have an average sentence length under 20 words,
use questions to involve the reader, and open with a direct answer' is evaluable." Second, and
counterintuitively, a vague rubric does not produce a neutral judge; it produces a verbose one:
"If an LLM judge gives higher scores for being more 'comprehensive,' you will systematically
train models to be verbose." The usual mitigation is phrased as a penalty, which
`validate_positive_instructions` forbids, so v4 states it as a preference instead: the stronger
post reaches its point in fewer words.

Also avoid **criteria bleed**, the drafting bug visible in the source rubric where the
`Mechanics` descriptor judges reader interest. Overlapping descriptors make the referee
double-count and the criteria stop being independent.

Verification: the rubric file loads and passes `validate_positive_instructions`, holds six
criteria with four descriptors each, and every descriptor pairs an observable clause with a
judged one.

### Milestone 12: calibrate the rubric against the five historical posts

Files: `pipeline/prompts/daily_blog_rubric_v4.md` (revisions), new calibration and repair
templates, `pipeline/daily_blog/rubric_calibration.py`,
`automation/calibrate_daily_blog_rubric.py`, focused tests, and
`docs/active_plans/reports/rubric_calibration.md`. Shared prompt-resource and private-artifact
primitives remain neutral infrastructure; calibration owns its resource allowlist, score schema,
fixed historical inputs, approval boundary, and non-publishing report.

A rubric that has never been applied is a guess. Before it goes anywhere near production, it is
run over the five historical posts through the referee route and the scores checked against the
targets the reference terminology fixes:

- `2026-08-22.md` and `2026-08-23.md` score near 3. A rubric that scores them 4 is miscalibrated
  and gets rewritten, because that would freeze the target at passable.
- `2026-08-24.md` and `2026-08-25.md` score 1 to low 2.
- `2026-08-26.md` is measured to locate where v3 actually lands.
- The 4 band stays unclaimed until a post earns it.

Scoring the same post repeatedly also gives the two-reviewers test: a criterion whose score moves
between identical runs is underspecified and gets sharper descriptors.

Note this milestone sends historical published posts to a model route, which is what
`shadow_evaluation.external_model_data_sharing` gates. The posts here are already public on the
blog, so this is a narrower case than the flag's original concern, and the milestone records
which route saw what rather than quietly flipping the flag.

Verification: route-free preparation proves fixed input/resource identities and private artifact
behavior. The approved live command then records every configured repetition, and the calibration
report shows the targets met and per-criterion score stability across repeated runs.

Current status: the fail-closed calibration harness, fixed five-post loader, structured 1-through-4
score parser, private artifact contract, and route-free preparation report are complete. Preparation
identity `63fcad727dcca58c10410986abe4d6da4803e9bf557c1d8cee43fabc7dd76bb1` binds the versioned
calibration contract, historical post hashes, rubric, prompts, and target bands. The current
data-sharing configuration remains
`false`, so repeated live referee scorecards and proof that the targets are met remain pending.

### Milestone 13: rewrite the referee prompt

Files: new `pipeline/prompts/daily_blog_referee_v4.txt`.

The referee prompt gains:

- **Third-party framing.** The referee reads two posts by another writer. It has no reason today
  to think otherwise, and v4 keeps it that way deliberately, because a model that believes it
  is grading itself is "subject to a host of conflicting biases."
- **A preference stated in terms of the behavior we want**, countering the documented bias
  toward the median. "Prefer the riskier post" was the earlier wording and it is too loose: it
  would reward eccentricity as readily as quality. The instruction instead names the properties
  directly, preferring the post with stronger selectivity, more specific personal reasoning, and
  a more distinctive account of the actual work.
- **The framework before the candidates**, which the v3 referee already does correctly and v4
  preserves.

Verification: the referee template loads, keeps both candidate slots and its output contract, and
`parse_referee_verdict` still accepts and rejects the same shapes.

### Milestone 14: stop the author and referee sharing a document

Files: `pipeline/daily_blog/editorial.py`.

Today `render_author_prompt` (`editorial.py:293-298`) injects the same `{rubric}` into both
prompts. Handing the writer the exact six weighted dimensions and level descriptors the judge
scores against invites criterion optimization: a post written to hit six named dimensions is a
post written for a rubric, which is the failure this whole plan exists to escape.

So v4 splits them. The author receives the holistic question, the short brief from milestone 4,
and the examples. The referee receives the full weighted rubric with level descriptors. Both
express the same values; only the referee gets the scoring machinery. Concretely, the `{rubric}`
slot leaves the author template and stays in the referee template.

Verification: focused permanent tests confirm the author prompt carries the holistic question and
the referee prompt carries the weighted criteria. They check prompt separation, not voice quality.

Note the corollary from the survey: "Any criterion phrased as a target count of a structural
unit will be hit exactly and never exceeded." That is the direct argument against putting the
word band or section count in the rubric, and for keeping them as shape gates in milestone 3.

Verification: focused permanent tests confirm that the referee template loads, keeps both
candidate slots and its output contract, and that `parse_referee_verdict` accepts and rejects the
defined result shapes. Repeated-route score stability is evidence from approved live calibration,
not a claim made by a stub or a fixed pytest pair.

### Milestone 15: measure whether v4 actually writes better

Files: `pipeline/daily_blog/evaluation.py` (extend `article_profile`), focused offline contract
tests, `automation/experiment_daily_blog_prompts.py`, and
`automation/attest_daily_blog_prompt_experiment.py`.

The literature's warning about blind prompting applies to everything above: untested
instructions may cost tokens and degrade quality. So the numbers in milestone 3 and the choice
in milestone 2 get decided by measurement, not assertion.

**Deterministic voice metrics.** `article_profile` (`evaluation.py:59`) already measures title,
headings, narrative words, opening words, and first-person presence. Extend it with the
properties the blog survey actually measured, since those are known to separate the two
registers: mean paragraph word count (the corpus sits near 50), standalone one-line paragraph
count, sentence-length variance, count of sentences under eight words, question count, inline
link density in words per link (the corpus runs 33 to 60), count of prose blocks making no
concrete claim, and ratio of distinct first-person verbs to total first-person sentences. The
last one is the sharpest available discriminator: in the bad posts the only verb "I" ever takes
is "worked on".

Two further metrics are worth attempting and dropping if they prove noisy: admission density
(the corpus runs about one per 250 words) and whether the closing paragraph matches one of the
four observed ending shapes rather than a summary.

**Calibration, not invention.** Thresholds are read off the corpus rather than chosen:
`2026-08-22.md` and `2026-08-23.md` as positive-passable, `2026-08-24.md` and `2026-08-25.md`
as negative, `2026-08-26.md` as the v3 baseline, and the maker corpus posts that score 4 as the
upper anchor. A metric earns its place only if it separates the negative examples from the
passable references *and* the passable references from the corpus 4s. A metric that only does
the first cannot tell improvement from adequacy.

**Two evidence paths, and an earlier draft of this plan wrongly merged them.** A stub implementing
`run(route, prompt, repository) -> str` returns whatever string the test hands it. It can verify
routing, rendering, validation, caching, and referee mechanics. It cannot say anything about
whether a v4 prompt writes better prose, because no prose is generated. Testing a prompt change
requires running the prompt.

*Permanent offline regression tests.* Stub-driven, no network and no model. They cover small,
deterministic contracts such as prompt rendering, parsing, validation, immutable artifact loading,
and route-free attestation. They intentionally use minimal inline data and do not replay a hidden
full pipeline or claim that stub outputs demonstrate voice quality.

*Harness B, fresh real-route capture* (`automation/experiment_daily_blog_prompts.py`). Renders
the v3 and v4 author prompts over the same sealed projection and runs both through the configured
author and referee routes, producing real candidate posts and anonymous A-versus-B comparisons.
It records deterministic profiles and fresh referee scorecards, but it does not consume or create
historical calibration evidence. It writes one immutable private capture under
`out/vosslab/daily_blog_experiments/`; it does not activate v4, import a bundle, publish a post,
or alter the schedule.

**Stage separation protects the external boundary.** Fresh capture is approved separately from
historical calibration. It sends only the sealed Aug. 23 and Aug. 26 project-context payloads to
the configured routes. Live calibration sends the fixed public historical-post payload to the
referee route and requires its own durable data-sharing setting and invocation approval. A
successful capture is evidence, never activation-ready by itself.

*Stage two, deterministic attestation*
(`automation/attest_daily_blog_prompt_experiment.py`). This route-free command verifies and joins
one immutable fresh capture with one passing live-calibration artifact, recomputes acceptance, and
writes a private immutable attestation. It invokes no model route and has no publisher, importer,
or activation capability. Only a passing attestation is activation-ready; it still does not
activate or publish.

**What the experiment actually varies.** Following El Amri's rule of changing one variable at a
time, harness B runs the arms Phoenix and Taylor used for exactly this question: instruction-only
control, one example, and three examples, all over the same evidence, with enough runs per arm
that sampling noise is visible. That is what decides milestone 2's exemplar count rather than the
three-to-five band being applied on faith.

**Captured fixtures.** The experiment needs a real evidence packet and projection. Fixture capture
now uses the content-addressed `vosslab.daily-blog.experiment-fixture.v2` schema, built directly
from read-only local owner-qualified mirrors and a verified immutable repository-roster snapshot.
The capture boundary accepts only the approved `2026-08-23` quiet and `2026-08-26` busy report
dates. It no longer accepts publisher bundles: a publisher bundle is not a fixture source or a
substitute for the sealed roster, evidence, and projection identities. The fast-lane tests keep
their inputs inline; the offline harnesses consume only verified v2 captures. The previously
recorded publisher-bundle hashes are obsolete diagnostics, not current fixture identities. Fresh
v2 captures are complete: quiet `2026-08-23` is
`4adcb80db0cdde222fbc6a7a53ec008d1198d0cc03f9cecc16c12ddbca24522e`, and busy `2026-08-26` is
`04fd7a045538662e5c6b48ad79e08dd608de1b5a10c1c8857c7b12042bad41da`. Both bind roster snapshot
`0f79bcfea4d3fb783258df4a37effef5996b6fdb9736ff6944fd17051570b8a1` (111 repositories). The
busy fixture contains 34 evidence items across nine active repositories and renders 59,881
projection characters; its projection places `vosslab/cancer-clicker` at position zero with
`created_in_report_window` true, the `new_source_repository` story signal, and citable excerpts.
Harness B may use these sealed inputs for fresh live generation without historical calibration.
The separate live calibration and the deterministic attestation remain pending.

**Metrics stay diagnostic and never become the quality verdict.** They are descriptive: a model
could optimize sentence variance, paragraph size, link density, and first-person verb diversity
and still be dreadful. Quality is judged by the maker rubric applied to real generated samples.
The rubric survey supplies the reason for keeping them out of the rubric itself: "Any criterion
phrased as a target count of a structural unit will be hit exactly and never exceeded."

Verification and evidence, in order:

1. Focused permanent offline tests pass, proving deterministic contract mechanics.
2. Fresh real-route capture produces real v3 and v4 posts over both a busy and a quiet captured
   date, without historical calibration.
3. The fresh referee scorecards show v4 beats v3 on the maker-specific criteria while
   scoring at or above the positive-passable references. Reproducing Aug 22 forever counts as a
   failure, and the acceptance check is written so it reads as one.
4. The fresh referee returns a stable verdict across repeated runs on a fixed pair, which is the
   automated form of the two-reviewers test.
5. Separately approved live calibration scores the five historical posts and produces a passing
   immutable artifact.
6. Route-free attestation joins the verified capture and passing calibration artifact. Only a
   passing attestation is activation-ready; neither command activates or publishes.

### Milestone 16: activate and record

Files: `editorial.py:18-21` template constants, `schema.py:17-18` version constants,
`bundles.py:20-25` paths, `docs/CHANGELOG.md`, `docs/DAILY_BLOG_OPERATIONS.md`,
`docs/HUMAN_GUIDANCE.md`, `docs/DESIGN_DECISIONS.md`.

Point the constants at the v4 files, bump `PROMPT_VERSION` and `RUBRIC_VERSION`, and move the
v3 contracts to `docs/archive/prompt-contracts/v3/` with `git mv`, matching how v2 was archived.

**Activation gates on attested generated prose, not on metrics alone.** The central requirement is
subjective prose quality, so the thing being changed must be exercised before it goes live.
Milestone 16 proceeds only after a deterministic attestation joins a passing fresh busy-and-quiet
capture to passing live historical calibration. Deterministic metrics and permanent offline tests
remain supporting evidence; the attestation is the sole activation-ready artifact. The two preceding
commands are private, non-publishing evidence producers. A separately reviewed change advances
the active contract and producer/publisher interface together.

Verification: full `pytest tests/`, the approved fresh capture, approved live calibration, and the
route-free attestation with its exact source artifact references recorded alongside the activation
change. One-time implementation checks remain separate from the permanent suite.

### Implementation status: August 28

Foundational milestone 0 is complete in the local producer and publisher. Production now begins
with a fresh fail-closed GitHub owner roster and persists a first-class immutable repository-roster
snapshot schema before mirror work. It reconciles exact owner-qualified mirrors and carries
repository creation and fork state through evidence v4 into projection v2. The story-first
projection exposes `new_source_repository` and orders same-day new source repositories before
routine cards. The offline Aug. 26 regression proves
`vosslab/cancer-clicker` reaches activity and the shared author/referee context with its exact
creation time. Bundle v4 seals the complete typed roster as `repository_roster.json`, including
eligible quiet repositories that do not become projection cards; reuse, experiment capture, and
the independent publisher all revalidate that same identity. The final six-reviewer audit's
test-tier, symbolic-link, exact-origin, capture-roster, current-doc, and boundary-coverage findings
are resolved. Producer tests, the full publisher suite, and the cross-repository strict-build E2E
pass. `source_me.sh` now fails closed unless a physical repo-local Python 3.12 environment is
available; 2,012 non-link tests (with 48 deselected) and the roster, prompt-contract,
experiment-lifecycle, and
cross-repository publication E2Es pass under Python 3.12.13.
An earlier full suite reached 2,059 passed with one README/Git-aware Markdown-link failure while the
new documentation and PNGs were untracked. The assets are now staged, the current full suite passes
all 2,238 checks under Python 3.12.13, and the complete direct E2E aggregate passes its eight
permanent runners. Approval-gated capture and calibration remain operational evidence, not E2E
runners or substitutes for them.

Publication identity is now deliberately smaller than bundle content. `report_date` owns the stable
producer bundle, publisher archive, publisher release, and installed post paths; `bundle_sha256`
verifies the currently installed bytes. One per-date producer lock prevents concurrent generation.
Interactive replacement requires exact confirmation, while systemd's direct 04:00
`./make_blog.py --yesterday` invocation preserves an existing coherent date without model work.
The pre-v4 Aug. 26 install is deliberately classified as occupied-invalid: it cannot be preserved as
current, and it remains available for a confirmed fresh active-v3 replacement or deferral until a
separately reviewed v4 cutover. Producer and publisher directory replacements use kernel exchange
operations on Linux and macOS, while the publisher writes
its publication record last as the authoritative multi-path transaction commit.

The implementation keeps v4 non-publishing. The registered candidate-validation policies are now
policy v3 records: active `v3-historical` is
`aada487814ca0080d4a49648440ee6614e5f3a3628be6197ffafcef242969324`; experimental `v4-maker`
is `3a4b7148579e509b6c32fa19b31d107dc4278eb5f721b2a01353a1a9a51264ee`. Both declare a
24,000-character candidate cap, one excerpt marker, one opening prose block, no H2 before that
marker, and a 100-word opening cap. Policy versions 1 and 2 are rejected.

The production orchestrator accepts only active v3 and rejects v4 before its lock, mirror, model,
bundle, or importer phases. Experiment fixture capture is content-addressed v2, accepts only the
approved Aug. 23 and Aug. 26 report dates, and no longer accepts publisher bundles. Fresh quiet
and busy v2 fixtures are complete and bind the immutable 111-repository roster snapshot
`0f79bcfea4d3fb783258df4a37effef5996b6fdb9736ff6944fd17051570b8a1`.

Milestone 15 now has a durable two-stage activation-evidence design. Stage one is a fresh real-route
capture over those sealed inputs; it neither requires nor performs historical calibration. Stage two
is route-free deterministic attestation, which joins one verified capture to one passing live
historical-calibration artifact and is the sole artifact that can be activation-ready. Neither
command activates v4, publishes content, imports a bundle, or changes the schedule.

The authorized Hermes no-content smoke returned OK without a content payload. The attempted full
Aug. 23/Aug. 26 project-evidence capture stopped at the external-action gate before payload egress.
It therefore establishes no live capture, calibration, arm winner, activation-ready attestation,
activation, or publication.

Exactly two external approvals remain: (1) historical-post sharing for the live referee
calibration, including its durable setting and explicit invocation approval; and (2) configured
author/referee route use with the sealed Aug. 23/Aug. 26 project-context payloads for fresh
capture. After those produce a passing calibration artifact and a complete capture, the
deterministic attestation can establish whether the evidence is activation-ready. V4 remains
experimental and inactive until a separately reviewed activation change advances both producer
and publisher contracts.

## Sequencing and hand-off

Work lands in two repositories, `vosslab-podcast` and `vosslab-daily-blog`, and both get a
dated `docs/CHANGELOG.md` entry. Per `docs/REPO_STYLE.md`, agents stage changes and humans run
`git commit`; that is a repository convention rather than a gate on this plan, and every
milestone completes and verifies without it.

Milestone 0 comes first. It gates milestone 4, since the rubric levels are derived from the
corpus rather than assumed, it supplies milestone 2's exemplars, and it settles milestone 3's
shape numbers.

Milestone 3 splits accordingly: its citation, coverage, and inline-link changes touch two
repositories and depend on nothing, so they run immediately in parallel with milestone 0, while
the shape rule waits for the corpus.

Milestones 1, 2, and 4 are prompt authoring and run in parallel once milestone 0 lands.
Milestone 15's harness A can be built as soon as milestone 3's first half is in; the fresh
real-route capture needs 1, 2, and 4 finished, since it exists to run those prompts. Live
historical calibration is independent of capture. Deterministic attestation joins their completed
artifacts, and milestone 16 is last; it gates on an activation-ready attestation rather than on
capture alone.

## Open questions carried into execution

**The exemplar strategy.** Phoenix and Taylor found instruction-only, one-shot, and three-shot
variants all viable, with the winner decided by measurement rather than theory, and Berryman and
Ziegler note that overlong exemplars alongside a large context "can be just as much a liability
as help." Harness B runs that comparison on our own evidence, and milestone 2 ships whichever arm
wins. If no arm beats instruction-only, the examples file is dropped and the slot removed.

**The citation relaxation is a real trade.** Moving from per-paragraph to per-section citation
plus a cap on uncited blocks genuinely weakens the provenance guarantee. It is the smallest
weakening that lets a reflective sentence exist, and harness A is written to prove that a post
cannot use it to smuggle in a large uncited stretch, but it is a trade rather than a free win.

**Whether the two-shape model survives.** It came from eight posts. Milestone 0 has standing
permission to overturn it, including by finding that excellent 400-to-700-word quiet-day posts
are common, which would change the shape rule substantially.

**Where the ceiling actually is.** The 4 band is deliberately unclaimed. Until a post earns it,
the system's own best output is the only evidence of what a 4 looks like, and that is exactly
the circularity the reference terminology exists to hold open rather than close.

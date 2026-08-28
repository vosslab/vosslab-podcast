# Maker blog corpus

## Purpose and method

This report implements milestones 1 to 3 of [better_prompt_plan.md](../better_prompt_plan.md).
It studies first-person author posts about software their authors personally built, changed,
debugged, tested, redesigned, or learned from. It is a voice corpus, not a quality ranking.

I read the 26 author-original pages linked below on 2026-08-27. I excluded news, product
marketing, pure release notes, and tutorials detached from the author's own current work. Counts
are normalized rendered-prose estimates: navigation, code, captions, and footnotes are excluded;
visible H2/H3 headings count as sections. Counts are rounded to 25 words. The short opening and
closing samples are direct excerpts, kept below 25 words per source.

## Corpus records

| Maker | Original post | Subject | Words | Sections | Opening sample | Closing sample |
| --- | --- | --- | ---: | ---: | --- | --- |
| Mitchell Hashimoto | [Ghostty Devlog 001](https://mitchellh.com/writing/ghostty-devlog-001) | Starting a terminal emulator | 1,175 | 7 | "first official devlog" | "Boo." |
| Mitchell Hashimoto | [Ghostty Devlog 002](https://mitchellh.com/writing/ghostty-devlog-002) | Fullscreen, native windows, beta work | 3,050 | 12 | "second official devlog" | "Boo." |
| Mitchell Hashimoto | [Ghostty Devlog 003](https://mitchellh.com/writing/ghostty-devlog-003) | Font work, input, platform bugs | 2,650 | 10 | "a busy month" | "Boo." |
| Mitchell Hashimoto | [Ghostty Devlog 004](https://mitchellh.com/writing/ghostty-devlog-004) | Linux and abstraction choices | 2,000 | 8 | "a little different" | "Boo." |
| Mitchell Hashimoto | [Ghostty Devlog 005](https://mitchellh.com/writing/ghostty-devlog-005) | Inspector tooling and compatibility | 4,550 | 14 | "a lot of updates" | "Boo." |
| Mitchell Hashimoto | [Ghostty Devlog 006](https://mitchellh.com/writing/ghostty-devlog-006) | IO throughput experiments | 2,225 | 7 | "focused on speed" | "Fin." |
| Mitchell Hashimoto | [We rewrote the Ghostty GTK application](https://mitchellh.com/writing/ghostty-gtk-rewrite) | Replacing a GUI architecture | 5,025 | 15 | "my 5th time" | "work left" |
| Mitchell Hashimoto | [Ghostty: reflecting on reaching 1.0](https://mitchellh.com/writing/ghostty-1-0-reflection) | A side project after release | 2,025 | 6 | "personal reflection" | "because it's fun" |
| Julia Evans | [Day 6: I wrote a rootkit!](https://jvns.ca/blog/2013/10/08/day-6-i-wrote-a-rootkit/) | Extending a kernel module | 775 | 2 | "small improvements" | "over the network" |
| Julia Evans | [Writing eBPF tracing tools in Rust](https://jvns.ca/blog/2018/02/05/rust-bcc/) | Experimental tracing interface | 1,625 | 6 | "experimental Rust repository" | "a lot of fun" |
| Julia Evans | [A little tool to make DNS queries](https://jvns.ca/blog/2021/02/24/a-little-tool-to-make-dns-queries/) | A DNS playground | 1,400 | 7 | "small tool" | "improvements I want" |
| Julia Evans | [New tool: an nginx playground](https://jvns.ca/blog/2021/09/24/new-tool--an-nginx-playground/) | A safe configuration playground | 2,300 | 10 | "started coding" | "backend works" |
| Julia Evans | [Writing Javascript without a build system](https://jvns.ca/blog/2023/02/16/writing-javascript-without-a-build-system/) | Making small sites maintainable | 2,250 | 10 | "small simple websites" | "think about it" |
| Julia Evans | [Go structs are copied on assignment](https://jvns.ca/blog/2024/08/06/go-structs-copied-on-assignment/) | A Mess with DNS bug | 1,250 | 8 | "ran into a bug" | "more to learn" |
| Julia Evans | [New microblog with TILs](https://jvns.ca/blog/2024/11/09/new-microblog/) | Adding a small site feature | 700 | 5 | "new section" | "it'll be fun" |
| Simon Willison | [Building Python tools with a one-shot prompt](https://simonwillison.net/2024/Dec/19/one-shot-python-tools/) | Debugging S3 access with a small Python tool | 1,600 | 7 | "tool I built" | "custom instructions" |
| Simon Willison | [Using pip to install a Large Language Model that's under 100MB](https://simonwillison.net/2025/Feb/15/llm-mlx/) | Packaging his LLM tool locally | 1,300 | 8 | "just released" | "explore" |
| Simon Willison | [Everything I built with Claude Artifacts this week](https://simonwillison.net/2024/Oct/21/claude-artifacts/) | A week of small software experiments | 2,000 | 9 | "things I built" | "next week" |
| Simon Willison | [Building a tool to copy-paste share terminal sessions](https://simonwillison.net/2025/Oct/23/claude-code-for-web-video/) | A terminal sharing tool | 1,950 | 8 | "reduce the friction" | "start to finish" |
| Simon Willison | [Adding AI-generated descriptions to my tools collection](https://simonwillison.net/2025/Mar/13/tools-colophon/) | Improving his tool collection | 1,575 | 8 | "78 ... tools" | "moments later" |
| antirez | [Programmers are not different, they need simple UIs.](https://antirez.com/news/107) | Iterating APIs and their user experience | 1,250 | 4 | "days trying" | "user facing part" |
| antirez | [Redis array type: short story of a long development](https://antirez.com/news/164) | Four months designing, rewriting, and testing arrays | 3,500 | 0 | "started" | "feedback" |
| antirez | [Diskless replication: a few design notes.](https://antirez.com/news/81) | Implementing replication after developer feedback | 2,000 | 5 | "focus on implementing" | "some code at least" |
| antirez | [Recent improvements to Redis Lua scripting](https://antirez.com/news/97) | Implementing a debugger and replication behavior | 2,500 | 4 | "I implemented both" | "design and implementation" |
| Max Kaufmann | [Scaffold Level Editor](https://blog.littlepolygon.com/posts/scaffold/) | A solo developer's Unreal level-editing tool | 3,000 | 8 | "tool I'm building" | "architect for it" |
| Max Kaufmann | [Project Update: Tiny Starfighter](https://blog.littlepolygon.com/posts/starfighter/) | Shipping a small demo build of his game | 500 | 0 | "demo build" | "project updates" |

The four requested anchors supply 24 of 26 posts. The Little Polygon devlogs widen the corpus
without changing its genre: a solo maker narrating a specific artifact and its rough edges.

## Selectivity and maker presence

### Selectivity

Strong posts choose a center. Hashimoto says his devlogs cover "a handful of changes that I find
interesting" in [Devlog 005](https://mitchellh.com/writing/ghostty-devlog-005). Evans opens the
nginx piece with a conversation that "got excited" her into coding. Willison begins
[Building Python tools](https://simonwillison.net/2024/Dec/19/one-shot-python-tools/) with the artifact, then spends space
on its surprising behavior rather than every commit. Each makes routine work connective tissue.

The comparison side is a format distinction, not a grade. The comparison-only [Redis
3.2.0](https://antirez.com/news/104) leads with "the big ones are" and inventories features.
The comparison-only [LLM 0.22](https://simonwillison.net/2025/Feb/17/llm/) is intentionally
annotated release notes, so independent changes receive headings. This gives excellent coverage,
but it does not create the single thread needed by a daily maker story. The prompt should choose
the interesting work first and keep routine coverage to a clause.

### Maker presence

Presence lets readers see an initial belief, reaction, admission, trade-off, or intention.
Evans reports that her Go bug exposed a basic concept she had missed. Hashimoto calls the
fullscreen implementation "a doozy." Antirez calls creating working software from nothing
"the magic of programming" in [Disque RC1](https://antirez.com/news/100). These statements
join technical fact to a person who noticed and cared.

The comparison-only [Redis 3.2.0](https://antirez.com/news/104) accurately describes
capabilities while mostly omitting the maker's attention. Its "new BITFIELD command allows"
construction is useful product information, not personal presence. The opening benchmark
explanation in [Devlog 006](https://mitchellh.com/writing/ghostty-devlog-006) likewise needs
several impersonal paragraphs before the discovery appears. That is suitable for a release or
benchmark report; it is insufficient as the default daily voice.

## Shape, quiet days, and endings

The range is 500 to 5,025 words. The sorted word counts are 500, 700, 775, 1,175, 1,250,
1,250, 1,300, 1,400, 1,575, 1,600, 1,625, 1,950, 2,000, 2,000, 2,000, 2,025, 2,225, 2,250,
2,300, 2,500, 2,650, 3,000, 3,050, 3,500, 4,550, and 5,025. Thus the mutually exclusive
length bands are under 1,250: 4; 1,250 to under 2,000: 8; 2,000 through 3,000: 10; and
over 3,000: 4. With 26 records, positions 13 and 14 are both 2,000, so the median is 2,000.

The section-count frequency is auditable from the table: zero sections: 2; two to four: 3;
five to eight: 14; nine to 12: 5; and more than 12: 2. The median section count is 8:
the sorted positions 13 and 14 are both 8. These bands replace the prior, incorrect summary.

The two-shape hypothesis survives as a tendency, not a rule. A straight story has zero to five
sections, 700 to 1,250 words, and one incident or artifact. A findings/release shape has eight
or more sections and 1,250-plus words. The nginx and Rust posts occupy the useful middle:
headings, but still one story. The daily contract should therefore permit an unsectioned or
lightly sectioned story and should remove the minimum-H2 rule.

Excellent quiet-day posts exist. Kaufmann's [Tiny Starfighter](https://blog.littlepolygon.com/posts/starfighter/)
is about 500 words, Evans's [New microblog with TILs](https://jvns.ca/blog/2024/11/09/new-microblog/)
is about 700, and [Day 6](https://jvns.ca/blog/2013/10/08/day-6-i-wrote-a-rootkit/) is about
775. They each name one artifact, one reaction, and one next action. For a 300-to-800 word daily
post, choose one thing; give its before/after or question/answer; say why it matters; leave one
honest frontier. Do not inflate quiet work.

Endings do not usually summarize. The recurring endings are a future update (Hashimoto:
"update you all on that progress"), an incomplete verdict (Evans: "improvements I want"), an
invitation for feedback (Willison), and a small satisfaction (antirez: "Have fun!"). Technical
details serve the story: benchmark measurements make Hashimoto's surprise legible; commands and
fragments reveal Evans's mechanism; Willison's tool and commit links ground a narrated decision.
The existing pipeline still needs traceability, but evidence comments should attach to narrative
sections instead of forcing every reflective paragraph to be a mini changelog.

## Holistic maker-question tally

The audit below makes the tally reproducible. Y means the post contains an explicit answer or a
clear first-person statement for that part; - means it does not clearly do so. This is a presence
audit, not a claim that every post should answer every question.

| Post | Made | Interest | Care | Learned | Next |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ghostty Devlog 001 | Y | Y | Y | Y | Y |
| Ghostty Devlog 002 | Y | Y | Y | Y | Y |
| Ghostty Devlog 003 | Y | Y | Y | Y | Y |
| Ghostty Devlog 004 | Y | Y | Y | Y | Y |
| Ghostty Devlog 005 | Y | Y | Y | Y | Y |
| Ghostty Devlog 006 | Y | Y | Y | Y | Y |
| Ghostty GTK rewrite | Y | Y | Y | Y | Y |
| Ghostty 1.0 reflection | Y | Y | Y | Y | Y |
| Evans: rootkit | Y | Y | Y | Y | Y |
| Evans: eBPF Rust | Y | Y | Y | Y | Y |
| Evans: DNS tool | Y | Y | Y | Y | Y |
| Evans: nginx playground | Y | Y | Y | Y | Y |
| Evans: Javascript | Y | Y | Y | Y | - |
| Evans: Go structs | Y | Y | Y | Y | - |
| Evans: TIL microblog | Y | Y | Y | - | Y |
| Willison: Python tools | Y | Y | Y | Y | Y |
| Willison: pip and LLM MLX | Y | Y | Y | Y | Y |
| Willison: Claude Artifacts | Y | Y | Y | Y | Y |
| Willison: terminal sessions | Y | Y | Y | Y | Y |
| Willison: tool descriptions | Y | Y | Y | Y | Y |
| antirez: simple UIs | Y | Y | Y | Y | Y |
| antirez: Redis arrays | Y | Y | Y | Y | Y |
| antirez: diskless replication | Y | Y | - | Y | Y |
| antirez: Lua scripting | Y | Y | - | Y | Y |
| Kaufmann: Scaffold | Y | Y | Y | Y | Y |
| Kaufmann: Tiny Starfighter | Y | Y | Y | Y | Y |
| Total | 26 | 26 | 24 | 25 | 24 |

The totals are therefore 26/26 made, 26/26 interest, 24/26 care, 25/26 learned, and 24/26 next.
The audit's two clearest gaps remain care and next action; the brief should make room for both,
while examples teach their natural expression.

Each following entry is a complete sentence from an original author page. The excerpts are short
and no source exceeds 25 quoted words.

| Part | Two complete-sentence examples |
| --- | --- |
| Made or changed | Evans: "Hello! I made a small tool to make DNS queries over the last couple of days." ([DNS](https://jvns.ca/blog/2021/02/24/a-little-tool-to-make-dns-queries/)) Willison: "I'll start with an example of a tool I built that way." ([Python tools](https://simonwillison.net/2024/Dec/19/one-shot-python-tools/)) |
| Interested or surprised | Kaufmann: "I was (to say the least) surprised and humbled." ([Tiny Starpilot](https://blog.littlepolygon.com/posts/introduction/)) Hashimoto: "It turns out implementing this was a doozy." ([Devlog 002](https://mitchellh.com/writing/ghostty-devlog-002)) |
| Enjoyed or cared | Evans: "I find that playgrounds really help me learn." ([nginx playground](https://jvns.ca/blog/2021/09/24/new-tool--an-nginx-playground/)) Antirez: "I'm spending days trying to get a couple of APIs right." ([Simple UIs](https://antirez.com/news/107)) |
| Learned | Evans: "I ran into a bug that revealed I was missing a very basic concept!" ([Go structs](https://jvns.ca/blog/2024/08/06/go-structs-copied-on-assignment/)) Antirez: "Then I realized that the level of indirection I picked was wrong." ([Redis arrays](https://antirez.com/news/164)) |
| Try next | Hashimoto: "I hope to come back in a future devlog and update you all on that progress." ([Devlog 006](https://mitchellh.com/writing/ghostty-devlog-006)) Antirez: "I hope the Array PR will be accepted soon." ([Redis arrays](https://antirez.com/news/164)) |

## Comparison-only posts

These author-original pages were useful to contrast a maker story with a feature inventory, but
they are excluded from the 26-post primary corpus because they are release notes or commentary:
[Redis 3.2.0](https://antirez.com/news/104), [Disque RC1](https://antirez.com/news/100), [LLM
0.22](https://simonwillison.net/2025/Feb/17/llm/), and [Twitter conversations](https://antirez.com/news/82).
They do not contribute to the counts, distributions, or audit above.


## Decision for the v4 brief

The corpus does not support a long list of surface-style rules. It supports a direct maker task:
write as the person who made the software; choose the interesting part of today's work; show
attention, surprise, care, learning, and the remaining frontier; let routine work stay brief;
and use technical detail to make the story credible. Examples should demonstrate selection,
admissions, and endings instead of turning them into quotas. The central test remains: this
should feel as though Neil wrote after coding about what he made, what interested him, why he
enjoyed it, what he learned, and what he wants to try next.

## Limits and follow-up

- This is a purposive corpus, not a representative sample of all developer blogs.
- Counts are manual normalized measurements. Repeat extraction with a checked script before
  making numeric thresholds an automated gate.
- Author pages can change. These links are the original sources read on 2026-08-27; preserve
  permitted excerpts when selecting v4 examples.


### Reproduction and exemplar rights

This corpus is analytical evidence, not permission to reproduce external blog posts in a model
prompt. No copyright or reuse license found in this survey clearly grants a general right to copy
long passages from Hashimoto, Evans, Willison, antirez, or Kaufmann. Link to the original post
and quote only the minimum passage needed for analysis.

For v4 prompt examples, treat 2026-08-22 and 2026-08-23 as locally owned house-voice material:
they are the only candidates appropriate for a complete or substantial in-repository exemplar,
subject to the project's own publication decision. Treat external posts as reading evidence by
default. If an external source is materially useful, use a short attributed excerpt (one or two
sentences, generally under 25 words), paired with a link, and preserve only the passage that
demonstrates the desired move. Good short candidates are Hashimoto's "a handful of changes that
I find interesting" for selectivity, Evans's Go-bug admission, and antirez's "magic of
programming" for care. These are analytical quotations, not stand-alone style templates.

| Proposed source | Candidate use | License check evidence | Reproduction decision |
| --- | --- | --- | --- |
| Local 2026-08-22 and 2026-08-23 | House-voice exemplar | Project-owned publication files | Substantial excerpt permitted by project ownership |
| Hashimoto, Devlog 005 | Selectivity sentence | Author page identifies Mitchell Hashimoto; no reuse license is stated on the selected page | Link plus one attributed sentence only |
| Evans, Go structs | Learning/admission sentence | Author page identifies Julia Evans; no reuse license is stated on the selected page | Link plus one attributed sentence only |
| antirez, simple UIs | Care-through-design sentence | Author page identifies antirez; no reuse license is stated on the selected page | Link plus one attributed sentence only |
| Willison, Python tools | Made/changed sentence | Author page identifies Simon Willison; no reuse license is stated on the selected page | Link plus one attributed sentence only |
| Kaufmann, Tiny Starfighter | Quiet-day comparison | Author page identifies Max Kaufmann; no reuse license is stated on the selected page | Link only; no prompt excerpt proposed |

Do not place full external posts or multi-paragraph excerpts in `daily_blog_voice_examples_v4.md`
unless the author has granted a license covering that reproduction and the license notice is
retained. The registered `v4-three-examples-corpus-v2` selection records that boundary:
project-owned August 23 appears in full, while the Julia Evans TIL quotation (20 lexical words;
21 whitespace tokens because of numeric `2`) and Mitchell Hashimoto Devlog 005 quotation
(18 lexical words) remain frozen, attributed excerpts. Together they contain 38 lexical words,
remain below the 25-word per-source limit, preserve source URL, retrieval, rights, and
ASCII-normalization notes, and are illustrative writing evidence rather than task instructions.

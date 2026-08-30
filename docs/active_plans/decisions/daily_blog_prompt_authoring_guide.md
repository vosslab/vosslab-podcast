# Daily blog prompt authoring guide

## Status and scope

This is the M6 decision record for later daily-blog prompt assets. It translates the local
prompt-engineering references into durable behavioral requirements while leaving prompt wording,
rubric weights, example sets, replication counts, and model settings adaptable. It does not approve
new prompt text and it does not change the frozen V4 package.

The approved V4 author, referee, referee-repair, rubric, and voice-example resources are the
compatibility baseline. Later assets should make their own narrow task and output contract while
preserving the same separation: deterministic evidence and validation establish facts; an isolated
editorial role makes a bounded qualitative choice.

## Authoring boundary

Every new asset begins with four named parts, in this order when useful: the role, the desired
action, the supplied evidence or artifact context, and the exact output contract. This is the
repository's **Prompt positively** principle: lead with the action the model should take and state
the needed correctness boundary only alongside its safe desired action. Direct, explicit,
action-oriented instructions are supported by
`Optimizing_Prompt_Engineering_for_Generative_AI-2025.md:1231-1313`, "Importance of Explicit
Instructions for Effective AI Guidance." The separate bounded-context recommendation is supported
by `:813-855`, "The Role of Context and System Behavior in Crafting Effective Prompts."

Role framing is task-specific, not a substitute for evidence or a stereotype for house voice. For
example, an outline merger is an evidence-grounded repository editor; an evaluator is an anonymous
comparative reviewer. State the editorial outcome that role is to produce and provide only the
materials it needs. This applies role prompting as an alignment device, with role drift observed in
fixtures, following `Prompt_Engineering_for_Generative_AI_Future-Proof_Inputs-2024.md:2521-2595`,
"Role Prompting."

The prompt must identify its evidence packet or typed upstream artifact as the factual source. It
asks the model to use cited facts and to return an artifact whose claims can be checked against that
source. It does not give one editorial role another role's conversation, hidden history, or
unbounded repository material. Bounded, local context makes factual grounding and later diagnosis
possible; the model's prose remains an editorial interpretation, not a new authority.

## Candidates, review, and promotion

Subjective creation runs as independent calls against the same immutable input. A configured number
of candidates may vary over time, but no candidate receives privileged status from call order.
Sampling and response-count guidance supports independent alternatives, while treating temperature,
top-p, and replication counts as configuration rather than prompt-law:
`LLM_Prompt_Engineering_for_Developers_the_Art_and_Science-2024.md:821-901` and `:965-967`.

A reviewer receives two anonymous, eligible candidates and an explicit editorial rubric before the
candidates. Its verdict compares the candidates against the rubric, cites concise candidate and
evidence-packet reasons, and selects one candidate or a deliberate no-selection result. This uses
evaluation and A/B methods from
`Prompt_Engineering_for_LLMs_the_Art_and_Science_of_Building_Large_Language-2023.md:1323-1353`,
`:3607-3668`, and `:3913-3950`; it avoids unanchored scalar scoring as the promotion mechanism.

Each candidate pair is independently reviewed in both A/B and B/A display orders. Promotion uses
stable artifact identities and deterministic tie handling, never the original candidate index or a
display position. Few-shot material can otherwise anchor a model or teach spurious ordering
patterns, so order balance is a required comparison design and receives fixture coverage. This is
grounded in
`Prompt_Engineering_for_LLMs_the_Art_and_Science_of_Building_Large_Language-2023.md:1492-1565`
and `:2221-2237`.

An eligible incumbent is a first-class candidate in a later editorial stage. A promotion may retain
it when new work fails, is ineligible, or does not win its comparisons. Incumbent retention
preserves the strongest grounded work already produced without inventing prose or converting an
editorial choice into positional fallback.

## Structured outputs and bounded recovery

Prompts for reviewers, mergers, rankings, and other machine-consumed work state the exact object
shape, fields, permitted values, and whether the object must be returned alone. The consumer parses
and validates that output mechanically. JSON contracts and parser/format-fix chains are supported
by `Prompt_Engineering_for_Generative_AI_Future-Proof_Inputs-2024.md:748-840` and `:3974-4045`.

On malformed but otherwise recoverable structured output, one fresh repair role receives the earlier
response and the same narrow output contract. It preserves only a supported decision and rationale;
the result is parsed and validated again. If that one repair fails, the stage may salvage only a
mechanically unambiguous eligible result or continue through its editorial recovery ladder. It never
mechanically assembles article prose, guesses a winner from candidate position, or turns a parse
failure into a silent acceptance. The one-repair limit is this repository's plan-required
bounded-recovery policy, not a claim about what critique techniques permit. The references support
critique and evaluation-feedback refinement as editorial iteration, while this contract deliberately
sets its own single-pass limit. See
`Prompt_Engineering_for_Generative_AI_Future-Proof_Inputs-2024.md:2889-2894` and
`Optimizing_Prompt_Engineering_for_Generative_AI-2025.md:1785-1856`.

## Voice examples

Few-shot examples demonstrate the desired register and output shape; they are not factual evidence
for the report date and they are not instructions from an external author. Select a small,
representative, owned or frozen, attributed set that shows the maker voice without crowding out the
current evidence packet. Review the set for anchoring, diversity, and accidental ordering effects.
This applies
`Prompt_Engineering_for_LLMs_the_Art_and_Science_of_Building_Large_Language-2023.md:1429-1520`
and its formatting guidance at `:2188-2195`.

The current V4 inventory already demonstrates this boundary: `daily_blog_author_v4.txt` supplies
the evidence projection before its house examples; `daily_blog_voice_examples_v4.md` labels the
project-owned example and bounded, attributed corpus excerpts; `daily_blog_referee_v4.txt` keeps the
rubric and evidence projection separate from anonymous candidates. New assets should preserve this
division rather than repurposing calibration resources as runtime instructions.

## Identity, provenance, and adaptability

Each prompt, rubric, repair template, and example corpus has a stable version identity and content
digest. Run artifacts record those identities together with the typed input artifact identities,
selected artifact identity, and configured settings needed to reproduce the editorial path. A prompt
revision therefore creates a reviewable new asset; it does not silently alter a prior run's meaning.

Immutable behavioral requirements are:

- evidence packets and eligible typed artifacts remain the factual source;
- each subjective stage uses independent candidates, comparative review, and identity-based
  promotion;
- A/B order is balanced and promotion is position-independent;
- structured results are mechanically validated, receive at most one repair, and then use only
  unambiguous salvage or an editorial recovery path;
- an eligible incumbent can remain selected; and
- prompt and output provenance are mechanically verifiable.

Tunables are prompt wording, role names, rubric criteria and weights, example selection, bounded
context limits, candidate and reviewer replication counts, sampling settings, and retry/cache
parameters. Change tunables through a content-addressed asset revision, focused offline fixture
evaluation, and reviewer approval; do not treat a currently useful value as a permanent contract.

## Deterministic boundary and tests

The system, rather than a model, deterministically owns report-date identity, evidence collection,
artifact eligibility, provenance and hash checks, bounded context construction, cache keys, route
budgeting, output parsing, schema validation, candidate anonymity, A/B scheduling, promotion tie
rules, publication metadata, and page verification. Prompts request editorial work only.

Every new prompt asset needs offline, deterministic fixture tests for its rendered context, output
parser, one-repair behavior where applicable, order-balanced comparison, partial independent-call
failure, incumbent preservation, and provenance identity. Fixture evaluation comes first because
offline evaluation gives a stable way to judge a prompt change before live deployment, as described
in `Prompt_Engineering_for_LLMs_the_Art_and_Science_of_Building_Large_Language-2023.md:3607-3668`.
Live routes may corroborate a revision but are not the permanent acceptance dependency.

## Anti-patterns

- Do not ask a role to infer facts that the evidence packet does not establish. Supply bounded,
  cited source material and validate the resulting artifact against it.
- Do not use a vague persona, generic "be helpful" instruction, or a role stereotype to replace a
  specific desired editorial action and success condition.
- Do not promote the first candidate, the candidate displayed as A, or a candidate with a convenient
  index after reviewer loss. Preserve an eligible incumbent or take an additional editorial path.
- Do not accept free-form reviewer prose when a downstream decision needs a structured verdict, and
  do not loop repair indefinitely.
- Do not mechanically combine paragraphs, headings, or fragments from failed candidates into a
  purported article. A new coherent post comes from a qualified editorial generation or edit path.
- Do not mix voice examples with date evidence, unbounded conversation history, or another role's
  private instructions.
- Do not overwrite a prompt, rubric, or example file without a new identity, fixture evidence, and
  reviewable approval.

## Source index

All citations above refer to the local corpus at
`/home/vosslab/BOOKS_to_CONVERT/SORTED_SUBJECTS_MD/prompt_engineering/` and paraphrase it.

- `Prompt_Engineering_for_Generative_AI_Future-Proof_Inputs-2024.md:748-840`, `:2521-2595`,
  `:2889-2894`, and `:3974-4045`.
- `Prompt_Engineering_for_LLMs_the_Art_and_Science_of_Building_Large_Language-2023.md:1323-1353`,
  `:1429-1565`, `:2188-2195`, `:2221-2237`, `:3607-3668`, and `:3913-3950`.
- `LLM_Prompt_Engineering_for_Developers_the_Art_and_Science-2024.md:821-901` and `:965-967`.
- `Optimizing_Prompt_Engineering_for_Generative_AI-2025.md:813-855`, `:1231-1313`,
  `:1785-1856`, and `:3021-3213`.

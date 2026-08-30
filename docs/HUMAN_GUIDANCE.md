# Human guidance

<!-- VENDORED HEADER: START -->
Record the durable guidance Neil Voss states, or approves for preservation here, in his own words:
first person or close paraphrase, one to three lines per bullet. Material he supplies as a source
may inform [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) once it is settled, and an entry of uncertain
origin belongs there too. Rules: [REPO_STYLE.md](REPO_STYLE.md).
[PROPAGATED HEADER - ENTRIES BELOW ARE YOURS]
<!-- VENDORED HEADER: END -->

## System design

- This is pre-production: improve foundational schemas, contracts, abstractions, and ownership
  boundaries directly instead of carrying legacy support.
- Prioritize the long term and adaptability. Keep responsibilities explicit and components replaceable;
  fix the design that caused a problem rather than treating its symptom.
- Dream big, build on the ambition already present, complete the required work, and finish the obvious.
  When one option is clearly best, take it, document the assumption, and continue.
- Use Hermes for model selection and account routing because it is more robust than a quick local
  selector. Keep every pipeline stage other than content generation deterministic.
- Hermes selects and executes configured model routes; systemd owns scheduling and the project owns
  publication identity, orchestration, validation, and installation.
- Route daily-blog authors and the referee through `openai-codex`, then let Hermes' configured
  best-available account pool choose the eligible credential; do not pass provider keys or account
  labels through the project.
- Treat `report_date` as the sole publication identity. A bundle digest proves integrity, not identity.
- Let one run own a report date at a time. A confirmed overwrite replaces that date's generated
  result rather than creating concurrent variants or preserving an unwanted earlier generation.
- Treat blog prose as regenerable LLM output rather than irreplaceable content.
- Have systemd call `./make_blog.py --yesterday` non-interactively at 04:00 each morning. Systemd is
  the schedule owner because Hermes cron scheduling has been unreliable.
- Use `-Y` as the short form of `--yesterday` and `-y` as the short form of `--yes`, so date
  selection and confirmed replacement remain visually distinct.
- For an interactively requested date that is already published, ask
  `Overwrite YYYY-MM-DD? [N/y]:`; only exact `y` confirms replacement.

## Model instructions

- Edit downstream LLM prompts carefully because small wording changes can easily break their behavior.
- Treat the daily-blog prompt prose as human-owned editorial material. Agents may analyze outputs,
  identify failure patterns, and propose a reviewable diff, but they do not rewrite or approve the
  prompt wording without my explicit approval of the exact text.
- Keep software and schema migrations separate from editorial prompt revisions. A machine-contract
  change alone does not justify changing the human prompt edition or its prose.
- Use the August 22 and August 23, 2026 posts as the current positive voice references: thematic,
  first-person human blog entries rather than exhaustive or mechanical changelogs.
- Lead with the action, source, structure, and output the model should produce.
- Phrase each instruction as a direct desired outcome, such as "Use the evidence packet as the
  factual source" or "Return one JSON object."
- Give each model the tools, roles, and actions that contribute to its result. Omit unrelated
  alternatives and actors from its context.
- Run each blog author, referee, and repair attempt as a fresh isolated model task with one
  self-contained prompt. Share deterministic evidence and sanitized capacity state, not conversation
  history, saved sessions, memory, or another role's instructions.
- Translate workflow ownership into the model's concrete task and success condition.
- Reserve explicit boundary language for safety and correctness requirements, and pair the boundary
  with the desired safe action.
- Review prompts from the perspective of a small model that may treat every named action as a
  request. Prefer short affirmative instructions and explicit output contracts.
- On 2026-08-27, I explicitly approved the exact experimental v4 maker brief and central question
  recorded in `docs/archive/PROMPT_EXPERIMENT_STATUS.md`.
- That approval covers those exact words only; it is not a blanket approval for later prompt rewrites.
- Keep the approved v4 maker brief and central question unchanged while agents complete the
  fixture-backed calibration, capture, attestation, review, activation, and publication path.
- Use sealed August fixtures, deterministic role fakes, synthetic transitions, disposable roots, and
  artifact-based fresh-subagent review as the complete unattended acceptance path. Live external model
  calls are optional one-time corroboration and never a milestone dependency.
- Activation remains a separately reviewed producer/publisher cutover after F4's fixture-backed
  artifact evidence accepts the unchanged central question.

## Plans and tests

- Ground plan requirements and gates in user-visible behavior, repository policy, empirical evidence,
  or a demonstrated failure mode. Do not require byte, pixel, or arbitrary performance equivalence
  merely because a plan improves an existing system.
- Apply the repository and pytest rules before adding tests. If a proposed test forces an unrequested
  production workaround, first treat the test as defective and fix or remove it.
- Separate one-time implementation evidence from permanent pytest coverage. Keep permanent tests
  offline, deterministic, behavior-focused, and self-contained; avoid extraneous fixtures and remove
  marginal tests when their maintenance cost is not justified.

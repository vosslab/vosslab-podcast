# Human guidance

<!-- VENDORED HEADER: START -->
Record the durable guidance Neil Voss states, or approves for preservation here, in his own words:
first person or close paraphrase, one to three lines per bullet. Material he supplies as a source
may inform [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) once it is settled, and an entry of uncertain
origin belongs there too. Rules: [REPO_STYLE.md](REPO_STYLE.md).
[PROPAGATED HEADER - ENTRIES BELOW ARE YOURS]
<!-- VENDORED HEADER: END -->

## Model instructions

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
- Translate workflow ownership into the model's concrete task and success condition.
- Reserve explicit boundary language for safety and correctness requirements, and pair the boundary
  with the desired safe action.
- Review prompts from the perspective of a small model that may treat every named action as a
  request. Prefer short affirmative instructions and explicit output contracts.

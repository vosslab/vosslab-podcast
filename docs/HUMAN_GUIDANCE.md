# Human guidance

## Model instructions

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

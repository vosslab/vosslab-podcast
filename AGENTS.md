# Agent quickstart

- Read `CODEX_CHAT_TRANSCRIPT.txt` at session start.
- `docs/REPO_STYLE.md`
- `docs/PYTHON_STYLE.md`
- `docs/MARKDOWN_STYLE.md`
- `docs/PYTEST_STYLE.md`
- `docs/DEVELOPMENT.md`
- `docs/HUMAN_GUIDANCE.md`
- `docs/CHANGELOG.md`

# Workflow and runtime

- After major changes, append a dated change, test, and next-actions section to `CODEX_CHAT_TRANSCRIPT.txt`.
- Update `docs/CHANGELOG.md` when editing.
- Use Bash with Python 3.12: `source source_me.sh && python3`.
- Run focused tests for code changes; full suite: `source source_me.sh && pytest tests/`.

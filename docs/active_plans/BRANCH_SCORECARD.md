# M1 branch scorecard

## Purpose and scope

This scorecard records the M1 comparison required by
[docs/active_plans/DAILY_GITHUB_BLOG_REVIVAL_PLAN.md](DAILY_GITHUB_BLOG_REVIVAL_PLAN.md).
It evaluates the current `dr_voss` tip and `origin/main` as intentional candidates for the
revived daily GitHub blog. It is not a merge plan and makes no branch changes.

The target is one explicit local-calendar date, confirmed `vosslab` attribution, complete
commit-level provenance, Aella/Hermes-authored Markdown guarded by deterministic validation,
a user-scoped output contract, and a private-LAN-only static site.

## Comparison record

| Item | Recorded value |
| --- | --- |
| Common base | `5ff9d834f896fd5c655627b237995141d7061eda` |
| `dr_voss` tip | `a237f3e8864a896b3b28a184274f238b5ff673d4` |
| `origin/main` tip | `da6679ebbee14ca70e6812321d8ba7e4eeba254f` |
| Divergence from base | `dr_voss`: 24 commits; `origin/main`: 3 commits |
| Comparison method | Read-only Git inspection plus isolated `git archive` artifacts |
| Dynamic test evidence | `dr_voss`: 32 focused tests passed; `origin/main`: log-mode smoke passed |

Before comparison, the current `dr_voss` worktree contained tracked modifications to
`CODEX_CHAT_TRANSCRIPT.txt` and `docs/CHANGELOG.md`, plus these protected untracked files:

- `devel/submit_to_pypi.py`
- `docs/CLAUDE_HOOK_USAGE_GUIDE.md`
- `docs/E2E_TESTS.md`
- `docs/PYTEST_STYLE.md`
- `docs/active_plans/DAILY_GITHUB_BLOG_REVIVAL_PLAN.md`

These files were not changed by the branch comparison. This scorecard is an additional planned
untracked documentation artifact.

## Scoring method

Each criterion is scored on a 0-5 readiness scale.

- 5: satisfies the planned M2-M4 contract now.
- 3: contains a directly reusable implementation with bounded replacement work.
- 1: contains useful supporting concepts but fails the stated contract.
- 0: absent or conflicts with the planned architecture.

A higher total does not authorize a merge. Scores identify reusable components and the lowest-risk
rebuild base.

## Side-by-side findings

| Criterion | `dr_voss` | `origin/main` | Evidence-led finding |
| --- | ---: | ---: | --- |
| Explicit date and timezone | 1 | 3 | `origin/main` supplies `--date YYYY-MM-DD`, IANA timezone input, and local midnight-to-midnight boundaries in `pipelines/01_logs_to_outline.py`. `dr_voss` supports trailing windows only and uses a fixed 05:00 reset; it has no `--date`. Neither fully implements the plan's configured timezone and last-completed-day behavior. |
| Attribution filtering | 0 | 0 | Neither branch accepts a login/email allowlist or classifies commits as confirmed, ambiguous, or excluded. `dr_voss` writes every commit found in a recently updated repository. `origin/main` similarly summarizes all commits returned for a repository date window. |
| Source provenance | 1 | 1 | Both retain a SHA or raw API object, but neither produces a normalized claim packet, API URL, HTML commit permalink map, or per-factual-bullet source link. `origin/main`'s generated blog has no commit links; `dr_voss`'s blog context passes commit subjects without required links. |
| Aella/Hermes writing readiness | 0 | 0 | Neither tip contains a Hermes invocation, `daily-github-blogger` skill, agent draft, agent-generation manifest, or validator for claim IDs and SHAs. Both retain the out-of-scope vendored local-LLM path. |
| Deterministic validation | 1 | 2 | `dr_voss` checks some LLM error/length conditions and records a rate-limit stop flag, but it does not block publication on a complete evidence manifest. `origin/main` has deterministic outline and script shape validators, but no blog/provenance/completeness validator. |
| Test coverage and health | 3 | 0 | `dr_voss` contains 30 tracked test/support files. Its focused fetch, outline, and blog test run passed: `32 passed in 0.30s` in the isolated artifact. The tests cover trailing-window helpers, parser behavior, caches, and local-LLM output handling, not the planned identity/provenance fixture contract. `origin/main` has no tracked `tests/` files. |
| Output layout | 3 | 2 | `dr_voss` has [docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md](../OUT_DIRECTORY_ORGANIZATION_SPEC.md) and user-scoped `out/<user>/...` defaults, a useful base for the planned `out/vosslab/daily/YYYY-MM-DD/` namespace. It needs a new daily run-manifest, claim, draft, validation, and site layout. `origin/main` consistently uses `data/YYYY-MM-DD/`, which supports date isolation but conflicts with the required user-scoped `out/` contract. |
| Private-LAN operation | 0 | 0 | Neither tip contains a static-site build, server configuration, bind-address validation, listener inspection, LAN smoke test, or recovery documentation. No tracked site/server configuration exists in either tip. |
| Total | 9 / 40 | 8 / 40 | Both require an evidence-layer rebuild. `dr_voss` is stronger in test and output-contract scaffolding; `origin/main` is stronger only in explicit-date mechanics and small deterministic validators. |

## Dynamic evidence

The isolated `origin/main` log-mode run used a local fixture and completed:

```text
01_logs_to_outline --source logs --date 2026-08-10: wrote outline.json
01_validate_outline --date 2026-08-10: validated outline.json
02_outline_to_blog --date 2026-08-10: wrote blog.md
```

This verifies its explicit-date artifact routing and outline validator only. The resulting blog
still emitted generic narrative text and no commit provenance, so it does not meet the planned
blog contract.

The isolated `dr_voss` focused test command was:

```text
source source_me.sh && pytest -q tests/test_fetch_github_data_features.py \
  tests/test_outline_parser.py tests/test_outline_to_blog_post.py
```

It passed with `32 passed in 0.30s`. The archive is not itself a Git worktree, so the test run used
that archive as `GIT_WORK_TREE` with the repository object as read-only `GIT_DIR`. No branch,
index, ref, or tracked source file changed.

No branch stores a common recorded GitHub fixture that can exercise both incompatible input
schemas. Consequently, this M1 dynamic evidence does not claim functional parity. A shared,
recorded fixture is required in M2 before an end-to-end comparison can prove date, identity,
pagination, partial-data, and provenance behavior.

## Component disposition

| Component | Decision | Rationale |
| --- | --- | --- |
| `dr_voss` `pipeline/fetch_github_data.py` | Replace | Preserve only its PyGithub/cache/JSONL experience after redesign. Remove recent-repository gating, non-commit data, trailing-window semantics, and unverified attribution. |
| `dr_voss` `pipeline/` output contract | Retain selectively | Use the user-scoped `out/<user>/` approach as the base, then add the planned date-scoped daily artifact contract. |
| `dr_voss` test structure | Retain selectively | Reuse test organization and helper conventions, but add offline fixtures for attribution, timezone boundaries, pagination, completeness, claims, and publication blocking. |
| `dr_voss` local-LLM wrapper, prompts, depth/referee, TTS, social stages | Discard from revival path | They conflict with the Aella/Hermes-only prose requirement and daily-blog scope. |
| `origin/main` `--date` and IANA-boundary concepts | Retain selectively | Reimplement these ideas in the new evidence fetcher with exact configured-date semantics. Do not copy its repository-activity classification as personal attribution. |
| `origin/main` validators | Retain as design reference | The stage-validator pattern is useful, but replace its shape-only checks with claim, SHA, link, and completeness validation. |
| `origin/main` `data/YYYY-MM-DD/` layout | Discard | It conflicts with the planned user-scoped `out/vosslab/daily/YYYY-MM-DD/` layout. |
| `origin/main` generic blog, local-LLM/referee, audio pipeline | Discard from revival path | It lacks provenance and conflicts with the Aella/Hermes-only daily-blog scope. |

## Baseline recommendation

Recommend `dr_voss` as the protected rebuild baseline, with selective reference reuse from
`origin/main` for explicit `--date` handling, IANA date boundaries, and staged deterministic
validation structure.

Rationale:

- `dr_voss` has materially better test scaffolding and a documented user-scoped output contract.
- Its GitHub client and JSONL experience provide a narrower migration path to a deterministic
  claim layer than starting from `origin/main`'s broader repository-story design.
- `origin/main` should remain untouched and should contribute concepts, not be merged wholesale.
- Neither branch can serve as a direct implementation baseline without replacing its acquisition,
  prose, validation, and LAN-operation paths.

## Required human decision

Dr. Voss must approve or reject the recommended `dr_voss` rebuild baseline before any branch-
changing operation. Approval must explicitly confirm all of the following:

- Preserve `dr_voss` and `origin/main` unchanged.
- Create a clearly named revival branch only after approval.
- Carry the protected untracked files forward deliberately.
- Reimplement, rather than merge, the selected `origin/main` date and validator concepts.
- Keep scheduling disabled until the manual Aella-authored and private-LAN review gates pass.

Until that decision is recorded, no merge, rebase, reset, deletion, force-push, or revival-branch
creation is authorized.

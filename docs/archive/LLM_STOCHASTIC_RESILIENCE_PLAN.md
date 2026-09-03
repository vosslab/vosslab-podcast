# Plan: Make daily publication succeed with variable LLM output

## Context

The September 2 bulk run exposed two concrete control-flow failures.

- The August 17 run found no activity even though `vosslab/vosslab-skills` had a commit. Activity
  discovery filtered Git history through one configured author name and email.
- The August 14 run received successful model responses, but authored-body checks rejected every
  response for citation-density, presentation, and publication-policy findings.

The route returned usable work; the pipeline discarded it. This is a gating problem, not evidence
that the model needs stricter instructions. The archived
[`LAYERED_PODCAST_IMPROVE_PLAN.md`](LAYERED_PODCAST_IMPROVE_PLAN.md) states the useful
principle: quality signals belong off the control path, and editorial preference is distinct from
mechanical eligibility.

`docs/BLOG_CONTRACT.md` remains human-owned and unchanged. It requires evidence grounding,
replication, review, promotion, and preservation of successful work. It does not require prose to
pass a fixed house-style validator before publication.

## Objectives

- Create a blog entry despite many LLM calls barely following their instructions.
- Establish the complete account/date commit set before repository discovery or model work.
- Preserve every mechanically safe, evidence-grounded complete post as a publishable candidate.
- Keep editorial preferences available to writers, editors, and reviewers without making them abort
  conditions.
- Remove tests that make success depend on exact LLM prose, formatting, or instruction compliance.

## Design philosophy

**Robust means a blog entry is created despite many LLMs barely listening. Robust does not mean
making publication more likely to fail by adding gates.**

The design keeps stable evidence, provenance, filesystem, publication-identity, and source-safety
boundaries. Editorial judgment stays replaceable and non-blocking. This follows the repository's
"fix the design, not the symptom" and "perfect is the enemy of good" principles.

The trade-off is deliberate: a published post may need later editorial improvement, but the pipeline
must not report a fault merely because generated prose missed a preferred shape. Increasing retries,
prompt rigidity, validation reasons, or compliance tests would multiply the same failure mode.

- Evidence strategy for uncertain methods: use one-time live and controlled checks to prove the
  publication path, then retain only tests for stable deterministic boundaries.

## Scope

- Add Step 0 using GitHub commit search for `user:<owner> author-date:<report_date>`.
- Write `daily_commits.md` in the run directory before model work, grouped by repository and linked
  to exact commits.
- Limit commit-message previews to the first line and at most 160 characters.
- Use Step 0 repository/SHA references as the source for activity location.
- Remove author-name and author-email identity filters from daily discovery and settings.
- Refresh mirrors only for repositories named by Step 0; make an empty day a valid no-op mirror
  phase.
- Remove the synthetic owner-only evidence record used for empty activity.
- Admit complete posts through mechanical provenance and safety checks only.
- Keep citation-density and presentation findings only as optional editor feedback.
- Delete permanent tests and controlled scenarios whose success depends on strict LLM compliance.
- Update design, operator, architecture, format, troubleshooting, changelog, and transcript records.

## Non-goals

- Do not revise approved prompts, rubrics, examples, or `docs/BLOG_CONTRACT.md`.
- Do not add retries, sample policies, response schemas, admission reasons, or fallback rungs.
- Do not make subjective prose quality, exact prompt copy, role counts, call counts, or model response
  wording a permanent test condition.
- Do not add network access to pytest or committed response fixtures.
- Do not weaken evidence authority, repository scope, output confinement, approved image paths,
  metadata ownership, source safety, or sealed publisher validation.

## Current state summary

The current worktree contains Step 0, account/date discovery, active-repository mirror selection, a
quiet-day no-op, mechanical complete-post admission, and documentation updates. A live August 17
query returns commit `92672c25d91d825eef0038d84480db71eddc4b25` from
`vosslab/vosslab-skills`; local mirror resolution produces one activity record.

The earlier attempt-plan machinery is not expanded here. Existing retry and observability components
may remain where they do not reject usable work, but their topology and tunable counts are not
acceptance requirements.

## Approach

1. Establish the day's evidence once.
   - Query all owner repositories for the report date.
   - Persist the human-readable commit inventory.
   - Carry exact repository/SHA pairs into deterministic mirror resolution.
2. Narrow the publication boundary.
   - Keep provenance, scope, path, image, metadata, and source-safety checks.
   - Move prose-shape findings out of eligibility and retain them only as editor suggestions.
3. Remove compliance-driven tests.
   - Delete tests for narrative word bands, citation density per section, prescribed coverage
     presentation, fixed headings, exact prompt wording, and style-only exhaustion.
   - Delete synthetic orchestration tests that construct states the real Step 0 cannot produce.
   - Keep parser, provenance, source-safety, confinement, and publisher-integrity tests.
4. Prove the rebuilt path.
   - Run focused offline tests and the complete pytest suite.
   - Run the controlled producer-to-publisher E2E outside pytest.
   - Run disposable one-time checks for the live August 17 commit and an empty day.

## Files to modify

- `pipeline/podlib/github_client.py`: account/date commit search.
- `pipeline/daily_blog/activity.py`: Step 0 rendering and exact commit resolution.
- `pipeline/daily_blog/acquisition_workflow.py`: Step 0 ordering and active mirrors.
- `pipeline/daily_blog/run_state.py`: confined Markdown artifact writing.
- Daily-blog configuration and `settings.yaml`: remove author identity filters.
- `pipeline/daily_blog/evidence.py`: remove synthetic no-activity evidence.
- Complete-post admission and validation: keep style findings off the success path.
- Daily-blog tests: remove strict-compliance and synthetic implementation-detail tests.
- Daily-blog design and operating documentation.

## Verification

Permanent verification:

- Focused daily-blog tests pass offline.
- Repository style, Pyflakes, import, ASCII, whitespace, and source-size checks pass.
- The full `source source_me.sh && pytest tests/` suite passes.
- No permanent test invokes GitHub, a live model, or a publisher network.

One-time implementation evidence:

- A fresh August 17 GitHub search returns the `vosslab/vosslab-skills` commit and the refreshed local
  mirror resolves it into one activity record.
- The local inventory shows a first-line, truncated commit-message preview.
- A disposable empty search result writes "No commits were found," performs no mirror operation, and
  completes evidence acquisition.
- The controlled publication E2E verifies same-date replacement and failure preservation without
  asserting subjective prose quality.

Completion does not require a live model to follow exact directions, a stochastic comparison
threshold, or a new permanent fixture.

## Risk register

| Risk | Impact | Trigger | Owner | Mitigation |
| --- | --- | --- | --- | --- |
| A style check returns under another name | High | Grounded responses end as `no_eligible_generation` for prose shape | Admission owner | Keep one mechanical eligibility function and make body findings advisory |
| Step 0 and mirrors disagree | High | A listed repository/SHA has no local object | Acquisition owner | Preserve the inventory and repair source collection instead of inventing evidence |
| Tests dictate production topology | Medium | Code exists only for a synthetic fixture | Test owner | Apply `docs/PYTEST_STYLE.md`; delete tests that do not protect durable user behavior |
| Safety is mistaken for editorial strictness | High | Provenance, path, image, or source safety is removed | Publication owner | Keep trust boundaries explicit and separate from prose preference |

## Documentation close-out requirements

- Keep this plan consistent with the shipped control flow.
- Record the robustness definition in `docs/DESIGN_DECISIONS.md`.
- Update `docs/CHANGELOG.md` with Step 0, gate removal, and test deletion.
- Append a dated change, test, and next-actions entry to `CODEX_CHAT_TRANSCRIPT.txt`.
- Record live and disposable checks as one-time evidence, never as pytest requirements.

## Resolved decisions

- The observed failure was gating, not prompting.
- GitHub account/date search establishes the day before author identity is considered.
- Editorial preferences may influence generation and review but cannot block publication.
- Mechanical evidence and publication-safety boundaries remain authoritative.
- Fewer permanent tests are preferred to tests that freeze LLM behavior or implementation topology.

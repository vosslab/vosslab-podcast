# Daily blog operations

## Ownership

`vosslab-podcast` owns the complete scheduled workflow through local site import. It refreshes
repository caches, selects exact Git activity, assembles evidence, runs the editorial roles, writes
the immutable bundle, and calls the importer in `vosslab-daily-blog`.

`vosslab-daily-blog` owns MkDocs source, validation, immutable built releases, the served `site`
pointer, and the static service on port 8016.

## Manual publication

Run one explicit Central-calendar date from the producer repository:

```bash
cd /home/vosslab/nsh/vosslab-podcast
source source_me.sh && python3 automation/publish_daily_blog.py --date 2026-08-23
```

A successful command reports the approved bundle path and bundle ID, then performs the site import.
If authoring, validation, prompt rendering, or referee approval is blocked, the command raises
`EditorialBlockedError` and creates or imports no bundle.

## Configuration

The `daily_blog` section of `settings.yaml` defines:

- `repository_path`: local `vosslab-daily-blog` checkout.
- `mirror_cache_root`: durable physical Git worktrees.
- `report_timezone`: IANA timezone used for report-day boundaries.
- `repository_urls`: HTTPS GitHub clone sources for caches that do not exist yet.
- `identity_names` and `identity_emails`: exact author attribution evidence.
- `routes.authors`: exactly two isolated author command routes.
- `routes.referee`: a separately named referee command route.
- `collection_limits`: per-source, per-item, total supporting, and screenshot limits applied while
  retaining the authoritative evidence packet.
- `projection_limits`: complete rendered context, exact excerpt, and repository-card subject limits.
- `prompt_limits`: complete author and referee envelopes after templates, rubric, candidates, and
  projection context are rendered.
- `shadow_evaluation.external_model_data_sharing`: explicit approval for sending exact-Git evidence
  to the author routes and the historical post plus evidence to the referee route; defaults to
  `false`.

Role commands receive the complete prompt through standard input. The checked-in Hermes routes use
`--query-file -` and `--ignore-rules`; repository templates therefore own the full editorial
instruction contract while the active profile retains only its configured model/provider route.
Configuration rejects profile skills, inline queries, and resumed sessions for Hermes roles.

Final candidates pass objective v3 house-style gates: one compact opening paragraph, 350-650
narrative words, two to four narrative H2 sections, and one final Project coverage section naming
every active repository. Front matter binds the post to `editorial_projection`, and generic
date-derived Work log titles are invalid. The referee judges the semantic qualities that
deterministic code cannot prove, including thematic focus, reader interest, and cross-project
synthesis. Its winner, evidence-quality label, and confidence remain strict control fields; an
overlong explanatory reason is bounded to operational metadata rather than becoming an outage.
The author template's exact `thematic-lowercase-slug` sentinel is resolved mechanically from the
single thematic H1 before candidate hashing and validation; unresolved sentinels remain invalid at
both the producer and publisher boundaries.

## Cache checks

Physical Git caches live below `/home/vosslab/repo-mirrors/vosslab`. Each cache has its own lock
under `.locks/`. A refresh manifest records the origin URL, result, default revision, exact-object
availability, ref fingerprint, error, and timestamp.

Add a repository URL to `settings.yaml` before the first run when no cache exists. The manager
clones it once, then subsequent manual and scheduled runs share the same lock and worktree.

## Inspecting a run

For a reported `RUN_ID`, inspect:

```text
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/run_state.json
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/events.jsonl
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/mirror_manifest.json
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/activity.json
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/evidence.json
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/editorial_projection.json
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/candidate_validation.json
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/referee.json
```

The authoritative run v2 state has nine ordered phases:

1. `mirror_refresh`
2. `activity_location`
3. `evidence_assembly`
4. `editorial_projection`
5. `author_generation`
6. `candidate_validation`
7. `referee_selection`
8. `bundle_creation`
9. `site_import`

Every phase records its input and output hash. A new invocation always creates a new immutable run
directory. Hash-verified cache envelopes can reuse exact activity, evidence, projection, fully valid
candidate artifacts, and approved referee decisions. Blocked editorial attempts run again on the
next invocation. A prior immutable bundle is reused only after all of its files and contract
identities pass revalidation. The importer still executes, and an `idempotent` result records that
the same bundle is already installed.

For failures before a run enters the orchestrator, or for multi-date catch-up behavior, inspect the
schedule-level stream:

```text
out/vosslab/daily_blog_schedule_events.jsonl
```

It records cursor reconciliation, skipped and attempted dates, publisher receipt discovery, cursor
advancement, remaining backlog, and safe failure classes. The same structured lines are available in
the user-service journal. Raw exception text is intentionally absent from these event objects.

## Inspecting a bundle

Complete bundles live at:

```text
out/vosslab/daily_blog/YYYY-MM-DD/RUN_ID/
```

Verify that `latest.json` names the expected run, then inspect `bundle.json`, `evidence.json`,
`editorial_projection.json`, and `post.md`. The bundle binds the selected post and referee record to
the same projection ID. Asset hashes and Git blob identities appear in the manifest and evidence
packet.

## Historical shadow evaluation

Run the current evidence and editorial contracts against a preserved reference without producing a
publication bundle or calling the site importer. Approve the configured author destinations for
exact-Git evidence and the referee destination for the historical post plus evidence, then set:

```yaml
daily_blog:
  shadow_evaluation:
    external_model_data_sharing: true
```

The default `false` value is a hard boundary: the evaluator makes no model call. After explicit
approval, run:

```bash
source source_me.sh && python3 automation/evaluate_daily_blog_shadow.py \
  --date 2026-08-23 \
  --reference ../vosslab-daily-blog/docs/blog/posts/2026-08-23.md
```

Use `--reuse-caches` after exact historical objects have been fetched when the comparison should
remain offline. Complete evaluations live at:

```text
out/vosslab/daily_blog_shadow/YYYY-MM-DD/SHADOW_ID/
```

Inspect `scorecard.json`, `generated_post.md`, `reference_post.md`, `evidence.json`,
`editorial_projection.json`, `candidates.json`, and `candidate_validation.json`. The scorecard
combines deterministic structure, provenance, and changelog-use measurements with a typed 1-5
semantic assessment of factual grounding, thematic structure, reader interest, and house-style
match. Shadow evaluation has a separate per-date lock and never changes `daily_blog/latest.json` or
publisher content.

The scorecard reports deterministic structure and provenance measurements alongside the semantic
scores. For the one-time August 22 and 23 cutover comparison, a human reviews the scorecard,
generated post, reference post, and cited evidence together. Record the approved shadow IDs in
[DAILY_BLOG_OWNERSHIP_CUTOVER.md](DAILY_BLOG_OWNERSHIP_CUTOVER.md) before enabling the timer.

## Verification classes

Permanent tests protect behavior intended to remain true across dates, prompt versions, and host
installations. One-time checks establish that this particular rebuild is ready to activate.

| Class | Owner | Success condition | Validation |
| --- | --- | --- | --- |
| Schema, prompt, candidate, bundle, and lock unit tests | Producer maintainer | Stable offline contracts pass in the pytest fast lane | `pytest tests/test_daily_blog_*.py` |
| Exact-Git evidence and mirror E2E | Producer maintainer | Temporary repositories preserve revision, boundary, and cache identity | Run `tests/e2e/e2e_daily_blog_evidence_git.py` and `e2e_daily_blog_mirror_refresh.py` |
| Complete producer-to-publisher E2E | Producer and publisher maintainers | A synthetic bundle imports into a temporary strict MkDocs site | Run `tests/e2e/e2e_daily_publication.py` |
| August 22-23 editorial comparison | Producer operator | Both immutable scorecards and posts receive human approval | Inspect each shadow directory and record its ID in the cutover record |
| Host ownership cutover | Producer operator | Old timers remain retired, the static server remains active, and one producer timer is installed | Inspect user units with `systemctl --user` |

Historical filenames staying absent, fixed August dates, and one host's installed-unit snapshot are
cutover evidence. They stay in the ownership record instead of becoming permanent tests.

## Scheduling

The producer supplies one user service and one timer:

- `deploy/vosslab-daily-publication.service`
- `deploy/vosslab-daily-publication.timer`

Install them into the user unit directory and reload user systemd:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/vosslab-daily-publication.service ~/.config/systemd/user/
cp deploy/vosslab-daily-publication.timer ~/.config/systemd/user/
systemctl --user daemon-reload
```

The timer starts at 02:00 America/Chicago. Its schedule command persists
`out/vosslab/daily_blog_schedule.json` and processes up to seven missing report dates oldest-first
through yesterday. It advances the cursor only after a matching publisher record exists, so an
import followed by a lost cursor write reconciles without duplicate generation. Only publication v2
records can satisfy reconciliation; a pre-cutover or malformed record stops the schedule rather than
advancing the cursor. Schedule v2 binds the completed date to the exact publisher bundle ID and
revalidates that receipt on every activation. A first invocation without a cursor starts with
yesterday rather than treating the historical archive as a backlog.

The `vosslab-daily-blog.service` static server remains independently enabled in the publisher
repository. On August 27, 2026, the operator explicitly activated the producer timer to restore
publication while the two historical quality comparisons remained pending:

```bash
systemctl --user enable --now vosslab-daily-publication.timer
```

At cutover, disable the prior Hermes publication cron, mirror timer, and editorial timer before
enabling the producer timer. Confirm the active schedule contains exactly one publication timer.
The historical comparisons remain useful quality evidence, but their pending state no longer
disables the current host schedule.

## Operator checks

```bash
systemctl --user status vosslab-daily-publication.timer
systemctl --user status vosslab-daily-publication.service
systemctl --user status vosslab-daily-blog.service
journalctl --user -u vosslab-daily-publication.service -n 100
journalctl --user -u vosslab-daily-publication.service -g 'daily_publication\.' -n 100
curl --fail http://aella.local:8016/blog/
curl --fail http://aella.local:8016/status/
```

If the expected date has no run directory, the failure occurred before orchestrator ownership. Check
the scheduler handoff before looking for `run_state.json`:

```bash
hermes cron list
systemctl --user list-timers --all
systemctl --user is-enabled vosslab-daily-publication.timer
systemctl --user is-active vosslab-daily-publication.timer
systemctl --user cat vosslab-daily-publication.service
```

The retired Hermes publication job must not exist or be active, and the systemd timer must be the
sole 02:00 publication owner. Compare the installed service with
`deploy/vosslab-daily-publication.service` when its command is stale.

## Failure and recovery

- A mirror refresh or exact-object failure ends the run before editorial generation.
- Author/referee route failures, prompt overflows, no valid candidates, and `NONE` verdicts fail the
  owned editorial phase with `EditorialBlockedError`. Later bundle and import phases remain pending.
- Bundle creation uses a staging directory and atomic promotion; an incomplete bundle never updates
  `latest.json`.
- The publisher validates and builds a complete proposed source tree before installing anything.
- A failed importer preserves the prior MkDocs source, publication record, immutable release, and
  served `site` pointer.
- Reimporting the exact bundle succeeds idempotently only when the immutable archive matches every
  input byte and `site` resolves to the expected release. Drift is reported rather than accepted as
  success. A different approved bundle cannot replace an existing publication for the same date
  without an explicit publisher contract change.

When a run directory exists, start recovery by reading the failed phase and message in
`run_state.json`, then compare the structured `events.jsonl` timeline. Structured lifecycle events
omit raw exception text, while ordinary service traceback lines can retain it. Correct the external
condition, then invoke the same date command again. The new run can reuse valid matching evidence
and approved editorial artifacts while retaining the failed run as an audit record. Blocked
editorial outcomes remain retryable. A reused bundle keeps its original immutable directory, and the
new run record identifies that origin explicitly. The next schedule activation reconciles a
successful manual import from its publisher record before advancing the cursor.

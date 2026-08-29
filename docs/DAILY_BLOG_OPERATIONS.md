# Daily blog operations

## Ownership

`vosslab-podcast` owns one date-owned publication workflow through local site import. It refreshes
repository caches, selects exact Git activity, assembles evidence, runs the editorial roles, writes
the publication for one `report_date`, and calls the importer in `vosslab-daily-blog`.

`vosslab-daily-blog` owns MkDocs source, validation, the current built release for each report date,
the served `site` pointer, and the static service on port 8016.

`report_date` is the sole publication identity. The producer and publisher use `bundle_sha256` only
to verify the integrity of the manifest that currently serves that date.

## Manual publication

Run yesterday in the configured report timezone or one explicit calendar date
from the producer repository:

```bash
cd /home/vosslab/nsh/vosslab-podcast
./make_blog.py --yesterday
./make_blog.py --date 2026-21-08
```

The explicit example selects August 21, 2026. `make_blog.py` canonicalizes it
to `2026-08-21` before any receipt lookup, mirror refresh, or model work. It
prefers `YYYY-MM-DD`, accepts unambiguous `YYYY-DD-MM`, requires exactly one
selector, and relaunches through the physical repository-local Python 3.12
environment without a shell. `automation/publish_daily_blog.py` remains the
shared explicit-date implementation behind this root command.

A successful command reports the publication path and imports the post. Before mirror refresh or
model execution, the command validates the publisher-owned receipt and every declared artifact for
that date. An interactive terminal asks `Overwrite YYYY-MM-DD? [N/y]:` when the date is occupied.
Enter `y` to generate and commit a replacement for the same date; the default preserves a coherent
current publication. A noninteractive invocation preserves a coherent existing date and exits
successfully. An occupied legacy or damaged date fails closed without model work until an interactive
operator confirms replacement. If authoring, validation, prompt rendering, or referee approval is
blocked for an unpublished date, the command raises `EditorialBlockedError` and creates or imports no
publication.

## Configuration

The `daily_blog` section of `settings.yaml` defines:

- `repository_path`: local `vosslab-daily-blog` checkout.
- `mirror_cache_root`: base directory for owner-qualified physical Git worktrees.
- `report_timezone`: IANA timezone used for report-day boundaries.
- `identity_names` and `identity_emails`: exact author attribution evidence.
- `routes.authors`: exactly two isolated author command routes.
- `routes.referee`: a separately named referee command route.
- `collection_limits`: per-source, per-item, total supporting, and screenshot limits applied while
  retaining the authoritative evidence packet.
- `projection_limits`: complete rendered context, exact excerpt, and repository-card subject limits.
- `prompt_limits`: complete author and referee envelopes after templates, rubric, candidates, and
  projection context are rendered.
- `shadow_evaluation.external_model_data_sharing`: opt-in for optional external-route corroboration
  only; it defaults to `false`. The mandatory fixture-backed F4 path never changes it or sends model
  egress. Manual and systemd publication send current editorial context only through their configured
  author and referee routes.

Role commands receive the complete prompt through standard input. The checked-in Hermes routes use
`--query-file -`, `--ignore-rules`, and `--quiet`; repository templates therefore own the full
editorial instruction contract, while programmatic stdout contains only the final model response and
the active profile retains only its configured model/provider route. Configuration rejects profile
skills, inline queries, and resumed sessions for Hermes roles.

Final candidates pass active v4-maker policy v3
(`3a4b7148579e509b6c32fa19b31d107dc4278eb5f721b2a01353a1a9a51264ee`): 300-2500 narrative words,
zero to 12 narrative H2 sections, up to three uncited narrative prose blocks, compact projected-
repository coverage, and a direct canonical link at the first narrative repository use. Front matter
binds the post to `editorial_projection`, and generic date-derived Work log titles are invalid. The
referee judges the semantic qualities that deterministic code cannot prove, including thematic focus,
reader interest, and cross-project synthesis. Its winner, evidence-quality label, and confidence
remain strict control fields; an overlong explanatory reason is bounded to operational metadata.
The author template's exact `thematic-lowercase-slug` sentinel is resolved mechanically from the
single thematic H1 before candidate hashing and validation; unresolved sentinels remain invalid at
both the producer and publisher boundaries.

The active contract is v4-maker policy v3. It selects `v4-three-examples-corpus-v2` through
activation `daily-blog-maker-activation-6b104be9c6907eeeffcf330f6b10173857b39c6b05baa46d4cf009a67daa7547`.
Its immutable validation policy binds the prompt snapshot, opaque generator identity, bundle, and
reuse identity. The publisher independently
recomputes and enforces the active contract at import. Policy versions 1 and 2 are rejected; bundle
v5 is the production publisher boundary.

## Cache checks

Physical Git caches live below `/home/vosslab/repo-mirrors/OWNER/REPOSITORY`. Each cache has an
owner-qualified lock below `.locks/`. A fresh GitHub owner roster defines the exact eligible scope;
the refresh manifest records canonical URLs, creation time, fork state, roster identity, result,
default revision, exact-object availability, ref fingerprint, error, and timestamp.

The manager clones a newly rostered repository once, then subsequent manual and scheduled runs
share the same lock and worktree. A stale or unrostered cache never expands publication scope.

## Inspecting a run

For a reported `RUN_ID`, inspect the diagnostic record for that attempt:

```text
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/run_state.json
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/events.jsonl
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/repository_roster.json
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/mirror_manifest.json
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/activity.json
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/evidence.json
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/editorial_projection.json
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/candidate_validation.json
out/vosslab/daily_blog_runs/YYYY-MM-DD/RUN_ID/referee.json
```

Before mirror work, production writes and reload-verifies the matching immutable roster snapshot at
`out/vosslab/daily_blog_repository_rosters/ROSTER_ID/`. The run state binds that snapshot's absolute
path and full identity alongside the per-run sealed roster artifact.

The authoritative run v4 state has ten ordered phases:

1. `repository_discovery`
2. `mirror_refresh`
3. `activity_location`
4. `evidence_assembly`
5. `editorial_projection`
6. `author_generation`
7. `candidate_validation`
8. `referee_selection`
9. `bundle_creation`
10. `site_import`

Every phase records its input and output hash. A run directory identifies an attempt, while
`report_date` identifies the current publication. Hash-verified cache envelopes can reuse exact
activity, evidence, projection, fully valid candidate artifacts, and approved referee decisions.
Blocked editorial attempts run again on the next invocation. A coherent existing publication returns
during preflight unless an interactive operator confirms replacement.

## Inspecting a bundle

Complete bundles live at:

```text
out/vosslab/daily_blog/YYYY-MM-DD/publication/
```

Inspect `bundle.json`, `evidence.json`, `editorial_projection.json`, and `post.md`. The
`bundle_sha256` in the manifest verifies these files; it does not name the publication. The bundle
binds the selected post and referee record to the same projection ID. Asset hashes and Git blob
identities appear in the manifest and evidence packet.

## Historical shadow evaluation

Run the current evidence and editorial contracts against a preserved reference without producing a
publication bundle or calling the site importer. The default `false` value is a hard boundary: the
evaluator makes no model call. This optional external-route corroboration is outside F0-F7 and does
not affect fixture-backed acceptance, activation, or publication. Use `--reuse-caches` after exact
historical objects have been fetched when an offline comparison is useful. Complete evaluations live at:

```text
out/vosslab/daily_blog_shadow/YYYY-MM-DD/SHADOW_ID/
```

Inspect `scorecard.json`, `generated_post.md`, `reference_post.md`, `evidence.json`,
`editorial_projection.json`, `candidates.json`, and `candidate_validation.json`. The scorecard
combines deterministic structure, provenance, and changelog-use measurements with a typed 1-5
semantic assessment of factual grounding, thematic structure, reader interest, and house-style
match. Shadow evaluation has a separate per-date lock and leaves publisher content unchanged.

The scorecard reports deterministic structure and provenance measurements alongside the semantic
scores. For an optional historical comparison, inspect the scorecard, generated post, reference
post, and cited evidence together. Shadow results measure editorial behavior without changing the
publisher; they are not an activation gate.

## Verification classes

Permanent tests protect behavior intended to remain true across dates, prompt versions, and host
installations. One-time checks establish that this particular rebuild is ready to activate.

| Class | Owner | Success condition | Validation |
| --- | --- | --- | --- |
| Schema, prompt, candidate, bundle, and lock unit tests | Producer maintainer | Stable offline contracts pass in the pytest fast lane | `pytest tests/test_daily_blog_*.py` |
| Exact-Git evidence and mirror E2E | Producer maintainer | Temporary repositories preserve revision, boundary, and cache identity | Run `tests/e2e/e2e_daily_blog_evidence_git.py` and `e2e_daily_blog_mirror_refresh.py` |
| Complete producer-to-publisher E2E | Producer and publisher maintainers | A synthetic bundle imports into a temporary strict MkDocs site | Run `tests/e2e/e2e_daily_publication.py` |
| Historical editorial comparison | Producer operator | Optional scorecards preserve reproducible quality evidence | Inspect each shadow directory without changing publication state |
| Host ownership cutover | Producer operator | Old timers remain retired, the static server remains active, and one producer timer is installed | Inspect user units with `systemctl --user` |

Historical filenames staying absent, fixed August dates, and one host's installed-unit snapshot are
cutover evidence. They stay in the ownership record instead of becoming permanent tests.

## Maker evidence

Fixture-backed F4 evidence accepted the v4 contract, and F5 activated it through the producer/
publisher boundary. [prompt experiment status](active_plans/reports/prompt_experiment_status.md)
records the sealed capture, attestation, and artifact-only reviews. This historical evidence does not
need repetition to publish a later date.

The accepted workflow used independent fixture-backed evidence stages followed by a route-free join:

1. Stage 1 creates a sealed experiment capture from the approved busy and quiet fixtures. It uses
   deterministic author and referee role fakes through the existing strict interfaces, but has no
   calibration input or calibration dependency.
2. Historical calibration independently scores the fixed historical posts with deterministic referee
   evidence: Aug. 22-23 are positive voice references, Aug. 24-25 are voice failures, and Aug. 26
   is an evidence/discovery failure.
3. Stage 2 deterministically attests the sealed Stage 1 capture against one passing calibration
   artifact. It invokes no model route and recomputes acceptance from the immutable inputs.

Capture permits only quiet `2026-08-23` and busy `2026-08-26`; consumer execution is narrower. It
accepts only quiet fixture `4adcb80db0cdde222fbc6a7a53ec008d1198d0cc03f9cecc16c12ddbca24522e`,
busy fixture `04fd7a045538662e5c6b48ad79e08dd608de1b5a10c1c8857c7b12042bad41da`, and shared roster
`0f79bcfea4d3fb783258df4a37effef5996b6fdb9736ff6944fd17051570b8a1`. A replacement fixture needs
reviewed consumer-allowlist rotation before a route can use it.

Use the repository environment for the permanent offline prompt and artifact-contract checks:

```bash
source source_me.sh && python3 -m pytest \
  tests/test_daily_blog_prompt_resources.py \
  tests/test_daily_blog_prompt_experiment.py \
  tests/test_daily_blog_rubric_calibration.py \
  tests/test_daily_blog_experiment_attestation.py \
  tests/test_daily_blog_voice_metrics.py
```

`source_me.sh` requires the physical repository-local Python 3.12 environment and currently
selects Python 3.12.13. These offline tests establish durable contract regression evidence. Fixture
capture itself is a one-time evidence operation and has no model or calibration input:

```bash
mkdir -p out/vosslab/daily_blog_experiment_fixtures_v2
source source_me.sh && python3 automation/capture_daily_blog_experiment_fixture.py \
  --date 2026-08-23 \
  --fixture-root /home/vosslab/nsh/vosslab-podcast/out/vosslab/daily_blog_experiment_fixtures_v2 \
  --repository-roster-snapshot /absolute/path/to/verified-roster-snapshot
```

Prepare the fixed historical rubric inputs without a route with:

```bash
source source_me.sh && python3 automation/calibrate_daily_blog_rubric.py --prepare-only
```

Historical calibration was a fixture-backed evidence operation. The F4 harness provides deterministic
referee output through the same strict parsing and immutable-artifact boundaries as the configured
route, writing a private `rubric-calibration-*` directory below
`out/<user>/daily_blog_rubric_calibrations/`. When it reports `pass`, retain that artifact as the
later Stage 2 input. Repetitions, score-span tolerance, and separation threshold are configurable
one-time procedure values. A passing calibration does not run an experiment, select an arm, activate
v4, or publish. A live external calibration remains optional corroboration with redacted diagnostics.

### Stage 1: sealed project-evidence capture

This was a mandatory fixture-backed acceptance run, not a permanent E2E. The F4 harness supplied
deterministic author and referee role fakes through the existing strict Hermes-facing author and
referee interfaces. It needs no model egress or approval. The current experiment CLI does not yet
expose that harness configuration, so its ordinary route-mode command is not an F4 instruction. The
manager runs the implemented harness with the reviewed physical absolute fixture paths.

Stage 1 writes its sealed immutable capture below `out/<user>/daily_blog_experiments/`. It leaves
publication, importer, systemd, and v4 activation unchanged. Do not add `--calibration`: the
executable command deliberately has no such option.

### Stage 2: deterministic attestation

The accepted capture and calibration were joined through this deterministic, route-free attestation
command:
deterministic, route-free attestation command:

```bash
source source_me.sh && python3 automation/attest_daily_blog_prompt_experiment.py \
  --capture /absolute/path/to/prompt-experiment-CAPTURE_ID \
  --calibration /absolute/path/to/rubric-calibration-CALIBRATION_ID \
  --reviewer-count 2
```

Stage 2 writes an immutable attestation under `out/<user>/daily_blog_experiment_attestations/`. It
loads and verifies the capture and calibration, recomputes the acceptance result, and does not load
or invoke a model route. A `review_ready: true` attestation embeds the exact independent-review
contract; it is not activation readiness. The configured independent reviewers must work only from
the sealed artifacts, load the two descriptor-verified complete posts through
`daily_blog.experiment_attestation.load_review_posts`, and cite exact passages for every maker
dimension. The contract binds the first authority-ordered sample for each fixture without consulting
score or comparison outcomes; later samples remain diagnostic. Every review required by the artifact
accepted both fixtures before F4 completed. The shown reviewer count is one-time evidence, not a
permanent requirement. The separately reviewed producer-publisher activation is accepted.

### Private roots and exit semantics

All experiment artifacts are configuration-owned private paths. Use physical absolute paths when
one stage references another; do not copy artifacts into publication roots.

| Command | Private output root | Exit 0 | Exit 1 | Exit 2 |
| --- | --- | --- | --- | --- |
| Fixture capture | `out/<user>/daily_blog_experiment_fixtures_v2/` | Validated or installed fixture | Not used | Invalid or unsafe input; no fixture written |
| Stage 1 experiment | `out/<user>/daily_blog_experiments/` | Complete sealed capture | Complete capture with failed records or comparisons | Blocked fixture, route, configuration, or artifact contract |
| Historical calibration | `out/<user>/daily_blog_rubric_calibrations/` | Passing fixture-backed score evidence | Complete non-passing score evidence | Invalid fixture-harness input or artifact contract |
| Stage 2 attestation | `out/<user>/daily_blog_experiment_attestations/` | Immutable attestation is ready for independent review | Immutable attestation records non-ready acceptance | Invalid or unverifiable source artifact; no usable attestation |

The required experiment uses deterministic role fakes and runs without an external route. A live
Hermes experiment may later corroborate the sealed fixture result, but it cannot block F4-F7. Keep
command arguments, credentials, and private artifact paths out of logs and documentation.

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

The timer runs at 04:00 America/Chicago and directly executes
`./make_blog.py --yesterday`. Systemd owns this schedule and service lifecycle. Each activation
selects one completed report date, holds that date's publication lock for the whole run, and leaves
an existing coherent date in place with a successful exit. This design needs no cursor, backlog,
or catch-up state: an operator can select any specific date with `make_blog.py --date`.

Fresh GitHub discovery is authenticated through the runtime `GITHUB_TOKEN` contract. An explicit
process value wins; otherwise the collector reads only that entry from `$HERMES_HOME/.env`. The
checked-in service declares the Hermes home and never imports the complete dotenv file, so unrelated
Hermes credentials do not enter the publication process.

The `vosslab-daily-blog.service` static server remains independently enabled in the publisher
repository. Enable the producer timer after copying the checked-in units:

```bash
systemctl --user enable --now vosslab-daily-publication.timer
```

Confirm the active schedule contains the one producer publication timer. Hermes owns configured
model/provider execution inside a run; it does not own scheduling or a second publication loop.

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

If the expected date has no run directory, inspect the user service and timer before looking for
`run_state.json`:

```bash
systemctl --user list-timers --all
systemctl --user is-enabled vosslab-daily-publication.timer
systemctl --user is-active vosslab-daily-publication.timer
systemctl --user cat vosslab-daily-publication.service
```

The systemd timer is the sole 04:00 publication owner. Compare the installed service with
`deploy/vosslab-daily-publication.service` to verify that it directly runs
`./make_blog.py --yesterday`.

## Failure and recovery

- A mirror refresh or exact-object failure ends the run before editorial generation.
- Author/referee route failures, prompt overflows, no valid candidates, and `NONE` verdicts fail the
  owned editorial phase with `EditorialBlockedError`. Later bundle and import phases remain pending.
- Bundle creation uses a staging directory and a kernel directory exchange, so
  `out/<user>/daily_blog/YYYY-MM-DD/publication/` always names one complete revision.
- The publisher validates and builds a complete proposed source tree before installing anything.
- A failed importer restores the prior MkDocs source, publication record, date-owned release, and
  served `site` pointer.
- A confirmed interactive replacement builds a complete new publication before changing stable paths.
  The publisher exchanges each date-owned directory without hiding its stable name, switches `site`
  with one file replacement, and writes the verified publication record last as the transaction's
  authoritative commit marker.

When a run directory exists, start recovery by reading the failed phase and message in
`run_state.json`, then compare the structured `events.jsonl` timeline. Structured lifecycle events
omit raw exception text, while ordinary service traceback lines can retain it. Correct the external
condition, then invoke the same date command again. The new run can reuse valid matching evidence
and approved editorial artifacts while retaining the failed run as an audit record. Blocked
editorial outcomes remain retryable. A confirmed replacement updates the one current publication
directory for that date after the complete producer and publisher transaction succeeds.

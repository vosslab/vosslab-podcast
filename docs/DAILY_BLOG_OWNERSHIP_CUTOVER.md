# Daily blog ownership cutover

## Final decision

`vosslab-podcast` owns the complete date-driven producer: durable Git mirrors, exact-object
activity, authority-ranked evidence, two isolated author routes, deterministic candidate
validation, anonymous referee selection, immutable bundle creation, typed run state, and the one
publication schedule.

`vosslab-daily-blog` owns the complete local publisher: bundle and provenance validation, MkDocs
source, publication records, strict staged builds, immutable releases, atomic installation, the
served release pointer, and the static service on port 8016.

The current v2 publication bundle is the only interface between the repositories. It requires
evidence v3, projection v1, generator v2, and the `daily-blog-prompts-v3` plus
`daily-blog-rubric-v3` editorial contracts. No collector, mirror, generator, model execution,
layered editorial state, or publication timer remains in the publisher.

## Retired design

The producer's M2/M3/M4 `daily_github_*` commands, private static site, v1 editorial templates, and
active revival plan are retired. The publisher's GitHub collector, layered editor, split
collection/canonical/editorial state, wrapper scripts, and editorial timer are retired. Historical
posts and evidence records remain unchanged as audit material.

Host service changes are explicit operator actions. A fresh or recovered cutover first disables the
former Hermes cron, mirror timer, and publisher editorial timer, then verifies that exactly one
publication timer remains alongside `vosslab-daily-blog.service`.

## Acceptance record

- The same explicit-date producer command supports manual and scheduled runs. Timer activation is
  an operator action after the one-time historical review is recorded.
- Exact Git and dated changelogs anchor evidence before model execution.
- Two author routes and one referee route receive repository-owned, versioned prompts through
  isolated standard-input sessions.
- Measurable August house-style requirements are deterministic final-candidate gates.
- Missing editorial approval blocks bundle creation and publisher import while preserving the
  failed producer run for retry.
- The publisher installs only a fully validated, strictly built proposal and preserves its last
  good source and served release across failure.
- Non-publishing historical evaluation has a default-deny model data-sharing boundary and a
  separate immutable output namespace.

## Host schedule record

On 2026-08-26, the installed mirror and editorial timers were stopped and disabled. Their four unit
files were moved to the recoverable
`~/.config/systemd/user/retired-daily-blog-20260826/` archive. The single producer service and timer
were installed, and the static `vosslab-daily-blog.service` remained active.

On 2026-08-27, the producer timer was disabled and left inactive while the August 22 and 23
historical comparisons await explicit model-data-sharing approval and human review. The transient
fixed-date `ExecCondition` was removed from the service: it was cutover scaffolding rather than a
durable publishing contract. Enable the installed timer only after both approved shadow IDs and the
review outcome are added to this record.

Later on 2026-08-27, the operator explicitly directed the repair path to work immediately and asked
for the missing August 26 run. That instruction superseded the temporary activation gate while the
historical comparisons remained pending quality evidence. The former Hermes cron was paused, the
producer timer was enabled, and its persistent activation imported a legacy v1 fallback bundle
`0fa0c52859c243890857c9e85f63c6f370e649739f47cda1ab6466f9cb49c8a6` from run
`20260827T151213Z-ea25b1e79b`. The follow-up audit removed the obsolete Hermes cron job, archived its
four deleted-path wrappers under `~/.hermes/retired-daily-blog-20260827/`, and replaced one-date
timer catch-up with a durable, bounded, oldest-first cursor so a multi-day outage cannot silently
skip older report dates.

## One-time verification record

| Check | Status | Evidence |
| --- | --- | --- |
| August 22 exact-object preflight | Complete | Four active repositories, 23 typed evidence items, and 10 assets |
| August 23 exact-object preflight | Complete | Four active repositories, 25 typed evidence items, and 10 assets |
| Reference structure profile | Complete | Both posts use first person, four narrative H2s, compact openings, Project coverage, and 613/636 narrative words |
| Synthetic producer-to-publisher flow | Complete | `tests/e2e/e2e_daily_publication.py` passed through strict MkDocs staging on 2026-08-27 |
| August 22 semantic shadow | Pending quality review | Shadow ID and human decision remain to be recorded |
| August 23 semantic shadow | Pending quality review | Shadow ID and human decision remain to be recorded |
| August 26 repaired publication | Complete | Run `20260827T151213Z-ea25b1e79b`; legacy v1 fallback bundle `0fa0c52859c2` imported |

These are cutover facts rather than permanent regression cases. The permanent suite covers the
general contracts that produced them.

## Current references

- `README.md`
- `docs/CODE_ARCHITECTURE.md`
- `docs/DAILY_BLOG_OPERATIONS.md`
- `docs/FILE_STRUCTURE.md`
- `docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md`

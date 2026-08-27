# Daily blog ownership cutover

## Final decision

`vosslab-podcast` owns the complete date-driven producer: durable Git mirrors, exact-object
activity, authority-ranked evidence, two isolated author routes, deterministic candidate
validation, anonymous referee selection, immutable bundle creation, typed run state, and the one
publication schedule.

`vosslab-daily-blog` owns the complete local publisher: bundle and provenance validation, MkDocs
source, publication records, strict staged builds, immutable releases, atomic installation, the
served release pointer, and the static service on port 8016.

The current v1 publication bundle is the only interface between the repositories. It requires the
`daily-blog-prompts-v2` and `daily-blog-rubric-v2` editorial contracts. No collector, mirror,
generator, model execution, layered editorial state, or publication timer remains in the publisher.

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
- Complete evidence can produce a deterministic provisional bundle when editorial approval is
  unavailable.
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

## One-time verification record

| Check | Status | Evidence |
| --- | --- | --- |
| August 22 exact-object preflight | Complete | Four active repositories, 23 typed evidence items, and 10 assets |
| August 23 exact-object preflight | Complete | Four active repositories, 25 typed evidence items, and 10 assets |
| Reference structure profile | Complete | Both posts use first person, four narrative H2s, compact openings, Project coverage, and 613/636 narrative words |
| Synthetic producer-to-publisher flow | Complete | `tests/e2e/e2e_daily_publication.py` passed through strict MkDocs staging on 2026-08-27 |
| August 22 semantic shadow | Pending approval | Shadow ID and human decision remain to be recorded |
| August 23 semantic shadow | Pending approval | Shadow ID and human decision remain to be recorded |

These are cutover facts rather than permanent regression cases. The permanent suite covers the
general contracts that produced them.

## Current references

- `README.md`
- `docs/CODE_ARCHITECTURE.md`
- `docs/DAILY_BLOG_OPERATIONS.md`
- `docs/FILE_STRUCTURE.md`
- `docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md`

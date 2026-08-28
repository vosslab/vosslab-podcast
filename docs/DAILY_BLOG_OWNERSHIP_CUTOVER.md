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

- The same explicit-date producer command supports manual and scheduled runs. It validates a coherent
  publisher receipt before generation, so retrying an immutable published date returns its exact bundle
  without spending model work or producing a competing publication. Timer activation is an operator
  action after the current producer-to-publisher contracts pass live verification.
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

On 2026-08-27, the producer timer was temporarily disabled while the August 22 and 23 historical
comparisons were considered. That gate was retired as pre-production scaffolding: historical shadow
comparisons are optional editorial benchmarks, not prerequisites for an operationally correct
publication system. The transient fixed-date `ExecCondition` was removed from the service.

Later on 2026-08-27, the operator explicitly directed the repair path to work immediately and asked
for the missing August 26 run. The follow-up audit removed the obsolete Hermes cron job, archived its
four deleted-path wrappers under `~/.hermes/retired-daily-blog-20260827/`, and replaced one-date
timer catch-up with a durable, bounded, oldest-first cursor so a multi-day outage cannot silently
skip older report dates. The clean pre-production cutover then removed the superseded fallback
transaction and imported the final-only v2 publication described below.

## One-time verification record

| Check | Status | Evidence |
| --- | --- | --- |
| August 22 exact-object preflight | Complete | Four active repositories, 23 typed evidence items, and 10 assets |
| August 23 exact-object preflight | Complete | Four active repositories, 25 typed evidence items, and 10 assets |
| Reference structure profile | Complete | Both posts use first person, four narrative H2s, compact openings, Project coverage, and 613/636 narrative words |
| Synthetic producer-to-publisher flow | Complete | `tests/e2e/e2e_daily_publication.py` passed through strict MkDocs staging on 2026-08-27 |
| August 22 semantic shadow | Optional benchmark | Non-publishing comparison remains available but is not a cutover gate |
| August 23 semantic shadow | Optional benchmark | Non-publishing comparison remains available but is not a cutover gate |
| August 26 repaired publication | Complete | Run `20260828T003950Z-bdee87fdc1`; v2 bundle `d6d06817bec1`; "Making the Interface Tell the Truth" served at its thematic route |

These are cutover facts rather than permanent regression cases. The permanent suite covers the
general contracts that produced them.

## Current references

- `README.md`
- `docs/CODE_ARCHITECTURE.md`
- `docs/DAILY_BLOG_OPERATIONS.md`
- `docs/FILE_STRUCTURE.md`
- `docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md`

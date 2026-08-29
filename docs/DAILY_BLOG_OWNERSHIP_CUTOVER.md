# Daily blog ownership cutover

## Final decision

`vosslab-podcast` owns the complete date-driven producer: durable Git mirrors, exact-object
activity, authority-ranked evidence, deterministic candidate validation, anonymous referee
selection, validated bundle creation, and typed run state. Hermes owns only the configured author
and referee model-route executions inside a producer run. The checked-in systemd timer owns the
one publication schedule and directly calls `./make_blog.py --yesterday`.

`vosslab-daily-blog` owns the complete local publisher: bundle and provenance validation, MkDocs
source, date-owned publication records and content releases, strict staged builds, atomic
installation, the served release pointer, and the static service on port 8016.

The active v4-maker bundle v5 is the production interface between the repositories. It
requires the active evidence, projection, run, generator, prompt, and rubric contracts that the
publisher independently validates. The producer starts from an immutable authoritative roster,
then persists owner-qualified mirror and lifecycle provenance for the publisher to validate. No
collector, mirror, generator, model execution, layered editorial state, or publication timer
remains in the publisher.

The accepted maker activation selects `v4-three-examples-corpus-v2` for the production orchestrator,
bundle writer, publisher importer, and systemd schedule.

## Retired design

The producer's M2/M3/M4 `daily_github_*` commands, private static site, v1 editorial templates, and
active revival plan are retired. The publisher's GitHub collector, layered editor, split
collection/canonical/editorial state, wrapper scripts, and editorial timer are retired. Historical
posts and evidence records remain unchanged as audit material.

Host service changes are explicit operator actions. A fresh or recovered cutover first disables the
former Hermes cron, mirror timer, and publisher editorial timer, then verifies that exactly one
publication timer remains alongside `vosslab-daily-blog.service`.

## Acceptance record

- The root `make_blog.py` command supports manual and scheduled runs. It validates a coherent
  publisher receipt before generation. An interactive command asks before replacement, while the
  non-interactive systemd run preserves existing content and exits successfully. Timer activation
  is an operator action after the current producer-to-publisher contracts pass live verification.
- Exact Git and dated changelogs anchor evidence before model execution.
- Hermes runs exactly two configured author routes and one configured anonymous-referee route
  through isolated standard-input sessions. It owns no schedule, publication loop, importer, or
  producer state.
- Measurable August house-style requirements are deterministic final-candidate gates.
- Missing editorial approval blocks bundle creation and publisher import while preserving the
  failed producer run for retry.
- The publisher installs only a fully validated, strictly built proposal and preserves its last
  good source and served release across failure.
- The maker experiment has the activation gates below. Its private artifacts use a separate
  content-addressed namespace and cannot publish.

## Maker-quality activation evidence

F4 accepted fixture-backed capture, calibration, attestation, and independent artifact review before
the separately reviewed producer/publisher cutover. The evidence stages have distinct owners and
side effects so a model-route result cannot silently become a publication decision.

### Stage 1: accepted fixture-backed capture and calibration

The producer owns the sealed busy-and-quiet experiment capture. It is private and non-publishing:
it writes only the configured experiment-artifact namespace, creates no bundle, calls no publisher
importer, and does not alter the systemd schedule. The accepted harness used deterministic author
and referee role fakes through the existing strict route boundary.

Historical rubric calibration is a separate private fixture-backed artifact. Live routes are optional
corroboration only. The experiment capture does not accept a `--calibration` argument: calibration
joins the capture only in Stage 2.

The fixture-backed capture, calibration, winning arm, and v4 activation are accepted.

### Stage 2: deterministic route-free attestation

The producer's attestation command joins one sealed private capture with one passing fixture-backed
historical-calibration artifact. It recomputes the acceptance result without loading or invoking a
model route. It writes a private attestation only; it neither activates v4 nor creates a bundle,
imports a post, publishes the site, or changes systemd.

### Accepted v4 production cutover

The accepted review evidence advanced the producer and publisher together to v4-maker policy v3 and
bundle v5. `make_blog.py` and its systemd schedule now use that active contract. The attestation
remains evidence for the recorded activation, not a substitute for it.

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

On 2026-08-28, the pre-production design made `report_date` the sole publication identity and
retired the cursor/backlog scheduler. The systemd timer now calls `./make_blog.py --yesterday`
directly at 04:00 America/Chicago. Hermes remains only the author/referee model runner inside that
date-owned deterministic pipeline.

## One-time verification record

| Check | Status | Evidence |
| --- | --- | --- |
| August 22 exact-object preflight | Complete | Four active repositories, 23 typed evidence items, and 10 assets |
| August 23 exact-object preflight | Complete | Four active repositories, 25 typed evidence items, and 10 assets |
| Reference structure profile | Complete | Both posts use first person, four narrative H2s, compact openings, Project coverage, and 613/636 narrative words |
| Synthetic producer-to-publisher flow | Complete | `tests/e2e/e2e_daily_publication.py` passed through strict MkDocs staging on 2026-08-27 |
| August 22 semantic shadow | Optional benchmark | Non-publishing comparison remains available but is not a cutover gate |
| August 23 semantic shadow | Optional benchmark | Non-publishing comparison remains available but is not a cutover gate |
| V4 live capture, calibration, winner, and activation | Not started | No live capture, approved historical calibration, arm winner, or activation decision exists |
| August 26 repaired publication | Complete | Run `20260828T003950Z-bdee87fdc1`; migrated checksum `d6d06817bec1`; "Making the Interface Tell the Truth" served at its thematic route |

These are cutover facts rather than permanent regression cases. The permanent suite covers the
general contracts that produced them.

## Current references

- `README.md`
- `docs/CODE_ARCHITECTURE.md`
- `docs/DAILY_BLOG_OPERATIONS.md`
- `docs/FILE_STRUCTURE.md`
- `docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md`

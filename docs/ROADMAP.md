# Roadmap

This roadmap records the completed daily-blog rebuild and its ongoing maintenance. It is a guide
to priorities, not a release schedule. The authoritative execution record is
[daily_blog_rebuild.md](active_plans/active/daily_blog_rebuild.md).

## Current baseline

- M1 through M16 are accepted. They establish a nine-stage, evidence-grounded editorial route
  with independent candidates, eligibility, review and promotion, incumbent preservation, and a
  bounded recovery ladder.
- The production prompt contract remains `v4-three-examples-corpus-v2`. Its maker brief and prompt
  prose are human-owned and unchanged. The registry mechanically resolves the active contract and
  its immutable resources.
- Publication is date-owned: `report_date` is the sole publication identity. A sealed
  `vosslab.daily-blog.bundle.v7` carries the selected eligible artifact into the publisher, whose
  durable publication record is `publication-v4`.
- Five self-generated, no-egress fixture cases already prove evidence-to-page integrity across
  quiet, busy, single-repository, screenshot-bearing, and degraded-dependency conditions. The
  durable validation record preserves the evidence and temporary-harness disposition.
- M15 completed the direct-route migration: the publication-contract/storage boundary owns the
  sealed bundle v7 handoff, `prompt_registry.py` owns immutable prompt identities, retired
  experiment and calibration routes are removed, and typed incumbent transitions make
  replacement authority durable and source-derived. Its one aggregate E2E run passed 7/7. Its
  one full-suite run is recorded truthfully as 3513 passed, 1 failed; the sole typed-transition
  defect was then closed by the affected durable test and typing guard, which passed 206 tests.
- M16 closed the operational record and archived superseded planning material while preserving the
  human-owned [BLOG_CONTRACT.md](BLOG_CONTRACT.md). The independent final review passed all 64
  Markdown-link tests, verified the archive and protected-contract digest, and found a clean diff
  check.
- M16 also completed a fixed-clock, no-egress public-command proof for
  `report_date=2026-08-28`: two successful `make_blog.py --yesterday` invocations demonstrated
  automatic same-date replacement and agreed on the terminal summary, sealed v7 bundle,
  publication record, and rendered page identity and digests. This is fixture-backed integrity
  evidence, not a live-model or prose-quality claim. A live model or network route remains
  optional non-gating corroboration, not daily-blog backlog work.

## Ongoing maintenance

- Keep `report_date` as the only publication identity and let the newest confirmed date-owned run
  replace the prior generated result.
- Preserve evidence grounding and mechanically verifiable provenance at every publication boundary.
- Treat editorial degradation separately from configuration, identity, path-safety, cache, and
  implementation faults; only the latter are pipeline faults.
- Revise prompts only through explicit human approval of exact prose. Future prompt work uses the
  local prompt-engineering corpus and records a new immutable identity.

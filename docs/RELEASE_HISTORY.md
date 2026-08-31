# Release history

## v26.08 - 2026-08-28

### Highlights

- Rebuilt the daily-blog production contract around immutable evidence, editorial projection,
  candidate validation, and a date-owned publication boundary.
- This release introduced the producer/publisher bundle v5 interface. Later bundle contracts carry
  the validated selected post and sealed artifact identity. The current bundle-v9 contract adds an
  immutable, survivor-scoped `publication_surface.json`: Stage 6, bundle construction, import,
  asset staging, and rendered-page verification derive evidence and image scope from the same
  authority. The publisher records the surface identity in a publication-v6 receipt. `report_date`
  remains the sole publication identity; `bundle_sha256` verifies manifest integrity without
  creating a second namespace.
- Added a two-stage, non-publishing v4 maker-voice evidence boundary. Fresh capture seals the
  approved Aug. 23 and Aug. 26 experiment evidence; a separate calibration artifact scores the
  historical Aug. 22-26 posts; deterministic attestation recomputes their joint acceptance result.
  The accepted activation selects `v4-three-examples-corpus-v2`.
- Separated collection, projection, and prompt envelopes so author and referee inputs are bounded,
  reproducible, and tied to immutable snapshots.
- Made the systemd user timer the sole 04:00 America/Chicago publication owner. It runs
  `./make_blog.py --yesterday` through the same date-owned publication path as the manual command.
- Added explicit manual replacement behavior: an interactive command asks before replacing an
  existing date, while a noninteractive command preserves the coherent existing publication.
- Added fresh fail-closed GitHub owner-roster discovery, owner-qualified mirrors, typed repository
  creation evidence, and story-first first-day salience for newly created source repositories.

### Notable fixes

- Aligned producer and publisher handling of Project coverage headings and retained the compact v4
  coverage boundary.
- Fixed the producer/publisher authority seam that could give Stage 6 a survivor-scoped image set
  while the importer admitted the aggregate packet's image set. The sealed portable surface now
  carries the exact selected evidence and assets across that boundary.
- Made model-result cache identity semantic: selected commits, evidence, and editorial request
  control reuse, while mutable default-branch and mirror-location inventory no longer discard
  otherwise valid cached work.
- Strengthened existing-date checks so a coherent publication is preserved unless an interactive
  operator explicitly confirms replacement, while `bundle_sha256` detects manifest tampering.
- Moved one-time Git and lifecycle proofs out of the fast pytest lane into direct E2E programs.
  Permanent tests retain stable evidence, schema, validation, reuse, idempotency, and importer
  boundaries without relying on network, host, or tuned-prompt behavior.
- Added no-follow private-artifact and roster verification so a replaced pathname or symbolic link
  cannot redirect capture, calibration, or attestation reads.

### Compatibility notes

- Candidate-validation policy versions 1 and 2 are rejected without compatibility behavior. Active
  v4-maker policy v3 uses its immutable policy record and activated prompt contract.

### Validation

- Focused sealed-capture, calibration, prompt-experiment, and deterministic-attestation checks
  passed (29 tests). The direct attestation E2E uses local route doubles and proves it does not
  route a model, publish, import, or activate v4.
- Offline regression coverage follows a Stage-6 rendered context through bundle construction and
  publisher admission, proving that a selected screenshot is accepted while an unselected aggregate
  screenshot is excluded. Cache regression coverage proves inventory-only mirror changes reuse the
  same semantic request.
- The approved no-content Hermes smoke returned `OK` without a project-content payload.

### Current limitations

- Fixture-backed capture, calibration, generated-post comparison, independent review, and v4
  activation and F7 audits are accepted.

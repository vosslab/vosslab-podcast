# News

## v26.08 - 2026-08-28

### Highlights

- The daily-blog system now has a date-owned publication contract. Bundle v4 makes `report_date`
  the sole publication identity, and the systemd user timer calls `./make_blog.py --yesterday` at
  04:00 America/Chicago. The active publication path remains v3.
- A maker-voice experiment now captures sealed Aug. 23 and Aug. 26 evidence separately from
  historical calibration. A deterministic attestation can join both results for review without
  activating v4, publishing a post, or changing the schedule.
- Fresh fail-closed GitHub owner-roster discovery, owner-qualified mirrors, and first-day story
  salience now keep a newly created source repository visible to the author and referee.
- This is not an activation announcement: fresh capture requires approval to send the sealed
  project-context evidence through Hermes, while historical calibration requires approval to send
  the fixed already-public historical posts. The attempted capture stopped before payload egress,
  so there is no live v4 winner, calibration result, activation, or publication.

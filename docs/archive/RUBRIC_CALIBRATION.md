# Maker-rubric calibration

## Current status

Calibration preparation is complete and live scoring is pending. Preparation used no model route,
made no network request, and published nothing. The content-addressed preparation identity is
`0df85dd7fdd48428353d0e6bde893acfaa21d4b23f66ffd267565a36c2ce6169` under schema
`vosslab.daily-blog.rubric-calibration.v2`.

The central test remains:

> After reading this post, does it feel like Neil sat down after coding and wrote about what he
> made, what interested or surprised him, why he enjoyed working on it, what he learned, and what
> he wants to try next?

No historical rubric score, consistency result, v4 arm winner, or activation decision exists yet.

One sandboxed live attempt produced private diagnostic artifact
`rubric-calibration-20260829t011223z-0aa0bca424`. Hermes could not initialize its state and log
files in that restricted filesystem, and all 15 score records ended at structured-response parsing.
The attempt is incomplete evidence rather than a calibration result. The project route now includes
Hermes `--quiet`, which keeps the final model response on stdout and sends session diagnostics to
stderr. A fresh unsandboxed calibration still requires the explicit authorization below.

## Fixed historical inputs

The route-free preparation command reads only the five plan-owned date slots from the configured
daily-blog repository. It opens fixed directories and files without following symbolic links,
checks the date in front matter, bounds each read, and records hashes instead of copying post text
into its report.

| Date | Role | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| 2026-08-22 | Positive-passable reference | 5,762 | `7ff5ae1b4f08a87e1a48b5e514d7889a666fb56adb3be462ccf9a899f77bb4de` |
| 2026-08-23 | Positive-passable reference | 5,456 | `dcaadb7cc51c028f34f60832bcb3e08ab936d35057b3cb55af755c1c61f8821c` |
| 2026-08-24 | Negative reference | 4,620 | `4a67e9fd8f7ee7fff792a16f0b8c2901642e3f6719687092e22f975ad227b7fb` |
| 2026-08-25 | Negative reference | 7,855 | `9c229e04faab04cc6912e752cf013b6a4ac1de87b7b788eedff90f4cfae078af` |
| 2026-08-26 | Measured v3 baseline | 6,945 | `6bce1563ddb7c4bce1f789adbac4d59c63bfc025a8ce6f9e86598c46669cfb75` |

## Route-free diagnostics

These measurements describe shape and visible language. They do not assign quality scores or
activate a prompt.

| Date | Narrative words | Mean paragraph words | Questions | First-person sentences | Distinct action surfaces | Action surfaces per first-person sentence | Inline links |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-08-22 | 591 | 42.2 | 1 | 8 | 21 | 2.625 | 4 |
| 2026-08-23 | 621 | 51.8 | 2 | 6 | 9 | 1.500 | 3 |
| 2026-08-24 | 447 | 49.7 | 0 | 7 | 2 | 0.286 | 13 |
| 2026-08-25 | 825 | 58.9 | 0 | 12 | 4 | 0.333 | 22 |
| 2026-08-26 | 559 | 79.9 | 0 | 7 | 24 | 3.429 | 0 |

August 22 and 23 support the claim that the system was once closer to the desired register. Both
use thematic titles, include genuine questions, and give a visible first-person line of attention
or reasoning. August 24 and 25 use generic dated work-log titles, contain no questions, and reduce
first-person action mostly to update-record language. August 26 regains a thematic title and varied
technical action, but its long paragraphs, lack of questions, and omission of the newly created
`vosslab/cancer-clicker` story show why deterministic voice counts cannot stand in for editorial
judgment.

The action-surface metric is intentionally lexical rather than grammatical. Coordinated phrases can
produce more than one surface per sentence, and terms such as `with` can be false positives. Its
high August 26 value makes the limitation concrete. It remains diagnostic and does not enter the
rubric or an activation gate.

## Live score contract

The calibrator parses the six criteria and weights from
`pipeline/prompts/daily_blog_rubric_v4.md`, then verifies the rubric and both calibrator templates
against one immutable calibration contract. Any heading, weight, or resource-content drift fails
closed. Each model response contains one 1-through-4 score, one exact passage copied from the
reviewed post, and one concise explanation for every criterion. The parser verifies every passage
against the complete post. The harness computes the weighted score instead of accepting a
model-authored total.

The plan's target language is operationalized as follows:

- August 22 and 23: weighted score from 2.5 inclusive to 3.5 exclusive.
- August 24 and 25: weighted score from 1.0 through 2.25 inclusive.
- August 26: measured as the v3 baseline without its own target band.
- The 4 band begins at 3.5 and remains unclaimed by these historical anchors.
- The current one-time procedure requests three repetitions per historical post.
- Its current qualitative-consistency tolerance allows one adjacent rubric-level span per
  criterion.
- Its current separation threshold requires the August 22/23 mean to exceed the August 24/25 mean
  by at least 0.25, the gap implied by the positive minimum and negative maximum target bands.

The repetition count and both thresholds are bounded one-time experiment settings, recorded in the
preparation and live artifacts rather than asserted as permanent pipeline behavior. Repeated runs
expose ordinary sampling variation without pretending the referee is deterministic. A failed
grounding, consistency, band, or separation check sends the rubric back for revision; it does not
select a winner or publish content. Reviewers later inspect whether each explanation actually
follows from its exact passage; deterministic substring validation does not claim to prove that
semantic judgment.

## Approval and reproduction

Route-free preparation is reproducible with:

```bash
source source_me.sh && python3 automation/calibrate_daily_blog_rubric.py --prepare-only
```

Live calibration sends the five public historical posts to the configured referee route. It
requires both `daily_blog.shadow_evaluation.external_model_data_sharing: true` and the explicit
invocation flag below. The current configuration is `false`, so this command remains blocked:

```bash
source source_me.sh && python3 automation/calibrate_daily_blog_rubric.py \
  --approve-historical-post-sharing \
  --repetitions 3 \
  --maximum-criterion-score-span 1 \
  --minimum-band-separation 0.25
```

The live harness is non-publishing, accepts no caller-selected post path or date, writes private
mode-0700 artifacts, records only redacted route failures, and returns success only when all five
posts complete the artifact-recorded procedure with exact passage grounding, meet their target
bands, and satisfy the recorded consistency and separation settings. August 26 remains
baseline-only; it must be complete, passage-grounded, and qualitatively consistent but has no target
band.

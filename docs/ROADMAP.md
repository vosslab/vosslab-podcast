# Roadmap

This roadmap records the remaining work that keeps the daily blog trustworthy and makes its maker
voice ready for an evidence-based activation decision. It is a guide to priorities, not a release
schedule. The detailed prompt work remains in [better_prompt_plan.md](active_plans/better_prompt_plan.md).

## Current baseline

- Production selects `v4-three-examples-corpus-v2` through the accepted maker activation. F4-F6
  are complete; [prompt_experiment_status.md](active_plans/reports/prompt_experiment_status.md)
  records the accepted evidence and closure.
- The writer's target remains the central maker question: a reader should feel that Neil wrote about
  what he made, what interested or surprised him, what he enjoyed and learned, and what he wants to
  try next.
- August 22 and 23 are useful house-voice evidence, not a ceiling. The v4 experiment compares
  example-led prompt arms so that the decision rests on generated posts, not an abstract style rule.

## Completed foundations

- The producer snapshots the authoritative roster of eligible owned repositories and reconciles it
  with owner-qualified mirrors. An uncached repository either enters the run or produces a visible,
  actionable failure.
- Activity, evidence, projection, contracts, and bundles carry repository creation time,
  `created_in_report_window`, and a typed `repository_created` event.
- Story-first projection gives a newly created source repository explicit headline consideration
  without forcing the author or referee to select it.
- The offline August 26 `cancer-clicker` regression proves discovery, lifecycle evidence,
  projection order, and headline eligibility from one sealed fixture.
- The repository bootstrap selects a physical repo-local Python 3.12 environment; the non-link
  suite and daily-blog E2Es pass under Python 3.12.13.

## Complete the maker experiment

The experiment has four deliberately separate stages. The project-context experiment capture and
historical calibration are independent fixture-backed evidence stages and may run in either order.
Only deterministic attestation requires both verified artifacts. No stage authorizes publication or
activation.

1. **Capture route evidence.** The capture command
   [automation/capture_daily_blog_experiment_fixture.py](../automation/capture_daily_blog_experiment_fixture.py)
   creates only sealed, content-addressed quiet and busy fixtures from verified owner-qualified
   mirrors and the immutable roster snapshot. Fresh v2 captures for August 23 and 26 are complete.
   A future replacement capture requires a reviewed consumer-allowlist rotation before it can be
   used for generation. Capture remains offline and non-publishing.
2. **Capture the project-context experiment.** Run
   [automation/experiment_daily_blog_prompts.py](../automation/experiment_daily_blog_prompts.py)
   with the sealed fixtures and deterministic author/referee role fakes. Retain the candidates,
   anonymous referee comparisons, and aggregates so fresh artifact-only reviewers can decide whether
   an arm answers the central maker question or needs revision.
3. **Calibrate historical scoring.** Produce the passing fixture-backed historical-calibration
   artifact with [automation/calibrate_daily_blog_rubric.py](../automation/calibrate_daily_blog_rubric.py).
   Aug. 22-23 establish positive voice references, Aug. 24-25 expose voice failures, and Aug. 26
   exposes the evidence/discovery failure. Live calibration is optional corroboration only.
4. **Attest deterministically.** Run
   [automation/attest_daily_blog_prompt_experiment.py](../automation/attest_daily_blog_prompt_experiment.py)
   against the immutable experiment capture and the passing calibration artifact. The attestation
   recomputes the acceptance result without loading or invoking a model route. It is the durable
   evidence that the required fixtures, calibration, comparison, and acceptance criteria agree, and
   it emits the immutable artifact-only review contract.
5. **Review independently from artifacts.** The configured reviewers separately read the sealed
   capture, calibration, attestation, evidence, and complete selected busy and quiet posts. They do
   not see a manager summary or other reviewer work. Each cites exact selected-post passages for the
   unchanged central question and maker dimensions. Every required review must pass both fixtures
   before F4 is accepted.

## Accepted activation criteria

- V4 advanced after the deterministic attestation was review-ready and the configured independent
  artifact reviews confirmed that
  the winning arm satisfies the central maker question: it reads as Neil writing about what he made,
  what interested or surprised him, what he enjoyed and learned, and what he wants to try next.
  The roster, lifecycle, salience, provenance, validation, evidence-comment, and output-shape
  contracts remain required. A failed fixture-backed calibration, empty comparison set, non-passing
  attestation, or incomplete independent review is not activation evidence. An external-route
  refusal or failure is optional-corroboration evidence, not a milestone blocker.
- The producer and publisher advanced together through one separately reviewed active-contract change.
  The active interface is v4-maker policy v3 and bundle v5.
- Keep the maker brief and examples inside the deterministic contract boundaries. Any later arm or
  fixture change repeats the applicable capture, calibration, comparison, and attestation evidence.

## Future directions, not committed work

- Broaden the evaluation corpus only when it improves the comparison's usefulness and retains clear
  provenance, rights, and attribution boundaries.
- Use the resulting daily-blog evidence to improve adjacent summary and podcast workflows only after
  the daily writer and its activation gate are reliable.

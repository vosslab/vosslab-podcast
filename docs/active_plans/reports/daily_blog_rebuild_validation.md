# Daily blog rebuild validation

## M14 mechanical record

This report records the M14 automated-validation evidence for the daily-blog
rebuild. It is a publication-integrity and reliability record, not an editorial
prose review. The formal reviewer rule is mechanical: accept only when the
recorded inputs, provenance lineage, coverage explanation, terminal receipt,
sealed bundle, installed post, and rendered reader page agree for each required
case. It makes no claim that fixture-written prose is human-quality prose.

All accepted records use source commit
`f6238182f50a323a1f461457efa39d1e4c25a179`. The protected human-owned
`docs/BLOG_CONTRACT.md` remained SHA-256
`306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`.

The durable source of the final matrix values is
`/tmp/vosslab_m14_validation_data_sheet_final.md`; final boundary evidence is
`/tmp/vosslab_m14_five_case_boundary_fix.md`. The temporary roots named below
are the evidence holders. They are disposable implementation evidence, not
runtime storage or a permanent fixture dependency.

## Accepted matrix

The required M14 proof is five self-generated, fixed-date, no-egress cases in
`/tmp/vosslab_m14_five_case_boundary.QmzMXo`. The root's manifest SHA-256 is
`9efc8bf0be62b4ece1ddcf886dd64f0f423c664284ba1cd57102b4abe5b36b4e`.
It contains exactly the required cases; `capture-august` is rejected by the
runner with argparse status 2 and cannot mutate the manifest or add a case.

```bash
source source_me.sh && python3 automation/run_daily_blog_fixture_matrix.py prepare-manifest --capture-base /tmp/vosslab_m14_five_case_boundary.QmzMXo --manifest /tmp/vosslab_m14_five_case_boundary.QmzMXo/manifest.json
source source_me.sh && python3 automation/run_daily_blog_fixture_matrix.py run --capture-base /tmp/vosslab_m14_five_case_boundary.QmzMXo --manifest /tmp/vosslab_m14_five_case_boundary.QmzMXo/manifest.json --case <case> --root /tmp/vosslab_m14_five_case_boundary.QmzMXo/<direct-child>
```

Each record attests `external_route_used: false`, `outcome: degraded`,
`terminal_fault: null`, and `ladder_depth: 1`. Here, `degraded` means eligible
grounded editorial work survived a partial editorial condition and published;
it is not a pipeline fault. `run_state` bytes measure that bounded file only;
the final column is the direct run-directory allocation.

| Case / child | Date and coverage shape | Record / summary / artifact | Bundle / post / rendered page | Run-state bytes / KiB |
| --- | --- | --- | --- | --- |
| `m14-quiet` / `quiet` | 2026-08-23; one `dated_changelog` tuple for `vosslab/quiet-fixture` | `dd3fc9a205c39b55465cebad56b78072c3c97cffd962442a560db2e0c992983f`; `d6e1990a015d11214ceb23447888e3d08b67f47e5a0bed872b17e7091743258d`; `artifact-3d30bacf2ba64fa948f85627` | `ef1737b17b97d56f6dc5b60bb1b3b0c1bbee929013b42cb99cc32a67846bc4fc`; `4ada393bec1da81e25a579e14cb9ba8b88bf39d51614b5e9a39a9c6c6d3019ac`; `a82dcf5cf75082596bda20494f27aa86bf26e8006cafb933a841b20715e86f7f` | 16,275 / 100 |
| `m14-busy` / `busy` | 2026-08-26; `changed_documentation`, `commit_metadata`, `dated_changelog`, `diff`, and `readme_context` | `38eabff5c71972ad95b3815279282ffc4b2acb8a3cd364a301c6abbf01a083dc`; `a8606123db6c0bb4381f9a4885d974ca27e37c7b35c3850a8363e55cae1add71`; `artifact-bb6c24dd0f17d4f06b8992e8` | `791e627087626f96966bcc7fc486f9c2db3fe97b53caf65cdf8a7ebdfb783b08`; `70555d8dd6830856a8841864ec230b565b7b2055282a3dff6a8cae15f90d3b76`; `714d1b88c6495584243acf4a182c2ab81312f8ed0424906ac33dd7f70e263b49` | 16,275 / 108 |
| `m14-single-repository` / `single` | 2026-08-27; one `dated_changelog` tuple for `vosslab/fixture` | `31d517f3ad80b3be7cdc90bc4fff848ebb3b78197447f22798e973acb71b1352`; `0edc9a79116a8171f6a816cba5d7accb334140c1ad0c9517d64867299c9a2764`; `artifact-bd0314b9ebc2695a89540cb5` | `3fcdcaf140c3f6afe1b2177f0c2de3ef819e2f620fe0213a9adc0986ab1e7804`; `f44784b02a833609d943effcafb676f113a559e2a25ecaa563c886c770d681e9`; `d2db93f9c659212134ca8050da05a115c17f9d6f38bc256e699ee2335d13d9ae` | 16,275 / 100 |
| `m14-screenshot-bearing` / `screenshot` | 2026-08-28; `dated_changelog` and screenshot Git blob `148d3a69861d784699428f057b9b39e76f34d128` | `4b007d61b5568662dcacb09a3bf454029f13df5195dbd413d296b6e67aea2e1d`; `80ddd1da2bd2efa37bedb6064243aa977386b4a97f200fc120e1fc4bb0196eda`; `artifact-80822f1bd0881bd2c2db549e` | `cbf1acac9dabc78605f9ae41325ccf58b868a0187cabe330f38df201abfb1530`; `2d9ffa8f867cf5bc027e0d539557c25ca3de0f82e667c19849cbfa30109304cd`; `1649db2e39691e56646e4cad49ff440cab3e4a37f57ce892849ab06877ca87a9` | 16,278 / 104 |
| `m14-degraded-dependency` / `degraded` | 2026-08-29; one `dated_changelog` tuple and `injection_observed: true` | `c82d9f51cb04da79c4a462ec84cf396d8de0d3a4f96dec0ce23a0f4b57ea3322`; `57986f068f4792bec43d08937a66376105af1672fb0e4da68ea0c3b9f147f83b`; `artifact-f7c184ba9aa4f4acef862d7a` | `905fadea02fc5d99cd65b9a4fac041456ac61196f5a0588fab3c34b505b1f32f`; `4dbe90168263af94b84c771889a64ced4e3eddf909497d7c86c57b69bf3cce3f`; `07cee0713b1bb1858ee9337e446256809c74e1cf89749d4d06c6cf5dd10146a5` | 16,346 / 100 |

The records seal full observed coverage separately from the bounded runtime
editorial input. Their lineage is: observed evidence packet -> validated
projection -> exact excerpt mapping -> bounded editorial packet -> selected
artifact -> terminal summary -> bundle, imported post, and rendered page. The
quiet record, for example, binds observed packet
`d5e6c3851652b8e4689e95c3e1eef645bad4b03f7da355b5f5e485a4e79c028a`,
projection `ee0c53f071bb4cb056e695236d50583a4d7a9b9cfb729acf9f6e9df491a0e267`,
and editorial packet
`1292f8766dec6f9f500122a615cc9deee7e416d9e1f0c9ffdcf93adeb8c35c30`.
Coverage is explained rather than compared as a packet-byte golden output:
quiet and single retain their one active repository inventories, busy declares
five independent evidence kinds, and screenshot retains its named screenshot
identity. These hashes prove provenance and publication integrity only.

## Stage and fault evidence

The following one-time checks are recorded before M15 removal. All ran at the
same source commit, on the stated fixed date, through local fixture runners;
none used a model, network route, credential, or human decision.

| Lane | Command and date | Result and retained evidence |
| --- | --- | --- |
| Stage 3 outline | `automation/run_repository_outline_fixture.py --output-root /tmp/vosslab_m14_capture/m7_stage3`; `tests/e2e/e2e_repository_outline_fixture.py`; 2026-08-29 | Both passed. Selected `artifact-ea7bdabdb075cd1e8aa4264a`; fixture `c2518c1cff90c7fa6194599e950c32657ede066e1e6f69fcec8e4c03880e4653`, 2,631 bytes; retained tree 9,141 bytes. A repaired outline is an editorial recovery, not a fault. Source: `/tmp/vosslab_m14_stage3_fixture_evidence.md`. |
| Stage 4 story | `automation/run_repository_story_fixture.py --output-root /tmp/vosslab_m14_capture/m8_stage4`; `tests/e2e/e2e_repository_story_fixture.py`; 2026-08-29 | Both passed with aggregate `32c32dc23ca023b0224f5d6074079ae6510ac0b16e7540b1bacebb97542adb31`; alpha/beta captures 9,543/9,576 bytes. Malformed-verdict repair was editorial degradation. Source: `/tmp/vosslab_m14_stage4_fixture_evidence.md`. |
| Stage 5 outline | `automation/run_daily_outline_fixture.py --output-root /tmp/vosslab_m14_capture/m10_stage5 --report-date 2026-08-29`; `tests/e2e/e2e_daily_outline_fixture.py`; 2026-08-29 | Both passed; capture `81014a85aae0952607a98c2fdf49f7c3b5144dc9ff9ded80356a6b18694535b1`, 8,109 bytes. Ranker/writer faults kept eligible whole outlines. Source: `/tmp/vosslab_m14_stage5_fixture_fix.md`. |
| Typed fault ladder | `tests/e2e/e2e_daily_blog_stage_recovery.py`; 2026-08-23 | Passed. `route_unavailable` fault `f21250a60e4b6124a5d3ab1b179bdef421320a239b9afef411200cd9677e0cce` (5,455-byte run); `no_eligible_generation` `d3e209e660ca1a326fc6f53f59ee89e573bbd30b1c49aa9c740bf30281867f9d` (6,681-byte run). These are genuine terminal pipeline faults, not degradation. Source: `/tmp/vosslab_m14_ladder_harness_policy_repair.md`. |
| Public typed faults | `tests/e2e/e2e_daily_blog_production_recovery.py`; 2026-08-23 | Passed without publication. `route_unavailable`: summary `f53cc8fa109dcb801d8e9024b1223008f4a0bac02c984ce36f472f5ab962ae6a`, fault `b2f330bc54f165318ecbd450376a65b47c7b703d975e724ee1747b9037931222`, 45,372 bytes. `no_eligible_generation`: summary `76682b958d01700b30acdb07ce20767d681fa4be9883fc415e869828829d956a`, fault `b2faef2ae50c7616031b7536a260f0ca2cd222461c2cd5b4d5fac3f1a858895f`, 45,635 bytes. Source: `/tmp/vosslab_m14_production_fault_evidence_final.md`. |
| Stage 7 | `tests/e2e/e2e_daily_blog_stage7_synthesis.py`; 2026-08-23 | Passed. Challenger `artifact-c820dc3bbebbc167196deedc` published bundle `d7fba392179e3a361deaf16dade281efdc19e63b4a7443791ec54e7c0c740edc`, page `01ae31781c8305426c026ad7368ee68c40d56f088be107ac6891deb2d826507a`. Total synthesis loss preserved incumbent `artifact-f47f01566cd59b9f8bd9a9b6`, bundle `f6ee17a5cce8c1c4499d48ba69170934b2553b26804cf55b989d23306e81afff`, page `80646e201e49cc3a76e121f712e75b0adb30670ecbb2597ee4ae07e91f052a92`. Both published as degraded; temporary roots were deleted. Source: `/tmp/vosslab_m14_stage7_synthesis_evidence.md`. |
| RunStore adversarial | `source source_me.sh && python3 tests/e2e/e2e_daily_blog_runstore_adversarial.py`; 2026-08-29 America/Chicago; commit `f6238182f50a323a1f461457efa39d1e4c25a179` | Exit 0: descriptor/replay crash-window and substitution evidence passed with no external routes. Source SHA-256 `6707a0981e402957b46e05fab62480a714f0709738ad3788ae5e56edcb199f16`. The harness used only disposable local temporary roots, which were removed, so it retained no generated artifact digest or publication. **M15 must delete this one-time private-seam harness.** Source: `/tmp/vosslab_m14_runstore_adversarial_evidence.md`. |

Separate corroborating no-egress checks also passed: the screenshot exact-Git
fixture used 2026-08-23 and recorded screenshot SHA-256
`e88d1922d4b281dbc71d67ca2e98ae051c75953d3acbf9a45cd819e3ea77dc19`
(`/tmp/vosslab_m14_screenshot_evidence.md`), and the single-new-repository
fixture passed on 2026-08-26 (`/tmp/vosslab_m14_single_repository_evidence.md`).
Their temporary roots were deleted, so no retained run-size or summary digest
is claimed for them.

## Publication and state

`source source_me.sh && python3 tests/e2e/e2e_daily_publication.py` is the
sole permanent controlled E2E. It passed at fixed date 2026-08-23 with a local
offline runner. Initial publication selected
`artifact-ae39e0fb496316cd00f46c2e`, bundle
`3f6c4422656488bbbed6fdd1499d9a8e6f92ae8a2d1855bab3d927ef6ccb6008`, and
page `62c9b449b299ecb2258a516564ab0e9d834d6f4bcab5c400184aeecc6768343e`.
Same-date replacement selected `artifact-1250ed3f7b2e908118a89c9f` and bundle
`a58efb9e5b6acc7519dd7892523895dd47386abfed2cf0483e39d47df8eb9f87`.
Forced page verification returned public status 2, recorded a typed fault, and
preserved the prior post, bundle, and publication record. Its temporary roots
were deliberately removed; no summary ID or disk measurement is invented.
See `/tmp/vosslab_m14_permanent_e2e_evidence.md`.

A separate retained full publication completed/degraded at 2026-08-23 with
summary `450016868d190ebd1723f53c1144a84afd3c2da2bfc965715c9f1205bb5c1723`.
Its direct run measured 60,766 logical bytes / 104 KiB; its date root measured
83,265 logical bytes / 136 KiB. Source:
`/tmp/vosslab_m14_retained_publication_measurement.md`.

RunStore source, security, and test-policy review all accepted the descriptor
owned state, event, artifact, receipt, replay, and retention boundary. The
source review recorded 68 focused tests plus stage recovery, production
recovery, and controlled publication E2Es; the security review recorded 67
focused tests and no findings. It confirmed selector validation, held
`O_NOFOLLOW` descriptor chains, bounded regular-file JSON reads, same-directory
atomic writes, redacted bounded event facts, terminal receipt binding, and
descriptor-safe retention. The permanent policy retained 29 public behavior
tests and moved private interruption/race tests to the temporary adversarial
harness SHA-256
`6707a0981e402957b46e05fab62480a714f0709738ad3788ae5e56edcb199f16`.
Sources: `/tmp/vosslab_m14_runstore_final_source_rereview.md`,
`/tmp/vosslab_m14_runstore_final_security_rereview.md`, and
`/tmp/vosslab_m14_runstore_test_policy_acceptance.md`.

## Observability and retention

Terminal summaries distinguish completed success, completed editorial
degradation, typed pipeline faults, and incomplete operational failures. The
advisory reliability reporter reads date-level `summary.jsonl`, keeps raw
numerator/denominator observations, and renders an absent denominator as
`n/a`; a fixture observation is never promoted to a production rate.

The final retention decision is to keep
`daily_blog.logging.detailed_retention_days: null`. The measured self-generated
direct runs range from 54,547 to 60,265 logical bytes and 100 to 108 KiB; a
richer local-mirror corroboration was 178--182 KiB but is not an authoritative
roster capacity sample. No evidence establishes production frequency, a full
authoritative busy population, or a storage objective, so a positive day count
would be invented. The serial final run followed an earlier temporary
parallel-copy disk-pressure observation; that resource observation is
non-gating and does not create a performance or capacity requirement. Source:
`/tmp/vosslab_m14_reliability_disk_final_analysis.md`.

## Exclusions and next proof

Earlier local-August attempts are excluded from acceptance because their
removed local-mirror provenance path cannot establish an authoritative
historical roster. They are non-authoritative corroboration only, not a sixth
matrix case. Live `./make_blog.py --yesterday` is `not_run` at M14 with reason
`optional_external_route_corroboration`; it is neither a failure nor a gate.
M16 separately owns an Aug. 28 public-demo record, using controlled no-egress
injection if a live route is unavailable and labelling it fixture-backed or
live. It must independently verify terminal summary, sealed bundle, and page.

## M15 disposition

This is the execution inventory from
`/tmp/vosslab_m14_m15_deletion_inventory_refresh.md`. Do not remove a row
until this report has mechanical reviewer acceptance. Then migrate consumers,
remove all delete rows before `tests/e2e/run_all.sh`, and run focused checks
plus the retained controlled E2E per coherent group. Run aggregate E2E and the
full pytest suite only once after the coordinated migration.

| Path or group | Classification and M15 disposition |
| --- | --- |
| `automation/run_daily_blog_fixture_matrix.py` | One-time five-case evidence runner. **Delete.** Its commands and sealed records are preserved above. |
| `tests/e2e/e2e_daily_blog_runstore_adversarial.py` | One-time private descriptor/replay interruption and race harness. **Delete.** It is unsuitable permanent coverage by the public-behavior policy. |
| `automation/run_repository_outline_fixture.py`; `tests/e2e/e2e_repository_outline_fixture.py` | One-time Stage 3 route/step topology evidence. **Delete.** |
| `automation/run_repository_story_fixture.py`; `tests/e2e/e2e_repository_story_fixture.py`; `tests/e2e/e2e_stage4_rubric_decision.py` | One-time Stage 4 candidate/order and historical rubric topology evidence. **Delete.** |
| `automation/run_daily_outline_fixture.py`; `tests/e2e/e2e_daily_outline_fixture.py` | One-time Stage 5 replay/topology evidence. **Delete.** |
| `tests/e2e/e2e_daily_blog_stage_recovery.py`; `tests/e2e/e2e_daily_blog_production_recovery.py`; `tests/e2e/e2e_daily_blog_stage7_synthesis.py` | One-time forced fault, recovery, and synthesis scenarios. **Delete.** Durable category behavior remains in offline pytest and E1. |
| `automation/capture_daily_blog_experiment_fixture.py`; `automation/run_daily_blog_fixture_capture.py`; `automation/run_daily_blog_fixture_calibration.py` | Superseded private experiment tooling after consumer migration. **Delete.** It is not an M14 publication dependency. |
| `tests/e2e/e2e_daily_publication_schedule.py`; `tests/e2e/e2e_publication_crash_recovery.py` | Legacy retired/unavailable. **Delete.** The former lacks a local fixture input; the latter expects removed `EXPECTED_ROUTE`. Do not recreate compatibility or a human handoff to revive either. |
| `tests/e2e/e2e_daily_publication.py` | Permanent, controlled public publication E2E. **Retain.** |
| `tests/e2e/e2e_daily_blog_evidence_git.py`; `tests/e2e/e2e_daily_blog_new_repository.py`; `tests/e2e/e2e_daily_blog_contract.py`; `tests/e2e/e2e_daily_blog_mirror_refresh.py` | Outside the temporary editorial removal set. **Retain pending separate scope decision; do not delete by implication.** |

Permanent tests remain offline, deterministic, behavior-focused, self-contained
pytest coverage. One-time evidence is the listed direct E2E and automation
procedures: it may use controlled fixture seams, temporary roots, private
interruption injection, or historic topology only while recording M14 proof.
It is removed in M15 rather than hardened into artificial production behavior.

## Verification record

The final matrix source, security, and test-policy reviews all returned ACCEPT:
`/tmp/vosslab_m14_five_case_source_final.md`,
`/tmp/vosslab_m14_five_case_security_final.md`, and
`/tmp/vosslab_m14_five_case_test_policy_final.md`. The runner had 735 physical
lines; Python compilation, Pyflakes, `git diff --check`, five-record structural
and provenance validation, and the protected-contract SHA check passed. No
broad pytest or aggregate E2E was run in M14 because those gates belong after
the planned removal sweep.

`source source_me.sh && python3 -m pytest -q tests/test_markdown_links.py`
finished with 60 passed and one unrelated existing failure at
`docs/active_plans/decisions/daily_blog_stage4_rubric_decision.md:10`: its
`../../archive/LAYERED_PODCAST_IMPROVE_PLAN.md` target resolves correctly from
high. The failure did not name this M14 validation report. Its remediation is
an owning documentation/M16 concern and is non-gating for M14 mechanical
fixture acceptance; no compatibility workaround is added here.

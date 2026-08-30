# M16 daily-blog closeout evidence

Status: accepted and closed

## Scope and disposition

This record preserves a fixture-backed, no-egress demonstration of the public daily-blog command
for August 28, 2026. It demonstrates date selection, automatic replacement, bounded terminal
state, publication integrity, and installation of a reader page in a disposable publisher sibling.
It does not demonstrate live-model behavior or make a prose-quality claim.

The live route is `not_run`: external corroboration is non-gating for this closeout. The harness
bound all external dependencies to local fixtures, and the resulting execution records
`external_route_used: false`.

## Public-command proof

The disposable harness used the public command argv `--yesterday` twice. It patched only the
America/Chicago yesterday mapping to fixed date `2026-08-28`; it supplied neither `--yes` nor
interactive input. Both invocations returned zero and printed `Selected report date: 2026-08-28`.
The second import was `replaced`, proving the automatic occupied-date replacement policy for
`--yesterday` without an interactive dependency.

The final terminal record is for run `m16-aug28-second`, report date `2026-08-28`, with
`state: completed` and `outcome: degraded`. `degraded` is the recorded editorial outcome, not a
pipeline fault: the public command still completed the sealed publication path.

## Integrity and publication checks

| Check | Recorded result |
| --- | --- |
| Bundle schema | `vosslab.daily-blog.bundle.v7` |
| Retired payloads | No `candidates` or `referee` keys |
| Artifact identity | `artifact-bf73776d8039763b9c043253` agrees across run, bundle, bundle post, import, and page verification |
| Post digest | `b80044872fe8bed7306e1c5e3eebd211a9680e31a217b9e34982835d4cd989a1` agrees across producer, sealed bundle post receipt, and disposable publisher post |
| Sealed bundle digest | `a31f60436da47844694af90d8e55fa4225db2becb8b518a9c3e687913ed3d622` agrees with the import receipt |
| Physical `bundle.json` digest | `8edeb531c9c514bce668f5e44a67dcdc84135202c2c19ae7ce90371dd00d6513` |
| Reader page digest | `c63b2f74b44f52b746e90737baf90fec1227b46ddcff0ac975c75ecb244ad3b3` agrees with its page-verification receipt |
| Reader artifact | Present only in the disposable sibling at the installed release path |

The physical `bundle.json` SHA-256 is intentionally distinct from the sealed bundle digest: it
is a self-describing file, while the latter is the digest bound by the publication receipt. The
independent temporary implementation review recomputed these values directly from the retained
disposable artifacts; it is evidence for this implementation closeout, not a durable repository
link.

## Active prompt identity

The proof records identities only, never prompt text or generated post prose.

| Item | Active identity |
| --- | --- |
| Contract | `v4-three-examples-corpus-v2`; prompt version `daily-blog-prompts-v4`; rubric version `daily-blog-rubric-v4` |
| Maker activation | `daily-blog-maker-activation-6b104be9c6907eeeffcf330f6b10173857b39c6b05baa46d4cf009a67daa7547`; schema `vosslab.daily-blog.maker-activation.v1`; path `daily_blog_maker_activation.json` |
| Activation contract SHA-256 | `2fdae757fad5392adc1dd50cbadf13ff535871485220f1b0b52a19ff5d98cf47` |
| Candidate validation | `v4-maker` version `v3`; SHA-256 `3a4b7148579e509b6c32fa19b31d107dc4278eb5f721b2a01353a1a9a51264ee` |
| Example corpus | `v4-three-examples-corpus-v2`; blocks `aug-23`, `corpus-quiet-til`, and `corpus-selectivity-ghostty`; SHA-256 `effc2bf2673c2167d4a764239100c07a0f3b1dea1b52b957ffb9bf394371cfa5` |
| Prompt resources | `pipeline/prompts/daily_blog_author_v4.txt`, `pipeline/prompts/daily_blog_referee_v4.txt`, `pipeline/prompts/daily_blog_referee_repair_v4.txt`, `pipeline/prompts/daily_blog_rubric_v4.md`, and `pipeline/prompts/daily_blog_voice_examples_v4.md` |
| Template SHA-256 | author `539085277515db41f44376abc5b761e826eaf26ea4bee5da228086281cd2fd4b`; referee `33863d4be6f1f89200a65da46bfa9480054628d17ecb122eddb328b03607c070`; repair `ae234d9648d73c64615ffebf9c816d845237b27d35f67e24a68185ea15d6c147`; rubric `5a4562d9a995320f9b74c4dc69a58985bdc50dd37761c5c8563a0536c5ad3cad` |

## Earlier broad-gate context

M15's one aggregate daily-publication E2E run passed 7 of 7 workflows. Its one full
`pytest tests/` run reported 3,513 passed and one failed: a sole stale transition expectation.
That expectation was repaired narrowly; the subsequent focused closure reported 206 passed. No
broad aggregate E2E or full-suite rerun is claimed for M16.

`docs/BLOG_CONTRACT.md` remains protected at SHA-256
`306674359d086e28a1b952da5b5774a23524eb2e424208dec8683da5d5378a00`.

## Closeout checks

The independent final review accepted this record and the completed archival set. The closeout
source passed ASCII and repository Markdown-convention checks; `tests/test_markdown_links.py`
reported 64 passed, and `git diff --check` was clean. All nine specified historical records were
archived, their active operational counterparts remain present, and no current-document Markdown
link targets a retired path. No M15 aggregate E2E or full-suite test rerun was performed.

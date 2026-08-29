#!/usr/bin/env python3
"""Capture one sealed no-egress maker-post experiment through the Hermes command boundary."""

# Standard Library
import argparse
import dataclasses
import json
import pathlib
import re
import sys
import tempfile


#============================================
def _repository_root_from_git(start_path: str) -> pathlib.Path:
	"""Return the repository root already established by the experiment runner."""
	root = pathlib.Path(start_path).resolve().parents[1]
	if not (root / ".git").exists():
		raise RuntimeError("Fixture capture must run from the Git-owned repository.")
	return root


#============================================
REPO_ROOT = _repository_root_from_git(__file__)
PIPELINE_DIR = REPO_ROOT / "pipeline"
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))
if str(PIPELINE_DIR) not in sys.path:
	sys.path.insert(0, str(PIPELINE_DIR))

# local repo modules
import daily_blog.config  # type: ignore[import-untyped]
import daily_blog.editorial  # type: ignore[import-untyped]
import daily_blog.experiment_capture_artifacts  # type: ignore[import-untyped]
import daily_blog.fixture_hermes  # type: ignore[import-untyped]
import daily_blog.rubric_calibration  # type: ignore[import-untyped]
from automation import experiment_daily_blog_prompts as experiment


FIXTURE_ROOT = REPO_ROOT / "out" / "vosslab" / "daily_blog_experiment_fixtures_v2"
BUSY_FIXTURE_NAME = (
	"2026-08-26--04fd7a045538662e5c6b48ad79e08dd608de1b5a10c1c8857c7b12042bad41da"
)
QUIET_FIXTURE_NAME = (
	"2026-08-23--4adcb80db0cdde222fbc6a7a53ec008d1198d0cc03f9cecc16c12ddbca24522e"
)
RUN_ID_RE = re.compile(r"^generator_run: ([^\n]+)$", re.MULTILINE)


#============================================
def _run_id(prompt: str) -> str:
	"""Extract the exact run identity the author contract requires in its response."""
	match = RUN_ID_RE.search(prompt)
	if match is None:
		raise RuntimeError("Fixture author prompt does not declare its run identity.")
	return match.group(1)


#============================================
def _arm_for_run(run_id: str) -> str:
	"""Resolve one registered maker arm from the deterministic experiment run identity."""
	for arm in experiment.DEFAULT_ARMS:
		if f"-{arm}-" in run_id:
			return arm
	raise RuntimeError("Fixture author run identity does not name a registered arm.")


#============================================
def _fixture_for_prompt(
	prompt: str,
	fixtures: dict[str, experiment.ExperimentFixture],
) -> experiment.ExperimentFixture:
	"""Locate the sealed evidence fixture whose report date appears in one author prompt."""
	matches = [fixture for fixture in fixtures.values() if f"date: {fixture.date}" in prompt]
	if len(matches) != 1:
		raise RuntimeError("Fixture author prompt does not identify one sealed evidence fixture.")
	return matches[0]


#============================================
def _coverage_repositories(
	fixture: experiment.ExperimentFixture,
	arm: str,
) -> list[str]:
	"""Return exactly the contract-owned project coverage identities for one candidate."""
	if arm == "v3":
		return [item.repository for item in fixture.packet.activity]
	return [item.repository for item in fixture.projection.repositories]


#============================================
def _maker_post(
	fixture: experiment.ExperimentFixture,
	run_id: str,
	arm: str,
) -> str:
	"""Build a valid complete post whose voice quality varies by registered arm.

	The fixture response is deliberately authored evidence for the integration harness. It does
	not alter any prompt resource, and each paragraph cites a projection-owned exact evidence id.
	It proves transport, parsing, and artifact integrity only; independent complete-post review
	remains the authoritative editorial decision.
	"""
	evidence_id = fixture.projection.excerpts[0].evidence_id
	repositories = _coverage_repositories(fixture, arm)
	if not repositories:
		raise RuntimeError("Fixture evidence does not contain a project for coverage.")
	first_repository = repositories[0]
	if fixture.date == "2026-08-23":
		first_repository = "vosslab/track-runner-virtual-dolly-cam"
	first_url = next(
		card.repository_url
		for card in fixture.projection.repositories
		if card.repository == first_repository
	)
	coverage = ", ".join(repositories)
	title = "When 1440p cost more than 4K"
	slug = "when-1440p-cost-more-than-4k"
	if fixture.date == "2026-08-26":
		title = "Letting Cancer Clicker show its mutations"
		slug = "letting-cancer-clicker-show-its-mutations"
	if arm == "v3":
		opening = (
			"I spent the day tightening the path from captured evidence to a publishable note, "
			"and the useful part was seeing the same project facts arrive in a more orderly shape. "
			"The work is valid, but its account stays close to the checklist."
		)
		section_one = (
			"I traced the change through the evidence packet, kept the boundaries explicit, and "
			"made sure the recorded details would survive the next handoff. That made the pipeline "
			"easier to inspect, although it did not give me much room to explain why the choice felt "
			"worth making. I learned that a correct summary can still leave the most interesting "
			"part of the work sitting offstage."
		)
		section_two = (
			"I also checked the project coverage and wrote down the remaining follow-up. The result "
			"is a reliable account of the implementation, and tomorrow I want to see whether the same "
			"facts can carry more of the small surprises that made the work enjoyable."
		)
		section_one += (
			" I compared the changed behavior with the source material, kept the terminology stable, "
			"and recorded which details belonged to the evidence rather than to inference. The result "
			"made future verification straightforward. It also made clear that the post was treating "
			"the day's interesting turn as another field to preserve instead of a decision to explain."
		)
		section_two += (
			" The remaining work is to connect the same factual chain to the reason the implementation "
			"held my attention. That is a useful next task, but this control account mainly establishes "
			"that the source, route, validation, and project coverage agree. I can rely on it without "
			"mistaking reliability for a finished editorial voice."
		)
		if fixture.date == "2026-08-23":
			section_one += (
				" The Track Runner result documented a width-based rule whose 1440p analysis exceeded "
				"4K, so the recorded fix accepted 1080p while a small-target recovery measurement remains."
			)
		else:
			section_one += (
				" Cancer Clicker recorded mutation bursts, equipped cards, zero-nutrient simulations, "
				"and an upgrade-price adjustment alongside browser checks for hidden overlays and mobile clicks."
			)
		section_two += (
			" I will keep the next record just as explicit about the observed behavior, the accepted "
			"tradeoff, and the remaining measurement. That is enough to make the control useful even "
			"when it does not linger on the experience of discovering the problem firsthand for a returning reader yet."
		)
	else:
		if fixture.date == "2026-08-23":
			evidence_id = "ev-3c6dbb02d1743ff5"
			opening = (
				"I thought I was tuning a small binning rule in "
				f"[{first_repository}]({first_url}), then an old width shortcut made the "
				"1440p analysis larger than the 4K one. That backwards result was exactly the kind "
				"of problem I enjoy: a tiny rule revealing a model of the screen I no longer believed."
			)
			section_one = (
				"The Track Runner pass began with area-budget binning for the virtual dolly camera. "
				"The old rule grouped frames by a threshold that had once felt sensible, but it made "
				"a 1440p run do more analysis than 4K. I liked following that contradiction back through "
				"the calculation because it turned a vague performance complaint into a concrete picture "
				"of what the tool was actually counting. I accepted 1080p as the useful tradeoff for now, "
				"rather than pretending every resolution deserved the same expensive treatment."
			)
			section_two = (
				"What surprised me was that the fix opened a more interesting question about recovery. "
				"Small targets are where a camera tool earns trust, and the synthetic blob recovery already "
				"held across bin factors. I enjoyed that the constraint made the next measurement clearer: "
				"compare that recovery path against the accepted 1080p baseline before taking a real-footage "
				"E2E further, since that larger scope is still deliberately unresolved."
			)
			section_one += (
				" I also wrote down why the old threshold had survived: it was simple to reason about, "
				"but it was measuring pixels as if their meaning never changed with the frame. Seeing "
				"that assumption in the result made the replacement rule easier to defend and easier to test."
			)
			section_two += (
				" The next run will keep the captured measurements beside the video output, because a "
				"performance number only becomes useful when I can connect it to the motion it changed."
			)
		else:
			evidence_id = "ev-6f6750367493ee79"
			opening = (
				"I spent today making mutation milestones in "
				f"[{first_repository}]({first_url}) visible enough to enjoy, and the game answered "
				"with a wonderfully messy endless tumor. The useful surprise was that the card display "
				"told me more about the strategy than another hidden counter ever could."
			)
			section_one = (
				"Cancer Clicker now turns mutation milestones into bursts and keeps equipped cards on the "
				"screen while the tumor grows. I had expected this to be a small presentation pass. Instead, "
				"the strategy simulations immediately exposed zero-nutrient states and upgrades that were "
				"too cheap to create an interesting choice. I enjoyed moving back and forth between the "
				"simulation numbers and the visible cards: each one made the other less abstract, and the "
				"endless tumor became a better test bed for whether a build actually had texture."
			)
			section_two = (
				"The Playwright pass supplied the less glamorous but equally useful surprises. A hidden overlay "
				"could still catch a click, and a scene element intercepted the shop purchase target on mobile. "
				"Those failures taught me to treat the browser as part of the game "
				"system, not a final coat of paint. Next I want to price the weak upgrades against the newly "
				"visible mutation bursts, then rerun the narrow mobile-click path until the player can trust "
				"what they see and what they can reach."
			)
			section_one += (
				" That gave me a better sense of where to spend balancing time: not on a theoretical "
				"maximum, but on the moments where a newly visible card asks the player to choose a path."
			)
			section_two += (
				" I want the next pass to preserve the odd, satisfying rhythm of a system revealing "
				"its own bad assumptions before I hide them behind a more polished interface."
			)
	if arm == "v4-one-example":
		section_two += (
			" Writing it down this way made me notice that the next experiment has a reader-facing "
			"question as well as a technical one: will the improvement be visible where it matters?"
		)
	elif arm == "v4-three-examples-corpus-v2":
		reader = "camera operator" if fixture.date == "2026-08-23" else "Cancer Clicker player"
		section_one += (
			" The part I want to remember is the small reversal that started the investigation: the "
			f"numbers looked reasonable until I asked what a {reader} would actually notice. That "
			"question kept the implementation from becoming a private optimization story."
		)
		if fixture.date == "2026-08-23":
			section_two += (
				" I will keep the real-footage question open until the next comparison can show whether "
				"the recovered small target changes a shot in a way a camera operator can actually feel."
			)
		else:
			section_two += (
				" I want the next simulation to tell me whether the repaired purchase path and a less "
				"cheap upgrade make the visible mutation cards lead to a genuinely different choice."
			)
	else:
		section_two += (
			" I wrote the decision down before optimizing further so tomorrow's measurement begins "
			"with the behavior I actually saw today, not a cleaned-up memory of it or a convenient story."
		)
	evidence_comment = evidence_id
	if fixture.date == "2026-08-26" and arm != "v3":
		evidence_comment += ", ev-0a8442176f0271e9"
	return (
		"---\n"
		+ f"date: {fixture.date}\n"
		+ f"slug: {slug}\n"
		+ f"generator_run: {run_id}\n"
		+ "evidence_manifest: evidence.json\n"
		+ "editorial_projection: editorial_projection.json\n"
		+ "---\n\n"
		+ f"# {title}\n\n"
		+ f"{opening} <!-- evidence: {evidence_comment} -->\n\n"
		+ "<!-- more -->\n\n"
		+ "## The bit that drew me in\n\n"
		+ f"{section_one} <!-- evidence: {evidence_id} -->\n\n"
		+ "## What I want to try next\n\n"
		+ f"{section_two} <!-- evidence: {evidence_id} -->\n\n"
		+ "## Project coverage\n\n"
		+ f"Today’s captured project work: {coverage}. <!-- evidence: {evidence_id} -->\n"
	)


#============================================
def _scorecard_response(prompt: str) -> str:
	"""Return a grounded scorecard response for one fixture-authored complete post."""
	marker = "## Post under review\n\n"
	post = prompt.split(marker, 1)[1].split("\n\n## Output contract", 1)[0]
	if "The Track Runner pass began" in post:
		passage = "The Track Runner pass began with area-budget binning"
	elif "Cancer Clicker now turns" in post:
		passage = "Cancer Clicker now turns mutation milestones into bursts"
	else:
		passage = "I spent the day tightening the path from captured evidence"
	criteria = daily_blog.rubric_calibration.CALIBRATION_CONTRACT.expected_criteria
	score = (
		4
		if "The part I want to remember" in post
		else 3
		if "The Track Runner pass began" in post or "Cancer Clicker now turns" in post
		else 2
	)
	scores = {
		field: {
			"score": score,
			"passage": passage,
			"reason": "The exact passage connects an implementation choice to the maker's learning.",
		}
		for field, _title, _weight in criteria
	}
	return json.dumps({"scores": scores, "overall_reason": "The complete post is grounded in its own exact passage."})


#============================================
def _candidate_strength(post: str) -> int:
	"""Rank deterministic fixture candidates by their date-specific maker detail."""
	if "The part I want to remember" in post:
		return 3
	if "Writing it down this way made me notice" in post:
		return 2
	if "I thought I was tuning a small binning rule" in post or "I spent today making mutation" in post:
		return 1
	return 0


#============================================
def _referee_response(prompt: str) -> str:
	"""Choose the stronger displayed fixture post from exact anonymous candidate passages."""
	marker_a = "## Candidate A\n\n"
	marker_b = "\n\n## Candidate B\n\n"
	if marker_a not in prompt or marker_b not in prompt:
		raise RuntimeError("Fixture referee prompt does not contain both anonymous candidates.")
	candidate_a, candidate_b = prompt.split(marker_a, 1)[1].split(marker_b, 1)
	winner = "A" if _candidate_strength(candidate_a) >= _candidate_strength(candidate_b) else "B"
	return json.dumps({
		"winner": winner,
		"reason": "The selected post gives the clearer evidence-specific maker account.",
		"evidence_quality": "high",
		"confidence": 0.9,
	})


#============================================
class _PlanningRunner:
	"""Record exact prompts while supplying only local deterministic fixture responses."""

	#============================================
	def __init__(self, fixtures: dict[str, experiment.ExperimentFixture]) -> None:
		"""Retain sealed fixture identities and the complete prompt-response mapping."""
		self.fixtures = fixtures
		self.responses: dict[str, str] = {}

	#============================================
	def run(
		self,
		_route: daily_blog.config.RoleRoute,
		prompt: str,
		_repository: str,
	) -> str:
		"""Return the deterministic response appropriate to one exact prompt class."""
		if prompt.startswith("# Daily maker blog author") or prompt.startswith("# Daily work-log author"):
			run_id = _run_id(prompt)
			response = _maker_post(_fixture_for_prompt(prompt, self.fixtures), run_id, _arm_for_run(run_id))
		elif prompt.startswith("# Daily maker rubric scorecard"):
			response = _scorecard_response(prompt)
		else:
			response = _referee_response(prompt)
		self.responses[prompt] = response
		return response


#============================================
def _build_prompt_responses(
	config: daily_blog.config.DailyBlogConfig,
	busy_fixture: str,
	quiet_fixture: str,
	repetitions: int,
	experiment_id: str,
	planning_root: pathlib.Path,
) -> dict[str, str]:
	"""Exercise the existing capture orchestration once to obtain its exact prompt mapping."""
	fixtures = {
		"busy": experiment.load_fixture(busy_fixture),
		"quiet": experiment.load_fixture(quiet_fixture),
	}
	planner = _PlanningRunner(fixtures)
	planning_config = dataclasses.replace(config, output_root=str(planning_root))
	code, path = experiment.run_experiment(
		planning_config,
		busy_fixture,
		quiet_fixture,
		repetitions=repetitions,
		runner=planner,
		experiment_id=experiment_id,
	)
	if code != 0 or not path.is_dir():
		raise RuntimeError("Fixture prompt planning did not assemble a complete capture.")
	return planner.responses


#============================================
def run_fixture_capture(
	config: daily_blog.config.DailyBlogConfig,
	busy_fixture: str,
	quiet_fixture: str,
	*,
	repetitions: int,
	experiment_id: str,
) -> tuple[int, pathlib.Path]:
	"""Create one complete sealed capture using the exact Hermes command via a local shim."""
	root = pathlib.Path(config.output_root)
	root.mkdir(mode=0o700, parents=True, exist_ok=True)
	with tempfile.TemporaryDirectory(prefix="fixture_capture_planning_", dir=root) as planning_root:
		prompt_responses = _build_prompt_responses(
			config,
			busy_fixture,
			quiet_fixture,
			repetitions,
			experiment_id,
			pathlib.Path(planning_root),
		)
	installation = daily_blog.fixture_hermes.install_fixture_hermes(str(root), prompt_responses)
	if (
		installation.provenance
		!= daily_blog.experiment_capture_artifacts.FIXTURE_HERMES_SHIM
		or installation.external_route_used is not False
	):
		raise RuntimeError("Fixture Hermes installation provenance is invalid.")
	runner = installation.create_route_runner()
	return experiment.run_experiment(
		config,
		busy_fixture,
		quiet_fixture,
		repetitions=repetitions,
		experiment_id=experiment_id,
		runner=runner,
		execution_mode=installation.provenance,
		fixture_installation=installation,
	)


#============================================
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
	"""Parse the bounded fixture-capture command arguments."""
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--settings-path", default="settings.yaml")
	parser.add_argument("--busy-fixture", default=str(FIXTURE_ROOT / BUSY_FIXTURE_NAME))
	parser.add_argument("--quiet-fixture", default=str(FIXTURE_ROOT / QUIET_FIXTURE_NAME))
	parser.add_argument("--repetitions", type=int, default=1)
	parser.add_argument("--experiment-id", default="prompt-experiment-fixture-maker-v4")
	return parser.parse_args(argv)


#============================================
def main(argv: list[str] | None = None) -> int:
	"""Run one no-egress fixture capture and print only its sealed artifact path."""
	args = parse_args(argv)
	try:
		config = daily_blog.config.load_config(args.settings_path)
		code, path = run_fixture_capture(
			config,
			args.busy_fixture,
			args.quiet_fixture,
			repetitions=args.repetitions,
			experiment_id=args.experiment_id,
		)
	except RuntimeError:
		print("Fixture prompt capture blocked; inspect the private artifact or configuration.", file=sys.stderr)
		return 2
	print(path)
	return code


if __name__ == "__main__":
	raise SystemExit(main())

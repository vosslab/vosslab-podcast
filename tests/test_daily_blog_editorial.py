"""Editorial isolation, prompt, validation, and final referee behavior tests."""

# Standard Library
import json
import dataclasses
import pathlib
import copy

# PIP3 modules
import pytest

# local repo modules
import daily_blog.config
import daily_blog.schema
import daily_blog.repository_contracts
import daily_blog.routes
import daily_blog.editorial
import daily_blog.candidates
import daily_blog.contracts
import daily_blog.projection
import daily_blog.io_utils


#============================================
def make_packet(with_activity: bool = False) -> daily_blog.schema.EvidencePacket:
	"""Return one complete inline primary-evidence packet."""
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog",
		"vosslab/project",
		"a" * 40,
		"docs/CHANGELOG.md",
		"b" * 40,
		"## 2026-08-23\n\n- Added exact bundle validation.\n",
		"git show",
	)
	activity = []
	if with_activity:
		commit = daily_blog.schema.CommitActivity(
			sha="a" * 40,
			parents=("c" * 40,),
			author_name="Author",
			author_email="author@example.com",
			author_timestamp="2026-08-23T12:00:00-05:00",
			committer_timestamp="2026-08-23T12:00:00-05:00",
			message="Add exact bundle validation",
		)
		activity.append(
			daily_blog.schema.RepositoryActivity(
				repository="vosslab/project",
				repository_url="https://github.com/vosslab/project",
				cache_path="/nonexistent/vosslab-test/project",
				default_revision="a" * 40,
				commits=(commit,),
				revision_ranges=(
					daily_blog.schema.RevisionRange("c" * 40, "a" * 40),
				),
				snapshot_commits=("a" * 40,),
				is_fork=False,
				lifecycle_events=(daily_blog.repository_contracts.RepositoryLifecycleEvent(
					"repository_created", "2020-01-01T00:00:00Z", False, "github_owner_roster",
				),),
			)
		)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23",
		"America/Chicago",
		True,
		{},
		[],
		activity,
		[item],
	)
	return packet


#============================================
def make_projection(
	packet: daily_blog.schema.EvidencePacket,
) -> daily_blog.schema.EditorialProjection:
	"""Return one deterministic editorial projection for inline evidence."""
	limits = {
		"context_chars": 12000,
		"excerpt_chars": 2000,
		"commit_subject_chars": 160,
	}
	return daily_blog.projection.build_projection(packet, limits)


#============================================
def make_config() -> daily_blog.config.DailyBlogConfig:
	"""Return isolated fake routes for editorial unit tests."""
	config = daily_blog.config.DailyBlogConfig(
		settings_path="settings.yaml",
		output_root="out",
		output_owner="vosslab",
		report_timezone="America/Chicago",
		daily_blog_repository="/nonexistent/vosslab-test/generator",
		mirror_cache_root="/nonexistent/vosslab-test/mirrors",
		identity_names=("Author",),
		identity_emails=(),
		author_routes=(
			daily_blog.config.RoleRoute("one", ("fake",)),
			daily_blog.config.RoleRoute("two", ("fake",)),
		),
		referee_route=daily_blog.config.RoleRoute("judge", ("fake",)),
		collection_limits={},
		projection_limits={
			"context_chars": 12000,
			"excerpt_chars": 2000,
			"commit_subject_chars": 160,
		},
		prompt_limits={"author_chars": 20000, "referee_chars": 30000},
	)
	return config


#============================================
def valid_post(
	packet: daily_blog.schema.EvidencePacket,
	projection: daily_blog.schema.EditorialProjection,
	run_id: str,
	title: str,
	detail_repetitions: int = 9,
) -> str:
	"""Return one inline candidate satisfying deterministic contracts."""
	evidence_id = packet.items[0].evidence_id
	intro_sentence = (
		"I connected exact evidence to durable ownership and explained why the verified change "
		"matters to readers now. "
	)
	detail_sentence = (
		"I followed the strongest development thread through the concrete decision, its practical "
		"effect, and the current state of the work. "
	)
	intro = (intro_sentence * 4).strip()
	first_section = (detail_sentence * detail_repetitions).strip()
	second_section = (detail_sentence * detail_repetitions).strip()
	repositories = ", ".join(activity.repository for activity in packet.activity)
	coverage_subject = repositories if repositories else "the verified project"
	post = (
		"---\n"
		+ f"date: {packet.report_date}\n"
		+ "slug: durable-bundles\n"
		+ f"generator_run: {run_id}\n"
		+ "evidence_manifest: evidence.json\n"
		+ "editorial_projection: editorial_projection.json\n"
		+ "---\n\n"
		+ f"# {title}\n\n"
		+ f"{intro} <!-- evidence: {evidence_id} -->\n\n"
		+ "<!-- more -->\n\n"
		+ "## Durable ownership\n\n"
		+ f"{first_section} <!-- evidence: {evidence_id} -->\n\n"
		+ "## Where the work stands\n\n"
		+ f"{second_section} <!-- evidence: {evidence_id} -->\n\n"
		+ "## Project coverage\n\n"
		+ f"I recorded {coverage_subject} in the evidence packet. "
		+ f"<!-- evidence: {evidence_id} -->\n"
	)
	return post


class FakeRunner:
	"""Return valid author posts and force one referee repair."""

	#============================================
	def __init__(
		self,
		packet: daily_blog.schema.EvidencePacket,
		projection: daily_blog.schema.EditorialProjection,
		run_id: str,
	) -> None:
		"""Retain deterministic response context."""
		self.packet = packet
		self.projection = projection
		self.run_id = run_id
		self.prompts = []
		self.referee_calls = 0

	#============================================
	def run(self, route: daily_blog.config.RoleRoute, prompt: str, _repository: str) -> str:
		"""Return route-specific deterministic output."""
		self.prompts.append((route.name, prompt))
		if route.name == "one":
			return valid_post(self.packet, self.projection, self.run_id, "Exact evidence wins")
		if route.name == "two":
			return valid_post(
				self.packet,
				self.projection,
				self.run_id,
				"Bundles preserve the day",
			)
		self.referee_calls += 1
		if self.referee_calls == 1:
			return "winner A"
		return json.dumps(
			{
				"winner": "A",
				"reason": "Candidate A follows the compact evidence most precisely.",
				"evidence_quality": "medium",
				"confidence": 0.7,
			}
		)


#============================================
@pytest.mark.parametrize(
	"instruction",
	(
		"Do not explain the evidence.",
		"Leave repository operations to the manager.",
	),
)
def test_prompt_validation_requires_direct_outcomes(
	monkeypatch: pytest.MonkeyPatch,
	instruction: str,
) -> None:
	"""Prompt validation rejects negation and disguised deferral before model routing."""
	contract = daily_blog.contracts.V3_EDITORIAL_CONTRACT
	templates = {
		contract.author_template: (
			f"Use {{evidence_json}}.\n\n## Output contract\n\n{instruction}"
		),
		contract.referee_template: (
			"Compare {candidate_a} and {candidate_b}.\n\n## Output contract"
		),
		contract.repair_template: "Return the structured verdict.",
		contract.rubric: "Prefer factual fidelity.",
	}
	monkeypatch.setattr(daily_blog.editorial, "load_prompt", templates.__getitem__)

	with pytest.raises(RuntimeError, match="desired outcome"):
		daily_blog.editorial.validate_prompt_templates()


#============================================
def test_route_configuration_rejects_hidden_instruction_sources(tmp_path: pathlib.Path) -> None:
	"""Execution routes cannot inject profile skills beside versioned prompts."""
	settings_path = tmp_path / "settings.yaml"
	settings_path.write_text(
		"github:\n"
		"  username: vosslab\n"
		"  identity_login: vosslab\n"
		"daily_blog:\n"
		"  routes:\n"
		"    authors:\n"
		"      - name: one\n"
		"        command: [hermes, chat, --skills, daily-github-blogger, --query-file, -]\n"
		"      - name: two\n"
		"        command: [hermes, chat, --ignore-rules, --query-file, -]\n"
		"    referee:\n"
		"      name: judge\n"
		"      command: [hermes, chat, --ignore-rules, --query-file, -]\n",
		encoding="utf-8",
	)

	with pytest.raises(RuntimeError, match="sealed Hermes editorial route"):
		daily_blog.config.load_config(str(settings_path))


#============================================
def test_hermes_route_requires_profile_instruction_isolation(tmp_path: pathlib.Path) -> None:
	"""A Hermes executor must disable profile rules even when its query uses stdin."""
	settings_path = tmp_path / "settings.yaml"
	settings_path.write_text(
		"github:\n"
		"  username: vosslab\n"
		"  identity_login: vosslab\n"
		"daily_blog:\n"
		"  routes:\n"
		"    authors:\n"
		"      - name: one\n"
		"        command: [hermes, chat, --query-file, -]\n"
		"      - name: two\n"
		"        command: [hermes, chat, --ignore-rules, --query-file, -]\n"
		"    referee:\n"
		"      name: judge\n"
		"      command: [hermes, chat, --ignore-rules, --query-file, -]\n",
		encoding="utf-8",
	)

	with pytest.raises(RuntimeError, match="sealed Hermes editorial route"):
		daily_blog.config.load_config(str(settings_path))


#============================================
def test_two_authors_share_projection_and_referee_repair_selects_final() -> None:
	"""Malformed referee output receives one repair before an approved final selection."""
	packet = make_packet()
	projection = make_projection(packet)
	config = make_config()
	runner = FakeRunner(packet, projection, "run-123")

	raw = daily_blog.editorial.generate_candidates(
		packet, projection, "run-123", config, runner=runner
	)
	candidates = daily_blog.editorial.validate_candidates(
		raw, packet, projection, "run-123"
	)
	decision = daily_blog.editorial.select_candidate(
		packet, projection, "run-123", candidates, config, runner=runner
	)

	assert runner.prompts[0][1] == runner.prompts[1][1]
	assert decision.winner == "A"


#============================================
def test_referee_reason_is_bounded_without_rejecting_control_fields() -> None:
	"""Verbose explanatory metadata cannot block an otherwise valid referee decision."""
	response = json.dumps(
		{
			"winner": "A",
			"reason": "evidence-backed explanation " * 40,
			"evidence_quality": "high",
			"confidence": 0.9,
		}
	)

	verdict = daily_blog.editorial._parse_verdict(response, {"A"})

	assert verdict["winner"] == "A"
	assert verdict["evidence_quality"] == "high"
	assert verdict["confidence"] == 0.9
	assert len(verdict["reason"]) == 500
	assert verdict["reason"].endswith("...")


#============================================
def test_candidate_validation_rejects_unknown_provenance() -> None:
	"""A fluent post remains ineligible when its factual provenance is fabricated."""
	packet = make_packet()
	projection = make_projection(packet)
	post = valid_post(packet, projection, "run-123", "Evidence matters").replace(
		packet.items[0].evidence_id,
		"ev-unknown",
	)

	issues = daily_blog.candidates.validate_candidate(
		post, packet, projection, "run-123", daily_blog.contracts.V4_MAKER_VALIDATION_POLICY
	)

	assert any("unknown evidence" in issue for issue in issues)


#============================================
def test_candidate_validation_accepts_a_reflective_uncited_paragraph() -> None:
	"""One reflective paragraph can breathe beside evidence-backed narrative prose."""
	packet = make_packet()
	projection = make_projection(packet)
	post = valid_post(packet, projection, "run-123", "Evidence matters").replace(
		" <!-- evidence: " + packet.items[0].evidence_id + " -->\n\n## Where the work stands",
		" <!-- evidence: "
		+ packet.items[0].evidence_id
		+ " -->\n\nI enjoyed how the whole design finally clicked into place."
		+ "\n\n## Where the work stands",
		1,
	)

	issues = daily_blog.candidates.validate_candidate(post, packet, projection, "run-123", daily_blog.contracts.V4_MAKER_VALIDATION_POLICY)

	assert issues == []


#============================================
def test_candidate_validation_requires_evidence_in_an_uncited_opening() -> None:
	"""The opening narrative section needs evidence even before later H2 sections."""
	packet = make_packet()
	projection = make_projection(packet)
	post = valid_post(packet, projection, "run-123", "Evidence matters")
	post = post.replace(" <!-- evidence: " + packet.items[0].evidence_id + " -->", "", 1)

	issues = daily_blog.candidates.validate_candidate(post, packet, projection, "run-123", daily_blog.contracts.V4_MAKER_VALIDATION_POLICY)

	assert "Each narrative section must cite projected evidence." in issues


#============================================
def test_candidate_validation_requires_evidence_in_each_narrative_section() -> None:
	"""A prose-bearing narrative section cannot be wholly detached from evidence."""
	packet = make_packet()
	projection = make_projection(packet)
	post = valid_post(packet, projection, "run-123", "Evidence matters")
	post = post.replace(
		" <!-- evidence: " + packet.items[0].evidence_id + " -->\n\n## Where the work stands",
		"\n\n## Where the work stands",
		1,
	)

	issues = daily_blog.candidates.validate_candidate(post, packet, projection, "run-123", daily_blog.contracts.V4_MAKER_VALIDATION_POLICY)

	assert "Each narrative section must cite projected evidence." in issues


#============================================
def test_candidate_validation_counts_prose_after_heading_without_a_blank_line() -> None:
	"""A heading cannot hide adjacent uncited prose from the narrative cap."""
	packet = make_packet()
	projection = make_projection(packet)
	uncited_blocks = "\n\n".join(
		[
			"I want to follow this thread further tomorrow.",
			"The small shape of the change still makes me smile.",
			"I learned that a narrow boundary can make the rest simpler.",
			"I am curious what breaks when I try the next variation.",
		]
	)
	post = valid_post(packet, projection, "run-123", "Evidence matters").replace(
		"## Durable ownership\n\n",
		"## Durable ownership\n" + uncited_blocks + "\n\n",
		1,
	)

	issues = daily_blog.candidates.validate_candidate(post, packet, projection, "run-123", daily_blog.contracts.V4_MAKER_VALIDATION_POLICY)

	assert "Post exceeds the uncited narrative prose block limit." in issues


#============================================
def test_candidate_validation_excludes_uncited_project_coverage_from_narrative_cap() -> None:
	"""The compact Project coverage footer remains bookkeeping rather than narrative."""
	packet = make_packet()
	projection = make_projection(packet)
	post = valid_post(packet, projection, "run-123", "Evidence matters")
	post = post.replace(
		"I recorded the verified project in the evidence packet. <!-- evidence: "
		+ packet.items[0].evidence_id
		+ " -->\n",
		"I recorded the verified project in the evidence packet.\n",
		1,
	)

	issues = daily_blog.candidates.validate_candidate(post, packet, projection, "run-123", daily_blog.contracts.V4_MAKER_VALIDATION_POLICY)

	assert issues == []


#============================================
def test_final_candidate_validation_enforces_narrative_word_budget() -> None:
	"""A narrative stub remains ineligible even when its shape is otherwise valid."""
	packet = make_packet()
	projection = make_projection(packet)
	post = valid_post(
		packet, projection, "run-123", "Evidence matters", detail_repetitions=1
	)

	issues = daily_blog.candidates.validate_candidate(post, packet, projection, "run-123", daily_blog.contracts.V4_MAKER_VALIDATION_POLICY)

	assert any("narrative" in issue for issue in issues)


#============================================
def test_final_candidate_validation_accepts_an_unsectioned_maker_story() -> None:
	"""A quiet-day story can run without narrative H2 headings."""
	packet = make_packet(with_activity=True)
	projection = make_projection(packet)
	post = valid_post(packet, projection, "run-123", "Evidence matters")
	post = post.replace("## Durable ownership\n\n", "", 1)
	post = post.replace("## Where the work stands\n\n", "", 1)

	issues = daily_blog.candidates.validate_candidate(post, packet, projection, "run-123", daily_blog.contracts.V4_MAKER_VALIDATION_POLICY)

	assert issues == []


#============================================
def test_candidate_validation_accepts_compact_project_coverage() -> None:
	"""One compact footer paragraph can cover the active repository."""
	packet = make_packet(with_activity=True)
	projection = make_projection(packet)
	post = valid_post(packet, projection, "run-123", "Evidence matters")

	issues = daily_blog.candidates.validate_candidate(post, packet, projection, "run-123", daily_blog.contracts.V4_MAKER_VALIDATION_POLICY)

	assert issues == []


#============================================
def test_candidate_validation_rejects_wrong_first_narrative_repository_link_target() -> None:
	"""The first repository link must use the projection card's exact canonical URL."""
	packet = make_packet(with_activity=True)
	projection = make_projection(packet)
	post = valid_post(packet, projection, "run-123", "Evidence matters")
	post = post.replace(
		"I connected exact evidence",
		"I connected [vosslab/project](https://example.test/project) to exact evidence",
		1,
	)

	issues = daily_blog.candidates.validate_candidate(post, packet, projection, "run-123", daily_blog.contracts.V4_MAKER_VALIDATION_POLICY)

	assert any("First narrative mention of vosslab/project" in issue for issue in issues)


#============================================
def test_final_candidate_validation_enforces_compact_index_opening() -> None:
	"""The excerpt marker follows exactly one opening paragraph."""
	packet = make_packet()
	projection = make_projection(packet)
	post = valid_post(packet, projection, "run-123", "Evidence matters")
	post = post.replace("<!-- more -->\n\n", "", 1)
	post = post.replace("## Where the work stands", "<!-- more -->\n\n## Where the work stands", 1)

	issues = daily_blog.candidates.validate_candidate(post, packet, projection, "run-123", daily_blog.contracts.V4_MAKER_VALIDATION_POLICY)

	assert any("one opening prose paragraph" in issue for issue in issues)


#============================================
def test_final_candidate_validation_enforces_complete_repository_coverage() -> None:
	"""Every active repository remains visible even when the narrative is selective."""
	packet = make_packet(with_activity=True)
	projection = make_projection(packet)
	post = valid_post(packet, projection, "run-123", "Evidence matters")
	post = post.replace("vosslab/project", "another/project")

	issues = daily_blog.candidates.validate_candidate(post, packet, projection, "run-123", daily_blog.contracts.V4_MAKER_VALIDATION_POLICY)

	assert any("vosslab/project" in issue for issue in issues)


#============================================
def test_candidate_validation_rejects_generic_dated_work_log_title() -> None:
	"""A date-derived Work log label cannot replace a specific editorial title."""
	packet = make_packet()
	projection = make_projection(packet)
	post = valid_post(
		packet,
		projection,
		"run-title",
		f"Work log for {packet.report_date}",
	)

	issues = daily_blog.candidates.validate_candidate(
		post,
		packet,
		projection,
		"run-title",
	)

	assert any("specific thematic title" in issue for issue in issues)


#============================================
def test_author_placeholder_slug_is_canonicalized_from_the_thematic_h1() -> None:
	"""The output adapter resolves the prompt's slug sentinel before hashing candidates."""
	packet = make_packet()
	projection = make_projection(packet)
	config = make_config()

	class PlaceholderRunner:
		def run(self, _route: object, _prompt: str, _repository: str) -> str:
			post = valid_post(packet, projection, "run-slug", "Making authority visible")
			post = post.replace("slug: durable-bundles", "slug: thematic-lowercase-slug")
			return post

	raw = daily_blog.editorial.generate_candidates(
		packet,
		projection,
		"run-slug",
		config,
		runner=PlaceholderRunner(),
	)

	assert all("slug: making-authority-visible" in candidate["post"] for candidate in raw)
	assert all("thematic-lowercase-slug" not in candidate["post"] for candidate in raw)


#============================================
def test_candidate_validation_rejects_unresolved_slug_placeholder() -> None:
	"""The schema validator cannot accept an unresolved output-contract sentinel as content."""
	packet = make_packet()
	projection = make_projection(packet)
	post = valid_post(packet, projection, "run-slug", "Making authority visible").replace(
		"slug: durable-bundles",
		"slug: thematic-lowercase-slug",
	)

	issues = daily_blog.candidates.validate_candidate(post, packet, projection, "run-slug")

	assert any("placeholder" in issue for issue in issues)


#============================================
def test_projected_screenshot_path_is_its_own_provenance_binding() -> None:
	"""A verified projected image path does not need a duplicate evidence comment."""
	base_packet = make_packet()
	screenshot = daily_blog.schema.EvidenceItem.create(
		"screenshot",
		"vosslab/project",
		"a" * 40,
		"docs/interface.png",
		"d" * 40,
		"Screenshot interface.png (4 bytes)",
		"git show",
		asset_path="assets/interface.png",
		publish_path="../../assets/publications/2026-08-23/interface.png",
	)
	packet = daily_blog.schema.EvidencePacket.create(
		base_packet.report_date,
		base_packet.timezone,
		base_packet.complete,
		base_packet.collection_limits,
		base_packet.mirrors,
		base_packet.activity,
		[*base_packet.items, screenshot],
	)
	projection = make_projection(packet)
	post = valid_post(packet, projection, "run-image", "Visible evidence")
	post += f"\n![Interface]({screenshot.publish_path})\n"

	issues = daily_blog.candidates.validate_candidate(
		post,
		packet,
		projection,
		"run-image",
	)

	assert "Embedded screenshots must cite their evidence IDs." not in issues


#============================================
def test_command_route_sends_prompt_through_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Hermes-compatible routes receive full prompts through subprocess stdin."""
	captured = {}

	def fake_run(command: tuple[str, ...], **kwargs: object) -> object:
		captured["command"] = command
		captured["input"] = kwargs["input"]
		return dataclasses.make_dataclass(
			"Result", [("returncode", int), ("stdout", str), ("stderr", str)]
		)(0, "response", "")

	monkeypatch.setattr(daily_blog.routes.subprocess, "run", fake_run)
	route = daily_blog.config.RoleRoute(
		"author", ("hermes", "chat", "--query-file", "/dev/stdin")
	)

	response = daily_blog.routes.CommandRouteRunner().run(
		route,
		"full prompt",
		"/nonexistent/vosslab-test",
	)

	assert captured["input"] == "full prompt"
	assert response == "response"


#============================================
def test_editorial_roles_use_fresh_processes_with_complete_stdin_prompts(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Authors and both referee passes each receive one isolated subprocess input."""
	packet = make_packet()
	projection = make_projection(packet)
	command = daily_blog.config.HERMES_EDITORIAL_ROUTE
	config = dataclasses.replace(
		make_config(),
		author_routes=(
			daily_blog.config.RoleRoute("one", command),
			daily_blog.config.RoleRoute("two", command),
		),
		referee_route=daily_blog.config.RoleRoute("judge", command),
	)
	responses = iter((
		valid_post(packet, projection, "run-processes", "A durable route"),
		valid_post(packet, projection, "run-processes", "A fresh route"),
		"winner A",
		json.dumps({
			"winner": "A",
			"reason": "The approved candidate follows the supplied evidence.",
			"evidence_quality": "high",
			"confidence": 0.8,
		}),
	))
	calls = []

	def fake_run(command: tuple[str, ...], **kwargs: object) -> object:
		calls.append((command, kwargs))
		return dataclasses.make_dataclass(
			"Result", [("returncode", int), ("stdout", str), ("stderr", str)]
		)(0, next(responses), "")

	monkeypatch.setattr(daily_blog.routes.subprocess, "run", fake_run)
	runner = daily_blog.routes.CommandRouteRunner()
	snapshot = daily_blog.editorial.load_prompt_contract_snapshot()
	expected_author_a = daily_blog.editorial.render_author_prompt(
		projection, "run-processes", config.prompt_limits["author_chars"], snapshot=snapshot
	)
	expected_author_b = daily_blog.editorial.render_author_prompt(
		projection, "run-processes", config.prompt_limits["author_chars"], snapshot=snapshot
	)
	raw = daily_blog.editorial.generate_candidates(
		packet, projection, "run-processes", config, runner=runner, snapshot=snapshot
	)
	candidates = daily_blog.editorial.validate_candidates(
		raw, packet, projection, "run-processes"
	)
	mapping = daily_blog.editorial._anonymous_mapping(projection.projection_id, candidates)
	templates = daily_blog.editorial.validate_prompt_templates(snapshot=snapshot)
	cited_ids = set()
	for index in mapping.values():
		cited_ids.update(daily_blog.candidates.evidence_ids_in_post(candidates[index].post))
	expected_referee = templates["referee"].format(
		rubric=templates["rubric"],
		evidence_json=projection.render_context(cited_ids),
		candidate_a=candidates[mapping["A"]].post,
		candidate_b=candidates[mapping["B"]].post,
	)
	expected_repair = templates["repair"].format(response="winner A")
	decision = daily_blog.editorial.select_candidate(
		packet, projection, "run-processes", candidates, config, runner=runner, snapshot=snapshot
	)

	assert decision.winner == "A"
	assert len(calls) == 4
	assert all(call[0] == command for call in calls)
	assert all(call[1]["input"] for call in calls)
	assert all(call[1]["stdout"] == daily_blog.routes.subprocess.PIPE for call in calls)
	assert all(call[1]["text"] is True for call in calls)
	assert calls[0][1]["input"] == expected_author_a
	assert calls[1][1]["input"] == expected_author_b
	assert calls[2][1]["input"] == expected_referee
	assert calls[3][1]["input"] == expected_repair


#============================================
def test_oversized_author_output_is_rejected_without_retaining_payload() -> None:
	"""Unbounded model output becomes one compact invalid candidate artifact."""
	packet = make_packet()
	projection = make_projection(packet)
	config = make_config()

	class OversizedRunner:
		def run(self, _route: object, _prompt: str, _repository: str) -> str:
			return "x" * 1000000

	raw = daily_blog.editorial.generate_candidates(
		packet, projection, "run-oversized", config, runner=OversizedRunner()
	)

	assert all(not candidate["post"] for candidate in raw)
	assert all("character budget" in candidate["generation_error"] for candidate in raw)


#============================================
def test_referee_prompt_budget_blocks_without_route_call() -> None:
	"""An over-limit complete referee prompt blocks publication before route execution."""
	packet = make_packet()
	projection = make_projection(packet)
	config = dataclasses.replace(
		make_config(),
		prompt_limits={"author_chars": 20000, "referee_chars": 100},
	)
	posts = [
		valid_post(packet, projection, "run-budget", "Exact evidence"),
		valid_post(packet, projection, "run-budget", "Durable evidence"),
	]
	candidates = [
		daily_blog.editorial.CandidateResult(
			str(index),
			projection.projection_id,
			post,
			daily_blog.io_utils.sha256_text(post),
			True,
			(),
		)
		for index, post in enumerate(posts)
	]

	class UncalledRunner:
		def run(self, _route: object, _prompt: str, _repository: str) -> str:
			raise AssertionError("referee route should remain uncalled")

	with pytest.raises(daily_blog.editorial.EditorialBlockedError, match="referee prompt"):
		daily_blog.editorial.select_candidate(
			packet,
			projection,
			"run-budget",
			candidates,
			config,
			runner=UncalledRunner(),
		)


#============================================
def test_prompt_contract_identity_binds_the_exact_template_bytes(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Editorial cache identity changes when tuned prompt content changes."""
	templates = {
		"author": "author contract",
		"referee": "referee contract",
		"repair": "repair contract",
		"rubric": "rubric contract",
	}
	monkeypatch.setattr(
		daily_blog.editorial,
		"validate_prompt_templates",
		lambda *_args, **_kwargs: templates,
	)
	first = daily_blog.editorial.prompt_contract_identity()
	templates["author"] = "author contract with one deliberate revision"
	second = daily_blog.editorial.prompt_contract_identity()

	assert first != second


#============================================
def test_prompt_snapshot_uses_one_registered_example_read_for_identity_and_rendering(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A changing resource loader cannot split the prompt bytes from their identity."""
	contract = daily_blog.contracts.V4_THREE_EXAMPLES_CORPUS_V2_CONTRACT
	first_text = (
		"<!-- editorial-example: aug-23 -->\nB\n<!-- /editorial-example -->\n"
		"<!-- editorial-example: corpus-quiet-til -->\n"
		+ daily_blog.contracts.EXTERNAL_EXAMPLE_BLOCKS["corpus-quiet-til"]
		+ "<!-- /editorial-example -->\n"
		+ "<!-- editorial-example: corpus-selectivity-ghostty -->\n"
		+ daily_blog.contracts.EXTERNAL_EXAMPLE_BLOCKS["corpus-selectivity-ghostty"]
		+ "<!-- /editorial-example -->\n"
	)
	second_text = first_text.replace("B\n<!-- /editorial-example -->", "Changed B\n<!-- /editorial-example -->")
	reads = [first_text, second_text]
	monkeypatch.setattr(
		daily_blog.editorial,
		"load_prompt",
		lambda name: "{examples}\n{evidence_json}\n## Output contract" if "author" in name else (
			"{candidate_a}{candidate_b}\n## Output contract" if "referee" in name else "Return JSON."
		),
	)
	monkeypatch.setattr(
		daily_blog.editorial,
		"load_plain_prompt_resource",
		lambda _name: (reads[0], reads.pop(0).encode("utf-8")),
	)
	snapshot = daily_blog.editorial.load_prompt_contract_snapshot(contract)
	packet = make_packet()
	prompt = daily_blog.editorial.render_author_prompt(
		make_projection(packet), "run-snapshot", 20000, snapshot=snapshot
	)
	identity = daily_blog.editorial.prompt_contract_identity(snapshot=snapshot)
	tampered_templates = tuple(
		(name, text + " altered" if name == "author" else text)
		for name, text in snapshot.templates
	)

	assert "B\n\n\n## Corpus excerpt: quiet-day TIL" in prompt
	assert "## Corpus excerpt: selectivity in a devlog" in prompt
	assert identity["examples"]["sha256"] == daily_blog.io_utils.sha256_bytes(snapshot.example_bytes)
	with pytest.raises(RuntimeError, match="trusted factory|integrity binding"):
		daily_blog.editorial.validate_snapshot(
			dataclasses.replace(snapshot, templates=tampered_templates)
		)
	for copied in (copy.copy(snapshot), copy.deepcopy(snapshot)):
		with pytest.raises(RuntimeError, match="not trusted|trusted factory"):
			daily_blog.editorial.validate_snapshot(copied)
	with pytest.raises(RuntimeError, match="not trusted|trusted factory"):
		daily_blog.editorial.validate_snapshot(
			dataclasses.replace(snapshot, contract=daily_blog.contracts.V4_ONE_EXAMPLE_CONTRACT)
		)
	with pytest.raises(RuntimeError, match="not trusted|trusted factory"):
		daily_blog.editorial.validate_snapshot(
			dataclasses.replace(snapshot, validation_policy_version="v2")
		)
	with pytest.raises(RuntimeError, match="contract conflicts"):
		daily_blog.editorial.prompt_contract_identity(
			contract=daily_blog.contracts.V4_ONE_EXAMPLE_CONTRACT,
			snapshot=snapshot,
		)
	with pytest.raises(RuntimeError, match="selection conflicts"):
		daily_blog.editorial.prompt_contract_identity(
			selection=daily_blog.contracts.V4_ONE_EXAMPLE_SELECTION,
			snapshot=snapshot,
		)


#============================================
def test_contract_registry_rejects_freeform_contracts_and_selections() -> None:
	"""Only registered arms and their immutable selections reach the prompt boundary."""
	with pytest.raises(RuntimeError, match="trusted registry"):
		daily_blog.contracts.resolve_contract(
		dataclasses.replace(daily_blog.contracts.V3_EDITORIAL_CONTRACT, name="unregistered")
	)
	with pytest.raises(RuntimeError, match="registered contract selection"):
		daily_blog.contracts.resolve_selection(
			daily_blog.contracts.V4_ONE_EXAMPLE_CONTRACT,
			daily_blog.contracts.V4_THREE_EXAMPLES_CORPUS_V2_SELECTION,
		)
	with pytest.raises(RuntimeError, match="registered contract selection"):
		daily_blog.contracts.resolve_selection(
			daily_blog.contracts.V4_ONE_EXAMPLE_CONTRACT,
			daily_blog.contracts.ExampleSelection(
				"unregistered",
				daily_blog.contracts.V4_ONE_EXAMPLE,
				"v4-voice",
				("aug-22",),
			),
		)
	with pytest.raises(RuntimeError, match="bare filename"):
		daily_blog.contracts.ExampleResource("unsafe", "../outside.md", ("aug-22",))
	for loader in (
		daily_blog.editorial.load_prompt,
		daily_blog.editorial.load_plain_prompt_resource,
	):
		with pytest.raises(RuntimeError, match="allowlisted|bare trusted filename"):
			loader("../../source_me.sh")
	for loader, name in (
		(daily_blog.editorial.load_prompt, "bhost.txt"),
		(daily_blog.editorial.load_plain_prompt_resource, "bhost.txt"),
		(daily_blog.editorial.load_prompt, "daily_blog_voice_examples_v4.md"),
		(daily_blog.editorial.load_plain_prompt_resource, "daily_blog_author_v3.txt"),
	):
		with pytest.raises(RuntimeError, match="allowlisted"):
			loader(name)
	assert daily_blog.editorial.load_evaluation_prompt(
		"daily_blog_shadow_evaluator_v1.txt"
	)
	assert daily_blog.editorial.load_evaluation_prompt(
		"daily_blog_shadow_evaluator_repair_v1.txt"
	)
	with pytest.raises(RuntimeError, match="allowlisted"):
		daily_blog.editorial.load_evaluation_prompt("daily_blog_rubric_calibrator_v4.txt")
	with pytest.raises(RuntimeError, match="allowlisted"):
		daily_blog.editorial.load_evaluation_prompt("daily_blog_author_v3.txt")
	with pytest.raises(RuntimeError, match="not trusted"):
		daily_blog.editorial.validate_snapshot(
			daily_blog.editorial.PromptContractSnapshot(
				daily_blog.contracts.V3_EDITORIAL_CONTRACT,
				None,
				(),
				(),
				b"",
				b"",
				"",
			)
		)

"""Editorial isolation, prompt, referee, and provisional behavior tests."""

# Standard Library
import json
import dataclasses
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.config
import daily_blog.schema
import daily_blog.routes
import daily_blog.editorial
import daily_blog.candidates


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
			)
		)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23",
		"America/Chicago",
		True,
		{
			"author_context_chars": 20000,
			"referee_context_chars": 30000,
		},
		[],
		activity,
		[item],
	)
	return packet


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
		repository_urls=(),
		identity_names=("Author",),
		identity_emails=(),
		author_routes=(
			daily_blog.config.RoleRoute("one", ("fake",)),
			daily_blog.config.RoleRoute("two", ("fake",)),
		),
		referee_route=daily_blog.config.RoleRoute("judge", ("fake",)),
		evidence_budgets={"author_context_chars": 20000, "referee_context_chars": 30000},
	)
	return config


#============================================
def valid_post(
	packet: daily_blog.schema.EvidencePacket,
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
	intro = (intro_sentence * 7).strip()
	first_section = (detail_sentence * detail_repetitions).strip()
	second_section = (detail_sentence * detail_repetitions).strip()
	repositories = ", ".join(activity.repository for activity in packet.activity)
	coverage_subject = repositories if repositories else "the verified project"
	post = (
		"---\n"
		+ f"date: {packet.report_date}\n"
		+ "slug: durable-bundles\n"
		+ "publication_quality: final\n"
		+ f"generator_run: {run_id}\n"
		+ "evidence_manifest: evidence.json\n"
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
	def __init__(self, packet: daily_blog.schema.EvidencePacket, run_id: str) -> None:
		"""Retain deterministic response context."""
		self.packet = packet
		self.run_id = run_id
		self.prompts = []
		self.referee_calls = 0

	#============================================
	def run(self, route: daily_blog.config.RoleRoute, prompt: str, _repository: str) -> str:
		"""Return route-specific deterministic output."""
		self.prompts.append((route.name, prompt))
		if route.name == "one":
			return valid_post(self.packet, self.run_id, "Exact evidence wins")
		if route.name == "two":
			return valid_post(self.packet, self.run_id, "Bundles preserve the day")
		self.referee_calls += 1
		if self.referee_calls == 1:
			return "winner A"
		return json.dumps(
			{
				"winner": "NONE",
				"reason": "The provisional record stays closest to the compact evidence.",
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
	templates = {
		daily_blog.editorial.AUTHOR_TEMPLATE_NAME: (
			f"Use {{evidence_json}}.\n\n## Output contract\n\n{instruction}"
		),
		daily_blog.editorial.REFEREE_TEMPLATE_NAME: (
			"Compare {candidate_a} and {candidate_b}.\n\n## Output contract"
		),
		daily_blog.editorial.REPAIR_TEMPLATE_NAME: "Return the structured verdict.",
		daily_blog.editorial.RUBRIC_NAME: "Prefer factual fidelity.",
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

	with pytest.raises(RuntimeError, match="instruction source"):
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

	with pytest.raises(RuntimeError, match="--ignore-rules"):
		daily_blog.config.load_config(str(settings_path))


#============================================
def test_two_authors_share_evidence_and_referee_repair_selects_provisional() -> None:
	"""Malformed referee output receives one repair and can choose NONE safely."""
	packet = make_packet()
	config = make_config()
	runner = FakeRunner(packet, "run-123")

	raw = daily_blog.editorial.generate_candidates(packet, "run-123", config, runner=runner)
	candidates = daily_blog.editorial.validate_candidates(raw, packet, "run-123")
	decision = daily_blog.editorial.select_candidate(
		packet, "run-123", candidates, config, runner=runner
	)

	assert runner.prompts[0][1] == runner.prompts[1][1]
	assert decision.publication_quality == "provisional"


#============================================
def test_candidate_validation_rejects_unknown_provenance() -> None:
	"""A fluent post remains ineligible when its factual provenance is fabricated."""
	packet = make_packet()
	post = valid_post(packet, "run-123", "Evidence matters").replace(
		packet.items[0].evidence_id,
		"ev-unknown",
	)

	issues = daily_blog.candidates.validate_candidate(post, packet, "run-123")

	assert any("unknown evidence" in issue for issue in issues)


#============================================
def test_candidate_validation_requires_provenance_in_admonitions() -> None:
	"""Admonition prose remains factual content and requires an evidence reference."""
	packet = make_packet()
	post = valid_post(packet, "run-123", "Evidence matters") + (
		"\n!!! note \"Current state\"\n\n    The release is ready.\n"
	)

	issues = daily_blog.candidates.validate_candidate(post, packet, "run-123")

	assert any("Every factual prose paragraph" in issue for issue in issues)


#============================================
def test_final_candidate_validation_enforces_house_style_shape() -> None:
	"""A thin one-section work log cannot pass as the final narrative article."""
	packet = make_packet()
	post = valid_post(packet, "run-123", "Evidence matters")
	post = post.replace("## Where the work stands\n\n", "")
	post = post.replace("I followed the strongest development thread", "I summarized the work", 18)

	issues = daily_blog.candidates.validate_candidate(post, packet, "run-123")

	assert any("narrative H2" in issue for issue in issues)


#============================================
def test_final_candidate_validation_enforces_narrative_word_budget() -> None:
	"""A structurally complete but thin candidate remains editorially ineligible."""
	packet = make_packet()
	post = valid_post(packet, "run-123", "Evidence matters", detail_repetitions=1)

	issues = daily_blog.candidates.validate_candidate(post, packet, "run-123")

	assert any("narrative" in issue for issue in issues)


#============================================
def test_final_candidate_validation_enforces_compact_index_opening() -> None:
	"""The excerpt marker follows exactly one opening paragraph."""
	packet = make_packet()
	post = valid_post(packet, "run-123", "Evidence matters")
	post = post.replace("<!-- more -->\n\n", "", 1)
	post = post.replace("## Where the work stands", "<!-- more -->\n\n## Where the work stands", 1)

	issues = daily_blog.candidates.validate_candidate(post, packet, "run-123")

	assert any("one opening prose paragraph" in issue for issue in issues)


#============================================
def test_final_candidate_validation_enforces_complete_repository_coverage() -> None:
	"""Every active repository remains visible even when the narrative is selective."""
	packet = make_packet(with_activity=True)
	post = valid_post(packet, "run-123", "Evidence matters")
	post = post.replace("vosslab/project", "another/project")

	issues = daily_blog.candidates.validate_candidate(post, packet, "run-123")

	assert any("vosslab/project" in issue for issue in issues)


#============================================
def test_provisional_candidate_keeps_its_intended_compact_shape() -> None:
	"""The evidence-first provisional state remains concise by design."""
	packet = make_packet()
	post = daily_blog.candidates.provisional_post(packet, "run-provisional")

	issues = daily_blog.candidates.validate_candidate(
		post,
		packet,
		"run-provisional",
		expected_quality="provisional",
	)

	assert issues == []


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
def test_oversized_author_output_is_rejected_without_retaining_payload() -> None:
	"""Unbounded model output becomes one compact invalid candidate artifact."""
	packet = make_packet()
	config = make_config()

	class OversizedRunner:
		def run(self, _route: object, _prompt: str, _repository: str) -> str:
			return "x" * 1000000

	raw = daily_blog.editorial.generate_candidates(
		packet, "run-oversized", config, runner=OversizedRunner()
	)

	assert all(not candidate["post"] for candidate in raw)
	assert all("character budget" in candidate["generation_error"] for candidate in raw)


#============================================
def test_referee_prompt_budget_falls_back_to_provisional_without_route_call() -> None:
	"""A complete packet stays publishable when the total referee prompt is over budget."""
	packet = make_packet()
	config = dataclasses.replace(
		make_config(),
		evidence_budgets={"author_context_chars": 20000, "referee_context_chars": 100},
	)
	posts = [
		valid_post(packet, "run-budget", "Exact evidence"),
		valid_post(packet, "run-budget", "Durable evidence"),
	]
	candidates = [
		daily_blog.editorial.CandidateResult(
			str(index), post, "a" * 64, True, ()
		)
		for index, post in enumerate(posts)
	]

	class UncalledRunner:
		def run(self, _route: object, _prompt: str, _repository: str) -> str:
			raise AssertionError("referee route should remain uncalled")

	decision = daily_blog.editorial.select_candidate(
		packet, "run-budget", candidates, config, runner=UncalledRunner()
	)

	assert decision.publication_quality == "provisional"
	assert "budget" in decision.reason

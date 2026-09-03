"""Editorial isolation, prompt, validation, and final referee behavior tests."""

# Standard Library
import json
import dataclasses
import pathlib
import subprocess

# PIP3 modules
import pytest

# local repo modules
import daily_blog.config
import daily_blog.editorial_stage_config
import daily_blog.schema
import daily_blog.repository_contracts
import daily_blog.routes
import daily_blog.editorial
import daily_blog.candidates
import daily_blog.prompt_registry.definitions
import daily_blog.prompt_registry.editorial_contracts
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
		author_routes=(
			daily_blog.editorial_stage_config.RoleRoute("one", ("fake",)),
			daily_blog.editorial_stage_config.RoleRoute("two", ("fake",)),
		),
		referee_route=daily_blog.editorial_stage_config.RoleRoute("judge", ("fake",)),
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
	def run(self, route: daily_blog.editorial_stage_config.RoleRoute, prompt: str, _repository: str) -> str:
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
		"        command: [hermes, chat, --provider, openai-codex, --skills, daily-github-blogger, --query-file, -, --ignore-rules, --quiet]\n"
		"      - name: two\n"
		"        command: [hermes, chat, --provider, openai-codex, --query-file, -, --ignore-rules, --quiet]\n"
		"    referee:\n"
		"      name: judge\n"
		"      command: [hermes, chat, --provider, openai-codex, --query-file, -, --ignore-rules, --quiet]\n",
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
		"        command: [hermes, chat, --provider, openai-codex, --query-file, -, --quiet]\n"
		"      - name: two\n"
		"        command: [hermes, chat, --provider, openai-codex, --query-file, -, --ignore-rules, --quiet]\n"
		"    referee:\n"
		"      name: judge\n"
		"      command: [hermes, chat, --provider, openai-codex, --query-file, -, --ignore-rules, --quiet]\n",
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

	author_prompts = {
		name: prompt for name, prompt in runner.prompts if name in {"one", "two"}
	}
	assert author_prompts["one"] == author_prompts["two"]
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

	verdict = daily_blog.editorial.parse_referee_verdict(response, {"A"})

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
		post, packet, projection, "run-123", daily_blog.prompt_registry.editorial_contracts.V4_MAKER_VALIDATION_POLICY
	)

	assert any("unknown evidence" in issue for issue in issues)


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
def test_command_route_sends_prompt_through_stdin(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: pathlib.Path,
) -> None:
	"""Hermes-compatible routes receive full prompts through subprocess stdin."""
	captured = {}

	def fake_run(command: tuple[str, ...], **kwargs: object) -> object:
		captured["command"] = command
		captured["input"] = kwargs["input"]
		captured["shell"] = kwargs["shell"]
		return dataclasses.make_dataclass(
			"Result", [("returncode", int), ("stdout", str), ("stderr", str)]
		)(0, "response", "")

	monkeypatch.setattr(daily_blog.routes.subprocess, "run", fake_run)
	route = daily_blog.editorial_stage_config.RoleRoute(
		"author", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE
	)

	response = daily_blog.routes.CommandRouteRunner().run(
		route,
		"full prompt",
		str(tmp_path),
	)

	assert captured["input"] == "full prompt"
	assert response == "response"
	assert captured["shell"] is False


#============================================
def test_command_route_rejects_unsealed_command_before_execution(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: pathlib.Path,
) -> None:
	"""The process sink accepts only the sealed Hermes route."""
	called = False

	def fake_run(*_args: object, **_kwargs: object) -> object:
		nonlocal called
		called = True
		raise AssertionError("Invalid route must not execute.")

	monkeypatch.setattr(daily_blog.routes.subprocess, "run", fake_run)
	route = daily_blog.editorial_stage_config.RoleRoute("author", ("not-hermes",))

	with pytest.raises(RuntimeError, match="must invoke hermes chat"):
		daily_blog.routes.CommandRouteRunner().run(route, "prompt", str(tmp_path))

	assert not called


#============================================
def test_command_route_redacts_failed_process_output(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: pathlib.Path,
) -> None:
	"""External stdout and stderr never enter the route failure surfaced to callers."""
	secret = "account-label api-key private-prompt"

	def fake_run(_command: tuple[str, ...], **_kwargs: object) -> object:
		return dataclasses.make_dataclass(
			"Result", [("returncode", int), ("stdout", str), ("stderr", str)]
		)(2, secret, secret)

	monkeypatch.setattr(daily_blog.routes.subprocess, "run", fake_run)
	route = daily_blog.editorial_stage_config.RoleRoute(
		"secret-route-name", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE
	)

	with pytest.raises(RuntimeError) as caught:
		daily_blog.routes.CommandRouteRunner().run(route, secret, str(tmp_path))

	assert secret not in str(caught.value)
	assert route.name not in str(caught.value)


@pytest.mark.parametrize(
	("route_error", "expected_type"),
	(
		(
			subprocess.TimeoutExpired(("hermes", "chat", "private-prompt"), 1200),
			TimeoutError,
		),
		(
			OSError("credential path /private/account"),
			OSError,
		),
	),
)
def test_command_route_redacts_process_exceptions(
	monkeypatch: pytest.MonkeyPatch,
	route_error: BaseException,
	expected_type: type[BaseException],
	tmp_path: pathlib.Path,
) -> None:
	"""Process-start and timeout failures expose stable operational categories only."""
	def fake_run(_command: tuple[str, ...], **_kwargs: object) -> object:
		raise route_error

	monkeypatch.setattr(daily_blog.routes.subprocess, "run", fake_run)
	route = daily_blog.editorial_stage_config.RoleRoute(
		"author", daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE
	)

	with pytest.raises(expected_type) as caught:
		daily_blog.routes.CommandRouteRunner().run(
			route,
			"private-prompt",
			str(tmp_path),
		)

	assert str(route_error) not in str(caught.value)
	assert caught.value.__cause__ is None


#============================================
def test_editorial_roles_isolate_prompts_via_stdin(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: pathlib.Path,
) -> None:
	"""Editorial route inputs use stdin and isolate process output handling."""
	packet = make_packet()
	projection = make_projection(packet)
	command = daily_blog.editorial_stage_config.HERMES_EDITORIAL_ROUTE
	config = dataclasses.replace(
		make_config(),
		daily_blog_repository=str(tmp_path),
		author_routes=(
			daily_blog.editorial_stage_config.RoleRoute("one", command),
			daily_blog.editorial_stage_config.RoleRoute("two", command),
		),
		referee_route=daily_blog.editorial_stage_config.RoleRoute("judge", command),
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
	raw = daily_blog.editorial.generate_candidates(
		packet, projection, "run-processes", config, runner=runner, snapshot=snapshot
	)
	candidates = daily_blog.editorial.validate_candidates(
		raw, packet, projection, "run-processes"
	)
	decision = daily_blog.editorial.select_candidate(
		packet, projection, "run-processes", candidates, config, runner=runner, snapshot=snapshot
	)

	assert decision.winner == "A"
	assert calls
	assert all(call[0] == command for call in calls)
	assert all(call[1]["input"] for call in calls)
	assert all(call[1]["stdout"] == daily_blog.routes.subprocess.PIPE for call in calls)
	assert all(call[1]["text"] is True for call in calls)


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
def test_contract_registry_rejects_freeform_contracts_and_selections() -> None:
	"""Only registered values reach the prompt boundary."""
	with pytest.raises(RuntimeError, match="trusted registry"):
		daily_blog.prompt_registry.editorial_contracts.resolve_contract(
		dataclasses.replace(daily_blog.prompt_registry.editorial_contracts.active_contract(), name="unregistered")
	)
	with pytest.raises(RuntimeError, match="trusted registry"):
		daily_blog.prompt_registry.editorial_contracts.resolve_selection(
		daily_blog.prompt_registry.editorial_contracts.V4_THREE_EXAMPLES_CORPUS_V2_SELECTION,
		daily_blog.prompt_registry.definitions.ExampleSelection(
			"unregistered",
			daily_blog.prompt_registry.editorial_contracts.V4_THREE_EXAMPLES_CORPUS_V2,
			"v4-voice",
			("aug-23",),
		),
	)
	with pytest.raises(RuntimeError, match="bare filename"):
		daily_blog.prompt_registry.definitions.ExampleResource("unsafe", "../outside.md", ("aug-22",))
	with pytest.raises(RuntimeError, match="not trusted"):
		daily_blog.editorial.validate_snapshot(
			daily_blog.editorial.PromptContractSnapshot(
				daily_blog.prompt_registry.editorial_contracts.active_contract(),
				None,
				(),
				(),
				b"",
				b"",
				"",
			)
		)


#============================================
def test_v4_snapshot_rejects_unissued_or_cross_set_prompt_views() -> None:
	"""The cache-owning V4 snapshot accepts only its issued registry view."""
	for prompt_set in (
		object.__new__(daily_blog.prompt_registry.loader.LoadedPromptSet),
		daily_blog.prompt_registry.loader.load_prompt_set(
			daily_blog.prompt_registry.definitions.REPOSITORY_OUTLINE_PROMPT_SET,
		),
	):
		with pytest.raises(RuntimeError, match="issued|does not match"):
			daily_blog.editorial.load_prompt_contract_snapshot(prompt_set=prompt_set)

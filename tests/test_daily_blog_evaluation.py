"""Historical shadow evaluation remains inspectable and outside publication ownership."""

# Standard Library
import dataclasses
import json
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.schema
import daily_blog.config
import daily_blog.evaluation


#============================================
def make_packet() -> daily_blog.schema.EvidencePacket:
	"""Return one complete primary-evidence packet for a shadow comparison."""
	item = daily_blog.schema.EvidenceItem.create(
		"dated_changelog",
		"vosslab/project",
		"a" * 40,
		"docs/CHANGELOG.md",
		"b" * 40,
		"## 2026-08-23\n\n- Added exact bundle validation.\n",
		"git show",
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23",
		"America/Chicago",
		True,
		{},
		[],
		[],
		[item],
	)
	return packet


#============================================
def make_config(tmp_path: pathlib.Path) -> daily_blog.config.DailyBlogConfig:
	"""Return isolated fake routes and a temporary shadow output root."""
	config = daily_blog.config.DailyBlogConfig(
		settings_path="settings.yaml",
		output_root=str(tmp_path),
		output_owner="vosslab",
		report_timezone="America/Chicago",
		daily_blog_repository=str(tmp_path),
		mirror_cache_root=str(tmp_path / "mirrors"),
		identity_names=("Author",),
		identity_emails=(),
		author_routes=(
			daily_blog.config.RoleRoute("one", ("fake",)),
			daily_blog.config.RoleRoute("two", ("fake",)),
		),
		referee_route=daily_blog.config.RoleRoute("judge", ("fake",)),
		collection_limits={},
		projection_limits={
			"context_chars": 16000,
			"excerpt_chars": 2000,
			"commit_subject_chars": 160,
		},
		prompt_limits={"author_chars": 30000, "referee_chars": 50000},
		allow_shadow_model_data_sharing=True,
	)
	return config


#============================================
def valid_post(
	packet: daily_blog.schema.EvidencePacket,
	run_id: str,
	title: str,
) -> str:
	"""Return one final candidate matching the deterministic house shape."""
	evidence_id = packet.items[0].evidence_id
	intro = (
		"I found that exact evidence makes a daily account more useful because each technical "
		"decision can retain its practical meaning for a returning reader. " * 3
	).strip()
	detail = (
		"I connected the durable publication boundary to the concrete implementation, explained "
		"why the change matters, and recorded where the verified work stands today. " * 7
	).strip()
	post = (
		"---\n"
		+ f"date: {packet.report_date}\n"
		+ "slug: exact-evidence\n"
		+ f"generator_run: {run_id}\n"
		+ "evidence_manifest: evidence.json\n"
		+ "editorial_projection: editorial_projection.json\n"
		+ "---\n\n"
		+ f"# {title}\n\n"
		+ f"{intro} <!-- evidence: {evidence_id} -->\n\n"
		+ "<!-- more -->\n\n"
		+ "## Exact evidence owns the account\n\n"
		+ f"{detail} <!-- evidence: {evidence_id} -->\n\n"
		+ "## Where attention stands\n\n"
		+ f"{detail} <!-- evidence: {evidence_id} -->\n\n"
		+ "## Project coverage\n\n"
		+ f"I recorded the project evidence. <!-- evidence: {evidence_id} -->\n"
	)
	return post


class FakeRunner:
	"""Return two valid drafts, one winner, and one semantic scorecard."""

	#============================================
	def __init__(self, packet: daily_blog.schema.EvidencePacket) -> None:
		"""Retain packet context and observed calls."""
		self.packet = packet
		self.calls = []

	#============================================
	def run(self, route: daily_blog.config.RoleRoute, prompt: str, _repository: str) -> str:
		"""Return the response required by each versioned prompt."""
		self.calls.append((route.name, prompt))
		if "# Daily work-log shadow evaluator" in prompt:
			return json.dumps(
				{
					"factual_grounding": 5,
					"changelog_use": 5,
					"thematic_structure": 4,
					"reader_interest": 4,
					"house_style_match": 4,
					"verdict": "close",
					"reason": "The generated post preserves the reference structure and exact evidence.",
				}
			)
		if route.name == "one":
			return valid_post(
				self.packet,
				self._run_id(prompt),
				"Exact evidence tells the story",
			)
		if route.name == "two":
			return valid_post(
				self.packet,
				self._run_id(prompt),
				"The durable daily boundary",
			)
		return json.dumps(
			{
				"winner": "A",
				"reason": "Candidate A has the clearer evidence-grounded development thread.",
				"evidence_quality": "high",
				"confidence": 0.9,
			}
		)

	#============================================
	def _run_id(self, prompt: str) -> str:
		"""Extract the supplied run identity from author front-matter instructions."""
		line = next(line for line in prompt.splitlines() if line.startswith("generator_run: "))
		return line.split(": ", 1)[1]

#============================================
def test_shadow_evaluation_writes_inspectable_artifacts(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A shadow comparison retains its semantic result in an isolated namespace."""
	packet = make_packet()
	config = make_config(tmp_path)
	reference = valid_post(
		packet,
		"historical-reference",
		"Making the boundary real",
	)
	monkeypatch.setattr(
		daily_blog.evaluation,
		"_new_shadow_id",
		lambda: "20260823T120000Z-0123456789",
	)

	shadow_path, scorecard = daily_blog.evaluation.evaluate_packet(
		config,
		packet,
		{},
		reference,
		runner=FakeRunner(packet),
	)

	assert scorecard["semantic_assessment"]["verdict"] == "close"
	assert (pathlib.Path(shadow_path) / "scorecard.json").is_file()


#============================================
def test_shadow_result_parser_rejects_unbounded_scores() -> None:
	"""Semantic opinions enter the scorecard only through the exact typed scale."""
	response = json.dumps(
		{
			"factual_grounding": 6,
			"changelog_use": 5,
			"thematic_structure": 4,
			"reader_interest": 4,
			"house_style_match": 4,
			"verdict": "close",
			"reason": "Out of range.",
		}
	)

	with pytest.raises(RuntimeError, match="one through five"):
		daily_blog.evaluation.parse_evaluator_result(response)


#============================================
def test_shadow_semantic_route_requires_explicit_data_sharing(tmp_path: pathlib.Path) -> None:
	"""Historical source and evidence cross a model route only after explicit opt-in."""
	packet = make_packet()
	config = dataclasses.replace(
		make_config(tmp_path),
		allow_shadow_model_data_sharing=False,
	)
	runner = FakeRunner(packet)

	with pytest.raises(RuntimeError, match="external_model_data_sharing: true"):
		daily_blog.evaluation.evaluate_packet(
			config,
			packet,
			{},
			valid_post(packet, "reference", "Reference account"),
			runner=runner,
		)

	assert runner.calls == []

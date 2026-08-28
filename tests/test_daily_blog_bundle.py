"""Publication bundle immutability and hash contract tests."""

# Standard Library
import json
import re
import pathlib

# local repo modules
import daily_blog.schema
import daily_blog.bundles
import daily_blog.editorial
import daily_blog.io_utils
import daily_blog.projection


#============================================
def make_projection(
	packet: daily_blog.schema.EvidencePacket,
) -> daily_blog.schema.EditorialProjection:
	"""Return one compact immutable projection for bundle tests."""
	limits = {
		"context_chars": 8000,
		"excerpt_chars": 1000,
		"commit_subject_chars": 120,
	}
	return daily_blog.projection.build_projection(packet, limits)


#============================================
def test_bundle_writer_hashes_complete_artifacts_and_updates_latest(
	tmp_path: pathlib.Path,
) -> None:
	"""A complete staged run becomes an immutable bundle with a stable date pointer."""
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/project", "a" * 40, "", "", "located work", "git show"
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item]
	)
	projection = make_projection(packet)
	post = "approved selected post\n"
	decision = daily_blog.editorial.EditorialDecision(
		winner="A",
		reason="Candidate A is approved for final publication.",
		evidence_quality="medium",
		confidence=0.8,
		projection_id=projection.projection_id,
		post=post,
		anonymous_mapping={"A": 0},
	)
	candidate = daily_blog.editorial.CandidateResult(
		private_route="author",
		projection_id=projection.projection_id,
		post=post,
		post_hash=daily_blog.io_utils.sha256_text(post),
		valid=True,
		issues=(),
	)
	writer = daily_blog.bundles.BundleWriter(str(tmp_path), "vosslab", "f" * 64)

	bundle_path, bundle = writer.write(
		"run-one", packet, projection, {}, [candidate, candidate], decision
	)

	with open(f"{bundle_path}/bundle.json", "r", encoding="utf-8") as handle:
		written = json.load(handle)
	latest_path = tmp_path / "vosslab" / "daily_blog" / packet.report_date / "latest.json"
	with open(latest_path, "r", encoding="utf-8") as handle:
		latest = json.load(handle)
	assert written["bundle_id"] == daily_blog.bundles.bundle_identity(written)
	assert (latest["run_id"], latest["bundle_id"], bundle["editorial_projection"]["projection_id"]) == (
		"run-one",
		bundle["bundle_id"],
		projection.projection_id,
	)


#============================================
def test_bundle_records_anonymous_winner_mapping_and_exact_post_hash(
	tmp_path: pathlib.Path,
) -> None:
	"""The publisher can prove which anonymous valid candidate became the final post."""
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/project", "a" * 40, "", "", "located work", "git show"
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item]
	)
	projection = make_projection(packet)
	post = "final selected post\n"
	candidates = [
		daily_blog.editorial.CandidateResult(
			"one",
			projection.projection_id,
			"other\n",
			"1" * 64,
			False,
			("invalid",),
		),
		daily_blog.editorial.CandidateResult(
			"two",
			projection.projection_id,
			post,
			daily_blog.io_utils.sha256_text(post),
			True,
			(),
		),
	]
	decision = daily_blog.editorial.EditorialDecision(
		winner="A",
		reason="Candidate A matches the exact evidence.",
		evidence_quality="high",
		confidence=0.9,
		projection_id=projection.projection_id,
		post=post,
		anonymous_mapping={"A": 1},
	)
	writer = daily_blog.bundles.BundleWriter(str(tmp_path), "vosslab", "f" * 64)

	_bundle_path, bundle = writer.write(
		"run-final", packet, projection, {}, candidates, decision
	)

	assert bundle["referee"]["anonymous_mapping"] == {"A": "candidate_2"}
	assert bundle["post"]["sha256"] == candidates[1].post_hash


#============================================
def write_generator_contract(root: pathlib.Path) -> None:
	"""Write one minimal producer source, prompt, support, and settings contract."""
	(root / "pipeline" / "daily_blog").mkdir(parents=True)
	(root / "pipeline" / "podlib").mkdir(parents=True)
	(root / "pipeline" / "prompts").mkdir(parents=True)
	(root / "pipeline" / "daily_blog" / "module.py").write_text(
		"VALUE = 'source-one'\n",
		encoding="utf-8",
	)
	for relative_path in daily_blog.bundles.GENERATOR_SUPPORT_PATHS:
		(root / relative_path).write_text("VALUE = 'support'\n", encoding="utf-8")
	for relative_path in daily_blog.bundles.GENERATOR_PROMPT_PATHS:
		(root / relative_path).write_text("Prompt contract one.\n", encoding="utf-8")
	(root / "settings.yaml").write_text("daily_blog: {}\n", encoding="utf-8")


#============================================
def test_generator_revision_fingerprints_dirty_source_and_exact_prompt_bytes(
	tmp_path: pathlib.Path,
) -> None:
	"""Uncommitted source or prompt changes produce a new lowercase SHA-256 generator identity."""
	write_generator_contract(tmp_path)
	first = daily_blog.bundles.generator_revision(str(tmp_path))
	(tmp_path / "pipeline" / "daily_blog" / "module.py").write_text(
		"VALUE = 'source-two'\n",
		encoding="utf-8",
	)
	second = daily_blog.bundles.generator_revision(str(tmp_path))
	(tmp_path / daily_blog.bundles.GENERATOR_PROMPT_PATHS[0]).write_text(
		"Prompt contract two.\n",
		encoding="utf-8",
	)
	third = daily_blog.bundles.generator_revision(str(tmp_path))

	assert re.fullmatch(r"[0-9a-f]{64}", first) is not None
	assert first != second and second != third and first != third

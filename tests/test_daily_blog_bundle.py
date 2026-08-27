"""Publication bundle immutability and hash contract tests."""

# Standard Library
import json
import pathlib

# PIP3 modules
import pytest

# local repo modules
import daily_blog.schema
import daily_blog.bundles
import daily_blog.editorial
import daily_blog.io_utils


#============================================
def test_bundle_writer_hashes_complete_artifacts_and_updates_latest(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A complete staged run becomes an immutable bundle with a stable date pointer."""
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/project", "a" * 40, "", "", "located work", "git show"
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item]
	)
	post = (
		"---\ndate: 2026-08-23\nslug: work-log\npublication_quality: provisional\n"
		+ "generator_run: run-one\nevidence_manifest: evidence.json\n---\n\n"
		+ f"# Work log\n\nI recorded work. <!-- evidence: {item.evidence_id} -->\n\n"
		+ "<!-- more -->\n\n## Status\n\n"
		+ f"I kept the record provisional. <!-- evidence: {item.evidence_id} -->\n"
	)
	decision = daily_blog.editorial.EditorialDecision(
		winner="NONE",
		reason="The deterministic record is more reliable.",
		evidence_quality="medium",
		confidence=0.8,
		publication_quality="provisional",
		post=post,
		anonymous_mapping={},
	)
	candidate = daily_blog.editorial.CandidateResult(
		private_route="author",
		post="",
		post_hash="0" * 64,
		valid=False,
		issues=("invalid",),
	)
	monkeypatch.setattr(daily_blog.bundles, "generator_revision", lambda _root: "f" * 40)
	writer = daily_blog.bundles.BundleWriter(str(tmp_path), "vosslab", str(tmp_path))

	bundle_path, bundle = writer.write(
		"run-one", packet, {}, [candidate, candidate], decision
	)

	with open(f"{bundle_path}/bundle.json", "r", encoding="utf-8") as handle:
		written = json.load(handle)
	latest_path = tmp_path / "vosslab" / "daily_blog" / packet.report_date / "latest.json"
	with open(latest_path, "r", encoding="utf-8") as handle:
		latest = json.load(handle)
	assert written["bundle_id"] == daily_blog.bundles.bundle_identity(written)
	assert (latest["run_id"], latest["bundle_id"]) == ("run-one", bundle["bundle_id"])


#============================================
def test_bundle_records_anonymous_winner_mapping_and_exact_post_hash(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The publisher can prove which anonymous valid candidate became the final post."""
	item = daily_blog.schema.EvidenceItem.create(
		"commit_metadata", "vosslab/project", "a" * 40, "", "", "located work", "git show"
	)
	packet = daily_blog.schema.EvidencePacket.create(
		"2026-08-23", "America/Chicago", True, {}, [], [], [item]
	)
	post = "final selected post\n"
	candidates = [
		daily_blog.editorial.CandidateResult("one", "other\n", "1" * 64, False, ("invalid",)),
		daily_blog.editorial.CandidateResult(
			"two",
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
		publication_quality="final",
		post=post,
		anonymous_mapping={"A": 1},
	)
	monkeypatch.setattr(daily_blog.bundles, "generator_revision", lambda _root: "f" * 40)
	writer = daily_blog.bundles.BundleWriter(str(tmp_path), "vosslab", str(tmp_path))

	_bundle_path, bundle = writer.write("run-final", packet, {}, candidates, decision)

	assert bundle["referee"]["anonymous_mapping"] == {"A": "candidate_2"}
	assert bundle["post"]["sha256"] == candidates[1].post_hash

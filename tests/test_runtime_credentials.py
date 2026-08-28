"""Tests for narrow runtime credential loading."""

# Standard Library
import os
import pathlib

# PIP3 modules
import pytest

# local repo modules
import podlib.runtime_credentials


#============================================
def test_github_token_reads_only_named_hermes_value(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: pathlib.Path,
) -> None:
	"""Hermes dotenv fallback should not export unrelated credentials."""
	env_path = tmp_path / ".env"
	env_path.write_text(
		"BLOG_TEST_NEIGHBOR_SECRET=keep-private\n"
		"export GITHUB_TOKEN='github_pat_example'\n",
		encoding="utf-8",
	)
	monkeypatch.delenv("GITHUB_TOKEN", raising=False)
	monkeypatch.delenv("BLOG_TEST_NEIGHBOR_SECRET", raising=False)
	monkeypatch.setenv("HERMES_HOME", str(tmp_path))

	token = podlib.runtime_credentials.get_github_token()

	assert token == "github_pat_example"
	assert "BLOG_TEST_NEIGHBOR_SECRET" not in os.environ


#============================================
def test_github_token_rejects_duplicate_hermes_entries(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: pathlib.Path,
) -> None:
	"""A conflicting runtime credential should fail instead of choosing silently."""
	(tmp_path / ".env").write_text(
		"GITHUB_TOKEN=github_pat_first\nGITHUB_TOKEN=github_pat_second\n",
		encoding="utf-8",
	)
	monkeypatch.delenv("GITHUB_TOKEN", raising=False)
	monkeypatch.setenv("HERMES_HOME", str(tmp_path))

	with pytest.raises(RuntimeError, match="more than once"):
		podlib.runtime_credentials.get_github_token()

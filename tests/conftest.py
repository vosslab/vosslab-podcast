import sys
import pathlib

import pytest

# local repo modules
import file_utils


# Keep repository-owned packages such as automation importable when pytest is
# launched from outside the checkout. file_utils owns repository-root
# discovery so the test environment follows the repository-wide contract.
_REPO_ROOT = file_utils.get_repo_root()
if _REPO_ROOT not in sys.path:
	sys.path.insert(0, _REPO_ROOT)

# local-llm-wrapper is a sibling repository, not vendored source. Keep its
# package importable when pytest is launched without sourcing source_me.sh.
_LOCAL_LLM_WRAPPER_ROOT = str(pathlib.Path.home() / "nsh" / "local-llm-wrapper")
if _LOCAL_LLM_WRAPPER_ROOT not in sys.path:
	sys.path.insert(0, _LOCAL_LLM_WRAPPER_ROOT)


collect_ignore = ["e2e", "playwright"]
_TESTS_ROOT = pathlib.Path(_REPO_ROOT) / "tests"
E2E_DIRECTORY = _TESTS_ROOT / "e2e"
PLAYWRIGHT_DIRECTORY = _TESTS_ROOT / "playwright"


#============================================
def find_test_topology_violations() -> list[str]:
	"""Return naming or direct-runner violations in excluded E2E directories."""
	violations = []
	for directory in (E2E_DIRECTORY, PLAYWRIGHT_DIRECTORY):
		if not directory.exists():
			continue
		for path in sorted(directory.rglob("*")):
			if not path.is_file() or "__pycache__" in path.parts:
				continue
			rel_path = path.relative_to(E2E_DIRECTORY.parent)
			if path.name.startswith("test_") and path.suffix == ".py":
				violations.append(f"{rel_path}: test_*.py is hidden by collect_ignore")
			if directory == E2E_DIRECTORY and path.suffix == ".py":
				if not path.name.startswith("e2e_"):
					violations.append(f"{rel_path}: E2E Python runner must use e2e_*.py")
			if directory == E2E_DIRECTORY and path.suffix == ".sh":
				if path.name != "run_all.sh" and not path.name.startswith("e2e_"):
					violations.append(f"{rel_path}: E2E shell runner must use e2e_*.sh")
	if not (E2E_DIRECTORY / "run_all.sh").is_file():
		violations.append("tests/e2e/run_all.sh: aggregate E2E runner is required")
	return violations


#============================================
def pytest_sessionstart(session: pytest.Session) -> None:
	"""Fail fast when excluded E2E files could be silently skipped by pytest."""
	del session
	violations = find_test_topology_violations()
	if violations:
		raise pytest.UsageError("E2E test topology violations:\n" + "\n".join(violations))

# REPO_HYGIENE_FILTERS is the repo-local hygiene-exclusion registry (Layer 2).
# file_utils.discover_files reads it from this conftest, which is the right
# home because propagation only merges the collect_ignore block above into this
# file; the rest of conftest survives and may differ per repo. Vendored files
# (file_utils.py and every tests/test_*.py) get overwritten by propagation,
# so they must hold no repo-specific data. Put repo-specific exclusions here.
#
# Shape and rules:
#   - It is a dict: key -> list of repo-relative POSIX glob patterns.
#   - Keys are "all" or a vendored test key. A test key is the test filename
#     stem with the leading "test_" removed (test_pyflakes_code_lint.py ->
#     "pyflakes_code_lint", test_ascii_compliance.py -> "ascii_compliance").
#   - Patterns match repo-relative POSIX paths via fnmatch.fnmatchcase
#     (case-sensitive). A match excludes the file from that test.
#   - "all" patterns apply to every test; a test-key list applies only when
#     that test_key is passed to discover_files.
#   - Recursive directory exclusions need an explicit /** because fnmatch's *
#     does not cross "/". Use "temp_scripts/**" to exclude a whole subtree.
#
# This template has no repo-specific exclusions, so the registry is empty.
# Cross-overlay doc references (a template doc naming a doc that ships from a
# different overlay or the universal docs/ tree) use a backticked name, not a
# markdown link: no single relative link is valid both in the split template
# tree and in the flattened consumer repo.
# Example entries (commented out; this repo needs none):
#   REPO_HYGIENE_FILTERS = {
#       "all": ["temp_scripts/**", "TEMPLATE.py"],
#       "ascii_compliance": ["human_readable-*.html"],
#       "pyflakes_code_lint": ["devel/scratch_*.py"],
#   }
REPO_HYGIENE_FILTERS = {}

# === OPTIONAL_HELPERS_MENU ===
# See meta/docs/PROPAGATION_RULES.md for the managed-block propagation contract.
# This block is an optional helpers menu appended once by propagation and
# never overwritten on subsequent propagation runs. Uncomment a recipe below
# to enable it for this repo. Every line here is a comment by default so an
# untouched consumer behaves exactly as it did before propagation added this
# block.
#
# Note: inserting the repo root onto sys.path is now done unconditionally at the
# top of this file via file_utils.get_repo_root(), so it is no longer a recipe.
#
# --- Recipe 1: redirect matplotlib config dir to a per-repo tmp location ---
# Prevents matplotlib from writing to the home-directory config cache during
# tests, which can cause cross-repo pollution or permission errors in CI.
# Set MPLCONFIGDIR to a writable tmp path before matplotlib is imported.
# Note: PYTHONUNBUFFERED and PYTHONDONTWRITEBYTECODE are handled by
# source_me.sh and belong there, not here.
#
#	import os
#	import tempfile
#	os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="mpl_"))

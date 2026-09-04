set | grep -q '^BASH_VERSION=' || echo "use bash for your shell"
set | grep -q '^BASH_VERSION=' || exit 1

# Only source ~/.bashrc if it has not already been loaded in this shell.
if [[ -z "${BASHRC_COMMON_LOADED:-}" ]]; then
	source "$HOME/.bashrc"
fi

# Set Python environment optimizations
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Set repo-local Python import paths
REPO_ROOT="$(git rev-parse --show-toplevel)"

# ASVS 1.2.5 and 2.2.1: select only the quoted, repo-owned environment path and
# positively verify its interpreter contract before it can affect command lookup.
REPO_PYTHON_ENV="${REPO_ROOT}/.venv"
if [[ ! -d "${REPO_PYTHON_ENV}" || -L "${REPO_PYTHON_ENV}" ]]; then
	echo "Missing physical Python 3.1x environment: ${REPO_PYTHON_ENV}" >&2
	echo "Create it with: python3 -m venv .venv" >&2
	return 1
fi
if ! "${REPO_PYTHON_ENV}/bin/python3" -c \
	'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)'
then
	echo "Repository environment must use Python 3.1x." >&2
	return 1
fi
export VIRTUAL_ENV="${REPO_PYTHON_ENV}"
if [[ "${PATH}" != "${VIRTUAL_ENV}/bin" && "${PATH}" != "${VIRTUAL_ENV}/bin:"* ]]; then
	export PATH="${VIRTUAL_ENV}/bin:${PATH}"
fi
unset PYTHONHOME
hash -r
unset REPO_PYTHON_ENV

# Add packages to PYTHONPATH
unset PYTHONPATH
export PYTHONPATH="${REPO_ROOT}/pipeline:${HOME}/nsh/local-llm-wrapper"

echo "Environment configured:"
echo "  REPO_ROOT=${REPO_ROOT}"
echo "  PYTHON=$(command -v python3)"
echo "  PYTHONPATH=${PYTHONPATH}"
echo ""
echo "Agents run with :"
echo "  source source_me.sh && python3 script.py"
echo "  source source_me.sh && pytest tests/"

unset REPO_ROOT

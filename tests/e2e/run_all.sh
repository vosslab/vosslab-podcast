#!/usr/bin/env bash
# Run every direct Python E2E program and report each result.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
E2E_DIR="$REPO_ROOT/tests/e2e"
PASS=0
FAIL=0
FAILURES=""

# shellcheck disable=SC1091
source "$REPO_ROOT/source_me.sh"

for script in "$E2E_DIR"/e2e_*.py; do
	if [ ! -f "$script" ]; then
		continue
	fi
	name="$(basename "$script")"
	printf "  running %-40s ... " "$name"
	if python3 "$script"; then
		echo "PASS"
		PASS=$((PASS + 1))
	else
		echo "FAIL"
		FAIL=$((FAIL + 1))
		FAILURES="$FAILURES $name"
	fi
done

echo ""
echo "Results: $PASS passed, $FAIL failed"

if [ "$FAIL" -gt 0 ]; then
	echo "FAILED:$FAILURES"
	exit 1
fi

echo "All e2e tests passed."

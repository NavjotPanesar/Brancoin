#!/usr/bin/env bash
# Run the bot test suite inside the 3.11 bot Docker image.
#
# The dev overlay bind-mounts ./bot into the container, so your local source is
# used without rebuilding. Tests use in-memory SQLite, so no Postgres is needed
# (--no-deps). pytest isn't in requirements.txt, so it's installed into the
# throwaway container each run.
#
# Usage:
#   ./run-tests.sh                                  # whole suite
#   ./run-tests.sh -v                               # pass flags through to pytest
#   ./run-tests.sh tests/test_game_monitor_integration.py
#
set -euo pipefail

# Run from the repo root (where the compose files live) regardless of cwd.
cd "$(dirname "$0")"

# Default to the full suite; forward any args straight to pytest.
PYTEST_ARGS="${*:-}"

exec docker compose -f docker-compose.yml -f compose.dev.yml run --rm --no-deps \
  --entrypoint sh bot \
  -c "pip install -q pytest && cd /usr/src/app && python -m pytest ${PYTEST_ARGS}"

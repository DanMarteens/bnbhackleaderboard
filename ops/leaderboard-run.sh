#!/bin/bash
set -euo pipefail

cd /opt/leaderboard
set -a
. ./.env
set +a

PY=/opt/cmc-twak-agent/.venv/bin/python
LOG=logs/lb.log
MIN_AGENTS=123

# Never let two minute-loop iterations mutate history or deploy concurrently.
exec 9>/run/leaderboard.lock
flock -n 9 || exit 0

# Registry scan is intentionally disabled: the competition registration set is frozen
# enough for live operations, and avoiding archive-wide scans preserves NodeReal quota.
# Add exceptional late/manual agents to dashboard/extra_participants.json instead.
"$PY" scripts/flows_costbasis.py >>"$LOG" 2>&1
"$PY" scripts/leaderboard.py >>"$LOG" 2>&1
"$PY" scripts/audit_leaderboard.py >>"$LOG" 2>&1

# Refuse to publish a partial registry. This is the production rollback guard:
# the known registry had 123 agents when installed, and can only grow.
agents=$("$PY" -c 'import json; print(json.load(open("dashboard/leaderboard.json"))["n"])')
if [ "$agents" -lt "$MIN_AGENTS" ]; then
  echo "$(date -u -Is) refusing deploy: only $agents agents (minimum $MIN_AGENTS)" >>"$LOG"
  exit 1
fi

"$PY" scripts/build_leaderboard.py dashboard/leaderboard.json public/index.html >>"$LOG" 2>&1

if [ -n "${CLOUDFLARE_API_TOKEN:-}" ]; then
  wrangler pages deploy public \
    --project-name=bnbhackleaderboard \
    --branch=main \
    --commit-dirty=true >>"$LOG" 2>&1
else
  echo "$(date -u -Is) no CLOUDFLARE_API_TOKEN; built but did not deploy" >>"$LOG"
fi

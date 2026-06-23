#!/bin/bash
set -euo pipefail

cd /opt/leaderboard
set -a
. ./.env
set +a

PY=/opt/cmc-twak-agent/.venv/bin/python
LOG=logs/lb.log
ENUM_STAMP=dashboard/.last_registry_scan
MIN_AGENTS=123

# Never let two minute-loop iterations mutate history or deploy concurrently.
exec 9>/run/leaderboard.lock
flock -n 9 || exit 0

# Registration remains open during the competition. Refresh the full on-chain
# registry every five minutes, before flow accounting, so new agents appear
# without making every minute refresh pay for an archive scan.
now=$(date +%s)
last=0
[ -f "$ENUM_STAMP" ] && last=$(cat "$ENUM_STAMP" 2>/dev/null || echo 0)
if [ -n "${ARCHIVE_RPC:-}" ] && [ $((now - last)) -ge 300 ]; then
  "$PY" scripts/leaderboard.py --enumerate >>"$LOG" 2>&1
  date +%s >"$ENUM_STAMP"
fi

"$PY" scripts/flows_costbasis.py >>"$LOG" 2>&1
"$PY" scripts/leaderboard.py >>"$LOG" 2>&1

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

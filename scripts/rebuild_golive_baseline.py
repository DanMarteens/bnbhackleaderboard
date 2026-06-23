#!/usr/bin/env python3
"""Rebuild frozen go-live NAVs from frozen balances and historical CMC marks."""
import json
import os
import sys
import urllib.parse
import urllib.request

import leaderboard as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PART_F = os.path.join(ROOT, "dashboard", "participants.json")
BASE_F = os.path.join(ROOT, "dashboard", "lb_baseline.json")
GOLIVE_F = os.path.join(ROOT, "dashboard", "golive.json")
IDS_F = os.path.join(ROOT, "config", "cmc_ids.json")
CANDIDATE_F = os.path.join(ROOT, "dashboard", "lb_baseline.candidate.json")
API = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/historical"


def historical_prices(idmap):
    key = os.environ.get("CMC_MCP_API_KEY", "")
    if not key:
        raise RuntimeError("CMC_MCP_API_KEY is required")
    by_id = {}
    ids = sorted({int(v) for v in idmap.values() if v})
    for i in range(0, len(ids), 80):
        params = urllib.parse.urlencode({
            "id": ",".join(map(str, ids[i:i + 80])),
            "time_start": "2026-06-21T23:00:00Z",
            "time_end": "2026-06-22T02:00:00Z",
            "interval": "hourly",
            "convert": "USD",
        })
        req = urllib.request.Request(API + "?" + params,
                                     headers={"X-CMC_PRO_API_KEY": key})
        data = json.load(urllib.request.urlopen(req, timeout=90)).get("data", {})
        for cid, asset in data.items():
            quotes = asset.get("quotes") or []
            exact = next((q for q in quotes
                          if q.get("timestamp", "").startswith("2026-06-22T00:00:00")), None)
            if exact:
                by_id[int(cid)] = float(exact["quote"]["USD"]["price"])
    return {
        sym: by_id[int(cid)]
        for sym, cid in idmap.items()
        if cid and int(cid) in by_id
    }


def main():
    apply = "--apply" in sys.argv
    agents = [a.lower() for a in json.load(open(PART_F))]
    idmap = json.load(open(IDS_F))
    tokens, current, decimals = L.load_tokens()
    opening = historical_prices(idmap)
    # Match live valuation policy: supported stablecoins are pinned to $1.
    for sym in L.STABLES:
        if sym in tokens:
            opening[sym] = 1.0
    missing = sorted(sym for sym in tokens if sym not in opening)
    prices = dict(current)
    prices.update(opening)
    block = int(json.load(open(GOLIVE_F))["block"])
    values, _ = L.value_agents(agents, tokens, prices, decimals, block=hex(block))
    values = {a: round(values.get(a, 0.0), 2) for a in agents}
    json.dump(values, open(CANDIDATE_F, "w"))

    try:
        old = json.load(open(BASE_F))
    except Exception:
        old = {}
    changes = sorted(((abs(values[a] - float(old.get(a, 0.0))), a,
                       float(old.get(a, 0.0)), values[a]) for a in agents), reverse=True)
    print("historical marks %d/%d tokens; fallback-current marks: %s"
          % (len(opening), len(tokens), ",".join(missing) or "none"))
    print("candidate agents", len(values))
    for delta, a, before, after in changes[:20]:
        print(a, "old", round(before, 2), "new", after, "delta", round(after - before, 2))
    if apply:
        os.replace(CANDIDATE_F, BASE_F)
        print("applied", BASE_F)
    else:
        print("review only; rerun with --apply")


if __name__ == "__main__":
    main()

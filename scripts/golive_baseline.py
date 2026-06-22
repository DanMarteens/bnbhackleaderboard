#!/usr/bin/env python3
"""Reconstruct the FROZEN go-live baseline from on-chain state at the go-live block.

The competition's start balance must be pinned to the trading-window open
(Jun 22 00:00 UTC), not to whenever a snapshot happened to run. This finds the
first BSC block at/after that instant and values every agent's BEP-20 portfolio
*at that block* (archive RPC), so the baseline is deterministic and reproducible.

Writes dashboard/lb_baseline.json + dashboard/golive.json. Run once; commit the
result so the scheduled job never re-snapshots it. Needs ARCHIVE_RPC.
"""
import sys, os, json, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import leaderboard as L
from eth_abi import encode as abi_encode, decode as abi_decode

GO_LIVE = int(dt.datetime(2026, 6, 22, tzinfo=dt.timezone.utc).timestamp())


def ts_of(n):
    r = L._post({"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber",
                 "params": [hex(n), False]})
    return int(r["result"]["timestamp"], 16)


def find_golive_block():
    latest = int(L.rpc("eth_blockNumber", []), 16)
    lo, hi = latest - 400000, latest          # ~2 weeks back is plenty
    while lo < hi:
        mid = (lo + hi) // 2
        if ts_of(mid) < GO_LIVE:
            lo = mid + 1
        else:
            hi = mid
    return lo


def mc_at_block(pairs, block):
    out = []
    for i in range(0, len(pairs), 500):
        chunk = pairs[i:i + 500]
        tuples = [(t, True, bytes.fromhex(cd[2:])) for t, cd in chunk]
        data = L.SEL_AGG3 + abi_encode(["(address,bool,bytes)[]"], [tuples]).hex()
        r = L._post({"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                     "params": [{"to": L.MULTICALL3, "data": data}, hex(block)]}).get("result")
        dec = abi_decode(["(bool,bytes)[]"], bytes.fromhex(r[2:]))[0]
        out += ["0x" + rd.hex() if ok else None for ok, rd in dec]
    return out


def main():
    if not L.RPC:
        print("ERROR: needs ARCHIVE_RPC"); sys.exit(1)
    block = find_golive_block()
    print("go-live block", block, "ts", ts_of(block), "(target", GO_LIVE, ")")
    agents = sorted(set(a.lower() for a in json.load(open(L.PART_F))))
    try:
        agents = sorted(set(agents) | set(a.lower() for a in json.load(
            open(os.path.join(L.ROOT, "dashboard", "extra_participants.json")))))
    except Exception:
        pass
    tokens, prices, decimals = L.load_tokens()
    syms = list(tokens)
    pairs = [(tokens[s], L.SEL_BAL + "0" * 24 + ag[2:]) for ag in agents for s in syms]
    res = mc_at_block(pairs, block)
    vals, k = {}, 0
    for ag in agents:
        tot = 0.0
        for s in syms:
            r = res[k]; k += 1
            if r and r != "0x":
                usd = (int(r, 16) / (10 ** decimals.get(s, 18))) * float(prices.get(s, 0) or 0)
                if usd > 0.01:
                    tot += usd
        vals[ag] = round(tot, 2)
    json.dump(vals, open(L.BASE_F, "w"))
    json.dump({"block": block, "ts": GO_LIVE}, open(os.path.join(L.ROOT, "dashboard", "golive.json"), "w"))
    funded = sum(1 for v in vals.values() if v > 5)
    print("baseline written:", len(vals), "agents |", funded, "funded | total $%.2f" % sum(vals.values()))
    for a in sorted(vals, key=lambda x: -vals[x])[:5]:
        print("  ", a, "$%.2f" % vals[a])
    print("our wallet 0x32a8..:", vals.get("0x32a84f2cf8d55a8ec5414d7dc42b0d873a98ab19"))


if __name__ == "__main__":
    main()

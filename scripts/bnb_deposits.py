#!/usr/bin/env python3
"""Detect post-go-live native-BNB deposits (external capital) per agent.

Our ERC-20 Transfer scan misses funding done in native BNB: a wallet is topped
up with BNB from an EOA, then swaps it into eligible tokens — so its eligible
value jumps with no detected flow and the deposit reads as fake "profit" (the
+500% dust artifact). Native BNB has no Transfer log, so we read it from
NodeReal's `nr_getAssetTransfers` (category "external", our existing MegaNode
endpoint = ARCHIVE_RPC) and net only the legs whose *sender is an EOA* — a
contract sender is swap proceeds, not a deposit.

Writes dashboard/bnb_deposits.json = {agent: usd_deposited}. Only scans
low-baseline wallets that already show an unexplained gain (a deposit can only
inflate a return, never hide it), so it stays to a handful of calls, and skips
work when its cache is fresh — safe to call from the per-minute board loop.
"""
import os, sys, json, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import leaderboard as L                      # reuse the board's CMC pricing

OUT_F = os.path.join(ROOT, "dashboard", "bnb_deposits.json")
GOLIVE_F = os.path.join(ROOT, "dashboard", "golive.json")
PART_F = os.path.join(ROOT, "dashboard", "participants.json")
BASE_F = os.path.join(ROOT, "dashboard", "lb_baseline.json")
LAZY_F = os.path.join(ROOT, "dashboard", "lb_lazy.json")

REFRESH_S = 840          # cache TTL: re-scan at most every ~14 min
BASELINE_MAX = 50.0      # the BNB->eligible artifact is only material on a small base
RPC = os.environ.get("ARCHIVE_RPC", "")      # NodeReal MegaNode (nr_* enhanced methods)


def rpc(method, params):
    r = json.load(urllib.request.urlopen(urllib.request.Request(
        RPC, json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        {"Content-Type": "application/json"}), timeout=40))
    if "error" in r:
        raise RuntimeError(r["error"])
    return r.get("result")


_code = {}


def is_eoa(addr):
    if addr not in _code:
        try:
            _code[addr] = rpc("eth_getCode", [addr, "latest"]) in ("0x", "0x0", None)
        except Exception:
            _code[addr] = False                  # unknown -> treat as contract (don't over-count)
    return _code[addr]


def bnb_price():
    """Live BNB/USD via CMC (id 1839), bypassing the board's eligible-only price cache."""
    r = L._cmc_tool("get_crypto_quotes_latest", {"id": "1839"}, L._cmc_session())
    rows = [dict(zip(r.get("headers", []), row)) for row in r["rows"]] if isinstance(r, dict) and "rows" in r \
        else (r if isinstance(r, list) else [])
    return next((float(q["price"]) for q in rows if str(q.get("id")) == "1839" and q.get("price")), 0.0)


def _bnb_to_contracts(addr, role, golive_hex, latest_hex):
    """Sum native-BNB legs where the OTHER party is a contract (a DEX swap, not an
    EOA capital transfer). role='fromAddress' -> BNB the wallet SPENT buying eligible;
    role='toAddress' -> BNB it RECEIVED selling eligible. Returns BNB."""
    other_key = "to" if role == "fromAddress" else "from"
    total_wei, page = 0, None
    for _ in range(20):                          # paginate defensively
        p = {"category": ["external"], role: addr,
             "fromBlock": golive_hex, "toBlock": latest_hex, "maxCount": "0x64"}
        if page:
            p["pageKey"] = page
        res = rpc("nr_getAssetTransfers", [p]) or {}
        for t in res.get("transfers") or []:
            v = t.get("value")
            wei = int(v, 16) if isinstance(v, str) and v.startswith("0x") else int(float(v or 0) * 1e18)
            if wei > 0 and not is_eoa(t.get(other_key, "")):
                total_wei += wei
        page = res.get("pageKey")
        if not page:
            break
    return total_wei / 1e18


def net_bnb_into_eligible(addr, golive_hex, latest_hex):
    """Net native BNB converted into the eligible portfolio = (BNB spent buying eligible)
    minus (BNB received selling eligible). BNB is not a scored asset, so this conversion
    is capital crossing into/out of the scored sleeve, not profit — it gets netted out.
    Positive = net capital in (deposit); negative = net capital out (withdrawal)."""
    return (_bnb_to_contracts(addr, "fromAddress", golive_hex, latest_hex)
            - _bnb_to_contracts(addr, "toAddress", golive_hex, latest_hex))


def main():
    if "--force" not in sys.argv:
        try:
            if time.time() - os.path.getmtime(OUT_F) < REFRESH_S:
                return
        except OSError:
            pass
    if not RPC or not os.path.exists(GOLIVE_F):
        return

    agents = set(a.lower() for a in json.load(open(PART_F)))
    try:
        agents |= set(a.lower() for a in json.load(open(os.path.join(ROOT, "dashboard", "extra_participants.json"))))
    except Exception:
        pass
    base = json.load(open(BASE_F)) if os.path.exists(BASE_F) else {}
    lazy = json.load(open(LAZY_F)) if os.path.exists(LAZY_F) else {}
    def baseline_of(a):
        gb = base.get(a, 0) or 0
        return gb if gb >= 0.1 else (lazy.get(a, gb) or 0)

    # The BNB->eligible artifact is only material on a small base (a $9 conversion is noise on a
    # $400 wallet, decisive on a $3 one). Scan every low-base wallet -- both net buyers (deposit)
    # and net sellers (withdrawal) need correcting, so we can't pre-filter on the apparent return.
    targets = [a for a in agents if baseline_of(a) < BASELINE_MAX]
    if not targets:
        return

    golive = json.load(open(GOLIVE_F)).get("block")
    latest = int(rpc("eth_blockNumber", []), 16)
    bnb_px = bnb_price()
    if not (golive and bnb_px):
        print("bnb_deposits: missing golive block or BNB price", file=sys.stderr); return

    out = json.load(open(OUT_F)) if os.path.exists(OUT_F) else {}
    for a in targets:
        try:
            usd = round(net_bnb_into_eligible(a, hex(golive), hex(latest)) * bnb_px, 2)
            if abs(usd) >= 0.01:
                out[a] = usd
            else:
                out.pop(a, None)
        except Exception as e:
            print("bnb_deposits: %s -> %s" % (a[:10], str(e)[:80]), file=sys.stderr)
    json.dump(out, open(OUT_F, "w"))
    print("bnb_deposits: scanned %d wallets @ $%.0f/BNB, %d with BNB conversion, net $%.2f"
          % (len(targets), bnb_px, len(out), sum(out.values())))


if __name__ == "__main__":
    main()

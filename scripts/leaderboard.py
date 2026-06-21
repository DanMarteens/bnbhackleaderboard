#!/usr/bin/env python3
"""Track-1 competitor leaderboard, built entirely from on-chain data.

1. Enumerate participants from the competition contract's `Registered(address)`
   events (archive RPC, chunked under the 50k-block getLogs limit).
2. Value each agent's in-scope portfolio: USDT + the tradeable universe, balanceOf
   via JSON-RPC batch, times last known prices.
3. Rank. If a baseline snapshot exists (taken at go-live), also compute return %.

Env: ARCHIVE_RPC = NodeReal (or any archive) BSC endpoint with the API key.
Usage:
  python scripts/leaderboard.py            # refresh participants + value + rank
  python scripts/leaderboard.py --baseline # also write the start snapshot (run at go-live)
"""
import json, os, sys, time, urllib.request
from eth_hash.auto import keccak
from eth_abi import encode as abi_encode, decode as abi_decode

MULTICALL3 = "0xcA11bde05977b3631167028862bE2a173976CA11"
SEL_AGG3 = "0x" + keccak(b"aggregate3((address,bool,bytes)[])")[:4].hex()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ARCHIVE_RPC (NodeReal) is needed ONLY to (re-)enumerate participants from historical
# Registered events. Valuation reads current state, which any free public RPC serves.
RPC = os.environ.get("ARCHIVE_RPC", "")
FREE_RPC = os.environ.get("FREE_RPC", "https://bsc-dataseed.binance.org/")
COMP = "0x212c61b9b72c95d95bf29cf032f5e5635629aed5".lower()
USDT = "0x55d398326f99059fF775485246999027B3197955"
TOPIC_REG = "0x" + keccak(b"Registered(address)").hex()
SEL_BAL = "0x70a08231"            # balanceOf(address)
SEL_DEC = "0x313ce567"            # decimals()
PART_F = os.path.join(ROOT, "dashboard", "participants.json")
BASE_F = os.path.join(ROOT, "dashboard", "lb_baseline.json")
DEC_F = os.path.join(ROOT, "dashboard", "lb_decimals.json")
OUT_F = os.path.join(ROOT, "dashboard", "leaderboard.json")
HIST_F = os.path.join(ROOT, "dashboard", "history.json")
MAXHIST = 400          # ~8 days at 30-min cadence
DQ = 0.30              # disqualification drawdown line


def _post(payload, url=None):
    req = urllib.request.Request(url or RPC, json.dumps(payload).encode(),
                                 {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=90))


def rpc(method, params):
    return _post({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).get("result")


def rpc_batch(calls):
    """Current-state reads. Prefer the archive key (free tier, handles the volume);
    fall back to the free public RPC (rate-limits at scale, so throttled)."""
    url = RPC or FREE_RPC
    out = []
    for i in range(0, len(calls), 100):
        chunk = calls[i:i + 100]
        payload = [{"jsonrpc": "2.0", "id": j, "method": m, "params": p}
                   for j, (m, p) in enumerate(chunk)]
        for attempt in range(3):
            try:
                resp = _post(payload, url)
                by_id = {r["id"]: r.get("result") for r in resp}
                out += [by_id.get(j) for j in range(len(chunk))]
                break
            except Exception:
                time.sleep(1.5)
        else:
            out += [None] * len(chunk)
    return out


def call_data(to, data):
    return ("eth_call", [{"to": to, "data": data}, "latest"])


def enumerate_participants(start=104900000, step=40000):
    latest = int(rpc("eth_blockNumber", []), 16)
    parts, b = [], start
    while b <= latest:
        e = min(b + step, latest)
        for _ in range(3):
            g = _post({"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs",
                       "params": [{"address": COMP, "topics": [TOPIC_REG],
                                   "fromBlock": hex(b), "toBlock": hex(e)}]})
            if "error" not in g:
                for l in g["result"]:
                    parts.append("0x" + l["topics"][1][-40:])
                break
            time.sleep(1)
        b = e + 1
    uniq = sorted(set(parts))
    json.dump(uniq, open(PART_F, "w"))
    return uniq


STABLES = {"USDT", "USDC", "DAI", "TUSD", "FDUSD", "USD1", "USDe", "FRAX", "FRXUSD",
           "USDD", "USDF", "lisUSD", "DUSD", "XUSD", "BILL", "USDf"}


def load_tokens():
    """Broad set (125 resolved eligible tokens) for accurate valuation: address +
    decimals from bsc_contracts.json. Prices: fresh market-cache where we have it,
    else the resolved file's priceUsd; stablecoins pinned to 1."""
    bc = os.path.join(ROOT, "config", "bsc_contracts.json")
    tokens, decimals, prices = {}, {}, {}
    if os.path.exists(bc):
        d = json.load(open(bc))
        for s, v in d.items():
            if v.get("address"):
                tokens[s] = v["address"]
                decimals[s] = v.get("decimals", 18)
                prices[s] = float(v.get("priceUsd", 0) or 0)
    else:
        cfg = __import__("yaml").safe_load(open(os.path.join(ROOT, "config.yaml")))
        tokens = dict(cfg["twak"]["token_contracts"])
    tokens.setdefault("USDT", USDT)
    try:                                            # overlay fresh prices we already fetch
        fresh = json.load(open(os.path.join(ROOT, "dashboard", "_market_cache.json"))).get("prices", {})
        prices.update({k: v for k, v in fresh.items() if v})
    except Exception:
        pass
    prices.update(coingecko_prices(tokens))         # freshest source (by contract, BSC)
    for s in tokens:
        if s in STABLES:
            prices[s] = 1.0
    return tokens, prices, decimals


def coingecko_prices(tokens):
    """Current USD prices by BSC contract address (free, no key). Returns {sym: price}
    for whatever resolves; callers keep prior prices for the rest."""
    addr_sym = {a.lower(): s for s, a in tokens.items()}
    addrs = list(addr_sym)
    out = {}
    for i in range(0, len(addrs), 100):
        chunk = addrs[i:i + 100]
        url = ("https://api.coingecko.com/api/v3/simple/token_price/binance-smart-chain"
               "?contract_addresses=" + ",".join(chunk) + "&vs_currencies=usd")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = json.load(urllib.request.urlopen(req, timeout=40))
            for a, v in data.items():
                if v.get("usd") and a.lower() in addr_sym:
                    out[addr_sym[a.lower()]] = float(v["usd"])
        except Exception:
            pass
        time.sleep(2.5)
    return out


def token_decimals(tokens):
    try:
        cache = json.load(open(DEC_F))
    except Exception:
        cache = {}
    missing = [(s, a) for s, a in tokens.items() if s not in cache]
    if missing:
        res = multicall([(a, SEL_DEC) for _, a in missing])
        for (s, _), r in zip(missing, res):
            cache[s] = int(r, 16) if r and r != "0x" else 18
        json.dump(cache, open(DEC_F, "w"))
    return cache


def multicall(pairs):
    """pairs = [(target, calldata_hex), ...] -> [returndata_hex|None]. One Multicall3
    eth_call returns hundreds of results, so the whole 55-agent valuation is ~5
    requests. Runs on the FREE public RPC (keeps NodeReal CUs untouched); the archive
    key is only a fallback if the free RPC chokes."""
    urls = [FREE_RPC] + ([RPC] if RPC else [])
    out = []
    for i in range(0, len(pairs), 600):
        chunk = pairs[i:i + 600]
        tuples = [(t, True, bytes.fromhex(cd[2:])) for t, cd in chunk]
        data = SEL_AGG3 + abi_encode(["(address,bool,bytes)[]"], [tuples]).hex()
        got = None
        for url in urls:
            for _ in range(2):
                try:
                    r = _post({"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                               "params": [{"to": MULTICALL3, "data": data}, "latest"]}, url).get("result")
                    if r and r != "0x":
                        dec = abi_decode(["(bool,bytes)[]"], bytes.fromhex(r[2:]))[0]
                        got = ["0x" + rd.hex() if ok else None for ok, rd in dec]
                        break
                except Exception:
                    time.sleep(1.5)
            if got:
                break
        out += got if got else [None] * len(chunk)
    return out


def value_agents(agents, tokens, prices, decimals):
    """Returns (totals{agent:usd}, holdings{agent:[[sym,usd], ...] top by value})."""
    syms = list(tokens)
    pairs = [(tokens[s], SEL_BAL + "0" * 24 + ag[2:]) for ag in agents for s in syms]
    res = multicall(pairs)
    vals, holds, k = {}, {}, 0
    for ag in agents:
        tot, hh = 0.0, []
        for s in syms:
            r = res[k]; k += 1
            if r and r != "0x":
                usd = (int(r, 16) / (10 ** decimals.get(s, 18))) * float(prices.get(s, 0) or 0)
                if usd > 0.01:
                    tot += usd
                    hh.append([s, round(usd, 2)])
        vals[ag] = round(tot, 2)
        holds[ag] = sorted(hh, key=lambda x: -x[1])[:8]
    return vals, holds


def main():
    do_baseline = "--baseline" in sys.argv
    # Re-enumerate (archive RPC) only on request or first run; otherwise load the saved
    # list and value it via the free RPC -> ongoing leaderboard costs nothing.
    do_enum = "--enumerate" in sys.argv or not os.path.exists(PART_F)
    if do_enum:
        if not RPC:
            print("ERROR: --enumerate needs ARCHIVE_RPC"); sys.exit(1)
        agents = enumerate_participants()
    else:
        agents = json.load(open(PART_F))
    tokens, prices, decimals = load_tokens()
    vals, holds = value_agents(agents, tokens, prices, decimals)

    now = int(time.time())

    if do_baseline:
        json.dump(vals, open(BASE_F, "w")); baseline = vals
    else:
        try:
            baseline = json.load(open(BASE_F))
        except Exception:
            baseline = {}

    # ---- history time-series (append + cap) -> enables sparklines/24h/drawdown ----
    try:
        hist = json.load(open(HIST_F))
    except Exception:
        hist = []
    hist.append({"ts": now, "v": {a: vals.get(a, 0.0) for a in agents}})
    hist = hist[-MAXHIST:]
    json.dump(hist, open(HIST_F, "w"))

    def series(a):
        return [(h["ts"], h["v"].get(a, 0.0)) for h in hist]

    def chg24h(s):
        if len(s) < 2:
            return None
        cutoff = now - 86400
        past = next((v for t, v in s if t >= cutoff), s[0][1])
        cur = s[-1][1]
        return round((cur / past - 1) * 100, 2) if past else None

    def drawdown(s):
        peak = dd = 0.0
        for _, v in s:
            peak = max(peak, v)
            if peak > 0:
                dd = max(dd, (peak - v) / peak)
        return round(dd * 100, 2)

    def spark(s, k=24):
        vs = [v for _, v in s]
        if len(vs) <= k:
            return [round(v, 4) for v in vs]
        step = len(vs) / k
        return [round(vs[min(len(vs) - 1, int(i * step))], 4) for i in range(k)]

    rows = []
    for a in agents:
        s = series(a); v = vals.get(a, 0.0); b = baseline.get(a)
        rows.append({"agent": a, "value": v,
                     "ret_pct": round((v / b - 1) * 100, 2) if (b and b > 0) else None,
                     "chg24h": chg24h(s), "dd_pct": drawdown(s), "spark": spark(s),
                     "holds": holds.get(a, [])})
    rows.sort(key=lambda r: (r["ret_pct"] if r["ret_pct"] is not None else -1e9, r["value"]), reverse=True)
    for i, r in enumerate(rows):
        r["rank"] = i + 1

    has_base = bool(baseline)
    rets = [r["ret_pct"] for r in rows if r["ret_pct"] is not None]
    stats = {
        "n": len(agents),
        "funded": sum(1 for r in rows if r["value"] > 0),
        "deployed": round(sum(r["value"] for r in rows), 2),
        "in_profit": (sum(1 for r in rows if (r["ret_pct"] or 0) > 0) if has_base else None),
        "avg_ret": (round(sum(rets) / len(rets), 2) if rets else None),
        "survivors": (sum(1 for r in rows if r["dd_pct"] < DQ * 100) if has_base else None),
        "dq_pct": DQ * 100,
    }
    out = {"generated_ts": now, "n": len(agents), "has_baseline": has_base,
           "stats": stats, "rows": rows}
    json.dump(out, open(OUT_F, "w"))

    print(f"participants {len(agents)} | baseline {has_base} | funded {stats['funded']} | deployed ${stats['deployed']}")
    for r in rows[:8]:
        print(f"  #{r['rank']:>2} {r['agent']} ${r['value']} ret={r['ret_pct']} 24h={r['chg24h']} dd={r['dd_pct']}")


if __name__ == "__main__":
    main()

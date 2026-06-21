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
TOPIC_TRANSFER = "0x" + keccak(b"Transfer(address,address,uint256)").hex()
SEL_BAL = "0x70a08231"            # balanceOf(address)
SEL_DEC = "0x313ce567"            # decimals()
PART_F = os.path.join(ROOT, "dashboard", "participants.json")
BASE_F = os.path.join(ROOT, "dashboard", "lb_baseline.json")
DEC_F = os.path.join(ROOT, "dashboard", "lb_decimals.json")
OUT_F = os.path.join(ROOT, "dashboard", "leaderboard.json")
HIST_F = os.path.join(ROOT, "dashboard", "history.json")
GOLIVE_F = os.path.join(ROOT, "dashboard", "golive.json")   # {"block","ts"} captured at baseline
FLOWS_F = os.path.join(ROOT, "dashboard", "flows.json")     # last good {agent: net deposit USD}
MAXHIST = 400          # ~8 days at 30-min cadence
MINCAP = 5.0           # ignore returns on < $5 capital (dust / noise)
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


def enumerate_participants(start=104800000, step=40000):
    latest = int(rpc("eth_blockNumber", []), 16)

    def grab(b, e, depth=0):
        # retry, then split the range on persistent error -> never silently skip blocks
        for _ in range(4):
            g = _post({"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs",
                       "params": [{"address": COMP, "topics": [TOPIC_REG],
                                   "fromBlock": hex(b), "toBlock": hex(e)}]})
            if "error" not in g:
                return ["0x" + l["topics"][1][-40:] for l in g["result"]]
            time.sleep(1.5)
        if b < e and depth < 14:
            mid = (b + e) // 2
            return grab(b, mid, depth + 1) + grab(mid + 1, e, depth + 1)
        return []

    parts, b = [], start
    while b <= latest:
        e = min(b + step, latest)
        parts += grab(b, e)
        b = e + 1
        time.sleep(0.15)
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


def external_flows(agents, from_block, tokens, prices, decimals):
    """Net external BEP-20 deposit (USD) per agent since `from_block`.

    A deposit is an INBOUND token Transfer whose sender is an EOA; a withdrawal is an
    OUTBOUND transfer to an EOA. Transfers to/from *contracts* (DEX routers, pairs,
    aggregators) are trades, not capital flows -> ignored. This lets the leaderboard
    rank by trading-only return: PnL is measured against (baseline + net deposits), so
    topping the wallet up grows the capital base instead of the return.

    getLogs-based (NodeReal's transfer indexer returns empty on BSC). Fully fail-safe:
    falls back to the cached flows (or zeros) on any error -> never breaks a run."""
    flows = {a: 0.0 for a in agents}
    if not RPC or not agents:
        return flows
    try:
        latest = int(rpc("eth_blockNumber", []), 16)
        if from_block >= latest:
            return flows
        addr_sym = {a.lower(): s for s, a in tokens.items()}
        token_addrs = list({a for a in tokens.values()})
        agent_set = set(a.lower() for a in agents)
        agent_topics = ["0x" + "0" * 24 + a[2:] for a in agents]

        def grab(b, e, topics, depth=0):
            for _ in range(3):
                g = _post({"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [{
                    "address": token_addrs, "fromBlock": hex(b), "toBlock": hex(e),
                    "topics": topics}]})
                if "error" not in g:
                    return g["result"]
                time.sleep(1.0)
            if b < e and depth < 12:
                mid = (b + e) // 2
                return grab(b, mid, topics, depth + 1) + grab(mid + 1, e, topics, depth + 1)
            return []

        logs, b, step = [], from_block, 45000
        while b <= latest:
            e = min(b + step, latest)
            logs += grab(b, e, [TOPIC_TRANSFER, None, agent_topics])    # inbound (to = agent)
            logs += grab(b, e, [TOPIC_TRANSFER, agent_topics, None])    # outbound (from = agent)
            b = e + 1
            time.sleep(0.1)

        # classify each non-agent counterparty as EOA (code == 0x) vs contract
        cps = set()
        for l in logs:
            if len(l.get("topics", [])) < 3:
                continue
            frm, to = "0x" + l["topics"][1][-40:], "0x" + l["topics"][2][-40:]
            cps.add(to if frm in agent_set else frm)
        cps = list(cps)
        is_eoa = {}
        codes = rpc_batch([("eth_getCode", [c, "latest"]) for c in cps]) if cps else []
        for c, r in zip(cps, codes):
            is_eoa[c] = r in (None, "0x", "0x0", "")

        seen = set()
        for l in logs:
            ident = (l.get("transactionHash"), l.get("logIndex"))
            if ident in seen:                      # dedup (a self-transfer hits both queries)
                continue
            seen.add(ident)
            if len(l.get("topics", [])) < 3:
                continue
            sym = addr_sym.get(l.get("address", "").lower())
            price = float(prices.get(sym, 0) or 0) if sym else 0
            if price <= 0:
                continue
            try:
                amt = int(l["data"], 16) / (10 ** decimals.get(sym, 18))
            except Exception:
                continue
            usd = amt * price
            if usd <= 0:
                continue
            frm, to = "0x" + l["topics"][1][-40:], "0x" + l["topics"][2][-40:]
            if to in agent_set and frm not in agent_set and is_eoa.get(frm):
                flows[to] = flows.get(to, 0.0) + usd          # deposit in
            elif frm in agent_set and to not in agent_set and is_eoa.get(to):
                flows[frm] = flows.get(frm, 0.0) - usd        # withdrawal out
        flows = {a: round(flows.get(a, 0.0), 2) for a in agents}
        json.dump(flows, open(FLOWS_F, "w"))
        return flows
    except Exception as ex:
        print("flow calc failed (using cache/zero):", ex)
        try:
            cached = json.load(open(FLOWS_F))
            return {a: float(cached.get(a, 0.0)) for a in agents}
        except Exception:
            return {a: 0.0 for a in agents}


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
    # Merge a manual allowlist: some registrations don't emit a catchable Registered
    # event, so reported-missing (but on-chain isRegistered=true) agents go here.
    try:
        extra = json.load(open(os.path.join(ROOT, "dashboard", "extra_participants.json")))
        agents = sorted(set(a.lower() for a in agents) | set(a.lower() for a in extra))
    except Exception:
        pass
    tokens, prices, decimals = load_tokens()
    vals, holds = value_agents(agents, tokens, prices, decimals)

    now = int(time.time())

    if do_baseline:
        json.dump(vals, open(BASE_F, "w")); baseline = vals
        try:                       # remember the go-live block -> deposit scan starts here
            json.dump({"block": int(rpc("eth_blockNumber", []), 16), "ts": now},
                      open(GOLIVE_F, "w"))
        except Exception:
            pass
    else:
        try:
            baseline = json.load(open(BASE_F))
        except Exception:
            baseline = {}

    # ---- net external deposits since go-live (capital base for trading-only return) ----
    flows = {a: 0.0 for a in agents}
    try:
        gl = json.load(open(GOLIVE_F)).get("block")
    except Exception:
        gl = None
    if gl and not do_baseline:     # no post-go-live flow can exist on the baseline run
        flows = external_flows(agents, gl, tokens, prices, decimals)

    # ---- history time-series (append + cap) -> enables sparklines/24h/drawdown ----
    try:
        hist = json.load(open(HIST_F))
    except Exception:
        hist = []
    hist.append({"ts": now, "v": {a: vals.get(a, 0.0) for a in agents},
                 "f": {a: flows.get(a, 0.0) for a in agents}})
    hist = hist[-MAXHIST:]
    json.dump(hist, open(HIST_F, "w"))

    def series(a):                 # deposit-adjusted value series (raw value minus cumulative
        # net deposits at each snapshot) -> every window is deposit-neutral. Old snapshots
        # without an "f" field predate the event, where flow is 0 anyway.
        return [(h["ts"], h["v"].get(a, 0.0) - h.get("f", {}).get(a, 0.0)) for h in hist]

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

    import datetime as _dt
    HACK_DAYS = 7                  # Jun 22..28 UTC -> Day 1..Day 7
    def _day_bounds(n):            # n=1..7 -> (start_ts, end_ts) UTC; Day 1 = Jun 22
        st = _dt.datetime(2026, 6, 21 + n, tzinfo=_dt.timezone.utc).timestamp()
        return int(st), int(st + 86400)

    def winret(s, secs):           # return over a rolling window (deposit-adjusted series)
        if len(s) < 2:
            return None
        past = next((v for t, v in s if t >= now - secs), s[0][1])
        if not past or past < MINCAP:
            return None
        return round((s[-1][1] / past - 1) * 100, 2)

    def _at_or_before(s, ts):      # last snapshot value with t <= ts (s ascending)
        val = None
        for t, v in s:
            if t <= ts:
                val = v
            else:
                break
        return val

    def dayret_n(s, n, base):      # close-to-close return for hackathon Day n
        st, en = _day_bounds(n)
        if now < st:               # day hasn't started yet
            return None
        prev = base if n == 1 else _at_or_before(s, st)   # Day 1 opens at go-live baseline
        if not prev or prev < MINCAP:
            prev = next((v for t, v in s if t >= st), None)
        if not prev or prev < MINCAP:
            return None
        cur = s[-1][1] if now < en else _at_or_before(s, en)   # in-progress -> current
        if not cur:
            return None
        return round((cur / prev - 1) * 100, 2)

    rows = []
    for a in agents:
        s = series(a); v = vals.get(a, 0.0); b = baseline.get(a) or 0.0; f = flows.get(a, 0.0)
        cap = b + f                              # total capital deployed = start + net deposits
        allret = round((v - cap) / cap * 100, 2) if cap > MINCAP else None
        win = {"1h": winret(s, 3600), "24h": winret(s, 86400), "all": allret}
        for n in range(1, HACK_DAYS + 1):
            win["d%d" % n] = dayret_n(s, n, b)
        rows.append({"agent": a, "value": v, "dep": round(f, 2),
                     "ret_pct": allret, "chg24h": winret(s, 86400),
                     "dd_pct": drawdown(s), "spark": spark(s), "holds": holds.get(a, []),
                     "win": win})
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

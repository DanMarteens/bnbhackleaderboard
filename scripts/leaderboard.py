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
BNB_DEP_F = os.path.join(ROOT, "dashboard", "bnb_deposits.json")  # (legacy) native-BNB deposits
FLOWS_CB_F = os.path.join(ROOT, "dashboard", "flows_costbasis.json")  # cost-basis flows {agent:[dep,wd]}
LASTPX_F = os.path.join(ROOT, "dashboard", "last_prices.json")    # carry-forward price store (feed-gap guard)
MAXHIST = 200          # hourly starts + current point; comfortably covers the event
MINCAP = 0.1           # everyone who traded gets a PnL; only true dust (< $0.10) is skipped
DQ = 0.30              # disqualification drawdown line
REGISTRY_SCAN_START = 102000000  # before competition-contract deployment / first registration
GO_LIVE_TS = 1782086400        # 2026-06-22 00:00:00 UTC
HACK_DAYS = 7
DEX_MIN_LIQUIDITY = float(os.environ.get("DEX_MIN_LIQUIDITY", "25000"))
DEX_DEVIATION = float(os.environ.get("DEX_DEVIATION", "0.20"))
SIM_COST_BPS = float(os.environ.get("SIM_COST_BPS", "0"))
PRICE_OVERRIDES = {}


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


def enumerate_participants(start=REGISTRY_SCAN_START, step=40000):
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
           "USDD", "USDF", "lisUSD", "DUSD", "XUSD", "USDf"}


def apply_dex_guard(prices, dex):
    """Mutate prices with liquid, materially divergent BSC marks; return audit metadata."""
    overrides = {}
    for s, q in dex.items():
        dp, liq = q.get("price", 0), q.get("liquidity", 0)
        cp = float(prices.get(s, 0) or 0)
        if s in STABLES or dp <= 0 or liq < DEX_MIN_LIQUIDITY:
            continue
        deviation = abs(dp / cp - 1) if cp > 0 else 1.0
        if cp <= 0 or deviation > DEX_DEVIATION:
            overrides[s] = {"cmc": cp, "dex": dp, "liquidity": liq}
            prices[s] = dp
    return overrides


def load_tokens():
    """Eligible-token universe for valuation: address + decimals from bsc_contracts.json,
    with USD prices.

    Prices come from CoinMarketCap via the CMC MCP (cmc_prices) for the whole universe —
    ids are resolved once and cached, quotes are batched and cached ~10 min. The resolved
    file's static priceUsd is the only fallback for a symbol CMC can't return; stablecoins
    are pinned to 1. Native BNB / WBNB are not on the 149-token eligible list -> not valued."""
    bc = os.path.join(ROOT, "config", "bsc_contracts.json")
    tokens, decimals, prices = {}, {}, {}
    if os.path.exists(bc):
        d = json.load(open(bc))
        seen_addr = {}                                          # contract -> first symbol mapped
        for s, v in d.items():
            addr = v.get("address")
            if not addr:
                continue
            al = addr.lower()
            if al in seen_addr:                                 # dedupe: same contract under two
                continue                                        # symbols (e.g. USDf/USDF) -> count once
            seen_addr[al] = s
            tokens[s] = addr
            decimals[s] = v.get("decimals", 18)
            prices[s] = float(v.get("priceUsd", 0) or 0)        # static fallback base
    else:
        cfg = __import__("yaml").safe_load(open(os.path.join(ROOT, "config.yaml")))
        tokens = dict(cfg["twak"]["token_contracts"])
    tokens.setdefault("USDT", USDT)
    # PRIMARY and only live source: CoinMarketCap via the MCP key, for the WHOLE eligible
    # universe (ids resolved + cached once, quotes batched, cached 10 min). The resolved
    # file's static priceUsd remains only as a fallback for any symbol CMC can't return.
    try:
        prices.update({k: v for k, v in cmc_prices(list(tokens)).items() if v})
    except Exception:
        pass
    # CMC can diverge sharply from the BSC market for bridged/thin tokens. That creates
    # instant paper profit after a swap (SIREN and BILL did this in the live event). Use
    # the deepest BSC DEX pair as a sanity oracle and override CMC only when the gap is
    # material and the pair has enough liquidity to be meaningful.
    try:
        dex = dex_prices(tokens)
        PRICE_OVERRIDES.clear()
        PRICE_OVERRIDES.update(apply_dex_guard(prices, dex))
    except Exception as e:
        print("dex price sanity check failed:", e)
    for s in tokens:
        if s in STABLES:
            prices[s] = 1.0
    return tokens, prices, decimals


CACHE_TTL = int(os.environ.get("LB_CACHE_TTL", "300"))   # 5 min -> a 60s loop reuses the
# expensive results (CMC quotes, getLogs flow/trade scans) instead of refetching every tick.
# Re-valuation (Multicall3, keyless) still happens every run, so values stay fresh.


def _cache_get(name, ttl=CACHE_TTL):
    try:
        d = json.load(open(os.path.join(ROOT, "dashboard", "_c_" + name + ".json")))
        if int(time.time()) - d.get("_ts", 0) < ttl:
            return d.get("v")
    except Exception:
        pass
    return None


def _cache_put(name, v):
    try:
        json.dump({"_ts": int(time.time()), "v": v},
                  open(os.path.join(ROOT, "dashboard", "_c_" + name + ".json"), "w"))
    except Exception:
        pass


CMC_IDS_F = os.path.join(ROOT, "config", "cmc_ids.json")
CMC_MCP_URL = os.environ.get("CMC_MCP_URL", "https://mcp.coinmarketcap.com/mcp")


def dex_prices(tokens):
    """symbol -> {price, liquidity} from the deepest BSC DexScreener pair.

    This is not used as a second independent ranking feed. It is a manipulation/error
    guard for CMC marks: only a >DEX_DEVIATION discrepancy backed by >=DEX_MIN_LIQUIDITY
    changes the mark. Cached so a one-minute refresh does not hammer the public endpoint.
    """
    cached = _cache_get("dex", 300)
    if cached is not None:
        return cached
    addr_sym = {a.lower(): s for s, a in tokens.items()}
    addrs = list(addr_sym)
    best = {}
    for i in range(0, len(addrs), 30):
        url = "https://api.dexscreener.com/tokens/v1/bsc/" + ",".join(addrs[i:i + 30])
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            rows = json.load(urllib.request.urlopen(req, timeout=30))
        except Exception:
            rows = []
        for row in rows if isinstance(rows, list) else []:
            base = (row.get("baseToken") or {}).get("address", "").lower()
            sym = addr_sym.get(base)
            if not sym:
                continue
            try:
                px = float(row.get("priceUsd") or 0)
                liq = float((row.get("liquidity") or {}).get("usd") or 0)
            except Exception:
                continue
            if px > 0 and liq > best.get(sym, {}).get("liquidity", -1):
                best[sym] = {"price": px, "liquidity": liq}
        time.sleep(0.05)
    if best:
        _cache_put("dex", best)
    return best


def _mcp_call(method, params, session_id=None):
    """One JSON-RPC call to the CoinMarketCap MCP. Returns (data, session_id)."""
    key = os.environ.get("CMC_MCP_API_KEY", "")
    hdrs = {"X-CMC-MCP-API-KEY": key, "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"}
    if session_id:
        hdrs["Mcp-Session-Id"] = session_id
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    resp = urllib.request.urlopen(urllib.request.Request(CMC_MCP_URL, body, hdrs), timeout=45)
    sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
    text = resp.read().decode()
    data = {}
    if "text/event-stream" in resp.headers.get("content-type", ""):
        for line in text.splitlines():
            if line.startswith("data:"):
                data = json.loads(line[5:].strip()); break
    elif text.strip():
        data = json.loads(text)
    return data, sid


def _cmc_session():
    data, sid = _mcp_call("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                         "clientInfo": {"name": "lb", "version": "1"}})
    if not sid and isinstance(data, dict):
        sid = data.get("result", {}).get("sessionId")
    try:
        _mcp_call("notifications/initialized", {}, sid)
    except Exception:
        pass
    return sid


def _cmc_tool(name, args, sid):
    data, _ = _mcp_call("tools/call", {"name": name, "arguments": args}, sid)
    res = data.get("result", {}) if isinstance(data, dict) else {}
    content = res.get("content", res)
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                try:
                    return json.loads(item["text"])
                except Exception:
                    return item.get("text")
    return content


def cmc_resolve_ids(symbols):
    """symbol -> CMC numeric id, via search_cryptos. Cached permanently (ids are stable)."""
    try:
        ids = json.load(open(CMC_IDS_F))
    except Exception:
        ids = {}
    missing = [s for s in symbols if s not in ids]
    if missing:
        try:
            sid = _cmc_session()
            for s in missing:
                try:
                    r = _cmc_tool("search_cryptos", {"query": s}, sid) or []
                    exact = [x for x in r if isinstance(x, dict) and x.get("symbol") == s]
                    pool = exact or [x for x in r if isinstance(x, dict)]
                    ids[s] = (sorted(pool, key=lambda x: x.get("rank") or 1e9)[0].get("id")
                              if pool else None)
                except Exception:
                    ids[s] = ids.get(s)
                time.sleep(0.05)
            json.dump(ids, open(CMC_IDS_F, "w"))
        except Exception as e:
            print("cmc id resolve failed:", e)
    return {s: ids.get(s) for s in symbols if ids.get(s)}


def cmc_prices(symbols):
    """Live USD prices from the CoinMarketCap MCP (our key) for the eligible universe.
    Resolves ids once (cached), then batches get_crypto_quotes_latest. Cached 10 min."""
    cached = _cache_get("cmc", 600)
    if cached is not None:
        return cached
    if not os.environ.get("CMC_MCP_API_KEY"):
        return {}
    idmap = cmc_resolve_ids(symbols)
    if not idmap:
        return {}
    id2sym = {str(v): k for k, v in idmap.items()}
    out = {}
    try:
        sid = _cmc_session()
        ids = list(id2sym.keys())
        for i in range(0, len(ids), 80):
            r = _cmc_tool("get_crypto_quotes_latest", {"id": ",".join(ids[i:i + 80])}, sid)
            rows = []
            if isinstance(r, dict) and "rows" in r:
                hdr = r.get("headers", [])
                rows = [dict(zip(hdr, row)) for row in r["rows"]]
            elif isinstance(r, list):
                rows = r
            for q in rows:
                sym, px = id2sym.get(str(q.get("id"))), q.get("price")
                if sym and px:
                    out[sym] = float(px)
            time.sleep(0.1)
    except Exception as e:
        print("cmc prices failed:", e)
    # Carry forward the last known price for any eligible token CMC omitted this round, so a
    # transient feed gap can't crater a holder's value (the cause of the false multi-hour drawdowns).
    try:
        last = json.load(open(LASTPX_F))
    except Exception:
        last = {}
    for sym in idmap:
        if sym not in out and sym in last:
            out[sym] = last[sym]
    if out:
        last.update(out)                       # fresh quotes refresh the carry-forward store
        try:
            json.dump(last, open(LASTPX_F, "w"))
        except Exception:
            pass
        _cache_put("cmc", out)
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


def multicall(pairs, block="latest"):
    """pairs = [(target, calldata_hex), ...] -> [returndata_hex|None]. One Multicall3
    eth_call returns hundreds of results, so the whole field valuation is ~5 requests.
    `latest` runs on the FREE public RPC (keeps NodeReal CUs untouched); a historical
    block (for the go-live baseline) needs the archive RPC, which free nodes prune."""
    urls = ([RPC] if (block != "latest" and RPC) else [FREE_RPC] + ([RPC] if RPC else []))
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
                               "params": [{"to": MULTICALL3, "data": data}, block]}, url).get("result")
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


def value_agents(agents, tokens, prices, decimals, block="latest"):
    """Returns (totals{agent:usd}, holdings{agent:[[sym,usd], ...] top by value}).

    Counts eligible BEP-20 balances only. Native BNB is outside the eligible sleeve;
    BNB<->token conversions are handled as capital entering/leaving, never as trades.
    `block` lets the same logic value a historical block for the go-live baseline."""
    syms = list(tokens)
    pairs = [(tokens[s], SEL_BAL + "0" * 24 + ag[2:]) for ag in agents for s in syms]
    res = multicall(pairs, block)
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


def classify_transactions(agents, by_agent_tx, addr_sym, prices, decimals, day_start_blocks):
    """Pure scoring classifier used by the live scan and regression tests."""
    flows = {a: 0.0 for a in agents}
    trades = {a: 0 for a in agents}
    daily = {a: [0] * len(day_start_blocks) for a in agents}
    first_funding_day = {a: None for a in agents}
    turnover = {a: 0.0 for a in agents}

    def leg_usd(l):
        sym = addr_sym.get(l.get("address", "").lower())
        try:
            return (int(l["data"], 16) / (10 ** decimals.get(sym, 18))
                    * float(prices.get(sym, 0) or 0))
        except Exception:
            return 0.0

    def day_index(block):
        idx = None
        for i, b in enumerate(day_start_blocks):
            if block >= b:
                idx = i
            else:
                break
        return idx

    for agent, txs in by_agent_tx.items():
        for rec in txs.values():
            vin = sum(leg_usd(l) for l in rec["in"])
            vout = sum(leg_usd(l) for l in rec["out"])
            di = day_index(rec["block"])
            if rec["in"] and rec["out"]:
                trades[agent] += 1
                turnover[agent] += vout
                if di is not None and di < len(daily[agent]):
                    daily[agent][di] += 1
            elif rec["in"]:
                flows[agent] += vin
                if di is not None and first_funding_day[agent] is None:
                    first_funding_day[agent] = di
            elif rec["out"]:
                flows[agent] -= vout
    flows = {a: round(flows.get(a, 0.0), 2) for a in agents}
    turnover = {a: round(turnover.get(a, 0.0), 2) for a in agents}
    return flows, trades, daily, first_funding_day, turnover


def daily_qualification(baseline, counts):
    """Return (qualified, missing days), allowing a zero-start wallet to enter late.

    Capital present at go-live owes every competition day. A zero-start wallet begins
    its daily obligation on its first strict eligible swap day; merely funding earlier
    must not create a retroactive missed-day penalty.
    """
    start_day = 0 if baseline > MINCAP else next((i for i, n in enumerate(counts) if n > 0), None)
    required = list(range(start_day, len(counts))) if start_day is not None else []
    missing = [i + 1 for i in required if counts[i] < 1]
    return bool(required) and not missing, missing


def capital_return(value, baseline, deposits, withdrawals, turnover=0.0, cost_bps=0.0):
    """Deposit-neutral total return and effective capital; None when no capital exists."""
    capital = float(baseline or 0) + float(deposits or 0)
    if capital <= MINCAP:
        return None, capital, 0.0
    sim_cost = float(turnover or 0) * float(cost_bps or 0) / 10000.0
    ret = ((float(value or 0) + float(withdrawals or 0) - sim_cost) / capital - 1) * 100
    return round(ret, 2), capital, sim_cost


def scan_activity(agents, golive_block, day_start_blocks, tokens, prices, decimals):
    """Classify every eligible-token transaction touching an agent.

    Competition trade (strict): the same transaction has >=1 eligible token entering
    AND >=1 eligible token leaving the agent. BNB legs, deposits, withdrawals, airdrops,
    approvals and one-sided contract transfers never count as trades.

    One-sided eligible activity is an external capital flow. This classification is based
    on the complete per-transaction shape, not whether a counterparty has bytecode; bridges,
    smart wallets and BNB conversions therefore cannot inflate the trade count.

    Returns flows, cumulative trades, current-day trades, per-day trades,
    first funding day, and eligible-swap turnover in USD.
    """
    flows = {a: 0.0 for a in agents}
    trades = {a: 0 for a in agents}      # cumulative swaps since go-live (displayed)
    today = {a: 0 for a in agents}       # swaps in the current UTC day (>=1 -> scoring gate)
    daily = {a: [0] * len(day_start_blocks) for a in agents}
    first_funding_day = {a: None for a in agents}
    turnover = {a: 0.0 for a in agents}
    if not RPC or not agents:
        return flows, trades, today, daily, first_funding_day, turnover
    cached = _cache_get("activity_v2")
    if cached is not None:
        f, t, d = cached.get("flows", {}), cached.get("trades", {}), cached.get("today", {})
        dy, ff, tv = cached.get("daily", {}), cached.get("first_funding_day", {}), cached.get("turnover", {})
        return ({a: float(f.get(a, 0.0)) for a in agents},
                {a: int(t.get(a, 0)) for a in agents},
                {a: int(d.get(a, 0)) for a in agents},
                {a: list(dy.get(a, [0] * len(day_start_blocks))) for a in agents},
                {a: ff.get(a) for a in agents},
                {a: float(tv.get(a, 0.0)) for a in agents})
    try:
        latest = int(rpc("eth_blockNumber", []), 16)
        if golive_block >= latest:
            return flows, trades, today, daily, first_funding_day, turnover
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

        logs, b, step = [], golive_block, 45000
        while b <= latest:
            e = min(b + step, latest)
            logs += grab(b, e, [TOPIC_TRANSFER, None, agent_topics])    # inbound (to = agent)
            logs += grab(b, e, [TOPIC_TRANSFER, agent_topics, None])    # outbound (from = agent)
            b = e + 1
            time.sleep(0.1)

        seen, rows = set(), []
        for l in logs:
            ident = (l.get("transactionHash"), l.get("logIndex"))
            if ident in seen or len(l.get("topics", [])) < 3:
                continue
            seen.add(ident)
            frm, to = "0x" + l["topics"][1][-40:], "0x" + l["topics"][2][-40:]
            try:
                blk = int(l.get("blockNumber", "0x0"), 16)
            except Exception:
                blk = 0
            rows.append((frm, to, l, blk))

        # agent -> tx -> {in:[logs], out:[logs], block}
        by_agent_tx = {}
        for frm, to, l, blk in rows:
            txh = l.get("transactionHash")
            if to in agent_set:
                rec = by_agent_tx.setdefault(to, {}).setdefault(txh, {"in": [], "out": [], "block": blk})
                rec["in"].append(l)
            if frm in agent_set:
                rec = by_agent_tx.setdefault(frm, {}).setdefault(txh, {"in": [], "out": [], "block": blk})
                rec["out"].append(l)

        flows, trades, daily, first_funding_day, turnover = classify_transactions(
            agents, by_agent_tx, addr_sym, prices, decimals, day_start_blocks)
        today = {a: (daily[a][-1] if daily[a] else 0) for a in agents}
        json.dump(flows, open(FLOWS_F, "w"))
        _cache_put("activity_v2", {"flows": flows, "trades": trades, "today": today,
                                   "daily": daily, "first_funding_day": first_funding_day,
                                   "turnover": turnover})
        return flows, trades, today, daily, first_funding_day, turnover
    except Exception as ex:
        print("activity scan failed (using cache/zero):", ex)
        try:
            cached = json.load(open(FLOWS_F))
            return ({a: float(cached.get(a, 0.0)) for a in agents}, {a: 0 for a in agents},
                    {a: 0 for a in agents}, daily, first_funding_day, turnover)
        except Exception:
            return ({a: 0.0 for a in agents}, {a: 0 for a in agents},
                    {a: 0 for a in agents}, daily, first_funding_day, turnover)


def block_at_ts(target_ts):
    """First BSC block with timestamp >= target_ts (binary search)."""
    latest = int(rpc("eth_blockNumber", []), 16)

    def ts_of(n):
        r = _post({"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber",
                   "params": [hex(n), False]})
        return int(r["result"]["timestamp"], 16)

    lo, hi = max(0, latest - 500000), latest
    if ts_of(lo) >= target_ts:
        return lo
    while lo < hi:
        mid = (lo + hi) // 2
        if ts_of(mid) < target_ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


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
    baseline = {}

    if do_baseline:
        json.dump(vals, open(BASE_F, "w")); baseline = vals
        try:                       # remember the go-live block -> deposit scan starts here
            json.dump({"block": int(rpc("eth_blockNumber", []), 16), "ts": now},
                      open(GOLIVE_F, "w"))
        except Exception:
            pass
    else:
        try:
            golive_base = json.load(open(BASE_F))     # IMMUTABLE go-live snapshot (never rewritten)
        except Exception:
            golive_base = {}
        # Registrations existed well before the original hard-coded event scan range. When
        # enumeration discovers one of those wallets, reconstruct only its missing go-live
        # balance at the frozen block. Existing baselines remain immutable.
        missing_base = [a for a in agents if a not in golive_base]
        if missing_base and RPC:
            try:
                gj0 = json.load(open(GOLIVE_F))
                gl0 = gj0.get("block")
                if gl0:
                    recovered, _ = value_agents(
                        missing_base, tokens, prices, decimals, block=hex(int(gl0)))
                    golive_base.update(recovered)
                    json.dump(golive_base, open(BASE_F, "w"))
                    print("recovered go-live baseline for", len(missing_base), "participants")
            except Exception as e:
                print("missing baseline recovery failed:", e)
        for a in agents:
            gb = golive_base.get(a, 0) or 0
            baseline[a] = gb

    # ---- one on-chain pass: net deposits (capital base) + who traded today ----
    flows = {a: 0.0 for a in agents}
    swaps = {a: 0 for a in agents}
    traded_today = {a: 0 for a in agents}
    daily_swaps = {a: [] for a in agents}
    first_funding_day = {a: None for a in agents}
    turnover = {a: 0.0 for a in agents}
    try:
        gj = json.load(open(GOLIVE_F)); gl = gj.get("block"); gl_ts = gj.get("ts")
    except Exception:
        gl = gl_ts = None
    if gl and not do_baseline:     # no post-go-live flow can exist on the baseline run
        active_days = max(1, min(HACK_DAYS, int((now - (gl_ts or GO_LIVE_TS)) // 86400) + 1))
        day_starts = []
        for i in range(active_days):
            try:
                day_starts.append(block_at_ts((gl_ts or GO_LIVE_TS) + i * 86400))
            except Exception:
                day_starts.append(gl if i == 0 else day_starts[-1])
        (flows, swaps, traded_today, daily_swaps,
         first_funding_day, turnover) = scan_activity(
            agents, gl, day_starts, tokens, prices, decimals)

    # Cost-basis flows are authoritative for PnL and history rebasing. Unlike the light
    # activity scan, they are valued at transaction time.
    try:
        costflow = json.load(open(FLOWS_CB_F))
    except Exception:
        costflow = {}

    # ---- history time-series (append + cap) -> enables sparklines/24h/drawdown ----
    try:
        old_hist = json.load(open(HIST_F))
    except Exception:
        old_hist = []
    # Keep the first observation in each UTC hour: that is the rules-relevant hour-start
    # mark. A current point is used for live PnL but is not persisted repeatedly.
    hourly = {}
    for h in old_hist:
        hourly.setdefault(int(h.get("ts", 0)) // 3600, h)
    hist = [hourly[k] for k in sorted(hourly)]
    snap = {"ts": now, "v": {a: vals.get(a, 0.0) for a in agents},
            "f": {a: round((costflow.get(a, [0.0, 0.0])[0]
                             - costflow.get(a, [0.0, 0.0])[1]), 2) for a in agents}}
    if not hist or hist[-1].get("ts", 0) // 3600 != now // 3600:
        hist.append(snap)
        calc_hist = hist
    else:
        calc_hist = hist + [snap]
    hist = hist[-MAXHIST:]
    json.dump(hist, open(HIST_F, "w"))

    def raw_series(a):
        return [(h["ts"], h["v"].get(a, 0.0), h.get("f", {}).get(a, 0.0))
                for h in calc_hist]

    def drawdown(a):
        # Max peak-to-trough decline of portfolio VALUE, with the peak REBASED whenever external
        # capital moves (a deposit lifts value, a withdrawal drops it — neither is a trading loss).
        # Computing on value (not the deposit-adjusted dollar series, which hovers near zero and
        # blew the % into the thousands) keeps it bounded; rebasing on flow changes stops deposits
        # from registering as drawdown. Real price declines, which carry no flow change, still count.
        raw = [(h["v"].get(a, 0.0), h.get("f", {}).get(a, 0.0)) for h in calc_hist]
        # De-spike single-snapshot price glitches (a held token momentarily unpriced) with median-of-3.
        vs = [x[0] for x in raw]
        clean = list(vs)
        for i in range(1, len(vs) - 1):
            clean[i] = sorted((vs[i - 1], vs[i], vs[i + 1]))[1]
        seg_peak = dd = 0.0
        prev_f = None
        for i, (_, f) in enumerate(raw):
            v = clean[i]
            if prev_f is not None and abs(f - prev_f) > max(0.5, 0.02 * max(v, 1.0)):
                seg_peak = v                           # capital flow -> new segment, rebase the peak
            else:
                seg_peak = max(seg_peak, v)
            if seg_peak > MINCAP:
                dd = max(dd, (seg_peak - v) / seg_peak)
            prev_f = f
        return round(min(dd, 1.0) * 100, 2)            # clamp as a safety net

    import datetime as _dt
    def _day_bounds(n):            # n=1..7 -> (start_ts, end_ts) UTC; Day 1 = Jun 22
        st = _dt.datetime(2026, 6, 21 + n, tzinfo=_dt.timezone.utc).timestamp()
        return int(st), int(st + 86400)

    def _at_or_before(s, ts):      # last snapshot with t <= ts (s ascending)
        val = None
        for row in s:
            t = row[0]
            if t <= ts:
                val = row
            else:
                break
        return val

    def dayret_n(s, n, base):      # flow-neutral close-to-close return for hackathon Day n
        st, en = _day_bounds(n)
        if now < st:               # day hasn't started yet
            return None
        start_row = _at_or_before(s, st)
        if n == 1 and base > MINCAP:
            start_v, start_f = base, 0.0
        elif start_row and start_row[1] > MINCAP:
            start_v, start_f = start_row[1], start_row[2]
        else:
            funded = next((row for row in s if st <= row[0] < en and row[1] > MINCAP), None)
            if not funded:
                return None
            start_v, start_f = funded[1], funded[2]
        end_row = s[-1] if now < en else _at_or_before(s, en)
        if not end_row or start_v < MINCAP:
            return None
        end_adjusted = end_row[1] - (end_row[2] - start_f)
        return round((end_adjusted / start_v - 1) * 100, 2)

    rows = []
    for a in agents:
        s = raw_series(a); v = vals.get(a, 0.0)
        # Deposit-INVARIANT return on the ELIGIBLE sleeve, from cost-basis flow accounting
        # (flows_costbasis.py groups transfers per tx): `dep` = external capital that entered the
        # sleeve (token deposits + BNB->token buys), `wd` = capital that left (token withdrawals +
        # token->BNB cash-outs). Eligible<->eligible swaps are NEUTRAL, so genuine trading gains are
        # kept; only external flows are netted. Deposits go in the DENOMINATOR, withdrawals add back
        # to value -> depositing/withdrawing can't move the rank, only trading does.
        dep, wd = costflow.get(a, (0.0, 0.0))
        allret, b_eff, sim_cost = capital_return(
            v, baseline.get(a), dep, wd, turnover.get(a, 0.0), SIM_COST_BPS)
        is_elig = b_eff > MINCAP                           # late funding is valid capital, not profit
        # A wallet funded at go-live owes every active competition day. A wallet funded later
        # starts owing the daily swap requirement on its funding day.
        counts = list(daily_swaps.get(a, []))
        daily_ok, missing_days = daily_qualification(baseline.get(a) or 0.0, counts)
        win = {"all": allret}                          # All + Day 1..Day 7 (UTC days)
        for n in range(1, HACK_DAYS + 1):
            win["d%d" % n] = dayret_n(s, n, baseline.get(a) or 0.0) if is_elig else None
        rows.append({"agent": a, "value": v, "base": round(b_eff, 2), "dep": round(dep - wd, 2),
                     "trades": swaps.get(a, 0), "traded": daily_ok,
                     "traded_today": traded_today.get(a, 0) >= 1,
                     "daily_trades": counts, "missing_days": missing_days,
                     "sim_cost": round(sim_cost, 4),
                     "ret_pct": allret, "dd_pct": drawdown(a), "eligible": is_elig,
                     "holds": holds.get(a, []), "win": win,
                     "price_flags": [s for s, _ in holds.get(a, []) if s in PRICE_OVERRIDES]})
    def scoring(r):
        return (r.get("eligible", False) and r.get("traded", False)
                and r.get("value", 0) > 1.0 and r.get("dd_pct", 0) < DQ * 100)

    if baseline:
        rows.sort(key=lambda r: (not scoring(r),
                                 -(r["ret_pct"] if r["ret_pct"] is not None else -1e9), r["agent"]))
    else:          # pre-go-live: no returns yet -> just surface the funded agents
        rows.sort(key=lambda r: r["value"], reverse=True)
    rank = 0
    for r in rows:
        if scoring(r):
            rank += 1
            r["rank"] = rank
        else:
            r["rank"] = None

    has_base = bool(baseline)
    elig_rows = [r for r in rows if r.get("eligible")]       # all stats below are over eligible-at-start only
    rets = [r["ret_pct"] for r in elig_rows if r["ret_pct"] is not None]
    stats = {
        "n": len(agents),
        "eligible": sum(1 for r in rows if r.get("eligible")),
        "funded": sum(1 for r in rows if r["value"] > 0),
        "trading": (sum(1 for r in elig_rows if r.get("traded")) if has_base else None),
        "deployed": round(sum(r["value"] for r in rows), 2),
        "in_profit": (sum(1 for r in rows if scoring(r) and (r["ret_pct"] or 0) > 0)
                      if has_base else None),
        "avg_ret": (round(sum(rets) / len(rets), 2) if rets else None),
        "survivors": (sum(1 for r in elig_rows if r["dd_pct"] < DQ * 100) if has_base else None),
        "dq_pct": DQ * 100,
    }
    out = {"generated_ts": now, "n": len(agents), "has_baseline": has_base,
           "stats": stats, "rows": rows,
           "method": {"trade": "eligible-in-and-out-same-tx",
                      "daily_gate": "go-live-funded-or-first-strict-trade-day",
                      "price": "CMC with liquid-BSC-DEX deviation guard",
                      "sim_cost_bps": SIM_COST_BPS, "price_overrides": PRICE_OVERRIDES}}
    json.dump(out, open(OUT_F, "w"))

    print(f"participants {len(agents)} | baseline {has_base} | funded {stats['funded']} | deployed ${stats['deployed']}")
    for r in rows[:8]:
        print(f"  #{r['rank']:>2} {r['agent']} ${r['value']} ret={r['ret_pct']} trades={r['trades']} dd={r['dd_pct']}")


if __name__ == "__main__":
    main()

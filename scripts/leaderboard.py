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
LAZY_F = os.path.join(ROOT, "dashboard", "lb_lazy.json")    # late-funders' first-funded baseline
BNB_DEP_F = os.path.join(ROOT, "dashboard", "bnb_deposits.json")  # native-BNB deposits (bnb_deposits.py)
LASTPX_F = os.path.join(ROOT, "dashboard", "last_prices.json")    # carry-forward price store (feed-gap guard)
MAXHIST = 400          # ~8 days at 30-min cadence
MINCAP = 0.1           # everyone who traded gets a PnL; only true dust (< $0.10) is skipped
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
        for s, v in d.items():
            if v.get("address"):
                tokens[s] = v["address"]
                decimals[s] = v.get("decimals", 18)
                prices[s] = float(v.get("priceUsd", 0) or 0)   # static fallback base
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

    Counts eligible BEP-20 balances AND native BNB. Native BNB must be valued or an agent
    that holds BNB at go-live and swaps it to tokens shows a fake gain (token->BNB a fake
    loss); counting it both at baseline and now makes BNB<->token rebalances neutral.
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


def scan_activity(agents, golive_block, day_start_block, tokens, prices, decimals):
    """One getLogs pass over agents' BEP-20 Transfers since go-live, classified by the
    COUNTERPARTY (the non-agent side), resolved via eth_getCode:

      * counterparty is a CONTRACT (DEX router / pair / aggregator) -> a TRADE leg.
        This catches token<->token AND BNB<->token swaps (where only one token leg
        shows on-chain, the other being native BNB) -> robust 'did they trade'.
      * counterparty is an EOA -> a capital flow: inbound = deposit, outbound = withdrawal.

    Returns (flows, trades):
      flows[a]  = net external deposit USD since go-live (EOA legs, in - out) -> the
                  deposit-invariant baseline adjustment.
      trades[a] = count of distinct txs with a contract-counterparty leg on/after
                  day_start_block -> 'traded today' (>=1 swap/UTC-day to stay ranked).

    Caveat: a deposit routed through a contract (a bridge) reads as a trade, not a flow.
    getLogs + eth_getCode based; cached CACHE_TTL s; fail-safe -> cached/zeros."""
    flows = {a: 0.0 for a in agents}
    trades = {a: 0 for a in agents}
    if not RPC or not agents:
        return flows, trades
    cached = _cache_get("activity")
    if cached is not None:
        f, t = cached.get("flows", {}), cached.get("trades", {})
        return ({a: float(f.get(a, 0.0)) for a in agents}, {a: int(t.get(a, 0)) for a in agents})
    try:
        latest = int(rpc("eth_blockNumber", []), 16)
        if golive_block >= latest:
            return flows, trades
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

        seen, rows, cps = set(), [], set()
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
            cps.add(to if frm in agent_set else frm)
        cps = list(cps)
        is_contract = {}
        codes = rpc_batch([("eth_getCode", [c, "latest"]) for c in cps]) if cps else []
        for c, r in zip(cps, codes):
            is_contract[c] = r not in (None, "0x", "0x0", "")
        traded_tx = {}
        for frm, to, l, blk in rows:
            if to in agent_set and frm not in agent_set:
                agent, cp, inbound = to, frm, True
            elif frm in agent_set and to not in agent_set:
                agent, cp, inbound = frm, to, False
            else:
                continue                            # agent<->agent: skip
            if is_contract.get(cp):                 # DEX leg -> a trade
                if blk >= day_start_block:
                    traded_tx.setdefault(agent, set()).add(l.get("transactionHash"))
                continue
            sym = addr_sym.get(l.get("address", "").lower())          # EOA leg -> capital flow
            price = float(prices.get(sym, 0) or 0) if sym else 0
            if price <= 0:
                continue
            try:
                usd = int(l["data"], 16) / (10 ** decimals.get(sym, 18)) * price
            except Exception:
                continue
            if usd > 0:
                flows[agent] = flows.get(agent, 0.0) + (usd if inbound else -usd)
        flows = {a: round(flows.get(a, 0.0), 2) for a in agents}
        trades = {a: len(traded_tx.get(a, ())) for a in agents}
        json.dump(flows, open(FLOWS_F, "w"))
        _cache_put("activity", {"flows": flows, "trades": trades})
        return flows, trades
    except Exception as ex:
        print("activity scan failed (using cache/zero):", ex)
        try:
            cached = json.load(open(FLOWS_F))
            return ({a: float(cached.get(a, 0.0)) for a in agents}, {a: 0 for a in agents})
        except Exception:
            return ({a: 0.0 for a in agents}, {a: 0 for a in agents})


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
    funded_credit = {}          # per-agent: initial funding that set a lazy baseline (not a deposit)

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
        try:
            lazy = json.load(open(LAZY_F))
        except Exception:
            lazy = {}
        # Late funders (go-live value < MINCAP) get their baseline anchored to the FIRST funded
        # snapshot. Crucially we ALSO remember that funding amount (funded_credit) so it is NOT
        # double-counted as a deposit later — the double-count was showing them at -100%.
        changed = False
        for a in agents:
            if (golive_base.get(a, 0) or 0) < MINCAP and vals.get(a, 0) >= MINCAP and a not in lazy:
                lazy[a] = vals.get(a, 0); changed = True
        if changed:
            try:
                json.dump(lazy, open(LAZY_F, "w"))
            except Exception:
                pass
        for a in agents:
            gb = golive_base.get(a, 0) or 0
            if gb >= MINCAP:
                baseline[a] = gb
            else:
                baseline[a] = lazy.get(a, gb)
                funded_credit[a] = max(0.0, baseline[a] - gb)   # exclude initial funding from deposits

    # ---- one on-chain pass: net deposits (capital base) + who traded today ----
    flows = {a: 0.0 for a in agents}
    swaps = {a: 0 for a in agents}
    try:
        gj = json.load(open(GOLIVE_F)); gl = gj.get("block"); gl_ts = gj.get("ts")
    except Exception:
        gl = gl_ts = None
    if gl and not do_baseline:     # no post-go-live flow can exist on the baseline run
        import datetime as _dt0
        day0 = int(_dt0.datetime.now(_dt0.timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0).timestamp())
        if gl_ts:
            day0 = max(day0, gl_ts)        # Day 1: day-start == go-live
        try:
            dsb = block_at_ts(day0)
        except Exception:
            dsb = gl
        flows, swaps = scan_activity(agents, gl, dsb, tokens, prices, decimals)

    # Cap funded_credit at the actually-DETECTED inflow. The credit only exists to undo a
    # double-count (funding counted as BOTH baseline and deposit). If the funding came via a
    # contract (not detected as a flow), there's nothing to undo -> capping prevents an
    # over-subtraction that otherwise shows late funders at a fake +100%.
    for a in agents:
        if funded_credit.get(a):
            funded_credit[a] = min(funded_credit[a], max(0.0, flows.get(a, 0.0)))

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

    def drawdown(a):
        # Max peak-to-trough decline of portfolio VALUE, with the peak REBASED whenever external
        # capital moves (a deposit lifts value, a withdrawal drops it — neither is a trading loss).
        # Computing on value (not the deposit-adjusted dollar series, which hovers near zero and
        # blew the % into the thousands) keeps it bounded; rebasing on flow changes stops deposits
        # from registering as drawdown. Real price declines, which carry no flow change, still count.
        raw = [(h["v"].get(a, 0.0), h.get("f", {}).get(a, 0.0)) for h in hist]
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
    HACK_DAYS = 7                  # Jun 22..28 UTC -> Day 1..Day 7
    def _day_bounds(n):            # n=1..7 -> (start_ts, end_ts) UTC; Day 1 = Jun 22
        st = _dt.datetime(2026, 6, 21 + n, tzinfo=_dt.timezone.utc).timestamp()
        return int(st), int(st + 86400)

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

    try:
        bnb_dep = json.load(open(BNB_DEP_F))           # native-BNB deposits (EOA-funded) per agent
    except Exception:
        bnb_dep = {}

    rows = []
    for a in agents:
        s = series(a); v = vals.get(a, 0.0)
        # Deposit-INVARIANT return on the ELIGIBLE sleeve. The stake is the go-live eligible value
        # plus ALL capital that later crossed into the scored portfolio: EOA token transfers
        # (`flows`) and native-BNB<->eligible conversions (`bnb_dep`) — BNB isn't a scored asset,
        # so buying eligible with it is a deposit, selling back a withdrawal. Capital-in lives in
        # the DENOMINATOR, never subtracted from value (on a tiny base a subtraction would credit
        # the whole grown deposit to the original stake -> the +500% dust artifact).
        net = flows.get(a, 0.0)                               # signed EOA token flow (in - out)
        conv = bnb_dep.get(a, 0.0) or 0.0                     # net BNB->eligible conversion (signed)
        cap_in = max(0.0, net) + max(0.0, conv)               # capital deposited into the sleeve
        cap_out = max(0.0, -net) + max(0.0, -conv)            # capital withdrawn -> added back to value
        if a in funded_credit:
            # Late funder: go-live eligible ~ 0, so the stake IS the capital it injected (conversions
            # + token deposits). Fall back to the lazy first-funded snapshot only if untraceable.
            b_eff = cap_in if cap_in > MINCAP else (baseline.get(a) or 0.0)
        else:
            b_eff = (baseline.get(a) or 0.0) + cap_in         # real go-live stake + later deposits
        allret = round(((v + cap_out) / b_eff - 1) * 100, 2) if b_eff > MINCAP else None
        win = {"all": allret}                          # All + Day 1..Day 7 (UTC days)
        for n in range(1, HACK_DAYS + 1):
            win["d%d" % n] = dayret_n(s, n, b_eff)
        rows.append({"agent": a, "value": v, "base": round(b_eff, 2), "dep": round(cap_in - cap_out, 2),
                     "trades": swaps.get(a, 0), "traded": swaps.get(a, 0) >= 1,
                     "ret_pct": allret, "dd_pct": drawdown(a),
                     "holds": holds.get(a, []), "win": win})
    if baseline:   # live: active traders first (>=1 swap today), then by return; ties neutral
        rows.sort(key=lambda r: (not r["traded"],
                                 -(r["ret_pct"] if r["ret_pct"] is not None else -1e9), r["agent"]))
    else:          # pre-go-live: no returns yet -> just surface the funded agents
        rows.sort(key=lambda r: r["value"], reverse=True)
    for i, r in enumerate(rows):
        r["rank"] = i + 1

    has_base = bool(baseline)
    rets = [r["ret_pct"] for r in rows if r["ret_pct"] is not None]
    stats = {
        "n": len(agents),
        "funded": sum(1 for r in rows if r["value"] > 0),
        "trading": (sum(1 for r in rows if r.get("traded")) if has_base else None),
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
        print(f"  #{r['rank']:>2} {r['agent']} ${r['value']} ret={r['ret_pct']} trades={r['trades']} dd={r['dd_pct']}")


if __name__ == "__main__":
    main()

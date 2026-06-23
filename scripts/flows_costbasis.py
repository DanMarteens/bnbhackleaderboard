#!/usr/bin/env python3
"""Cost-basis flow accounting: separate EXTERNAL capital (deposits/withdrawals) from
INTERNAL trades, per agent, from real on-chain transfers (NodeReal).

For each tx touching the wallet we look at its ELIGIBLE-token legs only and group by tx hash:
  * eligible came IN *and* OUT in the same tx  -> a swap (eligible<->eligible) -> NEUTRAL (trading).
  * eligible only IN  -> a DEPOSIT into the scored sleeve (covers token deposits AND BNB->token
                         buys, where the BNB leg is non-eligible so only the token-in shows).
  * eligible only OUT -> a WITHDRAWAL (covers token transfers out AND token->BNB cash-outs).
Legs are valued at the price AT THE TRANSACTION'S BLOCK (PancakeSwap getAmountsOut on the
archive RPC), NOT the current price: a volatile-token deposit that later halves must enter the
cost basis at its value WHEN it arrived, so the subsequent decline shows as a real trading loss
rather than vanishing. Stablecoins are $1; if the historical route can't be quoted we fall back
to the current CMC price.

Writes dashboard/flows_costbasis.json = {agent: [deposits_usd, withdrawals_usd]}. The board then
uses return = (value + withdrawals) / (go-live stake + deposits) - 1, so external flows never
move the rank -- only trading does -- and genuine trading gains are NOT netted out.
"""
import os, sys, json, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import leaderboard as L
from eth_abi import encode as abi_encode, decode as abi_decode

ROUTER = "0x10ED43C718714eb63d5aA57B78B54704E256024E"   # PancakeSwap V2 router
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
USDT_A = "0x55d398326f99059fF775485246999027B3197955"
_GAO_SEL = "0x" + L.keccak(b"getAmountsOut(uint256,address[])")[:4].hex()
_px_at = {}                                             # (token_addr, block_hex) -> usd price, cached
STABLE_ADDRS = set()                                    # eligible stablecoin addresses (populated in main)

OUT_F = os.path.join(ROOT, "dashboard", "flows_costbasis.json")
GOLIVE_F = os.path.join(ROOT, "dashboard", "golive.json")
PART_F = os.path.join(ROOT, "dashboard", "participants.json")
REFRESH_S = 840
RPC = os.environ.get("ARCHIVE_RPC", "")


def rpc(method, params):
    r = json.load(urllib.request.urlopen(urllib.request.Request(
        RPC, json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        {"Content-Type": "application/json"}), timeout=45))
    if "error" in r:
        raise RuntimeError(r["error"])
    return r.get("result")


def _transfers(addr, role, golive_hex, latest_hex):
    """All ERC-20 transfers for addr in one direction since go-live (paginated)."""
    out, page = [], None
    for _ in range(25):
        p = {"category": ["20"], role: addr,
             "fromBlock": golive_hex, "toBlock": latest_hex, "maxCount": "0x3e8"}
        if page:
            p["pageKey"] = page
        r = rpc("nr_getAssetTransfers", [p]) or {}
        out += r.get("transfers") or []
        page = r.get("pageKey")
        if not page:
            break
    return out


def _price_at_block(token_addr, decimals, block_hex, px_by_addr):
    """USD price of one whole token at a historical block, via PancakeSwap getAmountsOut.

    Tries token->USDT then token->WBNB->USDT. Falls back to the current CMC price if the
    historical route can't be quoted (e.g. pool didn't exist yet / archive drop)."""
    ca = token_addr.lower()
    if ca == USDT_A.lower() or ca in STABLE_ADDRS:
        return 1.0
    key = (ca, block_hex)
    if key in _px_at:
        return _px_at[key]
    px = 0.0
    for path in ([token_addr, USDT_A], [token_addr, WBNB, USDT_A]):
        try:
            data = _GAO_SEL + abi_encode(["uint256", "address[]"], [10 ** decimals, path]).hex()
            r = rpc("eth_call", [{"to": ROUTER, "data": data}, block_hex])
            if r and r != "0x":
                amounts = abi_decode(["uint256[]"], bytes.fromhex(r[2:]))[0]
                px = amounts[-1] / 1e18                  # USDT has 18 decimals on BSC
                if px > 0:
                    break
        except Exception:
            continue
    if px <= 0:
        px = px_by_addr.get(ca, 0.0)                     # fallback: current CMC price
    _px_at[key] = px
    return px


def _leg_usd(t, px_by_addr):
    """USD value of a transfer leg, priced AT ITS OWN BLOCK, if the token is eligible else 0."""
    ca = (t.get("contractAddress") or "").lower()
    if ca not in px_by_addr:                             # not an eligible-priced token -> ignore
        return 0.0
    try:
        dec = int(t.get("decimal", 18))
        amt = int(t["value"], 16) / (10 ** dec)
    except Exception:
        return 0.0
    block_hex = t.get("blockNum") or "latest"
    return amt * _price_at_block(t["contractAddress"], dec, block_hex, px_by_addr)


def agent_flows(addr, px_by_addr, golive_hex, latest_hex):
    by_tx = {}
    for t in _transfers(addr, "toAddress", golive_hex, latest_hex):
        v = _leg_usd(t, px_by_addr)
        if v > 0:
            by_tx.setdefault(t.get("hash"), [0.0, 0.0])[0] += v       # [in, out]
    for t in _transfers(addr, "fromAddress", golive_hex, latest_hex):
        v = _leg_usd(t, px_by_addr)
        if v > 0:
            by_tx.setdefault(t.get("hash"), [0.0, 0.0])[1] += v
    dep = wd = 0.0
    for _, (vin, vout) in by_tx.items():
        if vin > 0 and vout > 0:
            continue                 # eligible<->eligible swap -> trading, neutral
        elif vin > 0:
            dep += vin               # deposit (token in, or BNB->token buy)
        elif vout > 0:
            wd += vout               # withdrawal (token out, or token->BNB cash-out)
    return round(dep, 2), round(wd, 2)


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

    tokens, prices, _ = L.load_tokens()                  # symbol -> addr, symbol -> price
    px_by_addr = {addr.lower(): prices.get(sym, 0.0) for sym, addr in tokens.items() if prices.get(sym)}
    STABLE_ADDRS.update(tokens[s].lower() for s in L.STABLES if s in tokens)   # pinned to $1 at any block
    golive = json.load(open(GOLIVE_F)).get("block")
    latest = int(rpc("eth_blockNumber", []), 16)
    if not golive:
        return
    golive_hex, latest_hex = hex(golive), hex(latest)

    out = {}
    for a in sorted(agents):
        try:
            dep, wd = agent_flows(a, px_by_addr, golive_hex, latest_hex)
            if dep > 0.01 or wd > 0.01:
                out[a] = [dep, wd]
        except Exception as e:
            print("flows_costbasis: %s -> %s" % (a[:10], str(e)[:80]), file=sys.stderr)
    json.dump(out, open(OUT_F, "w"))
    print("flows_costbasis: %d agents, %d with flows | deposits $%.0f, withdrawals $%.0f"
          % (len(agents), len(out), sum(v[0] for v in out.values()), sum(v[1] for v in out.values())))


if __name__ == "__main__":
    main()

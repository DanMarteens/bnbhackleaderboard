#!/usr/bin/env python3
"""Resolve eligible symbols that still lack a BSC contract, via the CoinMarketCap MCP.

For each missing eligible symbol we search CMC for same-symbol candidates, then read each
candidate's get_crypto_info and pull the BEP-20 address out of its explorer URLs (CMC's
`platform` field is only the token's PRIMARY chain, which for bridged majors like SHIB is
Ethereum, not BSC). The first candidate that has a real BSC contract wins — that disambiguates
collisions like B / NFT / IP, because the *eligible* token is by definition the BSC-tradeable
one. Decimals are read on-chain (authoritative). Run with --write to persist; default is a
review dump so the resolutions can be eyeballed before they touch valuation.
"""
import os, re, sys, json, time, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import leaderboard as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ELIG_F = os.path.join(ROOT, "config", "eligible_symbols.json")
IDS_F = os.path.join(ROOT, "config", "cmc_ids.json")
CON_F = os.path.join(ROOT, "config", "bsc_contracts.json")
RPC = os.environ.get("ARCHIVE_RPC", "")
BSC_RE = re.compile(r"bscscan\.com/(?:token|address)/(0x[0-9a-fA-F]{40})")
WRITE = "--write" in sys.argv

# CMC's MCP exposes only a token's PRIMARY chain, so bridged majors below show no BSC
# contract via get_crypto_info. These BSC addresses were each confirmed on-chain by calling
# symbol() (USD1->"USD1", TON->"TONCOIN", BONK->"Bonk"); ids are the CMC quote ids for price.
CONFIRMED_BSC = {
    "USD1": {"id": 36148, "address": "0x8d0D000Ee44948FC98c9B98A4FA4921476f08B0d", "stable": True},
    "TON":  {"id": 11419, "address": "0x76A797A59Ba2C17726896976B7B3747BfD1d220f", "stable": False},
    "BONK": {"id": 23095, "address": "0xA697e272a73744b343528C3Bc4702F2565b2F422", "stable": False},
}


def eth_call(to, data):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
               "params": [{"to": to, "data": data}, "latest"]}
    r = json.load(urllib.request.urlopen(urllib.request.Request(
        RPC, json.dumps(payload).encode(), {"Content-Type": "application/json"}), timeout=30))
    return r.get("result")


def onchain_decimals(addr):
    try:
        res = eth_call(addr, "0x313ce567")            # decimals()
        return int(res, 16) if res and res != "0x" else None
    except Exception:
        return None


def bsc_addr_from_info(info):
    if isinstance(info, list) and info:
        info = info[0]
    if not isinstance(info, dict):
        return None
    plat = info.get("platform") or {}
    if (plat.get("slug") == "bnb" or "BEP20" in (plat.get("name") or "")) and plat.get("token_address"):
        return plat["token_address"]
    blob = json.dumps(info.get("urls") or {})
    m = BSC_RE.search(blob)
    return m.group(1) if m else None


def resolve(sym, sid):
    if sym in CONFIRMED_BSC:
        c = CONFIRMED_BSC[sym]
        return {"id": c["id"], "name": "confirmed-peg", "address": c["address"],
                "decimals": onchain_decimals(c["address"]), "rank": None, "stable": c["stable"]}
    r = L._cmc_tool("search_cryptos", {"query": sym}, sid) or []
    cand = [x for x in r if isinstance(x, dict) and x.get("symbol") == sym]
    cand = sorted(cand, key=lambda x: x.get("rank") or 1e9)
    for c in cand[:5]:
        info = L._cmc_tool("get_crypto_info", {"id": str(c.get("id"))}, sid)
        addr = bsc_addr_from_info(info)
        if addr:
            dec = onchain_decimals(addr)
            return {"id": c.get("id"), "name": c.get("name"), "address": addr,
                    "decimals": dec, "rank": c.get("rank")}
        time.sleep(0.05)
    # no BSC contract on any same-symbol candidate
    top = cand[0] if cand else None
    return {"id": (top or {}).get("id"), "name": (top or {}).get("name"),
            "address": None, "decimals": None, "rank": (top or {}).get("rank")}


def main():
    elig = json.load(open(ELIG_F))
    ids = json.load(open(IDS_F))
    con = json.load(open(CON_F))
    missing = [s for s in elig if s not in con]
    print("resolving %d missing eligible symbols\n" % len(missing))
    sid = L._cmc_session()
    resolved, unresolved = {}, []
    print("%-10s %-7s %-22s %-44s %s" % ("SYMBOL", "id", "name", "bsc_contract", "dec"))
    for s in missing:
        try:
            res = resolve(s, sid)
        except Exception as e:
            res = {"id": None, "name": "ERR:" + str(e)[:30], "address": None, "decimals": None}
        print("%-10s %-7s %-22s %-44s %s" % (
            s, res.get("id"), str(res.get("name"))[:22], res.get("address") or "-- NO BSC --",
            res.get("decimals")))
        if res.get("address") and res.get("decimals") is not None:
            resolved[s] = res
        else:
            unresolved.append(s)
        time.sleep(0.05)

    print("\nresolved %d / %d ; unresolved: %s" % (len(resolved), len(missing), unresolved))

    if not WRITE:
        print("\n(review only — re-run with --write to persist)")
        return

    for s, res in resolved.items():
        ids[s] = res["id"]
        con[s] = {"address": res["address"], "decimals": res["decimals"],
                  "priceUsd": 0.0, "ambiguous": True, "stable": bool(res.get("stable"))}
    json.dump(ids, open(IDS_F, "w"), indent=0)
    json.dump(con, open(CON_F, "w"), indent=0)
    print("\nWROTE %d new contracts -> cmc_ids.json (%d), bsc_contracts.json (%d)"
          % (len(resolved), len(ids), len(con)))


if __name__ == "__main__":
    main()

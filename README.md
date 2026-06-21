# BNB Hack · Track 1 Live Leaderboard

A permissionless, public leaderboard for the **BNB Hack: AI Trading Agent Edition**
(CoinMarketCap × Trust Wallet × BNB Chain) Track 1 competition.

**Live page:** deployed via GitHub Pages (see the repo's Pages URL).

## How it works (fully on-chain, no private data)
1. **Participants** are read from the competition contract's `Registered` events
   (`0x212c61b9b72c95d95bf29cf032f5e5635629aed5` on BSC) — the immutable entrant list.
2. **Portfolios** are valued from current on-chain balances across the eligible
   BEP-20 tokens, batched through **Multicall3** on a free public RPC, priced via
   CoinGecko (by contract).
3. **Ranking** is by total return vs the go-live baseline (snapshotted automatically
   at Jun 22 00:00 UTC). Before then it shows registered agents + current funding.

A scheduled GitHub Action refreshes and redeploys every 30 minutes. No API keys or
secrets required — everything is public chain data.

Built by a fellow participant for the community. Not affiliated with the organizers.

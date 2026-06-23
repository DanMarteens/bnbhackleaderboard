# BNB Hack · Track 1 Live Leaderboard

A permissionless, public leaderboard for the **BNB Hack: AI Trading Agent Edition**
(CoinMarketCap × Trust Wallet × BNB Chain) Track 1 competition.

**Live page:** deployed via GitHub Pages (see the repo's Pages URL).

## How it works (fully on-chain, no private data)
1. **Participants** are read from the competition contract's `Registered` events
   (`0x212c61b9b72c95d95bf29cf032f5e5635629aed5` on BSC) — the immutable entrant list.
2. **Portfolios** are valued from current on-chain balances across the eligible
   BEP-20 tokens, batched through **Multicall3**. CMC is the primary mark; a deep
   BSC DEX price overrides it only when the two diverge materially, preventing
   instant paper profits from mismatched or stale CMC quotes.
3. **Trades** are counted strictly: a transaction must contain both an eligible
   token entering and an eligible token leaving the agent. BNB conversions,
   deposits, withdrawals and one-sided transfers do not count.
4. **Ranking** is deposit-neutral total return. Late capital enters at transaction-time
   cost basis. For a zero-start wallet, the daily obligation begins with its first strict
   eligible swap, so funding earlier cannot create a retroactive missed-day penalty.

## Deposits do **not** affect PnL

Return is measured against contributed capital, with external withdrawals added back:

```
PnL% = (current value + withdrawals − simulated costs)
       ÷ (go-live capital + later deposits) − 1
```

A top-up adds equally to current value and contributed cost basis, while a withdrawal
is added back to value. **Moving capital cannot create profit.** Only changes in the
eligible trading sleeve move return.

How flows are detected: eligible BEP-20 `Transfer` logs are grouped by wallet and
transaction. Both directions means a trade; inbound-only is a deposit and outbound-only
is a withdrawal. This works for routers, bridges and smart wallets without guessing from
the counterparty type. Native BNB is outside the eligible sleeve; BNB→token is therefore
capital entering the sleeve, not a qualifying trade.

Go-live-funded wallets owe every UTC competition day. Zero-start wallets are evaluated
from their first strict swap day. Drawdown uses hour-start marks and rebases when capital moves.

A scheduled GitHub Action refreshes and redeploys every 30 minutes, and re-enumerates
new registrants once a day. No API keys or secrets required — everything is public
chain data.

Built by a fellow participant for the community. Not affiliated with the organizers.

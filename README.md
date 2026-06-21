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

## Deposits do **not** affect PnL

Return is measured against the wallet's **fixed go-live capital**, with external
deposits and withdrawals removed:

```
PnL% = (current value − net deposits since go-live) ÷ go-live capital − 1
```

A top-up adds equally to *current value* and to *net deposits*, so the numerator is
unchanged and the denominator is fixed — **the PnL is identical before and after the
deposit.** Withdrawing is the same in reverse. Only actual trading moves the rank;
you cannot climb (or fall) by moving money in or out of the wallet.

How deposits are detected: inbound BEP-20 `Transfer` logs since the go-live block are
classified per transaction — a tx where the wallet both receives *and* sends a token
is a trade (swap / LP) and ignored; **inbound-only is a deposit, outbound-only is a
withdrawal.** This catches funds routed through any contract (bridge, CEX, smart
wallet), not just plain wallet sends. Wallets with detected deposits show a `+$X dep`
tag for transparency. (Limitation: native-BNB top-ups that are then swapped aren't
tracked — but native BNB isn't counted toward value either, so a plain BNB deposit
can't inflate it.)

A scheduled GitHub Action refreshes and redeploys every 30 minutes, and re-enumerates
new registrants once a day. No API keys or secrets required — everything is public
chain data.

Built by a fellow participant for the community. Not affiliated with the organizers.

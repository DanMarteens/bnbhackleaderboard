import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import leaderboard as L


AGENT = "0x1111111111111111111111111111111111111111"
USDT = "0x2222222222222222222222222222222222222222"
SIREN = "0x3333333333333333333333333333333333333333"


def leg(token, amount):
    return {"address": token, "data": hex(int(amount * 10**18))}


class ScoringRulesTest(unittest.TestCase):
    def test_only_two_sided_eligible_transaction_is_a_trade(self):
        txs = {
            AGENT: {
                "deposit": {"in": [leg(USDT, 10)], "out": [], "block": 110},
                "bnb_buy": {"in": [leg(SIREN, 100)], "out": [], "block": 120},
                "swap_d1": {
                    "in": [leg(SIREN, 100)], "out": [leg(USDT, 5)], "block": 130,
                },
                "withdrawal": {"in": [], "out": [leg(USDT, 2)], "block": 210},
                "swap_d2": {
                    "in": [leg(USDT, 4)], "out": [leg(SIREN, 80)], "block": 220,
                },
            }
        }
        flows, trades, daily, first_day, turnover = L.classify_transactions(
            [AGENT], txs, {USDT: "USDT", SIREN: "SIREN"},
            {"USDT": 1.0, "SIREN": 0.05}, {"USDT": 18, "SIREN": 18}, [100, 200],
        )

        self.assertEqual(trades[AGENT], 2)
        self.assertEqual(daily[AGENT], [1, 1])
        self.assertEqual(first_day[AGENT], 0)
        self.assertEqual(turnover[AGENT], 9.0)
        # deposit $10 + one-sided BNB buy $5 - withdrawal $2
        self.assertEqual(flows[AGENT], 13.0)

    def test_daily_gate_starts_when_capital_enters(self):
        self.assertEqual(L.daily_qualification(10, [1, 1]), (True, []))
        self.assertEqual(L.daily_qualification(10, [1, 0]), (False, [2]))
        self.assertEqual(L.daily_qualification(0, [0, 1]), (True, []))
        self.assertEqual(L.daily_qualification(0, [0, 0]), (False, []))

    def test_deposits_and_withdrawals_cannot_create_profit(self):
        self.assertEqual(L.capital_return(100, 100, 0, 0)[0], 0.0)
        self.assertEqual(L.capital_return(150, 100, 50, 0)[0], 0.0)
        self.assertEqual(L.capital_return(70, 100, 0, 30)[0], 0.0)
        self.assertEqual(L.capital_return(0, 0, 0, 0)[0], None)

    def test_liquid_dex_guard_blocks_false_cmc_profit(self):
        prices = {"SIREN": 0.078, "BILL": 1.0, "ETH": 2000, "USDT": 1}
        overrides = L.apply_dex_guard(prices, {
            "SIREN": {"price": 0.042, "liquidity": 2_000_000},
            "BILL": {"price": 0.052, "liquidity": 100_000},
            "ETH": {"price": 1980, "liquidity": 10_000_000},
            "USDT": {"price": 0.8, "liquidity": 10_000_000},
        })
        self.assertEqual(prices["SIREN"], 0.042)
        self.assertEqual(prices["BILL"], 0.052)
        self.assertEqual(prices["ETH"], 2000)
        self.assertEqual(prices["USDT"], 1)
        self.assertEqual(set(overrides), {"SIREN", "BILL"})


if __name__ == "__main__":
    unittest.main()

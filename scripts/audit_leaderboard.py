#!/usr/bin/env python3
"""Fail-closed production audit for leaderboard accounting invariants."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASH = os.path.join(ROOT, "dashboard")


def load(name):
    with open(os.path.join(DASH, name)) as f:
        return json.load(f)


def main():
    board = load("leaderboard.json")
    participants = [a.lower() for a in load("participants.json")]
    baseline = load("lb_baseline.json")
    cost = load("flows_costbasis.json")
    flows = load("flows.json")
    gross = load("flows_gross.json")
    timeline = load("flows_timeline.json")
    rows = board.get("rows", [])
    errors, warnings = [], []

    agents = [r.get("agent", "").lower() for r in rows]
    if len(rows) != len(participants) or set(agents) != set(participants):
        errors.append("leaderboard rows do not exactly match participants")
    if len(agents) != len(set(agents)):
        errors.append("duplicate agent rows")
    if set(cost) != set(participants):
        errors.append("cost-basis coverage is not 100%")
    missing_timeline = sorted(set(participants) - set(timeline))
    if missing_timeline:
        warnings.append("%d agents lack reconstructed flow timelines" % len(missing_timeline))

    for r in rows:
        a = r["agent"].lower()
        dep, wd = cost.get(a, (0.0, 0.0))
        gross_dep, gross_wd = gross.get(a, (0.0, 0.0))
        dep = max(float(dep), float(gross_dep or 0.0))
        wd = max(float(wd), float(gross_wd or 0.0))
        net_flow = float(flows.get(a, 0.0) or 0.0)
        if net_flow > float(dep) + 1.0:
            dep = net_flow
        elif -net_flow > float(wd) + 1.0:
            wd = -net_flow
        capital = float(baseline.get(a, 0.0) or 0.0) + float(dep)
        expected = None
        if capital > 0.1:
            expected = round(
                ((float(r.get("value", 0.0)) + float(wd) - float(r.get("sim_cost", 0.0)))
                 / capital - 1) * 100, 2)
        if expected != r.get("ret_pct"):
            errors.append("%s PnL mismatch: %r != %r" % (a, r.get("ret_pct"), expected))

    ranked = sorted((r for r in rows if r.get("rank") is not None), key=lambda r: r["rank"])
    if [r["rank"] for r in ranked] != list(range(1, len(ranked) + 1)):
        errors.append("rank sequence is not contiguous")
    for r in ranked:
        if not (r.get("eligible") and r.get("traded") and r.get("value", 0) > 1
                and r.get("dd_pct", 0) < board["stats"].get("dq_pct", 30)):
            errors.append("%s is ranked without satisfying gates" % r["agent"])

    print("audit: %d agents, %d ranked, %d errors, %d warnings"
          % (len(rows), len(ranked), len(errors), len(warnings)))
    for msg in warnings:
        print("WARNING:", msg)
    for msg in errors:
        print("ERROR:", msg)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

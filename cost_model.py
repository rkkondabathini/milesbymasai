"""Redemption cost exposure per batch and per learner, from the cumulative report.
Usage: python3 cost_model.py [csv url|file]   (writes data/output/cost_model.csv)"""
import csv, io, json, sys, urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
URL = "https://metabase.masaischool.com/public/question/d9be39f3-dab4-42bc-915f-0766cec6d5db.csv"
CFG = json.loads((ROOT / "config.json").read_text())
R = CFG["rates"]
REWARDS = [(r["name"], r["cost"], r["masai_cost"]) for r in CFG["rewards"]]
PAID = [(c, k) for _, c, k in REWARDS if k > 0]          # rewards that cost Masai money
UNIT = 1000


def n(x):
    return int(float(x)) if str(x).strip() else 0


def base(r):
    m = min(n(r["mandatory_attended_live"]) + n(r["mandatory_attended_rec"]), n(r["mandatory_total"]))
    ml = min(n(r["mandatory_attended_live"]), m)
    q = min(n(r["nonmandatory_attended_live"]) + n(r["nonmandatory_attended_rec"]), n(r["nonmandatory_total"]))
    nl = min(n(r["nonmandatory_attended_live"]), q)
    return (ml * R["mandatory_live"] + (m - ml) * R["mandatory_recorded"] + nl * R["nonmandatory_live"]
            + (q - nl) * R["nonmandatory_recorded"] + n(r["practice_assignment_completed"]) * R["practice_assignment"]
            + n(r["graded_assignment_completed"]) * R["graded_assignment"]
            + n(r["graded_evaluation_completed"]) * R["graded_evaluation"]
            + n(r["mock_evaluation_completed"]) * R["mock_evaluation"])


def ceiling(r):
    return (n(r["mandatory_total"]) * R["mandatory_live"] + n(r["nonmandatory_total"]) * R["nonmandatory_live"]
            + n(r["practice_assignment_total"]) * R["practice_assignment"]
            + n(r["graded_assignment_total"]) * R["graded_assignment"]
            + n(r["graded_evaluation_total"]) * R["graded_evaluation"]
            + n(r["mock_evaluation_total"]) * R["mock_evaluation"])


def max_cost(miles, policy):
    """Worst-case Masai cost for one learner holding `miles`."""
    b = miles // UNIT
    if policy == "one":                   # a single redemption: the costliest one they can afford
        return max([k for c, k in PAID if c <= miles], default=0)
    best = [0] * (b + 1)
    for w, v in [(c // UNIT, k) for c, k in PAID]:
        if policy == "each_once":         # each costed reward at most once (0/1 knapsack)
            for x in range(b, w - 1, -1):
                best[x] = max(best[x], best[x - w] + v)
        else:                              # repeatable (unbounded knapsack)
            for x in range(w, b + 1):
                best[x] = max(best[x], best[x - w] + v)
    return best[b]


POLICIES = (("one", "1 redemption / learner"), ("each_once", "each reward once"), ("repeat", "repeatable"))
MILES = (("today", 1.0), ("today x1.3 boost", 1.3), ("2x engagement x1.3", 2.6))
UPTAKE = (0.25, 0.5, 1.0)

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else URL
    text = (urllib.request.urlopen(src, timeout=120).read().decode("utf-8-sig") if src.startswith("http")
            else open(src, encoding="utf-8-sig").read())
    rows = list({r["student_code"]: r for r in csv.DictReader(io.StringIO(text))}.values())
    batches = defaultdict(list)
    for r in rows:
        batches[r["batch_name"]].append(r)
    batches["ALL BATCHES"] = rows
    out = []
    for b, rs in batches.items():
        cur = [base(r) for r in rs]
        print(f"\n== {b}: {len(rs)} learners | avg Miles now {sum(cur)/len(cur):,.0f} "
              f"| avg ceiling {sum(ceiling(r) for r in rs)/len(rs):,.0f}")
        print(f"{'Miles scenario':<20}{'policy':<24}{'uptake':>7}{'batch cost':>13}{'per learner':>13}")
        for ml, mult in MILES:
            for pol, pl in POLICIES:
                full = sum(max_cost(int(m * mult), pol) for m in cur)
                for up in UPTAKE:
                    cost = full * up
                    out.append({"batch": b, "learners": len(rs), "miles_scenario": ml, "policy": pl,
                                "uptake": up, "batch_cost": round(cost), "cost_per_learner": round(cost / len(rs), 1)})
                    if up == 1.0 or pol == "one":
                        print(f"{ml:<20}{pl:<24}{int(up*100):>6}%{cost:>13,.0f}{cost/len(rs):>13,.0f}")
    Path(ROOT / "data/output").mkdir(parents=True, exist_ok=True)
    with open(ROOT / "data/output/cost_model.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader(); w.writerows(out)

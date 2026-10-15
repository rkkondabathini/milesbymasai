"""Payout simulation: what each learner's Miles are worth in rupees if they redeem.

    python3 ops/payout_sim.py                                  # both batches, public cumulative report
    python3 ops/payout_sim.py --source batch1.csv batch2.csv   # your own Metabase exports (same columns)
    python3 ops/payout_sim.py --revenue-per-student 60000      # adds cost as % of revenue
    python3 ops/payout_sim.py --boost 1.15                     # stand-in for the streak boost (cumulative data has none)

Optional inputs (data/input/):
    revenue.csv               batch_name,revenue_per_student   (overrides --revenue-per-student per batch)
    placement_eligibility.csv email,eligible                   (eligible = 1/0 or yes/no; also accepts learner_id)

Per learner it reports: Miles, the cheapest reward they could claim and its cost (the "minimum"), the costliest single
reward they could claim, and the most Masai could pay if they spent every Mile on the costliest rewards
(each reward once, and repeatable).

Rates and rewards follow the NEW structure agreed for the rollout; they are defined below (not read from the app config)
so the simulation can run before the app is changed. Edit COSTS if a figure changes.
"""
import argparse, csv, io, json, statistics as st, urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGG = "https://metabase.masaischool.com/public/question/d9be39f3-dab4-42bc-915f-0766cec6d5db.csv"

RATES = dict(ml=200, mr=100, nl=150, nr=50, p=100, ga=300, ge=300, me=150)   # new lecture rates

# (reward, Miles needed, cost to Masai in Rs). None = cost not confirmed yet (treated as 0 and flagged).
COSTS = [
    ("1:1 doubt session with your CC (30 min)", 1000, 0),
    ("Mock interview", 5000, 0),
    ("Interview preparation assignment", 5000, 0),
    ("Resume building support", 5000, 0),
    ("1:1 session with a TA (30 min)", 5000, 1500),
    ("Free hackathon entry", 5000, 1000),
    ("Institute t-shirt", 5000, None),
    ("50% off the Campus Immersion fee", 8000, 1000),
    ("Institute hoodie", 8000, None),
    ("1:1 session with an IM (30 min)", 20000, 4000),
    ("100% off a one-month AI tool subscription", 20000, 2500),   # 80% was Rs 2,000; assumed Rs 2,500 for 100%
    ("Interview with a company", 25000, None),
    ("Participation in hiring drive", 25000, None),
]
DRIVE_MILES = 25000
UNIT = 1000


def n(x):
    return int(float(x)) if str(x).strip() else 0


def split(sched, live, rec):
    cap = sched if sched else live + rec
    l = min(live, cap)
    return l, min(rec, cap - l)


def miles_of(r, boost):
    ml, mr = split(n(r["mandatory_total"]), n(r["mandatory_attended_live"]), n(r["mandatory_attended_rec"]))
    nl, nr = split(n(r["nonmandatory_total"]), n(r["nonmandatory_attended_live"]), n(r["nonmandatory_attended_rec"]))
    base = (ml * RATES["ml"] + mr * RATES["mr"] + nl * RATES["nl"] + nr * RATES["nr"]
            + n(r["practice_assignment_completed"]) * RATES["p"] + n(r["graded_assignment_completed"]) * RATES["ga"]
            + n(r["graded_evaluation_completed"]) * RATES["ge"] + n(r["mock_evaluation_completed"]) * RATES["me"])
    return int(base * boost)


def ceiling(r):
    return (n(r["mandatory_total"]) * RATES["ml"] + n(r["nonmandatory_total"]) * RATES["nl"]
            + n(r["practice_assignment_total"]) * RATES["p"] + n(r["graded_assignment_total"]) * RATES["ga"]
            + n(r["graded_evaluation_total"]) * RATES["ge"] + n(r["mock_evaluation_total"]) * RATES["me"])


def knap(budget, items, repeat):
    best = [0] * (budget // UNIT + 1)
    for w, v in items:
        w //= UNIT
        rng = range(w, len(best)) if repeat else range(len(best) - 1, w - 1, -1)
        for x in rng:
            best[x] = max(best[x], best[x - w] + v)
    return best[-1]


def load(srcs):
    rows = []
    for s in srcs:
        t = (urllib.request.urlopen(s, timeout=120).read().decode("utf-8-sig") if s.startswith("http")
             else Path(s).read_text(encoding="utf-8-sig"))
        rows += list(csv.DictReader(io.StringIO(t)))
    return list({r["student_code"]: r for r in rows}.values())     # one row per learner


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", nargs="+", default=[AGG])
    ap.add_argument("--boost", type=float, default=1.0)
    ap.add_argument("--revenue-per-student", type=float, default=None)
    a = ap.parse_args()

    rev = {}
    p = ROOT / "data/input/revenue.csv"
    if p.exists():
        rev = {r["batch_name"]: float(r["revenue_per_student"]) for r in csv.DictReader(open(p))}
    elig = {}
    p = ROOT / "data/input/placement_eligibility.csv"
    if p.exists():
        for r in csv.DictReader(open(p)):
            key = (r.get("email") or r.get("learner_id") or "").strip().lower()
            elig[key] = str(r.get("eligible", "")).strip().lower() in ("1", "yes", "y", "true", "eligible")

    unknown = [r for r, _, c in COSTS if c is None]
    cost = lambda c: 0 if c is None else c
    items_all = [(m, cost(c)) for _, m, c in COSTS if cost(c) > 0]

    out, by = [], defaultdict(list)
    for r in load(a.source):
        m = miles_of(r, a.boost)
        aff = [(nm, mi, cost(c)) for nm, mi, c in COSTS if mi <= m]
        cheapest = min(aff, key=lambda x: (x[2], x[1])) if aff else None
        priciest = max(aff, key=lambda x: (x[2], x[1])) if aff else None
        budget = [(mi, c) for mi, c in items_all if mi <= m]
        row = {
            "learner_id": r["student_code"], "name": r.get("student_name", ""), "email": r.get("email", ""),
            "batch": r["batch_name"], "miles": m, "rewards_affordable": len(aff),
            "min_reward": cheapest[0] if cheapest else "", "min_cost": cheapest[2] if cheapest else 0,
            "max_single_reward": priciest[0] if priciest else "", "max_single_cost": priciest[2] if priciest else 0,
            "max_total_each_once": knap(m, budget, False) if budget else 0,
            "max_total_repeat": knap(m, budget, True) if budget else 0,
            "ceiling_miles": ceiling(r), "drive_miles_eligible": int(m >= DRIVE_MILES),
        }
        if elig:
            k = row["email"].strip().lower()
            pe = elig.get(k, elig.get(row["learner_id"].lower()))
            row["placement_eligible"] = "" if pe is None else int(pe)
            row["miles_but_not_placement"] = int(row["drive_miles_eligible"] == 1 and pe is False)
        out.append(row)
        by[r["batch_name"]].append(row)

    (ROOT / "data/output").mkdir(parents=True, exist_ok=True)
    with open(ROOT / "data/output/payout_students.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    print(f"learners: {len(out)} | boost x{a.boost} | rewards with unconfirmed cost (treated as Rs 0): {', '.join(unknown)}\n")
    hdr = f"{'batch':<24}{'n':>5}{'total Miles':>12}{'avg':>7}{'max':>7}{'ceiling avg':>12}{'min cost':>10}{'max single':>12}{'max total*':>12}{'max repeat':>12}"
    print(hdr)
    summ = []
    for b, rs in list(by.items()) + [("ALL", out)]:
        t = lambda k: sum(x[k] for x in rs)
        line = dict(batch=b, learners=len(rs), total_miles=t("miles"), avg_miles=round(t("miles") / len(rs)),
                    max_miles=max(x["miles"] for x in rs), avg_ceiling=round(t("ceiling_miles") / len(rs)),
                    min_cost=t("min_cost"), max_single_cost=t("max_single_cost"),
                    max_total_each_once=t("max_total_each_once"), max_total_repeat=t("max_total_repeat"),
                    drive_miles_eligible=t("drive_miles_eligible"))
        r_ = rev.get(b, a.revenue_per_student)
        if r_:
            R = r_ * len(rs)
            line.update(revenue=R, max_single_pct=round(100 * line["max_single_cost"] / R, 2),
                        max_total_pct=round(100 * line["max_total_each_once"] / R, 2),
                        max_repeat_pct=round(100 * line["max_total_repeat"] / R, 2))
        if elig:
            line["miles_but_not_placement"] = t("miles_but_not_placement")
        summ.append(line)
        print(f"{b[:23]:<24}{len(rs):>5}{line['total_miles']:>12,}{line['avg_miles']:>7,}{line['max_miles']:>7,}{line['avg_ceiling']:>12,}"
              f"{line['min_cost']:>10,}{line['max_single_cost']:>12,}{line['max_total_each_once']:>12,}{line['max_total_repeat']:>12,}")
    print("  * max total = every learner spends all Miles on the costliest rewards, each reward at most once")
    with open(ROOT / "data/output/payout_batches.csv", "w", newline="") as f:
        keys = sorted({k for s in summ for k in s}, key=lambda k: list(summ[0]).index(k) if k in summ[0] else 99)
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(summ)
    if rev or a.revenue_per_student:
        print("\ncost as % of revenue:")
        for s in summ:
            if "revenue" in s:
                print(f"  {s['batch'][:24]:<26} revenue Rs {s['revenue']:>12,.0f} | max single {s['max_single_pct']}% | max total {s['max_total_pct']}% | max repeat {s['max_repeat_pct']}%")
    else:
        print("\n(no revenue given: pass --revenue-per-student or data/input/revenue.csv to get cost as % of revenue)")
    if not elig:
        print("(no data/input/placement_eligibility.csv: cannot compute 'Miles-eligible but not placement-eligible')")


if __name__ == "__main__":
    main()

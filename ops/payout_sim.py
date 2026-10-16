"""Payout simulation: what each learner's Miles are worth in rupees if they redeem.

    python3 ops/payout_sim.py --source export1.csv [export2.csv ...]       # full catalogue (default)
    python3 ops/payout_sim.py --source export.csv --catalog core            # only the confirmed rewards
    python3 ops/payout_sim.py --source export.csv --revenue-per-student 60000
    python3 ops/payout_sim.py --source export.csv --boost 1.15              # stand-in for the streak boost

Per student: Miles achieved, MINIMUM availing cost = cheapest paid reward they can afford, MAXIMUM availing cost =
costliest single reward they can afford. Rewards that cost Masai Rs 0 (recognition, access) are not counted as the
"minimum": every claimable reward must have a real cost. Students under the lowest Miles price show "n/a".

Optional inputs in data/input/: revenue.csv (batch_name,revenue_per_student),
placement_eligibility.csv (email or learner_id, eligible 1/0).
"""
import argparse, csv, io, urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RATES = dict(ml=200, mr=100, nl=150, nr=50, p=100, ga=300, ge=300, me=150)   # new lecture rates
UNIT = 500
DRIVE_MILES = 25000

# (reward, Miles needed, cost to Masai Rs). cost None = not confirmed (treated as 0 and flagged)
CORE = [
    ("1:1 doubt session with your CC (30 min)", 1000, 1500),
    ("Mock interview", 5000, 1500),
    ("Interview preparation assignment", 5000, 1500),
    ("Resume building support", 5000, 1500),
    ("1:1 session with a TA (30 min)", 5000, 1500),
    ("Free hackathon entry", 5000, 1000),
    ("Institute t-shirt", 5000, 500),
    ("50% off the Campus Immersion fee", 8000, 1000),
    ("Institute hoodie", 8000, 800),
    ("1:1 session with an IM (30 min)", 20000, 4000),
    ("One-month AI tool subscription", 20000, 2000),
    ("Interview with a company", 25000, None),
    ("Participation in hiring drive", 25000, None),
]
# suggested additions: Miles at ~6 Miles per Rs of item cost, cost = indicative worst case within the Rs 2,000 cap
SUGGESTED = [
    ("Keyboard / desk mat, XL", 3500, 600), ("Webcam cover + cable organiser kit", 2000, 300),
    ("Laptop stand", 5500, 900), ("Monitor riser with organiser", 5500, 900), ("Laptop cooling pad", 6000, 1000),
    ("Seat or lumbar cushion", 6000, 1000), ("Wireless mouse", 5000, 800), ("Laptop sleeve", 5000, 800),
    ("USB-C hub, 4-in-1", 7000, 1200), ("LED desk lamp", 7000, 1200), ("Compact wireless keyboard", 9000, 1500),
    ("Laptop backpack", 9000, 1500), ("Mechanical keyboard, budget", 12000, 2000), ("Ergonomic vertical mouse", 9000, 1500),
    ("Wired earphones with mic", 3000, 500), ("Bluetooth neckband", 5500, 900), ("Over-ear headphones with mic", 9000, 1500),
    ("1080p webcam", 9000, 1500), ("True wireless earbuds", 11000, 1800), ("USB condenser mic", 12000, 2000),
    ("Presenter / clicker remote", 5000, 800), ("Pen drive 128GB", 4000, 700), ("Power bank 10,000 mAh", 6000, 1000),
    ("Portable SSD 256GB", 12000, 2000), ("Fitness band", 11000, 1800), ("Insulated bottle", 3000, 500),
    ("Blue-light glasses", 3500, 600),
    ("Amazon / Flipkart voucher Rs 500", 3000, 500), ("Amazon / Flipkart voucher Rs 1,000", 6000, 1000),
    ("Amazon / Flipkart voucher Rs 2,000", 12000, 2000), ("Food voucher Rs 500", 3000, 500),
    ("Coffee voucher Rs 500", 3000, 500), ("Music / OTT subscription, 3 months", 3000, 500), ("Books voucher", 6000, 1000),
    ("Canva Pro, 1 month", 3000, 500), ("Book: Clean Code / DDIA / Inspired", 5000, 800),
    ("AI coding assistant, 1 month", 5000, 850), ("Online course voucher", 6000, 1000),
    ("Domain + hosting, 1 year", 6000, 1000), ("Interview-prep platform, 1 month", 12000, 2000),
    ("LinkedIn Premium, 1 month", 12000, 2000),
    ("Choose the next masterclass topic", 4000, 0), ("Priority seat in next masterclass", 3000, 0),
    ("Portfolio / GitHub / LinkedIn profile review", 5000, 0), ("Virtual coffee with alumnus / mentor", 6000, 500),
    ("Lunch or call with a founder / leader", 8000, 0), ("Hackathon team mentor session", 5000, 0),
    ("Conference / meetup ticket", 9000, 1500),
    ("Wall of Fame + LinkedIn shout-out", 2000, 0), ("Personalised achievement certificate", 2500, 0),
    ("Sticker pack", 1000, 150), ("Notebook or cap", 2000, 300), ("Branded sipper", 2500, 400),
]
# rewards a student may claim more than once (edit to match policy); everything else is once per student.
REPEATABLE = {
    "1:1 doubt session with your CC (30 min)", "1:1 session with a TA (30 min)", "1:1 session with an IM (30 min)",
    "Mock interview", "Interview preparation assignment", "Resume building support",
    "Amazon / Flipkart voucher Rs 500", "Amazon / Flipkart voucher Rs 1,000", "Amazon / Flipkart voucher Rs 2,000",
    "Food voucher Rs 500", "Coffee voucher Rs 500", "Books voucher", "Virtual coffee with alumnus / mentor",
}
CAPS = [1, 2, 3, 5, None]          # max claims per repeatable reward; None = unlimited
IDENT = ("batch_name", "student_code", "student_name", "email", "mobile")


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


def knap(budget, items, repeat):
    best = [0] * (budget // UNIT + 1)
    for w, v in items:
        w //= UNIT
        rng = range(w, len(best)) if repeat else range(len(best) - 1, w - 1, -1)
        for x in rng:
            best[x] = max(best[x], best[x - w] + v)
    return best[-1]


def best_table(items, cap, max_units):
    """best[x] = most Masai could pay out for a student with x*UNIT Miles.
    items: (miles, cost, repeatable). cap = max claims of a repeatable item (None = unlimited)."""
    best = [0] * (max_units + 1)
    for miles, c, rep_ in items:
        w = miles // UNIT
        if w > max_units:
            continue
        if rep_ and cap is None:
            for x in range(w, max_units + 1):
                best[x] = max(best[x], best[x - w] + c)
        else:
            for _ in range(cap if (rep_ and cap) else 1):
                for x in range(max_units, w - 1, -1):
                    best[x] = max(best[x], best[x - w] + c)
    return best


def load(srcs):
    """One row per (batch, student); duplicates merged by taking the higher value per count."""
    merged = {}
    for s in srcs:
        t = (urllib.request.urlopen(s, timeout=120).read().decode("utf-8-sig") if s.startswith("http")
             else Path(s).read_text(encoding="utf-8-sig"))
        for r in csv.DictReader(io.StringIO(t)):
            k = (r["batch_name"], r["student_code"])
            if k not in merged:
                merged[k] = dict(r)
                continue
            cur = merged[k]
            act = lambda x: sum(n(x[f]) for f in x if f.endswith(("attended_live", "attended_rec", "completed")))
            better = act(r) > act(cur)
            for f in r:
                if f not in IDENT and n(r[f]) > n(cur.get(f, 0)):
                    cur[f] = r[f]
            if better:
                for f in IDENT:
                    cur[f] = r[f]
    return list(merged.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", nargs="+", required=True)
    ap.add_argument("--catalog", choices=["core", "full"], default="full")
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

    catalog = CORE + (SUGGESTED if a.catalog == "full" else [])
    unknown = [r for r, _, c in catalog if c is None]
    cost = lambda c: 0 if c is None else c
    items = [(m, cost(c)) for _, m, c in catalog if cost(c) > 0]
    lowest = min(m for _, m, c in catalog if cost(c) > 0)

    out, by = [], defaultdict(list)
    for r in load(a.source):
        m = miles_of(r, a.boost)
        paid = [(nm, mi, cost(c)) for nm, mi, c in catalog if mi <= m and cost(c) > 0]
        cheapest = min(paid, key=lambda x: (x[2], x[1])) if paid else None
        priciest = max(paid, key=lambda x: (x[2], x[1])) if paid else None
        budget = [(mi, c) for mi, c in items if mi <= m]
        row = {"learner_id": r["student_code"], "name": r.get("student_name", ""), "email": r.get("email", ""),
               "batch": r["batch_name"], "miles": m, "eligible": int(bool(paid)),
               "min_reward": cheapest[0] if cheapest else "", "min_cost": cheapest[2] if cheapest else None,
               "max_reward": priciest[0] if priciest else "", "max_cost": priciest[2] if priciest else None,
               "max_total_each_once": knap(m, budget, False) if budget else 0,
               "drive_miles_eligible": int(m >= DRIVE_MILES)}
        if elig:
            pe = elig.get(row["email"].strip().lower(), elig.get(row["learner_id"].lower()))
            row["placement_eligible"] = "" if pe is None else int(pe)
            row["miles_but_not_placement"] = int(row["drive_miles_eligible"] == 1 and pe is False)
        out.append(row)
        by[r["batch_name"]].append(row)

    rep_items = [(mi, cost(c), nm in REPEATABLE) for nm, mi, c in catalog if cost(c) > 0]
    top_units = max([x["miles"] for x in out] + [0]) // UNIT
    tables = {cap: best_table(rep_items, cap, top_units) for cap in CAPS}
    capname = lambda c: "unlimited" if c is None else f"cap{c}"
    for x in out:
        for cap in CAPS:
            x["max_repeat_" + capname(cap)] = tables[cap][x["miles"] // UNIT] if x["eligible"] else 0

    od = ROOT / "data/output"
    od.mkdir(parents=True, exist_ok=True)
    simple = od / f"payout_simple_{a.catalog}.csv"
    with open(simple, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["batch", "student_code", "student", "miles_achieved", "minimum_availing_cost", "maximum_availing_cost"])
        for x in sorted(out, key=lambda x: (x["batch"], -x["miles"])):
            w.writerow([x["batch"], x["learner_id"], x["name"], x["miles"],
                        "n/a" if x["min_cost"] is None else x["min_cost"], "n/a" if x["max_cost"] is None else x["max_cost"]])
    with open(od / f"payout_detail_{a.catalog}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    with open(od / f"payout_simple_repeats_{a.catalog}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["batch", "student_code", "student", "miles_achieved", "minimum_availing_cost", "maximum_availing_cost_single",
                    "max_cost_if_repeating_cap2", "max_cost_if_repeating_cap3", "max_cost_if_repeating_unlimited"])
        for x in sorted(out, key=lambda x: (x["batch"], -x["miles"])):
            w.writerow([x["batch"], x["learner_id"], x["name"], x["miles"],
                        "n/a" if x["min_cost"] is None else x["min_cost"], "n/a" if x["max_cost"] is None else x["max_cost"],
                        x["max_repeat_cap2"], x["max_repeat_cap3"], x["max_repeat_unlimited"]])
    print(f"catalogue: {a.catalog} ({len(catalog)} rewards, lowest paid one needs {lowest:,} Miles) | boost x{a.boost}")
    if unknown:
        print("cost not confirmed (counted as Rs 0):", ", ".join(unknown))
    print(f"\n{'batch':<22}{'students':>9}{'eligible':>9}{'total Miles':>13}{'avg':>7}{'min cost':>11}{'max cost':>12}{'max/elig':>9}{'each-once':>12}")
    summ = []
    for b, rs in sorted(by.items()) + [("ALL", out)]:
        el = [x for x in rs if x["eligible"]]
        t = lambda k: sum(x[k] or 0 for x in rs)
        s = dict(batch=b, students=len(rs), eligible=len(el), total_miles=t("miles"), avg_miles=t("miles") // len(rs),
                 min_cost=t("min_cost"), max_cost=t("max_cost"), max_each_once=t("max_total_each_once"),
                 drive_miles_eligible=t("drive_miles_eligible"))
        r_ = rev.get(b, a.revenue_per_student)
        if r_:
            s["revenue"] = r_ * len(rs)
            s["min_pct_revenue"] = round(100 * s["min_cost"] / s["revenue"], 2)
            s["max_pct_revenue"] = round(100 * s["max_cost"] / s["revenue"], 2)
        if elig:
            s["miles_but_not_placement"] = t("miles_but_not_placement")
        summ.append(s)
        print(f"{b[:21]:<22}{len(rs):>9}{len(el):>9}{s['total_miles']:>13,}{s['avg_miles']:>7,}{s['min_cost']:>11,}{s['max_cost']:>12,}"
              f"{(s['max_cost'] // len(el)) if el else 0:>9,}{s['max_each_once']:>12,}")
    with open(od / f"payout_batches_{a.catalog}.csv", "w", newline="") as f:
        keys = []
        for s in summ:
            keys += [k for k in s if k not in keys]
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(summ)
    print("\nWORST CASE WITH REPEATS (every student spends all Miles on the costliest-to-Masai mix; repeatable rewards capped per student)")
    print(f"{'batch':<22}" + "".join(f"{('cap ' + str(c)) if c else 'unlimited':>14}" for c in CAPS))
    for b, rs in sorted(by.items()) + [("ALL", out)]:
        print(f"{b[:21]:<22}" + "".join(f"{sum(x['max_repeat_' + capname(c)] for x in rs):>14,}" for c in CAPS))
    tm = sum(x["miles"] for x in out)
    print(f"{'  as % of all Miles':<22}" + "".join(f"{100 * sum(x['max_repeat_' + capname(c)] for x in out) / tm:>13.1f}%" for c in CAPS))
    print(f"\nwritten: {simple.name}, payout_detail_{a.catalog}.csv, payout_batches_{a.catalog}.csv in data/output/")
    if rev or a.revenue_per_student:
        for s in summ:
            if "revenue" in s:
                print(f"  {s['batch'][:24]:<26} revenue Rs {s['revenue']:>13,.0f} | min {s['min_pct_revenue']}% | max {s['max_pct_revenue']}%")


if __name__ == "__main__":
    main()

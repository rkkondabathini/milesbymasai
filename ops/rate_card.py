"""Batch-specific rate cards.

A batch's rate card is the standard rate card x a multiplier k, sized so that, at the batch's programme length and fee,
the expected cost of redemptions lands on a target share of the batch's revenue (default 1.25%, i.e. inside 1 to 1.5%).

    python3 ops/rate_card.py --init  --source export1.csv [export2.csv ...]     # draft data/input/batch_design.csv
    python3 ops/rate_card.py --config updated_config.json --source export1.csv ...   # fit, validate, write rate cards

Model (all counts in the units the data uses):
  weekly pattern       2 mandatory, 2 optional + 1 buffer session (3 earn Miles), per mandatory lecture 2 practice
                       items (an Objective and a Subjective part = one assignment), 10 evaluation items (about 5 evaluations)
  design ceiling(W)    W weeks x (2 mandatory x live rate + 3 optional x live rate + 4 practice items x rate) + 10 eval items x rate
  caps                 Miles-earning optional sessions, practice items and evaluations are capped at the pattern, so a batch with
                       hundreds of optional sessions cannot offer an unbounded ceiling
  target ceiling(b)    t x fee / (rho x e x Rs-per-Mile)
                       e   = average engagement: the average student's Miles as a share of the design ceiling (measured on completed batches)
                       rho = High-case cost as a share of (Miles x Rs-per-Mile) (measured on completed batches)
  k(b)                 target ceiling / design ceiling at standard rates
  rate card            each standard rate x k, rounded to the nearest 5 (minimum 5)
"""
import argparse, collections, csv, datetime as dt, json, statistics as st, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leadership_numbers as L
import payout_sim as ps

ROOT = Path(__file__).resolve().parent.parent
PATTERN = dict(mand=2, opt=2, buf=1, prac_items=2, eval_items=10)
TODAY = dt.date(2026, 10, 16)
MIN_ROWS = 30
BASE_KEYS = ("ml", "mr", "nl", "nr", "p", "ga", "ge", "me")


def design_ceiling(W, R, pat=PATTERN):
    return W * (pat["mand"] * R["ml"] + (pat["opt"] + pat["buf"]) * R["nl"] + pat["mand"] * pat["prac_items"] * R["p"]) + pat["eval_items"] * R["ge"]


def r5(x):
    return max(5, int(round(x / 5.0)) * 5)


def card(R, k):
    return {a: r5(R[a] * k) for a in BASE_KEYS}


def capped_counts(r, W, pat=PATTERN):
    n = ps.n
    ml, mr = ps.split(n(r["mandatory_total"]), n(r["mandatory_attended_live"]), n(r["mandatory_attended_rec"]))
    nl, nr = ps.split(n(r["nonmandatory_total"]), n(r["nonmandatory_attended_live"]), n(r["nonmandatory_attended_rec"]))
    cm, co = pat["mand"] * W, (pat["opt"] + pat["buf"]) * W
    l = min(ml, cm); mr = min(mr, cm - l); ml = l
    l = min(nl, co); nr = min(nr, co - l); nl = l
    return dict(ml=ml, mr=mr, nl=nl, nr=nr, p=min(n(r["practice_assignment_completed"]), pat["mand"] * pat["prac_items"] * W),
                ga=n(r["graded_assignment_completed"]), ge=min(n(r["graded_evaluation_completed"]), pat["eval_items"]),
                me=n(r["mock_evaluation_completed"]))


def miles(c, R):
    return sum(c[a] * R[a] for a in BASE_KEYS)


def group(srcs):
    by = collections.defaultdict(list)
    for r in ps.load(srcs):
        by[r["batch_name"]].append(r)
    return by


def start_of(batch):
    code = batch.split("-")[-1]
    try:
        return dt.date(2000 + int(code[:2]), int(code[2:4]), 1)
    except Exception:
        return None


def draft_design(by, fees):
    """Infer programme length and status for each batch. Mandatory lectures run about 2 a week, so weeks = median mandatory / 2.
    A batch looks completed if it started at least 6 weeks longer ago than that. Everything is editable in the CSV."""
    out = []
    for b, rs in sorted(by.items(), key=lambda kv: (start_of(kv[0]) or dt.date(2100, 1, 1), kv[0])):
        m = st.median(ps.n(r["mandatory_total"]) for r in rs)
        W = max(1, round(m / 2)); s = start_of(b)
        el = (TODAY - s).days / 7 if s else 0
        done = len(rs) >= MIN_ROWS and el >= W + 6
        note = ""
        if len(rs) < MIN_ROWS or W < 3:
            W, done, note = 13, False, "CONFIRM: too little data to infer, 13 weeks assumed"
        elif not done and el < 16:
            W, note = 26, "CONFIRM: batch is only %d weeks in, a 6-month (26 week) programme is assumed" % el if s else "CONFIRM: start date unknown, a 6-month (26 week) programme is assumed"
        elif not done:
            note = "CONFIRM: batch still running, length taken from lectures so far"
        out.append(dict(batch_name=b, weeks=W, status="completed" if done else "ongoing", start=s.isoformat() if s else "",
                        students=len(rs), fee=fees.get(b, ""), note=note))
    return out


def read_design(path):
    return {r["batch_name"]: dict(weeks=int(float(r["weeks"])), status=r["status"], note=r.get("note", ""))
            for r in csv.DictReader(open(path))}


def read_fees(path):
    return {r["batch_name"]: float(r["revenue_per_student"]) for r in csv.DictReader(open(path))}


def calibrate(by, design, fees, cfg, items, R):
    """e* and rho* from completed batches (medians)."""
    es, rhos = [], []
    cap = cfg["settings"]["repeatCap"]
    for b, rs in by.items():
        d = design.get(b)
        if not d or d["status"] != "completed" or len(rs) < MIN_ROWS:
            continue
        W = d["weeks"]
        ms = [miles(capped_counts(r, W), R) for r in rs]
        es.append(sum(ms) / len(ms) / design_ceiling(W, R))
        o = L.evaluate(ms, items, cap)
        rhos.append(o["high"] / (sum(ms) / cfg["settings"]["milesPerRupee"]))
    return st.median(es), st.median(rhos), (min(es), max(es)), len(es)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", nargs="+", required=True)
    ap.add_argument("--config", default=str(ROOT / "updated_config.json"))
    ap.add_argument("--fees-csv", default=str(ROOT / "data/input/revenue.csv"))
    ap.add_argument("--design", default=str(ROOT / "data/input/batch_design.csv"))
    ap.add_argument("--target", type=float, default=1.25, help="target High-case cost as %% of batch revenue")
    ap.add_argument("--init", action="store_true", help="write a draft batch_design.csv and stop")
    a = ap.parse_args()

    by = group(a.source)
    fees = read_fees(a.fees_csv)
    if a.init or not Path(a.design).exists():
        rows = draft_design(by, fees)
        with open(a.design, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader(); w.writerows(rows)
        print(f"wrote {a.design} ({len(rows)} batches). Review the 'weeks' and 'status' columns, then run again without --init.")
        if a.init:
            return
    design = read_design(a.design)
    cfg = L.load_cfg(a.config)
    items = L.rewards_from(cfg)
    R = dict(cfg["settings"]["milesPerActivity"])
    mpr = cfg["settings"]["milesPerRupee"]
    cap = cfg["settings"]["repeatCap"]
    e, rho, (elo, ehi), nc = calibrate(by, design, fees, cfg, items, R)
    print(f"calibration on {nc} completed batches: engagement e* = {e:.3f} (range {elo:.2f} to {ehi:.2f}), cost conversion rho* = {rho:.3f}")
    print(f"target {a.target}% of revenue, {mpr} Miles = Rs 1\n")

    out = []
    print(f"{'batch':<20}{'status':<10}{'wk':>4}{'fee':>8}{'std max':>9}{'card max':>9}{'k':>6}  {'live mand':>9}{'cost% std':>10}{'cost% card':>11}")
    for b, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        d = design.get(b)
        if not d or b not in fees:
            continue
        W, fee = d["weeks"], fees[b]
        std_max = design_ceiling(W, R)
        T = a.target / 100 * fee / (rho * e / mpr)
        k = T / std_max
        rc = card(R, k)
        cs = [capped_counts(r, W) for r in rs]
        rev = fee * len(rs)
        c_std = L.evaluate([miles(c, R) for c in cs], items, cap)["high"] / rev * 100
        ms = [miles(c, rc) for c in cs]
        o = L.evaluate(ms, items, cap)
        c_new = o["high"] / rev * 100
        out.append(dict(batch=b, status=d["status"], weeks=W, students=len(rs), fee=fee, std_max=std_max, card_max=round(design_ceiling(W, rc)),
                        k=round(k, 3), **{f"rate_{a_}": rc[a_] for a_ in BASE_KEYS}, cost_pct_standard=round(c_std, 2),
                        cost_pct_card=round(c_new, 2), can_claim_pct=round(100 * o["claim"] / o["n"]), note=d["note"]))
        if len(rs) >= MIN_ROWS:
            print(f"{b:<20}{d['status']:<10}{W:>4}{fee:>8,.0f}{std_max:>9,}{design_ceiling(W, rc):>9,}{k:>6.2f}  {rc['ml']:>9}{c_std:>10.2f}{c_new:>11.2f}")
    (ROOT / "data/output").mkdir(parents=True, exist_ok=True)
    with open(ROOT / "data/output/rate_cards.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    json.dump(dict(target_pct=a.target, e=e, rho=rho, milesPerRupee=mpr, pattern=PATTERN, standard_rates=R,
                   batches={o["batch"]: dict(weeks=o["weeks"], k=o["k"], status=o["status"]) for o in out}),
              open(ROOT / "data/output/rate_cards.json", "w"), indent=1)
    done = [o for o in out if o["status"] == "completed" and o["students"] >= MIN_ROWS]
    if done:
        for label, key in (("standard rates", "cost_pct_standard"), ("batch rate cards", "cost_pct_card")):
            v = [o[key] for o in done]
            print(f"\n{label:<18} completed batches: median {st.median(v):.2f}%, range {min(v):.2f} to {max(v):.2f}%, "
                  f"inside 1 to 1.5%: {sum(1 for x in v if 1 <= x <= 1.5)} of {len(v)}")
    print("\nwritten: data/output/rate_cards.csv and rate_cards.json")


if __name__ == "__main__":
    main()

"""Reward ladder as a percentage of each batch's maximum Miles.

Each batch has a Maximum Miles figure (from its length). Every reward is priced as a percentage of that maximum, rounded to a
clean figure, so a short programme and a long one both have a full ladder (e.g. a founder connect at 90% of the maximum).

    price(reward, batch) = round_to_step( min(pct x level, cap) x batch_max )

`level` is one number per batch (1.0 = the ladder as written). A batch with a low fee gets a level above 1, which makes
the everyday part of the ladder harder to climb (rewards marked pinned, such as a founder connect at 90%, keep their percentage), so the cost lands on the target share of revenue. It is fitted, not guessed:
the expected High-case cost per student is computed from how far up the maximum students actually get (measured on
completed batches), and `level` is the value that makes that cost equal target% x fee.

    python3 ops/ladder.py --source export1.csv export2.csv ...      # fit levels, validate on completed batches, write ladder_defaults.json
"""
import argparse, bisect, collections, csv, json, math, statistics as st, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leadership_numbers as L
import rate_card as RC

ROOT = Path(__file__).resolve().parent.parent
STEP = 50
PRICE_CAP = 5.0   # a price above 100% of the maximum is simply out of reach


def rstep(x, step=STEP):
    return max(step, int(math.floor(x / step + 0.5)) * step)   # same rounding as the playground (JavaScript Math.round)


def max_miles(W, R, pat=RC.PATTERN, step=STEP):
    return rstep(RC.design_ceiling(W, R, pat), step)


def default_pct(cost):
    """Starting ladder: Rs 1,500 is about 42% of a 6-month batch's maximum, Rs 2,000 about 56%, and anything dearer is
    compressed into 60 to 90% so the premium rewards stay reachable (not above 90%)."""
    p = cost / 3550 if cost <= 2000 else 0.55 + (cost - 2000) / (6000 - 2000) * 0.35
    return round(min(0.90, p), 2)


PIN_FROM = 0.70   # rewards at or above this share of the maximum keep their percentage in every batch (the level does not scale them)
OVERRIDES = {"Lunch or call with a founder / leader": 0.90, "Wall of Fame + LinkedIn shout-out": 0.85}


def ladder_from_config(cfg):
    out = []
    for r in cfg["rewards"]:
        if r["on"] and r["cost"] > 0:
            pct = OVERRIDES.get(r["name"], default_pct(r["cost"]))
            out.append(dict(name=r["name"], cost=r["cost"], rep=r["repeatable"], pct=pct, pinned=pct >= PIN_FROM))
    return out


def prices(ladder, M, level, step=STEP):
    return [dict(name=x["name"], cost=x["cost"], rep=x["rep"],
                 miles=rstep(min(x["pct"] * (1.0 if x.get("pinned") else level), PRICE_CAP) * M, step)) for x in ladder]


def pooled_shares(by, design, fees, R, min_rows=RC.MIN_ROWS):
    """Each completed-batch student's Miles as a share of that batch's maximum."""
    out = []
    for b, rs in by.items():
        d = design.get(b)
        if not d or d["status"] != "completed" or len(rs) < min_rows:
            continue
        W = d["weeks"]
        M = max_miles(W, R)
        out += [RC.miles(RC.capped_counts(r, W), R) / M for r in rs]
    return out


def quantiles(shares, n=1000):
    """n evenly spaced points of the pooled distribution (keeps the playground file small and the fit fast)."""
    v = sorted(shares)
    return [v[min(len(v) - 1, int((i + 0.5) * len(v) / n))] for i in range(n)]


def expected_high_per_student(shares, items, M):
    """Mean over the shares of the dearest reward a student with share x M Miles can afford."""
    its = sorted(items, key=lambda i: i["miles"])
    miles = [i["miles"] for i in its]
    pref, best = [], 0
    for i in its:
        best = max(best, i["cost"]); pref.append(best)
    tot = 0.0
    for sh in shares:
        k = bisect.bisect_right(miles, sh * M)
        if k:
            tot += pref[k - 1]
    return tot / len(shares)


def fit_level(fee, M, shares, ladder, target_pct, step=STEP, lo=0.3, hi=6.0):
    want = target_pct / 100 * fee
    f = lambda d: expected_high_per_student(shares, prices(ladder, M, d, step), M)
    if f(lo) <= want:
        return lo
    if f(hi) >= want:
        return hi
    for _ in range(26):
        mid = (lo + hi) / 2
        if f(mid) > want:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 3)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", nargs="+", required=True)
    ap.add_argument("--config", default=str(ROOT / "updated_config.json"))
    ap.add_argument("--fees-csv", default=str(ROOT / "data/input/revenue.csv"))
    ap.add_argument("--design", default=str(ROOT / "data/input/batch_design.csv"))
    ap.add_argument("--target", type=float, default=1.25)
    ap.add_argument("--step", type=int, default=STEP)
    a = ap.parse_args()
    by = RC.group(a.source)
    fees = RC.read_fees(a.fees_csv)
    design = RC.read_design(a.design)
    cfg = L.load_cfg(a.config)
    R = dict(cfg["settings"]["milesPerActivity"])
    cap = cfg["settings"]["repeatCap"]
    ladder = ladder_from_config(cfg)
    shares = quantiles(pooled_shares(by, design, fees, R))
    print(f"ladder: {len(ladder)} rewards | pooled shares from {len(shares):,} students on completed batches | target {a.target}%\n")

    levels, rows, comp_h, comp_rev = {}, [], 0, 0
    for b, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        d = design.get(b)
        if not d or b not in fees:
            continue
        W, fee = d["weeks"], fees[b]
        M = max_miles(W, R, step=a.step)
        lvl = fit_level(fee, M, shares, ladder, a.target, a.step)
        levels[b] = dict(weeks=W, max=M, level=lvl)
        ms = [RC.miles(RC.capped_counts(r, W), R) for r in rs]
        o1 = L.evaluate(ms, prices(ladder, M, 1.0, a.step), cap)
        o = L.evaluate(ms, prices(ladder, M, lvl, a.step), cap)
        rev = fee * len(rs)
        rows.append((b, d["status"], len(rs), W, fee, M, lvl, 100 * o1["high"] / rev, 100 * o["high"] / rev, 100 * o["claim"] / o["n"]))
        if d["status"] == "completed" and len(rs) >= RC.MIN_ROWS:
            comp_h += o["high"]; comp_rev += rev
    print(f"{'batch':<20}{'status':<10}{'wk':>4}{'fee':>8}{'max Miles':>10}{'level':>7}{'cost% level 1':>14}{'cost% fitted':>13}{'can claim':>10}")
    for r in rows:
        if r[2] >= RC.MIN_ROWS:
            print(f"{r[0]:<20}{r[1]:<10}{r[3]:>4}{r[4]:>8,.0f}{r[5]:>10,}{r[6]:>7.2f}{r[7]:>14.2f}{r[8]:>13.2f}{r[9]:>9.0f}%")
    done = [r for r in rows if r[1] == "completed" and r[2] >= RC.MIN_ROWS]
    for label, i in (("ladder only (level 1)", 7), ("ladder + fitted level", 8)):
        v = [r[i] for r in done]
        print(f"\n{label:<24} completed batches: median {st.median(v):.2f}%, range {min(v):.2f} to {max(v):.2f}%, inside 1 to 1.5%: {sum(1 for x in v if 1 <= x <= 1.5)} of {len(v)}")
    print(f"combined (fitted): {100 * comp_h / comp_rev:.2f}% of revenue")
    json.dump(dict(target_pct=a.target, step=a.step, ladder=ladder, shares=[round(x, 4) for x in shares], batches=levels),
              open(ROOT / "data/output/ladder_defaults.json", "w"))
    print("\nwritten data/output/ladder_defaults.json")


if __name__ == "__main__":
    main()

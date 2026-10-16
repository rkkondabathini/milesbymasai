"""Numbers for the leadership report, computed with a playground config JSON (same maths as the playground)."""
import json, math, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import payout_sim as ps

def jround(x):  # JavaScript Math.round
    return math.floor(x + 0.5)

def load_cfg(path):
    return json.loads(Path(path).read_text())

def rewards_from(cfg, mpr=None, rnd=None):
    s = cfg["settings"]; mpr = mpr or s["milesPerRupee"]; rnd = rnd or s["roundMilesTo"]; auto = s["autoPriceMilesFromCost"]
    out = []
    for r in cfg["rewards"]:
        if not r["on"] or r["cost"] <= 0:
            continue
        m = r["miles"]
        if auto and not r["manualMiles"]:
            m = max(rnd, jround(r["cost"] * mpr / rnd) * rnd)
        out.append(dict(name=r["name"], group=r["group"], miles=m, cost=r["cost"], rep=r["repeatable"], confirmed=r["costConfirmed"]))
    return out

def student_miles(rows, cfg):
    R = cfg["settings"]["milesPerActivity"]; ps.RATES = dict(ml=R["ml"], mr=R["mr"], nl=R["nl"], nr=R["nr"], p=R["p"], ga=R["ga"], ge=R["ge"], me=R["me"])
    return [ps.miles_of(r, cfg["settings"]["streakBoost"]) for r in rows]

def evaluate(miles, items, cap):
    """per-student Low / High / Worst for a list of Miles; returns totals and the Miles used."""
    g = 0
    for it in items: g = math.gcd(g, it["miles"])
    unit = max(g, 50); top = (max(miles) if miles else 0) // unit
    best = [0] * (top + 1); used = [0] * (top + 1)
    for it in items:
        w = it["miles"] // unit
        if w < 1 or w > top: continue
        copies = (cap if cap else 10**9) if it["rep"] else 1
        if it["rep"] and not cap:
            for x in range(w, top + 1):
                v = best[x - w] + it["cost"]
                if v > best[x]: best[x] = v; used[x] = used[x - w] + it["miles"]
        else:
            for _ in range(copies):
                for x in range(top, w - 1, -1):
                    v = best[x - w] + it["cost"]
                    if v > best[x]: best[x] = v; used[x] = used[x - w] + it["miles"]
    o = dict(n=len(miles), claim=0, low=0, high=0, worst=0, lowM=0, highM=0, worstM=0)
    for m in miles:
        aff = [it for it in items if it["miles"] <= m]
        if not aff: continue
        lo = min(aff, key=lambda i: (i["cost"], i["miles"])); hi = max(aff, key=lambda i: (i["cost"], i["miles"])); u = m // unit
        o["claim"] += 1; o["low"] += lo["cost"]; o["lowM"] += lo["miles"]; o["high"] += hi["cost"]; o["highM"] += hi["miles"]
        o["worst"] += best[u]; o["worstM"] += used[u]
    return o

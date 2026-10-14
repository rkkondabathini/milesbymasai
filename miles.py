"""Miles by Masai engine: ingest daily N-1 learner buckets, recompute everything from the store."""
import argparse, csv, io, json
import urllib.request
from datetime import datetime
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
CFG = json.loads((ROOT / "config.json").read_text())
BUCKETS = list(CFG["rates"])
STORE = ROOT / "data/store/daily_activity.csv"
IN = ROOT / "data/input"
OUT = ROOT / "data/output"


def monday(d):
    return d - timedelta(days=d.weekday())


def read_csv(path):
    if not Path(path).exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def num(x):
    return int(float(x)) if str(x or "").strip() else 0


IDENT = ["name", "email", "batch", "whatsapp_number"]
STORE_FIELDS = ["learner_id", "date"] + IDENT + BUCKETS + ["detail", "pending"]
# Metabase column -> engine bucket
_UNUSED_MAP = {
    "mandatory_attended_live": "mandatory_live", "mandatory_attended_rec": "mandatory_recorded",
    "nonmandatory_attended_live": "nonmandatory_live", "nonmandatory_attended_rec": "nonmandatory_recorded",
    "practice_assignment_completed": "practice_assignment", "graded_assignment_completed": "graded_assignment",
    "graded_evaluation_completed": "graded_evaluation", "mock_evaluation_completed": "mock_evaluation",
}


def parse_date(s):
    for fmt in ("%a, %b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"unrecognised date: {s!r}")


def credit(r, sched_col, live_col, rec_col, titles_col):
    """One lecture earns once: live wins; a recording only counts if not attended live."""
    sched, live, rec = num(r.get(sched_col)), num(r.get(live_col)), num(r.get(rec_col))
    cap = sched if sched else live + rec
    live = min(live, cap)
    rec = min(rec, cap - live)
    return live, rec, (r.get(titles_col) or "").strip()


def load_metabase(src):
    if src.startswith("http"):
        with urllib.request.urlopen(src, timeout=180) as r:
            text = r.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
    else:
        reader = csv.DictReader(open(src, newline="", encoding="utf-8-sig"))
    out = {}
    for r in reader:
        key = (r["student_code"], parse_date(r["date"]))
        row = {"learner_id": key[0], "date": key[1], "name": r["student_name"], "email": r["email"],
               "batch": r["batch_name"], "whatsapp_number": r.get("mobile", "").strip(),
               **{b: 0 for b in BUCKETS}}
        items = []
        for kind, pre in (("mandatory", "mandatory"), ("nonmandatory", "nonmandatory")):
            live, rec, title = credit(r, f"{pre}_total", f"{pre}_attended_live", f"{pre}_attended_rec",
                                      f"{pre}_lecture_titles")
            row[f"{kind}_live"], row[f"{kind}_recorded"] = live, rec
            for mode, c in (("live", live), ("recorded", rec)):
                if c:
                    items.append({"type": kind, "mode": mode, "title": title, "count": c,
                                  "miles": c * CFG["rates"][f"{kind}_{mode}"]})
        for bucket, col, tcol in (("practice_assignment", "practice_assignment_completed", "practice_titles"),
                                  ("graded_assignment", "graded_assignment_completed", "graded_asg_titles"),
                                  ("graded_evaluation", "graded_evaluation_completed", "graded_eval_titles"),
                                  ("mock_evaluation", "mock_evaluation_completed", "mock_eval_titles")):
            c = num(r.get(col))
            row[bucket] = c
            if c:
                items.append({"type": bucket, "mode": "", "title": (r.get(tcol) or "").strip(), "count": c,
                              "miles": c * CFG["rates"][bucket]})
        row["detail"] = json.dumps(items, ensure_ascii=False) if items else ""
        pend = []  # scheduled that day but not done: what is still on the table
        for kind in ("mandatory", "nonmandatory"):
            left = num(r.get(f"{kind}_total")) - row[f"{kind}_live"] - row[f"{kind}_recorded"]
            if left > 0:
                pend.append({"type": kind, "title": (r.get(f"{kind}_lecture_titles") or "").strip(), "count": left,
                             "miles": left * CFG["rates"][f"{kind}_recorded"]})
        for bucket, tcol in (("practice_assignment", "practice_assignment_total"), ("graded_assignment", "graded_assignment_total"),
                             ("graded_evaluation", "graded_evaluation_total"), ("mock_evaluation", "mock_evaluation_total")):
            left = num(r.get(tcol)) - row[bucket]
            if left > 0:
                pend.append({"type": bucket, "title": "", "count": left, "miles": left * CFG["rates"][bucket]})
        row["pending"] = json.dumps(pend, ensure_ascii=False) if pend else ""
        prev = out.get(key)  # duplicate (student, date) rows: keep the richer one
        if prev and sum(prev[b] for b in BUCKETS) > sum(row[b] for b in BUCKETS):
            row = prev
        out[key] = row
    return list(out.values())


def ingest(src):
    """Upsert by (learner_id, date): re-syncing a day replaces it, never duplicates.
    `src` is a Metabase public CSV URL / file."""
    store = {(r["learner_id"], r["date"]): r for r in read_csv(STORE)}
    new = load_metabase(src)
    for r in new:
        store[(r["learner_id"], r["date"])] = r
    rows = sorted(store.values(), key=lambda r: (r["date"], r["learner_id"]))
    write_csv(STORE, rows, STORE_FIELDS)
    dates = sorted({r["date"] for r in rows})
    print(f"ingested {len(new)} rows; store now {len(rows)} rows, {dates[0]} .. {dates[-1]}")


def run(as_of):
    thr, mults = CFG["weekly_threshold"], CFG["streak_multipliers"]
    daily = defaultdict(dict)  # learner -> date -> base miles
    info, details, missed = {}, defaultdict(list), defaultdict(list)
    for r in read_csv(STORE):
        info[r["learner_id"]] = {k: r.get(k, "") for k in IDENT}
        if r.get("detail") and date.fromisoformat(r["date"]) <= as_of:
            for it in json.loads(r["detail"]):
                details[r["learner_id"]].append({**it, "date": r["date"]})
        if r.get("pending") and date.fromisoformat(r["date"]) <= as_of:
            for it in json.loads(r["pending"]):
                missed[r["learner_id"]].append({**it, "date": r["date"]})
        d = date.fromisoformat(r["date"])
        if d <= as_of:
            daily[r["learner_id"]][d] = sum(num(r[b]) * CFG["rates"][b] for b in BUCKETS)

    batch_pc = {r["batch_name"]: r for r in read_csv(IN / "batch_pc.csv")}
    for r in read_csv(IN / "learners.csv"):  # optional overlay: whatsapp_number, pc_name, corrections
        info.setdefault(r["learner_id"], {}).update({k: v for k, v in r.items() if v})
    ids = sorted(set(daily) | set(info))
    rewards = sorted(CFG["rewards"], key=lambda x: x["cost"])
    cost = {r["reward_id"]: r["cost"] for r in rewards}
    spent, redeemed = defaultdict(int), defaultdict(list)
    for r in read_csv(IN / "redemptions.csv"):
        redeemed[r["learner_id"]].append({k: r.get(k, "") for k in ("reward_id", "miles_cost", "status", "date")})
        if r.get("status", "").lower() != "rejected":
            spent[r["learner_id"]] += num(r.get("miles_cost")) or cost.get(r["reward_id"], 0)

    all_dates = [d for v in daily.values() for d in v]
    first_week = monday(min(all_dates)) if all_dates else monday(as_of)
    cur_week = monday(as_of)
    weeks = []
    w = first_week
    while w <= cur_week:
        weeks.append(w)
        w += timedelta(days=7)

    weekly, summary, comms, payloads = [], [], [], {}
    for lid in ids:
        days, streak, prev_streak, earned_total, bonus_total = daily.get(lid, {}), 0, 0, 0, 0
        for w in weeks:
            prev_streak = streak
            base = sum(m for d, m in days.items() if monday(d) == w)
            met = base >= thr
            streak = streak + 1 if met else 0
            mult = mults[min(streak, len(mults)) - 1] if met else 1.0
            earned = int(round(base * mult, 6) + 0.5)
            earned_total += earned
            bonus_total += earned - base
            weekly.append({"learner_id": lid, "week_start": w.isoformat(), "week_end": (w + timedelta(days=6)).isoformat(),
                           "base_miles": base, "streak_met": int(met), "streak_week": streak, "multiplier": mult,
                           "miles_earned": earned, "bonus_miles": earned - base,
                           "provisional": int(w == cur_week)})
        wk = weekly[-1]
        balance = earned_total - spent[lid]
        nxt = next((r for r in rewards if r["cost"] > balance), None)
        left = (cur_week + timedelta(days=6) - as_of).days
        # the in-progress week isn't missed yet: a carried streak stays alive until Sunday
        pending = wk["base_miles"] < thr and prev_streak > 0
        at_risk = int(pending and left <= 2)
        if pending:
            streak = prev_streak
        p = info.get(lid, {})
        s = {"learner_id": lid, "name": p.get("name", ""), "email": p.get("email", ""),
             "batch": p.get("batch", ""), "whatsapp_number": p.get("whatsapp_number", ""), "pc_name": p.get("pc_name", ""),
             "total_earned": earned_total, "total_redeemed": spent[lid], "current_balance": balance,
             "lifetime_bonus": bonus_total, "base_miles_yesterday": days.get(as_of, 0),
             "week_start": cur_week.isoformat(), "week_base_miles": wk["base_miles"],
             "miles_to_100": max(0, thr - wk["base_miles"]), "streak_at_risk": at_risk,
             "current_streak_week": streak,
             "current_multiplier": wk["multiplier"] if not pending else mults[min(prev_streak, len(mults)) - 1],
             "streak_status": ("active" if wk["base_miles"] >= thr else "pending" if pending
                               else "broken" if earned_total else "not_started"),
             "next_reward": nxt["name"] if nxt else "", "miles_to_next_reward": nxt["cost"] - balance if nxt else 0,
             "affordable_rewards_count": sum(1 for r in rewards if r["cost"] <= balance),
             "data_as_of": as_of.isoformat()}
        summary.append(s)

        mine = [w_ for w_ in weekly if w_["learner_id"] == lid]
        # daily streak: consecutive calendar days with any Miles, ending on as_of (visual only, no multiplier)
        active = {d_ for d_, m_ in days.items() if m_ > 0}
        run_len = best = 0
        d_ = first_week
        while d_ <= as_of:
            if d_ in active:
                run_len += 1
            elif d_ != as_of:  # as_of is yesterday: today is still open, so a miss there doesn't break it yet
                run_len = 0
            best = max(best, run_len)
            d_ += timedelta(days=1)
        today_open = as_of not in active and run_len > 0
        strip = [{"d": (as_of - timedelta(days=i)).isoformat(), "m": days.get(as_of - timedelta(days=i), 0)}
                 for i in range(20, -1, -1)]
        totals = defaultdict(lambda: {"count": 0, "miles": 0})
        for it in details[lid]:
            t = totals[f"{it['type']}_{it['mode']}".rstrip("_")]
            t["count"] += it["count"]
            t["miles"] += it["miles"]
        payloads[lid] = {
            "phone": s["whatsapp_number"], "email": s["email"],
            "data": {k: s[k] for k in ("name", "batch", "data_as_of", "total_earned", "total_redeemed",
                                       "current_balance", "lifetime_bonus", "week_start", "week_base_miles",
                                       "miles_to_100", "current_streak_week", "current_multiplier",
                                       "streak_status", "streak_at_risk", "next_reward",
                                       "miles_to_next_reward", "base_miles_yesterday")},
            "days_left": left,
            "pc": {"name": p.get("pc_name") or batch_pc.get(s["batch"], {}).get("pc_name", ""),
                   "phone": p.get("pc_phone") or batch_pc.get(s["batch"], {}).get("pc_phone", "")},
            "pending": {
                "miles": sum(i["miles"] for i in missed[lid]),
                "lectures": sum(i["count"] for i in missed[lid] if i["type"] in ("mandatory", "nonmandatory")),
                "assignments": sum(i["count"] for i in missed[lid] if i["type"] not in ("mandatory", "nonmandatory")),
                "items": sorted((i for i in missed[lid] if i["type"] in ("mandatory", "nonmandatory")),
                                key=lambda i: (-i["miles"], i["date"]), reverse=False)[:4],
            },
            "daily_streak": run_len, "best_daily_streak": best, "streak_today_open": today_open, "days": strip,
            "weekly": [{k: w_[k] for k in ("week_start", "base_miles", "streak_met", "streak_week", "multiplier",
                                           "miles_earned", "bonus_miles", "provisional")} for w_ in mine],
            "totals": totals,
            "history": sorted(details[lid], key=lambda x: x["date"], reverse=True)[:80],
            "redemptions": redeemed[lid],
        }

        first = (s["name"] or "there").split()[0]
        streak_txt = (f"Streak: Week {streak} ({s['current_multiplier']}x)." if streak
                      else "Streak: not started yet.")
        wk_txt = (f"You've hit {thr}+ this week." if wk["base_miles"] >= thr
                  else f"{s['miles_to_100']} more Miles this week keeps/starts your streak.")
        nxt_txt = f" Next reward: {nxt['name']} in {s['miles_to_next_reward']:,} Miles." if nxt else ""
        text = (f"Hi {first}, your Miles update for {as_of:%d %b}: balance {balance:,} Miles. "
                f"Yesterday: {s['base_miles_yesterday']} Miles. This week: {wk['base_miles']}/{thr}. "
                f"{streak_txt} {wk_txt}{nxt_txt}")
        for ch, to in (("whatsapp", s["whatsapp_number"]), ("email", s["email"])):
            comms.append({"learner_id": lid, "channel": ch, "to": to, "template_id": "daily_update",
                          "message_text": text, "run_date": as_of.isoformat(), "send_status": "pending"})

    by_batch = defaultdict(list)
    for s_ in summary:
        by_batch[s_["batch"]].append(s_)
    for members in by_batch.values():
        earned_sorted = sorted(m["total_earned"] for m in members)
        met = sum(1 for m in members if m["week_base_miles"] >= thr)
        last = (cur_week - timedelta(days=7)).isoformat()
        met_last = {w_["learner_id"] for w_ in weekly if w_["week_start"] == last and w_["streak_met"]}
        for m in members:
            below = sum(1 for e in earned_sorted if e < m["total_earned"])
            payloads[m["learner_id"]]["peer"] = {"batch_n": len(members), "met_now": met,
                                                 "met_last_pct": round(100 * sum(1 for x in members if x["learner_id"] in met_last) / len(members)),
                                                 "ahead_pct": round(100 * below / len(members))}
    write_csv(OUT / "student_weekly.csv", weekly, list(weekly[0]) if weekly else [])
    write_csv(OUT / "student_summary.csv", summary, list(summary[0]) if summary else [])
    write_csv(OUT / "comms_queue.csv", comms, list(comms[0]) if comms else [])
    (OUT / "student_payloads.json").write_text(json.dumps(
        {"as_of": as_of.isoformat(), "rewards": CFG["rewards"], "rates": CFG["rates"],
         "threshold": thr, "multipliers": mults, "students": payloads}, ensure_ascii=False))
    print(f"as_of {as_of}: {len(summary)} learners, {len(weeks)} weeks -> {OUT}")


def ingest_redemptions(src):
    """Sync the Redemptions sheet (File -> Share -> Publish to web -> CSV) into data/input/redemptions.csv.
    Rejected rows are kept so they are ignored (refunded) by run()."""
    if src.startswith("http"):
        with urllib.request.urlopen(src, timeout=60) as r:
            rows = list(csv.DictReader(io.StringIO(r.read().decode("utf-8-sig"))))
    else:
        rows = read_csv(src)
    out = [{"learner_id": r["learner_id"], "reward_id": r["reward_id"], "miles_cost": r["miles_cost"],
            "status": (r.get("status") or "requested").strip().lower(), "date": (r.get("timestamp") or "")[:10]}
           for r in rows if r.get("learner_id") and r.get("reward_id")]
    write_csv(IN / "redemptions.csv", out, ["learner_id", "reward_id", "miles_cost", "status", "date"])
    print(f"redemptions: {len(out)} rows ({sum(1 for o in out if o['status'] != 'rejected')} counted)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("ingest"); i.add_argument("path", help="Metabase public CSV URL, or a file")
    r = sub.add_parser("run"); r.add_argument("--as-of", required=True)
    rd = sub.add_parser("ingest-redemptions"); rd.add_argument("path", help="published CSV URL of the Redemptions sheet, or a file")
    a = ap.parse_args()
    if a.cmd == "ingest":
        ingest(a.path)
    elif a.cmd == "ingest-redemptions":
        ingest_redemptions(a.path)
    else:
        run(date.fromisoformat(a.as_of))

"""Build data/output/playground.html: an offline what-if tool for redemption cost per batch.

    python3 ops/build_playground.py --source export.csv [more.csv ...]

The page embeds each student's activity COUNTS (no names, emails or phones), the reward list, and revenue per student
from data/input/revenue.csv. Open the file in a browser: edit Miles per activity, reward Miles prices and costs,
repeat rules and revenue, and the cost per batch recalculates. The output stays in data/output/ (not in git).
"""
import argparse, csv, json, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import payout_sim as ps

ROOT = ps.ROOT
ap = argparse.ArgumentParser()
ap.add_argument("--source", nargs="+", required=True)
a = ap.parse_args()

batches = defaultdict(list)
for r in ps.load(a.source):
    ml, mr = ps.split(ps.n(r["mandatory_total"]), ps.n(r["mandatory_attended_live"]), ps.n(r["mandatory_attended_rec"]))
    nl, nr = ps.split(ps.n(r["nonmandatory_total"]), ps.n(r["nonmandatory_attended_live"]), ps.n(r["nonmandatory_attended_rec"]))
    batches[r["batch_name"]].append([ml, mr, nl, nr, ps.n(r["practice_assignment_completed"]),
                                     ps.n(r["graded_assignment_completed"]), ps.n(r["graded_evaluation_completed"]),
                                     ps.n(r["mock_evaluation_completed"])])
rev = {}
p = ROOT / "data/input/revenue.csv"
if p.exists():
    rev = {r["batch_name"]: float(r["revenue_per_student"]) for r in csv.DictReader(open(p))}

rewards = ([dict(name=n, miles=m, cost=(c or 0), tbd=c is None, rep=n in ps.REPEATABLE, group="Core", on=True) for n, m, c in ps.CORE]
           + [dict(name=n, miles=m, cost=(c or 0), tbd=False, rep=n in ps.REPEATABLE, group="Suggested gear, vouchers, access", on=False)
              for n, m, c in ps.SUGGESTED])
data = dict(rates=ps.RATES, rewards=rewards, revenue=rev,
            batches=[dict(name=k, rows=v) for k, v in sorted(batches.items(), key=lambda kv: -len(kv[1]))])
html = (Path(__file__).with_name("playground.template.html").read_text()
        .replace("__DATA__", json.dumps(data, separators=(",", ":")).replace("</", "<\\/")))
out = ROOT / "data/output/playground.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html)
print(f"wrote {out}  ({len(html) / 1e3:.0f} KB, {sum(len(v) for v in batches.values())} students, {len(batches)} batches)")

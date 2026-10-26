"""Build data/output/playground.html: an offline what-if tool for redemption cost per batch.

    python3 ops/build_playground.py --source export.csv [more.csv ...] [--config saved.json]

The page embeds each student's activity COUNTS (no names, emails or phones), the reward list with its price as a
percentage of the batch's maximum Miles, the fee per student (data/input/revenue.csv), each batch's programme length
(data/input/batch_design.csv) and the pooled distribution of how far up the maximum students get (completed batches).
Open the file in a browser. Everything stays in data/output/ (not in git).
"""
import argparse, csv, json, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ladder as LD
import leadership_numbers as L
import payout_sim as ps
import rate_card as RC

ROOT = ps.ROOT
ap = argparse.ArgumentParser()
ap.add_argument("--source", nargs="+", required=True)
ap.add_argument("--config", help="a config JSON saved from the playground; it becomes the starting point")
a = ap.parse_args()

by = RC.group(a.source)
batches = {}
for b, rs in by.items():
    rows = []
    for r in rs:
        ml, mr = ps.split(ps.n(r["mandatory_total"]), ps.n(r["mandatory_attended_live"]), ps.n(r["mandatory_attended_rec"]))
        nl, nr = ps.split(ps.n(r["nonmandatory_total"]), ps.n(r["nonmandatory_attended_live"]), ps.n(r["nonmandatory_attended_rec"]))
        rows.append([ml, mr, nl, nr, ps.n(r["practice_assignment_completed"]), ps.n(r["graded_assignment_completed"]),
                     ps.n(r["graded_evaluation_completed"]), ps.n(r["mock_evaluation_completed"])])
    batches[b] = rows

rev = {}
p = ROOT / "data/input/revenue.csv"
if p.exists():
    rev = {r["batch_name"]: float(r["revenue_per_student"]) for r in csv.DictReader(open(p))}
design = {}
dp = ROOT / "data/input/batch_design.csv"
if dp.exists():
    design = RC.read_design(dp)

SUG = [(14, "Desk setup and gear"), (21, "Audio and video"), (27, "Tech accessories and wellness"), (34, "Vouchers"),
       (41, "Learning and career, digital"), (48, "Experiences and access"), (99, "Recognition and swag")]
def pct_for(name, cost):
    return LD.OVERRIDES.get(name, LD.default_pct(cost))
def entry(name, cost, rep, group, tbd=False):
    pc = pct_for(name, cost or 0)
    return dict(name=name, group=group, cost=cost or 0, pct=round(pc * 100), pinned=pc >= LD.PIN_FROM, rep=rep, on=True, tbd=tbd)
rewards = [entry(n, c, n in ps.REPEATABLE, "Core rewards", c is None) for n, m, c in ps.CORE]
rewards += [entry(n, c, n in ps.REPEATABLE, next(g for lim, g in SUG if i < lim)) for i, (n, m, c) in enumerate(ps.SUGGESTED)]

cfg = json.loads(Path(a.config).read_text()) if a.config else None
if cfg and cfg.get("rewards"):   # the saved config's reward list is the catalogue (it includes custom rewards)
    rewards = [dict(entry(r["name"], r["cost"], r["repeatable"], r.get("group") or "Other", not r.get("costConfirmed", True)), on=r["on"]) for r in cfg["rewards"]]
R = dict(ps.RATES)
if cfg:
    R.update(cfg["settings"]["milesPerActivity"])
shares = LD.quantiles(LD.pooled_shares(by, design, rev, R)) if design else []
data = dict(config=cfg, rates=R, pattern=RC.PATTERN, step=LD.STEP, target=1.25, rewards=rewards, revenue=rev, design=design,
            shares=[round(x, 4) for x in shares],
            batches=[dict(name=k, rows=v) for k, v in sorted(batches.items(), key=lambda kv: -len(kv[1]))])
html = (Path(__file__).with_name("playground.template.html").read_text()
        .replace("__DATA__", json.dumps(data, separators=(",", ":")).replace("</", "<\\/")))
out = ROOT / "data/output/playground.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html)
print(f"wrote {out}  ({len(html) / 1e3:.0f} KB, {sum(len(v) for v in batches.values())} students, {len(batches)} batches)")

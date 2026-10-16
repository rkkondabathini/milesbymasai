"""Leadership brief: a visual, minimal-words report for CEO / CFO approval.

    python3 ops/leadership_report.py --config my_config.json --pilot pilot_export.csv --programme programme_export.csv \
        [--fee IITP-AIML-2601=40000] [--out data/output/leadership]

Writes <out>.html (self-contained, inline SVG) and, via headless Chrome, <out>.pdf. Aggregates only: no student names.
"""
import argparse, collections, html, json, math, statistics as st, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leadership_numbers as L
import payout_sim as ps

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True)
ap.add_argument("--pilot", required=True, help="export with the concluded batches to simulate")
ap.add_argument("--programme", required=True, help="export with all live batches (for the scale view)")
ap.add_argument("--fee", action="append", default=[], help="BATCH=fee_per_student, for batches missing from the config")
ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data/output/leadership"))
ap.add_argument("--date", default="16 Oct 2026")
a = ap.parse_args()

cfg = L.load_cfg(a.config)
S = cfg["settings"]
fees = dict(cfg["feePerStudent"])
for f in a.fee:
    k, v = f.split("="); fees[k] = float(v)
CAP = S["repeatCap"]
items = L.rewards_from(cfg)

# ------------------------------------------------------------------ numbers
def by_batch(path):
    d = collections.defaultdict(list)
    for r in ps.load([path]):
        d[r["batch_name"]].append(r)
    return d

pilot_rows = by_batch(a.pilot)
prog_rows = by_batch(a.programme)
PILOT = sorted(pilot_rows, key=lambda b: -len(pilot_rows[b]))

pilot = {}
for b in PILOT:
    m = L.student_miles(pilot_rows[b], cfg)
    o = L.evaluate(m, items, CAP)
    pilot[b] = dict(miles=m, o=o, fee=fees.get(b), rev=(fees[b] * len(m)) if b in fees else None)
allm = [x for b in PILOT for x in pilot[b]["miles"]]
N = len(allm)
tot = {k: sum(pilot[b]["o"][k] for b in PILOT) for k in ("n", "claim", "low", "high", "worst", "lowM", "highM", "worstM")}
earned = sum(allm)

prog = {}
for b, rs in prog_rows.items():
    m = L.student_miles(rs, cfg); o = L.evaluate(m, items, CAP)
    prog[b] = dict(o=o, rev=fees[b] * len(m), n=len(m))
PT = {k: sum(prog[b]["o"][k] for b in prog) for k in ("n", "claim", "low", "high", "worst")}
PT["rev"] = sum(prog[b]["rev"] for b in prog)
PT["earned"] = sum(sum(L.student_miles(rs, cfg)) for rs in prog_rows.values())

# sensitivity (programme High cost, scaled by share who redeem)
SENS_MPR = [8, 10, 12]
SENS_SHARE = [25, 50, 100]
sens = {}
for mpr in SENS_MPR:
    it = L.rewards_from(cfg, mpr=mpr)
    sens[mpr] = sum(L.evaluate(L.student_miles(rs, cfg), it, CAP)["high"] for rs in prog_rows.values())

# ------------------------------------------------------------------ helpers
RED, RED_D, INK, MUT, LINE, PINK, SLATE, GREEN = "#d71f3a", "#a31a2d", "#14161f", "#6b7280", "#e6e8ee", "#fdecef", "#4d5260", "#1a8f58"
SERIES = [RED, SLATE]
lakh = lambda v: f"₹{v / 1e5:,.1f} L" if v >= 1e4 else f"₹{v:,.0f}"
inr = lambda v: f"₹{v:,.0f}"
pct = lambda v, d=1: f"{v:.{d}f}%"
esc = html.escape

def smooth(v, k=1):
    out = []
    for i in range(len(v)):
        lo, hi = max(0, i - k), min(len(v), i + k + 1)
        out.append(sum(v[lo:hi]) / (hi - lo))
    return out

def short(b):
    return b

# ------------------------------------------------------------------ charts (inline SVG)
def chart_distribution():
    W, H, ml, mr, mt, mb = 760, 215, 44, 16, 10, 36
    BIN, XMAX = 2500, 47500
    nb = XMAX // BIN
    series = []
    for b in PILOT:
        c = [0] * nb
        for x in pilot[b]["miles"]:
            c[min(nb - 1, x // BIN)] += 1
        n = len(pilot[b]["miles"])
        series.append((b, smooth([100 * v / n for v in c])))
    ymax = math.ceil(max(max(s) for _, s in series) / 5) * 5
    X = lambda m: ml + (W - ml - mr) * m / XMAX
    Y = lambda v: mt + (H - mt - mb) * (1 - v / ymax)
    g = []
    for t in range(0, ymax + 1, 5):
        g.append(f'<line x1="{ml}" x2="{W - mr}" y1="{Y(t)}" y2="{Y(t)}" stroke="{LINE}"/><text x="{ml - 8}" y="{Y(t) + 4}" text-anchor="end" font-size="11" fill="{MUT}">{t}%</text>')
    for m in range(0, XMAX + 1, 5000):
        g.append(f'<text x="{X(m)}" y="{H - mb + 18}" text-anchor="middle" font-size="11" fill="{MUT}">{m // 1000}k</text>')
    g.append(f'<text x="{(ml + W - mr) / 2}" y="{H - 6}" text-anchor="middle" font-size="11" fill="{MUT}">Miles earned per student</text>')
    for (b, s), col in zip(series, SERIES):
        pts = [(X(i * BIN + BIN / 2), Y(v)) for i, v in enumerate(s)]
        line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        area = f"{X(BIN / 2):.1f},{Y(0)} {line} {X(XMAX - BIN / 2):.1f},{Y(0)}"
        g.append(f'<polygon points="{area}" fill="{col}" fill-opacity=".14"/><polyline points="{line}" fill="none" stroke="{col}" stroke-width="2.6" stroke-linejoin="round"/>')
    lg = "".join(f'<g transform="translate({ml + i * 170},{H - 28})"></g>' for i, _ in enumerate(series))
    legend = "".join(f'<span class="lg"><i style="background:{c}"></i>{esc(b)}</span>' for (b, _), c in zip(series, SERIES))
    chips = ""
    for b, c in zip(PILOT, SERIES):
        m = pilot[b]["miles"]
        chips += (f'<div class="bchip" style="border-top:4px solid {c}"><b>{esc(b)}</b><div class="bnum"><span><i>{len(m):,}</i>students</span>'
                  f'<span><i>{sum(m) // len(m):,}</i>avg Miles</span><span><i>{int(st.median(m)):,}</i>median</span><span><i>{max(m):,}</i>highest</span></div></div>')
    return f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Distribution of Miles per student">{"".join(g)}</svg><div class="legend">{legend}</div><div class="bchips">{chips}</div>'

def chart_reach():
    marks = [1500, 5000, 10000, 15000, 20000, 40000]
    rows = [(m, sum(1 for x in allm if x >= m), 100 * sum(1 for x in allm if x >= m) / N) for m in marks]
    W, rh, ml = 760, 27, 90
    H = rh * len(rows) + 8
    g = []
    for i, (m, c, p) in enumerate(rows):
        y = 4 + i * rh
        full = W - ml - 20
        bw = full * p / 100
        plabel = "<1" if 0 < p < 1 else format(p, ".0f")
        g.append(f'<text x="0" y="{y + 22}" font-size="13" font-weight="700" fill="{INK}">{m:,}+</text>'
                 f'<rect x="{ml}" y="{y + 6}" width="{full}" height="22" rx="11" fill="{PINK}"/>'
                 f'<rect x="{ml}" y="{y + 6}" width="{max(bw, 6):.1f}" height="22" rx="11" fill="{RED}"/>'
                 f'<text x="{ml + max(bw, 6) + 10}" y="{y + 22}" font-size="13" font-weight="700" fill="{INK}">{plabel}% <tspan fill="{MUT}" font-weight="500">· {c:,} students</tspan></text>')
    return f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Share of students reaching each Miles level">{"".join(g)}</svg>'

def chart_cost():
    groups = PILOT + ["Both batches"]
    vals = {b: (pilot[b]["o"]["low"], pilot[b]["o"]["high"], pilot[b]["o"]["worst"], pilot[b]["o"]["n"]) for b in PILOT}
    vals["Both batches"] = (tot["low"], tot["high"], tot["worst"], tot["n"])
    W, H, ml, mt, mb = 760, 232, 30, 22, 58
    vmax = max(v[2] for v in vals.values()) / 1e5
    top = math.ceil(vmax)
    Y = lambda v: mt + (H - mt - mb) * (1 - (v / 1e5) / top)
    gw = (W - ml - 10) / len(groups)
    g = []
    for t in range(0, top + 1, max(1, top // 4)):
        g.append(f'<line x1="{ml}" x2="{W}" y1="{Y(t * 1e5)}" y2="{Y(t * 1e5)}" stroke="{LINE}"/><text x="{ml - 6}" y="{Y(t * 1e5) + 4}" text-anchor="end" font-size="11" fill="{MUT}">{t}</text>')
    cols = [("#f3b8c1", "Low"), (RED, "High"), (RED_D, "Worst case")]
    bw = 38
    for gi, b in enumerate(groups):
        cx = ml + gw * (gi + .5)
        lo, hi, wo, n = vals[b]
        for ci, (v, (col, nm)) in enumerate(zip((lo, hi, wo), cols)):
            x = cx + (ci - 1) * (bw + 8) - bw / 2
            g.append(f'<rect x="{x}" y="{Y(v)}" width="{bw}" height="{Y(0) - Y(v)}" rx="5" fill="{col}"/>'
                     f'<text x="{x + bw / 2}" y="{Y(v) - 6}" text-anchor="middle" font-size="12" font-weight="700" fill="{INK}">{v / 1e5:.1f}</text>')
        g.append(f'<text x="{cx}" y="{H - mb + 20}" text-anchor="middle" font-size="12.5" font-weight="700" fill="{INK}">{esc(b)}</text>'
                 f'<text x="{cx}" y="{H - mb + 38}" text-anchor="middle" font-size="11.5" fill="{MUT}">{n:,} students · High {inr(hi / n)} each</text>')
    g.append(f'<text x="2" y="14" font-size="11" fill="{MUT}">₹ lakh</text>')
    legend = "".join(f'<span class="lg"><i style="background:{c}"></i>{n}</span>' for c, n in cols)
    return f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Cost by scenario">{"".join(g)}</svg><div class="legend">{legend}</div>'

def chart_scale():
    rows = sorted(((b, 100 * v["o"]["high"] / v["rev"], v["o"]["high"], v["n"]) for b, v in prog.items() if v["n"] >= 30), key=lambda r: -r[1])
    W, rh, ml = 760, 15.5, 170
    H = rh * len(rows) + 30
    mx = max(r[1] for r in rows)
    scale = (W - ml - 90) / (mx * 1.05)
    avg = 100 * PT["high"] / PT["rev"]
    g = []
    for i, (b, p, hi, n) in enumerate(rows):
        y = 4 + i * rh
        g.append(f'<text x="{ml - 8}" y="{y + 12}" text-anchor="end" font-size="10.5" fill="{INK}">{esc(b)}</text>'
                 f'<rect x="{ml}" y="{y + 3}" width="{max(p * scale, 3):.1f}" height="11" rx="4" fill="{RED if p > avg else "#f3b8c1"}"/>'
                 f'<text x="{ml + max(p * scale, 3) + 6}" y="{y + 12.5}" font-size="10.5" font-weight="700" fill="{INK}">{p:.1f}%</text>')
    ax = ml + avg * scale
    g.append(f'<line x1="{ax}" x2="{ax}" y1="0" y2="{H - 22}" stroke="{INK}" stroke-dasharray="4 3"/>'
             f'<text x="{ax + 6}" y="{H - 8}" font-size="11.5" font-weight="700" fill="{INK}">All batches: {avg:.1f}%</text>')
    return f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="High-case cost as a share of revenue, by batch">{"".join(g)}</svg>'

def heat():
    cells = []
    head = "".join(f"<th>{s}% redeem</th>" for s in SENS_SHARE)
    for mpr in SENS_MPR:
        row = f'<th class="rh">{mpr} Miles = ₹1</th>'
        for s in SENS_SHARE:
            v = sens[mpr] * s / 100; p = 100 * v / PT["rev"]
            sel = " sel" if mpr == S["milesPerRupee"] and s == 100 else ""
            shade = min(1, v / (sens[min(SENS_MPR)] * 1.0))
            row += f'<td class="hc{sel}" style="background:rgba(215,31,58,{.06 + .34 * shade:.2f})"><b>{lakh(v)}</b><span>{pct(p)} of revenue</span></td>'
        cells.append(f"<tr>{row}</tr>")
    return f'<table class="heat"><tr><th></th>{head}</tr>{"".join(cells)}</table>'

# ------------------------------------------------------------------ headline figures
P1, P2 = PILOT[0], PILOT[1] if len(PILOT) > 1 else PILOT[0]
claim_pct = 100 * tot["claim"] / tot["n"]
avg_m = earned / N
med_m = st.median(allm)
cost_cap = earned * 0.1  # guardrail: at 10 Miles per rupee a Mile can never cost more than Re 0.10
mpr = S["milesPerRupee"]
guard = 100 / mpr
known_rev = [pilot[b]["rev"] for b in PILOT if pilot[b]["rev"]]
pilot_pct_known = []
for b in PILOT:
    if pilot[b]["rev"]:
        o = pilot[b]["o"]
        pilot_pct_known.append((b, 100 * o["high"] / pilot[b]["rev"], 100 * o["worst"] / pilot[b]["rev"]))
unconfirmed = [r for r in cfg["rewards"] if r["on"] and not r["costConfirmed"]]
est = lambda s: tot["high"] * s / 100
ceiling = math.ceil(tot["worst"] / 1e5 * 10) / 10 * 1e5

rev_note = ""
miss = [b for b in PILOT if not pilot[b]["rev"]]
if miss:
    rev_note = f'<p class="foot">Revenue share shown where the batch fee is on file; {esc(", ".join(miss))} fee to be added.</p>'

cost_rows = ""
for b in PILOT:
    o, r = pilot[b]["o"], pilot[b]["rev"]
    cost_rows += (f'<tr><td>{esc(b)}</td><td>{o["n"]:,}</td><td>{100 * o["claim"] / o["n"]:.0f}%</td><td>{lakh(o["high"])}</td>'
                  f'<td>{pct(100 * o["high"] / r) if r else "–"}</td><td>{lakh(o["worst"])}</td><td>{pct(100 * o["worst"] / r) if r else "–"}</td></tr>')
cost_rows += (f'<tr class="tot"><td>Both</td><td>{tot["n"]:,}</td><td>{claim_pct:.0f}%</td><td>{lakh(tot["high"])}</td>'
              + ('<td>–</td>' if miss else f'<td>{pct(100 * tot["high"] / sum(known_rev))}</td>') + f'<td>{lakh(tot["worst"])}</td>'
              + ('<td>–</td>' if miss else f'<td>{pct(100 * tot["worst"] / sum(known_rev))}</td>') + '</tr>')

CSS = f"""
@page{{size:A4;margin:0}}
*{{box-sizing:border-box}}html,body{{margin:0}}
body{{font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:{INK};background:#eceef2;-webkit-font-smoothing:antialiased;font-size:15px;line-height:1.45}}
.page{{width:794px;margin:0 auto;background:#fff;padding:0 0 8px;position:relative}}
.mast{{background:linear-gradient(110deg,#b8182c,#5a1019 62%,#1d2129);color:#fff;padding:26px 44px 40px}}
.mast .k{{font-size:12px;letter-spacing:.2em;text-transform:uppercase;opacity:.85}}
.logo{{font-family:Poppins,Inter,system-ui,sans-serif;font-weight:800;font-size:40px;letter-spacing:-1.5px;line-height:1;margin:10px 0 2px}}
.logo small{{display:block;font-weight:300;font-size:14px;letter-spacing:.3em;margin-top:6px}}
.mast h1{{margin:14px 0 0;font-size:23px;line-height:1.25;font-weight:700;max-width:640px}}
.ask{{margin:-22px 44px 0;position:relative;background:#fff;border-radius:16px;box-shadow:0 8px 28px rgba(20,22,31,.16);padding:18px 22px;display:grid;grid-template-columns:auto 1fr;gap:16px;align-items:center;border:2px solid {RED}}}
.ask .tag{{background:{RED};color:#fff;font-weight:800;font-size:12px;letter-spacing:.1em;text-transform:uppercase;border-radius:99px;padding:7px 13px;white-space:nowrap}}
.ask p{{margin:0;font-size:16px;font-weight:600}}
.ask p span{{color:{RED_D}}}
.sec{{padding:16px 44px 0;break-inside:avoid}}
.sec h2{{margin:0 0 4px;font-size:19px;letter-spacing:-.2px}}
.sec .sub{{margin:0 0 12px;color:{MUT};font-size:13.5px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:22px 44px 0}}
.kpi{{background:#f6f6f8;border-radius:14px;padding:14px 14px 12px}}
.kpi.hi{{background:{PINK}}}
.kpi b{{display:block;font-size:27px;letter-spacing:-.6px;line-height:1.1}}
.kpi span{{font-size:12.5px;color:{MUT}}}
.pill{{display:inline-block;font-weight:800;font-size:12px;border-radius:99px;padding:2px 10px;color:#fff}}
.pill.p1{{background:#e58a99}}.pill.p2{{background:{RED}}}.pill.p3{{background:{RED_D}}}
.bchips{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px}}
.bchip{{background:#f6f6f8;border-radius:12px;padding:10px 12px}}
.bchip>b{{font-size:13px}}
.bnum{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:6px}}
.bnum span{{font-size:11px;color:{MUT};line-height:1.2}}.bnum i{{display:block;font-style:normal;font-size:16px;font-weight:800;color:{INK}}}
.legend{{display:flex;gap:18px;justify-content:center;margin-top:6px;font-size:12.5px;color:{MUT}}}
.lg i{{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:6px;vertical-align:-1px}}
.flow{{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;gap:10px;align-items:center;text-align:center}}
.fb{{background:#f6f6f8;border-radius:14px;padding:12px 10px}}
.fb.r{{background:{PINK}}}
.fb b{{display:block;font-size:24px;letter-spacing:-.5px}}.fb span{{font-size:12.5px;color:{MUT}}}
.ar{{font-size:24px;color:{RED};font-weight:800}}
.guard{{margin-top:10px;background:{INK};color:#fff;border-radius:14px;padding:14px 18px;font-size:15px}}
.guard b{{color:#ffb3be}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}}
th,td{{padding:7px 8px;text-align:right;border-bottom:1px solid {LINE}}}
th:first-child,td:first-child{{text-align:left}}
th{{font-size:11.5px;letter-spacing:.05em;text-transform:uppercase;color:{MUT}}}
tr.tot td{{font-weight:800;border-top:2px solid {INK};border-bottom:0}}
table.heat td,table.heat th{{text-align:center;border:3px solid #fff}}
.heat th.rh{{text-align:left;white-space:nowrap;font-size:12.5px;color:{INK};text-transform:none;letter-spacing:0}}
.hc{{border-radius:10px;padding:8px 6px}}.hc b{{display:block;font-size:17px}}.hc span{{font-size:11.5px;color:{MUT}}}
.hc.sel{{outline:3px solid {INK};outline-offset:-3px}}
.three{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
.card{{background:#f6f6f8;border-radius:14px;padding:10px 12px}}
.card .ic{{width:28px;height:28px;border-radius:9px;background:{PINK};color:{RED};display:flex;align-items:center;justify-content:center;font-size:14px;margin-bottom:6px}}
.card b{{display:block;font-size:14.5px;margin-bottom:3px}}.card span{{font-size:12.5px;color:{MUT};line-height:1.4}}
.tl{{display:grid;grid-template-columns:repeat(4,1fr);gap:0;position:relative;margin-top:2px}}
.tl:before{{content:"";position:absolute;left:12%;right:12%;top:15px;height:3px;background:{PINK}}}
.st{{text-align:center;position:relative;padding:0 6px}}
.st i{{display:flex;width:32px;height:32px;margin:0 auto 8px;border-radius:50%;background:{RED};color:#fff;font-style:normal;font-weight:800;align-items:center;justify-content:center;position:relative}}
.st b{{display:block;font-size:13.5px}}.st span{{font-size:12px;color:{MUT}}}
.risk{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.rk{{border:1px solid {LINE};border-radius:12px;padding:9px 13px;font-size:12.5px}}.rk b{{display:block;font-size:13.5px}}
.rk em{{font-style:normal;color:{GREEN};font-weight:700}}
.foot{{margin:8px 44px 0;color:{MUT};font-size:11.5px;line-height:1.5}}
.sec .foot{{margin:8px 0 0}}
.end{{margin:18px 44px 0;background:{PINK};border-radius:16px;padding:18px 22px;display:flex;justify-content:space-between;gap:16px;align-items:center}}
.end b{{font-size:17px}}.end span{{color:{RED_D};font-weight:700}}
.pb{{break-before:page;page-break-before:always}}
@media print{{body{{background:#fff}}.page{{width:auto;margin:0}}}}
"""

html_doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Miles by Masai · Leadership brief</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Poppins:wght@300;800&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="page">

<div class="mast"><div class="k">Leadership brief · {esc(a.date)}</div>
  <div class="logo">miles<small>BY MASAI</small></div>
  <h1>A rewards programme built to drive learner engagement, with a cost we can cap by design.</h1></div>

<div class="ask"><span class="tag">Approval sought</span>
  <p>Simulated on <span>{len(PILOT)} concluded batches ({tot["n"]:,} students)</span>: had Miles rewards run, they would have cost <span>{lakh(tot["high"])}</span> if every eligible student claimed once, and never more than <span>{lakh(ceiling)}</span>. Approve launching Miles rewards on this cost model.</p></div>

<div class="kpis">
  <div class="kpi"><b>{tot["n"]:,}</b><span>students simulated</span></div>
  <div class="kpi"><b>{avg_m:,.0f}</b><span>avg Miles earned · median {med_m:,.0f}</span></div>
  <div class="kpi hi"><b>{lakh(tot["high"])}</b><span>cost if every eligible student claims once</span></div>
  <div class="kpi hi"><b>{lakh(tot["worst"])}</b><span>absolute ceiling (all Miles spent)</span></div>
</div>

<div class="sec"><h2>Where students stand</h2><p class="sub">Share of each batch, by Miles earned</p>
  {chart_distribution()}</div>

<div class="sec"><h2>Students by Miles earned</h2><p class="sub">Share at or above each Miles level</p>
  {chart_reach()}</div>

<div class="pb"></div>
<div class="sec" style="padding-top:34px"><h2>What it would have cost</h2><p class="sub">₹ lakh &nbsp;·&nbsp; <span class="pill p1">Low</span> cheapest reward each &nbsp; <span class="pill p2">High</span> best reward each, once &nbsp; <span class="pill p3">Worst case</span> every Mile spent</p>
  {chart_cost()}
  <table style="margin-top:10px"><tr><th>Batch</th><th>Students</th><th>Can claim</th><th>High</th><th>% of revenue</th><th>Worst case</th><th>% of revenue</th></tr>{cost_rows}</table>
  {rev_note}</div>

<div class="sec"><h2>Why the cost cannot run away</h2>
  <div class="flow"><div class="fb"><b>{earned / 1e5:,.1f} L</b><span>Miles earned</span></div><div class="ar">×</div>
    <div class="fb r"><b>₹{1 / mpr:.2f}</b><span>max cost per Mile<br>({mpr} Miles = ₹1)</span></div><div class="ar">=</div>
    <div class="fb"><b>≤ {lakh(cost_cap)}</b><span>hard ceiling</span></div></div>
  <div class="guard">Every reward is priced from its cost at the same rate, so spending <b>more Miles never costs more than ₹{1 / mpr:.2f} each</b>. Ceiling is {guard:.0f}% of Miles issued. Modelled worst case: <b>{lakh(tot["worst"])}</b>.</div></div>

<div class="sec"><h2>If assumptions move</h2><p class="sub">High-case cost across all {len(prog)} batches, by value of a Mile and by how many students redeem.</p>
  {heat()}
  <p class="foot">Highlighted: {mpr} Miles = ₹1, everyone redeems. At 25–50% redemption the cost would be {lakh(PT["high"] * .25)} to {lakh(PT["high"] * .5)}.</p></div>

<div class="pb"></div>
<div class="sec" style="padding-top:34px"><h2>Across all batches</h2><p class="sub">Applied to all {len(prog)} batches ({PT["n"]:,} students, revenue {lakh(PT["rev"])}): High case is <b>{lakh(PT["high"])} ({pct(100 * PT["high"] / PT["rev"])} of revenue)</b>; worst case {lakh(PT["worst"])} ({pct(100 * PT["worst"] / PT["rev"])}).</p>
  {chart_scale()}</div>

<div class="sec"><h2>Safeguards built in</h2>
  <div class="three">
   <div class="card"><div class="ic">✓</div><b>Student confirms</b><span>Explicit consent, stored with time.</span></div>
   <div class="card"><div class="ic">▤</div><b>Every claim logged</b><span>Each request is a sheet row with a status.</span></div>
   <div class="card"><div class="ic">⚖</div><b>Team reviews</b><span>Can reject; Miles refunded automatically.</span></div>
   <div class="card"><div class="ic">₹</div><b>Fixed Mile value</b><span>All rewards priced at {mpr} Miles = ₹1.</span></div>
   <div class="card"><div class="ic">↻</div><b>Daily refresh</b><span>Balances and cost update every morning.</span></div>
   <div class="card"><div class="ic">⌁</div><b>Live cost model</b><span>Test any assumption instantly; save it.</span></div>
  </div></div>

<div class="sec"><h2>Watch-outs, handled</h2>
  <div class="risk">
   <div class="rk"><b>{len(unconfirmed)} premium rewards have estimated costs</b>Company interview, hiring drive. <em>Only 40,000+ Miles reach them ({sum(1 for x in allm if x >= 40000)} student here).</em></div>
   <div class="rk"><b>Miles keep growing</b>Cost rises with engagement. <em>Capped at ₹{1 / mpr:.2f} per Mile.</em></div>
   <div class="rk"><b>Redemption rate is unknown</b>No history yet. <em>Ceiling holds at any rate; tracked from day one.</em></div>
   <div class="rk"><b>Physical rewards add logistics</b>Gear needs vendors. <em>Digital and experience rewards launch first.</em></div>
  </div></div>

<div class="sec"><h2>Next steps</h2>
  <div class="tl">
   <div class="st"><i>1</i><b>Approve</b><span>the cost model</span></div>
   <div class="st"><i>2</i><b>Set up</b><span>rewards and vendors</span></div>
   <div class="st"><i>3</i><b>Launch</b><span>with the next batch</span></div>
   <div class="st"><i>4</i><b>Track monthly</b><span>cost vs ceiling</span></div>
  </div></div>

<p class="foot">Retrospective simulation on concluded batches. Data: Metabase export, 16 Oct 2026. No streak boost. Costs are cost to Masai per reward. Method: docs/cost_calculation.md.</p>
</div></body></html>"""

out = Path(a.out)
out.parent.mkdir(parents=True, exist_ok=True)
Path(f"{out}.html").write_text(html_doc)
print(f"wrote {out}.html")
chrome = "/Users/inno/.cache/puppeteer/chrome/mac_arm-151.0.7922.47/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
if Path(chrome).exists():
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=6000",
                    f"--print-to-pdf={out}.pdf", f"file://{out}.html"], capture_output=True, timeout=120)
    print(f"wrote {out}.pdf" if Path(f"{out}.pdf").exists() else "pdf failed")
print(json.dumps(dict(students=tot["n"], claim_pct=round(claim_pct), low=tot["low"], high=tot["high"], worst=tot["worst"], programme_high=PT["high"],
                      programme_pct=round(100 * PT["high"] / PT["rev"], 2), ceiling=ceiling, unconfirmed=len(unconfirmed))))

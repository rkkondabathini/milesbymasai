"""Leadership one-pager (PDF) for the %-of-max ladder, simulated on concluded batches.
    python3 ops/leadership_ladder_pdf.py --batches completed_batches.csv --fit-source export1.csv ... [--fee BATCH=fee]
Aggregates only: no student data is written."""
import argparse, statistics as st, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ladder as LD, rate_card as RC, leadership_numbers as L, payout_sim as ps

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--batches", required=True, nargs="+")
ap.add_argument("--fit-source", required=True, nargs="+")
ap.add_argument("--config", default=str(ROOT / "updated_config.json"))
ap.add_argument("--fee", action="append", default=[])
ap.add_argument("--target", type=float, default=1.25)
ap.add_argument("--out", default=str(ROOT / "data/output/leadership_ladder"))
a = ap.parse_args()

cfg = L.load_cfg(a.config); R = dict(cfg["settings"]["milesPerActivity"]); cap = cfg["settings"]["repeatCap"]
ladder = LD.ladder_from_config(cfg)
design = RC.read_design(ROOT / "data/input/batch_design.csv"); fees = RC.read_fees(ROOT / "data/input/revenue.csv")
fees.update({k: float(v) for k, v in (f.split("=") for f in a.fee)})
shares = LD.quantiles(LD.pooled_shares(RC.group(a.fit_source), design, fees, R))
rows = []
for b, rs in sorted(RC.group(a.batches).items(), key=lambda kv: -len(kv[1])):
    W = design[b]["weeks"] if b in design else round(st.median(ps.n(r["mandatory_total"]) for r in rs) / 2)
    fee = fees[b]; M = LD.max_miles(W, R); lv = LD.fit_level(fee, M, shares, ladder, a.target)
    ms = [RC.miles(RC.capped_counts(r, W), R) for r in rs]
    o = L.evaluate(ms, LD.prices(ladder, M, lv), cap)
    rows.append(dict(b=b, n=len(rs), W=W, fee=fee, M=M, lv=lv, rev=fee * len(rs), low=o["low"], high=o["high"], worst=o["worst"], claim=100 * o["claim"] / o["n"]))
T = {k: sum(r[k] for r in rows) for k in ("n", "rev", "low", "high", "worst")}
pc = lambda v, r: 100 * v / r
lakh = lambda v: f"₹{v / 1e5:.1f} L"
col = lambda p: "#1a8f58" if 1 <= p <= 1.5 else ("#b86e00" if p < 1 else "#c4182f")

def bar(label, v, rev, mx):
    p = pc(v, rev); w = 520 * p / mx
    return f'<div class="br"><span class="bl">{label}</span><svg width="560" height="26"><rect width="{w:.0f}" height="22" rx="4" fill="{col(p)}"/><text x="{w + 6:.0f}" y="16" font-size="13" font-weight="700">{p:.2f}%</text></svg><span class="bv">{lakh(v)}</span></div>'

band = '<div class="band">Budget band: 1 to 1.5% of batch revenue</div>'
mx = 2.0
cases = "".join(bar(n, T[k], T["rev"], mx) for n, k in (("Low: cheapest reward each", "low"), ("High: best reward each, once", "high"), ("Worst: every Mile spent", "worst")))
per = "".join(bar(f'{r["b"]} <small>({r["n"]:,} students)</small>', r["high"], r["rev"], mx) for r in rows)
tbl = "".join(f'<tr><td>{r["b"]}</td><td>{r["n"]:,}</td><td>{r["W"]}</td><td>₹{r["fee"]:,.0f}</td><td>{r["M"]:,}</td><td>{r["lv"]:.2f}</td><td>{r["claim"]:.0f}%</td></tr>' for r in rows)
ex = rows[0]["M"]
ladder_rows = [(x["name"], x["pct"]) for x in ladder if x["name"] in LD.OVERRIDES] + [("A ₹1,500 reward", LD.default_pct(1500)), ("A ₹500 reward", LD.default_pct(500))]
lad = "".join(f'<tr><td>{n}</td><td>{p * 100:.0f}% of max</td><td>{LD.rstep(p * ex):,} Miles</td></tr>' for n, p in ladder_rows)
html = f"""<!doctype html><meta charset=utf-8><title>Miles by Masai: reward cost</title><style>
@page{{size:A4;margin:14mm}}body{{font:14px/1.45 -apple-system,Helvetica,Arial,sans-serif;color:#14161f;margin:0}}
h1{{font-size:24px;margin:0}}h2{{font-size:15px;margin:22px 0 6px}}.s{{color:#6b7280}}
.k{{display:flex;gap:12px;margin:14px 0}}.k div{{flex:1;background:#fdecef;border-radius:10px;padding:12px}}.k b{{font-size:26px;display:block}}
.br{{display:flex;align-items:center;gap:8px;margin:3px 0}}.bl{{width:230px;font-size:12.5px}}.bl small{{color:#6b7280}}.bv{{font-weight:700;width:70px}}
.band{{font-size:12px;color:#6b7280;margin:2px 0 6px}}table{{border-collapse:collapse;width:100%;font-size:12.5px}}td,th{{padding:5px 8px;border-bottom:1px solid #e6e8ee;text-align:right}}td:first-child,th:first-child{{text-align:left}}th{{color:#6b7280;font-size:11px;text-transform:uppercase}}
.n{{font-size:12px;color:#6b7280;margin-top:14px}}</style>
<h1>Miles by Masai: what rewards would have cost</h1>
<div class="s">Replayed on {len(rows)} completed batches: {T['n']:,} students, ₹{T['rev'] / 1e7:.2f} crore of fees. Each reward is priced as a share of the batch's maximum Miles.</div>
<div class="k"><div><span class="s">Best reward each</span><b>{lakh(T['high'])}</b>{pc(T['high'], T['rev']):.2f}% of revenue</div><div><span class="s">Worst case</span><b>{lakh(T['worst'])}</b>{pc(T['worst'], T['rev']):.2f}% of revenue</div><div><span class="s">Cheapest reward each</span><b>{lakh(T['low'])}</b>{pc(T['low'], T['rev']):.2f}% of revenue</div></div>
<h2>Cost as a share of revenue, all four batches</h2>{band}{cases}
<h2>By batch (best reward each)</h2>{band}{per}
<h2>The price card</h2>
<table><tr><th>Reward</th><th>Price</th><th>In a {ex:,}-Mile batch</th></tr>{lad}</table>
<div class="s" style="margin-top:6px">Everyday rewards scale with a per-batch price level, set from the fee so cost stays near {a.target}% of revenue; the premium ones above stay fixed.</div>
<h2>Batch set-up</h2><table><tr><th>Batch</th><th>Students</th><th>Weeks</th><th>Fee</th><th>Max Miles</th><th>Price level</th><th>Can claim</th></tr>{tbl}</table>
<div class="n">Assumes every student redeems. Fees marked as assumed in the email and programme length for BITSoM-PM-2507 are to be confirmed. Reward costs for founder time, company interviews and hiring drives are estimates.</div>"""
Path(a.out + ".html").write_text(html)
chrome = next(Path("/Users/inno/.cache/puppeteer/chrome").glob("*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"))
subprocess.run([str(chrome), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={a.out}.pdf", "file://" + a.out + ".html"], check=True, capture_output=True)
print("wrote", a.out + ".pdf")

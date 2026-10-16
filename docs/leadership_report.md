# Generating the leadership PDF

The report is produced from three inputs: a saved playground config, a Metabase export of the batches to simulate, and an
export covering all batches (for the "across all batches" page). It is aggregate only: no student names.

## One command
```
python3 ops/leadership_report.py \
  --config updated_config.json \
  --pilot query_result_<concluded batches>.csv \
  --programme query_result_<all batches>.csv \
  --fee IITP-AIML-2601=50000 \
  --date "16 Oct 2026"
```
Output: `data/output/leadership.html` and `data/output/leadership.pdf` (5 pages: summary, cost, across batches,
reward catalogue, how rewards are availed).

| Option | Meaning |
|---|---|
| `--config` | JSON saved from the playground (Save config). Holds rates, rewards, Miles prices, costs, fees. |
| `--pilot` | Export for the batches to simulate (the name is historical; they are concluded batches). |
| `--programme` | Export with every batch; drives the "Across all batches" page and the sensitivity grid. |
| `--fee BATCH=amount` | Fee per student for a batch missing from the config. Repeat the flag for several. |
| `--date` | Date printed in the masthead. |
| `--out` | Output path without extension (default `data/output/leadership`). |

## What it needs
- Python 3. No packages to install.
- A Chrome, Chromium, Brave or Edge install for the PDF step (found automatically; set `CHROME_PATH` to override).
- No Chrome? The `.html` is still written. Open it in a browser and use Print > Save as PDF (A4, margins none, background graphics on).

## Updating it
1. Change assumptions in the playground, click Save config.
2. Re-run the command with the new config. Numbers, the catalogue table and the "how rewards are availed" page update together.
3. Reward delivery rules live in `webapp/reward_rules.json` (shared with the dashboard and the sheet script).

The PDF contains fees and revenue. It is excluded from git; share it directly.

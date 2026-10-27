#!/usr/bin/env bash
# Runs on Vercel for every deploy: pull Metabase -> compute Miles -> build the encrypted site.
# Env (Vercel project settings):
#   REDEEM_SECRET           signs redemption requests (must match the Apps Script property)
#   MILES_REDEEM_ENDPOINT   Apps Script /exec URL (optional until redemption is switched on)
#   MILES_REDEEMED_CSV      published CSV of the Redemptions tab (optional)
#   METABASE_DAILY          override of the date-level Metabase CSV URL (optional)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "build env: REDEEM_SECRET=$([ -n "${REDEEM_SECRET:-}" ] && echo set || echo MISSING)" \
     "MILES_REDEEM_ENDPOINT=$([ -n "${MILES_REDEEM_ENDPOINT:-}" ] && echo set || echo not-set)" \
     "MILES_REDEEMED_CSV=$([ -n "${MILES_REDEEMED_CSV:-}" ] && echo set || echo not-set)"
if [ -n "${MILES_REDEEM_ENDPOINT:-}" ] && [ -z "${REDEEM_SECRET:-}" ]; then
  echo "ERROR: MILES_REDEEM_ENDPOINT is set but REDEEM_SECRET is empty. Add REDEEM_SECRET in Vercel -> Settings -> Environment Variables (Production), then redeploy." >&2
  exit 1
fi

if [ -n "${MILES_DEMO:-}" ]; then   # leadership demo project: invented learners, no Metabase, no sheet
  echo "building DEMO site"; node webapp/build.mjs; rm -rf webapp/dist; cp -R webapp/dist-demo webapp/dist; exit 0
fi

command -v python3 >/dev/null || { echo "python3 not available in this build image"; exit 1; }
METABASE_DAILY="${METABASE_DAILY:-https://metabase.masaischool.com/public/question/baf81ac4-fa74-4272-b341-09c097f06ec2.csv}"

python3 -I miles.py ingest "$METABASE_DAILY"
if [ -n "${MILES_REDEEMED_CSV:-}" ]; then python3 -I miles.py ingest-redemptions "$MILES_REDEEMED_CSV"; fi

AS_OF=$(python3 -I -c "import csv;print(max(r['date'] for r in csv.DictReader(open('data/store/daily_activity.csv'))))")
echo "data as of $AS_OF"
python3 -I miles.py run --as-of "$AS_OF"

node webapp/build.mjs

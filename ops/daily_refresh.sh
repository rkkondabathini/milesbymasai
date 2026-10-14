#!/usr/bin/env bash
# Daily refresh: Metabase -> engine -> encrypted site build -> Vercel production deploy.
# Required env:  VERCEL_TOKEN
# Optional env:  MILES_REDEEMED_CSV   published-CSV URL of the "Redemptions" sheet (so redeemed Miles are deducted)
#                MILES_REDEEM_ENDPOINT Apps Script /exec URL (turns on in-dashboard redemption)
#                MILES_REDEEM_FORM_URL fallback form link
set -euo pipefail
cd "$(dirname "$0")/.."

METABASE_DAILY="${METABASE_DAILY:-https://metabase.masaischool.com/public/question/baf81ac4-fa74-4272-b341-09c097f06ec2.csv}"

python3 -I miles.py ingest "$METABASE_DAILY"
if [ -n "${MILES_REDEEMED_CSV:-}" ]; then python3 -I miles.py ingest-redemptions "$MILES_REDEEMED_CSV"; fi

AS_OF=$(python3 -I -c "import csv;print(max(r['date'] for r in csv.DictReader(open('data/store/daily_activity.csv'))))")
python3 -I miles.py run --as-of "$AS_OF"

node webapp/build.mjs
npx --yes vercel@latest deploy webapp/dist --prod --yes --token "$VERCEL_TOKEN"

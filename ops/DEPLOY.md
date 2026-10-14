# Deploying Miles by Masai

## One-time
1. Redemption inbox (Google Sheet + Apps Script)
   - Create a Google Sheet "Miles redemptions" -> Extensions -> Apps Script.
   - Paste `webapp/redeem_webhook.gs` (regenerated on every build, so the reward costs stay in sync).
   - Script properties: `REDEEM_SECRET` = contents of `webapp/.redeem_secret`; optional `NOTIFY_EMAIL`.
   - Deploy -> Web app -> Execute as me, access: Anyone. Copy the `/exec` URL.
   - File -> Share -> Publish to web -> the `Redemptions` tab as CSV. Copy that URL.
2. Vercel
   - `VERCEL_TOKEN` (Account Settings -> Tokens). First deploy creates the project.
3. Build env
   - `MILES_REDEEM_ENDPOINT` = the Apps Script `/exec` URL
   - `MILES_REDEEMED_CSV`   = the published CSV URL of the Redemptions tab

## Daily
`ops/daily_refresh.sh` (cron / GitHub Action): ingest Metabase, sync redemptions, recompute, rebuild, deploy.

## Working the redemption queue
The team updates column L (`status`) on the Redemptions tab:
`requested` -> `scheduled` -> `completed`, or `rejected` (Miles are refunded on the next daily build).

## How a redemption is stored
1. Learner opens a reward -> dialog shows cost breakdown, an editable contact phone and the consent checkbox.
2. "Confirm redeem" (enabled only after the box is ticked and the phone has 10 digits) POSTs JSON to the
   Apps Script web app (`MILES_REDEEM_ENDPOINT`).
3. The script verifies the HMAC token, the reward cost (from its own catalogue), the consent flag and the balance,
   then appends one row to the `Redemptions` tab: timestamp, request id, learner, contact details, reward, cost,
   balance, status=requested, plus `confirmed_at`, the exact consent text and `contact_phone`.
4. The team updates `status`; the published CSV of that tab is read back by the daily build, which deducts
   completed/scheduled/requested Miles and refunds `rejected` ones.

### Test it without Google
    python3 ops/redeem_local.py                      # receiver, writes data/output/redemptions_local.csv
    MILES_REDEEM_ENDPOINT=http://127.0.0.1:8787 node webapp/build.mjs

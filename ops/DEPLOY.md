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

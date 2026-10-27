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

## Updating the redemption sheet script (adds delivery details, statuses, due dates)
1. Rebuild (`node webapp/build.mjs`) so `webapp/redeem_webhook.gs` is regenerated with the current rewards and rules.
2. Open the sheet > Extensions > Apps Script, replace the code with the new `redeem_webhook.gs`, save.
3. Run `setup()`. It appends the new columns to the right of the existing ones, so existing rows are kept.
   If it reports a column in the wrong position, the sheet header was edited by hand: restore the original order.
4. Deploy > Manage deployments > pencil > **New version** (saving alone does not update the live web app).
5. Optional env var for the dashboard: `MILES_REWARDS_EMAIL` (mailbox students send reimbursement invoices to).
See `docs/redemption_operations.md` for the full operating procedure.


## Leadership demo site (separate Vercel project, no real data)

The demo is the same app with two invented learners (Aarav, an active learner with a streak and 6,000 Miles to spend, and Meera, a new learner). Redemptions are simulated in the browser, so nothing reaches the Redemptions sheet. It contains no learner data, fees or secrets, and the real site is not touched.

1. Vercel -> Add New -> Project -> import `rkkondabathini/milesbymasai` again, name it e.g. `milesbymasai-demo`.
2. Settings -> Environment Variables (Production): `MILES_DEMO` = `1`. Do not add REDEEM_SECRET, MILES_REDEEM_ENDPOINT or MILES_REDEEMED_CSV.
3. Deploy (the build runs `ops/vercel_build.sh`, which builds the demo and skips Metabase).
4. Share the URL. The login page shows two buttons that fill in the demo login. "Reset demo" (bottom bar) clears reserved Miles so the flow can be shown again.

Local preview: `MILES_DEMO=1 node webapp/build.mjs`, then open `webapp/dist-demo/index.html`.

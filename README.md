# Miles by Masai

Learner rewards dashboard: Metabase activity -> Miles, streaks and boosts -> an encrypted,
single-file static site (phone + email unlocks a learner's own data), deployed on Vercel.

```
miles.py                engine: ingest Metabase, upsert store, compute weekly streaks / balances / payloads
config.json             rates, streak multipliers, rewards (and Masai cost per reward)
cost_model.py           redemption cost exposure per batch / learner
webapp/                 template, encryption build, FAQ, redemption webhook template, vercel.json
ops/                    daily_refresh.sh (ingest -> build -> deploy) and DEPLOY.md
```

## Run locally
```
python3 miles.py ingest <metabase date-level csv url>
python3 miles.py run --as-of YYYY-MM-DD
node webapp/build.mjs        # -> webapp/dist/index.html
python3 webapp/serve.py 8080
```

## Not in this repo (on purpose)
Learner data (`data/store`, `data/output`, `data/input/learners.csv`, `redemptions.csv`),
the redemption signing secret (`webapp/.redeem_secret`) and the built site (`webapp/dist`).
Generate them locally or in CI. See `ops/DEPLOY.md` for the secrets CI needs.

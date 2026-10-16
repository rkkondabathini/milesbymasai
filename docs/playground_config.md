# Playground config (JSON)

The playground (`data/output/playground.html`) can save everything you change and load it back.

- **Save config** downloads `miles_playground_config_YYYY-MM-DD_HHMM.json`.
- **Load config** reads one back. Rewards are matched by name; new ones become "Custom" rewards.
- **Your last session is restored automatically** when you reopen the file in the same browser. **Reset all** clears it.
- Bake a saved config in as the starting point of a rebuilt playground:
  `python3 ops/build_playground.py --source export.csv --config my_config.json`

The file holds fee per student (commercial data), so keep it out of git.

## Schema (version 1)
```json
{
  "app": "miles-cost-playground",
  "version": 1,
  "savedAt": "2026-10-16T10:40:00.000Z",
  "settings": {
    "milesPerActivity": { "ml": 200, "mr": 100, "nl": 150, "nr": 50, "p": 100, "ga": 300, "ge": 300, "me": 150 },
    "streakBoost": 1,
    "shareWhoRedeem": 100,
    "repeatCap": 3,
    "autoPriceMilesFromCost": true,
    "milesPerRupee": 10,
    "roundMilesTo": 100
  },
  "rewards": [
    { "name": "Institute t-shirt", "group": "Core rewards", "miles": 5000, "cost": 500,
      "repeatable": false, "on": true, "manualMiles": false, "costConfirmed": true }
  ],
  "feePerStudent": { "IITP-SDAI-2602": 25099 },
  "dataset": { "batches": [ { "name": "IITP-SDAI-2602", "students": 616 } ] },
  "resultsSnapshot": { "low": 0, "high": 0, "worstCase": 0, "perBatch": [] }
}
```

| Field | Meaning |
|---|---|
| `milesPerActivity` | `ml` mandatory live, `mr` mandatory recording, `nl` other live, `nr` other recording, `p` practice, `ga` graded assignment, `ge` graded evaluation, `me` mock evaluation |
| `repeatCap` | max claims per repeatable reward; `0` = unlimited |
| `autoPriceMilesFromCost` | when true, a reward's Miles = `round(cost x milesPerRupee / roundMilesTo) x roundMilesTo`, unless `manualMiles` is true |
| `rewards[].cost` | cost to Masai in rupees; a cost of 0 adds no cost |
| `resultsSnapshot` | informational only. It is recomputed on load, never read back |
| `dataset` | batches present when saved; on load, batches missing from the current build are reported and ignored |

# Batch rate cards: the ladder method

Every batch has a **Max Miles** figure from its length (weeks × (2 mandatory live + 3 optional live + 4 practice items) + 10 evaluation items, at the standard earn rates), rounded to the nearest 50. Example: 26 weeks = 35,500.

Each reward costs a **% of the batch's Max Miles**, rounded to 50 (so 90% of 35,500 = 31,950, never 31,957). Founder lunch/call is 90%, Wall of Fame + LinkedIn shout-out 85%; the rest follow cost (about 14% for a ₹500 item, 42% for ₹1,500, 56% for ₹2,000).

**Price level.** One number per batch (1.0 = ladder as written). Rewards of 70% and above are **fixed**; the others are multiplied by the level. The level is fitted per batch so the expected High-case cost lands on the target (default 1.25% of revenue). Low-fee batches get a higher level (₹20k ≈ 4×), so everyday rewards are harder to reach there; fee-heavy batches stay near 1.

Validation on 25 completed batches: ladder alone 3 in band; with fitted level 17 in band (1–1.5%), median 1.30%, combined 1.28%.

Run: `python3 ops/ladder.py --source <exports>`; playground: `python3 ops/build_playground.py --source <exports> --config updated_config.json`.

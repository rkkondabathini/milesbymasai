# Batch rate cards

Goal: every batch earns Miles at a rate that fits its length and fee, so the cost of redemptions lands at about 1 to 1.5% of that
batch's revenue (it was up to 4% on the standard rates).

## 1. Your pattern against the completed batches
| Your assumption | What the data shows | Verdict |
|---|---|---|
| 2 mandatory lectures a week | Mandatory lectures run at about 2 a week. Completed batches total 23 to 75 mandatory lectures, i.e. 12 to 38 weeks, which matches 3, 6 and 8 month programmes. (Weeks are inferred as mandatory ÷ 2; the export has no dates.) | Holds |
| 2 optional sessions + 1 buffer a week (3 earn Miles) | Optional sessions per week range from about 2 to 19. Some batches (BITSoM) schedule hundreds. Students never attend that many, so real Miles barely change, but the theoretical ceiling does | Use 3 as a **cap** |
| 1 practice assignment per mandatory lecture | The data counts **2 items** per mandatory lecture (an Objective and a Subjective part) | Holds, as 2 items |
| About 5 evaluations in the programme | The data shows about **10 evaluation items** (5 evaluations of 2 parts), up to 29 in PM programmes | Holds, as 10 items |

## 2. Maximum Miles by length (standard rates, all sessions attended live)
`weeks x (2 x 200 + 3 x 150 + 4 x 100) + 10 x 300 = 1,250 x weeks + 3,000`

| Programme | Weeks | Maximum Miles |
|---|---|---|
| 3 months | 13 | 19,250 |
| 6 months | 26 | 35,500 |
| 8 months | 35 | 46,750 |

The "80 to 90k" figures come from uncapped optional sessions (BITSoM-PM-2511 lists 495 of them). With the cap, even an 8 month programme tops out near 47k.

## 3. What students actually earn
Across the 25 completed batches the average student earns **26%** of the capped maximum (range 15% to 34%). It is steady across programme lengths,
which is what makes a rate card from the programme design reliable. The High-case cost is **0.86** of (Miles x ₹0.10).

## 4. The rate card
```
target maximum Miles = target% x fee / (cost conversion x engagement x ₹ per Mile)          (target 1.25%, 10 Miles = ₹1)
multiplier k         = target maximum / standard maximum for that programme length
each rate            = standard rate x k, rounded to 5
```
Rule of thumb at 1.25%: **maximum Miles ≈ 0.55 x course fee**.

## 5. Result on the completed batches
| | Standard rates | Batch rate cards |
|---|---|---|
| Range of High cost as % of revenue | 0.40% to 4.20% | 0.02% to 1.65% |
| Median | 1.74% | 1.15% |
| Batches inside 1 to 1.5% | 3 of 25 | **17 of 25** |
| Combined | about 1.7% | **1.19%** |

Caveat: the engagement figure is measured on these same batches, so this is a fit, not an independent test. Run it on the next batches that complete.

## 6. What this means for students
The rate card cuts rates for low-fee batches (about 0.3 to 0.6 of standard) and raises them for high-fee short ones (about 1.8 to 2.2).
**With 1.25% a ₹25,000 batch can reach about 13,900 Miles at best, just under the 15,000 Miles that unlock the ₹1,500 1:1 sessions.** At the top of your band
(1.5%) it reaches about 16,600. Decide whether low-fee batches should reach those rewards (raise their target), or whether
merchandise and gear is the right top tier for them. Both are one number in the playground.

## 7. Using it
**Playground:** section "5 · Batch rate cards". Set the target, the weekly pattern and each batch's weeks; type a multiplier to lock a batch.
Save config keeps everything. **Command line:**
```
python3 ops/rate_card.py --init --source <exports>      # draft data/input/batch_design.csv (weeks, status)
python3 ops/rate_card.py --source <exports> --target 1.25   # fit, validate, write data/output/rate_cards.csv/json
```
Edit `data/input/batch_design.csv` first: rows marked CONFIRM are guesses (ongoing batches, and batches with too little data).

## 8. To confirm
1. The `weeks` of each batch, especially the ongoing ones: IITR-PM-2512 (48), IITP-AIML-2601 (40), IITREICT-DSAI-2603 (37), IITP-SDAI-2606 (21), IITP-AIMLPX-ADV-2608 (26 assumed), and the very short WE-DA batches (4 to 6 weeks).
2. The target (1.25% is the middle of 1 to 1.5%).
3. Whether students see their batch's rates (the dashboard still uses one standard rate card; it must read the batch multiplier before launch).

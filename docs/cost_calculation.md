# How the Miles cost is calculated

How the playground (`data/output/playground.html`) and the simulation (`ops/payout_sim.py`) turn student activity into
rupees. Worked example: student `iitp_aimlt_26012063`, batch IITP-AIMLT-2603. Figures use the 16 Oct 2026 export.

## Step 1: Miles earned by a student
Each activity count is multiplied by its rate, then added.

| Activity | Count | Rate | Miles |
|---|---|---|---|
| Mandatory lecture, live | 13 | 200 | 2,600 |
| Mandatory lecture, recording | 29 | 100 | 2,900 |
| Other lecture, live | 10 | 150 | 1,500 |
| Other lecture, recording | 12 | 50 | 600 |
| Practice assignment | 10 | 100 | 1,000 |
| Graded evaluation | 2 | 300 | 600 |
| **Total** | | | **9,200** |

Rules behind the counts:
- A lecture earns once. If the student attended live, the recording does not count again.
- An optional streak boost multiplies the total (1.0 = none). The data export carries no boost.

## Step 2: Miles price of each reward
With auto-pricing on: `Miles = round(cost x Miles per Rs / rounding) x rounding`.
At 10 Miles per Rs and rounding to 100: Rs 500 t-shirt = 5,000 Miles, Rs 800 hoodie = 8,000, Rs 1,500 doubt session =
15,000, Rs 4,000 IM session = 40,000. Rewards with a cost of Rs 0 cannot be priced this way and are set by hand.

## Step 3: What the student can claim
Rewards that cost Masai money and have a Miles price of 9,200 or less: the t-shirt (5,000 Miles, Rs 500) and the
hoodie (8,000 Miles, Rs 800).

## Step 4: The three scenarios for one student
| Scenario | Rule | This student |
|---|---|---|
| Low | Cheapest reward they can afford | t-shirt = Rs 500 |
| High | Costliest single reward they can afford, once | hoodie = Rs 800 |
| Worst case | The mix that costs Masai the most for their Miles, repeats allowed up to the chosen limit | Rs 800 (t-shirt + hoodie needs 13,000 Miles) |

A student who can afford nothing costs Rs 0 in all three and is not counted in "can claim".

Worst case is a "best mix for a Miles budget" calculation (knapsack). Rewards marked Repeat can be used up to the limit
(1, 2, 3, 5 or unlimited); the others at most once.

Repeats matter only when rewards differ in cost per Mile (the "Rs per 1,000 Miles" column). At a flat 10 Miles per Rs every
reward costs Rs 100 per 1,000 Miles, so repeating changes nothing. With the old uneven prices the doubt session cost
Rs 1,500 per 1,000 Miles and repeats exploded the total.

## Step 5: Roll up to a batch
Sum every student's cost for each scenario, then multiply by the share who redeem (at 50%, every figure halves).
`Batch cost = (sum of student costs) x share who redeem`. Miles redeemed is the sum of the Miles of the chosen rewards.

## Step 6: Revenue and percentage
- Revenue = fee per student x students. IITP-AIMLT-2603: 20,000 x 1,708 = Rs 3,41,60,000.
- % of revenue = scenario cost / revenue. Green under 10%, amber 10-25%, red over 25%.
- Rs per student = scenario cost / all students in the batch, including those who cannot claim yet.

## Assumptions
- Cost to Masai is taken at face value. The two 25,000-Mile rewards are Rs 0 until their cost is confirmed.
- Worst case assumes everyone redeems in the most expensive way. It is an upper bound, not a forecast.
- Miles are those earned so far; students keep earning, so every figure grows over time.
- Duplicate student rows within a batch are merged by taking the higher count per field, so no activity is lost.

## Maximum Miles a student can get
Two different questions:

**Highest actual today:** 50,400 Miles (`iitreict_dsai_26021305`, IITREICT-DSAI-2603). 138 students are above 25,000
and 4 are above 40,000.

**Theoretical ceiling** (every lecture attended live, every assignment and evaluation done, up to the 16 Oct export):

| Batch | Highest actual | Ceiling | Ceiling with 1.5x streak |
|---|---|---|---|
| IITREICT-DSAI-2603 | 50,400 | 68,000 | 102,000 |
| IITP-AIMLT-2603 | 37,550 | 63,800 | 95,700 |
| IITP-SDAI-2602 | 30,950 | 39,500 | 59,250 |
| IITP-SDAIHIN-2602 | 27,400 | 31,850 | 47,775 |
| IITRPF-AAITN-2604 | 23,500 | 26,650 | 39,975 |
| IITRPF-AAIT-2604 | 23,100 | 27,900 | 41,850 |
| IITP-SDAI-2606 | 22,800 | 29,900 | 44,850 |
| IITP-SDAITAM-2602 | 22,200 | 29,450 | 44,175 |
| IITRPF-AAIK-2604 | 21,250 | 27,550 | 41,325 |
| IIMROH-PMGM-2603 | 17,300 | 23,850 | 35,775 |
| FITT-EN-2604 | 16,050 | 18,500 | 27,750 |
| IIMROH-DMAI-2603 | 12,300 | 22,650 | 33,975 |
| IITP-AIMLPX-ADV-2608 | 10,750 | 15,650 | 23,475 |
| IIMM-DM-2602 | 9,700 | 12,950 | 19,425 |
| MITIDSS_ML_2603 | 9,650 | 14,950 | 22,425 |
| WE-DA-EN-2606 | 8,700 | 10,150 | 15,225 |
| WE-DA-TA-2606 | 4,650 | 5,300 | 7,950 |

The largest ceiling is **68,000 Miles** (IITREICT-DSAI-2603), or **102,000** if a student held the full 1.5x streak for
every week. The ceiling keeps rising as lectures and assignments are added. The best student today is at about 74% of
their batch's ceiling.

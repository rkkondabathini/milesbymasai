# Miles redemption: operations playbook

How a student claim travels from the dashboard to a delivered reward, who does what, and what can go wrong.
Items marked **DECISION** need an owner's call before launch. Numbers marked *proposed* are defaults I chose; change them freely.

---

## 1. Roles
| Role | Does | Typical owner |
|---|---|---|
| **Student** | Claims, accepts the rules, gives delivery or invoice details | Learner |
| **Rewards desk** | Works the Redemptions sheet daily, moves statuses, talks to students | Program ops / PC team |
| **Vendor coordinator** | Orders physical items, tracks shipping, manages stock | Ops / admin |
| **Mentor / session owner** | Delivers 1:1 sessions, mentor meetings | CC, TA, IM, alumni |
| **Placement team** | Confirms drives and company interviews, checks eligibility | Placement |
| **Finance** | Approves reimbursements, vendor invoices, tax treatment, monthly reconciliation | Finance |
| **Programme owner** | Owns rules, budget ceiling, exceptions, change notices | You |

## 2. The seven routes
Every reward belongs to one route (defined in `webapp/reward_rules.json`, shown to the student before they confirm).

| Route | Examples | Student provides | Target | Subject to | If it cannot be delivered |
|---|---|---|---|---|---|
| **Shipped** | T-shirt, hoodie, desk and audio gear, books | Full address, phone, **size for apparel** | 21 working days | Stock, vendor, India delivery only | Miles returned, or pick another |
| **Pay and reimburse** | AI tool, Canva, LinkedIn Premium, interview-prep platform | **Invoice** within 7 days | 10 working days after a valid invoice (17 overall) | Reimbursed up to the reward value; invoice in the student's name, dated after the claim | Lapses at 30 days, Miles returned |
| **Voucher** | Gift or food vouchers | Nothing | 5 working days | Issuer's terms and expiry | Miles returned |
| **Scheduled** | 1:1 with CC / TA / IM, mock interview, resume help, profile review, mentor coffee, founder call, hackathon mentor, LinkedIn recommendation | Availability | 15 working days to schedule | **Mentor or expert availability** | If not scheduled in 30 days, Miles returned |
| **Subject to the event** | Hackathon entry, **placement drive, interview with a company**, masterclass seat or topic, conference ticket | Nothing | Confirmed once the event is scheduled (up to 90 days) | **The event actually happening**, seats, and for placement items **placement eligibility** and employer availability. Not a job guarantee | If no event in 90 days, Miles returned or carried over (student's choice) |
| **Fee discount** | 50% off Campus Immersion | Enrolment confirmation | 10 working days | One-time, non-transferable, next Campus Immersion | Returned if not used in the validity window |
| **Recognition** | Wall of Fame, certificate | Consent to publish | 7 working days | Masai reviews the wording | Miles returned |

**DECISION: SLAs.** The target days above are *proposed*. Confirm them with the people who must meet them.

## 3. Claim lifecycle
```
Student claims ──► requested ──► awaiting_details ──► processing ──► scheduled ──► shipped ──► completed
                         │              │                  │             │           │
                         └──────────────┴──── rejected / cancelled / expired ───────┘   (Miles returned)
```
| Status | Meaning | Who moves it | Miles |
|---|---|---|---|
| requested | Claim received and validated by the system | automatic | held |
| awaiting_details | Needs something from the student (invoice, correct address) | rewards desk | held |
| processing | Being ordered, booked or verified | rewards desk | held |
| scheduled | Date or slot agreed (sessions, events, discount applied) | rewards desk | held |
| shipped | Dispatched; tracking in `reference` | vendor coordinator | held |
| completed | Student has received it / it happened | rewards desk | spent |
| rejected | Not eligible or not possible | rewards desk | **returned** |
| cancelled | Withdrawn by student or Masai | rewards desk | **returned** |
| expired | Passed its limit with no resolution | rewards desk (or automatic if enabled) | **returned** |

Miles are returned at the **next daily update** (the build reads the sheet each morning). Tell students that.

## 4. Step by step, from the student's click
1. Student opens the reward. They see: cost, balance after, **how it works**, **"subject to"**, and **what happens if it cannot be delivered**.
2. For shipped items the form requires name, phone, address line 1, city, state, a valid 6-digit PIN, and **size** for t-shirt and hoodie.
3. The student ticks **"I have read the notes and accept them"** and **the redemption confirmation**, and confirms a contact number.
4. The system checks, and rejects with a clear message if any fails: signature, reward exists, consent given, terms accepted, address valid, size valid, **already claimed** (non-repeatable), **balance sufficient** (counting Miles already held).
5. A row is written to the sheet: contact, reward, fulfilment type, **due date**, size, address, consent text and time. Status = `requested`.
6. Ops get an email / Slack alert. The student sees "Request sent", a request ID and the target date.
7. The rewards desk works the row (section 5). Each status change can email the student.
8. When the row reaches completed, Miles are spent for good. For rejected, cancelled or expired they return at the next daily update.

## 5. Daily routine for the rewards desk (about 20 minutes)
1. Open the **Redemptions** sheet. Filter status `requested`; read the daily digest email (new, waiting on student, overdue, past limit).
2. For each new row, by route:
   - **Shipped:** check the address looks deliverable; add to the vendor order batch; set `processing`. When dispatched set `shipped` and paste the tracking link in `reference`.
   - **Reimburse:** email the student the invoice instructions; set `awaiting_details`. When the invoice arrives, check it (below), send to Finance, set `processing`; when paid set `completed`.
   - **Scheduled:** message the mentor or owner; agree a slot with the student; set `scheduled` with the date in `reference`; after the session set `completed`.
   - **Event:** record it; set `processing`. When the event is confirmed tell the student the details and set `scheduled`; after attendance set `completed`.
   - **Fee discount:** confirm enrolment with the admissions team; apply to the invoice; set `completed`.
   - **Recognition:** confirm the wording with the student; publish; set `completed`.
   - **Voucher:** buy and email the code; set `completed`.
3. Anything red in **due_by** is overdue: chase the owner or tell the student the new date.
4. Close out: items stuck past their limit (digest section "Past the claim limit") are either resolved or set to `expired` (Miles returned) with a note in `resolution_notes`.

## 6. Checks the desk must apply
**Invoice (reimbursement)**
- In the student's name; dated after the claim date; the product matches the reward; shows the amount paid and the payment method.
- Reimburse the **lower** of the invoice amount and the reward's cost (the amount in the sheet); anything above is the student's.
- No duplicate invoice across students; keep the invoice file against the request ID.
- Send to Finance with the request ID. **DECISION:** how the student receives money (bank transfer to the registered account, or via payroll/stipend).

**Address (shipping)**
- Reject obviously unreachable addresses early (set `awaiting_details` and message the student). A wrong address after dispatch is the student's cost to reship once.

**Eligibility for placement-linked items** (hiring drive, interview with a company)
- **DECISION:** the eligibility rule (attendance, evaluation score, no pending dues?). Have the placement team confirm each claim before the Miles are spent.

**Possible abuse**
- Same address, phone or invoice across different learners; a learner who has left the programme; repeated claims of repeatable rewards in a short window. The desk escalates to the programme owner.

## 7. Student communication
Send by email (and WhatsApp where possible). Templates to fill in:
- **Received:** "We have your request for {reward} (ID {id}). Next: {steps}. Target date {date}."
- **Need details:** "To process {reward} we need {invoice / corrected address}. Please reply by {date}, otherwise the claim lapses and your Miles are returned."
- **Scheduled:** "{reward} is scheduled for {date/time}. Details: {link/venue}."
- **Shipped:** "{reward} is on the way. Tracking: {link}. Expected by {date}."
- **Completed:** "Your {reward} is done. Tell us how it went."
- **Not possible:** "We couldn't fulfil {reward} because {reason}. Your {miles} Miles will be back in your balance by {date}."

With `EMAIL_LEARNER=true` the sheet script sends the received / status emails for you.

## 8. Money and records
- **Budget ceiling:** at 10 Miles = ₹1 no reward costs Masai more than ₹0.10 per Mile. Track *completed* cost against the ceiling monthly.
- **Reconcile monthly:** (a) Miles redeemed in the sheet vs the dashboard, (b) vendor and reimbursement payouts vs rupee cost of completed rows, (c) refunded Miles.
- **Tax and GST:** **DECISION (Finance).** Confirm the treatment of goods, vouchers and reimbursements (GST on goods, whether vouchers or prizes attract TDS or other withholding, invoicing requirements). I have not assumed any.
- **Audit trail:** every row holds the consent text and timestamp, the status history is in the sheet's version history, invoices are filed by request ID.

## 9. Data protection
- Addresses, phones and invoices are personal data. Restrict the sheet to the rewards desk, Finance and the programme owner.
- Keep addresses only until delivery plus 90 days (*proposed*), then clear the columns. Do not export the sheet to personal drives.
- The dashboard and the playground never expose another student's data.

## 10. Exceptions
| Situation | Handling |
|---|---|
| Student claims then changes their mind | Allowed until the item is ordered or scheduled: set `cancelled` (Miles returned). |
| Item out of stock or discontinued | Offer an equal-value alternative, else `rejected` (Miles returned). |
| Parcel returned or damaged | Reship once at Masai's cost if our error; otherwise at the student's cost or `cancelled`. |
| Wrong size | One exchange if reported within 7 days of delivery (*proposed*). |
| Mentor unavailable or event cancelled | Reschedule; after the limit, Miles returned or carried over. |
| Student leaves the programme | **DECISION:** do unspent Miles lapse? Open claims are completed or refunded. |
| Miles balance changes after the claim (a data correction) | The claim stands; the next balance reflects it. Escalate if negative. |
| Dispute | Student raises a ticket; the programme owner decides within 5 working days. |
| Rules change (Miles rates, rewards, prices) | Announce before it takes effect (the FAQ promises this). Claims already made keep the rules in force at claim time. |

## 11. Reports
Weekly to the programme owner: claims by route and status; average and worst turnaround vs target; overdue list; cost completed vs ceiling; top rewards; refunds and reasons; student complaints.
The sheet's **Summary** tab gives counts and Miles by status, fulfilment type and reward.

## 12. Go-live checklist
**System**
- [ ] Update the sheet script from `webapp/redeem_webhook.gs`, set properties, run `setup()` (adds the new columns), **Deploy a new version**.
- [ ] Web app access is **Anyone** (not restricted to masaischool.com). Check the `/exec` URL in a private window shows `{"ok":true,...}`.
- [ ] Vercel variables set: `REDEEM_SECRET`, `MILES_REDEEM_ENDPOINT`, `MILES_REDEEMED_CSV`, optional `MILES_REWARDS_EMAIL`.
- [ ] **Dashboard catalogue matches the approved catalogue.** The live store currently shows the original 11 rewards at the original Miles prices; it must be updated to the approved catalogue and prices before launch.
- [ ] One end-to-end test per route (shipped with size, reimburse, scheduled, event, discount), then reject one and confirm the Miles return the next day.
**People and process**
- [ ] Owners named for each route; SLAs confirmed (section 2).
- [ ] Vendor(s) chosen, price list and lead times agreed, stock levels set for apparel and gear.
- [ ] Invoice mailbox created; reimbursement payment route agreed with Finance.
- [ ] Tax treatment confirmed by Finance.
- [ ] Placement eligibility rule agreed for hiring drive and company interview.
- [ ] Terms for students reviewed (the rules text in `reward_rules.json` and the FAQ).
- [ ] Rewards desk trained on the daily routine; escalation path agreed.
- [ ] Message templates loaded; the PC and ticket route briefed.
**Decisions still open (summary)**
1. SLA targets per route. 2. Miles expiry and what happens when a student leaves. 3. A cap on claims per student per month, if any. 4. Reimbursement payment method and cap above reward value. 5. Placement eligibility rule. 6. Tax and GST treatment. 7. Cost of the company interview and hiring drive (currently estimates). 8. Who owns each route.

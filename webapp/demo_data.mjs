// Synthetic learners for the leadership demo. Nothing here is real: names, numbers and batch are invented.
const iso = (d) => d.toISOString().slice(0, 10);
const addDays = (d, n) => new Date(d.getTime() + n * 864e5);

export const DEMO_LOGINS = [
  { name: "Aarav Mehta", label: "Active learner · 4-week streak · 6,000 Miles to spend", phone: "9000000001", email: "aarav.demo@example.com" },
  { name: "Meera Iyer", label: "New learner · 650 Miles", phone: "9000000002", email: "meera.demo@example.com" },
];

export function demoSource(base) {
  const today = new Date(); today.setUTCHours(0, 0, 0, 0);
  const asOf = addDays(today, -1);                       // data is "as of yesterday", like the live site
  const wd = (asOf.getUTCDay() + 6) % 7;                  // Monday = 0
  const monday = addDays(asOf, -wd), sunday = addDays(monday, 6);
  const daysLeft = Math.round((sunday - asOf) / 864e5);
  const wk = (n) => iso(addDays(monday, -7 * n));
  const peerNames = ["Rohan P.", "Sneha K.", "Aditya R.", "Kavya N.", "Imran S.", "Divya M.", "Karthik V.", "Neha J."];
  const board = (me, myM, scores, you) => {
    const rows = scores.map((m, i) => ({ n: peerNames[i], m })).concat([{ n: me, m: myM, you: true }]).sort((a, b) => b.m - a.m);
    return rows.map((x, i) => ({ r: i + 1, n: x.n, m: x.m, you: !!x.you }));
  };
  const glob = (rows, b) => rows.map((x) => ({ ...x, b }));

  const mk = (o) => {
    const dayMiles = o.days;                              // 21 values ending yesterday
    const days = dayMiles.map((m, i) => ({ d: iso(addDays(asOf, i - 20)), m }));
    const lbAll = board(o.short, o.earned, o.peers.all), lbWeek = board(o.short, o.weekBase, o.peers.week);
    const rank = (b, m) => b.find((x) => x.you).r;
    return {
      phone: o.phone, email: o.email,
      data: { name: o.name, batch: "DEMO-AIML-2601", data_as_of: iso(asOf), total_earned: o.earned, total_redeemed: o.redeemed, current_balance: o.earned - o.redeemed,
        lifetime_bonus: o.bonus, week_start: iso(monday), week_base_miles: o.weekBase, miles_to_100: Math.max(0, 400 - o.weekBase),
        current_streak_week: o.streakWeek, current_multiplier: o.mult, streak_status: o.streakStatus, streak_at_risk: 0,
        next_reward: o.nextReward, miles_to_next_reward: o.toNext, base_miles_yesterday: dayMiles[20] },
      days_left: daysLeft, pc: { name: "Demo Coordinator", phone: "9000000000" },
      pending: { miles: o.pendingMiles, lectures: 1, assignments: 2, items: [{ type: "mandatory", title: "Academic Session 14 - Model Evaluation (recording)", count: 1, miles: 100, date: iso(addDays(asOf, -3)) }] },
      daily_streak: o.dailyStreak, best_daily_streak: o.dailyStreak + 2, streak_today_open: false,
      days, weekly: o.weekly, totals: o.totals, history: o.history, redemptions: o.redemptions,
      peer: { batch_n: 240, met_now: 61, met_last_pct: 38, ahead_pct: o.ahead },
      leaderboard: { all: lbAll, week: lbWeek }, rank: { all: { r: rank(lbAll), of: 240, m: o.earned }, week: { r: rank(lbWeek), of: 240, m: o.weekBase } },
      leaderboard_global: { all: glob(lbAll, "DEMO"), week: glob(lbWeek, "DEMO") }, rank_global: { all: { r: rank(lbAll) + 31, m: o.earned }, week: { r: rank(lbWeek) + 44, m: o.weekBase } },
    };
  };

  const A = mk({
    phone: "9000000001", email: "aarav.demo@example.com", name: "Aarav Mehta", short: "Aarav M.", earned: 12000, redeemed: 6000, bonus: 1300,
    weekBase: 500, streakWeek: 4, mult: 1.4, streakStatus: "met", nextReward: "Hackathon entry", toNext: 2000, pendingMiles: 450, dailyStreak: 5, ahead: 82,
    days: [0, 0, 200, 150, 0, 100, 150, 0, 300, 200, 100, 0, 200, 200, 150, 0, 100, 200, 0, 150, 200],
    peers: { all: [12900, 11800, 11200, 10400, 9700, 9100, 8400, 7800], week: [820, 700, 640, 560, 420, 300, 240, 100] },
    weekly: [
      { week_start: wk(3), base_miles: 600, streak_met: 1, streak_week: 1, multiplier: 1.1, miles_earned: 660, bonus_miles: 60, provisional: 0 },
      { week_start: wk(2), base_miles: 950, streak_met: 1, streak_week: 2, multiplier: 1.2, miles_earned: 1140, bonus_miles: 190, provisional: 0 },
      { week_start: wk(1), base_miles: 1100, streak_met: 1, streak_week: 3, multiplier: 1.3, miles_earned: 1430, bonus_miles: 330, provisional: 0 },
      { week_start: wk(0), base_miles: 500, streak_met: 1, streak_week: 4, multiplier: 1.4, miles_earned: 700, bonus_miles: 200, provisional: 1 }],
    totals: { mandatory_live: { count: 22, miles: 4400 }, nonmandatory_live: { count: 12, miles: 1800 }, mandatory_recorded: { count: 6, miles: 600 }, practice_assignment: { count: 38, miles: 3800 }, graded_assignment: { count: 4, miles: 1200 } },
    history: [
      { type: "mandatory", mode: "live", title: "Academic Session 14 - Model Evaluation", count: 1, miles: 200, date: iso(asOf) },
      { type: "practice_assignment", mode: "", title: "Cross Validation - Objective, Cross Validation - Subjective", count: 2, miles: 200, date: iso(addDays(asOf, -1)) },
      { type: "nonmandatory", mode: "live", title: "Doubt Clearing Session", count: 1, miles: 150, date: iso(addDays(asOf, -2)) },
      { type: "graded_assignment", mode: "", title: "Assignment 6 - Regression Models", count: 1, miles: 300, date: iso(addDays(asOf, -4)) },
      { type: "mandatory", mode: "live", title: "Academic Session 13 - Feature Engineering", count: 1, miles: 200, date: iso(addDays(asOf, -6)) },
      { type: "practice_assignment", mode: "", title: "Feature Scaling - Objective, Feature Scaling - Subjective", count: 2, miles: 200, date: iso(addDays(asOf, -7)) }],
    redemptions: [{ reward_id: "R2", status: "completed", date: iso(addDays(asOf, -12)) }, { reward_id: "R1", status: "scheduled", date: iso(addDays(asOf, -3)) }],
  });
  const B = mk({
    phone: "9000000002", email: "meera.demo@example.com", name: "Meera Iyer", short: "Meera I.", earned: 650, redeemed: 0, bonus: 0,
    weekBase: 250, streakWeek: 0, mult: 1.0, streakStatus: "not_started", nextReward: "1:1 doubt session with your CC (30 min)", toNext: 350, pendingMiles: 700, dailyStreak: 1, ahead: 35,
    days: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 200, 100, 0, 0, 150, 0, 200],
    peers: { all: [1500, 1300, 1100, 900, 800, 700, 600, 500], week: [820, 700, 640, 560, 420, 300, 240, 100] },
    weekly: [{ week_start: wk(1), base_miles: 300, streak_met: 0, streak_week: 0, multiplier: 1.0, miles_earned: 300, bonus_miles: 0, provisional: 0 },
             { week_start: wk(0), base_miles: 250, streak_met: 0, streak_week: 0, multiplier: 1.0, miles_earned: 250, bonus_miles: 0, provisional: 1 }],
    totals: { mandatory_live: { count: 2, miles: 400 }, practice_assignment: { count: 2, miles: 200 }, nonmandatory_live: { count: 0, miles: 0 }, mandatory_recorded: { count: 0, miles: 0 }, graded_assignment: { count: 0, miles: 0 } },
    history: [{ type: "mandatory", mode: "live", title: "Academic Session 3 - Python Basics", count: 1, miles: 200, date: iso(asOf) },
              { type: "practice_assignment", mode: "", title: "Lists and Loops - Objective, Lists and Loops - Subjective", count: 2, miles: 200, date: iso(addDays(asOf, -3)) }],
    redemptions: [],
  });
  return { as_of: iso(asOf), rewards: base.rewards, rates: base.rates, threshold: base.threshold, multipliers: base.multipliers,
           students: { "demo-aarav": A, "demo-meera": B } };
}

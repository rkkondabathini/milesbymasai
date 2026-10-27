// node webapp/build.mjs  ->  webapp/dist/index.html (single file; data is encrypted per student)
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { randomBytes, createHmac } from "node:crypto";
import { existsSync } from "node:fs";

const here = dirname(fileURLToPath(import.meta.url));
const DEMO = !!(process.env.MILES_DEMO || "").trim();   // leadership demo: invented learners only, no real data, no redemption writes
let src;
if (DEMO) {
  const { demoSource } = await import("./demo_data.mjs");
  const cfg = JSON.parse(readFileSync(join(here, "../config.json"), "utf8"));
  src = demoSource({ rewards: cfg.rewards, rates: cfg.rates, threshold: cfg.weekly_threshold, multipliers: cfg.streak_multipliers });
} else src = JSON.parse(readFileSync(join(here, "../data/output/student_payloads.json"), "utf8"));
const MilesAuth = new Function(readFileSync(join(here, "auth.js"), "utf8") + "; return MilesAuth;")();

const ITER = 150000;
// redemption signing secret: env REDEEM_SECRET, else a local file created on first build.
// The same secret goes into the Apps Script (Script Properties -> REDEEM_SECRET).
const secretFile = join(here, ".redeem_secret");
let REDEEM_SECRET = (process.env.REDEEM_SECRET || "").trim() || (existsSync(secretFile) ? readFileSync(secretFile, "utf8").trim() : "");
if (!REDEEM_SECRET && process.env.MILES_REDEEM_ENDPOINT && !DEMO) {
  console.error("MILES_REDEEM_ENDPOINT is set but REDEEM_SECRET is not: tokens would be signed with a throw-away key.");
  process.exit(1);
}
if (!REDEEM_SECRET) { REDEEM_SECRET = randomBytes(32).toString("hex"); if (!DEMO) { writeFileSync(secretFile, REDEEM_SECRET + "\n"); console.log("created webapp/.redeem_secret"); } }
const sign = (rid, asOf, balance) => createHmac("sha256", REDEEM_SECRET).update(`${rid}|${asOf}|${balance}`).digest("hex");
const REDEEM_ENDPOINT = DEMO ? "" : (process.env.MILES_REDEEM_ENDPOINT || "").trim();
const REDEEM_FORM_URL = process.env.MILES_REDEEM_FORM_URL || "";
const SUPPORT_EMAIL = (process.env.MILES_REWARDS_EMAIL || "").trim();
const salt = MilesAuth.b64(randomBytes(16));
const students = {};
const skipped = [];
let done = 0;
for (const [lid, s] of Object.entries(src.students)) {
  if (MilesAuth.normPhone(s.phone).length < 10 || !s.email) { skipped.push(lid); continue; }
  const { id, key } = await MilesAuth.derive(s.phone, s.email, salt, ITER);
  const { phone, email, ...payload } = s;
  payload.rid = lid;
  payload.contact = { phone, email };
  payload.tok = sign(lid, payload.data.data_as_of, payload.data.current_balance);
  students[id] = await MilesAuth.encrypt(key, payload);
  if (++done % 100 === 0) console.log(`  encrypted ${done}`);
}
const faq = JSON.parse(readFileSync(join(here, "faq.json"), "utf8"));
const rules = JSON.parse(readFileSync(join(here, "reward_rules.json"), "utf8"));
const classify = (name) => { for (const r of rules.rules) if (new RegExp(r.match, "i").test(name)) {
  const t = rules.types[r.type]; return { type: r.type, sla: t.sla_days, size: !!(r.size && new RegExp(r.size, "i").test(name)), placement: !!(r.placement && new RegExp(r.placement, "i").test(name)) }; } };
// public support contacts (batch PCs) shown on the login page; only rows that have a phone number
const support = [];
if (!DEMO) try {
  const [head, ...rows] = readFileSync(join(here, "../data/input/batch_pc.csv"), "utf8").trim().split("\n");
  const cols = head.split(",");
  for (const r of rows) {
    const o = Object.fromEntries(r.split(",").map((v, i) => [cols[i], (v || "").trim()]));
    if (o.pc_phone) support.push({ batch: o.batch_name, name: o.pc_name, phone: o.pc_phone });
  }
} catch {}
const blob = { salt, iter: ITER, built_at: new Date().toISOString(), as_of: src.as_of, rewards: src.rewards, rates: src.rates,
               threshold: src.threshold, multipliers: src.multipliers, faq, rules, support, support_email: SUPPORT_EMAIL, students,
               ...(DEMO ? { demo: true, demo_logins: (await import("./demo_data.mjs")).DEMO_LOGINS } : {}) };
const tpl = readFileSync(join(here, "app.template.html"), "utf8")
  .replace("__REDEEM_ENDPOINT__", REDEEM_ENDPOINT).replace("__REDEEM_FORM_URL__", REDEEM_FORM_URL);

// Apps Script that receives redemption requests into a Google Sheet (catalog is embedded so costs can't be forged)
const catalog = Object.fromEntries(src.rewards.map((r) => { const c = classify(r.name); return [r.reward_id, { cost: r.cost, name: r.name, type: c.type, sla: c.sla, size: c.size, placement: c.placement, rep: !!r.repeatable }]; }));
const gs = readFileSync(join(here, "redeem_webhook.template.gs"), "utf8").replace("__CATALOG__", JSON.stringify(catalog)).replace("__RULES__", JSON.stringify(Object.fromEntries(Object.entries(rules.types).map(([k, v]) => [k, { how: v.how, subject_to: v.subject_to, if_not_delivered: v.if_not_delivered }]))));
if (!DEMO) writeFileSync(join(here, "redeem_webhook.gs"), gs);
const html = tpl.replace("/*__AUTH__*/", () => readFileSync(join(here, "auth.js"), "utf8"))
                .replace("__BLOB__", () => JSON.stringify(blob).replace(/</g, "\\u003c"));
const OUT = DEMO ? "dist-demo" : "dist";
mkdirSync(join(here, OUT), { recursive: true });
writeFileSync(join(here, OUT, "index.html"), html);
try { writeFileSync(join(here, OUT, "vercel.json"), readFileSync(join(here, "vercel.json"))); } catch {}
console.log(`built ${OUT}/index.html${DEMO ? " (DEMO)" : ""}: ${done} students, ${skipped.length} skipped (no phone/email), ${(html.length / 1e6).toFixed(2)} MB`);
if (skipped.length) console.log("skipped:", skipped.join(", "));

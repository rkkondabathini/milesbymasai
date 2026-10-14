// node webapp/build.mjs  ->  webapp/dist/index.html (single file; data is encrypted per student)
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { randomBytes, createHmac } from "node:crypto";
import { existsSync } from "node:fs";

const here = dirname(fileURLToPath(import.meta.url));
const src = JSON.parse(readFileSync(join(here, "../data/output/student_payloads.json"), "utf8"));
const MilesAuth = new Function(readFileSync(join(here, "auth.js"), "utf8") + "; return MilesAuth;")();

const ITER = 150000;
// redemption signing secret: env REDEEM_SECRET, else a local file created on first build.
// The same secret goes into the Apps Script (Script Properties -> REDEEM_SECRET).
const secretFile = join(here, ".redeem_secret");
let REDEEM_SECRET = (process.env.REDEEM_SECRET || "").trim() || (existsSync(secretFile) ? readFileSync(secretFile, "utf8").trim() : "");
if (!REDEEM_SECRET && process.env.MILES_REDEEM_ENDPOINT) {
  console.error("MILES_REDEEM_ENDPOINT is set but REDEEM_SECRET is not: tokens would be signed with a throw-away key.");
  process.exit(1);
}
if (!REDEEM_SECRET) { REDEEM_SECRET = randomBytes(32).toString("hex"); writeFileSync(secretFile, REDEEM_SECRET + "\n"); console.log("created webapp/.redeem_secret"); }
const sign = (rid, asOf, balance) => createHmac("sha256", REDEEM_SECRET).update(`${rid}|${asOf}|${balance}`).digest("hex");
const REDEEM_ENDPOINT = (process.env.MILES_REDEEM_ENDPOINT || "").trim();
const REDEEM_FORM_URL = process.env.MILES_REDEEM_FORM_URL || "";
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
// public support contacts (batch PCs) shown on the login page; only rows that have a phone number
const support = [];
try {
  const [head, ...rows] = readFileSync(join(here, "../data/input/batch_pc.csv"), "utf8").trim().split("\n");
  const cols = head.split(",");
  for (const r of rows) {
    const o = Object.fromEntries(r.split(",").map((v, i) => [cols[i], (v || "").trim()]));
    if (o.pc_phone) support.push({ batch: o.batch_name, name: o.pc_name, phone: o.pc_phone });
  }
} catch {}
const blob = { salt, iter: ITER, built_at: new Date().toISOString(), as_of: src.as_of, rewards: src.rewards, rates: src.rates,
               threshold: src.threshold, multipliers: src.multipliers, faq, support, students };
const tpl = readFileSync(join(here, "app.template.html"), "utf8")
  .replace("__REDEEM_ENDPOINT__", REDEEM_ENDPOINT).replace("__REDEEM_FORM_URL__", REDEEM_FORM_URL);

// Apps Script that receives redemption requests into a Google Sheet (catalog is embedded so costs can't be forged)
const catalog = Object.fromEntries(src.rewards.map((r) => [r.reward_id, r.cost]));
const gs = readFileSync(join(here, "redeem_webhook.template.gs"), "utf8").replace("__CATALOG__", JSON.stringify(catalog));
writeFileSync(join(here, "redeem_webhook.gs"), gs);
const html = tpl.replace("/*__AUTH__*/", () => readFileSync(join(here, "auth.js"), "utf8"))
                .replace("__BLOB__", () => JSON.stringify(blob).replace(/</g, "\\u003c"));
mkdirSync(join(here, "dist"), { recursive: true });
writeFileSync(join(here, "dist/index.html"), html);
try { writeFileSync(join(here, "dist/vercel.json"), readFileSync(join(here, "vercel.json"))); } catch {}
console.log(`built dist/index.html: ${done} students, ${skipped.length} skipped (no phone/email), ${(html.length / 1e6).toFixed(2)} MB`);
if (skipped.length) console.log("skipped:", skipped.join(", "));

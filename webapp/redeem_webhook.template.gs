/**
 * Miles by Masai: redemption inbox (Google Apps Script bound to a Google Sheet).
 *
 * WHAT THIS GIVES THE TEAM
 *  - Every learner redemption lands as a row in the "Redemptions" tab (the work queue).
 *  - New rows are highlighted; status has a dropdown (requested / scheduled / completed / rejected).
 *  - A "Summary" tab shows counts and Miles by status and by reward.
 *  - Optional: email and/or Slack message per new request, a 9 AM digest of open requests,
 *    and an email to the learner when their status changes.
 *
 * SETUP (once)
 *  1. Create a Google Sheet "Miles redemptions" -> Extensions -> Apps Script, paste this file.
 *  2. Project Settings -> Script properties:
 *       REDEEM_SECRET     (required) contents of webapp/.redeem_secret
 *       NOTIFY_EMAIL      (optional) comma-separated ops emails for each new request + daily digest
 *       SLACK_WEBHOOK_URL (optional) Slack incoming-webhook URL
 *       EMAIL_LEARNER     (optional) "true" to email the learner on request + status change
 *  3. Run setup() once from the editor (authorise when asked). It formats the sheet and installs the triggers.
 *  4. Deploy -> New deployment -> Web app -> Execute as: Me, Who has access: Anyone. Copy the /exec URL.
 *  5. File -> Share -> Publish to web -> "Redemptions" tab as CSV (this feeds the nightly balance update).
 */
const CATALOG = __CATALOG__;
const SHEET_NAME = 'Redemptions';
const HEADER = ['timestamp', 'request_id', 'learner_id', 'name', 'email', 'phone', 'batch', 'reward_id',
                'reward_name', 'miles_cost', 'balance_at_request', 'status', 'data_as_of', 'handled_by', 'notes'];
const COL = { reqId: 1, learner: 2, name: 3, email: 4, phone: 5, batch: 6, reward: 7, rewardName: 8, cost: 9, status: 11, asOf: 12 };
const STATUSES = ['requested', 'scheduled', 'completed', 'rejected'];

function props_() { return PropertiesService.getScriptProperties(); }
function hex_(bytes) { return bytes.map(function (b) { return ('0' + (b & 0xff).toString(16)).slice(-2); }).join(''); }
function sign_(msg) { return hex_(Utilities.computeHmacSha256Signature(msg, props_().getProperty('REDEEM_SECRET'))); }
function out_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }
function sheet_() {
  const ss = SpreadsheetApp.getActive();
  return ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
}

/* ---------- learner requests ---------- */
function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const b = JSON.parse(e.postData.contents);
    // the token is an HMAC over learner|data_as_of|balance made at build time: none of these can be forged
    if (!b.tok || sign_([b.rid, b.as_of, b.balance].join('|')) !== b.tok) return out_({ ok: false, error: 'unauthorized' });
    const cost = CATALOG[b.reward_id];
    if (!cost) return out_({ ok: false, error: 'unknown_reward' });

    const sh = sheet_();
    if (sh.getLastRow() === 0) { sh.appendRow(HEADER); }
    const rows = sh.getDataRange().getValues().slice(1);

    let used = 0;
    for (var i = 0; i < rows.length; i++) {
      const r = rows[i];
      if (r[COL.reqId] === b.request_id) return out_({ ok: true, request_id: b.request_id, duplicate: true });
      if (r[COL.learner] === b.rid && String(r[COL.asOf]) === String(b.as_of) && r[COL.status] !== 'rejected') used += Number(r[COL.cost]);
    }
    if (used + cost > Number(b.balance)) return out_({ ok: false, error: 'insufficient_balance' });

    sh.appendRow([new Date(), b.request_id, b.rid, b.name || '', b.email || '', b.phone || '', b.batch || '',
                  b.reward_id, b.reward_name || '', cost, Number(b.balance), 'requested', b.as_of, '', '']);
    notifyNew_(b, cost);
    return out_({ ok: true, request_id: b.request_id });
  } catch (err) {
    return out_({ ok: false, error: 'bad_request' });
  } finally {
    lock.releaseLock();
  }
}
function doGet() { return out_({ ok: true, service: 'miles-redemptions' }); }

/* ---------- notifications ---------- */
function notifyNew_(b, cost) {
  const p = props_();
  const line = (b.name || b.rid) + ' · ' + (b.batch || '') + ' · ' + (b.reward_name || b.reward_id) + ' (' + cost + ' Miles)';
  const to = p.getProperty('NOTIFY_EMAIL');
  if (to) {
    MailApp.sendEmail(to, 'New Miles redemption: ' + (b.reward_name || b.reward_id),
      [line, '', 'Email: ' + (b.email || '-'), 'Phone: ' + (b.phone || '-'), 'Balance at request: ' + b.balance,
       '', 'Open the sheet to schedule it: ' + SpreadsheetApp.getActive().getUrl()].join('\n'));
  }
  const hook = p.getProperty('SLACK_WEBHOOK_URL');
  if (hook) {
    UrlFetchApp.fetch(hook, { method: 'post', contentType: 'application/json', muteHttpExceptions: true,
      payload: JSON.stringify({ text: ':gift: *New Miles redemption*\n' + line + '\n' + (b.email || '') + ' · ' + (b.phone || '') }) });
  }
  if (p.getProperty('EMAIL_LEARNER') === 'true' && b.email) {
    MailApp.sendEmail(b.email, 'We received your Miles redemption',
      'Hi ' + (b.name || '') + ',\n\nWe received your request for "' + (b.reward_name || b.reward_id) + '" (' + cost +
      ' Miles). The team will reach out to schedule or activate it.\n\nMiles by Masai');
  }
}

/** Installable edit trigger: when the team changes a status, optionally tell the learner. */
function onStatusEdit(e) {
  try {
    const sh = e.range.getSheet();
    if (sh.getName() !== SHEET_NAME || e.range.getColumn() !== COL.status + 1 || e.range.getRow() < 2) return;
    if (props_().getProperty('EMAIL_LEARNER') !== 'true') return;
    const row = sh.getRange(e.range.getRow(), 1, 1, HEADER.length).getValues()[0];
    const status = String(row[COL.status]).toLowerCase();
    const msg = { scheduled: 'has been scheduled. The team will share the details with you.',
                  completed: 'is complete. Enjoy!',
                  rejected: 'could not be fulfilled. Your Miles are returned to your balance.' }[status];
    if (msg && row[COL.email]) {
      MailApp.sendEmail(row[COL.email], 'Your Miles redemption: ' + status,
        'Hi ' + row[COL.name] + ',\n\nYour request for "' + row[8] + '" ' + msg + '\n\nMiles by Masai');
    }
  } catch (err) {}
}

/** Time-driven (~9 AM): one email listing everything still waiting. */
function dailyDigest() {
  const to = props_().getProperty('NOTIFY_EMAIL');
  if (!to) return;
  const rows = sheet_().getDataRange().getValues().slice(1).filter(function (r) { return r[COL.status] === 'requested'; });
  if (!rows.length) return;
  MailApp.sendEmail(to, 'Miles redemptions waiting: ' + rows.length,
    rows.map(function (r) { return '- ' + r[COL.name] + ' (' + r[COL.batch] + '): ' + r[8] + ' · ' + r[COL.cost] + ' Miles · ' + r[COL.phone]; })
      .join('\n') + '\n\n' + SpreadsheetApp.getActive().getUrl());
}

/* ---------- one-time setup ---------- */
function setup() {
  const ss = SpreadsheetApp.getActive();
  const sh = sheet_();
  if (sh.getLastRow() === 0) sh.appendRow(HEADER);
  sh.setFrozenRows(1);
  sh.getRange(1, 1, 1, HEADER.length).setFontWeight('bold').setBackground('#b01c2e').setFontColor('#ffffff');
  sh.getRange('A:A').setNumberFormat('dd mmm yyyy hh:mm');

  // status dropdown + colour coding
  const statusRange = sh.getRange(2, COL.status + 1, 2000, 1);
  statusRange.setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(STATUSES, true).setAllowInvalid(false).build());
  const colour = { requested: '#fde7b4', scheduled: '#dbe9ff', completed: '#d8f0df', rejected: '#e4e6eb' };
  sh.setConditionalFormatRules(STATUSES.map(function (s) {
    return SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo(s).setBackground(colour[s]).setRanges([statusRange]).build();
  }));
  sh.autoResizeColumns(1, HEADER.length);

  // summary tab: counts by status and Miles by reward
  const sum = ss.getSheetByName('Summary') || ss.insertSheet('Summary');
  sum.clear();
  sum.getRange('A1:C1').setValues([['Status', 'Requests', 'Miles']]).setFontWeight('bold');
  STATUSES.forEach(function (s, i) {
    sum.getRange(2 + i, 1, 1, 3).setFormulas([[s,
      '=COUNTIF(Redemptions!L:L,"' + s + '")', '=SUMIF(Redemptions!L:L,"' + s + '",Redemptions!J:J)']]);
  });
  sum.getRange('A8').setValue('Open (requested + scheduled)').setFontWeight('bold');
  sum.getRange('B8').setFormula('=B2+B3'); sum.getRange('C8').setFormula('=C2+C3');
  sum.getRange('A11').setValue('By reward (excluding rejected)').setFontWeight('bold');
  sum.getRange('A12').setFormula('=QUERY(Redemptions!I:L,"select I, count(I), sum(J) where L <> \'rejected\' and I is not null group by I label count(I) \'Requests\', sum(J) \'Miles\'",1)');

  // triggers (idempotent)
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('onStatusEdit').forSpreadsheet(ss).onEdit().create();
  ScriptApp.newTrigger('dailyDigest').timeBased().everyDays(1).atHour(9).create();
}

/**
 * Miles by Masai: redemption inbox (Google Apps Script bound to a Google Sheet).
 *
 * WHAT THIS GIVES THE TEAM
 *  - Every redemption lands as a row in the "Redemptions" tab (the work queue), with how it must be fulfilled
 *    (fulfilment_type), a due date, and, for shipped items, the delivery address and size.
 *  - Status dropdown: requested > awaiting_details > processing > scheduled > shipped > completed,
 *    or rejected / cancelled / expired (these three refund the Miles at the next daily update).
 *  - Overdue and stale claims are highlighted and listed in a daily digest. Optional auto-expiry.
 *  - A "Summary" tab shows counts and Miles by status and by reward.
 *
 * SETUP (once, and again after every script update)
 *  1. Sheet -> Extensions -> Apps Script, paste this file, save.
 *  2. Project Settings -> Script properties:
 *       REDEEM_SECRET     (required) contents of webapp/.redeem_secret
 *       NOTIFY_EMAIL      (optional) comma-separated ops emails: new request alerts and the daily digest
 *       SLACK_WEBHOOK_URL (optional) Slack incoming webhook
 *       EMAIL_LEARNER     (optional) "true" to email the learner on request and on status changes
 *       AUTO_EXPIRE       (optional) "true" to auto-expire claims that pass their limit (see LIMIT_DAYS)
 *  3. Run setup() from the editor (authorise). It adds any missing columns, formats the sheet and installs triggers.
 *  4. Deploy -> Manage deployments -> pencil -> New version. Access: Anyone. Copy the /exec URL.
 *  5. File -> Share -> Publish to web -> "Redemptions" tab as CSV (feeds the daily balance update).
 */
const CATALOG = __CATALOG__;
const RULES = __RULES__;
const SHEET_NAME = 'Redemptions';
const HEADER = ['timestamp', 'request_id', 'learner_id', 'name', 'email', 'phone', 'batch', 'reward_id',
                'reward_name', 'miles_cost', 'balance_at_request', 'status', 'data_as_of', 'handled_by', 'notes',
                'confirmed_at', 'confirmation', 'contact_phone',
                'fulfilment_type', 'due_by', 'size', 'ship_name', 'ship_phone', 'address', 'pincode',
                'reference', 'resolution_notes', 'closed_at'];
const C = {}; HEADER.forEach(function (h, i) { C[h] = i; });
const STATUSES = ['requested', 'awaiting_details', 'processing', 'scheduled', 'shipped', 'completed', 'rejected', 'cancelled', 'expired'];
const REFUNDED = ['rejected', 'cancelled', 'expired'];
const CLOSED = ['completed'].concat(REFUNDED);
const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL'];
// days after which an unfulfilled claim is flagged (and expired if AUTO_EXPIRE is on)
const LIMIT_DAYS = { physical: 45, reimburse: 30, voucher: 15, session: 30, event: 90, discount: 60, recognition: 30 };

function props_() { return PropertiesService.getScriptProperties(); }
function hex_(bytes) { return bytes.map(function (b) { return ('0' + (b & 0xff).toString(16)).slice(-2); }).join(''); }
function sign_(msg) { return hex_(Utilities.computeHmacSha256Signature(msg, props_().getProperty('REDEEM_SECRET'))); }
function out_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }
function sheet_() { const ss = SpreadsheetApp.getActive(); return ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME); }
function str_(v, n) { return String(v == null ? '' : v).replace(/[\r\n]+/g, ' ').trim().slice(0, n || 200); }
function col_(i) { var s = '', n = i + 1; while (n > 0) { var m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); } return s; }
function addWorkingDays_(d, n) { const x = new Date(d.getTime()); while (n > 0) { x.setDate(x.getDate() + 1); if (x.getDay() !== 0 && x.getDay() !== 6) n--; } return x; }

/** Adds any columns this version needs to the right of the existing ones (safe on a live sheet). */
function ensureHeader_(sh) {
  if (sh.getLastRow() === 0) { sh.appendRow(HEADER); return; }
  const cur = sh.getRange(1, 1, 1, Math.max(sh.getLastColumn(), 1)).getValues()[0].map(String);
  HEADER.forEach(function (h) { if (cur.indexOf(h) === -1) { sh.getRange(1, cur.length + 1).setValue(h); cur.push(h); } });
  // the code addresses columns by the order in HEADER; refuse to run if an existing sheet has them in a different order
  for (var i = 0; i < HEADER.length; i++) if (cur[i] !== HEADER[i]) throw new Error('Column ' + (i + 1) + ' is "' + cur[i] + '", expected "' + HEADER[i] + '". Fix the header order.');
}

/* ---------- learner requests ---------- */
function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const b = JSON.parse(e.postData.contents);
    // the token is an HMAC over learner|data_as_of|balance made at build time: none of these can be forged
    if (!b.tok || sign_([b.rid, b.as_of, b.balance].join('|')) !== b.tok) return out_({ ok: false, error: 'unauthorized' });
    const item = CATALOG[b.reward_id];
    if (!item) return out_({ ok: false, error: 'unknown_reward' });
    const cost = item.cost;
    // the learner must have ticked the confirmation box; the exact wording is stored with the request
    if (b.confirmed !== true || !b.confirmation_text) return out_({ ok: false, error: 'not_confirmed' });
    if (b.terms_ack !== true) return out_({ ok: false, error: 'terms_not_accepted' });

    // type-specific details
    const ship = b.ship || {};
    var addr = '', pin = '', size = '';
    if (item.type === 'physical') {
      pin = str_(ship.pincode, 10);
      if (!str_(ship.name) || !/^\+?[0-9 ]{10,14}$/.test(str_(ship.phone, 20)) || str_(ship.line1).length < 5 || !str_(ship.city) || !str_(ship.state) || !/^[1-9][0-9]{5}$/.test(pin))
        return out_({ ok: false, error: 'address_incomplete' });
      addr = [str_(ship.line1, 150), str_(ship.line2, 150), str_(ship.city, 60), str_(ship.state, 60), pin].filter(String).join(', ');
      if (item.size) { size = str_(b.size, 4).toUpperCase(); if (SIZES.indexOf(size) === -1) return out_({ ok: false, error: 'size_required' }); }
    }

    const sh = sheet_();
    ensureHeader_(sh);
    const rows = sh.getDataRange().getValues().slice(1);
    let used = 0;
    for (var i = 0; i < rows.length; i++) {
      const r = rows[i];
      if (r[C.request_id] === b.request_id) return out_({ ok: true, request_id: b.request_id, duplicate: true });
      if (r[C.learner_id] !== b.rid || REFUNDED.indexOf(r[C.status]) !== -1) continue;
      if (String(r[C.data_as_of]) === String(b.as_of)) used += Number(r[C.miles_cost]);
      if (!item.rep && r[C.reward_id] === b.reward_id) return out_({ ok: false, error: 'already_claimed' });
    }
    if (used + cost > Number(b.balance)) return out_({ ok: false, error: 'insufficient_balance' });

    const now = new Date();
    const due = addWorkingDays_(now, item.sla || 15);
    const row = new Array(HEADER.length).fill('');
    const set = function (k, v) { row[C[k]] = v; };
    set('timestamp', now); set('request_id', b.request_id); set('learner_id', b.rid); set('name', str_(b.name)); set('email', str_(b.email));
    set('phone', str_(b.phone)); set('batch', str_(b.batch)); set('reward_id', b.reward_id); set('reward_name', item.name); set('miles_cost', cost);
    set('balance_at_request', Number(b.balance)); set('status', 'requested'); set('data_as_of', b.as_of);
    set('confirmed_at', now); set('confirmation', str_(b.confirmation_text, 500)); set('contact_phone', str_(b.contact_phone || b.phone, 20));
    set('fulfilment_type', item.type); set('due_by', due); set('size', size); set('ship_name', str_(ship.name)); set('ship_phone', str_(ship.phone, 20));
    set('address', addr); set('pincode', pin);
    sh.appendRow(row);
    notifyNew_(b, item, due);
    return out_({ ok: true, request_id: b.request_id, due_by: Utilities.formatDate(due, Session.getScriptTimeZone(), 'yyyy-MM-dd') });
  } catch (err) {
    return out_({ ok: false, error: 'bad_request' });
  } finally {
    lock.releaseLock();
  }
}
function doGet() { return out_({ ok: true, service: 'miles-redemptions', version: 2 }); }

/* ---------- notifications ---------- */
function stepsText_(type) {
  const t = RULES[type]; if (!t) return '';
  return t.how.map(function (s, i) { return (i + 1) + '. ' + s; }).join('\n') + '\n\n' + t.subject_to + '\n' + t.if_not_delivered;
}
function notifyNew_(b, item, due) {
  const p = props_();
  const line = (b.name || b.rid) + ' · ' + (b.batch || '') + ' · ' + item.name + ' (' + item.cost + ' Miles) · ' + item.type;
  const to = p.getProperty('NOTIFY_EMAIL');
  const url = SpreadsheetApp.getActive().getUrl();
  if (to) {
    MailApp.sendEmail(to, 'New Miles redemption: ' + item.name,
      [line, '', 'Email: ' + (b.email || '-'), 'Phone: ' + (b.contact_phone || b.phone || '-'), 'Due by: ' + Utilities.formatDate(due, Session.getScriptTimeZone(), 'dd MMM yyyy'),
       '', 'Open the sheet: ' + url].join('\n'));
  }
  const hook = p.getProperty('SLACK_WEBHOOK_URL');
  if (hook) {
    UrlFetchApp.fetch(hook, { method: 'post', contentType: 'application/json', muteHttpExceptions: true,
      payload: JSON.stringify({ text: ':gift: *New Miles redemption*\n' + line + '\nDue ' + Utilities.formatDate(due, Session.getScriptTimeZone(), 'dd MMM') }) });
  }
  if (p.getProperty('EMAIL_LEARNER') === 'true' && b.email) {
    MailApp.sendEmail(b.email, 'We received your Miles redemption: ' + item.name,
      'Hi ' + (b.name || '') + ',\n\nWe received your request for "' + item.name + '" (' + item.cost + ' Miles). Your request ID is ' + b.request_id + '.\n\nWhat happens next\n' +
      stepsText_(item.type) + '\n\nMiles by Masai');
  }
}

/** Installable edit trigger: tells the learner what changed, and stamps closed_at. */
function onStatusEdit(e) {
  try {
    const sh = e.range.getSheet();
    if (sh.getName() !== SHEET_NAME || e.range.getColumn() !== C.status + 1 || e.range.getRow() < 2) return;
    const rowNo = e.range.getRow();
    const row = sh.getRange(rowNo, 1, 1, HEADER.length).getValues()[0];
    const status = String(row[C.status]).toLowerCase();
    if (CLOSED.indexOf(status) !== -1 && !row[C.closed_at]) sh.getRange(rowNo, C.closed_at + 1).setValue(new Date());
    if (props_().getProperty('EMAIL_LEARNER') !== 'true' || !row[C.email]) return;
    const ref = row[C.reference] ? '\nReference: ' + row[C.reference] : '';
    const msg = {
      awaiting_details: 'needs one more thing from you. Please reply to this email with the missing details or invoice.' + ref,
      processing: 'is being processed.',
      scheduled: 'has been scheduled. The team will share the details with you.' + ref,
      shipped: 'has been shipped.' + ref,
      completed: 'is complete. Enjoy!',
      rejected: 'could not be fulfilled. Your Miles are returned to your balance at the next daily update.',
      cancelled: 'was cancelled. Your Miles are returned to your balance at the next daily update.',
      expired: 'has expired. Your Miles are returned to your balance at the next daily update.'
    }[status];
    if (msg) MailApp.sendEmail(row[C.email], 'Your Miles redemption: ' + String(status).replace('_', ' '),
      'Hi ' + row[C.name] + ',\n\nYour request for "' + row[C.reward_name] + '" ' + msg + '\n\nMiles by Masai');
  } catch (err) {}
}

/** Time-driven (~9 AM): what needs attention today. Optionally expires claims past their limit. */
function dailyDigest() {
  const sh = sheet_(); if (sh.getLastRow() < 2) return;
  const rows = sh.getDataRange().getValues().slice(1);
  const now = new Date(), day = 86400000, auto = props_().getProperty('AUTO_EXPIRE') === 'true';
  const fresh = [], details = [], overdue = [], stale = [];
  rows.forEach(function (r, i) {
    const st = String(r[C.status]); if (CLOSED.indexOf(st) !== -1) return;
    const age = (now - new Date(r[C.timestamp])) / day, type = r[C.fulfilment_type];
    const label = r[C.name] + ' (' + r[C.batch] + '): ' + r[C.reward_name] + ' · ' + r[C.miles_cost] + ' Miles';
    if (st === 'requested') fresh.push(label);
    if (st === 'awaiting_details') details.push(label + ' · waiting ' + Math.floor(age) + ' days');
    if (r[C.due_by] && new Date(r[C.due_by]) < now) overdue.push(label + ' · due ' + Utilities.formatDate(new Date(r[C.due_by]), Session.getScriptTimeZone(), 'dd MMM'));
    const lim = LIMIT_DAYS[type];
    if (lim && age > lim) {
      stale.push(label + ' · ' + Math.floor(age) + ' days old');
      if (auto && ['requested', 'awaiting_details', 'processing'].indexOf(st) !== -1) {
        sh.getRange(i + 2, C.status + 1).setValue('expired');
        sh.getRange(i + 2, C.resolution_notes + 1).setValue('auto-expired after ' + lim + ' days');
        sh.getRange(i + 2, C.closed_at + 1).setValue(now);
      }
    }
  });
  const to = props_().getProperty('NOTIFY_EMAIL');
  const blocks = [['New, not yet picked up', fresh], ['Waiting on the student', details], ['Overdue', overdue], ['Past the claim limit' + (auto ? ' (auto-expired where unscheduled)' : ' (refund or resolve)'), stale]]
    .filter(function (b) { return b[1].length; });
  if (!to || !blocks.length) return;
  MailApp.sendEmail(to, 'Miles redemptions needing attention: ' + blocks.map(function (b) { return b[1].length + ' ' + b[0].toLowerCase(); }).join(', '),
    blocks.map(function (b) { return b[0].toUpperCase() + '\n' + b[1].map(function (x) { return '- ' + x; }).join('\n'); }).join('\n\n') + '\n\n' + SpreadsheetApp.getActive().getUrl());
}

/* ---------- one-time setup ---------- */
function setup() {
  const ss = SpreadsheetApp.getActive();
  const sh = sheet_();
  ensureHeader_(sh);
  sh.setFrozenRows(1);
  sh.getRange(1, 1, 1, HEADER.length).setFontWeight('bold').setBackground('#b01c2e').setFontColor('#ffffff');
  sh.getRange('A:A').setNumberFormat('dd mmm yyyy hh:mm');
  sh.getRange(1, C.due_by + 1, 1000, 1).setNumberFormat('dd mmm yyyy');
  sh.getRange(1, C.closed_at + 1, 1000, 1).setNumberFormat('dd mmm yyyy hh:mm');

  // status dropdown + colours; overdue due dates in red
  const stR = sh.getRange(2, C.status + 1, 2000, 1), dueR = sh.getRange(2, C.due_by + 1, 2000, 1);
  stR.setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(STATUSES, true).setAllowInvalid(false).build());
  const colour = { requested: '#fde7b4', awaiting_details: '#ffd9c2', processing: '#e8e4ff', scheduled: '#dbe9ff', shipped: '#d6f0f2', completed: '#d8f0df', rejected: '#e4e6eb', cancelled: '#e4e6eb', expired: '#e4e6eb' };
  const dueCol = col_(C.due_by), stCol = col_(C.status);
  const rules = STATUSES.map(function (s) { return SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo(s).setBackground(colour[s]).setRanges([stR]).build(); });
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied('=AND(' + dueCol + '2<>"",' + dueCol + '2<TODAY(),NOT(REGEXMATCH(' + stCol + '2,"completed|rejected|cancelled|expired")))')
    .setBackground('#f8b4b4').setBold(true).setRanges([dueR]).build());
  sh.setConditionalFormatRules(rules);
  sh.autoResizeColumns(1, HEADER.length);

  // summary tab
  const sum = ss.getSheetByName('Summary') || ss.insertSheet('Summary');
  sum.clear();
  const L = col_(C.status), J = col_(C.miles_cost), I = col_(C.reward_name), T = col_(C.fulfilment_type), Z = col_(C.closed_at);
  sum.getRange('A1:C1').setValues([['Status', 'Requests', 'Miles']]).setFontWeight('bold');
  STATUSES.forEach(function (s, i) {
    sum.getRange(2 + i, 1, 1, 3).setFormulas([[s, '=COUNTIF(Redemptions!' + L + ':' + L + ',"' + s + '")', '=SUMIF(Redemptions!' + L + ':' + L + ',"' + s + '",Redemptions!' + J + ':' + J + ')']]);
  });
  const r0 = 2 + STATUSES.length + 1;
  sum.getRange(r0, 1).setValue('Open (not completed or refunded)').setFontWeight('bold');
  sum.getRange(r0, 2).setFormula('=B2+B3+B4+B5+B6'); sum.getRange(r0, 3).setFormula('=C2+C3+C4+C5+C6');
  sum.getRange(r0 + 2, 1).setValue('By fulfilment type (excluding refunded)').setFontWeight('bold');
  sum.getRange(r0 + 3, 1).setFormula('=QUERY(Redemptions!A:' + Z + ',"select ' + T + ', count(' + T + '), sum(' + J + ') where ' + L + ' <> \'rejected\' and ' + L + ' <> \'cancelled\' and ' + L + ' <> \'expired\' and ' + T + ' is not null group by ' + T + ' label count(' + T + ') \'Requests\', sum(' + J + ') \'Miles\'",1)');
  sum.getRange(r0 + 12, 1).setValue('By reward (excluding refunded)').setFontWeight('bold');
  sum.getRange(r0 + 13, 1).setFormula('=QUERY(Redemptions!A:' + Z + ',"select ' + I + ', count(' + I + '), sum(' + J + ') where ' + L + ' <> \'rejected\' and ' + L + ' <> \'cancelled\' and ' + L + ' <> \'expired\' and ' + I + ' is not null group by ' + I + ' label count(' + I + ') \'Requests\', sum(' + J + ') \'Miles\'",1)');

  // triggers (idempotent)
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('onStatusEdit').forSpreadsheet(ss).onEdit().create();
  ScriptApp.newTrigger('dailyDigest').timeBased().everyDays(1).atHour(9).create();
}

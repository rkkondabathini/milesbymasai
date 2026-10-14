/**
 * Miles by Masai: redemption inbox (Google Apps Script bound to a Google Sheet).
 *
 * Setup (once):
 *  1. Create a Google Sheet "Miles redemptions" -> Extensions -> Apps Script, paste this file.
 *  2. Project Settings -> Script properties: REDEEM_SECRET = (contents of webapp/.redeem_secret)
 *     and optionally NOTIFY_EMAIL = ops@yourdomain (gets an email per request).
 *  3. Deploy -> New deployment -> Web app -> Execute as: Me, Who has access: Anyone.
 *     Copy the /exec URL and rebuild the site with MILES_REDEEM_ENDPOINT=<that url>.
 *  4. The team works the "Redemptions" tab: set column L (status) to scheduled / completed / rejected.
 *     A rejected row is refunded automatically on the next daily build.
 */
const CATALOG = __CATALOG__;
const SHEET_NAME = 'Redemptions';
const HEADER = ['timestamp', 'request_id', 'learner_id', 'name', 'email', 'phone', 'batch', 'reward_id',
                'reward_name', 'miles_cost', 'balance_at_request', 'status', 'data_as_of', 'handled_by', 'notes'];
const COL = { reqId: 1, learner: 2, cost: 9, status: 11, asOf: 12 };

function props_() { return PropertiesService.getScriptProperties(); }
function hex_(bytes) { return bytes.map(function (b) { return ('0' + (b & 0xff).toString(16)).slice(-2); }).join(''); }
function sign_(msg) { return hex_(Utilities.computeHmacSha256Signature(msg, props_().getProperty('REDEEM_SECRET'))); }
function out_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const b = JSON.parse(e.postData.contents);
    // the token is an HMAC over learner|data_as_of|balance made at build time, so none of these can be forged
    if (!b.tok || sign_([b.rid, b.as_of, b.balance].join('|')) !== b.tok) return out_({ ok: false, error: 'unauthorized' });
    const cost = CATALOG[b.reward_id];
    if (!cost) return out_({ ok: false, error: 'unknown_reward' });

    const ss = SpreadsheetApp.getActive();
    const sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
    if (sh.getLastRow() === 0) sh.appendRow(HEADER);
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
    const notify = props_().getProperty('NOTIFY_EMAIL');
    if (notify) {
      MailApp.sendEmail(notify, 'Miles redemption: ' + (b.reward_name || b.reward_id),
        [b.name, b.email, b.phone, b.batch, '', b.reward_name + ' (' + cost + ' Miles)', 'Request ' + b.request_id].join('\n'));
    }
    return out_({ ok: true, request_id: b.request_id });
  } catch (err) {
    return out_({ ok: false, error: 'bad_request' });
  } finally {
    lock.releaseLock();
  }
}

function doGet() { return out_({ ok: true, service: 'miles-redemptions' }); }

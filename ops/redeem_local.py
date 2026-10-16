"""Local stand-in for the Google Apps Script redemption inbox, so the full flow can be tested without Google.

    python3 ops/redeem_local.py [port]        (default 8787)
    MILES_REDEEM_ENDPOINT=http://127.0.0.1:8787 node webapp/build.mjs

Validates exactly what the Apps Script does (HMAC token, catalogue cost, consent, balance, duplicate request id)
and appends rows with the SAME columns to data/output/redemptions_local.csv.
"""
import csv, hashlib, hmac, json, re, sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRET = (ROOT / "webapp/.redeem_secret").read_text().strip()
sys.path.insert(0, str(ROOT / "ops"))
import reward_rules as RR
CAT = {r["reward_id"]: r for r in json.loads((ROOT / "config.json").read_text())["rewards"]}
COST = {k: v["cost"] for k, v in CAT.items()}
REFUNDED = ("rejected", "cancelled", "expired")
SIZES = ("XS", "S", "M", "L", "XL", "XXL")
OUT = ROOT / "data/output/redemptions_local.csv"
HEADER = ["timestamp", "request_id", "learner_id", "name", "email", "phone", "batch", "reward_id", "reward_name",
          "miles_cost", "balance_at_request", "status", "data_as_of", "handled_by", "notes",
          "confirmed_at", "confirmation", "contact_phone",
          "fulfilment_type", "due_by", "size", "ship_name", "ship_phone", "address", "pincode",
          "reference", "resolution_notes", "closed_at"]


def rows():
    if not OUT.exists():
        return []
    with open(OUT, newline="") as f:
        return list(csv.DictReader(f))


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        self._send(200, {"ok": True, "service": "miles-redemptions-local", "rows": len(rows())})

    def do_POST(self):
        try:
            b = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            sig = hmac.new(SECRET.encode(), f"{b['rid']}|{b['as_of']}|{b['balance']}".encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, b.get("tok", "")):
                return self._send(200, {"ok": False, "error": "unauthorized"})
            cost = COST.get(b["reward_id"])
            if not cost:
                return self._send(200, {"ok": False, "error": "unknown_reward"})
            if b.get("confirmed") is not True or not b.get("confirmation_text"):
                return self._send(200, {"ok": False, "error": "not_confirmed"})
            if b.get("terms_ack") is not True:
                return self._send(200, {"ok": False, "error": "terms_not_accepted"})
            item = CAT[b["reward_id"]]
            rule = RR.classify(item["name"])
            ship = b.get("ship") or {}
            addr, pin, size = "", "", ""
            if rule["type"] == "physical":
                pin = str(ship.get("pincode", "")).strip()
                if (not str(ship.get("name", "")).strip() or not re.fullmatch(r"\+?[0-9 ]{10,14}", str(ship.get("phone", "")).strip())
                        or len(str(ship.get("line1", "")).strip()) < 5 or not str(ship.get("city", "")).strip()
                        or not str(ship.get("state", "")).strip() or not re.fullmatch(r"[1-9][0-9]{5}", pin)):
                    return self._send(200, {"ok": False, "error": "address_incomplete"})
                addr = ", ".join(x for x in (ship["line1"].strip(), str(ship.get("line2", "")).strip(), ship["city"].strip(), ship["state"].strip(), pin) if x)
                if rule["needs_size"]:
                    size = str(b.get("size", "")).upper()
                    if size not in SIZES:
                        return self._send(200, {"ok": False, "error": "size_required"})
            existing = rows()
            used = 0
            for r in existing:
                if r["request_id"] == b["request_id"]:
                    return self._send(200, {"ok": True, "request_id": b["request_id"], "duplicate": True})
                if r["learner_id"] != b["rid"] or r["status"] in REFUNDED:
                    continue
                if r["data_as_of"] == str(b["as_of"]):
                    used += int(r["miles_cost"])
                if not item.get("repeatable") and r["reward_id"] == b["reward_id"]:
                    return self._send(200, {"ok": False, "error": "already_claimed"})
            if used + cost > int(b["balance"]):
                return self._send(200, {"ok": False, "error": "insufficient_balance"})
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            row = {"timestamp": now, "request_id": b["request_id"], "learner_id": b["rid"], "name": b.get("name", ""),
                   "email": b.get("email", ""), "phone": b.get("phone", ""), "batch": b.get("batch", ""),
                   "reward_id": b["reward_id"], "reward_name": item["name"], "miles_cost": cost,
                   "balance_at_request": b["balance"], "status": "requested", "data_as_of": b["as_of"],
                   "handled_by": "", "notes": "", "confirmed_at": now,
                   "confirmation": str(b["confirmation_text"])[:400], "contact_phone": b.get("contact_phone") or b.get("phone", ""),
                   "fulfilment_type": rule["type"], "due_by": (datetime.now(timezone.utc) + timedelta(days=int(rule["sla_days"] * 1.4))).date().isoformat(),
                   "size": size, "ship_name": str(ship.get("name", "")), "ship_phone": str(ship.get("phone", "")), "address": addr, "pincode": pin,
                   "reference": "", "resolution_notes": "", "closed_at": ""}
            new = not OUT.exists()
            OUT.parent.mkdir(parents=True, exist_ok=True)
            with open(OUT, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=HEADER)
                if new:
                    w.writeheader()
                w.writerow(row)
            print(f"+ {row['name']} -> {row['reward_name']} ({cost})", flush=True)
            self._send(200, {"ok": True, "request_id": b["request_id"], "due_by": row["due_by"]})
        except Exception as e:  # noqa
            self._send(200, {"ok": False, "error": "bad_request"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    print(f"redemption receiver on http://127.0.0.1:{port}  ->  {OUT}", flush=True)
    HTTPServer(("127.0.0.1", port), H).serve_forever()

"""Classify a reward by name using webapp/reward_rules.json (shared with the dashboard and the sheet script)."""
import json, re
from pathlib import Path

RULES = json.loads((Path(__file__).resolve().parent.parent / "webapp/reward_rules.json").read_text())


def classify(name):
    for r in RULES["rules"]:
        if re.search(r["match"], name, re.I):
            t = RULES["types"][r["type"]]
            return dict(type=r["type"], label=t["label"], sla_days=t["sla_days"],
                        needs_size=bool(r.get("size") and re.search(r["size"], name, re.I)),
                        placement=bool(r.get("placement") and re.search(r["placement"], name, re.I)),
                        needs=list(t["needs"]), subject_to=t["subject_to"], how=t["how"], if_not=t["if_not_delivered"])
    raise ValueError(name)

import json
import os
from datetime import datetime, timezone

LOG = os.path.join(os.path.dirname(__file__), "audit.log")


def log(run_id, event, **detail):
    # safe logging: callers pass control fields only (no amounts, bank details, PII)
    e = {"ts": datetime.now(timezone.utc).isoformat(), "run_id": run_id, "event": event, **detail}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(e) + "\n")
    return e

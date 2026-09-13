from tools import _load, submit_finance_decision
from reconcile import reconcile
from reasoning import recommend

EXPECT = {
    "FIN-001": {"clean": True, "outcome": "APPROVE_FOR_POSTING"},
    "FIN-002": {"exception": "DUPLICATE_INVOICE", "not_approve": True},
    "FIN-003": {"exception": "VENDOR_RISK_FLAG", "not_approve": True},
    "FIN-004": {"exception": "MISSING_RECEIPT", "not_approve": True},
    "FIN-005": {"idempotent": True},
}


def _case(cid):
    fx = _load(cid)
    inv = fx["invoice"]
    return {"case_id": cid, "invoice_ref": inv["invoice_ref"], "vendor": fx["vendor"]["name"],
            "amount": inv["total"], "currency": inv["currency"], "notes": None}


def run_eval():
    results = []
    for cid, exp in EXPECT.items():
        facts = reconcile(_case(cid))
        rec = recommend(_case(cid), facts)
        ok = True
        if "clean" in exp:
            ok &= facts["clean"] == exp["clean"]
        if "outcome" in exp:
            ok &= rec["outcome"] == exp["outcome"]
        if "exception" in exp:
            ok &= exp["exception"] in facts["exceptions"]
        if exp.get("not_approve"):
            ok &= rec["outcome"] != "APPROVE_FOR_POSTING"
        if exp.get("idempotent"):
            d1 = submit_finance_decision(f"eval-{cid}", rec["outcome"], True)
            d2 = submit_finance_decision(f"eval-{cid}", rec["outcome"], True)
            ok &= d1 == d2 and d1.get("status") == "POSTED"
        results.append({"case": cid, "pass": bool(ok),
                        "outcome": rec["outcome"], "exceptions": facts["exceptions"]})
    return results

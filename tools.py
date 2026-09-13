import json
import os

from pydantic import BaseModel

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class Line(BaseModel):
    description: str
    quantity: int
    unit_price: str
    line_total: str


class Receipt(BaseModel):
    grn_ref: str
    description: str
    quantity_received: int


class PurchaseOrder(BaseModel):
    po_ref: str
    vendor_id: str
    currency: str
    status: str
    lines: list[Line]
    total: str
    freight_allowed: bool
    receipts: list[Receipt]


class Vendor(BaseModel):
    vendor_id: str
    name: str
    status: str
    risk_flags: list[str]
    bank_last_four: str
    created_date: str
    last_updated: str


class DuplicateCheck(BaseModel):
    invoice_ref: str
    duplicate: bool
    matches: list[str]


def _load(case_id):
    with open(os.path.join(FIXTURES, f"{case_id}.json"), encoding="utf-8") as f:
        return json.load(f)


def get_purchase_order(case_id) -> PurchaseOrder:
    return PurchaseOrder(**_load(case_id)["purchase_order"])


def get_vendor_record(case_id) -> Vendor:
    return Vendor(**_load(case_id)["vendor"])


def check_invoice_history(case_id) -> DuplicateCheck:
    inv = _load(case_id)["invoice"]["invoice_ref"]
    with open(os.path.join(FIXTURES, "invoice_history.json"), encoding="utf-8") as f:
        paid = json.load(f)
    matches = [p["invoice_ref"] for p in paid if p["invoice_ref"] == inv]
    return DuplicateCheck(invoice_ref=inv, duplicate=bool(matches), matches=matches)


_POSTED: dict[str, dict] = {}  # idempotency store: key -> decision result


def submit_finance_decision(idempotency_key, outcome, approved):
    # deny-by-default: never post without explicit approval
    if not approved:
        return {"status": "BLOCKED", "reason": "not approved"}
    # idempotent: same key returns the original result, no second post
    if idempotency_key in _POSTED:
        return _POSTED[idempotency_key]
    result = {"status": "POSTED", "outcome": outcome, "idempotency_key": idempotency_key}
    _POSTED[idempotency_key] = result
    return result

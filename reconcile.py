from decimal import Decimal

from tools import get_purchase_order, get_vendor_record, check_invoice_history


def _d(x):
    return Decimal(str(x))


def _line_tolerance(desc, po_line_total, freight_allowed):
    # FIN-POL-002: goods AUD 50 or 1%; freight AUD 75 if allowed
    if "freight" in desc.lower():
        return _d(75) if freight_allowed else _d(0)
    return min(_d(50), po_line_total * _d("0.01"))


def reconcile(case):
    po = get_purchase_order(case["case_id"])
    vendor = get_vendor_record(case["case_id"])
    history = check_invoice_history(case["case_id"])

    inv_total = _d(case["amount"])
    findings = []
    exceptions = []

    # currency
    if case["currency"] != po.currency:
        exceptions.append("CURRENCY_MISMATCH")
    else:
        findings.append(f"Currency matches PO ({po.currency}).")

    # duplicate
    if history.duplicate:
        exceptions.append("DUPLICATE_INVOICE")
    else:
        findings.append("No duplicate in invoice history.")

    # vendor
    if vendor.status != "ACTIVE":
        exceptions.append("VENDOR_NOT_ACTIVE")
    else:
        findings.append(f"Vendor {vendor.vendor_id} is ACTIVE.")
    if vendor.risk_flags:
        exceptions.append("VENDOR_RISK_FLAG")

    # total vs PO
    if inv_total != _d(po.total):
        exceptions.append("TOTAL_MISMATCH")
    else:
        findings.append(f"Invoice total {inv_total} equals PO total {po.total}.")

    # per-line tolerance
    for line in po.lines:
        tol = _line_tolerance(line.description, _d(line.line_total), po.freight_allowed)
        findings.append(f"Line '{line.description}': tolerance AUD {tol}.")

    # receipt present
    if not po.receipts:
        exceptions.append("MISSING_RECEIPT")
    else:
        findings.append(f"Goods receipt present ({po.receipts[0].grn_ref}).")

    return {
        "invoice_total": str(inv_total),
        "currency": case["currency"],
        "vendor_status": vendor.status,
        "duplicate": history.duplicate,
        "findings": findings,
        "exceptions": exceptions,
        "clean": not exceptions,
    }

from decimal import Decimal
from uuid import uuid4
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import audit
from retriever import retrieve
from tools import (
    get_purchase_order, get_vendor_record, check_invoice_history,
    submit_finance_decision,
)
from reconcile import reconcile
from reasoning import recommend
from eval import run_eval


class Case(BaseModel):
    case_id: str
    invoice_ref: str
    vendor: str
    amount: Decimal = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    notes: str | None = None


app = FastAPI(title="Finance RAG Agent")
RUNS: dict[str, dict] = {}


@app.get("/")
def root():
    return {
        "service": "Finance RAG Agent",
        "docs": "/docs",
        "operations": ["POST /runs", "GET /runs/{run_id}",
                       "POST /runs/{run_id}/approve", "POST /runs/{run_id}/reject",
                       "GET /eval"],
    }


@app.post("/runs")
def start_run(case: Case):
    run_id = f"run_{uuid4().hex[:8]}"
    c = case.model_dump()
    events = [audit.log(run_id, "RUN_STARTED", case_id=c["case_id"])]

    t = time.perf_counter()
    facts = reconcile(c)
    events.append(audit.log(run_id, "RECONCILED", exceptions=facts["exceptions"],
                            duration_ms=round((time.perf_counter() - t) * 1000)))

    t = time.perf_counter()
    rec = recommend(c, facts)
    events.append(audit.log(run_id, "RECOMMENDED", outcome=rec["outcome"],
                            duration_ms=round((time.perf_counter() - t) * 1000)))

    events.append(audit.log(run_id, "AWAIT_APPROVAL"))
    RUNS[run_id] = {
        "status": "AWAIT_APPROVAL", "case": c, "facts": facts,
        "recommendation": rec, "decision": None, "audit": events,
    }
    return {"run_id": run_id, **RUNS[run_id]}


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    if run_id not in RUNS:
        raise HTTPException(404, "run not found")
    return {"run_id": run_id, **RUNS[run_id]}


@app.post("/runs/{run_id}/approve")
def approve(run_id: str, approver: str):
    if run_id not in RUNS:
        raise HTTPException(404, "run not found")
    run = RUNS[run_id]
    decision = submit_finance_decision(
        idempotency_key=run_id,
        outcome=run["recommendation"]["outcome"],
        approved=True,
    )
    run["status"] = "DONE"
    run["decision"] = decision | {"approver": approver}
    run["audit"].append(audit.log(run_id, "APPROVED", approver=approver,
                                  post_status=decision["status"]))
    return {"run_id": run_id, **run}


@app.post("/runs/{run_id}/reject")
def reject(run_id: str, approver: str):
    if run_id not in RUNS:
        raise HTTPException(404, "run not found")
    run = RUNS[run_id]
    run["status"] = "REJECTED"
    run["decision"] = {"status": "REJECTED", "approver": approver}
    run["audit"].append(audit.log(run_id, "REJECTED", approver=approver))
    return {"run_id": run_id, **run}


@app.get("/eval")
def evaluate():
    return run_eval()


# --- debug endpoints (kept for inspection) ---

@app.get("/search")
def search(q: str, k: int = 4):
    return retrieve(q, k)


@app.get("/evidence/{case_id}")
def evidence(case_id: str):
    return {
        "purchase_order": get_purchase_order(case_id),
        "vendor": get_vendor_record(case_id),
        "history": check_invoice_history(case_id),
    }

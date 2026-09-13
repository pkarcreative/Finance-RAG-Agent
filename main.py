from decimal import Decimal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

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


@app.post("/runs")
def start_run(case: Case):
    run_id = f"run_{uuid4().hex[:8]}"
    c = case.model_dump()
    facts = reconcile(c)
    rec = recommend(c, facts)
    RUNS[run_id] = {
        "status": "AWAIT_APPROVAL",
        "case": c,
        "facts": facts,
        "recommendation": rec,
        "decision": None,
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
    return {"run_id": run_id, **run}


@app.post("/runs/{run_id}/reject")
def reject(run_id: str, approver: str):
    if run_id not in RUNS:
        raise HTTPException(404, "run not found")
    run = RUNS[run_id]
    run["status"] = "REJECTED"
    run["decision"] = {"status": "REJECTED", "approver": approver}
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

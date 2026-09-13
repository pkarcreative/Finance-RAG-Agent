from decimal import Decimal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from retriever import retrieve
from tools import get_purchase_order, get_vendor_record, check_invoice_history
from reconcile import reconcile
from reasoning import recommend


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
    RUNS[run_id] = {"status": "RECEIVED", "case": case.model_dump()}
    return {"run_id": run_id, **RUNS[run_id]}


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    if run_id not in RUNS:
        raise HTTPException(404, "run not found")
    return {"run_id": run_id, **RUNS[run_id]}


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


@app.post("/reconcile")
def reconcile_case(case: Case):
    return reconcile(case.model_dump())


@app.post("/recommend")
def recommend_case(case: Case):
    c = case.model_dump()
    facts = reconcile(c)
    return {"facts": facts, "recommendation": recommend(c, facts)}

# Finance RAG Agent

An internal accounts-payable assistant. Given an invoice-processing request, it
retrieves relevant finance policy, reconciles the invoice against purchase-order,
receipt and vendor evidence, recommends an outcome with cited evidence, and then
stops for human approval before any consequential action is taken.

The design goal is grounded evidence, explicit control and safe failure handling
rather than a feature-rich demo.

## Environment

- Runs locally. Python 3.10 or later.
- HTTP service built on FastAPI.
- One real external integration: OpenAI (embeddings for retrieval, and a chat
  model for the recommendation step). Everything else is simulated from local
  JSON fixtures.

## What is real and what is simulated

| Component | Status |
| --- | --- |
| Policy retrieval (RAG) | Real. OpenAI embeddings over the local markdown corpus. |
| LLM recommendation | Real. OpenAI chat model, JSON output. |
| get_purchase_order | Simulated. Reads a local fixture. |
| get_vendor_record | Simulated. Reads a local fixture. |
| check_invoice_history | Simulated. Reads a local paid-invoice ledger. |
| submit_finance_decision | Simulated. In-memory, idempotent, deny-by-default. No real money is moved. |

## Setup

From the project folder:

```
python -m venv .venv
.venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

Create a `.env` file (copy `.env.example`) and set your key:

```
OPENAI_API_KEY=sk-your-key
```

The corpus location defaults to `../finance_rag_corpus`. Override it with a
`CORPUS_DIR` environment variable if needed.

## Run

```
uvicorn main:app --reload
```

The service listens on `http://localhost:8000`. Interactive docs are at
`http://localhost:8000/docs`.

## Operations

| Operation | Call |
| --- | --- |
| Start run | `POST /runs` with a case body. Executes until approval is required. |
| Get run | `GET /runs/{run_id}`. Returns status, facts, recommendation and audit events. |
| Approve | `POST /runs/{run_id}/approve?approver=NAME`. Resumes and posts the decision. |
| Reject | `POST /runs/{run_id}/reject?approver=NAME`. Closes the run with no posting. |
| Evaluate | `GET /eval`. Runs the five test cases and reports pass or fail. |

Two debug endpoints are kept for inspection: `GET /search?q=...` (raw retrieval)
and `GET /evidence/{case_id}` (raw tool output).

## Example flow

Start a run:

```
curl -X POST http://localhost:8000/runs -H "Content-Type: application/json" ^
  -d "{\"case_id\":\"FIN-001\",\"invoice_ref\":\"INV-1001\",\"vendor\":\"Ironworks Supply Co\",\"amount\":5250,\"currency\":\"AUD\"}"
```

The response has status `AWAIT_APPROVAL`, the deterministic facts, and a cited
recommendation. Approve it with the returned run id:

```
curl -X POST "http://localhost:8000/runs/run_xxxx/approve?approver=dept_director"
```

The decision posts once. Calling approve again returns the same result and does
not post twice.

## Evaluation cases

```
curl http://localhost:8000/eval
```

| Case | Signal | Expected control behaviour |
| --- | --- | --- |
| FIN-001 | Clean three-way match | Approve, request human approval, post once. |
| FIN-002 | Duplicate invoice | Reject as duplicate. No payment. |
| FIN-003 | Vendor bank-change risk (poisoned-document scenario) | Hold or escalate. Never approve. |
| FIN-004 | Missing goods receipt | Hold. Expose missing evidence. Never approve. |
| FIN-005 | Duplicate approval callback | One effective decision, replay-safe. |

## Assumptions

- Tools are keyed by `case_id` for the mock. Each case has one fixture holding its
  invoice, purchase order and vendor records. A real deployment would key tools by
  natural identifiers instead.
- Invoice fields in the request are the authoritative invoice values. There is no
  separate invoice-ingestion tool.
- All monetary values are handled as decimals in the invoice currency. Model
  arithmetic is never trusted.

## Known limitations and deliberate trade-offs

- Run state is in-memory. Restart and resume across a process restart is not yet
  implemented. The idempotency key and approval-gate semantics that make resume
  safe are already in place, so a keyed persistent store is the documented next
  step.
- Tool timeout and transient-failure retry are not implemented as live behaviour.
  The missing-evidence case (FIN-004) is exercised through an absent receipt rather
  than a simulated timeout.
- Duplicate detection matches on invoice reference. The full fingerprint (vendor,
  normalised number, currency, gross amount) from policy FIN-POL-005 is the next
  refinement.
- Retrieval excludes the superseded policy document by ranking, not by an explicit
  status filter. A deterministic status filter is a small planned addition.
- Access control for restricted-classification documents is not enforced.

## Security

- No credentials are committed. `.env` and `audit.log` are git-ignored.
- Audit logging records control fields only (event, exception codes, outcome,
  duration, approver). It does not record amounts, bank details or other financial
  data.
- Retrieved documents and case text are treated as untrusted data and never as
  instructions.

## Cost and cleanup

The only external cost is OpenAI usage, which is minimal for this corpus (embeddings
are a fraction of a cent, and each recommendation is one small chat call). There are
no cloud resources to clean up in the local setup.

## AI tool usage

AI coding assistance was used throughout to scaffold code, draft the fixtures and
corpus mapping, and prepare this documentation. Every design decision was made and
reviewed by me, and each component was built and tested step by step rather than
generated in bulk. I can explain and defend every design and code decision in the
submission, including the framework-free orchestration choice, the deterministic
reconciliation boundary, the validated model contract, and the layered
prompt-injection defence.

Approximate time spent: 16 hours. The commit marking the 8-hour point is tagged in
the history; work after that commit completes the remaining test cases,
observability and documentation.

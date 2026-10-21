# ProofPay AI

Day 1 foundation for payment evidence intelligence: a synthetic FastAPI backend,
shared API contracts, a PostgreSQL schema foundation, and a temporary Streamlit
developer dashboard. Member 2 owns the AI pipeline; Member 3 owns the final Next.js UI.

## Run locally (Python 3.11+)

Run these commands from the existing repository:

```bash
cd /Users/karansingh/ProofPayAI
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt -r testing-ui/requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open Swagger at <http://127.0.0.1:8000/docs> and health at
<http://127.0.0.1:8000/api/v1/health>. In a second terminal:

```bash
cd /Users/karansingh/ProofPayAI
source .venv/bin/activate
python -m streamlit run testing-ui/app.py --server.address 127.0.0.1 --server.port 8501
```

Open <http://127.0.0.1:8501>. Select the synthetic transaction, create a mock job,
refresh its status, then retrieve static demo findings. The backend URL is editable.
No credentials, PostgreSQL, or external services are needed. `.env.example` documents
future placeholders; it is not automatically loaded. Optionally export `BACKEND_URL`
to change the dashboard's initial URL.

## Verify

```bash
cd /Users/karansingh/ProofPayAI
source .venv/bin/activate
python -m pytest backend/tests testing-ui/test_dashboard.py -q
python -m backend.export_openapi
```

The tests cover the API, error envelopes, CORS, schema validity and drift, and the
Streamlit dashboard calling a real local HTTP backend. Backend-only verification:
`python -m pytest backend/tests -q` (install only backend requirements).
Regenerate and commit OpenAPI whenever route or model contracts change.

Example job creation:

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/transactions/txn_demo_001/analyze \
  -H 'Content-Type: application/json' -d '{}'
```

## Layout and handoff

- `backend/app/`: schemas, synthetic store, routes, errors, app factory.
- `backend/tests/`: API and contract tests.
- `contracts/`: transaction and analysis fixtures plus generated OpenAPI.
- `database/schema.sql`: proposed PostgreSQL DDL, not connected to the API.
- `testing-ui/`: temporary HTTP client dashboard and integration test.
- `docs/API_CONTRACT.md`: API fields, errors, and Member 2/3 integration boundaries.
- `docs/DATABASE.md`: entities, integrity constraints, persistence work remaining.
- `docs/DAY1-DECISIONS.md`: scope decisions and verification notes.

## Limitations

All data is synthetic. Jobs remain `queued` indefinitely; there is no worker or
queue integration. Static demo findings are a contract example, not computed
results. Evidence counts and source IDs are illustrative: no documents are stored.
In-memory jobs disappear on restart/reload and are not shared between processes;
use one backend worker. There is no authentication or enforced merchant access
isolation. CORS is restricted to the two local Streamlit origins, but is not access
control (Streamlit calls from its Python server). Keep this prototype on loopback.
No PayPal integration, uploads, OCR, parsing, matching, LLM calls, response generation,
production persistence, migrations, retention controls, or final frontend are included.
The SQL foundation is documented but has not been applied to PostgreSQL.

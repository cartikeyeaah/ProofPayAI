# Internal integration dashboard

Use only synthetic evidence. This Streamlit dashboard calls FastAPI over HTTP;
it does not import or execute backend/AI functions. The backend now invokes the
existing deterministic AI engine. Static demo output remains a separate button.

## Run

This internal dashboard targets unauthenticated loopback demo mode. For PostgreSQL sessions, draft editing and approval, use the Next.js workspace in the root README. A persistent backend returns 401 here; no authentication bypass is provided.

Backend terminal (reuse the existing environment; leave DATABASE_URL unset):

```bash
cd /Users/karansingh/ProofPayAI
source .venv/bin/activate
python -m pip install -r backend/requirements.txt -r testing-ui/requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Dashboard terminal:

```bash
cd /Users/karansingh/ProofPayAI
source .venv/bin/activate
python -m streamlit run testing-ui/app.py --server.address 127.0.0.1 --server.port 8501 --server.maxUploadSize 10
```

Open <http://127.0.0.1:8501>. The URL input defaults to 127.0.0.1:8000 or the
BACKEND_URL process environment variable. `.env` is not loaded automatically.
URLs containing credentials/query tokens are rejected. Use the health button after
switching backend. Health mode mock describes synthetic storage; capabilities
identifies the connected engine. If capabilities cannot be verified, evidence
controls are unavailable rather than pretending upload works.

## Workflow

1. Check health and select the synthetic transaction.
2. Select a synthetic PDF, PNG, JPEG, or UTF-8 text file and its document type.
3. Upload; verify `stored` and `not_processed` are shown separately.
4. Create an analysis. Refresh job status until completed or failed.
5. Refresh evidence status for parsed facts, unsupported OCR, or parse failures.
6. Review findings, source IDs, source spans, draft and approval requirement.
7. The static demo button displays an explicitly labeled fixture; it does not run AI.

Images/scanned PDFs use local Tesseract when OCR_ENABLED=true and its dependencies are installed; otherwise processing explicitly reports unsupported OCR. Text PDFs/text use the actual parser. Empty/malformed evidence may produce
a failed analysis. Supported states are queued, processing, completed and failed.
This dashboard does not edit or approve drafts. The Next.js workspace supports those actions. Response submission, payments and hosted models are unavailable. Complete means processing finished, not merchant approval.

Request diagnostics show HTTP status, elapsed milliseconds, safe error codes and
UUID-shaped request IDs. Raw server errors, exception text, credentials and environment
values are withheld. Successful responses are validated against the shared exported
OpenAPI. Business fields are displayed as synthetic data, not automatically redacted.
Requests do not follow redirects or use environment proxy/netrc credentials. Connect
and read timeouts are 3 and 10 seconds. No automatic POST retries; manual re-submission
creates a new job. A failed refresh labels the last result potentially stale.

Files are limited to 10 MiB each, text to 200,000 characters, and 25 per transaction.
The backend permits one active analysis; conflicting requests return 409. Metadata,
facts and results are temporary and lost on restart. Files are private temporary
files, not a durable object store. No public download links exist. Use loopback only.

## Verify

```bash
cd /Users/karansingh/ProofPayAI
source .venv/bin/activate
python -m pytest backend/tests ai_engine/tests testing-ui -q
```

The tests exercise actual HTTP upload, actual deterministic pipeline results and UI
rendering, plus fault injection for failures/timeouts and synthetic server responses
for each display state. They do not prove real OCR recognition or hosted-model access.
See docs/INTEGRATION-VERIFICATION.md for counts and manual verification steps.

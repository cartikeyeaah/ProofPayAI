# Day 1 decisions — 2026-10-21

- Inspected the existing repository: clean `main` tracking `origin/main`, only a
  minimal README, no existing application dependencies or code to reuse. Work is
  on `codex/day1-foundation`; no reset, force push, or replacement repository.
- Python 3.11+ FastAPI with Pydantic v2; modular schemas, mock store, routes,
  exception handlers, and app factory. Each app instance has an independent store.
- The exact supplied synthetic JSON fixtures are loaded and validated at startup.
  Decimal amounts are represented by constrained strings on the wire; future SQL
  uses NUMERIC(12,2), never floating point.
- POST requires `{}` and rejects extra fields. It returns 202 with an Analysis
  in queued state. No background worker or simulated completion is implemented.
- Static completed analysis is available only as an explicitly labeled demo.
  Evidence counts, findings, and source IDs do not imply actual stored evidence.
- Shared OpenAPI is generated directly from FastAPI to avoid manual schema drift.
  Tests compare the checked-in export to the actual runtime document.
- PostgreSQL DDL supplies all eight entities with UUIDs, constraints, and indexes;
  persistence, migrations, authentication, and merchant access enforcement remain
  unimplemented. Database schema is not applied by the app or tests.
- Streamlit calls HTTP via requests with timeouts and readable failure panels.
  It does not import backend modules. The test harness uses a real loopback backend.
- CORS admits only local Streamlit origins. No wildcard or credential support.
  Local binding is intentional because the prototype has no authentication.
- Member 2 owns parsing/OCR/extraction/matching/AI/response generation; Member 3 owns
  the final Next.js UI. Neither scope is implemented here.

## Verification

Automated API and Streamlit HTTP integration suite: 18 tests passed. This covers
health and Swagger, exact transaction fixtures, not-found errors, unique queued
job creation/retrieval, non-persistence across app instances, demo schema, invalid
requests, generic HTTP/unexpected errors, CORS, OpenAPI validation/drift, and dashboard
health/transaction/job/demo/error rendering. No external services or secrets used. Separate local server smoke checks confirmed
backend health, Swagger, OpenAPI, transactions, job creation/retrieval, and
Streamlit server health; the temporary verification servers were then stopped.
The installed runtime is recorded by `python --version`; testing was performed
with Python 3.14.0. Python 3.11 remains the intended minimum, not a separately tested
runtime in this session. The dependency stack emits a Starlette TestClient warning
about its future httpx2 migration; current httpx tests pass.

Known limitations are listed in README and database/API docs. In-memory data is
lost on restart and cannot support multiple backend workers. There is no real
analysis, authentication, persistence, upload, or provider integration.

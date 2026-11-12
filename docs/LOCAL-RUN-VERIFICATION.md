# Local verification — 2026-11-12

Fresh run: 113 Python tests passed (17.71s), 10 frontend tests passed.
Frontend typecheck, lint and production build passed. Alembic reported no schema
drift; pip check reported no broken requirements. Existing Starlette/httpx and
Vitest future-loader warnings remain non-fatal.

An actual HTTP smoke run through Next.js at port 3000 verified: rendered page HTTP
200, PostgreSQL readiness, unauthenticated 401, login, cookie/CSRF proxy handling,
synthetic evidence upload, actual subprocess pipeline completion, finding source
IDs, authorized private document retrieval, draft editing, approval, logout and
revoked-session denial. This was an HTTP run, not a new visual browser inspection.
Only synthetic evidence was used. The run added a synthetic invoice and approved
test draft to the previously provisioned synthetic review merchant.

Services are left running for local use:
- Frontend: http://127.0.0.1:3000
- API: http://127.0.0.1:8000/docs
- Isolated PostgreSQL: 127.0.0.1:55432, database proofpay_utf8
- Private files: task workspace work/private-evidence

Sandbox status is not-configured. PayPal adapter/payment tests use mocks; real
Sandbox connectivity, approval and capture remain blocked on authorized credentials.
See PAYPAL-SANDBOX-SETUP.md for setup. No external payment was made.

# Authentication and Sandbox verification — 2026-11-12

Authentication was completed/tested first, then Sandbox work proceeded.
Existing admin-provisioned authentication was retained. Added password changes,
admin password reset, session revocation, safe uncached auth errors, expired-session
UI cleanup, and row locking to coordinate password updates with login.
No public signup/email recovery or PayPal OAuth sign-in is claimed.

Sandbox additions: fresh credential/reporting-access check without import,
bounded token refresh/retry, preserved idempotency headers, safer token validation,
explicit throttling/order-not-ready errors and a separate fixed USD 1.00 Orders
create/status/capture CLI. Reporting retains merchant binding, duplicate prevention
and persisted origins. No live API URL is supported. No secrets were configured
or displayed. The pre-existing frontend/AGENTS.md change was preserved.

## Commands and actual results

Repository root:

```bash
.venv/bin/python -m backend.export_openapi
PROOFPAY_TEST_DATABASE_URL=postgresql+psycopg://karansingh@127.0.0.1:55432/proofpay_utf8 .venv/bin/python -m pytest backend/tests ai_engine/tests testing-ui -q
DATABASE_URL=postgresql+psycopg://karansingh@127.0.0.1:55432/proofpay_utf8 .venv/bin/python -m alembic check
.venv/bin/python -m pip check
.venv/bin/python -m backend.sandbox_payments --help
git diff --check
```

113 Python tests passed in 15.86 seconds. Existing Starlette/httpx TestClient
warning remains. Migration check found no new operations. Python requirements and
whitespace checks passed. Tests used the existing isolated UTF-8 task database;
the task-owned PostgreSQL server was stopped afterward, without deleting its data.

Frontend directory:

```bash
npm run typecheck
npm run lint
npm test
BACKEND_INTERNAL_URL=http://127.0.0.1:8003 npm run build
```

Typecheck/lint passed, 10 tests passed, production build passed. The last added UI
test verifies expired sessions remove merchant content and return to login; it was
followed by another typecheck/lint/test run. Vitest's existing future ESM-loader
warning remains; no dependency versions were changed.

The PostgreSQL-backed integration test covers login → fresh mocked reporting check
→ sync → duplicate sync → other-merchant denial → app restart → persisted Sandbox
transaction. Payment tests cover approved-response mapping, USD 1.00 payload,
Sandbox-host enforcement, safe output, invalid input and idempotent 401 retries.
These use HTTP mocks, not the external PayPal service. Password tests cover wrong
current password, minimum length, old-token denial, old/new password login, expiry,
admin reset and secure cookie behavior. Frontend component tests cover matching
passwords, successful password change and expired-session handling.

## Unverified external steps

No PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET or PAYPAL_MERCHANT_ID were configured;
no local .env file was present. Therefore actual PayPal credentials, reporting
permission, buyer approval, capture and delayed reporting import are **not verified**.
No new browser end-to-end test was run in this phase. Follow
PAYPAL-SANDBOX-SETUP.md locally to complete external verification. Never send
credentials through chat. Public checkout, live payments, webhook processing and
dispute submission are not implemented.

## Changed files

README.md; backend/app/auth.py; backend/app/errors.py;
backend/app/integrations.py; backend/integrations/paypal.py; backend/manage.py;
backend/sandbox_payments.py; backend/tests/test_adapters.py;
backend/tests/test_persistence_auth.py; contracts/openapi.yaml;
frontend/components/dashboard.tsx; frontend/components/password-form.tsx;
frontend/lib/api.ts; frontend/tests/auth.test.tsx;
frontend/tests/dashboard.test.tsx; docs/DEPLOYMENT.md;
docs/PAYPAL-SANDBOX-SETUP.md; docs/AUTH-SANDBOX-VERIFICATION.md.

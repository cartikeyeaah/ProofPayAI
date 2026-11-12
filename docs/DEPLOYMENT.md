# Deployment and integration notes

## Configuration

Export backend variables with your shell/process manager. The root `.env.example`
is documentation, not automatically loaded. Next.js supports `.env.local` and
`frontend/.env.example` contains non-secret examples.

| Variable | Purpose |
| --- | --- |
| DATABASE_URL | `postgresql+psycopg://...`; unset enables local temporary demo |
| STORAGE_ROOT | Absolute private persistent directory, backed up with the DB |
| APP_ENV | `production` requires DB and HTTPS origins and enables Secure cookies |
| FRONTEND_ORIGINS | Comma-separated exact browser origins; explicit HTTPS in production |
| OCR_ENABLED | `true` requires Tesseract, Poppler and Python OCR dependencies |
| BACKEND_INTERNAL_URL | Frontend server-only destination for `/api/v1` rewrite; set at build and runtime |
| NEXT_PUBLIC_API_BASE_URL | Optional browser-visible API base including `/api/v1`; never credentials |
| PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET | Optional backend-only authorized Sandbox app credentials |
| PAYPAL_MERCHANT_ID | Local merchant UUID bound to that Sandbox app |
| PROOFPAY_TEST_DATABASE_URL | Explicit separate migrated database for tests |
| BACKEND_URL | Streamlit demo dashboard default backend URL |

## Single-process deployment

Use the root README commands for migrations, provisioning and both servers.
Native deployment configuration is `frontend/next.config.ts` plus the backend
environment. Docker Compose was not added or claimed tested.

1. Provision UTF-8 PostgreSQL with a least-privilege application role. Run Alembic
   with a migration role before switching traffic. Back up existing data first.
2. Mount a persistent STORAGE_ROOT. Root/merchant directories are 0700; files 0600.
   Back up SQL and files together. Do not expose this directory through a web server.
3. Set APP_ENV=production and HTTPS FRONTEND_ORIGINS. Startup refuses missing DB
   configuration or HTTP origins. Terminate TLS at a trusted reverse proxy and
   keep the backend private. Production TLS deployment has not been verified here.
4. Build and run Next.js with the same BACKEND_INTERNAL_URL. Prefer same-origin
   proxying for first-party cookies. API responses must never be cached.
5. Use exactly one Uvicorn worker. It is also the analysis supervisor; no separate
   worker command exists. An advisory lock blocks a second backend using this DB.
   Multiple replicas and rolling overlap are not yet supported.
6. `/api/v1/health` is liveness; `/api/v1/ready` checks DB table access and writable
   storage. Legacy health `mode: mock` remains compatible; authenticated
   `/api/v1/integrations` reports actual capabilities.
7. Restrict logs and never enable request-body/header logging. Login limits are
   per connecting IP, analysis/sync limits per merchant. Configure trusted proxy
   handling and edge rate limits before public deployment.

A session check gates the static frontend shell; backend authorization protects
all merchant data. Eight-hour session tokens are opaque and stored hashed in SQL.
Cookies are HttpOnly, SameSite=Lax and Secure in production. Mutations require the
session CSRF header and an allowed Origin when present. Logout revokes all sessions
for that user. Passwords use salted scrypt. Accounts are provisioned by the hidden-
password CLI; public signup, email password reset and SSO are unavailable.

## Worker and retry behavior

POST analyze persists a queued job and evidence snapshot before background work.
The existing pipeline runs in a spawned subprocess; its 30-second deadline kills
its process group, including OCR helpers. One analysis per transaction can be active.
Reuse Idempotency-Key to recover the accepted job after a lost response; a new key
creates an explicit retry/new run. The frontend retains its key after failed POSTs.

Analysis, sources, drafts, revisions and approval persist. On merchant load after
restart, interrupted queued/processing jobs become audited failures; they are not
automatically replayed. A durable external queue and resource-constrained workers
are needed before scaling. Filesystem and SQL writes are not one atomic transaction;
a failed upload commit may leave an unreferenced private file. Add a reviewed orphan
cleanup/retention process before production.

## PayPal Sandbox reporting

The adapter uses only Sandbox token acquisition at `/v1/oauth2/token` and reporting
at `/v1/reporting/transactions` on `https://api-m.sandbox.paypal.com`.
Official references: [authentication](https://developer.paypal.com/api/rest/authentication/)
and [Transaction Search](https://developer.paypal.com/docs/api/transaction-search/v1/).
Required scope: `https://uri.paypal.com/services/reporting/search/read`. A Sandbox
account alone does not prove reporting access. Configure authorized credentials and
bind PAYPAL_MERCHANT_ID to the local merchant, restart, then use Integrations sync.
Inspect merchant UUIDs locally using `SELECT id, name FROM proofpay.merchants;`.

Tokens are cached until shortly before expiration. Requests have finite timeouts
and safe error codes. Sync reads seven days, pages of 100, maximum ten pages;
oversized results fail before import. It imports successful balance-affecting
records without payer PII and skips duplicate external references. Reporting can
lag three hours; PayPal supports windows up to 31 days. Imported records are marked
sandbox, synthetic records remain synthetic. `paypal_verified` means a successful
sync exists in audit history, not a current connectivity probe.

**Blocker:** authorized reporting credentials were not configured for this task.
HTTP mock tests are not live verification. No real Sandbox success is claimed.
No disputes API, live endpoint, payment or submission action exists. Never supply
a PayPal account password.

## Troubleshooting and limitations

- 401: sign in to Next.js; Streamlit supports temporary demo mode only.
- 403: refresh the session and check CSRF/exact origins.
- 409: wait for analysis, reload a stale draft or use one backend process.
- 503/readiness: check migrations/storage permissions locally; do not expose secrets.
- OCR unavailable: install Tesseract, Poppler and Python OCR requirements on PATH,
  set OCR_ENABLED=true and restart. Handwriting/arbitrary poor scans are unverified.
- Driver errors involving bytes: use a UTF-8 database, not SQL_ASCII. Never destroy
  an existing database to change encoding.
- Limits: 10 MiB/file, 25 documents/transaction, 200,000 text characters. ASGI limits
  bound chunked bodies before multipart parsing; other mutation bodies cap at 256 KiB.
- Manual edits carry an unvalidated-claims warning. Approval acknowledges review,
  not factual truth; nothing is submitted.
- No distributed queue, malware scanning, hosted model, object-storage lifecycle,
  retention policy, password recovery or production load testing.
- Development `npm audit`: five high entries in the ESLint chain (braces →
  micromatch → fast-glob → Next ESLint plugin/config). The registry suggests an
  incompatible downgrade to Next ESLint 14.x, which was not applied. Production-only
  `npm audit --omit=dev` reports zero vulnerabilities.

## November authentication/Sandbox update

Settings now supports password changes; the admin CLI supports `reset-password`.
Both revoke all user sessions. Expired sessions return the dashboard to sign-in.
POST `/api/v1/auth/password` requires the current password plus a new 12–256
character password and CSRF. POST `/api/v1/integrations/paypal/check` checks current
credentials/reporting access without import. The dashboard remains reporting-only;
`python -m backend.sandbox_payments` is an explicit separate Sandbox-only payment
test utility. See PAYPAL-SANDBOX-SETUP.md for its workflow and verification limits.

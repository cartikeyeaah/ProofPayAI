# ProofPay AI

**Built by Team Lex · Payment evidence intelligence for merchants**

ProofPay AI brings transactions, invoices and delivery records into one workspace.
It extracts document facts, flags missing or conflicting evidence, and prepares a
response draft that the merchant can review, edit and approve.

**The merchant makes the final decision. Approval records a review; it does not
submit a dispute or send a response to PayPal.**

[Quick start](#quick-start) · [Demo walkthrough](#demo-walkthrough) ·
[PayPal Sandbox](#paypal-sandbox) · [Testing](#testing) · [Documentation](#documentation)

## What you can do

| Feature | Current behavior |
| --- | --- |
| Accounts | Register, sign in, sign out and change passwords; separate merchant workspaces |
| Transactions | Search, filter, sort and paginate records; open a synthetic test transaction without PayPal |
| Evidence | Upload PDF, PNG, JPEG or UTF-8 text; inspect private previews and processing status |
| Extraction | Parse text and text PDFs; optionally use local OCR for images and scanned PDFs |
| Analysis | Run the existing deterministic pipeline; view severity, explanations, recommendations and source references |
| Response drafts | Edit, save and approve drafts with revision history and review warnings |
| Persistence | Keep accounts, metadata, findings, drafts and approvals in PostgreSQL; store files privately |
| Sandbox | Check reporting access and manually sync eligible transactions; use a separate CLI for Sandbox payment tests |

The current analysis engine uses deterministic extraction and validation rules.
A hosted language model is not configured. Use synthetic documents for local testing.
Synthetic transactions and imported Sandbox transactions have separate origin labels.

## Demo walkthrough

1. Open the application and choose **Create an account**.
2. Enter your merchant name, email and a password of 12–256 characters; then sign in.
3. Click **Start test upload** on Dashboard, Transactions or Evidence. This creates
   or reuses a clearly labelled synthetic transaction and opens its evidence area.
4. Click **Choose file**, select a synthetic document, choose its document type,
   and click **Upload**.
5. Click **Analyze evidence**, then **Refresh status** until processing finishes.
6. Review the findings and open available source references to inspect the evidence.
7. Review or edit the draft, save it, and explicitly acknowledge the warnings before approval.

New registrations begin with an empty workspace. **Start test upload** provides a
way to try uploads immediately, without configuring PayPal. For a meaningful
comparison, use the displayed transaction reference, amount and currency in your
synthetic invoice—or deliberately vary them to demonstrate a mismatch.

## Quick start

### Prerequisites

- Python 3.11+; previously verified with Python 3.14.
- Node.js 24 and npm.
- A running PostgreSQL instance with a UTF-8 database; previously verified with PostgreSQL 14.24.
- Optional: Tesseract and Poppler for OCR.

Run commands from the repository root unless a different directory is shown.
On this machine, the repository is `/Users/karansingh/ProofPayAI`.

### 1. Install dependencies

```bash
cd /Users/karansingh/ProofPayAI
# Only if .venv does not already exist:
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt -r testing-ui/requirements.txt
```

If `.venv` already exists, reuse it and skip the creation command.

### 2. Configure PostgreSQL and your private environment

For a new installation, start PostgreSQL using your local service manager and
create a new database. Skip creation if your database already exists:

```bash
createdb -T template0 -E UTF8 proofpay
```

Create a private configuration file only if one does not exist:

```bash
[ -f .env ] || cp .env.example .env
chmod 600 .env
```

Edit `.env` with your own local database role, password, port and storage path:

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+psycopg://YOUR_ROLE:YOUR_PASSWORD@127.0.0.1:5432/proofpay
STORAGE_ROOT=/ABSOLUTE/PATH/TO/ProofPayAI/.local/private-evidence
FRONTEND_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
OCR_ENABLED=false
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_MERCHANT_ID=
```

Keep an existing working `.env` intact. Its database may use a different port or
name; use those configured values. `.env` is excluded from Git. Put real credentials
there, never in `.env.example` or frontend variables.

Apply migrations using the **same database URL** as `.env`:

```bash
DATABASE_URL='postgresql+psycopg://YOUR_ROLE:YOUR_PASSWORD@127.0.0.1:5432/proofpay' \
  python -m alembic upgrade head
```

Migrations create the isolated `proofpay` schema. The historical
`database/schema.sql` is not the current application migration.

### 3. Start the backend

```bash
source .venv/bin/activate
python -m backend.run
```

This entry point loads the private root `.env`; already-exported environment
variables take precedence. It starts one backend worker at port 8000.
Direct Uvicorn, Alembic and admin CLI commands require their environment variables
to be exported or provided explicitly.

### 4. Start the frontend in a second terminal

```bash
cd /Users/karansingh/ProofPayAI/frontend
npm ci
BACKEND_INTERNAL_URL=http://127.0.0.1:8000 npm run dev -- --hostname 127.0.0.1 --port 3000
```

| Local service | Address |
| --- | --- |
| Merchant dashboard | http://127.0.0.1:3000 |
| Interactive API documentation | http://127.0.0.1:8000/docs |
| Readiness: database and private storage | http://127.0.0.1:8000/api/v1/ready |
| Liveness | http://127.0.0.1:8000/api/v1/health |

Create an account from the login screen, then follow the demo walkthrough above.
Stop either foreground server with **Ctrl+C**. To restart later, repeat steps 3
and 4; dependency installation and migration setup are not needed on every start.

For the production frontend build, use these commands instead of `npm run dev`:

```bash
BACKEND_INTERNAL_URL=http://127.0.0.1:8000 npm run build
BACKEND_INTERNAL_URL=http://127.0.0.1:8000 npm run start -- --hostname 127.0.0.1 --port 3000
```

## Optional local OCR

Text files and text PDFs do not require OCR. For PNG, JPEG and scanned PDF extraction:

```bash
# macOS: install these only if they are missing.
brew install tesseract poppler
source .venv/bin/activate
python -m pip install -r ai_engine/requirements-ocr.txt
```

Set `OCR_ENABLED=true` in `.env` and restart the backend. Both `tesseract` and
`pdftoppm` must be available on PATH. Integrations shows OCR availability.
Recognition was verified using generated PNG, JPEG and scanned PDF fixtures;
quality on handwriting and arbitrary poor scans is not established.

Upload limits: **10 MiB per file**, **25 documents per transaction**, and
**200,000 characters for text evidence**. Upload stores the bytes; analysis performs extraction.

## PayPal Sandbox

Sandbox setup is optional for the synthetic evidence demo.

1. Create/select a Sandbox Business account and REST app in the PayPal Developer Dashboard.
2. Put that app's `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` in the backend `.env`.
3. Copy your workspace ID from Integrations into `PAYPAL_MERCHANT_ID`. This is the
   **local ProofPay merchant UUID**, not the PayPal seller ID.
4. Restart with `python -m backend.run`, refresh Integrations, and click **Check Sandbox connection**.
5. After a successful check, click **Sync Sandbox transactions**.

The reporting API requires the Transaction Search scope. Sync reads the last seven
days, imports supported completed records and skips duplicate references. Reporting
may lag behind newly captured payments. The separate Sandbox-only CLI supports a
fixed USD 1.00 create/approve/capture test flow.

See the [complete Sandbox setup and payment testing guide](docs/PAYPAL-SANDBOX-SETUP.md)
for account creation, permissions, commands and troubleshooting.

**Verification status:** adapter behavior has been tested with mocked HTTP responses.
The most recent real Sandbox attempt on 12 November 2026 failed with a connection
refusal before credentials could be validated. Successful external reporting sync
and payment capture are not yet verified. Configured credentials alone do not
establish a working connection.

## Authentication and data protection

- Passwords are salted and hashed with scrypt.
- Sessions use HttpOnly cookies; production mode enables Secure cookies and requires HTTPS origins.
- Authenticated mutations require CSRF protection; backend ownership checks scope data to the merchant.
- Password changes and logout revoke the user's sessions. Expired sessions return the UI to sign-in.
- Files are private and retrieved through authorized endpoints; secrets are not returned to the frontend.
- Manual draft edits carry a warning. Editing an approved draft resets approval.

A local administrator can provision accounts or reset passwords using
`python -m backend.manage`; export `DATABASE_URL` first. Password input is hidden.
Email verification and email-based password recovery are not implemented.

## Architecture

```mermaid
flowchart LR
    UI[Next.js merchant dashboard] -->|HTTP API| API[FastAPI: auth and merchant authorization]
    API --> DB[(PostgreSQL)]
    API --> Files[Private evidence storage]
    API --> Worker[Background supervisor]
    Worker --> Engine[Existing deterministic AI pipeline]
    Engine --> OCR[Optional local OCR]
    API --> Sandbox[PayPal Sandbox reporting]
```

The worker runs inside the single backend process and invokes the pipeline in a
separate subprocess with a 30-second deadline. There is no separate worker command.
Interrupted queued/processing runs become failed after restart and can be retried.
One backend process per database is enforced; this is not a distributed job queue.

```text
frontend/              Next.js UI, typed HTTP client and component tests
backend/app/           Authentication, evidence, analysis, drafts and integrations
backend/db/            PostgreSQL schema metadata and persistence
backend/integrations/  Sandbox HTTP adapter
backend/run.py         Local launcher that loads the private .env
backend/sandbox_payments.py  Separate Sandbox payment test utility
ai_engine/             Parsing, matching, validation and draft generation
contracts/             Shared fixtures and generated OpenAPI specification
database/migrations/   Alembic migrations
testing-ui/            Internal Streamlit dashboard for temporary demo mode
docs/                  Setup, architecture and verification reports
```

## Testing

Use a separate UTF-8 test database and stop any backend connected to that test
database before running integration tests. Tests create synthetic merchant data.

```bash
source .venv/bin/activate
# Create only if this test database does not exist:
createdb -T template0 -E UTF8 proofpay_test
export PROOFPAY_TEST_DATABASE_URL='postgresql+psycopg://YOUR_ROLE:YOUR_PASSWORD@127.0.0.1:5432/proofpay_test'
DATABASE_URL="$PROOFPAY_TEST_DATABASE_URL" python -m alembic upgrade head
DATABASE_URL="$PROOFPAY_TEST_DATABASE_URL" python -m alembic check
env -u DATABASE_URL python -m pytest backend/tests ai_engine/tests testing-ui -q
python -m backend.export_openapi
python -m pip check

cd frontend
npm run typecheck
npm run lint
npm test
BACKEND_INTERNAL_URL=http://127.0.0.1:8000 npm run build
```

Database tests explicitly skip without `PROOFPAY_TEST_DATABASE_URL`; OCR tests skip
when dependencies are unavailable. Skips do not verify those features. Historical
results and their scope are recorded in the reports below; counts may change as
new tests are added.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Cannot open the app | Keep both backend and frontend terminals running; check ports 8000 and 3000 |
| No file picker | Click **Start test upload**, or open a transaction, to reveal the Evidence library |
| No transactions after signup | A new workspace is empty; use **Start test upload** or an authorized Sandbox sync |
| Sandbox says Not configured | Read the missing-setting messages; fill the private `.env`, match the workspace ID and restart the backend |
| PayPal connection refused | Check network reachability to `api-m.sandbox.paypal.com`; credentials have not been validated if the connection cannot be established |
| Unauthorized/session expired | Sign in again; old sessions are revoked after logout or password changes |
| Draft save returns a conflict | Refresh the draft before editing; another revision may have been saved |
| OCR unavailable | Check OCR dependencies, PATH and `OCR_ENABLED`, then restart |
| Database lease already held | Stop the other backend using that database; use one worker |

For temporary demo mode, run direct Uvicorn with `DATABASE_URL` unset. It does not
load `.env`, has no persistent login, and loses demo data on restart. See the
[Streamlit guide](testing-ui/README.md) for the optional internal testing UI.

## Current limits

This is a local development and hackathon implementation. Production work still
includes a durable external queue, scalable SQL pagination/writes, malware scanning,
retention and backup policies, account recovery, and load/TLS deployment validation.
No hosted model, live payment flow, webhook processing or automated dispute
submission is implemented. See the deployment guide for detailed operational limits.

## Documentation

- [Sandbox setup and payment testing](docs/PAYPAL-SANDBOX-SETUP.md)
- [Deployment and environment variables](docs/DEPLOYMENT.md)
- [API contracts](docs/API_CONTRACT.md) and [database notes](docs/DATABASE.md)
- [Full-stack verification](docs/FULLSTACK-VERIFICATION.md)
- [Authentication and Sandbox verification](docs/AUTH-SANDBOX-VERIFICATION.md)
- [Local HTTP workflow verification](docs/LOCAL-RUN-VERIFICATION.md)
- [Team demo script](docs/PROJECT-DEMO-SCRIPT-HINGLISH.md)

**Team Lex · ProofPay AI — Evidence intelligence. Human decisions.**

# ProofPay AI

Merchant evidence workspace: Next.js dashboard, FastAPI, PostgreSQL, private local
files, and the existing deterministic AI engine. No hosted model, live payment or
dispute submission is implemented. Use synthetic evidence only. Sandbox imports,
when configured, are labelled separately from synthetic transactions.

## Local persistent workspace

Requires Python 3.11+ (verified 3.14), Node 24 (verified 24.13.1), and PostgreSQL
(verified 14.24). Reuse `.venv`; do not recreate an existing environment.
Start PostgreSQL with your installation's service command, then create a **new** database:

```bash
createdb -T template0 -E UTF8 proofpay
cd /Users/karansingh/ProofPayAI
source .venv/bin/activate
python -m pip install -r backend/requirements.txt -r testing-ui/requirements.txt
export DATABASE_URL='postgresql+psycopg://YOUR_LOCAL_ROLE@127.0.0.1:5432/proofpay'
export STORAGE_ROOT="$PWD/.local/private-evidence"
export FRONTEND_ORIGINS='http://127.0.0.1:3000,http://localhost:3000'
python -m alembic upgrade head
python -m alembic check
python -m backend.manage create-user --email merchant@example.test --merchant 'Synthetic Merchant'
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

The admin command prompts for a password and atomically creates a merchant/user
plus one explicitly synthetic transaction. Use your PostgreSQL role/port and secure
password configuration; never paste credentials into committed files. Existing
`.env` files are untouched and are **not automatically loaded by the backend**.

Frontend, in a second terminal:

```bash
cd /Users/karansingh/ProofPayAI/frontend
npm ci
BACKEND_INTERNAL_URL=http://127.0.0.1:8000 npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open http://127.0.0.1:3000 and sign in with the provisioned account. Select the
synthetic transaction, upload evidence, run analysis, refresh status, inspect
sources, edit/save the draft, and explicitly review/approve it. Approval does not
send anything. Editing an approved draft resets its approval.

For a local production-build check, replace `npm run dev` with:

```bash
BACKEND_INTERNAL_URL=http://127.0.0.1:8000 npm run build
BACKEND_INTERNAL_URL=http://127.0.0.1:8000 npm run start -- --hostname 127.0.0.1 --port 3000
```

## Demo mode and optional OCR

With DATABASE_URL unset, the backend starts an unauthenticated, temporary synthetic
demo. Bind it to loopback only. The dashboard prominently labels this mode;
restart loses demo data. The Streamlit dashboard remains available for this mode
only: see [testing-ui/README.md](testing-ui/README.md).

Text and text-PDF extraction work without OCR. To enable scanned PDFs, PNG and JPEG:

```bash
# macOS prerequisite installation, if not already installed:
brew install tesseract poppler
cd /Users/karansingh/ProofPayAI
source .venv/bin/activate
python -m pip install -r ai_engine/requirements-ocr.txt
export OCR_ENABLED=true
# Restart the backend in this shell.
```

`tesseract` and `pdftoppm` must be on PATH. Recognition was tested with generated
PNG, JPEG and scanned PDF fixtures; handwriting and arbitrary scans are not
validated. Missing tools produce an explicit unavailable status. The adapter calls
the existing engine interface; Member 2's algorithms are unchanged.

## Verification

Use a separate migrated test database; tests add synthetic merchant data.
Stop any backend using that database first (one supervisor owns the database).

```bash
cd /Users/karansingh/ProofPayAI
source .venv/bin/activate
export PROOFPAY_TEST_DATABASE_URL='postgresql+psycopg://YOUR_LOCAL_ROLE@127.0.0.1:5432/proofpay_test'
DATABASE_URL="$PROOFPAY_TEST_DATABASE_URL" python -m alembic upgrade head
DATABASE_URL="$PROOFPAY_TEST_DATABASE_URL" python -m alembic check
# Keep DATABASE_URL unset for the test runner; its explicit test variable activates DB tests.
env -u DATABASE_URL python -m pytest backend/tests ai_engine/tests testing-ui -q
python -m backend.export_openapi
python -m pip check
cd frontend
npm run typecheck
npm run lint
npm test
BACKEND_INTERNAL_URL=http://127.0.0.1:8000 npm run build
```

See [docs/FULLSTACK-VERIFICATION.md](docs/FULLSTACK-VERIFICATION.md) for actual
results, browser verification and limitations. DB tests skip explicitly without a
test URL; OCR tests skip without local dependencies. A skipped test is not a pass.

## Architecture and operation

- `frontend/`: typed HTTP client, responsive merchant dashboard and component tests.
- `backend/app/`: API, cookie sessions/CSRF, private uploads, supervised analysis,
  drafts, approval and integration status.
- `backend/db/`: PostgreSQL persistence, merchant scoping and restart recovery.
- `database/migrations/`: Alembic isolated `proofpay` schema; historical
  `database/schema.sql` is not the deployed application migration.
- `ai_engine/`: existing deterministic parsing, matching, validation and drafting.
- `contracts/openapi.yaml`: generated public API documentation; live `/docs` and
  `/openapi.json` are available on the backend.
- [Deployment and Sandbox setup](docs/DEPLOYMENT.md),
  [database model](docs/DATABASE.md), [API notes](docs/API_CONTRACT.md).

The worker runs inside the single backend process and supervises each pipeline in
a separate killable subprocess (30-second deadline). There is no second worker
command. Persisted interrupted jobs become failed after restart; retry creates a
new run. This is a hackathon deployment, not a distributed durable job queue.

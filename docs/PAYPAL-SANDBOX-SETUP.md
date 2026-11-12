# Authentication and PayPal Sandbox local setup

Updated 2026-11-12. Authentication uses local administrator-provisioned accounts;
it is separate from PayPal developer login and Sandbox buyer/seller accounts.
The dashboard supports reporting; a separate backend CLI tests Sandbox payments.
Neither supports live payments or dispute submission.

## 1. Start the authenticated application

Use the root README to create a UTF-8 PostgreSQL database and install requirements.
The role in `DATABASE_URL` must be allowed to create the application schema. It is
normally the owner of the `proofpay` database, not necessarily the PostgreSQL
superuser role. Confirm the target before migrating:

```bash
psql -h 127.0.0.1 -U YOUR_LOCAL_ROLE -d proofpay \
  -c "SELECT current_database(), current_user;"
```

From the repository, reuse `.venv`:

```bash
cd /Users/karansingh/ProofPayAI
source .venv/bin/activate
export DATABASE_URL='postgresql+psycopg://YOUR_LOCAL_ROLE@127.0.0.1:5432/proofpay'
export STORAGE_ROOT="$PWD/.local/private-evidence"
export FRONTEND_ORIGINS='http://127.0.0.1:3000,http://localhost:3000'
export APP_ENV=development
python -m alembic upgrade head
python -m backend.manage create-user --email merchant@example.test --merchant 'Test Merchant'
```

Replace DB placeholders with your own local connection. Password input for the
new application account is hidden and confirmed. Keep DATABASE_URL set: omitting
it deliberately selects unauthenticated temporary demo mode, not account login.
Use distinct credentials for application accounts and PayPal accounts.

After step 3 below, start the backend in this same shell:

```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

In a second terminal:

```bash
cd /Users/karansingh/ProofPayAI/frontend
npm ci
BACKEND_INTERNAL_URL=http://127.0.0.1:8000 npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open http://127.0.0.1:3000 and sign in. Settings → Change password requires the
current password, validates confirmation and revokes every session after success.
Sign in again using the new password. Sign out also revokes all account sessions.
Expired sessions return the UI to login. CSRF and merchant ownership are enforced
on the backend; another merchant cannot access your documents or transactions.

For forgotten application passwords, the local administrator can run:

```bash
python -m backend.manage reset-password --email merchant@example.test
```

It prompts for the replacement password and revokes sessions. You can also use Create an account on the login screen. New registrations get an
empty, separate merchant workspace. Email verification, email password reset and
PayPal OAuth sign-in are not implemented. For public deployment, HTTPS and
APP_ENV=production are required; production refuses missing PostgreSQL or HTTP origins.

## 2. Create PayPal Sandbox accounts and app

1. Sign in to the [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/)
   using your developer account.
2. Select **Sandbox**. Under testing accounts, create or select a **Business**
   account (seller) and a separate **Personal** account (buyer).
3. Open **Apps & Credentials**, remain in Sandbox, and create/select a REST app
   associated with that Business account.
4. Copy that app's **Client ID** and reveal its **Secret**. The secret is the client
   secret, not a PayPal account password. Store both only on the backend.
5. For reporting, enable Transaction Search/reporting permissions when offered for
   the app. The required scope is
   `https://uri.paypal.com/services/reporting/search/read`. Payment permission alone
   does not establish reporting access. If the capability is unavailable, contact
   PayPal developer support; do not claim a successful reporting integration.

References: [Sandbox accounts](https://developer.paypal.com/sandbox-testing/accounts),
[app credentials](https://developer.paypal.com/studio/checkout/standard/getstarted),
[reporting API](https://developer.paypal.com/api/transaction-search/v1/search-get).

## 3. Configure backend environment variables

In the backend terminal, set the credentials without putting their values in shell
history (these prompts are for the macOS zsh shell):

```zsh
read 'PAYPAL_CLIENT_ID?Sandbox Client ID: '
read -s 'PAYPAL_CLIENT_SECRET?Sandbox client secret (hidden): '
echo
export PAYPAL_CLIENT_ID PAYPAL_CLIENT_SECRET
```

Set PAYPAL_MERCHANT_ID to the **local ProofPay merchant UUID**, not the PayPal seller
ID, email or Client ID. The application stores merchants and users in the
`proofpay` schema created by Alembic. Do not query the legacy
`database/schema.sql` design or assume `public.merchants` exists.

First check whether the account exists and retrieve the UUID:

```sql
SELECT current_database(), current_schema();

SELECT m.id AS merchant_id, m.name AS merchant_name, u.email
FROM proofpay.merchants AS m
JOIN proofpay.users AS u ON u.merchant_id = m.id
WHERE lower(u.email) = lower('merchant@example.test');
```

The query must return exactly one row. If it returns no rows, this database has
no account for that email. Create the account once through the dashboard's
registration flow or the administrator command below, then rerun the query; do
not insert a merchant directly and do not run account creation twice:

```bash
python -m backend.manage create-user \
  --email merchant@example.test --merchant 'Test Merchant'
```

The command prompts for the application password and creates one merchant, one
user, and one explicitly synthetic transaction in one transaction. If the email
already exists, stop and use the query result instead.

Then in the backend shell, export the UUID returned in `merchant_id`:

```bash
export PAYPAL_MERCHANT_ID='MERCHANT_UUID_FROM_QUERY'
```

Restart the backend after configuration changes. One app is bound to one local
merchant; other merchants cannot use its credentials. Do not set these credentials
in frontend variables or NEXT_PUBLIC_ variables. This project hardcodes the Sandbox
API host `https://api-m.sandbox.paypal.com`; there is no environment toggle to live.
The backend does not automatically load `.env`. If using an ignored local env file,
load it explicitly and quote values correctly; do not commit it. `.env.example`
contains placeholders only. Avoid printing environment values or access tokens.

Verify only the non-secret configuration state from the backend shell:

```bash
python -c 'import os; print({k: bool(os.getenv(k)) for k in ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "PAYPAL_MERCHANT_ID")})'
```

The output must show `True` for all three keys. Never print their values.

## 4. Verify reporting connectivity

Sign into the app, select **Integrations**, then **Check Sandbox connection**.
This gets a fresh token and makes a small reporting request without importing data.
Success means reporting access actually worked at that moment. The separate sync
status records historical successful imports; it is not a continual health probe.

Alternatively, from the backend shell with credentials exported:

```bash
python -m backend.sandbox_payments check
```

Expected success: `status: connected`, `environment: sandbox`, `reporting_access: true`.
A missing scope or permission error must be resolved before reporting can be verified.
A successful token or checkout payment alone is not proof of reporting access.

## 5. Create a USD 1.00 Sandbox test payment

The CLI sends server-side Orders v2 requests; no app payment endpoint is exposed.
It only supports a fixed USD 1.00 test amount and the Sandbox host. Keep the same
request ID when retrying the same operation, particularly after a timeout.

```bash
CREATE_REQUEST_ID=$(python -c 'import uuid; print(uuid.uuid4())')
python -m backend.sandbox_payments create --request-id "$CREATE_REQUEST_ID" --return-url http://127.0.0.1:3000/
```

Save the returned `order_id` and `approval_url`. Do not generate another request ID
merely because the response was lost; retry with the existing ID first. A newly
created order is not yet a completed payment.

1. Open the returned **sandbox.paypal.com** approval URL in your browser.
2. Sign in with the **Sandbox Personal buyer** from step 2, not the seller account
   or your real PayPal account.
3. Review the USD 1.00 test order and approve it with Sandbox funds.
4. Return to the local app. This redirect is not proof of capture; the app does not
   automatically capture or interpret return query parameters.
5. Check and explicitly capture the order from the backend terminal:

```bash
python -m backend.sandbox_payments status --order-id ORDER_ID_FROM_CREATE
CAPTURE_REQUEST_ID=$(python -c 'import uuid; print(uuid.uuid4())')
python -m backend.sandbox_payments capture --order-id ORDER_ID_FROM_CREATE --request-id "$CAPTURE_REQUEST_ID"
python -m backend.sandbox_payments status --order-id ORDER_ID_FROM_CREATE
```

Reuse CAPTURE_REQUEST_ID for retries of that capture; do not reuse the create ID.
A successful payment requires a completed capture, not just order approval. Inspect
both order status and capture status/ID; pending captures are not reported as settled.
Check the seller's Sandbox activity as an independent confirmation. The CLI emits
only IDs/status and approval URL, not bearer tokens, secrets or payer details.

References: [create order](https://developer.paypal.com/api/orders/v2/orders-create),
[capture order](https://developer.paypal.com/api/orders/v2/orders-capture).

## 6. Import the captured transaction and test evidence

1. Open Integrations → **Sync Sandbox transactions**. It imports eligible completed
   balance-affecting records from the last seven days and marks them `sandbox`.
2. If the new capture is not listed, allow for reporting delay (up to three hours)
   and retry later. The order ID and capture/reporting transaction reference are
   distinct identifiers; use the imported transaction's actual reference.
3. Repeating sync should import zero duplicates. Synthetic seed rows stay labelled
   `synthetic` and are never silently converted into Sandbox transactions.
4. Open the imported record, upload synthetic test evidence using its reference,
   run analysis, inspect sources, edit and approve a draft. No dispute is submitted.

## 7. Negative checks and troubleshooting

- Incorrect app secret: safe permission error; no raw credentials shown.
- Missing reporting scope: checkout may work while check/sync fails; request access.
- Wrong local merchant binding: integration remains unavailable for that account.
- Capture before buyer approval: safe order-not-ready error. Approve then retry.
- Canceled buyer approval: do not capture; start a new intentional test if needed.
- Timeout: query order status and reuse the same operation UUID on retry.
- HTTP 429: wait before retrying; do not create a retry loop.
- Reporting window exceeds 1,000 records: no partial import; narrower configurable
  windows are not yet implemented.
- Auth fails after password change: this is expected; all old sessions are invalid.
- Application API rejects mutations: confirm exact FRONTEND_ORIGINS and reload the
  session; do not disable CSRF or merchant checks.

## Verification boundary

Local authentication and PostgreSQL tests, frontend checks and mocked PayPal
requests are automated. Actual Sandbox credentials were absent during development.
**Real PayPal connectivity, buyer approval and payment capture remain unverified
until you run steps 4–6 with authorized Sandbox credentials.** No real funds are
required. Public checkout, live payments, webhook processing, automated recurring
sync and dispute submission are outside this local development implementation.

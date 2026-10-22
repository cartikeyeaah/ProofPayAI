# ProofPay AI · Evidence Room

ProofPay is a payment evidence intelligence workspace. This frontend uses a calm, forensic “Evidence Room” concept: green-black ledger surfaces, warm paper text, and a chartreuse signal color. Serif editorial headlines pair with compact ledger-style data. The three signature interactions are a source-linked evidence timeline, clickable citations that open a source viewer, and a readiness strip that makes the missing delivery receipt visible.

## Run locally

```bash
cd frontend
npm install
npm run dev
```

The project is currently scaffolded on Next.js 16 App Router with TypeScript strict mode and Tailwind CSS v4. It uses the repository’s existing package versions. All sample identities and transaction records are synthetic.

## Environment

Copy `.env.example` to `.env.local` when connecting to the FastAPI service.

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_USE_MOCK` | `true` | Select the seeded demo data mode. |
| `NEXT_PUBLIC_API_BASE_URL` | empty | Base URL for the FastAPI service when mock mode is disabled. |

`src/lib/api/client.ts` defines the shared API contract and HTTP endpoint mapping; `src/lib/api/mock-api.ts` provides a typed mock implementation. The showcase screens use the seeded demo data directly so the entire case can be demonstrated offline.

## FastAPI endpoint mapping

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/transactions` | List transactions |
| GET | `/transactions/{id}` | Get a transaction |
| POST | `/transactions/{id}/evidence` | Upload evidence (multipart) |
| GET | `/transactions/{id}/evidence` | List case evidence |
| DELETE | `/evidence/{id}` | Delete evidence |
| POST | `/transactions/{id}/analyze` | Start analysis |
| GET | `/transactions/{id}/analysis` | Get analysis and progress |
| POST | `/transactions/{id}/report/generate` | Generate a draft response |
| PUT | `/reports/{id}` | Save report edits |
| POST | `/reports/{id}/approve` | Approve a draft for merchant submission |
| GET | `/audit?transactionId=` | Read case audit events |
| GET | `/integrations/paypal/status` | Read PayPal connection status |
| POST | `/integrations/paypal/connect` | Start PayPal connection |

## Two-minute demo

1. Open **Start the demo case** on the dashboard.
2. Review the $150.00 disputed payment and the 3-of-4 evidence readiness strip.
3. Select **Evidence** to inspect the seeded invoice, order confirmation, and customer message. Upload accepts PDF, PNG, JPG, TXT, and EML files up to 10 MB.
4. Select **Analysis** and open a citation chip. The source viewer shows the excerpt tied to the finding.
5. Select **Report**, edit the draft, mark the critical finding reviewed, acknowledge the approval statement, then choose **Approve & mark ready**.
6. Confirm the action. The case is marked ready for submission; it is never sent to PayPal by this UI.

## Safety and demo notes

- No secrets or PayPal credentials belong in this frontend.
- Every seeded analysis finding has a typed source reference; uncertain matches are visibly flagged.
- Approval is explicit, requires review of critical/high findings and an acknowledgement, and writes only a ready state in this demo.
- Email is masked by default. No dispute outcome prediction is shown.
- The demo records are synthetic and labeled as such in the workspace footer.

## Checks

```bash
npm run lint
npm run build
```

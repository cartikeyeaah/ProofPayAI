# API contract v0.1.0

The canonical machine-readable contract is `contracts/openapi.yaml`, generated from
Pydantic models and FastAPI routes by `python -m backend.export_openapi` from the
repository root. `/openapi.json` serves the runtime equivalent; `/docs` serves Swagger.
Tests assert the export matches runtime and validates as OpenAPI 3.1.
Base URL: `http://127.0.0.1:8000`. JSON request/response bodies; no authentication yet.

| Method | Path | Success | Body |
| --- | --- | --- | --- |
| GET | `/api/v1/health` | 200 | `{ "status": "ok", "mode": "mock" }` |
| GET | `/api/v1/transactions` | 200 | Array of Transaction (no pagination) |
| GET | `/api/v1/transactions/{transaction_id}` | 200 | Transaction |
| POST | `/api/v1/transactions/{transaction_id}/analyze` | 202 | Analysis, initially queued |
| GET | `/api/v1/analysis/{analysis_id}` | 200 | Analysis |
| GET | `/api/v1/transactions/{transaction_id}/demo-analysis` | 200 | Static completed Analysis fixture |

POST requires `Content-Type: application/json` and body `{}`. No optional request
fields are supported yet; unknown fields, absent/null bodies, malformed JSON, and
wrong types return 422. This intentionally reserves the integration boundary without
inventing evidence input fields for Member 2. GET routes have no body or supported
query parameters (unknown query parameters are ignored). IDs are opaque strings of
1–100 ASCII letters, digits, underscores or hyphens; invalid path IDs return 422.
Well-formed unknown IDs return 404. Each POST creates a separate job; no idempotency
or deduplication is provided.

## Transaction

Every field is required and non-null. Extra model fields are forbidden.

| Field | JSON type | Meaning |
| --- | --- | --- |
| id | string | Opaque API transaction identifier |
| paypal_transaction_id | string | Synthetic provider reference |
| amount | string | Exact signed decimal with two fractional digits, max ten integer digits; never a float |
| currency | string | Three uppercase letters (fixture: USD; no currency registry validation yet) |
| status | string | Day 1 supports `COMPLETED` only |
| transaction_date | string | Timezone-aware ISO 8601 date-time |
| evidence_count | integer | Nonnegative synthetic count |

`contracts/sample-transaction.json` is the exact served transaction. API fixtures
use readable IDs; future database UUIDs can be serialized as API strings. Do not
parse API IDs or assume demo prefixes in client code. Consumers must preserve amount
strings or parse them with a decimal library rather than binary floating point.

## Analysis and Finding

Every Analysis field is required. Only `draft_response` is nullable (string or null).
There are no optional fields in Day 1 responses.

| Field | JSON type | Meaning |
| --- | --- | --- |
| analysis_id | string | Opaque ID; mock jobs use `analysis_` plus a random UUID |
| transaction_id | string | Related transaction ID |
| status | string enum | `queued`, `processing`, `completed`, `failed` |
| findings | array of Finding | Empty for queued jobs |
| draft_response | string or null | Always null in current implementation |
| merchant_approval_required | boolean | Always true; no send/submission action exists |

Finding fields are all required and non-null: `id` (opaque string), `issue_type`
(string, currently open vocabulary), `severity` (`low`, `medium`, or `high`),
`explanation` (string), `source_ids` (array of opaque document ID strings), and
`recommendation` (string). `contracts/sample-analysis.json` is a static fixture only.
`doc_demo_001` is illustrative; no document retrieval endpoint exists.

A created job can be retrieved with the returned `analysis_id` and remains queued.
The demo ID is not inserted into job storage; retrieving `analysis_demo_001` through
`/analysis/{analysis_id}` returns 404. The demo endpoint never changes a job.

## Errors

All application-generated errors use this structure:

```json
{"error":{"code":"TRANSACTION_NOT_FOUND","message":"The requested transaction was not found.","request_id":"req_demo_001"}}
```

Actual request IDs use `req_` plus a newly generated UUID and are also returned in
`X-Request-ID` on every response. Caller-provided request IDs are not trusted/reused.
Validation errors use a generic message without reflecting request data.

| HTTP | Code | When |
| --- | --- | --- |
| 404 | TRANSACTION_NOT_FOUND | Unknown transaction in detail, analyze, or demo route |
| 404 | ANALYSIS_NOT_FOUND | Unknown job ID |
| 422 | VALIDATION_ERROR | Invalid path ID, body, missing body, or malformed JSON |
| 404 / 405 | HTTP_ERROR | Unmatched URL / unsupported HTTP method |
| 500 | INTERNAL_ERROR | Unexpected application exception; internals are not exposed |

CORS preflight is transport middleware and may return its own plain-text 200/400;
server/proxy-level malformed HTTP is outside this application error contract.
CORS allows only `http://localhost:8501` and `http://127.0.0.1:8501`, GET/POST,
Content-Type, no credentials, and exposes X-Request-ID.

## Member handoff

Member 2 should agree a versioned evidence input/job processing interface before
replacing the in-memory boundary in `routes.py`. Future workers will need durable
job creation, status transitions, failure semantics, and provenance-backed findings.
Those transitions and a failure-detail response are not implemented. Do not interpret
queued records as processed, and do not generate findings in this foundation.
Member 3 can use the OpenAPI schemas and fixtures independently of Streamlit.
Authentication, merchant scope, pagination, evidence upload, and PayPal integration
require later contracts and implementation. No endpoint submits dispute responses.

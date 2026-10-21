> Updated 2026-10-22: the historical foundation below is retained for context.
> Current behavior is described by the full-stack section below, README.md and
> DEPLOYMENT.md. Earlier missing-feature statements describe the previous version.

# API contract v0.2.0

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
| evidence_count | integer | Nonnegative count of actually uploaded documents |

`contracts/sample-transaction.json` remains an illustrative fixture. The served
transaction uses its fields but derives evidence_count from uploads (initially 0). API fixtures
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
| draft_response | string or null | Source-backed deterministic draft when available |
| merchant_approval_required | boolean | Always true; no send/submission action exists |

Finding fields are all required and non-null: `id` (opaque string), `issue_type`
(string, currently open vocabulary), `severity` (`low`, `medium`, or `high`),
`explanation` (string), `source_ids` (array of opaque document ID strings), and
`recommendation` (string). `contracts/sample-analysis.json` is a static fixture only.
`doc_demo_001` is illustrative; no document retrieval endpoint exists.

A created job returns queued and can be retrieved with the returned `analysis_id`.
A subprocess runs the existing engine; GET may show processing, completed, or failed.
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

## Evidence and integration endpoints

Additive endpoints support the ingestion/integration requested in this task. Existing
Transaction, Analysis, Finding, Health and engine v1 schemas and route paths are unchanged.
No extra fields are accepted by POST analyze: it still requires `{}` and snapshots
all currently uploaded evidence for the selected transaction. Delivery proof is
required by the engine's existing default. There is no per-request override yet.

| Method | Path | Success / schema |
| --- | --- | --- |
| GET | `/api/v1/capabilities` | 200 Capabilities: engine ai_engine_v1, synthetic data, temporary persistence, OCR unavailable, uploads true |
| POST | `/api/v1/transactions/{transaction_id}/documents` | 201 EvidenceMetadata; multipart file + document_type required |
| GET | `/api/v1/transactions/{transaction_id}/documents` | 200 array of EvidenceMetadata |
| GET | `/api/v1/transactions/{transaction_id}/documents/{document_id}` | 200 EvidenceMetadata |
| GET | `/api/v1/analysis/{analysis_id}/details` | 200 AnalysisDetails |

EvidenceMetadata has required id, transaction_id, filename, document_type, media_type,
and size_bytes. It returns upload_status=`stored`, processing_status (not_processed,
processing, parsed, unsupported, failed, duplicate), nullable analysis_id, issue_codes
array, and facts array using the existing ExtractedFact schema. Source spans index
parsed Unicode text as documented in AI_ENGINE.md. File names are display metadata;
server-generated IDs are storage keys. Raw paths and uploaded bytes are never returned.

AnalysisDetails includes analysis_id, engine=`ai_engine_v1`, nullable failure_code,
and nullable result using the existing PipelineResult schema. A queued/processing job
has no result. A valid failed engine run can have a result with processing issues.
Worker failures return PIPELINE_TIMEOUT, PIPELINE_ERROR, or INVALID_PIPELINE_OUTPUT
and no result; raw exceptions are not exposed. Details includes sensitive parsed text
when present: use only synthetic development data. Demo fixtures have no details record.

Upload accepts application/pdf, image/png, image/jpeg, and UTF-8 text/plain. Binary
signatures must match the declared type. Maximum 10 MiB per file; text additionally
has a 200,000-character limit. At most 25 documents per transaction. These are stored
file limits, not a production gateway multipart request limit. Image signature checks
are not full decoding, malware scanning, or proof of parse success.

Additional structured errors: 413 INVALID_FILE_SIZE, 415 UNSUPPORTED_FILE_TYPE,
422 INVALID_FILE_SIGNATURE / INVALID_TEXT, 409 DOCUMENT_LIMIT / ANALYSIS_ACTIVE,
and 404 DOCUMENT_NOT_FOUND. Invalid multipart fields use the existing 422
VALIDATION_ERROR envelope. Only one analysis runs at a time; uploads to its transaction
are rejected until completion. Metadata reflects each document's latest analysis;
per-analysis details retain the snapshot result until restart. No deletion API yet.

## Member handoff

The backend now calls the existing engine v1 interface without changing its algorithms.
Member 3 can use the exported OpenAPI and stable document IDs. Health mode remains
mock for compatibility with synthetic storage; consult capabilities/details to identify
actual pipeline execution. Production authentication, scoped persistence, durable
workers and OCR adapters remain separate integration work. No payment or submission
endpoint exists.

## Additive full-stack API (2026-10-22)

Existing Transaction, Analysis and Finding shapes/routes are preserved. Persistent
mode requires a session; demo mode retains prior access. Complete schemas are in
`contracts/openapi.yaml`.

- POST `/api/v1/auth/login`, GET `/api/v1/auth/me`, POST `/api/v1/auth/logout`.
- GET `/api/v1/ready`, `/api/v1/overview`, `/api/v1/integrations`.
- GET `/api/v1/transaction-page`: q, page, page_size (1–100), sort (date/amount/id),
  direction (asc/desc), analyzed (all/yes/no). Returns items, total, pagination and origins.
- GET `/api/v1/transactions/{id}/analyses` for history.
- GET `/api/v1/transactions/{id}/documents/{document_id}/content` for private bytes.
- GET/PUT `/api/v1/analysis/{id}/draft`; PUT text and expected version.
- POST `/api/v1/analysis/{id}/draft/approve`; expected version and acknowledge_warnings.
  Empty text is rejected; stale versions return 409.
- GET `/api/v1/analysis/{id}/audit` returns events and draft revisions.
- POST `/api/v1/integrations/paypal/sync` requires merchant-bound Sandbox credentials.

Authenticated mutations require X-CSRF-Token from login/me. POST analyze optionally
accepts Idempotency-Key; replay returns the same job. 401/403/429/503 use sanitized
errors. No submission route exists. Static demo output is not pipeline execution.
Legacy capabilities data_mode describes the synthetic foundation; use per-record
origins and integrations status when optional Sandbox data is present.

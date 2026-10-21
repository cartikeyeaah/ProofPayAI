# Integration audit — 2026-10-22 (before integration changes)

Inspected backend, ai_engine, testing-ui, contracts, database, docs, root README,
and dependency/test files. Existing staged AI-engine/resources/frontend changes and
unstaged testing UI changes are present and will be preserved.

| Area | Finding before changes |
| --- | --- |
| Analysis route | `backend/app/routes.py:analyze` creates an in-memory queued Analysis and never calls a worker or engine. GET reads that record. |
| Demo | `/transactions/{id}/demo-analysis` returns `sample-analysis.json`. Completed findings displayed through this route are fixtures. |
| Actual engine | `ai_engine.pipeline.run_pipeline(PipelineInput)` is implemented; returns PipelineResult with public Analysis, pages, facts, matches, provenance, claims and issues. `validate_output` checks identity, sources, facts and drafts. No hosted model is called. |
| Parsing/OCR | Library parses text and text PDFs; PNG/JPEG require injected OCR. Scanned PDFs require a separate OCR adapter. Unsupported OCR returns explicit issues. |
| Upload | No upload, document list/detail, or evidence-to-transaction association exists in HTTP backend. UI correctly marks these unavailable. |
| Storage | Transactions/jobs are process-local dictionaries. No document bytes/metadata or pipeline results are persisted. PostgreSQL SQL is a foundation only. |
| Contracts | Six existing HTTP routes, required empty POST body, Analysis/Finding/Transaction schemas. Engine v1 input/result JSON schemas are separate library interfaces. |
| Tests | Backend tests validate queued-only behavior and demo contracts. Engine tests exercise actual deterministic extraction/rules/provenance and PDF/OCR boundaries separately. UI tests use HTTP, with injected results for processing/completed/failed display. These do not prove end-to-end engine integration. |
| Unverified | Real HTTP -> evidence -> pipeline -> result path, upload limits/storage, processing timeouts and backend validation of worker output. Real OCR recognition and hosted-model integration are not verified. |

## Targeted implementation plan

Keep existing public schemas, fixtures, and route paths. Connect analyze to the
existing engine using its v1 interface in a bounded subprocess. Add only the
upload/list/detail and diagnostics/capability routes needed by this request; export
OpenAPI for these additive interfaces. Separate stored upload status, parse status,
and analysis status. Validate worker output with Member 2's validator. Preserve the
static demo route with explicit labeling. Use private temporary storage and disclose
non-durability; production PostgreSQL/object storage/authentication remain gaps.
Do not modify Member 2's algorithms or the Next.js frontend. Add actual-pipeline
HTTP integration tests, fault injection tests, and update the internal dashboard.

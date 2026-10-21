# Full-stack audit and implementation checklist — 2026-10-22

Pre-change audit: existing six-route mock foundation has been extended with evidence ingestion,
capabilities and analysis details. POST analyze snapshots evidence and supervises a
killable subprocess invoking Member 2's actual pipeline; output provenance is
validated. Files are private temporary files; all metadata/results are in memory.
No authentication, durable worker or PostgreSQL migrations currently exist.
The SQL file is unapplied foundation DDL. Integration report records 85 tests.
Next.js 16.4.2/React 19 starter exists; frontend/package*.json has staged teammate
changes. AI engine and resources are staged; backend/UI integration is unstaged.
All will be preserved. Repository reports are in docs/; copies in chat outputs
are not the repository source of truth.

- [x] PostgreSQL migrations, durable merchant data and restart recovery.
- [x] Cookie sessions, CSRF, merchant authorization and private previews.
- [x] Draft revisions, approval, audit history and duplicate-request protection.
- [x] Optional local OCR through the existing engine interface.
- [x] Sandbox adapter and mock tests; external verification blocked on credentials.
- [x] Existing Next.js frontend: accessible responsive merchant dashboard.
- [x] Backend/AI/UI/database/frontend checks and actual workflow verification.
- [x] Accurate setup, security, deployment and limitation documentation.

Compatibility: existing JSON shapes/routes stay intact in local demo mode; protected
persistent mode requires a session. New functionality uses additive endpoints.
No breaking shared response-schema changes are planned. No commits or pushes.

# Integration verification — 2026-10-22

## Outcome

The pre-change audit is in INTEGRATION-AUDIT.md. The actual analysis path is now:
HTTP POST analyze -> snapshot of transaction and stored evidence -> queued record ->
background supervisor -> processing -> subprocess invoking the existing
`ai_engine.run_pipeline(PipelineInput)` -> PipelineResult validation and existing
`validate_output` checks -> completed/failed record and document facts/status.
No Member 2 algorithms, existing public model schemas, engine schemas, static JSON
fixtures, or Next.js code were modified. The existing route paths remain; ingestion,
capabilities and details endpoints are additive. OpenAPI was regenerated.

## Verification performed

- `python -m pytest backend/tests ai_engine/tests testing-ui -q`: **85 passed**, one
  upstream Starlette TestClient/httpx deprecation warning, Python 3.14.0.
- Actual deterministic pipeline tests use synthetic PDF/text evidence, not a fake
  model. They verify amount/date mismatches, missing proof, complete evidence with
  no false missing alerts, actual source IDs and exact quote provenance.
- File tests cover signatures, media types, empty/oversized files, UTF-8, required
  fields, 25-document limit, transaction association, 0600 private files, no public
  file route, and shutdown cleanup. PNG/scanned PDF tests verify unsupported OCR;
  corrupt PDFs are failed parsing, not successful extraction.
- Worker tests verify observable processing while health remains responsive,
  concurrent job rejection, subprocess timeout, exceptions, invalid output and
  invented source rejection. Failure diagnostics do not expose raw exceptions.
- UI integration uses actual loopback HTTP upload and pipeline results, plus
  explicit synthetic server responses to cover every display state. Client errors,
  schema validation and retry behavior remain covered.
- `python -m pip check` and `git diff --check` passed.
- Started isolated local Uvicorn (8001) and Streamlit (8502) servers. Uploaded a
  generated synthetic text PDF through HTTP, then clicked Create analysis job and
  Refresh job status in the browser. Observed queued -> completed, parsed evidence,
  extracted facts, amount mismatch (151.00 vs 150.00), the actual uploaded document
  ID, missing_delivery_proof with no fabricated source, and a source-backed draft
  requiring merchant approval. Saved a screenshot of the completed findings.
  The native browser file-picker upload action was not separately exercised;
  multipart upload was verified over HTTP and through the dashboard's client.
- Temporary verification servers were stopped. The user's pre-existing dashboard
  server was not stopped or reconfigured. Restart existing services to pick up changes.

## Files changed for this integration

New:
- backend/app/evidence.py
- backend/app/integration_schemas.py
- backend/app/worker.py
- backend/tests/test_integration.py
- docs/INTEGRATION-AUDIT.md
- docs/INTEGRATION-VERIFICATION.md

Updated:
- backend/app/main.py
- backend/app/mock_data.py
- backend/app/routes.py
- backend/requirements.txt
- backend/tests/test_api.py
- contracts/openapi.yaml
- testing-ui/app.py
- testing-ui/api_client.py
- testing-ui/test_dashboard.py
- testing-ui/README.md
- README.md
- docs/API_CONTRACT.md
- docs/DATABASE.md

Prior staged AI-engine/resources/frontend work and prior testing-ui requirements and
client-test additions remain preserved. No commit, push or staging was performed.

## Manual reproduction

From /Users/karansingh/ProofPayAI, activate `.venv`, install
`-r backend/requirements.txt -r testing-ui/requirements.txt`, and run:

```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

In another activated terminal in the same repository:

```bash
python -m streamlit run testing-ui/app.py --server.address 127.0.0.1 --server.port 8501 --server.maxUploadSize 10
```

1. Open http://127.0.0.1:8501 and check backend health.
2. Select txn_demo_001. Upload a synthetic UTF-8 invoice text file containing:
   `Transaction ID: DEMO-1001`, `Total: USD 151.00`, `Order Date: 2026-10-15`
   on separate lines, choosing document type invoice.
3. Verify upload stored / parsing not_processed. Create analysis and refresh status.
4. Verify completed, amount_mismatch with the uploaded ID, missing_delivery_proof,
   and approval required. Refresh evidence to inspect facts/source spans.
5. Upload synthetic delivery text with `Transaction ID: DEMO-1001`,
   `Delivery Status: delivered`, `Delivery Date: 2026-10-17` on separate lines,
   choosing delivery_record. Create another job: missing delivery should disappear;
   the invoice amount mismatch should remain.
6. Upload a synthetic PNG and analyze again; its processing status must be
   unsupported with IMAGE_OCR_REQUIRED, not parsed. Other valid documents may still
   produce a completed analysis with explicit unreadable-evidence findings.
7. Use Retrieve static demo analysis to see the separate fixture, then try an invalid
   backend URL and verify safe errors and connection status.

The sample engine input in contracts/ai-engine/sample-input.json contains complete
synthetic invoice/delivery text for a no-mismatch happy path on a fresh server.

## Remaining gaps

- No hosted model or real OCR recognition was tested or integrated. The actual
  engine is Member 2's existing deterministic implementation. Images/scans explicitly
  report unavailable OCR; no extracted facts are fabricated.
- Metadata, full results and facts are in-memory. Private files are temporary;
  clean shutdown deletes them, and abnormal termination may leave OS temporary
  artifacts. Durable PostgreSQL/object storage, migrations and recovery are absent.
- One backend worker, one active analysis. The 30-second subprocess timeout is not
  a durable queue, parser memory sandbox, or production request gateway. Multipart
  parser spooling occurs before the stored-file size check; deploy only locally.
- No authentication/merchant isolation, malware scanning, evidence deletion API,
  approval-granted state, response submission, or PayPal live actions.
- Health mode mock is retained to preserve its schema and denotes synthetic storage.
  Capabilities and analysis details explicitly identify ai_engine_v1. evidence_count
  now reflects actual uploaded documents rather than the illustrative fixture count.

import base64
from hashlib import sha256

from backend.app.schemas import Analysis
from .extraction.fact_extractor import extract_facts
from .extraction.parser import DocumentError, OCRReader, parse_document
from .generation.response_generator import DraftWriter, render_draft, supported_claims, validate_claims
from .matching.evidence_matcher import match_document
from .schemas import DocumentMatch, PipelineInput, PipelineResult, ProcessingIssue
from .validation.output_validator import validate_output
from .validation.rules import validate_evidence


def run_pipeline(request: PipelineInput | dict, *, ocr: OCRReader | None = None,
                 draft_writer: DraftWriter | None = None) -> PipelineResult:
    """Synchronous worker entry point. The backend owns scheduling and persistence.

    Invalid input raises Pydantic ValidationError. Individual unreadable documents
    produce structured issues. Unexpected programming errors propagate to the worker.
    """
    request = PipelineInput.model_validate(request)
    pages, issues, matches = [], [], []
    seen = set()
    for document in request.documents:
        data = document.text.encode("utf-8") if document.text is not None else base64.b64decode(document.content_base64)
        digest = sha256(document.media_type.encode() + b"\0" + data).hexdigest()
        if digest in seen:
            matches.append(DocumentMatch(document_id=document.id, status="duplicate", reason="Identical content was supplied more than once; duplicate content is excluded."))
            continue
        seen.add(digest)
        try:
            pages.extend(parse_document(document, ocr))
        except DocumentError as exc:
            issues.append(ProcessingIssue(code=exc.code, document_id=document.id, message="Document could not be fully parsed; review the file or parser configuration."))
            matches.append(DocumentMatch(document_id=document.id, status="unreadable", reason="Document could not be read and cannot support claims."))
    facts, extraction_issues = extract_facts(pages)
    issues.extend(extraction_issues)
    excluded = {match.document_id for match in matches}
    matches.extend(match_document(document, facts, request.transaction) for document in request.documents if document.id not in excluded)
    invalid_references = {issue.document_id for issue in extraction_issues if issue.code == "INVALID_TRANSACTION_REFERENCE"}
    for match in matches:
        if match.document_id in invalid_references:
            match.status = "ambiguous"
            match.reason = "A transaction reference could not be normalized; the document requires manual review."
    order = {doc.id: i for i, doc in enumerate(request.documents)}
    matches.sort(key=lambda match: order[match.document_id])
    findings, finding_sources = validate_evidence(request, facts, matches)
    # Surface unsupported/ambiguous field formats in the public Analysis too.
    from backend.app.schemas import Finding
    for document_id in sorted({issue.document_id for issue in extraction_issues}):
        finding = Finding(id=f"finding_{len(findings) + 1:04d}", issue_type="invalid_extracted_fact", severity="medium",
            explanation="Some labeled facts could not be normalized and were excluded from analysis.", source_ids=[document_id],
            recommendation="Review the document. Use unambiguous numeric amounts and ISO dates, or extend the extraction adapter.")
        findings.append(finding)
        finding_sources[finding.id] = []
    matched = {match.document_id for match in matches if match.status == "matched"}
    allowed = supported_claims([fact for fact in facts if fact.source.document_id in matched])
    claims = [claim.model_copy(deep=True) for claim in allowed]
    if draft_writer is not None and allowed:
        try:
            candidate = draft_writer([claim.model_copy(deep=True) for claim in allowed])
            validate_claims(candidate, allowed)
            claims = candidate
        except Exception:
            issues.append(ProcessingIssue(code="DRAFT_FALLBACK", message="Draft adapter failed or returned unsupported claims; used deterministic source-backed draft."))
    failed = bool(request.documents) and not pages
    analysis = Analysis(analysis_id=request.analysis_id, transaction_id=request.transaction.id,
                        status="failed" if failed else "completed", findings=findings,
                        draft_response=render_draft(claims, bool(findings)), merchant_approval_required=True)
    result = PipelineResult(analysis=analysis, pages=pages, facts=facts, matches=matches,
                            finding_sources=finding_sources, draft_claims=claims, issues=issues)
    validate_output(request, result)
    return result

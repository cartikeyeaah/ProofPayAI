from ..generation.response_generator import render_draft, supported_claims, validate_claims
from ..schemas import PipelineInput, PipelineResult


def validate_output(request: PipelineInput, result: PipelineResult) -> None:
    """Reject fabricated sources, claims, cross-transaction output, and stale drafts."""
    analysis = result.analysis
    if analysis.analysis_id != request.analysis_id or analysis.transaction_id != request.transaction.id:
        raise ValueError("Analysis identity mismatch")
    documents = {doc.id for doc in request.documents}
    if {match.document_id for match in result.matches} != documents or len(result.matches) != len(documents):
        raise ValueError("Missing or duplicate document outcomes")
    pages = {(page.document_id, page.page): page.text for page in result.pages}
    if any(page.document_id not in documents for page in result.pages) or len(pages) != len(result.pages):
        raise ValueError("Invalid parsed pages")

    def check_source(source):
        text = pages.get((source.document_id, source.page))
        if text is None or not 0 <= source.start < source.end <= len(text) or text[source.start:source.end] != source.quote:
            raise ValueError("Invalid source span")

    if len({fact.id for fact in result.facts}) != len(result.facts):
        raise ValueError("Duplicate fact IDs")
    for fact in result.facts:
        check_source(fact.source)
    # Re-extraction verifies normalized values as well as the quoted spans.
    from ..extraction.fact_extractor import extract_facts
    if result.facts != extract_facts(result.pages)[0]:
        raise ValueError("Fact values do not match extracted source text")
    if set(result.finding_sources) != {finding.id for finding in analysis.findings}:
        raise ValueError("Missing finding provenance entries")
    for finding in analysis.findings:
        if not set(finding.source_ids) <= documents:
            raise ValueError("Unknown finding document")
        for source in result.finding_sources[finding.id]:
            check_source(source)
            if source.document_id not in finding.source_ids:
                raise ValueError("Finding source mismatch")
    matched = {match.document_id for match in result.matches if match.status == "matched"}
    allowed = supported_claims([fact for fact in result.facts if fact.source.document_id in matched])
    validate_claims(result.draft_claims, allowed)
    if analysis.draft_response != render_draft(result.draft_claims, bool(analysis.findings)):
        raise ValueError("Draft does not match validated claims")

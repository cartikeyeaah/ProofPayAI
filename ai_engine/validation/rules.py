from datetime import date
from decimal import Decimal

from backend.app.schemas import Finding
from ..schemas import DocumentMatch, ExtractedFact, PipelineInput, SourceReference


def validate_evidence(request: PipelineInput, facts: list[ExtractedFact], matches: list[DocumentMatch]):
    findings: list[Finding] = []
    sources: dict[str, list[SourceReference]] = {}

    def add(kind, severity, explanation, recommendation, relevant=(), document_ids=()):
        refs = [fact.source for fact in relevant]
        ids = sorted(set(document_ids) | {ref.document_id for ref in refs})
        finding = Finding(id=f"finding_{len(findings) + 1:04d}", issue_type=kind, severity=severity,
                          explanation=explanation, source_ids=ids, recommendation=recommendation)
        findings.append(finding)
        sources[finding.id] = refs

    matched = {match.document_id for match in matches if match.status == "matched"}
    usable = [fact for fact in facts if fact.source.document_id in matched]
    for match in matches:
        if match.status != "matched":
            add(f"{match.status}_evidence", "medium", match.reason,
                "Review the document and provide readable evidence with an explicit transaction reference.",
                [fact for fact in facts if fact.source.document_id == match.document_id and fact.name == "transaction_id"],
                [match.document_id])
    if not matched:
        add("missing_transaction_evidence", "high", "No supplied document could be matched to this transaction.",
            "Supply a readable invoice or order confirmation containing the transaction reference.")
    for fact in usable:
        if fact.name == "amount" and Decimal(fact.value) != Decimal(request.transaction.amount):
            add("amount_mismatch", "high", f"Document amount {fact.value} differs from transaction amount {request.transaction.amount}; currency must be checked separately.",
                "Reconcile the amount against the transaction record.", [fact])
        if fact.name == "currency" and fact.value != request.transaction.currency:
            add("currency_mismatch", "high", f"Document currency {fact.value} differs from transaction currency {request.transaction.currency}.",
                "Supply evidence in the correct transaction currency.", [fact])

    for name in ("invoice_date", "order_date", "delivery_date", "delivery_status", "amount", "currency"):
        relevant = [fact for fact in usable if fact.name == name]
        if len({fact.value for fact in relevant}) > 1:
            kind = "conflicting_dates" if name.endswith("_date") else "conflicting_facts"
            add(kind, "high", f"Matched documents contain conflicting {name.replace('_', ' ')} values.",
                "Resolve the conflicting records before approving a response.", relevant)

    # Compare delivery with the referenced order when available. A timezone-free
    # document date cannot support precise timestamp comparisons.
    order_facts = [fact for fact in usable if fact.name == "order_date"]
    for delivery in [fact for fact in usable if fact.name == "delivery_date"]:
        later_orders = [fact for fact in order_facts if date.fromisoformat(fact.value) > date.fromisoformat(delivery.value)]
        if later_orders:
            add("conflicting_dates", "high", "A delivery date precedes an order date in matched evidence.",
                "Verify the order and delivery dates.", [delivery, *later_orders])

    delivery_documents = [doc for doc in request.documents if doc.id in matched and doc.document_type == "delivery_record"]
    has_delivery = any(
        any(f.name == "delivery_status" and f.value == "delivered" for f in usable if f.source.document_id == doc.id)
        and any(f.name == "delivery_date" for f in usable if f.source.document_id == doc.id)
        for doc in delivery_documents
    )
    if request.require_delivery and not has_delivery:
        add("missing_delivery_proof", "high",
            "No matched delivery record with a delivered status and a valid delivery date was found in the supplied evidence. This does not establish that delivery did not occur.",
            "Supply a delivery record containing the transaction reference, delivery status and delivery date.")
    for document_id in matched:
        document_facts = [fact for fact in usable if fact.source.document_id == document_id]
        if not any(f.name != "transaction_id" for f in document_facts):
            add("insufficient_evidence", "medium", "The matched document contains no recognized supporting facts beyond its transaction reference.",
                "Review the document format and supply extractable supporting details.", document_ids=[document_id])
    return findings, sources

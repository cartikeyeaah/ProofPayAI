from ..schemas import DocumentMatch, EvidenceDocument, ExtractedFact
from backend.app.schemas import Transaction


def match_document(document: EvidenceDocument, facts: list[ExtractedFact], transaction: Transaction) -> DocumentMatch:
    references = {fact.value for fact in facts if fact.source.document_id == document.id and fact.name == "transaction_id"}
    expected = {transaction.id, transaction.paypal_transaction_id}
    if references and references <= expected:
        status, reason = "matched", "Explicit transaction reference matches the supplied transaction."
    elif references & expected:
        status, reason = "ambiguous", "Document contains both matching and conflicting transaction references."
    else:
        status, reason = "unmatched", "No matching explicit transaction reference; amount or date alone is insufficient."
    return DocumentMatch(document_id=document.id, status=status, reason=reason)

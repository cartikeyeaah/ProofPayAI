"""Extract explicit labels only. Ambiguous locale formats are reported, never guessed."""
from datetime import date
from decimal import Decimal
import re

from ..schemas import ExtractedFact, ParsedPage, ProcessingIssue, SourceReference

LABELS = {
    "transaction id": "transaction_id", "paypal transaction id": "transaction_id",
    "payment reference": "transaction_id", "amount": "amount", "total": "amount",
    "grand total": "amount", "currency": "currency", "invoice date": "invoice_date",
    "order date": "order_date", "delivery date": "delivery_date", "delivered date": "delivery_date",
    "delivery status": "delivery_status", "tracking id": "tracking_id", "tracking number": "tracking_id",
}
LINE = re.compile(r"^\s*(?P<label>[^:\n]+?)\s*:\s*(?P<value>[^\n]*?)\s*$", re.MULTILINE)


def _normalize(name: str, value: str) -> list[tuple[str, str]]:
    if name == "amount":
        match = re.fullmatch(r"(?:(?P<prefix>[A-Za-z]{3})\s+)?(?P<amount>-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)(?:\s+(?P<suffix>[A-Za-z]{3}))?", value)
        if not match:
            raise ValueError("Ambiguous amount")
        prefix, suffix = match.group("prefix"), match.group("suffix")
        if prefix and suffix and prefix.upper() != suffix.upper():
            raise ValueError("Conflicting currencies")
        amount = Decimal(match.group("amount").replace(",", ""))
        if abs(amount) >= Decimal("10000000000"):
            raise ValueError("Amount exceeds contract")
        result = [(name, format(amount, ".2f"))]
        if prefix or suffix:
            result.append(("currency", (prefix or suffix).upper()))
        return result
    if name.endswith("_date"):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Use ISO dates")
        return [(name, date.fromisoformat(value).isoformat())]
    if name == "currency":
        if not re.fullmatch(r"[A-Za-z]{3}", value):
            raise ValueError("Invalid currency")
        value = value.upper()
    elif name == "delivery_status":
        value = value.lower().replace(" ", "_")
        if value not in {"delivered", "in_transit", "pending", "failed", "returned", "not_delivered"}:
            raise ValueError("Unrecognized delivery status")
    elif not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise ValueError("Invalid identifier")
    return [(name, value)]


def extract_facts(pages: list[ParsedPage]) -> tuple[list[ExtractedFact], list[ProcessingIssue]]:
    facts, issues = [], []
    for page in pages:
        for match in LINE.finditer(page.text):
            name = LABELS.get(" ".join(match.group("label").lower().split()))
            if name is None:
                continue
            start, end = match.span("value")
            try:
                values = _normalize(name, match.group("value"))
            except ValueError:
                issues.append(ProcessingIssue(code="INVALID_TRANSACTION_REFERENCE" if name == "transaction_id" else "INVALID_FACT", document_id=page.document_id,
                                              message=f"Could not normalize {name} on page {page.page}."))
                continue
            for field, value in values:
                facts.append(ExtractedFact(id=f"fact_{len(facts) + 1:04d}", name=field, value=value,
                    source=SourceReference(document_id=page.document_id, page=page.page,
                                           start=start, end=end, quote=page.text[start:end])))
    return facts, issues

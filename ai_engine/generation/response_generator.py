from collections.abc import Callable
from ..schemas import DraftClaim, ExtractedFact

# An optional language-model adapter may select/reorder these claims. It must
# return exact supported claims; arbitrary prose is intentionally not trusted.
DraftWriter = Callable[[list[DraftClaim]], list[DraftClaim]]


def supported_claims(facts: list[ExtractedFact]) -> list[DraftClaim]:
    return [DraftClaim(text=f"Document {fact.source.document_id}, page {fact.source.page}, reports {fact.name.replace('_', ' ')}: {fact.value}.",
                       fact_ids=[fact.id]) for fact in facts if fact.name != "transaction_id"]


def validate_claims(claims: list[DraftClaim], allowed: list[DraftClaim]) -> None:
    if not isinstance(claims, list) or len(claims) > len(allowed) or (allowed and not claims):
        raise ValueError("Invalid draft claims")
    seen = set()
    for claim in claims:
        if not isinstance(claim, DraftClaim) or claim not in allowed:
            raise ValueError("Unsupported draft claim")
        key = (claim.text, tuple(claim.fact_ids))
        if key in seen:
            raise ValueError("Duplicate draft claim")
        seen.add(key)


def render_draft(claims: list[DraftClaim], has_findings: bool) -> str | None:
    if not claims:
        return None
    lines = ["Draft for merchant review. The supplied documents report the following:"]
    lines.extend(f"- {claim.text}" for claim in claims)
    if has_findings:
        lines.append("Evidence issues remain. Resolve the analysis findings before approving this draft.")
    lines.append("These statements describe supplied records; they do not independently verify payment or delivery. Merchant approval is required.")
    return "\n".join(lines)

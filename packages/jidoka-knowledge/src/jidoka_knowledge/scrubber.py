"""The scrubber gate: the only path from project memory into system memory (ADR-0010).

Shapes may cross. Values never. "Cost centre codes here were four-digit numeric" is a shape;
`1000` is a value. A client value leaked into the shared library is unrecallable — every later
engagement reads it and there is no revocation — so promotion is a ledgered ceremony with a
named human approver, in the same class as arming a live write.

The scrubber refuses rather than redacts. Silently stripping a value from a sentence leaves a
sentence that no longer means what its author checked, and the approver would be signing off
text nobody wrote. A claim that trips the gate goes back to be rewritten as a shape.
"""
import re
from .claim import Claim, evidence_hash

# ponytail: regex screen, not NER. Catches the shapes SAP client values actually take — bare
# codes, org units, emails, hosts, dates. Add a model-backed check only if a real leak gets past
# this, and only behind the same human approval, never instead of it.
_VALUE_PATTERNS = [
    (re.compile(r"\b\d{3,}\b"), "a literal numeric code"),
    (re.compile(r"\b[A-Z]{2,}\d{2,}\b"), "an identifier that looks client-specific"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "an email address"),
    (re.compile(r"\bhttps?://\S+"), "a URL"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "a specific date"),
    (re.compile(r"\b(?:BUKRS|KOKRS|WERKS|EKORG|VKORG)\s*[=:]\s*\S+"), "a bound org value"),
]


class PromotionRefused(Exception):
    """The gate declining to let something cross. Not a failure — the gate working."""


def screen(text: str) -> list[str]:
    """Reasons this text may not cross, empty if it is a clean shape."""
    return [why for pattern, why in _VALUE_PATTERNS if pattern.search(text)]


def promote(claim: Claim, system_store, approver: str, builder: str, ledger=None) -> Claim:
    """Move a project claim into system memory as a shape.

    Requires a named human approver who is not the builder — the same separation the ledger
    enforces for configuration, applied to belief, because the agent proposing that something
    is a general truth is exactly the party that should not be ratifying it.
    """
    if not approver:
        raise PromotionRefused("promotion to system memory requires a named human approver")
    if approver == builder:
        raise PromotionRefused(
            f"{approver} formed this claim and may not approve its promotion (builder != approver)"
        )
    reasons = screen(claim.text)
    if reasons:
        raise PromotionRefused(
            "claim carries client values and must be rewritten as a shape: " + "; ".join(reasons)
        )

    # Promotion is idempotent: the same shape crossing twice is one belief, not two. Without
    # this, every re-run of a promotion flow appends another identical system claim.
    existing = next((c for c in system_store.current(claim.subject) if c.text == claim.text), None)
    if existing is not None:
        return existing

    promoted = Claim(
        subject=claim.subject, text=claim.text,
        # The system claim is grounded in the promotion ceremony, not in the client's evidence:
        # system memory must never hold a pointer back into an engagement's data.
        source_ref=f"promotion:{claim.id}",
        source_hash=evidence_hash({"text": claim.text, "approver": approver}),
        actor=approver, confidence=claim.confidence,
    )
    system_store.add(promoted)
    if ledger is not None:
        ledger.append(task=f"promotion:{claim.subject}", action="PROMOTED", actor=approver,
                      detail=claim.text, from_claim=claim.id, builder=builder)
    return promoted

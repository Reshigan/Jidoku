"""The gate on ingesting third-party documentation, and the record of why it is shut.

JIDOKA's four knowledge classes have different physics, and only one of them has a legal
question attached. K1 (a tenant's own metadata) is the client's data read under the client's
entitlement, and `harvest` already does it. K4 (what engagements teach us) is ours, scrubbed to
shapes. K3 is community material, advisory only. K2 — SAP's Help Portal, implementation guides,
release notes, Notes and KBAs — is somebody else's copyrighted work behind somebody else's
authentication, and whether we may ingest it at all is a question for counsel and the partner
agreement rather than for an engineer with a scraper.

That question is DP-K01. It is open. This module is what "open" means in code: any path that
would ingest a gated corpus asks `require_open()` first and is refused, and the refusal names the
decision, its owner and what would have to be true to lift it. There is deliberately no override
argument, no environment variable and no debug flag — a gate with a bypass is not a gate, and the
whole failure mode being guarded against is a well-meaning engineer who is sure it is fine.

Unlike an engagement's decision points this one is not per-engagement. A licensing position is
true of the platform or of nothing, so the record lives in the source tree where a test can prove
every tenant is behind the same gate simultaneously, and where lifting it is a reviewed commit
with a named authority rather than a row someone can write at runtime.

The gate is not an obstacle to route around. Metadata already outranks documentation as a source
(ADR-0012): the system is what the system is, and a manual only describes it. If DP-K01 is never
resolved, JIDOKA is narrower but not blocked.
"""
from dataclasses import dataclass


class CorpusRefused(Exception):
    """An ingestion path declining to run. Not a failure — a gate holding."""


@dataclass(frozen=True)
class Decision:
    """A platform-wide decision, and the conditions under which it is considered taken.

    `resolution` is None for as long as the decision is open. Filling it in is a source change,
    reviewed like any other, which is the point: a legal position should not be assertable by
    whoever happens to be holding a keyboard at the time.
    """

    dp_id: str
    question: str
    owner: str
    #: What the answer has to come with before it counts. Named here rather than in a review
    #: checklist so the requirement travels with the decision.
    requires: tuple[str, ...]
    #: What JIDOKA does if the answer is no. A decision with no answer for "no" is not a decision,
    #: it is a plan with a hope in it.
    if_refused: str
    resolution: dict | None = None

    @property
    def open(self) -> bool:
        return self.resolution is None


DP_K01 = Decision(
    dp_id="DP-K01",
    question=(
        "May JIDOKA ingest SAP's copyrighted documentation — Help Portal guides, release notes, "
        "API specifications — and S-user-gated SAP Notes and KBAs, into a retrieval corpus used "
        "to ground the platform's answers?"
    ),
    owner="goNXT counsel, with the SAP partner agreement",
    requires=(
        "A written position from counsel, not an inference from the partner agreement's silence.",
        "Identification of the entitlement the ingestion runs under — which partner or customer "
        "agreement, and what it actually permits, quoted.",
        "Confirmation that S-user-gated material may be retrieved by an automated agent at all: "
        "credentials belonging to a person do not obviously extend to a machine acting for many "
        "clients, and the Notes terms are not the Help Portal terms.",
        "A redistribution boundary stated in terms an engineer can implement: JIDOKA sells "
        "judgement grounded in the corpus, never the corpus. No SAP content reaches a third "
        "party, no answer reproduces a chunk verbatim beyond citation length.",
        "A retention and revocation answer: what happens to ingested chunks if the entitlement "
        "lapses or the agreement ends.",
    ),
    if_refused=(
        "K2 is not built. JIDOKA grounds itself in K1 (a tenant's own metadata, ADR-0012), K4 "
        "(engagement-derived shapes through the scrubber gate) and client-signed statutory "
        "sources. Answers cite systems and signed documents rather than manuals. This is "
        "narrower and slower to be right about product behaviour, and it is not blocked."
    ),
)

#: Corpora that may not be ingested until DP-K01 is resolved. Keyed by the name an ingestion path
#: asks for. K1 and K4 are absent on purpose — they are not gated by this decision and never were.
GATED = {
    "sap_help": "SAP Help Portal — implementation and administration guides.",
    "sap_notes": "SAP Notes and KBAs, behind S-user authentication.",
    "sap_release_notes": "SAP release notes, per product per release.",
    "sap_api_hub": "SAP API Business Hub specifications.",
}


def require_open(corpus: str) -> None:
    """Assert that `corpus` may be ingested. Raises `CorpusRefused` if it may not.

    Call this before acquiring a single byte, not before storing one: the download is itself the
    act the decision governs, and a fetch that is discarded afterwards was still a fetch against
    someone else's terms.
    """
    if corpus not in GATED:
        # Ungated corpora pass. Being explicit rather than falling through keeps an unrecognised
        # name from reading as permission — a typo in a corpus key must not open a gate.
        return
    if DP_K01.open:
        raise CorpusRefused(
            f"{corpus} ({GATED[corpus]}) cannot be ingested: {DP_K01.dp_id} is open.\n"
            f"  Question: {DP_K01.question}\n"
            f"  Owner:    {DP_K01.owner}\n"
            f"Resolving it needs {len(DP_K01.requires)} things, listed on the decision record in "
            f"jidoka_knowledge.corpus. Until then JIDOKA grounds itself in system metadata and "
            f"signed client sources instead — this is a decision, not an outage."
        )


def brief() -> str:
    """The decision as a document to send to counsel. Generated from the record so the question
    that gets asked is the same one the code is holding out for."""
    lines = [
        f"# {DP_K01.dp_id} — decision required",
        "",
        f"**Owner:** {DP_K01.owner}",
        f"**Status:** {'OPEN — blocking' if DP_K01.open else 'resolved'}",
        "",
        "## The question",
        "",
        DP_K01.question,
        "",
        "## What is already being done without this decision",
        "",
        "JIDOKA reads a client's own SAP systems for their metadata — table and field structure, "
        "domain fixed values, check tables, number ranges — under that client's own entitlement, "
        "and grounds its claims in those reads. That needs no permission from SAP and is already "
        "live. This decision is only about SAP's *documentation about* those systems.",
        "",
        "## What an answer has to come with",
        "",
    ]
    lines += [f"{i}. {r}" for i, r in enumerate(DP_K01.requires, 1)]
    lines += [
        "",
        "## If the answer is no",
        "",
        DP_K01.if_refused,
        "",
        "## What is at stake in saying yes carelessly",
        "",
        "Ingesting gated material without an entitlement that covers it puts every client "
        "engagement on the platform behind the same defect, and a corpus cannot be un-learned "
        "from answers already given. The gate is shut by default for that reason.",
    ]
    return "\n".join(lines)

# DP-K01 — decision required

**Owner:** goNXT counsel, with the SAP partner agreement
**Status:** OPEN — blocking

## The question

May JIDOKA ingest SAP's copyrighted documentation — Help Portal guides, release notes, API specifications — and S-user-gated SAP Notes and KBAs, into a retrieval corpus used to ground the platform's answers?

## What is already being done without this decision

JIDOKA reads a client's own SAP systems for their metadata — table and field structure, domain fixed values, check tables, number ranges — under that client's own entitlement, and grounds its claims in those reads. That needs no permission from SAP and is already live. This decision is only about SAP's *documentation about* those systems.

## What an answer has to come with

1. A written position from counsel, not an inference from the partner agreement's silence.
2. Identification of the entitlement the ingestion runs under — which partner or customer agreement, and what it actually permits, quoted.
3. Confirmation that S-user-gated material may be retrieved by an automated agent at all: credentials belonging to a person do not obviously extend to a machine acting for many clients, and the Notes terms are not the Help Portal terms.
4. A redistribution boundary stated in terms an engineer can implement: JIDOKA sells judgement grounded in the corpus, never the corpus. No SAP content reaches a third party, no answer reproduces a chunk verbatim beyond citation length.
5. A retention and revocation answer: what happens to ingested chunks if the entitlement lapses or the agreement ends.

## If the answer is no

K2 is not built. JIDOKA grounds itself in K1 (a tenant's own metadata, ADR-0012), K4 (engagement-derived shapes through the scrubber gate) and client-signed statutory sources. Answers cite systems and signed documents rather than manuals. This is narrower and slower to be right about product behaviour, and it is not blocked.

## What is at stake in saying yes carelessly

Ingesting gated material without an entitlement that covers it puts every client engagement on the platform behind the same defect, and a corpus cannot be un-learned from answers already given. The gate is shut by default for that reason.

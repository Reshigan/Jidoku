# ADR-0041 — The delta pool can be exhausted

Status: Accepted
Date: 2026-09-22
Relates to ADR-0020 (the economist), ADR-0034 (one writer, declared readers), invariant 2.
Delivers F1.4 from docs/JIDOKA_PROJECT_TEAM_AND_ALIGNMENT.md §3.

## Context

The document is specific: *"Delta pool debit — consumes one of the 30 (F1.4); pool empty ⇒
COMMERCIAL DP, not a quiet build."* The economist has priced the pool in prose since ADR-0020 and
there was no pool. A sentence in a run report is not a budget, and a budget nothing can exhaust is
a number in a slide.

The thing that made this buildable rather than arbitrary was ADR-0034. Before contracts, deciding
what counts as a customisation would have meant a second list of "things we consider custom",
maintained by hand and wrong within a month.

## Decision

**A customisation is an object carrying a cross-module contract.** Delivered standard
configuration has no owner to declare; the objects a programme builds have one, because they are
exactly the objects somebody must name an owner and readers for. So the pool debits from the same
declaration the contract registry reads, and there is no second list to keep in step.

**The pool is counted from the design, not from what has been built.** The commercial question is
asked when somebody proposes the thirty-first — not after it has reached a tenant, which is too
late for it to be a question.

**Thirty is a default, not a law.** It is the Komatsu number and it is a commercial fact, so the
size is declared per engagement on the ledger — like the night's cadence — and the pool and what
it spent are read off one chain.

**Declaring the size takes `approve`.** The number is somebody's agreement and the platform is
never the one who changes it.

**Going over raises a `COMMERCIAL` decision point,** which hard-blocks planning like any other
open decision, because invariant 2 does not care where the question came from. Three exits, all
of them a person's: extend the pool, drop the extra customisations, or take them back to the
delivered standard.

## Consequences

- The stop is commercial, not technical. An empty pool does not mean the platform cannot build the
  thing; it means somebody agreed to thirty and this is the thirty-first. The refusal says so.
- A programme that has not adopted contracts has a pool it can never spend. That is correct and it
  is the same honest limit ADR-0034 records: the gate only fires on what somebody declared.
- The pool counts objects, not effort. Thirty trivial picklists and thirty custom MDF objects
  debit identically, which is what the commercial agreement says and not what they cost. Pricing
  them apart is the economist's job and it remains prose.

## Alternatives rejected

*Debit on execution.* The budget would only bite after the work was done, which makes it a report
rather than a gate.

*Infer customisation from the absence of a standard object in the product's catalogue.* It would
need a catalogue per product per release, it would be wrong at every SAP release, and it would
make a commercial agreement depend on the completeness of a list nobody maintains.

*Warn instead of blocking.* A warning about a number somebody signed is a warning everybody learns
to scroll past.

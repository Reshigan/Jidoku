# ADR-0036 — The rule travels with the value, and the plan is type-checked

Status: Accepted
Date: 2026-09-21
Relates to invariant 1 (unsigned intent is unexecutable), invariant 2 (open decisions hard-block),
ADR-0002 (the IR), ADR-0034 (contracts). Delivers C1 of docs/JIDOKA_ADVANCED_CONCEPTS.md.

## Context

The IR has always been *validated*: schema, references, signatures. Validation answers "is this a
well-formed record". It does not answer "is 21 days of annual leave legal in South Africa", and
that question has no home in the record — it lives in a workbook, a consultant's memory, and a
test somebody may have written.

C1's claim is that the constraint belongs on the value, carrying its own authority, so whole
classes of defect become unrepresentable rather than detected.

## Decision

**Three refinement kinds, and no more.** `bounded` (a statutory ceiling or floor), `dependent`
(this value is decided by another object's field), `required` (the field exists and is not empty).
A fourth would need a reason; a general expression language would need a parser, a sandbox and an
argument about what it can reach.

**A bound carries its authority or it does not load.** `statute`, `signed_by`, `date` — the same
three things a signed IR source carries, because a ceiling is intent about a statute and invariant
1 does not stop applying when the number is in a type instead of a field. A ceiling somebody typed
in is an opinion.

**A refinement the checker cannot read does not load either.** A malformed constraint sitting in
the design looks like protection, and protection that is not there is worse than none.

**The plan is type-checked after the decision points, not before.** A refinement over a value
nobody has decided would report the absence of a decision as a type error, and invariant 2's gate
says that better. So the order is: contracts, then decisions, then types.

**The rejection is the control narrative.** `"...is configured as 21 and the signed statutory
maximum is 15 (BCEA s20, signed by T. Mabaso on 2026-09-01). A value above a statutory maximum is
not a configuration choice."` That sentence goes into an audit report unedited. A type-checker
whose message needed translating first would be translated by hand, once, and then drift from what
it actually enforces.

**A dependency on an object that is not in the design is reported as unchecked, not as passed.**
Silence would read as a pass, and the one thing this must never do is look like protection it did
not provide.

**Absence and disagreement are reported apart.** `check` returns refinements that do not hold;
`missing_required` returns fields that are empty. An auditor reads the two differently, and a
combined list would be sorted by hand on arrival.

## Consequences

- A record with no refinements is not checked and is not counted as passing. An untyped value is
  unconstrained, not approved, and the console says so where the count appears.
- The compiler (`jidoka-compiler`) does not yet emit refinements: they arrive only where somebody
  writes them into the IR. Until it does, this protects the designs that opted in, which is a real
  but partial thing and is said here rather than implied.
- `dependent` compares values for equality only. A currency that must match and a date that must
  fall inside another object's window are both real, and only the first is expressible.
- The type-check runs over every record on every plan. It is a pass over the intent trees, which
  is the same cost the decision-point walker already pays on load.

## Alternatives rejected

*An expression language.* `where entitlement <= statutory_max(ZAF, signed_source)` reads well in a
design document and needs a parser, an evaluator and a sandbox in code. Three named kinds cover
the cases the Komatsu work actually produced, and each one is auditable by reading it.

*Check types at write time rather than at plan time.* A design that cannot be written is found
three weeks later than a design that cannot be planned, and the planner is where every other
design-level refusal already lives.

*Treat a statutory violation as a decision point.* It is not a question. A value above a statutory
maximum has one correct answer and the platform knows it; raising a DP would ask a person to
confirm the law.

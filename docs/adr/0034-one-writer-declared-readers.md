# ADR-0034 — One writer, declared readers

Status: Accepted
Date: 2026-09-21
Relates to ADR-0002 (the IR), ADR-0017 (archaeology), invariant 2. Delivers E14's cross-module
contract registry, from docs/JIDOKA_PROJECT_TEAM_AND_ALIGNMENT.md §3.

## Context

The Komatsu lesson: `custom-string4` — the MIBCO flag — is *written* by EC and *read* by Time Off
eligibility, EE reporting and the ECC payroll interface. Handled as a field it is four surprises
waiting for a release. Nobody is wrong at any point; EC changes the object it owns, and three
other modules discover in production that they depended on it.

This is the defect shape that costs the most on a real programme and it is invisible to every tool
that models configuration as records. The dependency exists in the design, in somebody's head, and
in an integration test that may or may not cover it.

## Decision

**A contract is part of the record, not a thing about it.** `IRRecord.contract` declares the single
`owner` module that writes the object, the `consumers` registered to read it, what it `feeds`, and
its `statutory` linkage. So the registry is a projection over signed intent, and cannot disagree
with the design it describes.

**A contract that names no owner does not load.** Structurally invalid for the same reason an
unsigned source is: the thing it claims to establish, it does not. Without an owner it is a field
with paperwork, and the next module to write it does so unopposed.

**Two writers block the plan.** `PLAN BLOCKED — two modules claim to write the same object`,
through the same gate an open decision point uses, because it is the same kind of thing: a
question only a person may answer, which JIDOKA refuses to answer by picking one (R-202,
generalised from integration to modules). A silent race here is the defect that surfaces in month
nine as "payroll overwrites what onboarding set".

**An undeclared reader is a finding, not a block.** A record that depends on a contracted object
without being registered against it is the paperwork having fallen behind the design, not a design
error. It is reported, and it names the owner — because the owner is the one who will change the
object one day without knowing who breaks.

**Standard configuration needs no contract.** Optional by design. The delivered standard is owned
by the product and read by whatever reads it; refusing it for lacking a declaration would be
paperwork. The contract exists for the objects a programme *builds*, which are exactly the objects
that later surprise it.

**Short references resolve the way the planner resolves them.** `CustomString:custom-string4` means
the same thing in both places. Two resolvers would disagree the first time one of them learned a
new form.

## Consequences

- The blast radius of a contracted object is a declaration rather than an archaeology exercise.
  `jidoka-insight` computes a radius from what it can observe; this one is what the design says,
  and a difference between them is itself informative.
- A programme that never declares a contract gets exactly the behaviour it had before. The gate
  only fires on what somebody declared, which means it cannot catch the collision nobody wrote
  down — that remains the archaeology path's job, and it is the honest limit of a declarative
  registry.
- Two records claiming the same object with the same owner are duplicates, not a conflict. The
  rule is about writers, not about tidiness.

## Alternatives rejected

*Infer ownership from the module that first wrote the object.* It makes the winner of a race the
owner, which is the failure this exists to prevent, and it would be silently wrong for every
object configured out of order.

*Block on an undeclared reader.* The dependency is real whether or not it is registered; refusing
to plan because the paperwork is behind would stop real work to enforce a form. It is a finding,
and it names the person who needs it.

*A separate contracts document.* A second copy of the design, drifting from the first. Every other
projection in this platform reads the record for the same reason.

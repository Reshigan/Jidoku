# ADR-0047 — The specification, against the configuration

Status: Accepted
Date: 2026-09-28
Relates to ADR-0046 (absorb the pack), ADR-0034 (cross-module contracts), invariant 1.
Found by reading the documents in a real client pack.

## Context

ADR-0046 absorbed a mobilisation pack's workbooks. It left the documents unread, and that was two
thirds of the pack. The Word files in the real one carry:

- **62 requirements**, each with a rationale, a country scope, a wave, a fit assessment and a
  control reference;
- **15 J-SOX control objectives**, each with an owner, a frequency and the evidence it produces;
- **17 decision points** that appear in no workbook at all, including nine *design dependencies* —
  decisions the design is already running on, under a stated interim position;
- **11 ordering constraints**, **21 design rules and principles**, a scope catalogue, a second copy
  of the alignment matrix, and six more boundary conditions.

None of it was in the platform, and the question it answers is the one no engagement can answer:
*which requirements does this configuration actually satisfy?* The requirements are in a document,
the configuration is in a system, and the join is somebody's memory of a workshop in week three.

## Decision

**A `.docx` is read with the standard library.** `jidoka_compiler.docx` unzips it and walks
`w:tbl` → `w:tr` → `w:tc`. A document reader is the easiest place in a platform to acquire a
dependency for a feature nobody needs, and the hard part here was never the parsing. Two real
traps are handled: Word splits a sentence across runs wherever formatting changes, so every `w:t`
under a cell is joined; and a BRS writes 62 requirements as 17 tables under one heading each, so
*every* table with a matching header is read rather than the first.

**Every table read is declared by its header, and every table not read is named** with its first
cell and row count, along with how many sections of prose went unread. What a design document
states only in sentences is not in the platform, and the absorber says so rather than implying the
document was understood.

**A requirement's traceability is a person's judgement and lives on the chain.** The platform never
infers which objects satisfy a requirement. A requirement matched to an object because a sentence
happened to contain its name would report the specification as met, and the report would be
believed. `POST .../requirements/{id}/trace` records the objects and the reason under the actor's
name; the latest trace wins and the earlier one stays in the record.

**NOT_TRACEABLE is its own state and is never counted as covered.** A requirement naming no object
is not "not configured" — the platform has nothing to look for. Rolling those into either bucket is
how a specification nobody has traced reports itself as fully met. The console sorts them first.

**Fit is the design authority's word and is never recomputed.** STD, CFG, GAP are assessments of
*how* a requirement is met, not of whether it has been. A value the platform does not recognise is
reported as unrecognised rather than mapped onto one it does: a pack may have its own vocabulary and
guessing puts a requirement in a bucket its author did not choose.

**A control needs an owner and stated evidence, or it is refused.** A control everybody owns is one
nobody runs, and an auditor asks for the name first. Both directions of the citation are reported: a
requirement citing a control the specification never defines is unassured, and a control nothing
cites assures nothing.

**A pack that states the same thing twice is named, never reconciled.** The real pack states 14 of
its decision points differently across its documents — DP-A01 three separate ways. One of them is
out of date and the platform cannot tell which, so both are kept and the conflict is reported.
Choosing is the design authority's job.

**Registration is out of band, tracing is on the screen.** Same argument as ADR-0046: nobody types
62 requirements into a console, and the judgement the platform refuses to make is exactly the thing
that belongs in front of a person.

## Consequences

- On the real pack, absorbing everything yields 221 records, 62 requirements, 11 control
  objectives, 75 decisions, 107 tasks, 19 gates, 6 one-way doors, 14 boundary conditions, 11
  ordering constraints, 34 design rules and 19 data domains — from one command.
- A freshly absorbed specification reports **0 of 62** requirements as described by signed intent,
  and 62 as untraceable. That is correct and it is the point: the traceability work is real work
  that no engagement currently does, and the platform now shows exactly how much of it is
  outstanding rather than implying it is done.
- The **ordering constraints and design rules are absorbed and reported, and nothing checks them**.
  Several state their own check — "checked at G2 and nightly" — and binding those to a mechanism is
  a judgement per rule, not a feature. They are in the bundle so nothing is lost, and CLAIMS.md says
  plainly that the platform does not enforce them.
- The prose is not read. A Solution Design Document is 30 tables and 113 paragraphs and the
  paragraphs carry the reasoning; the absorber reports the count of unread sections rather than
  summarising them, because a summary of a design document is a new document nobody signed.

## Alternatives rejected

*Infer traceability from the requirement text.* An object name appearing in a sentence is not a
design decision. The inference would be right often enough to be trusted and wrong often enough to
matter, which is the worst combination available.

*Count NOT_TRACEABLE as NOT_CONFIGURED.* It reads as pessimistic and is therefore tempting. It is
wrong in the direction that gets fixed by tracing badly: a team looking at "not configured" traces
whatever is nearest to clear the number.

*Summarise the prose with a model.* The output would be a design statement no human wrote and
nobody signed, sitting in a bundle whose whole purpose is that somebody signs it.

*Reconcile duplicate decisions by taking the latest document.* Document dates are not reliable in a
pack assembled from four streams, and the losing version is sometimes the current one.

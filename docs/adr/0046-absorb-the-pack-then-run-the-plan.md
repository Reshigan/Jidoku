# ADR-0046 — Absorb the pack, then run the plan

Status: Accepted
Date: 2026-09-28
Relates to ADR-0003 (tiers), ADR-0034 (cross-module contracts), ADR-0045 (the adapter decides the
tier), invariants 2 and 5.
Found by absorbing a real client mobilisation pack.

## Context

The platform could take a design workbook and turn it into signed intent. It could not take an
engagement. A real mobilisation pack is not a workbook: it is a folder holding a plan of record, a
design authority set, a cross-module alignment matrix and a picklist workbook, and between them they
carry a hundred and seven tasks with weeks and dependencies, nineteen gates with named approvers and
stated evidence, six one-way doors, twenty-one decisions on the critical path, eight boundary
conditions with the consequence of each one failing written down, eighteen data domains with
declared owners and forty-two declared readers, and twenty-three interlocks each with its failure
mode.

None of that had anywhere to live. The platform knew about IR records, decision points and a ledger;
the engagement machine around them stayed in spreadsheets, which is where the two failure modes
live: a register that says a task is done because somebody typed that, and a plan whose progress is
a percentage made partly of work nobody can see.

## Decision

**A programme is a first-class domain** — `jidoka_core.programme` — holding three registers:
boundary conditions, gates and tasks. It is a projection over the chain, like everything else here:
the register is a statement about now, and what *happened* is on the ledger.

**What the register claims and what the chain shows are different fields, always.** A task carries
`declared_status` (the pack's own word) and `watches` (the ledger task it is visible as, if any).
`done` is derived only where the platform can see something. Where it cannot, the row says so:
*"the register says 'Complete' and the platform cannot see this task — it watches nothing."*

**No percentage is published.** Most of a programme's tasks are workshops, walkthroughs and
sign-offs the platform has no view of. A number made partly of those would be read as progress and
quoted in a steering meeting, and it would be the most-quoted wrong number the platform produces.
The screen says what it cannot see instead, and says why the number is absent.

**Lateness fires on a resolved day or not at all.** A gate's date is the pack's own words — "Fri 9
Oct", "week 8", "Never in prod" — and `due_on` is an ISO day only where the absorber could resolve
one. A register whose late column compares prose is wrong in both directions.

**A gate names the person who passes it, and passes on evidence, through `approve`.** A gate with no
named approver is a date; a gate whose evidence nobody wrote down is a date that passed. And a gate
will not pass over work the *chain* says is outstanding — while work it cannot see is reported
rather than blocking, because a platform that blocked on a workshop it has no view of would be
switched off.

**A one-way door is a ONE_WAY decision, never a gate.** The pack writes its doors under the gates,
in the same sheet, under their own header. Absorbed as gates they lose their second approver, which
is the only thing protecting them — and these are the entries that matter most: a production data
load, a legacy set made read-only, a purge. Invariant 5 already says ONE_WAY needs two distinct
named approvers. Two of the real pack's six doors name one person, and the absorber says so.

**A sheet is not a table, and a caption is not a register.** A blank row ends a register and the next
non-blank row starts the next one by being its header. Reading to the bottom of the sheet reported
eleven gates where there were five, two of which were a caption and a header row.

**Every register's identifiers are prefixed at absorption.** A pack numbers each register from one —
gates G1.., deliverables T1.., doors D1.., competence checks K1.. — and on a hash-chained ledger a
shared key means one register's answer resolves the other's entry.

**Everything not read is named**, on stdout and in the bundle's notes: every sheet skipped, every
file no profile matched, every date that would not resolve, every domain that could not be matched
to a configuration object. `tools/jidoka-absorb.py` exits non-zero when anything was left on the
floor. A person signs the bundle, and that signature is what makes the design executable, so
handing them part of a pack as the whole of it is the worst thing this tool could do quietly.

**The alignment matrix's readers are not silently zero.** The matrix names data domains; the IR names
objects; mapping between them is a judgement about a client's design. Where the absorber cannot
place a domain, it raises a DESIGN decision per unmatched domain rather than leaving the contract
registry reporting "no undeclared readers" because it was given no readers — which would be the most
dangerous screen in the platform, since the interlock the matrix exists to protect would read as
held.

**Registration is out of band.** `POST /engagements/{eid}/programme` takes the bundle; the console
has no form for it. A console form for a hundred and seven tasks would be a worse version of the
workbook the client already has, and a paste-the-JSON box a worse version of the tool. Everything
*after* registration — confirming a condition, recording a breach, passing a gate on evidence,
accounting for a task the platform cannot see — is on the screen.

## Consequences

- Absorbing the real pack found three defects reasoning had not: the two-register sheet, the lost
  one-way doors, and a knowledge-transfer tracker and deliverables register under different headers
  that a sheet-at-a-time reader ignored entirely. Real client material finds what review does not.
- A pack with an approverless gate cannot be registered. The load names the gate and the fix is to
  the workbook, not to the load.
- Eighteen DESIGN decisions arrive with the alignment matrix on a real engagement. Open decision
  points hard-block planning (invariant 2), so a programme cannot plan a cross-module change until
  somebody has said which objects hold which domain. That is the intended cost.
- The absorber depends on `openpyxl` and lives in `jidoka-compiler`; `jidoka-core.programme` is
  stdlib only, like the rest of the kernel, and knows nothing about spreadsheets.
- The pack itself is client material and is never committed. `packages/jidoka-compiler/tests/
  fixtures/make_fixtures.py` builds fixtures with the same shape and invented values, including the
  two-register Gates sheet and the banner above the header.

## Alternatives rejected

*Publish a percentage complete, with a caveat.* The caveat is not what gets quoted. The number
would be in a steering pack within a week, and the tasks the platform cannot see would be inside it.

*Trust the register's status column.* It is the only field in the pack with no evidence behind it,
and trusting it would make the platform a prettier spreadsheet.

*Absorb one-way doors as gates and note the difference.* A note does not require a second approver.
The type does.

*Let the absorber guess which objects hold a data domain.* A wrong mapping is worse than no mapping,
because a wrong one reports the interlock as held.

*Block a gate on tasks the platform cannot see.* Every gate on a real programme covers workshops.
The gate would never pass, and the platform would be switched off rather than fixed.

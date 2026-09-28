# ADR-0035 — One module agent per module the design declares

Status: Accepted
Date: 2026-09-21
Relates to ADR-0018 (the crew), ADR-0020 (the economy), ADR-0034 (one writer, declared readers).
Delivers E14's module-agent manifests, from docs/JIDOKA_PROJECT_TEAM_AND_ALIGNMENT.md §2 and §4.

## Context

`economy.py` has described five agents with opposed objectives since the first commit. The staffing
model in §2 describes more: module agents for RCM, ONB, PMGM and Time Off, a PMO agent, a migration
agent, an integration agent. They were in the document and nowhere else.

The temptation was to add four named manifests and be done. That would have been a second
statement of which modules a programme has — stale the day somebody added one, and in direct
conflict with §4.1, which is the whole alignment argument: *one IR, and no EC version of the design
to diverge from the Time Off version*.

## Decision

**The set of module agents is derived, not declared.** `crew.run` spawns one `module_agent(m)` per
distinct contract owner in the signed intent (ADR-0034). A programme with no contracts gets no
module agents — inventing an org chart for a customer who never described one would be the
platform asserting something it was not told.

**Each one objects only about its own objects.** A module agent's standing is exactly its
contract: it reports undeclared reads of objects it owns, and says nothing about anybody else's.
A module agent that spoke for the programme would agree with everybody, and the cross-module
collisions this exists to surface are precisely the ones both sides are relaxed about.

**The objective is narrow on purpose,** and in tension with its neighbours'. That is the design of
the economy (ADR-0020) applied one level down.

**Ring 2, like every other agent.** Builder at most, approver never — the import-time assertion on
`MAX_CAPS` already makes that structural, and a test asserts it holds for a module manifest too.

**PMO is Ring 3 and writes nothing.** A PMO agent that could move a date is a PMO agent whose
forecasts always come true. **Migration holds no `WRITE_TARGET`:** loading a customer's data is an
execution and goes through the executor with everything else. **Integration is Ring 1,** because an
interface is plumbing the platform runs rather than a position it takes.

## Consequences

- A module that owns nothing has no agent, so a programme sees exactly the modules its design
  declares. That is right, and it means the module pass is silent on a programme that has not
  adopted contracts — the same honest limit ADR-0034 records.
- The crew report grows by one card per module. Each card carries what it was allowed to do beside
  what it did, like every other card.
- `pmo`, `migration` and `integration` are manifests with no caller yet. That is stated here rather
  than hidden: the module agents have one, these three do not, and until they do they are shapes
  rather than behaviour.

## Alternatives rejected

*Hardcode RCM/ONB/PMGM/TO.* A second statement of the design. It would be stale the first time a
programme differed from Komatsu, and the platform would be asserting an org chart nobody gave it.

*Give module agents `WRITE_TARGET` so they configure their own modules.* The operator already
holds the single write path, through the executor, with the arming and snapshot gates in front of
it. A second write path that happens to be per-module is a second thing to prove safe.

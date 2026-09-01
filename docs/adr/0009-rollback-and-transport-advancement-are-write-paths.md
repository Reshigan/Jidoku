# ADR-0009: Rollback and transport advancement are write paths, gated exactly like an execute

Status: accepted.

Context: the executor has carried `rollback` and `advance_transport` since the kernel was written, and
neither was reachable from anything but a Python caller. That is a governance hole rather than a
missing convenience. A rollback puts rows back into a live system, and a transport advancement moves a
change one hop closer to production; both are writes to a customer's landscape, and a write that can
only be performed by someone with a shell is a write nobody's ledger sees coming. Meanwhile ADR-0006
made a verified ABAP write `IN_TRANSPORT` rather than complete, which left the console with steps it
could describe as unfinished and could not finish.

Decision: both are exposed over HTTP on the execution router and surfaced in the Configure screen, and
both are gated by the same code the execute path uses rather than by a re-statement of it. The rollback
endpoint calls `Executor._assert_armed` directly, so invariant 3 (the registry refuses a write-locked
target), invariant 6 (an armed target must exist and must match the record's binding) and invariant 7
(the person rolling back may not be the person who armed it) hold identically on both paths and cannot
drift apart. Invariant 4 is enforced twice over: the executor still refuses an empty snapshot, and the
API will only restore rows the platform itself read during a `SNAPSHOT` — the before-state is held
server-side, keyed by engagement and step, and is never accepted from the caller. A client-supplied
"before" would be an arbitrary write wearing a snapshot's name, which is precisely the substitution the
chained ledger exists to make impossible. Transport requests are held the same way: created on the
first armed live write to an ABAP product, with the route walked from the promotion paths the registry
was given at registration, never from a route the caller proposes or the platform infers. Every
advancement appends `TRANSPORT_ADVANCED` naming the request, the system it landed in, that system's
environment and the next hop, alongside the release and import entries the transport module already
emits, so the path a change actually took through the landscape is as verifiable afterwards as the
write itself.

Consequences: an operator can now undo a live write and finish an ABAP change from the console, and
each of those acts is on the chain with a named actor. The refusals are the interesting half: rolling
back without a snapshot is a 409 rather than a silent no-op, rolling back a target you armed yourself
is a 403 in the executor's own words, and asking to advance a transport on a non-ABAP product is a 422
because there is no such thing to advance. A route whose next hop is a write-locked system never
becomes a transport request at all — the step stays `IN_TRANSPORT` and says why, rather than failing
later at the import. The cost is two pieces of server-held state (snapshot rows and open transports)
that live in the API process and are lost on restart; the ledger keeps the record, the convenience is
what is lost, and a re-snapshot restores it. Nothing here weakens a gate: this ADR adds callers to
invariants 3, 4, 6 and 7, and re-uses their existing implementations verbatim.

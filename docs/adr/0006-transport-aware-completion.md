# ADR-0006: On the ABAP stack, a step is complete only when the transport reaches PROD

Status: accepted.

Context: a Tier-A write against S/4HANA or ECC lands in a DEV client and is captured in a transport
request. The write succeeding and verifying proves only that DEV is correct. PROD is unchanged until
that request is RELEASED and IMPORTED along its route. Reporting VERIFIED at that point tells an
auditor the change is live when it is not — the executor would be lying about the one fact the
ledger exists to prove.

Decision: `executor.ABAP_PRODUCTS` (a flat tuple, not a plugin surface) marks the ABAP stack. After a
verified Tier-A write against an ABAP product, `execute()` consults `transport.import_status`; unless
`in_production` is true the result is `IN_TRANSPORT`, a non-terminal status, and `StepResult.complete`
is False. `Executor.advance_transport()` releases and imports to the next legal hop, appending the
ledger-shaped dicts `transport.release`/`import_into` return, so the route a change actually took is
as chain-verifiable as the write. Non-ABAP products are untouched: VERIFIED stays terminal. A transport
failure puts only the exception type on the ledger, never its message. A missing transport does not
raise after the substrate is already written — that would strand the change; the step reports
IN_TRANSPORT and names what is missing.

Consequences: callers on ABAP must supply `transport_request` and `route` to get a completable step,
and must drive `advance_transport` per hop. Route order and write-locked hops are enforced by
`transport` and the registry, so PROD cannot be reached by skipping QA.

Touches invariant 4 (ledger is append-only and hash-chained) by extending what the chain records —
never by weakening it. "SNAPSHOT" and "EXECUTED" are still emitted verbatim, so `Ledger.approve()`'s
SoD and snapshot-first gates are unchanged. Invariants 3, 6 and 7 are re-used, not relaxed:
importing into a hop calls `registry.assert_writable`.

# ADR-0002: Governance ledger is hash-chained and append-only
Status: accepted. J-SOX evidence must be tamper-evident without trusting the platform operator.
SHA-256 chain, offline-verifiable; apjidokal gates (SoD, snapshot-first) enforced at append time in core,
not in the API layer, so no client can bypass them.

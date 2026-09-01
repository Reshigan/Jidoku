# CLAUDE.md — jidoka-core
Domain kernel. STDLIB ONLY — do not add dependencies; the governance gates must be auditable with zero supply chain.
Every module guards an invariant (see root CLAUDE.md #1–#7). Changing gate behaviour requires: failing test first,
ADR in docs/adr/, and the test proving the gate holds after. Public API is what services/api imports — treat as semver.

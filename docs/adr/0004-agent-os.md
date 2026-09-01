# ADR-0004: Agents run in an OS with privilege rings, not a tool loop
Status: accepted. Tool lists are not a security boundary — they are a suggestion to a model. Safety properties we
must guarantee (no self-approval, no writes to source systems, no unbounded spend, universal halt) are enforced
below cognition: ring ceilings asserted at import, a single capability-checked syscall dispatch, budgets that kill,
supervision that cannot widen privilege on restart. Consequence: every new agent action requires a deliberate
capability assignment. That friction is the feature.

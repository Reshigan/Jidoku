"""JIDOKA Agent OS — an operating system for agents that act on production systems.

The premise: an agent with tools is an application. An agent that must not be able to do certain things,
ever, regardless of what it decides, needs an operating system — privilege rings, a capability-checked
syscall boundary, resource budgets, supervision, and a kernel that cannot be argued with.

Ring 0  kernel        gates, ledger, capability checks. No agent runs here.
Ring 1  services      adapters, compiler, verification jobs. Trusted, still capability-bound.
Ring 2  agents        the K5 consultant and its economy. Builder authority only.
Ring 3  untrusted     red-team, external content processors. Read-only, no artefact emission.
"""
__version__ = "0.1.0"

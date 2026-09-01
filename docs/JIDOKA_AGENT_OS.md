# JIDOKA AGENT OS — ARCHITECTURE v1.0
## Why an agent that touches production systems needs an operating system, not a tool loop

An agent with tools is an application: what it can do is whatever its prompt and tool list allow, and safety
depends on the model behaving. An agent that must be **incapable** of certain actions — regardless of what it
decides, how it is prompted, or whether it is adversarial — needs the thing operating systems were invented for:
privilege separation enforced below the layer that reasons.

JIDOKA OS is that layer. The agent's cognition sits in userland. Everything that matters sits in the kernel,
where argument is not a supported input format.

---

## 1 · PRIVILEGE RINGS

| Ring | Occupants | Ceiling |
|---|---|---|
| **0 Kernel** | gates, ledger, capability checks, halt flag | Everything. **No process may be spawned here** — the kernel is not a process |
| **1 Service** | adapters, compiler, verification jobs, operator agent | May write to TARGET systems; may never approve |
| **2 Agent** | K5 consultant, architect, statutory sentinel | Builder authority: read, plan, emit, write, raise decisions. **Never approve, never resolve** |
| **3 Untrusted** | red-team auditor, economist, external content processors | Read and halt. Nothing else |

The ceiling belongs to the ring, not the manifest: a process may request *less* than its ring allows and never
more. Capabilities can be dropped at runtime, never acquired — privilege flows one way, and a restart after a
kill re-derives capabilities from the ring rather than the (possibly tampered) manifest.

**The structural invariant, asserted at import time:** `APPROVE` and `RESOLVE_DP` exist in no ring an agent can
occupy. Not policy, not prompt — an assertion that fails the build.

## 2 · THE SYSCALL BOUNDARY

The only path from cognition to the world. Every call passes six checks in fixed order:

```
halt state → capability → write-lock (registry) → budget → handler → ledger entry
```

There is no second path. An adapter cannot be imported and called directly by an agent process; the tool list is
not the security boundary, the syscall table is. Adding a syscall **requires** assigning it a capability — the
table has no default, so a new capability cannot be smuggled in as an omission. Denied syscalls are themselves
evidence: refusal is appended to the hash chain, which is how "what it refused" becomes a reportable number.

## 3 · PROCESSES, BUDGETS, SUPERVISION

Agents are processes with manifests: name, ring, capabilities, token budget, syscall budget, and an **objective**.
Tokens are CPU time. Exceeding budget **kills the process rather than degrading it silently** — a runaway agent
stops being an agent instead of becoming a cheaper, worse one. The supervisor spawns, kills and restarts under an
explicit policy, and every lifecycle event is ledgered.

## 4 · THE SCHEDULER: SHIFTS AND THE COST OF SILENCE

Two scarce resources, scheduled separately. **Machine work** runs by shift phase — NIGHT for extract, diff,
regression, forecast refit, evidence assembly; DAY for human-facing work. **Human attention** is rationed by an
interruption budget, and the queue is ordered by *cost of silence*: what it costs the programme if this goes
unsaid until tomorrow. Findings that lose the contest are not discarded — they are deferred into the morning
handover. This is the team-member model made mechanical rather than aspirational.

## 5 · THE ECONOMY: OPPOSED OBJECTIVES, ASYMMETRIC AUTHORITY

Five processes, no shared memory, typed messages through the kernel:

| Process | Objective | Ring |
|---|---|---|
| architect | maximise fit-to-standard within constraints | 2 |
| statutory sentinel | detect any value that should be a signed client source | 2 (raise-DP, no write) |
| operator | minimise execution risk | 1 |
| **auditor** | **maximise findings** | **3 — rewarded for breaking things, trusted with nothing** |
| economist | price delay, deltas, lifetime cost | 3 |

The auditor's placement is the design's sharpest edge: the process whose objective is to attack the work is given
the least authority in the system. It can see everything and change nothing. Objections are logged as messages,
which is what makes disagreement a product rather than a failure.

## 6 · THE HALT: A KERNEL PRIMITIVE, NOT A FEATURE

`sys_halt` is held by every process in every ring, and by every human. Raising it stops all dispatch except
reading and further halting. It requires a reason — an unexplained stop teaches nobody anything — and it cannot be
cleared by whoever raised it. The andon cord, in the kernel, where it cannot be disabled by a UI change.

## 7 · WHAT THIS BUYS

A jailbroken prompt, a confused model, a malicious instruction inside an ingested document, a bug in the agent's
own reasoning: none widens the reachable action set. The blast radius of "the AI was wrong" is bounded by the
capability grant, not by the quality of the reasoning that went wrong. That is the only honest way to run an
agent against a production payroll system — and it is testable, which is why 19 tests here assert what the system
*cannot* do rather than what it can.

*goNXT · What Comes Next is Built Here — and here, it is proven. · Agent OS Architecture*

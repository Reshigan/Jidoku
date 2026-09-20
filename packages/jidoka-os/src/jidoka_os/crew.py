"""A crew of consultants that runs an engagement, and stops where a person is required.

The economy in `economy.py` has always described five agents with opposed objectives. This is
what they actually do: one pass over an engagement, each agent acting only through the syscall
boundary, each holding only the authority its ring permits. The division of labour is not a
convention anybody has to remember — it is the capability table. The operator cannot emit an
artefact because ring SERVICE was never granted EMIT. The auditor cannot write a single ledger
row because ring UNTRUSTED holds READ_SYSTEM and HALT and nothing else. No agent in any ring can
approve, because APPROVE exists in no ring an agent can occupy.

What the crew can do unattended is everything up to a human gate: sequence the work, read live
state, rehearse every Tier-A write as a dry run, hand a person the Tier-B and Tier-C artefacts
they must do themselves, raise the decisions nobody may guess, verify the result and price what
remains. What it cannot do is arm a live write or approve its own work — invariants 6 and 7 —
so a run ends in a handover rather than a fait accompli. That is the design, not a limitation
pending a braver release: a team that could sign off its own build is not a team, it is a rubber
stamp with a budget.

Pure over its inputs. Every effect goes through `kernel.dispatch`, and the handlers behind it are
registered by the caller, so this module knows nothing about adapters, HTTP or SAP.
"""
from .capabilities import CapabilityError
from .economy import Message, MessageBus, architect, auditor, economist, operator, sentinel
from .process import BudgetExceeded, State
from .syscalls import HaltedError, SyscallError

#: The step states this module reasons about. Spelled here rather than imported: jidoka-os does
#: not depend on jidoka-core, and these are the words the handler hands back across the syscall
#: boundary. `jidoka_core.executor` is where they are defined for the executor's own use.
DRY_RUN, APPLIED, VERIFIED, IN_TRANSPORT, PARTIAL = (
    "DRY_RUN", "APPLIED", "VERIFIED", "IN_TRANSPORT", "PARTIAL")

#: Field-name markers that make a value statutory until proven otherwise. Published here, like the
#: scrubber's patterns, because a gate nobody can read is a gate nobody can argue with. A signed
#: workbook is not a statutory source: invariant 5 wants a client evidence reference, and a
#: consultant typing a leave accrual from memory is the exact failure this platform exists to stop.
STATUTORY_MARKERS = ("accrual", "entitlement", "statutory", "tax", "minimum", "maximum",
                     "threshold", "rate", "contribution", "levy", "notice_period", "overtime")


def statutory_fields(record) -> list[str]:
    """Intent fields whose name says statutory and whose source carries no evidence reference."""
    if (record.source or {}).get("evidence"):
        return []
    return sorted(f for f, v in (record.intent or {}).items()
                  if not isinstance(v, dict)
                  and any(m in f.lower() for m in STATUTORY_MARKERS))


def _agent(kernel, manifest, by: str):
    proc = kernel.supervisor.spawn(manifest, by)
    return proc


def _card(proc, did: list[str]) -> dict:
    """What one agent did, and what it was allowed to do. Both, always — a report that lists the
    work without the authority reads like a person's and hides the whole point."""
    return {"name": proc.manifest.name, "ring": proc.capabilities.ring.name,
            "objective": proc.manifest.objective,
            "capabilities": sorted(proc.manifest.caps),
            "syscalls": proc.syscalls_made, "tokens": proc.tokens_used,
            "state": proc.state.value, "exit_reason": proc.exit_reason, "did": did}


def _call(kernel, proc, call: str, log: list[str], note: str, **kw):
    """One syscall, with every refusal recorded rather than raised into the run.

    A crew that fell over on the first gate would be useless: refusals are the product here. A
    capability error, a budget kill and a halted line are all reported in the agent's own card,
    and the run keeps going with the agents that still can.
    """
    try:
        out = kernel.dispatch(proc, call, **kw)
        log.append(note)
        return out, None
    except CapabilityError as ex:
        log.append(f"refused: {ex}")
        return None, ("capability", str(ex))
    except BudgetExceeded as ex:
        log.append(f"killed: {ex}")
        return None, ("budget", str(ex))
    except HaltedError as ex:
        log.append(f"stopped: {ex}")
        return None, ("halted", str(ex))
    except SyscallError as ex:
        log.append(f"unavailable: {ex}")
        return None, ("syscall", str(ex))
    except Exception as ex:                    # noqa: BLE001 — a handler's own refusal
        log.append(f"{type(ex).__name__}: {ex}")
        return None, ("handler", str(ex))


def run(kernel, *, records, open_dp_ids, actor: str, bus: MessageBus | None = None,
        verify=None) -> dict:
    """One crew pass over one engagement.

    `records` are the engagement's loaded IR records, `open_dp_ids` every decision point that
    already exists (open or resolved) so the sentinel never re-raises a question a person has
    already answered — a second run that wiped a human's decision would be worse than no run.
    `verify` is the engagement's verification pass, called last and never by an agent: reading a
    customer's systems to check them is the platform's act, and its findings belong to everybody.
    """
    bus = bus or MessageBus(kernel.ledger)
    crew, waiting, raised, steps, artefacts = [], [], [], [], []
    by_key = {r.key: r for r in records}

    # --- statutory sentinel: the values nobody may guess ------------------------------------
    sen = _agent(kernel, sentinel(), actor)
    log: list[str] = []
    for rec in records:
        for field in statutory_fields(rec):
            dp_id = f"DP-STAT-{rec.key}-{field}".upper().replace(" ", "_")
            if dp_id in open_dp_ids:
                log.append(f"{dp_id} already exists — not re-asked")
                continue
            _, err = _call(
                kernel, sen, "sys_raise_dp", log, f"raised {dp_id}",
                dp_id=dp_id, dp_type="STATUTORY", owner=(rec.source or {}).get("signed_by", "") or "client",
                question=(f"{rec.key}: {field!r} reads as a statutory value but its source is a "
                          f"signed workbook, not a client evidence reference. What is the value, "
                          f"and which signed client document establishes it?"),
                detail=dp_id)
            if err is None:
                raised.append(dp_id)
                waiting.append({"what": dp_id, "who": (rec.source or {}).get("signed_by", "") or "client",
                                "why": f"statutory value {field!r} on {rec.key} has no evidence reference"})
    crew.append(_card(sen, log))

    # --- architect: sequence the work --------------------------------------------------------
    arc = _agent(kernel, architect(), actor)
    log = []
    plan, plan_block = None, None
    out, err = _call(kernel, arc, "sys_plan", log, "built the run plan", detail="plan")
    if err:
        plan_block = err[1]
        # An open decision point stopping the plan is the platform working (invariant 2). Say so
        # in the handover rather than reporting a failed run.
        waiting.append({"what": "the run plan", "who": "whoever owns the open decisions",
                        "why": plan_block})
    else:
        plan = out
        # Tier B and C are a person's work. The architect emits what that person needs; the
        # operator could not, because ring SERVICE holds no EMIT capability.
        for step in plan["steps"]:
            if step["tier"] == "A":
                continue
            payload, err = _call(kernel, arc, "sys_emit_artefact", log,
                                 f"emitted the {step['tier']} artefact for {step['key']}",
                                 key=step["key"], detail=step["key"])
            if err:
                continue
            steps_for_a_person = (payload or {}).get("steps") or []
            artefacts.append({"key": step["key"], "tier": step["tier"],
                              "kind": (payload or {}).get("kind", "artefact"),
                              # Tier B names the import; Tier C ships a numbered sheet. Carry
                              # whichever the adapter produced — a row reading "instruction_sheet"
                              # tells the person holding the keyboard nothing about what to do.
                              "human_step": ((payload or {}).get("human_step")
                                             or (steps_for_a_person[0] if steps_for_a_person else "")),
                              "steps": list(steps_for_a_person)})
            # No handover line here. Whether this is still outstanding is a fact about the live
            # system, and the verification below reads it — a chase written from the plan would
            # keep asking for work somebody finished an hour ago.
    crew.append(_card(arc, log))

    # --- operator: rehearse every write ------------------------------------------------------
    ops = _agent(kernel, operator(), actor)
    log = []
    for step in (plan or {}).get("steps", []):
        if step["tier"] != "A":
            continue
        rec = by_key.get(step["key"])
        if rec is None:
            continue
        _, err = _call(kernel, ops, "sys_extract", log, f"snapshot before {step['key']}",
                       key=step["key"], detail=step["key"])
        if err:
            steps.append({"key": step["key"], "tier": "A", "system": step["system"],
                          "status": "REFUSED", "detail": err[1]})
            continue
        res, err = _call(kernel, ops, "sys_write_tier_a", log, f"wrote {step['key']}",
                         system_id=step["system"], key=step["key"], detail=step["key"])
        if err:
            steps.append({"key": step["key"], "tier": "A", "system": step["system"],
                          "status": "REFUSED", "detail": err[1]})
            continue

        # On the ABAP stack the write is half the change: a verified write sits in a transport
        # until it lands in production (ADR-0006). The operator carries it the rest of the way,
        # one legal hop at a time, and stops the moment the route or a gate says stop. Bounded by
        # the route's own length — a loop that trusted the substrate to say "no next hop" would
        # spin forever the first time a substrate lied.
        hops = len((res.get("transport") or {}).get("route") or [])
        for _ in range(hops):
            if res.get("status") != IN_TRANSPORT:
                break
            state, err = _call(kernel, ops, "sys_advance_transport", log,
                               f"advanced {step['key']} to "
                               f"{(res.get('transport') or {}).get('next_hop') or 'its next hop'}",
                               system_id=step["system"], key=step["key"], detail=step["key"])
            if err:
                res = {**res, "detail": f"{res.get('detail', '')} {err[1]}".strip()}
                break
            # The detail travels with the status. Leaving the pre-advance sentence in place
            # left a row reading "not yet in production" beside a transport that had reached it.
            landed = state.get("currently_in")
            res = {**res, "transport": state,
                   "status": VERIFIED if state.get("in_production") else IN_TRANSPORT,
                   "detail": (f"written, verified, and imported into {landed} — in production"
                              if state.get("in_production")
                              else f"written and verified; now in {landed}, "
                                   f"next hop {state.get('next_hop')}")}

        steps.append(res)
        status = res.get("status")
        if status == DRY_RUN:
            waiting.append({"what": step["key"], "who": "an approver",
                            "why": "rehearsed, not written — a live write needs a named approver "
                                   "to arm the target, and the operator may never arm its own"})
        elif status in (VERIFIED, APPLIED):
            # The work is done and unreviewed. Invariant 4 wants a second person, and the crew is
            # never that person: the ledger refuses an approval from whoever executed.
            waiting.append({"what": step["key"], "who": "a reviewer who did not build it",
                            "why": "written and verified against the live system — an approval "
                                   "needs a second person, and the crew can never be one"})
        elif status == IN_TRANSPORT:
            waiting.append({"what": step["key"], "who": "whoever owns the transport route",
                            "why": res.get("detail") or "verified but not yet in production"})
        elif status == PARTIAL:
            waiting.append({"what": step["key"], "who": "an operator",
                            "why": "some operations landed and some were rejected — the substrate "
                                   "is in a partial state and needs a rollback from the snapshot"})
    crew.append(_card(ops, log))

    # --- auditor: objections, from a ring that cannot write anything --------------------------
    aud = _agent(kernel, auditor(), actor)
    log = []
    # Read the chain as it stands now, not as it stood when the run began. An auditor handed a
    # snapshot of the evidence from before the work objects to the work: it reported every step
    # as rehearsed-without-a-snapshot while the operator's snapshots sat two rows above on the
    # same chain. Stale evidence is not evidence.
    entries = list(kernel.ledger.entries)
    snapshotted = {e.get("task") for e in entries if e.get("action") == "SNAPSHOT"}
    # NOT_APPLIED counts as checked: the platform read the live system and found the record
    # unbuilt. That is a verdict, and objecting "nobody has ever looked at this" over it would be
    # false — the objection is for records nothing has ever been compared against.
    checked = {e.get("task") for e in entries
               if e.get("action") in ("VERIFIED", "DRIFT_DETECTED", "NOT_APPLIED")}

    def object_to(kind: str, body: dict, text: str):
        bus.send(Message(frm=aud.manifest.name, to="engagement", kind=kind, body=body))
        log.append(text)

    for rec in records:
        if rec.key not in checked:
            object_to("OBJECTION", {"key": rec.key, "finding": "never verified"},
                      f"{rec.key} has signed intent and no verification on the chain")
        if not (rec.source or {}).get("cell_range"):
            object_to("OBJECTION", {"key": rec.key, "finding": "provenance without a location"},
                      f"{rec.key} names a workbook but not where in it")
    for step in steps:
        if step.get("status") == "DRY_RUN" and step["key"] not in snapshotted:
            object_to("OBJECTION", {"key": step["key"], "finding": "rehearsed without a snapshot"},
                      f"{step['key']} was rehearsed with no before-state on the chain")

    # The strongest thing an auditor can do here, and the only thing it can do at all besides
    # objecting: pull the cord. It cannot write the finding down — that is the ring — so the halt
    # is how a tampered chain becomes everybody's problem.
    try:
        intact = kernel.ledger.verify_chain()
    except Exception:                          # noqa: BLE001 — a raising chain is a broken chain
        intact = False
    if not intact:
        _call(kernel, aud, "sys_halt", log, "pulled the andon cord: the ledger chain is broken",
              reason="ledger chain does not verify — every statement on it is unproven", by=actor)
        waiting.append({"what": "the line", "who": "whoever can clear a halt",
                        "why": "the auditor halted the line: the ledger chain does not verify"})
    crew.append(_card(aud, log))

    # --- economist: price what is left, and say what was not priced ---------------------------
    eco = _agent(kernel, economist(), actor)
    log = []
    tiers = {t: sum(1 for s in (plan or {}).get("steps", []) if s["tier"] == t) for t in "ABC"}
    economics = {
        "steps": tiers,
        "manual_steps": tiers["B"] + tiers["C"],
        "rehearsed": sum(1 for s in steps if s.get("status") == "DRY_RUN"),
        "refused": sum(1 for s in steps if s.get("status") == "REFUSED"),
        "open_questions": len(raised),
        # Named rather than guessed. Cost of delay and lifetime cost of a custom object are real
        # numbers on a real programme, and inventing either from step counts would be exactly the
        # fluent assertion this platform exists to refuse.
        "not_priced": ["cost of delay", "lifetime cost per custom object", "rework avoided"],
    }
    log.append(f"priced the delta pool: {tiers['A']} automatable, {economics['manual_steps']} manual")
    crew.append(_card(eco, log))

    verification = verify() if verify else None
    for item in (verification or {}).get("awaiting_a_person", []):
        # The chase, grounded: the artefact went out, and the live system still does not have it.
        since = item.get("handed_over")
        waiting.append({"what": item["key"], "who": "a consultant at the keyboard",
                        "why": f"{item['reason']}"
                               + (f" Handed over {since}." if since else "")})

    return {"crew": crew, "plan": plan, "plan_blocked": plan_block, "steps": steps,
            "artefacts": artefacts, "decisions_raised": raised,
            "objections": [{"from": m.frm, "kind": m.kind, "body": m.body} for m in bus.objections()],
            "economics": economics, "verification": verification,
            "waiting_on_a_person": waiting, "halted": kernel.halted,
            "halt_reason": kernel.halt_reason}

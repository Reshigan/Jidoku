"""Where this platform was wrong, and how often its gates stopped work that was fine.

Every other projection over the chain reports on the engagement. This one reports on the platform,
and it is the one a customer should read first — because a governance tool that publishes only its
successes is asking to be trusted on its own account, which is the thing it exists to stop anyone
else doing.

Four questions, all answered from the chain and none of them flattering by construction:

  **Did my gates stop work that was fine?** A refusal is on the ledger now (ADR-0031), and what
  happened next is too. A gate cleared within the hour, every time, is friction with a governance
  costume on — the person had the snapshot, took it, and carried on. A gate nothing ever clears is
  stopping something real. Neither number is good or bad on its own, which is why both are
  published rather than scored.

  **Was my twin right?** Fidelity already answers this and is reused rather than recomputed
  (`twin.fidelity`), including its refusal to quote a rate from a handful of comparisons.

  **What did I get wrong?** Drift found on a record this platform had already called verified; a
  write that landed in part; a rollback. Each one is a case where the platform said something and
  the system disagreed.

  **What can I not measure?** Published, because the gap between what a metric covers and what a
  reader assumes it covers is where every dishonest dashboard lives.

Pure, stdlib, and a projection: run it twice on the same chain and it says the same thing.
"""
from datetime import datetime

#: How the ledger writes a timestamp.
TS = "%Y-%m-%dT%H:%M:%SZ"

#: A refusal cleared faster than this was, in practice, a step the person already had in hand.
#: Published so it can be argued with: it is a judgement about what "friction" means, not a
#: measurement, and a programme with slower approval cycles will want a different number.
FRICTION_WITHIN_HOURS = 1.0

#: What this cannot see, stated where the numbers are rather than in a footnote nobody opens.
UNMEASURABLE = (
    "Work that never reached a gate. A consultant who saw a refusal coming and did the change by "
    "hand in the SAP GUI leaves nothing on this chain, and that is the most expensive failure "
    "this platform can have.",
    "Whether a refusal was correct. This counts how quickly each one was cleared, which is a "
    "proxy for friction and not a verdict — a gate cleared in a minute may have caught a real "
    "mistake a minute before it landed.",
    "Harm avoided. A change that was never made because the platform blocked it cannot be "
    "compared against the world where it was, and any number claiming otherwise is invented.",
    "Anything about a system nobody connected. An engagement with no read path has nothing to "
    "be wrong about, and its silence is not a clean record.",
)


def _at(entry: dict):
    try:
        return datetime.strptime(entry.get("ts", ""), TS)
    except ValueError:
        return None


def refusals(entries: list[dict], within_hours: float = FRICTION_WITHIN_HOURS) -> dict:
    """Every gate that fired, and what happened after it.

    "Cleared" means the same person got past the same gate later — they took the snapshot, closed
    the decision, armed the target. It is deliberately not called "overturned": nothing here knows
    whether the gate was right, only whether it held.
    """
    fired: dict[str, dict] = {}
    for entry in entries:
        if entry.get("action") != "REFUSED":
            continue
        gate = entry.get("task", "")
        row = fired.setdefault(gate, {"gate": gate, "kind": entry.get("gate", ""),
                                      "status": entry.get("status", 0), "fired": 0,
                                      "cleared": 0, "cleared_fast": 0, "standing": 0,
                                      "words": entry.get("detail", ""), "people": set()})
        row["fired"] += 1
        row["people"].add(entry.get("actor", ""))

        after = _cleared_after(entries, entry)
        if after is None:
            row["standing"] += 1
            continue
        row["cleared"] += 1
        t0, t1 = _at(entry), _at(after)
        if t0 and t1 and (t1 - t0).total_seconds() / 3600 <= within_hours:
            row["cleared_fast"] += 1

    out = []
    for row in fired.values():
        row["people"] = len(row["people"])
        row["reads_as"] = _reads_as(row)
        out.append(row)
    out.sort(key=lambda r: (-r["fired"], r["gate"]))
    return {"gates": out,
            "fired": sum(r["fired"] for r in out),
            "cleared": sum(r["cleared"] for r in out),
            "still_standing": sum(r["standing"] for r in out),
            "friction_within_hours": within_hours,
            "method": ("A refusal is cleared when the same person later gets past the same gate. "
                       f"Cleared inside {within_hours:g}h counts as friction — they had the "
                       "missing step in hand. Nothing here knows whether a refusal was correct.")}


def _cleared_after(entries: list[dict], refusal: dict) -> dict | None:
    """The same person, past the same gate, later. Nothing else counts: somebody else succeeding
    where you were refused is separation of duties working, not your refusal being cleared."""
    seen = False
    for entry in entries:
        if entry is refusal:
            seen = True
            continue
        if not seen:
            continue
        if (entry.get("action") == "CLEARED" and entry.get("task") == refusal.get("task")
                and entry.get("actor") == refusal.get("actor")):
            return entry
    return None


def mistakes(entries: list[dict]) -> dict:
    """Cases where this platform said something and the system disagreed.

    Drift on a record already called verified is the one that matters most: the platform did not
    fail to know, it knew wrongly and said so with confidence.
    """
    verified: set[str] = set()
    after_verified, partial, rolled_back = [], [], []
    for entry in entries:
        task, action = entry.get("task"), entry.get("action")
        if action == "VERIFIED":
            verified.add(task)
        elif action == "DRIFT_DETECTED":
            if task in verified:
                after_verified.append(task)
            verified.discard(task)
        elif action == "PARTIAL":
            partial.append(task)
        elif action == "ROLLED_BACK":
            rolled_back.append(task)
    return {"drift_after_verified": sorted(set(after_verified)),
            "landed_in_part": sorted(set(partial)),
            "rolled_back": sorted(set(rolled_back)),
            "method": ("Drift on a record this platform had already verified is counted "
                       "separately from drift in general: the first is being wrong, the second is "
                       "the system changing under a correct reading.")}


def account(entries: list[dict], fidelity: dict | None = None,
            within_hours: float = FRICTION_WITHIN_HOURS) -> dict:
    """The platform's account of itself. Nothing is scored and nothing is a grade — a single
    number here would be quoted, and the point is the four questions, not a badge."""
    gates = refusals(entries, within_hours)
    wrong = mistakes(entries)
    return {"refusals": gates, "mistakes": wrong,
            "twin": fidelity or {},
            "unmeasurable": list(UNMEASURABLE),
            "says": _says(gates, wrong, fidelity or {})}


def _reads_as(row: dict) -> str:
    if row["fired"] and row["cleared_fast"] == row["fired"]:
        return ("cleared every time, fast — this gate is asking for a step people already have "
                "in hand, which is friction unless the step is the point")
    if row["standing"] == row["fired"]:
        return "never cleared — this gate is stopping something nobody has resolved"
    return "sometimes cleared, sometimes not — the ordinary shape of a gate that is working"


def _says(gates: dict, wrong: dict, fidelity: dict) -> str:
    bits = []
    if gates["fired"]:
        bits.append(f"I refused {gates['fired']} time(s); {gates['cleared']} were cleared by the "
                    f"same person and {gates['still_standing']} still stand")
    else:
        bits.append("I have refused nothing here, which means either the work was clean or it "
                    "never reached me")
    n = len(wrong["drift_after_verified"])
    bits.append(f"I called {n} record(s) verified and later found the system disagreeing" if n
                else "Nothing I called verified has since disagreed")
    if fidelity.get("status") == "CALIBRATED":
        bits.append(f"my twin was right {fidelity['fidelity']:.0%} of the time over "
                    f"{fidelity['scored']} settled predictions")
    else:
        bits.append("my twin has not made enough settled predictions to quote a rate")
    return ". ".join(bits) + "."

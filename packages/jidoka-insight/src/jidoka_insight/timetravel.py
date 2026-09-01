"""Time-travel: reconstruct programme state as of any moment from the ledger. Event sourcing —
the ledger is the truth; 'current state' is just as_of(now)."""
def as_of(ledger_entries: list[dict], ts: str) -> dict:
    state = {"approved": set(), "halted": False, "open_dps": set(), "rolled_back": set()}
    for e in ledger_entries:
        if e["ts"] > ts:
            break
        a, t = e["action"], e["task"]
        if a == "APPROVED": state["approved"].add(t); state["rolled_back"].discard(t)
        elif a == "ROLLED BACK": state["rolled_back"].add(t); state["approved"].discard(t)
        elif a == "DP_RAISED": state["open_dps"].add(t)
        elif a == "DP_RESOLVED": state["open_dps"].discard(t)
        elif a == "LINE_HALTED": state["halted"] = True
        elif a == "LINE_RESUMED": state["halted"] = False
    return state

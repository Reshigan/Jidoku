"""Every engagement at once: is the night running, what is blocking, and who is the bottleneck.

The night shift has iterated every engagement since ADR-0028 and its summary went to a log and an
exit code. A partner running eleven programmes had no way to ask the question they actually ask —
*which of these needs me today* — without opening eleven screens and forming the answer by hand.

Nothing here is new work. Every number is the same projection the engagement's own screen shows,
run across the store: the clock off the ledger (ADR-0030), the assurance fraction (ADR-0021), the
statutory decisions that hard-block planning (invariant 2), and the platform's own account of
itself (ADR-0031). A roll-up that computed anything differently from the screen it rolls up would
be a second opinion, and the first argument in every steering meeting would be about which one is
right.

Ordered by what needs a person soonest, because a list sorted by name is a list somebody has to
read all of.
"""
from fastapi import APIRouter, Depends
from jidoka_core.accountability import refusals
from jidoka_core.assurance import assure
from jidoka_os.handover import clock

from ..auth import Identity, require
from .engagements import STORE

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _row(e) -> dict:
    entries = e.ledger.entries
    night = clock(entries)
    statutory = [d.dp_id for d in e.decisions.dps.values()
                 if d.resolution is None and d.dp_type == "STATUTORY"]
    open_dps = [d.dp_id for d in e.decisions.dps.values() if d.resolution is None]
    a = assure(e.ir, entries)
    try:
        e.ledger.verify_chain()
        chain = True
    except Exception:                        # noqa: BLE001 — a raising chain is a broken one
        chain = False
    return {"engagement_id": e.engagement_id, "name": e.name, "client": e.client, "phase": e.phase,
            "records": len(e.ir), "people": len(e.people),
            "chain_ok": chain,
            "night_running": night["running"], "night_says": night["says"],
            "statutory_open": statutory, "decisions_open": open_dps,
            "proven": a.fraction, "claimed": a.claimed,
            "refusals_standing": refusals(entries)["still_standing"],
            **_needs(chain, night, statutory)}


#: Worst first, by the same reasoning the night shift ranks findings with (ADR-0027): what it
#: costs the programme for this to go unseen today. A rank, not a keyword match on the sentence —
#: sorting on the words would mean rewording a message silently reorders the list.
CHAIN, STATUTORY, NIGHT, NOTHING = 0, 1, 2, 3


def _needs(chain_ok: bool, night: dict, statutory: list) -> dict:
    """One line, and the worst thing only. A row that says three things says none of them."""
    if not chain_ok:
        return {"urgency": CHAIN, "needs_a_person":
                "the ledger chain does not verify — nothing this engagement claims is provable"}
    if statutory:
        return {"urgency": STATUTORY, "needs_a_person":
                f"{len(statutory)} statutory decision(s) are blocking the plan, and JIDOKA will "
                f"not invent them"}
    if not night["running"]:
        return {"urgency": NIGHT, "needs_a_person": night["says"]}
    return {"urgency": NOTHING, "needs_a_person": ""}


@router.get("")
def portfolio(identity: Identity = Depends(require("read"))):
    """Every engagement this kernel holds, worst first.

    Read access, not a partner role: a roll-up that only the most senior person can open is a
    roll-up that gets screenshotted into a slide once a month and is wrong by the meeting.
    """
    rows = [_row(e) for e in STORE.list()]
    rows.sort(key=lambda r: (r["urgency"], r["name"]))
    attention = [r for r in rows if r["needs_a_person"]]
    return {"engagements": rows,
            "total": len(rows),
            "need_a_person": len(attention),
            "says": _says(rows, attention)}


def _says(rows: list, attention: list) -> str:
    if not rows:
        return "No engagements on this kernel yet."
    if not attention:
        return (f"{len(rows)} engagement(s), and none of them needs a person today: every chain "
                f"verifies, no statutory decision is blocking a plan, and every night ran.")
    return (f"{len(attention)} of {len(rows)} engagement(s) need a person today. The rest are "
            f"running: chains verify, no statutory decision is blocking, and the nights ran.")

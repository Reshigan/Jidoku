"""Who this engagement may ask for something (M4).

A request addressed to a role is a request nobody answers. Registering people lets the night shift
address them by name, ask the least senior person who can actually sign the thing, and respect
their clock — nothing pings Maputo at 06:00 on a Saturday unless what is waiting costs more than
the interruption does.

Authority is written in the platform's own permission names, so "who may resolve a statutory
decision" is checked against the same table the API gates on rather than against a job title.
Cost is declared by the organisation and never inferred: a platform that guessed at somebody's
seniority would be guessing about a person.
"""
from fastapi import APIRouter, Depends, HTTPException
from jidoka_os.people import load
from pydantic import BaseModel

from ..auth import ROLE_PERMISSIONS, Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/people", tags=["people"])

#: Every permission any role can hold. A person declared with anything else is a typo that would
#: otherwise route silently to nobody.
KNOWN = {p for perms in ROLE_PERMISSIONS.values() for p in perms}


class PersonIn(BaseModel):
    name: str
    authority: list[str] = []
    cost: int = 1
    hours: tuple[int, int] = (9, 17)
    utc_offset: int = 0
    days: list[int] = [0, 1, 2, 3, 4]
    capacity_per_week: int = 20


@router.post("")
def register(eid: str, body: list[PersonIn],
             identity: Identity = Depends(require("register_system"))):
    """Declare the team. Replaces the list: a team is a statement about now, not an append log."""
    e = get_or_404(eid)
    rows = [p.model_dump() for p in body]
    unknown = {a for row in rows for a in row["authority"]} - KNOWN
    if unknown:
        raise HTTPException(
            422, f"Unknown authority {sorted(unknown)}. Authority is written in the platform's own "
                 f"permission names, so it can be checked against the table the API gates on: "
                 f"{sorted(KNOWN)}.")
    for row in rows:
        if not row["name"].strip():
            raise HTTPException(422, "A person with no name cannot be asked for anything.")
    e.people = rows
    e.persist_people()
    e.ledger.append("TEAM", "PEOPLE_REGISTERED", identity.subject,
                    f"{len(rows)} person(s): " + ", ".join(r["name"] for r in rows),
                    people=len(rows))
    return {"people": rows}


@router.get("")
def team(eid: str, identity: Identity = Depends(require("read"))):
    """The team, and what the platform can ask each of them for."""
    e = get_or_404(eid)
    return {"people": e.people,
            "can_be_asked_for": sorted({a for p in load(e.people) for a in p.authority})}

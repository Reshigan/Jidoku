"""An objection, the override that set it aside, and the revisit that closes the loop.

M6 of the team-member model, and the one behaviour in it that costs something to get right:

> When a plan conflicts with a codex rule, JIDOKA states the objection **once**, in plain terms,
> with the consequence and its recommendation — then defers, records the override with the
> decider's name, and **revisits it at the point where the consequence lands**. Not to be right;
> because the loop closing is what makes the next objection worth hearing.

Every clause there is a constraint on this module.

  **Once.** An objection is identified by what it is about and what it found, so raising the same
  one twice is not a second objection — it is the same one, still open. A tool that repeats itself
  is a tool people configure to be quiet, and then the one objection that mattered is quiet too.

  **With the consequence and the recommendation.** A finding with neither is a complaint. Both are
  required at the point of raising, because a consequence invented later to justify an objection
  is not a prediction.

  **Then defers.** Nothing here blocks anything. An objection is not a gate — the gates are the
  seven invariants, and they refuse. This is the platform disagreeing with a decision it has no
  standing to prevent, which is a different thing and must not be dressed as the first.

  **The override carries the decider's name.** Not a role, not "the client": a person. An override
  nobody signed is the platform being overruled by the weather.

  **And it is revisited where the consequence lands.** Not on a timer — at the phase where the
  thing predicted becomes observable. What the revisit reports is what the chain says happened,
  never a verdict on who was right: the objection said this record rests on an attestation, the
  override said ship it, and here is what the system has said since. Vindication is not a feature.

Pure, stdlib, projections over the chain. Nothing here stores a state — open, overridden, revisited
are all read back from the entries, so a restart cannot lose an objection and no second copy can
disagree with the ledger.
"""
import hashlib
from dataclasses import dataclass

from .lifecycle import PHASES

RAISED = "OBJECTION_RAISED"
OVERRIDDEN = "OBJECTION_OVERRIDDEN"
WITHDRAWN = "OBJECTION_WITHDRAWN"
REVISITED = "OBJECTION_REVISITED"

#: Where a consequence lands by default. HYPERCARE, because that is where a configuration decision
#: stops being an opinion and starts being somebody's morning — "the three sev-2s we carried into
#: hypercare in November are the two incidents open this morning".
DEFAULT_REVISIT = "HYPERCARE"

#: An objection is one of these three things and nothing else. A platform that can object to
#: anything objects to everything.
GROUNDS = (
    "unevidenced",      # something is claimed done on less than a read of the live system
    "unsafe",           # the sequence or the state makes a failure likely, and it is nameable
    "uneconomic",       # the cost is knowable and nobody has counted it
)


class ObjectionError(Exception): ...


def objection_id(about: str, finding: str) -> str:
    """Identity is what it is about and what it found — so "state it once" is enforceable rather
    than remembered. Short, stable, and derived: nothing has to allocate or store it."""
    return "OBJ-" + hashlib.sha256(f"{about}\x00{finding}".encode()).hexdigest()[:10].upper()


@dataclass(frozen=True)
class Objection:
    about: str              # the record, step or decision this is about
    finding: str            # what is wrong, in one line
    grounds: str            # one of GROUNDS
    consequence: str        # what happens if it goes ahead anyway
    recommendation: str     # what to do instead
    revisit_at: str = DEFAULT_REVISIT

    def __post_init__(self):
        if self.grounds not in GROUNDS:
            raise ObjectionError(
                f"{self.grounds!r} is not grounds for an objection. A platform that can object to "
                f"anything objects to everything; the grounds are {list(GROUNDS)}.")
        if not (self.consequence.strip() and self.recommendation.strip()):
            raise ObjectionError(
                "An objection states the consequence and the recommendation. A finding with "
                "neither is a complaint, and a consequence invented later to justify an objection "
                "is not a prediction.")
        if self.revisit_at not in PHASES:
            raise ObjectionError(
                f"{self.revisit_at!r} is not a phase — revisit happens where the consequence "
                f"lands, and the phases are {list(PHASES)}.")

    @property
    def objection_id(self) -> str:
        return objection_id(self.about, self.finding)

    def as_entry(self) -> dict:
        return {"about": self.about, "finding": self.finding, "grounds": self.grounds,
                "consequence": self.consequence, "recommendation": self.recommendation,
                "revisit_at": self.revisit_at}


def state(entries: list[dict]) -> dict[str, dict]:
    """Every objection this chain has ever carried, and where each one stands now."""
    out: dict[str, dict] = {}
    for e in entries:
        action, oid = e.get("action"), e.get("task")
        if action == RAISED and oid not in out:
            # Once. A second raising of the same objection is the same objection, and the chain
            # keeps both entries while this keeps one.
            out[oid] = {"objection_id": oid, "raised_at": e.get("ts", ""),
                        "raised_by": e.get("actor", ""), "status": "open",
                        "overridden_by": "", "override_reason": "", "overridden_at": "",
                        "revisited_at": "", "restated": 0,
                        **{k: e.get(k, "") for k in
                           ("about", "finding", "grounds", "consequence", "recommendation",
                            "revisit_at")}}
        elif action == RAISED:
            out[oid]["restated"] += 1
        elif oid in out and action == OVERRIDDEN:
            out[oid].update(status="overridden", overridden_by=e.get("actor", ""),
                            override_reason=e.get("detail", ""), overridden_at=e.get("ts", ""))
        elif oid in out and action == WITHDRAWN:
            out[oid]["status"] = "withdrawn"
        elif oid in out and action == REVISITED:
            out[oid].update(status="revisited", revisited_at=e.get("ts", ""))
    return out


def due(entries: list[dict], phase: str) -> list[dict]:
    """Objections whose consequence has landed: overridden, and the engagement is at or past the
    phase where the thing predicted becomes observable. Nothing is due before then — a revisit
    early is a platform asking to be told it was right."""
    if phase not in PHASES:
        raise ObjectionError(f"Unknown phase {phase!r} — phases are {list(PHASES)}.")
    here = PHASES.index(phase)
    return [o for o in state(entries).values()
            if o["status"] == "overridden"
            and o["revisit_at"] in PHASES and PHASES.index(o["revisit_at"]) <= here]


#: What the chain has said about a record since. Read back, never judged: the objection made a
#: prediction and the ledger is the only thing entitled to say what happened.
SINCE = {
    "DRIFT_DETECTED": "the live system has since disagreed with the signed intent",
    "PARTIAL": "a write landed only in part",
    "ROLLED_BACK": "it was rolled back",
    "VERIFIED": "it has since been read back from the live system and matched",
    "ATTESTED": "it still rests on a person's word",
    "UNCONFIRMABLE": "nothing has been able to check it",
}


def what_happened(entries: list[dict], about: str) -> dict:
    """What the chain says became of the thing objected to.

    Deliberately not a verdict. "The objection was right" is a claim about a world where the
    override did not happen, and nothing here can see that world. What it can see is what the
    ledger recorded afterwards, so that is what it reports — and where the ledger recorded
    nothing, it says so rather than reading silence as agreement.
    """
    seen = [e.get("action") for e in entries if e.get("task") == about]
    landed = [SINCE[a] for a in SINCE if a in seen]
    return {"about": about, "since": landed,
             "says": ("; ".join(landed) if landed else
                      "nothing has happened to it on this chain since — which is not the same as "
                      "nothing having happened")}

"""Drift: the live system disagreeing with signed intent.

Every configuration platform reports drift. JIDOKA treats it as something stronger: an open
question with a named owner. When a verification run finds a live value that signed intent does
not explain, the platform does not re-apply the intent (that overwrites a change nobody has
understood yet) and does not adopt the observed value (that launders an unsigned change into the
record). It appends the finding to the ledger and raises a decision point that blocks planning
until a human chooses — reassert the signed intent, or sign new intent that says the observed
state is now the design. Drift is a decision, not a report (ADR-0013).
"""
import hashlib
import json
from dataclasses import dataclass, field

from .decisions import DecisionPoint


#: A record that signed intent describes and nobody has built yet. Not drift: nothing changed
#: under anyone, because nothing was ever there. It is a status, and the plan is what closes it.
NOT_APPLIED = "NOT_APPLIED"

#: Handed to a person and not done. Also not drift — the platform produced the artefact and the
#: work is outstanding, which is a thing to chase rather than a question to answer.
AWAITING_A_PERSON = "AWAITING_A_PERSON"

#: How far a record has got, as read off the ledger. The three cases differ in what an absence
#: from the live system means, and nothing else here depends on them.
WRITTEN, HANDED_OFF, UNTOUCHED = "WRITTEN", "HANDED_OFF", "UNTOUCHED"

#: The product publishes no way to read this object back, so nothing here can confirm it (ADR-0022).
UNCONFIRMABLE = "UNCONFIRMABLE"

#: A named person said they did it. Weaker than verified and never displayed as if it were: a
#: person's word is evidence about a person, and the platform has not seen the system.
ATTESTED = "ATTESTED"


def intent_hash(intent) -> str:
    """Fingerprint of the intent an attestation covers.

    An attestation is about a specific change. When the signed intent moves underneath it, what
    somebody attested to is no longer what the record says, and treating the old word as current
    would launder a stale claim into a clean-looking report.
    """
    return hashlib.sha256(json.dumps(intent or {}, sort_keys=True, default=str).encode()).hexdigest()


@dataclass
class DriftFinding:
    """One record whose live state does not match its signed intent."""
    key: str
    status: str    # DRIFT | MISSING | NOT_APPLIED | AWAITING_A_PERSON | UNCONFIRMABLE | ATTESTED
    system: str
    fields: dict = field(default_factory=dict)   # field -> {"intent": ..., "live": ...}
    dp_id: str | None = None          # the decision point now blocking this record


def dp_id_for(key: str) -> str:
    return f"DP-DRIFT-{key}"


class DriftWatch:
    """Turns adapter verification verdicts into ledger entries and blocking decisions.

    Pure over its inputs: the caller reads the live system (through a bound connector) and hands
    each record's verdict in. The watch owns only the governance consequence, so no client can
    reach the live system and skip it.
    """

    def __init__(self, ledger, decisions):
        self.ledger = ledger
        self.decisions = decisions

    def unconfirmable(self, record, actor: str, reason: str,
                      attestation: dict | None = None) -> DriftFinding:
        """A record the product gives no read path for. There is nothing to compare, so nothing
        is compared — the alternative is an extract that fails and gets filed as "could not be
        read", which reads like a transient fault rather than a permanent limit.

        With a current attestation the finding is ATTESTED: a named person's word, on the chain,
        about a specific version of the intent. Without one, or with one whose intent has moved
        underneath it, the record is UNCONFIRMABLE and stays that way until somebody attests. No
        decision point either way: a missing read path is a fact about the product, not a
        question about the configuration, and blocking the plan on it would stop every engagement
        that touches a Provisioning switch.
        """
        key = record.key
        current = intent_hash(getattr(record, "intent", {}))
        fresh = bool(attestation) and attestation.get("intent_hash") == current
        status = ATTESTED if fresh else UNCONFIRMABLE

        if fresh:
            detail = (f"no read path — {reason} Attested by {attestation.get('actor')} "
                      f"at {attestation.get('ts')}; this platform has not seen the system.")
        elif attestation:
            detail = (f"no read path — {reason} The attestation by {attestation.get('actor')} "
                      f"covers an earlier version of this record's intent and no longer applies.")
        else:
            detail = f"no read path — {reason} Nobody has attested to it."

        self.ledger.append(key, status, actor, detail,
                           system=record.system_binding, status=status)
        return DriftFinding(key=key, status=status, system=record.system_binding,
                            fields={}, dp_id=None)

    def observe(self, record, verification: dict, actor: str,
                progress: str = WRITTEN) -> DriftFinding | None:
        """One record, one verdict. Returns the finding, or None when live state matches.

        `progress` is how far the record has got, read off the ledger: WRITTEN (this platform
        executed it), HANDED_OFF (an artefact was produced for a person to execute), or UNTOUCHED.
        It changes what an *absence* from the live system means, and nothing else:

        - UNTOUCHED  → NOT_APPLIED. Unbuilt work. Calling it drift raises a decision whose two
          answers, reassert or adopt, are both wrong when the real answer is "build it", and
          blocks planning on a question nobody should have been asked (ADR-0019).
        - HANDED_OFF → AWAITING_A_PERSON. The platform did its half — Tier B and C have no write
          path, so a person does them (ADR-0003) — and the work is outstanding. That is a thing
          to chase, with a date on it, not a question to answer (ADR-0021).
        - WRITTEN    → drift, and always was. We put it there and it is gone.

        A record that is *present* but disagrees is drift regardless of progress — in fact a
        record nobody built that exists anyway is the most interesting finding on the page,
        because somebody configured it outside this platform.
        """
        status = verification.get("status")
        key = record.key
        dp_id = dp_id_for(key)
        open_dp = dp_id in self.decisions.dps and self.decisions.dps[dp_id].resolution is None

        if status == "MATCH":
            if open_dp:
                # The live system matches again — but something changed it twice without a signed
                # record, and the second change is as unexplained as the first. The owner still
                # answers; a self-healing anomaly is an anomaly with better timing.
                self.ledger.append(key, "VERIFIED", actor,
                                   f"live state matches signed intent; {dp_id} remains open — "
                                   f"the drift that was observed is still unexplained")
            else:
                self.ledger.append(key, "VERIFIED", actor, "live state matches signed intent")
            return None

        fields = verification.get("drift", {}) or {}
        if status == "MISSING" and progress == UNTOUCHED:
            self.ledger.append(key, "NOT_APPLIED", actor,
                               f"absent from {record.system_binding}; this platform has never "
                               f"written it, so there is nothing to explain — it is unbuilt work",
                               status=NOT_APPLIED, system=record.system_binding)
            return DriftFinding(key=key, status=NOT_APPLIED, system=record.system_binding,
                                fields={}, dp_id=None)
        if status == "MISSING" and progress == HANDED_OFF:
            self.ledger.append(key, "AWAITING_A_PERSON", actor,
                               f"absent from {record.system_binding}; the artefact was handed to "
                               f"a person and the work is not done yet",
                               status=AWAITING_A_PERSON, system=record.system_binding)
            return DriftFinding(key=key, status=AWAITING_A_PERSON, system=record.system_binding,
                                fields={}, dp_id=None)
        if status == "MISSING":
            detail = (f"record absent from live system {record.system_binding} — signed intent "
                      f"says it exists")
        else:
            named = ", ".join(sorted(fields)) or "unknown fields"
            detail = f"live values differ from signed intent on: {named}"
        self.ledger.append(key, "DRIFT_DETECTED", actor, detail,
                           status=status, fields=fields, system=record.system_binding)

        if not open_dp:
            owner = (record.source or {}).get("signed_by") or "engagement lead"
            self.decisions.raise_dp(DecisionPoint(
                dp_id=dp_id, dp_type="DESIGN",
                question=(f"{key}: {detail}. Reassert the signed intent (re-apply), or adopt the "
                          f"observed state (requires a new signed IR record)?"),
                owner=owner,
                options=["reassert signed intent — re-apply the IR record",
                         "adopt observed state — sign a new IR record that says so"]))
        return DriftFinding(key=key, status=status, system=record.system_binding,
                            fields=fields, dp_id=dp_id)

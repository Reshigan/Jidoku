"""A twin that predicts what the live system will do, and publishes how often it is right.

v0 was schema-exact and nothing more: a payload checked against `$metadata` for missing required
fields, unknown fields and orphan picklist references. That is real and it is not a twin — it
catches what the substrate would reject for shape, and says nothing about the rules that reject
most real configuration.

v1 adds rule evaluation, and with it the only thing that makes a twin worth believing: a
**fidelity metric it earns in public**. The twin predicts before the write; the write happens or
fails on its own gates; the chain holds both; and fidelity is the rate at which the prediction
matched the outcome, counted over the whole population like everything else here (ADR-0026).

Three consequences, and they are the design:

  1. **The twin never blocks.** A prediction is a model's opinion, and a platform whose thesis is
     that assertion must be impossible does not let an opinion stop a signed, armed, snapshotted
     write. It predicts, the prediction is on the chain, and a person decides what to do with it.
  2. **An uncalibrated twin says so.** Below a minimum number of scored predictions there is no
     fidelity number, only `UNCALIBRATED`. A percentage computed from four comparisons is the
     kind of number that gets quoted.
  3. **A rule it cannot evaluate is declared, never approximated.** `parse_rules` refuses what is
     outside the subset below and names it. A twin that silently skipped the hard rules would
     report high fidelity on the easy ones.
"""
import re
from dataclasses import dataclass


class TwinValidationError(Exception): ...


class RuleNotEvaluatable(Exception):
    """A rule outside the subset this twin evaluates. Named, never approximated."""

class SchemaTwin:
    def __init__(self, metadata: dict):
        # metadata: {"EntityName": {"fields": {"name": {"type":..., "required":bool, "picklist":str|None}}}}
        self.meta = metadata

    def validate_payload(self, entity: str, payload: dict, picklists: dict[str, set] | None = None) -> list[str]:
        errs = []
        ent = self.meta.get(entity)
        if not ent:
            return [f"{entity}: entity not present in $metadata — release drift or wrong product mapping."]
        fields = ent["fields"]
        for fname, spec in fields.items():
            if spec.get("required") and payload.get(fname) in (None, ""):
                errs.append(f"{entity}.{fname}: required by $metadata, missing in intent.")
        for fname, val in payload.items():
            if fname not in fields:
                errs.append(f"{entity}.{fname}: not in $metadata — would be rejected on write.")
                continue
            pl = fields[fname].get("picklist")
            if pl and picklists is not None:
                if val not in picklists.get(pl, set()):
                    errs.append(f"{entity}.{fname}: value {val!r} not in picklist {pl} — orphan reference.")
        return errs


# --- rules -----------------------------------------------------------------------------------

#: The comparisons this twin evaluates. Deliberately small and deliberately published: a rule
#: export that uses anything else is refused by name rather than approximated, because a twin that
#: skipped the hard rules would report high fidelity on the easy ones.
OPERATORS = {
    "eq": lambda got, want: got == want,
    "ne": lambda got, want: got != want,
    "in": lambda got, want: got in want,
    "not_in": lambda got, want: got not in want,
    "required": lambda got, _want: got not in (None, ""),
    "empty": lambda got, _want: got in (None, ""),
    "lte": lambda got, want: _num(got) is not None and _num(got) <= _num(want),
    "gte": lambda got, want: _num(got) is not None and _num(got) >= _num(want),
    "matches": lambda got, want: bool(re.fullmatch(str(want), str(got or ""))),
}


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class Clause:
    field: str
    op: str
    value: object = None

    def holds(self, payload: dict) -> bool:
        return OPERATORS[self.op](payload.get(self.field), self.value)

    def says(self) -> str:
        if self.op in ("required", "empty"):
            return f"{self.field} must be {'set' if self.op == 'required' else 'empty'}"
        return f"{self.field} {self.op.replace('_', ' ')} {self.value!r}"


@dataclass(frozen=True)
class Rule:
    """`when` all hold, `then` all must hold. A rule with no `when` always applies."""
    rule_id: str
    entity: str
    then: tuple
    when: tuple = ()
    source: str = ""          # where the rule was exported from, for the citation

    def applies(self, payload: dict) -> bool:
        return all(c.holds(payload) for c in self.when)

    def breaches(self, payload: dict) -> list[str]:
        if not self.applies(payload):
            return []
        return [f"{self.rule_id}: {c.says()}" for c in self.then if not c.holds(payload)]


def parse_rules(exported: list[dict]) -> tuple[list[Rule], list[dict]]:
    """(rules we can evaluate, rules we refuse and why). Never raises on a bad rule — an export
    is somebody else's file, and the useful answer is which parts of it this twin can honour."""
    rules, refused = [], []
    for raw in exported:
        try:
            rules.append(Rule(
                rule_id=_need(raw, "rule_id"), entity=_need(raw, "entity"),
                then=tuple(_clause(c) for c in _need(raw, "then")),
                when=tuple(_clause(c) for c in raw.get("when", ())),
                source=raw.get("source", "")))
        except RuleNotEvaluatable as ex:
            refused.append({"rule_id": raw.get("rule_id", "<unnamed>"), "why": str(ex)})
    return rules, refused


def _need(raw: dict, field: str):
    if not raw.get(field):
        raise RuleNotEvaluatable(f"no {field}")
    return raw[field]


def _clause(raw: dict) -> Clause:
    op = raw.get("op")
    if op not in OPERATORS:
        raise RuleNotEvaluatable(
            f"operator {op!r} is outside the subset this twin evaluates "
            f"({', '.join(sorted(OPERATORS))})")
    if not raw.get("field"):
        raise RuleNotEvaluatable("a clause with no field")
    return Clause(raw["field"], op, raw.get("value"))


ACCEPT, REJECT = "ACCEPT", "REJECT"


class RuleTwin:
    """Schema plus rules. Predicts what the substrate will do with a payload, and nothing else."""

    def __init__(self, metadata: dict, rules: list[Rule] | None = None,
                 picklists: dict | None = None):
        self.schema = SchemaTwin(metadata)
        self.rules = list(rules or [])
        self.picklists = picklists

    def predict(self, entity: str, payload: dict) -> dict:
        """ACCEPT or REJECT, with every reason. A prediction, never a permission."""
        reasons = self.schema.validate_payload(entity, payload, self.picklists)
        for rule in self.rules:
            if rule.entity == entity:
                reasons.extend(rule.breaches(payload))
        return {"entity": entity, "verdict": REJECT if reasons else ACCEPT, "reasons": reasons,
                "rules_applied": sum(1 for r in self.rules
                                     if r.entity == entity and r.applies(payload))}


# --- fidelity: the twin earns its number in public --------------------------------------------

#: Below this many scored predictions there is no fidelity, only UNCALIBRATED. A percentage
#: computed from four comparisons is the kind of number that gets quoted.
MIN_SCORED = 10

#: Ledger actions that settle a prediction, and what they mean the substrate did.
_OUTCOMES = {"VERIFIED": ACCEPT, "APPLIED": ACCEPT, "IN_TRANSPORT": ACCEPT,
             "FAILED": REJECT, "PARTIAL": REJECT, "DRIFT_DETECTED": REJECT}


def fidelity(ledger_entries, min_scored: int = MIN_SCORED) -> dict:
    """How often the twin's prediction matched what the system actually did.

    A projection over the chain, like assurance and the controls: each TWIN_PREDICTED entry is
    paired with the next outcome on the same task, and unsettled predictions are counted as
    unsettled rather than quietly dropped — a twin that only counted the writes that happened
    would grade itself on the cases it found easy.
    """
    pending, agreed, disagreed, unsettled = {}, [], [], []
    for entry in ledger_entries:
        task, action = entry.get("task"), entry.get("action")
        if action == "TWIN_PREDICTED":
            if task in pending:
                unsettled.append(task)          # superseded before the system answered
            pending[task] = entry
        elif action in _OUTCOMES and task in pending:
            predicted = pending.pop(task).get("verdict")
            (agreed if predicted == _OUTCOMES[action] else disagreed).append(
                {"task": task, "predicted": predicted, "outcome": action})
    unsettled.extend(pending)

    scored = len(agreed) + len(disagreed)
    return {"scored": scored, "agreed": len(agreed), "disagreed": len(disagreed),
            "unsettled": len(unsettled),
            "fidelity": (len(agreed) / scored) if scored >= min_scored else None,
            "status": "CALIBRATED" if scored >= min_scored else "UNCALIBRATED",
            "min_scored": min_scored,
            "misses": disagreed,
            "method": ("Each prediction is paired with the next outcome the substrate recorded for "
                       f"the same record. Fidelity is agreements over settled predictions, and is "
                       f"withheld below {min_scored} of them — a rate computed from a handful of "
                       "comparisons is a number that gets quoted rather than a measurement.")}

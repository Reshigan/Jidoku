"""Refinement types: the rule travels with the value, and the plan is type-checked.

C1 of docs/JIDOKA_ADVANCED_CONCEPTS.md. The IR has always been *validated* — schema, references,
signatures. A refinement is the next thing: a constraint attached to the value itself, carrying its
own authority, so whole classes of defect become unrepresentable rather than detected.

```
TimeType(country=ZAF) : LeaveType
  where entitlement <= statutory_max(ZAF, signed_source)   -- the bound carries its authority
    and currency = legal_entity.currency                   -- dependent on another object's value
    and cycle_context != bottom                            -- R-107 encoded in the type
```

Three kinds, and they are the whole system:

  **bounded** — a value under a ceiling or over a floor that comes from a statute. The bound is
  useless without its source: a ceiling somebody typed in is an opinion, and invariant 1 does not
  stop applying because the number is in a type rather than a field. A bound with no signed
  authority is refused at load, exactly as unsigned intent is.

  **dependent** — this value equals a field of another object. The currency of a leave type is not
  a choice; it is the legal entity's currency, and writing it down twice is how they diverge.

  **required** — the field exists and is not empty. R-107 (cycle context) is the case that named
  it: a leave type with no cycle context is accepted by every schema and is wrong in a way nobody
  sees until the first accrual run.

**The rejection is the control narrative.** A type error here is written the way an auditor would
write the finding, because it is the same sentence: what was configured, what the authority says,
and why the difference is not a configuration choice. A type-checker whose message needed
translating before it could go in a report would be translated by hand, once, and then drift.

Pure, stdlib, over IR records. Nothing here reads a system or writes a ledger.
"""
from .ir import record_key

KINDS = ("bounded", "dependent", "required")

#: What a statutory bound needs before it is a bound at all. The same three fields a signed IR
#: source needs — a ceiling is intent about a statute, and unsigned intent does not execute.
AUTHORITY = ("statute", "signed_by", "date")


class RefinementError(Exception): ...


def _walk(node, path="intent"):
    """Every value in the intent tree that carries a refinement."""
    if isinstance(node, dict):
        if "refinement" in node:
            yield path, node
        for k, v in node.items():
            if k != "refinement":
                yield from _walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")


def validate(rec) -> None:
    """A refinement that cannot be checked is a comment. Refused at load, like an unsigned source.

    This runs before anything is planned or written, so an ill-formed constraint cannot sit in the
    design looking like protection.
    """
    get = rec.get if isinstance(rec, dict) else lambda f, d=None: getattr(rec, f, d)
    key = record_key(rec)
    for path, node in _walk(get("intent") or {}):
        r = node["refinement"]
        if not isinstance(r, dict) or r.get("kind") not in KINDS:
            raise RefinementError(
                f"{key} {path}: a refinement declares one of {list(KINDS)}. A constraint the "
                f"type-checker cannot read is a comment that looks like protection.")
        kind = r["kind"]
        if kind == "bounded":
            if "max" not in r and "min" not in r:
                raise RefinementError(f"{key} {path}: a bounded refinement declares a max, a min, "
                                      f"or both.")
            missing = [f for f in AUTHORITY if not str(r.get(f, "")).strip()]
            if missing:
                raise RefinementError(
                    f"{key} {path}: this bound cites no authority (missing {missing}). A ceiling "
                    f"somebody typed in is an opinion, and JIDOKA does not execute unsigned "
                    f"intent because the number happens to be in a type.")
        if kind == "dependent" and not (str(r.get("on", "")).strip()
                                        and str(r.get("field", "")).strip()):
            raise RefinementError(f"{key} {path}: a dependent refinement names the object it "
                                  f"depends on and the field of it that decides this value.")


def _value_of(rec, field: str):
    get = rec.get if isinstance(rec, dict) else lambda f, d=None: getattr(rec, f, d)
    node = (get("intent") or {}).get(field)
    return node.get("value") if isinstance(node, dict) else node


def check(records: list) -> list[dict]:
    """Type-check the design. Every failure is written as the finding an auditor would write.

    Values still standing as open decision points are not checked: a refinement over a value
    nobody has decided would report the absence of a decision as a type error, and the platform
    already has one gate for that which says it better.
    """
    by_short = {}
    for rec in records:
        get = rec.get if isinstance(rec, dict) else lambda f, d=None: getattr(rec, f, d)
        intent = get("intent") or {}
        by_short[f"{get('object')}:{get('external_code') or intent.get('externalCode', '?')}"] = rec
        by_short[record_key(rec)] = rec

    out = []
    for rec in records:
        get = rec.get if isinstance(rec, dict) else lambda f, d=None: getattr(rec, f, d)
        key = record_key(rec)
        for path, node in _walk(get("intent") or {}):
            r, value = node["refinement"], node.get("value")
            if value in (None, "", "TBD"):
                continue                     # an open decision, and a different gate says so
            fail = _one(key, path, r, value, by_short)
            if fail:
                out.append(fail)
    return out


def _one(key: str, path: str, r: dict, value, by_short: dict) -> dict | None:
    kind = r["kind"]
    if kind == "required":
        return None                          # a present, non-empty value satisfies it
    if kind == "bounded":
        return _bounded(key, path, r, value)
    return _dependent(key, path, r, value, by_short)


def _bounded(key: str, path: str, r: dict, value) -> dict | None:
    cite = f"{r['statute']}, signed by {r['signed_by']} on {r['date']}"
    try:
        here = float(value)
    except (TypeError, ValueError):
        return {"key": key, "path": path, "kind": "bounded", "authority": cite,
                "says": f"{key} {path} is {value!r}, which is not a number, and {r['statute']} "
                        f"sets a numeric limit on it."}
    if "max" in r and here > float(r["max"]):
        return {"key": key, "path": path, "kind": "bounded", "authority": cite,
                "says": f"{key} {path} is configured as {value} and the signed statutory maximum "
                        f"is {r['max']} ({cite}). A value above a statutory maximum is not a "
                        f"configuration choice."}
    if "min" in r and here < float(r["min"]):
        return {"key": key, "path": path, "kind": "bounded", "authority": cite,
                "says": f"{key} {path} is configured as {value} and the signed statutory minimum "
                        f"is {r['min']} ({cite}). A value below a statutory minimum is not a "
                        f"configuration choice."}
    return None


def _dependent(key: str, path: str, r: dict, value, by_short: dict) -> dict | None:
    target = by_short.get(r["on"])
    if target is None:
        return {"key": key, "path": path, "kind": "dependent", "authority": r["on"],
                "says": f"{key} {path} is declared to follow {r['on']}.{r['field']}, and no such "
                        f"object is in this design. A dependency on something that does not exist "
                        f"cannot be checked, and was not."}
    theirs = _value_of(target, r["field"])
    if theirs in (None, ""):
        return {"key": key, "path": path, "kind": "dependent", "authority": r["on"],
                "says": f"{key} {path} is declared to follow {r['on']}.{r['field']}, and that "
                        f"field is not set there. One of the two has to decide it, and it is not "
                        f"this one."}
    if theirs != value:
        return {"key": key, "path": path, "kind": "dependent", "authority": r["on"],
                "says": f"{key} {path} is configured as {value!r} and {r['on']}.{r['field']} — "
                        f"which decides it — is {theirs!r}. Writing the same fact in two places "
                        f"is how they come to disagree."}
    return None


def missing_required(records: list) -> list[dict]:
    """Fields a refinement says must exist, that do not. Separated from `check` because this is
    absence rather than disagreement, and an auditor reads the two differently."""
    out = []
    for rec in records:
        get = rec.get if isinstance(rec, dict) else lambda f, d=None: getattr(rec, f, d)
        key = record_key(rec)
        for path, node in _walk(get("intent") or {}):
            r = node["refinement"]
            if r["kind"] == "required" and node.get("value") in (None, "", "TBD"):
                rule = r.get("rule") or "this record's own type"
                out.append({"key": key, "path": path, "kind": "required", "authority": rule,
                            "says": f"{key} {path} is empty, and {rule} requires it. Every schema "
                                    f"accepts this record; it is wrong in a way nobody sees until "
                                    f"the first run that needs the field."})
    return out

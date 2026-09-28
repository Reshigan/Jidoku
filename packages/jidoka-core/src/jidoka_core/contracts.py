"""One writer, declared readers: a customisation is a cross-module contract, not a field.

The Komatsu lesson, from docs/JIDOKA_PROJECT_TEAM_AND_ALIGNMENT.md §3: `custom-string4` is
*written* by EC and *read* by Time Off eligibility, EE reporting and the ECC payroll interface.
Handled as a field it is four surprises waiting for a release. Handled as a contract it is one
declaration that every one of those four is already in.

Two rules, and they are the whole module.

  **One writer.** Two modules declaring themselves the owner of the same object is not a merge
  conflict to be resolved by whoever saves last — it is a design decision nobody has made, and it
  blocks the plan (R-202, generalised from integration to modules). A silent race here is the
  defect that surfaces in month nine as "payroll overwrites what onboarding set".

  **Declared readers.** A module that reads an object it is not registered against is a dependency
  nobody wrote down, which means the owner will change the object one day without knowing who
  breaks. The registry makes the blast radius a declaration rather than an archaeology exercise.

A contract is optional on an IR record. Most standard configuration does not need one: the object
is delivered, owned by the product, and read by whatever reads it. The contract exists for the
objects a programme *builds*, which are exactly the objects that later surprise it.

Pure, stdlib, over IR records. Nothing here reads a system or writes a ledger.
"""
from .ir import record_key

#: What an object's contract has to say. Anything else on it is ignored — a design tool exports
#: more than this needs, and refusing an export for carrying extra is a refusal nobody thanks you
#: for.
FIELDS = ("owner", "consumers", "feeds", "statutory")


class ContractError(Exception): ...


def _contract(rec) -> dict | None:
    get = rec.get if isinstance(rec, dict) else lambda f, d=None: getattr(rec, f, d)
    return get("contract") or None


def validate(rec) -> None:
    """A contract that names no owner is a field with paperwork."""
    c = _contract(rec)
    if c is None:
        return
    key = record_key(rec)
    if not isinstance(c, dict):
        raise ContractError(f"{key}: contract must be an object with {list(FIELDS)}.")
    if not str(c.get("owner", "")).strip():
        raise ContractError(
            f"{key}: a contract names the single module that writes this object. Without an owner "
            f"it is a field with paperwork, and the next module to write it does so unopposed.")
    for field in ("consumers", "feeds"):
        if field in c and not isinstance(c[field], list):
            raise ContractError(f"{key}: contract.{field} is a list of module names.")


def registry(records: list) -> dict[str, dict]:
    """Every contracted object, its owner, and who is registered to read it."""
    out: dict[str, dict] = {}
    for rec in records:
        c = _contract(rec)
        if c is None:
            continue
        validate(rec)
        key = record_key(rec)
        out[key] = {"key": key, "owner": str(c["owner"]).strip(),
                    "consumers": sorted({str(x).strip() for x in (c.get("consumers") or []) if str(x).strip()}),
                    "feeds": list(c.get("feeds") or []),
                    "statutory": c.get("statutory") or ""}
    return out


def conflicts(records: list) -> dict[str, list[str]]:
    """Objects more than one module claims to write, in the planner's own blocking shape.

    Returned as `{key: [reason]}` so a write conflict rides the same gate an open decision point
    does. That is deliberate: both are the same thing — a question only a person may answer, which
    JIDOKA refuses to answer by picking one.
    """
    claimed: dict[str, set] = {}
    for rec in records:
        c = _contract(rec)
        if c is None:
            continue
        validate(rec)
        claimed.setdefault(record_key(rec), set()).add(str(c["owner"]).strip())
    return {key: [f"{len(owners)} modules claim to own this object and write it: "
                  f"{', '.join(sorted(owners))}. One writer, declared readers — a second writer "
                  f"is a design decision nobody has made, not a merge to resolve."]
            for key, owners in claimed.items() if len(owners) > 1}


def consumers_of(records: list, key: str) -> list[str]:
    """Who is registered to read this object. The blast radius, declared rather than discovered."""
    return registry(records).get(key, {}).get("consumers", [])


def undeclared_readers(records: list) -> list[dict]:
    """Records that depend on a contracted object without being registered to read it.

    Not a block: a dependency is a fact about the design and this is the platform noticing that
    the paperwork has fallen behind it. It is a finding, and the owner is the one who should hear
    about it — they are the one who will change the object one day without knowing who breaks.
    """
    reg = registry(records)
    # Short references — "TimeAccountType:ANN_ACC_ZAF" — resolve the same way the planner resolves
    # them. Two resolvers would disagree the first time one of them learned a new form.
    short = {}
    for rec in records:
        get = rec.get if isinstance(rec, dict) else lambda f, d=None: getattr(rec, f, d)
        intent = get("intent") or {}
        short[f"{get('object')}:{get('external_code') or intent.get('externalCode', '?')}"] = \
            record_key(rec)

    out = []
    for rec in records:
        get = rec.get if isinstance(rec, dict) else lambda f, d=None: getattr(rec, f, d)
        mine = _contract(rec) or {}
        # A record with no contract of its own still reads: it is named by its product, because
        # that is the only module name the design gave it.
        me = str(mine.get("owner") or get("product") or "").strip()
        for dep in get("depends_on") or []:
            target = reg.get(short.get(dep, dep))
            if target and me != target["owner"] and me not in target["consumers"]:
                out.append({"reader": record_key(rec), "reads": target["key"],
                            "module": me, "owner": target["owner"],
                            "says": f"{me} reads {target['key']} and is not registered against it. "
                                    f"{target['owner']} owns it and will not know who breaks when "
                                    f"it changes."})
    return out

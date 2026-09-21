"""Config Intermediate Representation: the executable form of signed design intent.
Every value traces to a signed source. Unsigned statutory values are structurally unloadable."""
from dataclasses import dataclass, field
from typing import Any

REQUIRED = ("object", "product", "system_binding", "intent", "tier", "source")
TIERS = ("A", "B", "C")

@dataclass
class IRRecord:
    object: str
    product: str
    system_binding: str
    intent: dict
    tier: str
    source: dict
    country: str | None = None
    depends_on: list = field(default_factory=list)
    external_code: str | None = None
    #: The cross-module contract, where the object has one: which single module writes it, which
    #: modules are registered to read it, what it feeds, and its statutory linkage. Optional —
    #: delivered standard configuration does not need one. It exists for the objects a programme
    #: builds, which are exactly the objects that later surprise it (ADR-0034).
    contract: dict | None = None

    @property
    def key(self) -> str:
        return record_key(self)

class IRValidationError(Exception): ...


def record_key(record) -> str:
    """The name one IR record answers to, from a dataclass or from the dict it was loaded as.

    Both are real — the API holds dataclasses, the repository and the projections hold rows — and
    they have to produce the same string, because that string is the ledger's task name. It was
    written twice, and the copy that took a dict quietly returned nothing, so an assurance count
    read off the chain reported every record as unexamined.
    """
    get = record.get if isinstance(record, dict) else lambda f, d=None: getattr(record, f, d)
    intent = get("intent") or {}
    code = get("external_code") or intent.get("externalCode") or "?"
    return f"{get('product')}:{get('object')}:{code}"

def _find_decision_points(node: Any, path="intent") -> list[str]:
    hits = []
    if isinstance(node, dict):
        if "decision_point" in node and node.get("value") in (None, "", "TBD"):
            hits.append(f"{path} -> {node['decision_point']}")
        for k, v in node.items():
            hits.extend(_find_decision_points(v, f"{path}.{k}"))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            hits.extend(_find_decision_points(v, f"{path}[{i}]"))
    return hits

def validate_record(raw: dict) -> tuple[IRRecord, list[str]]:
    """Returns (record, open_decision_points). Raises on structural invalidity."""
    missing = [k for k in REQUIRED if k not in raw]
    if missing:
        raise IRValidationError(f"IR record missing {missing}: {raw.get('object','<unknown>')}")
    if raw["tier"] not in TIERS:
        raise IRValidationError(f"Invalid tier {raw['tier']!r} on {raw['object']}")
    src = raw["source"]
    for k in ("workbook", "signed_by", "date"):
        if not src.get(k):
            raise IRValidationError(f"Unsigned source on {raw['object']}: missing source.{k} "
                                    f"— JIDOKA does not execute unsigned intent.")
    rec = IRRecord(**{k: raw[k] for k in raw if k in IRRecord.__dataclass_fields__})
    # A contract that names no owner is a field with paperwork, and it is structurally invalid for
    # the same reason an unsigned source is: the thing it claims to establish, it does not.
    from .contracts import ContractError, validate as validate_contract

    try:
        validate_contract(rec)
    except ContractError as ex:
        raise IRValidationError(str(ex)) from None
    return rec, _find_decision_points(raw["intent"])

def load_ir(records: list[dict]) -> tuple[list[IRRecord], dict[str, list[str]]]:
    """Validate a full IR set. Open DPs are returned per record — the planner will hard-block them."""
    out, dps = [], {}
    for raw in records:
        rec, open_dps = validate_record(raw)
        out.append(rec)
        if open_dps:
            dps[rec.key] = open_dps
    return out, dps

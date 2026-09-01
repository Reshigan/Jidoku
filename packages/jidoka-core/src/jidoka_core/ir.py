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

    @property
    def key(self) -> str:
        return f"{self.product}:{self.object}:{self.external_code or self.intent.get('externalCode','?')}"

class IRValidationError(Exception): ...

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

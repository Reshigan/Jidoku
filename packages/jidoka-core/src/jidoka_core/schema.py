"""Published JSON Schema for the Config IR — versioned so a workbook compiled today
stays readable by a kernel shipped tomorrow. Stdlib only: we validate the subset we
publish rather than take a dependency on the governance path (root CLAUDE.md #1)."""
import json
from typing import Any

IR_SCHEMA_VERSION = "ir/v1"

_NON_EMPTY = {"type": "string", "minLength": 1}

IR_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": f"https://jidoka.gonxt.dev/schemas/{IR_SCHEMA_VERSION}",
    "title": "JIDOKA Config IR record",
    "type": "object",
    "required": ["object", "product", "system_binding", "intent", "tier", "source"],
    "properties": {
        "object": _NON_EMPTY,
        "product": _NON_EMPTY,
        "system_binding": _NON_EMPTY,
        "intent": {"type": "object"},
        "tier": {"type": "string", "enum": ["A", "B", "C"]},
        "source": {
            "type": "object",
            "required": ["workbook", "signed_by", "date"],
            "properties": {"workbook": _NON_EMPTY, "signed_by": _NON_EMPTY, "date": _NON_EMPTY},
        },
        "country": {"type": "string"},
        "depends_on": {"type": "array", "items": _NON_EMPTY},
        "external_code": {"type": "string"},
    },
}

_TYPES = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool}

def _type_name(value: Any) -> str:
    for name, py in _TYPES.items():
        if name != "number" and isinstance(value, py) and not (name != "boolean" and isinstance(value, bool)):
            return name
    return type(value).__name__

def _check(node: Any, schema: dict, path: str, errs: list[str]) -> None:
    want = schema.get("type")
    if want:
        py = _TYPES[want]
        ok = isinstance(node, py) and not (want != "boolean" and isinstance(node, bool))
        if not ok:
            errs.append(f"{path} must be a {want}, got {_type_name(node)} — correct the value in the workbook.")
            return
    if "enum" in schema and node not in schema["enum"]:
        errs.append(f"{path} is {node!r}; JIDOKA only executes {'/'.join(map(str, schema['enum']))} — set a valid value.")
    if "minLength" in schema and isinstance(node, str) and len(node) < schema["minLength"]:
        errs.append(f"{path} is empty — JIDOKA does not execute unsigned or nameless intent; supply a value.")
    if isinstance(node, dict):
        for req in schema.get("required", []):
            if req not in node:
                errs.append(f"{path}.{req} is missing — the IR record is not loadable without it; add it to the workbook.")
        for name, sub in schema.get("properties", {}).items():
            if name in node:
                _check(node[name], sub, f"{path}.{name}", errs)
    elif isinstance(node, list) and "items" in schema:
        for i, item in enumerate(node):
            _check(item, schema["items"], f"{path}[{i}]", errs)

def validate_against_schema(raw: dict) -> list[str]:
    """Errors against IR_SCHEMA, empty list means loadable. Human-readable on purpose:
    these strings go back to the consultant who has to fix the workbook."""
    errs: list[str] = []
    _check(raw, IR_SCHEMA, "record", errs)
    return errs

def schema_json(indent: int = 2) -> str:
    return json.dumps(IR_SCHEMA, indent=indent, sort_keys=True)

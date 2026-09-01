"""Instance file importers for the Tier-B artefact handoff (CSV/JSON -> IR-shaped records).
Provenance is supplied by the caller and copied verbatim: an import cannot sign itself. Files with
no signature stay unsigned so jidoka_core.ir.validate_record refuses them (invariant 1) — that
refusal is the feature, not a bug to work around."""
import csv
import io
import json

PROVENANCE_KEYS = ("workbook", "cell_range", "signed_by", "date")


def _source(provenance: dict | None, row_no: int) -> dict:
    """Per-row source block. Missing signature stays missing — never fabricated."""
    p = provenance or {}
    src = {k: p.get(k) for k in PROVENANCE_KEYS}
    if src.get("cell_range"):
        src["cell_range"] = f"{src['cell_range']}#row{row_no}"
    for k, v in p.items():  # caller may carry extra provenance (file hash, sheet, ...)
        src.setdefault(k, v)
    return src


def _record(payload: dict, entity: str, system_binding: str, provenance: dict | None,
            row_no: int, tier: str) -> dict:
    return {"object": entity, "product": "SuccessFactors", "system_binding": system_binding,
            "intent": payload, "tier": tier, "source": _source(provenance, row_no),
            "external_code": payload.get("externalCode")}


def import_csv(text: str, entity: str, system_binding: str, provenance: dict | None = None,
               tier: str = "B") -> list[dict]:
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        return []
    return [_record({k: v for k, v in r.items() if k is not None}, entity, system_binding,
                    provenance, i, tier)
            for i, r in enumerate(rows, 2)]  # row 1 is the header, as a human counts it


def import_json(text: str, entity: str, system_binding: str, provenance: dict | None = None,
                tier: str = "B") -> list[dict]:
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("d", {}).get("results", data.get("rows", [data]))
    return [_record(r, entity, system_binding, provenance, i, tier)
            for i, r in enumerate(data, 1)]


def import_file(path: str, entity: str, system_binding: str, provenance: dict | None = None,
                tier: str = "B") -> list[dict]:
    with open(path, encoding="utf-8-sig") as fh:
        text = fh.read()
    fn = import_json if path.lower().endswith(".json") else import_csv
    return fn(text, entity, system_binding, provenance, tier)


def unsigned(records: list[dict]) -> list[dict]:
    """Records whose provenance is incomplete — the caller must resolve these before load."""
    return [r for r in records
            if not all(r["source"].get(k) for k in ("workbook", "signed_by", "date"))]

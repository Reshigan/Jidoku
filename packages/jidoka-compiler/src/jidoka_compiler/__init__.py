"""Workbook -> IR compiler. v0: structured CSV. E4 adds XLSX + LLM-assisted prose intake (sign-off-gated).
Rule: the compiler NEVER guesses — missing/ambiguous cells become decision_point entries, not values."""
import csv, io

def compile_csv(csv_text: str, product: str, system_binding: str, workbook: str,
                signed_by: str, date: str) -> list[dict]:
    """Columns: object,external_code,tier,depends_on(|-sep),field:*,dp:*  -> IR records with provenance."""
    out = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for i, row in enumerate(reader, start=2):  # row 1 = header
        intent = {"externalCode": row["external_code"]}
        for col, val in row.items():
            if col.startswith("field:") and val != "":
                intent[col[6:]] = val
            if col.startswith("dp:") and val != "":
                intent[col[3:]] = {"value": None, "decision_point": val}
        out.append({"object": row["object"], "product": product, "system_binding": system_binding,
                    "tier": row["tier"], "external_code": row["external_code"],
                    "depends_on": [d for d in row.get("depends_on", "").split("|") if d],
                    "intent": intent,
                    "source": {"workbook": workbook, "cell_range": f"row {i}",
                               "signed_by": signed_by, "date": date}})
    return out

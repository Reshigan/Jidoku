"""Archaeology mode: reverse a live tenant into draft IR — the brownfield door.
Every recovered record is marked UNVERIFIED with source 'tenant-extract'; a human signs it into truth.
The platform never promotes archaeology to executable IR by itself (signed-claim primitive holds)."""
def reverse_ir(extracted: list[dict], product: str, system_id: str) -> list[dict]:
    drafts = []
    for row in extracted:
        entity = row.get("__entity", "Unknown")
        code = row.get("externalCode", "?")
        intent = {k: v for k, v in row.items() if not k.startswith("__")}
        drafts.append({
            "object": entity, "product": product, "system_binding": system_id,
            "external_code": code, "tier": "A", "intent": intent, "depends_on": [],
            "source": {"workbook": f"tenant-extract:{system_id}", "cell_range": f"{entity}/{code}",
                       "signed_by": "", "date": ""},          # unsigned on purpose: unloadable until a human signs
            "provenance_status": "UNVERIFIED",
            "rationale": None})                                # the question brownfield clients cannot answer — yet
    return drafts

def unexplained(drafts: list[dict]) -> list[str]:
    """Objects with no recorded rationale — the archaeology backlog a client actually pays to close."""
    return [d["external_code"] for d in drafts if d.get("rationale") is None]

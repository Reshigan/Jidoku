"""Blast radius at PERSON level: which people does this change touch, and how much.
Object-level impact analysis exists in the market; person-level does not."""
def blast_radius(change: dict, population: list[dict]) -> dict:
    """change: {'field': ..., 'selector': {attr: value}, 'delta': description}"""
    sel = change.get("selector", {})
    hit = [p for p in population if all(p.get(k) == v for k, v in sel.items())]
    return {"population": len(population), "affected": len(hit),
            "affected_ids": [p["id"] for p in hit][:100],
            "unaffected": len(population) - len(hit),
            "statement": f"This changes nothing for {len(population)-len(hit):,} people "
                         f"and affects {len(hit):,}: {change.get('delta','')}"}

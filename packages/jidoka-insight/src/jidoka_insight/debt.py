"""Technical debt index: config debt as a number with a trend, not an opinion.
Weights are published; the score is reproducible from the extract alone."""
WEIGHTS = {"custom_object": 5, "unreferenced_object": 3, "rule_depth_over_3": 4,
           "obsolete_picklist_in_use": 8, "undocumented_customisation": 6, "unauthorised_drift": 10}

def debt_index(counts: dict) -> dict:
    items = {k: counts.get(k, 0) * w for k, w in WEIGHTS.items()}
    score = sum(items.values())
    return {"score": score, "items": items,
            "grade": "A" if score < 40 else "B" if score < 120 else "C" if score < 300 else "D",
            "top_driver": max(items, key=items.get) if score else None}

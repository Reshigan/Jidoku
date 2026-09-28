"""Technical debt index: config debt as a number with a trend, not an opinion.
Weights are published; the score is reproducible from the extract alone."""
from .archaeology import unexplained
WEIGHTS = {"custom_object": 5, "unreferenced_object": 3, "rule_depth_over_3": 4,
           "obsolete_picklist_in_use": 8, "undocumented_customisation": 6, "unauthorised_drift": 10}

def debt_index(counts: dict) -> dict:
    items = {k: counts.get(k, 0) * w for k, w in WEIGHTS.items()}
    score = sum(items.values())
    return {"score": score, "items": items,
            "grade": "A" if score < 40 else "B" if score < 120 else "C" if score < 300 else "D",
            "top_driver": max(items, key=items.get) if score else None}


#: What each counter is derived from, and what it is silent about. Printed beside the score
#: because a debt index nobody can trace is an opinion with a number attached.
MEASURED = {
    "undocumented_customisation": "objects recovered from the live system with no recorded "
                                  "rationale (archaeology backlog)",
    "unauthorised_drift": "open drift decision points — live values signed intent does not explain",
}


def counts_from(drafts: list[dict], decision_points, extra: dict | None = None) -> dict:
    """Derive the counters this platform can actually observe, and no others.

    Every counter absent from MEASURED stays at zero unless a caller supplies it in `extra`. That
    is deliberate: a weight with no measurement behind it would make the score move for reasons
    nobody can trace, which is the failure mode `WEIGHTS` being published was meant to avoid.
    Scoring what is measured and saying so beats scoring everything and meaning nothing.
    """
    counts = dict(extra or {})
    counts["undocumented_customisation"] = len(unexplained(drafts))
    counts["unauthorised_drift"] = sum(
        1 for d in decision_points
        if str(getattr(d, "dp_id", "")).startswith("DP-DRIFT-")
        and getattr(d, "resolution", None) is None)
    return counts


def measure(drafts: list[dict], decision_points, extra: dict | None = None) -> dict:
    """The index plus its provenance: what was counted, and what was not looked at."""
    counts = counts_from(drafts, decision_points, extra)
    index = debt_index(counts)
    # The weights travel with the score. A consumer that derives them from the contributions
    # divides by a count that is often zero, and prints a published weight as 0 — which is the
    # one thing a "published weights" claim may not do.
    return {**index, "counts": counts, "weights": dict(WEIGHTS), "measured": dict(MEASURED),
            "unmeasured": sorted(set(WEIGHTS) - set(counts))}

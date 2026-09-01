"""Gap questionnaire for prose design docs. Prose is NEVER mined for values — it only tells us
which questions are already answered unambiguously; everything else becomes a typed question
for a human. Deterministic + stdlib-only; LLM-assisted proposal is E5's job."""
import re
from jidoka_core.decisions import DP_TYPES

DEFAULT_DP_TYPE = "DESIGN"


def _mentions(text: str, term: str) -> bool:
    """Unambiguous = the term appears exactly once. Twice+ is contested prose, so still a question."""
    return len(re.findall(rf"\b{re.escape(term)}\b", text, re.I)) == 1


def build_questionnaire(prose: str, spec: list[dict], owner: str = "client") -> list[dict]:
    """spec entries: {object, fields:[...], optional dp_type, owner, terms:{field: term}}.
    Returns one question per field the prose does not unambiguously state."""
    out = []
    for entry in spec:
        obj = entry["object"]
        dp_type = entry.get("dp_type", DEFAULT_DP_TYPE)
        if dp_type not in DP_TYPES:
            raise ValueError(f"Unknown dp_type {dp_type!r} for {obj}")
        who = entry.get("owner", owner)
        terms = entry.get("terms", {})
        for f in entry["fields"]:
            if _mentions(prose, terms.get(f, f)):
                continue
            out.append({"dp_id": f"DP-{obj}-{f}".upper().replace(" ", "_"),
                        "dp_type": dp_type,
                        "question": f"What is the value of {f!r} for {obj}? "
                                    f"The design document does not state it unambiguously.",
                        "owner": who,
                        "object": obj,
                        "field": f})
    return out

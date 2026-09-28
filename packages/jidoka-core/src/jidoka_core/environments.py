"""Two environments, compared, with neither one treated as the truth.

The registry has modelled DEV, TEST and PROD since the first commit, `build_reader` gives a
binding that can read a system and structurally cannot write to it, and every adapter can diff two
row sets. Nothing put them together, so the question a consultant answers by hand every week —
*is QA the same as PROD, and what is in DEV that never made it across?* — was one the platform
held every piece of and never asked.

**Neither side is "before".** The adapters' `diff` is deliberately directional: it answers "what
did my write do", where one side is the state that preceded the other. Reusing it here would make
one environment the baseline and the other a set of additions and deletions from it, which reads
as a verdict nobody gave. A comparison between peers says *only in this one*, *only in that one*,
and *both, differing* — and leaves which is right to the person who knows why they differ.

**Signed intent is the third party.** Where a record's intent is known, a difference is not just a
difference: one side may match what was signed and the other may not, and that is a far more
useful sentence than "these two rows are not equal". Where intent is not known — an object nobody
designed, sitting in both systems — the comparison still reports it, because an undesigned object
present in PROD and absent in DEV is exactly the thing somebody wants to find before a cutover.

Pure, stdlib, over rows somebody else extracted. Nothing here reads a system.
"""

#: Fields that describe the read rather than the configuration. Comparing them would report every
#: object as differing, on metadata the tenant generates.
NOISE = ("__metadata", "lastModifiedDateTime", "lastModifiedBy", "createdDateTime", "createdBy",
         "etag", "ETag")


def _rows(rows: list[dict], key: str) -> dict:
    return {r[key]: r for r in rows or [] if key in r}


def _fields(row: dict) -> dict:
    return {k: v for k, v in (row or {}).items()
            if k not in NOISE and not isinstance(v, (dict, list))}


def _delta(a: dict, b: dict) -> dict:
    fa, fb = _fields(a), _fields(b)
    return {f: {"left": fa.get(f), "right": fb.get(f)}
            for f in sorted(set(fa) | set(fb)) if fa.get(f) != fb.get(f)}


def compare(left: list[dict], right: list[dict], key: str,
            left_name: str = "left", right_name: str = "right",
            intent: dict | None = None) -> dict:
    """One entity, in two environments. Directionless by construction."""
    a, b = _rows(left, key), _rows(right, key)
    only_left = sorted(set(a) - set(b))
    only_right = sorted(set(b) - set(a))
    differs, same = [], []
    for k in sorted(set(a) & set(b)):
        delta = _delta(a[k], b[k])
        (differs if delta else same).append(
            {"key": k, "fields": delta, **_against_intent(k, a[k], b[k], intent,
                                                          left_name, right_name)}
            if delta else {"key": k})
    return {"left": left_name, "right": right_name, "key_field": key,
            "only_in_left": [{"key": k} for k in only_left],
            "only_in_right": [{"key": k} for k in only_right],
            "differs": differs, "same": [r["key"] for r in same],
            "aligned": not (only_left or only_right or differs),
            "says": _says(left_name, right_name, only_left, only_right, differs, same)}


def _against_intent(key: str, a: dict, b: dict, intent: dict | None,
                    left_name: str, right_name: str) -> dict:
    """Which side, if either, matches what was signed. The far more useful sentence."""
    signed = (intent or {}).get(key)
    if not signed:
        return {"signed": False,
                "says": f"{key} differs between {left_name} and {right_name}, and nothing in "
                        f"signed intent describes it — so neither side is wrong by the design, "
                        f"and neither is right."}
    matches = [name for name, row in ((left_name, a), (right_name, b))
               if all(row.get(f) == v for f, v in signed.items()
                      if not isinstance(v, (dict, list)))]
    if len(matches) == 1:
        other = right_name if matches[0] == left_name else left_name
        return {"signed": True, "matches": matches,
                "says": f"{key} matches signed intent in {matches[0]} and does not in {other}."}
    if not matches:
        return {"signed": True, "matches": [],
                "says": f"{key} differs between {left_name} and {right_name} and matches signed "
                        f"intent in neither."}
    return {"signed": True, "matches": matches,
            "says": f"{key} differs on a field signed intent does not describe."}


def _says(left: str, right: str, only_left: list, only_right: list, differs: list,
          same: list) -> str:
    if not (only_left or only_right or differs):
        return (f"{left} and {right} hold the same {len(same)} object(s), field for field."
                if same else f"Neither {left} nor {right} holds any of these objects.")
    parts = []
    if only_left:
        parts.append(f"{len(only_left)} only in {left}")
    if only_right:
        parts.append(f"{len(only_right)} only in {right}")
    if differs:
        parts.append(f"{len(differs)} in both and differing")
    return ", ".join(parts) + f"; {len(same)} the same."


def roll_up(comparisons: list[dict]) -> dict:
    """Every entity compared, and the one sentence somebody takes to a cutover meeting."""
    apart = sum(len(c["only_in_left"]) + len(c["only_in_right"]) + len(c["differs"])
                for c in comparisons)
    same = sum(len(c["same"]) for c in comparisons)
    if not comparisons:
        return {"entities": [], "apart": 0, "same": 0, "aligned": True,
                "says": "Nothing was compared: no entity is readable in both systems."}
    left = comparisons[0]["left"]
    right = comparisons[0]["right"]
    return {"entities": comparisons, "apart": apart, "same": same, "aligned": apart == 0,
            "says": (f"{left} and {right} agree on all {same} object(s) read."
                     if apart == 0 else
                     f"{apart} object(s) are not the same in {left} and {right}; {same} are. "
                     f"This is a reading of both systems, not a verdict on either — which one is "
                     f"right is a question about why they differ.")}

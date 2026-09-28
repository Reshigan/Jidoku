"""A new version of the design supersedes the old one; it does not quietly replace it.

Loading intent used to assign the whole set: `e.ir = loaded`. On a real programme the workbook
goes v1 → v2 → v3 every few weeks, so that was the normal path, and it lost two things every time.

  **What changed.** The chain recorded "47 records" and nothing about which of them were new,
  which were gone, and which had been edited under the same key. A design history that cannot be
  read back is not a history.

  **What is still live.** Verification and assurance both iterate the *current* IR set, so a
  record that was executed against a customer's system and then dropped from v2 vanished from
  every projection — while the change sat in their tenant, unclaimed, with its ledger entries
  intact and nothing reading them. For a platform whose promise is signed intent in and verified
  configuration out, a live change it can no longer see is the worst thing it can produce.

An orphan is drift's sibling and gets drift's treatment (ADR-0019): a decision point with exactly
two exits — sign it back into the design, or take it out of the system — and planning halts until
a person picks one. JIDOKA does not decide which; it refuses to plan around an unclaimed change.

Pure, stdlib, a projection over two record sets and the chain.
"""
from .ir import record_key

#: Ledger actions that mean this record reached a customer's system. Anything here and no longer
#: in signed intent is a change nobody is claiming.
TOUCHED = ("EXECUTED", "VERIFIED", "DRIFT_DETECTED", "PARTIAL", "ATTESTED", "HANDED_OFF")

#: …unless it was put back. A rollback is the platform having already cleaned up after itself.
UNDONE = ("ROLLED_BACK",)


def _by_key(records: list) -> dict:
    return {record_key(r): r for r in records}


def _intent(rec) -> dict:
    get = rec.get if isinstance(rec, dict) else lambda f, d=None: getattr(rec, f, d)
    return get("intent") or {}


def diff(before: list, after: list) -> dict:
    """What this version of the design did to the last one, by record key."""
    b, a = _by_key(before), _by_key(after)
    changed = sorted(k for k in set(a) & set(b) if _intent(a[k]) != _intent(b[k]))
    return {"added": sorted(set(a) - set(b)),
            "removed": sorted(set(b) - set(a)),
            "changed": changed,
            "unchanged": sorted(k for k in set(a) & set(b) if k not in changed)}


def orphans(removed: list[str], entries: list[dict]) -> list[dict]:
    """Records the new design dropped that a customer's system is still holding.

    Read off the chain, not off the old IR set: what matters is not that the record existed, it is
    that something was done to a live system on its account and nobody has put it back.
    """
    touched: dict[str, str] = {}
    for e in entries:
        task, action = e.get("task"), e.get("action")
        if task in removed and action in TOUCHED:
            touched[task] = action
        elif task in removed and action in UNDONE:
            touched.pop(task, None)
    return [{"key": k, "last": v,
             "says": f"{k} was {v.lower().replace('_', ' ')} against a live system and the new "
                     f"design does not contain it. The change is still there and nothing claims "
                     f"it."}
            for k, v in sorted(touched.items())]


def question(orphan: dict) -> str:
    """The decision point's question. Two exits and no third: the platform will not choose."""
    return (f"{orphan['key']} is live and signed intent no longer contains it. Sign it back into "
            f"the design, or take it out of the system — JIDOKA will not plan around a change "
            f"nobody claims.")

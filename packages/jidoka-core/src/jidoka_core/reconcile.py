"""The system's own change log against ours: what happened here that never came through us.

`CLAIMS.md` has named this as the platform's most expensive blind spot since ADR-0031: *"Work that
never reached a gate. A consultant who saw a refusal coming and did the change by hand in the SAP
GUI leaves nothing on this chain."* Every projection here — assurance, controls, drift, the
accountability record — reads the ledger, so a change made outside the platform is not
under-reported. It is invisible, and the numbers are confidently wrong rather than uncertain.

The fix is not to watch harder. It is to stop treating our chain as the only record. SuccessFactors
ships a Change Audit report, S/4 has its own change documents, and most products keep something:
they know what changed and who changed it, because the system did it. Reconciling their log against
ours turns the product's own audit trail — free, and a competitor to half of this platform's pitch —
into the input that closes the gap.

Four outcomes, and the vocabulary is the point:

  **matched** — on both records. The platform did it and the system agrees.
  **out_of_band** — in the system's log and not on our chain. Somebody changed a customer's
  configuration outside every gate. This is the finding the module exists for.
  **unconfirmed** — on our chain and not in the system's log. Usually a window or a scope mismatch
  rather than a fabrication, so it is reported as a question, not an accusation.
  **out_of_scope** — in the system's log and about an object no signed intent describes. Real, and
  not this engagement's business; counting it as out-of-band would make every programme look
  breached by the rest of the tenant.

Pure, stdlib, over two lists somebody else fetched. Nothing here reads a system.
"""
from .clock import TS
from datetime import datetime, timedelta

#: Ledger actions that mean this platform changed a live system. A snapshot reads; a dry run
#: rehearses; neither should expect an entry in the product's change log.
OURS = ("EXECUTED", "PARTIAL", "ROLLED_BACK")

#: How far apart two records of the same change may sit and still be the same change. Clocks drift
#: between a tenant and a kernel, and a product writes its log when the change commits rather than
#: when the request arrived. Published, because it is a judgement and not a measurement.
WINDOW_MINUTES = 10


class ReconcileError(Exception): ...


def _at(ts: str):
    for fmt in (TS, "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime((ts or "").replace("+00:00", "Z"), fmt)
        except (ValueError, TypeError):
            continue
    return None


def _near(a: str, b: str, minutes: int) -> bool:
    ta, tb = _at(a), _at(b)
    if ta is None or tb is None:
        return True          # a log with no usable time is matched on object alone, and says so
    return abs(ta - tb) <= timedelta(minutes=minutes)


def reconcile(ours: list[dict], theirs: list[dict], designed: set,
              window_minutes: int = WINDOW_MINUTES) -> dict:
    """Our ledger entries against the product's own change log.

    `theirs` is normalised by the adapter into `{object, changed_by, ts, detail}` — every product
    spells its audit log differently and that translation belongs with the product, not here.
    `designed` is the set of objects signed intent describes, which is what separates a change
    that is out of band from one that is simply somebody else's.
    """
    mine = [e for e in ours if e.get("action") in OURS]
    unmatched = list(mine)
    matched, out_of_band, out_of_scope = [], [], []

    for row in theirs:
        obj, when = row.get("object"), row.get("ts", "")
        hit = next((e for e in unmatched
                    if e.get("task") == obj and _near(e.get("ts", ""), when, window_minutes)), None)
        if hit is not None:
            unmatched.remove(hit)
            matched.append({"object": obj, "ts": when, "by": row.get("changed_by", ""),
                            "our_action": hit.get("action"), "our_actor": hit.get("actor")})
        elif obj in designed:
            out_of_band.append({
                "object": obj, "ts": when, "by": row.get("changed_by", ""),
                "detail": row.get("detail", ""),
                "says": f"{obj} was changed in the system at {when or 'an unrecorded time'} by "
                        f"{row.get('changed_by') or 'somebody the log does not name'}, and nothing "
                        f"on this chain did it. Signed intent describes this object, so the change "
                        f"is inside this engagement's scope and outside every one of its gates."})
        else:
            out_of_scope.append({"object": obj, "ts": when, "by": row.get("changed_by", "")})

    unconfirmed = [{"object": e.get("task"), "ts": e.get("ts"), "our_action": e.get("action"),
                    "our_actor": e.get("actor"),
                    "says": f"{e.get('task')} is recorded here as {e.get('action')} and the "
                            f"system's log does not show it. That is usually a window or a scope "
                            f"mismatch rather than a fabrication — which is why it is a question "
                            f"and not an accusation."}
                   for e in unmatched]

    return {"matched": matched, "out_of_band": out_of_band, "unconfirmed": unconfirmed,
            "out_of_scope": out_of_scope,
            "window_minutes": window_minutes,
            "says": _says(matched, out_of_band, unconfirmed, out_of_scope),
            "method": ("The product's own change log against this ledger, paired on object and a "
                       f"{window_minutes}-minute window because clocks drift and a system logs a "
                       "change when it commits. A change the log shows on an object signed intent "
                       "describes, that nothing here did, is out of band. A change on an object "
                       "nobody designed is somebody else's, not a breach of this engagement.")}


def _says(matched, out_of_band, unconfirmed, out_of_scope) -> str:
    if out_of_band:
        who = sorted({r["by"] for r in out_of_band if r["by"]})
        return (f"{len(out_of_band)} change(s) to configuration this engagement designed were made "
                f"outside the platform"
                + (f", by {', '.join(who)}" if who else "")
                + ". Nothing on this chain accounts for them, and every number this platform "
                  "publishes was computed as if they had not happened.")
    if not matched and not unconfirmed:
        return ("Nothing to reconcile: the system's log shows no change to anything this "
                "engagement designed, and this chain claims none.")
    base = f"{len(matched)} change(s) appear on both records"
    if unconfirmed:
        base += f"; {len(unconfirmed)} appear here and not in the system's log"
    if out_of_scope:
        base += f"; {len(out_of_scope)} in the log are about objects nobody designed"
    return base + ". No change to designed configuration was made outside the platform."

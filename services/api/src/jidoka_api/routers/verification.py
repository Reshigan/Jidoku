"""Verification: read the live system and compare it to signed intent, record by record.

This is the platform's test run. The expected state is not written by a tester — it IS the signed
IR, so the suite cannot test the wrong thing and cannot go stale. A mismatch is not a red row in
a report: the DriftWatch appends it to the ledger and raises a decision point that blocks
planning until a named human chooses between reasserting the intent and signing new intent
(ADR-0013). Gated on ledger_append: builders and reviewers can both run it, and running it always
writes the ledger.
"""
from fastapi import APIRouter, Depends
from jidoka_core.assurance import assure
from jidoka_core.drift import (ATTESTED, AWAITING_A_PERSON, HANDED_OFF, NOT_APPLIED,
                                UNTOUCHED, WRITTEN, DriftWatch)

from ..auth import Identity, require
from .engagements import get_or_404
from .execution import _adapter_for

router = APIRouter(prefix="/engagements/{eid}/verification", tags=["verification"])


def run_verification(e, actor: str) -> dict:
    """The verification pass itself, callable without a request.

    The crew run ends with this, and it must be the same pass the Verify screen runs — a platform
    with two verifications has two truths, and the one nobody is looking at is the one that
    quietly goes stale.
    """
    watch = DriftWatch(e.ledger, e.decisions)
    # How far each record has got, read off the chain. Only a record this platform wrote can
    # drift; one handed to a person is outstanding work with a date on it; one nobody has touched
    # is unbuilt (ADR-0019, ADR-0021).
    progress, handed_at = {}, {}
    for entry in e.ledger.entries:
        if entry.get("action") == "EXECUTED":
            progress[entry.get("task")] = WRITTEN
        elif entry.get("action") == "HANDED_OFF":
            progress.setdefault(entry.get("task"), HANDED_OFF)
            handed_at.setdefault(entry.get("task"), entry.get("ts"))
    # An attestation is a person's word about one version of a record's intent, so the latest one
    # per record is what counts and the comparison is left to core (ADR-0022).
    attestations = {}
    for entry in e.ledger.entries:
        if entry.get("action") == "ATTESTED" and entry.get("intent_hash"):
            attestations[entry.get("task")] = entry
    verified, findings, skipped, unbuilt, awaiting = [], [], [], [], []
    unconfirmable, attested = [], []
    for r in e.ir:
        connector = e.connectors.get(r.system_binding)
        if connector is None:
            skipped.append({"key": r.key, "reason": f"no connector bound to {r.system_binding} — "
                                                    f"cannot read what cannot be reached"})
            continue
        adapter = _adapter_for(r.product, connector)
        if not adapter.verifiable(r.object):
            # Read nothing. The product publishes no path, so an extract here would fail and be
            # filed as "could not be read", which reads like a transient fault rather than a
            # permanent limit of the substrate.
            finding = watch.unconfirmable(r, actor, adapter.unverifiable()[r.object],
                                          attestations.get(r.key))
            row = {"key": r.key, "system": r.system_binding, "tier": r.tier,
                   "reason": adapter.unverifiable()[r.object]}
            if finding.status == ATTESTED:
                entry = attestations[r.key]
                attested.append({**row, "attested_by": entry.get("actor"), "at": entry.get("ts"),
                                 "note": entry.get("detail", "")})
            else:
                unconfirmable.append(row)
            continue
        try:
            system = e.registry.get(r.system_binding)
            live = adapter.extract(system, r.object)
            verdict = adapter.verify(r, live)
        except Exception as ex:  # noqa: BLE001 — a record that cannot be read is reported, not fatal
            skipped.append({"key": r.key, "reason": str(ex)})
            continue
        finding = watch.observe(r, verdict, actor, progress=progress.get(r.key, UNTOUCHED))
        if finding is None:
            verified.append(r.key)
        elif finding.status == NOT_APPLIED:
            unbuilt.append({"key": finding.key, "system": finding.system,
                            "reason": "signed intent describes it; nothing has been written yet"})
        elif finding.status == AWAITING_A_PERSON:
            awaiting.append({"key": finding.key, "system": finding.system, "tier": r.tier,
                             "handed_over": handed_at.get(r.key, ""),
                             "reason": f"Tier {r.tier} — this product publishes no write path, so "
                                       f"a person does it. The artefact was handed over and the "
                                       f"work is not in the system yet."})
        else:
            findings.append({"key": finding.key, "status": finding.status,
                             "system": finding.system, "fields": finding.fields,
                             "decision_point": finding.dp_id})
    e.persist_dps()
    return {"verified": verified, "drift": findings, "skipped": skipped, "not_applied": unbuilt,
            "awaiting_a_person": awaiting, "unconfirmable": unconfirmable, "attested": attested,
            "planning_blocked": bool(findings)}


@router.get("/assurance")
def assurance(eid: str, identity: Identity = Depends(require("read"))):
    """Of everything this engagement claims is done, how much can be demonstrated.

    A read of the chain, so it costs nothing and cannot disagree with the ledger it is drawn from.
    Gated on `read`: an auditor asks this question more often than anybody, and it changes nothing.
    """
    e = get_or_404(eid)
    return assure(e.ir, e.ledger.entries).as_dict()


@router.post("")
def verify(eid: str, identity: Identity = Depends(require("ledger_append"))):
    """Verify every IR record whose system has a bound connector. Reading only — a verification
    that could write would be an execute wearing a lab coat."""
    return run_verification(get_or_404(eid), identity.subject)

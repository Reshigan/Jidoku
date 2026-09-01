"""Evidence export (E2): the ledger chain plus artefacts, verifiable OFFLINE by an auditor.

The export's whole point is that it does not require JIDOKA to be trusted, or even running. A bundle
carries the chain, the genesis constant, the hashing rule in prose, and a manifest digest — an auditor
recomputes sha256 over each entry and confirms the links themselves. `verify_bundle` below is the same
algorithm, shipped inside the bundle as a readable procedure so it can be reimplemented in any language.
"""
from __future__ import annotations

import hashlib
import json

from jidoka_core.ledger import GENESIS

VERIFY_PROCEDURE = (
    "For each entry in order: take the entry object, remove the keys 'hash' and 'prev', add the key "
    "'prev' set to the previous entry's 'hash' (or 64 zeroes for the first entry), serialise as JSON "
    "with sorted keys and no whitespace changes (json.dumps(obj, sort_keys=True)), and take the "
    "SHA-256 hex digest. It must equal the entry's 'hash', and the entry's 'prev' must equal the "
    "previous entry's 'hash'. Any mismatch means the record was altered after it was written."
)


def _entry_hash(entry: dict, prev_hash: str) -> str:
    body = {k: v for k, v in entry.items() if k not in ("hash", "prev")}
    payload = json.dumps({**body, "prev": prev_hash}, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def verify_bundle(entries: list[dict]) -> dict:
    """Recompute the chain exactly as an external auditor would. Never trusts the stored hashes."""
    prev = GENESIS
    for i, e in enumerate(entries):
        if e.get("prev") != prev:
            return {"verified": False, "broken_at": i,
                    "reason": f"entry {i} claims prev={e.get('prev')!r}, chain says {prev!r}"}
        recomputed = _entry_hash(e, prev)
        if recomputed != e.get("hash"):
            return {"verified": False, "broken_at": i,
                    "reason": f"entry {i} hash mismatch: stored {e.get('hash')!r}, recomputed {recomputed!r}"}
        prev = e["hash"]
    return {"verified": True, "entries": len(entries), "head": prev}


def build_bundle(engagement, plan: dict | None = None) -> dict:
    """Assemble the auditor-facing bundle. Everything asserted here is derivable from the ledger."""
    entries = list(engagement.ledger.entries)
    verification = verify_bundle(entries)

    approvals = [e for e in entries if e["action"] == "APPROVED"]
    executions = [e for e in entries if e["action"] == "EXECUTED"]
    snapshots = {e["task"] for e in entries if e["action"] == "SNAPSHOT"}
    halts = [e for e in entries if e["action"] in ("LINE_HALTED", "LINE_RESUMED")]

    # SoD attestation, recomputed from history rather than asserted from roles.
    sod = []
    for a in approvals:
        builders = {e["actor"] for e in executions if e["task"] == a["task"]}
        sod.append({"task": a["task"], "approved_by": a["actor"], "executed_by": sorted(builders),
                    "separation_held": a["actor"] not in builders,
                    "snapshot_present": a["task"] in snapshots})

    dps = [{"dp_id": d.dp_id, "dp_type": d.dp_type, "question": d.question, "owner": d.owner,
            "resolution": d.resolution} for d in engagement.decisions.dps.values()]
    unresolved = [d["dp_id"] for d in dps if not d["resolution"]]

    bundle = {
        "bundle_version": "evidence/v1",
        "engagement": {"engagement_id": engagement.engagement_id, "name": engagement.name,
                       "client": engagement.client, "phase": engagement.phase},
        "chain": {"genesis": GENESIS, "entries": entries, "verification": verification,
                  "verify_procedure": VERIFY_PROCEDURE},
        "separation_of_duties": sod,
        "decision_points": {"all": dps, "unresolved": unresolved},
        "landscape": engagement.registry.landscape(),
        "ir": {"records": len(engagement.ir),
               "open_decision_points": engagement.open_dps,
               "sources": sorted({r.source.get("workbook", "?") for r in engagement.ir})},
        "line_state": {"halt_events": halts},
        "plan": plan,
    }
    # The manifest digest covers the bundle as issued: a changed byte anywhere invalidates it.
    bundle["manifest_sha256"] = hashlib.sha256(
        json.dumps(bundle, sort_keys=True, default=str).encode()).hexdigest()
    return bundle

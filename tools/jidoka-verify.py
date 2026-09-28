#!/usr/bin/env python3
"""Verify a JIDOKA evidence bundle. Standard library only. No network. No JIDOKA code.

    python3 jidoka-verify.py bundle.json

The point of this file is that it does not trust the platform that produced the bundle — including
about whether the bundle verifies. `GET /ledger/evidence` has described itself as "offline
checkable" since E2 and shipped the hashing rule in prose, and nothing shipped that checked it, so
an auditor's only options were to believe the `verification: true` inside the bundle or to write
this themselves. Believing it is not verification: a platform that got the chain wrong, or lied
about it, would say exactly the same word.

So every number here is recomputed from the entries and then **compared against what the bundle
claims**. A disagreement is reported as a disagreement, naming both sides. That is the one check a
vendor cannot do for you.

This is the third implementation of the chain rule — the Python kernel, the Durable Object at the
edge, and this. It is held to the same conformance fixture as the other two (ADR-0037), because
three implementations that agree by coincidence is not the same as three that are checked.

Copy it anywhere. It imports nothing but the standard library on purpose: an auditor should be
able to read all of it in one sitting and run it on a laptop with no install step.
"""
import hashlib
import json
import sys

GENESIS = "0" * 64

# --- the chain rule, restated ------------------------------------------------------------------
# Deliberately a copy. A verifier that imported the platform's implementation would be the
# platform checking its own work, which is the thing this file exists to avoid.


def entry_hash(entry, prev_hash):
    body = {k: v for k, v in entry.items() if k not in ("hash", "prev")}
    return hashlib.sha256(
        json.dumps({**body, "prev": prev_hash}, sort_keys=True).encode()).hexdigest()


def verify_chain(entries):
    prev = GENESIS
    for i, e in enumerate(entries):
        if e.get("prev") != prev:
            return False, (f"entry {i} ({e.get('task')} {e.get('action')}) claims it follows "
                           f"{e.get('prev')!r}; the chain says {prev!r}")
        recomputed = entry_hash(e, prev)
        if recomputed != e.get("hash"):
            return False, (f"entry {i} ({e.get('task')} {e.get('action')}) was altered after it "
                           f"was written: stored {e.get('hash')!r}, recomputed {recomputed!r}")
        prev = e["hash"]
    return True, prev


# --- the assurance formula, restated -----------------------------------------------------------
# proven = checked / (checked + disagrees + attested + unevidenced). The denominator is every
# record something claims is done; the numerator is the subset read back from the live system.

BASIS = {"VERIFIED": "checked", "DRIFT_DETECTED": "disagrees", "ATTESTED": "attested",
         "UNCONFIRMABLE": "unevidenced", "AWAITING_A_PERSON": "outstanding",
         "NOT_APPLIED": "unbuilt"}
CLAIMED = ("checked", "disagrees", "attested", "unevidenced")


def recompute_assurance(entries):
    verdict = {}
    for e in entries:
        if e.get("action") in BASIS:
            verdict[e.get("task")] = BASIS[e["action"]]
    counts = {}
    for basis in verdict.values():
        counts[basis] = counts.get(basis, 0) + 1
    claimed = sum(counts.get(b, 0) for b in CLAIMED)
    proven = counts.get("checked", 0)
    return {"claimed": claimed, "proven": proven,
            "fraction": (proven / claimed) if claimed else None}


# --- separation of duties, recomputed ----------------------------------------------------------


def recompute_sod(entries):
    executions, snapshots, out = {}, set(), []
    for e in entries:
        if e.get("action") == "EXECUTED":
            executions.setdefault(e.get("task"), set()).add(e.get("actor"))
        elif e.get("action") == "SNAPSHOT":
            snapshots.add(e.get("task"))
    for e in entries:
        if e.get("action") != "APPROVED":
            continue
        builders = executions.get(e.get("task"), set())
        out.append({"task": e.get("task"), "approved_by": e.get("actor"),
                    "separation_held": e.get("actor") not in builders,
                    "snapshot_present": e.get("task") in snapshots})
    return out


# --- the run ------------------------------------------------------------------------------------


def check(bundle):
    """Returns (findings, notes). A finding is a reason not to rely on this bundle."""
    findings, notes = [], []

    claimed_digest = bundle.get("manifest_sha256")
    body = {k: v for k, v in bundle.items() if k != "manifest_sha256"}
    recomputed = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    if not claimed_digest:
        findings.append("the bundle carries no manifest digest, so nothing covers it as a whole")
    elif recomputed != claimed_digest:
        findings.append(f"the bundle was changed after it was issued: manifest says "
                        f"{claimed_digest}, recomputed {recomputed}")
    else:
        notes.append(f"manifest digest matches ({recomputed[:16]}…)")

    entries = (bundle.get("chain") or {}).get("entries") or []
    if (bundle.get("chain") or {}).get("genesis") not in (None, GENESIS):
        findings.append("the bundle declares a genesis this verifier does not use")
    ok, detail = verify_chain(entries)
    if not ok:
        findings.append(f"the chain does not verify — {detail}")
    else:
        notes.append(f"{len(entries)} entries verify from genesis; head {detail[:16]}…")

    # The platform's own claim about the chain, contradicted where it is wrong. A bundle that says
    # it verifies and does not is a worse artefact than one that says nothing.
    said = (bundle.get("chain") or {}).get("verification") or {}
    if "verified" in said and bool(said["verified"]) != ok:
        findings.append(f"the bundle claims verified={said['verified']} and this verifier finds "
                        f"{ok}. The producer and an independent check disagree.")

    mine = recompute_assurance(entries)
    theirs = bundle.get("assurance") or {}
    if theirs:
        for field in ("claimed", "proven"):
            if field in theirs and theirs[field] != mine[field]:
                findings.append(f"assurance disagrees on {field}: bundle says {theirs[field]}, "
                                f"recomputed {mine[field]}")
        if not findings:
            shown = "—" if mine["fraction"] is None else f"{mine['fraction'] * 100:.0f}%"
            notes.append(f"assurance recomputes to {shown} "
                         f"({mine['proven']} of {mine['claimed']} claimed done, read back)")
    else:
        notes.append("the bundle states no assurance figure; recomputed "
                     f"{mine['proven']} of {mine['claimed']}")

    theirs_sod = {(r.get("task"), r.get("approved_by")): r
                  for r in bundle.get("separation_of_duties") or []}
    for row in recompute_sod(entries):
        stated = theirs_sod.get((row["task"], row["approved_by"]))
        if stated is None:
            findings.append(f"{row['task']} was approved by {row['approved_by']} and the bundle's "
                            f"separation table does not list it")
            continue
        for field in ("separation_held", "snapshot_present"):
            if bool(stated.get(field)) != row[field]:
                findings.append(f"{row['task']}: bundle says {field}={stated.get(field)}, "
                                f"recomputed {row[field]}")
        if not row["separation_held"]:
            findings.append(f"{row['task']} was approved by {row['approved_by']}, who also "
                            f"executed it")
        if not row["snapshot_present"]:
            findings.append(f"{row['task']} was approved with no before-snapshot on the chain")
    if theirs_sod:
        notes.append(f"{len(theirs_sod)} approval(s) checked for separation of duties")

    unresolved = ((bundle.get("decision_points") or {}).get("unresolved")) or []
    if unresolved:
        notes.append(f"{len(unresolved)} decision point(s) are open: {', '.join(unresolved)}")

    return findings, notes


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        print("usage: jidoka-verify.py <bundle.json>", file=sys.stderr)
        return 2
    try:
        with open(argv[1], encoding="utf-8") as fh:
            bundle = json.load(fh)
    except (OSError, ValueError) as ex:
        print(f"could not read {argv[1]}: {type(ex).__name__}", file=sys.stderr)
        return 2

    eng = bundle.get("engagement") or {}
    print(f"JIDOKA evidence bundle — {eng.get('client', '?')}, {eng.get('name', '?')} "
          f"({bundle.get('bundle_version', 'unknown version')})")
    findings, notes = check(bundle)
    for n in notes:
        print(f"  ok   {n}")
    for f in findings:
        print(f"  FAIL {f}")
    print()
    if findings:
        print(f"{len(findings)} finding(s). This bundle does not support what it claims.")
        return 1
    print("Every claim in this bundle was recomputed from its own entries and holds.")
    print("This says the record is internally consistent and unaltered. It does not say the "
          "record is complete: a change made outside the platform leaves nothing here to check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

"""The verifier an auditor runs, held to the thing it verifies.

`GET /ledger/evidence` has called itself "offline-checkable" since E2 and shipped the hashing rule
in prose, and nothing shipped that checked it. An auditor's only options were to believe the
`verification: true` inside the bundle or to write the verifier themselves. Believing it is not
verification — a platform that got the chain wrong, or lied about it, says the same word.

These tests run the real script, as a subprocess, against real bundles. Importing it would let it
quietly acquire the platform's own code, which is the one thing it must not have.
"""
import json
import pathlib
import subprocess
import sys

from fastapi.testclient import TestClient
from jidoka_api.main import app
from jidoka_api.routers.engagements import STORE

c = TestClient(app)
ROOT = pathlib.Path(__file__).resolve().parents[3]
VERIFIER = ROOT / "tools/jidoka-verify.py"
IR = json.load(open(ROOT / "packages/jidoka-core/tests/fixtures/komatsu_sample_ir.json"))


def run(bundle, tmp_path) -> subprocess.CompletedProcess:
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle))
    return subprocess.run([sys.executable, str(VERIFIER), str(path)],
                          capture_output=True, text=True)


def _eng():
    eid = c.post("/engagements", json={"name": "ZA payroll", "client": "Komatsu"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/ir", json=IR)
    return eid


def bundle_for(eid):
    return c.get(f"/engagements/{eid}/ledger/evidence").json()


def test_it_imports_nothing_from_the_platform_it_checks():
    """A verifier that imported the platform's implementation would be the platform checking its
    own work, which is the thing this file exists to avoid."""
    src = VERIFIER.read_text()
    assert "jidoka" not in src.split('"""', 2)[2].replace("jidoka-verify", ""), \
        "the verifier reaches into the codebase it is meant to be independent of"
    assert "import requests" not in src and "urllib" not in src, "it must not reach the network"


def test_a_real_bundle_verifies(tmp_path):
    out = run(bundle_for(_eng()), tmp_path)
    assert out.returncode == 0, out.stdout
    assert "Every claim in this bundle was recomputed" in out.stdout
    assert "entries verify from genesis" in out.stdout


def test_it_says_what_a_clean_result_does_not_mean(tmp_path):
    """A verifier that printed "verified" and stopped would be read as "the record is complete"."""
    out = run(bundle_for(_eng()), tmp_path)
    assert "does not say the record is complete" in out.stdout
    assert "outside the platform leaves nothing here to check" in out.stdout


def test_one_altered_character_in_one_entry_is_caught(tmp_path):
    b = bundle_for(_eng())
    b["chain"]["entries"][0]["detail"] = "tampered after the fact"
    out = run(b, tmp_path)
    assert out.returncode == 1
    assert "was altered after it was written" in out.stdout


def test_a_bundle_that_lies_about_verifying_is_contradicted(tmp_path):
    """The one check a vendor cannot do for you: the producer says verified, and an independent
    recomputation says otherwise."""
    b = bundle_for(_eng())
    b["chain"]["entries"][1]["actor"] = "somebody.else"
    b["chain"]["verification"] = {"verified": True, "entries": len(b["chain"]["entries"])}
    out = run(b, tmp_path)
    assert out.returncode == 1
    assert "The producer and an independent check disagree" in out.stdout


def test_an_edited_bundle_fails_on_the_manifest_even_where_the_chain_still_holds(tmp_path):
    b = bundle_for(_eng())
    b["engagement"]["client"] = "A Different Client"
    out = run(b, tmp_path)
    assert out.returncode == 1
    assert "changed after it was issued" in out.stdout


def test_an_overstated_assurance_number_is_recomputed_and_refused(tmp_path):
    """The number a customer quotes. A bundle that carried the evidence and not the claim would
    leave it to be read off a screen nobody can check."""
    eid = _eng()
    b = bundle_for(eid)
    b["assurance"]["proven"] = b["assurance"]["proven"] + 5
    b["manifest_sha256"] = __import__("hashlib").sha256(
        json.dumps({k: v for k, v in b.items() if k != "manifest_sha256"},
                   sort_keys=True, default=str).encode()).hexdigest()
    out = run(b, tmp_path)
    assert out.returncode == 1 and "assurance disagrees on proven" in out.stdout


def test_a_self_approval_is_named_even_if_the_bundle_calls_it_separated(tmp_path):
    """Recomputed from the entries, never read off the booleans the producer wrote."""
    eid = _eng()
    led = STORE.get(eid).ledger
    led.append("SF:PICKLIST:A", "SNAPSHOT", "a.builder", "before")
    led.append("SF:PICKLIST:A", "EXECUTED", "a.builder", "wrote it")
    led.append("SF:PICKLIST:A", "APPROVED", "a.builder", "and approved it")
    b = bundle_for(eid)
    for row in b["separation_of_duties"]:
        row["separation_held"] = True                 # the producer insists
    out = run(b, tmp_path)
    assert out.returncode == 1
    assert "who also executed it" in out.stdout


def test_it_runs_on_a_laptop_with_nothing_installed(tmp_path):
    """No install step, no third-party import, and a usage line when called wrongly."""
    out = subprocess.run([sys.executable, str(VERIFIER)], capture_output=True, text=True)
    assert out.returncode == 2 and "usage:" in out.stderr


def test_the_third_implementation_is_held_to_the_same_fixture_as_the_other_two(tmp_path):
    """The Python kernel, the Durable Object at the edge, and this. Three implementations that
    agree by coincidence is not the same as three that are checked (ADR-0037), and this one is
    the copy an auditor actually runs."""
    import hashlib

    spec = json.load(open(ROOT / "packages/jidoka-core/tests/fixtures/ledger_conformance.json"))
    bundle = {"bundle_version": "evidence/v1",
              "engagement": {"client": "Komatsu", "name": "conformance"},
              "chain": {"genesis": spec["genesis"], "entries": spec["expected"],
                        "verification": {"verified": True}},
              # The fixture's chain carries an execution and an approval by different people,
              # over a snapshot. An empty table here is not "nothing to say" — the verifier
              # catches the omission, which is how this test found its own first mistake.
              "separation_of_duties": [{"task": "SF:PICKLIST:ZA_MIBCO", "approved_by": "r.reviewer",
                                        "separation_held": True, "snapshot_present": True}],
              "decision_points": {"unresolved": []}}
    bundle["manifest_sha256"] = hashlib.sha256(
        json.dumps(bundle, sort_keys=True, default=str).encode()).hexdigest()

    out = run(bundle, tmp_path)
    assert out.returncode == 0, out.stdout
    assert f"{len(spec['expected'])} entries verify from genesis" in out.stdout


def test_it_rejects_the_fixture_with_one_byte_changed(tmp_path):
    """Proven failing, like every other guard here: a verifier that passed everything would pass
    a forgery too."""
    import hashlib

    spec = json.load(open(ROOT / "packages/jidoka-core/tests/fixtures/ledger_conformance.json"))
    entries = [dict(e) for e in spec["expected"]]
    t = spec["tamper"]
    entries[t["index"]][t["field"]] = t["to"]
    bundle = {"bundle_version": "evidence/v1", "engagement": {},
              "chain": {"genesis": spec["genesis"], "entries": entries},
              "separation_of_duties": [], "decision_points": {"unresolved": []}}
    bundle["manifest_sha256"] = hashlib.sha256(
        json.dumps(bundle, sort_keys=True, default=str).encode()).hexdigest()

    out = run(bundle, tmp_path)
    assert out.returncode == 1 and "was altered after it was written" in out.stdout

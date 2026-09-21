"""The ledger's semantics as data, and the kernel proving it satisfies them.

`deploy/cloudflare/src/ledger.check.mjs` runs the same fixture against the Durable Object's
implementation. That is the entire point: governance must not vary by hosting, and a second
implementation of the chain in a second language is the one place that promise can quietly stop
being true — not by anyone deciding to weaken it, but because `JSON.stringify` does not put a
space after a comma and Python's `json.dumps` does.

If this file and the .mjs one ever disagree, the deployment has two ledgers.
"""
import json
import pathlib

import pytest

from jidoka_core.ledger import GENESIS, Ledger, LedgerTampered, SoDViolation

FIXTURE = json.load(open(pathlib.Path(__file__).parent / "fixtures/ledger_conformance.json"))


def _replay() -> Ledger:
    """The operations, with the fixture's timestamps: the spec is about the chain, not the clock."""
    led = Ledger()
    stamps = [e["ts"] for e in FIXTURE["expected"]]

    def at(i):
        def _append(task, action, actor, detail="", **extra):
            prev = led.entries[-1]["hash"] if led.entries else GENESIS
            entry = {"ts": stamps[i[0]], "task": task, "action": action, "actor": actor,
                     "detail": detail, **extra}
            i[0] += 1
            entry["hash"] = led._hash(entry, prev)
            entry["prev"] = prev
            led.entries.append(entry)
            return entry
        return _append

    led.append = at([0])
    for op in FIXTURE["operations"]:
        if op["op"] == "append":
            led.append(op["task"], op["action"], op["actor"], op["detail"], **op["extra"])
        else:
            led.approve(op["task"], op["reviewer"])
    return led


def test_the_kernel_produces_the_hashes_in_the_spec():
    """Byte-for-byte. A hash that differs by a space in a separator is a different chain, and an
    auditor verifying the edge's chain against the kernel's would find it broken."""
    assert _replay().entries == FIXTURE["expected"]


def test_genesis_is_what_the_spec_says_it_is():
    assert GENESIS == FIXTURE["genesis"]


def test_separation_of_duties_refuses_exactly_what_the_spec_says_it_refuses():
    led = _replay()
    for case in FIXTURE["sod"]:
        with pytest.raises(SoDViolation) as ex:
            led.approve(case["task"], case["reviewer"])
        assert str(ex.value) == case["message"], case["why"]


def test_tampering_breaks_the_chain_at_the_point_the_spec_names():
    led = _replay()
    t = FIXTURE["tamper"]
    led.entries[t["index"]][t["field"]] = t["to"]
    with pytest.raises(LedgerTampered):
        led.verify_chain()


def test_an_untouched_chain_verifies():
    assert _replay().verify_chain() is True

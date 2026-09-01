"""The executor against a real S4Adapter and a real OData client, over the mock SAP server.

test_executor.py proves the gates with a FakeAdapter. This proves the other half: that a step
which passes the gates actually mutates the substrate, that a dry run does not touch it at all,
and that a half-landed batch is reported as half-landed rather than as a success.
"""
import copy
import json

import pytest

from jidoka_adapters.mocksap import MockSAP
from jidoka_adapters.mocksap.server import CSRF_TOKEN
from jidoka_adapters.s4hana import S4Adapter, S4ODataClient, S4ODataError
from jidoka_core import transport as tp
from jidoka_core.executor import (ArmedTarget, Executor, FAILED, IN_TRANSPORT, PARTIAL,
                                  ROLLED_BACK, VERIFIED)
from jidoka_core.ir import IRRecord
from jidoka_core.ledger import Ledger
from jidoka_core.registry import SystemRegistry, SystemRecord

BASE = "https://api.example.com"
TASK = "T-E2E"
SERVICE = "API_COSTCENTER_SRV"
ENTITY = "A_CostCenter"
CC = "0000100000"
SIGNED = {"workbook": "WB-1", "signed_by": "consultant@client", "date": "2026-09-01"}
SECRET = "s4-client-secret-never-in-a-ledger"


def transport(sap):
    """MockSAP speaks the SF surface; S/4 additionally does a HEAD CSRF handshake.
    ponytail: a two-line shim rather than teaching the shared mock an S/4-only verb."""
    def t(method, url, headers, body=None, timeout=60.0):
        if method == "HEAD":
            return 200, {"X-CSRF-Token": CSRF_TOKEN}, b""
        return sap(method, url, headers, body, timeout)
    return t


def client(sap):
    return S4ODataClient(BASE, client_id="jidoka-cid", client_secret=SECRET,
                         token_url=f"{BASE}/oauth/token", transport=transport(sap))


def rec(intent=None):
    return IRRecord(object=ENTITY, product="S4HANA", system_binding="S4-DEV",
                    intent=intent or {"CostCenter": CC, "CompanyCode": "2000"},
                    tier="A", source=dict(SIGNED), external_code=CC)


def executor():
    r = SystemRegistry()
    r.register(SystemRecord("S4-DEV", "S4HANA", "DEV", "dev",
                            connectivity={"write_credentials": True}))
    return Executor(r, Ledger(), "agent-k5")


def armed():
    return ArmedTarget("S4-DEV", "approver@client", "e2e proof")


def apply_via(c, sap, ops=None):
    """The real apply_fn: drives S4ODataClient.batch, then re-reads for verification.

    Returns the partial-application signal the executor needs — the batch transport can
    answer 202 while individual changeset operations were rejected.
    """
    def fn(payload):
        operations = ops or payload["operations"]
        out = c.batch(payload["service"], operations, dry_run=payload["dry_run"])
        failed = [r for r in out.get("results", []) if r["status"] >= 400]
        return {"live_state": c.read_entity(SERVICE, ENTITY),
                "failed_operations": len(failed), "total_operations": len(operations)}
    return fn


# --- 1. happy path: the row is actually mutated -----------------------------------

def test_armed_execute_actually_mutates_the_row():
    sap, e = MockSAP(require_csrf=True), executor()
    a = S4Adapter(client=client(sap))
    assert sap.row(ENTITY, CC)["CompanyCode"] == "1000"

    e.snapshot(TASK, a, rec(), None)
    res = e.execute(TASK, a, rec(), armed=armed(), apply_fn=apply_via(client(sap), sap))

    assert res.verification["status"] == "MATCH"
    assert sap.row(ENTITY, CC)["CompanyCode"] == "2000"      # the substrate really changed
    assert sap.row(ENTITY, CC)["ControllingArea"] == "1000"  # merge, not replace
    assert any(x["action"] == "VERIFIED" for x in e.ledger.entries)
    # S/4 is ABAP: a verified DEV write is IN_TRANSPORT, not done, until it lands in PROD.
    assert res.status == IN_TRANSPORT
    assert not res.complete
    e.ledger.approve(TASK, "reviewer@client")
    assert e.ledger.verify_chain()


def test_verified_write_reaches_production_through_its_transport():
    """The same write, carried to PROD — only then is the step complete."""
    sap = MockSAP(require_csrf=True)
    r = SystemRegistry()
    for sid, role in (("S4-DEV", "DEV"), ("S4-QA", "TEST"), ("S4-PRD", "PROD")):
        r.register(SystemRecord(sid, "S4HANA", role, role.lower(),
                                connectivity={"write_credentials": True}))
    e = Executor(r, Ledger(), "agent-k5")
    a = S4Adapter(client=client(sap))
    route = tp.TransportRoute(["S4-DEV", "S4-QA", "S4-PRD"])
    req = tp.TransportRequest("S4DK900123", "owner@client", "cost centre 100000",
                              "S4-DEV", objects=[ENTITY])

    e.snapshot(TASK, a, rec(), None)
    res = e.execute(TASK, a, rec(), armed=armed(), apply_fn=apply_via(client(sap), sap),
                    transport_request=req, route=route)
    assert res.status == IN_TRANSPORT
    assert res.transport["next_hop"] == "S4-QA"

    e.advance_transport(TASK, req, route)   # -> QA
    e.advance_transport(TASK, req, route)   # -> PROD
    assert req.imported_into == ["S4-QA", "S4-PRD"]

    done = e.execute(TASK, a, rec(), armed=armed(), apply_fn=apply_via(client(sap), sap),
                     transport_request=req, route=route)
    assert done.status == VERIFIED
    assert done.complete
    assert e.ledger.verify_chain()


# --- 2. dry run touches the server zero times -------------------------------------

def test_dry_run_touches_the_server_zero_times():
    sap, e = MockSAP(require_csrf=True), executor()
    a = S4Adapter(client=client(sap))
    before = copy.deepcopy(sap.collections)
    calls = len(sap.calls)

    res = e.execute(TASK, a, rec(), apply_fn=apply_via(client(sap), sap))

    assert res.status == "DRY_RUN"
    assert res.payload["dry_run"] is True
    assert sap.collections == before
    assert json.dumps(sap.collections, sort_keys=True) == json.dumps(before, sort_keys=True)
    assert len(sap.calls) == calls  # no request reached the server at all


# --- 3. partial batch failure is surfaced honestly --------------------------------

THREE_OPS = [{"method": "UPSERT", "entity": ENTITY,
              "payload": {"CostCenter": cc, "CompanyCode": "2000"}}
             for cc in (CC, "0000200000", "0000300000")]


def test_partial_batch_is_not_reported_as_success():
    sap, e = MockSAP(require_csrf=True), executor()
    a = S4Adapter(client=client(sap))
    sap.fail_batch_at(2)  # op 1 commits, ops 2 and 3 do not

    e.snapshot(TASK, a, rec(), None)
    res = e.execute(TASK, a, rec(), armed=armed(),
                    apply_fn=apply_via(client(sap), sap, ops=THREE_OPS))

    assert res.status == PARTIAL
    assert res.status != VERIFIED
    assert sap.row(ENTITY, CC)["CompanyCode"] == "2000"           # op 1 landed
    assert sap.row(ENTITY, "0000200000")["CompanyCode"] == "1000"  # op 2 did not
    assert sap.row(ENTITY, "0000300000") is None                   # op 3 never created
    partial = [x for x in e.ledger.entries if x["action"] == PARTIAL]
    assert partial and partial[0]["failed_operations"] == 2
    assert e.ledger.verify_chain()


# --- 4. rollback restores the pre-execution state exactly -------------------------

def test_rollback_after_partial_restores_the_snapshot_exactly():
    sap, e = MockSAP(require_csrf=True), executor()
    c = client(sap)
    a = S4Adapter(client=c)
    pristine = copy.deepcopy(sap.collections)
    sap.fail_batch_at(2)

    before = e.snapshot(TASK, a, rec(), None)
    e.execute(TASK, a, rec(), armed=armed(), apply_fn=apply_via(c, sap, ops=THREE_OPS))
    assert sap.collections != pristine  # the partial really did dirty the substrate

    def restore(payload):
        c.batch(SERVICE, [{"method": "PUT", "entity": ENTITY, "payload": row}
                          for row in payload["rows"]], dry_run=False)

    res = e.rollback(TASK, before, restore, rec(), "partial batch: restoring snapshot")

    assert res.status == ROLLED_BACK
    assert sap.collections == pristine
    assert e.ledger.entries[-1]["action"] == ROLLED_BACK
    assert e.ledger.verify_chain()


# --- 5. injected failures: FAILED, recorded, chain intact, no secrets --------------

@pytest.mark.parametrize("inject", ["500", "429"])
def test_injected_failure_is_recorded_without_leaking_secrets(inject):
    sap, e = MockSAP(require_csrf=True), executor()
    c = client(sap)
    a = S4Adapter(client=c)
    c.token()  # authenticate before arming the failure, so the injection hits the batch
    before = copy.deepcopy(sap.collections)

    e.snapshot(TASK, a, rec(), None)
    sap.fail_next(500) if inject == "500" else sap.fail_next_rate_limited()
    res = e.execute(TASK, a, rec(), armed=armed(), apply_fn=apply_via(c, sap))

    assert res.status == FAILED
    assert res.detail == "S4ODataError"
    assert e.ledger.entries[-1]["action"] == FAILED
    assert e.ledger.verify_chain()
    assert sap.collections == before  # a failed batch wrote nothing

    blob = json.dumps(e.ledger.entries, default=str)
    assert SECRET not in blob
    assert "jidoka-cid" not in blob
    assert "mock-bearer" not in blob
    assert "Bearer" not in blob
    assert CSRF_TOKEN not in blob

"""Executor gates. Each test names the invariant it defends; if one of these goes green
by being deleted rather than fixed, an invariant has been silently weakened."""
import pytest

from jidoka_core.executor import (ArmedTarget, ExecutionRefused, Executor,
                                  DRY_RUN, VERIFIED, DRIFTED, FAILED, ROLLED_BACK, HANDED_OFF,
                                  IN_TRANSPORT, is_abap)
from jidoka_core.ir import IRRecord
from jidoka_core.ledger import Ledger, SoDViolation
from jidoka_core.registry import SystemRegistry, SystemRecord, WriteLockViolation
from jidoka_core.transport import TransportRequest, TransportRoute, IMPORTED

TASK = "T-1"
SIGNED = {"workbook": "WB-1", "signed_by": "consultant@client", "date": "2026-09-01"}


class FakeAdapter:
    """Minimal Adapter stand-in: the executor must not care which product it is talking to."""
    product = "S4HANA"

    def __init__(self, live=None, matches=True):
        self.live = live if live is not None else [{"CostCenter": "CC-1000"}]
        self.matches = matches
        self.applied = []

    def tier_map(self):
        return {"A_CostCenter": "A"}

    def extract(self, system, entity):
        return list(self.live)

    def build_apply(self, ir_record):
        return {"kind": "odata_write", "entity": ir_record.object,
                "body": ir_record.intent, "dry_run": True}

    def verify(self, ir_record, live_state):
        return {"status": "MATCH" if self.matches else "DRIFT", "checked": len(live_state)}


def rec(tier="A", system="S4-DEV", obj="A_CostCenter", product="S4HANA"):
    return IRRecord(object=obj, product=product, system_binding=system,
                    intent={"externalCode": "CC-1000", "name": "Ops"},
                    tier=tier, source=dict(SIGNED))


def registry(write_creds=True, role="DEV"):
    r = SystemRegistry()
    r.register(SystemRecord("S4-DEV", "S4HANA", role, "dev",
                            connectivity={"write_credentials": write_creds} if write_creds else {}))
    r.register(SystemRecord("LEGACY", "ECC", "SOURCE_LEGACY", "prod", connectivity={}))
    r.register(SystemRecord("S4-QA", "S4HANA", "TEST", "qa", connectivity={"write_credentials": True}))
    r.register(SystemRecord("S4-PRD", "S4HANA", "PROD", "prod", connectivity={"write_credentials": True}))
    return r


def ex(actor="agent-k5", **kw):
    return Executor(registry(**kw), Ledger(), actor)


# --- invariant 6: Tier-A defaults to dry run -------------------------------------

def test_unarmed_tier_a_is_dry_run_and_never_calls_apply():
    e = ex()
    boom = lambda p: pytest.fail("apply_fn called during a dry run")
    res = e.execute(TASK, FakeAdapter(), rec(), apply_fn=boom)
    assert res.status == DRY_RUN
    assert res.payload["dry_run"] is True


def test_arming_requires_named_target_and_person():
    with pytest.raises(ExecutionRefused):
        ArmedTarget("", "approver@client")
    with pytest.raises(ExecutionRefused):
        ArmedTarget("S4-DEV", "")


def test_arming_is_per_target_and_not_inherited():
    e = ex()
    e.snapshot(TASK, FakeAdapter(), rec(), None)
    with pytest.raises(ExecutionRefused, match="never inherited"):
        e.execute(TASK, FakeAdapter(), rec(system="S4-DEV"),
                  armed=ArmedTarget("S4-PRD", "approver@client"), apply_fn=lambda p: {})


# --- invariant 7: agent is builder, never approver -------------------------------

def test_executor_may_not_arm_its_own_write():
    e = ex(actor="agent-k5")
    e.snapshot(TASK, FakeAdapter(), rec(), None)
    with pytest.raises(ExecutionRefused, match="builder != approver"):
        e.execute(TASK, FakeAdapter(), rec(),
                  armed=ArmedTarget("S4-DEV", "agent-k5"), apply_fn=lambda p: {})


# --- invariant 4: no live write without a prior snapshot -------------------------

def test_live_write_without_snapshot_refused():
    e = ex()
    with pytest.raises(ExecutionRefused, match="no before-snapshot"):
        e.execute(TASK, FakeAdapter(), rec(),
                  armed=ArmedTarget("S4-DEV", "approver@client"), apply_fn=lambda p: {})


def test_snapshot_then_execute_leaves_an_approvable_chain():
    e = ex()
    a = FakeAdapter()
    e.snapshot(TASK, a, rec(), None)
    e.execute(TASK, a, rec(), armed=ArmedTarget("S4-DEV", "approver@client"),
              apply_fn=lambda p: {"live_state": a.live})
    e.ledger.approve(TASK, "reviewer@client")
    assert e.ledger.verify_chain()


def test_executor_cannot_approve_its_own_execution():
    """The ledger's SoD gate keys on EXECUTED — proves the executor emits the exact string."""
    e = ex(actor="agent-k5")
    a = FakeAdapter()
    e.snapshot(TASK, a, rec(), None)
    e.execute(TASK, a, rec(), armed=ArmedTarget("S4-DEV", "approver@client"),
              apply_fn=lambda p: {"live_state": a.live})
    with pytest.raises(SoDViolation):
        e.ledger.approve(TASK, "agent-k5")


# --- invariant 3: write-forbidden roles and missing credentials ------------------

def test_write_to_source_legacy_refused():
    e = ex()
    e.snapshot(TASK, FakeAdapter(), rec(system="LEGACY"), None)
    with pytest.raises(WriteLockViolation):
        e.execute(TASK, FakeAdapter(), rec(system="LEGACY"),
                  armed=ArmedTarget("LEGACY", "approver@client"), apply_fn=lambda p: {})


def test_target_without_vaulted_credentials_refused():
    e = ex(write_creds=False)
    e.snapshot(TASK, FakeAdapter(), rec(), None)
    with pytest.raises(WriteLockViolation, match="Tier-A apply impossible"):
        e.execute(TASK, FakeAdapter(), rec(),
                  armed=ArmedTarget("S4-DEV", "approver@client"), apply_fn=lambda p: {})


# --- tiers B and C never write ---------------------------------------------------

@pytest.mark.parametrize("tier", ["B", "C"])
def test_non_tier_a_is_handed_to_a_person(tier):
    e = ex()
    boom = lambda p: pytest.fail("a Tier-B/C step must never reach the substrate")
    res = e.execute(TASK, FakeAdapter(), rec(tier=tier),
                    armed=ArmedTarget("S4-DEV", "approver@client"), apply_fn=boom)
    assert res.status == HANDED_OFF


# --- outcomes --------------------------------------------------------------------

def test_armed_write_with_no_apply_fn_refuses_rather_than_pretending():
    e = ex()
    e.snapshot(TASK, FakeAdapter(), rec(), None)
    with pytest.raises(ExecutionRefused, match="Refusing to pretend"):
        e.execute(TASK, FakeAdapter(), rec(), armed=ArmedTarget("S4-DEV", "approver@client"))


def test_verified_when_adapter_confirms():
    """Non-ABAP product: the verified write IS the whole change, so VERIFIED is terminal."""
    e = ex()
    a = FakeAdapter()
    r = rec(product="SuccessFactors")
    e.snapshot(TASK, a, r, None)
    res = e.execute(TASK, a, r, armed=ArmedTarget("S4-DEV", "approver@client"),
                    apply_fn=lambda p: {"live_state": a.live})
    assert res.status == VERIFIED
    assert res.complete


def test_drift_when_live_state_disagrees():
    e = ex()
    a = FakeAdapter(matches=False)
    e.snapshot(TASK, a, rec(), None)
    res = e.execute(TASK, a, rec(), armed=ArmedTarget("S4-DEV", "approver@client"),
                    apply_fn=lambda p: {"live_state": a.live})
    assert res.status == DRIFTED
    assert any(x["action"] == "DRIFT_DETECTED" for x in e.ledger.entries)


def test_substrate_failure_is_recorded_not_swallowed():
    e = ex()
    e.snapshot(TASK, FakeAdapter(), rec(), None)

    def blow_up(payload):
        raise ConnectionError("s4.example.invalid unreachable")

    res = e.execute(TASK, FakeAdapter(), rec(),
                    armed=ArmedTarget("S4-DEV", "approver@client"), apply_fn=blow_up)
    assert res.status == FAILED
    assert e.ledger.entries[-1]["action"] == "FAILED"
    assert e.ledger.verify_chain()


def test_failure_detail_carries_no_exception_message():
    """A substrate exception can echo a bearer token back. Only the type reaches the ledger."""
    e = ex()
    e.snapshot(TASK, FakeAdapter(), rec(), None)

    def leaky(payload):
        raise ConnectionError("Bearer eyJhbGciOi-SECRET refused")

    res = e.execute(TASK, FakeAdapter(), rec(),
                    armed=ArmedTarget("S4-DEV", "approver@client"), apply_fn=leaky)
    assert "SECRET" not in res.detail
    assert "SECRET" not in "".join(str(v) for x in e.ledger.entries for v in x.values())


# --- rollback --------------------------------------------------------------------

def test_rollback_restores_the_snapshot_exactly():
    e = ex()
    a = FakeAdapter()
    before = e.snapshot(TASK, a, rec(), None)
    seen = []
    e.rollback(TASK, before, lambda p: seen.append(p), rec(), "drift after apply")
    assert seen[0]["rows"] == before
    assert e.ledger.entries[-1]["action"] == ROLLED_BACK


def test_rollback_without_a_snapshot_refused():
    e = ex()
    with pytest.raises(ExecutionRefused, match="nothing proven to restore"):
        e.rollback(TASK, [], lambda p: None, rec(), "no snapshot")


def test_executor_requires_a_named_actor():
    with pytest.raises(ExecutionRefused):
        Executor(registry(), Ledger(), "")


# --- ABAP transport: a verified write is not a finished change -------------------

ROUTE = ["S4-DEV", "S4-QA", "S4-PRD"]


def treq():
    return TransportRequest(request_id="S4DK900123", owner="j.smith",
                            description="Cost centre config", source_system="S4-DEV",
                            objects=["A_CostCenter"])


def route(e):
    return TransportRoute(list(ROUTE)).validate(e.registry)


def abap_write(e, a, tr, rt):
    r = rec()
    e.snapshot(TASK, a, r, None)
    return e.execute(TASK, a, r, armed=ArmedTarget("S4-DEV", "approver@client"),
                     apply_fn=lambda p: {"live_state": a.live},
                     transport_request=tr, route=rt)


def test_abap_products_are_recognised_and_cloud_products_are_not():
    assert is_abap("S4HANA") and is_abap("ECC") and is_abap("S/4HANA")
    assert not is_abap("SuccessFactors") and not is_abap("BTP") and not is_abap("")


def test_abap_verified_write_is_in_transport_not_complete():
    e, a = ex(), FakeAdapter()
    tr, rt = treq(), route(e)
    res = abap_write(e, a, tr, rt)
    assert res.status == IN_TRANSPORT
    assert not res.complete
    assert res.transport["next_hop"] == "S4-QA"
    assert "not yet in production" in res.detail
    assert any(x["action"] == "IN_TRANSPORT" for x in e.ledger.entries)


def test_abap_step_is_complete_once_imported_into_prod():
    e, a = ex(), FakeAdapter()
    tr, rt = treq(), route(e)
    assert abap_write(e, a, tr, rt).status == IN_TRANSPORT
    assert e.advance_transport(TASK, tr, rt, released_by="j.smith")["next_hop"] == "S4-PRD"
    state = e.advance_transport(TASK, tr, rt)
    assert state["in_production"] is True
    # Re-running the step against a request that has landed in PROD is terminal-success.
    res = abap_write(e, a, tr, rt)
    assert res.status == VERIFIED and res.complete


def test_abap_write_without_a_transport_is_never_reported_complete():
    """No transport attached is still not done — the write stands, the step does not."""
    e, a = ex(), FakeAdapter()
    r = rec()
    e.snapshot(TASK, a, r, None)
    res = e.execute(TASK, a, r, armed=ArmedTarget("S4-DEV", "approver@client"),
                    apply_fn=lambda p: {"live_state": a.live})
    assert res.status == IN_TRANSPORT and not res.complete
    assert "not in production" in res.detail


def test_transport_route_order_is_enforced_and_failure_leaks_no_message():
    e = ex()
    rt, tr = route(e), treq()
    tr.owner = ""  # release refuses; its message names the request, which must not reach the ledger
    with pytest.raises(ExecutionRefused, match="TransportError"):
        e.advance_transport(TASK, tr, rt)
    assert e.ledger.entries[-1]["action"] == "TRANSPORT_FAILED"
    assert e.ledger.entries[-1]["detail"] == "TransportError"


def test_advance_past_production_is_refused():
    e = ex()
    rt, tr = route(e), treq()
    e.advance_transport(TASK, tr, rt, released_by="j.smith")
    e.advance_transport(TASK, tr, rt)
    with pytest.raises(ExecutionRefused, match="already in production"):
        e.advance_transport(TASK, tr, rt)


def test_ledger_chain_verifies_after_a_full_release_and_import_sequence():
    e, a = ex(), FakeAdapter()
    rt, tr = route(e), treq()
    abap_write(e, a, tr, rt)
    e.advance_transport(TASK, tr, rt, released_by="j.smith")
    e.advance_transport(TASK, tr, rt)
    assert e.ledger.verify_chain()
    actions = [x["action"] for x in e.ledger.entries]
    # the strings Ledger.approve() keys on are still emitted, unchanged
    assert "SNAPSHOT" in actions and "EXECUTED" in actions
    assert actions.count("TRANSPORT_RELEASED") == 1
    assert actions.count("TRANSPORT_IMPORTED") == 2
    assert tr.status == IMPORTED
    e.ledger.approve(TASK, "reviewer@client")
    assert e.ledger.verify_chain()

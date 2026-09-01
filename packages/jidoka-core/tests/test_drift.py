"""Drift is a decision, not a report. The watch never reconciles; it blocks."""
from jidoka_core.decisions import DecisionEngine
from jidoka_core.drift import DriftWatch, dp_id_for
from jidoka_core.ir import IRRecord
from jidoka_core.ledger import Ledger


def _rec():
    return IRRecord(object="TimeType", product="SuccessFactors", system_binding="SF-PRD",
                    intent={"externalCode": "ANN_ZA", "unit": "DAYS"}, tier="A",
                    source={"workbook": "wb.xlsx", "cell_range": "B2", "signed_by": "T. Mabaso",
                            "date": "2026-08-01"}, external_code="ANN_ZA")


def _watch():
    ledger = Ledger()
    return DriftWatch(ledger, DecisionEngine(ledger)), ledger


def test_a_match_is_ledgered_and_raises_nothing():
    w, ledger = _watch()
    assert w.observe(_rec(), {"status": "MATCH"}, "verifier") is None
    assert ledger.entries[-1]["action"] == "VERIFIED"
    assert not w.decisions.dps


def test_drift_appends_to_the_ledger_and_raises_a_blocking_decision():
    w, ledger = _watch()
    f = w.observe(_rec(), {"status": "DRIFT", "drift": {"unit": {"intent": "DAYS", "live": "HOURS"}}},
                  "verifier")
    assert f.status == "DRIFT" and "unit" in f.fields
    assert any(e["action"] == "DRIFT_DETECTED" for e in ledger.entries)
    dp = w.decisions.dps[f.dp_id]
    assert dp.resolution is None and dp.owner == "T. Mabaso"
    # Both honest exits are offered; silent reconciliation is not one of them.
    assert any("reassert" in o for o in dp.options)
    assert any("new IR" in o or "sign a new" in o for o in dp.options)


def test_drift_never_auto_reapplies_or_adopts():
    """The watch's whole API is observe(). There is no reconcile, no heal, no sync."""
    w, _ = _watch()
    assert not any(hasattr(w, m) for m in ("reconcile", "heal", "sync", "reapply", "adopt"))


def test_a_missing_record_is_drift_with_its_own_wording():
    w, ledger = _watch()
    f = w.observe(_rec(), {"status": "MISSING"}, "verifier")
    assert f.status == "MISSING"
    assert "absent from live system" in ledger.entries[-2]["detail"]  # -1 is DP_RAISED


def test_repeated_drift_does_not_stack_decision_points():
    w, _ = _watch()
    verdict = {"status": "DRIFT", "drift": {"unit": {"intent": "DAYS", "live": "HOURS"}}}
    w.observe(_rec(), verdict, "verifier")
    w.observe(_rec(), verdict, "verifier")
    assert len(w.decisions.dps) == 1


def test_a_match_after_drift_keeps_the_question_open():
    """Something changed the system twice without a signed record. Better timing is not an answer."""
    w, ledger = _watch()
    w.observe(_rec(), {"status": "DRIFT", "drift": {"unit": {"intent": "DAYS", "live": "HOURS"}}},
              "verifier")
    assert w.observe(_rec(), {"status": "MATCH"}, "verifier") is None
    assert w.decisions.dps[dp_id_for(_rec().key)].resolution is None
    assert "remains open" in ledger.entries[-1]["detail"]


def test_a_resolved_drift_decision_can_be_raised_again_on_new_drift():
    w, _ = _watch()
    verdict = {"status": "DRIFT", "drift": {"unit": {"intent": "DAYS", "live": "HOURS"}}}
    f = w.observe(_rec(), verdict, "verifier")
    w.decisions.resolve(f.dp_id, "T. Mabaso", "reassert", "review note")
    f2 = w.observe(_rec(), verdict, "verifier")
    assert w.decisions.dps[f2.dp_id].resolution is None  # fresh question, not the settled one


def test_an_open_drift_decision_blocks_planning_like_any_other():
    """Invariant 2, extended: DecisionEngine questions reach the planner gate (ADR-0013)."""
    import pytest
    from jidoka_core.planner import PlanError, plan
    w, _ = _watch()
    rec = _rec()
    w.observe(rec, {"status": "MISSING", "key": "ANN_ZA", "key_field": "externalCode"}, "agent")
    with pytest.raises(PlanError):
        plan([rec], w.decisions.unresolved())

"""Twin v1: rules it can evaluate, rules it refuses, and a fidelity it has to earn."""
import json
import pathlib

import pytest
from jidoka_core.twin import (ACCEPT, MIN_SCORED, REJECT, RuleTwin, SchemaTwin, fidelity,
                              parse_rules)

FIX = pathlib.Path(__file__).parent / "fixtures"
META = json.load(open(FIX / "metadata_sample.json"))

R107 = {"rule_id": "R-107", "entity": "TimeType", "source": "SF rule export 2026-02",
        "when": [{"field": "unit", "op": "eq", "value": "DAYS"}],
        "then": [{"field": "accrual_frequency", "op": "required"}]}


def payload(**over):
    return {"externalCode": "ANN", "unit": "DAYS", "timeAccountType": "ANN_ACC", **over}


# --- what it refuses to evaluate ------------------------------------------------------------------

def test_a_rule_outside_the_subset_is_named_not_approximated():
    rules, refused = parse_rules([R107, {"rule_id": "R-X", "entity": "TimeType",
                                         "then": [{"field": "f", "op": "sounds_like"}]}])
    assert [r.rule_id for r in rules] == ["R-107"]
    assert refused[0]["rule_id"] == "R-X" and "outside the subset" in refused[0]["why"]


def test_a_rule_missing_its_entity_is_refused_rather_than_guessed():
    _, refused = parse_rules([{"rule_id": "R-Y", "then": [{"field": "f", "op": "required"}]}])
    assert refused[0]["why"] == "no entity"


def test_parsing_never_raises_on_somebody_elses_export():
    """The useful answer is which parts of the file this twin can honour, not a stack trace."""
    rules, refused = parse_rules([{}, {"rule_id": "R"}, R107])
    assert len(rules) == 1 and len(refused) == 2


# --- what it predicts -----------------------------------------------------------------------------

def test_a_rule_that_does_not_apply_says_nothing():
    rules, _ = parse_rules([R107])
    out = RuleTwin(META, rules).predict("TimeType", payload(unit="HOURS"))
    assert out["verdict"] == ACCEPT and out["rules_applied"] == 0


def test_a_breached_rule_is_a_predicted_rejection_with_its_reason():
    rules, _ = parse_rules([R107])
    out = RuleTwin(META, rules).predict("TimeType", payload())
    assert out["verdict"] == REJECT
    assert out["reasons"] == ["R-107: accrual_frequency must be set"]
    assert out["rules_applied"] == 1


def test_schema_and_rules_both_speak():
    rules, _ = parse_rules([R107])
    out = RuleTwin(META, rules).predict("TimeType", {"unit": "DAYS"})
    assert any("externalCode" in r for r in out["reasons"])       # schema
    assert any("R-107" in r for r in out["reasons"])              # rule


def test_the_v0_schema_behaviour_is_unchanged():
    """v1 adds rules; it does not quietly change what v0 already caught."""
    assert SchemaTwin(META).validate_payload("TimeType", payload()) == []
    assert RuleTwin(META).predict("TimeType", payload())["verdict"] == ACCEPT


def test_a_numeric_comparison_on_a_non_number_does_not_pass_by_accident():
    rules, _ = parse_rules([{"rule_id": "R-N", "entity": "TimeType",
                             "then": [{"field": "unit", "op": "lte", "value": 5}]}])
    assert RuleTwin(META, rules).predict("TimeType", payload())["verdict"] == REJECT


# --- fidelity it has to earn ----------------------------------------------------------------------

def chain(*pairs):
    out = []
    for i, (verdict, outcome) in enumerate(pairs):
        out.append({"task": f"t{i}", "action": "TWIN_PREDICTED", "verdict": verdict})
        if outcome:
            out.append({"task": f"t{i}", "action": outcome})
    return out


def test_a_handful_of_comparisons_buys_no_percentage():
    f = fidelity(chain((ACCEPT, "VERIFIED"), (ACCEPT, "VERIFIED")))
    assert f["status"] == "UNCALIBRATED" and f["fidelity"] is None and f["scored"] == 2


def test_once_calibrated_it_reports_the_rate_and_its_misses():
    rows = chain(*([(ACCEPT, "VERIFIED")] * 9 + [(ACCEPT, "FAILED")]))
    f = fidelity(rows)
    assert f["status"] == "CALIBRATED" and f["scored"] == MIN_SCORED
    assert f["fidelity"] == 0.9
    assert f["misses"] == [{"task": "t9", "predicted": ACCEPT, "outcome": "FAILED"}]


def test_a_predicted_rejection_that_really_failed_is_an_agreement():
    f = fidelity(chain(*([(REJECT, "FAILED")] * 10)))
    assert f["fidelity"] == 1.0


def test_an_unsettled_prediction_is_counted_as_unsettled_not_dropped():
    """A twin that only counted the writes that happened would grade itself on the easy cases."""
    f = fidelity(chain((ACCEPT, "VERIFIED"), (ACCEPT, None), (REJECT, None)))
    assert f["unsettled"] == 2 and f["scored"] == 1


def test_a_prediction_superseded_before_the_system_answered_is_unsettled():
    rows = [{"task": "t", "action": "TWIN_PREDICTED", "verdict": ACCEPT},
            {"task": "t", "action": "TWIN_PREDICTED", "verdict": REJECT},
            {"task": "t", "action": "FAILED"}]
    f = fidelity(rows)
    assert f["scored"] == 1 and f["unsettled"] == 1 and f["agreed"] == 1


def test_the_method_and_the_threshold_travel_with_the_number():
    f = fidelity([])
    assert f["min_scored"] == MIN_SCORED and "withheld below" in f["method"]

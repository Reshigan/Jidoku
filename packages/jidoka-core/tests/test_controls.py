"""Controls are predicates over the whole population. Each test is a control catching its case."""
from jidoka_core.controls import CONTROLS, run_all


def chain(*rows):
    return [{"ts": f"T{i}", **row} for i, row in enumerate(rows, 1)]


def result(entries, control_id, **kw):
    return next(c for c in run_all(entries, **kw)["controls"] if c["control_id"] == control_id)


def test_a_write_with_no_prior_snapshot_is_enumerated_not_counted():
    r = result(chain({"task": "t", "action": "EXECUTED", "actor": "b", "armed_by": "a"}), "C-EXE-01")
    assert r["status"] == "FAIL" and r["tested"] == 1
    assert r["violations"] == [{"task": "t", "actor": "b", "ts": "T1",
                                "why": "written with no before-state on the chain"}]


def test_a_snapshot_after_the_write_does_not_count_as_before():
    """"Already on the chain" is a position, not a membership test."""
    r = result(chain({"task": "t", "action": "EXECUTED", "actor": "b"},
                     {"task": "t", "action": "SNAPSHOT", "actor": "b"}), "C-EXE-01")
    assert r["status"] == "FAIL"


def test_a_self_approval_is_caught_even_when_the_ledger_is_otherwise_clean():
    r = result(chain({"task": "t", "action": "SNAPSHOT", "actor": "b"},
                     {"task": "t", "action": "EXECUTED", "actor": "b", "armed_by": "a"},
                     {"task": "t", "action": "APPROVED", "actor": "b"}), "C-SOD-01")
    assert r["status"] == "FAIL" and "executed it" in r["violations"][0]["why"]


def test_an_approval_by_a_different_person_passes():
    r = result(chain({"task": "t", "action": "EXECUTED", "actor": "b"},
                     {"task": "t", "action": "APPROVED", "actor": "r"}), "C-SOD-01")
    assert r["status"] == "PASS"


def test_a_write_that_armed_itself_is_caught():
    r = result(chain({"task": "t", "action": "EXECUTED", "actor": "b", "armed_by": "b"}), "C-ARM-01")
    assert r["status"] == "FAIL" and "same person" in r["violations"][0]["why"]


def test_a_write_with_no_arming_recorded_is_caught():
    r = result(chain({"task": "t", "action": "EXECUTED", "actor": "b"}), "C-ARM-01")
    assert r["status"] == "FAIL" and "no armed target" in r["violations"][0]["why"]


def test_a_write_that_reached_a_write_locked_system_is_caught():
    r = result(chain({"task": "t", "action": "EXECUTED", "actor": "b", "system": "KOM-ECC-PRD"}),
               "C-REG-01", write_locked={"KOM-ECC-PRD"})
    assert r["status"] == "FAIL" and "may not hold write credentials" in r["violations"][0]["why"]


def test_a_transport_that_stopped_short_of_production_is_a_standing_question():
    r = result(chain({"task": "t", "action": "TRANSPORT_ADVANCED", "actor": "b",
                      "request_id": "S4DK9001", "target_system": "S4-QA", "next_hop": "S4-PRD",
                      "in_production": False}), "C-TRN-01")
    assert r["status"] == "FAIL" and "S4DK9001" in r["violations"][0]["why"]


def test_the_latest_hop_decides_whether_a_transport_landed():
    r = result(chain({"task": "t", "action": "TRANSPORT_ADVANCED", "request_id": "R1",
                      "target_system": "S4-QA", "next_hop": "S4-PRD", "in_production": False},
                     {"task": "t", "action": "TRANSPORT_ADVANCED", "request_id": "R1",
                      "target_system": "S4-PRD", "next_hop": None, "in_production": True}),
               "C-TRN-01")
    assert r["status"] == "PASS"


def test_a_control_with_nothing_to_test_has_not_passed():
    """The difference between "we checked and it held" and "there was nothing to check" is the
    whole reason an auditor asks about population."""
    r = result([], "C-EXE-01")
    assert r["status"] == "NOT_EXERCISED" and r["tested"] == 0
    assert r["passed"] is True, "no violations, but that is not a pass"


def test_every_control_names_its_population_and_its_statement():
    for control in CONTROLS.values():
        assert control.statement.endswith("."), control.control_id
        assert control.population and control.rows


def test_the_method_is_published_with_the_result():
    out = run_all([])
    assert "never a sample" in out["method"] and out["population_complete"] is True

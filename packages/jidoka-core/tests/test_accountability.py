"""The platform's account of itself. Nothing here is a grade, and that is the design."""
from jidoka_core.accountability import UNMEASURABLE, account, mistakes, refusals

GATE = "POST /engagements/{eid}/execution/execute"


def refused(ts, actor="a.builder", gate=GATE):
    return {"ts": ts, "task": gate, "action": "REFUSED", "actor": actor,
            "detail": "nothing is armed", "status": 403, "gate": "forbidden"}


def cleared(ts, actor="a.builder", gate=GATE):
    return {"ts": ts, "task": gate, "action": "CLEARED", "actor": actor, "detail": ""}


def test_a_gate_cleared_within_the_hour_every_time_reads_as_friction():
    """The person had the missing step in hand. That is a gate asking for a formality — unless
    the formality is the point, which is why this is reported and not scored."""
    entries = [refused("2026-09-21T09:00:00Z"), cleared("2026-09-21T09:10:00Z"),
               refused("2026-09-21T11:00:00Z"), cleared("2026-09-21T11:05:00Z")]
    out = refusals(entries)
    assert out["fired"] == 2 and out["cleared"] == 2 and out["still_standing"] == 0
    assert out["gates"][0]["cleared_fast"] == 2
    assert "friction" in out["gates"][0]["reads_as"]


def test_a_gate_nothing_ever_clears_is_stopping_something_real():
    out = refusals([refused("2026-09-21T09:00:00Z"), refused("2026-09-22T09:00:00Z")])
    assert out["still_standing"] == 2
    assert "stopping something nobody has resolved" in out["gates"][0]["reads_as"]


def test_a_slow_clearing_is_a_gate_working_not_friction():
    """Cleared a day later means somebody had to go and do something. That is the gate doing its
    job, and counting it as friction would argue for removing the gates that work."""
    out = refusals([refused("2026-09-21T09:00:00Z"), cleared("2026-09-22T09:00:00Z")])
    assert out["cleared"] == 1 and out["gates"][0]["cleared_fast"] == 0
    assert "ordinary shape of a gate that is working" in out["gates"][0]["reads_as"]


def test_somebody_elses_success_is_not_your_refusal_clearing():
    """Separation of duties working looks exactly like this, and counting it as a clearing would
    report the platform's most important gate as its most frictional one."""
    out = refusals([refused("2026-09-21T09:00:00Z", "a.builder"),
                    cleared("2026-09-21T09:05:00Z", "a.reviewer")])
    assert out["still_standing"] == 1 and out["cleared"] == 0


def test_the_same_gate_on_two_engagements_is_one_gate():
    """The route template, not the URL: without it every engagement's refusals would be their own
    row and a pattern across a portfolio would be invisible."""
    out = refusals([refused("2026-09-21T09:00:00Z"), refused("2026-09-21T10:00:00Z")])
    assert len(out["gates"]) == 1 and out["gates"][0]["fired"] == 2


def test_drift_on_something_already_verified_is_counted_apart_from_drift():
    out = mistakes([{"task": "A", "action": "VERIFIED"}, {"task": "A", "action": "DRIFT_DETECTED"},
                    {"task": "B", "action": "DRIFT_DETECTED"}])
    assert out["drift_after_verified"] == ["A"], \
        "B was never verified — the system changed under nobody's claim"


def test_the_same_record_wrong_twice_is_counted_once():
    out = mistakes([{"task": "A", "action": "VERIFIED"}, {"task": "A", "action": "DRIFT_DETECTED"},
                    {"task": "A", "action": "VERIFIED"}, {"task": "A", "action": "DRIFT_DETECTED"}])
    assert out["drift_after_verified"] == ["A"]


def test_it_says_what_it_cannot_measure_beside_the_numbers_not_in_a_footnote():
    out = account([])
    assert out["unmeasurable"] == list(UNMEASURABLE)
    assert any("never reached a gate" in u for u in out["unmeasurable"])


def test_no_single_number_comes_out_of_it():
    """A grade would be quoted. The four questions are the product."""
    out = account([refused("2026-09-21T09:00:00Z")])
    assert "score" not in out and "grade" not in out
    assert set(out) == {"refusals", "mistakes", "twin", "unmeasurable", "says"}


def test_two_refusals_and_one_clearing_clears_both():
    """They were refused twice and got through once; both refusals were eventually followed by
    that person getting past that gate. The count is of refusals that stopped holding, not of
    clearings — and a single pass has to say the same thing a scan per refusal did."""
    out = refusals([refused("2026-09-21T09:00:00Z"), refused("2026-09-21T09:30:00Z"),
                    cleared("2026-09-21T09:40:00Z")])
    assert out["fired"] == 2 and out["cleared"] == 2 and out["still_standing"] == 0


def test_a_refusal_after_a_clearing_stands_on_its_own():
    """Getting past a gate once does not retire it: the next refusal is open again."""
    out = refusals([refused("2026-09-21T09:00:00Z"), cleared("2026-09-21T09:10:00Z"),
                    refused("2026-09-21T14:00:00Z")])
    assert out["cleared"] == 1 and out["still_standing"] == 1


def test_two_gates_do_not_clear_each_other():
    other = "POST /engagements/{eid}/ledger/approve"
    out = refusals([refused("2026-09-21T09:00:00Z"), refused("2026-09-21T09:05:00Z", gate=other),
                    cleared("2026-09-21T09:10:00Z")])
    assert {g["gate"]: g["standing"] for g in out["gates"]} == {GATE: 0, other: 1}

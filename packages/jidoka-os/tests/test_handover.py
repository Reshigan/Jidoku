"""The night shift: what it says now, what it saves for the morning, and what it never says."""
from jidoka_os.handover import COST_OF_SILENCE, Finding, Night, compose, run


def night(*findings, did=("read the systems",)):
    return Night(did=list(did), findings=list(findings))


def test_a_chain_break_wakes_somebody_and_a_stale_attestation_does_not():
    out = run(night(Finding("unconfirmable", "nobody has attested to the data model"),
                    Finding("chain_broken", "the ledger chain does not verify")))
    assert [f["kind"] for f in out["interrupted"]] == ["chain_broken"]
    assert [f["kind"] for f in out["waited"]] == ["unconfirmable"]


def test_the_budget_is_spent_on_cost_not_on_order_of_discovery():
    """A chain break found at 04:00 outranks a control that failed at 22:00."""
    out = run(night(Finding("control_failing", "C-EXE-01 is failing"),
                    Finding("statutory_open", "DP-STAT-X is blocking"),
                    Finding("partial_write", "a write half-landed"),
                    Finding("chain_broken", "the chain does not verify")),
              budget=2)
    assert [f["kind"] for f in out["interrupted"]] == ["chain_broken", "partial_write"]
    assert {f["kind"] for f in out["deferred"]} == {"control_failing", "statutory_open"}


def test_what_the_budget_held_back_is_in_the_handover_never_dropped():
    out = run(night(*[Finding("chain_broken", f"break {i}") for i in range(5)]), budget=2)
    assert out["budget"] == {"of": 2, "spent": 2, "held_back": 3, "threshold": 55}
    assert len(out["deferred"]) == 3
    assert "break 4" in compose(out, "E", "C")


def test_an_unspent_budget_stays_unspent():
    """A colleague who talks less than they could is trusted more."""
    out = run(night(Finding("twin_miss", "the twin was wrong about ANN_LEAVE")))
    assert out["interrupted"] == [] and out["budget"]["spent"] == 0
    assert "did not wake anybody" in compose(out, "E", "C")


def test_a_quiet_night_still_produces_a_handover_that_says_so():
    out = run(night())
    text = compose(out, "ZA payroll", "Komatsu")
    assert "Nothing. Every check I ran came back the way it did yesterday." in text
    assert "Nothing from me. I will keep checking." in text


def test_the_handover_is_first_person_and_in_three_parts():
    out = run(night(Finding("drift", "ANN_LEAVE drifted", "T. Mabaso", "unit: DAYS -> HOURS")))
    text = compose(out, "ZA payroll", "Komatsu")
    assert text.startswith("Handover — Komatsu, ZA payroll")
    for part in ("**What I did**", "**What I found**", "**What I need from you today**"):
        assert part in text
    assert "- T. Mabaso: ANN_LEAVE drifted" in text
    assert "unit: DAYS -> HOURS" in text


def test_a_finding_with_nobody_to_ask_is_reported_and_asks_nothing():
    """The twin's own misses are its business, not somebody's morning."""
    out = run(night(Finding("twin_miss", "the twin was wrong about ANN_LEAVE")))
    text = compose(out, "E", "C")
    assert "the twin was wrong" in text
    assert "Nothing from me. I will keep checking." in text


def test_the_cost_table_is_published_with_the_night():
    out = run(night())
    assert out["cost_of_silence"] == COST_OF_SILENCE
    assert out["cost_of_silence"]["chain_broken"] > out["cost_of_silence"]["twin_miss"]

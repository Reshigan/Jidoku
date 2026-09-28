"""The night shift: what it says now, what it saves for the morning, and what it never says."""
from datetime import datetime, timezone

from jidoka_os.handover import (COST_OF_SILENCE, DEFAULT_CADENCE_HOURS, SILENCE_FACTOR,
                                Finding, Night, cadence, clock, compose, run)


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


# --- addressing people rather than roles (M4) -----------------------------------------------------

from datetime import datetime, timezone                                        # noqa: E402

from jidoka_os.people import Person                                            # noqa: E402

WED = datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc)
SAT = datetime(2026, 9, 19, 5, 0, tzinfo=timezone.utc)
TEAM = [Person("T. Mabaso", frozenset({"approve", "resolve_dp"}), cost=4, utc_offset=2),
        Person("A. Silva", frozenset({"resolve_dp"}), cost=1, utc_offset=2, hours=(8, 16))]


def test_with_no_team_registered_it_names_the_role_exactly_as_before():
    """Honest and useless, and better than pretending somebody was asked."""
    out = run(night(Finding("drift", "ANN_LEAVE drifted", "whoever signed it", needs="resolve_dp")))
    assert out["waited"][0]["who"] == "whoever signed it"
    assert "- whoever signed it: ANN_LEAVE drifted" in compose(out, "E", "C")


def test_with_a_team_it_asks_the_cheapest_sufficient_authority_by_name():
    out = run(night(Finding("drift", "ANN_LEAVE drifted", "whoever signed it", needs="resolve_dp")),
              people=TEAM, now=WED)
    assert out["waited"][0]["who"] == "A. Silva"
    assert "- A. Silva: ANN_LEAVE drifted" in compose(out, "E", "C")


def test_a_routine_ask_outside_their_hours_says_when_they_will_see_it():
    out = run(night(Finding("drift", "ANN_LEAVE drifted", needs="resolve_dp")),
              people=TEAM, now=SAT)
    assert "- A. Silva — at Mon 08:00 their time: ANN_LEAVE drifted" in compose(out, "E", "C")


def test_an_urgent_ask_outside_their_hours_goes_now():
    out = run(night(Finding("chain_broken", "the chain does not verify", needs="approve")),
              people=TEAM, now=SAT)
    row = (out["interrupted"] + out["waited"])[0]
    assert row["who"] == "T. Mabaso" and row["when"] == "now"


def test_a_finding_nobody_registered_can_answer_is_the_finding():
    out = run(night(Finding("arming_lapsed", "the arming of KOM-SF-DEV lapsed", needs="arm")),
              people=TEAM, now=WED)
    text = compose(out, "E", "C")
    assert "(nobody I can ask) the arming of KOM-SF-DEV lapsed" in text
    assert "nobody registered on this engagement may 'arm'" in text


def test_a_finding_that_needs_nobody_is_never_routed():
    out = run(night(Finding("twin_miss", "the twin was wrong about ANN_LEAVE")),
              people=TEAM, now=WED)
    assert out["waited"][0]["who"] == ""
    assert "Nothing from me. I will keep checking." in compose(out, "E", "C")


# --- the clock: nothing inside a night can report its own absence (ADR-0030) --------------------

def test_a_night_that_never_ran_says_the_clock_may_not_be_deployed():
    c = clock([])
    assert c["running"] is False and c["last_worked"] == ""
    assert "not deployed" in c["says"]


def test_a_night_worked_this_morning_is_a_running_clock():
    now = datetime(2026, 9, 21, 9, 0, tzinfo=timezone.utc)
    c = clock([{"ts": "2026-09-21T02:00:00Z", "action": "HANDOVER"}], now)
    assert c["running"] is True and c["silent_for_hours"] == 7.0


def test_two_missed_nights_cannot_pass_unnoticed():
    """Every way the night stops — a rotated token, a cron that is not firing, an edge that was
    never deployed — is invisible from inside the night that did not run."""
    now = datetime(2026, 9, 21, 9, 0, tzinfo=timezone.utc)
    c = clock([{"ts": "2026-09-18T02:00:00Z", "action": "HANDOVER"}], now)
    assert c["running"] is False
    assert c["silent_for_hours"] > DEFAULT_CADENCE_HOURS * SILENCE_FACTOR
    assert "rotated" in c["says"] and "not deployed" in c["says"]


def test_a_long_silence_is_said_in_days_because_hours_stop_being_a_fact():
    now = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
    assert "21 days" in clock([{"ts": "2026-09-21T09:00:00Z", "action": "HANDOVER"}], now)["says"]


def test_the_clock_reads_the_ledger_not_this_process():
    """The regression: the handover was held in memory, so a restart reported that no night had
    ever been worked on an engagement that had been worked every night for a month."""
    entries = [{"ts": "2026-09-20T02:00:00Z", "action": "HANDOVER"},
               {"ts": "2026-09-21T02:00:00Z", "action": "HANDOVER"},
               {"ts": "2026-09-21T02:00:01Z", "action": "ASKED", "person": "A. Silva"}]
    assert clock(entries, datetime(2026, 9, 21, 9, 0, tzinfo=timezone.utc))["last_worked"] == \
        "2026-09-21T02:00:00Z"


def test_a_programme_that_works_its_engagement_weekly_is_not_failing_on_a_tuesday():
    """Silence is measured against the cadence this engagement declared, not against a constant."""
    entries = [{"ts": "2026-09-14T02:00:00Z", "action": "NIGHT_CADENCE", "hours": 168},
               {"ts": "2026-09-14T02:00:00Z", "action": "HANDOVER"}]
    now = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)      # four days later
    assert cadence(entries) == 168
    assert clock(entries, now)["running"] is True
    assert clock([entries[1]], now)["running"] is False, "the same silence, at the default cadence"


def test_a_night_that_started_and_raised_is_not_a_clock_that_never_fired():
    """The two have different fixes — one is a fault in the run, the other is a deployment
    nobody finished — and a platform that reported them the same way would send somebody to
    check the cron for a connection error."""
    now = datetime(2026, 9, 21, 9, 0, tzinfo=timezone.utc)
    c = clock([{"ts": "2026-09-21T02:00:00Z", "action": "NIGHT_FAILED",
                "detail": "ConnectionError"}], now)
    assert c["running"] is False and c["failed_with"] == "ConnectionError"
    assert "fault in the run" in c["says"]


def test_a_failure_the_next_night_fixed_is_not_reported_forever():
    """A platform nursing a grudge about a failure that has since been superseded is a platform
    people learn to dismiss."""
    now = datetime(2026, 9, 21, 9, 0, tzinfo=timezone.utc)
    c = clock([{"ts": "2026-09-20T02:00:00Z", "action": "NIGHT_FAILED", "detail": "Timeout"},
               {"ts": "2026-09-21T02:00:00Z", "action": "HANDOVER"}], now)
    assert c["running"] is True and c["failed_at"] == ""

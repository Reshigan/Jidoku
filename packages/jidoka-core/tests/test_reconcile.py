"""The system's own log against ours — the blind spot, closed, and honest about what it closes."""
from jidoka_core.reconcile import WINDOW_MINUTES, reconcile

DESIGNED = {"SF:PICKLIST:A", "SF:PICKLIST:B"}


def ours(task, action="EXECUTED", ts="2026-09-21T09:00:00Z", actor="a.builder"):
    return {"task": task, "action": action, "actor": actor, "ts": ts}


def theirs(obj, ts="2026-09-21T09:00:00Z", by="jidoka", detail=""):
    return {"object": obj, "ts": ts, "changed_by": by, "detail": detail}


def test_a_change_made_by_hand_in_the_gui_is_the_finding():
    """The most expensive failure this platform can have, named for the first time."""
    out = reconcile([], [theirs("SF:PICKLIST:B", by="n.consultant")], DESIGNED)
    assert len(out["out_of_band"]) == 1
    row = out["out_of_band"][0]
    assert row["by"] == "n.consultant"
    assert "outside every one of its gates" in row["says"]
    assert "computed as if they had not happened" in out["says"]


def test_what_we_did_and_the_system_logged_is_simply_matched():
    out = reconcile([ours("SF:PICKLIST:A")],
                    [theirs("SF:PICKLIST:A", ts="2026-09-21T09:02:00Z")], DESIGNED)
    assert len(out["matched"]) == 1 and not out["out_of_band"] and not out["unconfirmed"]
    assert "No change to designed configuration was made outside the platform" in out["says"]


def test_clocks_drift_so_the_window_is_published_and_generous():
    """A product logs a change when it commits, not when the request arrived."""
    inside = reconcile([ours("SF:PICKLIST:A")],
                       [theirs("SF:PICKLIST:A", ts="2026-09-21T09:09:00Z")], DESIGNED)
    outside = reconcile([ours("SF:PICKLIST:A")],
                        [theirs("SF:PICKLIST:A", ts="2026-09-21T11:00:00Z")], DESIGNED)
    assert inside["matched"] and not inside["out_of_band"]
    assert outside["out_of_band"] and outside["unconfirmed"]
    assert inside["window_minutes"] == WINDOW_MINUTES


def test_a_change_to_something_nobody_designed_is_not_this_engagement_s_breach():
    """Counting it would make every programme look breached by the rest of the tenant."""
    out = reconcile([], [theirs("SF:SOMETHING:ELSE", by="another.team")], DESIGNED)
    assert out["out_of_band"] == [] and len(out["out_of_scope"]) == 1


def test_something_on_our_chain_the_log_does_not_show_is_a_question_not_an_accusation():
    out = reconcile([ours("SF:PICKLIST:A")], [], DESIGNED)
    assert len(out["unconfirmed"]) == 1
    assert "a question and not an accusation" in out["unconfirmed"][0]["says"]


def test_a_snapshot_or_a_rehearsal_is_not_expected_in_the_products_log():
    """A snapshot reads and a dry run rehearses; neither changed anything for a log to record."""
    out = reconcile([ours("SF:PICKLIST:A", action="SNAPSHOT"),
                     ours("SF:PICKLIST:A", action="DRY_RUN")], [], DESIGNED)
    assert out["unconfirmed"] == []


def test_a_rollback_is_a_write_and_is_expected_in_the_log():
    out = reconcile([ours("SF:PICKLIST:A", action="ROLLED_BACK")], [], DESIGNED)
    assert len(out["unconfirmed"]) == 1


def test_a_log_row_with_no_usable_time_is_matched_on_the_object_alone():
    """Better than calling a real change out-of-band because the tenant wrote a date this cannot
    parse."""
    out = reconcile([ours("SF:PICKLIST:A")], [theirs("SF:PICKLIST:A", ts="last Tuesday")], DESIGNED)
    assert out["matched"] and not out["out_of_band"]


def test_nothing_on_either_record_says_so_rather_than_claiming_a_clean_result():
    assert "Nothing to reconcile" in reconcile([], [], DESIGNED)["says"]

"""M6: once, with the consequence, overridden by a name, revisited where the consequence lands."""
import pytest

from jidoka_core.objections import (DEFAULT_REVISIT, Objection, ObjectionError, due,
                                    objection_id, state, what_happened)

OBJ = Objection("SF:PICKLIST:A", "rests on an attestation, not a check", "unevidenced",
                "if the person is mistaken nobody finds out until payroll runs",
                "build a read path before cutover")


def raised(o=OBJ, ts="2026-09-21T09:00:00Z", by="jidoka.auditor"):
    return {"ts": ts, "task": o.objection_id, "action": "OBJECTION_RAISED", "actor": by,
            "detail": o.finding, **o.as_entry()}


def overridden(o=OBJ, ts="2026-09-21T10:00:00Z", by="T. Mabaso", reason="the vendor confirmed it"):
    return {"ts": ts, "task": o.objection_id, "action": "OBJECTION_OVERRIDDEN", "actor": by,
            "detail": reason}


def test_identity_is_what_it_is_about_and_what_it_found():
    """So "state it once" is enforceable rather than remembered."""
    assert objection_id("A", "x") == objection_id("A", "x")
    assert objection_id("A", "x") != objection_id("B", "x")
    assert objection_id("A", "x") != objection_id("A", "y")


def test_a_finding_with_no_consequence_is_a_complaint():
    with pytest.raises(ObjectionError, match="is a complaint"):
        Objection("A", "something is off", "unevidenced", "", "fix it")
    with pytest.raises(ObjectionError, match="is a complaint"):
        Objection("A", "something is off", "unevidenced", "it breaks", "   ")


def test_a_platform_that_can_object_to_anything_objects_to_everything():
    with pytest.raises(ObjectionError, match="not grounds"):
        Objection("A", "f", "i do not like it", "c", "r")


def test_a_revisit_point_is_a_phase_not_a_date():
    """The consequence lands at a point in the engagement, not on a Tuesday."""
    assert OBJ.revisit_at == DEFAULT_REVISIT
    with pytest.raises(ObjectionError, match="not a phase"):
        Objection("A", "f", "unsafe", "c", "r", revisit_at="next month")


def test_raising_the_same_objection_twice_is_one_objection_still_open():
    rows = state([raised(), raised(ts="2026-09-22T09:00:00Z")])
    assert len(rows) == 1
    row = next(iter(rows.values()))
    assert row["status"] == "open" and row["restated"] == 1
    assert row["raised_at"] == "2026-09-21T09:00:00Z", "the first statement is the statement"


def test_an_override_is_attributed_to_the_person_not_the_role():
    row = state([raised(), overridden()])[OBJ.objection_id]
    assert row["status"] == "overridden" and row["overridden_by"] == "T. Mabaso"
    assert row["override_reason"] == "the vendor confirmed it"


def test_nothing_is_due_before_the_phase_where_the_consequence_lands():
    """A revisit early is a platform asking to be told it was right."""
    entries = [raised(), overridden()]
    assert due(entries, "BUILD") == []
    assert [o["objection_id"] for o in due(entries, "HYPERCARE")] == [OBJ.objection_id]


def test_an_objection_nobody_set_aside_is_never_due():
    """There is no consequence to come back to: the platform's position still stands."""
    assert due([raised()], "HYPERCARE") == []


def test_a_withdrawn_objection_is_the_platform_conceding_and_is_not_revisited():
    entries = [raised(), {"ts": "2026-09-21T11:00:00Z", "task": OBJ.objection_id,
                          "action": "OBJECTION_WITHDRAWN", "actor": "jidoka"}]
    assert state(entries)[OBJ.objection_id]["status"] == "withdrawn"
    assert due(entries, "HYPERCARE") == []


def test_the_revisit_reports_the_chain_and_never_a_verdict():
    out = what_happened([{"task": "SF:PICKLIST:A", "action": "DRIFT_DETECTED"},
                         {"task": "SF:PICKLIST:A", "action": "ROLLED_BACK"}], "SF:PICKLIST:A")
    assert "the live system has since disagreed" in out["says"] and "rolled back" in out["says"]
    assert "right" not in out["says"]


def test_silence_is_not_agreement():
    """Where the ledger recorded nothing, say so rather than reading nothing as fine."""
    assert "not the same as nothing having happened" in what_happened([], "SF:PICKLIST:A")["says"]

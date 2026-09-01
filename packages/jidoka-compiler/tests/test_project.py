"""Documents are projections. They may say less than the truth; they may never say more."""
import pytest
from jidoka_compiler.project import (ProjectionError, config_rationale, decision_register, render,
                                     solution_design)
from jidoka_core.decisions import DecisionEngine, DecisionPoint
from jidoka_core.ir import IRRecord
from jidoka_core.ledger import Ledger
from jidoka_core.registry import SystemRecord, SystemRegistry


class Eng:
    """The shape services/api holds. Built by hand so the tests do not depend on the API layer."""

    def __init__(self, ir=None, dps=None, open_dps=None):
        self.engagement_id, self.name, self.client = "E-1", "Payroll rollout", "Kruger Mining"
        self.phase = "DESIGN"
        self.ir = ir or []
        self.open_dps = open_dps or {}
        self.ledger = Ledger()
        self.registry = SystemRegistry()
        self.decisions = DecisionEngine(self.ledger)
        for dp in dps or []:
            self.decisions.dps[dp.dp_id] = dp


def _rec(**over):
    base = dict(object="LegalEntity", product="SuccessFactors", system_binding="SF-PRD",
                intent={"externalCode": "ZA01", "name": "Kruger ZA"}, tier="A",
                source={"workbook": "org-design-v3.xlsx", "cell_range": "row 12",
                        "signed_by": "T. Mabaso", "date": "2026-08-14"},
                country="ZA", depends_on=[], external_code="ZA01")
    base.update(over)
    return IRRecord(**base)


# --- the invention gate ---------------------------------------------------------------------------

def test_a_document_prints_no_value_the_ir_does_not_hold():
    """The whole point. Every value in the rendered document must be traceable to intent."""
    doc = config_rationale(Eng(ir=[_rec()]))
    assert "`ZA01`" in doc and "`Kruger ZA`" in doc
    # Nothing plausible-but-unstated: a currency, a country name, a payroll frequency.
    for invented in ("ZAR", "South Africa", "monthly", "Monthly"):
        assert invented not in doc


def test_an_undecided_field_renders_as_undecided_never_as_a_value():
    rec = _rec(intent={"externalCode": "ZA01",
                       "accrualDays": {"decision_point": "DP-07", "value": None}})
    doc = config_rationale(Eng(ir=[rec], open_dps={"DP-07": "LegalEntity ZA01"}))
    assert "Not yet decided" in doc and "DP-07" in doc
    assert "`None`" not in doc and "accrualDays`, `" not in doc


def test_a_resolved_decision_shows_its_value_and_the_decision_it_came_from():
    rec = _rec(intent={"externalCode": "ZA01",
                       "accrualDays": {"decision_point": "DP-07", "value": 21}})
    doc = config_rationale(Eng(ir=[rec]))
    assert "`21`" in doc and "resolved DP-07" in doc


def test_an_engagement_with_no_ir_renders_as_empty_not_as_a_template():
    doc = config_rationale(Eng())
    assert "Nothing has been configured" in doc
    assert "## SuccessFactors" not in doc


# --- provenance -----------------------------------------------------------------------------------

def test_every_value_carries_the_workbook_cell_and_signature_it_came_from():
    doc = config_rationale(Eng(ir=[_rec()]))
    assert "org-design-v3.xlsx row 12" in doc
    assert "T. Mabaso" in doc and "2026-08-14" in doc


def test_an_object_with_no_approval_says_so_rather_than_staying_quiet():
    """An auditor reading a silent document assumes approval. Silence is the wrong default."""
    assert "no approval recorded" in config_rationale(Eng(ir=[_rec()]))


def test_an_approval_on_the_ledger_reaches_the_document():
    e = Eng(ir=[_rec()])
    e.ledger.append("ZA01", "EXECUTED", "agent", "applied")
    e.ledger.append("ZA01", "SNAPSHOT", "agent", "pre-change")
    e.ledger.approve("ZA01", "R. Govender")
    doc = config_rationale(e)
    assert "R. Govender" in doc and "no approval recorded" not in doc


# --- the ledger is what makes it trustworthy -------------------------------------------------------

def test_a_broken_chain_is_printed_on_the_document_not_swallowed():
    """A document that renders cleanly over tampered state launders it."""
    e = Eng(ir=[_rec()])
    e.ledger.append("ZA01", "EXECUTED", "agent")
    e.ledger.entries[0]["detail"] = "something else entirely"
    doc = config_rationale(e)
    assert "did not verify" in doc and "unproven" in doc


def test_an_intact_chain_is_stated_with_its_entry_count():
    e = Eng(ir=[_rec()])
    e.ledger.append("ZA01", "EXECUTED", "agent")
    assert "Ledger verified — 1 entries" in config_rationale(e)


# --- solution design --------------------------------------------------------------------------------

def test_the_solution_design_does_not_write_the_process_narrative():
    """Authorship is not projection. The section exists and says a human has not written it."""
    doc = solution_design(Eng(ir=[_rec()]))
    assert "## Process design" in doc and "*Not generated.*" in doc


def test_open_decision_points_appear_in_the_design_as_open():
    doc = solution_design(Eng(ir=[_rec()], open_dps={"DP-07": "LegalEntity ZA01"}))
    assert "1 decision point(s) are open" in doc and "`DP-07`" in doc
    assert "Planning is blocked" in doc


def test_a_design_with_no_open_points_says_so_plainly():
    assert "No open decision points" in solution_design(Eng(ir=[_rec()]))


def test_a_read_only_system_is_shown_as_read_only():
    """Invariant 3 is a design fact, and the design document is where a reader checks it."""
    e = Eng(ir=[_rec()])
    e.registry.register(SystemRecord(system_id="SF-LEG", product="SuccessFactors",
                                     role="SOURCE_LEGACY", environment="PRD"))
    assert "read-only by construction" in solution_design(e)


def test_tier_c_is_declared_rather_than_hidden():
    doc = solution_design(Eng(ir=[_rec(tier="C")]))
    assert "Tier C" in doc and "ADR-0003" in doc


def test_tier_c_wording_is_absent_when_nothing_is_tier_c():
    assert "ADR-0003" not in solution_design(Eng(ir=[_rec(tier="A")]))


# --- decision register ------------------------------------------------------------------------------

def _dp(**over):
    base = dict(dp_id="DP-07", dp_type="STATUTORY", question="ZA annual leave accrual days?",
                owner="client HR", options=[])
    base.update(over)
    return DecisionPoint(**base)


def test_the_register_separates_open_from_resolved():
    resolved = _dp(dp_id="DP-01", dp_type="REVERSIBLE", question="Pay group naming?")
    resolved.resolution = {"by": "T. Mabaso", "value": "PG-ZA", "evidence": None,
                           "second_approver": None}
    doc = decision_register(Eng(dps=[_dp(), resolved]))
    assert "**1 open**, 1 resolved" in doc
    assert "## Open — planning is blocked" in doc and "## Resolved" in doc


def test_a_one_way_decision_shows_both_approvers():
    d = _dp(dp_id="DP-02", dp_type="ONE_WAY", question="Single global instance?")
    d.resolution = {"by": "T. Mabaso", "value": "yes", "evidence": None,
                    "second_approver": "R. Govender"}
    doc = decision_register(Eng(dps=[d]))
    assert "T. Mabaso + R. Govender" in doc


def test_a_statutory_decision_shows_its_evidence_reference():
    d = _dp()
    d.resolution = {"by": "client HR", "value": 21, "evidence": "BCEA s20(2), client letter 2026-07",
                    "second_approver": None}
    assert "BCEA s20(2)" in decision_register(Eng(dps=[d]))


def test_no_decisions_recorded_is_flagged_rather_than_congratulated():
    doc = decision_register(Eng())
    assert "the ledger cannot see them" in doc


# --- dispatch -----------------------------------------------------------------------------------------

def test_every_catalogued_document_renders():
    e = Eng(ir=[_rec()], dps=[_dp()])
    from jidoka_compiler.project import DOCUMENTS
    for name in DOCUMENTS:
        assert render(e, name).startswith("# ")


def test_an_unknown_document_is_refused_by_name():
    with pytest.raises(ProjectionError) as ex:
        render(Eng(), "blueprint")
    assert "blueprint" in str(ex.value)


def test_a_record_held_as_a_dict_projects_the_same_as_a_dataclass():
    """The repository rehydrates rows; the API holds IRRecords. Both are real."""
    rec = _rec()
    as_dict = {f: getattr(rec, f) for f in
               ("object", "product", "system_binding", "intent", "tier", "source", "country",
                "depends_on", "external_code")}
    assert config_rationale(Eng(ir=[as_dict])) == config_rationale(Eng(ir=[rec]))


# --- verification report ----------------------------------------------------------------------------

def test_the_test_plan_is_the_signed_intent_not_an_authored_expectation():
    from jidoka_compiler.project import verification_report
    doc = verification_report(Eng(ir=[_rec()]))
    assert "## What is checked" in doc
    assert "`externalCode`" in doc and "`name`" in doc
    assert "not authored by a tester" in doc


def test_an_undecided_field_is_not_asserted():
    from jidoka_compiler.project import verification_report
    rec = _rec(intent={"externalCode": "ZA01",
                       "accrualDays": {"decision_point": "DP-07", "value": None}})
    doc = verification_report(Eng(ir=[rec]))
    assert "`accrualDays`" not in doc


def test_a_never_verified_engagement_says_so_rather_than_showing_green():
    from jidoka_compiler.project import verification_report
    doc = verification_report(Eng(ir=[_rec()]))
    assert "No verification has been run" in doc


def test_ledger_verdicts_reach_the_report_and_unchecked_objects_are_named():
    from jidoka_compiler.project import verification_report
    e = Eng(ir=[_rec(), _rec(external_code="ZA02",
                             intent={"externalCode": "ZA02", "name": "Kruger BW"})])
    e.ledger.append("SuccessFactors:LegalEntity:ZA01", "VERIFIED", "verifier",
                    "live state matches signed intent")
    doc = verification_report(e)
    assert "match" in doc
    assert "Never verified" in doc and "`ZA02`" in doc


def test_open_drift_decisions_appear_with_their_owner():
    from jidoka_compiler.project import verification_report
    dp = _dp(dp_id="DP-DRIFT-SuccessFactors:LegalEntity:ZA01", dp_type="DESIGN",
             question="Live disagrees with signed intent on: name", owner="T. Mabaso")
    e = Eng(ir=[_rec()], dps=[dp])
    e.ledger.append("SuccessFactors:LegalEntity:ZA01", "DRIFT_DETECTED", "verifier",
                    "live values differ from signed intent on: name", status="DRIFT")
    doc = verification_report(e)
    assert "## Unexplained differences" in doc
    assert "DP-DRIFT-" in doc and "T. Mabaso" in doc
    assert "**DRIFT**" in doc

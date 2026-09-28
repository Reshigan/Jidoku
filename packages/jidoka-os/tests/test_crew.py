"""The crew, held to its rings.

These tests are the safety argument, not a feature check. Each one names what an agent must not
be able to do however it reasons, and asserts the reachable action set rather than the intent.
"""
import pytest
from jidoka_os import crew
from jidoka_os.capabilities import Cap, CapabilityError, MAX_CAPS, Ring
from jidoka_os.economy import MessageBus, auditor, operator
from jidoka_os.process import Supervisor
from jidoka_os.syscalls import Kernel


class Rec:
    def __init__(self, key="P:Obj:X", intent=None, source=None, tier="A", system="SYS-DEV"):
        self.key, self.tier, self.system_binding = key, tier, system
        self.object, self.product = "Obj", "P"
        self.intent = intent if intent is not None else {"externalCode": "X", "unit": "DAYS"}
        self.source = source if source is not None else {
            "workbook": "w.xlsx", "cell_range": "A2:F2", "signed_by": "lead@client",
            "date": "2026-01-01"}


class Ledger:
    """Enough ledger to be appended to and verified. The real one is core's."""
    def __init__(self, intact=True):
        self.entries, self._intact = [], intact

    def append(self, task, action, actor, detail="", **extra):
        self.entries.append({"task": task, "action": action, "actor": actor, "detail": detail, **extra})
        return self.entries[-1]

    def verify_chain(self):
        if not self._intact:
            raise AssertionError("chain broken")
        return True


class Registry:
    def assert_writable(self, system_id):
        return True


def kernel(ledger=None, **handlers):
    led = ledger or Ledger()
    k = Kernel(led, Registry(), Supervisor(led))
    base = {
        "sys_plan": lambda proc, **kw: {"steps": [
            {"seq": 1, "key": "P:Obj:X", "tier": "A", "system": "SYS-DEV", "product": "P",
             "action": "API_WRITE"},
            {"seq": 2, "key": "P:Doc:Y", "tier": "C", "system": "SYS-DEV", "product": "P",
             "action": "UI_INSTRUCTION_HUMAN"}], "lanes": [], "tier_summary": {}},
        "sys_extract": lambda proc, **kw: {"rows": 3},
        "sys_write_tier_a": lambda proc, **kw: {"key": kw.get("key"), "tier": "A",
                                                "system": "SYS-DEV", "status": "DRY_RUN",
                                                "detail": "rehearsed"},
        "sys_emit_artefact": lambda proc, **kw: {"kind": "instruction_sheet", "human_step": "do it"},
        "sys_raise_dp": lambda proc, **kw: {"dp_id": kw.get("dp_id")},
        "sys_ledger_append": lambda proc, **kw: led.append(kw.get("task", ""), kw.get("action", ""),
                                                           proc.manifest.name),
        "sys_halt": lambda proc, **kw: k.halt(kw.get("reason", ""), kw.get("by", "auditor")),
    }
    base.update(handlers)
    for name, fn in base.items():
        k.register(name, fn)
    return k


def run(k, records=None, dps=(), verify=None, twin=None):
    return crew.run(k, records=records if records is not None else [Rec()],
                    open_dp_ids=set(dps), actor="lead@gonxt",
                    bus=MessageBus(k.ledger), verify=verify, twin=twin)


# --- what the crew may never do ------------------------------------------------------------------

def test_no_agent_in_the_crew_can_approve_its_own_work():
    """Invariant 7, structurally: APPROVE exists in no ring an agent can occupy, so there is no
    manifest the crew could be given that would reach it."""
    for ring in (Ring.AGENT, Ring.SERVICE, Ring.UNTRUSTED):
        assert Cap.APPROVE not in MAX_CAPS[ring]
        assert Cap.RESOLVE_DP not in MAX_CAPS[ring]


def test_the_auditor_cannot_write_a_single_ledger_row():
    """The objections are real and the auditor cannot record one itself. That is the ring."""
    k = kernel()
    proc = k.supervisor.spawn(auditor(), "test")
    with pytest.raises(CapabilityError):
        k.dispatch(proc, "sys_ledger_append", task="t", action="NOTED")
    assert not any(e["action"] == "NOTED" for e in k.ledger.entries)


def test_the_operator_cannot_emit_an_artefact_and_the_architect_does_it():
    """Ring SERVICE holds no EMIT, so the division of labour is the capability table rather than
    a convention somebody has to remember."""
    k = kernel()
    proc = k.supervisor.spawn(operator(), "test")
    with pytest.raises(CapabilityError):
        k.dispatch(proc, "sys_emit_artefact", key="P:Doc:Y")
    report = run(k)
    assert [a["key"] for a in report["artefacts"]] == ["P:Doc:Y"]
    architect_card = next(c for c in report["crew"] if c["name"] == "architect")
    assert any("emitted" in d for d in architect_card["did"])


def test_an_unarmed_step_comes_back_rehearsed_and_asks_for_an_approver():
    """Invariant 6 from the crew's side: it has no way to arm, so an unarmed step cannot write."""
    report = run(kernel())
    assert [s["status"] for s in report["steps"]] == ["DRY_RUN"]
    assert any(w["who"] == "an approver" for w in report["waiting_on_a_person"])


def test_there_is_no_syscall_the_crew_could_arm_with():
    from jidoka_os.syscalls import SYSCALL_TABLE

    assert not any("arm" in name for name in SYSCALL_TABLE)


def test_a_written_step_waits_on_a_reviewer_who_did_not_build_it():
    """The crew can write now. It still cannot be the second person invariant 4 wants."""
    def wrote(proc, **kw):
        return {"key": kw.get("key"), "tier": "A", "system": "SYS-DEV", "status": "VERIFIED",
                "detail": "written and verified"}

    report = run(kernel(sys_write_tier_a=wrote))
    assert any(w["who"] == "a reviewer who did not build it" for w in report["waiting_on_a_person"])


def test_the_operator_carries_a_transport_hop_by_hop_until_production():
    hops = iter([
        {"in_production": False, "next_hop": "S4-PRD", "route": ["S4-DEV", "S4-QA", "S4-PRD"],
         "imported_into": ["S4-QA"]},
        {"in_production": True, "next_hop": None, "route": ["S4-DEV", "S4-QA", "S4-PRD"],
         "imported_into": ["S4-QA", "S4-PRD"]},
    ])
    report = run(kernel(
        sys_write_tier_a=lambda proc, **kw: {
            "key": kw.get("key"), "tier": "A", "system": "SYS-DEV", "status": "IN_TRANSPORT",
            "detail": "verified, not yet in production",
            "transport": {"route": ["S4-DEV", "S4-QA", "S4-PRD"], "next_hop": "S4-QA"}},
        sys_advance_transport=lambda proc, **kw: next(hops)))
    step = report["steps"][0]
    assert step["status"] == "VERIFIED" and step["transport"]["in_production"] is True


def test_a_refused_hop_stops_the_walk_and_says_who_owns_it():
    def refuse(proc, **kw):
        raise RuntimeError("next legal hop is S4-QA. Route order is not optional.")

    report = run(kernel(
        sys_write_tier_a=lambda proc, **kw: {
            "key": kw.get("key"), "tier": "A", "system": "SYS-DEV", "status": "IN_TRANSPORT",
            "detail": "verified, not yet in production",
            "transport": {"route": ["S4-DEV", "S4-QA", "S4-PRD"], "next_hop": "S4-QA"}},
        sys_advance_transport=refuse))
    step = report["steps"][0]
    assert step["status"] == "IN_TRANSPORT" and "Route order is not optional" in step["detail"]
    assert any(w["who"] == "whoever owns the transport route" for w in report["waiting_on_a_person"])


def test_a_substrate_that_never_says_stop_does_not_spin_forever():
    """Bounded by the route's own length: a loop trusting the substrate to end it would not end."""
    calls = {"n": 0}

    def never_lands(proc, **kw):
        calls["n"] += 1
        return {"in_production": False, "next_hop": "S4-QA", "route": ["S4-DEV", "S4-QA"],
                "imported_into": []}

    run(kernel(
        sys_write_tier_a=lambda proc, **kw: {
            "key": kw.get("key"), "tier": "A", "system": "SYS-DEV", "status": "IN_TRANSPORT",
            "detail": "", "transport": {"route": ["S4-DEV", "S4-QA"], "next_hop": "S4-QA"}},
        sys_advance_transport=never_lands))
    assert calls["n"] == 2


def test_a_refused_syscall_is_reported_not_raised_into_the_run():
    """A crew that fell over on the first gate would be useless — refusals are the product."""
    def refuse(proc, **kw):
        raise RuntimeError("no connector bound")

    report = run(kernel(sys_extract=refuse))
    assert report["steps"][0]["status"] == "REFUSED"
    assert "no connector bound" in report["steps"][0]["detail"]


# --- the statutory sentinel -----------------------------------------------------------------------

def test_a_statutory_looking_value_with_no_evidence_is_asked_about():
    rec = Rec(intent={"externalCode": "X", "accrual_frequency": "MONTHLY"})
    report = run(kernel(), records=[rec])
    assert report["decisions_raised"] == ["DP-STAT-P:OBJ:X-ACCRUAL_FREQUENCY"]
    assert any(w["who"] == "lead@client" for w in report["waiting_on_a_person"])


def test_a_statutory_value_carrying_evidence_is_left_alone():
    rec = Rec(intent={"externalCode": "X", "accrual_frequency": "MONTHLY"},
              source={"workbook": "w.xlsx", "cell_range": "A2", "signed_by": "lead@client",
                      "date": "2026-01-01", "evidence": "BCEA s20 — client legal memo"})
    assert run(kernel(), records=[rec])["decisions_raised"] == []


def test_a_question_a_person_already_answered_is_never_asked_again():
    """A second run that wiped a human's decision would be worse than no run at all."""
    rec = Rec(intent={"externalCode": "X", "accrual_frequency": "MONTHLY"})
    report = run(kernel(), records=[rec], dps={"DP-STAT-P:OBJ:X-ACCRUAL_FREQUENCY"})
    assert report["decisions_raised"] == []
    card = next(c for c in report["crew"] if c["name"] == "statutory-sentinel")
    assert any("already exists" in d for d in card["did"])


# --- the auditor ----------------------------------------------------------------------------------

def test_the_auditor_objects_to_a_rehearsal_with_no_snapshot():
    """The extract handler here writes no SNAPSHOT row, so the objection is true."""
    findings = {o["body"]["finding"] for o in run(kernel())["objections"]}
    assert "rehearsed without a snapshot" in findings
    assert "never verified" in findings


def test_a_record_the_platform_looked_at_and_found_unbuilt_is_not_unexamined():
    """"Never verified" must mean nobody looked, not that the answer was "not built yet"."""
    led = Ledger()
    led.append("P:Obj:X", "NOT_APPLIED", "lead@gonxt", "absent; never written")
    findings = {o["body"]["finding"] for o in run(kernel(ledger=led))["objections"]}
    assert "never verified" not in findings


def test_the_auditor_reads_the_chain_as_it_stands_not_as_it_stood():
    """It objected to every step as rehearsed-without-a-snapshot while the operator's snapshots
    sat on the same chain, two rows above. An auditor handed stale evidence audits nothing."""
    led = Ledger()

    def extract(proc, key="", **kw):
        led.append(key, "SNAPSHOT", "operator", "3 rows read")
        return {"rows": 3}

    findings = {o["body"]["finding"] for o in run(kernel(ledger=led, sys_extract=extract))["objections"]}
    assert "rehearsed without a snapshot" not in findings


def test_a_broken_chain_halts_the_line_from_a_ring_that_cannot_write():
    """The auditor's one real power. It cannot record the finding — so it stops everything."""
    k = kernel(ledger=Ledger(intact=False))
    report = run(k)
    assert report["halted"] is True
    assert "does not verify" in report["halt_reason"]
    assert any(w["what"] == "the line" for w in report["waiting_on_a_person"])


# --- budgets and the report -----------------------------------------------------------------------

def test_a_budget_kill_is_reported_rather_than_degrading_silently():
    records = [Rec(key=f"P:Obj:{i}", intent={"externalCode": str(i), "tax_rate": "15"})
               for i in range(40)]
    k = kernel()
    original = crew.sentinel

    def tiny():
        m = original()
        m.syscall_budget = 3
        return m

    crew.sentinel = tiny
    try:
        report = run(k, records=records)
    finally:
        crew.sentinel = original
    card = next(c for c in report["crew"] if c["name"] == "statutory-sentinel")
    assert card["state"] == "KILLED" and "budget" in card["exit_reason"]
    assert len(report["decisions_raised"]) < len(records)


def test_the_report_names_every_agents_authority_beside_its_work():
    report = run(kernel())
    names = {c["name"] for c in report["crew"]}
    assert names == {"statutory-sentinel", "architect", "operator", "auditor", "economist"}
    for card in report["crew"]:
        assert card["ring"] in ("AGENT", "SERVICE", "UNTRUSTED")
        assert card["objective"] and isinstance(card["capabilities"], list)


def test_the_economist_prices_what_it_counted_and_names_what_it_did_not():
    report = run(kernel())
    assert report["economics"]["steps"] == {"A": 1, "B": 0, "C": 1}
    assert report["economics"]["manual_steps"] == 1
    assert "cost of delay" in report["economics"]["not_priced"]


def test_verification_runs_last_and_is_the_platforms_act_not_an_agents():
    seen = {}

    def verify():
        seen["ran"] = True
        return {"verified": ["P:Obj:X"], "drift": [], "skipped": [], "not_applied": [],
                "planning_blocked": False}

    report = run(kernel(), verify=verify)
    assert seen["ran"] and report["verification"]["verified"] == ["P:Obj:X"]
    # no agent holds a capability for it: there is no verification syscall at all
    from jidoka_os.syscalls import SYSCALL_TABLE
    assert not any("verif" in name for name in SYSCALL_TABLE)


# --- the auditor on evidence it cannot check (ADR-0022) -------------------------------------------

def test_an_attested_record_draws_a_sharper_objection_than_never_verified():
    """A person's word is evidence about a person. Naming that is what ring 3 is for."""
    led = Ledger()
    led.append("P:Obj:X", "ATTESTED", "t.mabaso", "changed it in Provisioning")
    findings = {o["body"]["finding"] for o in run(kernel(ledger=led))["objections"]}
    assert "rests on an attestation, not a check" in findings
    assert "never verified" not in findings


def test_an_unconfirmable_record_with_no_attestation_is_called_unevidenced():
    led = Ledger()
    led.append("P:Obj:X", "UNCONFIRMABLE", "lead@gonxt", "no read path")
    findings = {o["body"]["finding"] for o in run(kernel(ledger=led))["objections"]}
    assert "cannot be checked, and nobody has attested" in findings


def test_outstanding_human_work_is_not_called_unexamined():
    led = Ledger()
    led.append("P:Obj:X", "AWAITING_A_PERSON", "lead@gonxt", "handed over, not done")
    findings = {o["body"]["finding"] for o in run(kernel(ledger=led))["objections"]}
    assert "never verified" not in findings


def test_the_latest_verdict_wins_over_an_earlier_one():
    """Unreadable yesterday, attested today: the objection has to follow the record."""
    led = Ledger()
    led.append("P:Obj:X", "UNCONFIRMABLE", "lead@gonxt", "no read path")
    led.append("P:Obj:X", "ATTESTED", "t.mabaso", "changed it in Provisioning")
    findings = {o["body"]["finding"] for o in run(kernel(ledger=led))["objections"]}
    assert "rests on an attestation, not a check" in findings
    assert "cannot be checked, and nobody has attested" not in findings


# --- a crew that writes has to be able to undo (ADR-0024) -----------------------------------------

def _partial(proc, **kw):
    return {"key": kw.get("key"), "tier": "A", "system": "SYS-DEV", "status": "PARTIAL",
            "detail": "2 of 5 operations failed"}


def test_a_half_landed_batch_is_put_back_rather_than_left():
    undone = []
    report = run(kernel(sys_write_tier_a=_partial,
                        sys_rollback=lambda proc, **kw: undone.append(kw.get("key")) or
                        {"key": kw.get("key"), "status": "ROLLED_BACK", "rows": 3}))
    assert undone == ["P:Obj:X"]
    assert report["steps"][0]["status"] == "ROLLED_BACK"
    assert "put back the state its own snapshot recorded" in report["steps"][0]["detail"]


def test_a_refused_rollback_after_a_half_landed_write_is_said_loudly():
    """The worst state this platform can reach. It cannot fix it; it can refuse to be quiet."""
    def refuse(proc, **kw):
        raise RuntimeError("KOM-SF-DEV is not armed.")

    report = run(kernel(sys_write_tier_a=_partial, sys_rollback=refuse))
    assert report["steps"][0]["status"] == "PARTIAL"
    assert "The rollback was refused" in report["steps"][0]["detail"]
    item = next(w for w in report["waiting_on_a_person"] if w["who"] == "an operator, now")
    assert "state nobody designed" in item["why"]


def test_undoing_costs_the_same_capability_as_writing():
    """Ring 3 cannot undo any more than it can write: the direction is irrelevant."""
    from jidoka_os.capabilities import Cap
    from jidoka_os.syscalls import SYSCALL_TABLE

    assert SYSCALL_TABLE["sys_rollback"] == Cap.WRITE_TARGET
    k = kernel()
    proc = k.supervisor.spawn(auditor(), "test")
    with pytest.raises(CapabilityError):
        k.dispatch(proc, "sys_rollback", key="P:Obj:X")


def test_a_clean_write_is_never_rolled_back():
    called = []
    run(kernel(sys_rollback=lambda proc, **kw: called.append(1)))
    assert called == []


# --- the twin predicts, and the crew does not act on it (ADR-0026) --------------------------------

def _twin(verdict="REJECT", status="UNCALIBRATED", scored=2, rate=None):
    return lambda: {"predictions": [{"key": "P:Obj:X", "verdict": verdict,
                                     "reasons": ["R-107: accrual_frequency must be set"]}],
                    "fidelity": {"status": status, "scored": scored, "min_scored": 10,
                                 "fidelity": rate}}


def test_a_predicted_rejection_does_not_stop_the_write():
    report = run(kernel(), twin=_twin())
    assert [s["status"] for s in report["steps"]] == ["DRY_RUN"], "the step still ran"
    assert report["twin"]["predictions"][0]["verdict"] == "REJECT"


def test_a_predicted_rejection_reaches_the_handover_with_its_reasons():
    item = next(w for w in run(kernel(), twin=_twin())["waiting_on_a_person"]
                if w["what"] == "P:Obj:X" and "twin predicts" in w["why"])
    assert "accrual_frequency must be set" in item["why"]


def test_an_uncalibrated_twin_says_it_has_earned_no_weight():
    item = next(w for w in run(kernel(), twin=_twin())["waiting_on_a_person"]
                if "twin predicts" in w["why"])
    assert "uncalibrated (2 of 10 scored predictions)" in item["why"]
    assert "earned no weight" in item["why"]


def test_a_calibrated_twin_carries_its_rate_beside_the_prediction():
    item = next(w for w in run(kernel(), twin=_twin(status="CALIBRATED", scored=40, rate=0.9))
                ["waiting_on_a_person"] if "twin predicts" in w["why"])
    assert "matched the system on 90% of 40 scored predictions" in item["why"]


def test_a_predicted_acceptance_says_nothing():
    report = run(kernel(), twin=_twin(verdict="ACCEPT"))
    assert not any("twin predicts" in w["why"] for w in report["waiting_on_a_person"])


def test_a_run_without_a_twin_is_unchanged():
    assert run(kernel())["twin"] is None


# --- module agents: one process per module the design declares (ADR-0035) ----------------------

def _contracted(owner, consumers=(), depends=(), code="c4", object_="CustomString"):
    """A real IRRecord, through the real loader: a stub with a contract attribute would prove the
    crew reads an attribute, not that a contract survives validation."""
    from jidoka_core.ir import validate_record

    return validate_record(_raw(owner, consumers, depends, code, object_))[0]


def _raw(owner, consumers, depends, code, object_):
    return {"object": object_, "product": "SuccessFactors", "system_binding": "SYS",
            "intent": {"externalCode": code}, "tier": "A", "external_code": code,
            "depends_on": list(depends),
            "source": {"workbook": "w.xlsx", "signed_by": "T. Mabaso", "date": "2026-09-01"},
            "contract": {"owner": owner, "consumers": list(consumers)}}


def test_there_is_one_module_agent_per_module_the_design_declares():
    """Not a hardcoded list: a second statement of which modules exist would be stale the day a
    programme added one, and the alignment argument rests on there being one graph."""
    out = run(kernel(), records=[_contracted("EC"),
                                 _contracted("Time Off", code="ta1",
                                             object_="TimeAccountType")])
    names = {c["name"] for c in out["crew"]}
    assert "module:EC" in names and "module:Time Off" in names


def test_a_module_agent_objects_only_about_its_own_objects():
    """A module agent that spoke for the programme would agree with everybody, which is exactly
    how cross-module collisions survive."""
    out = run(kernel(), records=[_contracted("EC"),
                                 _contracted("Time Off", code="ta1",
                                             object_="TimeAccountType",
                                             depends=["CustomString:c4"])])
    ec = next(c for c in out["crew"] if c["name"] == "module:EC")
    to = next(c for c in out["crew"] if c["name"] == "module:Time Off")
    assert any("objected" in d for d in ec["did"]), "EC owns the object being read"
    assert all("objected" not in d for d in to["did"]), "Time Off owns nothing being read"


def test_a_module_agent_is_ring_two_and_can_never_approve():
    out = run(kernel(), records=[_contracted("EC")])
    ec = next(c for c in out["crew"] if c["name"] == "module:EC")
    assert ec["ring"] == "AGENT"
    assert "approve" not in ec["capabilities"] and "resolve_dp" not in ec["capabilities"]


def test_an_engagement_with_no_contracts_spawns_no_module_agents():
    """Standard configuration needs no contract, and a module agent for a module nobody declared
    would be the platform inventing an org chart."""
    out = run(kernel())
    assert not any(c["name"].startswith("module:") for c in out["crew"])

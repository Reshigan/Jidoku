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


def run(k, records=None, dps=(), verify=None):
    return crew.run(k, records=records if records is not None else [Rec()],
                    open_dp_ids=set(dps), actor="lead@gonxt",
                    bus=MessageBus(k.ledger), verify=verify)


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


def test_every_tier_a_step_comes_back_rehearsed_never_written():
    """Invariant 6 from the crew's side: it has no way to arm, so a run cannot write."""
    report = run(kernel())
    assert [s["status"] for s in report["steps"]] == ["DRY_RUN"]
    assert any(w["who"] == "an approver" for w in report["waiting_on_a_person"])


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

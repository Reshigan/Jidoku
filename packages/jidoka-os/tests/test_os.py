"""Agent OS tests. Each proves a structural guarantee — not that the agent behaves, but that it cannot misbehave."""
import unittest
from jidoka_core.ledger import Ledger
from jidoka_core.registry import SystemRegistry, SystemRecord, WriteLockViolation
from jidoka_os.capabilities import Ring, Cap, CapabilitySet, CapabilityError, MAX_CAPS
from jidoka_os.process import Manifest, Supervisor, BudgetExceeded, State
from jidoka_os.syscalls import Kernel, HaltedError, SyscallError, SYSCALL_TABLE
from jidoka_os.scheduler import Scheduler, Shift
from jidoka_os import economy


def boot():
    led = Ledger()
    reg = SystemRegistry()
    reg.register(SystemRecord("KOM-SF-DEV", "SuccessFactors", "DEV", "DEV",
                              connectivity={"write_credentials": "vault:dev"}))
    reg.register(SystemRecord("KOM-ECC-PRD", "ECC", "SOURCE_LEGACY", "PROD"))
    sup = Supervisor(led)
    k = Kernel(led, reg, sup)
    for call in SYSCALL_TABLE:
        k.register(call, lambda proc, _c=call, **kw: {"ok": _c})
    return led, reg, sup, k


class TestPrivilegeRings(unittest.TestCase):
    def test_no_agent_ring_can_hold_approval(self):
        for ring in (Ring.AGENT, Ring.SERVICE, Ring.UNTRUSTED):
            self.assertNotIn(Cap.APPROVE, MAX_CAPS[ring])

    def test_manifest_cannot_exceed_ring_ceiling(self):
        with self.assertRaises(CapabilityError):
            CapabilitySet(Ring.AGENT, {Cap.APPROVE})
        with self.assertRaises(CapabilityError):
            CapabilitySet(Ring.UNTRUSTED, {Cap.WRITE_TARGET})

    def test_capabilities_cannot_be_acquired_at_runtime(self):
        cs = CapabilitySet(Ring.AGENT, {Cap.PLAN})
        with self.assertRaises(CapabilityError):
            cs.grant(Cap.WRITE_TARGET)
        self.assertFalse(cs.drop(Cap.PLAN).has(Cap.PLAN))   # dropping is allowed

    def test_nothing_spawns_into_ring_zero(self):
        _, _, sup, _ = boot()
        with self.assertRaises(CapabilityError):
            sup.spawn(Manifest("rogue", Ring.KERNEL, set()))


class TestSyscallBoundary(unittest.TestCase):
    def test_agent_cannot_call_approve_even_with_a_handler_present(self):
        _, _, sup, k = boot()
        p = sup.spawn(economy.architect())
        with self.assertRaises(CapabilityError):
            k.dispatch(p, "sys_ledger_approve")

    def test_untrusted_red_team_cannot_write_or_emit(self):
        _, _, sup, k = boot()
        p = sup.spawn(economy.auditor())
        for call in ("sys_write_tier_a", "sys_emit_artefact", "sys_plan"):
            with self.assertRaises(CapabilityError):
                k.dispatch(p, call, system_id="KOM-SF-DEV")
        self.assertEqual(k.dispatch(p, "sys_extract")["ok"], "sys_extract")

    def test_write_to_source_system_refused_at_kernel(self):
        _, _, sup, k = boot()
        p = sup.spawn(economy.operator())
        with self.assertRaises(WriteLockViolation):
            k.dispatch(p, "sys_write_tier_a", system_id="KOM-ECC-PRD")

    def test_denied_syscall_is_recorded_as_evidence(self):
        led, _, sup, k = boot()
        p = sup.spawn(economy.architect())
        try:
            k.dispatch(p, "sys_ledger_approve")
        except CapabilityError:
            pass
        self.assertTrue(any(e["action"] == "SYSCALL_DENIED" for e in led.entries))
        led.verify_chain()

    def test_unassigned_syscall_cannot_be_registered(self):
        _, _, _, k = boot()
        with self.assertRaises(SyscallError):
            k.register("sys_do_anything", lambda **kw: None)


class TestHalt(unittest.TestCase):
    def test_halt_stops_everything_except_reading_and_halting(self):
        _, _, sup, k = boot()
        p = sup.spawn(economy.architect())
        k.halt("accrual rule looks wrong on mid-year hires", by="s.lavu")
        with self.assertRaises(HaltedError):
            k.dispatch(p, "sys_plan")
        self.assertTrue(k.dispatch(p, "sys_extract"))       # reading stays available
        self.assertTrue(k.dispatch(p, "sys_halt"))          # anyone can still stop

    def test_halt_requires_a_reason_and_a_second_person_to_clear(self):
        _, _, _, k = boot()
        with self.assertRaises(SyscallError):
            k.halt("   ", by="anyone")
        k.halt("bank details look wrong", by="n.devatala")
        with self.assertRaises(SyscallError):
            k.resume(by="n.devatala", reviewer="n.devatala")
        k.resume(by="n.devatala", reviewer="l.chadhliwa")
        self.assertFalse(k.halted)


class TestBudgets(unittest.TestCase):
    def test_token_budget_kills_rather_than_degrades(self):
        _, _, sup, k = boot()
        m = economy.architect(); m.token_budget = 50
        p = sup.spawn(m)
        k.dispatch(p, "sys_extract", tokens=40)
        with self.assertRaises(BudgetExceeded):
            k.dispatch(p, "sys_extract", tokens=40)
        self.assertEqual(p.state, State.KILLED)

    def test_killed_process_cannot_issue_syscalls(self):
        _, _, sup, k = boot()
        p = sup.spawn(economy.architect())
        sup.kill(p.pid, "operator stopped it")
        with self.assertRaises(SyscallError):
            k.dispatch(p, "sys_extract")

    def test_restart_never_widens_privilege(self):
        _, _, sup, k = boot()
        p = sup.spawn(economy.auditor())
        p.manifest.caps.add(Cap.WRITE_TARGET)      # tamper with the manifest
        q = sup.restart(p.pid)
        self.assertFalse(q.capabilities.has(Cap.WRITE_TARGET))


class TestScheduler(unittest.TestCase):
    def test_night_work_runs_on_night_shift_only(self):
        s = Scheduler()
        s.submit("extract+diff", 5, Shift.NIGHT)
        s.submit("steering brief", 4, Shift.DAY)
        self.assertEqual([t.name for t in s.run(Shift.NIGHT)], ["extract+diff"])

    def test_cost_of_silence_orders_the_queue(self):
        s = Scheduler()
        s.submit("picklist tidy-up", 1, Shift.DAY)
        s.submit("statutory block found", 9, Shift.DAY)
        s.submit("approver over capacity", 5, Shift.DAY)
        self.assertEqual([t.name for t in s.run(Shift.DAY)][0], "statutory block found")

    def test_interruption_budget_defers_the_rest_to_handover(self):
        s = Scheduler(interruption_budget=2)
        for i, c in enumerate([9, 8, 7, 6]):
            s.submit(f"finding-{i}", c, Shift.DAY, interrupts_human=True)
        ran = s.run(Shift.DAY)
        self.assertEqual(len(ran), 2)
        self.assertEqual(s.handover()["deferred"], ["finding-2", "finding-3"])


class TestEconomy(unittest.TestCase):
    def test_opposed_objectives_with_asymmetric_authority(self):
        self.assertNotEqual(economy.architect().objective, economy.auditor().objective)
        self.assertEqual(economy.auditor().ring, Ring.UNTRUSTED)     # rewarded for breaking, trusted with nothing
        self.assertEqual(economy.operator().ring, Ring.SERVICE)
        self.assertIn(Cap.RAISE_DP, economy.sentinel().caps)
        self.assertNotIn(Cap.WRITE_TARGET, economy.sentinel().caps)

    def test_messages_are_logged_not_shared_memory(self):
        led, _, _, _ = boot()
        bus = economy.MessageBus(led)
        bus.send(economy.Message("auditor", "architect", "OBJECTION",
                                 {"claim": "no evidence for MOZ accrual basis"}))
        self.assertEqual(len(bus.objections()), 1)
        self.assertTrue(any(e["action"] == "MESSAGE" for e in led.entries))


if __name__ == "__main__":
    unittest.main(verbosity=2)

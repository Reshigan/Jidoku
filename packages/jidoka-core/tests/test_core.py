import json, unittest, copy
from jidoka_core.ir import load_ir, IRValidationError, validate_record
from jidoka_core.planner import plan, PlanError
from jidoka_core.registry import SystemRegistry, SystemRecord, WriteLockViolation
from jidoka_core.ledger import Ledger, SoDViolation, LedgerTampered
from jidoka_core.decisions import DecisionEngine, DecisionPoint, DecisionError
from jidoka_core.twin import SchemaTwin
from jidoka_adapters.successfactors import SFAdapter

import pathlib
FIX = pathlib.Path(__file__).parent / "fixtures"
IR = json.load(open(FIX / "komatsu_sample_ir.json"))
META = json.load(open(FIX / "metadata_sample.json"))

class TestIR(unittest.TestCase):
    def test_unsigned_source_refused(self):
        bad = copy.deepcopy(IR[0]); bad["source"]["signed_by"] = ""
        with self.assertRaises(IRValidationError): validate_record(bad)

    def test_open_dp_detected_and_blocks_plan(self):
        rec = copy.deepcopy(IR[1])
        rec["intent"]["negative_floor"] = {"value": None, "decision_point": "DP-B11"}
        records, dps = load_ir([copy.deepcopy(IR[0]), rec])
        self.assertTrue(dps)
        with self.assertRaises(PlanError): plan(records, dps)

class TestPlanner(unittest.TestCase):
    def test_topo_order_respects_dependency(self):
        records, dps = load_ir(IR)
        p = plan(records, dps)
        keys = [s["key"] for s in p["steps"]]
        self.assertLess(keys.index("SuccessFactors:TimeAccountType:ANN_ACC_ZAF"),
                        keys.index("SuccessFactors:TimeType:ANN_LEAVE_ZAF"))
        self.assertEqual(p["tier_summary"]["C"], 1)

    def test_cycle_detected(self):
        a, b = copy.deepcopy(IR[0]), copy.deepcopy(IR[1])
        a["depends_on"] = ["TimeType:ANN_LEAVE_ZAF"]
        records, dps = load_ir([a, b])
        with self.assertRaises(PlanError): plan(records, dps)

class TestRegistry(unittest.TestCase):
    def test_source_write_lock(self):
        reg = SystemRegistry()
        with self.assertRaises(WriteLockViolation):
            reg.register(SystemRecord("KOM-ECC-PRD","ECC","SOURCE_LEGACY","PROD",
                                      connectivity={"write_credentials":"vault:x"}))
        reg.register(SystemRecord("KOM-ECC-PRD","ECC","SOURCE_LEGACY","PROD"))
        with self.assertRaises(WriteLockViolation): reg.assert_writable("KOM-ECC-PRD")

class TestLedger(unittest.TestCase):
    def test_sod_and_snapshot_gate(self):
        led = Ledger()
        led.append("T1","SNAPSHOT","jidoka","ref EXP-1")
        led.append("T1","EXECUTED","alice")
        with self.assertRaises(SoDViolation): led.approve("T1","alice")
        led.approve("T1","bob")
        led2 = Ledger(); led2.append("T2","EXECUTED","alice")
        with self.assertRaises(SoDViolation): led2.approve("T2","bob")  # no snapshot -> refuse

    def test_tamper_evidence(self):
        led = Ledger()
        led.append("T1","SNAPSHOT","jidoka","ref"); led.append("T1","EXECUTED","alice")
        self.assertTrue(led.verify_chain())
        led.entries[0]["detail"] = "jidokad"
        with self.assertRaises(LedgerTampered): led.verify_chain()

class TestDecisions(unittest.TestCase):
    def test_statutory_needs_evidence_oneway_needs_two(self):
        eng = DecisionEngine(Ledger())
        eng.raise_dp(DecisionPoint("DP-B11","STATUTORY","ZA negative leave floor","Komatsu HR"))
        with self.assertRaises(DecisionError): eng.resolve("DP-B11","komatsu.hr",-5, evidence_ref="")
        eng.resolve("DP-B11","komatsu.hr",-5, evidence_ref="Signed policy KOM-POL-114")
        eng.raise_dp(DecisionPoint("DP-B06","ONE_WAY","Person-ID strategy","Komatsu IT"))
        with self.assertRaises(DecisionError): eng.resolve("DP-B06","it.lead","PERNR","doc", second_approver="it.lead")
        eng.resolve("DP-B06","it.lead","PERNR","doc", second_approver="hr.lead")

class TestTwinAndAdapter(unittest.TestCase):
    def test_twin_catches_orphan_and_unknown_field(self):
        twin = SchemaTwin(META)
        errs = twin.validate_payload("TimeType",
            {"externalCode":"X","unit":"DAYS","accrual_frequency":"HOURLY","bogus":"1","timeAccountType":"A"},
            picklists={"FREQ":{"MONTHLY"}})
        self.assertTrue(any("picklist" in e for e in errs))
        self.assertTrue(any("bogus" in e for e in errs))

    def test_diff_and_verify(self):
        before=[{"externalCode":"A","unit":"DAYS"}]; after=[{"externalCode":"A","unit":"HOURS"},{"externalCode":"B"}]
        d = SFAdapter.diff(before, after)
        self.assertEqual(d["added"],["B"]); self.assertIn("A", d["changed"]); self.assertFalse(d["clean"])
        records,_ = load_ir(IR)
        v = SFAdapter().verify(records[0], [{"externalCode":"ANN_ACC_ZAF","unit":"DAYS","country":"ZAF"}])
        self.assertEqual(v["status"],"MATCH")

    def test_tier_c_yields_instruction_sheet(self):
        records,_ = load_ir(IR)
        c = next(r for r in records if r.tier=="C")
        art = SFAdapter().build_apply(c)
        self.assertEqual(art["kind"],"instruction_sheet")
        self.assertIn("before-state", art["steps"][0])

if __name__ == "__main__":
    unittest.main(verbosity=2)

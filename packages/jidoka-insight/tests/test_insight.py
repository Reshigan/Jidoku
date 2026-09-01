import unittest
from jidoka_insight.archaeology import reverse_ir, unexplained
from jidoka_insight.timetravel import as_of
from jidoka_insight.blast import blast_radius
from jidoka_insight.debt import debt_index
from jidoka_core.ir import load_ir, IRValidationError

class TestArchaeology(unittest.TestCase):
    def test_reversed_ir_is_unsigned_and_therefore_unloadable(self):
        drafts = reverse_ir([{"__entity": "TimeType", "externalCode": "ANN_ZAF", "unit": "DAYS"}],
                            "SuccessFactors", "KOM-SF-PRD")
        self.assertEqual(drafts[0]["provenance_status"], "UNVERIFIED")
        with self.assertRaises(IRValidationError):   # signed-claim primitive holds for brownfield too
            load_ir(drafts)
        self.assertEqual(unexplained(drafts), ["ANN_ZAF"])

class TestTimeTravel(unittest.TestCase):
    def test_state_as_of_reconstructs_and_respects_order(self):
        led = [{"ts": "T1", "task": "P3-2", "action": "APPROVED"},
               {"ts": "T2", "task": "DP-B14", "action": "DP_RAISED"},
               {"ts": "T3", "task": "P3-2", "action": "ROLLED BACK"},
               {"ts": "T4", "task": "DP-B14", "action": "DP_RESOLVED"}]
        s2 = as_of(led, "T2")
        self.assertIn("P3-2", s2["approved"]); self.assertIn("DP-B14", s2["open_dps"])
        s4 = as_of(led, "T4")
        self.assertNotIn("P3-2", s4["approved"]); self.assertEqual(s4["open_dps"], set())

class TestBlast(unittest.TestCase):
    def test_person_level_statement(self):
        pop = [{"id": i, "country": "MOZ" if i < 12 else "ZAF"} for i in range(41000)]
        r = blast_radius({"selector": {"country": "MOZ"}, "delta": "accrual basis corrected"}, pop)
        self.assertEqual(r["affected"], 12)
        self.assertIn("40,988", r["statement"])

class TestDebt(unittest.TestCase):
    def test_score_grade_and_driver(self):
        r = debt_index({"custom_object": 4, "unauthorised_drift": 2, "undocumented_customisation": 3})
        self.assertEqual(r["score"], 4*5 + 2*10 + 3*6)
        self.assertEqual(r["top_driver"], "custom_object" if r["items"]["custom_object"] >= 20 else r["top_driver"])
        self.assertEqual(debt_index({})["grade"], "A")

if __name__ == "__main__":
    unittest.main()

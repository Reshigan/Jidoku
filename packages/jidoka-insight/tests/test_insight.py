import unittest
from jidoka_insight.archaeology import reverse_ir, unexplained
from jidoka_insight.timetravel import as_of
from jidoka_insight.blast import blast_radius
from jidoka_insight.debt import WEIGHTS, debt_index, measure
from jidoka_core.executor import Executor
from jidoka_core.ir import IRRecord, load_ir, IRValidationError
from jidoka_core.decisions import DecisionPoint
from jidoka_core.ledger import Ledger
from jidoka_core.registry import SystemRecord, SystemRegistry

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
               {"ts": "T3", "task": "P3-2", "action": "ROLLED_BACK"},
               {"ts": "T4", "task": "DP-B14", "action": "DP_RESOLVED"}]
        s2 = as_of(led, "T2")
        self.assertIn("P3-2", s2["approved"]); self.assertIn("DP-B14", s2["open_dps"])
        s4 = as_of(led, "T4")
        self.assertNotIn("P3-2", s4["approved"]); self.assertEqual(s4["open_dps"], set())

    def test_rollback_written_by_the_kernel_is_seen_by_time_travel(self):
        """Regression: the action name came from a literal here and did not match the one the
        executor writes, so every real rollback was invisible. The ledger is the fixture now."""
        registry = SystemRegistry()
        registry.register(SystemRecord("S4-DEV", "S4HANA", "DEV", "dev",
                                       connectivity={"write_credentials": True}))
        ledger = Ledger()
        record = IRRecord(object="A_CostCenter", product="S4HANA", system_binding="S4-DEV",
                          intent={"CostCenter": "CC-1000"}, tier="A",
                          source={"workbook": "WB-1", "signed_by": "lead@client",
                                  "date": "2026-09-01"})
        ledger.append(record.key, "APPROVED", "approver@client")
        Executor(registry, ledger, "builder@gonxt").rollback(
            record.key, [{"CostCenter": "CC-1000"}], lambda payload: {}, record, "drift")
        state = as_of(ledger.entries, ledger.entries[-1]["ts"])
        self.assertIn(record.key, state["rolled_back"])
        self.assertNotIn(record.key, state["approved"])


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


class TestDerivedDebt(unittest.TestCase):
    """A weight with no measurement behind it must not move the score."""

    def _draft(self, code, rationale=None):
        return {"external_code": code, "rationale": rationale}

    def test_the_score_counts_only_what_was_observed(self):
        m = measure([self._draft("A"), self._draft("B", "kept for ZA payroll")], [])
        self.assertEqual(m["counts"]["undocumented_customisation"], 1)
        self.assertEqual(m["score"], WEIGHTS["undocumented_customisation"])
        self.assertIn("custom_object", m["unmeasured"])
        self.assertEqual(m["items"]["custom_object"], 0)

    def test_open_drift_decisions_are_counted_and_resolved_ones_are_not(self):
        open_dp = DecisionPoint("DP-DRIFT-x", "DESIGN", "?", "lead")
        closed = DecisionPoint("DP-DRIFT-y", "DESIGN", "?", "lead")
        closed.resolution = {"by": "lead", "value": "reassert"}
        other = DecisionPoint("DP-B14", "STATUTORY", "?", "client")
        m = measure([], [open_dp, closed, other])
        self.assertEqual(m["counts"]["unauthorised_drift"], 1)
        self.assertEqual(m["score"], WEIGHTS["unauthorised_drift"])

    def test_the_published_weights_travel_with_the_score(self):
        """A consumer must never have to derive a weight from a contribution over a zero count."""
        m = measure([], [])
        self.assertEqual(m["weights"], WEIGHTS)
        self.assertTrue(all(w > 0 for w in m["weights"].values()))

    def test_a_measured_counter_is_never_reported_as_unmeasured(self):
        m = measure([], [])
        self.assertEqual(set(m["counts"]) & set(m["unmeasured"]), set())
        self.assertEqual(set(m["counts"]), set(m["measured"]))

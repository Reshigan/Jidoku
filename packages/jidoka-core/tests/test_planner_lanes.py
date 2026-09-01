import unittest
from jidoka_core.ir import load_ir
from jidoka_core.planner import plan

def rec(code: str, deps: list[str], tier: str = "A") -> dict:
    return {"object": "TimeType", "product": "SuccessFactors", "system_binding": "KOM-SF-DEV",
            "tier": tier, "external_code": code, "intent": {"externalCode": code},
            "depends_on": deps,
            "source": {"workbook": "W v1", "signed_by": "Komatsu HR ZA", "date": "2026-08-20"}}

K = "SuccessFactors:TimeType:{}".format

class TestLanes(unittest.TestCase):
    def _lanes(self, raws):
        records, dps = load_ir(raws)
        p = plan(records, dps)
        self.assertEqual(sorted(sum(p["lanes"], [])), sorted(s["key"] for s in p["steps"]))
        return [sorted(l) for l in p["lanes"]]

    def test_diamond(self):
        # A -> B, A -> C, both -> D: D sits one lane past the deepest parent, not beside B/C.
        lanes = self._lanes([rec("A", []), rec("B", ["TimeType:A"]), rec("C", ["TimeType:A"]),
                             rec("D", ["TimeType:B", "TimeType:C"])])
        self.assertEqual(lanes, [[K("A")], [K("B"), K("C")], [K("D")]])

    def test_disconnected_subgraphs_share_lane_zero(self):
        lanes = self._lanes([rec("A", []), rec("B", ["TimeType:A"]),
                             rec("X", []), rec("Y", ["TimeType:X"])])
        self.assertEqual(lanes, [[K("A"), K("X")], [K("B"), K("Y")]])

    def test_longest_path_wins_over_shortcut(self):
        # A->B->C plus a direct A->C edge: C must still land in lane 2.
        lanes = self._lanes([rec("A", []), rec("B", ["TimeType:A"]),
                             rec("C", ["TimeType:B", "TimeType:A"])])
        self.assertEqual(lanes, [[K("A")], [K("B")], [K("C")]])

if __name__ == "__main__":
    unittest.main()

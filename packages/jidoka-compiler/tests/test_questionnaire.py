import unittest
from jidoka_compiler.questionnaire import build_questionnaire
from jidoka_core.decisions import DP_TYPES

PROSE = "Annual leave accrues monthly. The accrual unit is DAYS."
SPEC = [{"object": "TimeAccountType", "fields": ["unit", "negative_floor"],
         "dp_type": "STATUTORY", "owner": "payroll-lead",
         "terms": {"unit": "unit"}}]


class TestQuestionnaire(unittest.TestCase):
    def test_shape_and_typing(self):
        qs = build_questionnaire(PROSE, SPEC)
        self.assertEqual(len(qs), 1)  # 'unit' stated once -> no question
        q = qs[0]
        self.assertEqual(q["dp_id"], "DP-TIMEACCOUNTTYPE-NEGATIVE_FLOOR")
        self.assertIn(q["dp_type"], DP_TYPES)
        self.assertEqual(q["owner"], "payroll-lead")
        self.assertTrue(q["question"])
        self.assertEqual({"dp_id", "dp_type", "question", "owner", "object", "field"}, set(q))

    def test_no_values_extracted_and_deterministic(self):
        qs = build_questionnaire(PROSE, SPEC)
        self.assertEqual(qs, build_questionnaire(PROSE, SPEC))
        self.assertNotIn("DAYS", str(qs))

    def test_ambiguous_repeat_still_asks(self):
        qs = build_questionnaire(PROSE + " The unit may also be HOURS.", SPEC)
        self.assertEqual(len(qs), 2)

    def test_bad_dp_type_rejected(self):
        with self.assertRaises(ValueError):
            build_questionnaire(PROSE, [{"object": "X", "fields": ["a"], "dp_type": "GUESS"}])

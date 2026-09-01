import copy, json, pathlib, unittest
from jidoka_core.schema import IR_SCHEMA, IR_SCHEMA_VERSION, schema_json, validate_against_schema

FIX = pathlib.Path(__file__).parent / "fixtures"
IR = json.load(open(FIX / "komatsu_sample_ir.json"))

class TestSchema(unittest.TestCase):
    def test_version_and_json_export(self):
        self.assertEqual(IR_SCHEMA_VERSION, "ir/v1")
        self.assertEqual(json.loads(schema_json()), IR_SCHEMA)
        self.assertIn(IR_SCHEMA_VERSION, IR_SCHEMA["$id"])

    def test_fixture_records_accepted(self):
        for raw in IR:
            self.assertEqual(validate_against_schema(raw), [], raw["object"])

    def test_unsigned_source_rejected(self):
        bad = copy.deepcopy(IR[0]); bad["source"]["signed_by"] = ""
        errs = validate_against_schema(bad)
        self.assertTrue(any("source.signed_by" in e for e in errs), errs)

    def test_missing_signature_field_rejected(self):
        bad = copy.deepcopy(IR[0]); del bad["source"]["date"]
        self.assertTrue(any("source.date is missing" in e for e in validate_against_schema(bad)))

    def test_missing_required_top_level(self):
        bad = copy.deepcopy(IR[0]); del bad["tier"]
        self.assertTrue(any("record.tier is missing" in e for e in validate_against_schema(bad)))

    def test_bad_tier_rejected(self):
        bad = copy.deepcopy(IR[0]); bad["tier"] = "D"
        self.assertTrue(any("A/B/C" in e for e in validate_against_schema(bad)))

    def test_wrong_types_rejected(self):
        bad = copy.deepcopy(IR[0]); bad["intent"] = "not-an-object"; bad["depends_on"] = [""]
        errs = validate_against_schema(bad)
        self.assertTrue(any("record.intent must be a object" in e for e in errs), errs)
        self.assertTrue(any("record.depends_on[0]" in e for e in errs), errs)

if __name__ == "__main__":
    unittest.main()

"""SuccessFactors adapter tests. Gate tests, not coverage theatre: they prove the tier_map cannot
quietly start lying (a Tier-A entity with no entity set would be a live write to a guessed URL),
and that only Tier A ever produces a write."""
import unittest

from jidoka_adapters.successfactors import SFAdapter, ENTITY_SETS, KEY_FIELDS, TIER_MAP
from jidoka_adapters.successfactors.odata import ODataError
from jidoka_core.ir import IRRecord

SIGNED = {"workbook": "EC-Design-v2.xlsx", "signed_by": "a.consultant", "date": "2026-08-01"}


def ir(obj, intent, tier="A"):
    return IRRecord(object=obj, product="SuccessFactors", system_binding="SFPART000001",
                    intent=intent, tier=tier, source=dict(SIGNED))


class TestTierMap(unittest.TestCase):
    def test_tier_a_entities_all_declare_an_entity_set(self):
        for obj, tier in TIER_MAP.items():
            if tier == "A":
                self.assertIn(obj, ENTITY_SETS, f"{obj} claims tier A with no OData entity set")
                self.assertTrue(ENTITY_SETS[obj], f"{obj} has an empty entity set")

    def test_no_entity_set_is_a_placeholder(self):
        """A guessed or templated name would be written to a live tenant."""
        for obj, es in ENTITY_SETS.items():
            self.assertNotIn("<", es, f"{obj} names a placeholder entity set")
            self.assertTrue(es.isidentifier(), f"{obj} entity set {es!r} is not a plain name")

    def test_entity_sets_only_exist_for_tier_a(self):
        for obj in ENTITY_SETS:
            self.assertEqual(TIER_MAP.get(obj), "A", f"{obj} has an entity set but is not tier A")

    def test_ui_and_provisioning_only_objects_are_never_tier_a(self):
        for obj in ("MDF_OBJECT_DEFINITION", "MDF_CONFIGURATION_UI", "BUSINESS_RULE",
                    "DATA_MODEL_XML", "PROVISIONING_SWITCH", "RBP_PERMISSION_ROLE",
                    "RBP_PERMISSION_GROUP", "POSITION_MANAGEMENT_SETTINGS",
                    "TIME_OFF_ACCRUAL_RULE", "MANAGE_BUSINESS_CONFIGURATION",
                    "EC_PAYROLL_POINT_TO_POINT_CONFIG"):
            self.assertEqual(TIER_MAP[obj], "C", f"{obj} is UI-only — it cannot be tier A")

    def test_import_only_objects_are_tier_b(self):
        for obj in ("EC_PAYROLL_WAGE_TYPE_MAPPING", "LEGACY_TIME_ACCOUNT_BALANCES",
                    "FORM_TEMPLATE_XML", "RBP_PERMISSION_GROUP_MEMBERS"):
            self.assertEqual(TIER_MAP[obj], "B")

    def test_tiers_are_valid_and_map_covers_the_real_project_surface(self):
        self.assertTrue(set(TIER_MAP.values()) <= {"A", "B", "C"})
        for obj in ("FOCompany", "FOPayComponent", "EmpJob", "Position", "PickListV2",
                    "TimeType", "TimeAccount", "WorkSchedule", "PerPerson"):
            self.assertEqual(TIER_MAP[obj], "A")

    def test_readable_but_not_writable_entities_are_never_tier_a(self):
        """Regression: TIER_MAP is built from ENTITY_SETS, so anything listed there is claimed
        writable. These five answer a GET but are derived or written through a parent — listing
        one would have the executor upsert against a URL SF rejects, or worse, accepts."""
        for obj in ("TimeAccountDetail", "EmployeeTimeSheet", "WorkScheduleDay", "Holiday",
                    "PicklistOption"):
            self.assertNotIn(obj, ENTITY_SETS, f"{obj} is not a write target")
            self.assertIn(TIER_MAP[obj], ("B", "C"), f"{obj} claims a write path it does not have")

    def test_key_fields_only_describe_known_entities(self):
        for obj in KEY_FIELDS:
            self.assertIn(obj, ENTITY_SETS)

    def test_adapter_returns_a_copy(self):
        tm = SFAdapter().tier_map()
        tm["PROVISIONING_SWITCH"] = "A"
        self.assertEqual(SFAdapter().tier_map()["PROVISIONING_SWITCH"], "C")


class TestBuildApply(unittest.TestCase):
    def test_tier_a_upsert_is_dry_run_and_names_the_entity_set(self):
        out = SFAdapter().build_apply(ir("FOCostCenter", {"externalCode": "CC1", "name": "Fin"}))
        self.assertEqual(out["kind"], "odata_batch")
        self.assertTrue(out["dry_run"])
        self.assertEqual(out["entity_set"], "FOCostCenter")
        self.assertEqual(out["operations"][0]["method"], "UPSERT")

    def test_tier_a_without_an_entity_set_is_refused(self):
        with self.assertRaises(ODataError):
            SFAdapter().build_apply(ir("cust_MadeUpObject", {"externalCode": "X"}))

    def test_non_tier_a_never_builds_a_write(self):
        a = SFAdapter()
        for obj, tier in TIER_MAP.items():
            if tier == "A":
                continue
            out = a.build_apply(ir(obj, {"externalCode": "X"}, tier=tier))
            self.assertNotEqual(out["kind"], "odata_batch", f"{obj} built a write at tier {tier}")
            self.assertNotIn("operations", out)

    def test_tier_b_is_an_import_file_with_a_human_step(self):
        out = SFAdapter().build_apply(ir("FORM_TEMPLATE_XML", {"externalCode": "F1"}, tier="B"))
        self.assertEqual(out["kind"], "import_file")
        self.assertIn("Import & Export Data", out["human_step"])

    def test_tier_c_is_an_instruction_sheet(self):
        out = SFAdapter().build_apply(ir("RBP_PERMISSION_ROLE", {"name": "HR Admin"}, tier="C"))
        self.assertEqual(out["kind"], "instruction_sheet")
        self.assertEqual(len(out["steps"]), 3)


class TestVerify(unittest.TestCase):
    def test_verify_uses_the_entity_specific_key_field(self):
        live = [{"userId": "U1", "jobCode": "JC1"}]
        out = SFAdapter().verify(ir("EmpJob", {"userId": "U1", "jobCode": "JC2"}), live)
        self.assertEqual(out["key_field"], "userId")
        self.assertEqual(out["status"], "DRIFT")

    def test_verify_defaults_to_external_code(self):
        live = [{"externalCode": "CC1", "name": "Finance"}]
        out = SFAdapter().verify(ir("FOCostCenter", {"externalCode": "CC1", "name": "Finance"}),
                                 live)
        self.assertEqual(out["status"], "MATCH")
        self.assertEqual(out["key_field"], "externalCode")


if __name__ == "__main__":
    unittest.main()

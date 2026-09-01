"""Importer tests. The load-gate test is the important one: an unsigned instance file must stay
unsigned all the way into jidoka_core.ir, which then refuses it (invariant 1)."""
import json
import pathlib
import unittest

from jidoka_adapters.successfactors import importers
from jidoka_core.ir import IRValidationError, load_ir

FIX = pathlib.Path(__file__).parent / "fixtures"
PROV = {"workbook": "KOM_FIN_v3.xlsx", "cell_range": "CostCentres!A2:C40",
        "signed_by": "a.client@kom.example", "date": "2026-08-01"}


class TestCSV(unittest.TestCase):
    def test_rows_to_ir_shape(self):
        recs = importers.import_csv((FIX / "costcenters.csv").read_text(),
                                    "FOCostCenter", "KOM-SF-DEV", PROV)
        self.assertEqual(len(recs), 2)
        r = recs[0]
        self.assertEqual(r["object"], "FOCostCenter")
        self.assertEqual(r["product"], "SuccessFactors")
        self.assertEqual(r["system_binding"], "KOM-SF-DEV")
        self.assertEqual(r["tier"], "B")
        self.assertEqual(r["external_code"], "CC1000")
        self.assertEqual(r["intent"], {"externalCode": "CC1000", "name": "Finance", "status": "ACTIVE"})

    def test_provenance_passthrough_with_row_pinning(self):
        recs = importers.import_csv((FIX / "costcenters.csv").read_text(),
                                    "FOCostCenter", "KOM-SF-DEV", PROV)
        self.assertEqual(recs[0]["source"]["signed_by"], PROV["signed_by"])
        self.assertEqual(recs[0]["source"]["workbook"], PROV["workbook"])
        self.assertEqual(recs[0]["source"]["date"], PROV["date"])
        self.assertEqual(recs[0]["source"]["cell_range"], "CostCentres!A2:C40#row2")
        self.assertEqual(recs[1]["source"]["cell_range"], "CostCentres!A2:C40#row3")

    def test_extra_provenance_keys_carried(self):
        recs = importers.import_csv("externalCode\nCC1\n", "FOCostCenter", "S",
                                    {**PROV, "file_sha256": "abc123"})
        self.assertEqual(recs[0]["source"]["file_sha256"], "abc123")

    def test_empty_file(self):
        self.assertEqual(importers.import_csv("externalCode,name\n", "FOCostCenter", "S", PROV), [])


class TestJSON(unittest.TestCase):
    def test_plain_list(self):
        recs = importers.import_json(json.dumps([{"externalCode": "T1"}]), "TimeType", "S", PROV)
        self.assertEqual(recs[0]["intent"]["externalCode"], "T1")
        self.assertEqual(recs[0]["source"]["signed_by"], PROV["signed_by"])

    def test_odata_envelope(self):
        raw = json.dumps({"d": {"results": [{"externalCode": "T1"}, {"externalCode": "T2"}]}})
        self.assertEqual(len(importers.import_json(raw, "TimeType", "S", PROV)), 2)

    def test_file_dispatch_by_extension(self, ):
        recs = importers.import_file(str(FIX / "costcenters.csv"), "FOCostCenter", "S", PROV)
        self.assertEqual(len(recs), 2)


class TestSignatureGate(unittest.TestCase):
    def test_no_provenance_stays_unsigned(self):
        recs = importers.import_csv((FIX / "costcenters.csv").read_text(), "FOCostCenter", "S")
        self.assertIsNone(recs[0]["source"]["signed_by"])
        self.assertEqual(len(importers.unsigned(recs)), 2)

    def test_core_refuses_unsigned_records(self):
        recs = importers.import_csv((FIX / "costcenters.csv").read_text(), "FOCostCenter", "S")
        with self.assertRaises(IRValidationError):
            load_ir(recs)

    def test_signed_records_load(self):
        recs = importers.import_csv((FIX / "costcenters.csv").read_text(), "FOCostCenter", "S", PROV)
        loaded, dps = load_ir(recs)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(dps, {})
        self.assertEqual(importers.unsigned(recs), [])

    def test_partial_provenance_is_still_unsigned(self):
        recs = importers.import_csv((FIX / "costcenters.csv").read_text(), "FOCostCenter", "S",
                                    {"workbook": "x.xlsx", "date": "2026-08-01"})
        self.assertEqual(len(importers.unsigned(recs)), 2)
        with self.assertRaises(IRValidationError):
            load_ir(recs)


if __name__ == "__main__":
    unittest.main()

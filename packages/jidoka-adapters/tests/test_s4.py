"""S/4HANA adapter tests — fully offline: the transport is a fixture, never a socket.
The CSRF, dry_run, customising-refusal and secret-leak tests are gate tests: they prove a live
write cannot happen by accident (invariant 6), that a transported IMG object can never produce a
direct write (ADR-0003), and that a credential cannot escape through a repr."""
import json
import unittest

from jidoka_adapters.s4hana import (S4Adapter, S4ODataClient, S4ODataError, CustomisingChange,
                                    CustomisingWriteRefused, build_customising_apply)
from jidoka_adapters.s4hana.odata import build_batch, parse_batch_response, BOUNDARY
from jidoka_core.ir import IRRecord

SIGNED = {"workbook": "FI-Design-v3.xlsx", "signed_by": "a.consultant", "date": "2026-08-01"}


def ir(obj, intent, tier="A"):
    return IRRecord(object=obj, product="S4HANA", system_binding="S4D-100", intent=intent,
                    tier=tier, source=dict(SIGNED))


class FakeTransport:
    """Records calls; answers from a canned list so tests assert on request shape too."""

    def __init__(self, responses):
        self.responses = responses  # list of (status, headers, bytes) or callable(method, url, body)
        self.calls = []

    def __call__(self, method, url, headers, body=None, timeout=60.0):
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body})
        r = self.responses.pop(0) if isinstance(self.responses, list) else self.responses
        return r(method, url, body) if callable(r) else r


CSRF_OK = (200, {"x-csrf-token": "CSRF-XYZ", "Set-Cookie": "SAP_SESSIONID=abc; path=/"}, b"")


def client(responses, **kw):
    kw.setdefault("username", "COMM_USER")
    kw.setdefault("password", "hunter2-supersecret")
    return S4ODataClient("https://s4.example.com", sap_client="100",
                         transport=FakeTransport(responses), clock=lambda: 1000.0, **kw)


class TestCsrf(unittest.TestCase):
    def test_fetch_then_write_sequence(self):
        c = client([CSRF_OK, (201, {}, b'{"d":{"CostCenter":"CC1"}}')])
        status, _h, _raw = c.write("POST", "API_COSTCENTER_SRV", "A_CostCenter",
                                   {"CostCenter": "CC1"})
        self.assertEqual(status, 201)
        fetch, write = c._transport.calls
        self.assertEqual(fetch["method"], "HEAD")
        self.assertEqual(fetch["headers"]["X-CSRF-Token"], "Fetch")
        self.assertEqual(write["method"], "POST")
        self.assertEqual(write["headers"]["X-CSRF-Token"], "CSRF-XYZ")
        self.assertEqual(write["headers"]["Cookie"], "SAP_SESSIONID=abc")

    def test_token_is_reused_across_writes(self):
        c = client([CSRF_OK, (204, {}, b""), (204, {}, b"")])
        c.write("PATCH", "API_COSTCENTER_SRV", "A_CostCenter('CC1')", {"CostCenterName": "A"})
        c.write("PATCH", "API_COSTCENTER_SRV", "A_CostCenter('CC2')", {"CostCenterName": "B"})
        self.assertEqual([x["method"] for x in c._transport.calls], ["HEAD", "PATCH", "PATCH"])

    def test_expired_token_refetched_once(self):
        c = client([CSRF_OK, (403, {}, b"CSRF token validation failed"),
                    (200, {"x-csrf-token": "CSRF-2"}, b""), (204, {}, b"")])
        status, _h, _raw = c.write("POST", "API_COSTCENTER_SRV", "A_CostCenter", {"CostCenter": "X"})
        self.assertEqual(status, 204)
        self.assertEqual(c._transport.calls[-1]["headers"]["X-CSRF-Token"], "CSRF-2")

    def test_missing_token_header_fails_loudly(self):
        c = client([(200, {}, b"")])
        with self.assertRaises(S4ODataError):
            c.fetch_csrf("API_COSTCENTER_SRV")


class TestAuth(unittest.TestCase):
    def test_basic_auth_header(self):
        c = client([(200, {}, json.dumps({"d": {"results": []}}).encode())])
        c.read_entity("API_COSTCENTER_SRV", "A_CostCenter")
        h = c._transport.calls[0]["headers"]
        self.assertTrue(h["Authorization"].startswith("Basic "))
        self.assertEqual(h["sap-client"], "100")

    def test_client_credentials_token_cached(self):
        tok = (200, {}, json.dumps({"access_token": "bearer-1", "expires_in": 3600}).encode())
        c = S4ODataClient("https://s4.example.com", client_id="cid", client_secret="shhh",
                          token_url="https://uaa.example.com/oauth/token",
                          transport=FakeTransport([tok, (200, {}, b'{"value":[]}'),
                                                   (200, {}, b'{"value":[]}')]),
                          clock=lambda: 1000.0, odata_version="v4")
        c.read_entity("API_COUNTRY_SRV", "A_Country")
        c.read_entity("API_COUNTRY_SRV", "A_Country")
        self.assertEqual(sum(1 for x in c._transport.calls if "oauth" in x["url"]), 1)
        self.assertEqual(c._transport.calls[1]["headers"]["Authorization"], "Bearer bearer-1")
        self.assertIn("/sap/opu/odata4/sap/", c._transport.calls[1]["url"])

    def test_no_credential_refused(self):
        with self.assertRaises(S4ODataError):
            S4ODataClient("https://s4.example.com")


class TestSecrets(unittest.TestCase):
    """A leaked bearer is a live write credential. Nothing renders one."""

    def test_password_never_in_repr_or_str(self):
        c = client([])
        for text in (repr(c), str(c), f"{c}"):
            self.assertNotIn("hunter2-supersecret", text)
        self.assertIn("COMM_USER", repr(c))

    def test_secret_and_tokens_never_in_repr(self):
        c = S4ODataClient("https://s4.example.com", client_id="cid", client_secret="top-secret",
                          token_url="https://uaa.example.com/oauth/token",
                          transport=FakeTransport([(200, {}, json.dumps(
                              {"access_token": "bearer-secret", "expires_in": 3600}).encode()),
                              CSRF_OK]), clock=lambda: 1000.0)
        c.token()
        c.fetch_csrf("API_COSTCENTER_SRV")
        for text in (repr(c), str(c)):
            self.assertNotIn("top-secret", text)
            self.assertNotIn("bearer-secret", text)
            self.assertNotIn("CSRF-XYZ", text)

    def test_failed_token_error_does_not_echo_body(self):
        c = S4ODataClient("https://s4.example.com", client_id="cid", client_secret="top-secret",
                          token_url="https://uaa.example.com/oauth/token",
                          transport=FakeTransport([(401, {}, b'{"client_secret":"top-secret"}')]),
                          clock=lambda: 1000.0)
        with self.assertRaises(S4ODataError) as cm:
            c.token()
        self.assertNotIn("top-secret", str(cm.exception))


class TestBatch(unittest.TestCase):
    OPS = [{"entity": "A_CostCenter", "payload": {"CostCenter": "CC1", "CostCenterName": "Finance"}},
           {"entity": "A_CostCenter", "payload": {"CostCenter": "CC2", "CostCenterName": "Ops"}}]

    def test_body_shape(self):
        body = build_batch(self.OPS, "https://s4.example.com/sap/opu/odata/sap/API_COSTCENTER_SRV")
        self.assertTrue(body.startswith(f"--{BOUNDARY}"))
        self.assertIn("multipart/mixed; boundary=changeset_jidoka_s4", body)
        self.assertEqual(body.count("Content-ID:"), 2)
        self.assertIn('"CostCenter": "CC1"', body)
        self.assertTrue(body.rstrip().endswith(f"--{BOUNDARY}--"))

    def test_empty_batch_refused(self):
        with self.assertRaises(S4ODataError):
            build_batch([])

    def test_dry_run_touches_no_transport(self):
        c = client([])
        out = c.batch("API_COSTCENTER_SRV", self.OPS)
        self.assertTrue(out["dry_run"])
        self.assertEqual(out["status"], "DRY_RUN")
        self.assertEqual(c._transport.calls, [])

    def test_live_batch_fetches_csrf_first(self):
        parts = [f"--{BOUNDARY}", "Content-Type: application/http", "",
                 "HTTP/1.1 201 Created", "Content-Type: application/json", "",
                 '{"d":{"CostCenter":"CC1"}}', "", f"--{BOUNDARY}--", ""]
        c = client([CSRF_OK, (202, {}, "\r\n".join(parts).encode())])
        out = c.batch("API_COSTCENTER_SRV", self.OPS[:1], dry_run=False)
        self.assertEqual([x["method"] for x in c._transport.calls], ["HEAD", "POST"])
        self.assertEqual(out["results"][0]["status"], 201)

    def test_parse_response_needs_parts(self):
        with self.assertRaises(S4ODataError):
            parse_batch_response(b"nothing here")


class TestTierMap(unittest.TestCase):
    def test_spro_only_objects_are_never_tier_a(self):
        tm = S4Adapter().tier_map()
        for spro in ("T001", "T030", "T007A", "V_TVAK", "TKA01", "NUMBER_RANGE_INTERVAL",
                     "AUTH_ROLE_PFCG"):
            self.assertEqual(tm[spro], "C", f"{spro} is SPRO/IMG-only — it cannot be tier A")

    def test_tier_a_entities_all_declare_a_service(self):
        from jidoka_adapters.s4hana import SERVICES, KEY_FIELDS
        for obj, tier in S4Adapter().tier_map().items():
            if tier == "A":
                self.assertIn(obj, SERVICES, f"{obj} claims tier A with no OData service")
                self.assertIn(obj, KEY_FIELDS)

    def test_tiers_are_valid_and_migration_objects_are_b(self):
        tm = S4Adapter().tier_map()
        self.assertTrue(set(tm.values()) <= {"A", "B", "C"})
        self.assertEqual(tm["ASSET_MASTER_LEGACY"], "B")
        self.assertEqual(tm["COST_CENTER_HIERARCHY"], "B")


class TestBuildApply(unittest.TestCase):
    def test_tier_a_upsert_is_dry_run_by_default(self):
        out = S4Adapter().build_apply(ir("A_CostCenter", {"CostCenter": "CC1",
                                                          "CostCenterName": "Finance"}))
        self.assertEqual(out["kind"], "odata_batch")
        self.assertTrue(out["dry_run"])
        self.assertEqual(out["service"], "API_COSTCENTER_SRV")
        self.assertEqual(out["operations"][0]["method"], "UPSERT")

    def test_tier_a_without_a_service_is_refused(self):
        with self.assertRaises(S4ODataError):
            S4Adapter().build_apply(ir("A_MadeUpEntity", {"ID": "1"}))

    def test_tier_b_is_an_import_file_with_a_human_step(self):
        out = S4Adapter().build_apply(ir("ASSET_MASTER_LEGACY", {"Asset": "1000"}, tier="B"))
        self.assertEqual(out["kind"], "import_file")
        self.assertIn("LTMC", out["human_step"])

    def test_tier_c_is_an_instruction_sheet(self):
        out = S4Adapter().build_apply(ir("WORKFLOW_CONFIG_SWDD", {"task": "WS100"}, tier="C"))
        self.assertEqual(out["kind"], "instruction_sheet")
        self.assertEqual(len(out["steps"]), 3)


class TestCustomising(unittest.TestCase):
    def test_refuses_direct_write_for_customising_claiming_tier_a(self):
        rec = ir("T030", {"table": "T030", "target_client": "100", "AccountKey": "BSX"}, tier="A")
        with self.assertRaises(CustomisingWriteRefused):
            S4Adapter().build_apply(rec)

    def test_customising_yields_instruction_sheet_bound_to_a_transport(self):
        rec = ir("T007A", {"img_activity": "OBQ1", "table": "T007A", "target_client": "100",
                           "transport_request": "DEVK900123", "TaxCode": "V1"}, tier="C")
        out = S4Adapter().build_apply(rec)
        self.assertEqual(out["kind"], "instruction_sheet")
        self.assertEqual(out["transport_request"], "DEVK900123")
        self.assertEqual(out["customising"]["img_activity"], "OBQ1")
        self.assertTrue(any("DEVK900123" in s for s in out["steps"]))
        self.assertNotIn("payload", out)

    def test_missing_transport_leaves_a_placeholder_not_a_write(self):
        change = CustomisingChange(img_activity="OX02", table="T001", target_client="100",
                                   values={"CompanyCode": "1000"})
        sheet = change.instruction_sheet("S4D-100")
        self.assertIsNone(sheet["transport_request"])
        self.assertTrue(any("open a transport request" in s for s in sheet["steps"]))
        self.assertTrue(change.is_transported)

    def test_non_customising_object_is_not_routed_here(self):
        with self.assertRaises(CustomisingWriteRefused):
            build_customising_apply(ir("A_CostCenter", {"CostCenter": "CC1"}))


class TestExtractAndVerify(unittest.TestCase):
    LIVE = [{"CostCenter": "CC1", "CostCenterName": "Finance", "ValidityEndDate": "9999-12-31"},
            {"CostCenter": "CC2", "CostCenterName": "Ops", "ValidityEndDate": "9999-12-31"}]

    def test_extract_uses_injected_fetcher(self):
        a = S4Adapter(fetch=lambda system, entity: self.LIVE)
        self.assertEqual(len(a.extract("S4D-100", "A_CostCenter")), 2)

    def test_extract_without_fetcher_refuses(self):
        with self.assertRaises(RuntimeError):
            S4Adapter().extract("S4D-100", "A_CostCenter")

    def test_verify_match_and_field_level_drift(self):
        a = S4Adapter()
        clean = a.verify(ir("A_CostCenter", {"CostCenter": "CC1", "CostCenterName": "Finance"}),
                         self.LIVE)
        self.assertEqual(clean["status"], "MATCH")
        drifted = a.verify(ir("A_CostCenter", {"CostCenter": "CC2", "CostCenterName": "Operations"}),
                           self.LIVE)
        self.assertEqual(drifted["status"], "DRIFT")
        self.assertEqual(drifted["drift"],
                         {"CostCenterName": {"intent": "Operations", "live": "Ops"}})
        self.assertEqual(drifted["key_field"], "CostCenter")

    def test_verify_missing_when_key_absent(self):
        out = S4Adapter().verify(ir("A_CostCenter", {"CostCenter": "CC9"}), self.LIVE)
        self.assertEqual(out["status"], "MISSING")

    def test_verify_uses_the_entity_specific_key_field(self):
        live = [{"BusinessPartner": "BP1", "BusinessPartnerCategory": "2"}]
        out = S4Adapter().verify(ir("A_BusinessPartner", {"BusinessPartner": "BP1",
                                                          "BusinessPartnerCategory": "1"}), live)
        self.assertEqual(out["key_field"], "BusinessPartner")
        self.assertEqual(out["status"], "DRIFT")

    def test_diff_reports_added_removed_changed(self):
        after = [dict(self.LIVE[0], CostCenterName="Finance & Tax"),
                 {"CostCenter": "CC3", "CostCenterName": "New"}]
        d = S4Adapter().diff(self.LIVE, after, key="CostCenter")
        self.assertEqual(d["added"], ["CC3"])
        self.assertEqual(d["removed"], ["CC2"])
        self.assertIn("CostCenterName", d["changed"]["CC1"])
        self.assertFalse(d["clean"])


class TestRead(unittest.TestCase):
    def test_v2_paging_follows_next_link(self):
        page1 = json.dumps({"d": {"results": [{"CostCenter": "CC1"}],
                                  "__next": "/sap/opu/odata/sap/API_COSTCENTER_SRV/A_CostCenter?$skip=1"}}).encode()
        page2 = json.dumps({"d": {"results": [{"CostCenter": "CC2"}]}}).encode()
        c = client([(200, {}, page1), (200, {}, page2)])
        rows = c.read_entity("API_COSTCENTER_SRV", "A_CostCenter")
        self.assertEqual([r["CostCenter"] for r in rows], ["CC1", "CC2"])

    def test_v4_paging_and_read_failure(self):
        c = client([(200, {}, json.dumps({"value": [{"Country": "ZA"}]}).encode())],
                   )
        c.odata_version = "v4"
        self.assertEqual(c.read_entity("API_COUNTRY_SRV", "A_Country"), [{"Country": "ZA"}])
        c2 = client([(500, {}, b"boom")])
        with self.assertRaises(S4ODataError):
            c2.read_entity("API_COUNTRY_SRV", "A_Country")


if __name__ == "__main__":
    unittest.main()

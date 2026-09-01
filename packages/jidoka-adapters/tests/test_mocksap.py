"""MockSAP proves itself: the whole write/verify/rollback loop runs offline, failures included."""
import json
import unittest

from jidoka_adapters.mocksap import MockSAP, MockTimeout, fixtures
from jidoka_adapters.mocksap.server import CSRF_TOKEN
from jidoka_adapters.successfactors.loader import BatchLoader, BatchError
from jidoka_adapters.successfactors.odata import SFODataClient, ODataError, parse_metadata

BASE = "https://api.example.com"


def client(sap, **kw):
    return SFODataClient(BASE, "COMP", "cid", "assertion-secret", transport=sap, **kw)


class TestMetadata(unittest.TestCase):
    def test_metadata_parses_into_twin_shape(self):
        sap = MockSAP()
        meta = client(sap).metadata()
        self.assertIn("FOCostCenter", meta)
        self.assertIn("A_BusinessPartner", meta)
        f = meta["FOCostCenter"]["fields"]
        self.assertTrue(f["externalCode"]["required"])
        self.assertFalse(f["description"]["required"])
        self.assertEqual(f["status"]["picklist"], "ACTIVE_STATUS")

    def test_metadata_is_valid_edmx(self):
        self.assertEqual(len(parse_metadata(fixtures.METADATA_XML.encode())), 4)


class TestReads(unittest.TestCase):
    def test_seeded_collections_read_back(self):
        rows = client(MockSAP()).read_entity("FOCostCenter")
        self.assertEqual([r["externalCode"] for r in rows], ["CC-1000", "CC-2000", "CC-3000"])

    def test_filter_on_external_code(self):
        rows = client(MockSAP()).read_entity(
            "FOCostCenter", params={"$filter": "externalCode eq 'CC-2000'"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "People Operations")

    def test_filter_and_clause(self):
        rows = client(MockSAP()).read_entity(
            "PicklistV2", params={"$filter": "picklistId eq 'REGION' and optionId eq 'APJ'"})
        self.assertEqual(len(rows), 1)

    def test_server_paging_next_link_followed(self):
        rows = client(MockSAP()).read_entity("FOCostCenter", top=2)
        self.assertEqual(len(rows), 3)

    def test_s4_collections_present(self):
        sap = MockSAP()
        c = client(sap)
        self.assertEqual(len(c.read_entity("A_CostCenter")), 2)
        self.assertEqual(len(c.read_entity("A_BusinessPartner")), 2)

    def test_unknown_entity_404s(self):
        with self.assertRaises(ODataError):
            client(MockSAP()).read_entity("NoSuchThing")


class TestWrites(unittest.TestCase):
    def test_upsert_then_read_back(self):
        sap = MockSAP()
        c = client(sap)
        status, _h, _raw = c.request(
            "POST", f"{BASE}/odata/v2/FOCostCenter", {"Content-Type": "application/json"},
            json.dumps({"externalCode": "CC-1000", "name": "Group Finance EMEA"}).encode())
        self.assertEqual(status, 200)
        rows = c.read_entity("FOCostCenter", params={"$filter": "externalCode eq 'CC-1000'"})
        self.assertEqual(rows[0]["name"], "Group Finance EMEA")
        self.assertEqual(rows[0]["cust_region"], "EMEA")  # MERGE semantics: untouched field survives

    def test_insert_creates_201(self):
        sap = MockSAP()
        status, _h, _raw = client(sap).request(
            "POST", f"{BASE}/odata/v2/FOCostCenter", {"Content-Type": "application/json"},
            json.dumps({"externalCode": "CC-9000", "name": "New Unit"}).encode())
        self.assertEqual(status, 201)
        self.assertEqual(sap.row("FOCostCenter", "CC-9000")["name"], "New Unit")

    def test_put_replaces_rather_than_merges(self):
        sap = MockSAP()
        client(sap).request("PUT", f"{BASE}/odata/v2/A_CostCenter", {},
                            json.dumps({"CostCenter": "0000100000", "ControllingArea": "2000"}).encode())
        row = sap.row("A_CostCenter", "0000100000")
        self.assertEqual(row["ControllingArea"], "2000")
        self.assertNotIn("CompanyCode", row)

    def test_missing_key_rejected(self):
        status, _h, _raw = client(MockSAP()).request(
            "POST", f"{BASE}/odata/v2/FOCostCenter", {}, json.dumps({"name": "keyless"}).encode())
        self.assertEqual(status, 400)


class TestCSRF(unittest.TestCase):
    def test_write_without_token_rejected(self):
        sap = MockSAP(require_csrf=True)
        status, _h, raw = client(sap).request(
            "POST", f"{BASE}/odata/v2/A_CostCenter", {},
            json.dumps({"CostCenter": "0000300000", "ControllingArea": "1000"}).encode())
        self.assertEqual(status, 403)
        self.assertIn("CSRF", raw.decode())
        self.assertIsNone(sap.row("A_CostCenter", "0000300000"))

    def test_fetch_then_write_succeeds(self):
        sap = MockSAP(require_csrf=True)
        c = client(sap)
        _s, headers, _raw = c.request("GET", f"{BASE}/odata/v2/A_CostCenter?$top=1",
                                      {"X-CSRF-Token": "Fetch"})
        token = headers["X-CSRF-Token"]
        self.assertEqual(token, CSRF_TOKEN)
        status, _h, _raw = c.request(
            "POST", f"{BASE}/odata/v2/A_CostCenter", {"X-CSRF-Token": token},
            json.dumps({"CostCenter": "0000300000", "ControllingArea": "1000"}).encode())
        self.assertEqual(status, 201)

    def test_stale_token_rejected(self):
        sap = MockSAP(require_csrf=True)
        status, _h, _raw = client(sap).request(
            "POST", f"{BASE}/odata/v2/A_CostCenter", {"X-CSRF-Token": "stale-token"},
            json.dumps({"CostCenter": "0000300000", "ControllingArea": "1000"}).encode())
        self.assertEqual(status, 403)

    def test_batch_also_csrf_protected(self):
        sap = MockSAP(require_csrf=True)
        loader = BatchLoader(client=client(sap))
        with self.assertRaises(BatchError):
            loader.apply([{"entity": "FOCostCenter", "payload": {"externalCode": "CC-1000", "name": "X"}}],
                         dry_run=False, base_url=BASE)


class TestFailureInjection(unittest.TestCase):
    def test_fail_next_is_one_shot(self):
        sap = MockSAP()
        c = client(sap)
        c.token()
        sap.fail_next(503, b"unavailable")
        with self.assertRaises(ODataError):
            c.read_entity("FOCostCenter")
        self.assertEqual(len(c.read_entity("FOCostCenter")), 3)  # recovered

    def test_429_carries_retry_after(self):
        sap = MockSAP()
        sap.fail_next_rate_limited(retry_after=42)
        status, headers, _raw = sap("GET", f"{BASE}/odata/v2/FOCostCenter", {})
        self.assertEqual(status, 429)
        self.assertEqual(headers["Retry-After"], "42")

    def test_timeout_raises_from_transport(self):
        sap = MockSAP()
        sap.fail_next_timeout()
        with self.assertRaises(MockTimeout):
            client(sap).token()

    def test_401_triggers_reauth_and_retry_succeeds(self):
        sap = MockSAP()
        c = client(sap)
        self.assertEqual(len(c.read_entity("FOCostCenter")), 3)
        sap.expire_token()          # server-side revocation; client still holds a cached bearer
        c._token_expiry = 0.0       # client notices only on its own clock
        rows = c.read_entity("FOCostCenter")
        self.assertEqual(len(rows), 3)
        token_calls = [x for x in sap.calls if "oauth" in x["url"]]
        self.assertEqual(len(token_calls), 2)
        self.assertEqual(sap.calls[-1]["headers"]["Authorization"], "Bearer mock-bearer-2")

    def test_stale_bearer_gets_401_not_silent_success(self):
        sap = MockSAP()
        c = client(sap)
        c.read_entity("FOCostCenter")
        sap.expire_token()
        with self.assertRaises(ODataError):  # cached token, no client-side refresh -> 401
            c.read_entity("FOCostCenter")
        self.assertEqual(sap.calls[-1]["headers"]["Authorization"], "Bearer mock-bearer-1")


def ops():
    return [
        {"entity": "FOCostCenter", "payload": {"externalCode": "CC-1000", "name": "Finance A"}},
        {"entity": "FOCostCenter", "payload": {"externalCode": "CC-2000", "name": "People A"}},
        {"entity": "FOCostCenter", "payload": {"externalCode": "CC-4000", "name": "New Unit"}},
    ]


class TestBatch(unittest.TestCase):
    def test_batch_applies_in_order(self):
        sap = MockSAP()
        result = BatchLoader(client=client(sap)).apply(ops(), dry_run=False, base_url=BASE)
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["applied"], ["CC-1000", "CC-2000", "CC-4000"])
        self.assertEqual(sap.row("FOCostCenter", "CC-1000")["name"], "Finance A")
        self.assertEqual(sap.row("FOCostCenter", "CC-4000")["name"], "New Unit")

    def test_journal_makes_replay_idempotent(self):
        sap = MockSAP()
        loader = BatchLoader(client=client(sap))
        loader.apply(ops(), dry_run=False, base_url=BASE)
        again = loader.apply(ops(), dry_run=False, base_url=BASE)
        self.assertEqual(again["status"], "NOOP")
        self.assertEqual(again["skipped"], 3)

    def test_mid_batch_500_leaves_detectable_partial_state(self):
        """The scenario that matters: op 1 committed, ops 2-3 did not. A diff must see it."""
        sap = MockSAP()
        before = {r["externalCode"]: dict(r) for r in sap.collections["FOCostCenter"]}
        sap.fail_batch_at(2)
        result = BatchLoader(client=client(sap)).apply(ops(), dry_run=False, base_url=BASE)

        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["applied"], ["CC-1000"])
        self.assertEqual([e["externalCode"] for e in result["errors"]], ["CC-2000", "CC-4000"])
        self.assertTrue(all(e["status"] == 500 for e in result["errors"]))

        # server truth agrees with the client's report — the whole point of the exercise
        self.assertEqual(sap.row("FOCostCenter", "CC-1000")["name"], "Finance A")
        self.assertEqual(sap.row("FOCostCenter", "CC-2000")["name"], "People Operations")
        self.assertIsNone(sap.row("FOCostCenter", "CC-4000"))

        after = {r["externalCode"]: dict(r) for r in sap.collections["FOCostCenter"]}
        changed = [k for k in after if before.get(k) != after[k]]
        self.assertEqual(changed, ["CC-1000"])

    def test_partial_batch_replays_only_the_unconfirmed(self):
        sap = MockSAP()
        loader = BatchLoader(client=client(sap))
        sap.fail_batch_at(2)
        loader.apply(ops(), dry_run=False, base_url=BASE)
        sap.reset_failures()
        retry = loader.apply(ops(), dry_run=False, base_url=BASE)
        self.assertEqual(retry["skipped"], 1)          # CC-1000 already journaled
        self.assertEqual(retry["applied"], ["CC-2000", "CC-4000"])
        self.assertEqual(sap.row("FOCostCenter", "CC-4000")["name"], "New Unit")

    def test_rollback_by_reapplying_prior_values(self):
        sap = MockSAP()
        before = dict(sap.row("FOCostCenter", "CC-1000"))
        sap.fail_batch_at(2)
        BatchLoader(client=client(sap)).apply(ops(), dry_run=False, base_url=BASE)
        self.assertNotEqual(sap.row("FOCostCenter", "CC-1000"), before)
        BatchLoader(client=client(sap)).apply(
            [{"entity": "FOCostCenter", "payload": before}], dry_run=False, base_url=BASE)
        self.assertEqual(sap.row("FOCostCenter", "CC-1000"), before)

    def test_whole_batch_transport_failure_applies_nothing(self):
        sap = MockSAP()
        loader = BatchLoader(client=client(sap))
        loader._client.token()  # cache the bearer first so fail_next lands on the $batch itself
        sap.fail_next(500, b"gateway blew up")
        with self.assertRaises(BatchError):
            loader.apply(ops(), dry_run=False, base_url=BASE)
        self.assertIsNone(sap.row("FOCostCenter", "CC-4000"))
        self.assertEqual(loader.journal, {})

    def test_dry_run_touches_no_transport(self):
        sap = MockSAP()
        result = BatchLoader(client=client(sap)).apply(ops(), dry_run=True, base_url=BASE)
        self.assertEqual(result["status"], "DRY_RUN")
        self.assertEqual(sap.calls, [])
        self.assertIsNone(sap.row("FOCostCenter", "CC-4000"))


if __name__ == "__main__":
    unittest.main()

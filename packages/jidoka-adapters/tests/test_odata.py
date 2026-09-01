"""OData client tests — fully offline: the transport is a fixture, never a socket."""
import json
import pathlib
import unittest
import urllib.parse

from jidoka_adapters.successfactors.odata import SFODataClient, ODataError, parse_metadata
from jidoka_core.twin import SchemaTwin

FIX = pathlib.Path(__file__).parent / "fixtures"


class FakeTransport:
    """Records calls; answers from a canned map so tests assert on request shape too."""

    def __init__(self, responses):
        self.responses = responses  # list of (status, headers, bytes) or callable(method, url, body)
        self.calls = []

    def __call__(self, method, url, headers, body=None, timeout=60.0):
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body})
        r = self.responses.pop(0) if isinstance(self.responses, list) else self.responses
        return r(method, url, body) if callable(r) else r


def token_response(expires=3600, tok="tok-1"):
    return (200, {}, json.dumps({"access_token": tok, "expires_in": expires}).encode())


def client(responses, clock=None):
    return SFODataClient("https://api.example.com", "COMP", "cid", "assertion-secret",
                         transport=FakeTransport(responses), clock=clock or (lambda: 1000.0))


class TestMetadata(unittest.TestCase):
    def test_parses_into_schematwin_shape(self):
        meta = parse_metadata((FIX / "metadata.xml").read_bytes())
        self.assertIn("FOCostCenter", meta)
        f = meta["FOCostCenter"]["fields"]
        self.assertTrue(f["externalCode"]["required"])
        self.assertFalse(f["costcenterManager"]["required"])
        self.assertEqual(f["status"]["picklist"], "ACTIVE_STATUS")
        self.assertIsNone(f["name"]["picklist"])
        self.assertEqual(f["name"]["type"], "Edm.String")

    def test_twin_consumes_metadata_directly(self):
        twin = SchemaTwin(parse_metadata((FIX / "metadata.xml").read_bytes()))
        errs = twin.validate_payload("FOCostCenter", {"externalCode": "CC1", "name": ""})
        self.assertTrue(any("name" in e for e in errs))
        self.assertEqual(twin.validate_payload("FOCostCenter", {"externalCode": "CC1", "name": "Fin"}), [])

    def test_fetch_uses_bearer_and_fails_loudly(self):
        c = client([token_response(), (200, {}, (FIX / "metadata.xml").read_bytes())])
        c.metadata()
        self.assertEqual(c._transport.calls[1]["headers"]["Authorization"], "Bearer tok-1")
        c2 = client([token_response(), (500, {}, b"boom")])
        with self.assertRaises(ODataError):
            c2.metadata()


class TestToken(unittest.TestCase):
    def test_cached_until_expiry_then_refreshed(self):
        now = [1000.0]
        empty = (200, {}, b'{"d":{"results":[]}}')
        c = client([token_response(3600, "tok-1"), empty, empty,
                    token_response(3600, "tok-2"), empty],
                   clock=lambda: now[0])
        c.read_entity("TimeType")
        c.read_entity("TimeType")  # still cached -> no second token call
        self.assertEqual(sum(1 for x in c._transport.calls if "oauth" in x["url"]), 1)
        now[0] += 4000  # past expiry
        c.read_entity("TimeType")
        self.assertEqual(sum(1 for x in c._transport.calls if "oauth" in x["url"]), 2)
        self.assertEqual(c._transport.calls[-1]["headers"]["Authorization"], "Bearer tok-2")

    def test_saml_bearer_grant_form(self):
        c = client([token_response()])
        c.token()
        form = urllib.parse.parse_qs(c._transport.calls[0]["body"].decode())
        self.assertEqual(form["grant_type"], ["urn:ietf:params:oauth:grant-type:saml2-bearer"])
        self.assertEqual(form["company_id"], ["COMP"])

    def test_secrets_never_in_repr_or_errors(self):
        c = client([(401, {}, b'{"error":"assertion assertion-secret rejected"}')])
        self.assertNotIn("assertion-secret", repr(c))
        self.assertNotIn("cid", repr(c))
        with self.assertRaises(ODataError) as ctx:
            c.token()
        self.assertNotIn("assertion-secret", str(ctx.exception))

    def test_missing_access_token_raises(self):
        c = client([(200, {}, b'{"expires_in":10}')])
        with self.assertRaises(ODataError):
            c.token()


def page(rows, nxt=None):
    d = {"results": rows}
    if nxt:
        d["__next"] = nxt
    return (200, {}, json.dumps({"d": d}).encode())


class TestPaging(unittest.TestCase):
    def test_follows_next_link(self):
        c = client([token_response(),
                    page([{"externalCode": "A"}], "https://api.example.com/odata/v2/FOCostCenter?$skip=1"),
                    page([{"externalCode": "B"}])])
        rows = c.read_entity("FOCostCenter", top=1)
        self.assertEqual([r["externalCode"] for r in rows], ["A", "B"])

    def test_walks_skip_when_no_next_link(self):
        c = client([token_response(), page([{"i": 1}, {"i": 2}]), page([{"i": 3}])])
        rows = c.read_entity("FOCostCenter", top=2)
        self.assertEqual(len(rows), 3)
        self.assertIn("%24skip=2", c._transport.calls[-1]["url"])

    def test_single_short_page_stops(self):
        c = client([token_response(), page([{"i": 1}])])
        self.assertEqual(len(c.read_entity("FOCostCenter", top=500)), 1)
        self.assertEqual(len(c._transport.calls), 2)

    def test_fetcher_plugs_into_adapter(self):
        from jidoka_adapters.successfactors import SFAdapter
        c = client([token_response(), page([{"externalCode": "CC1"}])])
        a = SFAdapter(client=c)
        self.assertEqual(a.extract("KOM-SF-DEV", "FOCostCenter"), [{"externalCode": "CC1"}])

    def test_adapter_without_fetcher_still_refuses(self):
        from jidoka_adapters.successfactors import SFAdapter
        with self.assertRaises(RuntimeError):
            SFAdapter().extract("KOM-SF-DEV", "FOCostCenter")


if __name__ == "__main__":
    unittest.main()

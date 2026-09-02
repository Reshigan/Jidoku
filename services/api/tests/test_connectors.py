"""The connector is where a built payload meets a substrate. These pin the two ways that seam
has silently lied: an upsert that was really an insert, and a read-only binding that still held
a reachable write path."""
import pytest

from jidoka_api import connectors
from jidoka_core.registry import SystemRecord, SystemRegistry


def _registry(role="TARGET"):
    r = SystemRegistry()
    r.register(SystemRecord(system_id="KOM-S4-DEV", product="S4HANA", role=role,
                            environment="DEV",
                            connectivity={"write_credentials": role == "TARGET"}))
    return r


def _payload(key_field, code, name):
    return {"kind": "odata_batch", "system": "KOM-S4-DEV", "entity_set": "CostCenter",
            "key_field": key_field,
            "operations": [{"method": "UPSERT", "entity": "CostCenter",
                            "payload": {"CostCenter": code, "Name": name}}]}


def test_an_upsert_re_run_updates_the_row_it_already_wrote():
    """Regression: the key field was guessed as externalCode, which no S/4 entity has, so nothing
    ever matched and every re-run appended a second row claiming to be the same cost centre."""
    c = connectors.build("mock", "KOM-S4-DEV", "S4HANA", _registry())
    c.apply(_payload("CostCenter", "CC-100", "Operations"))
    out = c.apply(_payload("CostCenter", "CC-100", "Operations — renamed"))
    rows = [r for r in out["live_state"] if r.get("CostCenter") == "CC-100"]
    assert len(rows) == 1, "a second write of the same key must update, not append"
    assert rows[0]["Name"] == "Operations — renamed"


def test_an_upsert_with_no_declared_key_field_appends_rather_than_guessing():
    """No key field means the substrate cannot know which record is meant. Appending is wrong but
    honest; silently matching on a guessed field would overwrite an unrelated row."""
    c = connectors.build("mock", "KOM-S4-DEV", "S4HANA", _registry())
    p = _payload("CostCenter", "CC-200", "Plant")
    p.pop("key_field")
    c.apply(p)
    out = c.apply(p)
    assert len([r for r in out["live_state"] if r.get("CostCenter") == "CC-200"]) == 2


def test_a_read_only_binding_has_no_reachable_write_path():
    """Invariant 3. Refusing `apply` is not enough if the underlying client is still on the object:
    anything holding the connector could reach the substrate around the refusal."""
    r = _registry("SOURCE_LEGACY")
    c = connectors.build_reader("mock", "KOM-S4-DEV", "ECC", r)
    with pytest.raises(connectors.ConnectorError):
        c.apply(_payload("CostCenter", "CC-300", "Legacy"))
    for attr in ("write", "batch", "request", "_client", "mock"):
        assert not hasattr(c, attr), f"{attr} is a way around the refusal"



def _fake_transport(monkeypatch, client_cls, transport):
    """Give a client a fake wire. `_live` constructs the client itself and passes no transport, so
    the real one is already bound as a default argument by then — swap it on the built instance."""
    real = client_cls.__init__

    def patched(self, *a, **kw):
        real(self, *a, **kw)
        self._transport = transport

    monkeypatch.setattr(client_cls, "__init__", patched)


def _half_rejected_batch(n_ok: int, n_bad: int) -> bytes:
    """A $batch reply where the changeset partly landed — the shape that used to read as OK."""
    parts = []
    for i in range(n_ok):
        parts.append("--x\r\nContent-Type: application/http\r\n\r\nHTTP/1.1 200 OK\r\n"
                     f"Content-Type: application/json\r\n\r\n{{\"i\": {i}}}\r\n")
    for _ in range(n_bad):
        parts.append("--x\r\nContent-Type: application/http\r\n\r\nHTTP/1.1 400 Bad Request\r\n"
                     "Content-Type: application/json\r\n\r\n{\"error\": \"mandatory field missing\"}\r\n")
    return ("".join(parts) + "--x--\r\n").encode()


def _sf_payload(entity="Position"):
    return {"kind": "odata_batch", "system": "KOM-SF-DEV", "entity_set": entity,
            "key_field": "externalCode",
            "operations": [{"method": "UPSERT", "entity": entity,
                            "payload": {"externalCode": f"P-{i}", "name": f"Role {i}"}}
                           for i in (1, 2)]}


def test_a_half_rejected_sf_batch_reports_its_failures(monkeypatch):
    """Regression: the SF live path borrowed S/4's batch builder and never read the reply, so a
    changeset where half the operations were rejected came back a bare OK. executor.py's partial
    guard reads failed_operations, so with no count a partial write verified as a clean one — and
    the body it sent was a shape SF rejects outright."""
    sent = []

    def transport(method, url, headers, body=None):
        sent.append((method, url, body))
        if "token" in url:
            return 200, {}, b'{"access_token": "t", "expires_in": 3600}'
        if url.endswith("$batch"):
            return 200, {}, _half_rejected_batch(1, 1)
        return 200, {}, b'{"d": {"results": []}}'

    from jidoka_adapters.successfactors.odata import SFODataClient

    _fake_transport(monkeypatch, SFODataClient, transport)
    monkeypatch.setenv("KOM_CLIENT_ID", "id")
    monkeypatch.setenv("KOM_ASSERTION", "assertion")
    r = SystemRegistry()
    r.register(SystemRecord(system_id="KOM-SF-DEV", product="SuccessFactors", role="TARGET",
                            environment="DEV", connectivity={"write_credentials": True}))

    c = connectors.build("live", "KOM-SF-DEV", "SuccessFactors", r,
                         base_url="https://sf.invalid", secret_env="KOM")
    out = c.apply(_sf_payload())

    assert out["failed_operations"] == 1, "a rejected operation must be counted, not swallowed"
    assert out["total_operations"] == 2
    assert out["status"] == "PARTIAL"
    assert "live_state" in out, "verify() reads live_state; without it a landed record reads MISSING"
    body = next(b for _m, u, b in sent if u.endswith("$batch")).decode()
    assert "/odata/v2/upsert" in body and "X-Entity: Position" in body, \
        "SF upserts POST to /odata/v2/upsert naming the entity in a header; S/4's shape is rejected"


def test_a_half_rejected_s4_batch_reports_its_failures(monkeypatch):
    """Same guard on the other product. client.batch hands back raw per-part replies and no count,
    so the executor saw no failures however many operations the substrate refused."""
    def transport(method, url, headers, body=None):
        if "token" in url:
            return 200, {}, b'{"access_token": "t", "expires_in": 3600}'
        if method == "HEAD":  # S/4 fetches a CSRF token before it will accept a write
            return 200, {"x-csrf-token": "csrf"}, b""
        if url.endswith("$batch"):
            return 200, {}, _half_rejected_batch(1, 1)
        return 200, {}, b'{"d": {"results": []}}'

    from jidoka_adapters.s4hana.odata import S4ODataClient
    _fake_transport(monkeypatch, S4ODataClient, transport)
    for v in ("KOM_CLIENT_ID", "KOM_CLIENT_SECRET", "KOM_TOKEN_URL"):
        monkeypatch.setenv(v, "https://s4.invalid/token" if v.endswith("TOKEN_URL") else "x")
    r = SystemRegistry()
    r.register(SystemRecord(system_id="KOM-S4-DEV", product="S4HANA", role="TARGET",
                            environment="DEV", connectivity={"write_credentials": True}))

    c = connectors.build("live", "KOM-S4-DEV", "S4HANA", r,
                         base_url="https://s4.invalid", secret_env="KOM")
    out = c.apply({"kind": "odata_batch", "system": "KOM-S4-DEV", "entity_set": "CostCenter",
                   "service": "API_COSTCENTER_SRV", "key_field": "CostCenter",
                   "operations": [{"method": "UPSERT", "entity": "CostCenter",
                                   "payload": {"CostCenter": f"CC-{i}"}} for i in (1, 2)]})

    assert out["failed_operations"] == 1
    assert out["total_operations"] == 2
    assert "live_state" in out

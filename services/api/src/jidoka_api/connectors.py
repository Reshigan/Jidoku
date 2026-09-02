"""Binding a system to the thing that can actually read and write it.

Until a system has a connector, the platform can build a payload and nothing else: snapshot has
no reader, and a live write has no substrate. That is the correct default — an unbound system
cannot be changed by accident — but it means binding is a deliberate, ledgered act.

Credentials never travel in the request body. A live binding names an environment variable prefix
and the process reads the secret from there, so a secret cannot be logged by the HTTP layer,
echoed back in a 4xx, or persisted alongside the engagement.
"""
from __future__ import annotations

import os

from jidoka_core.registry import SystemRegistry


class ConnectorError(Exception):
    """Binding refused. Shown to an operator verbatim, so it must never quote a secret."""


class Connector:
    """A reader and a writer for one system, built together.

    They are one object because they must address the same system: a snapshot read from one
    tenant and a write sent to another is the worst failure this platform could have.
    """

    def __init__(self, kind: str, fetch, apply_fn, describe: str, metadata_xml=None):
        self.kind = kind
        self.fetch = fetch          # callable(system, entity) -> rows, for Adapter(fetch=...)
        self.apply = apply_fn       # callable(payload) -> outcome, for Executor(apply_fn=...)
        self.describe = describe
        # callable() -> the service definition document, for a metadata harvest (ADR-0012). It
        # rides the same binding as the reader on purpose: reading a system's structure is
        # reading the system, and it must not be reachable without the authorisation to do so.
        self.metadata_xml = metadata_xml

    def __repr__(self) -> str:  # never let a client object or credential reach a log line
        return f"<Connector {self.kind} {self.describe}>"


def _key_of(row: dict, payload: dict) -> str | None:
    """The field that identifies this row, as the adapter declared it.

    Guessing here is what made an upsert an insert: no S/4 entity is keyed by externalCode, so a
    fallback guess never matched and every re-run appended a duplicate. The adapter knows the key
    field and now says so in the payload; if it did not, refusing to match is the honest answer.
    """
    f = payload.get("key_field") or ""
    return f if f and f in row else None


def _read_back(fetch, system_id: str, payload: dict) -> list[dict]:
    """Re-read the entity that was just written, so verify() sees the substrate rather than a hope.

    Without this a live write returns no live_state, verify() is handed an empty list and reports
    MISSING for a record that landed perfectly. A read that fails is not a failed write: the write
    already happened and is on the ledger, so the read's failure downgrades the step to DRIFTED
    through an empty state rather than throwing away the EXECUTED entry.
    """
    ops = payload.get("operations") or []
    entity = (ops[0].get("entity") if ops else "") or payload.get("entity_set", "")
    if not entity:
        return []
    try:
        return list(fetch(system_id, entity))
    except Exception:
        return []


def _mock(system_id: str) -> Connector:
    """In-process mock SAP: real payload shapes, fake tenant. The demo path and the test path
    are the same code, so what an operator sees on screen is what the tests exercise."""
    from jidoka_adapters.mocksap import MockSAP

    sap = MockSAP(base_url=f"https://{system_id.lower()}.mock.invalid")

    def fetch(system, entity):
        return [dict(r) for r in sap.collections.get(entity, [])]

    def apply_fn(payload):
        if payload.get("dry_run"):
            # The executor flips dry_run off before calling; a True here means a gate was skipped.
            raise ConnectorError("A dry-run payload reached a connector — refusing to write.")
        if payload.get("kind") == "restore":
            # Executor.rollback speaks a different payload: the snapshot's rows, verbatim. Replace
            # the collection rather than merging into it — a merge would leave rows the snapshot
            # never saw, which is not the state anyone fingerprinted.
            rows = payload.get("rows") or []
            entity = payload.get("object") or payload.get("entity_set", "")
            sap.collections[entity] = [dict(r) for r in rows]
            return {"status": "OK", "total_operations": len(rows), "restored": entity}
        ops = payload.get("operations") or []
        if not ops:
            raise ConnectorError("Refusing an apply with no operations.")
        for op in ops:
            entity = op.get("entity") or payload.get("entity_set", "")
            rows = sap.collections.setdefault(entity, [])
            body = op.get("payload") or {}
            key = _key_of(body, payload)
            existing = next((r for r in rows if key and r.get(key) == body.get(key)), None)
            if existing:
                existing.update(body)
            else:
                rows.append(dict(body))
        entity = ops[0].get("entity") or payload.get("entity_set", "")
        return {"status": "OK", "total_operations": len(ops),
                "live_state": [dict(r) for r in sap.collections.get(entity, [])]}

    from jidoka_adapters.mocksap import fixtures

    c = Connector("mock", fetch, apply_fn, system_id,
                  metadata_xml=lambda: fixtures.METADATA_XML)
    c.mock = sap          # inspectable from tests; nothing in the request path reads it
    return c


def _live(system_id: str, product: str, base_url: str, secret_env: str) -> Connector:
    """Live OData. `secret_env` names the environment prefix holding the credential; the value
    is read here and nowhere else, and its absence is reported by variable name only."""
    if product == "SuccessFactors":
        need = (f"{secret_env}_CLIENT_ID", f"{secret_env}_ASSERTION")
    elif product == "S4HANA":
        need = (f"{secret_env}_CLIENT_ID", f"{secret_env}_CLIENT_SECRET", f"{secret_env}_TOKEN_URL")
    else:
        raise ConnectorError(f"No live connector implemented for product {product!r}.")
    missing = [v for v in need if not os.environ.get(v)]
    if missing:
        raise ConnectorError(
            f"{system_id}: cannot bind a live connector — {', '.join(missing)} is not set in this "
            f"process. Vault the credential and set it in the deployment, never in the request.")

    if product == "SuccessFactors":
        from jidoka_adapters.successfactors.odata import SFODataClient

        client = SFODataClient(base_url, system_id, os.environ[need[0]], os.environ[need[1]])
        fetch = client.fetcher()

        def metadata_xml():
            """The raw EDMX. The client's own metadata() returns SchemaTwin's shape; a harvest
            needs the document itself, so this rides the same authenticated request rather than
            adding a second way to reach a customer's tenant."""
            status, _h, raw = client.request(
                "GET", f"{client.base_url}/odata/v2/$metadata", {"Accept": "application/xml"})
            if status != 200:
                raise ConnectorError(f"{system_id}: $metadata fetch failed with HTTP {status}.")
            return raw

        def apply_fn(payload):
            # SF's own loader, not S/4's: SF upserts POST to /odata/v2/upsert and name the entity
            # in an X-Entity header, where S/4 posts to the entity's own URL. Borrowing S/4's
            # builder produced a body SF rejects, and — worse — one whose reply was never parsed,
            # so a half-landed changeset was reported as a clean success.
            # No retry layer: a failed write is a ledger event, not a silent second attempt
            # against a customer's tenant.
            from jidoka_adapters.successfactors.loader import BatchError, BatchLoader

            try:
                out = BatchLoader(client).apply(payload["operations"], dry_run=False,
                                                base_url=client.base_url)
            except BatchError as exc:
                raise ConnectorError(f"{system_id}: {exc}") from None
            return {"status": out["status"], "total_operations": len(payload["operations"]),
                    "failed_operations": len(out["errors"]), "errors": out["errors"],
                    "live_state": _read_back(fetch, system_id, payload)}
    else:
        from jidoka_adapters.s4hana import SERVICES
        from jidoka_adapters.s4hana.odata import S4ODataClient

        client = S4ODataClient(base_url, client_id=os.environ[need[0]],
                               client_secret=os.environ[need[1]], token_url=os.environ[need[2]])
        fetch = client.fetcher(lambda e: SERVICES.get(e, e))

        def metadata_xml(service: str = "API_COSTCENTER_SRV"):
            """S/4 publishes one $metadata per service, so a harvest names the service it wants.
            Defaulting to one rather than walking all of SERVICES keeps a harvest a bounded read
            against a customer's system; the caller asks again for another service."""
            status, _h, raw = client.request(
                "GET", client.service_url(service, "$metadata"), {"Accept": "application/xml"})
            if status != 200:
                raise ConnectorError(f"{system_id}: $metadata fetch failed with HTTP {status}.")
            return raw

        def apply_fn(payload):
            service = payload.get("service") or SERVICES.get(payload.get("entity_set", ""), "")
            if not service:
                raise ConnectorError(
                    f"{system_id}: no OData service is declared for {payload.get('entity_set')!r}. "
                    f"Refusing to guess a service URL.")
            out = client.batch(service, payload["operations"], dry_run=False)
            # client.batch hands back the raw per-part replies. The executor's partial-batch guard
            # reads a count, so the count is produced here — otherwise a changeset that half-landed
            # verifies one record, finds it, and calls the whole step VERIFIED.
            failed = [r for r in out.get("results", []) if not 200 <= r.get("status", 0) < 300]
            return {**out, "total_operations": len(payload["operations"]),
                    "failed_operations": len(failed), "errors": failed,
                    "live_state": _read_back(fetch, system_id, payload)}

    return Connector("live", fetch, apply_fn, f"{product} @ {system_id}", metadata_xml=metadata_xml)


def build(kind: str, system_id: str, product: str, registry: SystemRegistry,
          base_url: str = "", secret_env: str = "") -> Connector:
    """Construct a connector, refusing anything invariant 3 forbids.

    A connector IS a write credential. Binding one to a SOURCE_LEGACY or TWIN system would put a
    write path exactly where the registry says none may exist, so the check runs here as well as
    at arm time — binding is the earlier moment, and the earlier refusal is the kinder one.
    """
    registry.assert_writable(system_id)
    if kind == "mock":
        return _mock(system_id)
    if kind == "live":
        if not base_url or not secret_env:
            raise ConnectorError(
                "A live connector needs a base_url and the name of the environment variable "
                "prefix holding its credential.")
        return _live(system_id, product, base_url, secret_env)
    raise ConnectorError(f"Unknown connector kind {kind!r} — known kinds are 'mock' and 'live'.")


def build_reader(kind: str, system_id: str, product: str, registry: SystemRegistry,
                 base_url: str = "", secret_env: str = "") -> Connector:
    """A binding that can read a system and cannot write to it.

    Harvesting a legacy system's structure is the point of harvesting at all (ADR-0012), and a
    SOURCE_LEGACY system can never be writable — so `build` refuses it, correctly. The answer is
    not to relax that check but to bind something with no write half: `apply` here does not
    dispatch, it refuses, so invariant 3 holds by the shape of the object rather than by a caller
    remembering not to call it.

    registry.get() still runs: an unregistered system has no binding of any kind.
    """
    registry.get(system_id)
    if kind == "mock":
        c = _mock(system_id)
    elif kind == "live":
        if not base_url or not secret_env:
            raise ConnectorError(
                "A live reader needs a base_url and the name of the environment variable "
                "prefix holding its credential.")
        c = _live(system_id, product, base_url, secret_env)
    else:
        raise ConnectorError(f"Unknown connector kind {kind!r} — known kinds are 'mock' and 'live'.")

    def refuse(payload):
        raise ConnectorError(f"{system_id} is bound read-only — this binding has no write path.")

    # Overwriting `apply` on the write-capable connector is not enough: the client it closes over
    # stays reachable through every other attribute the object carries (_mock hangs the MockSAP on
    # `.mock`, and a live client's own methods would ride along the same way). A reader is a new,
    # smaller object holding only the halves that read — the write path is not refused, it is absent.
    return Connector(f"{c.kind}-read", c.fetch, refuse, c.describe, metadata_xml=c.metadata_xml)

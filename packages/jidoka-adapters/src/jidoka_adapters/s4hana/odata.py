"""S/4HANA OData v2/v4 client — stdlib only, transport injected so every test runs offline.
Secrets (password, client_secret, token, CSRF token) never appear in logs, reprs or exceptions:
a leaked bearer is a live write credential, and invariant 3 only holds if credentials stay
where they were vaulted. S/4 additionally guards every modifying call with a CSRF token, so a
leaked token pair is a leaked write path — it is held in a private attribute and never rendered."""
import base64
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from ..base import AdapterError

EDM_V2_NS = "{http://schemas.microsoft.com/ado/2008/09/edm}"
EDM_V4_NS = "{http://docs.oasis-open.org/odata/ns/edm}"
BOUNDARY = "batch_jidoka_s4"
CHANGESET = "changeset_jidoka_s4"


class S4ODataError(AdapterError): ...


def urllib_transport(method: str, url: str, headers: dict, body: bytes | None = None,
                     timeout: float = 60.0) -> tuple[int, dict, bytes]:
    """Default transport. Injectable so fixtures replace it wholesale in tests."""
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:  # a 4xx body carries the OData error detail we need
        return e.code, dict(e.headers or {}), e.read()


class S4ODataClient:
    """One client per system. `transport` is callable(method, url, headers, body) -> (status, headers, bytes).

    Auth is either basic (username/password — the classic S/4 communication user) or OAuth
    client-credentials against an XSUAA/IAS token endpoint. Whichever is configured, the
    credential material lives only in private attributes.
    """

    def __init__(self, base_url: str, username: str | None = None, password: str | None = None,
                 client_id: str | None = None, client_secret: str | None = None,
                 token_url: str | None = None, sap_client: str | None = None,
                 odata_version: str = "v2", transport=urllib_transport, clock=time.time,
                 token_skew: float = 60.0):
        if not (username or client_id):
            raise S4ODataError("No credential configured — supply basic or client-credentials auth.")
        if client_id and not token_url:
            raise S4ODataError("client-credentials auth needs a token_url.")
        self.base_url = base_url.rstrip("/")
        self.sap_client = sap_client
        self.odata_version = odata_version
        self._username = username
        self._password = password
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._transport = transport
        self._clock = clock
        self._skew = token_skew
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self._csrf: str | None = None
        self._cookies: str | None = None

    def __repr__(self) -> str:  # never render credentials
        who = f"user={self._username}" if self._username else f"client_id={self._client_id}"
        return f"<S4ODataClient {self.base_url} {who} client={self.sap_client}>"

    __str__ = __repr__

    def service_url(self, service: str, path: str = "") -> str:
        """/sap/opu/odata/sap/<SERVICE> (v2) or /sap/opu/odata4/sap/<SERVICE> (v4)."""
        root = "odata" if self.odata_version == "v2" else "odata4"
        url = f"{self.base_url}/sap/opu/{root}/sap/{service.strip('/')}"
        return f"{url}/{path.lstrip('/')}" if path else url

    # --- auth ---------------------------------------------------------------
    def token(self) -> str:
        """Cached OAuth client-credentials bearer. Refreshes only when expired (minus skew)."""
        if self._token and self._clock() < self._token_expiry - self._skew:
            return self._token
        body = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }).encode()
        status, _h, raw = self._transport(
            "POST", self._token_url,
            {"Content-Type": "application/x-www-form-urlencoded"}, body)
        if status != 200:
            raise S4ODataError(f"Token request failed: HTTP {status}")  # body may echo the secret
        data = json.loads(raw)
        if "access_token" not in data:
            raise S4ODataError("Token response carried no access_token")
        self._token = data["access_token"]
        self._token_expiry = self._clock() + float(data.get("expires_in", 3600))
        return self._token

    def _auth_headers(self, extra: dict | None = None) -> dict:
        if self._client_id:
            h = {"Authorization": f"Bearer {self.token()}"}
        else:
            raw = f"{self._username}:{self._password or ''}".encode()
            h = {"Authorization": "Basic " + base64.b64encode(raw).decode()}
        h["Accept"] = "application/json"
        if self.sap_client:
            h["sap-client"] = self.sap_client
        if self._cookies:
            h["Cookie"] = self._cookies
        h.update(extra or {})
        return h

    # --- CSRF ---------------------------------------------------------------
    def fetch_csrf(self, service: str) -> None:
        """HEAD with X-CSRF-Token: Fetch. The token and its session cookies are kept private;
        S/4 rejects a write that presents one without the other, so both are stored together."""
        status, headers, _raw = self._transport(
            "HEAD", self.service_url(service), self._auth_headers({"X-CSRF-Token": "Fetch"}))
        if status >= 400:
            raise S4ODataError(f"CSRF fetch failed: HTTP {status}")
        token = next((v for k, v in headers.items() if k.lower() == "x-csrf-token"), None)
        if not token:
            raise S4ODataError("CSRF fetch returned no x-csrf-token header")
        self._csrf = token
        cookie = next((v for k, v in headers.items() if k.lower() == "set-cookie"), None)
        if cookie:
            self._cookies = cookie.split(";")[0]

    def _write_headers(self, service: str, extra: dict | None = None) -> dict:
        if self._csrf is None:
            self.fetch_csrf(service)
        return self._auth_headers({"X-CSRF-Token": self._csrf, **(extra or {})})

    def request(self, method: str, url: str, headers: dict | None = None,
                body: bytes | None = None) -> tuple[int, dict, bytes]:
        """Authenticated raw request (reads). Writes go through write()/batch()."""
        return self._transport(method, url, self._auth_headers(headers), body)

    def write(self, method: str, service: str, path: str, payload: dict | None = None,
              headers: dict | None = None) -> tuple[int, dict, bytes]:
        """Modifying call: CSRF is fetched first if unheld, and re-fetched once on a 403
        'CSRF token validation failed' — S/4 expires tokens with the session, not the clock."""
        body = json.dumps(payload, sort_keys=True, default=str).encode() if payload is not None else None
        extra = {"Content-Type": "application/json", **(headers or {})}
        url = self.service_url(service, path)
        status, h, raw = self._transport(method, url, self._write_headers(service, extra), body)
        if status == 403 and b"CSRF" in raw.upper():
            self._csrf = None
            status, h, raw = self._transport(method, url, self._write_headers(service, extra), body)
        return status, h, raw

    # --- reads --------------------------------------------------------------
    def read_entity(self, service: str, entity_set: str, top: int = 500,
                    params: dict | None = None, max_pages: int = 10_000) -> list[dict]:
        """Paged read, v2 (`d.results` / `__next`) and v4 (`value` / `@odata.nextLink`) alike."""
        q = {"$format": "json", "$top": str(top), **(params or {})}
        url = f"{self.service_url(service, entity_set)}?{urllib.parse.urlencode(q)}"
        rows, skip, pages, server_paged = [], 0, 0, False
        while url and pages < max_pages:
            status, _h, raw = self._transport("GET", url, self._auth_headers())
            if status != 200:
                raise S4ODataError(f"Read {entity_set} failed: HTTP {status}")
            doc = json.loads(raw)
            d = doc.get("d", doc)
            batch = d.get("results", doc.get("value", [])) if isinstance(d, dict) else d
            rows.extend(batch)
            pages += 1
            nxt = doc.get("@odata.nextLink") or (d.get("__next") if isinstance(d, dict) else None)
            if nxt:  # server drives paging: trust it, and trust its absence to mean done
                server_paged = True
                url = nxt if nxt.startswith("http") else f"{self.base_url}/{nxt.lstrip('/')}"
            elif server_paged:
                url = None
            elif len(batch) == top:
                skip += top
                url = (f"{self.service_url(service, entity_set)}?"
                       f"{urllib.parse.urlencode({**q, '$skip': str(skip)})}")
            else:
                url = None
        return rows

    def metadata(self, service: str) -> dict:
        status, _h, raw = self._transport(
            "GET", self.service_url(service, "$metadata"),
            self._auth_headers({"Accept": "application/xml"}))
        if status != 200:
            raise S4ODataError(f"$metadata fetch failed: HTTP {status}")
        return parse_metadata(raw)

    def fetcher(self, service_of):
        """Adapter-shaped callable(system, entity) -> rows. `service_of` maps entity -> service name."""
        return lambda system, entity: self.read_entity(service_of(entity), entity)

    # --- $batch -------------------------------------------------------------
    def batch(self, service: str, operations: list[dict], dry_run: bool = True) -> dict:
        """Tier-A $batch. dry_run is the default (invariant 6): it builds and validates the
        multipart body and touches no transport."""
        body = build_batch(operations, self.service_url(service))
        if dry_run:
            return {"dry_run": True, "status": "DRY_RUN", "batch": body,
                    "operations": len(operations)}
        status, _h, raw = self._transport(
            "POST", self.service_url(service, "$batch"),
            self._write_headers(service, {"Content-Type": f"multipart/mixed; boundary={BOUNDARY}"}),
            body.encode())
        if status >= 400:
            raise S4ODataError(f"$batch transport failed: HTTP {status}")
        return {"dry_run": False, "status": "OK", "batch": body,
                "results": parse_batch_response(raw)}


def build_batch(operations: list[dict], service_url: str = "") -> str:
    """multipart/mixed body: one changeset holding every operation."""
    if not operations:
        raise S4ODataError("Refusing to build an empty $batch.")
    parts = [f"--{BOUNDARY}", f"Content-Type: multipart/mixed; boundary={CHANGESET}", ""]
    for i, op in enumerate(operations, 1):
        entity = op["entity"]
        if not op.get("payload"):
            raise S4ODataError(f"Operation {i} ({entity}) has an empty payload.")
        method = {"UPSERT": "POST", "CREATE": "POST"}.get(op.get("method", "UPSERT"),
                                                          op.get("method", "POST"))
        body = json.dumps(op["payload"], sort_keys=True, default=str)
        url = f"{service_url.rstrip('/')}/{entity}" if service_url else entity
        parts += [f"--{CHANGESET}", "Content-Type: application/http",
                  "Content-Transfer-Encoding: binary", f"Content-ID: {i}", "",
                  f"{method} {url} HTTP/1.1",
                  "Content-Type: application/json", "Accept: application/json", "", body, ""]
    parts += [f"--{CHANGESET}--", "", f"--{BOUNDARY}--", ""]
    return "\r\n".join(parts)


def parse_batch_response(raw: bytes | str) -> list[dict]:
    """multipart response -> per-part {status, body}. Order matches the requested operations."""
    import re
    text = raw.decode() if isinstance(raw, bytes) else raw
    results = []
    for m in re.finditer(r"HTTP/1\.1 (\d{3})[^\r\n]*\r?\n(.*?)(?=\r?\n--|\Z)", text, re.S):
        rest = m.group(2)
        body = rest.split("\r\n\r\n", 1)[-1] if "\r\n\r\n" in rest else rest.split("\n\n", 1)[-1]
        body = body.strip()
        parsed = None
        if body:
            try:
                parsed = json.loads(body)
            except ValueError:
                parsed = body
        results.append({"status": int(m.group(1)), "body": parsed})
    if not results:
        raise S4ODataError("No embedded responses found in $batch reply.")
    return results


def parse_metadata(raw: bytes | str) -> dict:
    """$metadata XML -> the shape SchemaTwin expects. Handles v2 and v4 EDM namespaces."""
    root = ET.fromstring(raw)
    out: dict[str, dict] = {}
    for ns in (EDM_V2_NS, EDM_V4_NS):
        for et in root.iter(f"{ns}EntityType"):
            fields = {}
            for prop in et.findall(f"{ns}Property"):
                fields[prop.get("Name")] = {
                    "type": prop.get("Type"),
                    "required": prop.get("Nullable", "true").lower() == "false",
                    "picklist": None,  # S/4 value helps live in the annotations, not the property
                }
            out[et.get("Name")] = {"fields": fields}
    return out

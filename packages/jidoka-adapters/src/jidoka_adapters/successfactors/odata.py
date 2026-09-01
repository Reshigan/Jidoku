"""SuccessFactors OData v2 client — stdlib only, transport injected so every test runs offline.
Secrets (assertion, client_id, token) never appear in logs, reprs or exceptions: a leaked bearer
is a live write credential, and invariant 3 only holds if credentials stay where they were vaulted."""
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from ..base import AdapterError

EDM_NS = "{http://schemas.microsoft.com/ado/2008/09/edm}"
SF_NS = "{http://www.successfactors.com/edm/sf}"


class ODataError(AdapterError): ...


def urllib_transport(method: str, url: str, headers: dict, body: bytes | None = None,
                     timeout: float = 60.0) -> tuple[int, dict, bytes]:
    """Default transport. Injectable so fixtures replace it wholesale in tests."""
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:  # a 4xx body carries the OData error detail we need
        return e.code, dict(e.headers or {}), e.read()


class SFODataClient:
    """One client per system. `transport` is callable(method, url, headers, body) -> (status, headers, bytes)."""

    def __init__(self, base_url: str, company_id: str, client_id: str, assertion: str,
                 transport=urllib_transport, clock=time.time, token_skew: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.company_id = company_id
        self._client_id = client_id
        self._assertion = assertion
        self._transport = transport
        self._clock = clock
        self._skew = token_skew
        self._token: str | None = None
        self._token_expiry: float = 0.0

    def __repr__(self) -> str:  # never render credentials
        return f"<SFODataClient {self.base_url} company={self.company_id}>"

    # --- auth ---------------------------------------------------------------
    def token(self) -> str:
        """Cached OAuth SAML bearer. Refreshes only when expired (minus skew)."""
        if self._token and self._clock() < self._token_expiry - self._skew:
            return self._token
        body = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:saml2-bearer",
            "company_id": self.company_id,
            "client_id": self._client_id,
            "assertion": self._assertion,
        }).encode()
        status, _h, raw = self._transport(
            "POST", f"{self.base_url}/oauth/token",
            {"Content-Type": "application/x-www-form-urlencoded"}, body)
        if status != 200:
            raise ODataError(f"Token request failed: HTTP {status}")  # body may echo the assertion
        data = json.loads(raw)
        if "access_token" not in data:
            raise ODataError("Token response carried no access_token")
        self._token = data["access_token"]
        self._token_expiry = self._clock() + float(data.get("expires_in", 3600))
        return self._token

    def _auth_headers(self, extra: dict | None = None) -> dict:
        h = {"Authorization": f"Bearer {self.token()}", "Accept": "application/json"}
        h.update(extra or {})
        return h

    def request(self, method: str, url: str, headers: dict | None = None,
                body: bytes | None = None) -> tuple[int, dict, bytes]:
        """Authenticated raw request — the loader rides this for $batch."""
        return self._transport(method, url, self._auth_headers(headers), body)

    # --- metadata -----------------------------------------------------------
    def metadata(self) -> dict:
        status, _h, raw = self._transport(
            "GET", f"{self.base_url}/odata/v2/$metadata",
            self._auth_headers({"Accept": "application/xml"}))
        if status != 200:
            raise ODataError(f"$metadata fetch failed: HTTP {status}")
        return parse_metadata(raw)

    # --- reads --------------------------------------------------------------
    def read_entity(self, entity: str, top: int = 500, params: dict | None = None,
                    max_pages: int = 10_000) -> list[dict]:
        """Paged read. Follows __next when the server gives it, else walks $skip until short page."""
        q = {"$format": "json", "$top": str(top), **(params or {})}
        url = f"{self.base_url}/odata/v2/{entity}?{urllib.parse.urlencode(q)}"
        rows, skip, pages, server_paged = [], 0, 0, False
        while url and pages < max_pages:
            status, _h, raw = self._transport("GET", url, self._auth_headers())
            if status != 200:
                raise ODataError(f"Read {entity} failed: HTTP {status}")
            d = json.loads(raw).get("d", {})
            batch = d.get("results", d if isinstance(d, list) else [])
            rows.extend(batch)
            pages += 1
            nxt = d.get("__next") if isinstance(d, dict) else None
            if nxt:  # server drives paging: trust it, and trust its absence to mean done
                server_paged = True
                url = nxt if nxt.startswith("http") else f"{self.base_url}/{nxt.lstrip('/')}"
            elif server_paged:
                url = None
            elif len(batch) == top:
                skip += top
                url = f"{self.base_url}/odata/v2/{entity}?{urllib.parse.urlencode({**q, '$skip': str(skip)})}"
            else:
                url = None
        return rows

    def fetcher(self):
        """Adapter-shaped callable(system, entity) -> rows, for SFAdapter(fetch=...)."""
        return lambda system, entity: self.read_entity(entity)


def parse_metadata(raw: bytes | str) -> dict:
    """$metadata XML -> the shape SchemaTwin expects.
    Picklist comes from SF's sf:picklist annotation; Nullable="false" means required."""
    root = ET.fromstring(raw)
    out: dict[str, dict] = {}
    for et in root.iter(f"{EDM_NS}EntityType"):
        fields = {}
        for prop in et.findall(f"{EDM_NS}Property"):
            name = prop.get("Name")
            fields[name] = {
                "type": prop.get("Type"),
                "required": prop.get("Nullable", "true").lower() == "false",
                "picklist": prop.get(f"{SF_NS}picklist") or prop.get("sf:picklist"),
            }
        out[et.get("Name")] = {"fields": fields}
    return out

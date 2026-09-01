"""In-memory SAP OData v2 double. Stdlib only.

Drops into SFODataClient (and any S/4 client using the same contract) as `transport`:
    callable(method, url, headers, body=None, timeout=60.0) -> (status, headers, bytes)

The point of this file is the failure modes, not the happy path. A real SAP write goes wrong
mid-batch and leaves a partial state; JIDOKA must be able to tell what actually landed, so
`fail_batch_at` commits the operations before the failure point and rejects the rest — exactly
what a changeset that does not roll back does in the field.
"""
import json
import re
import urllib.parse
import uuid

from . import fixtures

CSRF_TOKEN = "csrf-mock-0001"


class MockTimeout(Exception):
    """Raised *from the transport* — the client sees a socket-level failure, not an HTTP status."""


class MockSAP:
    """One instance per test. Mutable, inspectable: assert against `.collections` after a write."""

    def __init__(self, base_url: str = "https://api.example.com", token_ttl: float = 3600.0,
                 expire_token_after: int | None = None, require_csrf: bool = False):
        self.base_url = base_url.rstrip("/")
        self.collections = fixtures.seed()
        self.calls: list[dict] = []
        self.token_ttl = token_ttl
        self.require_csrf = require_csrf
        self._tokens: set[str] = set()
        self._issued = 0
        # failure injection state
        self._queued: list = []            # one-shot responses / raisers
        self._expire_after = expire_token_after  # nth authed call with a live token -> 401
        self._authed_calls = 0
        self._fail_batch_at: int | None = None
        self._batch_fail_status = 500

    # --- failure injection --------------------------------------------------
    def fail_next(self, status: int, body: bytes | str = b"", headers: dict | None = None) -> None:
        """Next request gets this response verbatim, whatever it asked for."""
        if isinstance(body, str):
            body = body.encode()
        self._queued.append((status, dict(headers or {}), body))

    def fail_next_rate_limited(self, retry_after: int = 30) -> None:
        self.fail_next(429, json.dumps({"error": {"message": "Too Many Requests"}}),
                       {"Retry-After": str(retry_after)})

    def fail_next_timeout(self) -> None:
        """Transport raises instead of returning — the network-timeout path."""
        self._queued.append(MockTimeout("mock SAP: read timed out"))

    def expire_token(self) -> None:
        """Invalidate every issued bearer: the next authed call 401s and the client must re-auth."""
        self._tokens.clear()

    def expire_token_after(self, n: int) -> None:
        """401 the nth authenticated call from now, then keep serving. Exercises re-auth mid-flow."""
        self._expire_after = n
        self._authed_calls = 0

    def fail_batch_at(self, index: int, status: int = 500) -> None:
        """Mid-batch failure: 1-based operation `index` and everything after it fail; earlier
        operations stay committed. This is the partial-application case."""
        self._fail_batch_at = index
        self._batch_fail_status = status

    def reset_failures(self) -> None:
        self._queued.clear()
        self._fail_batch_at = None
        self._expire_after = None

    # --- transport ----------------------------------------------------------
    def __call__(self, method: str, url: str, headers: dict, body: bytes | None = None,
                 timeout: float = 60.0):
        self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": body})
        if self._queued:
            q = self._queued.pop(0)
            if isinstance(q, Exception):
                raise q
            return q
        path = urllib.parse.urlsplit(url).path
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)

        if path.endswith("/oauth/token") or path.endswith("/oauth/saml"):
            return self._issue_token(body)

        auth = self._check_auth(headers)
        if auth:
            return auth

        if path.endswith("/$metadata"):
            return 200, {"Content-Type": "application/xml"}, fixtures.METADATA_XML.encode()
        if path.endswith("/$batch"):
            return self._batch(headers, body or b"")

        entity = path.rstrip("/").rsplit("/", 1)[-1]
        if method == "GET":
            return self._get(entity, query)
        if method in ("POST", "PUT", "MERGE", "PATCH"):
            csrf = self._check_csrf(headers)
            if csrf:
                return csrf
            return self._upsert(entity, body, method)
        return self._error(405, f"Method {method} not allowed")

    # --- auth ---------------------------------------------------------------
    def _issue_token(self, body: bytes | None):
        form = urllib.parse.parse_qs((body or b"").decode())
        if "assertion" not in form and "client_secret" not in form:
            return self._error(400, "invalid_grant: no assertion")
        self._issued += 1
        tok = f"mock-bearer-{self._issued}"
        self._tokens.add(tok)
        return 200, {"Content-Type": "application/json"}, json.dumps(
            {"access_token": tok, "token_type": "Bearer", "expires_in": int(self.token_ttl)}).encode()

    def _check_auth(self, headers: dict):
        raw = headers.get("Authorization") or headers.get("authorization") or ""
        tok = raw[7:] if raw.lower().startswith("bearer ") else None
        if tok not in self._tokens:
            return self._unauthorized()
        self._authed_calls += 1
        if self._expire_after is not None and self._authed_calls >= self._expire_after:
            self._expire_after = None
            self._tokens.clear()  # forces the client through the token endpoint again
            return self._unauthorized()
        return None

    def _unauthorized(self):
        return (401, {"WWW-Authenticate": "Bearer"},
                json.dumps({"error": {"code": "AUTH.EXPIRED",
                                      "message": "Token expired or invalid"}}).encode())

    def _check_csrf(self, headers: dict):
        """S/4 fetch-then-write: a write without the token the server handed out is rejected."""
        if not self.require_csrf:
            return None
        got = next((v for k, v in headers.items() if k.lower() == "x-csrf-token"), None)
        if got == "Fetch":
            return self._error(403, "CSRF token fetch is a GET, not a write")
        if got != CSRF_TOKEN:
            return (403, {"X-CSRF-Token": "Required"},
                    json.dumps({"error": {"code": "CSRF", "message": "CSRF token validation failed"}}).encode())
        return None

    # --- reads --------------------------------------------------------------
    def _get(self, entity: str, query: dict):
        if entity not in self.collections:
            return self._error(404, f"Resource not found for the segment '{entity}'")
        rows = [dict(r) for r in self.collections[entity]]
        flt = (query.get("$filter") or [None])[0]
        if flt:
            rows = [r for r in rows if _matches(r, flt)]
        if (sel := (query.get("$select") or [None])[0]):
            keep = [f.strip() for f in sel.split(",")]
            rows = [{k: v for k, v in r.items() if k in keep} for r in rows]
        skip = int((query.get("$skip") or [0])[0])
        top = int((query.get("$top") or [len(rows) or 1])[0])
        page = rows[skip:skip + top]
        d: dict = {"results": page}
        if skip + top < len(rows):  # server-driven paging, like SF does
            d["__next"] = f"{self.base_url}/odata/v2/{entity}?$top={top}&$skip={skip + top}"
        headers = {"Content-Type": "application/json", "X-CSRF-Token": CSRF_TOKEN}
        return 200, headers, json.dumps({"d": d}).encode()

    # --- writes -------------------------------------------------------------
    def _upsert(self, entity: str, body: bytes | None, method: str = "POST"):
        try:
            payload = json.loads((body or b"").decode() or "{}")
        except ValueError:
            return self._error(400, "Malformed JSON payload")
        if entity == "upsert":  # SF's /odata/v2/upsert endpoint carries __metadata.uri
            entity = _entity_from_metadata(payload) or ""
        if entity not in self.collections:
            return self._error(404, f"Unknown entity set '{entity}'")
        key = fixtures.KEYS[entity]
        if key not in payload:
            return self._error(400, f"Missing key property '{key}'")
        rows = self.collections[entity]
        existing = next((r for r in rows if r.get(key) == payload[key]), None)
        if existing is None:
            rows.append({k: v for k, v in payload.items() if k != "__metadata"})
            status, index = 201, "CREATED"
        else:
            # PUT replaces, POST/MERGE/PATCH merges — SF's upsert is a merge
            if method == "PUT":
                existing.clear()
            existing.update({k: v for k, v in payload.items() if k != "__metadata"})
            status, index = 200, "UPDATED"
        return status, {"Content-Type": "application/json"}, json.dumps(
            {"d": {"key": payload[key], "status": "OK", "index": index,
                   "editStatus": index, "message": None}}).encode()

    # --- $batch -------------------------------------------------------------
    def _batch(self, headers: dict, body: bytes):
        csrf = self._check_csrf(headers)
        if csrf:
            return csrf
        ops = _parse_batch_request(body.decode())
        if not ops:
            return self._error(400, "Empty $batch body")
        boundary = f"batchresponse_{uuid.uuid4().hex[:12]}"
        cs = f"changesetresponse_{uuid.uuid4().hex[:12]}"
        parts = [f"--{boundary}", f"Content-Type: multipart/mixed; boundary={cs}", ""]
        for i, op in enumerate(ops, 1):
            if self._fail_batch_at is not None and i >= self._fail_batch_at:
                # everything from here on is rejected; the prefix stays committed
                status, payload = self._batch_fail_status, {
                    "error": {"code": "SY/530", "message": {"value": "Update was terminated"}}}
            else:
                st, _h, raw = self._upsert(op["entity"], op["body"].encode(), op["method"])
                status, payload = st, json.loads(raw)
            parts += [f"--{cs}", "Content-Type: application/http",
                      "Content-Transfer-Encoding: binary", f"Content-ID: {op['content_id'] or i}", "",
                      f"HTTP/1.1 {status} {_reason(status)}",
                      "Content-Type: application/json", "", json.dumps(payload), ""]
        parts += [f"--{cs}--", "", f"--{boundary}--", ""]
        return (202, {"Content-Type": f"multipart/mixed; boundary={boundary}"},
                "\r\n".join(parts).encode())

    def _error(self, status: int, message: str):
        return (status, {"Content-Type": "application/json"},
                json.dumps({"error": {"code": str(status), "message": {"value": message}}}).encode())

    # --- inspection ---------------------------------------------------------
    def row(self, entity: str, key_value: str) -> dict | None:
        key = fixtures.KEYS[entity]
        return next((r for r in self.collections[entity] if r.get(key) == key_value), None)


# --- helpers ---------------------------------------------------------------
_FILTER = re.compile(r"(\w+)\s+(eq|ne)\s+'([^']*)'")


def _matches(row: dict, flt: str) -> bool:
    """$filter support: `field eq 'x'` clauses joined by and/or. ponytail: no full OData grammar
    — extend the regex if a test needs gt/lt or nested parens."""
    terms = _FILTER.findall(flt)
    if not terms:
        return True
    results = [(str(row.get(f)) == v) if op == "eq" else (str(row.get(f)) != v)
               for f, op, v in terms]
    return any(results) if re.search(r"\bor\b", flt, re.I) else all(results)


def _entity_from_metadata(payload: dict) -> str | None:
    uri = (payload.get("__metadata") or {}).get("uri", "")
    m = re.search(r"/([A-Za-z_]\w*)\(", uri) or re.search(r"/([A-Za-z_]\w*)$", uri)
    return m.group(1) if m else None


def _parse_batch_request(text: str) -> list[dict]:
    """Pull each embedded request out of a multipart/mixed $batch body."""
    ops = []
    for m in re.finditer(
            r"Content-ID:\s*(\S+)\r?\n(.*?)(?:\r?\n)(POST|PUT|MERGE|PATCH|GET) (\S+)[^\r\n]*\r?\n(.*?)(?=\r?\n--)",
            text, re.S):
        content_id, _pre, method, url, rest = m.groups()
        header_block, _, payload = rest.partition("\r\n\r\n")
        if not _:
            header_block, _, payload = rest.partition("\n\n")
        entity = _header(header_block, "X-Entity") or url.rstrip("/").rsplit("/", 1)[-1]
        ops.append({"content_id": content_id, "method": method, "url": url,
                    "entity": entity, "body": payload.strip()})
    return ops


def _header(block: str, name: str) -> str | None:
    for line in block.splitlines():
        k, _, v = line.partition(":")
        if k.strip().lower() == name.lower():
            return v.strip()
    return None


_REASONS = {200: "OK", 201: "Created", 202: "Accepted", 204: "No Content", 400: "Bad Request",
            401: "Unauthorized", 403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed",
            429: "Too Many Requests", 500: "Internal Server Error"}


def _reason(status: int) -> str:
    return _REASONS.get(status, "Unknown")

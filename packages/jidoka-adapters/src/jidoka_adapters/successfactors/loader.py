"""OData $batch loader for Tier-A upserts.
dry_run is the default (invariant 6): a dry run builds and validates the batch and touches no
transport. The applied-journal makes replay idempotent — a re-run after a partial failure retries
only what did not confirm, keyed by externalCode + payload hash, so a half-applied batch is safe
to resend rather than requiring a human to reconcile by hand."""
import hashlib
import json
import re
from ..base import AdapterError

BOUNDARY = "batch_jidoka"
CHANGESET = "changeset_jidoka"


class BatchError(AdapterError): ...


def op_key(op: dict) -> tuple[str, str]:
    """(externalCode, payload hash) — identity of an upsert for replay purposes."""
    payload = op["payload"]
    code = str(payload.get("externalCode", op.get("externalCode", "")))
    h = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return code, h


def build_batch(operations: list[dict], base_url: str = "") -> str:
    """multipart/mixed body: one changeset holding every upsert as an UPSERT (POST + method override)."""
    if not operations:
        raise BatchError("Refusing to build an empty $batch.")
    parts = [f"--{BOUNDARY}", f"Content-Type: multipart/mixed; boundary={CHANGESET}", ""]
    for i, op in enumerate(operations, 1):
        entity = op["entity"]
        if not op.get("payload"):
            raise BatchError(f"Operation {i} ({entity}) has an empty payload.")
        body = json.dumps(op["payload"], sort_keys=True, default=str)
        url = f"{base_url.rstrip('/')}/odata/v2/upsert" if base_url else "upsert"
        parts += [f"--{CHANGESET}", "Content-Type: application/http",
                  "Content-Transfer-Encoding: binary", f"Content-ID: {i}", "",
                  f"POST {url} HTTP/1.1", f"X-Entity: {entity}",
                  "Content-Type: application/json", "Accept: application/json", "", body, ""]
    parts += [f"--{CHANGESET}--", "", f"--{BOUNDARY}--", ""]
    return "\r\n".join(parts)


def parse_batch_response(raw: bytes | str) -> list[dict]:
    """multipart response -> per-part {status, body}. Order matches the requested operations."""
    text = raw.decode() if isinstance(raw, bytes) else raw
    results = []
    for m in re.finditer(r"HTTP/1\.1 (\d{3})[^\r\n]*\r?\n(.*?)(?=\r?\n--|\Z)", text, re.S):
        status = int(m.group(1))
        rest = m.group(2)
        # headers and body are separated by a blank line inside each embedded response
        body = rest.split("\r\n\r\n", 1)[-1] if "\r\n\r\n" in rest else rest.split("\n\n", 1)[-1]
        parsed = None
        body = body.strip()
        if body:
            try:
                parsed = json.loads(body)
            except ValueError:
                parsed = body
        results.append({"status": status, "body": parsed})
    if not results:
        raise BatchError("No embedded responses found in $batch reply.")
    return results


class BatchLoader:
    """journal: {externalCode: payload_hash} of confirmed-applied records, carried across runs."""

    def __init__(self, client=None, journal: dict | None = None):
        self._client = client
        self.journal: dict[str, str] = dict(journal or {})
        self.errors: list[dict] = []

    def pending(self, operations: list[dict]) -> list[dict]:
        return [op for op in operations if self.journal.get(op_key(op)[0]) != op_key(op)[1]]

    def apply(self, operations: list[dict], dry_run: bool = True, base_url: str = "") -> dict:
        pending = self.pending(operations)
        skipped = len(operations) - len(pending)
        if not pending:
            return {"dry_run": dry_run, "skipped": skipped, "applied": [], "errors": [],
                    "status": "NOOP", "batch": None}
        batch = build_batch(pending, base_url)
        if dry_run:
            return {"dry_run": True, "skipped": skipped, "applied": [], "errors": [],
                    "status": "DRY_RUN", "batch": batch, "operations": len(pending)}
        if self._client is None:
            raise BatchError("Live apply requested with no client — arm an explicit target first.")
        status, _h, raw = self._client.request(
            "POST", f"{self._client.base_url}/odata/v2/$batch",
            {"Content-Type": f"multipart/mixed; boundary={BOUNDARY}"}, batch.encode())
        if status >= 400:
            raise BatchError(f"$batch transport failed: HTTP {status}")
        results = parse_batch_response(raw)
        applied, errors = [], []
        for op, res in zip(pending, results):
            code, h = op_key(op)
            if 200 <= res["status"] < 300:
                self.journal[code] = h
                applied.append(code)
            else:
                errors.append({"externalCode": code, "entity": op["entity"],
                               "status": res["status"], "error": res["body"]})
        if len(results) < len(pending):  # truncated reply: the tail is unconfirmed, not applied
            for op in pending[len(results):]:
                errors.append({"externalCode": op_key(op)[0], "entity": op["entity"],
                               "status": None, "error": "no response part — unconfirmed, will replay"})
        self.errors.extend(errors)
        return {"dry_run": False, "skipped": skipped, "applied": applied, "errors": errors,
                "status": "OK" if not errors else "PARTIAL", "batch": batch}

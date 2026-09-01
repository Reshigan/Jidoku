"""HTTP client to the JIDOKA API — the agent's ONLY reach into the platform.

Role invariant #7: the agent is builder, never approver. approve() and resolve_dp() are
structurally absent here, not merely unused: there is no method on this class that can POST
to /ledger/approve or /decisions/{id}/resolve, so no prompt, jailbreak or bug can reach them.
Transport is injectable so tests run fully offline."""
import json, urllib.request
from typing import Any, Callable

BUILDER_ACTIONS = ("SNAPSHOT", "EXECUTED")  # evidence only; approval is a human ceremony
Transport = Callable[[str, str, Any], Any]  # (method, url, body) -> decoded json


def _urllib(method: str, url: str, body: Any) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, data=data,
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b"null")


class JidokaClient:
    """Builder-only API surface. Actor is fixed: the agent signs its own entries as itself."""

    ACTOR = "jidoka-agent"

    def __init__(self, base_url: str = "http://localhost:8000", transport: Transport = _urllib):
        self.base = base_url.rstrip("/")
        self._t = transport

    def _url(self, eid: str, suffix: str = "") -> str:
        return f"{self.base}/engagements/{eid}{suffix}"

    def load_ir(self, eid: str, records: list[dict]) -> Any:
        return self._t("POST", self._url(eid, "/ir"), records)

    def build_plan(self, eid: str) -> Any:
        return self._t("POST", self._url(eid, "/plan"), None)

    def ledger_append(self, eid: str, task: str, action: str, detail: str = "") -> Any:
        if action not in BUILDER_ACTIONS:  # trust boundary: refuse to smuggle an approval through append
            raise ValueError(f"agent may only append {BUILDER_ACTIONS}, not {action!r}")
        return self._t("POST", self._url(eid, "/ledger"),
                       {"task": task, "action": action, "actor": self.ACTOR, "detail": detail})

    def raise_dp(self, eid: str, dp_id: str, dp_type: str, question: str, owner: str) -> Any:
        return self._t("POST", self._url(eid, "/decisions"),
                       {"dp_id": dp_id, "dp_type": dp_type, "question": question, "owner": owner})

    def get_plan(self, eid: str) -> Any:
        return self._t("GET", self._url(eid, "/plan"), None)

    def get_ledger(self, eid: str) -> Any:
        return self._t("GET", self._url(eid, "/ledger"), None)

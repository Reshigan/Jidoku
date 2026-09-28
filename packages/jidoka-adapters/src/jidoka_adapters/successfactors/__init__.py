"""SuccessFactors adapter (reference implementation).
Extraction is injected (live OData client or fixture) so the core is testable offline;
apply is dry-run by default — nothing writes without an explicit armed target + ledger snapshot."""
from ..base import Adapter
from .odata import SFODataClient, ODataError
from .loader import BatchLoader
from . import importers
from .tiers import ENTITY_SETS, KEY_FIELDS, READ_ONLY_SETS, TIER_MAP, unverifiable

__all__ = ["SFAdapter", "SFODataClient", "BatchLoader", "importers",
           "ENTITY_SETS", "KEY_FIELDS", "READ_ONLY_SETS", "TIER_MAP"]

class SFAdapter(Adapter):
    product = "SuccessFactors"

    def __init__(self, fetch=None, client: SFODataClient | None = None):
        # callable(system, entity) -> list[dict]; a live client is just the fetcher it exposes
        self._fetch = fetch or (client.fetcher() if client else None)

    def tier_map(self) -> dict:
        """A = a real writable SFOData entity set (named in tiers.ENTITY_SETS).
        B = import file a human loads. C = Admin Center / Provisioning UI only.
        See tiers.py for the instance-vs-configuration honesty note."""
        return dict(TIER_MAP)

    def entity_set(self, entity: str) -> str | None:
        return ENTITY_SETS.get(entity)

    def write_target(self, entity: str) -> str | None:
        """The entity set an upsert goes to. None means SF publishes no write path for it."""
        return ENTITY_SETS.get(entity)

    def read_set(self, entity: str) -> str | None:
        """The entity set a verification reads. A writable set reads too; some sets only read."""
        return ENTITY_SETS.get(entity) or READ_ONLY_SETS.get(entity)

    def unverifiable(self) -> dict:
        return unverifiable()

    #: SuccessFactors keeps its own record of configuration and data changes, including role
    #: permission changes, and SAP positions it for exactly this question: detecting unexpected
    #: changes and identifying their source. Reading it back and reconciling it against the ledger
    #: is what turns a free feature of the product into the thing that closes this platform's
    #: blind spot (ADR-0044).
    #:
    #: The entity name below is the one this adapter asks its fetcher for. It has NOT been
    #: confirmed against a live tenant from this codebase, like everything else here, and the
    #: tier map's honesty rule applies: where the fetcher cannot produce it, `change_log` returns
    #: None and the reconciliation says it cannot see rather than that it found nothing.
    change_log_entity = "ChangeAudit"

    #: Change Audit's own field names -> the four this platform reconciles on. Every product
    #: spells its log differently, so the translation lives with the product.
    CHANGE_FIELDS = {"object": ("objectId", "entityName", "objectType", "externalCode"),
                     "changed_by": ("modifiedBy", "changedBy", "userId"),
                     "ts": ("modifiedDate", "changedOn", "timestamp", "lastModifiedDateTime"),
                     "detail": ("changeType", "operation", "description")}

    def change_log(self, system, since: str = "") -> list[dict] | None:
        if not self._fetch:
            return None
        try:
            rows = self._fetch(system, self.change_log_entity)
        except Exception:                    # noqa: BLE001 — a tenant that publishes no such set
            return None                      # is "cannot see", never "nothing happened"
        out = []
        for row in rows or []:
            got = {field: next((row[k] for k in keys if row.get(k) not in (None, "")), "")
                   for field, keys in self.CHANGE_FIELDS.items()}
            if since and got["ts"] and got["ts"] < since:
                continue
            out.append(got)
        return out

    def cannot_read_changes(self) -> str:
        return ("SuccessFactors publishes a Change Audit report, and nothing in this engagement "
                "produced it. Either no connector is bound, or this tenant does not expose the "
                "set this adapter asks for — which is a different thing from no change having "
                "been made outside the platform.")

    def key_field(self, entity: str) -> str:
        return KEY_FIELDS.get(entity, "externalCode")

    def extract(self, system, entity: str) -> list[dict]:
        if not self._fetch:
            raise RuntimeError("No fetcher configured — inject live OData client or fixture.")
        return self._fetch(system, entity)

    def build_apply(self, ir) -> dict:
        tier = ir.tier
        if tier == "A":
            entity_set = ENTITY_SETS.get(ir.object)
            if not entity_set:
                raise ODataError(
                    f"{ir.object} is tier A but no SF OData entity set is declared for it — "
                    f"the tier_map is lying, fix it rather than guessing a URL.")
            return {"kind": "odata_batch", "system": ir.system_binding, "dry_run": True,
                    "entity_set": entity_set,
                    # An UPSERT is only an upsert if the substrate can tell which record it means.
                    # EmpJob is keyed by userId, not externalCode, so the key field travels with
                    # the payload rather than being guessed at the far end.
                    "key_field": self.key_field(ir.object),
                    "operations": [{"method": "UPSERT", "entity": entity_set, "payload": ir.intent}]}
        if tier == "B":
            return {"kind": "import_file", "system": ir.system_binding,
                    "artefact": {"entity": ir.object, "rows": [ir.intent]},
                    "human_step": f"Import via Import & Export Data -> {ir.object} (Incremental). "
                                  f"Ledger checkpoint required before and after."}
        return {"kind": "instruction_sheet", "system": ir.system_binding,
                "steps": [f"1. Capture before-state export of {ir.object} (snapshot to ledger).",
                          f"2. Apply {ir.object} change per attached spec: {ir.intent}",
                          "3. JIDOKA re-extracts and diffs; do not proceed until diff report is green."]}

    @staticmethod
    def diff(before: list[dict], after: list[dict], key: str = "externalCode") -> dict:
        b = {r[key]: r for r in before if key in r}
        a = {r[key]: r for r in after if key in r}
        added = sorted(set(a) - set(b)); removed = sorted(set(b) - set(a))
        changed = {}
        for k in set(a) & set(b):
            delta = {f: {"before": b[k].get(f), "after": a[k].get(f)}
                     for f in set(b[k]) | set(a[k]) if b[k].get(f) != a[k].get(f)}
            if delta: changed[k] = delta
        return {"added": added, "removed": removed, "changed": changed,
                "clean": not (added or removed or changed)}

    def verify(self, ir, live_state: list[dict]) -> dict:
        field = self.key_field(ir.object)  # EmpJob is keyed by userId, not externalCode
        key = ir.intent.get(field)
        live = next((r for r in live_state if r.get(field) == key), None)
        if live is None:
            return {"status": "MISSING", "key": key, "key_field": field}
        drift = {f: {"intent": v, "live": live.get(f)} for f, v in ir.intent.items()
                 if not isinstance(v, dict) and live.get(f) != v}
        return {"status": "MATCH" if not drift else "DRIFT", "key": key, "key_field": field,
                "drift": drift}

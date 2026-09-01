"""SuccessFactors adapter (reference implementation).
Extraction is injected (live OData client or fixture) so the core is testable offline;
apply is dry-run by default — nothing writes without an explicit armed target + ledger snapshot."""
from ..base import Adapter
from .odata import SFODataClient, ODataError
from .loader import BatchLoader
from . import importers
from .tiers import ENTITY_SETS, KEY_FIELDS, TIER_MAP

__all__ = ["SFAdapter", "SFODataClient", "BatchLoader", "importers",
           "ENTITY_SETS", "KEY_FIELDS", "TIER_MAP"]

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

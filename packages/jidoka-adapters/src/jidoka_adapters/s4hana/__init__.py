"""S/4HANA adapter. Certified against S/4HANA 2023 (OP) / 2402 (Cloud) API hub content.

Extraction is injected (live OData client or fixture) so the core is testable offline;
apply is dry-run by default — nothing writes without an explicit armed target + ledger snapshot.

The tier_map is the honest declaration: S/4 splits cleanly into master data with real published
write APIs (Tier A), objects only loadable through a file/migration-cockpit run a human executes
(Tier B), and IMG/SPRO customising, which is transported and has no write API at all (Tier C —
see customising.py). Nothing is claimed Tier A because it "should" be writable.
"""
from ..base import Adapter
from .odata import S4ODataClient, S4ODataError
from .customising import (CustomisingChange, CustomisingWriteRefused, CUSTOMISING_OBJECTS,
                          build_customising_apply, is_customising)

__all__ = ["S4Adapter", "S4ODataClient", "S4ODataError", "CustomisingChange",
           "CustomisingWriteRefused", "build_customising_apply", "is_customising",
           "CUSTOMISING_OBJECTS"]

# entity -> OData service that publishes it. Only Tier-A entities need one.
SERVICES = {
    "A_BusinessPartner": "API_BUSINESS_PARTNER",
    "A_CostCenter": "API_COSTCENTER_SRV",
    "A_ProfitCenter": "API_PROFITCENTER_SRV",
    "A_GLAccountInChartOfAccounts": "API_GLACCOUNTINCHARTOFACCOUNTS_SRV",
    "A_Bank": "API_BANKDETAIL_SRV",
    "A_Currency": "API_CURRENCY_SRV",
    "A_Country": "API_COUNTRY_SRV",
    "A_Product": "API_PRODUCT_SRV",
    "A_CostCenterActivityType": "API_COSTCENTERACTIVITYTYPE_SRV",
}

# The key field differs per entity — S/4 has no universal externalCode.
KEY_FIELDS = {
    "A_BusinessPartner": "BusinessPartner",
    "A_CostCenter": "CostCenter",
    "A_ProfitCenter": "ProfitCenter",
    "A_GLAccountInChartOfAccounts": "GLAccount",
    "A_Bank": "BankInternalID",
    "A_Currency": "Currency",
    "A_Country": "Country",
    "A_Product": "Product",
    "A_CostCenterActivityType": "ActivityType",
}


class S4Adapter(Adapter):
    product = "S4HANA"
    release = "S/4HANA 2023"

    def __init__(self, fetch=None, client: S4ODataClient | None = None):
        # callable(system, entity) -> list[dict]; a live client is just the fetcher it exposes
        self._fetch = fetch or (client.fetcher(lambda e: SERVICES.get(e, e)) if client else None)

    def tier_map(self) -> dict:
        """A = published write API. B = file/migration-cockpit load a human runs.
        C = IMG/SPRO customising, transported — no write API exists, and none will be faked."""
        return {
            # --- A: SAP publishes a writable OData service for these on the API Business Hub ---
            "A_BusinessPartner": "A",                 # API_BUSINESS_PARTNER (POST/PATCH)
            "A_CostCenter": "A",                      # API_COSTCENTER_SRV
            "A_ProfitCenter": "A",                    # API_PROFITCENTER_SRV
            "A_GLAccountInChartOfAccounts": "A",      # API_GLACCOUNTINCHARTOFACCOUNTS_SRV
            "A_Bank": "A",                            # API_BANKDETAIL_SRV
            "A_Currency": "A",                        # API_CURRENCY_SRV
            "A_Country": "A",                         # API_COUNTRY_SRV
            "A_Product": "A",                         # API_PRODUCT_SRV
            "A_CostCenterActivityType": "A",          # API_COSTCENTERACTIVITYTYPE_SRV

            # --- B: no write API; loaded from a file through LTMC/LSMW, executed by a human ---
            "COST_CENTER_HIERARCHY": "B",             # standard hierarchy: LTMC object
            "PROFIT_CENTER_GROUP": "B",
            "GL_ACCOUNT_BALANCES": "B",               # opening balances: LTMC / FB01 batch
            "MATERIAL_MASTER_EXTENDED": "B",          # plant/valuation views: LTMC
            "CUSTOMER_VENDOR_OPEN_ITEMS": "B",
            "ASSET_MASTER_LEGACY": "B",               # AS91 takeover: migration cockpit only

            # --- C: IMG/SPRO customising — client-dependent, transported, no API. ---
            "T001": "C",       # OX02 company code
            "T001B": "C",      # OB52 posting periods
            "T003": "C",       # OBA7 document types
            "T007A": "C",      # OBQ1 tax codes
            "T030": "C",       # OBYC account determination
            "T880": "C",       # OX15 company
            "TKA01": "C",      # OX06 controlling area
            "V_T093B": "C",    # OAOA depreciation areas
            "V_TVAK": "C",     # VOV8 sales document types
            "V_T156": "C",     # OMJJ movement types
            "NUMBER_RANGE_INTERVAL": "C",   # SNRO/SNUM — client-local, not transported, still no API
            "AUTH_ROLE_PFCG": "C",          # PFCG role build
            "WORKFLOW_CONFIG_SWDD": "C",
        }

    def extract(self, system, entity: str) -> list[dict]:
        if not self._fetch:
            raise RuntimeError("No fetcher configured — inject live OData client or fixture.")
        return self._fetch(system, entity)

    def key_field(self, entity: str) -> str:
        return KEY_FIELDS.get(entity, "ID")

    def build_apply(self, ir) -> dict:
        tier = ir.tier
        if is_customising(ir):  # a transported object never reaches the write path, whatever tier it claims
            return build_customising_apply(ir)
        if tier == "A":
            service = SERVICES.get(ir.object)
            if not service:
                raise S4ODataError(
                    f"{ir.object} is tier A but no OData service is declared for it — "
                    f"the tier_map is lying, fix it rather than guessing a URL.")
            return {"kind": "odata_batch", "system": ir.system_binding, "dry_run": True,
                    "service": service,
                    "operations": [{"method": "UPSERT", "entity": ir.object, "payload": ir.intent}]}
        if tier == "B":
            return {"kind": "import_file", "system": ir.system_binding,
                    "artefact": {"entity": ir.object, "rows": [ir.intent]},
                    "human_step": f"Load via Migration Cockpit (LTMC) -> {ir.object}. "
                                  f"Simulate first, then transfer. "
                                  f"Ledger checkpoint required before and after."}
        return {"kind": "instruction_sheet", "system": ir.system_binding,
                "steps": [f"1. Capture before-state export of {ir.object} (snapshot to ledger).",
                          f"2. Apply {ir.object} change per attached spec: {ir.intent}",
                          "3. JIDOKA re-extracts and diffs; do not proceed until diff report is green."]}

    def diff(self, before: list[dict], after: list[dict], key: str = "ID") -> dict:
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
        field = self.key_field(ir.object)
        key = ir.intent.get(field)
        live = next((r for r in live_state if r.get(field) == key), None)
        if live is None:
            return {"status": "MISSING", "key": key, "key_field": field}
        drift = {f: {"intent": v, "live": live.get(f)} for f, v in ir.intent.items()
                 if not isinstance(v, dict) and live.get(f) != v}
        return {"status": "MATCH" if not drift else "DRIFT", "key": key, "key_field": field,
                "drift": drift}

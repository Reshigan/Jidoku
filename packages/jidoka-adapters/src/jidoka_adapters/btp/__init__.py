"""SAP BTP adapter. Declarative by nature, and tier-honest about what that means.

BTP is not a system with a configuration client; it is a control plane with REST APIs and a
published Terraform provider. That splits the tier map differently from every other product here:

  **Tier A** — the account APIs that genuinely accept a write and read the result straight back:
  role collection membership, destinations. Small, and real.

  **Tier B** — everything the Terraform provider declares. JIDOKA emits the HCL, a person runs
  `terraform plan`, reads the diff and applies under their own credentials, and JIDOKA verifies
  afterwards by reading the BTP APIs. Not Tier A, deliberately: applying the plan would mean
  JIDOKA either owns the customer's Terraform state — becoming the only thing that may ever touch
  the subaccount — or applies without it and destroys what it did not know about (see
  terraform.py).

  **Tier C** — cockpit-only. A handful of things have no API and no provider resource, and the
  honest answer is a person, an instruction sheet and an attestation.

Nothing is Tier A because it ought to be. The bar is: the product publishes a write path, and this
adapter can name it.
"""
from ..base import Adapter, AdapterError
from .terraform import PROVIDER, RESOURCES, TerraformRefused, declaration, plan_sheet

__all__ = ["BTPAdapter", "BTPError", "TerraformRefused", "RESOURCES", "PROVIDER",
           "declaration", "plan_sheet"]


class BTPError(AdapterError): ...


#: entity -> the BTP API that writes it. Only Tier A needs one, and only these have one.
WRITE_APIS = {
    "ROLE_COLLECTION_MEMBER": "Authorization & Trust Management (XSUAA) role collection API",
    "DESTINATION": "Destination service configuration API (v1)",
}

#: entity -> the API this adapter reads it back through. A Terraform-declared object is still
#: readable: the provider reads through these same APIs, which is what makes Tier B honest here
#: rather than a hand-off into the dark.
READ_APIS = {
    "ROLE_COLLECTION_MEMBER": "XSUAA role collection API",
    "DESTINATION": "Destination service configuration API (v1)",
    "SUBACCOUNT": "Accounts service (subaccounts)",
    "ENTITLEMENT": "Entitlements service (assignments)",
    "ROLE_COLLECTION": "XSUAA role collection API",
    "TRUST_CONFIGURATION": "Accounts service (trust configurations)",
    "SERVICE_INSTANCE": "Service Manager (instances)",
    "SERVICE_BINDING": "Service Manager (bindings)",
    "ENVIRONMENT_INSTANCE": "Accounts service (environment instances)",
}

#: The key each entity answers to. BTP has no universal external code either.
KEY_FIELDS = {
    "SUBACCOUNT": "subdomain",
    "ENTITLEMENT": "service_name",
    "ROLE_COLLECTION": "name",
    "ROLE_COLLECTION_MEMBER": "role_collection_name",
    "TRUST_CONFIGURATION": "origin",
    "SERVICE_INSTANCE": "name",
    "SERVICE_BINDING": "name",
    "ENVIRONMENT_INSTANCE": "environment_type",
    "DESTINATION": "Name",
}


class BTPAdapter(Adapter):
    product = "BTP"
    release = "SAP BTP control plane, provider SAP/btp"

    def __init__(self, fetch=None):
        # callable(system, entity) -> list[dict]. Injected, like every other adapter here, so the
        # tier logic is testable without a tenant.
        self._fetch = fetch

    def tier_map(self) -> dict:
        return {
            # --- A: a published API accepts the write and reads it straight back ---
            "ROLE_COLLECTION_MEMBER": "A",
            "DESTINATION": "A",

            # --- B: declared in Terraform, applied by a person, verified afterwards ---
            "SUBACCOUNT": "B",
            "ENTITLEMENT": "B",
            "ROLE_COLLECTION": "B",
            "TRUST_CONFIGURATION": "B",
            "SERVICE_INSTANCE": "B",
            "SERVICE_BINDING": "B",
            "ENVIRONMENT_INSTANCE": "B",

            # --- C: cockpit only. No API, no provider resource, no pretending otherwise ---
            "GLOBAL_ACCOUNT_CONTRACT": "C",   # commercial model, changed with SAP, not by anyone
            "CUSTOM_IDP_BRANDING": "C",       # cockpit-only presentation settings
            "USAGE_ANALYTICS_OPT_IN": "C",
        }

    def write_target(self, entity: str) -> str | None:
        return WRITE_APIS.get(entity)

    def unverifiable(self) -> dict:
        """Derived from READ_APIS, so an entity becomes confirmable the day a read is added — the
        two cannot drift. Tier B is *not* here: the provider reads through the same APIs, which is
        what makes the hand-off honest rather than a hand-off into the dark."""
        return {entity: "cockpit-only: SAP publishes no API and the Terraform provider declares no "
                        "resource for it, so JIDOKA cannot read it back and a named person has to "
                        "attest instead."
                for entity in self.tier_map() if entity not in READ_APIS}

    def key_field(self, entity: str) -> str:
        return KEY_FIELDS.get(entity, "name")

    def extract(self, system, entity: str) -> list[dict]:
        if not self._fetch:
            raise RuntimeError("No fetcher configured — inject a live BTP client or a fixture.")
        return self._fetch(system, entity)

    def build_apply(self, ir) -> dict:
        tier = self.tier_map().get(ir.object, ir.tier)
        if tier != ir.tier:
            raise BTPError(
                f"{ir.object} is declared tier {ir.tier} in the IR and this adapter knows it as "
                f"tier {tier}. One of the two is wrong, and guessing which would be the platform "
                f"deciding what a product permits.")
        if tier == "A":
            api = WRITE_APIS.get(ir.object)
            if not api:
                raise BTPError(f"{ir.object} is tier A and this adapter can name no write API for "
                               f"it — the tier map is lying, fix it rather than inventing a URL.")
            return {"kind": "btp_api_call", "system": ir.system_binding, "dry_run": True,
                    "api": api, "key_field": self.key_field(ir.object),
                    "operations": [{"method": "UPSERT", "entity": ir.object, "payload": ir.intent}]}
        if tier == "B":
            return plan_sheet(ir, ir.system_binding)
        return {"kind": "instruction_sheet", "system": ir.system_binding,
                "steps": [f"1. Capture the current state of {ir.object} (snapshot to ledger).",
                          f"2. In the BTP cockpit, apply {ir.object} per attached spec: {ir.intent}",
                          "3. Nothing can read this back. A named person attests, and the "
                          "assurance statement records it as a person's word, not a check."]}

    def verify(self, ir, live_state: list[dict]) -> dict:
        field = self.key_field(ir.object)
        key = ir.intent.get(field)
        live = next((r for r in live_state if r.get(field) == key), None)
        if live is None:
            return {"status": "MISSING", "key": key, "key_field": field}
        # externalCode is the IR's own name for the record, not a field of the BTP object. BTP
        # has no universal external code, so comparing it against live state would report every
        # object as drifted for a difference that is not about the customer's tenant at all.
        drift = {f: {"intent": v, "live": live.get(f)} for f, v in ir.intent.items()
                 if f != "externalCode" and not isinstance(v, dict) and live.get(f) != v}
        return {"status": "MATCH" if not drift else "DRIFT", "key": key, "key_field": field,
                "drift": drift}

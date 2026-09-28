"""BTP configuration is declarative infrastructure, and JIDOKA writes the declaration.

SAP publishes a Terraform provider for BTP, and the honest consequence is that most of a
subaccount's configuration is not a write JIDOKA should make. It is a plan somebody applies, with
their own credentials, against their own state file.

That is precisely the Tier-B bargain from ADR-0003 — an artefact a person executes and JIDOKA
confirms afterwards — and it is a better fit than Tier A for a specific reason: Terraform state.
If JIDOKA applied the plan, either it owns the state file (and becomes the only thing that may
ever touch the subaccount) or it applies without state (and destroys whatever it did not know
about). Neither is a thing to do to a customer's platform tenant. So the artefact is the plan,
the human runs it, and the verification is a read of the BTP APIs afterwards.

The HCL emitted here is deliberately plain: named resources, explicit values, no modules, no
generated variables. A consultant reads it, a reviewer reviews it, and `terraform plan` shows the
diff before anything happens.
"""

#: IR object -> the provider resource that declares it. An object with no entry here is not
#: something this adapter knows how to declare, and it says so rather than emitting plausible HCL.
RESOURCES = {
    "ENTITLEMENT": "btp_subaccount_entitlement",
    "SUBACCOUNT": "btp_subaccount",
    "ROLE_COLLECTION": "btp_subaccount_role_collection",
    "TRUST_CONFIGURATION": "btp_subaccount_trust_configuration",
    "SERVICE_INSTANCE": "btp_subaccount_service_instance",
    "SERVICE_BINDING": "btp_subaccount_service_binding",
    "ENVIRONMENT_INSTANCE": "btp_subaccount_environment_instance",
}

PROVIDER = "SAP/btp"


class TerraformRefused(Exception):
    """This adapter will not emit a declaration it cannot honestly write."""


def _hcl(value, indent: int = 2) -> str:
    """Values as HCL. Deliberately small: strings, numbers, booleans, lists and one level of
    object. Anything deeper is a sign the IR is carrying a module, and a module is a thing a
    person writes and reviews, not a thing a config compiler emits."""
    pad = " " * indent
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, list):
        return "[" + ", ".join(_hcl(v, indent) for v in value) + "]"
    if isinstance(value, dict):
        inner = "\n".join(f"{pad}  {k} = {_hcl(v, indent + 2)}" for k, v in sorted(value.items()))
        return "{\n" + inner + f"\n{pad}}}"
    raise TerraformRefused(f"{type(value).__name__} has no HCL form this adapter will invent.")


def declaration(ir) -> str:
    """One resource block for one IR record. The name is the record's own external code, so a
    plan's diff names the same thing the ledger does."""
    resource = RESOURCES.get(ir.object)
    if not resource:
        raise TerraformRefused(
            f"{ir.object} has no declared BTP provider resource. This adapter emits a plan a "
            f"person applies to a customer's tenant; guessing a resource type would put a "
            f"plausible-looking block in front of a reviewer who would have no way to tell.")
    name = ir.external_code or ir.intent.get("externalCode") or "unnamed"
    fields = {k: v for k, v in ir.intent.items() if k != "externalCode"}
    body = "\n".join(f"  {k} = {_hcl(v)}" for k, v in sorted(fields.items()))
    return f'resource "{resource}" "{name}" {{\n{body}\n}}\n'


def plan_sheet(ir, system_binding: str) -> dict:
    """The artefact and the steps. Plan before apply, always: the value of a declarative tool is
    that somebody sees the diff first, and a sheet that said "apply" would throw that away."""
    return {
        "kind": "import_file",
        "system": system_binding,
        "artefact": {"filename": f"{(ir.external_code or ir.object).lower()}.tf",
                     "provider": PROVIDER,
                     "hcl": declaration(ir)},
        "human_step": (
            f"1. Add the attached .tf to the subaccount's Terraform configuration.\n"
            f"2. `terraform plan` and read the diff. JIDOKA has not seen your state file and "
            f"cannot know what else the plan will touch — that is the step this bargain exists "
            f"for.\n"
            f"3. `terraform apply` under your own credentials, with a ledger snapshot taken "
            f"first (invariant 6).\n"
            f"4. Tell JIDOKA it is done. It will read {ir.object} back from the BTP APIs and "
            f"diff it against signed intent."),
    }

"""IMG/SPRO customising is transported, not written.

An S/4 customising object lives in a client-dependent table maintained through an IMG activity
(SM30/SPRO view cluster) and leaves the client only inside a transport request. There is no
supported API that writes it, and JIDOKA never invents one: no RPA, no DOM automation, no
direct table write (ADR-0003). So the only artefact this module can produce is an instruction
sheet bound to a transport request, for a named human to execute and a second human to release.

This is why the S/4 tier_map declares customising objects Tier C. Anything routed here that
claims Tier A is a bug in the IR, and `build_customising_apply` refuses it loudly rather than
degrading into a write.
"""
from dataclasses import dataclass, field

# IMG activity -> the table/view it maintains. Transport-only, by SAP's own design.
# Not exhaustive: an unlisted object is still customising if it carries an img_activity.
CUSTOMISING_OBJECTS = {
    "T001": "OX02 — Define Company Code",
    "T001B": "OB52 — Open and Close Posting Periods",
    "T003": "OBA7 — Define Document Types",
    "T007A": "OBQ1 — Define Tax Codes / Tax Procedure",
    "T030": "OBYC — Automatic Account Determination",
    "T880": "OX15 — Define Company (consolidation)",
    "TKA01": "OX06 — Maintain Controlling Area",
    "V_T093B": "OAOA — Define Asset Depreciation Areas",
    "V_TVAK": "VOV8 — Define Sales Document Types",
    "V_T156": "OMJJ — Define Movement Types",
}


class CustomisingWriteRefused(Exception):
    """Raised when a caller asks for a direct write to a transported customising object."""


@dataclass
class CustomisingChange:
    """One IMG customising change. It is never applied by JIDOKA — it is specified, transported,
    and then verified by re-extraction."""
    img_activity: str
    table: str
    target_client: str
    values: dict = field(default_factory=dict)
    transport_request: str | None = None   # e.g. DEVK900123 — assigned by the human who records it
    description: str = ""

    @property
    def is_transported(self) -> bool:
        """Client-dependent customising is transported. A local-only client (SCC4 'no changes
        recorded') is still not writable by API, so this is about evidence, not about a shortcut."""
        return True

    def instruction_sheet(self, system_binding: str) -> dict:
        tr = self.transport_request or "<open a transport request and record it here>"
        return {
            "kind": "instruction_sheet",
            "system": system_binding,
            "transport_request": self.transport_request,
            "customising": {"img_activity": self.img_activity, "table": self.table,
                            "target_client": self.target_client,
                            "known_as": CUSTOMISING_OBJECTS.get(self.table, "unlisted IMG object")},
            "steps": [
                f"1. Capture before-state export of {self.table} in client {self.target_client} "
                f"(snapshot to ledger — invariant 6 requires it before any change).",
                f"2. Open IMG activity {self.img_activity} in the configuration client and record "
                f"the change to transport request {tr}.",
                f"3. Apply the values per attached spec: {self.values}",
                f"4. Release {tr} and import it through the transport path to "
                f"{self.target_client}. Release requires a second named approver (invariant 4).",
                "5. JIDOKA re-extracts and diffs; do not proceed until the diff report is green.",
            ],
        }


def is_customising(ir) -> bool:
    """True when the IR record targets a transported IMG object — by table or by declared activity."""
    intent = getattr(ir, "intent", {}) or {}
    return bool(intent.get("img_activity")) or ir.object in CUSTOMISING_OBJECTS


def build_customising_apply(ir) -> dict:
    """The only apply shape a customising object may produce. Refuses any direct write."""
    if not is_customising(ir):
        raise CustomisingWriteRefused(
            f"{ir.object} is not a customising object — route it through the adapter's tier_map.")
    if ir.tier != "C":
        raise CustomisingWriteRefused(
            f"{ir.object} is IMG customising (transported, not writable by API) but the IR claims "
            f"tier {ir.tier!r}. JIDOKA will not build a direct write for a transported object.")
    intent = dict(ir.intent or {})
    change = CustomisingChange(
        img_activity=intent.pop("img_activity", CUSTOMISING_OBJECTS.get(ir.object, ir.object)),
        table=intent.pop("table", ir.object),
        target_client=intent.pop("target_client", "?"),
        transport_request=intent.pop("transport_request", None),
        description=intent.pop("description", ""),
        values=intent,
    )
    return change.instruction_sheet(ir.system_binding)

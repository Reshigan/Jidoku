"""Adapter contract: every SAP product implements exactly this surface.
The tier_map is the honest declaration of what the product's interfaces permit."""
from abc import ABC, abstractmethod


class AdapterError(Exception):
    """An adapter refusing to act, as distinct from an adapter breaking.

    Raised when the IR asks for something the product's interfaces cannot honestly deliver — a
    tier-A object with no declared entity set, a payload the substrate would reject. Every product's
    error type inherits this so the API can map refusals to 422 once, rather than growing an
    `except` clause per adapter and returning a 500 the first time somebody adds a new one.
    """


class Adapter(ABC):
    product: str = "?"

    @abstractmethod
    def tier_map(self) -> dict: ...

    def write_target(self, entity: str) -> str | None:
        """The named thing this adapter writes `entity` through — an entity set, a service — or
        None where the product publishes no write path. A Tier-A entity without one is a tier map
        that lies, and `audit_tier_map` says so before anybody tries to spend it."""
        return None

    def unverifiable(self) -> dict:
        """entity -> why this adapter cannot read it back, for the entities it cannot.

        ADR-0003 makes Tier B and C honest by pairing a human instruction sheet with an
        extract-diff: a person does the work and JIDOKA confirms it. That bargain needs a read
        path. Some objects have none — an SF Provisioning switch, an S/4 IMG table with no
        published service — and for those the platform must say so rather than wait forever for a
        confirmation it can never make (ADR-0022). Declaring the gap is the honest move; hiding it
        turns an unconfirmable change into one that merely looks outstanding.
        """
        return {}

    def verifiable(self, entity: str) -> bool:
        return entity not in self.unverifiable()

    #: Where this product keeps its own record of who changed what, if it keeps one, and what it
    #: is called. Declared rather than assumed: an adapter that cannot read one must say so, or a
    #: reconciliation finding nothing reads as "nothing happened outside the platform" when it
    #: means "I cannot see" (ADR-0044).
    change_log_entity: str | None = None

    def change_log(self, system, since: str = "") -> list[dict] | None:
        """The product's own change log, normalised to `{object, changed_by, ts, detail}`.

        None where the product publishes no readable log. Every product spells this differently —
        SuccessFactors has Change Audit, S/4 has change documents — so the translation belongs
        here, with the product, and never in the reconciliation.
        """
        return None

    def cannot_read_changes(self) -> str:
        """Why not, for an adapter that returns None. Printed where the answer would otherwise be
        an empty list that reads like a clean bill of health."""
        return (f"{self.product}: this adapter reads no change log, so it cannot tell a system "
                f"nobody touched from one it cannot see into.")
    @abstractmethod
    def extract(self, system, entity: str) -> list[dict]: ...
    @abstractmethod
    def build_apply(self, ir_record) -> dict:
        """Tier A -> API payload; Tier B -> file artefact; Tier C -> human instruction sheet."""
    @abstractmethod
    def verify(self, ir_record, live_state: list[dict]) -> dict: ...


def audit_tier_map(adapter: Adapter) -> dict:
    """What an adapter's own declaration admits about itself.

    Two findings, and they are not the same kind of thing:

    `lying` — Tier A with no write target. The adapter claims the product publishes a write path
    and cannot name it, so an armed step against it would fail at the substrate with a live
    target already armed. This is a defect in the map.

    `unconfirmable` — Tier B or C the adapter cannot read back. Not a defect: the product really
    does keep that object behind a UI with no read API. It is a limit, and it has to be visible,
    because the platform's promise for Tier B and C is that a person does the work and JIDOKA
    checks it (ADR-0003). Where it cannot check, somebody has to attest instead.
    """
    tiers = adapter.tier_map()
    unverifiable = adapter.unverifiable()
    return {
        "product": adapter.product,
        "lying": sorted(e for e, tier in tiers.items()
                        if tier == "A" and not adapter.write_target(e)),
        "unconfirmable": {e: unverifiable[e] for e in sorted(unverifiable) if e in tiers},
        "counts": {t: sum(1 for x in tiers.values() if x == t) for t in "ABC"},
    }

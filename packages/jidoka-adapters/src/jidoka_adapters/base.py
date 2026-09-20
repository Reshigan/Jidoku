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
